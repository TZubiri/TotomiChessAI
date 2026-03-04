# Architecture 3 - Chess UI Library Shell

This branch uses off-the-shelf board/rules libraries for speed:

- `chess.js` for legal move validation in-browser.
- `chessboard.js` for board drag/drop UI.

The backend only manages guest sessions and move history.

## Run

```bash
python3 frontend_chesslib/server.py
```

Open <http://127.0.0.1:8083>.
