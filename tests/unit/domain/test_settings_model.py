"""Tests for the domain settings model."""

from __future__ import annotations

import pytest

from dicomviewer.domain.settings import (
    AppearanceSettings,
    LoggingSettings,
    Settings,
    SettingsError,
)


def test_appearance_defaults_to_dark() -> None:
    assert AppearanceSettings().theme == "dark"


def test_theme_is_normalized_to_lowercase() -> None:
    assert AppearanceSettings.from_mapping({"theme": "LIGHT"}).theme == "light"


def test_unknown_theme_is_rejected() -> None:
    with pytest.raises(SettingsError):
        AppearanceSettings.from_mapping({"theme": "solarized"})


def test_settings_from_mapping_merges_sections() -> None:
    settings = Settings.from_mapping(
        {"logging": {"level": "DEBUG"}, "appearance": {"theme": "light"}}
    )
    assert settings.logging.level == "DEBUG"
    assert settings.appearance.theme == "light"


def test_settings_to_mapping_round_trips() -> None:
    settings = Settings(
        logging=LoggingSettings(level="DEBUG"),
        appearance=AppearanceSettings(theme="light"),
    )
    rebuilt = Settings.from_mapping(settings.to_mapping())
    assert rebuilt == settings
