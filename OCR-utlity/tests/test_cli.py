from pathlib import Path

from ocr_utility import cli


def _ready_cli(monkeypatch) -> None:
    monkeypatch.setattr(cli, "check_tesseract_available", lambda: None)


def test_single_image_writes_requested_output(tmp_path: Path, monkeypatch, capsys) -> None:
    source = tmp_path / "receipt.png"
    source.touch()
    target = tmp_path / "results" / "receipt.txt"
    _ready_cli(monkeypatch)
    monkeypatch.setattr(cli, "ocr_image", lambda image, language: "total: 10\n")

    exit_code = cli.main([str(source), "--output", str(target)])

    assert exit_code == 0
    assert target.read_text(encoding="utf-8") == "total: 10\n"
    assert "Saved:" in capsys.readouterr().out


def test_folder_combine_skips_failed_image_and_returns_partial_failure(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "first.png").touch()
    (tmp_path / "second.png").touch()
    target = tmp_path / "combined.txt"
    _ready_cli(monkeypatch)

    def fake_ocr(image: Path, language: str) -> str:
        if image.name == "second.png":
            raise cli.ImageOcrError("bad image")
        return "first text"

    monkeypatch.setattr(cli, "ocr_image", fake_ocr)

    exit_code = cli.main([str(tmp_path), "--combine", "--output", str(target)])

    assert exit_code == 2
    assert target.read_text(encoding="utf-8") == "--- first.png ---\nfirst text\n"


def test_list_languages_needs_no_input(tmp_path: Path, monkeypatch, capsys) -> None:
    _ready_cli(monkeypatch)
    monkeypatch.setattr(cli, "installed_languages", lambda: ["eng", "hin"])

    assert cli.main(["--list-langs"]) == 0
    assert "eng" in capsys.readouterr().out

