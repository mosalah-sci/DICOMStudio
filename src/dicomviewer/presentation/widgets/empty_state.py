"""Informative empty-state widget."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.shared.constants import EMPTY_STATE_ICON_SIZE, PADDING_8


class SidebarNote(QWidget):
    """A single muted line of text for a sidebar's non-content state.

    Sidebar empty states stay visually clean: a short, unobtrusive hint
    instead of the larger onboarding empty state shown in the central area.
    """

    def __init__(self, parent: QWidget, text: str = "") -> None:
        """Build the note with the given muted hint text."""
        super().__init__(parent)
        self._label = QLabel(text, self)
        self._label.setObjectName("sidebarNote")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_8, PADDING_8, PADDING_8, PADDING_8)
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addStretch()

    def set_text(self, text: str) -> None:
        """Replace the note text."""
        self._label.setText(text)


class EmptyState(QWidget):
    """A centered icon, title, description and optional action button."""

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        *,
        title: str,
        icon_name: str | None = None,
        description: str | None = None,
        action_text: str | None = None,
        on_action: Callable[[], None] | None = None,
    ) -> None:
        """Build the empty state with the given icon, copy and action."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(PADDING_8)
        layout.addStretch()
        if icon_name is not None:
            icon_label = QLabel(self)
            icon_label.setPixmap(
                icon_provider.icon(icon_name, EMPTY_STATE_ICON_SIZE).pixmap(
                    EMPTY_STATE_ICON_SIZE, EMPTY_STATE_ICON_SIZE
                )
            )
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)
        title_label = QLabel(title, self)
        title_label.setObjectName("emptyStateTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        self._description_label: QLabel | None = None
        if description is not None:
            description_label = QLabel(description, self)
            description_label.setObjectName("emptyStateBody")
            description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            description_label.setWordWrap(True)
            layout.addWidget(description_label)
            self._description_label = description_label
        if action_text is not None and on_action is not None:
            action_button = QPushButton(action_text, self)
            action_button.setObjectName("emptyStateAction")
            action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            action_button.setToolTip("Open a folder of DICOM studies (Ctrl+O)")
            action_button.clicked.connect(on_action)
            layout.addSpacing(PADDING_8)
            layout.addWidget(action_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def set_description(self, description: str) -> None:
        """Replace the body text of the empty state."""
        if self._description_label is not None:
            self._description_label.setText(description)
