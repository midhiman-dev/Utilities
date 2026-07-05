"""Shared DTOs and JSON serialization for pipeline contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TranscriptionRequest:
    source: Path
    workspace_dir: Path


@dataclass(slots=True)
class SegmentResult:
    start: float
    end: float
    detected_lang: str
    original_text: str
    english_text: str
    confidence: float
    flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VoiceNoteResult:
    file: str
    duration_sec: float | None
    segments: list[SegmentResult] = field(default_factory=list)
    full_english_text: str = ""
    full_original_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass(slots=True)
class PipelineStageResult:
    source: Path
    stage: str
    status: str
    message: str
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)
    voice_note: VoiceNoteResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": serialize_value(self.source),
            "stage": self.stage,
            "status": self.status,
            "message": self.message,
            "code": self.code,
            "details": serialize_value(self.details),
            "artifacts": {key: serialize_value(value) for key, value in self.artifacts.items()},
            "voice_note": serialize_value(self.voice_note),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "__dataclass_fields__"):
        return {key: serialize_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value
