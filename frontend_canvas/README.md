# Architecture 2 - HTML5 Canvas

This prototype renders the board on a single `<canvas>` and talks to a thin JSON API.

## What is included

- Main page board + Play button only.
- Guest sessions with random color assignment.
- Session cap set to 4 concurrent games.
- If user is black, AI plays first automatically.
- After each user move, backend applies an AI reply.

## Run

```bash
python3 frontend_canvas/server.py
```

Open <http://127.0.0.1:8082>.
