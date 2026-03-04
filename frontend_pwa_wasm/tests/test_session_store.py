import unittest

from frontend_pwa_wasm.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_session_limit(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session()
        with self.assertRaises(RuntimeError):
            store.create_session()

    def test_move_updates_turn(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session()
        store.apply_move(session.session_id, "e2", "e4")
        updated = store.get(session.session_id)
        self.assertEqual(updated.turn, "black")


if __name__ == "__main__":
    unittest.main()
