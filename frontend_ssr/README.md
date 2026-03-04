# Architecture 1 - Server-rendered HTML

This prototype is the old-school option: server-rendered pages with minimal JavaScript.

## What is included

- Main page board + Play button only.
- Guest sessions without login.
- Hard limit of 4 concurrent sessions.
- Random user color assignment.
- Immediate AI first move when user is black.
- Legal move validation and AI replies powered by the local chess engine.

## Run

```bash
python3 frontend_ssr/server.py
```

Then open <http://127.0.0.1:8081>.
