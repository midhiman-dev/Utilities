from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .vad import AudioChunk


class DenoiseProcessor(Protocol):
    def denoise_chunks(self, chunks: list[AudioChunk]) -> list[AudioChunk]:
        """Return ordered denoised chunks for downstream ASR."""


class NoOpDenoiseProcessor:
    """Default runtime stub until real denoise is configured."""

    def denoise_chunks(self, chunks: list[AudioChunk]) -> list[AudioChunk]:
        return list(chunks)


@dataclass(slots=True)
class FakeDenoiseProcessor:
    output_chunks: list[AudioChunk] | None = None
    calls: list[list[AudioChunk]] = field(default_factory=list)

    def denoise_chunks(self, chunks: list[AudioChunk]) -> list[AudioChunk]:
        self.calls.append(list(chunks))
        if self.output_chunks is None:
            return list(chunks)
        return list(self.output_chunks)
