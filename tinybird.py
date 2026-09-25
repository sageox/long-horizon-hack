"""Tinybird: events.jsonl lines into the events datasource, the board back out.

    uv run tinybird.py runs/<run>/events.jsonl

plays a finished run into Tinybird at the viewer's speed, so the dashboard
fills beside it. TB_HOST and TB_TOKEN come from the environment or .env;
without TB_HOST this talks to Tinybird Local.
"""

import json
import sys
import time
from datetime import datetime
from itertools import groupby
from pathlib import Path

import requests

from kitchen import _secret

HOST = _secret("TB_HOST") or "http://localhost:7181"
TOKEN = _secret("TB_TOKEN")
MINUTE = 0.3  # seconds per simulated minute, as in the viewer


def new_run() -> str:
    """The endpoints show max(run), so a run is named by its start time."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def send(run: str, seq: int, lines: list[dict]) -> None:
    """Append events.jsonl lines to the events datasource, numbered from seq."""
    rows = []
    for i, line in enumerate(lines):
        row = {**line, "run": run, "seq": seq + i}
        if "pass" in row:
            row["pass"] = int(row["pass"])
        rows.append(json.dumps(row))
    response = requests.post(
        f"{HOST}/v0/events", params={"name": "events"}, data="\n".join(rows),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    response.raise_for_status()


def board(run: str, robot: str = "task_board") -> dict | None:
    """The latest board this robot wrote in this run, as Tinybird has it."""
    response = requests.get(
        f"{HOST}/v0/pipes/board_for_robot.json", params={"run": run, "robot": robot, "token": TOKEN}
    )
    response.raise_for_status()
    rows = response.json()["data"]
    return json.loads(rows[0]["board"]) if rows else None


def stream(path: Path) -> str:
    """Send a run's lines minute by minute at playback speed; returns the new run's name."""
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    run, start, seq = new_run(), time.time(), 0
    for t, minute in groupby(lines, key=lambda line: line["t"]):
        minute = list(minute)
        time.sleep(max(0, start + t * MINUTE - time.time()))
        send(run, seq, minute)
        seq += len(minute)
    return run


if __name__ == "__main__":
    print(stream(Path(sys.argv[1])))
