"""pydicom-backed metadata extraction service.

Reads only the header of an instance (never the pixel data), formats each
public element into a display-friendly value, and groups it logically for
presentation. Private tags and empty elements are dropped so the panel stays
readable, and value size is bounded so large binary attributes never bloat the
document.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from dicomviewer.application.metadata import MetadataExtractionError
from dicomviewer.domain.metadata import (
    GROUP_ORDER,
    MetadataDocument,
    MetadataElement,
    MetadataGroup,
    classify_metadata_group,
)
from dicomviewer.domain.studies import Image

_MAX_BINARY_VALUE = 64
_SKIPPED_GROUPS = frozenset({0x0000, 0xFFFC, 0xFFFE})


class PydicomMetadataService:
    """Extracts grouped metadata from DICOM instances via pydicom."""

    def extract(self, image: Image) -> MetadataDocument:
        """Return the grouped metadata of ``image``."""
        dataset = self._read(image.path)
        elements: list[MetadataElement] = []
        for tag in dataset.keys():
            element = self._convert(dataset, tag)
            if element is None:
                continue
            if not self._is_visible(element):
                continue
            converted = self._to_element(tag, element)
            if converted is not None:
                elements.append(converted)
        elements.sort(key=_element_sort_key)
        groups = self._group(elements)
        return MetadataDocument(source=image.path, groups=groups)

    def _read(self, path: Path) -> Any:
        """Read only the DICOM header for ``path``."""
        pydicom = importlib.import_module("pydicom")
        try:
            return pydicom.dcmread(path, stop_before_pixels=True, defer_size="1 KB")
        except Exception as exc:
            raise MetadataExtractionError(f"Could not read metadata from {path}: {exc}") from exc

    def _convert(self, dataset: Any, tag: Any) -> Any | None:
        """Return the converted data element for ``tag``, or ``None`` to skip."""
        try:
            return dataset[tag]
        except Exception:
            return None

    def _to_element(self, tag: Any, element: Any) -> MetadataElement | None:
        """Convert one data element to a display element, or ``None`` to skip."""
        try:
            keyword = str(element.keyword) if element.keyword else str(tag)
            group = classify_metadata_group(int(tag.group), keyword)
            return MetadataElement(
                tag=_format_tag(tag),
                keyword=keyword,
                group=group,
                name=str(element.name or keyword),
                value=self._format_value(element),
                value_representation=str(element.VR or ""),
            )
        except Exception:
            return None

    def _is_visible(self, element: Any) -> bool:
        """Return whether an element should be shown in the metadata panel."""
        tag = element.tag
        if tag.is_private:
            return False
        if int(tag.group) in _SKIPPED_GROUPS:
            return False
        if element.is_empty:
            return False
        return True

    def _group(self, elements: list[MetadataElement]) -> tuple[MetadataGroup, ...]:
        """Order elements into the logical presentation groups."""
        by_group: dict[str, list[MetadataElement]] = {}
        for element in elements:
            by_group.setdefault(element.group, []).append(element)
        group_names = sorted(by_group, key=_group_sort_key)
        return tuple(
            MetadataGroup(name=name, elements=tuple(by_group[name])) for name in group_names
        )

    def _format_value(self, element: Any) -> str:
        """Format a pydicom element value for display and copying."""
        if element.is_empty:
            return "<no value>"
        value = element.value
        if element.VR == "SQ":
            return f"Sequence ({len(value)} item(s))"
        if isinstance(value, bytes):
            if len(value) > _MAX_BINARY_VALUE:
                return f"<binary {len(value)} bytes>"
            return value.decode("latin-1")
        if isinstance(value, Sequence) and not isinstance(value, str):
            return _join_values(cast(Sequence[object], value))
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).strip()


def _join_values(values: Sequence[object]) -> str:
    """Join a DICOM multi-valued attribute with the standard delimiter."""
    return "\\".join(str(item) for item in values)


def _format_tag(tag: Any) -> str:
    """Return a canonical ``(GGGG,EEEE)`` tag string."""
    return f"({int(tag.group):04X},{int(tag.element):04X})"


def _element_sort_key(element: MetadataElement) -> tuple[int, int]:
    """Order elements by their numeric tag within a group."""
    group, element_number = element.tag[1:-1].split(",")
    return int(group, 16), int(element_number, 16)


def _group_sort_key(name: str) -> tuple[int, str]:
    """Order groups by the canonical display order, unknowns last."""
    try:
        index = GROUP_ORDER.index(name)
    except ValueError:
        index = len(GROUP_ORDER)
    return index, name
