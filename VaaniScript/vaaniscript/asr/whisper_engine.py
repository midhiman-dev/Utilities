"""ASR engine boundary and faster-whisper adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from ..contracts import SegmentResult

LANGUAGE_SCOPE = {"hi", "bn"}


@dataclass(slots=True)
class AsrOutput:
    segments: list[SegmentResult] = field(default_factory=list)
    detected_language: str | None = None
    segment_qualities: list["AsrSegmentQuality"] = field(default_factory=list)


@dataclass(slots=True)
class AsrSegmentQuality:
    avg_logprob: float | None = None
    no_speech_prob: float | None = None


class AsrEngine(Protocol):
    def transcribe(self, audio_path: Path) -> AsrOutput:
        """Transcribe a normalized WAV file into stable segment DTOs."""


@dataclass(slots=True)
class FakeAsrEngine:
    output: AsrOutput = field(default_factory=AsrOutput)
    outputs: list[AsrOutput] = field(default_factory=list)
    calls: list[Path] = field(default_factory=list)

    def transcribe(self, audio_path: Path) -> AsrOutput:
        self.calls.append(audio_path)
        if self.outputs:
            return self.outputs.pop(0)
        return self.output


class NoOpAsrEngine:
    """Default local stub used until real ASR execution is enabled."""

    def transcribe(self, audio_path: Path) -> AsrOutput:
        return AsrOutput(segments=[], detected_language=None)


class FasterWhisperEngine:
    def __init__(self, model_size: str = "small", *, compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self._model: Any | None = None

    def transcribe(self, audio_path: Path) -> AsrOutput:
        model = self._get_model()
        segments, info = model.transcribe(
            str(audio_path),
            language=None,
            condition_on_previous_text=False,
            vad_filter=False,
        )

        detected_language = getattr(info, "language", None)
        scoped_language = detected_language if detected_language in LANGUAGE_SCOPE else None
        mapped_segments = [
            self._map_segment(segment, default_language=scoped_language) for segment in segments
        ]
        segment_qualities = [self._map_segment_quality(segment) for segment in segments]
        return AsrOutput(
            segments=mapped_segments,
            detected_language=scoped_language,
            segment_qualities=segment_qualities,
        )

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        module = import_module("faster_whisper")
        whisper_model = getattr(module, "WhisperModel")
        self._model = whisper_model(self.model_size, compute_type=self.compute_type)
        return self._model

    @staticmethod
    def _map_segment(segment: Any, *, default_language: str | None) -> SegmentResult:
        avg_logprob = getattr(segment, "avg_logprob", None)
        confidence = _logprob_to_confidence(avg_logprob)
        segment_language = default_language if default_language in LANGUAGE_SCOPE else "unknown"
        return SegmentResult(
            start=float(getattr(segment, "start", 0.0)),
            end=float(getattr(segment, "end", 0.0)),
            detected_lang=segment_language,
            original_text=str(getattr(segment, "text", "")).strip(),
            english_text="",
            confidence=confidence,
            flags=[],
        )

    @staticmethod
    def _map_segment_quality(segment: Any) -> AsrSegmentQuality:
        avg_logprob = getattr(segment, "avg_logprob", None)
        no_speech_prob = getattr(segment, "no_speech_prob", None)
        return AsrSegmentQuality(
            avg_logprob=float(avg_logprob) if avg_logprob is not None else None,
            no_speech_prob=float(no_speech_prob) if no_speech_prob is not None else None,
        )


def _logprob_to_confidence(avg_logprob: float | None) -> float:
    if avg_logprob is None:
        return 0.0
    if avg_logprob >= 0:
        return 1.0
    confidence = 1.0 + (float(avg_logprob) / 5.0)
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)
