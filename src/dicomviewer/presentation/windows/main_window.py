"""Main application window."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QByteArray, QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow, QWidget

from dicomviewer.application.discovery import StudyScanner, ThumbnailService
from dicomviewer.application.viewing import PixelDecoder, ViewRenderer
from dicomviewer.application.window_state_store import WindowState, WindowStateStore
from dicomviewer.domain.studies import Series, StudyTree
from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.actions.assembly import create_toolbar, populate_menu_bar
from dicomviewer.presentation.dialogs.about_dialog import AboutDialog
from dicomviewer.presentation.dialogs.settings_dialog import SettingsDialog
from dicomviewer.presentation.feedback.error_presenter import ErrorPresenter
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.theme.theme_controller import ThemeController
from dicomviewer.presentation.theme.themes import THEMES
from dicomviewer.presentation.widgets.metadata_panel import MetadataPanel
from dicomviewer.presentation.widgets.status_bar import StatusBar
from dicomviewer.presentation.widgets.study_explorer_panel import StudyExplorerPanel
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

    finished = Signal(int, Path, object)  # generation, folder, StudyTree
    failed = Signal(int, str)

    def __init__(self, generation: int, folder: Path, parent: QObject | None = None) -> None:
        """Create a relay for one scan run."""
        super().__init__(parent)
        self._generation = generation
        self._folder = folder

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
        window_state_store: WindowStateStore,
        icon_provider: IconProvider,
        study_scanner: StudyScanner,
        thumbnail_service: ThumbnailService,
        pixel_decoder: PixelDecoder,
        view_renderer: ViewRenderer,
        error_presenter: ErrorPresenter | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the window and assemble its complete shell."""
        super().__init__(parent)
        self._app_name = app_name
        self._version = version
        self._theme_controller = theme_controller
        self._window_state_store = window_state_store
        self._icon_provider = icon_provider
        self._study_scanner = study_scanner
        self._thumbnail_service = thumbnail_service
        self._pixel_decoder = pixel_decoder
        self._view_renderer = view_renderer
        self._scan_thread: QThread | None = None
        self._scan_worker: StudyScanWorker | None = None
        self._scan_relay: _ScanRelay | None = None
        self._scan_generation = 0
        self._error_presenter = error_presenter or ErrorPresenter()

        self.setWindowTitle(f"{app_name} - v{version}")
        self.setMinimumSize(960, 600)
        self.resize(1280, 800)

        self._build_workspace()
        self._catalog = self._build_catalog()
        self._status_bar = StatusBar(version)
        self.setStatusBar(self._status_bar)
        populate_menu_bar(self.menuBar(), self._catalog)
        self.addToolBar(create_toolbar(self, self._catalog))

        self._capture_default_layout()
        self._restore_persisted_layout()
        self._sync_dock_toggles()
        self._sync_viewer_actions(self._viewer_panel.has_image)
        theme_name = self._theme_controller.current_theme
        self._status_bar.set_theme(THEMES[theme_name].display_name)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt virtual override
        """Stop any running scan and persist the window layout on close."""
        self._stop_scan()
        self._save_window_state()
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
            },
        )

    def _build_workspace(self) -> None:
        """Create the central viewer and the two dockable side panels."""
        self._viewer_panel = ViewerPanel(
            self,
            self._icon_provider,
            decoder=self._pixel_decoder,
            renderer=self._view_renderer,
        )
        self._viewer_panel.content_changed.connect(self._sync_viewer_actions)
        self._viewer_panel.zoom_changed.connect(self._on_zoom_changed)
        self._viewer_panel.window_level_changed.connect(self._on_window_level_changed)
        self.setCentralWidget(self._viewer_panel)

        self._study_explorer_panel = StudyExplorerPanel(
            self, self._icon_provider, thumbnail_service=self._thumbnail_service
        )
        self._study_explorer_panel.series_activated.connect(self._on_series_activated)
        self._study_explorer_dock = self._create_dock(
            "studyExplorerDock",
            "Study Explorer",
            self._study_explorer_panel,
        )
        self._metadata_dock = self._create_dock(
            "metadataDock",
            "Metadata",
            MetadataPanel(self, self._icon_provider),
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._study_explorer_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._metadata_dock)

        self._study_explorer_dock.setMinimumWidth(SIDEBAR_WIDTHS["study_explorer"])
        self._metadata_dock.setMinimumWidth(SIDEBAR_WIDTHS["metadata"])
        self.resizeDocks(
            [self._study_explorer_dock, self._metadata_dock],
            [SIDEBAR_WIDTHS["study_explorer"], SIDEBAR_WIDTHS["metadata"]],
            Qt.Orientation.Horizontal,
        )

    def _create_dock(self, object_name: str, title: str, widget: QWidget) -> QDockWidget:
        """Create a closable, floatable, movable dock widget."""
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.visibilityChanged.connect(self._on_dock_visibility_changed)
        return dock

    def _capture_default_layout(self) -> None:
        """Snapshot the default dock layout for later restoration."""
        self._default_dock_state = self.saveState(_STATE_VERSION)

    def _restore_persisted_layout(self) -> None:
        """Apply the saved geometry and dock layout, when one exists."""
        state = self._window_state_store.load()
        if state is None:
            return
        self.restoreGeometry(QByteArray(state.geometry))
        self.restoreState(QByteArray(state.dock_state), _STATE_VERSION)

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
        self._study_explorer_panel.show_scanning()
        self._status_bar.showMessage(f"Scanning {folder}…")

        worker = StudyScanWorker(self._study_scanner, folder)
        relay = _ScanRelay(generation, folder)
        thread = QThread(self)
        thread.setObjectName("study-scan")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(relay.on_finished)
        worker.failed.connect(relay.on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        relay.finished.connect(self._on_scan_finished)
        relay.failed.connect(self._on_scan_failed)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_scan_thread_finished)
        self._scan_worker = worker
        self._scan_thread = thread
        self._scan_relay = relay
        thread.start()

    def _on_scan_thread_finished(self) -> None:
        """Release the finished scan thread reference.

        Keeping the object alive in Python after Qt's deferred deletion has
        run can make garbage collection double-delete it and crash.
        """
        thread = self._scan_thread
        if thread is not None and not thread.isRunning():
            self._scan_thread = None

    def _on_scan_finished(self, generation: int, folder: Path, tree: StudyTree) -> None:
        """Populate the study explorer and report the scan outcome."""
        if generation != self._scan_generation:
            return
        self._study_explorer_panel.set_study_tree(tree)
        if not tree.has_content():
            self._status_bar.showMessage("No DICOM studies found.")
            return
        message = (
            f"Loaded {tree.patient_count} patients, {tree.study_count} studies, "
            f"{tree.series_count} series."
        )
        if tree.invalid_files:
            message += f" {tree.invalid_files} invalid files ignored."
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
        """Display the activated series in the viewer."""
        self._viewer_panel.load_series(series.images, index)
        self._status_bar.showMessage(
            f"Loaded {series.modality or 'series'} with {series.image_count} images."
        )

    def _sync_viewer_actions(self, has_image: bool) -> None:
        """Enable or disable the view actions based on loaded content."""
        for action_id in (
            ActionId.FIT_TO_WINDOW,
            ActionId.ZOOM_IN,
            ActionId.ZOOM_OUT,
            ActionId.RESET_VIEW,
            ActionId.WINDOW_LEVEL,
        ):
            self._catalog.action(action_id).setEnabled(has_image)

    def _on_zoom_changed(self, zoom: float) -> None:
        """Report the current zoom level in the status bar."""
        self._status_bar.showMessage(f"Zoom {zoom * 100.0:.0f}%")

    def _on_window_level_changed(self, center: object, width: float) -> None:
        """Report the current window/level in the status bar."""
        if width > 0 and isinstance(center, (int, float)):
            self._status_bar.showMessage(f"Window width {width:.0f} · Level {center:.0f}")
        else:
            self._status_bar.showMessage("Window/level: automatic")

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        """Keep the View/Window menu toggles in sync with the docks."""
        sender = self.sender()
        if sender is self._study_explorer_dock:
            self._catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).setChecked(visible)
        elif sender is self._metadata_dock:
            self._catalog.action(ActionId.TOGGLE_METADATA).setChecked(visible)

    def _sync_dock_toggles(self) -> None:
        """Force the dock toggles to match the current dock visibility."""
        self._catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).setChecked(
            self._study_explorer_dock.isVisible()
        )
        self._catalog.action(ActionId.TOGGLE_METADATA).setChecked(self._metadata_dock.isVisible())

    def _open_settings(self) -> None:
        """Open the settings dialog with live theme preview."""
        dialog = SettingsDialog(
            self,
            current_theme=self._theme_controller.current_theme,
            on_theme_changed=self._change_theme,
        )
        dialog.exec()

    def _change_theme(self, theme_name: str) -> None:
        """Switch the theme, refresh icons and update the status bar."""
        self._theme_controller.switch(theme_name)
        self._catalog.refresh_icons()
        self._status_bar.set_theme(THEMES[theme_name].display_name)

    def _show_about(self) -> None:
        """Open the about dialog."""
        dialog = AboutDialog(self, self._icon_provider, self._app_name, self._version)
        dialog.exec()

    def _toggle_study_explorer(self) -> None:
        """Show or hide the study explorer dock."""
        checked = self._catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).isChecked()
        self._study_explorer_dock.setVisible(checked)

    def _toggle_metadata(self) -> None:
        """Show or hide the metadata dock."""
        checked = self._catalog.action(ActionId.TOGGLE_METADATA).isChecked()
        self._metadata_dock.setVisible(checked)

    def _toggle_fullscreen(self) -> None:
        """Toggle between fullscreen and normal window state."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _exit_application(self) -> None:
        """Close the window, quitting the application."""
        self.close()

    def _restore_default_layout(self) -> None:
        """Restore the default dock positions and panel widths."""
        self.restoreState(self._default_dock_state, _STATE_VERSION)
        self._study_explorer_dock.setVisible(True)
        self._metadata_dock.setVisible(True)
        self.resizeDocks(
            [self._study_explorer_dock, self._metadata_dock],
            [SIDEBAR_WIDTHS["study_explorer"], SIDEBAR_WIDTHS["metadata"]],
            Qt.Orientation.Horizontal,
        )
        self._sync_dock_toggles()
