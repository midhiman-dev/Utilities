from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str  # path | text | int | float | bool | choice
    required: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    id: str
    title: str
    script_name: str
    fields: tuple[FieldSpec, ...]


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        id="merge",
        title="Merge PDFs",
        script_name="merge_optimize_pdfs.py",
        fields=(
            FieldSpec("input", "Input Folder", "path", required=True),
            FieldSpec("output", "Output Folder", "path", required=True),
            FieldSpec("recursive", "Recursive", "bool"),
            FieldSpec("sort", "Sort", "choice", choices=("name", "mtime")),
            FieldSpec("overwrite", "Overwrite", "bool"),
            FieldSpec("verbose", "Verbose", "bool"),
            FieldSpec("dry_run", "Dry Run", "bool"),
        ),
    ),
    ToolSpec(
        id="compress",
        title="Compress PDFs",
        script_name="compress_max_pdfs.py",
        fields=(
            FieldSpec("input", "Input Folder", "path", required=True),
            FieldSpec("output", "Output Folder", "path"),
            FieldSpec("recursive", "Recursive", "bool"),
            FieldSpec("overwrite", "Overwrite", "bool"),
            FieldSpec("mode", "Mode", "choice", choices=("auto", "lossless", "aggressive")),
            FieldSpec("target_mb", "Target MB", "float"),
            FieldSpec("dpi", "DPI", "int"),
            FieldSpec("jpeg_quality", "JPEG Quality", "int"),
            FieldSpec("grayscale", "Grayscale", "bool"),
            FieldSpec("max_pages", "Max Pages", "int"),
            FieldSpec("dry_run", "Dry Run", "bool"),
            FieldSpec("verbose", "Verbose", "bool"),
        ),
    ),
    ToolSpec(
        id="xlsx_html",
        title="XLSX to HTML",
        script_name="xlsx_to_html.py",
        fields=(
            FieldSpec("input", "Input XLSX", "path", required=True),
            FieldSpec("output", "Output HTML", "path"),
            FieldSpec("no_toc", "Disable TOC", "bool"),
            FieldSpec("index", "Include Index", "bool"),
        ),
    ),
    ToolSpec(
        id="docx_excel",
        title="DOCX to Excel",
        script_name="backlog_docx_to_excel.py",
        fields=(
            FieldSpec("input", "Input DOCX", "path", required=True),
            FieldSpec("output", "Output XLSX", "path"),
            FieldSpec("verbose", "Verbose", "bool"),
            FieldSpec("emit_csv", "Emit CSV", "bool"),
            FieldSpec("csv_dir", "CSV Directory", "path"),
            FieldSpec("csv_encoding", "CSV Encoding", "text"),
            FieldSpec("csv_delimiter", "CSV Delimiter", "text"),
            FieldSpec("csv_quote", "CSV Quote", "choice", choices=("minimal", "all")),
            FieldSpec("csv_overwrite", "CSV Overwrite", "bool"),
        ),
    ),
)

TOOL_BY_ID = {tool.id: tool for tool in TOOLS}


def default_values() -> dict[str, dict[str, Any]]:
    defaults: dict[str, dict[str, Any]] = {
        "merge": {
            "recursive": False,
            "sort": "name",
            "overwrite": False,
            "verbose": False,
            "dry_run": False,
        },
        "compress": {
            "recursive": False,
            "overwrite": False,
            "mode": "auto",
            "target_mb": "4.0",
            "dpi": "150",
            "jpeg_quality": "70",
            "grayscale": False,
            "max_pages": "",
            "dry_run": False,
            "verbose": False,
        },
        "xlsx_html": {
            "no_toc": False,
            "index": False,
        },
        "docx_excel": {
            "verbose": False,
            "emit_csv": False,
            "csv_encoding": "utf-8",
            "csv_delimiter": ",",
            "csv_quote": "minimal",
            "csv_overwrite": False,
        },
    }
    return defaults


def tool_script_path(workspace_root: Path, tool_id: str) -> Path:
    return workspace_root / TOOL_BY_ID[tool_id].script_name
