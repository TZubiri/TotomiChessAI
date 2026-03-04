# Architecture 5 - PWA + optional WASM analysis

This branch targets a modern installable web app while keeping backend logic thin.

## Included in scaffold

- Main page board + Play button only.
- Guest sessions capped at 4 games.
- Random color assignment with auto AI first move for black users.
- JSON API for single-session lifecycle and moves.
- PWA manifest + service worker for offline shell cache.

## Run

```bash
python3 frontend_pwa_wasm/server.py
```

Open <http://127.0.0.1:8085>.
