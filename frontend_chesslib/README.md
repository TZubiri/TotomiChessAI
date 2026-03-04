# Architecture 3 - Chess UI Library Shell

This branch uses a lightweight library-assisted frontend:

- Local `chess.js` copy for in-browser move validation/replay.

The page is intentionally minimal: board + Play button, then alternating user/AI moves.

- Guest sessions with random color assignment.
- 4-session cap.
- If user is black, AI auto-plays first.
- Backend remains authoritative for legality and AI turns.

## Run

```bash
python3 frontend_chesslib/server.py
```

Open <http://127.0.0.1:8083>.
