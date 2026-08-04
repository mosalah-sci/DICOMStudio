"""Tests for the Qt conversion of rendered frames."""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage

from dicomviewer.application.viewing import RenderedImage
from dicomviewer.presentation.imaging.rendered_image import (
    rendered_image_from_qimage,
    to_qimage,
)


def test_to_qimage_returns_non_null_image_of_expected_size(qapp) -> None:
    rendered = RenderedImage(width=4, height=3, data=bytes(4 * 3 * 4))
    image = to_qimage(rendered)
    assert not image.isNull()
    assert image.width() == 4
    assert image.height() == 3
    assert image.format().name == "Format_ARGB32"


def test_rendered_image_from_qimage_round_trips_ar32_data(qapp) -> None:
    source = QImage(2, 2, QImage.Format.Format_ARGB32)
    source.fill(QColor(10, 20, 30))
    rendered = rendered_image_from_qimage(source)
    assert rendered.width == 2
    assert rendered.height == 2
    assert rendered.validate()
    # ARGB32 stores bytes as B, G, R, A in memory.
    assert rendered.data[:4] == bytes((30, 20, 10, 255))
    rebuilt = to_qimage(rendered)
    assert rebuilt.pixel(0, 0) == source.pixel(0, 0)
