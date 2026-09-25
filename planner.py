"""The planner: a memory's context and the menu in, one action or one recipe lookup out."""

import json

import llm
from kitchen import ACTIONS

SYSTEM = (
    "You are a home robot. You have one goal for the day, and you are asked what to do next many "
    "times during it. Choose the one step from the menu that the goal needs now. Use what you "
    "remember: what people told you, what went wrong, and what you already did and when.\n\n"
    "Menu:\n" + "\n".join(f"- {a}" for a in ACTIONS)
)
SEARCH = "\n\nOr, before choosing, you may look up a recipe once: give search_recipe a web search query."
FIELDS = (
    "\n\nAnswer in JSON. asked: what someone most recently asked you to do, or nothing. "
    "due: anything on your board whose time has come by now, or nothing. "
    "facts: what you remember that changes how to do the next step. "
    "reason: why this step is the one the goal needs now. step: one step from the menu."
)

# Ollama writes JSON keys in alphabetical order, whatever order the schema gives. asked, due, facts
# and reason sort before search_recipe and step, so the model fills them in before it chooses.
NOTES = {k: {"type": "string"} for k in ("asked", "due", "facts", "reason")}
STEP = {
    "type": "object",
    "properties": {**NOTES, "step": {"type": "string", "enum": ACTIONS}},
    "required": [*NOTES, "step"],
}
LOOKUP = {
    "type": "object",
    "properties": {**NOTES, "search_recipe": {"type": "string"}},
    "required": [*NOTES, "search_recipe"],
}


def messages(context: list[dict], clock: str, can_search: bool = True) -> list[dict]:
    system = SYSTEM + (SEARCH if can_search else "") + FIELDS
    ask = {"role": "user", "content": f"It is {clock}. What next?"}
    return [{"role": "system", "content": system}, *context, ask]


def decide(context: list[dict], clock: str, can_search: bool = True) -> dict:
    """{"reason", "action"}, or {"reason", "search_recipe"} when can_search, plus asked, due and facts."""
    schema = {"anyOf": [STEP, LOOKUP]} if can_search else STEP
    reply = json.loads(llm.chat(llm.PLANNER, messages(context, clock, can_search), schema))
    if "step" in reply:
        reply["action"] = reply.pop("step")
    return reply
