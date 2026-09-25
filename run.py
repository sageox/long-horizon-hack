"""The harness: every robot over one day, runs/<run>/events.jsonl out, a scorecard per robot on stdout.

    uv run run.py --day fixtures/day.jsonl [--robots task_board,...] [--run name]
"""

import argparse
import json
import time
from pathlib import Path

import kitchen
import llm
import memory
import planner

ROBOTS = ["full_history", "sliding_window", "task_board", "rolling_summary"]
BUDGET = 4_096


def latest_board(events: Path, robot: str) -> dict | None:
    """The robot's newest board line: what a reboot reads. M6 points this at Tinybird."""
    board = None
    if events.exists():
        for raw in events.read_text().splitlines():
            row = json.loads(raw)
            if row["robot"] == robot and row["kind"] == "board":
                board = json.loads(row["board"])
    return board


def build(robot: str, run_dir: Path):
    """A fresh memory that restores itself from whatever this run has already written."""
    if robot == "full_history":
        return memory.FullHistory(run_dir / f"{robot}.log.jsonl")
    if robot == "sliding_window":
        return memory.SlidingWindow(BUDGET, run_dir / f"{robot}.log.jsonl")
    if robot == "task_board":
        return memory.TaskBoard(BUDGET, latest_board(run_dir / "events.jsonl", robot))
    if robot == "rolling_summary":
        return memory.RollingSummary(BUDGET, run_dir / f"{robot}.log.jsonl")
    raise SystemExit(f"unknown robot {robot!r}; robots are {', '.join(ROBOTS)}")


def kind_of(line: dict) -> str:
    if "system" in line:
        return "system"
    for kind in ("see", "web"):
        if kind in line:
            return kind
    return "event"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--day", default=str(kitchen.DAY))
    p.add_argument("--robots", default=",".join(ROBOTS))
    p.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S"))
    args = p.parse_args()
    names = args.robots.split(",")
    run_dir = Path("runs") / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    events = run_dir / "events.jsonl"
    for old in [events, *(run_dir / f"{r}.log.jsonl" for r in names)]:  # a rerun under the same name
        old.unlink(missing_ok=True)
    robots = {r: build(r, run_dir) for r in names}
    out = events.open("a")

    def emit(robot: str, line: dict, kind: str, text: str, **extra) -> None:
        context = planner.messages(robots[robot].context(), line["clock"])
        row = {"robot": robot, "t": line["t"], "clock": line["clock"], "kind": kind, "text": text, **extra,
               "context_tokens": llm.count_tokens(llm.render(context))}
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()  # the power cut's restore reads this file

    def observe(robot: str, line: dict, kind: str | None, text: str = "", **extra) -> None:
        mem = robots[robot]
        mem.observe(line)
        if kind:
            emit(robot, line, kind, text, **extra)
        if getattr(mem, "changes", None):
            emit(robot, line, "board", "; ".join(mem.changes), board=json.dumps(mem.board(), ensure_ascii=False))
            mem.changes.clear()

    def ask(robot: str, line: dict) -> None:
        mem, clock = robots[robot], line["clock"]
        graded = {"check": line["check"]["id"]} if "check" in line else {}
        try:
            reply = planner.decide(mem.context(), clock)
            if "search_recipe" in reply:
                page = kitchen.search_recipe(reply["search_recipe"])
                observe(robot, kitchen.web_line(line["t"], clock, page), "web", page["title"], query=page["query"])
                reply = planner.decide(mem.context(), clock, can_search=False)
        except llm.ContextOverflow as e:
            if graded:
                graded["pass"] = kitchen.grade(line, "context_overflow")
            emit(robot, line, "error", str(e), action="context_overflow", **graded)
            return
        action = reply["action"]
        if graded:
            graded["pass"] = kitchen.grade(line, action)
        emit(robot, line, "action", action, action=action, reason=reply["reason"], **graded)
        observe(robot, {"t": line["t"], "clock": clock, "did": action}, None)

    for line in kitchen.load_day(args.day):
        if "ask" in line:
            for robot in names:
                ask(robot, line)
            continue
        if line.get("system") == "power_cut":  # drop every memory; each fresh one restores itself
            robots = {r: build(r, run_dir) for r in names}
        text = f"Goal: {line['goal']}" if "goal" in line else next(line[k] for k in ("see", "event") if k in line)
        for robot in names:
            observe(robot, kitchen.for_robot(line), kind_of(line), text)
    out.close()
    scorecard(events, names)
    print(f"\nviewer: python3 -m http.server 8000, then "
          f"http://127.0.0.1:8000/viewer/?events=../runs/{args.run}/events.jsonl")


def scorecard(events: Path, names: list[str]) -> None:
    rows = [json.loads(raw) for raw in events.read_text().splitlines()]
    for robot in names:
        mine = [r for r in rows if r["robot"] == robot]
        graded = [r for r in mine if "check" in r]
        wall = next((r for r in mine if r["context_tokens"] > llm.WINDOW), None)
        print(f"\n{robot}: {sum(r['pass'] for r in graded)}/{len(graded)}"
              + (f", over {llm.WINDOW:,} tokens from {wall['clock']}" if wall else "")
              + f", peak {max(r['context_tokens'] for r in mine):,} tokens")
        for r in graded:
            print(f"  {'PASS' if r['pass'] else 'FAIL'} {r['clock']} {r['check']:13} {r['action']:29} "
                  f"{r.get('reason', r['text'])[:110]}")


if __name__ == "__main__":
    main()
