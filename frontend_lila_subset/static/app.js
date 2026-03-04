const statusEl = document.getElementById("status");
const playButton = document.getElementById("play");
const moveButton = document.getElementById("move");
const boardEl = document.getElementById("board");
const metaEl = document.getElementById("meta");
const movesEl = document.getElementById("moves");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");

const FILES = "abcdefgh";
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

const PIECE_IMAGE = {
  P: "/static/pieces/cburnett/wP.svg",
  N: "/static/pieces/cburnett/wN.svg",
  B: "/static/pieces/cburnett/wB.svg",
  R: "/static/pieces/cburnett/wR.svg",
  Q: "/static/pieces/cburnett/wQ.svg",
  K: "/static/pieces/cburnett/wK.svg",
  p: "/static/pieces/cburnett/bP.svg",
  n: "/static/pieces/cburnett/bN.svg",
  b: "/static/pieces/cburnett/bB.svg",
  r: "/static/pieces/cburnett/bR.svg",
  q: "/static/pieces/cburnett/bQ.svg",
  k: "/static/pieces/cburnett/bK.svg",
};

let game = null;
let orientation = "white";
let boardMatrix = STARTING_BOARD.map((row) => row.slice());
let selectedSquare = null;
let dragging = null;
let historyBoards = [STARTING_BOARD.map((row) => row.slice())];
let viewedPly = 0;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function boardCoordToSquare(row, col) {
  return `${FILES[col]}${8 - row}`;
}

function cloneBoard(matrix) {
  return matrix.map((row) => row.slice());
}

function squareToBoardCoord(square) {
  const file = square[0];
  const rank = Number(square[1]);
  return {
    row: 8 - rank,
    col: FILES.indexOf(file),
  };
}

function displayToBoardCoord(displayRow, displayCol) {
  if (orientation === "white") {
    return { row: displayRow, col: displayCol };
  }
  return { row: 7 - displayRow, col: 7 - displayCol };
}

function pieceBelongsToUser(piece) {
  if (!game || !piece || piece === ".") {
    return false;
  }
  return game.userColor === "white" ? piece === piece.toUpperCase() : piece === piece.toLowerCase();
}

function userCanMove() {
  return Boolean(game && game.status === "in_progress" && game.userToMove);
}

function moveResultStatus() {
  if (!game || game.status === "in_progress") {
    return "Move accepted.";
  }
  return "Game complete. Click a move or use Left/Right keys to review.";
}

function canReviewHistory() {
  return Boolean(game && game.status !== "in_progress");
}

function reviewStatusText(ply) {
  if (!game) {
    return "";
  }
  return ply === game.moveList.length ? "Review mode: final position." : `Review mode: position after ply ${ply}.`;
}

function isTypingElement(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function setGameInUrl(gameId) {
  const url = new URL(window.location.href);
  url.searchParams.set("game", gameId);
  history.replaceState({}, "", url.toString());
}

function renderMeta() {
  if (!game) {
    metaEl.innerHTML = "<p>Press Play to start a guest game.</p>";
    return;
  }

  const reviewLine =
    game.status === "in_progress"
      ? ""
      : `<p><strong>Review:</strong> ${
          viewedPly === game.moveList.length ? "final position" : `position after ply ${viewedPly}`
        }</p>`;
  const ended =
    game.status === "in_progress"
      ? ""
      : `<p><strong>Game over:</strong> ${game.winner ? `${game.winner} wins` : "draw"} (${game.statusReason}).</p>`;
  const aiLine = game.lastAiMove ? `<p><strong>AI move:</strong> ${game.lastAiMove}</p>` : "";
  metaEl.innerHTML = `
    <p><strong>You are ${game.userColor}.</strong> AI is ${game.aiColor}.</p>
    <p><strong>Turn:</strong> ${game.turn}</p>
    ${aiLine}
    ${reviewLine}
    ${ended}
  `;
}

function createMoveButton(moveText, ply) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "history-move";
  button.dataset.ply = String(ply);
  button.textContent = moveText;
  button.disabled = !game || game.status === "in_progress";
  if (ply === viewedPly) {
    button.classList.add("active");
  }
  return button;
}

function createMoveSpacer() {
  const spacer = document.createElement("span");
  spacer.className = "move-spacer";
  return spacer;
}

