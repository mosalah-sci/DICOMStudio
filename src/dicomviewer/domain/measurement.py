"""Measurement domain model and geometry.

Pure data and math for distance and angle measurements. Measurements are
stored in image pixel coordinates so they stay independent of the viewport
transform; physical distances are derived using the DICOM pixel spacing when
available. No GUI or DICOM dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Point:
    """A point in image pixel coordinates."""

    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        """Return the Euclidean distance to ``other`` in pixels."""
        return math.hypot(self.x - other.x, self.y - other.y)


class MeasurementKind(StrEnum):
    """The supported kinds of measurement."""

    DISTANCE = "distance"
    ANGLE = "angle"


_POINT_COUNTS: dict[MeasurementKind, int] = {
    MeasurementKind.DISTANCE: 2,
    MeasurementKind.ANGLE: 3,
}


@dataclass(frozen=True)
class Measurement:
    """One completed measurement with its defining points.

    A distance measurement has two points (start, end); an angle measurement
    has three (vertex, point on the first ray, point on the second ray).
    """

    kind: MeasurementKind
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        """Validate that the point count matches the measurement kind."""
        expected = _POINT_COUNTS.get(self.kind)
        if expected is None:
            raise ValueError(f"Unknown measurement kind: {self.kind!r}")
        if len(self.points) != expected:
            raise ValueError(
                f"{self.kind.value} measurements require {expected} points, "
                f"got {len(self.points)}"
            )


def required_point_count(kind: MeasurementKind) -> int:
    """Return the number of points a ``kind`` measurement needs."""
    expected = _POINT_COUNTS.get(kind)
    if expected is None:
        raise ValueError(f"Unknown measurement kind: {kind!r}")
    return expected


def _require_kind(measurement: Measurement, kind: MeasurementKind) -> None:
    """Reject a measurement of the wrong kind with a clear error."""
    if measurement.kind is not kind:
        raise ValueError(f"Expected a {kind.value} measurement, got {measurement.kind.value}")


def distance_pixels(measurement: Measurement) -> float:
    """Return the length of a distance measurement in pixels."""
    _require_kind(measurement, MeasurementKind.DISTANCE)
    start, end = measurement.points
    return start.distance_to(end)


def distance_with_spacing(
    measurement: Measurement,
    row_spacing: float,
    column_spacing: float,
) -> float:
    """Return the physical length of a distance measurement.

    DICOM pixel spacing gives the distance between adjacent rows (``dy``) and
    columns (``dx``) in millimetres, so the pixel deltas are scaled per axis.
    """
    _require_kind(measurement, MeasurementKind.DISTANCE)
    start, end = measurement.points
    dx = (end.x - start.x) * column_spacing
    dy = (end.y - start.y) * row_spacing
    return math.hypot(dx, dy)


def angle_degrees(measurement: Measurement) -> float:
    """Return the smaller angle between the two rays, in degrees."""
    _require_kind(measurement, MeasurementKind.ANGLE)
    vertex, ray1, ray2 = measurement.points
    angle1 = math.atan2(ray1.y - vertex.y, ray1.x - vertex.x)
    angle2 = math.atan2(ray2.y - vertex.y, ray2.x - vertex.x)
    difference = abs(angle1 - angle2)
    if difference > math.pi:
        difference = 2.0 * math.pi - difference
    return math.degrees(difference)
