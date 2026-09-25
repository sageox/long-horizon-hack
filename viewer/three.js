import {
  DAY_END,
  WALL,
  CHECKS,
  STRATEGIES,
  clock,
  formatAction,
  parseEvents,
  stateAt,
} from "./replay.js";

const $ = (selector) => document.querySelector(selector);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const number = (value) => Math.round(value).toLocaleString("en-US");
const params = new URLSearchParams(location.search);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const source = params.get("events");
const colors = {
  full_history: "#bd7c62",
  sliding_window: "#b8995d",
  task_board: "#668c59",
  rolling_summary: "#9480aa",
};
const symbols = {
  full_history: "≋",
  sliding_window: "▤",
  task_board: "▦",
  rolling_summary: "↻",
};
const descriptions = {
  full_history: "Every event. An ever-growing context.",
  sliding_window: "The newest 4K tokens. The past slips away.",
  task_board: "A task board and memories. A 4K working set.",
  rolling_summary: "A running summary, rewritten as the day goes on.",
};
let data = null,
  selected = "task_board",
  minute = 0,
  playing = false,
  speed = 1;
let scene = null,
  states = {},
  renderedMinute = -1,
  previousFrame = null,
  frameId = null;
let loadVersion = 0;
let activeSource = null,
  watching = false,
  following = false;
let backendRuns = [],
  lastSnapshot = "",
  pollTimer = null;
let waitingForRun = !source;
const strategy = (id) => ({
  name: STRATEGIES[id]?.name || formatAction(id),
  color: colors[id] || "#84967a",
});

function showError(message) {
  $("#notice").textContent = message;
  $("#notice").hidden = false;
}

async function setupScene() {
  try {
    const { createKitchenScene } = await import("./kitchen-scene.js");
    scene = createKitchenScene($("#scene"));
    $("#scene-loading").hidden = true;
    if (data) render(true);
  } catch (error) {
    $("#scene-loading").textContent =
      "The 3D view is unavailable. You can still explore the replay below.";
    $("#reset-camera").disabled = true;
    showError(
      `Could not start the 3D kitchen: ${error.message}. Run npm install in viewer/ and use a browser with WebGL2 enabled.`,
    );
  }
}

function installData(text, name) {
  const parsed = parseEvents(text);
  setPlaying(false);
  data = parsed;
  selected = data.robots.includes(params.get("robot"))
    ? params.get("robot")
    : data.robots.includes("task_board")
      ? "task_board"
      : data.robots[0];
  minute = 0;
  $("#data-badge").textContent = data.mock
    ? "ILLUSTRATIVE REPLAY"
    : "EVENT REPLAY";
  $("#data-badge").title = data.mock
    ? "Scripted target outcomes, not measured model results."
    : "Loaded event log; this is a replay, not a live run.";
  $("#source-label").textContent =
    `${name.split("/").pop()} · ${data.mock ? "Scripted outcomes" : "Recorded events"} · 3D reconstruction`;
  $("#source-label").title = name;
  $("#timeline").max = data.duration;
  $("#play").disabled =
    $("#restart").disabled =
    $("#timeline").disabled =
    $("#scorecard-button").disabled =
      false;
  $("#notice").hidden = true;
  $("#scorecard").close();
  buildStrategies();
  buildMilestones();
  seek(0);
}

function playbackEnd() {
  return watching ? data.rows.at(-1).t : data.duration;
}

function updateSource() {
  if (!data) return;
  const run = backendRuns.find((run) => run.url === activeSource);
  $("#data-badge").textContent = data.mock
    ? "ILLUSTRATIVE REPLAY"
    : following
      ? "FOLLOWING BACKEND"
      : watching
        ? "BACKEND REPLAY"
        : "EVENT REPLAY";
  $("#data-badge").title = data.mock
    ? "Scripted outcomes, not measured model results."
    : watching
      ? "Reading the Python runner’s event file. New rows are loaded automatically."
      : "Loaded event log; this is a replay.";
  $("#source-label").textContent =
    `${run ? `Python run: ${run.name}` : activeSource?.split("/").pop() || "Imported file"} · ${data.mock ? "Scripted outcomes" : "Recorded events"} · 3D reconstruction`;
  $("#follow-backend").hidden = !watching;
  $("#follow-backend").setAttribute("aria-pressed", following);
  $("#follow-backend").textContent = following
    ? "Following backend"
    : "Follow backend";
  $("#backend-run").value = activeSource || "";
}

