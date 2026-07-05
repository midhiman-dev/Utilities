import json
import subprocess
from pathlib import Path

from vaaniscript.config import Settings
from vaaniscript.pipeline import VaaniPipeline


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_pipeline_probes_before_normalize(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"
    calls: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "9.5", "format_name": "ogg"}}')
        if command[0] == "ffmpeg":
            return _completed()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    settings = Settings(app={"workspace_dir": str(tmp_path / "work")})
    result = VaaniPipeline(settings).transcribe(source)

    assert result.status == "ready"
    assert result.stage == "ingest"
    assert [command[0] for command in calls] == ["ffprobe", "ffmpeg"]
    assert result.artifacts["normalized_wav"] == tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"


def test_pipeline_surfaces_probe_failure(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "broken.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return _completed(returncode=1, stderr="not decodable")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)

    result = VaaniPipeline(Settings()).transcribe(source)

    assert result.status == "error"
    assert result.stage == "ingest"
    assert result.code == "decode_failed"
    assert result.details["stderr"] == "not decodable"


def test_pipeline_surfaces_unsupported_format(tmp_path: Path) -> None:
    result = VaaniPipeline(Settings()).transcribe(tmp_path / "voice.wav")

    assert result.status == "error"
    assert result.code == "unsupported_format"


def test_pipeline_result_is_json_serializable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.mp3"

    def fake_probe(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "5.0", "format_name": "mp3"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_probe)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_probe)

    result = VaaniPipeline(Settings(app={"workspace_dir": str(tmp_path / "work")})).transcribe(source)
    payload = result.to_dict()

    assert payload["details"]["probe"]["extension"] == ".mp3"
    assert json.loads(json.dumps(payload))["stage"] == "ingest"
