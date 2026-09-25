# Plan

Two people, roughly four hours. The split works because both halves meet at one
file and neither needs the other to exist first.

## The contract: `session.jsonl`

One JSON object per line, one line per page the agent pulled. **Agree this now
and nothing else needs coordinating.**

```json
{"step": 12,
 "url": "https://example.com/some-page",
 "topic": "some-page",
 "query": "what the agent searched to find it",
 "title": "Page title",
 "body": "full extracted text",
 "fetched_at": "2026-09-25T11:40:12Z",
 "tokens": 2140}
```

`topic` is the stable key `recall()` looks up later. `url` is what makes a live
refetch possible, so carry it from the first Nimble response even though nothing
reads it until C.

## Split

**Faridun — collect.** The live agent. Nimble search and extract, agent picks
its own next query, writes `session.jsonl` as responses land. Deliverable: a
file with 100+ real lines.

**Madhur — replay.** The three memory strategies behind one interface, the
grading, the event rows. Works against a **hand-written 20-line
`session.jsonl`** until the real one exists. Deliverable: three scores and three
token totals from one command.

Neither of you waits. Swap the fixture for the real file when collect lands.

## The interface

```python
class Memory:
    def observe(self, page: dict) -> None: ...   # one session.jsonl line
    def context(self) -> list[dict]: ...         # messages for the next turn
```

Three implementations: `FullHistory`, `SlidingWindow(k)`, `WorkingSet`.
About twenty lines each.

## Order

1. Fixture `session.jsonl` by hand, 20 lines. Five minutes, unblocks everything.
2. Both halves in parallel against it.
3. Integrate: real collect output into the replay harness.
4. Chart from the JSONL. **Submittable here.**
5. Tinybird behind the chart.
6. C: `recall()` tool and `evict()`.
7. Rehearse the three minutes twice. Submit at 16:15.

## Rules for today

Write JSONL to stdout first, Tinybird second. If ingest fights us we still have
a result and a chart.

Cache every Nimble response as it arrives. A live run is the flakiest part of
the demo and the stage is the worst place to find that out.

Grade with string matching against a known answer. No LLM judge.

Branch for real work, both of us. `main` stays green so either of us can demo
from it at any moment.
