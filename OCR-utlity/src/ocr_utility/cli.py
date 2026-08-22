"""Command-line interface for local image OCR."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import (
    ImageOcrError,
    TesseractUnavailableError,
    check_tesseract_available,
    collect_images,
    configure_tesseract,
    installed_languages,
    ocr_image,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-utility",
        description="Extract text from images locally with Tesseract OCR.",
    )
    parser.add_argument("input", nargs="?", help="An image file or a folder of images.")
    parser.add_argument("-o", "--output", help="Output .txt file, or output directory for folder mode.")
    parser.add_argument("--combine", action="store_true", help="Combine a folder's OCR output into one file.")
    parser.add_argument("--lang", default="eng", help="Tesseract language(s), such as eng or eng+hin.")
    parser.add_argument("--list-langs", action="store_true", help="List installed language packs and exit.")
    parser.add_argument(
        "--tesseract-cmd",
        default=os.environ.get("OCR_TESSERACT_CMD"),
        help="Tesseract executable path; defaults to the OCR_TESSERACT_CMD environment variable.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text, creating the output parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ocr_one(image_path: Path, language: str) -> str | None:
    try:
        return ocr_image(image_path, language)
    except ImageOcrError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)
    configure_tesseract(args.tesseract_cmd)

    try:
        check_tesseract_available()
    except TesseractUnavailableError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.list_langs:
        print("Installed language packs:")
        for language in installed_languages():
            print(f"  {language}")
        return 0

    if not args.input:
        build_parser().error("input is required unless --list-langs is used")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: path not found: {input_path}", file=sys.stderr)
        return 1

    images = collect_images(input_path)
    if not images:
        print(f"Error: no supported images found at: {input_path}", file=sys.stderr)
        return 1

    if input_path.is_file():
        text = _ocr_one(input_path, args.lang)
        if text is None:
            return 2
        if args.output:
            output_path = Path(args.output)
            write_text(output_path, text)
            print(f"Saved: {output_path}")
        else:
            print(text, end="" if text.endswith("\n") else "\n")
        return 0

    failures = 0
    if args.combine:
        sections: list[str] = []
        for image_path in images:
            text = _ocr_one(image_path, args.lang)
            if text is None:
                failures += 1
                continue
            sections.append(f"--- {image_path.name} ---\n{text.rstrip()}\n")
        result = "\n".join(sections)
        if args.output:
            output_path = Path(args.output)
            write_text(output_path, result)
            print(f"Saved combined text ({len(images) - failures}/{len(images)} images): {output_path}")
        else:
            print(result, end="" if result.endswith("\n") else "\n")
    else:
        output_dir = Path(args.output) if args.output else input_path
        output_dir.mkdir(parents=True, exist_ok=True)
        for image_path in images:
            text = _ocr_one(image_path, args.lang)
            if text is None:
                failures += 1
                continue
            output_file = output_dir / f"{image_path.stem}.txt"
            write_text(output_file, text)
            print(f"OCR'd: {image_path.name} -> {output_file}")

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

