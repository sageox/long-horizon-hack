"""Each robot's dinner table at 18:00, drawn by FLUX.2 from what it actually did.

    uv run tables.py runs/<run>/events.jsonl          # writes runs/<run>/tables/<robot>.jpg
    uv run tables.py runs/<run>/events.jsonl --dry    # prints the prompts, calls nothing

The table comes from the robot's own action lines plus the fixed script, the
same state the viewer's kitchen chips show, so a picture never shows a dish
the robot didn't make. Every robot gets the same scene and seed, so the
pictures differ only where the robots did. An image is drawn once per table:
it is kept while its prompt is unchanged. tables.json records each prompt,
state and cost next to the images. Needs BFL_API_KEY in the environment or .env.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

import kitchen

MODEL = "flux-2-pro"
API = f"https://api.bfl.ai/v1/{MODEL}"
SEED, WIDTH, HEIGHT = 1800, 1024, 768
SCENE = (
    "Photograph of a family dining table at six in the evening, seen from a standing "
    "adult's eye height, warm lamp light, an English home dining room with a sideboard "
    "and a vase of paper flowers. No people. Realistic, natural colours, 35mm."
)


def table(rows: list[dict]) -> dict:
    """What is on one robot's table at 18:00: its actions, over what the script already did."""
    s = {"crumble": "in the oven", "cloth": "on the bathroom line", "places": 0,
         "stew": None, "salted": 1, "served": False, "roast": "in the oven", "salad": True}
    for r in rows:
        if r.get("kind") != "action":
            continue
        a = r.get("action")
        if a == "take_crumble_out":
            s["crumble"] = "out"
        elif a == "take_roast_out":
            s["roast"] = "out"
        elif a in ("stew_with_oil", "stew_with_butter"):
            s["stew"] = "olive oil" if a == "stew_with_oil" else "butter"
        elif a == "add_salt":
            s["salted"] += 1
        elif a == "serve_stew":
            s["served"] = True
        elif a == "get_cloth_from_bathroom_line":
            s["cloth"] = "on the table"
        elif a == "get_cloth_from_dryer":
            s["cloth"] = "not found"
        elif a in ("set_table_for_6", "set_table_for_7"):
            s["places"] = int(a[-1])
    return s


def prompt(s: dict) -> str:
    parts = [SCENE]
    parts.append("A white linen tablecloth covers the table." if s["cloth"] == "on the table"
                 else "The table is bare wood with no tablecloth.")
    words = {6: "six", 7: "seven"}
    n = s["places"]
    parts.append(f"Exactly {words.get(n, n)} ({n}) place settings, evenly spaced around the table, each with a "
                 f"white plate, knife, fork and glass, and exactly {words.get(n, n)} chairs." if n
                 else "No places are set: no plates, cutlery or glasses.")
    dishes = []
    if s["roast"] == "out":
        dishes.append("a golden roast chicken on a platter in the middle")
    if s["stew"] and s["served"]:
        dishes.append("a pot of tomato, chickpea and spinach vegetable stew" if s["stew"] == "olive oil"
                      else "a pot of creamy vegetable stew made with butter and cream")
    if s["salad"]:
        dishes.append("a bowl of green salad")
    if s["crumble"] == "out":
        dishes.append("an apple crumble with a rough golden oat topping, no pastry, in a baking dish")
    parts.append("On the table: " + ", ".join(dishes) + ".")
    if s["roast"] != "out":
        parts.append("Through the doorway, thin smoke drifts from the closed kitchen oven.")
    return " ".join(parts)


def draw(text: str, key: str, timeout: float = 120) -> tuple[bytes, float | None]:
    """One FLUX.2 image: submit, poll until Ready, download the signed URL at once."""
    headers = {"x-key": key, "Content-Type": "application/json", "accept": "application/json"}
    body = {"prompt": text, "width": WIDTH, "height": HEIGHT, "seed": SEED,
            "output_format": "jpeg", "disable_pup": True}
    job = requests.post(API, headers=headers, json=body, timeout=30)
    job.raise_for_status()
    job = job.json()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.8)
        poll = requests.get(job["polling_url"], headers=headers, timeout=30)
        poll.raise_for_status()
        result = poll.json()
        status = result.get("status")
        if status == "Ready":
            image = requests.get(result["result"]["sample"], timeout=60)
            image.raise_for_status()
            return image.content, job.get("cost")
        if status not in ("Pending", "Queued", "Processing", "Task not found"):
            raise RuntimeError(f"FLUX.2 {status}: {json.dumps(result)[:300]}")
    raise TimeoutError(f"FLUX.2 not ready after {timeout:.0f}s")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("events", help="runs/<run>/events.jsonl")
    p.add_argument("--dry", action="store_true", help="print the prompts, call nothing")
    p.add_argument("--robots", help="comma-separated subset")
    args = p.parse_args()

    events = Path(args.events)
    rows = [json.loads(line) for line in events.read_text().splitlines() if line.strip()]
    robots = list(dict.fromkeys(r["robot"] for r in rows))
    if args.robots:
        robots = [r for r in robots if r in args.robots.split(",")]
    out = events.parent / "tables"
    manifest_path = out / "tables.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    mock = any(r.get("mock") for r in rows)
    key = None if args.dry else kitchen._secret("BFL_API_KEY")
    if not args.dry and not key:
        sys.exit("tables.py: BFL_API_KEY is not set in the environment or .env")

    for robot in robots:
        s = table([r for r in rows if r["robot"] == robot])
        text = prompt(s)
        digest = hashlib.sha256(f"{MODEL}|{SEED}|{WIDTH}x{HEIGHT}|{text}".encode()).hexdigest()[:16]
        image = out / f"{robot}.jpg"
        if args.dry:
            print(f"{robot}: {json.dumps(s)}\n  {text}\n")
            continue
        if image.exists() and manifest.get(robot, {}).get("digest") == digest:
            print(f"{robot}: kept {image}")
            continue
        out.mkdir(parents=True, exist_ok=True)
        data, cost = draw(text, key)
        image.write_bytes(data)
        manifest[robot] = {"digest": digest, "model": MODEL, "seed": SEED, "state": s,
                           "prompt": text, "cost": cost, "mock": mock,
                           "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"{robot}: drew {image} ({len(data) // 1024} KB, cost {cost})")


if __name__ == "__main__":
    main()
