from __future__ import annotations

from .config import Config
from .models import AudioChunk, TranscriptSegment

_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _get_model(config: Config):
    from faster_whisper import WhisperModel  # imported lazily - only needed for the local provider

    key = (config.local_whisper_model, config.local_whisper_device, config.local_whisper_compute_type)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = WhisperModel(
            config.local_whisper_model,
            device=config.local_whisper_device,
            compute_type=config.local_whisper_compute_type,
        )
    return _MODEL_CACHE[key]


def transcribe_chunk_local(chunk: AudioChunk, config: Config) -> list[TranscriptSegment]:
    """Transcribe one audio chunk locally via faster-whisper.

    Whisper does not do speaker diarization, so `speaker` is always None
    here (downstream stages already treat speaker as optional).
    """
    model = _get_model(config)
    segments, _info = model.transcribe(chunk.path, beam_size=5)
    return [
        TranscriptSegment(
            start=chunk.start_offset + seg.start,
            end=chunk.start_offset + seg.end,
            speaker=None,
            text=seg.text.strip(),
        )
        for seg in segments
    ]
