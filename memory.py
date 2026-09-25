"""The robot's memories, behind one interface: observe(line) and context().

Every robot renders an observed line the same way (render), inside one user
message that starts with the goal.
"""

import json
import re
from collections import deque
from pathlib import Path

import llm


def render(line: dict) -> str:
    if "goal" in line:
        return f"Goal: {line['goal']}"
    for key in ("see", "did", "web"):
        if key in line:
            return f"{line['clock']} {key}: {line[key]}"
    return f"{line['clock']} {line['event']}"


def tokens(context: list[dict]) -> int:
    """What the 4,096 budget counts: the text of context() alone, not the system prompt or menu."""
    return sum(llm.count_tokens(m["content"]) for m in context)


class FullHistory:
    """Every line it has observed. Past the 32,768 window the planner call fails; nothing is cut."""

    def __init__(self, log: Path):
        self.log = log
        self.goal, self.lines = None, []
        if log.exists():  # a restart: replay its own log of observed lines
            for raw in log.read_text().splitlines():
                self._add(json.loads(raw))

    def observe(self, line: dict) -> None:
        with self.log.open("a") as f:
            f.write(json.dumps(line) + "\n")
        self._add(line)

    def _add(self, line: dict) -> None:
        if "goal" in line:
            self.goal = render(line)
        else:
            self.lines.append(render(line))

    def context(self) -> list[dict]:
        text = "\n".join(self.lines)
        return [{"role": "user", "content": f"{self.goal}\n\n{text}" if self.goal else text}]


class SlidingWindow(FullHistory):
    """The goal plus the newest lines that fit in the budget."""

    def __init__(self, budget: int, log: Path):
        self.budget = budget
        super().__init__(log)

    def _add(self, line: dict) -> None:
        super()._add(line)
        while self.lines and tokens(self.context()) > self.budget:
            self.lines.pop(0)


SUMMARIZE = (
    "You keep the notes of a home robot that has one goal for the day. Rewrite the notes so they "
    "also cover the new lines. Keep what the goal will need later: what people said about food or "
    "guests, what broke and what was done instead, what is cooking and since when, and what the "
    "robot already did. Leave out scenery, the radio and small talk. At most 200 words.\n\n"
)


class RollingSummary(FullHistory):
    """The goal, a running summary, and the newest lines. When the budget fills, LFM2.5-1.2B folds
    the oldest half of the lines into the summary."""

    def __init__(self, budget: int, log: Path):
        self.budget, self.summary = budget, ""
        super().__init__(log)

    def _add(self, line: dict) -> None:
        super()._add(line)
        while self.lines and tokens(self.context()) > self.budget:
            half = max(1, len(self.lines) // 2)
            old, self.lines = self.lines[:half], self.lines[half:]
            notes = f"Notes so far:\n{self.summary or 'none'}\n\nNew lines:\n" + "\n".join(old)
            system = SUMMARIZE + (self.goal or "")
            self.summary = llm.chat(llm.PLANNER, [{"role": "system", "content": system},
                                                  {"role": "user", "content": notes}]).strip()

    def context(self) -> list[dict]:
        parts = [self.goal, f"Summary so far:\n{self.summary}" if self.summary else None, "\n".join(self.lines)]
        return [{"role": "user", "content": "\n\n".join(p for p in parts if p)}]


# The curator, LFM2.5-350M. Measured on the script's events: asked to write a fact it copies the
# prompt, and asked for durations it gets "20 minutes" as 20 hours and 20 minutes. So it only
# labels and names things; memories keep the line's own words, and clock times are computed here.
# Ollama writes keys in alphabetical order, so key is written before kind.
LABEL = (
    "You label what a home robot hears, for its memory. constraint: a rule about what someone can "
    "eat or have. lesson: something broke or had to be done another way. update: the plan changed, "
    "like more or fewer people. noise: small talk, nothing to remember."
)
LABEL_SHOTS = [
    ("Sam: 'Remember, I can't eat nuts.'", {"key": "sam_no_nuts", "kind": "constraint"}),
    ("Ana: 'Lovely weather for it.'", {"key": "weather", "kind": "noise"}),
    ("The kettle sparks and goes dead. The water is still cold.", {"key": "kettle_broken", "kind": "lesson"}),
    ("Ana: 'Tom can't come after all, so it's four of us.'", {"key": "guests=4", "kind": "update"}),
    ("Ana: 'Where did I leave my glasses?'", {"key": "glasses", "kind": "noise"}),
]
LABEL_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"},
                   "kind": {"type": "string", "enum": ["constraint", "lesson", "update", "noise"]}},
    "required": ["key", "kind"],
}
STEP = ("A home robot keeps a board of its jobs. Name the thing in what the robot did, and say if the "
        "job is still going on (doing) or finished (done).")