function renderMoveList() {
  movesEl.innerHTML = "";
  if (!game) {
    return;
  }

  const startRow = document.createElement("li");
  startRow.className = "move-row";

  const startNo = document.createElement("span");
  startNo.className = "move-no";
  startNo.textContent = "0.";

  startRow.appendChild(startNo);
  startRow.appendChild(createMoveButton("start", 0));
  startRow.appendChild(createMoveSpacer());
  movesEl.appendChild(startRow);

  if (!game.moveList.length) {
    return;
  }

  for (let index = 0; index < game.moveList.length; index += 2) {
    const number = Math.floor(index / 2) + 1;
    const whiteMove = game.moveList[index] || "";
    const blackMove = game.moveList[index + 1] || "";

    const row = document.createElement("li");
    row.className = "move-row";

    const numberEl = document.createElement("span");
    numberEl.className = "move-no";
    numberEl.textContent = `${number}.`;

    row.appendChild(numberEl);
    if (whiteMove) {
      row.appendChild(createMoveButton(whiteMove, index + 1));
    } else {
      row.appendChild(createMoveSpacer());
    }
    if (blackMove) {
      row.appendChild(createMoveButton(blackMove, index + 2));
    } else {
      row.appendChild(createMoveSpacer());
    }

    movesEl.appendChild(row);
  }

  if (game.status === "in_progress" || viewedPly === game.moveList.length) {
    movesEl.scrollTop = movesEl.scrollHeight;
  }
}

function createCoordinateLabel(square, isDark) {
  const label = document.createElement("span");
  label.className = `coord ${isDark ? "dark" : "light"}`;
  label.textContent = square;
  return label;
}

function renderBoard() {
  boardEl.innerHTML = "";

  for (let displayRow = 0; displayRow < 8; displayRow += 1) {
    for (let displayCol = 0; displayCol < 8; displayCol += 1) {
      const isLight = (displayRow + displayCol) % 2 === 0;
      const boardCoord = displayToBoardCoord(displayRow, displayCol);
      const square = boardCoordToSquare(boardCoord.row, boardCoord.col);
      const piece = boardMatrix[boardCoord.row][boardCoord.col];

      const squareEl = document.createElement("div");
      squareEl.className = `square ${isLight ? "light" : "dark"}`;
      if (square === selectedSquare) {
        squareEl.classList.add("target");
      }
      squareEl.dataset.square = square;
      squareEl.style.left = `${displayCol * 12.5}%`;
      squareEl.style.top = `${displayRow * 12.5}%`;

      if (displayCol === 0) {
        const rank = createCoordinateLabel(square[1], !isLight);
        rank.classList.add("rank");
        squareEl.appendChild(rank);
      }
      if (displayRow === 7) {
        const file = createCoordinateLabel(square[0], !isLight);
        file.classList.add("file");
        squareEl.appendChild(file);
      }

      if (piece !== ".") {
        const pieceEl = document.createElement("img");
        pieceEl.src = PIECE_IMAGE[piece];
        pieceEl.alt = piece;
        pieceEl.draggable = false;
        pieceEl.className = "piece";
        pieceEl.dataset.square = square;
        pieceEl.dataset.piece = piece;
        squareEl.appendChild(pieceEl);
      }

      boardEl.appendChild(squareEl);
    }
  }
}

function applyUciMoveToMatrix(matrix, moveText) {
  if (!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(moveText)) {
    return;
  }

  const fromSquare = moveText.slice(0, 2);
  const toSquare = moveText.slice(2, 4);
  const promotion = moveText.length === 5 ? moveText[4] : null;

  const from = squareToBoardCoord(fromSquare);
  const to = squareToBoardCoord(toSquare);
  const movingPiece = matrix[from.row][from.col];
  if (!movingPiece || movingPiece === ".") {
    return;
  }

  const isWhite = movingPiece === movingPiece.toUpperCase();
  const pieceType = movingPiece.toLowerCase();

  if (pieceType === "k" && Math.abs(to.col - from.col) === 2) {
    if (to.col === 6) {
      const rook = matrix[from.row][7];
      matrix[from.row][7] = ".";
      matrix[from.row][5] = rook;
    } else if (to.col === 2) {
      const rook = matrix[from.row][0];
      matrix[from.row][0] = ".";
      matrix[from.row][3] = rook;
    }
  }

  if (pieceType === "p" && from.col !== to.col && matrix[to.row][to.col] === ".") {
    const captureRow = isWhite ? to.row + 1 : to.row - 1;
    if (captureRow >= 0 && captureRow < 8) {
      matrix[captureRow][to.col] = ".";
    }
  }

  matrix[from.row][from.col] = ".";
  const nextPiece = promotion ? (isWhite ? promotion.toUpperCase() : promotion.toLowerCase()) : movingPiece;
  matrix[to.row][to.col] = nextPiece;
}

