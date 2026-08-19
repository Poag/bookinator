from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    chunk_minutes: float = 12
    chunk_overlap_seconds: float = 5
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_api_key: str = ""
    projects_dir: Path = PACKAGE_ROOT / "projects"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load config.toml if present, falling back to built-in defaults.

        A config.toml is optional (handy for a self-contained Docker deploy
        where only the API key env vars need to be supplied). API keys are
        always read from the environment / .env, never from config.toml.
        """
        load_dotenv()
        path = config_path or (PACKAGE_ROOT / "config.toml")
        data: dict = {}
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)

        audio = data.get("audio", {})
        openrouter = data.get("openrouter", {})
        anthropic = data.get("anthropic", {})
        paths = data.get("paths", {})
        defaults = cls()

        return cls(
            ffmpeg_path=audio.get("ffmpeg_path", defaults.ffmpeg_path),
            ffprobe_path=audio.get("ffprobe_path", defaults.ffprobe_path),
            chunk_minutes=float(audio.get("chunk_minutes", defaults.chunk_minutes)),
            chunk_overlap_seconds=float(
                audio.get("chunk_overlap_seconds", defaults.chunk_overlap_seconds)
            ),
            openrouter_model=openrouter.get("model", defaults.openrouter_model),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            anthropic_model=anthropic.get("model", defaults.anthropic_model),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            projects_dir=Path(paths.get("projects_dir", str(defaults.projects_dir))),
        )
