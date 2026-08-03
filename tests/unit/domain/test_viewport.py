"""Tests for the viewport state model."""

from __future__ import annotations

from dicomviewer.domain.viewport import (
    MAX_ZOOM,
    MIN_ZOOM,
    FitMode,
    Viewport,
    clamp_slice,
    clamp_zoom,
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
