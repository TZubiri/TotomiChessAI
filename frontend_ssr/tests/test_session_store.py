import unittest
from typing import cast

from frontend_ssr.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_enforces_max_sessions(self) -> None:
        store = SessionStore(max_sessions=4)
        for _ in range(4):
            store.create_session(forced_user_color="white")
        with self.assertRaises(RuntimeError):
            store.create_session(forced_user_color="white")

    def test_ai_moves_first_when_user_is_black(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session(forced_user_color="black")
        payload = session.to_dict()
        self.assertEqual(payload["user_color"], "black")
        self.assertEqual(payload["turn"], "black")
        self.assertEqual(len(cast(list[str], payload["moves"])), 1)

    def test_user_move_triggers_ai_reply(self) -> None:
        store = SessionStore(max_sessions=1)
        session = store.create_session(forced_user_color="white")
        updated = store.apply_user_move(session.session_id, "e2e4").to_dict()
        self.assertGreaterEqual(len(cast(list[str], updated["moves"])), 2)
        self.assertEqual(updated["turn"], "white")


if __name__ == "__main__":
    unittest.main()
