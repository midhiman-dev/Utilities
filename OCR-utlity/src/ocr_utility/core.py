"""Tesseract integration and image discovery for the OCR CLI."""

from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp"})


class OcrError(Exception):
    """Base exception for a failed OCR operation."""


class TesseractUnavailableError(OcrError):
    """Raised when the Tesseract executable cannot be started."""


class ImageOcrError(OcrError):
    """Raised when one image cannot be decoded or recognized."""


def configure_tesseract(command: str | None) -> None:
    """Configure the Tesseract executable path when explicitly supplied."""
    if command:
        pytesseract.pytesseract.tesseract_cmd = command


def check_tesseract_available() -> None:
    """Verify that the configured Tesseract command can be started."""
    try:
        pytesseract.get_tesseract_version()
    except (pytesseract.TesseractNotFoundError, OSError) as exc:
        raise TesseractUnavailableError(
            "Tesseract OCR engine was not found. Install it and add it to PATH, "
            "or pass --tesseract-cmd with the executable path."
        ) from exc


def installed_languages() -> list[str]:
    """Return the available Tesseract language identifiers."""
    return sorted(pytesseract.get_languages(config=""))


def collect_images(input_path: Path) -> list[Path]:
    """Return one image or the supported direct children of a directory."""
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if input_path.is_dir():
        return sorted(
            (item for item in input_path.iterdir() if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS),
            key=lambda item: item.name.lower(),
        )
    return []


def ocr_image(image_path: Path, language: str) -> str:
    """Extract text from one image, preserving the source image unchanged."""
    try:
        with Image.open(image_path) as image:
            return pytesseract.image_to_string(image, lang=language)
    except UnidentifiedImageError as exc:
        raise ImageOcrError(f"Not a readable image: {image_path}") from exc
    except (OSError, pytesseract.TesseractError) as exc:
        raise ImageOcrError(f"OCR failed for {image_path}: {exc}") from exc

