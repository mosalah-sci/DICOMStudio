"""Tests for the export application port."""

from __future__ import annotations

from dicomviewer.application.export import ExportError
from dicomviewer.domain.exceptions.base import DicomViewerError


def test_export_error_is_an_application_error() -> None:
    assert issubclass(ExportError, DicomViewerError)