function followBackend(on) {
  following = on && watching;
  if (following) {
    setPlaying(false);
    seek(playbackEnd(), true);
  }
  updateSource();
  if (!following) render(true);
}

async function refreshBackendRuns() {
  const response = await fetch("/api/runs", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const { runs } = await response.json();
  const catalogChanged = JSON.stringify(runs) !== JSON.stringify(backendRuns);
  backendRuns = runs;
  $("#backend-status").textContent =
    `${runs.filter((run) => !run.mock).length} recorded runs available`;
  if (catalogChanged)
    $("#backend-run").innerHTML =
      `<option value="" disabled>Choose a run</option>${runs.map((run) => `<option value="${escape(run.url)}">${escape(run.name)}${run.mock ? " (mock)" : ""} · ${clock(run.last_t)}</option>`).join("")}<option value="../runs/mock/events.jsonl">Illustrative demo (mock)</option>`;
  $("#backend-run").value = activeSource || "";
  if (waitingForRun) {
    const latest = runs.find((run) => !run.mock);
    if (latest) {
      waitingForRun = !(await loadUrl(latest.url, true));
    } else {
      $("#data-badge").textContent = "WAITING FOR PYTHON";
      $("#backend-status").textContent =
        "No recorded runs yet. Start the Python runner or choose the illustrative demo.";
    }
  }
}

async function refreshSnapshot() {
  const version = loadVersion,
    url = activeSource;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const text = await response.text();
  if (version !== loadVersion || text === lastSnapshot) return;
  // The backend flushes whole JSONL rows. Ignore a partial row during a write.
  const snapshot = text.slice(0, text.lastIndexOf("\n") + 1);
  if (!snapshot.trim()) {
    $("#backend-status").textContent =
      "Waiting for the first complete event; last snapshot retained.";
    return;
  }
  const next = parseEvents(snapshot);
  const robotsChanged = data.robots.join("\n") !== next.robots.join("\n");
  data = next;
  lastSnapshot = text;
  if (!data.robots.includes(selected)) selected = data.robots[0];
  if (robotsChanged) buildStrategies();
  buildMilestones();
  $("#timeline").max = data.duration;
  if (following) seek(playbackEnd(), true);
  else seek(Math.min(minute, playbackEnd()), true);
  updateSource();
}

async function pollBackend() {
  try {
    await refreshBackendRuns();
    if (watching && data) await refreshSnapshot();
  } catch (error) {
    $("#backend-status").textContent =
      `Connection unavailable (${error.message}). ${data ? "Last snapshot retained." : "Start npm run dev to connect."}`;
  } finally {
    pollTimer = setTimeout(pollBackend, 2000);
  }
}

async function loadUrl(url, initial = false) {
  const version = ++loadVersion;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const text = await response.text();
    if (version !== loadVersion) return;
    installData(text, url);
    activeSource = url;
    watching = url.startsWith("/backend-runs/") || params.get("live") === "1";
    lastSnapshot = text;
    following = false;
    const inProgress = !data.robots.every((robot) =>
      data.rows.some((row) => row.robot === robot && row.t >= DAY_END),
    );
    if (
      watching &&
      (params.get("live") === "1" || (inProgress && !params.has("at")))
    )
      followBackend(true);
    if (initial) {
      const match = /^(\d{1,2}):(\d{2})$/.exec(params.get("at") || "");
      if (match && Number(match[2]) < 60)
        seek((Number(match[1]) - 8) * 60 + Number(match[2]));
      if (params.get("autoplay") === "1") setPlaying(true);
    }
    updateSource();
    return true;
  } catch (error) {
    if (version !== loadVersion) return;
    $("#data-badge").textContent = data
      ? $("#data-badge").textContent
      : "NO REPLAY LOADED";
    showError(
      `Couldn't load ${url}: ${error.message}. Use “Load run” to choose an events.jsonl file, or start the demo with “cd viewer && npm install && npm run dev”.`,
    );
    return false;
  }
}

