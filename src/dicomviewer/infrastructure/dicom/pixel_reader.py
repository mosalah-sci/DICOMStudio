"""Full-resolution pixel decoding from DICOM files.

Decodes a single instance into a :class:`PixelArray` carrying the raw frame
plus the metadata the renderer needs (rescale, window and photometric
interpretation). Formats that cannot be displayed raise
:class:`UnsupportedPixelFormatError` instead of crashing the viewer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from dicomviewer.application.viewing import (
    SUPPORTED_COLOR_PHOTOMETRICS,
    PixelArray,
    UnsupportedPixelFormatError,
)
from dicomviewer.domain.studies import Image


def _read_full(path: Path) -> Any:
    """Read a full DICOM dataset (including pixel data) as untyped data."""
    import importlib  # lazy import keeps startup fast

    pydicom = importlib.import_module("pydicom")
    return pydicom.dcmread(path)


def _first_float(value: object | None) -> float | None:
    """Return the first element of a DICOM numeric value as float."""
    if value is None:
        return None
    try:
        array = np.asarray(value)
    except Exception:
        return None
    if array.size == 0:
        return None
    try:
        return float(array.flat[0])
    except (TypeError, ValueError):
        return None


class PydicomPixelDecoder:
    """Pixel decoder backed by pydicom."""

    def decode(self, image: Image) -> PixelArray:
        """Decode ``image`` into a displayable pixel array."""
        try:
            dataset = _read_full(image.path)
        except Exception as exc:
            raise UnsupportedPixelFormatError(
                f"Could not read DICOM file {image.path}: {exc}"
            ) from exc
        if not hasattr(dataset, "PixelData"):
            raise UnsupportedPixelFormatError(f"No pixel data in {image.path}")
        try:
            frame = np.asarray(dataset.pixel_array)
        except Exception as exc:
            raise UnsupportedPixelFormatError(
                f"Unsupported pixel format in {image.path}: {exc}"
            ) from exc

        samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
        photometric = str(
            getattr(dataset, "PhotometricInterpretation", "MONOCHROME2") or "MONOCHROME2"
        )
        bits_allocated = int(getattr(dataset, "BitsAllocated", 16) or 16)

        if frame.ndim == 2:
            pixels, width, height = frame, frame.shape[1], frame.shape[0]
        elif frame.ndim == 3 and samples > 1:
            pixels, width, height = frame, frame.shape[1], frame.shape[0]
            if photometric not in SUPPORTED_COLOR_PHOTOMETRICS:
                raise UnsupportedPixelFormatError(
                    f"Unsupported color space {photometric!r} in {image.path}"
                )
        elif frame.ndim == 3:
            pixels, width, height = frame[0], frame.shape[2], frame.shape[1]
        else:
            raise UnsupportedPixelFormatError(f"Unsupported pixel shape in {image.path}")

        return PixelArray(
            pixels=pixels,
            width=width,
            height=height,
            samples=samples,
            bits_allocated=bits_allocated,
            photometric_interpretation=photometric,
            rescale_slope=_first_float(getattr(dataset, "RescaleSlope", None)) or 1.0,
            rescale_intercept=_first_float(getattr(dataset, "RescaleIntercept", None)) or 0.0,
            window_center=_first_float(getattr(dataset, "WindowCenter", None)),
            window_width=_first_float(getattr(dataset, "WindowWidth", None)),
        )
