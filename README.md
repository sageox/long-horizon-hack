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
Tinybird. A small Liquid model decides which events become memories. Each
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
| Liquid AI | LFM2.5-1.2B plans; LFM2.5-350M curates memory; both local |
| Tinybird | the task board, memories and event log; the chart off the same rows |
| Black Forest Labs | FLUX images of the kitchen and the 18:00 tables |

## Layout

    world/      the kitchen: task graph, events, checks → day.jsonl
    memory/     the three strategies behind one interface
    robot/      curator and planner
    harness/    runs the day per strategy, grades, emits events
    web/        the viewer

## Running it

    cp .env.example .env     # fill in the keys
    make run                 # the day, three strategies, cached as it goes
    make chart               # serve the viewer
