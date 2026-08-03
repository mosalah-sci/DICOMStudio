"""Applying a theme to the running QApplication."""

from __future__ import annotations

from importlib.resources import files

from loguru import logger
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from dicomviewer.presentation.theme.themes import THEMES, ThemeSpec, ThemeTokens

_DISABLED_TEXT_ROLES = (
    QPalette.ColorRole.WindowText,
    QPalette.ColorRole.Text,
    QPalette.ColorRole.ButtonText,
    QPalette.ColorRole.Highlight,
    QPalette.ColorRole.HighlightedText,
    QPalette.ColorRole.Link,
)


class ThemeProvider:
    """Configures the application palette and stylesheet for a theme."""

    def __init__(self, application: QApplication) -> None:
        """Apply themes to the given application instance."""
        self._application = application

    def apply(self, theme_name: str) -> None:
        """Apply the named theme to the application."""
        spec = _theme_spec(theme_name)
        self._application.setPalette(_build_palette(spec.tokens))
        stylesheet = _load_stylesheet()
        if stylesheet is not None:
            self._application.setStyleSheet(_substitute(stylesheet, spec))


def _theme_spec(theme_name: str) -> ThemeSpec:
    """Look up a theme spec, raising a clear error for unknown names."""
    try:
        return THEMES[theme_name]
    except KeyError:
        raise ValueError(f"Unknown theme: {theme_name!r}") from None


def _build_palette(tokens: ThemeTokens) -> QPalette:
    """Build a QPalette from the theme's color tokens."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens.window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens.base))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens.alternate))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens.tooltip_bg))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens.tooltip_text))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens.text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens.placeholder))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens.surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens.text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens.selection))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens.on_accent))
    palette.setColor(QPalette.ColorRole.Link, QColor(tokens.link))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(tokens.link))
    for role in _DISABLED_TEXT_ROLES:
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(tokens.disabled))
    return palette


def _load_stylesheet() -> str | None:
    """Load the base stylesheet resource, degrading gracefully on failure."""
    try:
        resource = files("dicomviewer.resources").joinpath("styles", "base.qss")
        return resource.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Could not load the base stylesheet: {}", exc)
        return None


def _substitute(stylesheet: str, spec: ThemeSpec) -> str:
    """Replace ``@token@`` placeholders with the theme's token values."""
    for key, value in spec.token_values().items():
        stylesheet = stylesheet.replace(f"@{key}@", value)
    return stylesheet
