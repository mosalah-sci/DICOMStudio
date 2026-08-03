"""Smoke tests for the main application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QWidget

from dicomviewer.application.discovery import DiscoveryError
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


def test_main_window_has_expected_title(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window.windowTitle() == "DICOM Viewer Professional - v0.5.0"


def test_main_window_shows_an_empty_state(make_window: Callable[..., MainWindow]) -> None:
    window = make_window(version="1.0.0")
    central = window.centralWidget()
    assert isinstance(central, QWidget)
    labels = central.findChildren(QLabel)
    assert any("No study loaded" in label.text() for label in labels)


def test_main_window_has_menus_and_docks(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window.menuBar() is not None
    assert window.findChild(QDockWidget, "studyExplorerDock") is not None
    assert window.findChild(QDockWidget, "metadataDock") is not None
    assert window.statusBar() is not None


def test_dock_toggle_action_shows_and_hides_the_panel(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    dock = window.findChild(QDockWidget, "studyExplorerDock")
    toggle = window.action(ActionId.TOGGLE_STUDY_EXPLORER)
    assert dock is not None
    toggle.setChecked(False)
    toggle.trigger()
    assert not dock.isVisible()


def test_unavailable_actions_are_disabled(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert not window.action(ActionId.OPEN_FILES).isEnabled()
    assert not window.action(ActionId.MEASURE).isEnabled()
    assert window.action(ActionId.OPEN_FOLDER).isEnabled()
    assert window.action(ActionId.SETTINGS).isEnabled()
    assert not window.action(ActionId.ZOOM_IN).isEnabled()


def test_closing_the_window_persists_the_layout(
    make_window: Callable[..., MainWindow],
    tmp_path: Path,
) -> None:
    window = make_window()
    window.close()
    assert (tmp_path / "window_state.json").exists()


def test_theme_switch_updates_the_status_bar(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    window._change_theme("light")
    labels = window.statusBar().findChildren(QLabel)
    assert any(label.text() == "Light" for label in labels)


def test_start_scan_populates_explorer_and_status(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    assert scanner.calls == [folder]
    assert "1 patients, 1 studies, 1 series" in window.statusBar().currentMessage()
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )


def test_failed_scan_reverts_and_reports(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(error=DiscoveryError("Folder not found: X"))
    window = make_window(study_scanner=scanner)
    window._start_scan(tmp_path / "missing")
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 0)
    assert "Scan failed" in window.statusBar().currentMessage()
    assert window._error_presenter.errors
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )


def test_empty_scan_reports_no_studies(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=StudyTree.empty(Path(".")))
    window = make_window(study_scanner=scanner)
    window._start_scan(tmp_path / "empty")
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 2)
    assert "No DICOM studies found" in window.statusBar().currentMessage()
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )


def test_activating_a_series_loads_the_viewer(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    panel._tree.itemActivated.emit(series_item, 0)
    assert window._viewer_panel.has_image
    assert window._viewer_panel.current_slice == 0
    assert window.action(ActionId.ZOOM_IN).isEnabled()
    assert window.action(ActionId.FIT_TO_WINDOW).isEnabled()


def test_viewer_actions_are_disabled_without_content(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    assert not window.action(ActionId.ZOOM_IN).isEnabled()
    assert not window.action(ActionId.RESET_VIEW).isEnabled()
    assert all(not action.isEnabled() for action in window._preset_actions)


def test_window_preset_menu_exists(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window._preset_actions
    assert any(action.text() == "CT Lung" for action in window._preset_actions)


def test_applying_a_window_preset_updates_the_viewer(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    panel._tree.itemActivated.emit(series_item, 0)
    assert window._viewer_panel.has_image
    assert all(action.isEnabled() for action in window._preset_actions)
    lung = next(action for action in window._preset_actions if action.text() == "CT Lung")
    lung.trigger()
    assert window._viewer_panel._viewer.viewport.window_center == -500.0
    assert window._viewer_panel._viewer.viewport.window_width == 1500.0
    assert "CT Lung" in window.statusBar().currentMessage()
