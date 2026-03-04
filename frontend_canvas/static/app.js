const boardCanvas = document.getElementById("board");
const ctx = boardCanvas.getContext("2d");
const playBtn = document.getElementById("play");
const moveBtn = document.getElementById("move");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");

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

function setSessionInUrl(sessionId) {
  const url = new URL(window.location.href);
  url.searchParams.set("session", sessionId);
  history.replaceState({}, "", url.toString());
}

function setStatus(message) {
  statusEl.textContent = message;
}

function squareName(row, col) {
  return "abcdefgh"[col] + String(8 - row);
}

function squareFromCanvasEvent(event) {
  const rect = boardCanvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) * boardCanvas.width) / rect.width;
  const y = ((event.clientY - rect.top) * boardCanvas.height) / rect.height;
  const squareSize = boardCanvas.width / 8;
  const col = Math.floor(x / squareSize);
  const row = Math.floor(y / squareSize);
  if (col < 0 || col > 7 || row < 0 || row > 7) {
    return null;
  }
  return squareName(row, col);
}

function userCanMove() {
  return Boolean(session && session.status === "in_progress" && session.user_to_move);
}

function renderMeta() {
  if (!session) {
    metaEl.innerHTML = "<p>Press Play to start. You will be assigned white or black.</p>";
    return;
  }
  const winnerText = session.winner ? `${session.winner} wins` : "draw";
  const finished = session.status === "in_progress" ? "" : `<p class=\"finish\">Game over: ${winnerText} (${session.status_reason}).</p>`;
  const aiMove = session.last_ai_move ? `<p>AI move: <strong>${session.last_ai_move}</strong></p>` : "";
  const moveTail = session.moves.slice(-12).join(" ") || "-";
  metaEl.innerHTML = `
    <p><strong>You are ${session.user_color}</strong>. AI is ${session.ai_color}.</p>
    <p>Turn: <strong>${session.turn}</strong></p>
    ${aiMove}
    <p>Moves: ${moveTail}</p>
    ${finished}
  `;
}

function drawBoard(board) {
  const size = boardCanvas.width / 8;
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      ctx.fillStyle = (row + col) % 2 === 0 ? "#f6e4bf" : "#a87443";
      ctx.fillRect(col * size, row * size, size, size);

      const square = squareName(row, col);
      if (square === selectedSquare) {
        ctx.strokeStyle = "#bb3f1c";
        ctx.lineWidth = 4;
        ctx.strokeRect(col * size + 2, row * size + 2, size - 4, size - 4);
      }

      const piece = board[row][col];
      if (piece !== ".") {
        ctx.font = "52px Cambria";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = piece === piece.toUpperCase() ? "#f6f6f6" : "#141414";
        ctx.fillText(PIECES[piece] || piece, col * size + size / 2, row * size + size / 2 + 1);
      }
    }
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

async function loadInitialBoard() {
  drawBoard(STARTING_BOARD);
  renderMeta();
}

async function play() {
  try {
    session = await requestJSON("/api/play", { method: "POST" });
    setSessionInUrl(session.session_id);
    selectedSquare = null;
    drawBoard(session.board);
    renderMeta();
    setStatus(`Assigned ${session.user_color}. ${session.user_to_move ? "Your move." : "AI moved first."}`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function sendMove(fromSquare, toSquare) {
  if (!session) {
    setStatus("Press Play first.");
    return;
  }
  try {
    session = await requestJSON("/api/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session.session_id, from: fromSquare, to: toSquare }),
    });
    selectedSquare = null;
    drawBoard(session.board);
    renderMeta();
    setStatus(session.status === "in_progress" ? "Move accepted." : "Game complete.");
  } catch (error) {
    setStatus(error.message);
  }
}

boardCanvas.addEventListener("click", async (event) => {
  if (!userCanMove()) {
    setStatus(session ? "Wait for your turn." : "Press Play first.");
    return;
  }

  const square = squareFromCanvasEvent(event);
  if (!square) {
    return;
  }

  if (!selectedSquare) {
    selectedSquare = square;
    fromInput.value = square;
    toInput.value = "";
    drawBoard(session.board);
    setStatus(`From ${square}. Select destination.`);
    return;
  }

  const fromSquare = selectedSquare;
  const toSquare = square;
  selectedSquare = null;
  fromInput.value = fromSquare;
  toInput.value = toSquare;
  await sendMove(fromSquare, toSquare);
});

moveBtn.addEventListener("click", async () => {
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
  await sendMove(fromSquare, toSquare);
});

playBtn.addEventListener("click", play);

drawBoard(STARTING_BOARD);
renderMeta();
setStatus("Press Play to start.");

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get("session");
  if (!sessionId) {
    await loadInitialBoard();
    return;
  }

  try {
    session = await requestJSON(`/api/state/${sessionId}`);
    drawBoard(session.board);
    renderMeta();
    setStatus("Session restored from URL.");
  } catch {
    await loadInitialBoard();
    setStatus("Could not restore session; press Play.");
  }
}

boot();
