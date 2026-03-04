from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chess import (  # noqa: E402
    Board,
    RANDOM_AI_PROFILE,
    apply_ai_move,
    apply_user_move,
    get_game_status,
)


COLORS = ("white", "black")
DEFAULT_AI_PROFILE = dict(RANDOM_AI_PROFILE)


def _board_to_matrix(board: Board) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in range(7, -1, -1):
        rendered_row: List[str] = []
        for col in range(8):
            piece = board.get_piece_at((col, row))
            rendered_row.append(piece.symbol if piece is not None else ".")
        rows.append(rendered_row)
    return rows


def starting_board_matrix() -> List[List[str]]:
    return _board_to_matrix(Board())


@dataclass
class Session:
    session_id: str
    board: Board
    user_color: str
    ai_color: str
    ai_profile: dict
    moves: List[str] = field(default_factory=list)
    status: str = "in_progress"
    status_reason: Optional[str] = None
    winner: Optional[str] = None
    last_ai_move: Optional[str] = None

    @property
    def turn(self) -> str:
        return "white" if self.board.total_halfmoves_played % 2 == 0 else "black"

    @property
    def user_to_move(self) -> bool:
        return self.status == "in_progress" and self.turn == self.user_color

    def to_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "board": _board_to_matrix(self.board),
            "moves": list(self.moves),
            "turn": self.turn,
            "user_color": self.user_color,
            "ai_color": self.ai_color,
            "user_to_move": self.user_to_move,
            "status": self.status,
            "status_reason": self.status_reason,
            "winner": self.winner,
            "last_ai_move": self.last_ai_move,
        }


class SessionStore:
    def __init__(self, max_sessions: int = 4) -> None:
        self.max_sessions = max_sessions
        self._sessions: Dict[str, Session] = {}
        self._lock = Lock()

    def _refresh_status(self, session: Session) -> None:
        status_payload = get_game_status(session.board, session.turn)
        session.status = status_payload["state"]
        session.status_reason = status_payload["reason"]
        session.winner = status_payload["winner"]

    def _apply_ai_turn_if_needed(self, session: Session) -> None:
        if session.status != "in_progress":
            return
        if session.turn != session.ai_color:
            return
        _, _, _, ai_move_text = apply_ai_move(
            session.board,
            session.ai_color,
            session.ai_profile,
            record=False,
        )
        session.last_ai_move = ai_move_text
        session.moves.append(ai_move_text)
        self._refresh_status(session)

    def create_session(self, forced_user_color: Optional[str] = None) -> Session:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError("session limit reached")

            user_color = forced_user_color if forced_user_color in COLORS else random.choice(COLORS)
            ai_color = "black" if user_color == "white" else "white"
            session = Session(
                session_id=uuid4().hex[:8],
                board=Board(),
                user_color=user_color,
                ai_color=ai_color,
                ai_profile=DEFAULT_AI_PROFILE,
            )
            self._refresh_status(session)
            self._apply_ai_turn_if_needed(session)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            return session

    def apply_user_move(self, session_id: str, move_text: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            if session.status != "in_progress":
                raise ValueError("game is already finished")
            if session.turn != session.user_color:
                raise ValueError("wait for your turn")

            _, _, normalized_move = apply_user_move(
                session.board,
                session.user_color,
                move_text.strip().lower(),
                record=False,
            )
            session.moves.append(normalized_move)
            session.last_ai_move = None
            self._refresh_status(session)
            self._apply_ai_turn_if_needed(session)
            return session
