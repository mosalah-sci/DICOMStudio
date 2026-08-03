"""Tests for the Qt conversion of rendered frames."""

from __future__ import annotations

from dicomviewer.application.viewing import RenderedImage
from dicomviewer.presentation.imaging.rendered_image import to_qimage


def test_to_qimage_returns_non_null_image_of_expected_size(qapp) -> None:
    rendered = RenderedImage(width=4, height=3, data=bytes(4 * 3 * 4))
    image = to_qimage(rendered)
    assert not image.isNull()
    assert image.width() == 4
    assert image.height() == 3
    assert image.format().name == "Format_ARGB32"
