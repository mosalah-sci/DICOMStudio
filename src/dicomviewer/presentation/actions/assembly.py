"""Menu bar and toolbar assembly from the action catalog."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar, QToolBar

from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.shared.constants import TOOLBAR_ICON_SIZE


def populate_menu_bar(
    menu_bar: QMenuBar,
    catalog: ActionCatalog,
    window_presets: Sequence[WindowPreset] = (),
    on_window_preset: Callable[[WindowPreset], None] | None = None,
    on_clear_measurements: Callable[[], None] | None = None,
) -> tuple[QAction, ...]:
    """Populate the standard application menus from the catalog.

    Returns the preset actions so callers can enable or disable them based on
    loaded content.
    """
    file_menu = menu_bar.addMenu("&File")
    _add(file_menu, catalog, ActionId.OPEN_FOLDER)
    _add(file_menu, catalog, ActionId.OPEN_FILES)
    file_menu.addSeparator()
    _add(file_menu, catalog, ActionId.EXPORT_IMAGE)
    _add(file_menu, catalog, ActionId.COPY_IMAGE)
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
    preset_actions = _add_window_presets(tools_menu, window_presets, on_window_preset)
    _add(tools_menu, catalog, ActionId.MEASURE)
    if on_clear_measurements is not None:
        tools_menu.addSeparator()
        _add(tools_menu, catalog, ActionId.CLEAR_MEASUREMENTS)
    _add(tools_menu, catalog, ActionId.SCREENSHOT)

    window_menu = menu_bar.addMenu("&Window")
    _add(window_menu, catalog, ActionId.TOGGLE_STUDY_EXPLORER)
    _add(window_menu, catalog, ActionId.TOGGLE_METADATA)
    window_menu.addSeparator()
    _add(window_menu, catalog, ActionId.RESTORE_LAYOUT)
    _add(window_menu, catalog, ActionId.FULLSCREEN)

    help_menu = menu_bar.addMenu("&Help")
    _add(help_menu, catalog, ActionId.ABOUT)
    return preset_actions


def _add_window_presets(
    tools_menu: QMenu,
    presets: Sequence[WindowPreset],
    on_window_preset: Callable[[WindowPreset], None] | None,
) -> tuple[QAction, ...]:
    """Add a Window Presets submenu, returning its actions."""
    if not presets:
        return ()
    submenu = tools_menu.addMenu("Window &Presets")
    actions: list[QAction] = []
    for preset in presets:
        action = QAction(preset.name, submenu)
        action.setStatusTip(f"Apply the {preset.name} window/level preset")
        if on_window_preset is not None:
            action.triggered.connect(lambda _checked=False, p=preset: on_window_preset(p))
        submenu.addAction(action)
        actions.append(action)
    return tuple(actions)


def populate_recent_folders_menu(
    menu: QMenu,
    recent_folders: Sequence[Path],
    on_open_recent: Callable[[Path], None] | None = None,
) -> None:
    """Populate ``menu`` with one action per recently opened folder.

    The menu is cleared first so callers can re-populate it whenever the
    recent list changes. An empty list yields a single disabled placeholder.
    """
    menu.clear()
    if not recent_folders:
        placeholder = QAction("No Recent Folders", menu)
        placeholder.setEnabled(False)
        menu.addAction(placeholder)
        return
    for folder in recent_folders:
        action = QAction(str(folder), menu)
        action.setStatusTip(f"Open {folder}")
        action.setToolTip(str(folder))
        if on_open_recent is not None:
            action.triggered.connect(lambda _checked=False, f=folder: on_open_recent(f))
        menu.addAction(action)


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
