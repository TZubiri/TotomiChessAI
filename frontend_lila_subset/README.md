# Architecture 4 - Lichess-compatible Subset

This branch does not bootstrap all of `lila`; it implements a small API subset
with similar endpoint shapes so we can later swap in a deeper compatibility layer.

## Scope in this scaffold

- Guest game creation (`/api/challenge/open`).
- Board state lookup (`/api/board/game/{id}`).
- Move submission (`/api/board/game/{id}/move/{uci}`).
- Event snapshot endpoint (`/api/stream/event`).
- 4-game concurrency cap.

## Run

```bash
python3 frontend_lila_subset/server.py
```

Open <http://127.0.0.1:8084>.
