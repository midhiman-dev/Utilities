#!/usr/bin/env python3
"""
xlsx_to_csv.py - Convert every worksheet in an Excel file to its own CSV.

Usage:
    python xlsx_to_csv.py <file.xlsx>
    python xlsx_to_csv.py --tui
    python xlsx_to_csv.py

Output:
    A folder named after the input file (for example, Inventory/ for
    Inventory.xlsx) containing one UTF-8 CSV per worksheet.

Requirements:
    pip install pandas openpyxl
"""

from __future__ import annotations

import csv
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit(
        "Missing dependency: pandas\n"
        "Run: pip install pandas openpyxl"
    )

try:
    import openpyxl  # noqa: F401 (required pandas Excel engine)
except ImportError:
    sys.exit(
        "Missing dependency: openpyxl\n"
        "Run: pip install openpyxl"
    )


SUPPORTED_EXTENSIONS = (".xlsx", ".xlsm", ".xltx", ".xltm")


@dataclass
class SheetExportResult:
    sheet_name: str
    file_name: str
    rows: int
    columns: int


@dataclass
class ConversionResult:
    source_path: str
    output_dir: str
    total_sheets: int
    exported_sheets: list[SheetExportResult]
    errors: list[tuple[str, str]]


class ConversionError(Exception):
    """Raised when the workbook cannot be converted."""


def sanitise_filename(name: str) -> str:
    """Replace characters that are illegal in filenames on any major OS."""
    illegal = r'\/:*?"<>|'
    for ch in illegal:
        name = name.replace(ch, "_")
    return name.strip() or "sheet"


def resolve_output_path(output_dir: str, base_name: str) -> str:
    """Return a unique CSV path, appending _2, _3, etc. if needed."""
    candidate = os.path.join(output_dir, f"{base_name}.csv")
    if not os.path.exists(candidate):
        return candidate

    counter = 2
    while True:
        candidate = os.path.join(output_dir, f"{base_name}_{counter}.csv")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def fail(message: str) -> None:
    raise ConversionError(message)


def validate_input(xlsx_path: str) -> str:
    """Validate and normalize the provided workbook path."""
    normalized = os.path.abspath(os.path.expanduser(xlsx_path.strip().strip('"')))
    if not normalized:
        fail("No workbook path was provided.")

    if not os.path.exists(normalized):
        fail(f"File not found: {normalized}")

    if not os.path.isfile(normalized):
        fail(f"Expected a file but received: {normalized}")

    if not os.access(normalized, os.R_OK):
        fail(f"Permission denied (cannot read): {normalized}")

    if not normalized.lower().endswith(SUPPORTED_EXTENSIONS):
        fail(
            f"Unsupported file type: {normalized}\n"
            "This tool accepts .xlsx, .xlsm, .xltx, and .xltm files only."
        )

    return normalized


def read_workbook(xlsx_path: str) -> dict[str, pd.DataFrame]:
    """Load every worksheet from the workbook."""
    try:
        sheets = pd.read_excel(
            xlsx_path,
            sheet_name=None,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
        )
    except Exception as exc:  # pragma: no cover - depends on workbook state
        die_with_hint(exc, xlsx_path)

    if not sheets:
        fail("The workbook contains no sheets.")

    return sheets


def convert(xlsx_path: str, logger=print) -> ConversionResult:
    """Convert all worksheets in a workbook into CSV files."""
    source_path = validate_input(xlsx_path)
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    output_dir = os.path.join(os.path.dirname(source_path), base_name)

    logger("")
    logger(f"[READ] {source_path}")
    sheets = read_workbook(source_path)

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        fail(f"Cannot create output folder '{output_dir}': {exc}")

    logger(f"[OUT ] {output_dir}")
    logger(f"[INFO] Sheets found: {len(sheets)}")
    logger("")

    exported: list[SheetExportResult] = []
    errors: list[tuple[str, str]] = []
    pad = len(str(len(sheets)))

    for idx, (sheet_name, df) in enumerate(sheets.items(), start=1):
        safe_name = sanitise_filename(sheet_name)
        csv_path = resolve_output_path(output_dir, safe_name)
        label = f"[{idx:{pad}d}/{len(sheets)}]"

        try:
            df.to_csv(
                csv_path,
                index=False,
                encoding="utf-8-sig",
                quoting=csv.QUOTE_MINIMAL,
                lineterminator="\n",
            )
            item = SheetExportResult(
                sheet_name=sheet_name,
                file_name=os.path.basename(csv_path),
                rows=len(df),
                columns=len(df.columns),
            )
            exported.append(item)
            logger(
                f"  OK   {label} {sheet_name!r:30s} -> {item.file_name} "
                f"({item.rows} rows, {item.columns} cols)"
            )
        except OSError as exc:
            errors.append((sheet_name, str(exc)))
            logger(f"  FAIL {label} {sheet_name!r} -> {exc}")

    logger("")
    logger("-" * 55)
    if errors:
        logger(
            f"Completed with errors: {len(exported)}/{len(sheets)} sheets exported."
        )
        for name, error in errors:
            logger(f"  - {name!r}: {error}")
    else:
        logger(
            f"Done. {len(exported)} sheet(s) exported to: {output_dir}"
        )
    logger("")

    return ConversionResult(
        source_path=source_path,
        output_dir=output_dir,
        total_sheets=len(sheets),
        exported_sheets=exported,
        errors=errors,
    )


