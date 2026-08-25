"""Widget/image coordinate and scale transforms for the image viewer.

Pure geometry over an explicit ``(viewport, image size, widget size)``
frame: no widget state, so results are deterministic and independently
testable. The mapping mirrors the paint-time transform exactly — the frame
is scaled to ``target_rect`` and rotated/flipped inside it — so annotations
and measurements land on the same anatomy regardless of orientation.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from dicomviewer.domain.measurement import DEFAULT_HIT_TOLERANCE, Point
from dicomviewer.domain.viewport import (
    FitMode,
    Viewport,
    orient_point,
    oriented_size,
    unorient_point,
)

# Constant widget-space hit slop, converted with the current display scale.
HIT_TOLERANCE_WIDGET = 8.0
_MIN_HIT_TOLERANCE = 1.0
_MAX_HIT_TOLERANCE = 64.0


def effective_scale(
    viewport: Viewport,
    image_width: int,
    image_height: int,
    widget_width: float,
    widget_height: float,
) -> float:
    """Return the scale that maps display pixels to widget pixels."""
    display_width, display_height = oriented_size(image_width, image_height, viewport.rotation)
    if display_width <= 0 or display_height <= 0:
        return 1.0
    if viewport.fit_mode == FitMode.FIT:
        return min(widget_width / display_width, widget_height / display_height)
    if viewport.fit_mode == FitMode.ACTUAL:
        return 1.0
    return viewport.zoom


def target_rect(
    viewport: Viewport,
    image_width: int,
    image_height: int,
    widget_width: float,
    widget_height: float,
) -> QRectF:
    """Return the destination rectangle for the rendered frame.

    The rectangle covers the oriented display size; the paint transform
    rotates/flips the frame inside it.
    """
    scale = effective_scale(viewport, image_width, image_height, widget_width, widget_height)
    display_width, display_height = oriented_size(image_width, image_height, viewport.rotation)
    target_width, target_height = (
        dimension * scale for dimension in (display_width, display_height)
    )
    center_x = widget_width / 2.0 + viewport.pan_x * scale
    center_y = widget_height / 2.0 + viewport.pan_y * scale
    return QRectF(
        center_x - target_width / 2.0,
        center_y - target_height / 2.0,
        target_width,
        target_height,
    )


def widget_to_image(
    viewport: Viewport,
    image_width: int,
    image_height: int,
    widget_width: float,
    widget_height: float,
    position: QPointF,
) -> Point:
    """Map a widget coordinate into image pixel coordinates.

    The widget position is first expressed in display space, then run
    through the inverse of the orientation transform applied at paint time.
    Coordinates clamp to the last pixel index so tools stay on the image.
    """
    rect = target_rect(viewport, image_width, image_height, widget_width, widget_height)
    if rect.width() <= 0 or rect.height() <= 0:
        return Point(0.0, 0.0)
    display_width, display_height = oriented_size(image_width, image_height, viewport.rotation)
    display_x = (position.x() - rect.left()) / rect.width() * display_width
    display_y = (position.y() - rect.top()) / rect.height() * display_height
    point = unorient_point(
        display_x,
        display_y,
        image_width,
        image_height,
        viewport.rotation,
        viewport.flip_h,
        viewport.flip_v,
    )
    return Point(
        min(max(point[0], 0.0), float(image_width - 1)),
        min(max(point[1], 0.0), float(image_height - 1)),
    )


def image_to_widget(
    viewport: Viewport,
    image_width: int,
    image_height: int,
    widget_width: float,
    widget_height: float,
    point: Point,
) -> QPointF:
    """Map an image pixel coordinate into widget coordinates."""
    rect = target_rect(viewport, image_width, image_height, widget_width, widget_height)
    if rect.width() <= 0 or rect.height() <= 0:
        return QPointF(rect.left(), rect.top())
    display_width, display_height = oriented_size(image_width, image_height, viewport.rotation)
    display_x, display_y = orient_point(
        point.x,
        point.y,
        image_width,
        image_height,
        viewport.rotation,
        viewport.flip_h,
        viewport.flip_v,
    )
    return QPointF(
        rect.left() + display_x / display_width * rect.width(),
        rect.top() + display_y / display_height * rect.height(),
    )


def hit_tolerance(scale: float) -> float:
    """Return the hit-test tolerance in image pixels for a display scale.

    The constant widget-space slop is converted with the current display
    scale and clamped so it stays usable at extreme zoom levels.
    """
    if scale <= 0.0:
        return DEFAULT_HIT_TOLERANCE
    return min(max(HIT_TOLERANCE_WIDGET / scale, _MIN_HIT_TOLERANCE), _MAX_HIT_TOLERANCE)
