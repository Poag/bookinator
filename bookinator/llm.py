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
    return module.chat_completion(config, config.writing_model, messages, max_tokens=max_tokens)


def call_text_json(config: Config, system: str, user: str, max_tokens: int = 4096):
    text = call_text(config, system, user, max_tokens).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


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
