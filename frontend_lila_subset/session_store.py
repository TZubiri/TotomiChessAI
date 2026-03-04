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
class Game:
    game_id: str
    status: str = "started"
    moves: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    @property
    def turn(self) -> str:
        return "white" if len(self.moves) % 2 == 0 else "black"

    def to_board_dict(self) -> Dict[str, object]:
        return {
            "id": self.game_id,
            "status": self.status,
            "turn": self.turn,
            "moves": " ".join(self.moves),
            "moveList": list(self.moves),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class GameStore:
    def __init__(self, max_games: int = 4) -> None:
        self.max_games = max_games
        self._games: Dict[str, Game] = {}
        self._lock = Lock()

    def open_challenge(self) -> Game:
        with self._lock:
            if len(self._games) >= self.max_games:
                raise RuntimeError("game limit reached")
            game = Game(game_id=uuid4().hex[:8])
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

    def submit_move(self, game_id: str, uci_move: str) -> Game:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError(game_id)
            move = uci_move.strip().lower()
            if not _is_uci(move):
                raise ValueError("invalid uci move")
            game.moves.append(move)
            game.updated_at = time()
            return game
