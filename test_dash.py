"""Checks for dash.py's query guard. No network: sql() only builds the text."""
import dash


def rejects(**kwargs):
    try:
        dash.sql(**kwargs)
    except ValueError:
        return True
    return False


def test_newest_run_by_default():
    assert "(SELECT max(run) FROM dinner_events)" in dash.sql("context_by_minute")


def test_a_named_run_is_quoted_in():
    assert "run = '2026-09-25 14:46:42'" in dash.sql("checks_by_robot", run="2026-09-25 14:46:42")


def test_the_browser_cannot_inject_sql():
    assert rejects(view="context_by_minute", run="x' OR 1=1 --")
    assert rejects(view="board_for_robot", robot="task_board'; DROP TABLE dinner_events --")
    assert rejects(view="latest_events", limit="20; DELETE")
    assert rejects(view="latest_events", limit=1000)
    assert rejects(view="SELECT * FROM other_teams_table")


def test_every_panel_query_builds():
    for view in dash.QUERIES:
        assert "dinner_events" in dash.sql(view)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
