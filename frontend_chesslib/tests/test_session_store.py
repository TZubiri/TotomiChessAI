import unittest

from frontend_chesslib.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_enforces_session_cap(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session()
        with self.assertRaises(RuntimeError):
            store.create_session()

    def test_rejects_bad_uci(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session()
        with self.assertRaises(ValueError):
            store.append_move(session.session_id, "hello")


if __name__ == "__main__":
    unittest.main()
