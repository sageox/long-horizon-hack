# Plan

Two people, roughly four hours. The split works because both halves meet at one
file and neither needs the other to exist first.

Full plan with the interactive day: `ox plan view robot-dinner-at-six`.

## The demo

A home robot gets one goal at 08:00: **dinner for the family on the table at
18:00.** About 40 dependent steps over ten hours, on LFM2.5-1.2B with a 32,768
token window. The same day runs three times, one per memory strategy. At 18:00
we grade the table.

| Time | Event | Tests |
|---|---|---|
| 09:00 | Ruth: "Leo is vegan now." | memory: a constraint, used at 13:00 |
| 11:00 | Dryer breaks; cloth hung in the bathroom | memory: a lesson, used at 16:30 |
| 12:00 | Ruth: "Mia's coming, so seven." | memory: an update, used at 16:30 |
| 13:30 | Stew salted | state: don't salt again at 17:45 |
| 14:00 | Roast in. The oven has no timer. | state: take it out at 17:30 |
| 14:10 | Power cut, robot restarts | state: board restored from Tinybird |
| 14:51 | Full history reaches 32,768 tokens | context: it can no longer plan |

Six checks at 18:00: crumble out (the control, all three pass), stew vegan,
tablecloth on the table, seven places, roast out on time, stew salted once.

Nimble is out; there is no web data in a kitchen. Liquid, Tinybird and FLUX
are in.

## The contract: `day.jsonl`

One JSON object per line: something that happens, or the world asking the
robot what to do next. **Agree this now and nothing else needs coordinating.**

```json
{"t": 60, "clock": "09:00", "event": "Ruth: 'Leo told me he's vegan now, you know.'"}
{"t": 570, "clock": "17:30", "ask": "what next?",
 "menu": ["take_roast_out", "tidy_living_room", "make_salad", "set_table", "wait"],
 "check": {"id": "roast_out", "pass_if": "take_roast_out"}}
```

`t` is minutes since 08:00. The robot never sees `check`; the harness grades
the chosen action against it by string match.

## Split

**Faridun, the kitchen.** `kitchen.py`: task graph, event script, action
effects, the six checks, then the viewer. Deliverable: a full `day.jsonl` and
a viewer that plays `events.jsonl`.

**Madhur, the robot.** The three memories behind one interface, the curator,
the planner, Tinybird. Works against a **hand-written 30-line `day.jsonl`**
until the real one exists. Deliverable: three scorecards and three context
curves from one command.

Neither of you waits. Swap the fixture for the real file when the kitchen
lands.

## The interface

```python
class Memory:
    def observe(self, event: dict) -> None: ...   # one day.jsonl line
    def context(self) -> list[dict]: ...          # the planner's prompt
```

Three implementations, each given the same planner:

- `FullHistory`: every event. Past 32,768 tokens the planner call fails and we
  log it. No silent truncation, or it becomes a worse sliding window.
- `SlidingWindow(4096)`: the goal plus the most recent events that fit.
- `TaskBoard(4096)`: the goal, a board (todo / doing / done / blocked with
  start times), memories keyed by label (`constraint:leo_vegan`,
  `lesson:dryer_broken`, `update:guests=7`), and the last 10 events. Every
  change goes to Tinybird before the planner runs, so a reboot loses nothing.

Curator: LFM2.5-350M labels each event constraint / lesson / update / noise.
Planner: LFM2.5-1.2B picks one action from the menu. Both run locally through
Ollama or llama.cpp. Count tokens with the LFM tokenizer so the 32K wall is
real.

## Order

1. 12:45: fixture `day.jsonl` by hand, both LFM models answering locally.
2. Both halves in parallel against the fixture.
3. 13:30: planner go/no-go. Given a hand-written perfect board, does 1.2B pick
   the right action at all six checks? If not, Bedrock plans under an enforced
   32K cap and LFM stays the curator.
4. 14:15: integrate. Full day, three scorecards, one command.
5. 14:45: viewer plays the day. **Submittable here.** Record a backup video.
6. Tinybird behind the board and the chart; the 14:10 reboot reads from it.
7. FLUX kitchen and 18:00 tables, pre-generated. Freeze at 15:30.
8. Rehearse the three minutes twice. Submit at 16:15.

If behind, cut in this order: FLUX, the live power cut (keep it in the video),
the Tinybird chart (the board still persists), the LFM planner. Never cut the
single all-day goal, the board, the 32K wall, the six checks, or the equal 4K
budget for window and board.

## Rules for today

Write JSONL to stdout first, Tinybird second. If ingest fights us we still have
a result and a chart.

Cache every model call by prompt hash. The demo plays back a recorded day; only
the power cut runs live.

Grade with string matching against the menu action. No LLM judge.

Show every decision, not just the six checks. The crumble control passes for
all three, so the baselines are not rigged.

Branch for real work, both of us. `main` stays green so either of us can demo
from it at any moment.
