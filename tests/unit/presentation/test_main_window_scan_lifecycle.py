"""Characterization tests for the MainWindow scan lifecycle.

These tests pin the CURRENT behavior of ``MainWindow._start_scan`` /
``_stop_scan`` and the window's presentation reactions to scan results,
ahead of and during the R1.3 ScanController extraction. They describe
existing behavior, not desired future behavior:

- both starting a scan and stopping one bump the controller's generation
  counter, so a stopped scan's late results are always stale;
- the window adopts results only through its connected handler reactions;
- the scan thread teardown releases the delegated thread/worker/relay
  references (sender-based cleanup lives in the controller and is covered
  by ``test_scan_controller.py``, together with the stale-generation
  signal filtering that moved there).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication
from tests.qt_utils import pump_until

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.presentation.windows.main_window import MainWindow


def _sample_tree(marker: str = "s-ct") -> StudyTree:
    series = Series(marker, "CT", 1, "Chest", (Image(Path("a.dcm"), 1),))
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


class _BlockBehavior:
    """Scan behavior that blocks until released, then returns its tree."""

    def __init__(self, tree: StudyTree) -> None:
        self.tree = tree
        self.started = threading.Event()
        self.release = threading.Event()
        self.done = threading.Event()

    def __call__(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        self.started.set()
        self.release.wait(timeout=10.0)
        self.done.set()
        return self.tree


def _instant_behavior(tree: StudyTree):
    """Scan behavior completing immediately."""

    def scan(folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        return tree

    return scan


class _QueuedScanner:
    """StudyScanner double serving one queued behavior per scan call."""

    def __init__(self, *behaviors) -> None:
        self.behaviors = list(behaviors)

    def scan(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        behavior = self.behaviors.pop(0)
        return behavior(folder, should_cancel, on_progress)


class _SlowScanner:
    """StudyScanner double that takes a fixed, short time to finish."""

    def __init__(self, tree: StudyTree, delay: float = 0.2) -> None:
        self.tree = tree
        self.delay = delay

    def scan(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        time.sleep(self.delay)
        return self.tree


def _release_threads(window: MainWindow, qapp: QApplication) -> None:
    assert pump_until(
        qapp, lambda: window._scan_thread is None or not window._scan_thread.isRunning()
    )
    qapp.processEvents()


def test_stop_scan_without_active_scan_is_a_noop(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    window._stop_scan()
    assert window._scan_generation == 0
    assert window._scan_thread is None


def test_stop_scan_bumps_generation_and_drops_late_results(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = _SlowScanner(_sample_tree(), delay=0.2)
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()

    window._start_scan(folder)
    assert window._scan_generation == 1
    window._stop_scan()
    assert window._scan_generation == 2

    # The slow scan still completes and emits finished, but its results are
    # stale by then: the explorer keeps showing the scanning state and no
    # study tree is adopted. The thread teardown still releases everything.
    assert pump_until(qapp, lambda: window._scan_thread is None)
    qapp.processEvents()
    assert window._study_tree is None
    assert window._study_explorer_panel._stack.currentIndex() == 1
    assert window._scan_worker is None
    assert window._scan_relay is None


def test_close_stops_a_running_scan(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = _SlowScanner(_sample_tree(), delay=0.2)
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()

    window._start_scan(folder)
    assert window._scan_generation == 1
    window.close()
    qapp.processEvents()
    assert window._scan_generation == 2
    assert pump_until(qapp, lambda: window._scan_thread is None)


def test_old_thread_finishing_after_newer_scan_does_not_disturb_it(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    blocked = _BlockBehavior(_sample_tree("old-series"))
    newest_tree = _sample_tree("newest-series")
    window = make_window(study_scanner=_QueuedScanner(blocked, _instant_behavior(newest_tree)))
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    window._start_scan(first)
    assert window._scan_generation == 1
    assert pump_until(qapp, blocked.started.is_set)

    # A newer scan supersedes the blocked one and completes immediately.
    window._start_scan(second)
    assert window._scan_generation == 2
    assert pump_until(qapp, lambda: window._study_tree is newest_tree)
    assert pump_until(qapp, lambda: window._scan_thread is None)
    qapp.processEvents()

    # Now release the old scan. Its finished/teardown arrive while the
    # window has NO active scan: the stale result must be dropped and the
    # sender-based teardown must delete the old thread without resurrecting
    # or clearing anything.
    blocked.release.set()
    assert pump_until(qapp, blocked.done.is_set)
    for _ in range(5):
        qapp.processEvents()

    assert window._study_tree is newest_tree
    assert window._scan_thread is None
    assert window._scan_worker is None
    assert window._scan_relay is None
