"""Checks for kitchen.py. Run with `python test_kitchen.py` or pytest."""
import contextlib
import io
import json
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

os.environ["KITCHEN_OFFLINE"] = "1"  # never spend a Nimble call in a test

import kitchen  # noqa: E402

CHECK_IDS = ["crumble_out", "stew_vegan", "cloth", "seven_places", "roast_out", "salted_once"]


def asks():
    return [line for line in kitchen.load_day() if "check" in line]


def test_menu_is_the_fixed_list():
    assert len(kitchen.ACTIONS) == len(set(kitchen.ACTIONS)) == 13
    assert kitchen.LOOKUPS == ["search_recipe(query)"]


def test_the_six_checks_in_order():
    assert [line["check"]["id"] for line in asks()] == CHECK_IDS


def test_every_answer_is_on_the_menu():
    for line in asks():
        assert line["check"]["pass_if"] in kitchen.ACTIONS, line["check"]["id"]


def test_right_answers_pass_and_wrong_ones_fail():
    assert all(kitchen.grade(line, line["check"]["pass_if"]) for line in asks())
    for wrong in ["wait", "continue_chores", "context_overflow", ""]:
        assert not any(kitchen.grade(line, wrong) for line in asks()), wrong


def test_lines_without_a_check_grade_none():
    for line in kitchen.load_day():
        if "check" not in line:
            assert kitchen.grade(line, "wait") is None


def test_robot_never_sees_the_check():
    for line in asks():
        assert "check" not in kitchen.for_robot(line)
        assert "check" in line  # the original is untouched


def test_vegan_queries_get_the_olive_oil_stew():
    for q in ["vegan vegetable stew for 7", "Plant-Based stew", "dairy  free stew", "stew without butter"]:
        page = kitchen.search_recipe(q)
        assert page["title"].startswith("Hearty Vegan"), q
        assert "olive oil" in page["body"], q


def test_other_queries_get_the_butter_stew():
    for q in ["vegetable stew recipe", "stew", "", "hearty stew for seven"]:
        page = kitchen.search_recipe(q)
        assert page["title"] == "Grandma's Classic Vegetable Stew", q
        assert "butter" in page["body"], q


def test_page_carries_no_answer_label():
    page = kitchen.search_recipe("vegan stew")
    assert set(page) == {"query", "url", "title", "body", "source"}
    assert page["query"] == "vegan stew"


def test_web_line_is_observable():
    page = kitchen.search_recipe("vegan stew for 7")
    line = kitchen.web_line(300, "13:00", page)
    assert (line["t"], line["clock"], line["query"]) == (300, "13:00", "vegan stew for 7")
    assert line["web"].startswith("Hearty Vegan") and "check" not in line


def test_day_has_a_line_every_minute():
    assert [line["t"] for line in kitchen.load_day()] == list(range(601))


def test_script_lines_survive_verbatim():
    day = kitchen.DAY.read_text().splitlines()
    for line in kitchen.SCRIPT.read_text().splitlines():
        assert line in day, line


def test_day_file_is_the_seed_0_build():
    assert kitchen.build_day(0) == kitchen.load_day()
    assert kitchen.build_day(1) != kitchen.build_day(0)


# Anything a check depends on, or the dining table's state. Filler naming one
# would hand a memoryless robot the answer, or bias it away.
BANNED = re.compile(r"\b(" + "|".join([
    "leo", "vegan", "butter", "oil", "olive", "mia", "six", "seven", "guests?", "places", "plates?",
    "chairs", "dinner", "family", "cloth", "tablecloth", "bathroom", "dryer", "dried", "damp",
    "laundry", "washing", "line", "hung", "hang", "oven", "roast", "chicken", "stew", "salt",
    "salted", "pot", "hob", "recipe", "crumble", "apples?", "salad", "vegetables?", "timer",
]) + r")\b", re.I)


def filler():
    script = {line["t"] for line in kitchen.load_day(kitchen.SCRIPT)}
    return [line for line in kitchen.load_day() if line["t"] not in script]


def test_filler_never_names_what_a_check_depends_on():
    for line in filler():
        assert set(line) == {"t", "clock", "see"}
        hit = BANNED.search(line["see"])
        assert not hit, f'{line["clock"]}: {hit.group(0)!r} in {line["see"]!r}'