async function loadFile(file) {
  if (!file) return;
  waitingForRun = false;
  const version = ++loadVersion;
  try {
    const text = await file.text();
    if (version !== loadVersion) return;
    installData(text, file.name);
    activeSource = null;
    watching = following = waitingForRun = false;
    updateSource();
  } catch (error) {
    if (version === loadVersion)
      showError(`Couldn't load ${file.name}: ${error.message}`);
  }
}

function buildStrategies() {
  $("#strategies").style.setProperty(
    "--strategy-count",
    Math.min(data.robots.length, 4),
  );
  $(".subtitle").textContent =
    `${data.robots.length} memory ${data.robots.length === 1 ? "strategy" : "strategies"}. One robot. Ten hours to get it right.`;
  $("#strategies").innerHTML = data.robots
    .map((id) => {
      const info = strategy(id);
      return `<button class="strategy-card" data-robot="${escape(id)}" style="--strategy:${info.color}" aria-pressed="${id === selected}" aria-label="Follow ${escape(info.name)}">
      <div class="strategy-top"><span class="strategy-symbol" aria-hidden="true">${symbols[id] || "◇"}</span><span class="strategy-name">${escape(info.name)}</span><span class="following">FOLLOWING</span></div>
      <p class="strategy-description">${escape(descriptions[id] || "Events from this strategy’s recorded day.")}</p>
      <div class="strategy-middle"><span class="token-number"><span class="tokens">0</span><small>tokens</small></span><span class="score-number"><span class="score">0</span><small> / 6</small></span></div>
      <div class="metric-labels"><span>PROMPT CONTEXT</span><span>CHECKS PASSED</span></div>
      <svg class="sparkline" viewBox="0 0 320 36" preserveAspectRatio="none" role="img" aria-label="Context tokens over time; dashed line is the 32,768-token limit"><path class="area"/><path class="limit" d="M0 9H320"/><path class="curve"/></svg>
      <div class="strategy-footer"><span class="strategy-health">Day just started</span><span class="check-dots">${CHECKS.map((check) => `<i data-check="${check.id}" title="${check.label}: pending">·</i>`).join("")}</span></div>
    </button>`;
    })
    .join("");
}

function buildMilestones() {
  const markers = [
    [60, "Vegan guest"],
    [182, "Dryer breaks"],
    [240, "One more guest"],
  ];
  const cut = data.rows.find(
    (row) =>
      row.kind === "system" &&
      (row.system === "power_cut" || /power[\s_-]*cut/i.test(row.text || "")),
  );
  if (cut) markers.push([cut.t, "Power cut", "power"]);
  markers.push([570, "Roast check"], [DAY_END, "Dinner", "end"]);
  $("#milestones").innerHTML = markers
    .map(
      ([t, label, cls = ""]) =>
        `<button class="milestone ${cls}" style="left:${(t / data.duration) * 100}%" data-minute="${t}" title="${clock(t)} · ${label}" aria-label="Jump to ${clock(t)}: ${label}">${label}</button>`,
    )
    .join("");
  $(".timeline-labels").innerHTML = Array.from(
    { length: 6 },
    (_, i) => `<span>${clock((data.duration * i) / 5)}</span>`,
  ).join("");
}

function seek(next, fromBackend = false) {
  if (!data) return;
  if (!fromBackend) followBackend(false);
  minute = Math.max(0, Math.min(playbackEnd(), next));
  if (minute >= playbackEnd() && playing) setPlaying(false);
  render(true);
}

