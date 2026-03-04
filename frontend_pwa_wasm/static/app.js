const statusEl = document.getElementById("status");
const playButton = document.getElementById("play");
const moveButton = document.getElementById("move");
const metaEl = document.getElementById("meta");
const boardEl = document.getElementById("board");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");

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

const STARTING_BOARD = [
  ["r", "n", "b", "q", "k", "b", "n", "r"],
  ["p", "p", "p", "p", "p", "p", "p", "p"],
  [".", ".", ".", ".", ".", ".", ".", "."],
  [".", ".", ".", ".", ".", ".", ".", "."],
  [".", ".", ".", ".", ".", ".", ".", "."],
  [".", ".", ".", ".", ".", ".", ".", "."],
  ["P", "P", "P", "P", "P", "P", "P", "P"],
  ["R", "N", "B", "Q", "K", "B", "N", "R"],
];

let session = null;
let selectedSquare = null;
let boardMatrix = STARTING_BOARD.map((row) => row.slice());

function setStatus(text) {
  statusEl.textContent = text;
}

function squareName(row, col) {
  return "abcdefgh"[col] + String(8 - row);
}

function setSessionInUrl(sessionId) {
  const url = new URL(window.location.href);
  url.searchParams.set("session", sessionId);
  history.replaceState({}, "", url.toString());
}

function userCanMove() {
  return Boolean(session && session.status === "in_progress" && session.user_to_move);
}

function renderMeta() {
  if (!session) {
    metaEl.innerHTML = "<p>Board ready. Press Play to get white or black.</p>";
    return;
  }

  const moveTail = session.moves.slice(-12).join(" ") || "-";
  const finished =
    session.status === "in_progress"
      ? ""
      : `<p class=\"finish\">Game over: ${session.winner ? `${session.winner} wins` : "draw"} (${session.status_reason}).</p>`;
  const aiLine = session.last_ai_move ? `<p>AI move: <strong>${session.last_ai_move}</strong></p>` : "";

  metaEl.innerHTML = `
    <p><strong>You are ${session.user_color}</strong>. AI is ${session.ai_color}.</p>
    <p>Turn: <strong>${session.turn}</strong></p>
    ${aiLine}
    <p>Moves: ${moveTail}</p>
    ${finished}
  `;
}

function renderBoard() {
  boardEl.innerHTML = "";
  for (let row = 0; row < 8; row += 1) {
    const tr = document.createElement("tr");
    for (let col = 0; col < 8; col += 1) {
      const td = document.createElement("td");
      const square = squareName(row, col);
      td.className = (row + col) % 2 === 0 ? "light" : "dark";
      td.dataset.square = square;
      if (square === selectedSquare) {
        td.classList.add("selected");
      }
      const piece = boardMatrix[row][col];
      if (piece !== ".") {
        td.textContent = PIECES[piece] || "";
      }
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

async function play() {
  try {
    session = await requestJSON("/api/play", { method: "POST" });
    setSessionInUrl(session.session_id);
    boardMatrix = session.board;
    selectedSquare = null;
    renderBoard();
    renderMeta();
    setStatus(`Assigned ${session.user_color}. ${session.user_to_move ? "Your move." : "AI moved first."}`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function sendMove(fromSquare, toSquare) {
  if (!session) {
    throw new Error("Press Play first.");
  }
  const payload = await requestJSON("/api/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: session.session_id, from: fromSquare, to: toSquare }),
  });
  session = payload;
  boardMatrix = session.board;
  selectedSquare = null;
  renderBoard();
  renderMeta();
}

boardEl.addEventListener("click", async (event) => {
  const target = event.target;
  if (!target.dataset.square) {
    return;
  }
  if (!userCanMove()) {
    setStatus(session ? "Wait for your turn." : "Press Play first.");
    return;
  }

  if (!selectedSquare) {
    selectedSquare = target.dataset.square;
    fromInput.value = selectedSquare;
    toInput.value = "";
    renderBoard();
    setStatus(`From ${selectedSquare}. Pick destination.`);
    return;
  }

  const fromSquare = selectedSquare;
  const toSquare = target.dataset.square;
  fromInput.value = fromSquare;
  toInput.value = toSquare;
  try {
    await sendMove(fromSquare, toSquare);
    setStatus(session.status === "in_progress" ? "Move accepted." : "Game complete.");
  } catch (error) {
    setStatus(error.message);
  }
});

moveButton.addEventListener("click", async () => {
  if (!userCanMove()) {
    setStatus(session ? "Wait for your turn." : "Press Play first.");
    return;
  }
  const fromSquare = fromInput.value.trim().toLowerCase();
  const toSquare = toInput.value.trim().toLowerCase();
  if (fromSquare.length !== 2 || toSquare.length !== 2) {
    setStatus("Enter both squares.");
    return;
  }
  try {
    await sendMove(fromSquare, toSquare);
    setStatus(session.status === "in_progress" ? "Move accepted." : "Game complete.");
  } catch (error) {
    setStatus(error.message);
  }
});

async function restoreFromUrl() {
  const sessionId = new URLSearchParams(window.location.search).get("session");
  if (!sessionId) {
    return;
  }
  try {
    session = await requestJSON(`/api/state/${sessionId}`);
    boardMatrix = session.board;
    renderBoard();
    renderMeta();
    setStatus("Session restored.");
  } catch {
    setStatus("Could not restore session. Press Play.");
  }
}

playButton.addEventListener("click", play);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
}

renderBoard();
renderMeta();
restoreFromUrl();
