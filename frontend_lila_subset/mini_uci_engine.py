#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chess import (  # noqa: E402
    Board,
    Pawn,
    apply_coordinate_move,
    choose_ai_move,
    get_ai_profiles,
    position_to_square,
)


ENGINE_NAME = "OpenCode Mini UCI"
ENGINE_AUTHOR = "OpenCode"


def _opponent(color: str) -> str:
    return "black" if color == "white" else "white"


def _profile_by_id(profile_id: str) -> dict:
    profiles = get_ai_profiles()
    by_id = {profile["id"]: profile for profile in profiles}
    if profile_id in by_id:
        return by_id[profile_id]
    return by_id.get("d0_random", profiles[0])


def _parse_position_tokens(tokens: List[str]) -> tuple[Board, str]:
    if not tokens:
        raise ValueError("position requires arguments")
    if tokens[0] != "startpos":
        raise ValueError("only 'startpos' positions are supported")

    board = Board()
    active_color = "white"

    if len(tokens) == 1:
        return board, active_color

    if tokens[1] != "moves":
        raise ValueError("expected 'moves' after 'startpos'")

    for move_text in tokens[2:]:
        apply_coordinate_move(board, active_color, move_text, record=False)
        active_color = _opponent(active_color)

    return board, active_color


def _move_to_uci(board: Board, move: tuple[tuple[int, int], tuple[int, int]]) -> str:
    from_pos, to_pos = move
    text = f"{position_to_square(from_pos)}{position_to_square(to_pos)}"
    piece = board.get_piece_at(from_pos)
    if isinstance(piece, Pawn) and to_pos[1] in (0, 7):
        return f"{text}q"
    return text


class MiniUCIEngine:
    def __init__(self) -> None:
        profile_id = os.environ.get("LILA_UCI_PROFILE", "d0_random")
        self.default_depth = max(1, int(os.environ.get("LILA_UCI_DEPTH", "1")))
        self.profile = dict(_profile_by_id(profile_id))
        self.random_profile = dict(_profile_by_id("d0_random"))
        self.board = Board()
        self.active_color = "white"

    def _send(self, line: str) -> None:
        sys.stdout.write(f"{line}\n")
        sys.stdout.flush()

    def _handle_uci(self) -> None:
        self._send(f"id name {ENGINE_NAME}")
        self._send(f"id author {ENGINE_AUTHOR}")
        self._send("uciok")

    def _handle_position(self, line: str) -> None:
        tokens = line.split()[1:]
        try:
            self.board, self.active_color = _parse_position_tokens(tokens)
        except ValueError as exc:
            self._send(f"info string position parse error: {exc}")

    def _handle_go(self, line: str) -> None:
        depth = self.default_depth
        tokens = line.split()
        for index, token in enumerate(tokens):
            if token == "depth" and index + 1 < len(tokens):
                try:
                    depth = max(1, int(tokens[index + 1]))
                except ValueError:
                    pass
                break

        profile = dict(self.profile)
        profile["plies"] = max(0, depth)
        try:
            chosen_move = choose_ai_move(self.board, self.active_color, profile)
        except Exception:
            fallback_profile = dict(self.random_profile)
            fallback_profile["plies"] = 0
            try:
                chosen_move = choose_ai_move(self.board, self.active_color, fallback_profile)
            except Exception:
                legal_moves = self.board.get_legal_moves_for_color(self.active_color)
                chosen_move = legal_moves[0] if legal_moves else None
        if chosen_move is None:
            self._send("bestmove 0000")
            return

        self._send(f"bestmove {_move_to_uci(self.board, chosen_move)}")

    def run(self) -> None:
        while True:
            raw = sys.stdin.readline()
            if not raw:
                break
            line = raw.strip()
            if not line:
                continue

            if line == "uci":
                self._handle_uci()
                continue
            if line == "isready":
                self._send("readyok")
                continue
            if line.startswith("position "):
                self._handle_position(line)
                continue
            if line.startswith("go"):
                self._handle_go(line)
                continue
            if line in {"ucinewgame", "stop", "ponderhit"}:
                continue
            if line in {"quit", "exit"}:
                break


def main() -> None:
    engine = MiniUCIEngine()
    engine.run()


if __name__ == "__main__":
    main()
