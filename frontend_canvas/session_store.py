from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Tuple
from uuid import uuid4


FILES = "abcdefgh"


def _starting_board() -> List[List[str]]:
    return [
        list("rnbqkbnr"),
        list("pppppppp"),
        list("........"),
        list("........"),
        list("........"),
        list("........"),
        list("PPPPPPPP"),
        list("RNBQKBNR"),
    ]


def _square_to_idx(square: str) -> Tuple[int, int]:
    square = square.strip().lower()
    if len(square) != 2 or square[0] not in FILES or square[1] not in "12345678":
        raise ValueError(f"invalid square: {square!r}")
    col = FILES.index(square[0])
    row = 8 - int(square[1])
    return row, col


@dataclass
class Session:
    session_id: str
    board: List[List[str]]
    turn: str
    moves: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "turn": self.turn,
            "moves": list(self.moves),
            "board": [row[:] for row in self.board],
        }


class SessionStore:
    def __init__(self, max_sessions: int = 4) -> None:
        self.max_sessions = max_sessions
        self._sessions: Dict[str, Session] = {}
        self._lock = Lock()

    def create_session(self) -> Session:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError("session limit reached")
            session_id = uuid4().hex[:8]
            session = Session(session_id, _starting_board(), "white", [])
            self._sessions[session_id] = session
            return session

    def list_sessions(self) -> List[Session]:
        with self._lock:
            return list(self._sessions.values())

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            return session

    def apply_move(self, session_id: str, source: str, target: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            src_row, src_col = _square_to_idx(source)
            dst_row, dst_col = _square_to_idx(target)
            piece = session.board[src_row][src_col]
            if piece == ".":
                raise ValueError("empty source square")
            if session.turn == "white" and not piece.isupper():
                raise ValueError("white to move")
            if session.turn == "black" and not piece.islower():
                raise ValueError("black to move")

            session.board[src_row][src_col] = "."
            session.board[dst_row][dst_col] = piece
            session.moves.append(f"{source.lower()}-{target.lower()}")
            session.turn = "black" if session.turn == "white" else "white"
            return session
