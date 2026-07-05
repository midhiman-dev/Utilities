"""ffmpeg-backed normalization wrappers for ingest."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..errors import DECODE_FAILED, VaaniScriptError
from .probe import AudioProbe, run_command

FFMPEG_BINARY = "ffmpeg"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(slots=True)
class NormalizedAudio:
    source: Path
    probe: AudioProbe
    output_path: Path


def build_normalized_output_path(source: Path, work_dir: Path) -> Path:
    file_token = source.suffix.lower().removeprefix(".") or "audio"
    output_name = f"{source.stem}.{file_token}.normalized.wav"
    return work_dir / "normalized" / output_name


def build_normalize_command(
    source: Path,
    output_path: Path,
    ffmpeg_binary: str = FFMPEG_BINARY,
) -> list[str]:
    return [
        ffmpeg_binary,
        "-y",
        "-i",
        str(source),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-sample_fmt",
        "s16",
        str(output_path),
    ]


def normalize_audio(
    probe: AudioProbe,
    *,
    work_dir: Path,
    runner: CommandRunner | None = None,
    ffmpeg_binary: str = FFMPEG_BINARY,
) -> NormalizedAudio:
    runner = runner or run_command
    output_path = build_normalized_output_path(probe.source, work_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = build_normalize_command(probe.source, output_path, ffmpeg_binary=ffmpeg_binary)
    completed = runner(command)
    if completed.returncode != 0:
        raise VaaniScriptError(
            code=DECODE_FAILED,
            message="Audio normalization failed.",
            source=probe.source,
            details={"stderr": completed.stderr.strip(), "command": command},
        )

    return NormalizedAudio(source=probe.source, probe=probe, output_path=output_path)
