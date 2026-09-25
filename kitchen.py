"""The kitchen: the fixed action menu, grading, and the recipe lookup.

The harness imports grade() and search_recipe(). Grading is a string match
against the hidden check and nothing else. Kitchen state (roast in or out,
places set) is display only; the viewer derives it from action lines.

Standard library only, so it runs before pyproject.toml exists.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DAY = FIXTURES / "day.jsonl"
WEB_CACHE = FIXTURES / "web_cache.json"

_menu = json.loads((FIXTURES / "menu.json").read_text())
ACTIONS: list[str] = _menu["actions"]  # the enum for the planner's schema
LOOKUPS: list[str] = _menu["lookups"]


def load_day(path: str | Path = DAY) -> list[dict]:
    """The day script, one dict per line, in file order."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def for_robot(line: dict) -> dict:
    """The line as the robot may see it: everything except the hidden check."""
    return {k: v for k, v in line.items() if k != "check"}


def grade(line: dict, action: str) -> bool | None:
    """Whether action passes this line's check, or None if it has no check.

    Passes only when action equals check["pass_if"]. An overflowed call is
    graded as "context_overflow", which is on no menu, so it fails.
    """
    check = line.get("check")
    if check is None:
        return None
    return action == check["pass_if"]


def search_recipe(query: str) -> dict:
    """One recipe page for the robot's free-text query.

    Reads fixtures/web_cache.json: the first entry whose match_any phrase
    appears in the lowercased query, else the default page. The cache's "fat"
    label is ours, not the page's, so it is never returned.
    """
    q = " ".join(query.lower().split())
    entries = json.loads(WEB_CACHE.read_text())["search_recipe"]
    page = next((e for e in entries if any(m in q for m in e.get("match_any", ()))), None)
    if page is None:
        page = next(e for e in entries if e.get("default"))
    return {
        "query": query,
        "url": page["url"],
        "title": page["title"],
        "body": page["body"],
        "source": "cache",
    }


def web_line(t: int, clock: str, page: dict) -> dict:
    """The line a memory observes after its own lookup, at the ask's t."""
    return {
        "t": t,
        "clock": clock,
        "web": f"{page['title']}. {page['body']}",
        "query": page["query"],
        "url": page["url"],
    }
