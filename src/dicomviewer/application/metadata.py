"""Application port and search use case for DICOM metadata.

Infrastructure implements the extraction port; Presentation depends only on
the interface declared here. Search/filter is a pure use case so the GUI never
owns matching rules.
"""

from __future__ import annotations

from typing import Protocol

from dicomviewer.domain.exceptions import DicomViewerError
from dicomviewer.domain.metadata import MetadataDocument, MetadataElement, MetadataGroup
from dicomviewer.domain.studies import Image


class MetadataExtractionError(DicomViewerError):
    """Raised when metadata cannot be read from a DICOM instance."""


class MetadataService(Protocol):
    """Extracts grouped DICOM metadata from an image instance."""

    def extract(self, image: Image) -> MetadataDocument:
        """Return the grouped metadata of ``image``.

        Raises :class:`MetadataExtractionError` for files that cannot be read.
        """
        ...


def filter_metadata(document: MetadataDocument, query: str) -> MetadataDocument:
    """Return a document containing only elements matching ``query``.

    Matching is case-insensitive over the keyword, display name, group, tag and
    value of every element. Groups left without matches are dropped. A blank
    query returns the document unchanged.
    """
    needle = query.strip().casefold()
    if not needle:
        return document
    groups: list[MetadataGroup] = []
    for group in document.groups:
        elements = [element for element in group.elements if _matches(element, needle)]
        if elements:
            groups.append(MetadataGroup(name=group.name, elements=tuple(elements)))
    return MetadataDocument(source=document.source, groups=tuple(groups))


def _matches(element: MetadataElement, needle: str) -> bool:
    """Return whether any searchable field of ``element`` contains ``needle``."""
    fields = (
        element.keyword,
        element.name,
        element.group,
        element.tag,
        element.value,
        element.value_representation,
    )
    return any(needle in field.casefold() for field in fields)
