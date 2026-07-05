from pathlib import Path

from vaaniscript.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.app.allow_cloud_fallback is False
    assert settings.pipeline.asr_model == "small"


def test_settings_load_from_toml(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[app]",
                'workspace_dir = "./custom-workspace"',
                'database_path = "./state.sqlite3"',
                "",
                "[pipeline]",
                'asr_model = "medium"',
                "translation_enabled = true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VAANISCRIPT_CONFIG", str(config_path))

    settings = Settings()

    assert settings.app.workspace_dir == Path("./custom-workspace")
    assert settings.app.database_path == Path("./state.sqlite3")
    assert settings.pipeline.asr_model == "medium"
    assert settings.pipeline.translation_enabled is True