function buildHistoryBoards(moveList) {
  const snapshots = [cloneBoard(STARTING_BOARD)];
  const current = cloneBoard(STARTING_BOARD);
  for (const moveText of moveList) {
    applyUciMoveToMatrix(current, moveText);
    snapshots.push(cloneBoard(current));
  }
  return snapshots;
}

function setViewedPly(ply, statusText) {
  if (!game) {
    return;
  }

  const maxPly = game.moveList.length;
  viewedPly = Math.max(0, Math.min(ply, maxPly));
  const nextBoard = historyBoards[viewedPly] || historyBoards[maxPly] || STARTING_BOARD;
  boardMatrix = cloneBoard(nextBoard);
  selectedSquare = null;

  renderBoard();
  renderMeta();
  renderMoveList();

  if (statusText) {
    setStatus(statusText);
  }
}

function stepReview(delta) {
  if (!canReviewHistory()) {
    return;
  }
  const maxPly = game.moveList.length;
  const nextPly = Math.max(0, Math.min(maxPly, viewedPly + delta));
  if (nextPly === viewedPly) {
    return;
  }
  setViewedPly(nextPly, reviewStatusText(nextPly));
}

function updateBoardFromGame(nextGame) {
  const previousGameId = game ? game.id : null;
  const previousViewedPly = viewedPly;

  game = nextGame;
  orientation = game.userColor;
  historyBoards = buildHistoryBoards(game.moveList);

  if (game.id !== previousGameId || game.status === "in_progress") {
    viewedPly = game.moveList.length;
  } else {
    viewedPly = Math.min(previousViewedPly, game.moveList.length);
  }

  setViewedPly(viewedPly);
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
  const nextGame = await requestJSON(`/api/board/game/${gameId}`);
  updateBoardFromGame(nextGame);
}

