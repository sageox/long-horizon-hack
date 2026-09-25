"""Token counting, the 32K guard, Ollama calls, and the prompt-hash cache."""

import hashlib
import json
from pathlib import Path

import requests
from tokenizers import Tokenizer

PLANNER = "hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M"
CURATOR = "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF"
# The planner's own window is 128K. 32,768 is the robot's budget: checked here, and num_ctx for Ollama.
WINDOW = 32_768
OPTIONS = {"temperature": 0, "seed": 0, "num_ctx": WINDOW}
OLLAMA = "http://localhost:11434/api/chat"
CACHE = Path(__file__).parent / "cache" / "llm.jsonl"

# The 8B planner uses the same tokenizer: counts from this one equal Ollama's for it.
TOKENIZER = Tokenizer.from_pretrained("LiquidAI/LFM2.5-1.2B-Instruct")

_cache = {}
if CACHE.exists():
    for line in CACHE.read_text().splitlines():
        entry = json.loads(line)
        _cache[entry["key"]] = entry["content"]


class ContextOverflow(Exception):
    def __init__(self, tokens: int):
        super().__init__(f"prompt is {tokens:,} tokens, over the {WINDOW:,} window")
        self.tokens = tokens


def render(messages: list[dict]) -> str:
    """The LFM2.5 chat template, as Ollama applies it, for text-only messages without tools."""
    turns = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
    return "<|startoftext|>" + turns + "<|im_start|>assistant\n"


def count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text, add_special_tokens=False))


def chat(model: str, messages: list[dict], schema: dict | None = None) -> str:
    """The model's reply. With a schema, Ollama constrains the reply to JSON that matches it."""
    tokens = count_tokens(render(messages))
    # Ollama truncates an overlong prompt and answers without an error, so the wall is checked here.
    if tokens > WINDOW:
        raise ContextOverflow(tokens)
    body = {"model": model, "messages": messages, "options": OPTIONS, "stream": False}
    if schema:
        body["format"] = schema
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if key not in _cache:
        response = requests.post(OLLAMA, json=body)
        response.raise_for_status()
        _cache[key] = response.json()["message"]["content"]
        CACHE.parent.mkdir(exist_ok=True)
        with CACHE.open("a") as f:
            f.write(json.dumps({"key": key, "model": model, "content": _cache[key]}) + "\n")
    return _cache[key]
