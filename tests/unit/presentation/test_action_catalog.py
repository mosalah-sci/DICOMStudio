"""Tests for the action catalog."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QObject

from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.theme.icon_provider import IconProvider

_ENABLED_IDS = (
    ActionId.OPEN_FOLDER,
    ActionId.SETTINGS,
    ActionId.TOGGLE_STUDY_EXPLORER,
    ActionId.TOGGLE_METADATA,
    ActionId.RESTORE_LAYOUT,
    ActionId.FULLSCREEN,
    ActionId.ABOUT,
    ActionId.EXIT,
    ActionId.FIT_TO_WINDOW,
    ActionId.ZOOM_IN,
    ActionId.ZOOM_OUT,
    ActionId.RESET_VIEW,
    ActionId.WINDOW_LEVEL,
    ActionId.MEASURE,
    ActionId.COPY_IMAGE,
    ActionId.EXPORT_IMAGE,
    ActionId.SCREENSHOT,
    ActionId.INSPECT_DICOM,
    ActionId.ROTATE_CW,
    ActionId.ROTATE_CCW,
    ActionId.FLIP_HORIZONTAL,
    ActionId.FLIP_VERTICAL,
    ActionId.INVERT,
    ActionId.ANNOTATE_POINT,
    ActionId.ANNOTATE_ARROW,
    ActionId.ANNOTATE_TEXT,
    ActionId.TOGGLE_INFO_OVERLAY,
    ActionId.MANAGE_WINDOW_PRESETS,
)


def _handlers() -> dict[ActionId, Callable[[], None]]:
    return {action_id: _noop for action_id in _ENABLED_IDS}


def _noop() -> None:
    pass


@pytest.fixture
def catalog(icon_provider: IconProvider, qapp) -> ActionCatalog:
    # Keep the QObject parent alive for the duration of the test.
    parent = QObject()
    catalog = ActionCatalog(parent, icon_provider, handlers=_handlers())
    yield catalog


def test_catalog_requires_a_handler_for_every_enabled_action(
    icon_provider: IconProvider,
    qapp,
) -> None:
    with pytest.raises(ValueError):
        ActionCatalog(QObject(), icon_provider, handlers={})


def test_unavailable_actions_exist_but_are_disabled(catalog: ActionCatalog) -> None:
    assert not catalog.action(ActionId.OPEN_FILES).isEnabled()
    assert not catalog.action(ActionId.CLEAR_MEASUREMENTS).isEnabled()
    assert not catalog.action(ActionId.CLEAR_ANNOTATIONS).isEnabled()
    assert not catalog.action(ActionId.PLAY_CINE).isEnabled()
    assert catalog.action(ActionId.ZOOM_IN).isEnabled()
    assert catalog.action(ActionId.OPEN_FOLDER).isEnabled()
    assert catalog.action(ActionId.SETTINGS).isEnabled()


def test_measure_action_is_checkable(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.MEASURE).isCheckable()
    assert catalog.action(ActionId.MEASURE).isEnabled()


def test_annotation_actions_are_checkable(catalog: ActionCatalog) -> None:
    for action_id in (
        ActionId.ANNOTATE_POINT,
        ActionId.ANNOTATE_ARROW,
        ActionId.ANNOTATE_TEXT,
    ):
        assert catalog.action(action_id).isCheckable()
        assert catalog.action(action_id).isEnabled()


def test_play_cine_is_checkable_with_space_shortcut(catalog: ActionCatalog) -> None:
    action = catalog.action(ActionId.PLAY_CINE)
    assert action.isCheckable()
    assert action.shortcut().toString() == "Space"


def test_info_overlay_toggle_is_checkable(catalog: ActionCatalog) -> None:
    action = catalog.action(ActionId.TOGGLE_INFO_OVERLAY)
    assert action.isCheckable()
    assert action.isEnabled()


def test_enabled_actions_are_wired(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.SETTINGS).isEnabled()
    assert catalog.action(ActionId.ABOUT).isEnabled()


def test_shortcuts_are_registered(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.SETTINGS).shortcut().toString() == "Ctrl+,"
    assert catalog.action(ActionId.OPEN_FOLDER).shortcut().toString() == "Ctrl+O"


def test_export_image_accepts_both_ctrl_s_and_ctrl_e(catalog: ActionCatalog) -> None:
    shortcuts = [s.toString() for s in catalog.action(ActionId.EXPORT_IMAGE).shortcuts()]
    assert "Ctrl+S" in shortcuts
    assert "Ctrl+E" in shortcuts


def test_actions_have_tooltips(catalog: ActionCatalog) -> None:
    assert "Ctrl+O" in catalog.action(ActionId.OPEN_FOLDER).toolTip()
    assert catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).toolTip() != ""
    assert catalog.action(ActionId.MEASURE).toolTip() != ""


def test_dock_toggles_are_checkable(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).isCheckable()
    assert not catalog.action(ActionId.SETTINGS).isCheckable()


def test_actions_have_icons(catalog: ActionCatalog) -> None:
    assert not catalog.action(ActionId.OPEN_FOLDER).icon().isNull()
