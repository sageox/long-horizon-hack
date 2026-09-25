import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { DAY_END, WALL, clock, parseEvents, stateAt } from "./replay.js";

function event(t, extra = {}) {
  return {
    robot: "task_board",
    t,
    kind: "event",
    text: "Kitchen event",
    ...extra,
  };
}

function parse(rows) {
  return parseEvents(rows.map((row) => JSON.stringify(row)).join("\n"));
}

test("parsing preserves time ties and includes only robots present in the log", () => {
  const data = parse([
    event(60, { robot: "other_strategy", text: "first" }),
    event(0, { robot: "rolling_summary" }),
    event(60, { robot: "task_board", text: "second", mock: "true" }),
    event(45, { robot: "sliding_window" }),
    event(730, { robot: "full_history" }),
  ]);
  assert.deepEqual(data.robots, [
    "full_history",
    "sliding_window",
    "task_board",
    "rolling_summary",
    "other_strategy",
  ]);
  assert.deepEqual(
    data.rows.filter((row) => row.t === 60).map((row) => row.text),
    ["first", "second"],
  );
  assert.equal(data.duration, 730);
  assert.equal(data.mock, false);
  const single = parse([event(0, { robot: "custom", mock: true })]);
  assert.deepEqual(single.robots, ["custom"]);
  assert.equal(single.mock, true);
  assert.equal(single.duration, DAY_END);
});

test("malformed input reports the source line instead of rendering partial data", () => {
  assert.throws(
    () => parseEvents(`${JSON.stringify(event(0))}\nnot json`),
    /Line 2: invalid JSON/,
  );
  assert.throws(() => parseEvents("[]"), /Line 1: expected an event object/);
  assert.throws(() => parse([event(-1)]), /Line 1: t must be/);
  assert.throws(() => parse([event("60")]), /Line 1: t must be/);
  assert.throws(
    () => parse([event(0, { robot: "" })]),
    /Line 1: robot must be/,
  );
  assert.throws(
    () => parse([event(0, { kind: null })]),
    /Line 1: kind must be/,
  );
  assert.throws(
    () => parse([event(0, { context_tokens: -1 })]),
    /context_tokens must be/,
  );
  assert.throws(
    () => parse([event(0, { pass: "false" })]),
    /pass must be true or false/,
  );
  assert.throws(() => parseEvents("\n \n"), /No events found/);
});

test("the schema sample is accepted without labelling real rows as mock", () => {
  const sample = parseEvents(
    readFileSync(
      new URL("../fixtures/events.sample.jsonl", import.meta.url),
      "utf8",
    ),
  );
  assert.equal(sample.mock, false);
  assert.deepEqual(sample.robots, [
    "full_history",
    "sliding_window",
    "task_board",
  ]);
  assert.equal(stateAt(sample.rows, "task_board", 600).score, 2);
  assert.equal(
    stateAt(sample.rows, "sliding_window", 600).kitchen.stew,
    "butter",
  );
});

