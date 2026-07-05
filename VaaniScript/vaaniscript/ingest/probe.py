"""Safe audio probing wrappers for supported input formats."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..errors import DECODE_FAILED, UNSUPPORTED_FORMAT, VaaniScriptError

SUPPORTED_EXTENSIONS = {".opus", ".mp3", ".m4a"}
FFPROBE_BINARY = "ffprobe"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(slots=True)
class AudioProbe:
    source: Path
    extension: str
    duration_seconds: float | None
    format_name: str | None


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess for ingest operations."""

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def _validate_extension(source: Path) -> str:
    extension = source.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise VaaniScriptError(
            code=UNSUPPORTED_FORMAT,
            message=f"Unsupported audio format: {extension or '<none>'}",
            source=source,
            details={"supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
        )
    return extension


def build_probe_command(source: Path, ffprobe_binary: str = FFPROBE_BINARY) -> list[str]:
    return [
        ffprobe_binary,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name",
        "-of",
        "json",
        str(source),
    ]


def probe_audio(
    source: Path,
    *,
    runner: CommandRunner | None = None,
    ffprobe_binary: str = FFPROBE_BINARY,
) -> AudioProbe:
    extension = _validate_extension(source)
    runner = runner or run_command
    command = build_probe_command(source, ffprobe_binary=ffprobe_binary)
    completed = runner(command)

    if completed.returncode != 0:
        raise VaaniScriptError(
            code=DECODE_FAILED,
            message="Audio probe failed.",
            source=source,
            details={"stderr": completed.stderr.strip(), "command": command},
        )

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VaaniScriptError(
            code=DECODE_FAILED,
            message="Audio probe returned invalid metadata.",
            source=source,
            details={"stdout": completed.stdout, "command": command},
        ) from exc

    format_data = payload.get("format") or {}
    duration_raw = format_data.get("duration")
    try:
        duration_seconds = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise VaaniScriptError(
            code=DECODE_FAILED,
            message="Audio probe returned an invalid duration.",
            source=source,
            details={"duration": duration_raw, "command": command},
        ) from exc

    return AudioProbe(
        source=source,
        extension=extension,
        duration_seconds=duration_seconds,
        format_name=format_data.get("format_name"),
    )
