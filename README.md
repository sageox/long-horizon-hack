# Long Horizon Hack

A home robot that cooks dinner over a ten-hour day on a 32K-token on-device
model, and still gets it on the table.

Built at the Long Horizon Agents Hackathon, San Francisco, 25 September 2026.

## The problem

A chat agent can start a new conversation. A robot can't. It is switched on in
the morning and every step until evening is one session. Carry everything and
the context fills the device's window by mid-afternoon; keep only the recent
past and the robot forgets the roast it put in the oven three hours ago.

## What this does

At 08:00 the robot gets one goal: dinner for the family at 18:00. About 40
dependent steps, with interruptions: a guest turns out to be vegan, the dryer
breaks, another guest is added, the power cuts out with the roast in the oven.

The robot keeps a task board and a small set of memories outside the model, in
RawTree, the hackathon's Tinybird offering. A small Liquid model decides which
events become memories. Each
decision gets a fresh prompt built from the goal, the board, the memories and
the last few events, inside a fixed budget.

## The claim

Same model, same day, same budget: only the robot with persistent state and
curated memory gets dinner right. We measure it against two controls:

| Strategy | Context | Expected at 18:00 |
|---|---|---|
| Full history | every event, always | hits 32K at 14:51 and stops planning |
| Sliding window | last 4K tokens | forgets the roast, the vegan guest, the salt |
| Task board | board + memories, 4K | all six checks pass |

The sliding window is the control that matters: it has the same budget as the
task board, so the difference is what gets kept, not how much.

## Stack

| Tool | Role |
|---|---|
| Liquid AI | LFM2.5-8B-A1B plans every action (8B parameters, about 1B active per token); LFM2.5-1.2B curates memories and writes the rolling summary. Both local, through Ollama |
| Tinybird (RawTree) | the task board and the event log; the 14:10 reboot reads the board back, and the dashboard queries the same rows |
| Black Forest Labs | FLUX.2 draws each robot's 18:00 table from its own actions (`tables.py`) |
| Nimble | recipe lookup at 13:00; what the robot searches for depends on what it remembered |

## Layout

    kitchen.py   the day, the menu, grading, the recipe lookup
    llm.py       token counting, the 32K guard, Ollama calls, the prompt-hash cache
    planner.py   one action, or one recipe lookup, per ask
    memory.py    full history, sliding window, rolling summary, task board and its curator
    run.py       every robot over the day: events.jsonl, asks.jsonl, a scorecard each
    rawtree.py   rows into RawTree, the board back out, a finished run streamed live
    dash.py      serves the viewer and the dashboard's RawTree queries
    tables.py    FLUX.2 pictures of each robot's table
    viewer/      the kitchen viewer, the dashboard, the Three.js replay

## Running it

    ollama pull hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M
    ollama pull hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF
    uv run run.py --day fixtures/day.jsonl --run demo   # calls in cache/llm.jsonl replay
    uv run dash.py                                       # the viewer and dashboard on :8000
    uv run rawtree.py runs/demo/events.jsonl             # stream the run into RawTree

Keys go in `.env`: `RAWTREE_API_KEY` for the board and the dashboard,
`NIMBLE_API_KEY` for live recipe search (without it the lookup answers from
`fixtures/web_cache.json`), `BFL_API_KEY` for `tables.py`.

## Three.js demo

The interactive kitchen reads the Python runner's `runs/<run>/events.jsonl`
directly. Start the viewer:

```bash
cd viewer
npm ci
npm run dev
```

Open [localhost:8000/viewer/three.html](http://localhost:8000/viewer/three.html).
Requires Node.js/npm, Python 3.12+, and a browser with WebGL2. Three.js is the
only frontend dependency; it is served locally, with no build step or CDN.

The viewer discovers backend runs and opens the newest non-mock run. Choose
another run from the selector. **Follow backend** follows new events as
`run.py` writes them; scrubbing or playing switches to replay while continuing
to load new rows. In-progress runs cannot be scrubbed beyond their last event.
The server reads complete lines only, so an event being written is never shown
partly. This is a read-only connection: the viewer does not start model calls.

Start the Python harness separately in the backend checkout:

```bash
uv run run.py --day fixtures/day.jsonl --run demo
```

If the backend is in another worktree, point the viewer at its runs directory:

```bash
npm run dev -- --runs-dir /path/to/backend/worktree/runs
```

For parallel `amsterdam` and `dallas` worktrees, use
`--runs-dir ../../dallas/runs` from `amsterdam/viewer/`.
No backend files are copied or modified. After the branches are combined,
the default repository `runs/` directory works without that argument.

Startup also generates `runs/mock/events.jsonl` using `mock_run.py`, available
only by choosing **Illustrative demo (mock)** or providing its URL. This is an
**illustrative replay with scripted outcomes**, visibly labeled, not measured
model results. It is never selected automatically when backend data is absent.
The 3D room and movement are a reconstruction; decisions, context counts,
board snapshots, and scores come from the selected log. The scene uses the
shared dinner script for fixed staging such as putting the roast in the oven.

Select a memory strategy, play or scrub the day, jump to an interruption,
inspect the robot's memories and activity, or open the six-check scorecard.
Drag the kitchen to orbit; scroll to zoom. Space plays/pauses, the arrow keys
skip ten minutes, `1`/`2`/`4` change speed, and `R` restarts. The timeline and
other controls also work with the keyboard.

Use **Load run**, drop an `events.jsonl`, or point at a backend replay:

```
/viewer/three.html?events=../runs/<run>/events.jsonl&at=14:00&robot=task_board
```

`autoplay=1` starts playback; `live=1` follows updates to the specified URL.
The demo shows only strategies found in the log,
including `rolling_summary` when present. The original event viewer and
Tinybird dashboard remain available from the navigation. Run the replay and server tests
with `npm test` in `viewer/`.
