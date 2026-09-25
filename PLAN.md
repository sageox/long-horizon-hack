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

### Sponsors

| Sponsor | What it does in the demo | Status |
|---|---|---|
| **Liquid AI** | The robot's brain. LFM2.5-1.2B picks every action; LFM2.5-350M decides which events become memories. Both local. The 1.2B model's 32,768-token window is the wall full history hits at 14:51. | agreed |
| **Tinybird** | The robot's memory outside the model: task board, memories, event log. The 14:10 reboot reads it; the live dashboard polls it. | agreed |
| **AWS** | Bedrock plans instead if LFM2.5-1.2B fails the 13:30 go/no-go. | agreed, fallback |
| **Black Forest Labs** | **FLUX 3 Action** as the robot's hands: executes the planner's instruction for one step, the 17:30 roast. Replaces the pre-generated FLUX images. | proposed (Faridun), needs a GPU |
| **Nimble** | Recipe lookup when the stew starts at 13:00. The query depends on memory: the window robot forgot Leo is vegan and searches for the wrong stew. | proposed (Faridun), open |

**Why FLUX 3 Action fits.** It is a 7B robot policy: camera frames, joint state
and an instruction in, the next 32 to 42 motor commands out, then it re-plans
from fresh frames. It carries no memory beyond the arm's current state, so it
handles seconds and our task board handles hours. On stage: "FLUX 3 Action can
take the roast out of the oven. It can't remember there's a roast in the oven."

