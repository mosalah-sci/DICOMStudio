"""Settings lifecycle management.

The manager owns the current validated settings snapshot and is the single
place that persists configuration changes. Theme switching is one special case;
viewing, measurement and recent-folder preferences go through the same update
path so every layer reads one consistent snapshot.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from dicomviewer.application.settings_store import SettingsStore
from dicomviewer.domain.settings import AppearanceSettings, Settings


class ThemeManager:
    """Tracks and persists the active theme and user preferences.

    The manager owns the current settings snapshot. ``switch`` validates the
    theme, persists it and updates the snapshot; ``apply_override`` updates the
    snapshot without persisting, for one-shot command-line overrides. Generic
    preference updates and a full reset are exposed through ``update`` and
    ``reset``.
    """

    def __init__(self, store: SettingsStore, settings: Settings) -> None:
        """Store the injected store and the starting settings snapshot."""
        self._store = store
        self._settings = settings

    @property
    def current_theme(self) -> str:
        """Name of the active theme."""
        return self._settings.appearance.theme

    @property
    def current_settings(self) -> Settings:
        """Return the current validated settings snapshot."""
        return self._settings

    def apply_override(self, theme: str) -> None:
        """Switch the snapshot theme in memory without persisting it."""
        self._settings = _with_theme(self._settings, theme)

    def switch(self, theme: str) -> None:
        """Switch, persist and confirm the active theme."""
        updated = _with_theme(self._settings, theme)
        self._store.save(updated)
        self._settings = updated

    def update(self, settings: Settings) -> None:
        """Persist and adopt a complete new settings snapshot."""
        self._store.save(settings)
        self._settings = settings

    def reset(self) -> Settings:
        """Discard user overrides, adopt and return the default settings."""
        self._store.reset()
        self._settings = self._store.load()
        return self._settings

    def add_recent_folder(self, folder: Path) -> Settings:
        """Record ``folder`` as recently opened, persist and return settings."""
        updated = replace(self._settings, recent=self._settings.recent.add(folder))
        self._store.save(updated)
        self._settings = updated
        return updated

    def remove_recent_folder(self, folder: Path) -> Settings:
        """Drop ``folder`` from the recent list, persist and return settings."""
        updated = replace(self._settings, recent=self._settings.recent.remove(folder))
        self._store.save(updated)
        self._settings = updated
        return updated

    def clear_recent_folders(self) -> Settings:
        """Clear the recent folders list, persist and return settings."""
        updated = replace(self._settings, recent=self._settings.recent.clear())
        self._store.save(updated)
        self._settings = updated
        return updated


def _with_theme(settings: Settings, theme: str) -> Settings:
    """Return a copy of ``settings`` with a validated theme."""
    appearance = AppearanceSettings.from_mapping({"theme": theme})
    return replace(settings, appearance=appearance)
