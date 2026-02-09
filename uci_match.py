#!/usr/bin/env python3
import argparse
import os
import re
import shlex
import select
import subprocess
import time

from chess import Board, apply_coordinate_move, get_game_status


def _opponent(color):
    return "black" if color == "white" else "white"


class UCIProcess:
    def __init__(self, command_text, label):
        self.command_text = command_text
        self.label = label
        self.process = None
        self._read_buffer = ""

    def start(self):
        command = shlex.split(self.command_text)
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def send(self, line):
        if self.process is None or self.process.stdin is None:
            raise RuntimeError(f"{self.label} process is not running")
        self.process.stdin.write(f"{line}\n")
        self.process.stdin.flush()

    def _read_more(self, timeout_seconds):
        if self.process is None or self.process.stdout is None:
            raise RuntimeError(f"{self.label} process is not running")
        fd = self.process.stdout.fileno()
        ready, _, _ = select.select([fd], [], [], timeout_seconds)
        if not ready:
            return ""
        chunk = os.read(fd, 4096)
        if not chunk:
            return ""
        text = chunk.decode("utf-8", errors="replace")
        self._read_buffer += text
        return text

    def read_until_regex(self, pattern, timeout_seconds=10):
        deadline = time.time() + timeout_seconds
        compiled = re.compile(pattern)
        while True:
            match = compiled.search(self._read_buffer)
            if match:
                self._read_buffer = self._read_buffer[match.end() :]
                return match
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(f"{self.label} terminated while waiting for pattern: {pattern}")
            if time.time() >= deadline:
                raise RuntimeError(f"Timeout waiting for pattern from {self.label}: {pattern}")
            self._read_more(0.1)

    def handshake(self):
        self.send("uci")
        try:
            self.read_until_regex(r"\buciok\b", timeout_seconds=5)
        except RuntimeError:
            pass
        self.send("isready")
        self.read_until_regex(r"\breadyok\b", timeout_seconds=20)
        self.send("ucinewgame")

    def bestmove(self, moves, movetime_ms):
        position_line = "position startpos"
        if moves:
            position_line = f"{position_line} moves {' '.join(moves)}"
        self.send(position_line)
        self.send(f"go movetime {movetime_ms}")
        match = self.read_until_regex(r"\bbestmove\s+(\S+)", timeout_seconds=max(10, movetime_ms / 1000.0 + 10))
        return match.group(1)

    def stop(self):
        if self.process is None:
            return
        try:
            self.send("quit")
        except Exception:
            pass
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()


def parse_args():
    parser = argparse.ArgumentParser(description="Run a UCI match between GNU Chess and this engine")
    parser.add_argument(
        "--our-engine",
        default="./chess_uci.sh",
        help="Command used to launch this repository UCI engine",
    )
    parser.add_argument(
        "--gnuchess",
        default="gnuchess --uci",
        help="Command used to launch GNU Chess in UCI mode",
    )
    parser.add_argument(
        "--gnuchess-color",
        choices=["white", "black"],
        default="white",
        help="Which color GNU Chess should play",
    )
    parser.add_argument("--movetime-ms", type=int, default=300, help="Per-move think time in milliseconds")
    parser.add_argument("--max-plies", type=int, default=200, help="Stop after this many plies")
    return parser.parse_args()


def main():
    args = parse_args()

    our_engine = UCIProcess(args.our_engine, "our-engine")
    gnuchess = UCIProcess(args.gnuchess, "gnuchess")
    our_engine.start()
    gnuchess.start()

    white_engine = gnuchess if args.gnuchess_color == "white" else our_engine
    black_engine = our_engine if args.gnuchess_color == "white" else gnuchess
    white_label = "gnuchess" if args.gnuchess_color == "white" else "our-engine"
    black_label = "our-engine" if args.gnuchess_color == "white" else "gnuchess"

    try:
        our_engine.handshake()
        gnuchess.handshake()

        board = Board()
        active_color = "white"
        move_history = []

        for ply in range(1, args.max_plies + 1):
            current_engine = white_engine if active_color == "white" else black_engine
            current_label = white_label if active_color == "white" else black_label
            bestmove = current_engine.bestmove(move_history, args.movetime_ms)
            if bestmove in {"0000", "(none)", "none"}:
                print(f"{current_label} has no move ({bestmove})")
                break

            apply_coordinate_move(board, active_color, bestmove)
            move_history.append(bestmove)
            print(f"ply {ply:3d} {active_color:5s} {current_label:10s} {bestmove}")

            active_color = _opponent(active_color)
            status = get_game_status(board, active_color)
            if status["state"] != "in_progress":
                print(f"Game over: {status}")
                return

        print("Reached move limit")
    finally:
        our_engine.stop()
        gnuchess.stop()


if __name__ == "__main__":
    main()
