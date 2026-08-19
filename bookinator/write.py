from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .llm import call_text
from .models import ChapterMeta, ChapterNotes, ChaptersFile, StoryBible

SYSTEM_PROMPT = (
    "You are a novelist adapting a real conversation into a fantasy novel. "
    "You are given a story bible mapping real people/topics to fantasy "
    "characters/concepts, plus the plot points, jokes, and quotes to hit for "
    "this specific chapter. Write the chapter as polished fantasy prose "
    "(third person, past tense unless the bible says otherwise) that hits "
    "every listed beat—the plot points must happen, the jokes must land in "
    "fantasy form, and the notable quotes should be adapted (not verbatim, "
    "but recognizably preserving what made them funny or striking). Do not "
    "invent major new plot points beyond what's listed. Stay consistent with "
    "prior chapters. Write only the chapter prose, starting with a Markdown "
    "H2 heading for the chapter title—no author notes or preamble."
)


def _bible_block(bible: StoryBible) -> str:
    chars = "\n".join(
        f"- {c.real_name} -> {c.fantasy_name} ({c.role}): {c.description}" for c in bible.characters
    )
    return (
        f"World: {bible.world_name}\nSetting: {bible.setting}\nTone: {bible.tone}\n"
        f"Naming conventions: {bible.naming_conventions}\n\nCharacters:\n{chars}\n\n"
        f"Notes: {bible.notes}"
    )


def _notes_block(notes: ChapterNotes) -> str:
    parts = ["Plot points to include:"]
    parts += [f"- {p.description}" for p in notes.plot_points] or ["(none)"]
    parts.append("\nJokes/funny moments to include:")
    parts += [
        f"- {j.description}" + (f' (original: "{j.quote}")' if j.quote else "") for j in notes.jokes
    ] or ["(none)"]
    parts.append("\nNotable quotes to adapt:")
    parts += [f'- {q.speaker or "?"}: "{q.text}"' for q in notes.quotes] or ["(none)"]
    return "\n".join(parts)


def write_chapter(
    chapter: ChapterMeta,
    notes: ChapterNotes,
    bible: StoryBible,
    prev_chapter_ending: str | None,
    config: Config,
) -> str:
    user = (
        f"STORY BIBLE\n{_bible_block(bible)}\n\n"
        f"CHAPTER {chapter.index + 1}: {chapter.title}\n"
        f"Original summary: {chapter.summary}\n\n"
        f"{_notes_block(notes)}\n"
    )
    if prev_chapter_ending:
        user += f"\nPrevious chapter ended with:\n{prev_chapter_ending}\n"
    return call_text(config, SYSTEM_PROMPT, user, max_tokens=8192)


def _tail(text: str, chars: int = 1200) -> str:
    return text[-chars:]


def write_project(
    chapters_file_path: Path,
    notes_path: Path,
    bible_path: Path,
    drafts_dir: Path,
    config: Config,
) -> list[Path]:
    """Stage 6: write each chapter as fantasy prose via the Claude API.

    Resumable per-chapter: a chapter whose draft file already exists is left
    alone (but still used to seed the "previous chapter" continuity context).
    """
    chapters_file = ChaptersFile.model_validate_json(chapters_file_path.read_text())
    raw_notes = json.loads(notes_path.read_text())
    notes_by_index = {n["chapter_index"]: ChapterNotes(**n) for n in raw_notes}
    bible = StoryBible.model_validate_json(bible_path.read_text())

    drafts_dir.mkdir(parents=True, exist_ok=True)
    prev_ending: str | None = None
    paths: list[Path] = []
    for chapter in chapters_file.chapters:
        out_path = drafts_dir / f"chapter_{chapter.index + 1:02d}.md"
        if out_path.exists():
            prev_ending = _tail(out_path.read_text())
            paths.append(out_path)
            continue
        notes = notes_by_index[chapter.index]
        prose = write_chapter(chapter, notes, bible, prev_ending, config)
        out_path.write_text(prose)
        prev_ending = _tail(prose)
        paths.append(out_path)
    return paths
