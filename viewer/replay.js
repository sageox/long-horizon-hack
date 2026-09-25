export const DAY_END = 600;
export const WALL = 32768;
export const BUDGET = 4096;

export const CHECKS = [
  { id: "crumble_out", label: "Crumble out" },
  { id: "stew_vegan", label: "Vegan stew" },
  { id: "cloth", label: "Tablecloth" },
  { id: "seven_places", label: "Seven places" },
  { id: "roast_out", label: "Roast out" },
  { id: "salted_once", label: "Salted once" },
];

export const STRATEGIES = {
  full_history: {
    name: "Full history",
    description: "Keeps every line it has seen.",
    color: "#e58c65",
  },
  sliding_window: {
    name: "Sliding window",
    description: "Keeps the goal and the newest 4,096 tokens.",
    color: "#dda85c",
  },
  task_board: {
    name: "Task board",
    description:
      "Keeps a board, labelled memories and the last 10 lines in Tinybird.",
    color: "#73cbbb",
  },
  rolling_summary: {
    name: "Rolling summary",
    description: "Rewrites a running summary when the window fills.",
    color: "#b29cde",
  },
};

export function clock(minute) {
  const total = 8 * 60 + Math.max(0, Math.floor(minute));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function formatAction(action) {
  return String(action || "").replaceAll("_", " ");
}

export function parseEvents(text) {
  const rows = [];
  for (const [index, line] of text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .entries()) {
    if (!line.trim()) continue;
    let row;
    try {
      row = JSON.parse(line);
    } catch {
      throw new Error(`Line ${index + 1}: invalid JSON.`);
    }
    const invalid = (message) => {
      throw new Error(`Line ${index + 1}: ${message}`);
    };
    if (!row || typeof row !== "object" || Array.isArray(row))
      invalid("expected an event object.");
    if (typeof row.robot !== "string" || !row.robot.trim())
      invalid("robot must be a nonempty string.");
    if (!Number.isFinite(row.t) || row.t < 0)
      invalid("t must be a finite, nonnegative number of minutes.");
    if (typeof row.kind !== "string" || !row.kind.trim())
      invalid("kind must be a nonempty string.");
    for (const field of ["text", "action", "check", "reason", "query"]) {
      if (row[field] != null && typeof row[field] !== "string")
        invalid(`${field} must be a string.`);
    }
    if (
      row.context_tokens != null &&
      (!Number.isFinite(row.context_tokens) || row.context_tokens < 0)
    ) {
      invalid("context_tokens must be a finite, nonnegative number.");
    }
    if (row.pass != null && typeof row.pass !== "boolean")
      invalid("pass must be true or false.");
    rows.push(row);
  }
  if (!rows.length)
    throw new Error("No events found. Choose a nonempty events.jsonl file.");
  rows.sort((a, b) => a.t - b.t); // Stable sort preserves file order within a minute.
  const order = Object.keys(STRATEGIES);
  const rank = (robot) =>
    order.includes(robot) ? order.indexOf(robot) : order.length;
  const robots = [...new Set(rows.map((row) => row.robot))].sort(
    (a, b) => rank(a) - rank(b),
  );
  return {
    rows,
    robots,
    mock: rows.some((row) => row.mock === true),
    duration: Math.max(DAY_END, rows.at(-1).t),
  };
}

// The shared stage directions in fixtures/script.jsonl. Graded decisions are
// deliberately absent: taking food out, choosing oil, and laying places must
// come from the selected robot's logged actions.
const STAGE = [
  { t: 90, station: "laundry" },
  { t: 150, cloth: "dryer", station: "laundry" },
  { t: 160, crumble: "in_oven", station: "oven" },
  { t: 185, cloth: "line", station: "laundry" },
  { t: 330, salt: true, station: "stove" },
  { t: 360, roast: "in_oven", station: "oven" },
  { t: 480, salad: true, station: "counter" },
];

export function stateAt(rows, robot, minute) {
  const kitchen = {
    roast: "absent",
    crumble: "absent",
    stew: "none",
    saltCount: 0,
    cloth: "none",
    places: 0,
    salad: false,
    served: false,
    station: "counter",
  };
  const state = {
    contextTokens: 0,
    checks: {},
    score: 0,
    graded: 0,
    board: null,
    lastDecision: null,
    feed: [],
    observation: "",
    powerCut: false,
    overflow: false,
    restored: false,
    kitchen,
  };
  let stageIndex = 0;
  let cutAt = null;
  let hasRobot = false;
  const stageUntil = (time) => {
    while (stageIndex < STAGE.length && STAGE[stageIndex].t <= time) {
      const { t, salt, ...changes } = STAGE[stageIndex++];
      Object.assign(kitchen, changes);
      if (salt) kitchen.saltCount++;
    }
  };

  for (const row of rows) {
    if (row.t > minute) break;
    if (row.robot !== robot) continue;
    hasRobot = true;
    stageUntil(row.t);
    if (row.context_tokens != null) state.contextTokens = row.context_tokens;
    if (state.contextTokens > WALL || row.action === "context_overflow")
      state.overflow = true;
    if (row.kind === "see") {
      state.observation = row.text || "";
      continue;
    }
    if (
      CHECKS.some((check) => check.id === row.check) &&
      typeof row.pass === "boolean"
    ) {
      state.checks[row.check] = { pass: row.pass, t: row.t };
    }
    if (row.check || row.kind === "action") state.lastDecision = row;
    if (row.kind === "board" && row.board) {
      try {
        const board =
          typeof row.board === "string" ? JSON.parse(row.board) : row.board;
        if (board && typeof board === "object" && !Array.isArray(board)) {
          state.board = board;
          if (/restored/i.test(row.text || "")) state.restored = true;
        }
      } catch {
        /* Keep the last valid board if a logged snapshot is malformed. */
      }
    }
    if (
      row.kind === "system" &&
      (row.system === "power_cut" || /power[\s_-]*cut/i.test(row.text || ""))
    ) {
      cutAt = row.t;
      state.restored = false;
    }
    if (row.kind === "action") {
      switch (row.action) {
        case "take_crumble_out":
          kitchen.crumble = "out";
          kitchen.station = "oven";
          break;
        case "take_roast_out":
          kitchen.roast = "out";
          kitchen.station = "oven";
          break;
        case "stew_with_oil":
          kitchen.stew = "vegan";
          kitchen.station = "stove";
          break;
        case "stew_with_butter":
          kitchen.stew = "butter";
          kitchen.station = "stove";
          break;
        case "add_salt":
          kitchen.saltCount++;
          kitchen.station = "stove";
          break;
        case "serve_stew":
          kitchen.served = true;
          kitchen.station = "table";
          break;
        case "make_salad":
          kitchen.salad = true;
          kitchen.station = "counter";
          break;
        case "get_cloth_from_bathroom_line":
          kitchen.cloth = "table";
          kitchen.station = "table";
          break;
        case "get_cloth_from_dryer":
          kitchen.cloth = kitchen.cloth === "dryer" ? "table" : "missing";
          kitchen.station = "laundry";
          break;
        case "set_table_for_6":
          kitchen.places = 6;
          kitchen.station = "table";
          break;
        case "set_table_for_7":
          kitchen.places = 7;
          kitchen.station = "table";
          break;
        case "continue_chores":
          kitchen.station = "counter";
          break;
      }
    }
    state.feed.push(row);
    if (state.feed.length > 20) state.feed.shift();
  }
  if (hasRobot) stageUntil(minute);
  if (minute >= 180 && kitchen.crumble === "in_oven")
    kitchen.crumble = "overdue";
  if (minute >= 570 && kitchen.roast === "in_oven") kitchen.roast = "overdue";
  state.powerCut = cutAt != null && minute - cutAt < 6;
  const checks = Object.values(state.checks);
  state.score = checks.filter((check) => check.pass).length;
  state.graded = checks.length;
  return state;
}
