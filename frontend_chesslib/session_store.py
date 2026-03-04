from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import Dict, List
from uuid import uuid4


def _is_uci(move: str) -> bool:
    move = move.strip().lower()
    if len(move) not in (4, 5):
        return False
    if move[0] not in "abcdefgh" or move[2] not in "abcdefgh":
        return False
    if move[1] not in "12345678" or move[3] not in "12345678":
        return False
    if len(move) == 5 and move[4] not in "qrbn":
        return False
    return True


@dataclass
class Session:
    session_id: str
    moves: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    def to_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "moves": list(self.moves),
            "turn": "white" if len(self.moves) % 2 == 0 else "black",
            "created_at": self.created_at,
            "updated_at": self.updated_at,
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
            session = Session(session_id=uuid4().hex[:8])
            self._sessions[session.session_id] = session
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

    def append_move(self, session_id: str, uci_move: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            move = uci_move.strip().lower()
            if not _is_uci(move):
                raise ValueError("invalid uci move")
            session.moves.append(move)
            session.updated_at = time()
            return session
