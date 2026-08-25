"""Main application window."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import (
    QByteArray,
    QMimeData,
    QObject,
    QStandardPaths,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QWidget,
)

from dicomviewer.application.annotation import AnnotationCollection
from dicomviewer.application.discovery import StudyScanner, ThumbnailService
from dicomviewer.application.export import ExportError, ImageExporter
from dicomviewer.application.inspection import TagInspector
from dicomviewer.application.measurement import MeasurementCollection
from dicomviewer.application.metadata import MetadataService
from dicomviewer.application.processing import ImageAnalyzer
from dicomviewer.application.settings_manager import SettingsManager
from dicomviewer.application.viewing import PixelDecoder, ViewRenderer
from dicomviewer.application.window_state_store import WindowState, WindowStateStore
from dicomviewer.domain.annotation import AnnotationKind
from dicomviewer.domain.export import ExportFormat
from dicomviewer.domain.image_processing import (
    WINDOW_PRESETS,
    WindowPreset,
    find_window_preset,
)
from dicomviewer.domain.measurement import MeasurementKind
from dicomviewer.domain.settings import (
    MeasurementSettings,
    PresetsSettings,
    Settings,
    SettingsError,
    ViewingSettings,
    WorkspaceSettings,
)
from dicomviewer.domain.studies import Image, Series, StudyTree
from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.actions.assembly import (
    MenuHandles,
    create_toolbar,
    populate_menu_bar,
    populate_recent_folders_menu,
    refresh_window_presets_menu,
)
from dicomviewer.presentation.dialogs.about_dialog import AboutDialog
from dicomviewer.presentation.dialogs.preset_manager_dialog import PresetManagerDialog
from dicomviewer.presentation.dialogs.settings_dialog import SettingsDialog
from dicomviewer.presentation.dialogs.tag_inspector_dialog import TagInspectorDialog
from dicomviewer.presentation.feedback.error_presenter import ErrorPresenter
from dicomviewer.presentation.imaging.rendered_image import to_qimage
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.theme.theme_controller import ThemeController
from dicomviewer.presentation.theme.themes import THEMES
from dicomviewer.presentation.widgets.metadata_panel import MetadataPanel
from dicomviewer.presentation.widgets.sidebar_drawer import SidebarDrawer
from dicomviewer.presentation.widgets.status_bar import StatusBar
from dicomviewer.presentation.widgets.study_explorer_panel import StudyExplorerPanel
from dicomviewer.presentation.widgets.viewer_overlays import SeriesOverlayInfo
from dicomviewer.presentation.widgets.viewer_panel import ViewerPanel
from dicomviewer.presentation.workers.scan_worker import StudyScanWorker
from dicomviewer.shared.constants import SIDEBAR_WIDTHS

_STATE_VERSION = 1


class _ScanRelay(QObject):
    """Forward worker results to the main thread with scan metadata.

    The worker emits from its own thread, so its signals must not deliver
    GUI-affecting work directly. This relay lives in the main thread, carries
    the generation/folder of one scan, and re-emits with those values.
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