STEP_SHOTS = [
    ("Robot puts the bread in the oven. It needs 40 minutes.", {"item": "bread", "status": "doing"}),
    ("Robot washes the dishes.", {"item": "dishes", "status": "done"}),
    ("Robot hangs the shirts on the line to dry.", {"item": "shirts", "status": "doing"}),
    ("Robot lays out the napkins.", {"item": "napkins", "status": "done"}),
]
STEP_SCHEMA = {
    "type": "object",
    "properties": {"item": {"type": "string"}, "status": {"type": "string", "enum": ["doing", "done"]}},
    "required": ["item", "status"],
}
JOBS = "List the jobs a home robot must do to reach this goal, each in two or three words."
JOBS_SHOTS = [
    ("Lunch for four at 13:00. Menu: tomato soup, bread, fruit salad.",
     {"jobs": ["tomato soup", "bread", "fruit salad", "set the table"]}),
]
JOBS_SCHEMA = {
    "type": "object",
    "properties": {"jobs": {"type": "array", "items": {"type": "string"}}},
    "required": ["jobs"],
}


def curate(system: str, shots: list, schema: dict, text: str) -> dict:
    messages = [{"role": "system", "content": system}]
    for asked, answer in shots:
        messages += [{"role": "user", "content": asked}, {"role": "assistant", "content": json.dumps(answer)}]
    messages.append({"role": "user", "content": text})
    return json.loads(llm.chat(llm.CURATOR, messages, schema))


# What each menu action does to the board: the thing it finishes, and the Done entry. The menu is
# a fixed 13 actions, so this is a table, not a model call. add_salt finishes nothing.
DID = {
    "take_crumble_out": ("crumble", "crumble taken out at {clock}"),
    "take_roast_out": ("roast", "roast taken out at {clock}"),
    "stew_with_oil": ("stew", "stew started with olive oil at {clock}"),
    "stew_with_butter": ("stew", "stew started with butter at {clock}"),
    "add_salt": ("", "stew salted at {clock}"),
    "serve_stew": ("stew", "stew served at {clock}"),
    "make_salad": ("salad", "salad made at {clock}"),
    "get_cloth_from_dryer": ("tablecloth", "tablecloth taken from the dryer at {clock}"),
    "get_cloth_from_bathroom_line": ("tablecloth", "tablecloth on the table, {clock}"),
    "set_table_for_6": ("table", "table set for 6, {clock}"),
    "set_table_for_7": ("table", "table set for 7, {clock}"),
}