function render(force = false) {
  if (!data) return;
  const tick = Math.floor(minute);
  if (!force && tick === renderedMinute) return;
  renderedMinute = tick;
  states = Object.fromEntries(
    data.robots.map((id) => [id, stateAt(data.rows, id, minute)]),
  );
  const state = states[selected],
    info = strategy(selected);
  $("#clock").textContent = clock(minute);
  $("#timeline").value = tick;
  $("#timeline").setAttribute("aria-valuetext", clock(minute));
  $("#timeline").style.setProperty(
    "--progress",
    `${(minute / data.duration) * 100}%`,
  );
  $("#scene-strategy").textContent = info.name;
  $("#scene-status").textContent = state.powerCut
    ? "RESTARTING"
    : state.overflow
      ? "CONTEXT FULL"
      : following
        ? "FOLLOWING"
        : playing
          ? "PLAYING"
          : "PAUSED";
  $("#strategy-dot").style.background = info.color;
  $("#scene-period").textContent =
    minute < 240
      ? "Morning light"
      : minute < 480
        ? "Afternoon light"
        : "Evening light";
  $("#day-phase").textContent =
    minute >= DAY_END
      ? "DINNER IS HERE"
      : minute >= 480
        ? "THE FINAL STRETCH"
        : minute >= 360
          ? "THE LONG AFTERNOON"
          : minute >= 240
            ? "A CHANGE OF PLANS"
            : "THE MORNING ROUTINE";
  $("#guest-count").textContent =
    `${minute >= 240 ? "Seven" : "Six"} guests. Four dishes. No new session.`;
  $("#power-banner").hidden = !state.powerCut;
  document
    .querySelectorAll(".milestone")
    .forEach((button) =>
      button.classList.toggle("past", Number(button.dataset.minute) <= minute),
    );
  renderCaption(state);
  renderMemory(state);
  renderActivity(state);
  document
    .querySelectorAll(".strategy-card")
    .forEach((card) => renderStrategy(card, states[card.dataset.robot]));
  if ($("#scorecard").open) renderScorecard();
  scene?.update({
    minute,
    robot: selected,
    color: info.color,
    kitchen: state.kitchen,
    powerCut: state.powerCut,
    overflow: state.overflow,
    playing: playing && !reducedMotion.matches,
  });
}

function renderCaption(state) {
  const latest = state.feed.findLast((row) => row.kind !== "board");
  let text = "Good morning. Dinner is in ten hours.",
    kicker = "08:00 · A FRESH START";
  if (latest) {
    text =
      latest.kind === "action"
        ? `${formatAction(latest.action)}${latest.reason ? ` — ${latest.reason}` : ""}`
        : latest.kind === "web"
          ? `Looking up “${latest.query || latest.text}”.`
          : latest.text || text;
    kicker = `${clock(latest.t)} · ${latest.kind === "action" ? "A DECISION MADE" : latest.kind === "goal" ? "TODAY’S GOAL" : "IN THE KITCHEN"}`;
  }
  if (state.powerCut) {
    kicker = `${clock(minute)} · AN INTERRUPTION`;
    text = "Power cut. What survives the restart?";
  } else if (state.overflow) {
    kicker = `${clock(minute)} · THE CONTEXT LIMIT`;
    text = "The context is full. This robot can no longer plan.";
  } else if (minute >= DAY_END) {
    kicker = "18:00 · THE FAMILY ARRIVES";
    text = `${state.score} of ${CHECKS.length} dinner checks passed. ${state.score === CHECKS.length ? "Dinner is ready." : "See what this robot remembered."}`;
  }
  $("#caption-kicker").textContent = kicker;
  $("#caption").textContent = text;
}

