"""Application ports for DICOM study discovery.

Infrastructure implements these protocols; Presentation depends only on the
interfaces declared here, preserving the clean architecture dependency rule.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from dicomviewer.domain.exceptions import DicomViewerError
from dicomviewer.domain.studies import Image, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail


class DiscoveryError(DicomViewerError):
    """Raised when a study folder cannot be scanned."""


class StudyScanner(Protocol):
    """Scans a folder recursively and builds the study tree."""

    def scan(
        self,
        folder: Path,
        should_cancel: Callable[[], bool] | None = None,
    ) -> StudyTree:
        """Scan ``folder`` and return the discovered hierarchy.

        Invalid or unreadable files are ignored gracefully. The optional
        ``should_cancel`` predicate lets long scans be aborted cooperatively.
        """
        ...


class ThumbnailService(Protocol):
    """Generates grayscale thumbnails from DICOM image instances."""

    def generate(self, image: Image, size: int) -> Thumbnail | None:
        """Return a ``size``-bounded grayscale thumbnail, or ``None``.

        ``None`` is returned for instances that cannot produce a thumbnail,
        such as files without pixel data.
        """
        ...
