"""Tests for the export format domain model."""

from __future__ import annotations

from dicomviewer.domain.export import ExportFormat


def test_format_members() -> None:
    assert ExportFormat.PNG.value == "png"
    assert ExportFormat.JPEG.value == "jpeg"


def test_extensions() -> None:
    assert ExportFormat.PNG.extension == ".png"
    assert ExportFormat.JPEG.extension == ".jpg"


def test_mime_types() -> None:
    assert ExportFormat.PNG.mime_type == "image/png"
    assert ExportFormat.JPEG.mime_type == "image/jpeg"


def test_format_parsing() -> None:
    assert ExportFormat("png") is ExportFormat.PNG
    assert ExportFormat("jpeg") is ExportFormat.JPEG
