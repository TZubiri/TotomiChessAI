from __future__ import annotations

import atexit
import subprocess
import sys
from pathlib import Path
from threading import Lock
from typing import Iterable, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
ENGINE_SCRIPT = Path(__file__).resolve().parent / "mini_uci_engine.py"


class UCIClient:
    def __init__(self, command: Optional[Iterable[str]] = None) -> None:
        self._command = list(command) if command is not None else [sys.executable, str(ENGINE_SCRIPT)]
        self._lock = Lock()
        self._process: subprocess.Popen[str] | None = None
        self._start_process()
        atexit.register(self.close)

    def _start_process(self) -> None:
        self.close()
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(ROOT_DIR),
        )
        self._send("uci")
        self._read_until(lambda line: line == "uciok")
        self._send("isready")
        self._read_until(lambda line: line == "readyok")

    def _ensure_running(self) -> None:
        if self._process is None or self._process.poll() is not None:
            self._start_process()

    def _send(self, line: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("UCI engine process is not available")
        self._process.stdin.write(f"{line}\n")
        self._process.stdin.flush()

    def _read_line(self) -> str:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("UCI engine process is not available")
        line = self._process.stdout.readline()
        if line == "":
            raise RuntimeError("UCI engine process exited unexpectedly")
        return line.strip()

    def _read_until(self, predicate) -> str:
        while True:
            line = self._read_line()
            if predicate(line):
                return line

    def bestmove(self, moves: list[str], depth: int = 1) -> Optional[str]:
        with self._lock:
            self._ensure_running()
            if moves:
                self._send(f"position startpos moves {' '.join(moves)}")
            else:
                self._send("position startpos")
            self._send(f"go depth {max(1, depth)}")

            while True:
                line = self._read_line()
                if not line.startswith("bestmove "):
                    continue
                tokens = line.split()
                if len(tokens) < 2 or tokens[1] == "0000":
                    return None
                return tokens[1]

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None

        try:
            if process.stdin is not None:
                process.stdin.write("quit\n")
                process.stdin.flush()
        except OSError:
            pass

        try:
            process.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            process.kill()
        finally:
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
