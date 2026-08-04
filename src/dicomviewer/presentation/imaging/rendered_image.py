"""Qt conversion helpers for rendered frames."""

from __future__ import annotations

from PySide6.QtGui import QImage

from dicomviewer.application.viewing import RenderedImage


def to_qimage(rendered: RenderedImage) -> QImage:
    """Convert a rendered RGBA frame to an owned, display-ready QImage.

    The QImage is copied so it owns its pixel buffer instead of referencing
    the Python bytes object, which may otherwise be garbage collected.
    """
    image = QImage(
        bytes(rendered.data),
        rendered.width,
        rendered.height,
        rendered.stride,
        QImage.Format.Format_ARGB32,
    )
    if image.isNull():
        return image
    return image.copy()


def rendered_image_from_qimage(image: QImage) -> RenderedImage:
    """Convert a QImage to a :class:`RenderedImage` payload.

    The payload uses the same ARGB32 byte order as the display pipeline, so a
    captured view round-trips through :func:`to_qimage` without a channel
    swap. The bytes are copied immediately so the result stays valid after
    the source image is released.
    """
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    return RenderedImage(width=argb.width(), height=argb.height(), data=bytes(argb.constBits()))
