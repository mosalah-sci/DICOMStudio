"""Tests for the measurement domain model."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from dicomviewer.domain.measurement import (
    Measurement,
    MeasurementKind,
    Point,
    angle_degrees,
    distance_pixels,
    distance_with_spacing,
    required_point_count,
)


def test_distance_measurement_requires_two_points() -> None:
    measurement = Measurement(MeasurementKind.DISTANCE, (Point(0.0, 0.0), Point(3.0, 4.0)))
    assert required_point_count(MeasurementKind.DISTANCE) == 2
    assert measurement.kind is MeasurementKind.DISTANCE


def test_angle_measurement_requires_three_points() -> None:
    vertex = Point(0.0, 0.0)
    measurement = Measurement(MeasurementKind.ANGLE, (vertex, Point(1.0, 0.0), Point(0.0, 1.0)))
    assert required_point_count(MeasurementKind.ANGLE) == 3
    assert measurement.kind is MeasurementKind.ANGLE


@pytest.mark.parametrize(
    "kind, points",
    [
        (MeasurementKind.DISTANCE, (Point(0.0, 0.0),)),
        (MeasurementKind.DISTANCE, (Point(0.0, 0.0), Point(1.0, 1.0), Point(2.0, 2.0))),
        (MeasurementKind.ANGLE, (Point(0.0, 0.0), Point(1.0, 0.0))),
        (MeasurementKind.ANGLE, ()),
    ],
)
def test_measurement_rejects_wrong_point_counts(
    kind: MeasurementKind,
    points: tuple[Point, ...],
) -> None:
    with pytest.raises(ValueError):
        Measurement(kind, points)


def test_distance_pixels_is_euclidean() -> None:
    measurement = Measurement(MeasurementKind.DISTANCE, (Point(1.0, 1.0), Point(4.0, 5.0)))
    assert distance_pixels(measurement) == pytest.approx(5.0)


def test_distance_pixels_of_zero_length() -> None:
    measurement = Measurement(MeasurementKind.DISTANCE, (Point(2.0, 3.0), Point(2.0, 3.0)))
    assert distance_pixels(measurement) == 0.0


def test_distance_with_spacing_scales_each_axis() -> None:
    measurement = Measurement(MeasurementKind.DISTANCE, (Point(0.0, 0.0), Point(2.0, 2.0)))
    # 2 pixels along x at 0.5 mm and 2 pixels along y at 1.0 mm.
    assert distance_with_spacing(measurement, row_spacing=1.0, column_spacing=0.5) == pytest.approx(
        math.hypot(1.0, 2.0)
    )


def test_angle_degrees_of_right_angle() -> None:
    measurement = Measurement(
        MeasurementKind.ANGLE,
        (Point(0.0, 0.0), Point(1.0, 0.0), Point(0.0, 1.0)),
    )
    assert angle_degrees(measurement) == pytest.approx(90.0)


def test_angle_degrees_returns_the_smaller_angle() -> None:
    measurement = Measurement(
        MeasurementKind.ANGLE,
        (Point(0.0, 0.0), Point(1.0, 0.0), Point(-1.0, 0.0)),
    )
    # Rays pointing in opposite directions: the smaller angle is 180 degrees.
    assert angle_degrees(measurement) == pytest.approx(180.0)


def test_angle_degrees_of_45_degrees() -> None:
    measurement = Measurement(
        MeasurementKind.ANGLE,
        (Point(0.0, 0.0), Point(1.0, 0.0), Point(1.0, 1.0)),
    )
    assert angle_degrees(measurement) == pytest.approx(45.0)


def test_measurements_are_immutable_dataclasses() -> None:
    measurement = Measurement(MeasurementKind.DISTANCE, (Point(0.0, 0.0), Point(1.0, 1.0)))
    with pytest.raises(FrozenInstanceError):
        measurement.points = ()  # type: ignore[misc]
