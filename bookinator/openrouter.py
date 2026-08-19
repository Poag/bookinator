from __future__ import annotations

import time

import requests

from .config import Config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def chat_completion(
    config: Config, model: str, messages: list[dict], max_tokens: int = 4096, timeout: int = 600
) -> str:
    """Call OpenRouter's chat completions endpoint and return the reply text.

    Shared by transcribe.py (audio-capable model, multimodal content) and
    llm.py (text-only models for every other stage) - every LLM call in the
    pipeline goes through this one function and one API key.
    """
    if not config.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"OpenRouter call failed (model={model}): {last_error}")
