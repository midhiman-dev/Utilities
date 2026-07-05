"""Pipeline interfaces and placeholder orchestration for Slice S0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .config import Settings


@dataclass(slots=True)
class PipelineContext:
    source: Path
    settings: Settings


@dataclass(slots=True)
class PipelineResult:
    source: Path
    status: str
    message: str
    artifacts: dict[str, Path] = field(default_factory=dict)


class PipelineStage(Protocol):
    def run(self, context: PipelineContext) -> PipelineResult:
        """Execute a pipeline stage."""


class PlaceholderStage:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: PipelineContext) -> PipelineResult:
        return PipelineResult(
            source=context.source,
            status="placeholder",
            message=(
                f"{self.name} is not implemented in Slice S0. "
                "This scaffold reserves the ingest -> VAD/denoise -> ASR -> "
                "language detection -> translation -> storage/export flow."
            ),
        )


class VaaniPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ingest = PlaceholderStage("ingest")
        self.audio = PlaceholderStage("audio")
        self.asr = PlaceholderStage("asr")
        self.lang = PlaceholderStage("lang")
        self.translate = PlaceholderStage("translate")
        self.storage = PlaceholderStage("storage")

    def transcribe(self, source: Path) -> PipelineResult:
        context = PipelineContext(source=source, settings=self.settings)
        return self.ingest.run(context)

    def batch(self, source_dir: Path) -> PipelineResult:
        context = PipelineContext(source=source_dir, settings=self.settings)
        return PipelineResult(
            source=source_dir,
            status="placeholder",
            message=(
                "batch is wired as a CLI entry point in Slice S0, but folder "
                "processing will arrive in a later slice."
            ),
        )

    def watch(self, source_dir: Path) -> PipelineResult:
        context = PipelineContext(source=source_dir, settings=self.settings)
        return PipelineResult(
            source=source_dir,
            status="placeholder",
            message=(
                "watch is wired as a CLI entry point in Slice S0, but file "
                "watching and persistence are not implemented yet."
            ),
        )
