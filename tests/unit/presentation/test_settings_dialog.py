"""Tests for the settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QComboBox

from dicomviewer.presentation.dialogs.settings_dialog import SettingsDialog


def test_dialog_lists_every_theme(qapp: QApplication) -> None:
    dialog = SettingsDialog(None, current_theme="dark", on_theme_changed=lambda _: None)
    combo = dialog.findChild(QComboBox)
    assert combo is not None
    assert combo.count() == 2


def test_theme_change_notifies_the_callback(qapp: QApplication) -> None:
    changes: list[str] = []
    dialog = SettingsDialog(None, current_theme="dark", on_theme_changed=changes.append)
    combo = dialog.findChild(QComboBox)
    assert combo is not None
    combo.setCurrentIndex(1)
    assert changes == ["light"]
