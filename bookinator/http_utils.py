from __future__ import annotations

import time

import requests


def post_chat_completion(
    url: str, payload: dict, headers: dict | None = None, timeout: int = 600
) -> str:
    """POST an OpenAI-compatible chat completion request, with retries.

    Shared by openrouter.py and ollama.py - both providers speak the same
    request/response shape, so only the URL/headers/model differ.
    """
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            resp = requests.post(url, headers=headers or {}, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"Chat completion call failed (url={url}): {last_error}")
