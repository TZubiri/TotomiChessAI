import unittest

from frontend_lila_subset.session_store import GameStore


class GameStoreTests(unittest.TestCase):
    def test_enforces_game_cap(self) -> None:
        store = GameStore(max_games=4)
        for _ in range(4):
            store.open_challenge()
        with self.assertRaises(RuntimeError):
            store.open_challenge()

    def test_rejects_invalid_uci(self) -> None:
        store = GameStore(max_games=1)
        game = store.open_challenge()
        with self.assertRaises(ValueError):
            store.submit_move(game.game_id, "oops")


if __name__ == "__main__":
    unittest.main()
