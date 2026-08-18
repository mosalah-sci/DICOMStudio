"""DICOM tag inspection model.

Pure data describing the raw DICOM elements of one instance for the Dataset
Inspector. Unlike the curated metadata model, every element is surfaced —
including private tags — so a user can inspect exactly what the file carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TagEntry:
    """One raw DICOM element ready for the tag inspector."""

    tag: str
    keyword: str
    name: str
    value_representation: str
    value: str
    is_private: bool = False

    @property
    def identifier(self) -> str:
        """Return a stable display identifier combining tag and keyword."""
        return f"{self.tag} {self.keyword}".strip()


@dataclass(frozen=True)
class TagDocument:
    """The full set of elements read from one DICOM instance."""

    source: Path
    entries: tuple[TagEntry, ...] = ()

    @property
    def entry_count(self) -> int:
        """Return the number of elements in the document."""
        return len(self.entries)

    def has_content(self) -> bool:
        """Return whether at least one element was read."""
        return self.entry_count > 0
