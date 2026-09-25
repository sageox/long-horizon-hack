"""The stage server: the viewer's files, plus the dashboard's four queries on RawTree.

    uv run dash.py [--port 8000]

then open /viewer/stage.html?events=../runs/<run>/events.jsonl&source=rawtree&autoplay=1
and, in another terminal, `uv run rawtree.py runs/<run>/events.jsonl` to stream the run.

The browser only ever calls this server. RAWTREE_API_KEY stays here, never in a
URL on the projected screen, and the key can write to a database other teams
share, so the browser can't send SQL: it picks one of four fixed queries, and
run, robot and limit are checked before they reach one. The four queries are
the dashboard's panels; the newest run is the default, so a fresh stream takes
over the screen by itself.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
TABLE = "dinner_events"
NEWEST = f"(SELECT max(run) FROM {TABLE})"
# RawTree columns are Dynamic: cast before comparing, grouping or sorting. A
# line without a field reads back as '' through toString.
QUERIES = {
    "context_by_minute": """
        SELECT toString(robot) AS robot, toUInt32(t) AS t,
               argMax(toUInt32(context_tokens), toUInt32(seq)) AS context_tokens
        FROM {table} WHERE run = {run}
        GROUP BY robot, t ORDER BY robot, t""",
    "checks_by_robot": """
        SELECT toString(robot) AS robot, toString(`check`) AS `check`, toUInt8(`pass`) AS `pass`,
               toUInt32(t) AS t, toString(clock) AS clock, toString(action) AS action,
               toString(reason) AS reason
        FROM {table} WHERE run = {run} AND toString(`check`) != ''
        ORDER BY t, robot""",
    "board_for_robot": """
        SELECT toString(robot) AS robot, toUInt32(t) AS t, toString(clock) AS clock,
               toString(text) AS text, toString(board) AS board
        FROM {table} WHERE run = {run} AND toString(robot) = {robot} AND toString(kind) = 'board'
        ORDER BY toUInt32(t) DESC, toUInt32(seq) DESC LIMIT 1""",
    "latest_events": """
        SELECT toString(robot) AS robot, toUInt32(t) AS t, toString(clock) AS clock,
               toString(kind) AS kind, toString(text) AS text, toString(action) AS action,
               toString(`check`) AS `check`, toString(`pass`) AS `pass`,
               toUInt32(context_tokens) AS context_tokens, toString(mock) AS mock
        FROM {table} WHERE run = {run} AND toString(kind) != 'see'
        ORDER BY toUInt32(t) DESC, toUInt32(seq) DESC LIMIT {limit}""",
    "runs": """
        SELECT toString(run) AS run, count() AS lines,
               countIf(toString(mock) IN ('true', '1')) > 0 AS mock
        FROM {table} GROUP BY run ORDER BY run DESC LIMIT 10""",
}
RUN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")  # rawtree.new_run's format
ROBOT = re.compile(r"[a-z_]{1,40}")


def sql(view: str, run: str | None = None, robot: str = "task_board", limit: str | int = 20) -> str:
    """One of the fixed queries, with its parameters checked. ValueError on anything else."""
    if view not in QUERIES:
        raise ValueError(f"no query named {view!r}")
    if run is not None and not RUN.fullmatch(run):
        raise ValueError("run must look like 2026-09-25 14:46:42")
    if not ROBOT.fullmatch(robot):
        raise ValueError("robot must be lowercase letters and underscores")
    limit = int(limit)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1 to 100")
    return QUERIES[view].format(table=TABLE, run=f"'{run}'" if run else NEWEST, robot=f"'{robot}'", limit=limit)


_cache: dict[str, tuple[float, list]] = {}


def answer(view: str, params: dict) -> list[dict]:
    """The query's rows, shared for half a second so several screens poll RawTree once."""
    import rawtree  # reads RAWTREE_API_KEY; imported here so the static files serve without it

    text = sql(view, **params)
    hit = _cache.get(text)
    if hit and time.monotonic() - hit[0] < 0.5:
        return hit[1]
    rows = rawtree.query(text)
    _cache[text] = (time.monotonic(), rows)
    return rows


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if not url.path.startswith("/rawtree/"):
            return super().do_GET()
        view = url.path.removeprefix("/rawtree/")
        params = {k: v[-1] for k, v in parse_qs(url.query).items() if k in ("run", "robot", "limit")}
        try:
            body, status = {"data": answer(view, params)}, 200
        except ValueError as e:
            body, status = {"error": str(e)}, 400
        except Exception as e:  # RawTree down, no key, a bad column: say so on the panel
            body, status = {"error": f"{type(e).__name__}: {e}"[:500]}, 502
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):  # quiet: the dashboard polls four times a second
        if not self.path.startswith("/rawtree/"):
            super().log_message(format, *args)


def main() -> None:
    p = argparse.ArgumentParser(description="Serve the viewer and the dashboard's RawTree queries.")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(ROOT)))
    base = f"http://127.0.0.1:{args.port}"
    print(f"stage:     {base}/viewer/stage.html?events=../runs/<run>/events.jsonl&source=rawtree&autoplay=1")
    print(f"dashboard: {base}/viewer/tinybird.html?source=rawtree")
    server.serve_forever()


if __name__ == "__main__":
    main()
