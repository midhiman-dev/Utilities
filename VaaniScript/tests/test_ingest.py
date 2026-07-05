import json
import subprocess
from pathlib import Path

import pytest

from vaaniscript.errors import DECODE_FAILED, UNSUPPORTED_FORMAT, VaaniScriptError
from vaaniscript.ingest.normalize import (
    build_normalize_command,
    build_normalized_output_path,
    normalize_audio,
)
from vaaniscript.ingest.probe import AudioProbe, build_probe_command, probe_audio


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.mark.parametrize("name", ["sample.opus", "sample.mp3", "sample.m4a"])
def test_probe_supports_expected_extensions(name: str) -> None:
    source = Path(name)

    probe = probe_audio(
        source,
        runner=lambda command: _completed(
            stdout=json.dumps({"format": {"duration": "12.5", "format_name": "mock"}})
        ),
    )

    assert probe.source == source
    assert probe.extension == source.suffix
    assert probe.duration_seconds == 12.5
    assert probe.format_name == "mock"


def test_probe_rejects_unsupported_extensions() -> None:
    with pytest.raises(VaaniScriptError) as excinfo:
        probe_audio(Path("sample.wav"))

    assert excinfo.value.code == UNSUPPORTED_FORMAT


def test_probe_wraps_subprocess_failure() -> None:
    with pytest.raises(VaaniScriptError) as excinfo:
        probe_audio(
            Path("broken.opus"),
            runner=lambda command: _completed(returncode=1, stderr="invalid data"),
        )

    assert excinfo.value.code == DECODE_FAILED
    assert excinfo.value.details["stderr"] == "invalid data"


def test_probe_constructs_ffprobe_command() -> None:
    command = build_probe_command(Path("voice.opus"))

    assert command == [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name",
        "-of",
        "json",
        "voice.opus",
    ]


def test_normalize_constructs_ffmpeg_command(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized" / "voice.opus.normalized.wav"
    command = build_normalize_command(Path("voice.opus"), output_path)

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "voice.opus",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-sample_fmt",
        "s16",
        str(output_path),
    ]


def test_normalized_output_path_is_deterministic(tmp_path: Path) -> None:
    output_path = build_normalized_output_path(Path("nested/voice.m4a"), tmp_path)

    assert output_path == tmp_path / "normalized" / "voice.m4a.normalized.wav"


def test_normalize_wraps_subprocess_failure(tmp_path: Path) -> None:
    probe = AudioProbe(
        source=Path("broken.mp3"),
        extension=".mp3",
        duration_seconds=4.2,
        format_name="mp3",
    )

    with pytest.raises(VaaniScriptError) as excinfo:
        normalize_audio(
            probe,
            work_dir=tmp_path,
            runner=lambda command: _completed(returncode=1, stderr="decode failed"),
        )

    assert excinfo.value.code == DECODE_FAILED
    assert excinfo.value.details["stderr"] == "decode failed"
