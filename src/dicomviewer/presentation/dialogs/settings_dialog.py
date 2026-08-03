"""Settings dialog."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.presentation.theme.themes import THEMES
from dicomviewer.shared.constants import PADDING_12, PADDING_16


class SettingsDialog(QDialog):
    """Exposes configuration options to the user.

    Milestone 2 ships the dialog shell with the appearance group; theme
    changes apply immediately through the injected callback.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        current_theme: str,
        on_theme_changed: Callable[[str], None],
    ) -> None:
        """Build the dialog for the given theme state and change callback."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(360)

        self._theme_names = list(THEMES)
        self._on_theme_changed = on_theme_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_16, PADDING_16, PADDING_16, PADDING_16)
        layout.setSpacing(PADDING_12)

        appearance_group = QGroupBox("Appearance", self)
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        self._theme_combo = QComboBox(appearance_group)
        for theme_name in self._theme_names:
            self._theme_combo.addItem(THEMES[theme_name].display_name)
        self._theme_combo.setCurrentIndex(self._theme_names.index(current_theme))
        self._theme_combo.currentIndexChanged.connect(self._notify_theme_changed)
        appearance_layout.addRow("Theme", self._theme_combo)
        hint = QLabel("Changes apply immediately.", appearance_group)
        hint.setObjectName("emptyStateBody")
        appearance_layout.addRow("", hint)
        layout.addWidget(appearance_group)

        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _notify_theme_changed(self, index: int) -> None:
        """Forward the newly selected theme to the caller."""
        self._on_theme_changed(self._theme_names[index])
