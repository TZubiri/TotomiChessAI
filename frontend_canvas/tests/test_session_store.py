import unittest

from frontend_canvas.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_rejects_more_than_four_sessions(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session()
        with self.assertRaises(RuntimeError):
            store.create_session()

    def test_turn_validation(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session()
        with self.assertRaises(ValueError):
            store.apply_move(session.session_id, "e7", "e6")


if __name__ == "__main__":
    unittest.main()
