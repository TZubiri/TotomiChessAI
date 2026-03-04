from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from session_store import SessionStore


STORE = SessionStore(max_sessions=4)
ROOT = Path(__file__).resolve().parent


def _render_board(board: list[list[str]]) -> str:
    rows = []
    for r, row in enumerate(board):
        cells = []
        rank = 8 - r
        for c, piece in enumerate(row):
            file_name = "abcdefgh"[c]
            square = f"{file_name}{rank}"
            color = "light" if (r + c) % 2 == 0 else "dark"
            glyph = "" if piece == "." else piece
            cells.append(f'<td class="{color}" data-square="{square}">{escape(glyph)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(rows)


class AppHandler(BaseHTTPRequestHandler):
    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def _read_form(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(content_length).decode("utf-8")
        parsed = parse_qs(data)
        return {k: v[0] for k, v in parsed.items() if v}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._show_lobby(parsed.query)
            return
        if parsed.path == "/static/style.css":
            self._serve_css()
            return
        if parsed.path.startswith("/session/"):
            self._show_session(parsed.path.removeprefix("/session/"), parsed.query)
            return
        self._send_html("<h1>Not found</h1>", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/sessions":
            self._create_session()
            return
        if self.path.startswith("/session/") and self.path.endswith("/move"):
            session_id = self.path.removeprefix("/session/").removesuffix("/move").strip("/")
            self._submit_move(session_id)
            return
        self._send_html("<h1>Not found</h1>", status=HTTPStatus.NOT_FOUND)

    def _serve_css(self) -> None:
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        body = css.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _show_lobby(self, query: str) -> None:
        params = parse_qs(query)
        message = escape(params.get("msg", [""])[0])
        sessions_html = []
        for session in STORE.list_sessions():
            sessions_html.append(
                f'<li><a href="/session/{session.session_id}">Session {session.session_id}</a> '
                f'(turn: {session.turn})</li>'
            )
        sessions = "".join(sessions_html) or "<li>No active sessions.</li>"
        html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Guest Chess Lobby</title>
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main>
      <h1>Guest Chess Lobby</h1>
      <p class="note">Max 4 concurrent sessions. No registration required.</p>
      <p class="message">{message}</p>
      <form method="post" action="/sessions">
        <button type="submit">Create Session</button>
      </form>
      <h2>Open Sessions</h2>
      <ul>{sessions}</ul>
    </main>
  </body>
</html>
"""
        self._send_html(html)

    def _create_session(self) -> None:
        try:
            session = STORE.create_session()
        except RuntimeError:
            self._redirect("/?msg=Session+limit+reached")
            return
        self._redirect(f"/session/{session.session_id}")

    def _show_session(self, session_id: str, query: str) -> None:
        params = parse_qs(query)
        message = escape(params.get("msg", [""])[0])
        try:
            session = STORE.get(session_id)
        except KeyError:
            self._send_html("<h1>Session not found</h1>", status=HTTPStatus.NOT_FOUND)
            return
        board_html = _render_board(session.board)
        history = " ".join(session.moves[-12:]) or "No moves yet."
        html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Session {session.session_id}</title>
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main>
      <p><a href="/">Back to lobby</a></p>
      <h1>Session {session.session_id}</h1>
      <p>Turn: <strong>{session.turn}</strong></p>
      <p class="message">{message}</p>
      <table class="board">{board_html}</table>
      <form method="post" action="/session/{session.session_id}/move" class="move-form">
        <label>From <input name="from" placeholder="e2" required /></label>
        <label>To <input name="to" placeholder="e4" required /></label>
        <button type="submit">Play Move</button>
      </form>
      <p>Recent moves: {history}</p>
    </main>
  </body>
</html>
"""
        self._send_html(html)

    def _submit_move(self, session_id: str) -> None:
        form = self._read_form()
        source = form.get("from", "")
        target = form.get("to", "")
        try:
            STORE.apply_move(session_id, source, target)
            self._redirect(f"/session/{session_id}?msg=Move+accepted")
        except (KeyError, ValueError) as exc:
            self._redirect(f"/session/{session_id}?msg={escape(str(exc)).replace(' ', '+')}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8081), AppHandler)
    print("Serving Architecture 1 on http://127.0.0.1:8081")
    server.serve_forever()


if __name__ == "__main__":
    main()
