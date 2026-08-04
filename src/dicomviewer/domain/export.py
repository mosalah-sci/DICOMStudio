"""Export format model.

A pure enumeration describing the visual formats the application can export.
No GUI or encoding logic lives here.
"""

from __future__ import annotations

from enum import StrEnum


class ExportFormat(StrEnum):
    """The supported visual export formats."""

    PNG = "png"
    JPEG = "jpeg"

    @property
    def extension(self) -> str:
        """Return the canonical file extension, including the dot."""
        return ".png" if self is ExportFormat.PNG else ".jpg"

    @property
    def mime_type(self) -> str:
        """Return the IANA media type for the format."""
        return "image/png" if self is ExportFormat.PNG else "image/jpeg"
