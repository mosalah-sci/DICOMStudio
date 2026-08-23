"""Mouse interaction for placing point, arrow and text annotations.

The tool mirrors :class:`MeasurementTool`: widget clicks are translated into
image pixel coordinates through the viewer's transform, drafts live in image
space so they survive pan/zoom, and completed annotations are emitted to the
viewer for storage. A single existing annotation can be selected for deletion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QInputDialog

from dicomviewer.domain.annotation import (
    Annotation,
    AnnotationKind,
    required_point_count,
)
from dicomviewer.domain.measurement import Point

if TYPE_CHECKING:
    from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget

_DRAFT_COLOR = QColor("#a78bfa")
_HANDLE_RADIUS = 3.0


class AnnotationTool(QObject):
    """Collects clicks on the viewer to build basic annotations."""

    commit_requested = Signal(object)  # Annotation
    removal_requested = Signal(object)  # Annotation
    selection_changed = Signal()
    changed = Signal()

    def __init__(
        self,
        viewer: ImageViewerWidget,
        text_provider: Callable[[str], str | None] | None = None,
    ) -> None:
        """Create a tool bound to ``viewer``.

        ``text_provider`` supplies the string for text annotations; it
        receives the dialog title and returns the entered label or ``None``
        when cancelled. It is injectable so tests never open a modal dialog.
        """
        super().__init__(viewer)
        self._viewer = viewer
        self._kind: AnnotationKind | None = None
        self._draft: dict[int, tuple[Point, ...]] = {}
        self._preview: Point | None = None
        self._selected: Annotation | None = None
        self._text_provider = text_provider

    @property
    def kind(self) -> AnnotationKind | None:
        """Return the active annotation kind, or ``None`` when inactive."""
        return self._kind

    def is_active(self) -> bool:
        """Return whether the tool is collecting or selecting annotations."""
        return self._kind is not None

    def activate(self, kind: AnnotationKind) -> None:
        """Start collecting ``kind`` annotations."""
        self._kind = kind
        self.reset()
        self.changed.emit()

    def deactivate(self) -> None:
        """Stop collecting and clear draft and selection."""
        self._kind = None
        self.reset()
        self.set_selected(None)
        self.changed.emit()

    def reset(self) -> None:
        """Discard any draft without changing the active kind."""
        self._draft.clear()
        self._preview = None
        self.changed.emit()

    def selected(self) -> Annotation | None:
        """Return the currently selected annotation, if any."""
        return self._selected

    def set_selected(self, annotation: Annotation | None) -> None:
        """Select ``annotation`` (or nothing) and notify listeners."""
        if self._selected is annotation:
            return
        self._selected = annotation
        self.selection_changed.emit()
        self.changed.emit()

    def has_draft(self) -> bool:
        """Return whether a partial draft exists for the current slice."""
        return bool(self._draft.get(self._viewer.current_slice))

    def handle_press(self, position: QPointF) -> None:
        """Place one point at ``position``, completing an annotation if done.

        A first press that lands near an existing annotation selects it
        instead of starting a new draft.
        """
        if self._kind is None or not self._viewer.has_image:
            return
        slice_index = self._viewer.current_slice
        image_point = self._viewer.widget_to_image(position)
        if not self.has_draft():
            hit = self._viewer.annotations.annotation_at(
                slice_index, image_point, tolerance=self._viewer.hit_tolerance_pixels()
            )
            if hit is not None:
                self.set_selected(hit)
                return
        if self._kind is AnnotationKind.TEXT:
            self._commit_text(image_point)
            return
        points = list(self._draft.get(slice_index, ()))
        points.append(image_point)
        self._preview = image_point
        if len(points) >= required_point_count(self._kind):
            tip = points[1] if self._kind is AnnotationKind.ARROW else None
            annotation = Annotation(
                kind=self._kind,
                anchor=points[0],
                tip=tip,  # type: ignore[arg-type]
            )
            self.reset()
            self.commit_requested.emit(annotation)
        else:
            self._draft[slice_index] = tuple(points)
            self.changed.emit()

    def handle_move(self, position: QPointF) -> None:
        """Move the rubber-band preview endpoint to ``position``."""
        if self._kind is None or not self.has_draft():
            return
        self._preview = self._viewer.widget_to_image(position)
        self.changed.emit()

    def handle_right_press(self, position: QPointF) -> bool:
        """Handle a right click; return whether it was consumed.

        Priority: cancel the running draft, request removal of the hit
        annotation, then deselect. An unconsumed click lets the viewer fall
        back to its default right-button behaviour.
        """
        if self._kind is None:
            return False
        if self.has_draft():
            self.reset()
            return True
        hit = self._viewer.annotations.annotation_at(
            self._viewer.current_slice,
            self._viewer.widget_to_image(position),
            tolerance=self._viewer.hit_tolerance_pixels(),
        )
        if hit is not None:
            self.removal_requested.emit(hit)
            return True
        if self._selected is not None:
            self.set_selected(None)
            return True
        return False

    def delete_selected(self) -> bool:
        """Request removal of the selection; return whether one existed."""
        if self._selected is None:
            return False
        annotation = self._selected
        self.set_selected(None)
        self.removal_requested.emit(annotation)
        return True

    def draft_points(self) -> tuple[Point, ...]:
        """Return the draft points placed on the current slice."""
        return self._draft.get(self._viewer.current_slice, ())

    def preview_point(self) -> Point | None:
        """Return the preview endpoint following the pointer, if any."""
        return self._preview

    def paint(self, painter: QPainter) -> None:
        """Draw the in-progress draft with its preview segment."""
        widgets = [self._viewer.image_to_widget(point) for point in self.draft_points()]
        preview = self.preview_point()
        if preview is not None:
            widgets.append(self._viewer.image_to_widget(preview))
        if not widgets:
            return
        painter.save()
        painter.setPen(QPen(_DRAFT_COLOR, 1.5))
        painter.setBrush(_DRAFT_COLOR)
        placed = widgets[:-1] if preview is not None else widgets
        for point in placed:
            painter.drawEllipse(point, _HANDLE_RADIUS, _HANDLE_RADIUS)
        if len(widgets) >= 2:
            painter.setPen(QPen(_DRAFT_COLOR, 1.0, Qt.PenStyle.DashLine))
            painter.drawPolyline(QPolygonF(widgets))
        painter.restore()

    def _commit_text(self, anchor: Point) -> None:
        """Prompt for a label and emit the finished text annotation."""
        title = "Text annotation"
        text = self._text_provider(title) if self._text_provider else self._ask_text(title)
        if text:
            self.commit_requested.emit(
                Annotation(kind=AnnotationKind.TEXT, anchor=anchor, text=text)
            )

    def _ask_text(self, title: str) -> str | None:
        """Ask for annotation text through a modal input dialog."""
        text, accepted = QInputDialog.getText(self._viewer, title, "Label:")
        if not accepted:
            return None
        stripped = text.strip()
        return stripped or None