def die_with_hint(exc: Exception, path: str) -> None:
    """Raise a user-friendly conversion error."""
    msg = str(exc).lower()
    if "password" in msg or "encrypted" in msg:
        fail(
            "The file appears to be password-protected.\n"
            "Please remove the password before converting."
        )
    if "zipfile" in msg or "not a zip" in msg or "badzip" in msg:
        fail(
            f"Cannot read '{path}'.\n"
            "The file may be corrupted or is not a valid Excel file."
        )
    fail(
        f"Failed to open '{path}'.\n"
        f"Reason: {exc}\n\n"
        f"{traceback.format_exc()}"
    )


def find_workbooks(directory: Path) -> list[Path]:
    """Return supported workbooks in the provided directory."""
    workbooks = [
        path for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return workbooks


def prompt_workbook_selection() -> str | None:
    """Interactive workbook picker for the TUI flow."""
    current_dir = Path.cwd()

    while True:
        workbooks = find_workbooks(current_dir)
        print("=" * 55)
        print("XL2CSV TUI")
        print(f"Current directory: {current_dir}")
        print("")

        if workbooks:
            print("Available workbooks:")
            for idx, workbook in enumerate(workbooks, start=1):
                print(f"  {idx}. {workbook.name}")
        else:
            print("No supported Excel workbooks found in the current directory.")

        print("")
        print("Enter a number, paste a workbook path, or type 'q' to quit.")
        choice = input("> ").strip()

        if not choice:
            print("A workbook path is required.")
            continue

        if choice.lower() in {"q", "quit", "exit"}:
            return None

        if choice.isdigit():
            selected = int(choice)
            if 1 <= selected <= len(workbooks):
                return str(workbooks[selected - 1])
            print("Selection out of range.")
            continue

        return choice


def prompt_repeat() -> bool:
    """Ask whether the user wants to convert another workbook."""
    while True:
        answer = input("Convert another workbook? [y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("Enter 'y' or 'n'.")


def run_tui() -> int:
    """Launch the dependency-free terminal UI."""
    print("Interactive mode started. Press Ctrl+C or type 'q' to exit.")

    while True:
        try:
            selected = prompt_workbook_selection()
            if selected is None:
                print("Exiting.")
                return 0

            try:
                convert(selected)
            except ConversionError as exc:
                print("")
                print(f"Error: {exc}")
                print("")

            if not prompt_repeat():
                print("Exiting.")
                return 0
            print("")
        except KeyboardInterrupt:
            print("")
            print("Exiting.")
            return 130


def print_help() -> None:
    print(
        "Usage:\n"
        "  python xlsx_to_csv.py <file.xlsx>\n"
        "  python xlsx_to_csv.py --tui\n"
        "  python xlsx_to_csv.py\n\n"
        "Modes:\n"
        "  <file.xlsx>  Convert a specific workbook directly.\n"
        "  --tui        Launch the interactive terminal UI.\n"
        "  no args      Launch the interactive terminal UI.\n\n"
        "Supported formats:\n"
        "  .xlsx, .xlsm, .xltx, .xltm\n"
    )


def main() -> int:
    args = sys.argv[1:]

    if not args:
        return run_tui()

    if len(args) == 1 and args[0] in {"-h", "--help"}:
        print_help()
        return 0

    if len(args) == 1 and args[0] in {"-i", "--interactive", "--tui"}:
        return run_tui()

    if len(args) == 1:
        try:
            convert(args[0])
        except ConversionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
