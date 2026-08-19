from __future__ import annotations

import time

import requests


def post_chat_completion(
    url: str, payload: dict, headers: dict | None = None, timeout: int = 600
) -> str:
    """POST an OpenAI-compatible chat completion request, with retries.

    Used by openrouter.py for transcription.
    """
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            resp = requests.post(url, headers=headers or {}, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
            continue

        if not resp.ok:
            # requests' own HTTPError message discards the response body,
            # which is exactly where OpenRouter puts the actual reason
            # ({"error": {...}}) - include it so the failure is
            # diagnosable instead of a bare "400 Client Error".
            error = RuntimeError(f"{resp.status_code} {resp.reason}: {resp.text[:1000]}")
            last_error = error
            # A 4xx other than 429 (rate limit) means the request itself
            # is malformed/rejected - retrying the identical payload would
            # just fail the same way again, so fail fast instead of
            # burning ~14s of backoff on a request that can't succeed.
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise error
            if attempt < 3:
                time.sleep(2**attempt)
            continue

        try:
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"].get("content")
            finish_reason = choice.get("finish_reason")
            if not content or finish_reason == "length":
                # Some providers return HTTP 200 with a null/empty content
                # string instead of raising - e.g. the model ran out of
                # max_tokens before producing a final answer, or was
                # filtered/refused. A non-empty but "length"-truncated
                # response is just as unusable (and, for JSON-shaped
                # replies, invalid) - treat both as a failure worth
                # retrying rather than silently returning cut-off content.
                raise RuntimeError(
                    f"incomplete response (finish_reason={finish_reason!r}, "
                    f"content_length={len(content or '')}) - the model likely "
                    "ran out of max_tokens"
                )
            return content
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)

    raise RuntimeError(f"Chat completion call failed (url={url}): {last_error}")
