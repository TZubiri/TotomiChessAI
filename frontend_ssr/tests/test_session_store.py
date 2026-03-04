import unittest

from frontend_ssr.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_enforces_max_sessions(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session()
        with self.assertRaises(RuntimeError):
            store.create_session()

    def test_applies_move_and_toggles_turn(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session()
        store.apply_move(session.session_id, "e2", "e4")
        updated = store.get(session.session_id)
        self.assertEqual(updated.turn, "black")
        self.assertEqual(updated.board[6][4], ".")
        self.assertEqual(updated.board[4][4], "P")


if __name__ == "__main__":
    unittest.main()
