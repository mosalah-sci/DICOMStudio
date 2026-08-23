"""Application state for image annotations.

Mirrors :class:`MeasurementCollection`: the presentation tool completes
annotations and stores them here, per slice, in image pixel coordinates.
Pure data — no GUI or DICOM dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dicomviewer.domain.annotation import Annotation, annotation_at
from dicomviewer.domain.measurement import DEFAULT_HIT_TOLERANCE, Point


@dataclass
class AnnotationCollection:
    """Per-slice annotation storage."""

    _entries: dict[int, list[Annotation]] = field(default_factory=dict[int, list[Annotation]])

    def add(self, slice_index: int, annotation: Annotation) -> None:
        """Append an annotation to ``slice_index``."""
        self._entries.setdefault(slice_index, []).append(annotation)

    def remove(self, slice_index: int, annotation: Annotation) -> bool:
        """Remove an exact annotation; return whether it was found."""
        entries = self._entries.get(slice_index, [])
        try:
            entries.remove(annotation)
        except ValueError:
            return False
        return True

    def clear(self, slice_index: int) -> None:
        """Remove all annotations from ``slice_index``."""
        self._entries.pop(slice_index, None)

    def clear_all(self) -> None:
        """Remove every annotation from every slice."""
        self._entries.clear()

    def for_slice(self, slice_index: int) -> list[Annotation]:
        """Return the annotations stored for ``slice_index``."""
        return list(self._entries.get(slice_index, []))

    def has_any(self) -> bool:
        """Return whether any annotation exists on any slice."""
        return any(self._entries.values())

    def annotation_at(
        self,
        slice_index: int,
        point: Point,
        tolerance: float = DEFAULT_HIT_TOLERANCE,
    ) -> Annotation | None:
        """Return the topmost annotation within ``tolerance`` of ``point``."""
        return annotation_at(self._entries.get(slice_index, []), point, tolerance)
