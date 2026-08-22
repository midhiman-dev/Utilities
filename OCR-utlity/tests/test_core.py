from pathlib import Path

from ocr_utility.core import collect_images


def test_collect_images_accepts_a_supported_file(tmp_path: Path) -> None:
    image = tmp_path / "photo.PNG"
    image.touch()

    assert collect_images(image) == [image]


def test_collect_images_ignores_unsupported_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "zebra.jpg").touch()
    (tmp_path / "Alpha.PNG").touch()
    (tmp_path / "notes.pdf").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "hidden.png").touch()

    assert [path.name for path in collect_images(tmp_path)] == ["Alpha.PNG", "zebra.jpg"]

