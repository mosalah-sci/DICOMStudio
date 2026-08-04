"""Tests for the application ThemeManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.application.theme_manager import ThemeManager
from dicomviewer.domain.settings import (
    AppearanceSettings,
    LoggingSettings,
    RecentFoldersSettings,
    Settings,
    SettingsError,
)


class FakeSettingsStore:
    """In-memory SettingsStore recording every persisted snapshot."""

    def __init__(self) -> None:
        self.saved: list[Settings] = []
        self.defaults = Settings(
            logging=LoggingSettings(),
            appearance=AppearanceSettings(),
            recent=RecentFoldersSettings(),
        )
        self.reset_calls = 0

    def load(self) -> Settings:
        return self.defaults

    def save(self, settings: Settings) -> None:
        self.saved.append(settings)

    def reset(self) -> None:
        self.reset_calls += 1


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


def test_current_settings_exposes_the_snapshot() -> None:
    manager = ThemeManager(FakeSettingsStore(), _settings("dark"))
    assert manager.current_settings.appearance.theme == "dark"


def test_update_persists_and_adopts_a_new_snapshot() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    updated = _settings("light")
    manager.update(updated)
    assert manager.current_settings == updated
    assert store.saved[-1] == updated


def test_reset_calls_the_store_and_returns_defaults() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("light"))
    result = manager.reset()
    assert store.reset_calls == 1
    assert result.appearance.theme == "dark"


def test_add_recent_folder_persists_and_moves_it_first() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    first = manager.add_recent_folder(Path("a"))
    manager.add_recent_folder(Path("b"))
    assert manager.current_settings.recent.folders == (Path("b"), Path("a"))
    assert store.saved[-1].recent.folders == (Path("b"), Path("a"))
    assert first.recent.folders == (Path("a"),)


def test_remove_recent_folder_persists() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    manager.add_recent_folder(Path("a"))
    manager.add_recent_folder(Path("b"))
    result = manager.remove_recent_folder(Path("a"))
    assert result.recent.folders == (Path("b"),)


def test_clear_recent_folders_persists() -> None:
    store = FakeSettingsStore()
    manager = ThemeManager(store, _settings("dark"))
    manager.add_recent_folder(Path("a"))
    result = manager.clear_recent_folders()
    assert result.recent.folders == ()
