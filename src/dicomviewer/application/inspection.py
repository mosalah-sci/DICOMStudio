"""Application port and search use case for the DICOM tag inspector.

Infrastructure implements the inspection port; Presentation depends only on
the interface declared here. Filtering is a pure use case so the dialog never
owns matching rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dicomviewer.domain.exceptions import DicomViewerError
from dicomviewer.domain.tags import TagDocument, TagEntry


class InspectionError(DicomViewerError):
    """Raised when a DICOM instance cannot be inspected."""


class TagInspector(Protocol):
    """Reads the raw DICOM elements of an instance."""

    def inspect(self, path: Path) -> TagDocument:
        """Return every element of the instance at ``path``.

        Raises :class:`InspectionError` for files that cannot be read.
        """
        ...


def filter_tags(document: TagDocument, query: str) -> TagDocument:
    """Return a document containing only entries matching ``query``.

    Matching is case-insensitive over the tag, keyword, name, value
    representation and value of every entry. A blank query returns the
    document unchanged.
    """
    needle = query.strip().casefold()
    if not needle:
        return document
    entries = tuple(entry for entry in document.entries if _matches(entry, needle))
    return TagDocument(source=document.source, entries=entries)


def _matches(entry: TagEntry, needle: str) -> bool:
    """Return whether any searchable field of ``entry`` contains ``needle``."""
    fields = (
        entry.tag,
        entry.keyword,
        entry.name,
        entry.value_representation,
        entry.value,
    )
    return any(needle in field.casefold() for field in fields)
