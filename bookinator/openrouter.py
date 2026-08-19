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

    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    return post_chat_completion(OPENROUTER_URL, payload, headers, timeout)