def test_filler_never_describes_the_dining_table():
    for line in filler():
        if line["see"].startswith("Dining room"):
            assert not re.search(r"\btable\b", line["see"], re.I), line["see"]


def test_filler_is_about_75_tokens():
    sizes = [kitchen.est_tokens(line["see"]) for line in filler()]
    assert 65 <= sum(sizes) / len(sizes) <= 85
    assert 50 <= min(sizes) and max(sizes) <= 100


def test_wall_lands_between_the_stew_and_the_table():
    # After 13:00 even with a live 4K recipe page, before the 16:30 checks.
    for render, clock in kitchen.walls(kitchen.load_day(), page=4_000).items():
        assert clock and "13:45" <= clock <= "16:15", (render, clock)


def test_window_still_holds_the_crumble_at_11():
    # The control: the crumble went in at 10:40, so 20 lines back.
    assert kitchen.window_lines(kitchen.load_day(), 180) > 25


@contextlib.contextmanager
def nimble(urlopen):
    """A key, a throwaway copy of the cache, and urlopen replaced."""
    saved = kitchen.WEB_CACHE, urllib.request.urlopen, os.environ.get("NIMBLE_API_KEY")
    cache = Path(tempfile.mkdtemp()) / "web_cache.json"
    shutil.copy(kitchen.WEB_CACHE, cache)
    kitchen.WEB_CACHE, urllib.request.urlopen = cache, urlopen
    os.environ["NIMBLE_API_KEY"] = "test-key"
    try:
        yield cache
    finally:
        kitchen.WEB_CACHE, urllib.request.urlopen = saved[0], saved[1]
        if saved[2] is None:
            os.environ.pop("NIMBLE_API_KEY", None)
        else:
            os.environ["NIMBLE_API_KEY"] = saved[2]


def unreachable(*args, **kwargs):
    raise AssertionError("called Nimble")


def test_live_search_is_recorded_then_replayed():
    sent = []
    results = [
        {"title": "A pin", "url": "https://pins.example/1", "content": "Save this!"},
        {"title": "Real Vegan Stew", "url": "https://recipes.example.org/vegan-stew",
         "content": "My story. " * 1000 + "Ingredients: 2 tbsp olive oil, 1 onion. Method: soften."},
    ]

    def urlopen(request, timeout):
        sent.append(request)
        return io.BytesIO(json.dumps({"request_id": "r1", "total_results": 2, "results": results}).encode())

    with nimble(urlopen) as cache:
        page = kitchen.search_recipe("Vegan  Stew for 7", live=True)
        assert (page["source"], page["title"]) == ("nimble", "Real Vegan Stew")
        assert page["body"].startswith("My story.") and "Ingredients: 2 tbsp olive oil" in page["body"]
        assert len(page["body"]) <= kitchen.PAGE_CHARS

        request = sent[0]
        assert request.full_url == kitchen.NIMBLE_SEARCH
        assert request.get_header("Authorization") == "Bearer test-key"
        body = json.loads(request.data)
        assert body["query"] == "Vegan  Stew for 7" and body["full_content"] is True

        recorded = json.loads(cache.read_text())["recorded"]
        assert list(recorded) == ["vegan stew for 7"] and recorded["vegan stew for 7"]["fetched_at"]

        urllib.request.urlopen = unreachable
        again = kitchen.search_recipe("vegan stew for 7", live=True)
        assert again["source"] == "recorded"
        assert (again["title"], again["body"]) == (page["title"], page["body"])


def test_nimble_failure_falls_back_to_the_synthetic_page():
    def urlopen(request, timeout):
        raise OSError("connection refused")

    with nimble(urlopen) as cache:
        page = kitchen.search_recipe("vegan stew", live=True)
        assert page["source"] == "cache" and page["title"].startswith("Hearty Vegan")
        assert json.loads(cache.read_text())["recorded"] == {}


def test_offline_never_calls_out_even_with_a_key():
    with nimble(unreachable):
        assert kitchen.search_recipe("a query nobody recorded")["source"] == "cache"


def test_short_pages_start_at_the_top():
    assert kitchen._recipe_part("Ingredients: oil.") == "Ingredients: oil."
    assert kitchen._recipe_part("x" * 20_000) == "x" * kitchen.PAGE_CHARS


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
