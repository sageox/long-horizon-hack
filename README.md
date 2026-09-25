# Long Horizon Hack

A web research agent whose working context stops growing while the task keeps going.

Built at the Long Horizon Agents Hackathon, San Francisco, 25 September 2026.

## The problem

Long research runs get expensive and unreliable exactly as they get useful. An
agent that reads 200 pages carries all 200 on every subsequent step, so cost
climbs without limit and the model loses the thread.

## What this does

The agent researches a live question across real pages, choosing its own
queries. Every page it pulls goes to an append-only archive; a small model
decides what earns a one-line note in the working set. When the agent needs a
detail it dropped, it queries the archive, and refetches from the live web if
the archive misses too.

## The claim

Context stays flat while history grows, **and the answer stays correct**. We
measure that against two controls over one captured session:

| Strategy | Context | Expected |
|---|---|---|
| Full history | every page, always | correct, cost explodes |
| Sliding window | last k pages | flat and wrong |
| Working set | filtered notes + archive | flat and correct |

The sliding window is the control that matters: it is flat because it forgets
by position rather than by value, so it proves the filter is doing something
truncation cannot.

## Stack

| Tool | Role |
|---|---|
| AWS Bedrock | runs the agent |
| Nimble | live web search and extraction |
| Liquid AI | the keep-or-drop filter (small model) |
| Tinybird | the archive, and the chart off the same rows |

## Layout

    collect/    live run, caches every response to session.jsonl
    memory/     the three strategies behind one interface
    harness/    replay + grading + event emission
    web/        the chart

## Running it

    cp .env.example .env     # fill in the four keys
    make run                 # live session, cached as it goes
    make replay              # three strategies over the cached session
    make chart               # serve the comparison
