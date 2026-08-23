"""Orientation behaviour of the image viewer widget."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.domain.measurement import Point
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _series(count: int = 1) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _viewer() -> ImageViewerWidget:
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )
    viewer.resize(80, 60)
    viewer.load_series(_series())
    return viewer


def test_identity_orientation_round_trips_coordinates(qapp) -> None:
    del qapp
    viewer = _viewer()
    point = QPointF(40.0, 30.0)
    image_point = viewer.widget_to_image(point)
    assert viewer.image_to_widget(image_point) == point


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotation_keeps_widget_points_stable(qapp, rotation: int) -> None:
    del qapp
    viewer = _viewer()
    for _ in range(rotation // 90):
        viewer.rotate_cw()
    assert viewer.viewport.rotation == rotation
    widget_point = QPointF(40.0, 30.0)
    image_point = viewer.widget_to_image(widget_point)
    mapped_back = viewer.image_to_widget(image_point)
    assert mapped_back.x() == pytest.approx(widget_point.x())
    assert mapped_back.y() == pytest.approx(widget_point.y())


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("flip", ["h", "v", "both"])
def test_orientation_coordinate_round_trip(qapp, rotation: int, flip: str) -> None:
    del qapp
    viewer = _viewer()
    for _ in range(rotation // 90):
        viewer.rotate_cw()
    if flip in ("h", "both"):
        viewer.flip_horizontally()
    if flip in ("v", "both"):
        viewer.flip_vertically()
    # A grid of interior image points must map to the widget and back
    # consistently; edge coordinates are clamped to the last pixel index.
    for x in (0.25, 3.5, 6.75):
        for y in (0.25, 2.5, 4.75):
            widget = viewer.image_to_widget(Point(x, y))
            recovered = viewer.widget_to_image(widget)
            assert recovered.x == pytest.approx(x), (rotation, flip, x, y)
            assert recovered.y == pytest.approx(y), (rotation, flip, x, y)


def test_rotation_swaps_the_target_rect_aspect(qapp) -> None:
    del qapp
    viewer = _viewer()
    upright = viewer._target_rect(viewer._qimage)
    assert upright.width() == pytest.approx(80.0)
    assert upright.height() == pytest.approx(60.0)
    viewer.rotate_cw()
    rotated = viewer._target_rect(viewer._qimage)
    assert rotated.width() == pytest.approx(45.0)  # min(80/6, 60/8)=7.5 * 6
    assert rotated.height() == pytest.approx(60.0)


def test_reset_view_clears_orientation(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer.rotate_cw()
    viewer.flip_horizontally()
    viewer.toggle_invert()
    viewer.reset_view()
    assert viewer.viewport.has_identity_orientation()


def test_toggle_invert_rerenders_the_frame(qapp) -> None:
    renderer = FakeViewRenderer()
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        renderer,
        analyzer=FakeImageAnalyzer(),
    )
    viewer.load_series(_series())
    calls = len(renderer.calls)
    viewer.rotate_cw()
    assert len(renderer.calls) == calls  # rotation is paint-time only
    viewer.toggle_invert()
    assert len(renderer.calls) == calls + 1
