# Architecture 5 - PWA + optional WASM analysis

This branch targets a modern installable web app while keeping backend logic thin.

## Included in scaffold

- Guest sessions capped at 4 games.
- JSON API for session lifecycle and moves.
- PWA manifest + service worker for offline shell cache.
- Optional local analysis hook for a future Stockfish WASM worker.

## Run

```bash
python3 frontend_pwa_wasm/server.py
```

Open <http://127.0.0.1:8085>.
