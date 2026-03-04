from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from session_store import SessionStore, starting_board_matrix


STORE = SessionStore(max_sessions=4)
ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"


def _json(handler: BaseHTTPRequestHandler, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if path == "/manifest.webmanifest":
            self._serve_static("manifest.webmanifest", "application/manifest+json; charset=utf-8")
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            content_type = "text/plain; charset=utf-8"
            if relative.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            elif relative.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif relative.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif relative.endswith(".webmanifest"):
                content_type = "application/manifest+json; charset=utf-8"
            self._serve_static(relative, content_type)
            return
        if path == "/api/initial-board":
            _json(self, {"board": starting_board_matrix()})
            return
        if path.startswith("/api/state/"):
            session_id = path.removeprefix("/api/state/").strip("/")
            try:
                session = STORE.get(session_id)
            except KeyError:
                _json(self, {"error": "session not found"}, HTTPStatus.NOT_FOUND)
                return
            _json(self, session.to_dict())
            return
        _json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/play":
            try:
                session = STORE.create_session()
            except RuntimeError as exc:
                _json(self, {"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            _json(self, session.to_dict(), HTTPStatus.CREATED)
            return

        if self.path == "/api/move":
            self._submit_move()
            return

        _json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _submit_move(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        payload = json.loads(body) if body else {}

        session_id = str(payload.get("session_id", "")).strip()
        source = str(payload.get("from", "")).strip().lower()
        target = str(payload.get("to", "")).strip().lower()

        if not session_id:
            _json(self, {"error": "missing session_id"}, HTTPStatus.BAD_REQUEST)
            return
        if len(source) != 2 or len(target) != 2:
            _json(self, {"error": "invalid move squares"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            session = STORE.apply_user_move(session_id, f"{source}{target}")
        except KeyError:
            _json(self, {"error": "session not found"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError as exc:
            _json(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        _json(self, session.to_dict())

    def _serve_static(self, filename: str, content_type: str) -> None:
        path = STATIC_ROOT / filename
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8085), AppHandler)
    print("Serving Architecture 5 on http://127.0.0.1:8085")
    server.serve_forever()


if __name__ == "__main__":
    main()
