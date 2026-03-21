"""
CLI tool to merge PDFs per subfolder and optionally optimize using pikepdf.
Pure Python; intended for Windows-first usage.
"""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

from pikepdf import ObjectStreamMode, Pdf


@dataclass
class Summary:
    """Collects processing statistics for reporting."""

    folders_discovered: int = 0
    folders_processed: int = 0
    outputs_created: int = 0
    pdfs_merged: int = 0
    pdfs_skipped: int = 0
    optimization_wins: int = 0
    optimization_fallbacks: int = 0
    outputs_skipped_existing: int = 0
    folders_skipped_no_pdfs: int = 0


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge PDFs per subfolder and optimize the merged output using pikepdf "
            "(pure Python)."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input root folder containing subfolders with PDFs",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output folder where merged PDFs will be written",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process all descendant subfolders (default: only immediate subfolders)",
    )
    parser.add_argument(
        "--sort",
        choices=["name", "mtime"],
        default="name",
        help="Merge order for PDFs in each folder (default: name)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs (default: skip existing)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without writing files",
    )
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    return logging.getLogger("merge_optimize_pdfs")


def slugify_folder_name(name: str) -> str:
    """Convert folder name to a safe Windows filename slug."""

    slug = name.strip().lower().replace(" ", "_")
    for ch in INVALID_FILENAME_CHARS:
        slug = slug.replace(ch, "")
    slug = "".join(ch for ch in slug if ch.isprintable())
    slug = slug.strip("._")
    return slug or "merged"


def discover_target_folders(input_root: Path, recursive: bool) -> List[Path]:
    if recursive:
        folders = [p for p in input_root.rglob("*") if p.is_dir()]
    else:
        folders = [p for p in input_root.iterdir() if p.is_dir()]
    if not folders:
        has_root_pdfs = any(
            p.is_file() and p.suffix.lower() == ".pdf" for p in input_root.iterdir()
        )
        if has_root_pdfs:
            folders = [input_root]
    folders_sorted = sorted(folders, key=lambda p: p.as_posix().lower())
    return folders_sorted


def find_pdfs(folder: Path, sort_mode: str) -> List[Path]:
    pdfs = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    if sort_mode == "name":
        pdfs.sort(key=lambda p: p.name.lower())
    else:
        pdfs.sort(key=lambda p: p.stat().st_mtime)
    return pdfs


def merge_pdfs(
    pdf_paths: Sequence[Path], temp_output: Path, logger: logging.Logger
) -> Tuple[int, int, int]:
    """Merge PDFs into a temp file. Returns (merged_count, skipped_count, pages_total)."""

    merged_count = 0
    skipped_count = 0
    pages_total = 0
    pdf_dest = Pdf.new()
    try:
        for pdf_path in pdf_paths:
            try:
                with Pdf.open(pdf_path) as src:
                    pages_total += len(src.pages)
                    pdf_dest.pages.extend(src.pages)
                    merged_count += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Skipping PDF in %s: %s (%s)", pdf_path.parent.name, pdf_path.name, exc
                )
                skipped_count += 1

        if merged_count == 0:
            return merged_count, skipped_count, pages_total

        pdf_dest.save(temp_output)
        return merged_count, skipped_count, pages_total
    finally:
        pdf_dest.close()


def optimize_pdf(source: Path, temp_dir: Path, logger: logging.Logger) -> Tuple[Path, bool]:
    """Optimize a merged PDF. Returns (path_to_use, optimized_was_better)."""

    fd, opt_path_str = tempfile.mkstemp(prefix="opt_", suffix=".pdf", dir=temp_dir)
    os.close(fd)
    opt_path = Path(opt_path_str)

    try:
        with Pdf.open(source) as pdf:
            pdf.save(
                opt_path,
                compress_streams=True,
                object_stream_mode=ObjectStreamMode.generate,
            )

        source_size = source.stat().st_size
        optimized_size = opt_path.stat().st_size

        if optimized_size < source_size:
            logger.debug(
                "Optimization reduced size from %s to %s bytes", source_size, optimized_size
            )
            return opt_path, True

        logger.info(
            "Optimization did not reduce size for %s (merged=%s, optimized=%s). Using merged.",
            source.name,
            source_size,
            optimized_size,
        )
        opt_path.unlink(missing_ok=True)
        return source, False

    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Optimization failed for %s: %s", source.name, exc)
        opt_path.unlink(missing_ok=True)
        return source, False


def ensure_output_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def process_folder(
    folder: Path,
    output_dir: Path,
    sort_mode: str,
    overwrite: bool,
    dry_run: bool,
    logger: logging.Logger,
    summary: Summary,
) -> None:
    pdfs = find_pdfs(folder, sort_mode)
    if not pdfs:
        logger.info("No PDFs in %s; skipping", folder)
        summary.folders_skipped_no_pdfs += 1
        return

    slug = slugify_folder_name(folder.name)
    final_path = output_dir / f"{slug}.pdf"

    if final_path.exists() and not overwrite:
        logger.info("Output exists and overwrite is False; skipping %s", final_path)
        summary.outputs_skipped_existing += 1
        return

    if dry_run:
        logger.info(
            "[DRY-RUN] Would merge %d PDFs from %s into %s", len(pdfs), folder, final_path
        )
        return

    fd, merged_temp_str = tempfile.mkstemp(prefix="merged_", suffix=".pdf", dir=output_dir)
    os.close(fd)
    merged_temp = Path(merged_temp_str)

    merged_count, skipped_count, pages_total = merge_pdfs(pdfs, merged_temp, logger)
    summary.pdfs_merged += merged_count
    summary.pdfs_skipped += skipped_count

    if merged_count == 0:
        logger.info("All PDFs failed to merge in %s; skipping output", folder)
        merged_temp.unlink(missing_ok=True)
        return

    selected_path, optimized_better = optimize_pdf(merged_temp, output_dir, logger)
    if optimized_better:
        summary.optimization_wins += 1
    else:
        summary.optimization_fallbacks += 1

    selected_path.replace(final_path)
    if selected_path != merged_temp:
        merged_temp.unlink(missing_ok=True)

    summary.outputs_created += 1
    logger.info("Wrote %s (%s pages)", final_path, pages_total)


def print_summary(summary: Summary, logger: logging.Logger) -> None:
    logger.info(
        "Summary: folders=%s, outputs=%s, pdfs_merged=%s, pdfs_skipped=%s, "
        "opt_wins=%s, opt_fallbacks=%s, outputs_skipped=%s, no_pdf_folders=%s",
        summary.folders_processed,
        summary.outputs_created,
        summary.pdfs_merged,
        summary.pdfs_skipped,
        summary.optimization_wins,
        summary.optimization_fallbacks,
        summary.outputs_skipped_existing,
        summary.folders_skipped_no_pdfs,
    )


def run(args: argparse.Namespace) -> int:
    logger = configure_logging(args.verbose)

    input_root = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()

    if not input_root.exists() or not input_root.is_dir():
        raise SystemExit(f"Input path does not exist or is not a directory: {input_root}")

    ensure_output_dir(output_root, args.dry_run)

    summary = Summary()

    folders = discover_target_folders(input_root, args.recursive)
    summary.folders_discovered = len(folders)

    for folder in folders:
        summary.folders_processed += 1
        process_folder(
            folder=folder,
            output_dir=output_root,
            sort_mode=args.sort,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            logger=logger,
            summary=summary,
        )

    print_summary(summary, logger)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
