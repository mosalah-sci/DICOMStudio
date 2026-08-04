"""Application ports for exporting visual results.

The presentation captures the current viewport as an RGBA
:class:`RenderedImage` and hands it to an :class:`ImageExporter`, which
encodes it into PNG or JPEG bytes or files. The exchange type stays Qt-free
so the codec implementation can live entirely in Infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dicomviewer.application.viewing import RenderedImage
from dicomviewer.domain.exceptions.base import DicomViewerError
from dicomviewer.domain.export import ExportFormat


class ExportError(DicomViewerError):
    """Raised when a view cannot be encoded or written."""


class ImageExporter(Protocol):
    """Encodes a rendered view into PNG or JPEG output."""

    def encode(
        self,
        image: RenderedImage,
        format: ExportFormat,
        quality: int = 90,
    ) -> bytes:
        """Return the encoded payload for ``image`` in ``format``.

        ``quality`` applies to lossy JPEG encoding. Raises
        :class:`ExportError` if the image cannot be encoded.
        """
        ...

    def write(
        self,
        image: RenderedImage,
        format: ExportFormat,
        path: Path,
        quality: int = 90,
    ) -> None:
        """Write ``image`` encoded in ``format`` to ``path``.

        ``quality`` applies to lossy JPEG encoding. Raises
        :class:`ExportError` if the image cannot be written.
        """
        ...
