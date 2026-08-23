"""Tests for the numpy view renderer."""

from __future__ import annotations

import numpy as np
import pytest

from dicomviewer.application.processing import ProcessingPipeline
from dicomviewer.application.viewing import PixelArray, RenderingError
from dicomviewer.domain.viewport import Viewport
from dicomviewer.infrastructure.rendering.renderer import NumpyViewRenderer


class _InvertStage:
    """Inverts a normalized frame to verify pipeline injection."""

    name = "invert"

    def apply(self, frame: np.ndarray) -> np.ndarray:
        return 1.0 - frame


def _grayscale() -> PixelArray:
    grid = np.arange(256, dtype=np.uint16).reshape(16, 16)
    return PixelArray(pixels=grid, width=16, height=16)


def _rescaled() -> PixelArray:
    grid = np.arange(256, dtype=np.uint16).reshape(16, 16)
    return PixelArray(
        pixels=grid,
        width=16,
        height=16,
        rescale_slope=2.0,
        rescale_intercept=-256.0,
    )


def test_render_produces_valid_rgba_frame() -> None:
    rendered = NumpyViewRenderer().render(_grayscale(), Viewport.initial())
    assert rendered.width == 16 and rendered.height == 16
    assert rendered.validate()
    assert rendered.stride == 64


def test_render_applies_explicit_window_level() -> None:
    renderer = NumpyViewRenderer()
    auto = renderer.render(_grayscale(), Viewport.initial())
    windowed = renderer.render(_grayscale(), Viewport.initial().with_window(128.0, 64.0))
    assert auto.data != windowed.data


def test_render_inverts_monochrome1() -> None:
    pixels = _grayscale()
    mono1 = PixelArray(
        pixels=pixels.pixels,
        width=16,
        height=16,
        photometric_interpretation="MONOCHROME1",
    )
    renderer = NumpyViewRenderer()
    dark = renderer.render(pixels, Viewport.initial())
    inverted = renderer.render(mono1, Viewport.initial())
    assert dark.data != inverted.data


def test_display_invert_cancels_monochrome1_polarity() -> None:
    pixels = _grayscale()
    mono1 = PixelArray(
        pixels=pixels.pixels,
        width=16,
        height=16,
        photometric_interpretation="MONOCHROME1",
    )
    renderer = NumpyViewRenderer()
    plain = renderer.render(pixels, Viewport.initial())
    both_inverted = renderer.render(mono1, Viewport.initial().toggle_invert())
    assert plain.data == both_inverted.data


def test_display_invert_flips_monochrome2_output() -> None:
    renderer = NumpyViewRenderer()
    pixels = _grayscale()
    normal = renderer.render(pixels, Viewport.initial())
    inverted = renderer.render(pixels, Viewport.initial().toggle_invert())
    assert normal.data != inverted.data
    # Inverting twice returns to the original mapping.
    restored = renderer.render(pixels, Viewport.initial().toggle_invert().toggle_invert())
    assert restored.data == normal.data


def test_display_invert_flips_color_output() -> None:
    ramp = np.tile(np.arange(64, dtype=np.uint16), (8, 1))
    color = PixelArray(
        pixels=np.stack((ramp, ramp, ramp), axis=-1),
        width=64,
        height=8,
        samples=3,
        photometric_interpretation="RGB",
    )
    renderer = NumpyViewRenderer()
    normal = renderer.render(color, Viewport.initial())
    inverted = renderer.render(color, Viewport.initial().toggle_invert())
    assert normal.validate() and inverted.validate()
    assert normal.data != inverted.data


def test_render_color_produces_frame() -> None:
    color = PixelArray(
        pixels=np.zeros((8, 8, 3), dtype=np.uint16),
        width=8,
        height=8,
        samples=3,
        photometric_interpretation="RGB",
    )
    rendered = NumpyViewRenderer().render(color, Viewport.initial())
    assert rendered.validate()


def test_effective_window_resolves_auto_baseline() -> None:
    renderer = NumpyViewRenderer()
    pixels = _rescaled()
    center, width = renderer.effective_window(pixels, Viewport.initial())
    assert width > 0
    assert -256.0 <= center <= 254.0


def test_effective_window_honours_explicit_window() -> None:
    renderer = NumpyViewRenderer()
    viewport = Viewport.initial().with_window(10.0, 20.0)
    assert renderer.effective_window(_rescaled(), viewport) == (10.0, 20.0)


def test_render_wraps_failures_in_rendering_error() -> None:
    class Exploding:
        pixels = np.zeros((2, 2), dtype=np.uint16)  # type: ignore[assignment]

        @property
        def width(self) -> int:
            return 2

        @property
        def height(self) -> int:
            return 2

        @property
        def is_color(self) -> bool:
            return True

        @property
        def rescale_slope(self) -> float:
            return 1.0

        @property
        def rescale_intercept(self) -> float:
            return 0.0

        @property
        def is_monochrome1(self) -> bool:
            return False

    renderer = NumpyViewRenderer()
    with pytest.raises(RenderingError):
        renderer.render(Exploding(), Viewport.initial())  # type: ignore[arg-type]


def test_render_applies_the_injected_processing_stage() -> None:
    renderer = NumpyViewRenderer(processing_pipeline=ProcessingPipeline((_InvertStage(),)))
    plain = NumpyViewRenderer().render(_grayscale(), Viewport.initial())
    processed = renderer.render(_grayscale(), Viewport.initial())
    assert plain.data != processed.data


def test_render_with_an_empty_pipeline_is_unchanged() -> None:
    renderer = NumpyViewRenderer(processing_pipeline=ProcessingPipeline(()))
    plain = NumpyViewRenderer(processing_pipeline=None).render(_grayscale(), Viewport.initial())
    assert plain.data == renderer.render(_grayscale(), Viewport.initial()).data


def test_render_does_not_mutate_the_input_pixels() -> None:
    pixels = _grayscale()
    original = pixels.pixels.copy()
    NumpyViewRenderer().render(pixels, Viewport.initial())
    np.testing.assert_array_equal(pixels.pixels, original)
