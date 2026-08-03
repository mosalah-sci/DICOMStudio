"""Informative empty-state widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.shared.constants import EMPTY_STATE_ICON_SIZE, PADDING_8


class EmptyState(QWidget):
    """A centered icon, title and description used before content exists."""

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        *,
        title: str,
        icon_name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Build the empty state with the given icon and copy."""
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
        if description is not None:
            description_label = QLabel(description, self)
            description_label.setObjectName("emptyStateBody")
            description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            description_label.setWordWrap(True)
            layout.addWidget(description_label)
        layout.addStretch()
