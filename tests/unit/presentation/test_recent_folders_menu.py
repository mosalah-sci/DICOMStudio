"""Tests for the Recent Studies menu helper."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from dicomviewer.presentation.actions.assembly import populate_recent_folders_menu


def test_empty_list_yields_a_disabled_placeholder(qapp) -> None:
    menu = QMenu()
    populate_recent_folders_menu(menu, ())
    assert menu.actions()
    assert not menu.actions()[0].isEnabled()
    assert menu.actions()[0].text() == "No Recent Studies"


def test_folders_become_clickable_actions(qapp) -> None:
    menu = QMenu()
    opened: list[Path] = []
    populate_recent_folders_menu(menu, (Path("a"), Path("b")), opened.append)
    actions = menu.actions()
    assert len(actions) == 2
    assert actions[0].text() == "a"
    actions[1].trigger()
    assert opened == [Path("b")]


def test_menu_is_cleared_before_repopulating(qapp) -> None:
    menu = QMenu()
    populate_recent_folders_menu(menu, (Path("a"),))
    populate_recent_folders_menu(menu, (Path("b"), Path("c")))
    assert len(menu.actions()) == 2


def test_actions_are_qactions_with_tooltips(qapp) -> None:
    menu = QMenu()
    populate_recent_folders_menu(menu, (Path("x"),))
    action = menu.actions()[0]
    assert isinstance(action, QAction)
    assert action.toolTip() == "x"


def test_entries_show_the_folder_name_with_full_path_tooltip(qapp) -> None:
    menu = QMenu()
    folder = Path("C:/data/patient 1")
    populate_recent_folders_menu(menu, (folder,))
    action = menu.actions()[0]
    assert action.text() == "patient 1"
    assert action.toolTip() == str(folder)


def test_clear_action_is_appended_when_a_handler_is_provided(qapp) -> None:
    menu = QMenu()
    cleared: list[bool] = []
    populate_recent_folders_menu(
        menu, (Path("a"), Path("b")), on_clear_recent=lambda: cleared.append(True)
    )
    actions = menu.actions()
    assert actions[-1].text() == "Clear Recent Studies"
    actions[-1].trigger()
    assert cleared == [True]


def test_no_clear_action_without_a_handler(qapp) -> None:
    menu = QMenu()
    populate_recent_folders_menu(menu, (Path("a"),))
    assert len(menu.actions()) == 1
