from __future__ import annotations

import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .paths import AppPaths


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def _write_env_json(workspace_root: Path, paths: AppPaths, temp_file: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "workspace_root": str(workspace_root),
        "appdata_config": str(paths.config_root),
        "appdata_profiles": str(paths.profiles_root),
        "localappdata_logs": str(paths.logs_root),
    }
    temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def create_diagnostics_bundle(workspace_root: Path, paths: AppPaths, destination_zip: Path) -> Path:
    destination_zip.parent.mkdir(parents=True, exist_ok=True)

    env_file = destination_zip.parent / "environment_info.json"
    _write_env_json(workspace_root=workspace_root, paths=paths, temp_file=env_file)

    with zipfile.ZipFile(destination_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source_root, arc_prefix in (
            (paths.config_root, "config"),
            (paths.profiles_root, "profiles"),
            (paths.logs_root, "logs"),
        ):
            for file_path in _iter_files(source_root):
                rel = file_path.relative_to(source_root)
                zf.write(file_path, Path(arc_prefix) / rel)

        zf.write(env_file, Path("environment_info.json"))

    env_file.unlink(missing_ok=True)
    return destination_zip
