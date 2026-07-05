"""Local build backend for offline editable installs in Slice S0."""

from __future__ import annotations

import base64
import hashlib
import os
import tomllib
import zipfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent


def _project_metadata() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def _dist_info_dir() -> str:
    project = _project_metadata()
    normalized = project["name"].replace("-", "_")
    return f"{normalized}-{project['version']}.dist-info"


def _wheel_name() -> str:
    project = _project_metadata()
    normalized = project["name"].replace("-", "_")
    return f"{normalized}-{project['version']}-py3-none-any.whl"


def _metadata_text() -> str:
    project = _project_metadata()
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
        f"Summary: {project['description']}",
        f"Requires-Python: {project['requires-python']}",
        "Provides-Extra: dev",
        "",
    ]
    return "\n".join(lines)


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: local-s0-backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _entry_points_text() -> str:
    project = _project_metadata()
    scripts = project.get("scripts", {})
    lines = ["[console_scripts]"]
    for name, target in scripts.items():
        lines.append(f"{name} = {target}")
    lines.append("")
    return "\n".join(lines)


def _hash_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _iter_source_files() -> Iterable[Path]:
    for package_dir in ("vaaniscript", "typer", "pydantic_settings"):
        yield from (ROOT / package_dir).rglob("*.py")


def _record_rows(files: list[tuple[str, bytes]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for rel_path, data in files:
        rows.append([rel_path, _hash_bytes(data), str(len(data))])
    rows.append([f"{_dist_info_dir()}/RECORD", "", ""])
    return rows


def _build_archive(wheel_directory: str, editable: bool) -> str:
    wheel_dir = Path(wheel_directory)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_dir / _wheel_name()
    dist_info = _dist_info_dir()
    files: list[tuple[str, bytes]] = []

    if editable:
        pth_name = f"{_project_metadata()['name']}.pth"
        files.append((pth_name, (str(ROOT) + os.linesep).encode("utf-8")))
    else:
        for source_path in _iter_source_files():
            rel_path = source_path.relative_to(ROOT).as_posix()
            files.append((rel_path, source_path.read_bytes()))

    files.extend(
        [
            (f"{dist_info}/METADATA", _metadata_text().encode("utf-8")),
            (f"{dist_info}/WHEEL", _wheel_text().encode("utf-8")),
            (f"{dist_info}/entry_points.txt", _entry_points_text().encode("utf-8")),
        ]
    )

    record_rows = _record_rows(files)
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path, data in files:
            archive.writestr(rel_path, data)
        record_bytes = "".join(",".join(row) + "\n" for row in record_rows).encode("utf-8")
        archive.writestr(f"{dist_info}/RECORD", record_bytes)

    return wheel_path.name


def build_wheel(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_archive(wheel_directory, editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_archive(wheel_directory, editable=True)


def get_requires_for_build_wheel(config_settings: dict | None = None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings: dict | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict | None = None,
) -> str:
    dist_info = Path(metadata_directory) / _dist_info_dir()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(_entry_points_text(), encoding="utf-8")
    return dist_info.name


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict | None = None,
) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)
