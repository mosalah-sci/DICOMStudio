"""Tests for the export helper functions of the main window."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.domain.export import ExportFormat
from dicomviewer.presentation.windows.main_window import (
    _export_format_for,
    _timestamp,
)


def test_export_format_from_extension() -> None:
    assert _export_format_for(Path("out.png"), "") is ExportFormat.PNG
    assert _export_format_for(Path("out.jpg"), "") is ExportFormat.JPEG
    assert _export_format_for(Path("out.JPEG"), "") is ExportFormat.JPEG


def test_export_format_from_filter() -> None:
    assert _export_format_for(Path("out"), "JPEG Image (*.jpg *.jpeg)") is ExportFormat.JPEG
    assert _export_format_for(Path("out"), "PNG Image (*.png)") is ExportFormat.PNG


def test_export_format_falls_back_to_filter_when_extension_is_missing() -> None:
    assert _export_format_for(Path("out"), "JPEG Image (*.jpg *.jpeg)") is ExportFormat.JPEG


def test_export_format_rejects_unknown_inputs() -> None:
    assert _export_format_for(Path("out.bmp"), "") is None


def test_timestamp_is_compact_and_sortable() -> None:
    stamp = _timestamp()
    assert len(stamp) == 15
    assert stamp[:8].isdigit()
    assert stamp[9:].isdigit()
    assert stamp[8] == "_"