function renderMemory(state) {
  const board = state.board;
  const memories =
    board?.memories &&
    typeof board.memories === "object" &&
    !Array.isArray(board.memories)
      ? Object.entries(board.memories)
      : [];
  let html = "";
  if (board) {
    html = `<p class="memory-section-title">WHAT STAYS WITH ME <span>${memories.length} memories</span></p><ul class="memory-list">${memories.map(([key, value]) => `<li class="memory-note"><span class="note-type">${escape(key.split(":")[0].toUpperCase())}</span><p>${escape(value)}</p></li>`).join("")}</ul>`;
    const doing = Array.isArray(board.doing) ? board.doing : [];
    const done = Array.isArray(board.done) ? board.done : [];
    const todo = Array.isArray(board.todo) ? board.todo : [];
    const blocked = Array.isArray(board.blocked) ? board.blocked : [];
    html += `<p class="memory-section-title">ON THE BOARD <span>${done.length} done</span></p>${doing.map((task) => `<p class="task-line">${escape(formatAction(task))}</p>`).join("")}${todo.map((task) => `<p class="task-line">${escape(formatAction(task))}</p>`).join("")}${done.map((task) => `<p class="task-line done">${escape(formatAction(task))}</p>`).join("")}${blocked.map((task) => `<p class="task-line">Blocked: ${escape(formatAction(task))}</p>`).join("")}`;
  } else if (selected === "task_board") {
    html =
      '<div class="empty-memory"><svg><use href="#i-memory"/></svg><strong>A little memory.<br>A long way to go.</strong><p>The day is just beginning. As the robot receives updates, its logged task board and saved memories will appear here.</p></div><p class="memory-section-title">THE FIRST THING TO REMEMBER</p><div class="memory-note"><span class="note-type">GOAL</span><p>Dinner for the family at 18:00.</p></div>';
  } else {
    const title = state.overflow
      ? "Too much to hold."
      : selected === "sliding_window"
        ? "Only the recent past."
        : selected === "rolling_summary"
          ? "The day, condensed."
          : "Every moment adds up.";
    html = `<div class="empty-memory"><svg><use href="#i-memory"/></svg><strong>${title}</strong><p>${escape(STRATEGIES[selected]?.description || "This event log has no task-board snapshot for this robot.")}</p></div><p class="memory-section-title">PROMPT CONTEXT</p><div class="context-retained">${number(state.contextTokens)} <small>/ 32,768 tokens</small></div><div class="memory-note"><span class="note-type">${state.overflow ? "CONTEXT LIMIT REACHED" : "FROM THE LOG"}</span><p>${escape(state.lastDecision?.reason || "No decision logged yet. Play the day to watch this strategy respond.")}</p></div>`;
  }
  $("#memory-content").innerHTML = html;
  $("#memory-mode").textContent = board
    ? state.restored
      ? "BOARD RESTORED AFTER RESTART"
      : "PERSISTENT TASK BOARD"
    : selected === "task_board"
      ? "AWAITING BOARD SNAPSHOT"
      : selected === "sliding_window"
        ? "4K MEMORY BUDGET"
        : selected === "rolling_summary"
          ? "ROLLING SUMMARY"
          : "FULL EVENT HISTORY";
  $("#memory-footnote").textContent = board
    ? "Keeps what matters."
    : selected === "sliding_window"
      ? "What gets left behind?"
      : "One continuous day.";
}

function renderActivity(state) {
  $("#activity-count").textContent = state.feed.length;
  $("#activity-feed").innerHTML =
    [...state.feed]
      .reverse()
      .map((row) => {
        let text =
          row.kind === "action"
            ? `${formatAction(row.action)}${row.reason ? ` — ${row.reason}` : ""}`
            : row.kind === "web"
              ? `Search: ${row.query || ""} · ${row.text || ""}`
              : row.text;
        if (row.check && typeof row.pass === "boolean")
          text = `${row.pass ? "✓" : "×"} ${text}`;
        return `<li><time>${clock(row.t)}</time><div><span class="event-kind">${escape(row.kind.toUpperCase())}</span><p>${escape(text)}</p></div></li>`;
      })
      .join("") || "<li><p>No events for this robot yet.</p></li>";
}

