from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from session_store import SessionStore


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
        if self.path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/static/app.js":
            self._serve_static("app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/static/style.css":
            self._serve_static("style.css", "text/css; charset=utf-8")
            return
        if self.path == "/api/sessions":
            sessions = [s.to_dict() for s in STORE.list_sessions()]
            _json(self, {"sessions": sessions, "max_sessions": STORE.max_sessions})
            return
        if self.path.startswith("/api/sessions/"):
            session_id = self.path.removeprefix("/api/sessions/")
            try:
                session = STORE.get(session_id)
            except KeyError:
                _json(self, {"error": "session not found"}, status=HTTPStatus.NOT_FOUND)
                return
            _json(self, session.to_dict())
            return

        _json(self, {"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/sessions":
            try:
                session = STORE.create_session()
            except RuntimeError:
                _json(self, {"error": "session limit reached"}, status=HTTPStatus.CONFLICT)
                return
            _json(self, session.to_dict(), status=HTTPStatus.CREATED)
            return
        if self.path.startswith("/api/sessions/") and self.path.endswith("/move"):
            session_id = self.path.removeprefix("/api/sessions/").removesuffix("/move").strip("/")
            self._submit_move(session_id)
            return
        _json(self, {"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def _submit_move(self, session_id: str) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(raw) if raw else {}
        source = data.get("from", "")
        target = data.get("to", "")
        try:
            session = STORE.apply_move(session_id, source, target)
        except KeyError:
            _json(self, {"error": "session not found"}, status=HTTPStatus.NOT_FOUND)
            return
        except ValueError as exc:
            _json(self, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        _json(self, session.to_dict())

    def _serve_static(self, filename: str, content_type: str) -> None:
        file_path = STATIC_ROOT / filename
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8082), AppHandler)
    print("Serving Architecture 2 on http://127.0.0.1:8082")
    server.serve_forever()


if __name__ == "__main__":
    main()
