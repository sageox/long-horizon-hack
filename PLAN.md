# Plan

Two people, roughly four hours. The split works because both halves meet at one
file and neither needs the other to exist first.

Full plan with the interactive day: `ox plan view robot-dinner-at-six`.

## The demo

A home robot gets one goal at 08:00: **dinner for the family on the table at
18:00.** About 40 dependent steps over ten hours, on LFM2.5-8B-A1B held to a
32,768-token window. The same day runs three times, one per memory strategy. At 18:00
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
| **Liquid AI** | The robot's brain. LFM2.5-8B-A1B (8B parameters, about 1B active per token) picks every action; LFM2.5-350M decides which events become memories. Both local. The robot's 32,768-token budget is the wall full history hits at 14:51. | agreed |
| **Tinybird** | The robot's memory outside the model: task board, memories, event log. The 14:10 reboot reads it; the live dashboard polls it. | agreed |
| **AWS** | Was the planner fallback (Bedrock). Dropped at the go/no-go: the planner stays on Liquid. | dropped |
| **Black Forest Labs** | **FLUX 3 Action** as the robot's hands: executes the planner's instruction for one step, the 17:30 roast. Run once on a GPU, recorded, played on stage. | Faridun's pick, needs a GPU |
| **Nimble** | Recipe lookup when the stew starts at 13:00. The query depends on memory: the window robot forgot Leo is vegan and searches for the wrong stew. | in |

**Why FLUX 3 Action fits.** It is a 7B robot policy: camera frames, joint state
and an instruction in, the next 32 to 42 motor commands out, then it re-plans
from fresh frames. It carries no memory beyond the arm's current state, so it
handles seconds and our task board handles hours. On stage: "FLUX 3 Action can
take the roast out of the oven. It can't remember there's a roast in the oven."

