from __future__ import annotations

from pydantic import BaseModel, Field


class AudioChunk(BaseModel):
    index: int
    path: str
    start_offset: float  # seconds into the full (normalized) recording


class TranscriptSegment(BaseModel):
    start: float
    end: float
    speaker: str | None = None
    text: str


class Transcript(BaseModel):
    project: str
    segments: list[TranscriptSegment] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        lines = []
        for s in self.segments:
            speaker = f" {s.speaker}:" if s.speaker else ""
            lines.append(f"[{s.start:.1f}-{s.end:.1f}]{speaker} {s.text}")
        return "\n".join(lines)


class ChapterMeta(BaseModel):
    index: int
    title: str
    summary: str
    start: float
    end: float


class ChaptersFile(BaseModel):
    chapters: list[ChapterMeta] = Field(default_factory=list)


class PlotPoint(BaseModel):
    description: str
    timestamp: float | None = None


class Joke(BaseModel):
    description: str
    quote: str | None = None
    timestamp: float | None = None


class Quote(BaseModel):
    speaker: str | None = None
    text: str
    timestamp: float | None = None


class ChapterNotes(BaseModel):
    chapter_index: int
    plot_points: list[PlotPoint] = Field(default_factory=list)
    jokes: list[Joke] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)


class CharacterMapping(BaseModel):
    real_name: str
    fantasy_name: str
    role: str
    description: str


class StoryBible(BaseModel):
    world_name: str
    setting: str
    tone: str
    naming_conventions: str
    characters: list[CharacterMapping] = Field(default_factory=list)
    notes: str = ""
