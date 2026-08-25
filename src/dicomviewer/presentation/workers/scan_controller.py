"""Scan lifecycle orchestration.

The :class:`ScanController` owns everything concurrency-related about
scanning a folder: the generation counter that identifies each run, the
``QThread``/worker pair, the main-thread relay and the stale-result filter.
Presentation code reacts to the controller's signals and never touches
threads or workers.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from dicomviewer.application.discovery import StudyScanner
from dicomviewer.domain.studies import StudyTree
from dicomviewer.presentation.workers.scan_worker import StudyScanWorker


class ScanRelay(QObject):
    """Forward worker results to the controller's thread with scan metadata.

    The worker emits from its own thread, so its signals must not deliver
    GUI-affecting work directly. This relay lives in the creating thread,
    carries the generation/folder of one scan, and re-emits with those
    values.
    """

    progress = Signal(int, int, int, str)  # generation, scanned, invalid, folder
    finished = Signal(int, Path, object)  # generation, folder, StudyTree
    failed = Signal(int, str)

    def __init__(self, generation: int, folder: Path, parent: QObject | None = None) -> None:
        """Create a relay for one scan run."""
        super().__init__(parent)
        self._generation = generation
        self._folder = folder

    @Slot(int, int)
    def on_progress(self, scanned: int, invalid: int) -> None:
        """Forward throttled progress counts to the main thread."""
        self.progress.emit(self._generation, scanned, invalid, str(self._folder))

    @Slot(object)
    def on_finished(self, tree: StudyTree) -> None:
        """Forward a completed scan to the main thread."""
        self.finished.emit(self._generation, self._folder, tree)

    @Slot(str)
    def on_failed(self, message: str) -> None:
        """Forward a failed scan to the main thread."""
        self.failed.emit(self._generation, message)


class ScanController(QObject):
    """Runs folder scans on background threads, one at a time.

    Starting a scan supersedes any previous one: the generation counter is
    bumped and results from older runs are discarded, whichever order they
    arrive in. Stopping bumps the generation too, so a stopped scan's late
    results are always stale. The controller owns the thread, worker and
    relay; teardown drops the stored references before the finished thread
    is scheduled for deletion, and only ever for the thread that actually
    finished.
    """

    progress = Signal(int, int, int, str)  # generation, scanned, invalid, folder
    finished = Signal(int, Path, object)  # generation, folder, StudyTree
    failed = Signal(int, str)

    def __init__(self, scanner: StudyScanner, parent: QObject | None = None) -> None:
        """Create an idle controller running scans with ``scanner``."""
        super().__init__(parent)
        self._scanner = scanner
        self._generation = 0
        self._thread: QThread | None = None
        self._worker: StudyScanWorker | None = None
        self._relay: ScanRelay | None = None

    @property
    def generation(self) -> int:
        """Return the current scan generation counter."""
        return self._generation

    @property
    def scan_thread(self) -> QThread | None:
        """Return the live scan thread, if any (diagnostics and tests)."""
        return self._thread

    @property
    def scan_worker(self) -> StudyScanWorker | None:
        """Return the live scan worker, if any (diagnostics and tests)."""
        return self._worker

    @property
    def scan_relay(self) -> ScanRelay | None:
        """Return the live scan relay, if any (diagnostics and tests)."""
        return self._relay

    def start(self, folder: Path) -> None:
        """Start a background scan of ``folder``, superseding any previous one."""
        self._generation += 1
        generation = self._generation
        worker = StudyScanWorker(self._scanner, folder)
        relay = ScanRelay(generation, folder)
        thread = QThread(self)
        thread.setObjectName("study-scan")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(relay.on_progress)
        worker.finished.connect(relay.on_finished)
        worker.failed.connect(relay.on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        relay.progress.connect(self._on_relay_progress)
        relay.finished.connect(self._on_relay_finished)
        relay.failed.connect(self._on_relay_failed)
        thread.finished.connect(self._on_thread_finished)
        self._worker = worker
        self._thread = thread
        self._relay = relay
        thread.start()

    def stop(self) -> None:
        """Abort a running scan and wait for its thread to finish."""
        if self._thread is None or not self._thread.isRunning():
            return
        self._generation += 1
        self._thread.requestInterruption()
        self._thread.wait(3000)

    @Slot(int, int, int, str)
    def _on_relay_progress(self, generation: int, scanned: int, invalid: int, folder: str) -> None:
        """Re-emit progress unless it belongs to a superseded scan."""
        if generation != self._generation:
            return
        self.progress.emit(generation, scanned, invalid, folder)

    @Slot(int, Path, object)
    def _on_relay_finished(self, generation: int, folder: Path, tree: StudyTree) -> None:
        """Re-emit completion unless it belongs to a superseded scan."""
        if generation != self._generation:
            return
        self.finished.emit(generation, folder, tree)

    @Slot(int, str)
    def _on_relay_failed(self, generation: int, message: str) -> None:
        """Re-emit failure unless it belongs to a superseded scan."""
        if generation != self._generation:
            return
        self.failed.emit(generation, message)

    @Slot()
    def _on_thread_finished(self) -> None:
        """Release a finished scan thread and its worker objects.

        ``QThread.finished`` is emitted once the thread's event loop has
        stopped, so the thread is guaranteed not running here. All references
        are dropped *before* ``deleteLater()`` is scheduled; once the deferred
        deletion runs, nothing in this controller points at the QThread
        again, so a deleted C++ object is never dereferenced.

        The sender is used instead of ``self._thread`` so an older thread
        that finishes after a newer scan has started never deletes (or
        clears the references of) the current scan.
        """
        thread = self.sender()
        if not isinstance(thread, QThread):
            return
        if self._thread is thread:
            self._thread = None
            self._worker = None
            self._relay = None
        thread.deleteLater()
