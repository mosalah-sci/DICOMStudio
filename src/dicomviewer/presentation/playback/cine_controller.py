"""Cine playback controller for multi-frame series.

A small QObject owning the playback timer. It asks its panel for the
current slice and advances modulo the series length, so playback stays in
sync with every other navigation source (slider, wheel, keys). The frames
per second are re-read on every tick through ``fps_provider`` so a settings
change takes effect immediately without rebuilding the controller.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal

MIN_FPS = 1.0
MAX_FPS = 60.0


class CinePanel(Protocol):
    """The slice-navigation surface the controller drives."""

    def current_slice(self) -> int:
        """Return the displayed zero-based index."""
        ...

    def set_slice(self, index: int) -> None:
        """Display the slice at ``index``."""
        ...

    def slice_count(self) -> int:
        """Return how many slices the panel can navigate."""
        ...


class CineController(QObject):
    """Advances a viewer panel through its slices at a fixed rate."""

    playing_changed = Signal(bool)

    def __init__(
        self,
        panel: CinePanel,
        fps_provider: Callable[[], float],
        parent: QObject | None = None,
    ) -> None:
        """Create a paused controller over ``panel``.

        ``fps_provider`` is consulted whenever the timer interval updates so
        speed changes apply without restarting playback manually.
        """
        super().__init__(parent)
        self._panel = panel
        self._fps_provider = fps_provider
        self._playing = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._on_tick)

    @property
    def is_playing(self) -> bool:
        """Return whether playback is running."""
        return self._playing

    def start(self) -> None:
        """Start playback; a no-op when already playing."""
        if self._playing:
            return
        fps = self._clamped_fps()
        if fps <= 0.0:
            logger.warning("Cine playback requested without a usable frame rate")
            return
        self._timer.start(round(1000.0 / fps))
        self._playing = True
        self.playing_changed.emit(True)

    def pause(self) -> None:
        """Stop playback; a no-op when already paused."""
        if not self._playing:
            return
        self._timer.stop()
        self._playing = False
        self.playing_changed.emit(False)

    def toggle(self) -> None:
        """Start or stop playback depending on the current state."""
        if self._playing:
            self.pause()
        else:
            self.start()

    def refresh_rate(self) -> None:
        """Apply the current frames-per-second while keeping play state."""
        if not self._playing:
            return
        fps = self._clamped_fps()
        if fps <= 0.0:
            self.pause()
            return
        self._timer.start(round(1000.0 / fps))

    def _on_tick(self) -> None:
        """Advance to the next slice, wrapping around at the end."""
        count = self.slice_count()
        if count < 2:
            self.pause()
            return
        next_index = (self._panel.current_slice() + 1) % count
        self._panel.set_slice(next_index)

    def slice_count(self) -> int:
        """Return how many slices the panel can navigate."""
        return max(int(self._panel.slice_count()), 0)

    def _clamped_fps(self) -> float:
        """Return the provider's rate bounded to sane timer values.

        Non-positive or non-finite rates mean "unusable" and yield ``0.0``,
        which keeps playback from starting or pauses it.
        """
        try:
            fps = float(self._fps_provider())
        except Exception as exc:
            logger.warning("Cine frame rate lookup failed: {}", exc)
            return 0.0
        if fps != fps or fps in (float("inf"), float("-inf")) or fps <= 0.0:
            return 0.0
        return max(min(fps, MAX_FPS), MIN_FPS)
