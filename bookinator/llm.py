from __future__ import annotations

import json
import time

import anthropic

from .config import Config


def _client(config: Config) -> anthropic.Anthropic:
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=config.anthropic_api_key)


def call_claude(config: Config, system: str, user: str, max_tokens: int = 4096) -> str:
    client = _client(config)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            message = client.messages.create(
                model=config.anthropic_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(block.text for block in message.content if block.type == "text")
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"Claude API call failed: {last_error}")


def call_claude_json(config: Config, system: str, user: str, max_tokens: int = 4096):
    text = call_claude(config, system, user, max_tokens).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
