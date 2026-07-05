"""Application configuration for VaaniScript."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(slots=True)
class AppConfig:
    workspace_dir: Path = Path("./workspace")
    input_dir: Path = Path("./audio")
    output_dir: Path = Path("./outputs")
    database_path: Path = Path("./vaaniscript.sqlite3")
    log_level: str = "INFO"
    allow_cloud_fallback: bool = False
    model_root: Path = Path("./models")
    default_source_language: str = ""

    def __post_init__(self) -> None:
        for field_name in ("workspace_dir", "input_dir", "output_dir", "database_path", "model_root"):
            value = getattr(self, field_name)
            if not isinstance(value, Path):
                setattr(self, field_name, Path(value))


@dataclass(slots=True)
class PipelineConfig:
    asr_model: str = "small"
    translation_enabled: bool = False
    denoise_enabled: bool = False
    vad_enabled: bool = False
    max_audio_minutes: int = 10

    def __post_init__(self) -> None:
        if self.max_audio_minutes < 1:
            raise ValueError("max_audio_minutes must be >= 1")


class Settings(BaseSettings):
    app: AppConfig
    pipeline: PipelineConfig

    model_config = SettingsConfigDict(
        env_prefix="VAANISCRIPT_",
        env_nested_delimiter="__",
        extra="ignore",
        default_config_path="config.toml",
    )

    def __init__(self, **overrides: Any) -> None:
        config_path = Path(
            overrides.pop("_config_path", None)
            or os.getenv("VAANISCRIPT_CONFIG")
            or self.model_config["default_config_path"]
        )
        data = self._load_toml(config_path)
        data = self._merge_env(data)
        data = self._merge_overrides(data, overrides)
        self.app = AppConfig(**data.get("app", {}))
        self.pipeline = PipelineConfig(**data.get("pipeline", {}))

    @staticmethod
    def _load_toml(config_path: Path) -> dict[str, Any]:
        if not config_path.is_file():
            return {}

        with config_path.open("rb") as handle:
            return tomllib.load(handle)

    @classmethod
    def _merge_env(cls, data: dict[str, Any]) -> dict[str, Any]:
        merged = {
            "app": dict(data.get("app", {})),
            "pipeline": dict(data.get("pipeline", {})),
        }
        prefix = cls.model_config["env_prefix"]
        delimiter = cls.model_config["env_nested_delimiter"]
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix) :]
            if delimiter not in remainder:
                continue
            section, field = remainder.split(delimiter, 1)
            section_key = section.lower()
            field_key = field.lower()
            if section_key not in {"app", "pipeline"}:
                continue
            merged.setdefault(section_key, {})
            merged[section_key][field_key] = cls._coerce_env_value(value)
        return merged

    @staticmethod
    def _merge_overrides(data: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        merged = {
            "app": dict(data.get("app", {})),
            "pipeline": dict(data.get("pipeline", {})),
        }
        for key in ("app", "pipeline"):
            if key in overrides and isinstance(overrides[key], dict):
                merged[key].update(overrides[key])
        return merged

    @staticmethod
    def _coerce_env_value(value: str) -> Any:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if value.isdigit():
            return int(value)
        return value


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from env and optional TOML config."""

    if config_path is None:
        return Settings()

    return Settings(_config_path=config_path)
