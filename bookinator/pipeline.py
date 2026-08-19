from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .audio import chunk_audio
from .config import Config
from .models import AudioChunk
from .transcribe import transcribe_project

STAGES = ["chunk", "transcribe"]

STAGE_LABELS = {
    "chunk": "1. Chunk & normalize audio",
    "transcribe": "2. Transcribe",
}


@dataclass
class ProjectPaths:
    name: str
    base: Path
    raw: Path
    transcript: Path
    audio_chunks: Path

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

    raise ValueError(f"Unknown stage: {stage}")


def run_all(config: Config, name: str) -> list[str]:
    return [run_stage(config, name, stage) for stage in STAGES]
