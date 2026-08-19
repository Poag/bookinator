from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from .config import Config
from .models import AudioChunk


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def get_duration_seconds(path: Path, config: Config) -> float:
    output = _run(
        [
            config.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(path),
        ]
    )
    return float(json.loads(output)["format"]["duration"])


def _normalize(input_path: Path, out_dir: Path, config: Config) -> Path:
    normalized_path = out_dir / "normalized.mp3"
    if normalized_path.exists():
        return normalized_path
    _run(
        [
            config.ffmpeg_path,
            "-y",
            "-i", str(input_path),
            "-ac", "1",
            "-ar", "16000",
            str(normalized_path),
        ]
    )
    return normalized_path


def chunk_audio(input_path: Path, out_dir: Path, config: Config) -> list[AudioChunk]:
    """Stage 1: normalize to mono and split into overlapping chunks.

    Resumable: if a chunk manifest already exists, it's returned as-is
    rather than re-running ffmpeg.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "chunks.json"
    if manifest_path.exists():
        return [AudioChunk(**c) for c in json.loads(manifest_path.read_text())]

    normalized_path = _normalize(input_path, out_dir, config)
    duration = get_duration_seconds(normalized_path, config)

    step = config.chunk_minutes * 60
    overlap = config.chunk_overlap_seconds
    num_chunks = max(1, math.ceil(duration / step))

    chunks: list[AudioChunk] = []
    for i in range(num_chunks):
        nominal_start = i * step
        start = max(0.0, nominal_start - overlap) if i > 0 else 0.0
        end = min(duration, nominal_start + step)
        length = end - start
        if length <= 0:
            continue
        chunk_path = out_dir / f"chunk_{i:03d}.mp3"
        _run(
            [
                config.ffmpeg_path,
                "-y",
                "-i", str(normalized_path),
                "-ss", str(start),
                "-t", str(length),
                "-acodec", "libmp3lame",
                "-q:a", "4",
                str(chunk_path),
            ]
        )
        chunks.append(AudioChunk(index=i, path=str(chunk_path), start_offset=start))

    manifest_path.write_text(json.dumps([c.model_dump() for c in chunks], indent=2))
    return chunks
