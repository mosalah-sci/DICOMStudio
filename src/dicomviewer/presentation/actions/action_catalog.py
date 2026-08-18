"""Central catalog of QActions built from declarative specifications."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.theme.icon_provider import IconProvider


@dataclass(frozen=True)
class ActionSpec:
    """Declarative description of a single application action."""

    action_id: ActionId
    text: str
    icon: str | None = None
    shortcut: str | None = None
    additional_shortcuts: tuple[str, ...] = ()
    tooltip: str | None = None
    status_tip: str | None = None
    checkable: bool = False
    enabled: bool = True


_SPECS: tuple[ActionSpec, ...] = (
    ActionSpec(
        ActionId.OPEN_FOLDER,
        "&Open Folder...",
        icon="folder",
        shortcut="Ctrl+O",
        tooltip="Open a folder of DICOM studies (Ctrl+O)",
        status_tip="Open a folder of DICOM studies",
    ),
    ActionSpec(
        ActionId.OPEN_FILES,
        "Open &Files...",
        icon="folder-plus",
        shortcut="Ctrl+Shift+O",
        tooltip="Open individual DICOM files (Ctrl+Shift+O)",
        status_tip="Open individual DICOM files",
        enabled=False,
    ),
    ActionSpec(
        ActionId.EXPORT_IMAGE,
        "&Export Image...",
        icon="save",
        shortcut="Ctrl+S",
        additional_shortcuts=("Ctrl+E",),
        tooltip="Export the current view as a PNG or JPEG image (Ctrl+E)",
        status_tip="Export the current view as a PNG or JPEG image",
    ),
    ActionSpec(
        ActionId.FIT_TO_WINDOW,
        "&Fit to Window",
        icon="maximize",
        shortcut="Ctrl+0",
        tooltip="Fit the image to the viewer (F)",
        status_tip="Fit the image to the viewer",
    ),
    ActionSpec(
        ActionId.ZOOM_IN,
        "Zoom &In",
        icon="zoom-in",
        shortcut="+",
        tooltip="Zoom in (Ctrl+wheel also zooms)",
        status_tip="Zoom in (Ctrl+wheel also zooms)",
    ),
    ActionSpec(
        ActionId.ZOOM_OUT,
        "Zoom &Out",
        icon="zoom-out",
        shortcut="-",
        tooltip="Zoom out (Ctrl+wheel also zooms)",
        status_tip="Zoom out (Ctrl+wheel also zooms)",
    ),
    ActionSpec(
        ActionId.RESET_VIEW,
        "&Reset View",
        icon="rotate-ccw",
        tooltip="Reset zoom, pan and window/level (R)",
        status_tip="Reset zoom, pan and window/level",
    ),
    ActionSpec(
        ActionId.WINDOW_LEVEL,
        "Reset &Window/Level",
        icon="target",
        tooltip="Reset the window/level to automatic (W, or right-drag to adjust)",
        status_tip="Reset the window/level to automatic (right-drag adjusts it)",
    ),
    ActionSpec(
        ActionId.MEASURE,
        "&Measure",
        icon="ruler",
        tooltip="Measure distances and angles on the image (M)",
        status_tip="Measure distances and angles on the image",
        checkable=True,
    ),
    ActionSpec(
        ActionId.CLEAR_MEASUREMENTS,
        "&Clear Measurements",
        icon="eraser",
        tooltip="Remove all measurements from every slice",
        status_tip="Remove all measurements from every slice",
        enabled=False,
    ),
    ActionSpec(
        ActionId.COPY_IMAGE,
        "&Copy Image to Clipboard",
        icon="copy",
        shortcut="Ctrl+C",
        tooltip="Copy the current view to the clipboard (Ctrl+C)",
        status_tip="Copy the current view to the clipboard",
    ),
    ActionSpec(
        ActionId.SCREENSHOT,
        "&Screenshot",
        icon="camera",
        tooltip="Save a PNG screenshot of the current view",
        status_tip="Save a PNG screenshot of the current view",
    ),
    ActionSpec(
        ActionId.INSPECT_DICOM,
        "&Inspect DICOM Dataset...",
        icon="info",
        shortcut="Ctrl+I",
        tooltip="Inspect the raw DICOM tags of the current image (Ctrl+I)",
        status_tip="Inspect the raw DICOM tags of the current image",
    ),
    ActionSpec(
        ActionId.SETTINGS,
        "&Settings...",
        icon="sliders",
        shortcut="Ctrl+,",
        tooltip="Open the settings dialog (Ctrl+,)",
        status_tip="Open the settings dialog",
    ),
    ActionSpec(
        ActionId.TOGGLE_STUDY_EXPLORER,
        "Study &Explorer",
        icon="panel-left",
        tooltip="Show or hide the Study Explorer sidebar",
        status_tip="Show or hide the study explorer",
        checkable=True,
    ),
    ActionSpec(
        ActionId.TOGGLE_METADATA,
        "&Metadata Panel",
        icon="panel-right",
        tooltip="Show or hide the Metadata sidebar",
        status_tip="Show or hide the metadata panel",
        checkable=True,
    ),
    ActionSpec(
        ActionId.RESTORE_LAYOUT,
        "Restore &Default Layout",
        icon="maximize",
        tooltip="Restore the default window layout",
        status_tip="Restore the default window layout",
    ),
    ActionSpec(
        ActionId.FULLSCREEN,
        "&Fullscreen",
        icon="maximize-2",
        shortcut="F11",
        tooltip="Toggle fullscreen viewer mode (F11, Esc to exit)",
        status_tip="Toggle fullscreen mode",
        checkable=True,
    ),
    ActionSpec(
        ActionId.ABOUT,
        "&About...",
        icon="info",
        tooltip="Show application information",
        status_tip="Show application information",
    ),
    ActionSpec(
        ActionId.EXIT,
        "E&xit",
        shortcut="Ctrl+Q",
        tooltip="Quit the application (Ctrl+Q)",
        status_tip="Quit the application",
    ),
)


class ActionCatalog:
    """Creates and owns every QAction used by menus and toolbars.

    Actions are created once from declarative specs. Enabled actions must
    have a handler registered at construction time; unavailable actions stay
    visible but disabled so the interface communicates future capabilities.
    """

    def __init__(
        self,
        parent: QObject,
        icon_provider: IconProvider,
        handlers: Mapping[ActionId, Callable[[], None]],
    ) -> None:
        """Build all actions, requiring a handler for every enabled one.

        A handler may also be provided for a disabled action so it can be
        wired ahead of time and later enabled (for example Clear
        Measurements).
        """
        self._icon_provider = icon_provider
        self._icon_names: dict[ActionId, str] = {}
        self._actions: dict[ActionId, QAction] = {}
        for spec in _SPECS:
            action = self._create_action(parent, spec)
            handler = handlers.get(spec.action_id)
            if spec.enabled and handler is None:
                raise ValueError(f"No handler registered for enabled action {spec.action_id!r}")
            if handler is not None:
                action.triggered.connect(handler)
            self._actions[spec.action_id] = action

    def action(self, action_id: ActionId) -> QAction:
        """Return the action identified by ``action_id``."""
        return self._actions[action_id]

    def refresh_icons(self) -> None:
        """Re-apply icons from the current theme color (after a theme switch)."""
        for action_id, icon_name in self._icon_names.items():
            self._actions[action_id].setIcon(self._icon_provider.icon(icon_name))

    def _create_action(self, parent: QObject, spec: ActionSpec) -> QAction:
        """Construct a single QAction from its specification."""
        action = QAction(spec.text, parent)
        action.setObjectName(spec.action_id.value)
        if spec.icon is not None:
            action.setIcon(self._icon_provider.icon(spec.icon))
            self._icon_names[spec.action_id] = spec.icon
        if spec.shortcut is not None:
            shortcuts = [QKeySequence(spec.shortcut)]
            shortcuts.extend(QKeySequence(extra) for extra in spec.additional_shortcuts)
            action.setShortcuts(shortcuts)
        if spec.tooltip is not None:
            action.setToolTip(spec.tooltip)
        if spec.status_tip is not None:
            action.setStatusTip(spec.status_tip)
        if spec.checkable:
            action.setCheckable(True)
        action.setEnabled(spec.enabled)
        return action
