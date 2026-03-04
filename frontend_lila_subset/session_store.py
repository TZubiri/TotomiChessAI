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
class Game:
    game_id: str
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

    def to_board_dict(self) -> Dict[str, object]:
        return {
            "id": self.game_id,
            "status": self.status,
            "statusReason": self.status_reason,
            "winner": self.winner,
            "turn": self.turn,
            "moves": " ".join(self.moves),
            "moveList": list(self.moves),
            "board": _board_to_matrix(self.board),
            "userColor": self.user_color,
            "aiColor": self.ai_color,
            "userToMove": self.user_to_move,
            "lastAiMove": self.last_ai_move,
        }


class GameStore:
    def __init__(self, max_games: int = 4) -> None:
        self.max_games = max_games
        self._games: Dict[str, Game] = {}
        self._lock = Lock()

    def _refresh_status(self, game: Game) -> None:
        payload = get_game_status(game.board, game.turn)
        game.status = payload["state"]
        game.status_reason = payload["reason"]
        game.winner = payload["winner"]

    def _apply_ai_turn_if_needed(self, game: Game) -> None:
        if game.status != "in_progress":
            return
        if game.turn != game.ai_color:
            return

        _, _, _, ai_move_text = apply_ai_move(
            game.board,
            game.ai_color,
            game.ai_profile,
            record=False,
        )
        game.last_ai_move = ai_move_text
        game.moves.append(ai_move_text)
        self._refresh_status(game)

    def open_challenge(self, forced_user_color: Optional[str] = None) -> Game:
        with self._lock:
            if len(self._games) >= self.max_games:
                raise RuntimeError("game limit reached")

            user_color = forced_user_color if forced_user_color in COLORS else random.choice(COLORS)
            ai_color = "black" if user_color == "white" else "white"
            game = Game(
                game_id=uuid4().hex[:8],
                board=Board(),
                user_color=user_color,
                ai_color=ai_color,
                ai_profile=DEFAULT_AI_PROFILE,
            )
            self._refresh_status(game)
            self._apply_ai_turn_if_needed(game)
            self._games[game.game_id] = game
            return game

    def list_games(self) -> List[Game]:
        with self._lock:
            return list(self._games.values())

    def get_game(self, game_id: str) -> Game:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError(game_id)
            return game

    def submit_user_move(self, game_id: str, uci_move: str) -> Game:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError(game_id)
            if game.status != "in_progress":
                raise ValueError("game is already finished")
            if game.turn != game.user_color:
                raise ValueError("wait for your turn")

            _, _, normalized_move = apply_user_move(
                game.board,
                game.user_color,
                uci_move.strip().lower(),
                record=False,
            )
            game.moves.append(normalized_move)
            game.last_ai_move = None
            self._refresh_status(game)
            self._apply_ai_turn_if_needed(game)
            return game
