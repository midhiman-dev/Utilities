"""ASR engine abstractions and adapters."""

from .whisper_engine import (
    AsrEngine,
    AsrOutput,
    AsrSegmentQuality,
    FakeAsrEngine,
    FasterWhisperEngine,
    NoOpAsrEngine,
)

__all__ = [
    "AsrEngine",
    "AsrOutput",
    "AsrSegmentQuality",
    "FakeAsrEngine",
    "FasterWhisperEngine",
    "NoOpAsrEngine",
]
