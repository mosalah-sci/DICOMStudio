"""About dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.shared.constants import (
    APP_COPYRIGHT,
    APP_DESCRIPTION,
    EMPTY_STATE_ICON_SIZE,
    LICENSE_NAME,
    PADDING_8,
    PADDING_16,
)


class AboutDialog(QDialog):
    """Summarizes the application identity, version and license."""

    def __init__(
        self,
        parent: QWidget | None,
        icon_provider: IconProvider,
        app_name: str,
        version: str,
    ) -> None:
        """Build the dialog for the given application metadata."""
        super().__init__(parent)
        self.setWindowTitle(f"About {app_name}")
        self.setModal(True)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_16, PADDING_16, PADDING_16, PADDING_16)
        layout.setSpacing(PADDING_8)

        icon_label = QLabel(self)
        icon_label.setPixmap(
            icon_provider.icon("activity", EMPTY_STATE_ICON_SIZE).pixmap(
                EMPTY_STATE_ICON_SIZE, EMPTY_STATE_ICON_SIZE
            )
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        name_label = QLabel(app_name, self)
        name_label.setObjectName("emptyStateTitle")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        version_label = QLabel(f"Version {version}", self)
        version_label.setObjectName("emptyStateBody")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        description_label = QLabel(APP_DESCRIPTION, self)
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description_label)

        legal_label = QLabel(f"{LICENSE_NAME}\n{APP_COPYRIGHT}", self)
        legal_label.setObjectName("emptyStateBody")
        legal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(PADDING_8)
        layout.addWidget(legal_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
