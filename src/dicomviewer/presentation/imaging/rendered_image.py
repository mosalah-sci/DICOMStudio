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
