"""pydicom-backed DICOM tag inspection service.

Reads only the header of an instance (never the pixel data) and surfaces every
element — public and private — with its tag, keyword/name, value representation
and formatted value. Malformed files raise :class:`InspectionError`; individual
unreadable elements are skipped so one bad attribute never hides the rest.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from dicomviewer.application.inspection import InspectionError
from dicomviewer.domain.tags import TagDocument, TagEntry

_MAX_BINARY_VALUE = 64


class PydicomTagInspector:
    """Reads the raw DICOM elements of an instance via pydicom."""

    def inspect(self, path: Path) -> TagDocument:
        """Return every element of the instance at ``path``."""
        dataset = self._read(path)
        entries: list[TagEntry] = []
        for tag in dataset.keys():
            entry = self._to_entry(dataset, tag)
            if entry is not None:
                entries.append(entry)
        entries.sort(key=_entry_sort_key)
        return TagDocument(source=Path(path), entries=tuple(entries))

    def _read(self, path: Path) -> Any:
        """Read only the DICOM header for ``path``."""
        pydicom = importlib.import_module("pydicom")
        try:
            return pydicom.dcmread(path, stop_before_pixels=True, defer_size="1 KB")
        except Exception as exc:
            raise InspectionError(f"Could not read DICOM dataset from {path}: {exc}") from exc

    def _to_entry(self, dataset: Any, tag: Any) -> TagEntry | None:
        """Convert one raw element to a display entry, or ``None`` to skip."""
        try:
            element = dataset[tag]
            if element.is_empty:
                return None
            keyword = str(element.keyword) if element.keyword else ""
            name = str(element.name or keyword or str(tag))
            return TagEntry(
                tag=_format_tag(tag),
                keyword=keyword,
                name=name,
                value_representation=str(element.VR or ""),
                value=_format_value(element),
                is_private=bool(tag.is_private),
            )
        except Exception:
            return None


def _format_tag(tag: Any) -> str:
    """Return a canonical ``(GGGG,EEEE)`` tag string."""
    return f"({int(tag.group):04X},{int(tag.element):04X})"


def _format_value(element: Any) -> str:
    """Format a pydicom element value for display and searching."""
    value = element.value
    if element.VR == "SQ":
        return f"Sequence ({len(value)} item(s))"
    if isinstance(value, bytes):
        if len(value) > _MAX_BINARY_VALUE:
            return f"<binary {len(value)} bytes>"
        return value.decode("latin-1")
    if isinstance(value, Sequence) and not isinstance(value, str):
        return "\\".join(str(item) for item in cast(Sequence[object], value))
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).strip()


def _entry_sort_key(entry: TagEntry) -> tuple[int, int]:
    """Order entries by their numeric tag."""
    group, element_number = entry.tag[1:-1].split(",")
    return int(group, 16), int(element_number, 16)
