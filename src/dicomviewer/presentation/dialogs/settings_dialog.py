"""Settings dialog."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.domain.image_processing import WINDOW_PRESETS
from dicomviewer.domain.settings import (
    MAX_CACHE_SIZE,
    MAX_CINE_FPS,
    MIN_CACHE_SIZE,
    MIN_CINE_FPS,
    MeasurementSettings,
    Settings,
    SettingsError,
    ViewingSettings,
)
from dicomviewer.presentation.theme.themes import THEMES
from dicomviewer.shared.constants import PADDING_12, PADDING_16

_NO_PRESET = "None (Automatic)"


class SettingsDialog(QDialog):
    """Exposes configuration options to the user.

    The dialog groups settings by Appearance, Viewing and Measurements. Theme
    changes apply immediately for a live preview; viewing and measurement
    preferences are collected and applied through ``on_apply`` when the user
    accepts. ``on_reset`` restores the bundled defaults and returns the new
    snapshot so the dialog can refresh its controls.
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        current_theme: str,
        viewing: ViewingSettings,
        measurements: MeasurementSettings,
        on_theme_changed: Callable[[str], None],
        on_apply: Callable[[ViewingSettings, MeasurementSettings], None],
        on_reset: Callable[[], Settings],
    ) -> None:
        """Build the dialog for the given settings state and callbacks."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._theme_names = list(THEMES)
        self._preset_names = [preset.name for preset in WINDOW_PRESETS]
        self._on_theme_changed = on_theme_changed
        self._on_apply = on_apply
        self._on_reset = on_reset

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_16, PADDING_16, PADDING_16, PADDING_16)
        layout.setSpacing(PADDING_12)

        layout.addWidget(self._build_appearance_group(current_theme))
        layout.addWidget(self._build_viewing_group(viewing))
        layout.addWidget(self._build_measurements_group(measurements))

        self._warning_label = QLabel(self)
        self._warning_label.setObjectName("settingsWarning")
        self._warning_label.setStyleSheet("color: #EF4444;")
        self._warning_label.setWordWrap(True)
        self._warning_label.hide()
        layout.addWidget(self._warning_label)

        layout.addStretch()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults,
            self,
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        self._buttons.clicked.connect(self._on_button_clicked)
        layout.addWidget(self._buttons)

    def _build_appearance_group(self, current_theme: str) -> QGroupBox:
        """Create the appearance group with the live theme selector."""
        group = QGroupBox("Appearance", self)
        form = QFormLayout(group)
        form.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        self._theme_combo = QComboBox(group)
        self._theme_combo.setObjectName("themeCombo")
        for theme_name in self._theme_names:
            self._theme_combo.addItem(THEMES[theme_name].display_name)
        self._set_combo_index(self._theme_combo, self._theme_names.index(current_theme))
        self._theme_combo.currentIndexChanged.connect(self._notify_theme_changed)
        form.addRow("Theme", self._theme_combo)
        hint = QLabel("Changes apply immediately.", group)
        hint.setObjectName("emptyStateBody")
        form.addRow("", hint)
        return group

    def _build_viewing_group(self, viewing: ViewingSettings) -> QGroupBox:
        """Create the viewing preferences group."""
        group = QGroupBox("Viewing", self)
        form = QFormLayout(group)
        form.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        self._preset_combo = QComboBox(group)
        self._preset_combo.setObjectName("presetCombo")
        self._preset_combo.addItem(_NO_PRESET)
        for preset_name in self._preset_names:
            self._preset_combo.addItem(preset_name)
        self._preset_combo.setCurrentIndex(self._preset_index(viewing.default_window_preset))
        form.addRow("Default window preset", self._preset_combo)

        self._cache_spin = QSpinBox(group)
        self._cache_spin.setObjectName("cacheSpin")
        self._cache_spin.setRange(MIN_CACHE_SIZE, MAX_CACHE_SIZE)
        self._cache_spin.setValue(viewing.max_cache_size)
        self._cache_spin.setToolTip("Number of decoded slices kept in memory")
        form.addRow("Decode cache size", self._cache_spin)

        self._smooth_check = QCheckBox("Smooth image scaling", group)
        self._smooth_check.setObjectName("smoothCheck")
        self._smooth_check.setChecked(viewing.smooth_scaling)
        form.addRow("", self._smooth_check)

        self._statistics_check = QCheckBox("Statistics and histogram", group)
        self._statistics_check.setObjectName("statisticsCheck")
        self._statistics_check.setChecked(viewing.show_statistics_overlay)
        form.addRow("Show", self._statistics_check)

        self._overlay_check = QCheckBox("Measurements", group)
        self._overlay_check.setObjectName("measurementOverlayCheck")
        self._overlay_check.setChecked(viewing.show_measurement_overlay)
        form.addRow("Show", self._overlay_check)

        self._info_check = QCheckBox("Patient/study info", group)
        self._info_check.setObjectName("infoOverlayCheck")
        self._info_check.setChecked(viewing.show_info_overlay)
        form.addRow("Show", self._info_check)

        self._cine_spin = QSpinBox(group)
        self._cine_spin.setObjectName("cineFpsSpin")
        self._cine_spin.setRange(MIN_CINE_FPS, MAX_CINE_FPS)
        self._cine_spin.setValue(viewing.cine_fps)
        self._cine_spin.setToolTip("Cine playback speed in frames per second")
        form.addRow("Cine playback (fps)", self._cine_spin)
        return group

    def _build_measurements_group(self, measurements: MeasurementSettings) -> QGroupBox:
        """Create the measurement preferences group."""
        group = QGroupBox("Measurements", self)
        form = QFormLayout(group)
        form.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        self._color_edit = QLineEdit(measurements.color, group)
        self._color_edit.setObjectName("colorEdit")
        self._color_edit.setMaxLength(7)
        self._color_edit.setPlaceholderText("#RRGGBB")
        self._pick_button = QPushButton("Pick...", group)
        self._pick_button.setObjectName("colorPickButton")
        self._pick_button.clicked.connect(self._select_color)
        form.addRow("Overlay colour", self._color_edit)
        form.addRow("", self._pick_button)
        return group

    def _on_accept(self) -> None:
        """Validate the controls and apply the preferences on success."""
        try:
            viewing = ViewingSettings.from_mapping(
                {
                    "default_window_preset": self._selected_preset(),
                    "max_cache_size": self._cache_spin.value(),
                    "smooth_scaling": self._smooth_check.isChecked(),
                    "show_statistics_overlay": self._statistics_check.isChecked(),
                    "show_measurement_overlay": self._overlay_check.isChecked(),
                    "show_info_overlay": self._info_check.isChecked(),
                    "cine_fps": self._cine_spin.value(),
                }
            )
            measurements = MeasurementSettings.from_mapping({"color": self._color_edit.text()})
        except SettingsError as exc:
            self._warning_label.setText(str(exc))
            self._warning_label.show()
            return
        self._warning_label.hide()
        self._on_apply(viewing, measurements)
        self.accept()

    def _handle_reset(self) -> None:
        """Restore defaults and repopulate the controls from the snapshot."""
        self._warning_label.hide()
        settings = self._on_reset()
        self._set_combo_index(self._theme_combo, self._theme_names.index(settings.appearance.theme))
        self._preset_combo.setCurrentIndex(
            self._preset_index(settings.viewing.default_window_preset)
        )
        self._cache_spin.setValue(settings.viewing.max_cache_size)
        self._smooth_check.setChecked(settings.viewing.smooth_scaling)
        self._statistics_check.setChecked(settings.viewing.show_statistics_overlay)
        self._overlay_check.setChecked(settings.viewing.show_measurement_overlay)
        self._info_check.setChecked(settings.viewing.show_info_overlay)
        self._cine_spin.setValue(settings.viewing.cine_fps)
        self._color_edit.setText(settings.measurements.color)

    def _select_color(self) -> None:
        """Open a colour picker and write the chosen hex value."""
        current = QColor(self._color_edit.text())
        chosen = QColorDialog.getColor(
            current if current.isValid() else QColor("#22d3ee"),
            self,
            "Choose Measurement Colour",
        )
        if chosen.isValid():
            self._color_edit.setText(chosen.name())

    def _notify_theme_changed(self, index: int) -> None:
        """Forward the newly selected theme to the caller."""
        self._on_theme_changed(self._theme_names[index])

    def _on_button_clicked(self, button: QPushButton) -> None:
        """Handle the Reset button without interfering with OK/Cancel."""
        if self._buttons.buttonRole(button) == QDialogButtonBox.ButtonRole.ResetRole:
            self._handle_reset()

    def _selected_preset(self) -> str:
        """Return the chosen preset name, or an empty string for none."""
        index = self._preset_combo.currentIndex()
        if index <= 0:
            return ""
        return self._preset_names[index - 1]

    def _preset_index(self, preset_name: str) -> int:
        """Return the combo index for ``preset_name``, or the none entry."""
        if preset_name in self._preset_names:
            return self._preset_names.index(preset_name) + 1
        return 0

    @staticmethod
    def _set_combo_index(combo: QComboBox, index: int) -> None:
        """Set a combo index without emitting the change signal."""
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)
