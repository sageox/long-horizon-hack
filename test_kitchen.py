"""Checks for kitchen.py. Run with `python test_kitchen.py` or pytest."""
import kitchen

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


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
