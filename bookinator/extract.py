from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .llm import call_text_json, require_object_list
from .models import ChapterMeta, ChapterNotes, ChaptersFile, Joke, PlotPoint, Quote, Transcript

SYSTEM_PROMPT = (
    "You are a story editor extracting material from one chapter of a podcast "
    "transcript, to be used later to write a fantasy-novel adaptation of this "
    "chapter. Pull out everything worth preserving: plot-relevant events, "
    "funny moments/jokes/running bits, and notable quotes worth adapting. Be "
    "specific and concrete—favor several small, vivid beats over a few vague "
    "ones. Respond with ONLY JSON, no prose: "
    '{"plot_points": [{"description": str, "timestamp": float|null}], '
    '"jokes": [{"description": str, "quote": str|null, "timestamp": float|null}], '
    '"quotes": [{"speaker": str|null, "text": str, "timestamp": float|null}]}'
)


def _chapter_text(transcript: Transcript, chapter: ChapterMeta) -> str:
    lines = [
        f"[{s.start:.1f}-{s.end:.1f}]" + (f" {s.speaker}:" if s.speaker else "") + f" {s.text}"
        for s in transcript.segments
        if chapter.start <= s.start < chapter.end
    ]
    return "\n".join(lines)


def extract_chapter_notes(chapter: ChapterMeta, transcript: Transcript, config: Config) -> ChapterNotes:
    user = f"Chapter: {chapter.title}\n\nTranscript excerpt:\n\n{_chapter_text(transcript, chapter)}"
    raw = call_text_json(config, SYSTEM_PROMPT, user, max_tokens=4096)
    return ChapterNotes(
        chapter_index=chapter.index,
        plot_points=[PlotPoint(**p) for p in require_object_list(raw.get("plot_points", []), "plot_points")],
        jokes=[Joke(**j) for j in require_object_list(raw.get("jokes", []), "jokes")],
        quotes=[Quote(**q) for q in require_object_list(raw.get("quotes", []), "quotes")],
    )


def extract_project(
    chapters_file_path: Path, transcript_path: Path, chapters_dir: Path, config: Config
) -> list[ChapterNotes]:
    """Stage 4: extract plot points/jokes/quotes per chapter.

    Resumable per-chapter: chapters already present in notes.json are kept
    as-is rather than re-extracted.
    """
    chapters_file = ChaptersFile.model_validate_json(chapters_file_path.read_text())
    transcript = Transcript.model_validate_json(transcript_path.read_text())

    notes_path = chapters_dir / "notes.json"
    cached: dict[int, dict] = {}
    if notes_path.exists():
        cached = {n["chapter_index"]: n for n in json.loads(notes_path.read_text())}

    all_notes: list[ChapterNotes] = []
    for chapter in chapters_file.chapters:
        if chapter.index in cached:
            all_notes.append(ChapterNotes(**cached[chapter.index]))
            continue
        notes = extract_chapter_notes(chapter, transcript, config)
        all_notes.append(notes)
        cached[chapter.index] = notes.model_dump()
        chapters_dir.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(json.dumps(list(cached.values()), indent=2))

    return all_notes