function renderStrategy(card, state) {
  const id = card.dataset.robot;
  card.setAttribute("aria-pressed", id === selected);
  card.classList.toggle("overflow", state.overflow);
  card.querySelector(".tokens").textContent = number(state.contextTokens);
  card.querySelector(".score").textContent = state.score;
  card.querySelector(".strategy-health").textContent = state.overflow
    ? "32K limit reached · planning stopped"
    : state.powerCut
      ? "Restarting from saved state"
      : state.graded === CHECKS.length
        ? "All six checks evaluated"
        : `${state.graded} of 6 checks evaluated`;
  for (const dot of card.querySelectorAll("[data-check]")) {
    const check = state.checks[dot.dataset.check];
    dot.className = check ? (check.pass ? "pass" : "fail") : "";
    dot.textContent = check ? (check.pass ? "✓" : "×") : "·";
    dot.title = `${CHECKS.find((item) => item.id === dot.dataset.check).label}: ${check ? (check.pass ? "passed" : "failed") : "pending"}`;
  }
  // Every chart shares the same time and token scale. The dashed line is 32K.
  const points = data.rows.filter(
    (row) => row.robot === id && row.t <= minute && row.context_tokens != null,
  );
  const path = points
    .map(
      (row, index) =>
        `${index ? "L" : "M"}${((row.t / data.duration) * 320).toFixed(2)},${(35 - Math.min(row.context_tokens / WALL, 1.3) * 26).toFixed(2)}`,
    )
    .join(" ");
  card.querySelector(".curve").setAttribute("d", path);
  card
    .querySelector(".area")
    .setAttribute(
      "d",
      points.length
        ? `${path} L${((points.at(-1).t / data.duration) * 320).toFixed(2)},36 L${((points[0].t / data.duration) * 320).toFixed(2)},36 Z`
        : "",
    );
}

function renderScorecard() {
  $("#score-note").textContent =
    `${clock(minute)} · ${data.mock ? "Illustrative replay — scripted target outcomes, not measured model results." : "Results from the loaded event log."}`;
  $("#score-table").innerHTML =
    `<thead><tr><th scope="col">Memory strategy</th>${CHECKS.map((check) => `<th scope="col">${check.label}</th>`).join("")}<th scope="col">Passed</th></tr></thead><tbody>${data.robots
      .map(
        (id) =>
          `<tr><th scope="row">${escape(strategy(id).name)}</th>${CHECKS.map(
            (check) => {
              const result = states[id].checks[check.id];
              return `<td class="${result ? (result.pass ? "pass" : "fail") : ""}" aria-label="${result ? (result.pass ? "Passed" : "Failed") : "Pending"}">${result ? (result.pass ? "✓" : "×") : "—"}</td>`;
            },
          ).join("")}<td>${states[id].score} / 6</td></tr>`,
      )
      .join("")}</tbody>`;
  $("#jump-end").hidden = minute >= DAY_END;
}

function setPlaying(on) {
  if (on && !data) return;
  if (on) followBackend(false);
  playing = on;
  if (playing && minute >= playbackEnd()) minute = 0;
  $("#play").setAttribute("aria-label", playing ? "Pause day" : "Play day");
  $("#play")
    .querySelector("use")
    .setAttribute("href", playing ? "#i-pause" : "#i-play");
  if (frameId != null) cancelAnimationFrame(frameId);
  frameId = null;
  previousFrame = null;
  render(true);
  if (playing) frameId = requestAnimationFrame(frame);
}

function frame(now) {
  if (!playing) return;
  // One simulated minute per 0.3 seconds, matching the existing viewer.
  if (previousFrame != null)
    minute = Math.min(
      playbackEnd(),
      minute + (Math.min(now - previousFrame, 250) / 300) * speed,
    );
  previousFrame = now;
  if (minute >= playbackEnd()) {
    setPlaying(false);
    return;
  }
  render();
  frameId = requestAnimationFrame(frame);
}

