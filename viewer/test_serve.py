from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import quote

from serve import RunHandler


def event(t=0, **extra):
    return {"robot": "task_board", "t": t, "kind": "event", "text": "Kitchen event", **extra}


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.log_patch = patch.object(RunHandler, "log_message")
        self.log_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(RunHandler, runs_dir=self.runs))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.log_patch.stop()
        self.temporary.cleanup()

    def write_run(self, name, rows, tail=b"", updated=None):
        path = self.runs / name / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(json.dumps(row).encode() + b"\n" for row in rows) + tail)
        if updated is not None:
            os.utime(path, (updated, updated))
        return path

    def get(self, path):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_run_listing_sorts_records_and_distinguishes_mock_from_real(self):
        self.write_run("older-mock", [event(0, mock=True)], updated=100)
        self.write_run("real run ♥", [event(3), event(1)], updated=300)
        self.write_run("string-flag", [event(2, mock="true")], updated=200)
        self.write_run("empty", [])
        self.write_run("partial-only", [], b'{"robot":')
        self.write_run("nested/child", [event(10)])
        status, headers, body = self.get("/api/runs")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        runs = json.loads(body)["runs"]
        self.assertEqual([run["name"] for run in runs], ["real run ♥", "string-flag", "older-mock"])
        self.assertEqual([run["mock"] for run in runs], [False, False, True])
        self.assertEqual(runs[0], {
            "name": "real run ♥", "url": f"/backend-runs/{quote('real run ♥', safe='')}/events.jsonl",
            "mock": False, "rows": 2, "last_t": 3, "updated": 300.0,
        })
        self.assertEqual(self.get(runs[0]["url"])[0], 200)

    def test_snapshot_withholds_partial_row_and_changes_after_flush(self):
        next_line = json.dumps(event(10)).encode() + b"\n"
        path = self.write_run("growing", [event(0)], next_line[:17])
        first_line = json.dumps(event(0)).encode() + b"\n"
        status, headers, body = self.get("/backend-runs/growing/events.jsonl")
        self.assertEqual(status, 200)
        self.assertEqual(body, first_line)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(headers["Content-Type"].startswith("application/x-ndjson"))
        self.assertEqual(json.loads(self.get("/api/runs")[2])["runs"][0]["rows"], 1)
        with path.open("ab") as stream:
            stream.write(next_line[17:])
            stream.flush()
        self.assertEqual(self.get("/backend-runs/growing/events.jsonl")[2], first_line + next_line)
        run = json.loads(self.get("/api/runs")[2])["runs"][0]
        self.assertEqual((run["rows"], run["last_t"]), (2, 10))

    def test_invalid_complete_rows_are_excluded_and_return_clear_errors(self):
        self.write_run("bad-json", [event()], b"not json\n")
        self.write_run("bad-schema", [event(t=True)])
        self.write_run("nonstandard-json", [event(context_tokens=float("nan"))])
        self.write_run("oversized-number", [event(t=10 ** 400)])
        self.assertEqual(json.loads(self.get("/api/runs")[2]), {"runs": []})
        status, headers, body = self.get("/backend-runs/bad-json/events.jsonl")
        self.assertEqual(status, 500)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("Line 2", json.loads(body)["error"])
        self.assertEqual(self.get("/backend-runs/bad-schema/events.jsonl")[0], 500)
        self.assertEqual(self.get("/backend-runs/nonstandard-json/events.jsonl")[0], 500)
        self.assertEqual(self.get("/backend-runs/oversized-number/events.jsonl")[0], 500)

    def test_unicode_inside_a_json_string_is_not_treated_as_a_row_boundary(self):
        path = self.write_run("unicode", [])
        content = (json.dumps(event(text="First\u2028second"), ensure_ascii=False) + "\n").encode()
        path.write_bytes(content)
        self.assertEqual(self.get("/backend-runs/unicode/events.jsonl")[2], content)
        self.assertEqual(json.loads(self.get("/api/runs")[2])["runs"][0]["rows"], 1)

    def test_missing_traversal_and_symlinks_cannot_read_outside_runs(self):
        outside = self.root / "private"
        outside.mkdir()
        secret = outside / "events.jsonl"
        secret.write_text(json.dumps(event(text="private data")) + "\n")
        (self.runs / "directory-link").symlink_to(outside, target_is_directory=True)
        (self.runs / "file-link").mkdir()
        (self.runs / "file-link" / "events.jsonl").symlink_to(secret)
        for path in (
            "/backend-runs/missing/events.jsonl",
            "/backend-runs/../private/events.jsonl",
            "/backend-runs/%2e%2e/events.jsonl",
            "/backend-runs/..%2fprivate/events.jsonl",
            "/backend-runs/%00/events.jsonl",
            "/backend-runs/directory-link/events.jsonl",
            "/backend-runs/file-link/events.jsonl",
            "/backend-runs/valid/other.jsonl",
        ):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn(b"private data", body)
        self.assertEqual(json.loads(self.get("/api/runs")[2]), {"runs": []})

    def test_missing_runs_directory_is_empty_and_repository_files_remain_available(self):
        self.runs.rmdir()
        self.assertEqual(json.loads(self.get("/api/runs")[2]), {"runs": []})
        status, _, body = self.get("/fixtures/events.sample.jsonl")
        self.assertEqual(status, 200)
        self.assertIn(b'"robot": "task_board"', body)


if __name__ == "__main__":
    unittest.main()
