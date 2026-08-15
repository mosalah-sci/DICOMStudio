"""Tests for the study scan worker."""

from __future__ import annotations

from pathlib import Path

from tests.dicom_utils import FakeStudyScanner

from dicomviewer.application.discovery import DiscoveryError
from dicomviewer.domain.studies import StudyTree
from dicomviewer.presentation.workers.scan_worker import StudyScanWorker


def test_worker_emits_progress_counts(qapp) -> None:
    scanner = FakeStudyScanner()
    worker = StudyScanWorker(scanner, Path("studies"))
    progress: list = []
    worker.progress.connect(lambda scanned, invalid: progress.append((scanned, invalid)))
    worker.run()
    assert progress == [(1, 0)]


def test_worker_does_not_emit_progress_when_the_scan_throws(qapp) -> None:
    scanner = FakeStudyScanner(error=DiscoveryError("Folder not found: X"))
    worker = StudyScanWorker(scanner, Path("studies"))
    progress: list = []
    worker.progress.connect(progress.append)
    worker.run()
    assert progress == []


def test_worker_emits_finished_with_the_tree(qapp) -> None:
    scanner = FakeStudyScanner()
    worker = StudyScanWorker(scanner, Path("studies"))
    finished: list = []
    failed: list = []
    worker.finished.connect(finished.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert len(finished) == 1
    assert len(failed) == 0
    assert isinstance(finished[0], StudyTree)


def test_worker_emits_failed_with_the_message(qapp) -> None:
    scanner = FakeStudyScanner(error=DiscoveryError("Folder not found: X"))
    worker = StudyScanWorker(scanner, Path("studies"))
    failed: list = []
    worker.failed.connect(failed.append)
    worker.run()
    assert len(failed) == 1
    assert "Folder not found" in failed[0]


def test_worker_emits_failed_for_os_errors(qapp) -> None:
    scanner = FakeStudyScanner(error=PermissionError("denied"))
    worker = StudyScanWorker(scanner, Path("studies"))
    failed: list = []
    worker.failed.connect(failed.append)
    worker.run()
    assert len(failed) == 1


def test_worker_reports_unexpected_errors_instead_of_silently_dying(qapp) -> None:
    scanner = FakeStudyScanner(error=RuntimeError("boom"))
    worker = StudyScanWorker(scanner, Path("studies"))
    finished: list = []
    failed: list = []
    worker.finished.connect(finished.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert len(finished) == 0
    assert len(failed) == 1
    assert "Scan error" in failed[0]
