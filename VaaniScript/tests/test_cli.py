import json
from pathlib import Path

from typer.testing import CliRunner

from vaaniscript.cli import app
from vaaniscript.config import Settings
from vaaniscript.pipeline import VaaniPipeline


runner = CliRunner()


def test_help_starts() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.stdout
    assert "transcribe" in result.stdout
    assert "watch" in result.stdout


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_transcribe_reports_structured_ingest_result(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_build_pipeline() -> VaaniPipeline:
        class FakePipeline:
            def transcribe(self, input_source: Path):
                assert Path(input_source) == source
                return VaaniPipeline(Settings()).transcribe(tmp_path / "voice.wav")

        return FakePipeline()  # type: ignore[return-value]

    monkeypatch.setattr("vaaniscript.cli.build_pipeline", fake_build_pipeline)

    result = runner.invoke(app, ["transcribe", str(source)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["stage"] == "ingest"
    assert payload["status"] == "error"
    assert payload["code"] == "unsupported_format"
