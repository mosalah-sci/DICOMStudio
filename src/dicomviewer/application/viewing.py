"""Application ports for medical image viewing.

Infrastructure implements the decoding and rendering ports; Presentation
depends only on these interfaces and the plain data types declared here,
preserving the clean architecture dependency rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from dicomviewer.domain.exceptions.base import DicomViewerError
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import Viewport

SUPPORTED_COLOR_PHOTOMETRICS = frozenset({"RGB", "PALETTE COLOR"})


class UnsupportedPixelFormatError(DicomViewerError):
    """Raised when DICOM pixel data cannot be decoded for display."""


class RenderingError(DicomViewerError):
    """Raised when decoded pixel data cannot be converted to an image."""


@dataclass(frozen=True)
class PixelArray:
    """Decoded pixel data together with the metadata required to render it."""

    pixels: np.ndarray
    width: int
    height: int
    samples: int = 1
    bits_allocated: int = 16
    photometric_interpretation: str = "MONOCHROME2"
    rescale_slope: float = 1.0
    rescale_intercept: float = 0.0
    window_center: float | None = None
    window_width: float | None = None
    pixel_spacing: tuple[float, float] = (1.0, 1.0)

    @property
    def is_color(self) -> bool:
        """Return whether the frame carries color channels."""
        return self.samples > 1

    @property
    def is_monochrome1(self) -> bool:
        """Return whether the frame must be inverted for display."""
        return self.photometric_interpretation == "MONOCHROME1"


@dataclass(frozen=True)
class RenderedImage:
    """An 8-bit RGBA frame ready for display, row-major with alpha 255."""

    width: int
    height: int
    data: bytes

    @property
    def stride(self) -> int:
        """Return the byte length of one row."""
        return self.width * 4

    def validate(self) -> bool:
        """Return whether the payload matches the declared dimensions."""
        return len(self.data) == self.stride * self.height


class PixelDecoder(Protocol):
    """Decodes a DICOM image instance into an array of pixel values."""

    def decode(self, image: Image) -> PixelArray:
        """Return the decoded pixels and rendering metadata for ``image``.

        Raises :class:`UnsupportedPixelFormatError` for files that cannot
        produce a displayable frame.
        """
        ...


class ViewRenderer(Protocol):
    """Renders a decoded frame to an RGBA image using a viewport."""

    def render(self, pixels: PixelArray, viewport: Viewport) -> RenderedImage:
        """Return the full-resolution RGBA frame for ``pixels``.

        The rendered frame is independent of zoom and pan: those transforms
        are applied at paint time so buffers are reused across zooms.
        """
        ...

    def effective_window(self, pixels: PixelArray, viewport: Viewport) -> tuple[float, float]:
        """Return the (center, width) window that would currently apply.

        When the viewport requests an automatic window, this derives one from
        the pixel data so interactive window/level adjustment has a baseline.
        """
        ...
