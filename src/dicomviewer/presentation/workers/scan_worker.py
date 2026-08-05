"""Worker that runs a study scan on a background thread."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal, Slot

from dicomviewer.application.discovery import DiscoveryError, StudyScanner


class StudyScanWorker(QObject):
    """Runs ``StudyScanner.scan`` off the GUI thread and reports the result.

    The worker is moved to a :class:`QThread` by its owner. On completion the
    owner must quit and recycle the thread; the worker emits one terminal
    signal per run.
    """

    finished = Signal(object)  # StudyTree
    failed = Signal(str)

    def __init__(self, scanner: StudyScanner, folder: Path, parent: QObject | None = None) -> None:
        """Create a worker scanning ``folder`` with ``scanner``."""
        super().__init__(parent)
        self._scanner = scanner
        self._folder = folder

    @Slot()
    def run(self) -> None:
        """Execute the scan and emit the outcome."""
        try:
            tree = self._scanner.scan(self._folder)
        except DiscoveryError as exc:
            self.failed.emit(str(exc))
            return
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # never let a scan die silently
            logger.exception("Unexpected scan error for {}", self._folder)
            self.failed.emit(f"Scan error: {exc}")
            return
        self.finished.emit(tree)
