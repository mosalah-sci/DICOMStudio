"""Tests for the cine playback controller."""

from __future__ import annotations

from dicomviewer.presentation.playback.cine_controller import CineController


class FakePanel:
    """Slice-navigation double recording set_slice calls."""

    def __init__(self, count: int = 5) -> None:
        self.count = count
        self._index = 0
        self.jumps: list[int] = []

    def current_slice(self) -> int:
        return self._index

    def set_slice(self, index: int) -> None:
        self._index = index
        self.jumps.append(index)

    def slice_count(self) -> int:
        return self.count


def test_controller_starts_paused(qapp) -> None:
    del qapp
    controller = CineController(FakePanel(), lambda: 15.0)
    assert not controller.is_playing


def test_start_and_pause_emit_state_changes(qapp) -> None:
    del qapp
    panel = FakePanel()
    controller = CineController(panel, lambda: 15.0)
    states: list[bool] = []
    controller.playing_changed.connect(states.append)
    controller.start()
    assert controller.is_playing
    controller.start()  # idempotent
    assert states == [True]
    controller.pause()
    assert not controller.is_playing
    controller.pause()
    assert states == [True, False]
    assert not panel.jumps


def test_tick_advances_slices_modulo_count(qapp) -> None:
    del qapp
    panel = FakePanel(count=3)
    controller = CineController(panel, lambda: 10.0)
    controller._on_tick()
    controller._on_tick()
    controller._on_tick()
    assert panel.jumps == [1, 2, 0]


def test_single_slice_series_pauses_immediately(qapp) -> None:
    del qapp
    panel = FakePanel(count=1)
    controller = CineController(panel, lambda: 10.0)
    states: list[bool] = []
    controller.playing_changed.connect(states.append)
    controller.start()
    controller._on_tick()
    assert states == [True, False]
    assert panel.jumps == []


def test_timer_interval_reflects_fps(qapp) -> None:
    del qapp
    controller = CineController(FakePanel(), lambda: 20.0)
    controller.start()
    assert controller._timer.interval() == 50
    controller.pause()
    assert not controller._timer.isActive()


def test_refresh_rate_updates_interval_while_playing(qapp) -> None:
    del qapp
    rate = {"fps": 10.0}
    controller = CineController(FakePanel(), lambda: rate["fps"])
    controller.start()
    rate["fps"] = 30.0
    controller.refresh_rate()
    assert controller._timer.interval() == 33
    assert controller.is_playing


def test_refresh_rate_pauses_when_rate_becomes_invalid(qapp) -> None:
    del qapp
    rate = {"fps": 10.0}
    controller = CineController(FakePanel(), lambda: rate["fps"])
    controller.start()
    rate["fps"] = 0.0
    controller.refresh_rate()
    assert not controller.is_playing


def test_extreme_rates_are_clamped(qapp) -> None:
    del qapp
    controller = CineController(FakePanel(), lambda: 500.0)
    controller.start()
    assert controller._timer.interval() == round(1000 / 60)
    controller.pause()
    slow = CineController(FakePanel(), lambda: 0.01)
    slow.start()
    assert slow._timer.interval() == 1000


def test_failing_provider_disables_start(qapp) -> None:
    def broken() -> float:
        raise RuntimeError("settings offline")

    del qapp
    controller = CineController(FakePanel(), broken)
    states: list[bool] = []
    controller.playing_changed.connect(states.append)
    controller.start()
    assert states == [] and not controller.is_playing
