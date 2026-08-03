"""Metadata panel dock widget."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.empty_state import EmptyState
from dicomviewer.shared.constants import PADDING_12


class MetadataPanel(QWidget):
    """Right sidebar hosting DICOM metadata inspection.

    Milestone 2 ships the panel shell with an informative empty state; the
    metadata browser is added by a later milestone.
    """

    def __init__(self, parent: QWidget, icon_provider: IconProvider) -> None:
        """Build the panel with its empty state."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        layout.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="info",
                title="No metadata available",
                description="Select a series to inspect its DICOM metadata.",
            )
        )
