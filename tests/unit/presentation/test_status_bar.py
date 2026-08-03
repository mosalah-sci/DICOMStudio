"""Tests for the status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from dicomviewer.presentation.widgets.status_bar import StatusBar


def test_status_bar_updates_the_theme_label(qapp: QApplication) -> None:
    bar = StatusBar("0.1.0")
    bar.set_theme("Light")
    labels = bar.findChildren(QLabel)
    assert any(label.text() == "Light" for label in labels)


def test_status_bar_shows_the_version(qapp: QApplication) -> None:
    bar = StatusBar("0.1.0")
    labels = bar.findChildren(QLabel)
    assert any(label.text() == "v0.1.0" for label in labels)
