"""Tests for the pure numpy rendering pipeline stages."""

from __future__ import annotations

import numpy as np

from dicomviewer.infrastructure.rendering import pipeline


def test_rescale_applies_slope_and_intercept() -> None:
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    rescaled = pipeline.rescale(pixels, slope=2.0, intercept=-1.0)
    assert rescaled.dtype == np.float64
    np.testing.assert_allclose(rescaled, [[-1.0, 1.0], [3.0, 5.0]])


def test_rescale_is_identity_by_default() -> None:
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    rescaled = pipeline.rescale(pixels, slope=1.0, intercept=0.0)
    np.testing.assert_allclose(rescaled, pixels)


def test_apply_window_maps_values_to_unit_range() -> None:
    rescaled = np.arange(101, dtype=np.float64)
    mapped = pipeline.apply_window(rescaled, center=50.0, width=100.0)
    assert mapped.dtype == np.float32
    np.testing.assert_allclose(mapped[0], 0.0)
    np.testing.assert_allclose(mapped[50], 0.5)
    np.testing.assert_allclose(mapped[100], 1.0)


def test_apply_window_clips_outside_values() -> None:
    rescaled = np.array([-1000.0, 0.0, 1000.0], dtype=np.float64)
    mapped = pipeline.apply_window(rescaled, center=0.0, width=100.0)
    assert mapped[0] == 0.0 and mapped[2] == 1.0


def test_auto_window_uses_percentile_spread() -> None:
    rescaled = np.concatenate([np.zeros(100), np.full(100, 1000.0)])
    center, width = pipeline.auto_window(rescaled)
    assert width > 0
    assert center > 0


def test_effective_window_falls_back_to_auto() -> None:
    rescaled = np.arange(256, dtype=np.float64)
    _auto_center, width = pipeline.effective_window(rescaled, center=None, width=0.0)
    assert width > 0
    explicit_center, explicit_width = pipeline.effective_window(rescaled, center=10.0, width=20.0)
    assert (explicit_center, explicit_width) == (10.0, 20.0)


def test_apply_photometric_inverts_monochrome1() -> None:
    normalized = np.array([0.0, 0.25, 1.0])
    np.testing.assert_allclose(pipeline.apply_photometric(normalized, True), [1.0, 0.75, 0.0])
    np.testing.assert_allclose(pipeline.apply_photometric(normalized, False), normalized)


def test_to_rgba_grayscale_produces_opaque_four_channel_frame() -> None:
    normalized = np.array([[0.0, 1.0], [0.5, 0.0]])
    rgba = pipeline.to_rgba_grayscale(normalized)
    assert rgba.shape == (2, 2, 4)
    assert rgba.dtype == np.uint8
    assert rgba[0, 0, 0] == 0 and rgba[0, 1, 0] == 255
    assert rgba[0, 1, 1] == 255 and rgba[0, 1, 2] == 255
    assert rgba[0, 0, 3] == 255


def test_normalize_color_scales_channels() -> None:
    color = np.array([[[0, 100], [200, 255]]], dtype=np.uint16)
    normalized = pipeline.normalize_color(color)
    assert normalized.min() == 0.0
    assert normalized.max() == 1.0


def test_to_rgba_color_produces_opaque_frame() -> None:
    rgb = np.zeros((2, 2, 3), dtype=np.float32)
    rgb[0, 0] = (1.0, 0.0, 0.0)
    rgba = pipeline.to_rgba_color(rgb)
    assert rgba.shape == (2, 2, 4)
    assert (rgba[0, 0, 0:3] == [255, 0, 0]).all()
    assert (rgba[0, 1, 0:3] == 0).all()
    assert (rgba[0, 0, 3] == 255).all()
