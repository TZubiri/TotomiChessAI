# Architecture 4 - Lichess-compatible Subset

This branch does not bootstrap all of `lila`; it implements a small API subset
with similar endpoint shapes so we can later swap in a deeper compatibility layer.

## Scope in this scaffold

- Main page board + Play button only.
- Lichess-inspired layout and board styling.
- Click, tap, and click-hold-drag move input.
- Guest game creation (`/api/challenge/open`).
- Board state lookup (`/api/board/game/{id}`).
- Move submission (`/api/board/game/{id}/move/{uci}`).
- Event snapshot endpoint (`/api/stream/event`).
- 4-game concurrency cap.
- Random color assignment with automatic AI first move for black users.
- Backend move generation goes through a local UCI subprocess (`mini_uci_engine.py`).

## Run

```bash
python3 frontend_lila_subset/server.py
```

Open <http://127.0.0.1:8084>.
