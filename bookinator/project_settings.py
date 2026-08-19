from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class StageOverride(BaseModel):
    # None means "inherit from the global config.toml default" for that field.
    provider: str | None = None
    model: str | None = None


class ProjectSettings(BaseModel):
    transcription: StageOverride = StageOverride()
    chapterize: StageOverride = StageOverride()
    extract: StageOverride = StageOverride()
    bible: StageOverride = StageOverride()
    write: StageOverride = StageOverride()
    continuity: StageOverride = StageOverride()


# Provider choices offered per role in the settings UI. "transcription" is
# the only role that can go local (faster-whisper); the rest are text/LLM
# stages that can go openrouter or ollama.
ROLE_PROVIDERS: dict[str, list[str]] = {
    "transcription": ["openrouter", "local"],
    "chapterize": ["openrouter", "ollama"],
    "extract": ["openrouter", "ollama"],
    "bible": ["openrouter", "ollama"],
    "write": ["openrouter", "ollama"],
    "continuity": ["openrouter", "ollama"],
}

ROLE_LABELS: dict[str, str] = {
    "transcription": "Transcription (stage 2)",
    "chapterize": "Chapter segmentation (stage 3)",
    "extract": "Extraction (stage 4)",
    "bible": "Story bible (stage 5)",
    "write": "Prose writing (stage 6)",
    "continuity": "Continuity pass (stage 7)",
}


def settings_path(project_base: Path) -> Path:
    return project_base / "settings.json"


def load_project_settings(project_base: Path) -> ProjectSettings:
    path = settings_path(project_base)
    if not path.exists():
        return ProjectSettings()
    return ProjectSettings.model_validate_json(path.read_text())


def save_project_settings(project_base: Path, settings: ProjectSettings) -> None:
    project_base.mkdir(parents=True, exist_ok=True)
    settings_path(project_base).write_text(settings.model_dump_json(indent=2))
