"""Tests for the Qt-backed image exporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.application.export import ExportError
from dicomviewer.application.viewing import RenderedImage
from dicomviewer.domain.export import ExportFormat
from dicomviewer.infrastructure.imaging.qt_exporter import QtImageExporter

EXPORTER = QtImageExporter()
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def _sample(width: int = 8, height: int = 6) -> RenderedImage:
    """Return an opaque 8x6 RGBA frame with a recognizable pattern."""
    data = bytearray(width * height * 4)
    for index in range(width * height):
        row = index // width
        column = index % width
        data[index * 4] = column * 32
        data[index * 4 + 1] = row * 40
        data[index * 4 + 2] = 128
        data[index * 4 + 3] = 255
    return RenderedImage(width=width, height=height, data=bytes(data))


def test_encode_png_returns_png_bytes(qapp) -> None:
    payload = EXPORTER.encode(_sample(), ExportFormat.PNG)
    assert payload[:8] == PNG_MAGIC


def test_encode_jpeg_returns_jpeg_bytes(qapp) -> None:
    payload = EXPORTER.encode(_sample(), ExportFormat.JPEG)
    assert payload[:3] == JPEG_MAGIC
    assert len(payload) > 0


def test_png_round_trip_preserves_dimensions_and_colours(qapp) -> None:
    from PySide6.QtGui import QImage

    rendered = _sample(width=8, height=6)
    payload = EXPORTER.encode(rendered, ExportFormat.PNG)
    decoded = _decode(payload, ExportFormat.PNG)
    assert decoded.width() == 8
    assert decoded.height() == 6
    # Compare pixels in the ARGB32 space that the payload bytes are defined in.
    source = QImage(
        bytes(rendered.data),
        rendered.width,
        rendered.height,
        rendered.stride,
        QImage.Format.Format_ARGB32,
    )
    for y in range(6):
        for x in range(8):
            assert decoded.pixel(x, y) == source.pixel(x, y), (x, y)


def test_jpeg_quality_changes_the_payload(qapp) -> None:
    rendered = _sample()
    low = EXPORTER.encode(rendered, ExportFormat.JPEG, quality=10)
    high = EXPORTER.encode(rendered, ExportFormat.JPEG, quality=95)
    assert low != high


def test_write_creates_a_file(qapp, tmp_path: Path) -> None:
    path = tmp_path / "export.png"
    EXPORTER.write(_sample(), ExportFormat.PNG, path)
    assert path.read_bytes()[:8] == PNG_MAGIC


def test_write_jpeg_creates_a_file(qapp, tmp_path: Path) -> None:
    path = tmp_path / "export.jpg"
    EXPORTER.write(_sample(), ExportFormat.JPEG, path, quality=80)
    assert path.read_bytes()[:3] == JPEG_MAGIC


def test_encode_rejects_an_invalid_image(qapp) -> None:
    invalid = RenderedImage(width=0, height=0, data=b"")
    with pytest.raises(ExportError):
        EXPORTER.encode(invalid, ExportFormat.PNG)


def test_write_rejects_an_unwritable_target(qapp, tmp_path: Path) -> None:
    with pytest.raises(ExportError):
        EXPORTER.write(_sample(), ExportFormat.PNG, tmp_path)


def _decode(payload: bytes, format: ExportFormat):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage

    buffer = QBuffer()
    buffer.setData(payload)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    image = QImage.fromData(buffer.data(), format.value)
    buffer.close()
    return image
