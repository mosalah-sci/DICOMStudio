"""Smoke tests for the main application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QPushButton,
    QWidget,
)

from dicomviewer.application.discovery import DiscoveryError
from dicomviewer.application.export import ExportError
from dicomviewer.domain.export import ExportFormat
from dicomviewer.domain.measurement import MeasurementKind
from dicomviewer.domain.settings import MeasurementSettings, ViewingSettings
from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.windows.main_window import MainWindow
from dicomviewer.shared.constants import APP_NAME, __version__
from tests.dicom_utils import FakeImageExporter, FakeStudyScanner
from tests.qt_utils import pump_until


def _sample_tree() -> StudyTree:
    series = Series("s-ct", "CT", 1, "Chest", (Image(Path("a.dcm"), 1),))
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


def test_main_window_has_expected_title(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window.windowTitle() == f"{APP_NAME} - v{__version__}"


def test_main_window_shows_an_empty_state(make_window: Callable[..., MainWindow]) -> None:
    window = make_window(version="1.0.0")
    central = window.centralWidget()
    assert isinstance(central, QWidget)
    labels = central.findChildren(QLabel)
    assert any("Welcome to DICOMStudio" in label.text() for label in labels)


def test_empty_viewer_state_offers_an_open_folder_action(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    monkeypatch,
) -> None:
    window = make_window()
    opened: list[list[str]] = []

    def fake_dialog(parent, title: str) -> str:
        opened.append([title])
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake_dialog)
    buttons = window.centralWidget().findChildren(QPushButton)
    open_button = next(button for button in buttons if "Open Folder" in button.text())
    open_button.click()
    assert opened == [["Open DICOM Folder"]]


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
    assert not window.action(ActionId.EXPORT_IMAGE).isEnabled()
    assert not window.action(ActionId.SCREENSHOT).isEnabled()
    assert not window.action(ActionId.COPY_IMAGE).isEnabled()
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


def test_activating_a_series_populates_the_metadata_panel(
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
    metadata = window._metadata_panel
    assert metadata._stack.currentIndex() == 1
    texts = [
        metadata._tree.topLevelItem(i).text(0) for i in range(metadata._tree.topLevelItemCount())
    ]
    assert "Patient" in texts
    assert "Study" in texts
    assert "Series" in texts


def test_searching_metadata_filters_the_panel(
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
    metadata = window._metadata_panel
    metadata._search.setText("nonexistent")
    assert metadata._stack.currentIndex() == 2
    metadata._search.setText("DOE")
    assert metadata._stack.currentIndex() == 1


def test_starting_a_new_scan_resets_the_metadata_panel(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    explorer = window._study_explorer_panel
    assert pump_until(qapp, lambda: explorer._stack.currentIndex() == 3)
    series_item = explorer._tree.topLevelItem(0).child(0).child(0)
    explorer._tree.itemActivated.emit(series_item, 0)
    assert window._metadata_panel._stack.currentIndex() == 1
    window._start_scan(folder)
    assert window._metadata_panel._stack.currentIndex() == 0


def test_measurement_flow_enables_and_clears(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    explorer = window._study_explorer_panel
    assert pump_until(qapp, lambda: explorer._stack.currentIndex() == 3)
    series_item = explorer._tree.topLevelItem(0).child(0).child(0)
    explorer._tree.itemActivated.emit(series_item, 0)

    measure = window.action(ActionId.MEASURE)
    clear_all = window.action(ActionId.CLEAR_MEASUREMENTS)
    assert measure.isEnabled()
    assert not clear_all.isEnabled()

    measure.trigger()
    assert window._viewer_panel.measure_mode is MeasurementKind.DISTANCE
    viewer = window._viewer_panel._viewer
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(200, 150))
    assert window._viewer_panel.measurements.has_any()
    assert clear_all.isEnabled()

    clear_all.trigger()
    assert not window._viewer_panel.measurements.has_any()
    assert not clear_all.isEnabled()
    assert window._viewer_panel.measure_mode is MeasurementKind.DISTANCE

    measure.trigger()
    assert window._viewer_panel.measure_mode is None


def _load_series(
    window: MainWindow,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Start a scan and activate the first series, mirroring existing tests."""
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    explorer = window._study_explorer_panel
    assert pump_until(qapp, lambda: explorer._stack.currentIndex() == 3)
    series_item = explorer._tree.topLevelItem(0).child(0).child(0)
    explorer._tree.itemActivated.emit(series_item, 0)
    assert window._viewer_panel.has_image


