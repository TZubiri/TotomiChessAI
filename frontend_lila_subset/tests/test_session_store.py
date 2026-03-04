import unittest
from typing import cast

from frontend_lila_subset.session_store import DeterministicUCIEngine, GameStore


class GameStoreTests(unittest.TestCase):
    def _store(self, max_games: int) -> GameStore:
        return GameStore(max_games=max_games, uci_engine=DeterministicUCIEngine())

    def test_enforces_game_cap(self) -> None:
        store = self._store(max_games=4)
        for _ in range(4):
            store.open_challenge(forced_user_color="white")
        with self.assertRaises(RuntimeError):
            store.open_challenge(forced_user_color="white")

    def test_ai_moves_first_for_black_user(self) -> None:
        store = self._store(max_games=1)
        game = store.open_challenge(forced_user_color="black").to_board_dict()
        self.assertEqual(game["turn"], "black")
        self.assertEqual(len(cast(list[str], game["moveList"])), 1)

    def test_user_move_triggers_ai_reply(self) -> None:
        store = self._store(max_games=1)
        game = store.open_challenge(forced_user_color="white")
        payload = store.submit_user_move(game.game_id, "e2e4").to_board_dict()
        self.assertGreaterEqual(len(cast(list[str], payload["moveList"])), 2)
        self.assertEqual(payload["turn"], "white")


if __name__ == "__main__":
    unittest.main()
