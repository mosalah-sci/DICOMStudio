"""Qt-backed export of composited views to PNG and JPEG.

The exporter encodes an RGBA :class:`RenderedImage` into PNG or JPEG bytes or
files using the Qt image codecs. PNG is lossless; JPEG is lossy with a quality
setting. This is the only place image codecs are invoked, keeping the rest of
the codebase free of Qt specifics.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage, QImageWriter

from dicomviewer.application.export import ExportError
from dicomviewer.application.viewing import RenderedImage
from dicomviewer.domain.export import ExportFormat


class QtImageExporter:
    """Encodes rendered views to PNG or JPEG using the Qt image codecs."""

    def encode(
        self,
        image: RenderedImage,
        format: ExportFormat,
        quality: int = 90,
    ) -> bytes:
        """Return the ``format``-encoded payload for ``image``."""
        if not image.validate():
            raise ExportError("Cannot encode an invalid image")
        qimage = _to_qimage(image)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        try:
            writer = QImageWriter(buffer, format.value.encode("ascii"))
            writer.setQuality(quality)
            if not writer.write(qimage):
                raise ExportError(
                    f"Could not encode image as {format.value.upper()}: {writer.errorString()}"
                )
            return bytes(buffer.data().data())
        finally:
            buffer.close()

    def write(
        self,
        image: RenderedImage,
        format: ExportFormat,
        path: Path,
        quality: int = 90,
    ) -> None:
        """Write ``image`` encoded in ``format`` to ``path``."""
        if not image.validate():
            raise ExportError("Cannot encode an invalid image")
        path = Path(path)
        try:
            qimage = _to_qimage(image)
            writer = QImageWriter(str(path), format.value.encode("ascii"))
            writer.setQuality(quality)
            if not writer.write(qimage):
                raise ExportError(f"Could not write export file {path}: {writer.errorString()}")
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"Could not export image to {path}: {exc}") from exc
        logger.info("Exported {} image to {}", format.value.upper(), path)


def _to_qimage(rendered: RenderedImage) -> QImage:
    """Build an owned, display-ready QImage from a rendered RGBA frame."""
    image = QImage(
        bytes(rendered.data),
        rendered.width,
        rendered.height,
        rendered.stride,
        QImage.Format.Format_ARGB32,
    )
    if image.isNull():
        raise ExportError("Could not build an image from the rendered data")
    return image.copy()
