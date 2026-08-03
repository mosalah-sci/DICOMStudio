"""Orchestrates the numpy rendering pipeline for full-frame images."""

from __future__ import annotations

import numpy as np

from dicomviewer.application.viewing import (
    PixelArray,
    RenderedImage,
    RenderingError,
)
from dicomviewer.domain.viewport import Viewport
from dicomviewer.infrastructure.rendering import pipeline


class NumpyViewRenderer:
    """Renders decoded frames to RGBA using the modular numpy pipeline."""

    def render(self, pixels: PixelArray, viewport: Viewport) -> RenderedImage:
        """Return the full-resolution RGBA frame for ``pixels``."""
        try:
            rgba = self._render_rgba(pixels, viewport)
        except Exception as exc:
            raise RenderingError(f"Could not render image: {exc}") from exc
        return RenderedImage(width=pixels.width, height=pixels.height, data=rgba.tobytes())

    def effective_window(self, pixels: PixelArray, viewport: Viewport) -> tuple[float, float]:
        """Return the window that would currently apply for ``pixels``."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        return pipeline.effective_window(rescaled, viewport.window_center, viewport.window_width)

    def _render_rgba(self, pixels: PixelArray, viewport: Viewport) -> np.ndarray:
        """Render the frame to an RGBA array without error wrapping."""
        if pixels.is_color:
            return self._render_color(pixels)
        return self._render_monochrome(pixels, viewport)

    def _render_monochrome(self, pixels: PixelArray, viewport: Viewport) -> np.ndarray:
        """Render a grayscale frame through rescale, window and inversion."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        center, width = pipeline.effective_window(
            rescaled, viewport.window_center, viewport.window_width
        )
        normalized = pipeline.apply_window(rescaled, center, width)
        normalized = pipeline.apply_photometric(normalized, pixels.is_monochrome1)
        return pipeline.to_rgba_grayscale(normalized)

    def _render_color(self, pixels: PixelArray) -> np.ndarray:
        """Render a color frame by normalizing its channels."""
        normalized = pipeline.normalize_color(pixels.pixels)
        return pipeline.to_rgba_color(normalized)
