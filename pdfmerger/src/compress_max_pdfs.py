"""
Aggressive PDF compression tool with lossless and lossy modes.
- Stage A: lossless optimization via pikepdf.
- Stage B: rasterize + rebuild via PyMuPDF for maximum size reduction.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from pikepdf import ObjectStreamMode, Pdf


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


@dataclass
class Summary:
    total_pdfs: int = 0
    lossless_used: int = 0
    aggressive_used: int = 0
    copied_original: int = 0
    failures: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    met_target: int = 0
    missed_target: int = 0
    target_misses: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class FileResult:
    output_path: Path
    mode_used: str  # lossless | aggressive | copied
    original_size: int
    final_size: int
    warning: Optional[str] = None


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compress PDFs with lossless (pikepdf) and/or aggressive rasterization (PyMuPDF)."
    )
    parser.add_argument("--input", required=True, help="Input folder containing PDFs")
    parser.add_argument(
        "--output",
        help="Output folder (default: <input>/compressedfiles)",
    )
    parser.add_argument("--recursive", action="store_true", help="Process PDFs in subfolders")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    parser.add_argument(
        "--mode",
        choices=["auto", "lossless", "aggressive"],
        default="auto",
        help="Compression mode (default: auto)",
    )
    parser.add_argument(
        "--target-mb",
        type=float,
        help="In auto mode, run aggressive if still above this size (MB) after lossless",
    )
    parser.add_argument("--dpi", type=int, default=150, help="Rasterization DPI (default 150)")
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=70,
        help="JPEG quality 40-85 for aggressive mode (default 70)",
    )
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="Render pages in grayscale during aggressive mode",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Process only first N pages (for testing)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List actions without writing")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    return logging.getLogger("compress_max_pdfs")


def sanitize_filename(name: str) -> str:
    sanitized = name
    for ch in INVALID_FILENAME_CHARS:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.strip()
    return sanitized or "compressed"


def discover_pdfs(root: Path, recursive: bool) -> List[Path]:
    if recursive:
        return sorted([p for p in root.rglob("*.pdf") if p.is_file()], key=lambda p: p.as_posix().lower())
    return sorted([p for p in root.glob("*.pdf") if p.is_file()], key=lambda p: p.as_posix().lower())


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def lossless_optimize(source: Path, temp_dir: Path, logger: logging.Logger) -> Optional[Path]:
    fd, temp_str = tempfile.mkstemp(prefix="lossless_", suffix=".pdf", dir=temp_dir)
    os.close(fd)
    temp_path = Path(temp_str)
    try:
        with Pdf.open(source) as pdf:
            pdf.save(
                temp_path,
                compress_streams=True,
                object_stream_mode=ObjectStreamMode.generate,
            )
        if temp_path.exists() and temp_path.stat().st_size > 0:
            return temp_path
        logger.warning("Lossless optimization produced no file for %s", source.name)
        temp_path.unlink(missing_ok=True)
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Lossless optimization failed for %s: %s", source.name, exc)
        temp_path.unlink(missing_ok=True)
        return None


def rasterize_rebuild(
    source: Path,
    temp_dir: Path,
    dpi: int,
    jpeg_quality: int,
    grayscale: bool,
    max_pages: Optional[int],
    logger: logging.Logger,
) -> Optional[Path]:
    fd, temp_str = tempfile.mkstemp(prefix="aggr_", suffix=".pdf", dir=temp_dir)
    os.close(fd)
    temp_path = Path(temp_str)

    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        colorspace = fitz.csGRAY if grayscale else None
        with fitz.open(source) as doc:
            new_doc = fitz.open()
            try:
                page_count = len(doc)
                pages_to_process = page_count if max_pages is None else min(max_pages, page_count)
                for page_index in range(pages_to_process):
                    page = doc.load_page(page_index)
                    pix = page.get_pixmap(matrix=mat, colorspace=colorspace, alpha=False)
                    img_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_quality)
                    rect = page.rect
                    new_page = new_doc.new_page(width=rect.width, height=rect.height)
                    new_page.insert_image(new_page.rect, stream=img_bytes)
                new_doc.save(temp_path, deflate=True)
            finally:
                new_doc.close()
        if temp_path.exists() and temp_path.stat().st_size > 0:
            return temp_path
        logger.warning("Aggressive rasterize produced no file for %s", source.name)
        temp_path.unlink(missing_ok=True)
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Aggressive rasterize failed for %s: %s", source.name, exc)
        temp_path.unlink(missing_ok=True)
        return None


def should_run_aggressive(
    mode: str,
    lossless_ok: bool,
    lossless_size: Optional[int],
    original_size: int,
    target_bytes: Optional[int],
    threshold_bytes: int,
) -> Tuple[bool, str]:
    """Return (should_run, reason)."""

    if mode == "aggressive":
        return True, "mode=aggressive"
    if mode == "lossless":
        return False, "mode=lossless"

    # auto mode
    if original_size > threshold_bytes:
        return True, "above-threshold"
    if not lossless_ok:
        return True, "lossless-failed"
    if lossless_size is None:
        return True, "lossless-missing"
    if lossless_size >= original_size:
        return True, "lossless-not-smaller"
    if target_bytes is not None and lossless_size > target_bytes:
        return True, "above-target"
    return False, "lossless-acceptable"


def atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dest)


def copy_to_temp(source: Path, temp_dir: Path) -> Path:
    fd, temp_str = tempfile.mkstemp(prefix="copy_", suffix=source.suffix, dir=temp_dir)
    os.close(fd)
    temp_path = Path(temp_str)
    shutil.copy2(source, temp_path)
    return temp_path


def process_pdf(
    pdf_path: Path,
    input_root: Path,
    output_dir: Path,
    overwrite: bool,
    mode: str,
    target_bytes: Optional[int],
    threshold_bytes: int,
    dpi: int,
    jpeg_quality: int,
    grayscale: bool,
    max_pages: Optional[int],
    dry_run: bool,
    logger: logging.Logger,
    summary: Summary,
) -> Optional[FileResult]:
    summary.total_pdfs += 1
    try:
        rel_display = str(pdf_path.relative_to(input_root))
    except ValueError:
        rel_display = pdf_path.name

    sanitized_name = sanitize_filename(pdf_path.name)
    output_path = output_dir / sanitized_name

    if output_path.exists() and not overwrite:
        logger.info("[%s] Skipping existing (overwrite=False): %s", rel_display, output_path)
        return None

    original_size = pdf_path.stat().st_size
    summary.bytes_before += original_size

    if dry_run:
        logger.info(
            "[DRY-RUN][%s] Would compress %s (%s) -> %s",
            rel_display,
            pdf_path,
            format_size(original_size),
            output_path,
        )
        return None

    temp_candidates: List[Path] = []
    chosen_path: Optional[Path] = None
    mode_used = "copied"
    warning: Optional[str] = None

    temp_dir = Path(tempfile.mkdtemp(prefix="cmp_", dir=output_dir))

    # Stage A: lossless
    lossless_path = None
    if mode in ("auto", "lossless"):
        lossless_path = lossless_optimize(pdf_path, temp_dir, logger)
        if lossless_path:
            temp_candidates.append(lossless_path)

    lossless_ok = lossless_path is not None
    lossless_size = lossless_path.stat().st_size if lossless_path else None

    run_aggr, aggr_reason = should_run_aggressive(
        mode,
        lossless_ok,
        lossless_size,
        original_size,
        target_bytes,
        threshold_bytes,
    )

    aggr_path = None
    if run_aggr:
        aggr_path = rasterize_rebuild(
            pdf_path,
            temp_dir,
            dpi=dpi,
            jpeg_quality=jpeg_quality,
            grayscale=grayscale,
            max_pages=max_pages,
            logger=logger,
        )
        if aggr_path and aggr_path.exists():
            temp_candidates.append(aggr_path)
        else:
            aggr_path = None

    # Decide output path
    candidates: List[Tuple[str, Path]] = []
    if lossless_path:
        candidates.append(("lossless", lossless_path))
    if aggr_path:
        candidates.append(("aggressive", aggr_path))

    if candidates:
        candidates = [(m, p) for m, p in candidates if p.exists()]
    if candidates:
        mode_used, chosen_path = min(candidates, key=lambda item: item[1].stat().st_size)
    elif lossless_ok and lossless_path and lossless_path.exists():
        chosen_path = lossless_path
        mode_used = "lossless"
    else:
        # fallback: copy original
        chosen_path = copy_to_temp(pdf_path, temp_dir)
        mode_used = "copied"
        warning = "Both compression stages failed; copied original"
        temp_candidates.append(chosen_path)

    if not chosen_path or not chosen_path.exists():
        logger.warning("[%s] Chosen output missing (%s); falling back", rel_display, chosen_path)
        warning = (warning + "; " if warning else "") + "Chosen output missing; fallback"
        if lossless_path and lossless_path.exists():
            chosen_path = lossless_path
            mode_used = "lossless"
        else:
            chosen_path = copy_to_temp(pdf_path, temp_dir)
            mode_used = "copied"
            temp_candidates.append(chosen_path)

    final_size = chosen_path.stat().st_size if chosen_path and chosen_path.exists() else original_size

    # Capture sizes BEFORE cleanup (files will be moved/deleted)
    aggr_size = aggr_path.stat().st_size if aggr_path and aggr_path.exists() else None

    try:
        atomic_replace(chosen_path, output_path)
    finally:
        # cleanup other temps and temp dir
        for temp in temp_candidates:
            if temp != output_path and temp != chosen_path and temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    logger.debug("Temp cleanup failed for %s", temp)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except OSError:
            logger.debug("Temp dir cleanup failed for %s", temp_dir)

    # summarize
    if mode_used == "lossless":
        summary.lossless_used += 1
    elif mode_used == "aggressive":
        summary.aggressive_used += 1
    else:
        summary.copied_original += 1
    summary.bytes_after += final_size

    if target_bytes is not None:
        if final_size <= target_bytes:
            summary.met_target += 1
        else:
            summary.missed_target += 1
            summary.target_misses.append((rel_display, final_size))
            if mode_used == "aggressive":
                logger.warning(
                    "[%s] Target not met after aggressive; final size %s (target %.2f MB)",
                    rel_display,
                    format_size(final_size),
                    target_bytes / (1024 * 1024),
                )

    saved = original_size - final_size
    pct = (saved / original_size * 100) if original_size else 0.0

    lossless_str = format_size(lossless_size) if lossless_size is not None else "-"
    aggr_str = format_size(aggr_size) if aggr_size is not None else "-"
    stage_str = "aggressive" if mode_used == "aggressive" else "lossless" if mode_used == "lossless" else "copied"
    logger.info(
        "[%s] Original: %s | Lossless: %s | Aggressive: %s | Final: %s | Saved: %.1f%% | Mode=%s | Stage=%s | Reason=%s",
        rel_display,
        format_size(original_size),
        lossless_str,
        aggr_str,
        format_size(final_size),
        pct,
        mode,
        stage_str,
        aggr_reason,
    )

    return FileResult(
        output_path=output_path,
        mode_used=mode_used,
        original_size=original_size,
        final_size=final_size,
        warning=warning,
    )


def print_summary(summary: Summary, logger: logging.Logger) -> None:
    total_saved = summary.bytes_before - summary.bytes_after
    pct = (total_saved / summary.bytes_before * 100) if summary.bytes_before else 0.0
    logger.info(
        "Summary: files=%s, lossless=%s, aggressive=%s, copied=%s, failures=%s, saved=%s (%.1f%%), met_target=%s, missed_target=%s",
        summary.total_pdfs,
        summary.lossless_used,
        summary.aggressive_used,
        summary.copied_original,
        summary.failures,
        format_size(total_saved),
        pct,
        summary.met_target,
        summary.missed_target,
    )

    if summary.target_misses:
        top_misses = sorted(summary.target_misses, key=lambda item: item[1], reverse=True)[:10]
        lines = [f"  {path} -> {format_size(size)}" for path, size in top_misses]
        logger.info("Files over target (top %s):\n%s", len(lines), "\n".join(lines))


def run(args: argparse.Namespace) -> int:
    logger = configure_logging(args.verbose)

    threshold_bytes = 4 * 1024 * 1024

    # Default target for auto mode if not provided
    if args.mode == "auto" and args.target_mb is None:
        args.target_mb = 4.0

    target_bytes = int(args.target_mb * 1024 * 1024) if args.target_mb is not None else None

    input_root = Path(args.input).expanduser().resolve()
    if not input_root.is_dir():
        raise SystemExit(f"Input folder does not exist or is not a directory: {input_root}")

    output_root = Path(args.output).expanduser().resolve() if args.output else input_root / "compressedfiles"
    output_root.mkdir(parents=True, exist_ok=True)

    if args.jpeg_quality < 40 or args.jpeg_quality > 85:
        raise SystemExit("--jpeg-quality must be between 40 and 85")
    if args.dpi < 72 or args.dpi > 400:
        raise SystemExit("--dpi should be between 72 and 400 for practical use")

    pdf_files = discover_pdfs(input_root, args.recursive)
    if not pdf_files:
        logger.info("No PDFs found in %s", input_root)
        return

    summary = Summary()

    for pdf_path in pdf_files:
        try:
            process_pdf(
                pdf_path=pdf_path,
                input_root=input_root,
                output_dir=output_root,
                overwrite=args.overwrite,
                mode=args.mode,
                target_bytes=target_bytes,
                threshold_bytes=threshold_bytes,
                dpi=args.dpi,
                jpeg_quality=args.jpeg_quality,
                grayscale=args.grayscale,
                max_pages=args.max_pages,
                dry_run=args.dry_run,
                logger=logger,
                summary=summary,
            )
        except Exception as exc:  # pylint: disable=broad-except
            summary.failures += 1
            logger.error("Failed to process %s: %s", pdf_path, exc)

    print_summary(summary, logger)
    return 0


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
