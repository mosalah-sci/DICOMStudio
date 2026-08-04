"""Tests for the Recent Folders menu helper."""

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
    assert menu.actions()[0].text() == "No Recent Folders"


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
