"""Focused tests for :class:`ScanController` lifecycle orchestration.

The stale-generation suppression tests moved here from the MainWindow
characterization suite during R1.3: the controller owns the generation
filter, so the equivalent coverage now pins signal-level filtering while
the window suite keeps covering the presentation reactions.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from tests.qt_utils import pump_until

from dicomviewer.application.discovery import DiscoveryError
from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.presentation.workers.scan_controller import ScanController


def _sample_tree(marker: str = "s-ct") -> StudyTree:
    series = Series(marker, "CT", 1, "Chest", (Image(Path("a.dcm"), 1),))
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


class _Recorder:
    """Collects every controller signal emission in delivery order."""

    def __init__(self, controller: ScanController) -> None:
        self.events: list[tuple[str, tuple[object, ...]]] = []
        controller.progress.connect(lambda *args: self.events.append(("progress", args)))
        controller.finished.connect(lambda *args: self.events.append(("finished", args)))
        controller.failed.connect(lambda *args: self.events.append(("failed", args)))

    def of(self, kind: str) -> list[tuple[object, ...]]:
        return [args for name, args in self.events if name == kind]


def _instant(tree: StudyTree, progress: list[tuple[int, int]] | None = None):
    """Behavior completing immediately, optionally emitting progress first."""

    def scan(folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        for scanned, invalid in progress or []:
            on_progress(scanned, invalid)
        return tree

    return scan


def _failing(message: str):
    """Behavior that always fails."""

    def scan(folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        raise DiscoveryError(message)

    return scan


class _BlockUntilReleased:
    """Behavior that blocks until released, then optionally reports."""

    def __init__(
        self,
        tree: StudyTree | None = None,
        *,
        error: str | None = None,
        progress: list[tuple[int, int]] | None = None,
    ) -> None:
        self.tree = tree
        self.error = error
        self.progress = progress or []
        self.started = threading.Event()
        self.release = threading.Event()
        self.done = threading.Event()

    def __call__(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        self.started.set()
        self.release.wait(timeout=10.0)
        for scanned, invalid in self.progress:
            on_progress(scanned, invalid)
        self.done.set()
        if self.error is not None:
            raise DiscoveryError(self.error)
        return self.tree  # type: ignore[return-value]


class _ScriptedScanner:
    """StudyScanner double serving one queued behavior per scan call."""

    def __init__(self, *behaviors: Callable[..., StudyTree]) -> None:
        self.behaviors = list(behaviors)

    def scan(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        behavior = self.behaviors.pop(0)
        return behavior(folder, should_cancel, on_progress)


def test_idle_controller_has_generation_zero_and_stop_is_a_noop(qapp) -> None:
    controller = ScanController(_ScriptedScanner())
    recorder = _Recorder(controller)
    controller.stop()
    qapp.processEvents()
    assert controller.generation == 0
    assert controller.scan_thread is None
    assert controller.scan_worker is None
    assert controller.scan_relay is None
    assert recorder.events == []


def test_successful_scan_emits_progress_then_finished_and_cleans_up(qapp, tmp_path: Path) -> None:
    tree = _sample_tree()
    controller = ScanController(_ScriptedScanner(_instant(tree, progress=[(5, 2)])))
    recorder = _Recorder(controller)
    folder = tmp_path / "studies"

    controller.start(folder)
    assert controller.generation == 1
    assert pump_until(qapp, lambda: controller.scan_thread is None)
    qapp.processEvents()

    assert recorder.of("progress") == [(1, 5, 2, str(folder))]
    assert recorder.of("finished") == [(1, folder, tree)]
    assert recorder.of("failed") == []
    assert controller.scan_worker is None
    assert controller.scan_relay is None


def test_failed_scan_emits_failed_and_cleans_up(qapp, tmp_path: Path) -> None:
    controller = ScanController(_ScriptedScanner(_failing("Folder not found: X")))
    recorder = _Recorder(controller)

    controller.start(tmp_path / "missing")
    assert controller.generation == 1
    assert pump_until(qapp, lambda: controller.scan_thread is None)
    qapp.processEvents()

    assert recorder.of("failed") == [(1, "Folder not found: X")]
    assert recorder.of("finished") == []
    assert controller.scan_thread is None
    assert controller.scan_worker is None
    assert controller.scan_relay is None


def test_superseded_finished_is_not_forwarded(qapp, tmp_path: Path) -> None:
    old_tree = _sample_tree("old-series")
    new_tree = _sample_tree("newest-series")
    blocked = _BlockUntilReleased(old_tree)
    controller = ScanController(_ScriptedScanner(blocked, _instant(new_tree)))
    recorder = _Recorder(controller)
    first = tmp_path / "first"
    second = tmp_path / "second"

    controller.start(first)
    assert pump_until(qapp, blocked.started.is_set)

    controller.start(second)
    assert controller.generation == 2
    assert pump_until(qapp, lambda: controller.scan_thread is None)
    qapp.processEvents()

    # Release the superseded run after the newer one fully completed: its
    # late completion must be dropped and its teardown must not resurrect
    # or clear any references.
    blocked.release.set()
    assert pump_until(qapp, blocked.done.is_set)
    for _ in range(5):
        qapp.processEvents()

    assert recorder.of("finished") == [(2, second, new_tree)]
    assert controller.generation == 2
    assert controller.scan_thread is None
    assert controller.scan_worker is None
    assert controller.scan_relay is None


def test_superseded_progress_is_not_forwarded(qapp, tmp_path: Path) -> None:
    blocked = _BlockUntilReleased(progress=[(7, 3)])
    controller = ScanController(_ScriptedScanner(blocked, _instant(_sample_tree())))
    recorder = _Recorder(controller)

    controller.start(tmp_path / "first")
    assert pump_until(qapp, blocked.started.is_set)
    controller.start(tmp_path / "second")
    assert pump_until(qapp, lambda: controller.scan_thread is None)

    blocked.release.set()
    assert pump_until(qapp, blocked.done.is_set)
    for _ in range(5):
        qapp.processEvents()

    assert recorder.of("progress") == []
    assert len(recorder.of("finished")) == 1


def test_superseded_failed_is_not_forwarded(qapp, tmp_path: Path) -> None:
    blocked = _BlockUntilReleased(error="late failure")
    controller = ScanController(_ScriptedScanner(blocked, _instant(_sample_tree())))
    recorder = _Recorder(controller)

    controller.start(tmp_path / "first")
    assert pump_until(qapp, blocked.started.is_set)
    controller.start(tmp_path / "second")
    assert pump_until(qapp, lambda: controller.scan_thread is None)

    blocked.release.set()
    assert pump_until(qapp, blocked.done.is_set)
    for _ in range(5):
        qapp.processEvents()

    assert recorder.of("failed") == []


def test_stop_bumps_generation_and_drops_late_results(qapp, tmp_path: Path) -> None:
    class _Slow:
        def scan(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
            time.sleep(0.15)
            return _sample_tree()

    controller = ScanController(_Slow())
    recorder = _Recorder(controller)

    controller.start(tmp_path / "studies")
    assert controller.generation == 1
    controller.stop()
    assert controller.generation == 2

    assert pump_until(qapp, lambda: controller.scan_thread is None)
    qapp.processEvents()
    # The slow scan still ran to completion, but its results belong to a
    # superseded generation and are dropped entirely.
    assert recorder.events == []
    assert controller.scan_worker is None
    assert controller.scan_relay is None
