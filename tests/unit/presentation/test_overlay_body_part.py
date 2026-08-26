"""Body-part propagation from scanner to the viewer info overlay (v1.4 M2)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication
from tests.dicom_utils import FakeStudyScanner
from tests.qt_utils import pump_until

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.presentation.windows.main_window import MainWindow


def _tree(body_part: str) -> StudyTree:
    series = Series("s-ct", "CT", 1, "Chest", (Image(Path("a.dcm"), 1),), body_part=body_part)
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


def _load_first_series(window: MainWindow, qapp: QApplication, tmp_path: Path) -> None:
    folder = tmp_path / "studies"
    folder.mkdir(exist_ok=True)
    window._start_scan(folder)
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    panel._tree.itemActivated.emit(series_item, 0)
    qapp.processEvents()


def test_series_body_part_reaches_the_info_overlay(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_tree("CHEST")))
    _load_first_series(window, qapp, tmp_path)

    info = window._viewer_panel._viewer._series_info
    assert info is not None
    assert info.body_part == "CHEST"


def test_empty_body_part_keeps_overlay_fallback(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_tree("")))
    _load_first_series(window, qapp, tmp_path)

    info = window._viewer_panel._viewer._series_info
    assert info is not None
    assert info.body_part == ""
