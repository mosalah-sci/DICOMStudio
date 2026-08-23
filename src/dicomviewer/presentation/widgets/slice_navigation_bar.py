"""Slice navigation bar shown beneath the viewer.

Combines previous/next buttons, a range slider, an editable
"current / total" slice counter and an optional play button that the cine
controller listens to. The bar is a dumb widget: it emits
:attr:`slice_selected` and :attr:`play_toggled` and exposes slots for the
viewer to keep it in sync.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from dicomviewer.presentation.theme.icon_provider import IconProvider


class SliceNavigationBar(QWidget):
    """Horizontal slice navigation strip with play/pause."""

    slice_selected = Signal(int)
    play_toggled = Signal(bool)

    def __init__(
        self,
        icon_provider: IconProvider,
        parent: QWidget | None = None,
    ) -> None:
        """Create the bar in its hidden (no series) state."""
        super().__init__(parent)
        self._icons = icon_provider
        self._count = 0
        self._suppress = False

        self._previous_button = QPushButton(self)
        self._previous_button.setObjectName("slicePreviousButton")
        self._previous_button.setToolTip("Previous slice")
        self._previous_button.setIcon(icon_provider.icon("chevron-left"))
        self._previous_button.clicked.connect(self._on_previous)

        self._next_button = QPushButton(self)
        self._next_button.setObjectName("sliceNextButton")
        self._next_button.setToolTip("Next slice")
        self._next_button.setIcon(icon_provider.icon("chevron-right"))
        self._next_button.clicked.connect(self._on_next)

        self._play_button = QPushButton(self)
        self._play_button.setObjectName("slicePlayButton")
        self._play_button.setToolTip("Play series (Space)")
        self._play_button.setCheckable(True)
        self._play_button.setIcon(icon_provider.icon("play"))
        self._play_button.toggled.connect(self._on_play_toggled)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setObjectName("sliceSlider")
        self._slider.setRange(0, 0)
        self._slider.valueChanged.connect(self._on_slider_moved)

        self._current_box = QSpinBox(self)
        self._current_box.setObjectName("sliceCurrentBox")
        self._current_box.setRange(1, 1)
        self._current_box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._current_box.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._current_box.setKeyboardTracking(False)
        self._current_box.setToolTip("Current slice — type a number and press Enter to jump")
        self._current_box.valueChanged.connect(self._on_current_edited)

        self._total_label = QLabel(self)
        self._total_label.setObjectName("sliceTotalLabel")
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        layout.addWidget(self._previous_button)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._next_button)
        layout.addWidget(self._current_box)
        layout.addWidget(self._total_label)
        layout.addWidget(self._play_button)

        self.hide()

    # Slots used by the viewer panel ---------------------------------------

    def set_range(self, count: int) -> None:
        """Configure the bar for ``count`` slices and show or hide it."""
        self._count = max(count, 0)
        self._suppress = True
        try:
            self._slider.setRange(0, max(self._count - 1, 0))
            self._slider.setValue(0)
            self._current_box.setRange(1, max(self._count, 1))
            self._current_box.setValue(1)
        finally:
            self._suppress = False
        self._total_label.setText(f"/ {self._count}")
        self._update_enabled()
        self.setVisible(self._count > 1)

    def set_index(self, index: int) -> None:
        """Reflect ``index`` without re-emitting :attr:`slice_selected`."""
        if self._count <= 0:
            return
        clamped = min(max(index, 0), self._count - 1)
        self._suppress = True
        try:
            self._slider.setValue(clamped)
            self._current_box.setValue(clamped + 1)
        finally:
            self._suppress = False

    def set_playing(self, playing: bool) -> None:
        """Reflect the playback state on the play button."""
        self._suppress = True
        try:
            self._play_button.setChecked(playing)
        finally:
            self._suppress = False
        self._play_button.setIcon(self._icons.icon("pause" if playing else "play"))

    def current_index(self) -> int:
        """Return the currently displayed zero-based index."""
        return self._slider.value()

    # Internal handlers ----------------------------------------------------

    def _on_previous(self) -> None:
        """Step one slice back."""
        self._emit_index(self._slider.value() - 1)

    def _on_next(self) -> None:
        """Step one slice forward."""
        self._emit_index(self._slider.value() + 1)

    def _on_slider_moved(self, value: int) -> None:
        """Forward slider movement to listeners."""
        if not self._suppress:
            self._apply_index(value)

    def _on_current_edited(self, value: int) -> None:
        """Forward current-slice edits (Enter, focus-out, arrows) to listeners."""
        if not self._suppress:
            self._apply_index(value - 1)

    def _on_play_toggled(self, checked: bool) -> None:
        """Forward play/pause toggles and update the icon."""
        self._play_button.setIcon(self._icons.icon("pause" if checked else "play"))
        if not self._suppress:
            self.play_toggled.emit(checked)

    def _apply_index(self, index: int) -> None:
        """Clamp and publish a new index, keeping all controls in step."""
        if self._count <= 0:
            return
        clamped = min(max(index, 0), self._count - 1)
        self._suppress = True
        try:
            self._slider.setValue(clamped)
            self._current_box.setValue(clamped + 1)
        finally:
            self._suppress = False
        self.slice_selected.emit(clamped)

    def _emit_index(self, index: int) -> None:
        """Emit only when the index actually changes."""
        if self._count > 0 and index != self._slider.value():
            self._apply_index(index)

    def _update_enabled(self) -> None:
        """Enable or disable the controls for the loaded slice count."""
        has_slices = self._count > 1
        self._previous_button.setEnabled(has_slices)
        self._next_button.setEnabled(has_slices)
        self._slider.setEnabled(has_slices)
        self._current_box.setEnabled(has_slices)
        self._total_label.setEnabled(has_slices)
