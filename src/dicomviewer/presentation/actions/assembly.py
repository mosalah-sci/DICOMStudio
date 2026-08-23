"""Menu bar and toolbar assembly from the action catalog."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar, QToolBar

from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.shared.constants import TOOLBAR_ICON_SIZE

_MANAGE_PRESETS_OBJECT = "manageWindowPresets"


@dataclass(frozen=True)
class MenuHandles:
    """References to menus whose contents change at runtime."""

    preset_actions: tuple[QAction, ...]
    presets_menu: QMenu


def populate_menu_bar(
    menu_bar: QMenuBar,
    catalog: ActionCatalog,
    window_presets: Sequence[WindowPreset] = (),
    on_window_preset: Callable[[WindowPreset], None] | None = None,
    on_clear_measurements: Callable[[], None] | None = None,
    on_clear_annotations: Callable[[], None] | None = None,
    on_manage_presets: Callable[[], None] | None = None,
) -> MenuHandles:
    """Populate the standard application menus from the catalog.

    The returned handles give callers access to the window-preset actions so
    they can be gated on loaded content, and to the presets submenu so it can
    be rebuilt when custom presets change.
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
    view_menu.addSeparator()
    _add(view_menu, catalog, ActionId.ROTATE_CW)
    _add(view_menu, catalog, ActionId.ROTATE_CCW)
    _add(view_menu, catalog, ActionId.FLIP_HORIZONTAL)
    _add(view_menu, catalog, ActionId.FLIP_VERTICAL)
    view_menu.addSeparator()
    _add(view_menu, catalog, ActionId.INVERT)
    _add(view_menu, catalog, ActionId.PLAY_CINE)
    view_menu.addSeparator()
    _add(view_menu, catalog, ActionId.TOGGLE_INFO_OVERLAY)

    tools_menu = menu_bar.addMenu("&Tools")
    _add(tools_menu, catalog, ActionId.WINDOW_LEVEL)
    presets_menu, preset_actions = create_window_presets_menu(
        tools_menu, window_presets, on_window_preset, on_manage_presets
    )
    tools_menu.addSeparator()
    _add(tools_menu, catalog, ActionId.MEASURE)
    _add(tools_menu, catalog, ActionId.ANNOTATE_POINT)
    _add(tools_menu, catalog, ActionId.ANNOTATE_ARROW)
    _add(tools_menu, catalog, ActionId.ANNOTATE_TEXT)
    if on_clear_measurements is not None or on_clear_annotations is not None:
        tools_menu.addSeparator()
        if on_clear_measurements is not None:
            _add(tools_menu, catalog, ActionId.CLEAR_MEASUREMENTS)
        if on_clear_annotations is not None:
            _add(tools_menu, catalog, ActionId.CLEAR_ANNOTATIONS)
    tools_menu.addSeparator()
    _add(tools_menu, catalog, ActionId.INSPECT_DICOM)
    _add(tools_menu, catalog, ActionId.SCREENSHOT)

    window_menu = menu_bar.addMenu("&Window")
    _add(window_menu, catalog, ActionId.TOGGLE_STUDY_EXPLORER)
    _add(window_menu, catalog, ActionId.TOGGLE_METADATA)
    window_menu.addSeparator()
    _add(window_menu, catalog, ActionId.RESTORE_LAYOUT)
    _add(window_menu, catalog, ActionId.FULLSCREEN)

    help_menu = menu_bar.addMenu("&Help")
    _add(help_menu, catalog, ActionId.ABOUT)
    return MenuHandles(preset_actions=preset_actions, presets_menu=presets_menu)


def create_window_presets_menu(
    tools_menu: QMenu,
    presets: Sequence[WindowPreset],
    on_window_preset: Callable[[WindowPreset], None] | None,
    on_manage_presets: Callable[[], None] | None,
) -> tuple[QMenu, tuple[QAction, ...]]:
    """Create the Window Presets submenu with a trailing Manage entry."""
    submenu = tools_menu.addMenu("Window &Presets")
    submenu.setObjectName("windowPresetsMenu")
    manage_action = QAction("&Manage Presets...", submenu)
    manage_action.setObjectName(_MANAGE_PRESETS_OBJECT)
    manage_action.setStatusTip("Create, edit and delete custom window presets")
    if on_manage_presets is not None:
        manage_action.triggered.connect(lambda _checked=False: on_manage_presets())
    submenu.setProperty("manageAction", manage_action)
    actions = refresh_window_presets_menu(submenu, presets, on_window_preset)
    return submenu, actions


def refresh_window_presets_menu(
    submenu: QMenu,
    presets: Sequence[WindowPreset],
    on_window_preset: Callable[[WindowPreset], None] | None,
) -> tuple[QAction, ...]:
    """Rebuild ``submenu`` content as ``presets... | --- | Manage``.

    The Manage entry is preserved across rebuilds so its handler survives;
    everything else is recreated from ``presets``.
    """
    manage_action = submenu.property("manageAction")
    for action in list(submenu.actions()):
        submenu.removeAction(action)
    actions: list[QAction] = []
    for preset in presets:
        action = QAction(preset.name, submenu)
        action.setStatusTip(f"Apply the {preset.name} window/level preset")
        if on_window_preset is not None:
            action.triggered.connect(lambda _checked=False, p=preset: on_window_preset(p))
        submenu.addAction(action)
        actions.append(action)
    if isinstance(manage_action, QAction):
        submenu.addSeparator()
        submenu.addAction(manage_action)
    return tuple(actions)


def populate_recent_folders_menu(
    menu: QMenu,
    recent_folders: Sequence[Path],
    on_open_recent: Callable[[Path], None] | None = None,
    on_clear_recent: Callable[[], None] | None = None,
) -> None:
    """Populate ``menu`` with one action per recently opened study folder.

    The menu is cleared first so callers can re-populate it whenever the
    recent list changes. Entries show the folder name with the full path as a
    tooltip; an empty list yields a single disabled placeholder. When
    ``on_clear_recent`` is provided a Clear action is appended.
    """
    menu.clear()
    if not recent_folders:
        placeholder = QAction("No Recent Studies", menu)
        placeholder.setEnabled(False)
        menu.addAction(placeholder)
        return
    for folder in recent_folders:
        label = folder.name or str(folder)
        action = QAction(label, menu)
        action.setStatusTip(f"Open {folder}")
        action.setToolTip(str(folder))
        if on_open_recent is not None:
            action.triggered.connect(lambda _checked=False, f=folder: on_open_recent(f))
        menu.addAction(action)
    if on_clear_recent is not None:
        menu.addSeparator()
        clear_action = QAction("Clear Recent Studies", menu)
        clear_action.setStatusTip("Remove every entry from the recent studies list")
        clear_action.triggered.connect(lambda _checked=False: on_clear_recent())
        menu.addAction(clear_action)


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
    _add(toolbar, catalog, ActionId.ANNOTATE_POINT)
    _add(toolbar, catalog, ActionId.INVERT)
    _add(toolbar, catalog, ActionId.PLAY_CINE)
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
