from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .llm import call_claude_json
from .models import CharacterMapping, ChapterNotes, StoryBible

SYSTEM_PROMPT = (
    "You are a fantasy worldbuilder. Given a summary of real plot points, "
    "characters, and running jokes from a podcast, invent a fantasy world and "
    "cast of characters that can carry the same events, relationships, and "
    "humor, retold as a fantasy story. Map every recurring real participant "
    "and recurring topic/bit to a fantasy character, faction, place, or "
    "in-world concept so later chapters can refer to them consistently. "
    "Respond with ONLY JSON, no prose: "
    '{"world_name": str, "setting": str, "tone": str, '
    '"naming_conventions": str, '
    '"characters": [{"real_name": str, "fantasy_name": str, "role": str, '
    '"description": str}], "notes": str}'
)


def _notes_digest(all_notes: list[ChapterNotes]) -> str:
    lines = []
    for notes in all_notes:
        lines.append(f"-- Chapter {notes.chapter_index} --")
        for p in notes.plot_points:
            lines.append(f"PLOT: {p.description}")
        for j in notes.jokes:
            lines.append(f"JOKE: {j.description}" + (f' ("{j.quote}")' if j.quote else ""))
        for q in notes.quotes:
            lines.append(f"QUOTE ({q.speaker or 'Unknown'}): {q.text}")
    return "\n".join(lines)


def build_bible(all_notes: list[ChapterNotes], config: Config) -> StoryBible:
    user = "Extracted material from the whole podcast:\n\n" + _notes_digest(all_notes)
    raw = call_claude_json(config, SYSTEM_PROMPT, user, max_tokens=4096)
    return StoryBible(
        world_name=raw["world_name"],
        setting=raw["setting"],
        tone=raw["tone"],
        naming_conventions=raw["naming_conventions"],
        characters=[CharacterMapping(**c) for c in raw.get("characters", [])],
        notes=raw.get("notes", ""),
    )


def build_bible_for_project(notes_path: Path, bible_path: Path, config: Config) -> StoryBible:
    """Stage 5: build the story bible from all chapters' extracted notes."""
    raw_notes = json.loads(notes_path.read_text())
    all_notes = [ChapterNotes(**n) for n in raw_notes]
    bible = build_bible(all_notes, config)
    bible_path.write_text(bible.model_dump_json(indent=2))
    return bible
