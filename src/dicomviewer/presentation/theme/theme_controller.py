"""Coordinates theme persistence, palette application and icon tinting."""

from __future__ import annotations

from dicomviewer.application.settings_manager import SettingsManager
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.theme.theme_provider import ThemeProvider
from dicomviewer.presentation.theme.themes import THEMES


class ThemeController:
    """Single entry point for switching or refreshing the active theme."""

    def __init__(
        self,
        manager: SettingsManager,
        provider: ThemeProvider,
        icons: IconProvider,
    ) -> None:
        """Compose theme persistence, application and icon tinting."""
        self._manager = manager
        self._provider = provider
        self._icons = icons

    @property
    def current_theme(self) -> str:
        """Name of the active theme."""
        return self._manager.current_theme

    def apply_current(self) -> None:
        """Apply the persisted theme to the UI (used at startup)."""
        name = self._manager.current_theme
        self._provider.apply(name)
        self._icons.set_color(THEMES[name].tokens.icon)

    def switch(self, theme_name: str) -> None:
        """Persist and apply a new theme."""
        self._manager.switch(theme_name)
        self.apply_current()
