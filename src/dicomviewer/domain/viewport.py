"""Viewport state and geometry for the medical image viewer.

The viewport is pure data describing how a slice is displayed: zoom, pan,
window/level and the active slice. It carries no GUI or DICOM dependencies so
its clamping rules can be unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

MIN_ZOOM = 0.05
MAX_ZOOM = 32.0
MIN_WINDOW_WIDTH = 1e-3


class FitMode(StrEnum):
    """How the image is scaled to fit the viewport."""

    FIT = "fit"
    ACTUAL = "actual"
    FREE = "free"


ORIENTATION_STEP = 90


@dataclass(frozen=True)
class Viewport:
    """The complete display state of one image slice.

    ``window_width`` of zero (and ``window_center`` of ``None``) mean "auto":
    the renderer derives the window from the pixel data. The orientation
    fields describe how the frame is presented on screen; rotation is a
    clockwise multiple of :data:`ORIENTATION_STEP` degrees, flips mirror the
    displayed axes and ``invert`` reverses the grayscale mapping.
    """

    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    window_center: float | None = None
    window_width: float = 0.0
    slice_index: int = 0
    fit_mode: FitMode = FitMode.FIT
    rotation: int = 0
    flip_h: bool = False
    flip_v: bool = False
    invert: bool = False

    @classmethod
    def initial(cls) -> Viewport:
        """Return the default viewport: fit to window, auto window level."""
        return cls()

    def to_free(self) -> Viewport:
        """Switch to free zooming while keeping the current zoom level."""
        return replace(self, fit_mode=FitMode.FREE)

    def with_zoom(self, value: float) -> Viewport:
        """Return a copy zoomed by ``value`` (clamped), exiting fit mode."""
        return replace(self, zoom=clamp_zoom(value), fit_mode=FitMode.FREE)

    def with_pan(self, pan_x: float, pan_y: float) -> Viewport:
        """Return a copy with the given pan offsets."""
        return replace(self, pan_x=pan_x, pan_y=pan_y)

    def with_slice(self, index: int, count: int) -> Viewport:
        """Return a copy whose slice index is clamped to ``count`` frames."""
        return replace(self, slice_index=clamp_slice(index, count))

    def with_window(self, center: float | None, width: float) -> Viewport:
        """Return a copy with the given window/level, clamping the width.

        A non-positive width restores the automatic window (center reset).
        """
        if width <= 0:
            return replace(self, window_center=None, window_width=0.0)
        return replace(self, window_center=center, window_width=clamp_window_width(width))

    def rotate_cw(self) -> Viewport:
        """Return a copy rotated 90 degrees clockwise."""
        return replace(self, rotation=(self.rotation + ORIENTATION_STEP) % 360)

    def rotate_ccw(self) -> Viewport:
        """Return a copy rotated 90 degrees counter-clockwise."""
        return replace(self, rotation=(self.rotation - ORIENTATION_STEP) % 360)

    def toggle_flip_h(self) -> Viewport:
        """Return a copy with the horizontal flip toggled."""
        return replace(self, flip_h=not self.flip_h)

    def toggle_flip_v(self) -> Viewport:
        """Return a copy with the vertical flip toggled."""
        return replace(self, flip_v=not self.flip_v)

    def toggle_invert(self) -> Viewport:
        """Return a copy with grayscale inversion toggled."""
        return replace(self, invert=not self.invert)

    def has_identity_orientation(self) -> bool:
        """Return whether no rotation, flip or inversion is applied."""
        return self.rotation == 0 and not self.flip_h and not self.flip_v and not self.invert

    def fit(self) -> Viewport:
        """Return a copy that fits the image to the window."""
        return replace(self, fit_mode=FitMode.FIT, zoom=1.0)

    def actual(self) -> Viewport:
        """Return a copy showing the image at 100% pixel scale."""
        return replace(self, fit_mode=FitMode.ACTUAL, zoom=1.0, pan_x=0.0, pan_y=0.0)


def clamp_zoom(value: float) -> float:
    """Clamp a zoom factor to the supported range."""
    return min(max(value, MIN_ZOOM), MAX_ZOOM)


def clamp_window_width(value: float) -> float:
    """Ensure a window width stays positive."""
    return max(value, MIN_WINDOW_WIDTH)


def clamp_slice(index: int, count: int) -> int:
    """Clamp a slice index to the valid range for ``count`` frames."""
    if count <= 0:
        return 0
    return min(max(index, 0), count - 1)


def normalize_rotation(degrees: float) -> int:
    """Normalize ``degrees`` to the nearest clockwise multiple of 90."""
    steps = round(degrees / ORIENTATION_STEP)
    return (steps * ORIENTATION_STEP) % 360


def oriented_size(width: int, height: int, rotation: int) -> tuple[int, int]:
    """Return the displayed ``(width, height)`` after a 90-degree rotation."""
    normalized = normalize_rotation(rotation)
    if normalized % 180 == 90:
        return height, width
    return width, height


def orient_point(
    x: float,
    y: float,
    width: int,
    height: int,
    rotation: int,
    flip_h: bool = False,
    flip_v: bool = False,
) -> tuple[float, float]:
    """Map image coordinates to display coordinates.

    Flips mirror about the image axes first, then the frame rotates
    clockwise by ``rotation`` degrees. Coordinates are continuous, so the
    transform is exactly invertible (see :func:`unorient_point`).
    """
    fx = width - x if flip_h else x
    fy = height - y if flip_v else y
    normalized = normalize_rotation(rotation)
    if normalized == 90:
        return height - fy, fx
    if normalized == 180:
        return width - fx, height - fy
    if normalized == 270:
        return fy, width - fx
    return fx, fy


def unorient_point(
    x: float,
    y: float,
    width: int,
    height: int,
    rotation: int,
    flip_h: bool = False,
    flip_v: bool = False,
) -> tuple[float, float]:
    """Map display coordinates back to image coordinates."""
    normalized = normalize_rotation(rotation)
    if normalized == 90:
        fx, fy = y, height - x
    elif normalized == 180:
        fx, fy = width - x, height - y
    elif normalized == 270:
        fx, fy = width - y, x
    else:
        fx, fy = x, y
    ux = width - fx if flip_h else fx
    uy = height - fy if flip_v else fy
    return ux, uy
