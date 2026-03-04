import unittest
from typing import cast

from frontend_pwa_wasm.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_session_limit(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session(forced_user_color="white")
        with self.assertRaises(RuntimeError):
            store.create_session(forced_user_color="white")

    def test_ai_moves_first_when_user_black(self) -> None:
        store = SessionStore(max_sessions=1)
        payload = store.create_session(forced_user_color="black").to_dict()
        self.assertEqual(payload["turn"], "black")
        self.assertEqual(len(cast(list[str], payload["moves"])), 1)

    def test_user_move_triggers_ai_reply(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session(forced_user_color="white")
        payload = store.apply_user_move(session.session_id, "e2e4").to_dict()
        self.assertGreaterEqual(len(cast(list[str], payload["moves"])), 2)
        self.assertEqual(payload["turn"], "white")


if __name__ == "__main__":
    unittest.main()
