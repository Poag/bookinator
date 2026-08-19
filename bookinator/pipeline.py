from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .audio import chunk_audio
from .assemble import assemble_manuscript
from .bible import build_bible_for_project
from .chapters import chapterize_project
from .config import Config
from .continuity import run_continuity_pass
from .extract import extract_project
from .models import AudioChunk
from .transcribe import transcribe_project
from .write import write_project

STAGES = ["chunk", "transcribe", "chapterize", "extract", "bible", "write", "continuity", "assemble"]

STAGE_LABELS = {
    "chunk": "1. Chunk & normalize audio",
    "transcribe": "2. Transcribe (OpenRouter)",
    "chapterize": "3. Segment into chapters",
    "extract": "4. Extract plot points / jokes / quotes",
    "bible": "5. Build story bible",
    "write": "6. Write fantasy prose (OpenRouter)",
    "continuity": "7. Continuity pass",
    "assemble": "8. Assemble manuscript",
}


@dataclass
class ProjectPaths:
    name: str
    base: Path
    raw: Path
    transcript: Path
    audio_chunks: Path
    chapters: Path
    bible: Path
    drafts: Path
    manuscript: Path
    continuity_report: Path

    @classmethod
    def for_project(cls, config: Config, name: str) -> "ProjectPaths":
        base = config.projects_dir / name
        transcript = base / "transcript"
        return cls(
            name=name,
            base=base,
            raw=base / "raw",
            transcript=transcript,
            audio_chunks=transcript / "audio_chunks",
            chapters=base / "chapters",
            bible=base / "bible.json",
            drafts=base / "drafts",
            manuscript=base / "manuscript.md",
            continuity_report=base / "continuity_report.md",
        )


def list_projects(config: Config) -> list[str]:
    if not config.projects_dir.exists():
        return []
    return sorted(p.name for p in config.projects_dir.iterdir() if p.is_dir())


def create_project(config: Config, name: str, mp3_source: Path, mp3_filename: str) -> ProjectPaths:
    if not name or any(c in name for c in "/\\.."):
        raise ValueError("Invalid project name")
    paths = ProjectPaths.for_project(config, name)
    paths.raw.mkdir(parents=True, exist_ok=True)
    dest = paths.raw / mp3_filename
    shutil.copy2(mp3_source, dest)
    return paths


def find_source_mp3(paths: ProjectPaths) -> Path | None:
    if not paths.raw.exists():
        return None
    mp3s = sorted(paths.raw.glob("*.mp3"))
    return mp3s[0] if mp3s else None


def stage_status(paths: ProjectPaths) -> dict[str, bool]:
    return {
        "chunk": (paths.audio_chunks / "chunks.json").exists(),
        "transcribe": (paths.transcript / "transcript.json").exists(),
        "chapterize": (paths.chapters / "chapters.json").exists(),
        "extract": (paths.chapters / "notes.json").exists(),
        "bible": paths.bible.exists(),
        "write": paths.drafts.exists() and any(paths.drafts.glob("chapter_*.md")),
        "continuity": paths.continuity_report.exists(),
        "assemble": paths.manuscript.exists(),
    }


def run_stage(config: Config, name: str, stage: str) -> str:
    """Run a single named stage for a project, returning a short result message."""
    paths = ProjectPaths.for_project(config, name)

    if stage == "chunk":
        mp3 = find_source_mp3(paths)
        if mp3 is None:
            raise RuntimeError("No source mp3 found in this project's raw/ folder")
        chunks = chunk_audio(mp3, paths.audio_chunks, config)
        return f"Created {len(chunks)} audio chunks"

    if stage == "transcribe":
        manifest = paths.audio_chunks / "chunks.json"
        if not manifest.exists():
            raise RuntimeError("Run the chunk stage first")
        chunks = [AudioChunk(**c) for c in json.loads(manifest.read_text())]
        transcript = transcribe_project(chunks, config, paths.transcript, name)
        return f"Transcribed {len(transcript.segments)} segments"

    if stage == "chapterize":
        chapters_file = chapterize_project(paths.transcript / "transcript.json", paths.chapters, config)
        return f"Found {len(chapters_file.chapters)} chapters"

    if stage == "extract":
        notes = extract_project(
            paths.chapters / "chapters.json", paths.transcript / "transcript.json", paths.chapters, config
        )
        return f"Extracted notes for {len(notes)} chapters"

    if stage == "bible":
        bible = build_bible_for_project(paths.chapters / "notes.json", paths.bible, config)
        return f"Built story bible for '{bible.world_name}'"

    if stage == "write":
        drafts = write_project(
            paths.chapters / "chapters.json", paths.chapters / "notes.json", paths.bible, paths.drafts, config
        )
        return f"Wrote {len(drafts)} chapter drafts"

    if stage == "continuity":
        result = run_continuity_pass(paths.chapters / "chapters.json", paths.bible, paths.drafts, config)
        return f"{len(result.get('fixes', []))} chapters revised for continuity"

    if stage == "assemble":
        out = assemble_manuscript(paths.chapters / "chapters.json", paths.drafts, name, paths.manuscript)
        return f"Assembled manuscript at {out}"

    raise ValueError(f"Unknown stage: {stage}")


def run_all(config: Config, name: str) -> list[str]:
    return [run_stage(config, name, stage) for stage in STAGES]