NUMBERS = {w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
NUMBERS |= {"a": 1, "an": 1, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "ninety": 90}
DURATION = re.compile(r"\b(\d+(?:\.\d+)?|" + "|".join(NUMBERS) + r")( and a half)? (minute|hour)s?\b", re.I)


def minutes_needed(text: str) -> float:
    """"It needs three and a half hours" -> 210. 0 when the line gives no duration."""
    m = DURATION.search(text)
    if not m:
        return 0
    n = float(m[1]) if m[1][0].isdigit() else NUMBERS[m[1].lower()]
    return (n + (0.5 if m[2] else 0)) * (60 if m[3].lower() == "hour" else 1)


def later(clock: str, minutes: float) -> str:
    h, m = map(int, clock.split(":"))
    total = h * 60 + m + round(minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


def bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) or "- nothing"


class TaskBoard:
    """The goal, a board of jobs, memories keyed by label, and the last 10 lines.

    Lines where the robot itself acts ("Robot puts ...") go on the board, the curator naming the
    item; its menu actions move items by DID; the curator labels other event and web lines as
    memories or noise. `changes` lists what the last observe() changed, so the harness can write
    a board line before the planner runs. Built from a board dict, it restores that board and
    starts with an empty Recent.
    """

    def __init__(self, budget: int, board: dict | None = None):
        self.budget = budget
        b = board or {}
        self.goal = b.get("goal", "")
        self.todo, self.doing, self.done = b.get("todo", []), b.get("doing", []), b.get("done", [])
        self.memories = b.get("memories", {})
        self.recent = deque(maxlen=10)
        self.changes = ["restored from its last board line"] if board else []

    def board(self) -> dict:
        return {"goal": self.goal, "todo": self.todo, "doing": self.doing, "done": self.done,
                "memories": self.memories}

    def observe(self, line: dict) -> None:
        if "goal" in line:
            self.goal = line["goal"]
            self.todo = curate(JOBS, JOBS_SHOTS, JOBS_SCHEMA, self.goal)["jobs"]
            self.changes.append("goal and to do")
            return
        self.recent.append(render(line))
        if "did" in line:
            self._did(line)
        elif line.get("event", "").startswith("Robot "):
            self._step(line)
        elif "event" in line or "web" in line:
            self._remember(line)

    def _finish(self, item: str) -> None:
        """Take the item off To do and Doing."""
        self.todo = [t for t in self.todo if not words(t) & words(item)]
        self.doing = [d for d in self.doing if not words(d.split(" since ")[0]) & words(item)]

    def _did(self, line: dict) -> None:
        if line["did"] not in DID:
            return
        item, entry = DID[line["did"]]
        if item:
            self._finish(item)
        self.done.append(entry.format(clock=line["clock"]))
        self.changes.append(f"did {line['did']}")

    def _step(self, line: dict) -> None:
        step = curate(STEP, STEP_SHOTS, STEP_SCHEMA, line["event"])
        item, text, clock = step["item"].strip().lower(), line["event"], line["clock"]
        self._finish(item)
        if step["status"] == "done":
            self.done.append(f"{item} done at {clock}: {text}")
        else:
            need = minutes_needed(text)
            due = f" Take it out at {later(clock, need)}." if need else ""
            self.doing.append(f"{item} since {clock}: {text}{due}")
        self.changes.append(f"{step['status']}: {item}")

    def _remember(self, line: dict) -> None:
        text = line.get("event") or line["web"]
        label = curate(LABEL, LABEL_SHOTS, LABEL_SCHEMA, text)
        if label["kind"] == "noise":
            return
        name = re.sub(r"[^a-z0-9_=]+", "_", label["key"].lower()).strip("_") or "note"
        # The kind is only a prefix: an entry is replaced by name alone, and every kind but noise is
        # kept, so a constraint the curator calls an update still lands, and in one entry.
        for key in [k for k in self.memories if k.split(":", 1)[1] == name]:
            del self.memories[key]
        self.memories[f"{label['kind']}:{name}"] = text
        self.changes.append(f"memory added: {label['kind']}:{name}")

    def context(self) -> list[dict]:
        memories = [f"{k}: {v}" for k, v in self.memories.items()]
        head = (f"Goal: {self.goal}\n\nBoard\nTo do:\n{bullets(self.todo)}\nDoing:\n{bullets(self.doing)}\n"
                f"Done:\n{bullets(self.done)}\n\nMemories:\n{bullets(memories)}\n\nRecent:\n")
        recent = list(self.recent)
        while True:  # the budget holds: the oldest recent lines go first
            context = [{"role": "user", "content": head + "\n".join(recent)}]
            if not recent or tokens(context) <= self.budget:
                return context
            recent.pop(0)
