from __future__ import annotations

from pathlib import Path

from .config import Config
from .llm import call_text_json
from .models import ChapterMeta, ChaptersFile, Transcript

SYSTEM_PROMPT = (
    "You are an editor breaking a podcast transcript into natural chapters "
    "for a book adaptation. Propose chapter breaks at topic changes, not at "
    "fixed intervals. Respond with ONLY a JSON array, no prose. Each element: "
    '{"title": "<short chapter title>", "summary": "<one-line summary>", '
    '"start": <seconds, float, matching a segment start time in the transcript>, '
    '"end": <seconds, float>}. Chapters must be contiguous and cover the full '
    "transcript from its first segment's start to its last segment's end."
)


def build_chapters(transcript: Transcript, config: Config) -> ChaptersFile:
    user = "Transcript (each line is [start-end] speaker: text):\n\n" + transcript.full_text
    raw = call_text_json(config, SYSTEM_PROMPT, user, max_tokens=4096)
    chapters = [
        ChapterMeta(index=i, title=c["title"], summary=c["summary"], start=c["start"], end=c["end"])
        for i, c in enumerate(raw)
    ]
    return ChaptersFile(chapters=chapters)


def chapterize_project(transcript_path: Path, chapters_dir: Path, config: Config) -> ChaptersFile:
    """Stage 3: segment the merged transcript into chapters."""
    transcript = Transcript.model_validate_json(transcript_path.read_text())
    chapters_file = build_chapters(transcript, config)
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "chapters.json").write_text(chapters_file.model_dump_json(indent=2))
    return chapters_file
