"""Tests for the slice navigation bar widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.slice_navigation_bar import SliceNavigationBar

ICON_DIR = Path(__file__).resolve().parents[3] / "src" / "dicomviewer" / "resources" / "icons"


def _bar() -> SliceNavigationBar:
    return SliceNavigationBar(IconProvider(ICON_DIR))


def test_bar_starts_hidden_and_disabled(qapp) -> None:
    del qapp
    bar = _bar()
    assert not bar.isVisibleTo(bar.parentWidget() or bar)
    bar.set_range(0)
    assert not bar.isVisibleTo(bar)


def test_single_slice_hides_the_bar(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(1)
    assert not bar.isVisibleTo(bar)


def test_set_range_configures_controls(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(5)
    assert bar._slider.maximum() == 4
    assert bar._current_box.maximum() == 5
    assert bar._total_label.text() == "/ 5"
    assert bar._slider.isEnabled()


def test_index_changes_propagate_to_listeners(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(5)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar.set_index(2)
    assert bar.current_index() == 2
    assert bar._current_box.value() == 3
    assert selected == []  # programmatic sync is silent
    bar._on_next()
    assert selected == [3]
    bar._on_previous()
    bar._on_previous()
    assert selected == [3, 2, 1]


def test_current_box_emits_selections(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(8)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar._slider.setValue(6)
    assert selected == [6]
    bar._current_box.setValue(2)
    assert selected == [6, 1]
    assert bar._slider.value() == 1


def test_indices_are_clamped(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(4)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar._apply_index(-5)
    assert bar.current_index() == 0
    bar._apply_index(99)
    assert bar.current_index() == 3
    assert selected == [0, 3]


def test_play_button_toggles_and_updates_icon(qapp) -> None:
    del qapp
    bar = _bar()
    states: list[bool] = []
    bar.play_toggled.connect(states.append)
    bar._play_button.click()
    assert states == [True]
    bar.set_playing(False)
    assert not bar._play_button.isChecked()
    assert states == [True]  # set_playing stays silent


def test_set_playing_reflects_state_without_emitting(qapp) -> None:
    del qapp
    bar = _bar()
    states: list[bool] = []
    bar.play_toggled.connect(states.append)
    bar.set_playing(True)
    assert bar._play_button.isChecked()
    assert states == []


def test_typed_entry_commits_once_on_enter(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(150)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar._current_box.setFocus(Qt.FocusReason.OtherFocusReason)
    bar._current_box.selectAll()
    QTest.keyClicks(bar._current_box, "37")
    assert selected == []  # keyboard tracking is off while typing
    QTest.keyClick(bar._current_box, Qt.Key.Key_Return)
    assert selected == [36]
    assert bar._slider.value() == 36


def test_out_of_range_entry_reverts_safely(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(8)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar.set_index(2)
    bar._current_box.setFocus(Qt.FocusReason.OtherFocusReason)
    bar._current_box.selectAll()
    QTest.keyClicks(bar._current_box, "999")
    QTest.keyClick(bar._current_box, Qt.Key.Key_Return)
    assert selected == []  # rejected input never jumps
    assert bar.current_index() == 2
    assert bar._slider.isEnabled()  # the bar remains fully usable


def test_invalid_text_is_rejected_without_emitting(qapp) -> None:
    del qapp
    bar = _bar()
    bar.set_range(8)
    selected: list[int] = []
    bar.slice_selected.connect(selected.append)
    bar._current_box.setFocus(Qt.FocusReason.OtherFocusReason)
    QTest.keyClicks(bar._current_box, "abc")
    QTest.keyClick(bar._current_box, Qt.Key.Key_Return)
    assert selected == []
    assert bar._current_box.value() == 1