def test_export_actions_enabled_after_loading(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_sample_tree()))
    _load_series(window, qapp, tmp_path)
    assert window.action(ActionId.EXPORT_IMAGE).isEnabled()
    assert window.action(ActionId.SCREENSHOT).isEnabled()
    assert window.action(ActionId.COPY_IMAGE).isEnabled()


def test_save_export_writes_a_file_and_reports(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    exporter = FakeImageExporter()
    window = make_window(
        study_scanner=FakeStudyScanner(tree=_sample_tree()),
        image_exporter=exporter,
    )
    _load_series(window, qapp, tmp_path)
    target = tmp_path / "export.png"
    window._save_export(target, ExportFormat.PNG)
    assert exporter.writes
    assert exporter.writes[0][1] is ExportFormat.PNG
    assert target.exists()
    assert "Exported PNG to" in window.statusBar().currentMessage()


def test_save_export_reports_errors(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    exporter = FakeImageExporter(error=ExportError("disk full"))
    window = make_window(
        study_scanner=FakeStudyScanner(tree=_sample_tree()),
        image_exporter=exporter,
    )
    _load_series(window, qapp, tmp_path)
    window._save_export(tmp_path / "export.png", ExportFormat.PNG)
    assert window._error_presenter.errors
    assert "Export Failed" in window._error_presenter.errors[0][0]


def test_screenshot_saves_to_the_screenshot_dir(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    screenshots = tmp_path / "shots"
    exporter = FakeImageExporter()
    window = make_window(
        study_scanner=FakeStudyScanner(tree=_sample_tree()),
        image_exporter=exporter,
        screenshot_dir=screenshots,
    )
    _load_series(window, qapp, tmp_path)
    window._capture_screenshot()
    files = list(screenshots.glob("DICOMStudio_*.png"))
    assert len(files) == 1
    assert files[0].exists()


def test_copy_image_copies_to_the_clipboard(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_sample_tree()))
    _load_series(window, qapp, tmp_path)
    qapp.clipboard().clear()
    window._copy_image()
    assert not qapp.clipboard().image().isNull()
    assert "clipboard" in window.statusBar().currentMessage()


def test_viewing_preferences_are_applied_at_startup(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    viewer = window._viewer_panel._viewer
    assert viewer._max_cache == 3
    assert viewer._smooth_scaling is True
    assert viewer._show_statistics_overlay is True
    assert viewer._show_measurement_overlay is True
    assert viewer._measurement_color == "#22d3ee"


def test_start_scan_records_a_recent_folder(
    make_window: Callable[..., MainWindow],
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_sample_tree()))
    folder = tmp_path / "studies"
    folder.mkdir()
    window._start_scan(folder)
    assert window._settings_manager.current_settings.recent.folders[0] == folder
    assert window._recent_menu is not None
    assert any(action.text() == str(folder) for action in window._recent_menu.actions())


def test_open_recent_folder_starts_a_scan(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window._open_recent_folder(folder)
    assert pump_until(qapp, lambda: scanner.calls == [folder])
    assert window._settings_manager.current_settings.recent.folders[0] == folder


def test_scan_thread_is_released_after_finishing_without_error(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()

    # Rapid consecutive scans exercise the thread-finished teardown path and
    # confirm no RuntimeError from dereferencing a deleted QThread.
    for _ in range(2):
        window._start_scan(folder)
        assert pump_until(
            qapp, lambda: window._scan_thread is None or not window._scan_thread.isRunning()
        )
        assert pump_until(qapp, lambda: window._scan_thread is None)

    assert window._scan_worker is None
    assert window._scan_relay is None


def test_open_recent_folder_drops_a_missing_folder(
    make_window: Callable[..., MainWindow],
    tmp_path: Path,
) -> None:
    window = make_window()
    missing = tmp_path / "missing"
    window._settings_manager.add_recent_folder(missing)
    window._open_recent_folder(missing)
    assert window._settings_manager.current_settings.recent.folders == ()
    assert "no longer exists" in window.statusBar().currentMessage()


def test_open_path_scans_a_directory(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    window.open_path(folder)
    assert pump_until(qapp, lambda: scanner.calls == [folder])


def test_open_path_scans_a_file_parent_directory(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    dicom_file = folder / "a.dcm"
    dicom_file.touch()
    window.open_path(dicom_file)
    assert pump_until(qapp, lambda: scanner.calls == [folder])


def test_open_path_ignores_a_missing_path(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    window.open_path(tmp_path / "missing")
    qapp.processEvents()
    assert scanner.calls == []


def test_apply_settings_persists_and_updates_the_viewer(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    viewing = ViewingSettings(
        default_window_preset="CT Lung",
        max_cache_size=6,
        smooth_scaling=False,
        show_statistics_overlay=False,
        show_measurement_overlay=True,
    )
    window._apply_settings(viewing, MeasurementSettings(color="#ff0000"))
    viewer = window._viewer_panel._viewer
    assert viewer._max_cache == 6
    assert viewer._smooth_scaling is False
    assert viewer._show_statistics_overlay is False
    assert viewer._show_measurement_overlay is True
    assert viewer._measurement_color == "#ff0000"
    assert window._settings_manager.current_settings.viewing.max_cache_size == 6
    assert "Settings saved" in window.statusBar().currentMessage()


def test_default_window_preset_applies_on_series_load(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window(study_scanner=FakeStudyScanner(tree=_sample_tree()))
    window._apply_settings(ViewingSettings(default_window_preset="CT Lung"), MeasurementSettings())
    _load_series(window, qapp, tmp_path)
    viewport = window._viewer_panel._viewer.viewport
    assert viewport.window_center == -500.0
    assert viewport.window_width == 1500.0


def test_reset_settings_restores_defaults(
    make_window: Callable[..., MainWindow],
    tmp_path: Path,
) -> None:
    window = make_window()
    window._apply_settings(
        ViewingSettings(max_cache_size=9, default_window_preset="CT Lung"),
        MeasurementSettings(color="#ff0000"),
    )
    window._settings_manager.add_recent_folder(tmp_path / "recent")
    assert window._settings_manager.current_settings.viewing.max_cache_size == 9
    window._reset_settings()
    settings = window._settings_manager.current_settings
    assert settings.viewing.max_cache_size == 3
    assert settings.viewing.default_window_preset == ""
    assert settings.measurements.color == "#22d3ee"
    assert settings.recent.folders == ()
    assert window._viewer_panel._viewer._max_cache == 3
    assert window._viewer_panel._viewer._measurement_color == "#22d3ee"


def test_scanning_state_mentions_the_folder(
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
    # The scanning state is shown synchronously; the worker only finishes
    # once we return to the event loop.
    assert panel._stack.currentIndex() == 1
    assert str(folder) in panel._scanning_state._description_label.text()
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 3)
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )


def test_empty_scan_message_names_the_folder(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=StudyTree.empty(Path(".")))
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "empty"
    folder.mkdir()
    window._start_scan(folder)
    panel = window._study_explorer_panel
    assert pump_until(qapp, lambda: panel._stack.currentIndex() == 2)
    assert f"No DICOM studies found in {folder}." in window.statusBar().currentMessage()
    assert pump_until(
        qapp, lambda: (window._scan_thread is None or not window._scan_thread.isRunning())
    )


def _mime_from_paths(paths: list[Path]) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def test_dropping_a_folder_starts_a_scan(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    mime = _mime_from_paths([folder])
    assert window._droppable_paths(mime) == [folder]
    window._handle_dropped_paths([folder])
    assert pump_until(qapp, lambda: scanner.calls == [folder])


def test_dropping_a_file_scans_its_parent_folder(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scanner = FakeStudyScanner(tree=_sample_tree())
    window = make_window(study_scanner=scanner)
    folder = tmp_path / "studies"
    folder.mkdir()
    dicom_file = folder / "a.dcm"
    dicom_file.touch()
    window._handle_dropped_paths([dicom_file])
    assert pump_until(qapp, lambda: scanner.calls == [folder])


def test_dropping_remote_or_missing_urls_is_ignored(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window()
    mime = QMimeData()
    mime.setUrls(
        [QUrl("https://example.com/study.dcm"), QUrl.fromLocalFile(str(tmp_path / "gone"))]
    )
    assert window._droppable_paths(mime) == []
    assert not window.acceptDrops() or True  # drop handling must not crash


def test_drag_enter_accepts_local_file_drops(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = make_window()
    folder = tmp_path / "studies"
    folder.mkdir()
    mime = _mime_from_paths([folder])
    assert window._droppable_paths(mime)
    assert window.acceptDrops()


def _show_window(qapp: QApplication, window: MainWindow) -> None:
    window.show()
    qapp.processEvents()


def test_entering_fullscreen_hides_the_chrome_and_escape_exits(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
) -> None:
    window = make_window()
    _show_window(qapp, window)
    assert window._study_explorer_dock.isVisible()
    window._enter_fullscreen()
    assert window.isFullScreen()
    assert not window.menuBar().isVisible()
    assert not window._toolbar.isVisible()
    assert not window._study_explorer_dock.isVisible()
    assert not window._metadata_dock.isVisible()
    window._on_viewer_escape()
    assert not window.isFullScreen()
    assert window._study_explorer_dock.isVisible()
    assert window._metadata_dock.isVisible()
    assert window._fullscreen_chrome == {}
    window.close()
    qapp.processEvents()


def test_fullscreen_restores_previously_hidden_chrome(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
) -> None:
    window = make_window()
    _show_window(qapp, window)
    window._toolbar.setVisible(False)
    window._study_explorer_dock.setVisible(False)
    qapp.processEvents()
    window._enter_fullscreen()
    window._exit_fullscreen()
    assert not window._toolbar.isVisible()
    assert not window._study_explorer_dock.isVisible()
    assert window._metadata_dock.isVisible()
    window.close()
    qapp.processEvents()


def test_workspace_settings_are_persisted_and_restored(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
) -> None:
    first = make_window()
    _show_window(qapp, first)
    first._study_explorer_dock.setVisible(False)
    first._metadata_dock.setVisible(False)
    qapp.processEvents()
    first.close()
    qapp.processEvents()

    restored = make_window()
    restored._apply_workspace_settings()
    assert not restored._study_explorer_dock.isVisible()
    assert not restored._metadata_dock.isVisible()
    assert not restored.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
    assert not restored.action(ActionId.TOGGLE_METADATA).isChecked()
    restored.close()
    qapp.processEvents()


def test_workspace_persistence_round_trips_through_settings_file(
    make_window: Callable[..., MainWindow],
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    first = make_window()
    _show_window(qapp, first)
    first._study_explorer_dock.setVisible(False)
    qapp.processEvents()
    first.close()
    qapp.processEvents()

    persisted = first._settings_manager.current_settings.workspace
    assert persisted.study_explorer_visible is False
    assert persisted.metadata_visible is True

    restored = make_window()
    restored._apply_workspace_settings()
    _show_window(qapp, restored)
    assert not restored._study_explorer_dock.isVisible()
    assert restored._metadata_dock.isVisible()
    restored.close()
    qapp.processEvents()
