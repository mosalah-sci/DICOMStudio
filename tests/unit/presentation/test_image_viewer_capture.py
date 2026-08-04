"""Tests for capturing the current viewport as an exportable image."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.domain.measurement import MeasurementKind
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _series(count: int = 3) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _viewer() -> ImageViewerWidget:
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )
    viewer.resize(400, 300)
    viewer.load_series(_series())
    return viewer


def test_capture_returns_viewport_sized_image(qapp) -> None:
    viewer = _viewer()
    capture = viewer.capture_view()
    assert capture.width == 400
    assert capture.height == 300
    assert capture.validate()


def test_capture_requires_a_loaded_image(qapp) -> None:
    viewer = ImageViewerWidget(
        None, FakePixelDecoder(), FakeViewRenderer(), analyzer=FakeImageAnalyzer()
    )
    with pytest.raises(ValueError):
        viewer.capture_view()


def test_capture_preserves_measurement_overlays(qapp) -> None:
    viewer = _viewer()
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(200, 150))
    capture = viewer.capture_view()
    # The measurement is drawn in cyan (#22d3ee) over the white frame.
    assert _contains_colour(capture.data, (34, 211, 238))


def test_capture_uses_the_configured_measurement_colour(qapp) -> None:
    viewer = _viewer()
    viewer.set_measurement_color("#ff0000")
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(200, 150))
    capture = viewer.capture_view()
    assert _contains_colour(capture.data, (255, 0, 0))


def test_capture_matches_the_current_viewport(qapp) -> None:
    viewer = _viewer()
    fitted = viewer.capture_view()
    viewer.zoom_in()
    zoomed = viewer.capture_view()
    assert fitted.data != zoomed.data


def _contains_colour(data: bytes, target: tuple[int, int, int], tolerance: int = 60) -> bool:
    # RenderedImage payloads are ARGB32 bytes (B, G, R, A), so compare the
    # three colour channels as an unordered set to be channel-order agnostic.
    expected = sorted(target)
    for index in range(0, len(data), 4):
        channels = sorted((data[index], data[index + 1], data[index + 2]))
        if all(abs(a - b) <= tolerance for a, b in zip(channels, expected, strict=True)):
            return True
    return False
