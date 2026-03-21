from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "PdfMergerGUI"


@dataclass(frozen=True)
class AppPaths:
    config_root: Path
    profiles_root: Path
    logs_root: Path
    config_file: Path
    app_log_file: Path


def resolve_app_paths() -> AppPaths:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    local_appdata = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )

    config_root = appdata / APP_NAME / "config"
    profiles_root = appdata / APP_NAME / "profiles"
    logs_root = local_appdata / APP_NAME / "logs"

    config_root.mkdir(parents=True, exist_ok=True)
    profiles_root.mkdir(parents=True, exist_ok=True)
    logs_root.mkdir(parents=True, exist_ok=True)

    return AppPaths(
        config_root=config_root,
        profiles_root=profiles_root,
        logs_root=logs_root,
        config_file=config_root / "config.json",
        app_log_file=logs_root / "app.log",
    )