$("#play").onclick = () => setPlaying(!playing);
$("#restart").onclick = () => {
  setPlaying(false);
  seek(0);
};
$("#timeline").oninput = (event) => seek(Number(event.target.value));
$("#speed").onchange = (event) => {
  speed = Number(event.target.value);
};
$("#reset-camera").onclick = () => scene?.resetCamera();
$("#strategies").onclick = (event) => {
  const card = event.target.closest("[data-robot]");
  if (!card) return;
  selected = card.dataset.robot;
  render(true);
};
$("#milestones").onclick = (event) => {
  const marker = event.target.closest("[data-minute]");
  if (marker) seek(Number(marker.dataset.minute));
};
function selectTab(id) {
  for (const name of ["memory", "activity"]) {
    const active = name === id;
    $(`#${name}-tab`).setAttribute("aria-selected", active);
    $(`#${name}-tab`).tabIndex = active ? 0 : -1;
    $(`#${name}-panel`).hidden = !active;
  }
}
for (const id of ["memory", "activity"]) {
  $(`#${id}-tab`).onclick = () => selectTab(id);
  $(`#${id}-tab`).onkeydown = (event) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const next =
        event.key === "Home"
          ? "memory"
          : event.key === "End"
            ? "activity"
            : id === "memory"
              ? "activity"
              : "memory";
      selectTab(next);
      $(`#${next}-tab`).focus();
    }
  };
}
$("#scorecard-button").onclick = () => {
  followBackend(false);
  setPlaying(false);
  renderScorecard();
  $("#scorecard").showModal();
};
$("#close-scorecard").onclick = () => $("#scorecard").close();
$("#scorecard").onclick = (event) => {
  if (
    event.target === $("#scorecard") &&
    (event.clientX < event.target.getBoundingClientRect().left ||
      event.clientX > event.target.getBoundingClientRect().right ||
      event.clientY < event.target.getBoundingClientRect().top ||
      event.clientY > event.target.getBoundingClientRect().bottom)
  )
    event.target.close();
};
$("#jump-end").onclick = () => {
  setPlaying(false);
  seek(DAY_END);
};
$("#import").onclick = () => $("#file").click();
for (const destination of ["index.html", "tinybird.html"]) {
  const link = document.querySelector(`nav a[href="${destination}"]`);
  link.onclick = () => {
    const query = activeSource
      ? new URLSearchParams({ events: activeSource, at: clock(minute), ...(params.has("source") && { source: params.get("source") }) })
      : "";
    link.href = `${destination}${query ? `?${query}` : ""}`;
  };
}
$("#backend-run").onchange = (event) => {
  waitingForRun = false;
  loadUrl(event.target.value);
};
$("#follow-backend").onclick = () => followBackend(!following);
$("#file").onchange = (event) => {
  loadFile(event.target.files[0]);
  event.target.value = "";
};
addEventListener("keydown", (event) => {
  if (
    event.target.closest(
      "button, input, select, textarea, a, [contenteditable]",
    ) ||
    $("#scorecard").open ||
    event.metaKey ||
    event.ctrlKey ||
    event.altKey ||
    !data
  )
    return;
  if (event.code === "Space") {
    event.preventDefault();
    setPlaying(!playing);
  } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
    event.preventDefault();
    seek(minute + (event.key === "ArrowRight" ? 10 : -10));
  } else if (event.key.toLowerCase() === "r") {
    setPlaying(false);
    seek(0);
  } else if (["1", "2", "4"].includes(event.key)) {
    speed = Number(event.key);
    $("#speed").value = event.key;
  }
});
addEventListener("dragover", (event) => {
  if (!event.dataTransfer.types.includes("Files")) return;
  event.preventDefault();
  $("#drop-overlay").hidden = false;
});
addEventListener("dragleave", (event) => {
  if (!event.relatedTarget) $("#drop-overlay").hidden = true;
});
addEventListener("drop", (event) => {
  event.preventDefault();
  $("#drop-overlay").hidden = true;
  loadFile(event.dataTransfer.files[0]);
});
document.addEventListener("visibilitychange", () => {
  previousFrame = null;
});
addEventListener("pagehide", (event) => {
  clearTimeout(pollTimer);
  if (frameId != null) cancelAnimationFrame(frameId);
  if (!event.persisted) scene?.dispose();
});
addEventListener("pageshow", (event) => {
  if (event.persisted) {
    setPlaying(playing);
    pollBackend();
  }
});

setupScene();
if (source) loadUrl(source, true);
pollBackend();
