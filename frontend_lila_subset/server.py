from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from session_store import GameStore


STORE = GameStore(max_games=4)
ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"


def _send_json(handler: BaseHTTPRequestHandler, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/static/app.js":
            self._serve_static("app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/static/style.css":
            self._serve_static("style.css", "text/css; charset=utf-8")
            return
        if self.path == "/api/stream/event":
            events = [
                {
                    "type": "gameStart",
                    "game": {"id": game.game_id, "turn": game.turn, "moves": game.moves},
                }
                for game in STORE.list_games()
            ]
            _send_json(self, {"events": events})
            return
        if self.path.startswith("/api/board/game/"):
            game_id = self.path.removeprefix("/api/board/game/").strip("/")
            try:
                game = STORE.get_game(game_id)
            except KeyError:
                _send_json(self, {"error": "game not found"}, HTTPStatus.NOT_FOUND)
                return
            _send_json(self, game.to_board_dict())
            return
        _send_json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/challenge/open":
            self._create_open_challenge()
            return
        if self.path.startswith("/api/board/game/") and "/move/" in self.path:
            self._submit_board_move()
            return
        _send_json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _create_open_challenge(self) -> None:
        try:
            game = STORE.open_challenge()
        except RuntimeError:
            _send_json(self, {"error": "game limit reached"}, HTTPStatus.CONFLICT)
            return

        payload = {
            "challenge": {
                "id": game.game_id,
                "status": "created",
                "url": f"/api/board/game/{game.game_id}",
            }
        }
        _send_json(self, payload, HTTPStatus.CREATED)

    def _submit_board_move(self) -> None:
        path = self.path.removeprefix("/api/board/game/")
        game_id, _, move_path = path.partition("/move/")
        uci_move = move_path.strip("/")
        try:
            game = STORE.submit_move(game_id, uci_move)
        except KeyError:
            _send_json(self, {"error": "game not found"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError as exc:
            _send_json(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        _send_json(self, {"ok": True, "game": game.to_board_dict()})

    def _serve_static(self, filename: str, content_type: str) -> None:
        path = STATIC_ROOT / filename
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8084), AppHandler)
    print("Serving Architecture 4 on http://127.0.0.1:8084")
    server.serve_forever()


if __name__ == "__main__":
    main()
