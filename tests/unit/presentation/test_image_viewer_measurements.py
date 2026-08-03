"""Tests for measurement interaction in the image viewer widget."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.application.viewing import PixelArray
from dicomviewer.domain.measurement import MeasurementKind, Point
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import FitMode
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _series(count: int = 3) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _viewer(
    decoder: FakePixelDecoder | None = None,
    renderer: FakeViewRenderer | None = None,
    analyzer: FakeImageAnalyzer | None = None,
) -> ImageViewerWidget:
    viewer = ImageViewerWidget(
        None,
        decoder or FakePixelDecoder(),
        renderer or FakeViewRenderer(),
        analyzer=analyzer or FakeImageAnalyzer(),
    )
    viewer.resize(400, 300)
    viewer.load_series(_series())
    return viewer


def _click(viewer: ImageViewerWidget, button: Qt.MouseButton, x: int, y: int) -> None:
    QTest.mouseClick(viewer, button, pos=QPoint(x, y))


def test_measure_mode_activation_signals(qapp) -> None:
    viewer = _viewer()
    modes: list[object] = []
    viewer.measure_mode_changed.connect(modes.append)
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    assert viewer.measure_mode is MeasurementKind.DISTANCE
    viewer.set_measure_mode(None)
    assert viewer.measure_mode is None
    assert modes == [MeasurementKind.DISTANCE, None]


def test_two_clicks_store_a_distance_measurement_in_image_coordinates(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    measurements = viewer.measurements.for_slice(0)
    assert len(measurements) == 1
    assert measurements[0].kind is MeasurementKind.DISTANCE
    # The image is 8x6 pixels shown at scale 50: widget (x, y) -> image (x/50, y/50).
    assert measurements[0].points == (Point(2.0, 2.0), Point(4.0, 3.0))


def test_three_clicks_store_an_angle_measurement(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.ANGLE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 200)
    measurements = viewer.measurements.for_slice(0)
    assert len(measurements) == 1
    assert measurements[0].kind is MeasurementKind.ANGLE
    assert len(measurements[0].points) == 3


def test_measurements_changed_emits_on_commit(qapp) -> None:
    viewer = _viewer()
    changed: list[object] = []
    viewer.measurements_changed.connect(changed.append)
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    assert changed and changed[-1].has_any()


def test_measurements_are_stored_per_slice(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    assert len(viewer.measurements.for_slice(0)) == 1
    viewer.set_slice(1)
    assert viewer.measurements.for_slice(1) == []
    viewer.set_slice(0)
    assert len(viewer.measurements.for_slice(0)) == 1


def test_measure_clicks_do_not_pan(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    assert viewer.viewport.fit_mode == FitMode.FIT
    assert viewer.viewport.pan_x == 0.0
    assert viewer.viewport.pan_y == 0.0


def test_measure_mode_still_allows_slice_navigation(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    viewer.next_slice()
    assert viewer.current_slice == 1


def test_right_click_cancels_the_draft(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.ANGLE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    assert len(viewer._measure_tool.draft_points()) == 1
    _click(viewer, Qt.MouseButton.RightButton, 150, 120)
    assert viewer._measure_tool.draft_points() == []


def test_escape_exits_measure_mode(qapp) -> None:
    viewer = _viewer()
    modes: list[object] = []
    viewer.measure_mode_changed.connect(modes.append)
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer.measure_mode is None
    assert modes[-1] is None


def test_remove_measurement_removes_one(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    measurement = viewer.measurements.for_slice(0)[0]
    viewer.remove_measurement(measurement)
    assert viewer.measurements.for_slice(0) == []
    assert not viewer.measurements.has_any()


def test_clear_measurements_removes_everything(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    for _ in range(2):
        _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
        _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    viewer.set_slice(1)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    assert viewer.measurements.counts() == {0: 2, 1: 1}
    viewer.clear_measurements()
    assert not viewer.measurements.has_any()


def test_loading_a_new_series_resets_measurements(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    assert viewer.measurements.has_any()
    viewer.load_series(_series())
    assert not viewer.measurements.has_any()


def test_clear_resets_measurements_and_mode(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    _click(viewer, Qt.MouseButton.LeftButton, 100, 100)
    _click(viewer, Qt.MouseButton.LeftButton, 200, 150)
    viewer.clear()
    assert not viewer.measurements.has_any()
    assert viewer.measure_mode is None


def test_coordinate_round_trip_maps_image_to_widget_and_back(qapp) -> None:
    viewer = _viewer()
    point = Point(3.5, 2.5)
    position = viewer.image_to_widget(point)
    assert viewer.widget_to_image(position) == point


def test_pixel_spacing_flows_from_the_decoder(qapp) -> None:
    pixels = PixelArray(
        pixels=np.zeros((6, 8), dtype=np.uint16),
        width=8,
        height=6,
        pixel_spacing=(0.5, 0.5),
    )
    viewer = _viewer(decoder=FakePixelDecoder(pixels=pixels))
    assert viewer.measurements.pixel_array is not None
    assert viewer.measurements.pixel_array.pixel_spacing == (0.5, 0.5)


def test_measurement_tool_remains_active_across_slices(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    viewer.set_slice(2)
    assert viewer.measure_mode is MeasurementKind.DISTANCE
