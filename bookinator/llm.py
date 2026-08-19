from __future__ import annotations

import json

from .config import Config
from .openrouter import chat_completion


def call_text(config: Config, system: str, user: str, max_tokens: int = 4096) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return chat_completion(config, config.writing_model, messages, max_tokens=max_tokens)


def call_text_json(config: Config, system: str, user: str, max_tokens: int = 4096):
    text = call_text(config, system, user, max_tokens).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
