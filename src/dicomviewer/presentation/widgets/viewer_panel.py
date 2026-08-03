"""Central image viewer panel."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.empty_state import EmptyState


class ViewerPanel(QWidget):
    """Primary workspace where medical images are displayed.

    The viewer keeps the near-black imaging background from day one; rendering
    arrives with the image viewer milestone.
    """

    def __init__(self, parent: QWidget, icon_provider: IconProvider) -> None:
        """Build the viewer area with its empty state."""
        super().__init__(parent)
        self.setObjectName("viewerPanel")
        layout = QVBoxLayout(self)
        layout.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="activity",
                title="No study loaded",
                description="Open a folder to begin examining DICOM studies.",
            )
        )
