"""RawTree, the hackathon's Tinybird offering: events.jsonl lines into the
dinner_events table, the board back out.

    uv run rawtree.py runs/<run>/events.jsonl

plays a finished run into RawTree at the viewer's speed, so the dashboard
fills beside it. RAWTREE_API_KEY comes from the environment or .env. RawTree
creates the table on the first insert and infers its columns.
"""

import json
import sys
import time
from datetime import datetime
from itertools import groupby
from pathlib import Path

import requests

from kitchen import _secret

API = "https://api.rawtree.com/v1"
TABLE = "dinner_events"  # the hackathon's database is shared between teams, who prefix their tables
KEY = _secret("RAWTREE_API_KEY")
HEADERS = {"Authorization": f"Bearer {KEY}"}
MINUTE = 0.3  # seconds per simulated minute, as in the viewer


def new_run() -> str:
    """Queries show the newest run with max(run), so a run is named by its start time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def send(run: str, seq: int, lines: list[dict]) -> None:
    """Insert events.jsonl lines into the table, numbered from seq."""
    rows = [{**line, "run": run, "seq": seq + i} for i, line in enumerate(lines)]
    requests.post(f"{API}/tables/{TABLE}", json=rows, headers=HEADERS).raise_for_status()


def query(sql: str) -> list[dict]:
    response = requests.post(f"{API}/query", json={"sql": sql}, headers=HEADERS)
    if not response.ok:  # raise_for_status would drop RawTree's message, which says what is wrong with the SQL
        raise RuntimeError(f"RawTree {response.status_code}: {response.text}")
    return response.json()["data"]


def board(run: str, robot: str = "task_board") -> dict | None:
    """The latest board this robot wrote in this run, as RawTree has it."""
    rows = query(
        f"SELECT board FROM {TABLE} WHERE run = '{run}' AND robot = '{robot}' AND kind = 'board' "
        "ORDER BY t DESC, seq DESC LIMIT 1"
    )
    return json.loads(rows[0]["board"]) if rows else None


def stream(path: Path) -> str:
    """Send a run's lines at playback speed; returns the new run's name."""
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    run, start, seq = new_run(), time.time(), 0
    # One insert per second of playback: an insert takes longer than a simulated minute's 0.3 s.
    for second, batch in groupby(lines, key=lambda line: int(line["t"] * MINUTE)):
        batch = list(batch)
        time.sleep(max(0, start + second - time.time()))
        send(run, seq, batch)
        seq += len(batch)
    return run


if __name__ == "__main__":
    print(stream(Path(sys.argv[1])))
