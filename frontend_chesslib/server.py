from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from session_store import SessionStore


STORE = SessionStore(max_sessions=4)
ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"


def _write_json(handler: BaseHTTPRequestHandler, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
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
            sessions = [session.to_dict() for session in STORE.list_sessions()]
            _write_json(self, {"sessions": sessions, "max_sessions": STORE.max_sessions})
            return
        if self.path.startswith("/api/sessions/"):
            session_id = self.path.removeprefix("/api/sessions/")
            try:
                session = STORE.get(session_id)
            except KeyError:
                _write_json(self, {"error": "session not found"}, HTTPStatus.NOT_FOUND)
                return
            _write_json(self, session.to_dict())
            return
        _write_json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/sessions":
            try:
                session = STORE.create_session()
            except RuntimeError:
                _write_json(self, {"error": "session limit reached"}, HTTPStatus.CONFLICT)
                return
            _write_json(self, session.to_dict(), HTTPStatus.CREATED)
            return
        if self.path.startswith("/api/sessions/") and self.path.endswith("/moves"):
            session_id = self.path.removeprefix("/api/sessions/").removesuffix("/moves").strip("/")
            self._append_move(session_id)
            return
        _write_json(self, {"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _append_move(self, session_id: str) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        data = json.loads(raw) if raw else {}
        uci = data.get("uci", "")
        try:
            session = STORE.append_move(session_id, uci)
        except KeyError:
            _write_json(self, {"error": "session not found"}, HTTPStatus.NOT_FOUND)
            return
        except ValueError as exc:
            _write_json(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        _write_json(self, session.to_dict())

    def _serve_static(self, filename: str, content_type: str) -> None:
        path = STATIC_ROOT / filename
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8083), AppHandler)
    print("Serving Architecture 3 on http://127.0.0.1:8083")
    server.serve_forever()


if __name__ == "__main__":
    main()
