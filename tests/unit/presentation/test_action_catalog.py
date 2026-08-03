"""Tests for the action catalog."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QObject

from dicomviewer.presentation.actions.action_catalog import ActionCatalog
from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.theme.icon_provider import IconProvider

_ENABLED_IDS = (
    ActionId.SETTINGS,
    ActionId.TOGGLE_STUDY_EXPLORER,
    ActionId.TOGGLE_METADATA,
    ActionId.RESTORE_LAYOUT,
    ActionId.FULLSCREEN,
    ActionId.ABOUT,
    ActionId.EXIT,
)


def _handlers() -> dict[ActionId, Callable[[], None]]:
    return {action_id: _noop for action_id in _ENABLED_IDS}


def _noop() -> None:
    pass


@pytest.fixture
def catalog(icon_provider: IconProvider) -> ActionCatalog:
    # Keep the QObject parent alive for the duration of the test.
    parent = QObject()
    catalog = ActionCatalog(parent, icon_provider, handlers=_handlers())
    yield catalog


def test_catalog_requires_a_handler_for_every_enabled_action(
    icon_provider: IconProvider,
) -> None:
    with pytest.raises(ValueError):
        ActionCatalog(QObject(), icon_provider, handlers={})


def test_unavailable_actions_exist_but_are_disabled(catalog: ActionCatalog) -> None:
    assert not catalog.action(ActionId.OPEN_FOLDER).isEnabled()
    assert not catalog.action(ActionId.ZOOM_IN).isEnabled()
    assert catalog.action(ActionId.SETTINGS).isEnabled()


def test_enabled_actions_are_wired(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.SETTINGS).isEnabled()
    assert catalog.action(ActionId.ABOUT).isEnabled()


def test_shortcuts_are_registered(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.SETTINGS).shortcut().toString() == "Ctrl+,"
    assert catalog.action(ActionId.OPEN_FOLDER).shortcut().toString() == "Ctrl+O"


def test_dock_toggles_are_checkable(catalog: ActionCatalog) -> None:
    assert catalog.action(ActionId.TOGGLE_STUDY_EXPLORER).isCheckable()
    assert not catalog.action(ActionId.SETTINGS).isCheckable()


def test_actions_have_icons(catalog: ActionCatalog) -> None:
    assert not catalog.action(ActionId.OPEN_FOLDER).icon().isNull()
