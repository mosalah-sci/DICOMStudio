"""Pure numpy rendering pipeline stages.

Each stage is a standalone function operating on numpy arrays so it can be
unit-tested without pydicom or Qt. The pipeline follows the professional
medical imaging flow: rescale, VOI LUT / window level, normalization, then
conversion to an RGBA payload.
"""

from __future__ import annotations

import numpy as np

MIN_WINDOW_WIDTH = 1e-3
LOW_PERCENTILE = 1.0
HIGH_PERCENTILE = 99.0


def rescale(pixels: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    """Apply the modality rescale slope and intercept as float64."""
    array = np.asarray(pixels)
    if slope == 1.0 and intercept == 0.0:
        return array.astype(np.float64)
    return array.astype(np.float64) * slope + intercept


def auto_window(rescaled: np.ndarray) -> tuple[float, float]:
    """Estimate a (center, width) window from the percentile spread."""
    low, high = np.percentile(rescaled, (LOW_PERCENTILE, HIGH_PERCENTILE))
    center = float((high + low) / 2.0)
    width = float(high - low)
    if width <= MIN_WINDOW_WIDTH:
        minimum = float(np.min(rescaled))
        maximum = float(np.max(rescaled))
        center = (minimum + maximum) / 2.0
        width = maximum - minimum
    return center, max(width, MIN_WINDOW_WIDTH)


def effective_window(
    rescaled: np.ndarray,
    center: float | None,
    width: float,
) -> tuple[float, float]:
    """Resolve the window to apply, falling back to an automatic one."""
    if width <= 0:
        return auto_window(rescaled)
    if center is None:
        center = auto_window(rescaled)[0]
    return center, width


def apply_window(rescaled: np.ndarray, center: float, width: float) -> np.ndarray:
    """Map pixel values to the [0, 1] range using a window/level mapping."""
    width = max(width, MIN_WINDOW_WIDTH)
    low = center - width / 2.0
    high = center + width / 2.0
    return np.clip((rescaled - low) / (high - low), 0.0, 1.0).astype(np.float32)


def apply_photometric(normalized: np.ndarray, invert: bool) -> np.ndarray:
    """Invert MONOCHROME1 images so bright tissues appear bright."""
    if invert:
        return 1.0 - normalized
    return normalized


def to_rgba_grayscale(normalized: np.ndarray) -> np.ndarray:
    """Expand a [0, 1] grayscale plane to an RGBA uint8 array."""
    gray = (normalized * 255.0).round().astype(np.uint8)
    height, width = gray.shape
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = gray
    rgba[..., 1] = gray
    rgba[..., 2] = gray
    rgba[..., 3] = 255
    return rgba


def normalize_color(pixels: np.ndarray) -> np.ndarray:
    """Map each color channel of a multi-sample frame to [0, 1]."""
    array = np.asarray(pixels, dtype=np.float64)
    span = float(array.max() - array.min())
    if span <= 0:
        return np.zeros_like(array)
    return ((array - array.min()) / span).astype(np.float32)


def to_rgba_color(rgb: np.ndarray) -> np.ndarray:
    """Convert a normalized (height, width, channels) frame to RGBA uint8."""
    height, width, _channels = rgb.shape
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., 0:3] = (rgb * 255.0).round().astype(np.uint8)
    rgba[..., 3] = 255
    return rgba
