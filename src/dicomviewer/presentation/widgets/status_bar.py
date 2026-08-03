"""Application status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar


class StatusBar(QStatusBar):
    """Shows contextual messages plus permanent theme and version labels."""

    def __init__(self, version: str) -> None:
        """Build the status bar with the given application version."""
        super().__init__()
        self._theme_label = QLabel(self)
        self._version_label = QLabel(f"v{version}", self)
        self.addPermanentWidget(self._theme_label)
        self.addPermanentWidget(self._version_label)
        self.showMessage("Ready")

    def set_theme(self, display_name: str) -> None:
        """Update the theme indicator shown on the right side."""
        self._theme_label.setText(display_name)
