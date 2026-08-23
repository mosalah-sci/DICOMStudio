"""Annotation domain model and geometry.

Pure data and math for basic image annotations. Annotations are stored in
image pixel coordinates so they stay independent of the viewport transform,
exactly like measurements. No GUI or DICOM dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from dicomviewer.domain.measurement import DEFAULT_HIT_TOLERANCE, Point


class AnnotationKind(StrEnum):
    """The supported kinds of annotation."""

    POINT = "point"
    ARROW = "arrow"
    TEXT = "text"


_POINT_COUNTS: dict[AnnotationKind, int] = {
    AnnotationKind.POINT: 1,
    AnnotationKind.ARROW: 2,
    AnnotationKind.TEXT: 1,
}


@dataclass(frozen=True)
class Annotation:
    """One completed annotation.

    A point annotation has an ``anchor`` only; an arrow annotation points
    from ``anchor`` to ``tip``; a text annotation renders ``text`` at
    ``anchor`` and carries no tip.
    """

    kind: AnnotationKind
    anchor: Point
    tip: Point | None = None
    text: str = ""

    def __post_init__(self) -> None:
        """Validate that the payload matches the annotation kind."""
        expected = _POINT_COUNTS.get(self.kind)
        if expected is None:
            raise ValueError(f"Unknown annotation kind: {self.kind!r}")
        if self.kind is AnnotationKind.ARROW:
            if self.tip is None:
                raise ValueError("Arrow annotations require a tip point")
        elif self.tip is not None:
            raise ValueError(f"{self.kind.value} annotations do not accept a tip")
        if self.kind is AnnotationKind.TEXT and not self.text.strip():
            raise ValueError("Text annotations require non-empty text")
        if self.kind is not AnnotationKind.TEXT and self.text:
            raise ValueError(f"{self.kind.value} annotations do not accept text")


def required_point_count(kind: AnnotationKind) -> int:
    """Return the number of clicks a ``kind`` annotation needs."""
    expected = _POINT_COUNTS.get(kind)
    if expected is None:
        raise ValueError(f"Unknown annotation kind: {kind!r}")
    return expected


def distance_to_segment(point: Point, start: Point, end: Point) -> float:
    """Return the Euclidean distance from ``point`` to the segment."""
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return point.distance_to(start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    clamped = min(max(t, 0.0), 1.0)
    nearest = Point(start.x + clamped * dx, start.y + clamped * dy)
    return point.distance_to(nearest)


def distance_to_annotation(annotation: Annotation, point: Point) -> float:
    """Return the hit-test distance from ``point`` to ``annotation``.

    Points and text anchors are matched by proximity to their anchor;
    arrows are matched by proximity to the shaft or either endpoint.
    """
    if annotation.kind is AnnotationKind.ARROW and annotation.tip is not None:
        return min(
            point.distance_to(annotation.anchor),
            point.distance_to(annotation.tip),
            distance_to_segment(point, annotation.anchor, annotation.tip),
        )
    return point.distance_to(annotation.anchor)


def annotation_at(
    annotations: list[Annotation],
    point: Point,
    tolerance: float = DEFAULT_HIT_TOLERANCE,
) -> Annotation | None:
    """Return the first annotation within ``tolerance`` of ``point``.

    Later annotations win over earlier ones because they are drawn on top,
    so the search runs from the end of the list backwards.
    """
    for annotation in reversed(annotations):
        if distance_to_annotation(annotation, point) <= tolerance:
            return annotation
    return None


def arrowhead_points(anchor: Point, tip: Point, head_length: float) -> tuple[Point, Point]:
    """Return the two base corners of an arrowhead pointing into ``tip``.

    The corners are placed perpendicular to the shaft at ``head_length``
    behind ``tip``, which lets the painter draw a solid triangular head in
    widget space without trigonometry beyond two atan2 calls here.
    """
    angle = math.atan2(tip.y - anchor.y, tip.x - anchor.x)
    spread = math.atan2(head_length, head_length * 2.0)
    left = Point(
        tip.x - head_length * math.cos(angle - spread),
        tip.y - head_length * math.sin(angle - spread),
    )
    right = Point(
        tip.x - head_length * math.cos(angle + spread),
        tip.y - head_length * math.sin(angle + spread),
    )
    return left, right
