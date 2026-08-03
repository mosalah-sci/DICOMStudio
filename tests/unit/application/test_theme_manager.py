"""Tests for the application ThemeManager."""

from __future__ import annotations

import pytest

from dicomviewer.application.theme_manager import ThemeManager
from dicomviewer.domain.settings import AppearanceSettings, LoggingSettings, Settings, SettingsError


class FakeSettingsStore:
    """In-memory SettingsStore recording every persisted snapshot."""

    def __init__(self) -> None:
        self.saved: list[Settings] = []

    def load(self) -> Settings | None:
        return None

    def save(self, settings: Settings) -> None:
        self.saved.append(settings)


def _settings(theme: str = "dark") -> Settings:
    return Settings(logging=LoggingSettings(), appearance=AppearanceSettings(theme=theme))


def test_current_theme_returns_initial_theme() -> None:
    manager = ThemeManager(FakeSettingsStore(), _settings("dark"))
    assert manager.current_theme == "dark"


def test_switch_persists_and_updates_the_theme() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    manager.switch("light")
    assert manager.current_theme == "light"
    assert store.saved[-1].appearance.theme == "light"


def test_switch_rejects_unknown_theme_without_saving() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    with pytest.raises(SettingsError):
        manager.switch("neon")
    assert store.saved == []


def test_apply_override_updates_without_persisting() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    manager.apply_override("light")
    assert manager.current_theme == "light"
    assert store.saved == []
