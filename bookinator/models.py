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