**Why Nimble is still open.** The earlier call was "no web data in a kitchen."
The counter-case: a home robot looking up a recipe is ordinary, and it puts the
vegan failure on screen as a wrong search rather than a missing string. It is
also the only sponsor that scores on Autonomy ("acts on the web using real-time
data"), which otherwise scores near zero. Decide together. Neither changes the
day's script, the six checks or the scorecard. FLUX 3 Action sits below the
planner and touches nothing in the contract; Nimble adds one action,
`search_recipe(query)`, to `fixtures/menu.json`.

### On stage: the kitchen and Tinybird side by side

The left half of the screen is the kitchen viewer playing the day. The right
half is a live Tinybird dashboard, and every panel on it is a Tinybird
endpoint polled once a second, not a copy of the viewer's data. The harness
streams `events.jsonl` into Tinybird at playback speed, so the right side
fills as the day plays.

| Panel | Endpoint | What it shows |
|---|---|---|
| Context per robot | `context_by_minute` | three lines climbing, the 32K wall |
| Scorecard | `checks_by_robot` | checks filling in as they happen |
| The board | `board_for_robot?robot=task_board` | exactly what the robot reads when it wakes |
| Event tail | `latest_events` | rows landing, per robot |

At the power cut the left robot goes dark, its event tail stops, and the board
panel stays: "this is what it wakes up with." On restart the robot reads that
same endpoint and its rows start landing again. The audience sees the robot's
memory living in Tinybird, not in the process.

If Tinybird fails on the day, the right half reads local JSONL and is labelled
as such.

## The contract: `day.jsonl`

One JSON object per line: something that happens, or the world asking the
robot what to do next. **Agree this now and nothing else needs coordinating.**

```json
{"t": 59, "clock": "08:59", "see": "Kitchen. Ruth at the table with tea. Radio on."}
{"t": 60, "clock": "09:00", "event": "Ruth: 'Leo told me he's vegan now, you know.'"}
{"t": 570, "clock": "17:30", "ask": "what next?",
 "check": {"id": "roast_out", "pass_if": "take_roast_out"}}
```

`t` is minutes since 08:00. The robot never sees `check`; the harness grades
the chosen action against it by string match.

One `see` line every minute, about 75 tokens each. That density is what fills
32K by mid-afternoon; the ~40 events alone come to about 3K and full history
would never hit the wall.

The action menu is one fixed list in `kitchen.py`, the same on every ask. A
menu that offers `take_roast_out` only while the roast is in hands every robot
the answer.

The script is fixed. Actions change graded state (roast in or out, salt count,
places set), never which events happen next, so a robot that goes wrong early
doesn't send the day down a branch nobody wrote.

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

Three implementations, each given the same planner (a fourth if there's time):

- `FullHistory`: every event. Past 32,768 tokens the planner call fails and we
  log it. No silent truncation, or it becomes a worse sliding window.
- `SlidingWindow(4096)`: the goal plus the most recent events that fit.
- `TaskBoard(4096)`: the goal, a board (todo / doing / done / blocked with
  start times), memories keyed by label (`constraint:leo_vegan`,
  `lesson:dryer_broken`, `update:guests=7`), and the last 10 events. Every
  change goes to Tinybird before the planner runs, so a reboot loses nothing.
- `RollingSummary(4096)`, if done by 14:15: when the window fills, LFM rewrites
  a running summary. This is what production agents do, and judges will ask
  "why not just summarize?" Whatever it scores, it's the honest comparison.

Curator: LFM2.5-350M labels each event constraint / lesson / update / noise.
Planner: LFM2.5-1.2B picks one action from the menu. Both run locally through
Ollama (0.34.4, installed, both models pulled). Weights:
`LiquidAI/LFM2.5-1.2B-Instruct-GGUF` and `LiquidAI/LFM2.5-350M-GGUF`;
`LiquidAI/LFM2-1.2B-Tool-GGUF` is a tool-calling variant to try if the planner
struggles to pick from the menu.

Ollama truncates an overlong prompt without an error. Measured at 12:50: with
`num_ctx` 32768, a ~50K-token prompt came back with `prompt_eval_count` 16,387
and a normal answer. Left alone, full history quietly becomes a sliding window
and never hits the wall. Count tokens ourselves with the LFM tokenizer
(`tokenizers` package, `tokenizer.json` from the model repo) before every
call, pass `num_ctx` 32768, and fail the call when the count is over. Don't
trust `prompt_eval_count`; it's measured after truncation.

Latency is not the story. A 12K-token prompt took 1.4 to 2 seconds on this
laptop, so pitch the 32K wall, not slow reactions.

## Order

1. 12:45: fixture `day.jsonl` by hand, both LFM models answering locally.
2. Both halves in parallel against the fixture.
3. 13:30: planner go/no-go. Given a hand-written perfect board, does 1.2B pick
   the right action at all six checks? If not, Bedrock plans under an enforced
   32K cap and LFM stays the curator.
4. 14:15: integrate. Full day, three scorecards, one command.
5. 14:45: viewer plays the day. **Submittable here.** Record a backup video.
6. Tinybird behind the board and the chart; the 14:10 reboot reads from it.
   The right half of the screen polls the four endpoints.
7. FLUX 3 Action on the 17:30 roast step, if BFL gives us a GPU: the planner's
   `take_roast_out` becomes the policy's instruction. Pre-generated FLUX images
   only if there's no GPU. Freeze at 15:30.
8. Rehearse the three minutes twice. Submit at 16:15.

If behind, cut in this order: FLUX, the live power cut (keep it in the video),
the Tinybird chart (the board still persists), the LFM planner. Never cut the
single all-day goal, the board, the 32K wall, the six checks, or the equal 4K
budget for window and board.

## Blind spots

Checked at 12:40. Each has an owner and a time.

- ~~**The repo is private.**~~ Done 12:48: history scanned for secrets (none),
  repo made public.
- ~~**No local runtime.**~~ Done 12:50: Ollama installed as a service, both LFM
  models pulled.
- **Silent truncation.** Confirmed, see above. Madhur, in the planner wrapper
  before the 13:30 gate.
- **Keys.** Tinybird workspace token, FLUX API key, Bedrock credentials (the
  planner fallback). Nobody has checked they work. Madhur, by 13:00. Add a
  Nimble key if the recipe lookup goes in.
- **FLUX 3 Action needs Linux and an NVIDIA GPU.** Its setup doc says so and
  lists an H200; it won't run on either Mac, and there is no hosted API in the
  docs. Ask the BFL table whether they host inference or lend GPUs for the
  Action track. Faridun, now. If not, show the planner emitting the
  instruction and say plainly that no rollout ran; don't fake one.
- ~~**Faridun's last commit (11:18) was the web-research fixture.**~~ Done:
  `fixtures/day.jsonl` and `fixtures/menu.json` replaced it, reproducing
  2/6, 1/6, 6/6. The switch is confirmed.
- **Six checks, one run.** A robot with no memory can guess a two-way choice
  right. Temperature 0, show the model's stated reason for each check, and
  run three days with different `see` noise if time allows. Say "in our run",
  not "always".
- **The live power cut has to be live.** Run the task-board robot for real
  from 14:00, with model calls served from the cache by prompt hash. If the
  board comes back right, every prompt after the restart matches the recorded
  run and hits the cache; a miss means the restore went wrong. It's fast on
  stage and it checks itself.
- **Reading straight back from Tinybird.** Ingest may lag a few seconds behind
  the write. Write to local JSONL first; on reboot read Tinybird and compare
  with the local log, and show both if they differ.
- **Tinybird is the biggest prize pool.** Covered by the side-by-side above.
  Set up the workspace and the four endpoints by 14:15 so the live panel is
  tested before the submittable gate. Risk: workspace setup eats time; check
  the account and token at 13:00.
- **Unknowns about the event.** Ask the organizers how long a finalist demo is
  and what judges score. Host the video somewhere with a shareable link.
- **The README states the result before the run.** Replace it with the real
  scorecard at 14:45.

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