async function play() {
  try {
    const payload = await requestJSON("/api/challenge/open", { method: "POST" });
    setGameInUrl(payload.challenge.id);
    updateBoardFromGame(payload.game);
    setStatus(`Assigned ${game.userColor}. ${game.userToMove ? "Your move." : "AI moved first."}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function sendMove(fromSquare, toSquare) {
  if (!game) {
    throw new Error("Press Play first.");
  }
  const uci = `${fromSquare}${toSquare}`;
  const payload = await requestJSON(`/api/board/game/${game.id}/move/${uci}`, { method: "POST" });
  updateBoardFromGame(payload.game);
}

function cleanupDrag() {
  if (!dragging) {
    return;
  }
  if (dragging.originPiece) {
    dragging.originPiece.classList.remove("origin-hidden");
  }
  if (dragging.ghost && dragging.ghost.parentNode) {
    dragging.ghost.parentNode.removeChild(dragging.ghost);
  }
  dragging = null;
}

function moveGhost(clientX, clientY) {
  if (!dragging) {
    return;
  }
  dragging.ghost.style.left = `${clientX - 32}px`;
  dragging.ghost.style.top = `${clientY - 32}px`;
}

function findSquareAtPoint(clientX, clientY) {
  const hit = document.elementFromPoint(clientX, clientY);
  if (!hit) {
    return null;
  }
  const squareEl = hit.closest(".square");
  if (!squareEl) {
    return null;
  }
  return squareEl.dataset.square;
}

boardEl.addEventListener("pointerdown", (event) => {
  const pieceEl = event.target.closest(".piece");
  if (!pieceEl) {
    return;
  }
  if (!userCanMove()) {
    setStatus(game ? "Wait for your turn." : "Press Play first.", true);
    return;
  }
  if (!pieceBelongsToUser(pieceEl.dataset.piece)) {
    return;
  }

  event.preventDefault();
  const ghost = pieceEl.cloneNode(true);
  ghost.classList.add("dragging-piece");
  document.body.appendChild(ghost);
  pieceEl.classList.add("origin-hidden");

  dragging = {
    pointerId: event.pointerId,
    fromSquare: pieceEl.dataset.square,
    originPiece: pieceEl,
    ghost,
  };

  selectedSquare = pieceEl.dataset.square;
  fromInput.value = selectedSquare;
  toInput.value = "";
  moveGhost(event.clientX, event.clientY);
  renderBoard();
  boardEl.setPointerCapture(event.pointerId);
  setStatus(`Dragging from ${selectedSquare}...`);
});

boardEl.addEventListener("pointermove", (event) => {
  if (!dragging || dragging.pointerId !== event.pointerId) {
    return;
  }
  moveGhost(event.clientX, event.clientY);
});

boardEl.addEventListener("pointerup", async (event) => {
  if (!dragging || dragging.pointerId !== event.pointerId) {
    return;
  }
  const fromSquare = dragging.fromSquare;
  const toSquare = findSquareAtPoint(event.clientX, event.clientY);
  cleanupDrag();

  if (!toSquare || toSquare === fromSquare) {
    renderBoard();
    setStatus("Move cancelled.");
    return;
  }

  fromInput.value = fromSquare;
  toInput.value = toSquare;

  try {
    await sendMove(fromSquare, toSquare);
    setStatus(moveResultStatus());
  } catch (error) {
    renderBoard();
    setStatus(error.message, true);
  }
});

boardEl.addEventListener("pointercancel", () => {
  cleanupDrag();
  renderBoard();
});

boardEl.addEventListener("click", async (event) => {
  if (dragging) {
    return;
  }
  const squareEl = event.target.closest(".square");
  if (!squareEl || !userCanMove()) {
    return;
  }
  const square = squareEl.dataset.square;
  const { row, col } = squareToBoardCoord(square);
  const piece = boardMatrix[row][col];

  if (!selectedSquare) {
    if (!pieceBelongsToUser(piece)) {
      return;
    }
    selectedSquare = square;
    fromInput.value = square;
    toInput.value = "";
    renderBoard();
    setStatus(`From ${square}. Pick destination.`);
    return;
  }

  const fromSquare = selectedSquare;
  const toSquare = square;
  fromInput.value = fromSquare;
  toInput.value = toSquare;

  try {
    await sendMove(fromSquare, toSquare);
    setStatus(moveResultStatus());
  } catch (error) {
    setStatus(error.message, true);
    renderBoard();
  }
});

movesEl.addEventListener("click", (event) => {
  const button = event.target.closest(".history-move");
  if (!button || !canReviewHistory()) {
    return;
  }

  const ply = Number(button.dataset.ply);
  if (!Number.isInteger(ply)) {
    return;
  }

  setViewedPly(ply, reviewStatusText(ply));
});

window.addEventListener("keydown", (event) => {
  if (!canReviewHistory() || isTypingElement(event.target)) {
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    stepReview(-1);
    return;
  }

  if (event.key === "ArrowRight") {
    event.preventDefault();
    stepReview(1);
    return;
  }

  if (event.key === "Home") {
    event.preventDefault();
    setViewedPly(0, reviewStatusText(0));
    return;
  }

  if (event.key === "End") {
    event.preventDefault();
    setViewedPly(game.moveList.length, reviewStatusText(game.moveList.length));
  }
});

moveButton.addEventListener("click", async () => {
  if (!userCanMove()) {
    setStatus(game ? "Wait for your turn." : "Press Play first.", true);
    return;
  }
  const fromSquare = fromInput.value.trim().toLowerCase();
  const toSquare = toInput.value.trim().toLowerCase();
  if (fromSquare.length !== 2 || toSquare.length !== 2) {
    setStatus("Enter both squares.", true);
    return;
  }

  try {
    await sendMove(fromSquare, toSquare);
    setStatus(moveResultStatus());
  } catch (error) {
    setStatus(error.message, true);
  }
});

playButton.addEventListener("click", play);

async function restoreFromUrl() {
  const gameId = new URLSearchParams(window.location.search).get("game");
  if (!gameId) {
    return;
  }
  try {
    await loadGame(gameId);
    setStatus("Session restored.");
  } catch {
    setStatus("Could not restore session. Press Play.", true);
  }
}

renderBoard();
renderMeta();
renderMoveList();
restoreFromUrl();
