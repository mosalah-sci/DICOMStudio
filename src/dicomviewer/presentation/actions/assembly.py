"""Menu bar and toolbar assembly from the action catalog."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar, QToolBar

from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.shared.constants import TOOLBAR_ICON_SIZE


def populate_menu_bar(menu_bar: QMenuBar, catalog: ActionCatalog) -> None:
    """Populate the standard application menus from the catalog."""
    file_menu = menu_bar.addMenu("&File")
    _add(file_menu, catalog, ActionId.OPEN_FOLDER)
    _add(file_menu, catalog, ActionId.OPEN_FILES)
    file_menu.addSeparator()
    _add(file_menu, catalog, ActionId.EXPORT_IMAGE)
    file_menu.addSeparator()
    _add(file_menu, catalog, ActionId.SETTINGS)
    file_menu.addSeparator()
    _add(file_menu, catalog, ActionId.EXIT)

    view_menu = menu_bar.addMenu("&View")
    _add(view_menu, catalog, ActionId.FIT_TO_WINDOW)
    _add(view_menu, catalog, ActionId.ZOOM_IN)
    _add(view_menu, catalog, ActionId.ZOOM_OUT)
    _add(view_menu, catalog, ActionId.RESET_VIEW)

    tools_menu = menu_bar.addMenu("&Tools")
    _add(tools_menu, catalog, ActionId.WINDOW_LEVEL)
    _add(tools_menu, catalog, ActionId.MEASURE)
    _add(tools_menu, catalog, ActionId.SCREENSHOT)

    window_menu = menu_bar.addMenu("&Window")
    _add(window_menu, catalog, ActionId.TOGGLE_STUDY_EXPLORER)
    _add(window_menu, catalog, ActionId.TOGGLE_METADATA)
    window_menu.addSeparator()
    _add(window_menu, catalog, ActionId.RESTORE_LAYOUT)
    _add(window_menu, catalog, ActionId.FULLSCREEN)

    help_menu = menu_bar.addMenu("&Help")
    _add(help_menu, catalog, ActionId.ABOUT)


def create_toolbar(main_window: QMainWindow, catalog: ActionCatalog) -> QToolBar:
    """Create the main toolbar from the catalog."""
    toolbar = QToolBar("Main Toolbar", main_window)
    toolbar.setObjectName("mainToolbar")
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    _add(toolbar, catalog, ActionId.OPEN_FOLDER)
    _add(toolbar, catalog, ActionId.OPEN_FILES)
    toolbar.addSeparator()
    _add(toolbar, catalog, ActionId.FIT_TO_WINDOW)
    _add(toolbar, catalog, ActionId.ZOOM_IN)
    _add(toolbar, catalog, ActionId.ZOOM_OUT)
    _add(toolbar, catalog, ActionId.RESET_VIEW)
    toolbar.addSeparator()
    _add(toolbar, catalog, ActionId.WINDOW_LEVEL)
    _add(toolbar, catalog, ActionId.MEASURE)
    _add(toolbar, catalog, ActionId.SCREENSHOT)
    toolbar.addSeparator()
    _add(toolbar, catalog, ActionId.SETTINGS)
    return toolbar


def _add(
    container: QMenu | QToolBar,
    catalog: ActionCatalog,
    action_id: ActionId,
) -> None:
    """Add a single action to a menu or toolbar."""
    container.addAction(catalog.action(action_id))
