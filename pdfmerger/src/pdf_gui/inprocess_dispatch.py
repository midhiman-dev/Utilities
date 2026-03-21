from __future__ import annotations

from typing import Any

from src import backlog_docx_to_excel
from src import compress_max_pdfs
from src import merge_optimize_pdfs
from src import xlsx_to_html


def values_to_argv(tool_id: str, values: dict[str, Any]) -> list[str]:
    argv: list[str] = []

    def add_flag(flag: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str) and value.strip() == "":
            return
        argv.extend([flag, str(value)])

    if tool_id == "merge":
        add_flag("--input", values.get("input"))
        add_flag("--output", values.get("output"))
        if values.get("recursive"):
            argv.append("--recursive")
        add_flag("--sort", values.get("sort") or "name")
        if values.get("overwrite"):
            argv.append("--overwrite")
        if values.get("verbose"):
            argv.append("--verbose")
        if values.get("dry_run"):
            argv.append("--dry-run")
        return argv

    if tool_id == "compress":
        add_flag("--input", values.get("input"))
        add_flag("--output", values.get("output"))
        if values.get("recursive"):
            argv.append("--recursive")
        if values.get("overwrite"):
            argv.append("--overwrite")
        add_flag("--mode", values.get("mode") or "auto")
        add_flag("--target-mb", values.get("target_mb"))
        add_flag("--dpi", values.get("dpi"))
        add_flag("--jpeg-quality", values.get("jpeg_quality"))
        if values.get("grayscale"):
            argv.append("--grayscale")
        add_flag("--max-pages", values.get("max_pages"))
        if values.get("dry_run"):
            argv.append("--dry-run")
        if values.get("verbose"):
            argv.append("--verbose")
        return argv

    if tool_id == "xlsx_html":
        input_path = values.get("input")
        if input_path:
            argv.append(str(input_path))
        output_path = values.get("output")
        if output_path:
            argv.append(str(output_path))
        if values.get("no_toc"):
            argv.append("--no-toc")
        if values.get("index"):
            argv.append("--index")
        return argv

    if tool_id == "docx_excel":
        add_flag("--input", values.get("input"))
        add_flag("--output", values.get("output"))
        if values.get("verbose"):
            argv.append("--verbose")
        if values.get("emit_csv"):
            argv.append("--emit-csv")
        add_flag("--csv-dir", values.get("csv_dir"))
        add_flag("--csv-encoding", values.get("csv_encoding"))
        add_flag("--csv-delimiter", values.get("csv_delimiter"))
        add_flag("--csv-quote", values.get("csv_quote"))
        if values.get("csv_overwrite"):
            argv.append("--csv-overwrite")
        return argv

    raise ValueError(f"Unsupported tool id: {tool_id}")


def run_tool(tool_id: str, values: dict[str, Any]) -> int:
    argv = values_to_argv(tool_id, values)

    if tool_id == "merge":
        return int(merge_optimize_pdfs.main(argv))
    if tool_id == "compress":
        return int(compress_max_pdfs.main(argv))
    if tool_id == "xlsx_html":
        return int(xlsx_to_html.main(argv))
    if tool_id == "docx_excel":
        return int(backlog_docx_to_excel.main(argv))

    raise ValueError(f"Unsupported tool id: {tool_id}")
