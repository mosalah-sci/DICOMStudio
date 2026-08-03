"""Background thumbnail generation using a bounded thread pool."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from dicomviewer.application.discovery import ThumbnailService
from dicomviewer.domain.studies import Image
from dicomviewer.domain.thumbnail import Thumbnail


class ThumbnailLoader(QObject):
    """Generates thumbnails off the GUI thread and reports them by signal.

    ``thumbnail_ready`` is emitted from the pool threads; Qt delivers it to
    receivers in their own threads (the GUI thread), so no locking is needed
    in the consumer.
    """

    thumbnail_ready = Signal(str, Path, object)  # series uid, image path, Thumbnail

    def __init__(
        self,
        service: ThumbnailService,
        parent: QObject | None = None,
        *,
        max_threads: int = 2,
    ) -> None:
        """Create a loader backed by ``service`` with a bounded thread pool."""
        super().__init__(parent)
        self._service = service
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max_threads)

    def request(self, series_uid: str, image: Image, size: int) -> None:
        """Queue a thumbnail generation for ``image``."""
        self._pool.start(_ThumbnailRunnable(self._service, image, size, series_uid, self))

    def cancel_pending(self) -> None:
        """Drop queued jobs; jobs already running complete on their own."""
        self._pool.clear()


class _ThumbnailRunnable(QRunnable):
    """One thumbnail generation job."""

    def __init__(
        self,
        service: ThumbnailService,
        image: Image,
        size: int,
        series_uid: str,
        emitter: ThumbnailLoader,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._service = service
        self._image = image
        self._size = size
        self._series_uid = series_uid
        self._emitter = emitter

    def run(self) -> None:
        """Generate the thumbnail and emit it, tolerating all failures."""
        thumbnail: Thumbnail | None = None
        try:
            thumbnail = self._service.generate(self._image, self._size)
        except Exception:
            logger.debug("Thumbnail generation failed: {}", self._image.path)
            thumbnail = None
        if thumbnail is not None:
            self._emitter.thumbnail_ready.emit(self._series_uid, self._image.path, thumbnail)