test("the complete mock day reproduces all three target scorecards and visible outcomes", () => {
  const directory = mkdtempSync(join(tmpdir(), "dinner-replay-"));
  try {
    const output = join(directory, "events.jsonl");
    execFileSync("python3", [
      fileURLToPath(new URL("../mock_run.py", import.meta.url)),
      "--out",
      output,
    ]);
    const { rows, mock } = parseEvents(readFileSync(output, "utf8"));
    assert.equal(mock, true);
    const full = stateAt(rows, "full_history", 600);
    const window = stateAt(rows, "sliding_window", 600);
    const board = stateAt(rows, "task_board", 600);
    assert.deepEqual([full.score, window.score, board.score], [2, 1, 6]);
    assert.deepEqual([full.graded, window.graded, board.graded], [6, 6, 6]);
    assert.equal(full.overflow, true);
    assert.equal(full.kitchen.roast, "overdue");
    assert.equal(full.kitchen.served, false);
    assert.equal(window.kitchen.stew, "butter");
    assert.equal(window.kitchen.saltCount, 2);
    assert.equal(window.kitchen.cloth, "missing");
    assert.equal(window.kitchen.places, 6);
    assert.equal(window.kitchen.roast, "overdue");
    assert.deepEqual(board.kitchen, {
      roast: "out",
      crumble: "out",
      stew: "vegan",
      saltCount: 1,
      cloth: "table",
      places: 7,
      salad: true,
      served: true,
      station: "table",
    });
    assert.equal(board.restored, true);
    assert.equal(
      board.board.memories["constraint:leo_vegan"],
      "Leo is vegan since the summer.",
    );
    assert.equal(stateAt(rows, "task_board", 179).kitchen.crumble, "in_oven");
    assert.equal(stateAt(rows, "task_board", 180).kitchen.crumble, "out");
    assert.equal(stateAt(rows, "task_board", 569).kitchen.roast, "in_oven");
    assert.equal(stateAt(rows, "task_board", 370).powerCut, true);
    assert.equal(stateAt(rows, "task_board", 376).powerCut, false);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("rewinding discards future decisions and does not mutate earlier states or rows", () => {
  const { rows } = parse([
    event(0),
    event(300, {
      kind: "action",
      action: "stew_with_oil",
      check: "stew_vegan",
      pass: true,
    }),
    event(585, {
      kind: "action",
      action: "serve_stew",
      check: "salted_once",
      pass: true,
    }),
  ]);
  const original = structuredClone(rows);
  const before = stateAt(rows, "task_board", 299);
  assert.equal(stateAt(rows, "task_board", 600).kitchen.served, true);
  assert.deepEqual(stateAt(rows, "task_board", 299), before);
  assert.equal(before.kitchen.stew, "none");
  assert.equal(before.kitchen.served, false);
  assert.equal(before.lastDecision, null);
  assert.equal(before.score, 0);
  assert.deepEqual(rows, original);
});

test("scripted staging and actual actions are replayed chronologically, with actions last at a tie", () => {
  const { rows } = parse([
    event(0),
    event(150, { kind: "action", action: "take_crumble_out" }),
    event(200, { kind: "action", action: "add_salt" }),
    event(360, { kind: "action", action: "take_roast_out" }),
  ]);
  assert.equal(stateAt(rows, "task_board", 160).kitchen.crumble, "in_oven");
  assert.equal(stateAt(rows, "task_board", 330).kitchen.saltCount, 2);
  const final = stateAt(rows, "task_board", 600);
  assert.equal(final.kitchen.roast, "out");
  assert.equal(final.kitchen.crumble, "overdue");
  assert.equal(final.kitchen.served, false);
  assert.equal(final.kitchen.places, 0);
  assert.equal(final.score, 0);
});

test("each check has one authoritative result even when repeated or corrected", () => {
  const { rows } = parse([
    event(180, { kind: "action", check: "crumble_out", pass: true }),
    event(180, { kind: "action", check: "crumble_out", pass: true }),
    event(181, { kind: "error", check: "crumble_out", pass: false }),
    event(182, { kind: "action", check: "not_a_dinner_check", pass: true }),
  ]);
  const repeated = stateAt(rows, "task_board", 180);
  assert.equal(repeated.score, 1);
  assert.equal(repeated.graded, 1);
  const corrected = stateAt(rows, "task_board", 182);
  assert.equal(corrected.score, 0);
  assert.equal(corrected.graded, 1);
  assert.deepEqual(corrected.checks.crumble_out, { pass: false, t: 181 });
});

test("power cuts, restoration, and overflow require their corresponding logged evidence", () => {
  const board = { todo: ["stew"], doing: [], done: [], memories: {} };
  const { rows } = parse([
    event(0, { context_tokens: WALL }),
    event(10, { kind: "error", text: "Recipe lookup failed" }),
    event(370, {
      kind: "system",
      text: "Power cut. Restarting.",
      context_tokens: 0,
    }),
    event(370, {
      kind: "board",
      text: "restored from tinybird",
      board: JSON.stringify(board),
      context_tokens: 1000,
    }),
    event(371, { kind: "board", board: "bad snapshot" }),
    event(400, { kind: "see", text: "Kitchen.", context_tokens: WALL + 1 }),
  ]);
  assert.equal(stateAt(rows, "task_board", 369).powerCut, false);
  assert.equal(stateAt(rows, "task_board", 369).restored, false);
  assert.equal(stateAt(rows, "task_board", 369).overflow, false);
  const restarting = stateAt(rows, "task_board", 375.9);
  assert.equal(restarting.powerCut, true);
  assert.equal(restarting.restored, true);
  assert.deepEqual(restarting.board, board);
  assert.equal(stateAt(rows, "task_board", 376).powerCut, false);
  assert.equal(stateAt(rows, "task_board", 400).overflow, true);
  const explicit = parse([
    event(1, { kind: "error", action: "context_overflow" }),
  ]).rows;
  assert.equal(stateAt(explicit, "task_board", 1).overflow, true);
  const noCut = parse([event(0)]).rows;
  assert.equal(stateAt(noCut, "task_board", 370).powerCut, false);
});

test("the feed keeps the latest twenty non-observations and updates the observation separately", () => {
  const { rows } = parse([
    ...Array.from({ length: 25 }, (_, t) => event(t)),
    event(25, {
      kind: "see",
      text: "Kitchen. Radio on.",
      context_tokens: 1200,
    }),
  ]);
  const state = stateAt(rows, "task_board", 25);
  assert.equal(state.feed.length, 20);
  assert.equal(state.feed[0].t, 5);
  assert.equal(state.feed.at(-1).t, 24);
  assert.equal(state.observation, "Kitchen. Radio on.");
  assert.equal(state.contextTokens, 1200);
  assert.deepEqual(
    [clock(0), clock(180), clock(599.9), clock(600)],
    ["08:00", "11:00", "17:59", "18:00"],
  );
});
