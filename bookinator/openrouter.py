from __future__ import annotations

from .config import Config
from .http_utils import post_chat_completion

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def chat_completion(
    config: Config, model: str, messages: list[dict], max_tokens: int = 4096, timeout: int = 600
) -> str:
    """Call OpenRouter's chat completions endpoint and return the reply text.

    Used for whichever role (transcription/writing) has its provider set to
    "openrouter" in config.
    """
    if not config.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        # Reasoning-capable models (e.g. Claude Sonnet 5) default to
        # extended thinking on via OpenRouter, and thinking tokens count
        # against this same max_tokens budget - for our structured-output
        # and prose tasks that just burns the budget on invisible
        # reasoning before any real content comes out (seen as either
        # null content or output truncated after a handful of
        # characters). None of our prompts need visible chain-of-thought,
        # so turn it off.
        "reasoning": {"enabled": False},
    }
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    return post_chat_completion(OPENROUTER_URL, payload, headers, timeout)
