"""Grayscale thumbnail generation from DICOM pixel data.

The service reads one instance, reduces it to an 8-bit grayscale image scaled
to fit a bounding box, and returns the plain byte payload defined in the
Domain layer. Files that cannot produce a thumbnail yield ``None`` instead of
raising, so the caller can render it gracefully.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from dicomviewer.domain.studies import Image
from dicomviewer.domain.thumbnail import Thumbnail


def _read_full(path: Path) -> Any:
    """Read a full DICOM dataset (including pixel data) as untyped data."""
    import importlib  # lazy import keeps startup fast

    pydicom = importlib.import_module("pydicom")
    return pydicom.dcmread(path)


class PydicomThumbnailService:
    """Thumbnail generator backed by pydicom and numpy."""

    def generate(self, image: Image, size: int) -> Thumbnail | None:
        """Return a ``size``-bounded grayscale thumbnail for ``image``."""
        try:
            dataset = _read_full(image.path)
            if not hasattr(dataset, "PixelData"):
                return None
            pixels = dataset.pixel_array
            samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
        except Exception:
            logger.debug("Could not read pixel data for thumbnail: {}", image.path)
            return None

        grayscale = self._to_grayscale(pixels, samples)
        if grayscale is None:
            logger.debug("Unsupported pixel shape for thumbnail: {}", image.path)
            return None

        try:
            sampled, width, height = self._sample(grayscale, size)
            rescaled = self._rescale(sampled, dataset)
            normalized = self._normalize(rescaled, dataset)
            data = (normalized * 255.0).round().astype(np.uint8)
        except Exception:
            logger.debug("Could not render thumbnail: {}", image.path)
            return None
        return Thumbnail(width=width, height=height, data=data.tobytes())

    def _to_grayscale(self, pixels: np.ndarray, samples: int) -> np.ndarray | None:
        """Reduce arbitrary pixel arrays to a single 2-D grayscale plane."""
        array = np.asarray(pixels)
        if array.ndim == 2:
            return array
        if array.ndim == 3:
            if samples > 1:
                return array.mean(axis=2)
            return array[0]
        return None

    def _rescale(self, array: np.ndarray, dataset: object) -> np.ndarray:
        """Apply the modality rescale slope and intercept."""
        slope = float(getattr(dataset, "RescaleSlope", 1) or 1)
        intercept = float(getattr(dataset, "RescaleIntercept", 0) or 0)
        return array.astype(np.float64) * slope + intercept

    def _normalize(self, array: np.ndarray, dataset: object) -> np.ndarray:
        """Map pixel values to the [0, 1] range using the VOI window."""
        center, width = self._voi_window(array, dataset)
        if width and width > 0:
            low = center - width / 2.0
            high = center + width / 2.0
            normalized = np.clip((array - low) / (high - low), 0.0, 1.0)
        else:
            low, high = np.percentile(array, (1.0, 99.0))
            if high > low:
                normalized = np.clip((array - low) / (high - low), 0.0, 1.0)
            else:
                normalized = np.zeros_like(array)
        if getattr(dataset, "PhotometricInterpretation", None) == "MONOCHROME1":
            normalized = 1.0 - normalized
        return normalized

    def _voi_window(self, array: np.ndarray, dataset: object) -> tuple[float, float]:
        """Return the (center, width) VOI window, falling back to min/max."""
        raw_width = getattr(dataset, "WindowWidth", None)
        if raw_width is not None:
            width = float(np.asarray(raw_width).flat[0])
            raw_center = getattr(dataset, "WindowCenter", None)
            if raw_center is not None:
                center = float(np.asarray(raw_center).flat[0])
            else:
                center = float(array.min() + array.max()) / 2.0
            return center, width
        return float(array.min() + array.max()) / 2.0, 0.0

    def _sample(self, array: np.ndarray, size: int) -> tuple[np.ndarray, int, int]:
        """Downsample ``array`` to fit a square bounding box, preserving aspect.

        The image is sampled *before* rescaling and windowing so the expensive
        float rescale, percentile and normalization work on the small target
        resolution instead of the full frame. Sampling is a plain nearest-row/
        column selection, so a windowed dataset renders byte-for-byte the same
        as the previous full-resolution pipeline.
        """
        height, width = array.shape
        scale = size / max(height, width)
        new_height = max(1, round(height * scale))
        new_width = max(1, round(width * scale))
        row_indices = (np.arange(new_height) * height / new_height).astype(np.int64)
        col_indices = (np.arange(new_width) * width / new_width).astype(np.int64)
        sampled = array[row_indices][:, col_indices]
        return sampled, new_width, new_height
