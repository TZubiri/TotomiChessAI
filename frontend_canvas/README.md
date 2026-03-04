# Architecture 2 - HTML5 Canvas

This prototype renders the board on a single `<canvas>` and talks to a thin JSON API.

## What is included

- Guest session creation without login.
- Session cap set to 4 concurrent games.
- Click-to-move interaction in canvas.
- Backend remains authoritative for turn ownership.

## Run

```bash
python3 frontend_canvas/server.py
```

Open <http://127.0.0.1:8082>.
