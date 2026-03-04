const statusEl = document.getElementById("status");
const playButton = document.getElementById("play");
const moveButton = document.getElementById("move");
const boardEl = document.getElementById("board");
const metaEl = document.getElementById("meta");
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

let game = null;
let selectedSquare = null;
let boardMatrix = STARTING_BOARD.map((row) => row.slice());

function setStatus(text) {
  statusEl.textContent = text;
}

function squareName(row, col) {
  return "abcdefgh"[col] + String(8 - row);
}

function setGameInUrl(gameId) {
  const url = new URL(window.location.href);
  url.searchParams.set("game", gameId);
  history.replaceState({}, "", url.toString());
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

function renderMeta() {
  if (!game) {
    metaEl.innerHTML = "<p>Board ready. Press Play to open a guest challenge.</p>";
    return;
  }

  const moveTail = game.moveList.slice(-12).join(" ") || "-";
  const ended =
    game.status === "in_progress"
      ? ""
      : `<p class=\"finish\">Game over: ${game.winner ? `${game.winner} wins` : "draw"} (${game.statusReason}).</p>`;

  const aiLine = game.lastAiMove ? `<p>AI move: <strong>${game.lastAiMove}</strong></p>` : "";
  metaEl.innerHTML = `
    <p><strong>You are ${game.userColor}</strong>. AI is ${game.aiColor}.</p>
    <p>Turn: <strong>${game.turn}</strong></p>
    ${aiLine}
    <p>Moves: ${moveTail}</p>
    ${ended}
  `;
}

function userCanMove() {
  return Boolean(game && game.status === "in_progress" && game.userToMove);
}

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

async function loadGame(gameId) {
  game = await requestJSON(`/api/board/game/${gameId}`);
  boardMatrix = game.board;
  selectedSquare = null;
  renderBoard();
  renderMeta();
}

async function play() {
  try {
    const payload = await requestJSON("/api/challenge/open", { method: "POST" });
    setGameInUrl(payload.challenge.id);
    await loadGame(payload.challenge.id);
    setStatus(`Assigned ${game.userColor}. ${game.userToMove ? "Your move." : "AI moved first."}`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function sendMove(fromSquare, toSquare) {
  if (!game) {
    throw new Error("Press Play first.");
  }
  const uci = `${fromSquare}${toSquare}`;
  const payload = await requestJSON(`/api/board/game/${game.id}/move/${uci}`, { method: "POST" });
  game = payload.game;
  boardMatrix = game.board;
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
    setStatus(game ? "Wait for your turn." : "Press Play first.");
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
    setStatus(game.status === "in_progress" ? "Move accepted." : "Game complete.");
  } catch (error) {
    setStatus(error.message);
  }
});

moveButton.addEventListener("click", async () => {
  if (!userCanMove()) {
    setStatus(game ? "Wait for your turn." : "Press Play first.");
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
    setStatus(game.status === "in_progress" ? "Move accepted." : "Game complete.");
  } catch (error) {
    setStatus(error.message);
  }
});

async function restoreFromUrl() {
  const gameId = new URLSearchParams(window.location.search).get("game");
  if (!gameId) {
    return;
  }
  try {
    await loadGame(gameId);
    setStatus("Session restored.");
  } catch {
    setStatus("Could not restore session. Press Play.");
  }
}

playButton.addEventListener("click", play);
renderBoard();
renderMeta();
restoreFromUrl();
