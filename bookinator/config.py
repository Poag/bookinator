from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PACKAGE_ROOT / "config"


@dataclass
class Config:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    chunk_minutes: float = 12
    chunk_overlap_seconds: float = 5

    # Stage 2 (transcription). provider = "openrouter" (cloud, audio-capable
    # multimodal model) or "local" (faster-whisper, runs in-process).
    transcription_provider: str = "openrouter"
    transcription_model: str = "google/gemini-2.5-flash"  # used when provider == "openrouter"
    local_whisper_model: str = "small"  # used when provider == "local"
    local_whisper_device: str = "cpu"
    local_whisper_compute_type: str = "int8"

    openrouter_api_key: str = ""
    projects_dir: Path = PACKAGE_ROOT / "projects"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load config/config.toml if present, falling back to built-in defaults.

        A config.toml is optional (handy for a self-contained Docker deploy
        where only OPENROUTER_API_KEY needs to be supplied) unless you're
        opting into the "local" provider, which is configured entirely in
        config.toml (no secrets involved). It lives in its own config/
        directory so the whole directory can be bind-mounted as one Docker
        volume (see docker-compose.yml).
        """
        load_dotenv()
        path = config_path or (CONFIG_DIR / "config.toml")
        data: dict = {}
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)

        audio = data.get("audio", {})
        transcription = data.get("transcription", {})
        paths = data.get("paths", {})
        defaults = cls()

        transcription_provider = transcription.get("provider", defaults.transcription_provider)
        if transcription_provider == "local":
            transcription_model = transcription.get("local_whisper_model", defaults.local_whisper_model)
        else:
            transcription_model = transcription.get("openrouter_model", defaults.transcription_model)

        return cls(
            ffmpeg_path=audio.get("ffmpeg_path", defaults.ffmpeg_path),
            ffprobe_path=audio.get("ffprobe_path", defaults.ffprobe_path),
            chunk_minutes=float(audio.get("chunk_minutes", defaults.chunk_minutes)),
            chunk_overlap_seconds=float(
                audio.get("chunk_overlap_seconds", defaults.chunk_overlap_seconds)
            ),
            transcription_provider=transcription_provider,
            transcription_model=transcription_model,
            local_whisper_model=transcription.get("local_whisper_model", defaults.local_whisper_model),
            local_whisper_device=transcription.get("local_whisper_device", defaults.local_whisper_device),
            local_whisper_compute_type=transcription.get(
                "local_whisper_compute_type", defaults.local_whisper_compute_type
            ),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            projects_dir=Path(paths.get("projects_dir", str(defaults.projects_dir))),
        )
