"""Structured errors for VaaniScript pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


UNSUPPORTED_FORMAT = "unsupported_format"
DECODE_FAILED = "decode_failed"
DURATION_LIMIT_EXCEEDED = "duration_limit_exceeded"
NO_SPEECH_DETECTED = "no_speech_detected"


@dataclass(slots=True)
class VaaniScriptError(Exception):
    """A controlled, serializable application error."""

    code: str
    message: str
    source: Path | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
