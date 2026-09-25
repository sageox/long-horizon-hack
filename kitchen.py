"""The kitchen: the fixed action menu, grading, the recipe lookup, the day.

The harness imports grade() and search_recipe(). Grading is a string match
against the hidden check and nothing else. Kitchen state (roast in or out,
places set) is display only; the viewer derives it from action lines.

fixtures/script.jsonl holds the fixed lines: the goal, every event, every ask.
`python kitchen.py` fills each empty minute with a see line and writes
fixtures/day.jsonl, the file the harness plays.

Standard library only, so it runs before pyproject.toml exists.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCRIPT = FIXTURES / "script.jsonl"
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


# The full day ---------------------------------------------------------------
#
# Every minute without a fixed line gets a see line of about SEE_TOKENS. That
# density is what fills full history's 32,768 tokens by mid-afternoon. Filler
# is noise by construction: it never names what a check depends on (the oven,
# the stew, salt, the cloth, the dryer, the bathroom, how many are coming, who
# eats what) and never describes the dining table, whose state after 16:30
# depends on the robot's own choice. test_kitchen.py enforces the word list.

SEE_TOKENS = 75
CHARS_PER_TOKEN = 4  # an estimate until llm.py counts with the LFM tokenizer

# Where the robot is from minute t on, agreeing with the script's see lines.
ROBOT_ROOM = [
    (0, "Kitchen"), (115, "Living room"), (140, "Kitchen"), (183, "Hallway"),
    (190, "Kitchen"), (225, "Living room"), (262, "Kitchen"),
    (340, "Living room"), (358, "Kitchen"), (375, "Hallway"),
    (415, "Living room"), (470, "Kitchen"), (500, "Dining room"),
    (520, "Living room"), (555, "Kitchen"),
]

# Where Ruth is from minute t on: (t, room, seen in the same room, heard from elsewhere).
RUTH = [
    (0, "Kitchen", [
        "Ruth at the table in her dressing gown, both hands round her tea.",
        "Ruth reads the back of the cereal box, lips moving.",
        "Ruth stirs her tea and looks out at the garden.",
        "Ruth taps the table in time with nothing in particular.",
    ], [
        "Ruth's voice from the kitchen, talking back to the radio.",
        "The clink of Ruth's spoon against her mug in the kitchen.",
    ]),
    (115, "Living room", [
        "Ruth in the armchair with the crossword, pen tapping her teeth.",
        "Ruth counts letters on her fingers for a clue.",
        "Ruth frowns at the crossword and crosses something out.",
        "Ruth looks up from the crossword and smiles at nothing.",
    ], [
        "From the living room, the scratch of Ruth's pen on the crossword.",
        "Ruth mutters a crossword clue in the living room.",
        "The creak of Ruth's armchair from the living room.",
        "Ruth laughs at something on the radio in the living room.",
    ]),
    (260, "Kitchen", [
        "Ruth eats a sandwich at the table, slowly.",
        "Ruth brushes crumbs off her lap.",
        "Ruth sips water and reads the paper.",
        "Ruth folds the newspaper in half, then in half again.",
    ], [
        "Ruth's voice from the kitchen, reading the paper aloud.",
        "The rustle of Ruth's newspaper in the kitchen.",
    ]),
    (305, "Living room", [
        "Ruth dozing in the armchair, glasses pushed up on her forehead.",
        "Ruth asleep under a blanket, one slipper off.",
        "Ruth snoring softly, mouth a little open.",
        "Ruth half awake, turning the pages of a magazine.",
    ], [
        "Soft snoring from the living room.",
        "The living room is quiet; Ruth is dozing.",
        "A small cough from Ruth in the living room.",
        "Ruth shifts in the armchair in the living room.",
    ]),
    (450, "Living room", [
        "Ruth back at the crossword, pen in hand.",
        "Ruth reads a clue aloud, then answers it herself.",
        "Ruth fills in a long answer with a pleased sniff.",
        "Ruth rubs her knees and goes back to the crossword.",
    ], [
        "Ruth reads a crossword clue aloud in the living room.",
        "The scratch of Ruth's pen from the living room.",
        "Ruth sighs at a clue in the living room.",
        "Ruth's armchair creaks in the living room.",
    ]),
    (541, "Upstairs", [], [
        "Footsteps upstairs; Ruth is changing.",
        "A wardrobe door creaks upstairs.",
        "Ruth calls something from upstairs that doesn't carry.",
        "The stairs creak as Ruth moves about on the landing.",
    ]),
    (560, "Kitchen", [
        "Ruth at the table in her good cardigan, reading.",
        "Ruth turns a page and adjusts her glasses.",
        "Ruth reads with a finger following the words.",
        "Ruth looks up at the clock, then back at her book.",
    ], [
        "Ruth's page turns, faintly, from the kitchen.",
        "Ruth hums in the kitchen.",
    ]),
]

RADIO = [
    (0, ["The house is quiet, the radio still off.", "No radio yet, just the fridge and the birds.",
         "Quiet apart from the clock.", "The radio sits silent on the shelf."]),
    (20, ["The radio reads the morning headlines.", "Traffic news on the radio: roadworks on the ring road.",
          "The radio forecast says rain by the afternoon.", "A radio phone-in about hedgehogs in gardens."]),
    (120, ["The radio plays a string quartet.", "Piano on the radio, something slow.",
           "The radio presenter introduces a symphony.", "A choir on the radio, very far away."]),
    (240, ["The lunchtime news on the radio.", "A radio report about bus fares going up.",
           "Sport headlines on the radio.", "The radio reads the shipping forecast."]),
    (300, ["An afternoon play on the radio, two actors arguing.", "The radio play has reached a courtroom scene.",
           "Radio drama: a door slams and someone laughs.", "A gardening programme on the radio."]),
    (370, ["The radio has been silent since the power cut.", "No radio now, only the rain.",
           "The radio's display is dark.", "Just the rain and the fridge."]),
    (480, ["A quiz show on the radio.", "The radio quizmaster asks about rivers.",
           "Laughter from a panel show on the radio.", "The radio is back on, a quiz."]),
    (540, ["Drive-time music on the radio.", "An old love song on the radio.",
           "The radio plays the evening news jingle.", "Traffic news on the radio: queues on the bridge."]),
]

WEATHER = {  # by clock hour
    8: ["Low sun slants across the floor.", "A thin mist sits over the garden.",
        "Pale morning light on the worktop.", "Birds busy at the feeder outside."],
    9: ["Bright sky over the rooftops.", "Sun on the windowsill, warming the tomatoes.",
        "A clear morning, not a cloud.", "Someone next door is mowing a lawn."],
    10: ["Clouds drifting in from the west.", "The sun comes and goes behind the clouds.",
         "A breeze moves the hedge.", "A delivery van idles in the street."],
    11: ["The sky has gone grey.", "Wind rattles the letterbox.",
         "Grey light, the garden very still.", "A gull cries somewhere overhead."],
    12: ["Overcast, the light flat and white.", "Heavy clouds low over the chimneys.",
         "The street is quiet, everyone at lunch.", "A dog barks twice down the road."],
    13: ["The first drops of rain tick on the glass.", "Rain starting, the patio darkening.",
         "Rain on the skylight.", "The garden bench is spotted with rain."],
    14: ["Steady rain, the gutter gurgling.", "Rain drumming on the conservatory roof.",
         "A car hisses past on the wet road.", "Water streams down the window."],
    15: ["The rain is easing.", "Puddles on the patio catch the light.",
         "A blackbird hops across the wet lawn.", "Drips fall from the porch."],
    16: ["The rain has stopped.", "Low sun under the clouds, everything gleaming.",
         "Wet leaves stuck to the path.", "A faint rainbow over the rooftops."],
    17: ["Dusk coming on.", "Street lamps flickering on one by one.",
         "The sky going orange behind the houses.", "Lights coming on in the houses opposite."],
}

DETAILS = {
    "Kitchen": [
        "The fridge hums.", "The kettle ticks as it cools.", "Three bananas and a lemon in the fruit bowl.",
        "A stack of post on the windowsill.", "Two mugs in the sink.", "The tap drips every few seconds.",
        "The wall calendar is still on last month.", "Keys in the bowl by the back door.",
        "A jar of wooden spoons on the worktop.", "The floor tiles are cold under the wheels.",
        "A spider plant trails from the top of the fridge.", "The bin is half full.",
        "Magnets on the fridge: a lighthouse, a cat, a postcard from Spain.",
        "A fly circles the ceiling light.", "Breadcrumbs on the breadboard.", "The dishwasher door is ajar.",
    ],
    "Living room": [
        "The mantel clock ticks.", "A half-finished jigsaw of a harbour on the coffee table.",
        "Cushions squashed into one corner of the sofa.", "A pile of library books on the footstool.",
        "Photos on the mantelpiece: a wedding, a beach, a graduation.",
        "The television is off, a film of dust on the screen.", "Ruth's knitting bag by the armchair.",
        "A draught from the bay window.", "A bowl of wrapped sweets on the side table.",
        "The carpet shows the tracks of this morning's vacuum.", "A standard lamp leans slightly to the left.",
        "A crossword dictionary lies open, face down.",
    ],
    "Hallway": [
        "Coats on the hooks by the door.", "An umbrella stand with three umbrellas.",
        "Shoes paired along the skirting board.", "The runner rug sits slightly crooked.",
        "Frosted glass in the front door.", "A small table with the telephone and a notepad.",
        "A barometer on the wall pointing to Change.", "The stair carpet is worn in the middle.",
    ],
    "Dining room": [
        "The sideboard, its doors closed.", "A vase of paper flowers on the sideboard.",
        "One bulb out in the ceiling light.", "The curtains half drawn.",
        "A framed map of the coast on the wall.", "The carpet smells faintly of polish.",
    ],
}

AFTER_POWER_CUT = [
    "The lights are back. The microwave clock blinks 00:00.",
    "Self-test after the restart: all joints respond.",
    "The fridge shudders and starts humming again.",
    "The router's lights come back green one by one.",
]

STATUS = [
    "All joints nominal.", "Grippers clean.", "Floor sensors clear.", "Wi-Fi strong.",
    "Left wheel squeaks slightly.", "Camera lens clean.", "Arm temperature normal.", "Microphones clear.",
]


def _at(table: list, t: int):
    """The row of a (from_t, ...) table that covers minute t."""
    return [row for row in table if row[0] <= t][-1]


def clock(t: int) -> str:
    return f"{8 + t // 60:02d}:{t % 60:02d}"


def see_text(t: int, rng: random.Random) -> str:
    """One minute of noise from wherever the robot is."""
    room = _at(ROBOT_ROOM, t)[1]
    _, ruth_room, near, far = _at(RUTH, t)
    parts = [
        f"{room}.",
        rng.choice(near if room == ruth_room and near else far),
        rng.choice(WEATHER[8 + t // 60]),
        rng.choice(_at(RADIO, t)[1]),
    ]
    details = list(DETAILS[room])
    rng.shuffle(details)
    if 370 < t <= 380:
        details.insert(0, rng.choice(AFTER_POWER_CUT))
    status = f"Battery {96 - t // 9} percent. {rng.choice(STATUS)}"
    target = SEE_TOKENS * CHARS_PER_TOKEN
    for d in details:
        if len(" ".join(parts + [status])) + len(d) // 2 >= target:
            break
        parts.append(d)
    return " ".join(parts + [status])


def build_day(seed: int = 0, script: str | Path = SCRIPT) -> list[dict]:
    """The script plus a see line for every minute it leaves empty."""
    fixed = load_day(script)
    taken = {line["t"] for line in fixed}
    rng = random.Random(seed)
    filler = [
        {"t": t, "clock": clock(t), "see": see_text(t, rng)}
        for t in range(max(taken)) if t not in taken
    ]
    return sorted(fixed + filler, key=lambda line: line["t"])


def est_tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


def _text(line: dict) -> str:
    return next(str(line[k]) for k in ("goal", "event", "see", "web", "ask") if k in line)


# Two guesses at how a memory renders a line, until memory.py settles it.
RENDERS = {
    "as text": lambda line: est_tokens(f"{line['clock']} {_text(line)}"),
    "as JSON": lambda line: est_tokens(json.dumps(for_robot(line))),
}


def walls(day: list[dict], overhead: int = 600, window: int = 32_768, page: int = 250) -> dict:
    """The clock at which full history's prompt passes the window, per render.

    overhead is the system prompt and menu; page is the recipe at 13:00 (the
    cached one; a live page is 2 to 4K and moves the wall earlier).
    """
    out = {}
    for name, size in RENDERS.items():
        total, out[name] = overhead, None
        for line in day:
            total += 12 if "ask" in line else size(line)  # an ask adds a "did" line
            if line["t"] == 300 and "ask" in line:
                total += page
            if total > window:
                out[name] = line["clock"]
                break
    return out


def window_lines(day: list[dict], t: int, budget: int = 4_096) -> int:
    """How many lines before minute t fit in the budget beside the goal, as JSON."""
    used, held = est_tokens(day[0]["goal"]), 0
    for line in reversed([line for line in day if line["t"] < t and "ask" not in line]):
        used += RENDERS["as JSON"](line)
        if used > budget:
            break
        held += 1
    return held


def summary(day: list[dict]) -> str:
    see = [est_tokens(line["see"]) for line in day if "see" in line]
    wall = ", ".join(f"{clock} {name}" for name, clock in walls(day).items())
    return (
        f"{len(day)} lines, {len(see)} see lines at ~{sum(see) // len(see)} tokens each "
        f"(chars/{CHARS_PER_TOKEN}). Full history passes 32,768 at {wall}. "
        f"At 11:00 a 4,096 window holds the last {window_lines(day, 180)} lines."
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Write the full day: the script plus a see line every empty minute.")
    p.add_argument("--seed", type=int, default=0, help="see-line noise; 0 is the committed day")
    p.add_argument("--out", default=str(DAY))
    args = p.parse_args(argv)
    day = build_day(args.seed)
    with open(args.out, "w") as f:
        for line in day:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"{args.out}: {summary(day)}", file=sys.stderr)


if __name__ == "__main__":
    main()
