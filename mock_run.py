"""A mock events.jsonl: the TARGET day, not a result.

Writes runs/mock/events.jsonl so the viewer and the Tinybird pipes can be
built before run.py exists. Every line carries "mock": true and the viewer
badges it. Token counts are kitchen.py's chars/4 estimate; decisions are the
target scorecard (full history 2/6, sliding window 1/6, task board 6/6) with
hand-written reasons. Never show this as a run.

    python mock_run.py [--out runs/mock/events.jsonl]
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import kitchen

WALL, OVERHEAD, BUDGET = 32_768, 600, 4_096
ROBOTS = ["full_history", "sliding_window", "task_board"]

REASONS = {
    "crumble_out": "The crumble went in at 10:40 for 20 minutes.",
    "stew_vegan": "Leo is vegan and this recipe uses olive oil.",
    "cloth": "The dryer broke; the cloth is on the bathroom line.",
    "seven_places": "Mia is coming, so seven.",
    "roast_out": "The roast went in at 14:00 for three and a half hours.",
    "salted_once": "The stew was salted at 13:30.",
}
WINDOW_MISSES = {  # what the window robot does once the fact has scrolled away
    "stew_vegan": ("stew_with_butter", "The recipe calls for butter."),
    "cloth": ("get_cloth_from_dryer", "Tablecloths dry in the dryer."),
    "seven_places": ("set_table_for_6", "The goal says six people."),
    "roast_out": ("continue_chores", "Nothing in view needs doing."),
    "salted_once": ("add_salt", "The recipe says season before serving."),
}
QUERIES = {
    "full_history": "vegan vegetable stew",
    "sliding_window": "vegetable stew recipe",
    "task_board": "vegan vegetable stew for 7",
}
MEMORIES = {  # t: (key, text) the curator would keep
    60: ("constraint:leo_vegan", "Leo is vegan since the summer."),
    185: ("lesson:dryer_broken", "Dryer is broken; tablecloth is on the bathroom line."),
    240: ("update:guests=7", "Mia is coming, seven people."),
}
BOARD_MOVES = {  # t: (task, column, note)
    160: ("crumble", "doing", "crumble in since 10:40, out at 11:00"),
    180: ("crumble", "done", "crumble"),
    300: ("stew", "doing", "stew on since 13:00, olive oil"),
    330: ("stew", "doing", "stew simmering since 13:30, salted"),
    360: ("roast", "doing", "roast in since 14:00, out at 17:30"),
    480: ("salad", "done", "salad"),
    510: ("set_table", "doing", "tablecloth on, laying for 7"),
    512: ("set_table", "done", "set_table"),
    570: ("roast", "done", "roast"),
    585: ("stew", "done", "stew"),
}


def tokens(line: dict) -> int:
    return kitchen.RENDERS["as JSON"](line)


def text(line: dict) -> str:
    return next(str(line[k]) for k in ("goal", "event", "see", "web") if k in line)


class Board:
    def __init__(self):
        self.cols = {"todo": ["crumble", "stew", "roast", "salad", "set_table"],
                     "doing": [], "done": [], "blocked": []}
        self.notes: dict[str, str] = {}
        self.memories: dict[str, str] = {}

    def move(self, task: str, col: str, note: str) -> None:
        for c in self.cols.values():
            if task in c:
                c.remove(task)
        self.cols[col].append(task)
        self.notes[task] = note

    def as_json(self) -> str:
        cols = {c: [self.notes.get(t, t) if c == "doing" else t for t in ts] for c, ts in self.cols.items()}
        return json.dumps({**cols, "memories": self.memories})


def run(day: list[dict]) -> list[dict]:
    out: list[dict] = []
    full = 0  # full history: every observed line survives, reboot included
    window: deque[int] = deque()  # sliding window: the newest lines that fit
    recent: deque[int] = deque(maxlen=10)  # task board: the last 10 lines
    board = Board()
    goal = kitchen.est_tokens(day[0]["goal"])

    def emit(robot, line, kind, text_, ctx, **extra):
        out.append({"robot": robot, "t": line["t"], "clock": line["clock"], "kind": kind,
                    "text": text_, **extra, "context_tokens": ctx, "mock": True})

    def ctx(robot):  # the whole prompt, as on the sample's overflow line
        if robot == "full_history":
            return OVERHEAD + full
        if robot == "sliding_window":
            return OVERHEAD + goal + sum(window)
        return OVERHEAD + goal + kitchen.est_tokens(board.as_json()) + sum(recent)

    def observe(n):
        nonlocal full
        full += n
        window.append(n)
        while goal + sum(window) > BUDGET:
            window.popleft()
        recent.append(n)

    for line in day:
        t = line["t"]
        if "ask" in line:
            check = line["check"]
            for robot in ROBOTS:
                action, reason = check["pass_if"], REASONS[check["id"]]
                if robot == "sliding_window" and check["id"] in WINDOW_MISSES:
                    action, reason = WINDOW_MISSES[check["id"]]
                if t == 300:  # the stew: one lookup first
                    page = kitchen.search_recipe(QUERIES[robot], live=False)
                    web = kitchen.web_line(t, line["clock"], page)
                    if robot == "sliding_window":
                        action, reason = "stew_with_butter", "The recipe calls for butter."
                    emit(robot, line, "web", page["title"], ctx(robot), query=page["query"])
                if ctx(robot) > WALL:
                    emit(robot, line, "error", f"prompt is {ctx(robot):,} tokens, over the 32,768 window",
                         ctx(robot), action="context_overflow", check=check["id"], pass_=False)
                else:
                    emit(robot, line, "action", action, ctx(robot), action=action, reason=reason,
                         check=check["id"], pass_=kitchen.grade(line, action))
            if t == 300:
                observe(tokens(web))
            observe(12)  # the "did" line
        else:
            kind = "system" if "system" in line else ("event" if "event" in line or "goal" in line else "see")
            body = f"Goal: {line['goal']}" if "goal" in line else text(line)
            observe(tokens(line))
            for robot in ROBOTS:
                if robot == "task_board" and line.get("system") == "power_cut":
                    emit(robot, line, "system", body, 0)
                    emit(robot, line, "board", "restored from tinybird", ctx(robot), board=board.as_json())
                    continue
                emit(robot, line, kind, body, ctx(robot))
        changed = []
        if t in MEMORIES and "ask" not in line:
            key, note = MEMORIES[t]
            board.memories[key] = note
            changed.append(f"memory added: {key}")
        if t in BOARD_MOVES and (t not in (180, 300, 510, 512, 570, 585) or "ask" in line):
            task, col, note = BOARD_MOVES[t]
            board.move(task, col, note)
            changed.append(f"{task} -> {col}")
        if changed:
            emit("task_board", line, "board", "; ".join(changed), ctx("task_board"), board=board.as_json())
    for row in out:  # "pass" is a keyword, so it travels as pass_ until here
        if "pass_" in row:
            row["pass"] = row.pop("pass_")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--day", default=str(kitchen.DAY))
    p.add_argument("--out", default="runs/mock/events.jsonl")
    args = p.parse_args()
    rows = run(kitchen.load_day(args.day))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    score = {r: sum(1 for x in rows if x["robot"] == r and x.get("pass")) for r in ROBOTS}
    wall = next((x["clock"] for x in rows if x["robot"] == "full_history" and x["context_tokens"] > WALL), None)
    print(f"{args.out}: {len(rows)} MOCK lines, target scorecard {score}, full history at the wall from {wall}")


if __name__ == "__main__":
    main()
