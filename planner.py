"""The planner: a memory's context and the menu in, one action or one recipe lookup out."""

import json
from pathlib import Path

import llm

ACTIONS = json.loads((Path(__file__).parent / "fixtures" / "menu.json").read_text())["actions"]

SYSTEM = (
    "You are a home robot. You have one goal for the day, and you are asked what to do next many "
    "times during it. Choose the one step from the menu that the goal needs now. Use what you "
    "remember: what people told you, what went wrong, and what you already did and when.\n\n"
    "Menu:\n" + "\n".join(f"- {a}" for a in ACTIONS)
)
SEARCH = "\n\nOr, before choosing, you may look up a recipe once: give search_recipe a web search query."

# Ollama writes JSON keys in alphabetical order, whatever order the schema gives. The action is
# asked for as "step" so that "reason" is written first and the model reasons before it chooses.
STEP = {
    "type": "object",
    "properties": {"reason": {"type": "string"}, "step": {"type": "string", "enum": ACTIONS}},
    "required": ["reason", "step"],
}
LOOKUP = {
    "type": "object",
    "properties": {"reason": {"type": "string"}, "search_recipe": {"type": "string"}},
    "required": ["reason", "search_recipe"],
}


def messages(context: list[dict], clock: str, can_search: bool = True) -> list[dict]:
    system = SYSTEM + (SEARCH if can_search else "")
    ask = {"role": "user", "content": f"It is {clock}. What next?"}
    return [{"role": "system", "content": system}, *context, ask]


def decide(context: list[dict], clock: str, can_search: bool = True) -> dict:
    """{"reason", "action"}, or {"reason", "search_recipe"} when can_search."""
    schema = {"anyOf": [STEP, LOOKUP]} if can_search else STEP
    reply = json.loads(llm.chat(llm.PLANNER, messages(context, clock, can_search), schema))
    if "step" in reply:
        reply["action"] = reply.pop("step")
    return reply
