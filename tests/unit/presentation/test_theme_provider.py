"""Tests for the theme provider."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from dicomviewer.presentation.theme.theme_provider import ThemeProvider


def test_apply_dark_sets_the_palette_window_color(qapp: QApplication) -> None:
    provider = ThemeProvider(qapp)
    provider.apply("dark")
    color = qapp.palette().color(QPalette.ColorRole.Window).name()
    assert color == "#1b1b1f"


def test_apply_light_sets_a_lighter_palette(qapp: QApplication) -> None:
    provider = ThemeProvider(qapp)
    provider.apply("light")
    color = qapp.palette().color(QPalette.ColorRole.Window).name()
    assert color == "#f4f4f6"


def test_apply_sets_a_stylesheet_with_substituted_tokens(qapp: QApplication) -> None:
    provider = ThemeProvider(qapp)
    provider.apply("dark")
    stylesheet = qapp.styleSheet()
    assert "1B1B1F" in stylesheet
    assert "@window@" not in stylesheet


def test_unknown_theme_is_rejected(qapp: QApplication) -> None:
    provider = ThemeProvider(qapp)
    with pytest.raises(ValueError):
        provider.apply("neon")
    qapp.setStyleSheet("")
