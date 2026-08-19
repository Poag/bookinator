from __future__ import annotations

import json

from . import ollama, openrouter
from .config import Config


def _provider_module(provider: str):
    if provider == "ollama":
        return ollama
    if provider == "openrouter":
        return openrouter
    raise ValueError(f"Unknown writing_provider: {provider!r}")


def call_text(config: Config, system: str, user: str, max_tokens: int = 4096) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    module = _provider_module(config.writing_provider)
    # Reasoning-capable models (e.g. Claude Sonnet 5) default to extended
    # thinking on via OpenRouter, and thinking tokens count against this
    # same max_tokens budget - for our structured-output and prose tasks
    # that just burns the budget on invisible reasoning before any real
    # content comes out (seen as either null content or output truncated
    # after a handful of characters). None of these prompts need visible
    # chain-of-thought, so turn it off. Scoped to text calls only -
    # transcribe.py's audio calls don't pass this, since Gemini's
    # audio-input path rejected it with a 400.
    return module.chat_completion(
        config,
        config.writing_model,
        messages,
        max_tokens=max_tokens,
        extra={"reasoning": {"enabled": False}},
    )


def call_text_json(config: Config, system: str, user: str, max_tokens: int = 4096, attempts: int = 3):
    """Call the model and parse its reply as JSON, retrying on malformed output.

    Models occasionally return JSON that doesn't parse - truncated mid
    string, a stray comment, etc. A fresh completion often comes back
    clean on retry, so this resamples a few times before giving up. If
    every attempt fails, the raised error includes a preview of the last
    raw response so the failure is diagnosable instead of just a bare
    JSONDecodeError with no context about what the model actually sent.
    """
    last_error: json.JSONDecodeError | None = None
    last_text = ""
    for _ in range(attempts):
        text = call_text(config, system, user, max_tokens).strip()
        last_text = text
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            last_error = exc

    preview = last_text[:500] + ("..." if len(last_text) > 500 else "")
    raise ValueError(
        f"Model did not return valid JSON after {attempts} attempt(s): {last_error}\n\n"
        f"Last response:\n{preview}"
    )


def require_object_list(value, field_name: str) -> list[dict]:
    """Validate that a parsed-JSON field is a list of JSON objects.

    Callers build pydantic models from each item with **item - a model
    that didn't follow the requested schema (e.g. returned a list of
    arrays instead of objects) would otherwise fail deep inside a list
    comprehension with an opaque "argument after ** must be a mapping"
    TypeError. This raises a clear, actionable error naming the field and
    the actual value the model returned instead.
    """
    if not isinstance(value, list):
        raise ValueError(f"expected {field_name!r} to be a JSON array, got {type(value).__name__}: {value!r}")
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(
                f"expected every item in {field_name!r} to be a JSON object, but found a "
                f"{type(item).__name__} instead: {item!r}"
            )
    return value
