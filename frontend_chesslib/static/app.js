import { Chess } from "/static/vendor/chess.min.js";

const playButton = document.getElementById("play");
const moveButton = document.getElementById("move");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");
const boardEl = document.getElementById("board");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");

const PIECES = {
  wp: "♙",
  wn: "♘",
  wb: "♗",
  wr: "♖",
  wq: "♕",
  wk: "♔",
  bp: "♟",
  bn: "♞",
  bb: "♝",
  br: "♜",
  bq: "♛",
  bk: "♚",
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
let game = new Chess();
let displayBoard = STARTING_BOARD.map((row) => row.slice());

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

function rebuildGameFromMoves(moves) {
  game = new Chess();
  for (const moveText of moves) {
    const from = moveText.slice(0, 2);
    const to = moveText.slice(2, 4);
    const promotion = moveText[4] || "q";
    const legal = game.move({ from, to, promotion });
    if (!legal) {
      throw new Error(`invalid move in history: ${moveText}`);
    }
  }
}

function renderMeta() {
  if (!session) {
    metaEl.innerHTML = "<p>Board is ready. Press Play for your color assignment.</p>";
    return;
  }
  const movesTail = session.moves.slice(-12).join(" ") || "-";
  const finished =
    session.status === "in_progress"
      ? ""
      : `<p class=\"finish\">Game over: ${session.winner ? `${session.winner} wins` : "draw"} (${session.status_reason}).</p>`;
  const aiLine = session.last_ai_move ? `<p>AI move: <strong>${session.last_ai_move}</strong></p>` : "";
  metaEl.innerHTML = `
    <p><strong>You are ${session.user_color}</strong>. AI is ${session.ai_color}.</p>
    <p>Turn: <strong>${session.turn}</strong></p>
    ${aiLine}
    <p>Moves: ${movesTail}</p>
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
      td.dataset.square = square;
      td.className = (row + col) % 2 === 0 ? "light" : "dark";
      if (square === selectedSquare) {
        td.classList.add("selected");
      }

      const piece = displayBoard[row][col];
      if (piece && piece !== ".") {
        const color = piece === piece.toUpperCase() ? "w" : "b";
        const type = piece.toLowerCase();
        td.textContent = PIECES[`${color}${type}`] || "";
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
    rebuildGameFromMoves(session.moves);
    displayBoard = session.board;
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

  const candidate = game.move({ from: fromSquare, to: toSquare, promotion: "q" });
  if (!candidate) {
    throw new Error("Illegal move for current position.");
  }
  game.undo();

  const payload = await requestJSON("/api/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: session.session_id, from: fromSquare, to: toSquare }),
  });
  session = payload;
  rebuildGameFromMoves(session.moves);
  displayBoard = session.board;
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
    renderMeta();
    return;
  }

  try {
    session = await requestJSON(`/api/state/${sessionId}`);
    rebuildGameFromMoves(session.moves);
    displayBoard = session.board;
    renderBoard();
    renderMeta();
    setStatus("Session restored.");
  } catch {
    renderMeta();
    setStatus("Could not restore session; press Play.");
  }
}

playButton.addEventListener("click", play);
renderBoard();
setStatus("Ready. Press Play.");
restoreFromUrl();
