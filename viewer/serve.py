"""Serve the demo and complete JSONL snapshots from a backend's runs directory."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]


def reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


class RunHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, runs_dir: Path = REPO_ROOT / "runs", **kwargs):
        self.runs_dir = Path(runs_dir).expanduser().resolve()
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def snapshot(self, name: str) -> tuple[bytes, list[dict], float]:
        if not name or name in {".", ".."} or any(char in name for char in "/\\\0"):
            raise FileNotFoundError("Run not found")
        directory = self.runs_dir / name
        path = directory / "events.jsonl"
        if directory.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(self.runs_dir):
            raise FileNotFoundError("Run not found")
        with path.open("rb") as stream:
            content = stream.read()
            updated = os.fstat(stream.fileno()).st_mtime
        content = content[:content.rfind(b"\n") + 1]
        rows = []
        for number, line in enumerate(content.decode("utf-8-sig").split("\n"), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, parse_constant=reject_constant)
                if not isinstance(row, dict):
                    raise ValueError("expected an event object")
                for field in ("robot", "kind"):
                    if not isinstance(row.get(field), str) or not row[field].strip():
                        raise ValueError(f"{field} must be a nonempty string")
                for field in ("t", "context_tokens"):
                    value = row.get(field)
                    if field == "context_tokens" and value is None:
                        continue
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError(f"{field} must be a finite, nonnegative number")
                for field in ("text", "action", "check", "reason", "query"):
                    if row.get(field) is not None and not isinstance(row[field], str):
                        raise ValueError(f"{field} must be a string")
                if row.get("pass") is not None and type(row["pass"]) is not bool:
                    raise ValueError("pass must be true or false")
            except (ValueError, OverflowError) as error:
                raise ValueError(f"Line {number}: {error}") from error
            rows.append(row)
        return content, rows, updated

    def respond(self, status: int, payload: dict | bytes) -> None:
        is_json = isinstance(payload, dict)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if is_json else payload
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8" if is_json else "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/runs":
            runs = []
            for candidate in self.runs_dir.glob("*/events.jsonl"):
                name = candidate.parent.name
                try:
                    _, rows, updated = self.snapshot(name)
                except (OSError, ValueError) as error:
                    self.log_message("Skipping unreadable run %r: %s", name, error)
                    continue
                if rows:
                    runs.append({
                        "name": name,
                        "url": f"/backend-runs/{quote(name, safe='')}/events.jsonl",
                        "mock": any(row.get("mock") is True for row in rows),
                        "rows": len(rows),
                        "last_t": max(row["t"] for row in rows),
                        "updated": updated,
                    })
            runs.sort(key=lambda run: run["updated"], reverse=True)
            self.respond(200, {"runs": runs})
        elif path.startswith("/backend-runs/"):
            parts = unquote(path).split("/")
            if len(parts) != 4 or parts[1] != "backend-runs" or parts[3] != "events.jsonl":
                self.respond(404, {"error": "Run not found"})
                return
            try:
                content, _, _ = self.snapshot(parts[2])
            except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
                self.respond(404, {"error": "Run not found"})
            except (OSError, ValueError) as error:
                self.respond(500, {"error": f"Could not read run {parts[2]!r}: {error}"})
            else:
                self.respond(200, content)
        else:
            super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    handler = partial(RunHandler, runs_dir=args.runs_dir)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Demo: http://127.0.0.1:{server.server_port}/viewer/three.html · Backend runs: {args.runs_dir.expanduser().resolve()}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
