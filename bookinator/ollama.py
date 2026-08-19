from __future__ import annotations

from .config import Config
from .http_utils import post_chat_completion


def chat_completion(
    config: Config, model: str, messages: list[dict], max_tokens: int = 4096, timeout: int = 600
) -> str:
    """Call a self-hosted Ollama server's OpenAI-compatible endpoint.

    Used for the writing role when writing_provider = "ollama". No API key
    is required; Ollama has no auth by default.
    """
    url = f"{config.ollama_base_url.rstrip('/')}/v1/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    return post_chat_completion(url, payload, timeout=timeout)
