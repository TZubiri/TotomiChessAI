import re
import unittest

from frontend_lila_subset.uci_client import UCIClient


class UCIClientTests(unittest.TestCase):
    def test_returns_uci_move_from_start_position(self) -> None:
        client = UCIClient()
        self.addCleanup(client.close)

        move = client.bestmove([], depth=1)

        self.assertIsNotNone(move)
        self.assertRegex(move or "", re.compile(r"^[a-h][1-8][a-h][1-8][q]?$"))

    def test_handles_multiple_position_queries(self) -> None:
        client = UCIClient()
        self.addCleanup(client.close)

        move_one = client.bestmove(["e2e4"], depth=1)
        move_two = client.bestmove(["e2e4", "e7e5", "g1f3"], depth=1)

        self.assertRegex(move_one or "", re.compile(r"^[a-h][1-8][a-h][1-8][q]?$"))
        self.assertRegex(move_two or "", re.compile(r"^[a-h][1-8][a-h][1-8][q]?$"))


if __name__ == "__main__":
    unittest.main()
