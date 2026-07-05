"""Pipeline interfaces and Slice S1 ingest orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .asr import AsrEngine, NoOpAsrEngine
from .config import Settings
from .contracts import PipelineStageResult, SegmentResult, TranscriptionRequest, VoiceNoteResult
from .errors import DURATION_LIMIT_EXCEEDED, VaaniScriptError
from .ingest import normalize_audio, probe_audio


@dataclass(slots=True)
class PipelineContext:
    request: TranscriptionRequest
    settings: Settings


PipelineResult = PipelineStageResult


class PipelineStage(Protocol):
    def run(self, context: PipelineContext) -> PipelineResult:
        """Execute a pipeline stage."""


class PlaceholderStage:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: PipelineContext) -> PipelineResult:
        return PipelineResult(
            source=context.request.source,
            stage=self.name,
            status="placeholder",
            message=(
                f"{self.name} is not implemented in Slice S0. "
                "This scaffold reserves the ingest -> VAD/denoise -> ASR -> "
                "language detection -> translation -> storage/export flow."
            ),
        )


class VaaniPipeline:
    def __init__(self, settings: Settings, *, asr_engine: AsrEngine | None = None) -> None:
        self.settings = settings
        self.asr_engine = asr_engine or NoOpAsrEngine()
        self.ingest = IngestStage()
        self.audio = PlaceholderStage("audio")
        self.asr = PlaceholderStage("asr")
        self.lang = PlaceholderStage("lang")
        self.translate = PlaceholderStage("translate")
        self.storage = PlaceholderStage("storage")

    def transcribe(self, source: Path) -> PipelineResult:
        context = PipelineContext(
            request=TranscriptionRequest(source=source, workspace_dir=self.settings.app.workspace_dir),
            settings=self.settings,
        )
        ingest_result = self.ingest.run(context)
        if ingest_result.status != "ready":
            return ingest_result

        normalized_wav = ingest_result.artifacts["normalized_wav"]
        asr_output = self.asr_engine.transcribe(normalized_wav)
        voice_note = ingest_result.voice_note or VoiceNoteResult(file=source.name, duration_sec=None)
        voice_note.segments = list(asr_output.segments)
        voice_note.full_original_text = self._merge_original_text(voice_note.segments)

        return PipelineResult(
            source=ingest_result.source,
            stage=ingest_result.stage,
            status=ingest_result.status,
            message=(
                "Input validated, probed, normalized, and passed through the ASR adapter boundary. "
                "Translation is not implemented in Slice S4."
            ),
            code=ingest_result.code,
            details={
                **ingest_result.details,
                "asr": {
                    "detected_language": asr_output.detected_language,
                    "segment_count": len(asr_output.segments),
                },
            },
            artifacts=ingest_result.artifacts,
            voice_note=voice_note,
        )

    def batch(self, source_dir: Path) -> PipelineResult:
        context = PipelineContext(
            request=TranscriptionRequest(source=source_dir, workspace_dir=self.settings.app.workspace_dir),
            settings=self.settings,
        )
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
        context = PipelineContext(
            request=TranscriptionRequest(source=source_dir, workspace_dir=self.settings.app.workspace_dir),
            settings=self.settings,
        )
        return PipelineResult(
            source=source_dir,
            stage="watch",
            status="placeholder",
            message=(
                "watch is wired as a CLI entry point in Slice S0, but file "
                "watching and persistence are not implemented yet."
            ),
        )

    @staticmethod
    def _merge_original_text(segments: list[SegmentResult]) -> str:
        return " ".join(segment.original_text for segment in segments if segment.original_text).strip()


class IngestStage:
    def run(self, context: PipelineContext) -> PipelineResult:
        try:
            probe = probe_audio(context.request.source)
            self._validate_duration(probe.duration_seconds, context)
            normalized = normalize_audio(probe, work_dir=context.request.workspace_dir)
        except VaaniScriptError as exc:
            return PipelineResult(
                source=context.request.source,
                stage="ingest",
                status="error",
                message=exc.message,
                code=exc.code,
                details=exc.details,
                voice_note=VoiceNoteResult(
                    file=context.request.source.name,
                    duration_sec=None,
                ),
            )

        return PipelineResult(
            source=context.request.source,
            stage="ingest",
            status="ready",
            code=None,
            message=(
                "Input validated, probed, and normalized. "
                "ASR and translation are not implemented in Slice S1."
            ),
            details={"probe": probe},
            artifacts={"normalized_wav": normalized.output_path},
            voice_note=VoiceNoteResult(
                file=context.request.source.name,
                duration_sec=probe.duration_seconds,
            ),
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
                source=context.request.source,
                details={
                    "duration_seconds": duration_seconds,
                    "max_duration_seconds": max_duration_seconds,
                },
            )
