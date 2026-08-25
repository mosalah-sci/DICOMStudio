"""Geometry tests for the extracted viewer transform helpers.

These pin the observable coordinate/scale behavior of the pure functions
in :mod:`dicomviewer.presentation.widgets.viewer_transform` — the same math
the widget applies at paint time. Widget-level round-trips under rotation
and flip remain covered by ``test_image_viewer_orientation.py``.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from dicomviewer.domain.measurement import DEFAULT_HIT_TOLERANCE, Point
from dicomviewer.domain.viewport import FitMode, Viewport
from dicomviewer.presentation.widgets import viewer_transform as vt

WIDGET_W = 80.0
WIDGET_H = 60.0


def _viewport(**overrides) -> Viewport:
    overrides.setdefault("fit_mode", FitMode.FIT)
    return Viewport(**overrides)


def _frame(viewport: Viewport, width: int = 8, height: int = 6):
    return (
        viewport,
        width,
        height,
        WIDGET_W,
        WIDGET_H,
    )


def test_fit_scale_uses_the_limiting_axis() -> None:
    # 8x6 image in an 80x60 widget: height is limiting (60/6 == 80/8), so the
    # scale is exactly 10.0; a taller image makes width the limiter.
    assert vt.effective_scale(*_frame(_viewport())) == pytest.approx(10.0)
    assert vt.effective_scale(*_frame(_viewport(), width=4, height=12)) == pytest.approx(5.0)


def test_actual_and_free_scale_modes() -> None:
    actual = _viewport(fit_mode=FitMode.ACTUAL)
    assert vt.effective_scale(*_frame(actual)) == 1.0
    free = _viewport(fit_mode=FitMode.FREE, zoom=3.5)
    assert vt.effective_scale(*_frame(free)) == 3.5


def test_rotation_swaps_display_size_for_scale() -> None:
    rotated = _viewport(rotation=90)
    # Display size becomes 6x8, so height (60/8) is now the limiter.
    assert vt.effective_scale(*_frame(rotated)) == pytest.approx(7.5)


def test_degenerate_display_size_falls_back_to_identity() -> None:
    assert vt.effective_scale(*_frame(_viewport(), width=0, height=0)) == 1.0


def test_target_rect_is_centered_and_scaled() -> None:
    rect = vt.target_rect(*_frame(_viewport()))
    assert rect.width() == pytest.approx(80.0)
    assert rect.height() == pytest.approx(60.0)
    assert rect.left() == pytest.approx(0.0)
    assert rect.top() == pytest.approx(0.0)
    assert rect.center().x() == pytest.approx(40.0)
    assert rect.center().y() == pytest.approx(30.0)


def test_pan_shifts_the_target_rect_center() -> None:
    viewport = _viewport(fit_mode=FitMode.FREE, zoom=1.0, pan_x=10.0, pan_y=-5.0)
    rect = vt.target_rect(viewport, 8, 6, WIDGET_W, WIDGET_H)
    assert rect.center().x() == pytest.approx(50.0)
    assert rect.center().y() == pytest.approx(25.0)


def test_widget_to_image_maps_the_widget_center_to_image_center() -> None:
    # The mapping is proportional over [0, width] / [0, height], so the
    # widget center lands on width/2 and height/2.
    point = vt.widget_to_image(*_frame(_viewport()), QPointF(40.0, 30.0))
    assert point.x == pytest.approx(4.0)
    assert point.y == pytest.approx(3.0)


def test_widget_to_image_clamps_to_the_last_pixel_index() -> None:
    bottom_right = vt.widget_to_image(*_frame(_viewport()), QPointF(500.0, 500.0))
    assert (bottom_right.x, bottom_right.y) == (7.0, 5.0)
    top_left = vt.widget_to_image(*_frame(_viewport()), QPointF(-500.0, -500.0))
    assert (top_left.x, top_left.y) == (0.0, 0.0)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("flip_h", [False, True])
@pytest.mark.parametrize("flip_v", [False, True])
def test_widget_image_round_trip_survives_any_orientation(
    rotation: int, flip_h: bool, flip_v: bool
) -> None:
    viewport = _viewport(
        rotation=rotation,
        fit_mode=FitMode.FREE,
        zoom=2.0,
        pan_x=3.0,
        flip_h=flip_h,
        flip_v=flip_v,
    )
    # Interior points only: continuous coordinates clamp to the last pixel
    # index (width-1 / height-1), matching the widget mapping contract.
    for image_x in (0.25, 4.0, 6.75):
        for image_y in (0.25, 3.0, 4.75):
            widget = vt.image_to_widget(viewport, 8, 6, WIDGET_W, WIDGET_H, Point(image_x, image_y))
            recovered = vt.widget_to_image(viewport, 8, 6, WIDGET_W, WIDGET_H, widget)
            assert recovered.x == pytest.approx(image_x)
            assert recovered.y == pytest.approx(image_y)


def test_rotated_mapping_moves_the_expected_corner() -> None:
    # 90-degree rotation: display size becomes 6x8, fit scale is min(80/6,
    # 60/8) = 7.5, so the rect is 45x60 at left=17.5. The image top-left
    # corner maps to display (6, 0), i.e. widget x = 17.5 + 6*7.5 = 62.5.
    viewport = _viewport(rotation=90)
    corner = vt.image_to_widget(viewport, 8, 6, WIDGET_W, WIDGET_H, Point(0.0, 0.0))
    assert corner.x() == pytest.approx(62.5)
    assert corner.y() == pytest.approx(0.0)


def test_degenerate_widget_returns_safe_values() -> None:
    collapsed = vt.widget_to_image(_viewport(), 8, 6, 0.0, 0.0, QPointF(40.0, 30.0))
    assert (collapsed.x, collapsed.y) == (0.0, 0.0)
    rect_point = vt.image_to_widget(_viewport(), 8, 6, 0.0, 0.0, Point(1.0, 1.0))
    assert rect_point.x() == 0.0 and rect_point.y() == 0.0


def test_hit_tolerance_defaults_on_non_positive_scale() -> None:
    assert vt.hit_tolerance(0.0) == DEFAULT_HIT_TOLERANCE
    assert vt.hit_tolerance(-1.0) == DEFAULT_HIT_TOLERANCE


def test_hit_tolerance_converts_and_clamps() -> None:
    assert vt.hit_tolerance(4.0) == pytest.approx(2.0)  # inside the band
    assert vt.hit_tolerance(2.0) == pytest.approx(4.0)  # inside the band
    assert vt.hit_tolerance(0.1) == pytest.approx(vt._MAX_HIT_TOLERANCE)  # zoomed far out
    assert vt.hit_tolerance(100.0) == pytest.approx(1.0)  # extreme zoom clamps to the floor