class MainWindow(QMainWindow):
    """Root window hosting the professional application shell.

    Composes the menu bar, toolbar, status bar and the three-panel dock
    workspace (study explorer, viewer, metadata). Window geometry and dock
    layout are persisted across sessions.
    """

    def __init__(
        self,
        app_name: str,
        version: str,
        theme_controller: ThemeController,
        settings_manager: SettingsManager,
        window_state_store: WindowStateStore,
        icon_provider: IconProvider,
        study_scanner: StudyScanner,
        thumbnail_service: ThumbnailService,
        pixel_decoder: PixelDecoder,
        view_renderer: ViewRenderer,
        image_analyzer: ImageAnalyzer,
        metadata_service: MetadataService,
        image_exporter: ImageExporter,
        tag_inspector: TagInspector,
        screenshot_dir: Path | None = None,
        error_presenter: ErrorPresenter | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the window and assemble its complete shell."""
        super().__init__(parent)
        self._app_name = app_name
        self._version = version
        self._theme_controller = theme_controller
        self._settings_manager = settings_manager
        self._window_state_store = window_state_store
        self._icon_provider = icon_provider
        self.setWindowIcon(icon_provider.brand_icon())
        self._study_scanner = study_scanner
        self._thumbnail_service = thumbnail_service
        self._pixel_decoder = pixel_decoder
        self._view_renderer = view_renderer
        self._image_analyzer = image_analyzer
        self._metadata_service = metadata_service
        self._image_exporter = image_exporter
        self._tag_inspector = tag_inspector
        self._screenshot_dir = screenshot_dir
        self._scan_thread: QThread | None = None
        self._scan_worker: StudyScanWorker | None = None
        self._scan_relay: _ScanRelay | None = None
        self._scan_generation = 0
        self._current_series: Series | None = None
        self._study_tree: StudyTree | None = None
        self._preset_actions: tuple[QAction, ...] = ()
        self._presets_menu: QMenu | None = None
        self._recent_menu: QMenu | None = None
        self._error_presenter = error_presenter or ErrorPresenter()
        self._fullscreen_chrome: dict[QWidget, bool] = {}

        self.setWindowTitle(f"{app_name} - v{version}")
        self.setMinimumSize(960, 600)
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        self._build_workspace()
        self._catalog = self._build_catalog()
        self._status_bar = StatusBar(version)
        self.setStatusBar(self._status_bar)
        handles: MenuHandles = populate_menu_bar(
            self.menuBar(),
            self._catalog,
            window_presets=WINDOW_PRESETS,
            on_window_preset=self._apply_window_preset,
            on_clear_measurements=self._clear_measurements,
            on_clear_annotations=self._clear_annotations,
            on_manage_presets=self._manage_window_presets,
        )
        self._preset_actions = handles.preset_actions
        self._presets_menu = handles.presets_menu
        self._toolbar = create_toolbar(self, self._catalog)
        self.addToolBar(self._toolbar)
        self._build_recent_folders_menu()
        self._apply_viewing_preferences()

        self._capture_default_layout()
        self._restore_persisted_layout()
        self._apply_workspace_settings()
        self._sync_sidebar_toggles()
        self._sync_viewer_actions(self._viewer_panel.has_image)
        theme_name = self._theme_controller.current_theme
        self._status_bar.set_theme(THEMES[theme_name].display_name)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt virtual override
        """Stop any running scan and persist the window layout on close."""
        self._stop_scan()
        self._save_window_state()
        self._persist_workspace_settings()
        super().closeEvent(event)

    def action(self, action_id: ActionId) -> QAction:
        """Return the action identified by ``action_id``."""
        return self._catalog.action(action_id)

    def _build_catalog(self) -> ActionCatalog:
        """Create the action catalog wired to this window's handlers."""
        return ActionCatalog(
            self,
            self._icon_provider,
            handlers={
                ActionId.OPEN_FOLDER: self._open_folder,
                ActionId.SETTINGS: self._open_settings,
                ActionId.TOGGLE_STUDY_EXPLORER: self._toggle_study_explorer,
                ActionId.TOGGLE_METADATA: self._toggle_metadata,
                ActionId.RESTORE_LAYOUT: self._restore_default_layout,
                ActionId.FULLSCREEN: self._toggle_fullscreen,
                ActionId.ABOUT: self._show_about,
                ActionId.EXIT: self._exit_application,
                ActionId.FIT_TO_WINDOW: self._viewer_panel.fit_to_window,
                ActionId.ZOOM_IN: self._viewer_panel.zoom_in,
                ActionId.ZOOM_OUT: self._viewer_panel.zoom_out,
                ActionId.RESET_VIEW: self._viewer_panel.reset_view,
                ActionId.WINDOW_LEVEL: self._viewer_panel.reset_window_level,
                ActionId.ROTATE_CW: self._viewer_panel.rotate_cw,
                ActionId.ROTATE_CCW: self._viewer_panel.rotate_ccw,
                ActionId.FLIP_HORIZONTAL: self._viewer_panel.flip_horizontally,
                ActionId.FLIP_VERTICAL: self._viewer_panel.flip_vertically,
                ActionId.INVERT: self._viewer_panel.toggle_invert,
                ActionId.PLAY_CINE: self._viewer_panel.toggle_playback,
                ActionId.MEASURE: self._toggle_measure,
                ActionId.ANNOTATE_POINT: self._annotate_point,
                ActionId.ANNOTATE_ARROW: self._annotate_arrow,
                ActionId.ANNOTATE_TEXT: self._annotate_text,
                ActionId.CLEAR_MEASUREMENTS: self._clear_measurements,
                ActionId.CLEAR_ANNOTATIONS: self._clear_annotations,
                ActionId.TOGGLE_INFO_OVERLAY: self._toggle_info_overlay,
                ActionId.MANAGE_WINDOW_PRESETS: self._manage_window_presets,
                ActionId.EXPORT_IMAGE: self._export_image,
                ActionId.SCREENSHOT: self._capture_screenshot,
                ActionId.COPY_IMAGE: self._copy_image,
                ActionId.INSPECT_DICOM: self._inspect_dicom,
            },
        )

    def _build_workspace(self) -> None:
        """Create the central drawer workspace around the viewer.

        The Study Explorer slides on the left and Metadata on the right, both
        arranged in a single horizontal layout with the viewer between them so
        the viewer naturally reclaims the space a drawer releases while it
        slides.
        """
        self._study_explorer_panel = StudyExplorerPanel(
            self, self._icon_provider, thumbnail_service=self._thumbnail_service
        )
        self._study_explorer_panel.series_activated.connect(self._on_series_activated)
        self._study_explorer_panel.inspect_requested.connect(self._inspect_image)
        self._metadata_panel = MetadataPanel(
            self,
            self._icon_provider,
            metadata_service=self._metadata_service,
        )

        self._viewer_panel = ViewerPanel(
            self,
            self._icon_provider,
            decoder=self._pixel_decoder,
            renderer=self._view_renderer,
            analyzer=self._image_analyzer,
        )
        self._viewer_panel.content_changed.connect(self._sync_viewer_actions)
        self._viewer_panel.zoom_changed.connect(self._on_zoom_changed)
        self._viewer_panel.window_level_changed.connect(self._on_window_level_changed)
        self._viewer_panel.slice_changed.connect(self._on_slice_changed)
        self._viewer_panel.measurements_changed.connect(self._on_measurements_changed)
        self._viewer_panel.measure_mode_changed.connect(self._sync_measure_action)
        self._viewer_panel.annotations_changed.connect(self._on_annotations_changed)
        self._viewer_panel.annotation_mode_changed.connect(self._sync_annotation_actions)
        self._viewer_panel.playback_changed.connect(self._on_playback_changed)
        self._viewer_panel.open_folder_requested.connect(self._open_folder)
        self._viewer_panel.escape_pressed.connect(self._on_viewer_escape)

        self._study_explorer_drawer = SidebarDrawer(
            self,
            "Study Explorer",
            self._study_explorer_panel,
            side="left",
            open_width=SIDEBAR_WIDTHS["study_explorer"],
        )
        self._study_explorer_drawer.open_changed.connect(self._sync_sidebar_toggles)
        self._metadata_drawer = SidebarDrawer(
            self,
            "Metadata",
            self._metadata_panel,
            side="right",
            open_width=SIDEBAR_WIDTHS["metadata"],
        )
        self._metadata_drawer.open_changed.connect(self._sync_sidebar_toggles)

        workspace = QWidget(self)
        workspace.setObjectName("workspaceContainer")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._study_explorer_drawer)
        layout.addWidget(self._viewer_panel, 1)
        layout.addWidget(self._metadata_drawer)
        self.setCentralWidget(workspace)

    def _capture_default_layout(self) -> None:
        """Snapshot the default window layout for later restoration."""
        self._default_dock_state = self.saveState(_STATE_VERSION)

    def _restore_persisted_layout(self) -> None:
        """Apply the saved geometry and window layout, when one exists.

        A layout that cannot be applied (incompatible or damaged) is replaced
        with the default layout so both side drawers stay open and a loaded
        study can never be rendered inaccessible by a broken save.
        """
        state = self._window_state_store.load()
        if state is None:
            return
        self.restoreGeometry(QByteArray(state.geometry))
        if not self.restoreState(QByteArray(state.dock_state), _STATE_VERSION):
            logger.warning("Ignoring incompatible dock layout; using the default layout.")
            self._restore_default_layout()

    def _apply_workspace_settings(self) -> None:
        """Restore sidebar open state and widths from the typed settings.

        The typed settings are the source of truth for the sidebars. Restoring
        skips the slide animation so a persisted collapsed drawer starts
        collapsed; the View/Window menu toggles are synced to match.
        """
        workspace = self._settings_manager.current_settings.workspace
        self._study_explorer_drawer.set_open_width(workspace.study_explorer_width)
        self._metadata_drawer.set_open_width(workspace.metadata_width)
        self._study_explorer_drawer.set_open(workspace.study_explorer_visible, animate=False)
        self._metadata_drawer.set_open(workspace.metadata_visible, animate=False)
        self._sync_sidebar_toggles()

    def _persist_workspace_settings(self) -> None:
        """Save the current sidebar open state and widths to the settings."""
        workspace = WorkspaceSettings(
            study_explorer_visible=self._study_explorer_drawer.is_open,
            metadata_visible=self._metadata_drawer.is_open,
            study_explorer_width=self._study_explorer_drawer.open_width,
            metadata_width=self._metadata_drawer.open_width,
        )
        updated = replace(self._settings_manager.current_settings, workspace=workspace)
        try:
            self._settings_manager.update(updated)
        except SettingsError as exc:
            logger.warning("Could not persist the workspace layout: {}", exc)

    def _save_window_state(self) -> None:
        """Serialize geometry and dock layout to the window state store."""
        state = WindowState(
            geometry=bytes(self.saveGeometry().data()),
            dock_state=bytes(self.saveState(_STATE_VERSION).data()),
        )
        try:
            self._window_state_store.save(state)
        except OSError as exc:
            logger.error("Could not save window layout: {}", exc)

    def _open_folder(self) -> None:
        """Prompt for a folder and start scanning it for DICOM studies."""
        folder = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if not folder:
            return
        self._start_scan(Path(folder))

    def _start_scan(self, folder: Path) -> None:
        """Start a background scan of ``folder``, cancelling any previous one."""
        self._scan_generation += 1
        generation = self._scan_generation
        try:
            self._settings_manager.add_recent_folder(folder)
        except SettingsError as exc:
            self._error_presenter.show_warning(
                self,
                "Recent Folder Not Saved",
                "This folder will be scanned, but it could not be added to the recent list.",
                detail=str(exc),
            )
        self._refresh_recent_menu()
        self._study_explorer_panel.show_scanning(folder)
        self._metadata_panel.show_initial()
        self._status_bar.showMessage(f"Scanning {folder}…")

        worker = StudyScanWorker(self._study_scanner, folder)
        relay = _ScanRelay(generation, folder)
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
        relay.progress.connect(self._on_scan_progress)
        relay.finished.connect(self._on_scan_finished)
        relay.failed.connect(self._on_scan_failed)
        thread.finished.connect(self._on_scan_thread_finished)
        self._scan_worker = worker
        self._scan_thread = thread
        self._scan_relay = relay
        thread.start()

    def _on_scan_thread_finished(self) -> None:
        """Release the finished scan thread and its worker objects.

        ``QThread.finished`` is emitted once the thread's event loop has
        stopped, so the thread is guaranteed not running here. All references
        are dropped *before* ``deleteLater()`` is scheduled; once the deferred
        deletion runs, nothing in this window points at the QThread again,
        so a deleted C++ object is never dereferenced.

        The sender is used instead of ``self._scan_thread`` so an older thread
        that finishes after a newer scan has started never deletes (or clears
        the references of) the current scan.
        """
        thread = self.sender()
        if not isinstance(thread, QThread):
            return
        if self._scan_thread is thread:
            self._scan_thread = None
            self._scan_worker = None
            self._scan_relay = None
        thread.deleteLater()

    def _on_scan_progress(self, generation: int, scanned: int, invalid: int, folder: str) -> None:
        """Keep the user informed while a scan is in progress."""
        del invalid
        if generation != self._scan_generation:
            return
        self._status_bar.showMessage(f"Scanning {folder}… {scanned} files")

    def _on_scan_finished(self, generation: int, folder: Path, tree: StudyTree) -> None:
        """Populate the study explorer and report the scan outcome.

        A restored layout may hide the study explorer; once a scan actually
        loads studies the explorer is always brought back so the loaded data
        can be browsed and selected.
        """
        if generation != self._scan_generation:
            return
        self._study_tree = tree
        self._study_explorer_panel.set_study_tree(tree)
        if not tree.has_content():
            self._status_bar.showMessage(f"No DICOM studies found in {folder}.")
            return
        if not self._study_explorer_drawer.is_open:
            self._study_explorer_drawer.set_open(True)
        message = (
            f"Scan complete: {tree.patient_count} patients, {tree.study_count} studies, "
            f"{tree.series_count} series."
        )
        if tree.invalid_files:
            suffix = "" if tree.invalid_files == 1 else "s"
            message += f" {tree.invalid_files} invalid file{suffix} ignored."
        self._status_bar.showMessage(message)

    def _on_scan_failed(self, generation: int, message: str) -> None:
        """Report a failed scan without interrupting the session."""
        if generation != self._scan_generation:
            return
        self._status_bar.showMessage("Scan failed.")
        self._study_explorer_panel.show_initial()
        self._error_presenter.show_error(
            self,
            "Scan Failed",
            "The selected folder could not be scanned.",
            detail=message,
        )

    def _stop_scan(self) -> None:
        """Abort a running scan and wait for its thread to finish."""
        if self._scan_thread is None or not self._scan_thread.isRunning():
            return
        self._scan_generation += 1
        self._scan_thread.requestInterruption()
        self._scan_thread.wait(3000)

    def _on_series_activated(self, series: Series, index: int) -> None:
        """Display the activated series in the viewer and metadata panel."""
        self._current_series = series
        self._update_series_info(series)
        self._viewer_panel.load_series(series.images, index)
        self._metadata_panel.show_series(series.images, index)
        self._apply_default_window_preset()
        self._status_bar.showMessage(
            f"Loaded {series.modality or 'series'} with {series.image_count} images."
        )

    def _update_series_info(self, series: Series) -> None:
        """Build and push the info overlay details for ``series``.

        The owning patient/study rows are resolved through the domain model;
        series activated outside a scanned tree (tests, future loaders)
        simply show their own metadata.
        """
        patient_name = patient_id = birth_date = patient_sex = study_description = ""
        tree = self._study_tree
        if tree is not None:
            context = tree.find_series_context(series.series_instance_uid)
            if context is not None:
                patient, study = context
                patient_name = patient.name
                patient_id = patient.patient_id
                birth_date = patient.birth_date
                patient_sex = patient.sex
                study_description = study.description
        self._viewer_panel.set_series_info(
            SeriesOverlayInfo(
                patient_name=patient_name,
                patient_id=patient_id,
                birth_date=birth_date,
                patient_sex=patient_sex,
                study_description=study_description,
                series_description=series.description,
                modality=series.modality,
                series_number=series.series_number,
            )
        )

    def _on_slice_changed(self, index: int, count: int) -> None:
        """Show the metadata and thumbnail selection of the new slice."""
        self._metadata_panel.show_slice(index)
        self._study_explorer_panel.set_active_slice(index)

    def _current_image(self) -> Image | None:
        """Return the image currently displayed in the viewer, if any."""
        series = self._current_series
        if series is None or not series.images:
            return None
        index = min(max(self._viewer_panel.current_slice, 0), len(series.images) - 1)
        return series.images[index]

    def _inspect_image(self, image: Image) -> None:
        """Open the DICOM dataset inspector for ``image``."""
        dialog = TagInspectorDialog(self, image.path, self._tag_inspector)
        dialog.exec()

    def _inspect_dicom(self) -> None:
        """Inspect the DICOM tags of the image currently displayed."""
        image = self._current_image()
        if image is not None:
            self._inspect_image(image)

    def _apply_window_preset(self, preset: WindowPreset) -> None:
        """Apply a named clinical window preset to the viewer."""
        self._viewer_panel.apply_preset(preset)
        self._status_bar.showMessage(f"Window preset: {preset.name}")

    def _sync_viewer_actions(self, has_image: bool) -> None:
        """Enable or disable the view actions based on loaded content."""
        for action_id in (
            ActionId.FIT_TO_WINDOW,
            ActionId.ZOOM_IN,
            ActionId.ZOOM_OUT,
            ActionId.RESET_VIEW,
            ActionId.WINDOW_LEVEL,
            ActionId.ROTATE_CW,
            ActionId.ROTATE_CCW,
            ActionId.FLIP_HORIZONTAL,
            ActionId.FLIP_VERTICAL,
            ActionId.INVERT,
            ActionId.MEASURE,
            ActionId.ANNOTATE_POINT,
            ActionId.ANNOTATE_ARROW,
            ActionId.ANNOTATE_TEXT,
            ActionId.EXPORT_IMAGE,
            ActionId.SCREENSHOT,
            ActionId.COPY_IMAGE,
            ActionId.INSPECT_DICOM,
        ):
            self._catalog.action(action_id).setEnabled(has_image)
        play_enabled = has_image and self._viewer_panel.slice_count > 1
        if not play_enabled:
            self._viewer_panel.pause_playback()
        self._catalog.action(ActionId.PLAY_CINE).setEnabled(play_enabled)
        for action in self._preset_actions:
            action.setEnabled(has_image)

    def _toggle_measure(self) -> None:
        """Toggle the measurement tool on or off."""
        action = self._catalog.action(ActionId.MEASURE)
        if action.isChecked():
            self._viewer_panel.set_measure_mode(MeasurementKind.DISTANCE)
        else:
            self._viewer_panel.set_measure_mode(None)

    def _sync_measure_action(self, kind: object) -> None:
        """Keep the Measure action checked to match the active tool."""
        checked = kind is not None
        action = self._catalog.action(ActionId.MEASURE)
        if action.isChecked() != checked:
            action.setChecked(checked)

    def _annotate_point(self) -> None:
        """Toggle the point annotation tool on or off."""
        self._toggle_annotation_mode(AnnotationKind.POINT, ActionId.ANNOTATE_POINT)

    def _annotate_arrow(self) -> None:
        """Toggle the arrow annotation tool on or off."""
        self._toggle_annotation_mode(AnnotationKind.ARROW, ActionId.ANNOTATE_ARROW)

    def _annotate_text(self) -> None:
        """Toggle the text annotation tool on or off."""
        self._toggle_annotation_mode(AnnotationKind.TEXT, ActionId.ANNOTATE_TEXT)

    def _toggle_annotation_mode(self, kind: AnnotationKind, action_id: ActionId) -> None:
        """Enter ``kind`` when its action was checked, leave it otherwise."""
        action = self._catalog.action(action_id)
        self._viewer_panel.set_annotation_mode(kind if action.isChecked() else None)

    def _sync_annotation_actions(self, kind: object) -> None:
        """Keep the three annotate actions checked to match the active tool."""
        expected = {
            ActionId.ANNOTATE_POINT: AnnotationKind.POINT,
            ActionId.ANNOTATE_ARROW: AnnotationKind.ARROW,
            ActionId.ANNOTATE_TEXT: AnnotationKind.TEXT,
        }
        for action_id, mode in expected.items():
            action = self._catalog.action(action_id)
            checked = kind == mode
            if action.isChecked() != checked:
                action.setChecked(checked)

    def _on_annotations_changed(self, annotations: AnnotationCollection) -> None:
        """Enable Clear Annotations only while annotations exist."""
        has_any = annotations.has_any()
        self._catalog.action(ActionId.CLEAR_ANNOTATIONS).setEnabled(has_any)

    def _clear_annotations(self) -> None:
        """Remove every annotation and report it in the status bar."""
        self._viewer_panel.clear_annotations()
        self._status_bar.showMessage("Cleared all annotations.")

    def _on_playback_changed(self, playing: bool) -> None:
        """Mirror cine playback state onto the Play Series action."""
        action = self._catalog.action(ActionId.PLAY_CINE)
        if action.isChecked() != playing:
            action.setChecked(playing)

    def _toggle_info_overlay(self) -> None:
        """Show or hide the patient/study information overlay."""
        enabled = self._catalog.action(ActionId.TOGGLE_INFO_OVERLAY).isChecked()
        self._viewer_panel.set_show_info_overlay(enabled)

    def _manage_window_presets(self) -> None:
        """Open the window-preset manager dialog.

        Mutations inside the dialog are published immediately through the
        apply callback, so nothing is left to do when it closes.
        """
        PresetManagerDialog(
            self,
            presets=self._settings_manager.current_settings.presets,
            on_apply=self._apply_custom_presets,
        ).exec()

    def _apply_custom_presets(self, presets: PresetsSettings) -> None:
        """Persist a new custom preset list and rebuild the presets menu."""
        updated = replace(
            self._settings_manager.current_settings,
            presets=presets,
        )
        try:
            self._settings_manager.update(updated)
        except SettingsError as exc:
            self._error_presenter.show_warning(
                self,
                "Presets Not Saved",
                "The preset changes apply for this session, but they could not be saved.",
                detail=str(exc),
            )
        self._refresh_preset_menu()

    def _combined_presets(self) -> tuple[WindowPreset, ...]:
        """Return built-in presets followed by the user's custom ones."""
        return (*WINDOW_PRESETS, *self._settings_manager.current_settings.presets.custom)

    def _refresh_preset_menu(self) -> None:
        """Rebuild the Window Presets submenu from the current settings."""
        if self._presets_menu is None:
            return
        self._preset_actions = refresh_window_presets_menu(
            self._presets_menu,
            self._combined_presets(),
            self._apply_window_preset,
        )
        has_image = self._viewer_panel.has_image
        for action in self._preset_actions:
            action.setEnabled(has_image)

    def _clear_measurements(self) -> None:
        """Remove every measurement and report it in the status bar."""
        self._viewer_panel.clear_measurements()
        self._status_bar.showMessage("Cleared all measurements.")

    def _export_image(self) -> None:
        """Prompt for a PNG or JPEG destination and export the current view."""
        if not self._viewer_panel.has_image:
            return
        default_name = f"DICOMStudio_export_{_timestamp()}.png"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Image",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)",
        )
        if not path:
            return
        export_format = _export_format_for(Path(path), selected_filter)
        if export_format is None:
            self._status_bar.showMessage("Unsupported export format.")
            return
        self._save_export(Path(path), export_format)

    def _save_export(self, path: Path, export_format: ExportFormat) -> None:
        """Capture the current view and write it to ``path`` in ``export_format``."""
        try:
            capture = self._viewer_panel.capture_view()
            self._image_exporter.write(capture, export_format, path)
        except (ExportError, ValueError, OSError) as exc:
            self._error_presenter.show_error(
                self,
                "Export Failed",
                "The current view could not be exported.",
                detail=str(exc),
            )
            return
        self._status_bar.showMessage(f"Exported {export_format.value.upper()} to {path}")

    def _capture_screenshot(self) -> None:
        """Save a timestamped PNG screenshot of the current view."""
        directory = self._screenshot_dir or _default_screenshot_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._error_presenter.show_error(
                self,
                "Screenshot Failed",
                "The screenshots folder could not be created.",
                detail=str(exc),
            )
            return
        self._save_export(directory / f"DICOMStudio_{_timestamp()}.png", ExportFormat.PNG)

    def _copy_image(self) -> None:
        """Copy the current view to the system clipboard."""
        if not self._viewer_panel.has_image:
            return
        try:
            capture = self._viewer_panel.capture_view()
        except ValueError as exc:
            self._error_presenter.show_error(
                self,
                "Copy Failed",
                "The current view could not be captured.",
                detail=str(exc),
            )
            return
        QApplication.clipboard().setImage(to_qimage(capture))
        self._status_bar.showMessage("Copied the current view to the clipboard.")

    def _on_measurements_changed(self, measurements: MeasurementCollection) -> None:
        """Enable Clear Measurements only while measurements exist."""
        has_any = measurements.has_any()
        self._catalog.action(ActionId.CLEAR_MEASUREMENTS).setEnabled(has_any)
        if has_any:
            self._status_bar.showMessage(f"{measurements.counts()} measurements stored.")

    def _on_zoom_changed(self, zoom: float) -> None:
        """Report the current zoom level in the status bar."""
        self._status_bar.showMessage(f"Zoom {zoom * 100.0:.0f}%")

    def _on_window_level_changed(self, center: object, width: float) -> None:
        """Report the current window/level in the status bar."""
        if width > 0 and isinstance(center, (int, float)):
            self._status_bar.showMessage(f"Window width {width:.0f} · Level {center:.0f}")
        else:
            self._status_bar.showMessage("Window/level: automatic")

    def _sync_sidebar_toggles(self) -> None:
        """Force the Window menu toggles to match the drawer open state."""
        self._catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).setChecked(
            self._study_explorer_drawer.is_open
        )
        self._catalog.action(ActionId.TOGGLE_METADATA).setChecked(self._metadata_drawer.is_open)

    def _open_settings(self) -> None:
        """Open the settings dialog with live preview and applied preferences."""
        settings = self._settings_manager.current_settings
        dialog = SettingsDialog(
            self,
            current_theme=settings.appearance.theme,
            viewing=settings.viewing,
            measurements=settings.measurements,
            on_theme_changed=self._change_theme,
            on_apply=self._apply_settings,
            on_reset=self._reset_settings,
        )
        dialog.exec()

    def _apply_settings(
        self,
        viewing: ViewingSettings,
        measurements: MeasurementSettings,
    ) -> None:
        """Persist the chosen preferences and apply them to the viewer."""
        updated = replace(
            self._settings_manager.current_settings,
            viewing=viewing,
            measurements=measurements,
        )
        try:
            self._settings_manager.update(updated)
        except SettingsError as exc:
            self._error_presenter.show_warning(
                self,
                "Settings Not Saved",
                "The new preferences apply for this session, but they could not be saved.",
                detail=str(exc),
            )
        self._apply_viewing_preferences()
        self._apply_default_window_preset()
        self._status_bar.showMessage("Settings saved.")

    def _reset_settings(self) -> Settings:
        """Restore the bundled defaults and refresh the whole application."""
        try:
            settings = self._settings_manager.reset()
        except SettingsError as exc:
            self._error_presenter.show_error(
                self,
                "Settings Reset Failed",
                "The default settings could not be restored.",
                detail=str(exc),
            )
            settings = self._settings_manager.current_settings
        self._theme_controller.apply_current()
        self._catalog.refresh_icons()
        self._status_bar.set_theme(THEMES[settings.appearance.theme].display_name)
        self._apply_viewing_preferences()
        self._refresh_preset_menu()
        self._refresh_recent_menu()
        return settings

    def _apply_viewing_preferences(self) -> None:
        """Push the persisted viewing and measurement settings to the viewer."""
        settings = self._settings_manager.current_settings
        self._viewer_panel.set_max_cache(settings.viewing.max_cache_size)
        self._viewer_panel.set_smooth_scaling(settings.viewing.smooth_scaling)
        self._viewer_panel.set_show_statistics_overlay(settings.viewing.show_statistics_overlay)
        self._viewer_panel.set_show_measurement_overlay(settings.viewing.show_measurement_overlay)
        self._viewer_panel.set_show_info_overlay(settings.viewing.show_info_overlay)
        self._catalog.action(ActionId.TOGGLE_INFO_OVERLAY).setChecked(
            settings.viewing.show_info_overlay
        )
        self._viewer_panel.set_cine_fps(settings.viewing.cine_fps)
        self._viewer_panel.set_measurement_color(settings.measurements.color)

    def _apply_default_window_preset(self) -> None:
        """Apply the configured default window preset to the current series."""
        preset_name = self._settings_manager.current_settings.viewing.default_window_preset
        if not preset_name or not self._viewer_panel.has_image:
            return
        preset = find_window_preset(preset_name)
        if preset is None:
            preset = self._settings_manager.current_settings.presets.find(preset_name)
        if preset is not None:
            self._viewer_panel.apply_preset(preset)

    def _build_recent_folders_menu(self) -> None:
        """Insert the Recent Studies submenu into the File menu."""
        file_menu = next(
            (menu for menu in self.menuBar().findChildren(QMenu) if menu.title() == "&File"),
            None,
        )
        if file_menu is None:
            return
        recent_menu = QMenu("Recent &Studies", file_menu)
        separators = [action for action in file_menu.actions() if action.isSeparator()]
        if separators:
            file_menu.insertMenu(separators[0], recent_menu)
        else:
            file_menu.addMenu(recent_menu)
        self._recent_menu = recent_menu
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        """Rebuild the Recent Studies submenu from the persisted settings."""
        if self._recent_menu is None:
            return
        populate_recent_folders_menu(
            self._recent_menu,
            self._settings_manager.current_settings.recent.folders,
            self._open_recent_folder,
            on_clear_recent=self._clear_recent_studies,
        )

    def _clear_recent_studies(self) -> None:
        """Clear the recent studies list and rebuild its menu."""
        try:
            self._settings_manager.clear_recent_folders()
        except SettingsError as exc:
            self._error_presenter.show_warning(
                self,
                "Recent Studies Not Cleared",
                "The recent studies list could not be cleared.",
                detail=str(exc),
            )
        self._refresh_recent_menu()
        self._status_bar.showMessage("Recent studies cleared.")

    def _open_recent_folder(self, folder: Path) -> None:
        """Open a recently used folder, dropping it when it no longer exists."""
        if not folder.is_dir():
            try:
                self._settings_manager.remove_recent_folder(folder)
            except SettingsError as exc:
                self._error_presenter.show_warning(
                    self,
                    "Recent Folder Not Removed",
                    "The folder no longer exists, but it could not be removed "
                    "from the recent list.",
                    detail=str(exc),
                )
            self._refresh_recent_menu()
            self._status_bar.showMessage("That folder no longer exists.")
            return
        self._start_scan(folder)

    def open_path(self, path: Path) -> None:
        """Open a file or folder passed on the command line (file association).

        Individual DICOM files are opened by scanning their parent directory,
        matching how the study explorer groups files by study and series.
        """
        if path.is_dir():
            self._start_scan(path)
        elif path.is_file():
            self._start_scan(path.parent)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept drags that carry at least one existing file or folder path."""
        if self._droppable_paths(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """Keep accepting file and folder drags over the whole window."""
        if self._droppable_paths(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Start the existing loading pipeline for the dropped paths."""
        paths = self._droppable_paths(event.mimeData())
        if not paths:
            return
        self._handle_dropped_paths(paths)
        event.acceptProposedAction()

    def _droppable_paths(self, mime: QMimeData | None) -> list[Path]:
        """Return the existing local file/folder paths carried by ``mime``."""
        if mime is None or not mime.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.exists():
                paths.append(path)
        return paths

    def _handle_dropped_paths(self, paths: Sequence[Path]) -> None:
        """Load a dropped folder, or a dropped file's containing folder.

        Reuses the exact same scan pipeline as the Open Folder action and the
        command line, so there is exactly one loading system.
        """
        folders = [path for path in paths if path.is_dir()]
        if folders:
            self._start_scan(folders[0])
            return
        files = [path for path in paths if path.is_file()]
        if files:
            self._start_scan(files[0].parent)

    def _on_viewer_escape(self) -> None:
        """Exit fullscreen when Esc is pressed outside a tool."""
        if self.isFullScreen():
            self._exit_fullscreen()
            self._catalog.action(ActionId.FULLSCREEN).setChecked(False)

    def _change_theme(self, theme_name: str) -> None:
        """Switch the theme, refresh icons and update the status bar."""
        try:
            self._theme_controller.switch(theme_name)
        except SettingsError as exc:
            # The snapshot is adopted in memory either way; persistence
            # failures are non-fatal and only reported to the user.
            self._error_presenter.show_warning(
                self,
                "Theme Preference Not Saved",
                "The theme changed for this session, but it could not be saved.",
                detail=str(exc),
            )
        self._catalog.refresh_icons()
        self._status_bar.set_theme(THEMES[theme_name].display_name)

    def _show_about(self) -> None:
        """Open the about dialog."""
        dialog = AboutDialog(self, self._icon_provider, self._app_name, self._version)
        dialog.exec()

    def _toggle_study_explorer(self) -> None:
        """Open or collapse the study explorer drawer."""
        checked = self._catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
        self._study_explorer_drawer.set_open(checked)

    def _toggle_metadata(self) -> None:
        """Open or collapse the metadata drawer."""
        checked = self._catalog.action(ActionId.TOGGLE_METADATA).isChecked()
        self._metadata_drawer.set_open(checked)

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen viewer mode.

        In fullscreen the menu bar, toolbar, status bar and sidebars are
        hidden to maximize the image area; the previous visibility of every
        element is restored on exit. Viewer state is untouched throughout.
        """
        if self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()
        self._catalog.action(ActionId.FULLSCREEN).setChecked(self.isFullScreen())

    def _enter_fullscreen(self) -> None:
        """Remember the chrome visibility, hide it and enter fullscreen."""
        self._fullscreen_chrome = {
            self.menuBar(): self.menuBar().isVisible(),
            self._toolbar: self._toolbar.isVisible(),
            self.statusBar(): self.statusBar().isVisible(),
            self._study_explorer_drawer: self._study_explorer_drawer.isVisible(),
            self._metadata_drawer: self._metadata_drawer.isVisible(),
        }
        self._set_chrome_visible(False)
        self.showFullScreen()

    def _exit_fullscreen(self) -> None:
        """Leave fullscreen and restore the previously visible chrome."""
        self.showNormal()
        self._set_chrome_visible(True)
        self._fullscreen_chrome = {}

    def _set_chrome_visible(self, visible: bool) -> None:
        """Show or hide the window chrome and sidebars.

        Drawer open/collapsed state is untouched, so a collapsed drawer stays
        collapsed and an open one stays open across the fullscreen toggle.
        """
        for widget in self._fullscreen_chrome:
            widget.setVisible(visible and self._fullscreen_chrome[widget])

    def _exit_application(self) -> None:
        """Close the window, quitting the application."""
        self.close()

    def _restore_default_layout(self) -> None:
        """Restore the default layout and open both drawers at default widths."""
        self.restoreState(self._default_dock_state, _STATE_VERSION)
        self._study_explorer_drawer.set_open_width(SIDEBAR_WIDTHS["study_explorer"])
        self._metadata_drawer.set_open_width(SIDEBAR_WIDTHS["metadata"])
        self._study_explorer_drawer.set_open(True)
        self._metadata_drawer.set_open(True)
        self._sync_sidebar_toggles()


def _export_format_for(path: Path, selected_filter: str) -> ExportFormat | None:
    """Return the export format implied by ``path`` or the selected filter."""
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg") or "JPEG" in selected_filter:
        return ExportFormat.JPEG
    if suffix == ".png" or "PNG" in selected_filter:
        return ExportFormat.PNG
    return None


def _timestamp() -> str:
    """Return a compact, sortable timestamp for default file names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _default_screenshot_dir() -> Path:
    """Return the folder where screenshots are saved by default."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    base = Path(location) if location else Path.home()
    return base / "dicomviewer-screenshots"
