"""Regression tests for window layout restore and the Study Explorer dock.

These lock in the PACS requirement that a successfully loaded study is never
left unreachable: the Study Explorer must always be visible after a scan that
finds content, regardless of what the persisted layout says.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.windows.main_window import MainWindow
from tests.dicom_utils import FakeStudyScanner
from tests.qt_utils import pump_until


def _sample_tree() -> StudyTree:
    series = Series("s-ct", "CT", 1, "Chest", (Image(Path("a.dcm"), 1),))
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


def _show(qapp: QApplication, window: MainWindow) -> None:
    """Show the window and pump events so dock visibility settles."""
    window.show()
    qapp.processEvents()


def test_first_launch_shows_both_docks(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
) -> None:
    window = make_window()
    _show(qapp, window)
    assert window._study_explorer_dock.isVisible()
    assert window._metadata_dock.isVisible()
    assert window.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
    assert window.action(ActionId.TOGGLE_METADATA).isChecked()
    window.close()
    qapp.processEvents()


def test_restored_layout_keeps_study_explorer_visible(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
) -> None:
    first = make_window()
    _show(qapp, first)
    assert first._study_explorer_dock.isVisible()
    first.close()
    qapp.processEvents()

    restored = make_window()
    _show(qapp, restored)
    assert restored._study_explorer_dock.isVisible()
    assert restored.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
    restored.close()
    qapp.processEvents()


def test_hidden_study_explorer_returns_after_successful_scan(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    first = make_window()
    _show(qapp, first)
    first._study_explorer_dock.setVisible(False)
    qapp.processEvents()
    assert not first._study_explorer_dock.isVisible()
    first.close()
    qapp.processEvents()

    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    _show(qapp, window)
    assert not window._study_explorer_dock.isVisible()
    assert not window.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()

    window._start_scan(tmp_path / "studies")
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    assert window._study_explorer_dock.isVisible()
    assert window.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )
    window.close()
    qapp.processEvents()


def test_corrupted_dock_layout_falls_back_to_visible_docks(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    (tmp_path / "window_state.json").write_text(
        json.dumps(
            {
                "geometry": base64.b64encode(b"geometry").decode("ascii"),
                "dock_state": base64.b64encode(b"not-a-qt-layout").decode("ascii"),
            }
        ),
        encoding="utf-8",
    )
    window = make_window()
    _show(qapp, window)
    assert window._study_explorer_dock.isVisible()
    assert window._metadata_dock.isVisible()
    assert window.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
    window.close()
    qapp.processEvents()


def test_repeated_launch_close_cycles_keep_study_explorer_accessible(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    for cycle in range(3):
        window = make_window(study_scanner=FakeStudyScanner(tree=_sample_tree()))
        _show(qapp, window)
        window._start_scan(tmp_path / f"cycle-{cycle}")
        panel = window._study_explorer_panel
        assert pump_until(qapp, lambda panel=panel: panel._stack.currentIndex() == 3)
        assert window._study_explorer_dock.isVisible()
        assert window.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
        assert pump_until(
            qapp,
            lambda window=window: (
                window._scan_thread is None or not window._scan_thread.isRunning()
            ),
        )
        window.close()
        qapp.processEvents()
