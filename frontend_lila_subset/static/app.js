const statusEl = document.getElementById("status");
const openButton = document.getElementById("open-challenge");
const gameList = document.getElementById("game-list");
const moveForm = document.getElementById("move-form");
const gameIdInput = document.getElementById("game-id");
const uciInput = document.getElementById("uci");

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

async function refreshEvents() {
  const payload = await requestJSON("/api/stream/event");
  gameList.innerHTML = "";
  for (const event of payload.events) {
    const li = document.createElement("li");
    li.textContent = `${event.game.id} | turn: ${event.game.turn} | moves: ${event.game.moves.join(" ") || "-"}`;
    gameList.appendChild(li);
  }
  if (!payload.events.length) {
    const li = document.createElement("li");
    li.textContent = "No active games.";
    gameList.appendChild(li);
  }
}

async function openChallenge() {
  try {
    const payload = await requestJSON("/api/challenge/open", { method: "POST" });
    const gameId = payload.challenge.id;
    gameIdInput.value = gameId;
    setStatus(`Created game ${gameId}.`);
    await refreshEvents();
  } catch (error) {
    setStatus(error.message);
  }
}

async function submitMove(event) {
  event.preventDefault();
  const gameId = gameIdInput.value.trim();
  const uci = uciInput.value.trim().toLowerCase();
  if (!gameId || !uci) {
    return;
  }
  try {
    await requestJSON(`/api/board/game/${gameId}/move/${uci}`, { method: "POST" });
    setStatus(`Move ${uci} applied to ${gameId}.`);
    uciInput.value = "";
    await refreshEvents();
  } catch (error) {
    setStatus(error.message);
  }
}

openButton.addEventListener("click", openChallenge);
moveForm.addEventListener("submit", submitMove);

refreshEvents();
