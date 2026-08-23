"""Tests for the viewport state model."""

from __future__ import annotations

import pytest

from dicomviewer.domain.viewport import (
    MAX_ZOOM,
    MIN_ZOOM,
    FitMode,
    Viewport,
    clamp_slice,
    clamp_zoom,
    normalize_rotation,
    orient_point,
    oriented_size,
    unorient_point,
)


def test_initial_viewport_fits_to_window() -> None:
    viewport = Viewport.initial()
    assert viewport.fit_mode == FitMode.FIT
    assert viewport.zoom == 1.0
    assert viewport.window_center is None
    assert viewport.window_width == 0.0
    assert viewport.slice_index == 0


def test_with_zoom_clamps_to_supported_range() -> None:
    viewport = Viewport.initial()
    assert viewport.with_zoom(1000.0).zoom == MAX_ZOOM
    assert viewport.with_zoom(0.0001).zoom == MIN_ZOOM


def test_with_zoom_exits_fit_mode() -> None:
    viewport = Viewport.initial()
    assert viewport.with_zoom(2.0).fit_mode == FitMode.FREE


def test_fit_and_actual_restore_centered_scale() -> None:
    viewport = Viewport(zoom=3.0, pan_x=10.0, fit_mode=FitMode.FREE)
    assert viewport.fit().fit_mode == FitMode.FIT
    actual = viewport.actual()
    assert actual.fit_mode == FitMode.ACTUAL
    assert actual.zoom == 1.0
    assert actual.pan_x == 0.0 and actual.pan_y == 0.0


def test_with_slice_clamps_to_count() -> None:
    viewport = Viewport.initial()
    assert viewport.with_slice(99, 5).slice_index == 4
    assert viewport.with_slice(-3, 5).slice_index == 0
    assert viewport.with_slice(2, 0).slice_index == 0


def test_with_window_clamps_width_and_keeps_auto() -> None:
    viewport = Viewport.initial()
    adjusted = viewport.with_window(40.0, -5.0)
    assert adjusted.window_width == 0.0
    assert adjusted.window_center is None
    positive = viewport.with_window(40.0, 200.0)
    assert positive.window_width == 200.0
    assert positive.window_center == 40.0


def test_clamp_helpers() -> None:
    assert clamp_zoom(0.0) == MIN_ZOOM
    assert clamp_zoom(50.0) == MAX_ZOOM
    assert clamp_zoom(1.0) == 1.0
    assert clamp_slice(1, 3) == 1
    assert clamp_slice(5, 3) == 2
    assert clamp_slice(-1, 3) == 0


def test_initial_viewport_has_identity_orientation() -> None:
    viewport = Viewport.initial()
    assert viewport.rotation == 0
    assert viewport.flip_h is False
    assert viewport.flip_v is False
    assert viewport.invert is False
    assert viewport.has_identity_orientation()


def test_rotation_wraps_modulo_360() -> None:
    viewport = Viewport.initial()
    assert viewport.rotate_cw().rotation == 90
    assert viewport.rotate_cw().rotate_cw().rotation == 180
    three = viewport.rotate_cw().rotate_cw().rotate_cw()
    assert three.rotation == 270
    assert three.rotate_cw().rotation == 0
    back = viewport.rotate_ccw()
    assert back.rotation == 270
    assert back.rotate_ccw().rotation == 180


def test_flip_and_invert_toggle() -> None:
    viewport = Viewport.initial()
    assert viewport.toggle_flip_h().flip_h is True
    assert viewport.toggle_flip_v().flip_v is True
    assert viewport.toggle_invert().invert is True
    flipped_twice = viewport.toggle_flip_h().toggle_flip_h()
    assert flipped_twice.flip_h is False


def test_orientation_mutations_preserve_other_state() -> None:
    viewport = Viewport(zoom=2.5, pan_x=3.0, window_center=40.0, window_width=400.0)
    rotated = viewport.rotate_cw().toggle_flip_h().toggle_invert()
    assert (rotated.zoom, rotated.pan_x, rotated.window_center, rotated.window_width) == (
        viewport.zoom,
        viewport.pan_x,
        viewport.window_center,
        viewport.window_width,
    )
    assert not rotated.has_identity_orientation()


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [(0, 0), (90, 90), (-90, 270), (450, 90), (180, 180), (-360, 0), (-135, 180)],
)
def test_normalize_rotation(degrees: float, expected: int) -> None:
    assert normalize_rotation(degrees) == expected


def test_oriented_size_swaps_for_quarter_turns() -> None:
    assert oriented_size(200, 100, 0) == (200, 100)
    assert oriented_size(200, 100, 90) == (100, 200)
    assert oriented_size(200, 100, 180) == (200, 100)
    assert oriented_size(200, 100, 270) == (100, 200)


def test_corner_points_map_to_corners_for_every_orientation() -> None:
    width, height = 40, 30
    right = width - 0.5
    bottom = height - 0.5
    cases = [
        # (rotation, flip_h, flip_v, display point for image top-right corner)
        (0, False, False, (right, 0.5)),  # stays top-right
        (90, False, False, (bottom, right)),  # quarter turn sends it to bottom-right
        (180, False, False, (0.5, bottom)),
        (270, False, False, (0.5, 0.5)),
        (0, True, False, (0.5, 0.5)),  # horizontal mirror sends it to top-left
        (90, True, True, (0.5, 0.5)),
    ]
    for rotation, flip_h, flip_v, expected in cases:
        display = orient_point(right, 0.5, width, height, rotation, flip_h, flip_v)
        assert display == pytest.approx(expected), (rotation, flip_h, flip_v)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("flip_h", [False, True])
@pytest.mark.parametrize("flip_v", [False, True])
def test_orient_unorient_round_trip(rotation: int, flip_h: bool, flip_v: bool) -> None:
    width, height = 64, 48
    samples = [(0.0, 0.0), (63.0, 47.0), (10.25, 32.5), (32.0, 24.0)]
    for x, y in samples:
        dx, dy = orient_point(x, y, width, height, rotation, flip_h, flip_v)
        ux, uy = unorient_point(dx, dy, width, height, rotation, flip_h, flip_v)
        assert ux == pytest.approx(x)
        assert uy == pytest.approx(y)


def test_flip_only_mapping_mirrors_about_axes() -> None:
    width, height = 10, 20
    assert orient_point(2.0, 5.0, width, height, 0, flip_h=True) == (8.0, 5.0)
    assert orient_point(2.0, 5.0, width, height, 0, flip_v=True) == (2.0, 15.0)
    assert orient_point(2.0, 5.0, width, height, 0, True, True) == (8.0, 15.0)
