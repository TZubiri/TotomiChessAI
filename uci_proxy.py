import argparse
import subprocess
import sys
import threading
from datetime import datetime


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _log_line(log_file, direction, line):
    log_file.write(f"{_timestamp()} {direction} {line}\n")
    log_file.flush()


def _pump_engine_stdout(engine_process, log_file, finished_event):
    if engine_process.stdout is None:
        finished_event.set()
        return

    try:
        for raw_line in engine_process.stdout:
            line = raw_line.rstrip("\n")
            _log_line(log_file, "<<", line)
            sys.stdout.write(raw_line)
            sys.stdout.flush()
    finally:
        finished_event.set()


def run_proxy(log_path, engine_command):
    exit_code = 1
    with open(log_path, "a", encoding="utf-8") as log_file:
        _log_line(log_file, "--", f"Starting engine: {' '.join(engine_command)}")

        engine_process = subprocess.Popen(
            engine_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        finished_event = threading.Event()
        stdout_thread = threading.Thread(
            target=_pump_engine_stdout,
            args=(engine_process, log_file, finished_event),
            daemon=True,
        )
        stdout_thread.start()

        try:
            if engine_process.stdin is not None:
                for raw_line in sys.stdin:
                    line = raw_line.rstrip("\n")
                    _log_line(log_file, ">>", line)
                    try:
                        engine_process.stdin.write(raw_line)
                        engine_process.stdin.flush()
                    except BrokenPipeError:
                        break
        finally:
            if engine_process.stdin is not None:
                try:
                    engine_process.stdin.close()
                except OSError:
                    pass

            finished_event.wait(timeout=5.0)
            try:
                exit_code = engine_process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                engine_process.kill()
                exit_code = engine_process.wait(timeout=5.0)

            stdout_thread.join(timeout=1.0)
            _log_line(log_file, "--", f"Engine exited with code {exit_code}")
    return exit_code


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="UCI proxy that logs stdin/stdout traffic")
    parser.add_argument("--log", default="uci_proxy.log", help="Path to append UCI traffic logs")
    parser.add_argument("engine_command", nargs=argparse.REMAINDER, help="Engine command after '--'")
    args = parser.parse_args(argv)
    command = args.engine_command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("Missing engine command. Example: -- wsl.exe -d Ubuntu --cd /home/opencode/chess -e python3 chess_uci.py d4_pawnwise")
    return args.log, command


def main(argv=None):
    log_path, engine_command = _parse_args(argv)
    return run_proxy(log_path, engine_command)


if __name__ == "__main__":
    raise SystemExit(main())
