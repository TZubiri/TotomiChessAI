const statusEl = document.getElementById("status");
const createBtn = document.getElementById("create-session");
const analyzeBtn = document.getElementById("analyze");
const sessionList = document.getElementById("session-list");
const boardEl = document.getElementById("board");
const installBtn = document.getElementById("install");

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

let selectedSquare = null;
let activeSession = null;
let installEvent = null;

function setStatus(text) {
  statusEl.textContent = text;
}

function squareName(row, col) {
  return "abcdefgh"[col] + String(8 - row);
}

function parseSquare(square) {
  const col = "abcdefgh".indexOf(square[0]);
  const row = 8 - Number(square[1]);
  return { row, col };
}

function renderBoard() {
  boardEl.innerHTML = "";
  if (!activeSession) {
    return;
  }
  for (let row = 0; row < 8; row += 1) {
    const tr = document.createElement("tr");
    for (let col = 0; col < 8; col += 1) {
      const td = document.createElement("td");
      const square = squareName(row, col);
      const piece = activeSession.board[row][col];
      td.className = (row + col) % 2 === 0 ? "light" : "dark";
      if (square === selectedSquare) {
        td.classList.add("selected");
      }
      td.dataset.square = square;
      td.textContent = piece === "." ? "" : PIECES[piece] || piece;
      tr.appendChild(td);
    }
    boardEl.appendChild(tr);
  }
}

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

async function refreshSessions() {
  const payload = await requestJSON("/api/sessions");
  sessionList.innerHTML = "";
  for (const session of payload.sessions) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.textContent = `${session.session_id} (${session.turn})`;
    button.addEventListener("click", () => loadSession(session.session_id));
    li.appendChild(button);
    sessionList.appendChild(li);
  }
  if (!payload.sessions.length) {
    const li = document.createElement("li");
    li.textContent = "No sessions yet.";
    sessionList.appendChild(li);
  }
}

async function loadSession(sessionId) {
  activeSession = await requestJSON(`/api/sessions/${sessionId}`);
  selectedSquare = null;
  renderBoard();
  setStatus(`Loaded session ${sessionId}. Turn: ${activeSession.turn}.`);
  await refreshSessions();
}

async function createSession() {
  try {
    const session = await requestJSON("/api/sessions", { method: "POST" });
    await loadSession(session.session_id);
  } catch (error) {
    setStatus(error.message);
  }
}

async function submitMove(fromSquare, toSquare) {
  if (!activeSession) {
    return;
  }
  try {
    activeSession = await requestJSON(`/api/sessions/${activeSession.session_id}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: fromSquare, to: toSquare }),
    });
    selectedSquare = null;
    renderBoard();
    await refreshSessions();
    setStatus(`Move ${fromSquare}-${toSquare} accepted. Turn: ${activeSession.turn}.`);
  } catch (error) {
    setStatus(error.message);
    selectedSquare = null;
    renderBoard();
  }
}

async function runLocalAnalysis() {
  if (!activeSession) {
    setStatus("Load a session first.");
    return;
  }

  const pieces = [];
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const piece = activeSession.board[row][col];
      if (piece !== ".") {
        pieces.push({ piece, square: squareName(row, col) });
      }
    }
  }

  const whiteMaterial = pieces
    .filter((entry) => entry.piece === entry.piece.toUpperCase())
    .map((entry) => entry.piece.toUpperCase())
    .reduce((sum, piece) => sum + materialValue(piece), 0);
  const blackMaterial = pieces
    .filter((entry) => entry.piece === entry.piece.toLowerCase())
    .map((entry) => entry.piece.toUpperCase())
    .reduce((sum, piece) => sum + materialValue(piece), 0);
  const diff = whiteMaterial - blackMaterial;

  setStatus(
    `Offline heuristic: material diff ${diff >= 0 ? "+" : ""}${diff}. Stockfish WASM hook pending.`
  );
}

function materialValue(piece) {
  if (piece === "P") return 1;
  if (piece === "N") return 3;
  if (piece === "B") return 3;
  if (piece === "R") return 5;
  if (piece === "Q") return 9;
  return 0;
}

boardEl.addEventListener("click", async (event) => {
  const target = event.target;
  if (!target.dataset.square || !activeSession) {
    return;
  }
  if (!selectedSquare) {
    selectedSquare = target.dataset.square;
    renderBoard();
    setStatus(`Selected ${selectedSquare}. Choose destination.`);
    return;
  }
  const from = selectedSquare;
  const to = target.dataset.square;
  selectedSquare = null;
  await submitMove(from, to);
});

createBtn.addEventListener("click", createSession);
analyzeBtn.addEventListener("click", runLocalAnalysis);

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installEvent = event;
  installBtn.disabled = false;
});

installBtn.addEventListener("click", async () => {
  if (!installEvent) {
    setStatus("Install prompt not available yet.");
    return;
  }
  installEvent.prompt();
  await installEvent.userChoice;
  installEvent = null;
  installBtn.disabled = true;
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .register("/static/service-worker.js")
    .then(() => setStatus("Service worker ready."))
    .catch(() => setStatus("Service worker registration failed."));
}

refreshSessions();
