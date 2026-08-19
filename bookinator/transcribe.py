from __future__ import annotations

import base64
import json
from pathlib import Path

from .config import Config
from .models import AudioChunk, Transcript, TranscriptSegment
from .openrouter import chat_completion

SYSTEM_PROMPT = (
    "You are a precise audio transcriptionist. Transcribe the provided audio "
    "verbatim, preserving speaker turns where you can distinguish speakers. "
    "Do not summarize, clean up disfluencies, or omit anything that was said, "
    "including jokes, asides, and interruptions.\n\n"
    "Respond with ONLY a JSON array of segments, no prose before or after. "
    "Each segment is an object: "
    '{"start": <seconds from the start of this audio clip, float>, '
    '"end": <seconds, float>, "speaker": "<speaker label or null>", '
    '"text": "<verbatim text>"}. '
    "Break into segments roughly every time the speaker changes or every "
    "10-30 seconds of continuous speech, whichever comes first. Estimate "
    "start/end times as best you can from pacing; approximate is fine."
)


def _audio_format(path: Path) -> str:
    return path.suffix.lstrip(".").lower() or "mp3"


def _parse_segments(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # Fallback: the model didn't return valid JSON. Keep the raw response as
    # a single untimed segment so nothing is lost; inspect/fix by hand later.
    return [{"start": 0.0, "end": 0.0, "speaker": None, "text": content.strip()}]


def transcribe_chunk(chunk: AudioChunk, config: Config, cache_dir: Path) -> list[TranscriptSegment]:
    cache_path = cache_dir / f"chunk_{chunk.index:03d}.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text())
        return [TranscriptSegment(**s) for s in data]

    audio_bytes = Path(chunk.path).read_bytes()
    b64 = base64.b64encode(audio_bytes).decode("ascii")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": b64,
                        "format": _audio_format(Path(chunk.path)),
                    },
                }
            ],
        },
    ]
    content = chat_completion(config, config.transcription_model, messages, max_tokens=8192)
    raw_segments = _parse_segments(content)

    segments = [
        TranscriptSegment(
            start=chunk.start_offset + s["start"],
            end=chunk.start_offset + s["end"],
            speaker=s.get("speaker"),
            text=s["text"],
        )
        for s in raw_segments
    ]

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps([s.model_dump() for s in segments], indent=2))
    return segments


def transcribe_project(
    chunks: list[AudioChunk], config: Config, transcript_dir: Path, project: str
) -> Transcript:
    """Stage 2: transcribe each audio chunk via OpenRouter and merge in order.

    Per-chunk results are cached to disk so a failed/retried run doesn't
    re-pay for chunks that already transcribed successfully.
    """
    cache_dir = transcript_dir / "chunks"
    all_segments: list[TranscriptSegment] = []
    for chunk in chunks:
        all_segments.extend(transcribe_chunk(chunk, config, cache_dir))

    all_segments.sort(key=lambda s: s.start)
    transcript = Transcript(project=project, segments=all_segments)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / "transcript.json").write_text(transcript.model_dump_json(indent=2))
    return transcript
