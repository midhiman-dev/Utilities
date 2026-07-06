from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class AudioChunk:
    path: Path
    start_sec: float = 0.0
    end_sec: float | None = None
    flags: list[str] = field(default_factory=list)


class VadProcessor(Protocol):
    def detect_speech_chunks(self, normalized_wav: Path) -> list[AudioChunk]:
        """Return ordered speech chunks derived from a normalized WAV path."""


class NoOpVadProcessor:
    """Default runtime stub until real VAD/chunking is configured."""

    def detect_speech_chunks(self, normalized_wav: Path) -> list[AudioChunk]:
        return [AudioChunk(path=normalized_wav)]


@dataclass(slots=True)
class FakeVadProcessor:
    chunks: list[AudioChunk] = field(default_factory=list)
    calls: list[Path] = field(default_factory=list)

    def detect_speech_chunks(self, normalized_wav: Path) -> list[AudioChunk]:
        self.calls.append(normalized_wav)
        return list(self.chunks)
