# Architecture 1 - Server-rendered HTML

This prototype is the old-school option: server-rendered pages with minimal JavaScript.

## What is included

- Guest sessions without login.
- Hard limit of 4 concurrent sessions.
- Server-side board state per session.
- Basic move form (`from` and `to`), no full legality engine yet.

## Run

```bash
python3 frontend_ssr/server.py
```

Then open <http://127.0.0.1:8081>.
