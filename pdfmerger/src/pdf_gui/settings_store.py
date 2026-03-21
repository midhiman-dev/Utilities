from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import AppPaths, resolve_app_paths
from .tool_specs import default_values


class SettingsStore:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or resolve_app_paths()
        self.defaults = default_values()

    def load_config(self) -> dict[str, dict[str, Any]]:
        if not self.paths.config_file.exists():
            return json.loads(json.dumps(self.defaults))

        try:
            data = json.loads(self.paths.config_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(self.defaults))

        merged = json.loads(json.dumps(self.defaults))
        for tool_id, values in data.items():
            if tool_id in merged and isinstance(values, dict):
                merged[tool_id].update(values)
        return merged

    def save_config(self, config: dict[str, dict[str, Any]]) -> None:
        payload = json.dumps(config, indent=2, ensure_ascii=False)
        self.paths.config_file.write_text(payload, encoding="utf-8")

    def reset_defaults(self) -> dict[str, dict[str, Any]]:
        defaults_copy = json.loads(json.dumps(self.defaults))
        self.save_config(defaults_copy)
        return defaults_copy

    def _tool_profile_dir(self, tool_id: str) -> Path:
        path = self.paths.profiles_root / tool_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_profiles(self, tool_id: str) -> list[str]:
        profile_dir = self._tool_profile_dir(tool_id)
        return sorted(p.stem for p in profile_dir.glob("*.json"))

    def save_profile(self, tool_id: str, profile_name: str, values: dict[str, Any]) -> Path:
        profile_dir = self._tool_profile_dir(tool_id)
        safe_name = "".join(ch for ch in profile_name if ch.isalnum() or ch in ("-", "_", " ")).strip()
        if not safe_name:
            safe_name = datetime.now().strftime("profile_%Y%m%d_%H%M%S")
        path = profile_dir / f"{safe_name}.json"
        path.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_profile(self, tool_id: str, profile_name: str) -> dict[str, Any]:
        path = self._tool_profile_dir(tool_id) / f"{profile_name}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def export_profile(self, tool_id: str, profile_name: str, target_file: Path) -> Path:
        source = self._tool_profile_dir(tool_id) / f"{profile_name}.json"
        if not source.exists():
            raise FileNotFoundError(source)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target_file)
        return target_file

    def import_profile(self, tool_id: str, source_file: Path) -> str:
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        profile_name = source_file.stem
        self.save_profile(tool_id, profile_name, payload)
        return profile_name
