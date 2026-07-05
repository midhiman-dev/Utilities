"""Pipeline interfaces and Slice S1 ingest orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from typing import Protocol

from .config import Settings
from .errors import DURATION_LIMIT_EXCEEDED, VaaniScriptError
from .ingest import normalize_audio, probe_audio


@dataclass(slots=True)
class PipelineContext:
    source: Path
    settings: Settings


@dataclass(slots=True)
class PipelineResult:
    source: Path
    stage: str
    status: str
    message: str
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "stage": self.stage,
            "status": self.status,
            "message": self.message,
            "code": self.code,
            "details": _serialize_value(self.details),
            "artifacts": {key: str(value) for key, value in self.artifacts.items()},
        }


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialize_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return value


class PipelineStage(Protocol):
    def run(self, context: PipelineContext) -> PipelineResult:
        """Execute a pipeline stage."""


class PlaceholderStage:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: PipelineContext) -> PipelineResult:
        return PipelineResult(
            source=context.source,
            stage=self.name,
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
        self.ingest = IngestStage()
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
            stage="batch",
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
            stage="watch",
            status="placeholder",
            message=(
                "watch is wired as a CLI entry point in Slice S0, but file "
                "watching and persistence are not implemented yet."
            ),
        )


class IngestStage:
    def run(self, context: PipelineContext) -> PipelineResult:
        try:
            probe = probe_audio(context.source)
            self._validate_duration(probe.duration_seconds, context)
            normalized = normalize_audio(probe, work_dir=context.settings.app.workspace_dir)
        except VaaniScriptError as exc:
            return PipelineResult(
                source=context.source,
                stage="ingest",
                status="error",
                message=exc.message,
                code=exc.code,
                details=exc.details,
            )

        return PipelineResult(
            source=context.source,
            stage="ingest",
            status="ready",
            code=None,
            message=(
                "Input validated, probed, and normalized. "
                "ASR and translation are not implemented in Slice S1."
            ),
            details={"probe": probe},
            artifacts={"normalized_wav": normalized.output_path},
        )

    @staticmethod
    def _validate_duration(duration_seconds: float | None, context: PipelineContext) -> None:
        if duration_seconds is None:
            return

        max_duration_seconds = context.settings.pipeline.max_audio_minutes * 60
        if duration_seconds > max_duration_seconds:
            raise VaaniScriptError(
                code=DURATION_LIMIT_EXCEEDED,
                message="Audio duration exceeds the configured limit.",
                source=context.source,
                details={
                    "duration_seconds": duration_seconds,
                    "max_duration_seconds": max_duration_seconds,
                },
            )
