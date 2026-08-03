"""Mouse interaction for building distance and angle measurements.

The tool translates widget clicks into image pixel coordinates through the
viewer's transform, keeps a per-slice set of placed points plus a preview
point that follows the pointer, and emits a :class:`Measurement` when enough
points have been placed. All state lives in image space so it survives pan,
zoom and window changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from dicomviewer.domain.measurement import (
    Measurement,
    MeasurementKind,
    Point,
    required_point_count,
)

if TYPE_CHECKING:
    from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


class MeasurementTool(QObject):
    """Collects points on the viewer to build distance and angle measurements."""

    commit_requested = Signal(object)
    changed = Signal()

    def __init__(self, viewer: ImageViewerWidget) -> None:
        """Create a tool bound to ``viewer``."""
        super().__init__(viewer)
        self._viewer = viewer
        self._kind: MeasurementKind | None = None
        self._draft: dict[int, list[Point]] = {}
        self._preview: Point | None = None

    @property
    def kind(self) -> MeasurementKind | None:
        """Return the active measurement kind, or ``None`` when inactive."""
        return self._kind

    def is_active(self) -> bool:
        """Return whether the tool is collecting points."""
        return self._kind is not None

    def activate(self, kind: MeasurementKind) -> None:
        """Start collecting a ``kind`` measurement."""
        self._kind = kind
        self._draft.clear()
        self._preview = None
        self.changed.emit()

    def deactivate(self) -> None:
        """Stop collecting and discard any draft."""
        self._kind = None
        self._draft.clear()
        self._preview = None
        self.changed.emit()

    def reset(self) -> None:
        """Discard all drafts without changing the active kind."""
        self._draft.clear()
        self._preview = None
        self.changed.emit()

    def draft_points(self) -> list[Point]:
        """Return the placed points for the current slice."""
        return list(self._draft.get(self._viewer.current_slice, []))

    def preview_point(self) -> Point | None:
        """Return the pointer position preview for the current slice, if any."""
        return self._preview

    def handle_press(self, position: QPointF) -> None:
        """Place one point at ``position``, completing a measurement if done."""
        if self._kind is None or not self._viewer.has_image:
            return
        slice_index = self._viewer.current_slice
        points = self._draft.setdefault(slice_index, [])
        points.append(self._viewer.widget_to_image(position))
        self._preview = self._viewer.widget_to_image(position)
        if len(points) >= required_point_count(self._kind):
            self._draft[slice_index] = []
            self._preview = None
            self.commit_requested.emit(Measurement(self._kind, tuple(points)))
        self.changed.emit()

    def handle_move(self, position: QPointF) -> None:
        """Move the preview point to ``position``."""
        if self._kind is None:
            return
        points = self._draft.get(self._viewer.current_slice, [])
        if not points or len(points) >= required_point_count(self._kind):
            return
        self._preview = self._viewer.widget_to_image(position)
        self.changed.emit()

    def cancel_draft(self) -> None:
        """Discard the in-progress draft for the current slice."""
        slice_index = self._viewer.current_slice
        if self._draft.get(slice_index):
            self._draft[slice_index] = []
        self._preview = None
        self.changed.emit()

    def paint(self, painter: QPainter) -> None:
        """Draw the placed points, preview and connecting lines."""
        points = list(self.draft_points())
        if self._preview is not None:
            points.append(self._preview)
        if not points:
            return
        widgets = [self._viewer.image_to_widget(point) for point in points]
        painter.save()
        painter.setPen(QPen(QColor("#ffe066"), 1.5))
        painter.setBrush(QColor("#ffe066"))
        for point in widgets:
            painter.drawEllipse(point, 3.0, 3.0)
        if len(widgets) >= 2:
            painter.setPen(QPen(QColor("#ffe066"), 1.0, Qt.PenStyle.DashLine))
            painter.drawPolyline(QPolygonF(widgets))
        painter.restore()
