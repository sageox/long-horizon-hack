"""The harness: every robot over one day, runs/<run>/events.jsonl out, a scorecard per robot on stdout.

    uv run run.py --day fixtures/day.jsonl [--robots task_board,...] [--run name] [--perfect]

runs/<run>/asks.jsonl holds each robot's context at each ask, before any lookup, with the ask's
check: planner.messages(context, clock) is the prompt it got. With --perfect every ask is answered
with its check's pass_if instead of asking the planner, so asks.jsonl holds the contexts a planner
that got every earlier ask right would see. The wall still holds, rows are marked mock, and no
scorecard is printed.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

import kitchen
import llm
import memory
import planner
import rawtree

ROBOTS = ["full_history", "sliding_window", "task_board", "rolling_summary"]
BUDGET = 4_096


def latest_board(events: Path, robot: str, remote_run: str | None) -> dict | None:
    """The robot's newest board line: what a reboot reads. From RawTree when it is on, compared
    with this run's events.jsonl, which is also the fallback."""
    local = None
    if events.exists():
        for raw in events.read_text().splitlines():
            row = json.loads(raw)
            if row["robot"] == robot and row["kind"] == "board":
                local = json.loads(row["board"])
    if not remote_run:
        return local
    # A write takes a moment to show up in RawTree: measured, a board sent just before the 14:10
    # power cut wasn't there when it was read. Wait for the last board this run sent.
    for _ in range(10):
        try:
            remote = rawtree.board(remote_run, robot)
        except (requests.RequestException, RuntimeError) as e:
            print(f"{robot}: RawTree board read failed, restoring from the local log: {e}", file=sys.stderr)
            return local
        if remote == local:
            return remote
        time.sleep(1)
    print(f"{robot}: RawTree's board still differs from the local log's after 10 s; restoring from the "
          f"local log\n  RawTree: {json.dumps(remote)}\n  local:   {json.dumps(local)}", file=sys.stderr)
    return local


def build(robot: str, run_dir: Path, remote_run: str | None):
    """A fresh memory that restores itself from whatever this run has already written."""
    if robot == "full_history":
        return memory.FullHistory(run_dir / f"{robot}.log.jsonl")
    if robot == "sliding_window":
        return memory.SlidingWindow(BUDGET, run_dir / f"{robot}.log.jsonl")
    if robot == "task_board":
        return memory.TaskBoard(BUDGET, latest_board(run_dir / "events.jsonl", robot, remote_run))
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
    p.add_argument("--perfect", action="store_true", help="answer every ask right; see the module docstring")
    args = p.parse_args()
    names = args.robots.split(",")
    run_dir = Path("runs") / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    events = run_dir / "events.jsonl"
    for old in [events, *(run_dir / f"{r}.log.jsonl" for r in names)]:  # a rerun under the same name
        old.unlink(missing_ok=True)
    remote_run = rawtree.new_run() if rawtree.KEY else None  # RawTree is on when .env has its key
    robots = {r: build(r, run_dir, remote_run) for r in names}
    out = events.open("a")
    asks = (run_dir / "asks.jsonl").open("w")
    written = 0

    def emit(robot: str, line: dict, kind: str, text: str, **extra) -> dict:
        nonlocal written
        context = planner.messages(robots[robot].context(), line["clock"])
        row = {"robot": robot, "t": line["t"], "clock": line["clock"], "kind": kind, "text": text, **extra,
               "context_tokens": llm.count_tokens(llm.render(context))}
        if args.perfect:
            row["mock"] = True  # the viewer badges it: not a run
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()  # the power cut's restore reads this file
        written += 1
        return row

    def observe(robot: str, line: dict, kind: str | None, text: str = "", **extra) -> None:
        mem = robots[robot]
        mem.observe(line)
        if kind:
            emit(robot, line, kind, text, **extra)
        if getattr(mem, "changes", None):
            row = emit(robot, line, "board", "; ".join(mem.changes), board=json.dumps(mem.board(), ensure_ascii=False))
            mem.changes.clear()
            if remote_run:  # before the planner runs again, so a reboot loses nothing
                try:
                    rawtree.send(remote_run, written - 1, [row])
                except requests.RequestException as e:
                    print(f"{robot}: RawTree send failed, the local log has the board: {e}", file=sys.stderr)

    def ask(robot: str, line: dict) -> None:
        mem, clock = robots[robot], line["clock"]
        graded = {"check": line["check"]["id"]} if "check" in line else {}
        context = mem.context()
        tokens = llm.count_tokens(llm.render(planner.messages(context, clock)))
        asks.write(json.dumps({"robot": robot, "t": line["t"], "clock": clock, "check": line.get("check"),
                               "context_tokens": tokens, "context": context}, ensure_ascii=False) + "\n")
        try:
            if args.perfect:
                if tokens > llm.WINDOW:  # as planner.decide would
                    raise llm.ContextOverflow(tokens)
                reply = {"reason": "perfect planner: the check's answer", "action": line["check"]["pass_if"]}
            else:
                reply = planner.decide(context, clock)
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
            robots = {r: build(r, run_dir, remote_run) for r in names}
        text = f"Goal: {line['goal']}" if "goal" in line else next(line[k] for k in ("see", "event") if k in line)
        for robot in names:
            observe(robot, kitchen.for_robot(line), kind_of(line), text)
    out.close()
    asks.close()
    if not args.perfect:
        scorecard(events, names)
    print(f"\nasks: runs/{args.run}/asks.jsonl\nviewer: python3 -m http.server 8000, then "
          f"http://127.0.0.1:8000/viewer/?events=../runs/{args.run}/events.jsonl")
    if remote_run:
        print(f"RawTree: board lines under run {remote_run!r}; for the dashboard, "
              f"uv run rawtree.py runs/{args.run}/events.jsonl")


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
