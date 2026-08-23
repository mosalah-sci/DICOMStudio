"""Tests for the measurement application state and labels."""

from __future__ import annotations

from dicomviewer.application.measurement import MeasurementCollection, measurement_label
from dicomviewer.domain.measurement import Measurement, MeasurementKind, Point


def _distance() -> Measurement:
    return Measurement(MeasurementKind.DISTANCE, (Point(0.0, 0.0), Point(3.0, 4.0)))


def test_collection_stores_measurements_per_slice() -> None:
    collection = MeasurementCollection()
    measurement = _distance()
    collection.add(0, measurement)
    collection.add(2, _distance())
    assert collection.for_slice(0) == [measurement]
    assert len(collection.for_slice(2)) == 1
    assert collection.for_slice(1) == []
    assert collection.counts() == {0: 1, 2: 1}


def test_collection_remove_exact_measurement() -> None:
    collection = MeasurementCollection()
    measurement = _distance()
    collection.add(0, measurement)
    assert collection.remove(0, measurement) is True
    assert collection.for_slice(0) == []
    assert collection.remove(0, measurement) is False


def test_collection_clear_slice_and_clear_all() -> None:
    collection = MeasurementCollection()
    collection.add(0, _distance())
    collection.add(1, _distance())
    collection.clear(0)
    assert collection.for_slice(0) == []
    assert collection.has_any()
    collection.clear_all()
    assert not collection.has_any()
    assert collection.counts() == {}


def test_measurement_at_finds_topmost_within_tolerance() -> None:
    collection = MeasurementCollection()
    near = Measurement(MeasurementKind.DISTANCE, (Point(10.0, 10.0), Point(20.0, 10.0)))
    top = Measurement(MeasurementKind.DISTANCE, (Point(11.5, 8.5), Point(21.5, 8.5)))
    collection.add(0, near)
    collection.add(0, top)
    assert collection.measurement_at(0, Point(12.0, 9.2), tolerance=1.0) is top
    assert collection.measurement_at(0, Point(10.0, 11.0), tolerance=1.0) is near
    assert collection.measurement_at(0, Point(500, 500)) is None
    assert collection.measurement_at(3, Point(15, 9)) is None


def test_measurement_at_matches_angle_rays_and_vertex() -> None:
    collection = MeasurementCollection()
    angle = Measurement(
        MeasurementKind.ANGLE,
        (Point(10.0, 10.0), Point(30.0, 10.0), Point(10.0, 30.0)),
    )
    collection.add(1, angle)
    assert collection.measurement_at(1, Point(25.0, 10.4), tolerance=0.5) is angle
    assert collection.measurement_at(1, Point(10.4, 22.0), tolerance=0.5) is angle
    assert collection.measurement_at(1, Point(11.0, 11.0), tolerance=1.5) is angle
    assert collection.measurement_at(1, Point(25.0, 25.0)) is None


def test_distance_label_uses_pixel_spacing_when_available() -> None:
    collection = MeasurementCollection(pixel_spacing=(0.5, 0.5))
    # 5 pixels along the hypotenuse at 0.5 mm per axis -> 2.5 mm.
    assert measurement_label(_distance(), collection.pixel_spacing) == "2.50 mm  (5.00 px)"


def test_distance_label_falls_back_to_pixels() -> None:
    collection = MeasurementCollection()
    assert measurement_label(_distance(), collection.pixel_spacing) == "5.00 px"


def test_angle_label_reports_degrees() -> None:
    measurement = Measurement(
        MeasurementKind.ANGLE,
        (Point(0.0, 0.0), Point(1.0, 0.0), Point(0.0, 1.0)),
    )
    assert measurement_label(measurement, None) == "90.0°"
