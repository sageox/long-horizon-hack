"""Checks for tables.py: the 18:00 table each robot earned. No API calls."""
import os

os.environ["KITCHEN_OFFLINE"] = "1"

import kitchen  # noqa: E402
import mock_run  # noqa: E402
import tables  # noqa: E402

ROWS = mock_run.run(kitchen.load_day())  # the target day, in memory


def state(robot):
    return tables.table([r for r in ROWS if r["robot"] == robot])


def test_the_task_board_earns_the_full_table():
    s = state("task_board")
    assert (s["cloth"], s["places"], s["roast"], s["stew"], s["served"], s["crumble"]) == \
        ("on the table", 7, "out", "olive oil", True, "out")
    text = tables.prompt(s)
    assert "tablecloth covers" in text and "seven (7) place settings" in text and "roast chicken" in text
    assert "chickpea" in text and "smoke" not in text


def test_the_window_forgets_what_scrolled_away():
    s = state("sliding_window")
    assert (s["cloth"], s["places"], s["roast"], s["stew"], s["salted"]) == ("not found", 6, "in the oven", "butter", 2)
    text = tables.prompt(s)
    assert "no tablecloth" in text and "six (6) place settings" in text
    assert "roast chicken" not in text and "stew" not in text and "smoke" in text


def test_full_history_past_the_wall_sets_nothing():
    s = state("full_history")
    assert (s["cloth"], s["places"], s["roast"], s["served"]) == ("on the bathroom line", 0, "in the oven", False)
    assert "No places are set" in tables.prompt(s)


def test_every_robot_shares_the_scene():
    for robot in ("task_board", "sliding_window", "full_history"):
        assert tables.prompt(state(robot)).startswith(tables.SCENE)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
