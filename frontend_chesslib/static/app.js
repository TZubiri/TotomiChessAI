let game = new Chess();
let board = null;
let activeSessionId = null;

const createButton = document.getElementById("create-session");
const statusEl = document.getElementById("status");
const sessionListEl = document.getElementById("session-list");

function setStatus(text) {
  statusEl.textContent = text;
}

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

function rebuildGameFromMoves(moves) {
  game = new Chess();
  for (const move of moves) {
    const legal = game.move({ from: move.slice(0, 2), to: move.slice(2, 4), promotion: move[4] || "q" });
    if (!legal) {
      throw new Error(`invalid move in history: ${move}`);
    }
  }
}

async function refreshSessionList() {
  const payload = await requestJSON("/api/sessions");
  sessionListEl.innerHTML = "";
  for (const session of payload.sessions) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = `${session.session_id} (${session.turn})`;
    btn.addEventListener("click", () => loadSession(session.session_id));
    li.appendChild(btn);
    sessionListEl.appendChild(li);
  }
}

async function loadSession(sessionId) {
  const session = await requestJSON(`/api/sessions/${sessionId}`);
  activeSessionId = sessionId;
  rebuildGameFromMoves(session.moves);
  board.position(game.fen());
  setStatus(`Loaded session ${sessionId}. Turn: ${session.turn}.`);
  await refreshSessionList();
}

async function createSession() {
  try {
    const created = await requestJSON("/api/sessions", { method: "POST" });
    await loadSession(created.session_id);
  } catch (error) {
    setStatus(error.message);
  }
}

async function sendMove(uci) {
  if (!activeSessionId) {
    return;
  }
  try {
    await requestJSON(`/api/sessions/${activeSessionId}/moves`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uci }),
    });
    await refreshSessionList();
  } catch (error) {
    throw error;
  }
}

function onDrop(source, target) {
  const promotion = "q";
  const move = game.move({ from: source, to: target, promotion });
  if (!move) {
    return "snapback";
  }
  const uci = `${source}${target}${move.promotion || ""}`;
  sendMove(uci)
    .then(() => {
      setStatus(`Move ${uci} accepted.`);
    })
    .catch((error) => {
      game.undo();
      board.position(game.fen());
      setStatus(error.message);
    });
  return undefined;
}

function onSnapEnd() {
  board.position(game.fen());
}

function initBoard() {
  board = Chessboard("board", {
    draggable: true,
    position: "start",
    onDrop,
    onSnapEnd,
  });
}

createButton.addEventListener("click", createSession);

initBoard();
refreshSessionList();
