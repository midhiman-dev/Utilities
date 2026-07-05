from typer.testing import CliRunner

from vaaniscript.cli import app


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
