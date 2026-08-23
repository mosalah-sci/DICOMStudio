"""Regression tests for cine playback through the full viewer panel stack.

These reproduce the v1.3.0 "Play Series does not change the slice" bug: the
cine controller silently saw a single-slice panel when its navigation
surface did not expose ``slice_count``, auto-pausing on the first tick.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QSpinBox
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer
from tests.qt_utils import pump_until

from dicomviewer.domain.studies import Image
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.viewer_panel import ViewerPanel

ICON_DIR = Path(__file__).resolve().parents[3] / "src" / "dicomviewer" / "resources" / "icons"


def _series(count: int) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _panel() -> ViewerPanel:
    return ViewerPanel(
        None,
        IconProvider(ICON_DIR),
        decoder=FakePixelDecoder(),
        renderer=FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )


def _current_box(panel: ViewerPanel) -> QSpinBox:
    return panel._nav_bar._current_box


def test_play_advances_displayed_slices(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))  # type: ignore[arg-type]
    seen: list[int] = []
    panel.slice_changed.connect(lambda index, _count: seen.append(index))

    assert panel.current_slice == 0
    panel.toggle_playback()
    assert panel.is_playing

    advanced = pump_until(
        qapp,
        lambda: len({index for index in seen}) >= 2,
    )
    assert advanced, f"playback never changed the slice (slices seen: {seen})"
    assert panel.current_slice != 0 or seen[-1] == 0


def test_pause_stops_and_resume_continues(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))  # type: ignore[arg-type]
    panel.toggle_playback()
    assert pump_until(qapp, lambda: panel.current_slice != 0)

    panel.toggle_playback()
    assert not panel.is_playing
    paused_at = panel.current_slice
    QTest.qWait(150)
    assert panel.current_slice == paused_at

    panel.toggle_playback()
    assert panel.is_playing
    assert pump_until(qapp, lambda: panel.current_slice != paused_at)


def test_playback_wraps_safely_at_series_boundary(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(4))  # type: ignore[arg-type]
    panel.set_slice(3)
    panel.toggle_playback()

    wrapped = pump_until(qapp, lambda: panel.current_slice == 0)
    assert wrapped, "playback did not wrap past the final slice"
    assert panel.is_playing


def test_changing_series_stops_stale_playback(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))  # type: ignore[arg-type]
    panel.toggle_playback()
    assert panel.is_playing

    states: list[bool] = []
    panel.playback_changed.connect(states.append)
    panel.load_series(_series(3))  # type: ignore[arg-type]

    assert not panel.is_playing
    assert states == [False]
    assert panel.current_slice == 0
    QTest.qWait(120)
    assert panel.current_slice == 0


def test_cine_updates_unified_current_slice_control(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))  # type: ignore[arg-type]
    panel.toggle_playback()
    assert pump_until(qapp, lambda: panel.current_slice != 0)

    box = _current_box(panel)
    assert box.value() == panel.current_slice + 1
    assert panel._nav_bar.current_index() == panel.current_slice


def test_direct_entry_jumps_to_requested_slice(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))  # type: ignore[arg-type]
    jumps: list[int] = []
    panel.slice_changed.connect(lambda index, _count: jumps.append(index))

    _current_box(panel).setValue(4)
    assert panel.current_slice == 3
    assert jumps[-1] == 3


def test_out_of_range_entry_clamps_without_breaking_viewer(qapp) -> None:
    panel = _panel()
    panel.load_series(_series(5))
    _current_box(panel).setValue(999)
    assert panel.current_slice == 4

    panel.set_slice(-7)
    assert panel.current_slice == 0
    assert panel.has_image


def test_nav_bar_play_button_starts_playback(qapp) -> None:
    """Regression: the nav-bar play button drives the cine controller.

    ``play_toggled`` used to be emitted with no consumer, so clicking the
    button flipped its own state while playback never started.
    """
    panel = _panel()
    panel.load_series(_series(5))

    panel._nav_bar._play_button.click()
    assert panel.is_playing
    assert pump_until(qapp, lambda: panel.current_slice != 0)
    panel._nav_bar._play_button.click()
    assert not panel.is_playing


def test_nav_bar_button_stays_synchronized_without_signal_loops(qapp) -> None:
    """Playback state pushed from either side keeps the button in step once."""
    panel = _panel()
    panel.load_series(_series(5))
    states: list[bool] = []
    panel.playback_changed.connect(states.append)

    # Controller-driven start reflects onto the button without re-emitting.
    panel.toggle_playback()
    qapp.processEvents()
    assert states == [True]
    assert panel._nav_bar._play_button.isChecked()

    # Button-driven pause reaches the controller exactly once.
    panel._nav_bar._play_button.click()
    qapp.processEvents()
    assert not panel.is_playing
    assert states == [True, False]
    assert not panel._nav_bar._play_button.isChecked()
