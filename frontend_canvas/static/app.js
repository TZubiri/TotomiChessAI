const board = document.getElementById("board");
const ctx = board.getContext("2d");
const sessionList = document.getElementById("session-list");
const statusEl = document.getElementById("status");
const createBtn = document.getElementById("create-session");

const PIECES = {
  P: "♙",
  N: "♘",
  B: "♗",
  R: "♖",
  Q: "♕",
  K: "♔",
  p: "♟",
  n: "♞",
  b: "♝",
  r: "♜",
  q: "♛",
  k: "♚",
};

let activeSession = null;
let selectedSquare = null;

function squareName(row, col) {
  return "abcdefgh"[col] + String(8 - row);
}

function squareFromEvent(event) {
  const rect = board.getBoundingClientRect();
  const scaleX = board.width / rect.width;
  const scaleY = board.height / rect.height;
  const x = (event.clientX - rect.left) * scaleX;
  const y = (event.clientY - rect.top) * scaleY;
  const size = board.width / 8;
  const col = Math.floor(x / size);
  const row = Math.floor(y / size);
  if (row < 0 || row > 7 || col < 0 || col > 7) {
    return null;
  }
  return squareName(row, col);
}

function setStatus(message) {
  statusEl.textContent = message;
}

function drawBoard() {
  const size = board.width / 8;
  ctx.clearRect(0, 0, board.width, board.height);
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const isLight = (row + col) % 2 === 0;
      ctx.fillStyle = isLight ? "#f2e0be" : "#b0804a";
      ctx.fillRect(col * size, row * size, size, size);

      const sq = squareName(row, col);
      if (sq === selectedSquare) {
        ctx.strokeStyle = "#a1251a";
        ctx.lineWidth = 3;
        ctx.strokeRect(col * size + 2, row * size + 2, size - 4, size - 4);
      }

      const piece = activeSession?.board?.[row]?.[col];
      if (piece && piece !== ".") {
        ctx.fillStyle = piece === piece.toUpperCase() ? "#f8f8f8" : "#131313";
        ctx.font = "42px Georgia";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(PIECES[piece] || piece, col * size + size / 2, row * size + size / 2 + 1);
      }
    }
  }
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

async function refreshSessions() {
  const payload = await fetchJSON("/api/sessions");
  sessionList.innerHTML = "";
  payload.sessions.forEach((session) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = `${session.session_id} (${session.turn})`;
    btn.addEventListener("click", () => loadSession(session.session_id));
    li.appendChild(btn);
    sessionList.appendChild(li);
  });
}

async function loadSession(sessionId) {
  activeSession = await fetchJSON(`/api/sessions/${sessionId}`);
  selectedSquare = null;
  drawBoard();
  setStatus(`Loaded session ${sessionId}. Turn: ${activeSession.turn}.`);
  await refreshSessions();
}

async function createSession() {
  try {
    const created = await fetchJSON("/api/sessions", { method: "POST" });
    await loadSession(created.session_id);
  } catch (error) {
    setStatus(error.message);
  }
}

async function submitMove(fromSquare, toSquare) {
  if (!activeSession) {
    return;
  }
  try {
    activeSession = await fetchJSON(`/api/sessions/${activeSession.session_id}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: fromSquare, to: toSquare }),
    });
    selectedSquare = null;
    drawBoard();
    setStatus(`Move ${fromSquare}-${toSquare} accepted. Turn: ${activeSession.turn}.`);
    await refreshSessions();
  } catch (error) {
    setStatus(error.message);
    selectedSquare = null;
    drawBoard();
  }
}

board.addEventListener("click", async (event) => {
  if (!activeSession) {
    setStatus("Create or load a session first.");
    return;
  }
  const square = squareFromEvent(event);
  if (!square) {
    return;
  }
  if (!selectedSquare) {
    selectedSquare = square;
    drawBoard();
    setStatus(`Selected ${square}. Choose destination.`);
    return;
  }
  const fromSquare = selectedSquare;
  selectedSquare = null;
  await submitMove(fromSquare, square);
});

createBtn.addEventListener("click", createSession);

(async () => {
  drawBoard();
  await refreshSessions();
})();
