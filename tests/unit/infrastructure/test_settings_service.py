"""Tests for the configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.domain.settings import AppearanceSettings, Settings, SettingsError
from dicomviewer.infrastructure.configuration.settings_service import (
    SettingsService,
    load_default_settings,
)


def test_defaults_are_loaded_from_the_bundled_file() -> None:
    settings = load_default_settings()
    assert settings.logging.level == "INFO"
    assert settings.logging.rotation == "10 MB"
    assert settings.logging.retention == "7 days"
    assert settings.appearance.theme == "dark"
    assert settings.recent.folders == ()
    assert settings.viewing.default_window_preset == ""
    assert settings.viewing.max_cache_size == 3
    assert settings.measurements.color == "#22d3ee"


def test_load_returns_defaults_when_no_user_file_exists(tmp_path: Path) -> None:
    service = SettingsService(
        defaults=load_default_settings(), user_settings_path=tmp_path / "settings.toml"
    )
    settings = service.load()
    assert settings.logging.level == "INFO"
    assert settings.appearance.theme == "dark"


def test_load_merges_user_overrides_over_defaults(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    user_file.write_text('[logging]\nlevel = "DEBUG"\n', encoding="utf-8")
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    settings = service.load()
    assert settings.logging.level == "DEBUG"
    assert settings.logging.rotation == "10 MB"


def test_load_applies_the_theme_from_the_user_file(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    user_file.write_text('[appearance]\ntheme = "light"\n', encoding="utf-8")
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    settings = service.load()
    assert settings.appearance.theme == "light"


def test_save_round_trip_preserves_settings(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    defaults = load_default_settings()
    service.save(Settings(logging=defaults.logging))
    reloaded = service.load()
    assert reloaded == defaults


def test_invalid_log_level_is_rejected(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    user_file.write_text('[logging]\nlevel = "LOUD"\n', encoding="utf-8")
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    with pytest.raises(SettingsError):
        service.load()


def test_invalid_theme_is_rejected(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    user_file.write_text('[appearance]\ntheme = "solarized"\n', encoding="utf-8")
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    with pytest.raises(SettingsError):
        service.load()


def test_load_merges_new_section_overrides(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    user_file.write_text(
        '[viewing]\ndefault_window_preset = "CT Lung"\nmax_cache_size = 6\n',
        encoding="utf-8",
    )
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    settings = service.load()
    assert settings.viewing.default_window_preset == "CT Lung"
    assert settings.viewing.max_cache_size == 6
    assert settings.viewing.smooth_scaling is True


def test_save_persists_recent_folders(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    defaults = load_default_settings()
    recent = defaults.recent.add(Path("D:\\studies"))
    service.save(Settings(logging=defaults.logging, recent=recent))
    reloaded = service.load()
    assert reloaded.recent.folders == (Path("D:\\studies"),)


def test_reset_discards_user_overrides(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    defaults = load_default_settings()
    service.save(Settings(logging=defaults.logging, appearance=AppearanceSettings(theme="light")))
    assert service.load().appearance.theme == "light"
    service.reset()
    assert service.load().appearance.theme == "dark"


def test_reset_is_safe_without_a_user_file(tmp_path: Path) -> None:
    user_file = tmp_path / "settings.toml"
    service = SettingsService(defaults=load_default_settings(), user_settings_path=user_file)
    service.reset()
    assert service.load() == load_default_settings()
