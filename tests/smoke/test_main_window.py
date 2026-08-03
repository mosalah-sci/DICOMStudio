"""Smoke tests for the main application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QDockWidget, QLabel, QWidget

from dicomviewer.presentation.actions.action_ids import ActionId
from dicomviewer.presentation.windows.main_window import MainWindow


def test_main_window_has_expected_title(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window.windowTitle() == "DICOM Viewer Professional - v0.2.0"


def test_main_window_shows_an_empty_state(make_window: Callable[..., MainWindow]) -> None:
    window = make_window(version="1.0.0")
    central = window.centralWidget()
    assert isinstance(central, QWidget)
    labels = central.findChildren(QLabel)
    assert any("No study loaded" in label.text() for label in labels)


def test_main_window_has_menus_and_docks(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert window.menuBar() is not None
    assert window.findChild(QDockWidget, "studyExplorerDock") is not None
    assert window.findChild(QDockWidget, "metadataDock") is not None
    assert window.statusBar() is not None


def test_dock_toggle_action_shows_and_hides_the_panel(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    dock = window.findChild(QDockWidget, "studyExplorerDock")
    toggle = window.action(ActionId.TOGGLE_STUDY_EXPLORER)
    assert dock is not None
    toggle.setChecked(False)
    toggle.trigger()
    assert not dock.isVisible()


def test_unavailable_actions_are_disabled(make_window: Callable[..., MainWindow]) -> None:
    window = make_window()
    assert not window.action(ActionId.OPEN_FOLDER).isEnabled()
    assert not window.action(ActionId.ZOOM_IN).isEnabled()
    assert window.action(ActionId.SETTINGS).isEnabled()


def test_closing_the_window_persists_the_layout(
    make_window: Callable[..., MainWindow],
    tmp_path: Path,
) -> None:
    window = make_window()
    window.close()
    assert (tmp_path / "window_state.json").exists()


def test_theme_switch_updates_the_status_bar(
    make_window: Callable[..., MainWindow],
) -> None:
    window = make_window()
    window._change_theme("light")
    labels = window.statusBar().findChildren(QLabel)
    assert any(label.text() == "Light" for label in labels)
