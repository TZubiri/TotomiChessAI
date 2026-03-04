from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlencode, urlparse

from session_store import SessionStore, starting_board_matrix


STORE = SessionStore(max_sessions=4)
ROOT = Path(__file__).resolve().parent

PIECE_GLYPHS = {
    "P": "&#9817;",
    "N": "&#9816;",
    "B": "&#9815;",
    "R": "&#9814;",
    "Q": "&#9813;",
    "K": "&#9812;",
    "p": "&#9823;",
    "n": "&#9822;",
    "b": "&#9821;",
    "r": "&#9820;",
    "q": "&#9819;",
    "k": "&#9818;",
}


def _render_board(board: list[list[str]]) -> str:
    rows = []
    for row_index, row in enumerate(board):
        rank = 8 - row_index
        row_cells = []
        for col_index, piece in enumerate(row):
            file_name = "abcdefgh"[col_index]
            square = f"{file_name}{rank}"
            shade = "light" if (row_index + col_index) % 2 == 0 else "dark"
            glyph = PIECE_GLYPHS.get(piece, "")
            row_cells.append(f'<td class="{shade}" data-square="{square}">{glyph}</td>')
        rows.append("<tr>" + "".join(row_cells) + "</tr>")
    return "".join(rows)


class AppHandler(BaseHTTPRequestHandler):
    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, session_id: str | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if session_id is not None:
            self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly")
        self.end_headers()

    def _read_form(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length).decode("utf-8")
        parsed = parse_qs(payload)
        return {key: values[0] for key, values in parsed.items() if values}

    def _current_session_id(self) -> str | None:
        raw_cookie = self.headers.get("Cookie", "")
        if not raw_cookie:
            return None
        cookie = SimpleCookie()
        cookie.load(raw_cookie)
        value = cookie.get("session_id")
        if value is None:
            return None
        return value.value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._show_page(parsed.query)
            return
        if parsed.path == "/static/style.css":
            self._serve_css()
            return
        self._send_html("<h1>Not found</h1>", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/play":
            self._start_game()
            return
        if self.path == "/move":
            self._submit_move()
            return
        self._send_html("<h1>Not found</h1>", status=HTTPStatus.NOT_FOUND)

    def _serve_css(self) -> None:
        content = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        body = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _show_page(self, query: str) -> None:
        params = parse_qs(query)
        message = escape(params.get("msg", [""])[0])

        session_payload = None
        query_session = params.get("session", [None])[0]
        session_id = query_session or self._current_session_id()
        if session_id:
            try:
                session_payload = STORE.get(session_id).to_dict()
            except KeyError:
                session_payload = None

        if session_payload is None:
            board = starting_board_matrix()
            status_line = "Press Play to start. You will be randomly assigned white or black."
            color_line = ""
            turn_line = ""
            history_line = ""
            move_form = ""
            ai_line = ""
        else:
            board = cast(list[list[str]], session_payload["board"])
            user_color = cast(str, session_payload["user_color"])
            ai_color = cast(str, session_payload["ai_color"])
            turn = cast(str, session_payload["turn"])
            status = cast(str, session_payload["status"])
            user_to_move = cast(bool, session_payload["user_to_move"])
            winner = cast(str | None, session_payload["winner"])
            status_reason = cast(str | None, session_payload["status_reason"])
            moves = cast(list[str], session_payload["moves"])

            color_line = f"<p><strong>You are {user_color}.</strong> AI is {ai_color}.</p>"
            turn_line = f"<p>Turn: <strong>{turn}</strong></p>"

            if status == "in_progress":
                status_line = "Your move." if user_to_move else "AI thinking..."
            else:
                if winner:
                    status_line = f"Game over: {winner} wins ({status_reason})."
                else:
                    status_line = f"Game over: draw ({status_reason})."

            ai_move = cast(str | None, session_payload.get("last_ai_move"))
            ai_line = f"<p>AI move: {escape(ai_move)}</p>" if ai_move else ""
            history_text = " ".join(moves[-14:]) or "-"
            history_line = f"<p>Moves: {escape(history_text)}</p>"

            if user_to_move:
                move_form = """
      <form method="post" action="/move" class="move-form">
        <label>From <input id="from" name="from" maxlength="2" placeholder="e2" required /></label>
        <label>To <input id="to" name="to" maxlength="2" placeholder="e4" required /></label>
        <button type="submit">Move</button>
      </form>
"""
            else:
                move_form = ""

        board_html = _render_board(board)

        html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Guest Chess SSR</title>
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main>
      <h1>Guest Chess</h1>
      <p class="message">{message}</p>
      <form method="post" action="/play">
        <button type="submit">Play</button>
      </form>
      {color_line}
      {turn_line}
      <p>{escape(status_line)}</p>
      {ai_line}
      <table class="board" id="board">{board_html}</table>
      {move_form}
      {history_line}
    </main>
    <script>
      const board = document.getElementById("board");
      const fromInput = document.getElementById("from");
      const toInput = document.getElementById("to");
      if (board && fromInput && toInput) {{
        board.addEventListener("click", (event) => {{
          const cell = event.target.closest("td");
          if (!cell || !cell.dataset.square) return;
          if (!fromInput.value) {{
            fromInput.value = cell.dataset.square;
            return;
          }}
          if (!toInput.value) {{
            toInput.value = cell.dataset.square;
            return;
          }}
          fromInput.value = cell.dataset.square;
          toInput.value = "";
        }});
      }}
    </script>
  </body>
</html>
"""
        self._send_html(html)

    def _start_game(self) -> None:
        try:
            session = STORE.create_session()
        except RuntimeError as exc:
            query = urlencode({"msg": str(exc)})
            self._redirect(f"/?{query}")
            return

        message = f"Assigned {session.user_color}."
        query = urlencode({"msg": message})
        self._redirect(f"/?{query}", session_id=session.session_id)

    def _submit_move(self) -> None:
        session_id = self._current_session_id()
        if session_id is None:
            self._redirect("/?msg=Press+Play+first")
            return

        form = self._read_form()
        source = form.get("from", "").strip().lower()
        target = form.get("to", "").strip().lower()
        if len(source) != 2 or len(target) != 2:
            self._redirect("/?msg=Enter+both+squares")
            return

        try:
            STORE.apply_user_move(session_id, f"{source}{target}")
            self._redirect("/?msg=Move+accepted")
        except (KeyError, ValueError) as exc:
            query = urlencode({"msg": str(exc)})
            self._redirect(f"/?{query}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8081), AppHandler)
    print("Serving Architecture 1 on http://127.0.0.1:8081")
    server.serve_forever()


if __name__ == "__main__":
    main()