**Why Nimble is in.** The earlier call was "no web data in a kitchen." But a
home robot looking up a recipe is ordinary, and it puts the vegan failure on
screen as a wrong search rather than a missing string: the task board searches
for a vegan stew and gets olive oil, the window searches for a plain one and
gets butter. It is the only sponsor that scores on Autonomy ("acts on the web
using real-time data"), and the only one besides Liquid and Tinybird that runs
from a laptop, which makes it our guaranteed third tool. Neither Nimble nor
FLUX 3 Action changes the day's script, the six checks or the scorecard.

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

`search_recipe(query)` is a **lookup**, not an action, and lives under
`lookups` in `fixtures/menu.json`. At any ask the planner may make one lookup
before choosing its action; the harness runs it through Nimble, emits the
result as a `web` line at the same `t`, calls `observe()` on it for every
memory, then asks again. Only the final action is graded, so a robot can't pass
a check by searching instead of acting. Offline, `fixtures/web_cache.json`
answers instead: queries mentioning vegan, plant-based or dairy-free get the
olive-oil stew, anything else gets butter. For the real run, write each Nimble
response back to that file so a replay returns the same page.

A live recipe page is 2 to 4K tokens against about 250 in the cache, so full
history reaches 32K earlier than 14:51. No check changes; quote the time the
run actually shows.

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

Neither of you waits. `fixtures/script.jsonl` (38 lines, six checks) holds the
fixed lines; `python kitchen.py` fills every empty minute with a see line and
writes `fixtures/day.jsonl` (601 lines), the file the harness plays.
`fixtures/events.sample.jsonl` stands in for the harness output so the viewer
and the Tinybird pipes can be built before `run.py` exists.

### Tasks

Madhur, branch `madhur/robot`:

| # | Task | Files | By |
|---|---|---|---|
| M1 | Token count, 32K guard, Ollama call, prompt-hash cache | `llm.py` | 13:45 |
| M2 | Planner: context and menu in, action or one lookup out | `planner.py` | 13:50 |
| M3 | Go/no-go on a hand-written perfect board; Bedrock if it fails | scratch | 14:00 |
| M4 | `FullHistory`, `SlidingWindow`, `TaskBoard`, the 350M curator | `memory.py` | 14:15 |
| M5 | Harness: all robots over the day, `events.jsonl`, scorecards | `run.py` | 14:15 |
| M6 | Tinybird `events` datasource, ingest, reboot reads the board | `run.py`, `tinybird/datasources/` | 15:00 |
| M7 | `RollingSummary`, only if M4 is done by 14:15 | `memory.py` | stretch |

Faridun, branch `faridun/kitchen`:

| # | Task | Files | By |
|---|---|---|---|
| F1 | `grade(line, action)` and `search_recipe(query)` over `web_cache.json` | `kitchen.py` | 13:50 |
| F2 | Full day: a `see` line every minute around the fixed events | `kitchen.py`, `day.jsonl` | 14:15 |
| F3 | Live Nimble behind `search_recipe`, writing responses back to the cache | `kitchen.py` | 14:15 |
| F4 | Viewer: three robots side by side, checks lighting up | `viewer/index.html` | 14:45 |
| F5 | The four Tinybird endpoints and the right-half panel | `tinybird/pipes/`, `viewer/` | 15:15 |
| F6 | FLUX 3 Action: GPU from BFL, record the 17:30 rollout | none | 15:30 |
| F7 | Backup video once F4 plays a real run | none | 14:45 |

Handoffs: `kitchen.py` at 13:50 (the harness imports `grade` and
`search_recipe`), the generated `day.jsonl` at 14:15, a real `events.jsonl`
for the viewer at 14:45. The only shared directory is `tinybird/`: Madhur owns
the datasource, Faridun the pipes.

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
Planner: LFM2.5-8B-A1B picks one action from the menu. Both run locally through
Ollama 0.34.4. Weights: `LiquidAI/LFM2.5-8B-A1B-GGUF` (Q4_K_M, 5.2 GB) and
`LiquidAI/LFM2.5-350M-GGUF`. The 8B writes hidden reasoning before it answers,
so a decision takes about 10 seconds; the day has six asks per robot.

Ollama truncates an overlong prompt without an error. Measured at 12:50: with
`num_ctx` 32768, a ~50K-token prompt came back with `prompt_eval_count` 16,387
and a normal answer. Left alone, full history quietly becomes a sliding window
and never hits the wall. Count tokens ourselves with the LFM tokenizer
(`tokenizers` package, `tokenizer.json` from the model repo) before every
call, pass `num_ctx` 32768, and fail the call when the count is over. Don't
trust `prompt_eval_count`; it's measured after truncation.

Latency is not the story. A 12K-token prompt took 1.4 to 2 seconds on this
laptop, so pitch the 32K wall, not slow reactions.

## Conventions

Decided 13:30. Change one here before changing it in code.

**Every robot survives the power cut.** At the `system: power_cut` line the
harness drops each memory object and builds a fresh one that restores itself:
`TaskBoard` from the Tinybird board (local JSONL if Tinybird lags or fails),
`FullHistory` and `SlidingWindow` by replaying their own log of observed
lines. If the baselines lost everything at 14:10, full history would never hit
the wall at 14:51 and the baselines would lose for a reason that isn't memory
design. The power cut tests whether what a robot kept is enough, not whether
it kept anything.

**Robots:** `full_history`, `sliding_window`, `task_board`, `rolling_summary`.

**Run order.** The harness walks the day once; for each line it steps every
robot. `events.jsonl` comes out interleaved by `t`, and the viewer and the
Tinybird streamer both play that one file.

**What a memory observes:** every day line except `ask`; after each decision a
`{"t", "clock", "did": "<action>"}` line, so the robot knows it chose to salt
or not; and the `web` line from its own lookup. The curator labels `event` and
`web` lines only. `see` lines go straight into the last-10 buffer.

**The task board** (M4, 14:30). The curator lists To do from the goal line. An
event where the robot itself acts ("Robot puts the roast chicken in the oven.
It needs three and a half hours.") goes on the board instead of being
labelled: the curator names the item and says doing or done, and code parses
the duration and appends "Take it out at 17:30". A `did` line moves items by a
table in `memory.py`, one row per menu action. Other `event` and `web` lines
are labelled, and a memory's text is the line's own words: asked to write a
fact, the 350M copies its prompt. The kind is only a prefix and memories are
replaced by name, so a wrong kind still keeps the memory; a line labelled
noise is dropped. The `board` JSON has `goal`, `todo`, `doing`, `done` and
`memories`. Recent is not in it, so after the power cut it starts empty.

**Planner output** is Ollama structured output with a JSON schema, `anyOf`
`{"asked", "due", "facts", "reason": str, "step": <enum of menu.actions>}` or
the same notes with `"search_recipe": str`. Ollama writes keys in alphabetical
order whatever order the schema gives, so the model fills in what was asked,
what is due, the facts that matter and its reason before it writes the choice.
`planner.decide` returns the step as `action`. The enum makes an off-menu
action impossible. After one lookup the second call's schema drops the lookup, so the
second answer has to be an action.

**Over 32K** no call is made. The harness logs `kind: "error"`,
`action: "context_overflow"`, fails the check if the ask had one, and keeps
observing so the context curve keeps climbing. No retry.

**The 4,096 budget** counts only the tokens of `memory.context()`. The system
prompt and the menu are the same fixed overhead for every robot. The 32,768
wall is checked against the whole rendered prompt.

**Grading** is `action == check["pass_if"]` and nothing else. Kitchen state
(roast in or out, places set) is display only; the viewer derives it from
`action` lines.

**Tokens** are counted with the LFM2.5-1.2B `tokenizer.json` over the rendered
chat prompt. `context_tokens` is written on every `events.jsonl` line, not
just on asks, so the chart has a point per line.

**Model calls:** `temperature` 0, `seed` 0, `num_ctx` 32768. Cache in
`cache/llm.jsonl` keyed by the `sha256` of the whole request: model, messages,
options and schema, since the same prompt under a different schema gets a
different answer. The cache is committed, so either laptop replays the day
without a model.

**`events.jsonl`**, one line per thing that happened to one robot:

```json
{"robot": "task_board", "t": 570, "clock": "17:30", "kind": "action",
 "text": "take_roast_out", "action": "take_roast_out",
 "reason": "Roast went in at 14:00 for 3.5 hours.",
 "check": "roast_out", "pass": true, "context_tokens": 3120}
```

`kind` is one of `see`, `event`, `web`, `system`, `action`, `error`, `board`.
Always present: `robot`, `t`, `clock`, `kind`, `text`, `context_tokens`.
Optional: `action`, `reason`, `query` (on `web`), `check` and `pass` (on the
graded action), `board` (on `board`). `TaskBoard` writes a `board` line
whenever its board or memories change; `board` is the whole board as a JSON
string. See `fixtures/events.sample.jsonl`.

**Tinybird:** one datasource, `events`, with the `events.jsonl` schema plus
`run`, the run's start time, so the endpoints' `max(run)` is the newest run,
and `seq`, the line's order in its run. `tinybird.py` sends lines and reads the
board back; `uv run tinybird.py runs/<run>/events.jsonl` streams a finished run
at playback speed. Without `TB_HOST` it talks to Tinybird Local
(`uvx --from tinybird tb local start`, then `tb deploy` in `tinybird/`).
`board_for_robot` returns the latest `board` row for a robot, and the reboot
reads that endpoint. Local JSONL first, Tinybird second.

**Playback:** one simulated minute is 0.3 seconds, so the day plays in three
minutes. The viewer and the streamer use the same constant.

**Memory keys:** `<kind>:<snake_label>`, `kind` one of `constraint`, `lesson`,
`update`. The curator's `noise` label is dropped.

**Layout:** flat Python files at the repo root, `pyproject.toml` with uv,
dependencies `tokenizers` and `requests` (Ollama's HTTP API directly, no SDK).
The viewer is one file, `viewer/index.html`. Output goes to
`runs/<run>/events.jsonl` (gitignored) with the scorecard on stdout. One
command: `uv run run.py --day fixtures/day.jsonl`, with `--robots task_board`
to run a subset.

**Secrets** in `.env` (gitignored): `TB_HOST`, `TB_TOKEN`, `NIMBLE_API_KEY`,
`AWS_PROFILE`, `AWS_REGION`.

**Branches:** `madhur/robot` and `faridun/kitchen`. Merge to `main` when
`run.py` runs green on the fixture.

## Order

1. 12:45: fixture `day.jsonl` by hand, both LFM models answering locally.
2. Both halves in parallel against the fixture.
3. 14:00 (was 13:30): planner go/no-go. Given a hand-written perfect board,
   does 1.2B pick the right action at all six checks? Done 14:35: no. The
   1.2B scored at most 3/6 across seven prompt and board variants; the 2.6B,
   the 1.2B Thinking model and LFM2-24B-A2B at most 4/6. Bedrock was ruled out
   to keep the planner on Liquid. The planner is LFM2.5-8B-A1B, 5/6 on a
   clearly worded board. Wording decides a lot: it read "roast... out at
   17:30" as already out, so boards say "take it out at 17:30".
4. 14:15: integrate. Full day, three scorecards, one command.
5. 14:45: viewer plays the day. **Submittable here.** Record a backup video.
6. Tinybird behind the board and the chart; the 14:10 reboot reads from it.
   The right half of the screen polls the four endpoints.
7. FLUX 3 Action on the 17:30 roast step, if BFL gives us a GPU: the planner's
   `take_roast_out` becomes the policy's instruction. Run it once on a GPU
   (BFL's, or an AWS GPU instance, which also makes AWS a sponsor we actually
   use), record its 32-step joint plan and show it beside the camera frames
   it planned from. The released model doesn't decode its video tokens, so
   there is no clip to play. Runbook: `docs/flux3-action.md`. Freeze at 15:30.
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
  before the 14:00 gate.
- **Keys.** Tinybird workspace token, Nimble API key, Bedrock credentials
  (the planner fallback), and Hugging Face access to the FLUX 3 Action
  weights, which are open weights with no API key. Nobody has checked they
  work. Madhur, by 13:00.
- **FLUX 3 Action needs Linux and an NVIDIA GPU.** Its setup doc says so and
  lists an H200; it won't run on either Mac, and there is no hosted API in the
  docs. Ask the BFL table whether they host inference or lend GPUs for the
  Action track, and whether the BFL prize covers all FLUX models or only
  Action. Faridun, now. If BFL can't, an AWS GPU instance (L40S or larger).
  With no GPU at all, show the planner emitting the instruction and say
  plainly that no rollout ran. Checked 14:00: it needs about 32 GB of GPU
  memory, and its only output is joint targets, `(1, 32, 8)`; video tokens
  are sampled but not decoded, so "record the video" is off the table.
- ~~**Tool Use needs three sponsor tools that actually run.**~~ Covered:
  Liquid, Tinybird and Nimble all run from a laptop. FLUX 3 Action on a GPU
  makes four, and running it on an AWS instance makes five. Bedrock still runs
  only if the planner fails at 14:00.
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
