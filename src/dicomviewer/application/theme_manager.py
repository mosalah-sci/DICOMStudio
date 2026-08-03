"""Theme lifecycle management."""

from __future__ import annotations

from dataclasses import replace

from dicomviewer.application.settings_store import SettingsStore
from dicomviewer.domain.settings import AppearanceSettings, Settings


class ThemeManager:
    """Tracks and persists the active theme.

    The manager owns the current settings snapshot. ``switch`` validates the
    theme, persists it and updates the snapshot; ``apply_override`` updates the
    snapshot without persisting, for one-shot command-line overrides.
    """

    def __init__(self, store: SettingsStore, settings: Settings) -> None:
        """Store the injected store and the starting settings snapshot."""
        self._store = store
        self._settings = settings

    @property
    def current_theme(self) -> str:
        """Name of the active theme."""
        return self._settings.appearance.theme

    def apply_override(self, theme: str) -> None:
        """Switch the snapshot theme in memory without persisting it."""
        self._settings = _with_theme(self._settings, theme)

    def switch(self, theme: str) -> None:
        """Switch, persist and confirm the active theme."""
        updated = _with_theme(self._settings, theme)
        self._store.save(updated)
        self._settings = updated


def _with_theme(settings: Settings, theme: str) -> Settings:
    """Return a copy of ``settings`` with a validated theme."""
    appearance = AppearanceSettings.from_mapping({"theme": theme})
    return replace(settings, appearance=appearance)
