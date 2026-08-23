"""Tests for the settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QSpinBox,
)

from dicomviewer.domain.image_processing import WINDOW_PRESETS
from dicomviewer.domain.settings import (
    MAX_CINE_FPS,
    MIN_CINE_FPS,
    AppearanceSettings,
    LoggingSettings,
    MeasurementSettings,
    Settings,
    ViewingSettings,
)
from dicomviewer.presentation.dialogs.settings_dialog import SettingsDialog


def _viewing() -> ViewingSettings:
    return ViewingSettings()


def _measurements() -> MeasurementSettings:
    return MeasurementSettings()


def _settings(**overrides) -> Settings:
    return Settings(logging=LoggingSettings(), **overrides)


def _noop(*args, **kwargs) -> None:
    del args, kwargs


def _make_dialog(
    current_theme: str = "dark",
    viewing: ViewingSettings | None = None,
    measurements: MeasurementSettings | None = None,
) -> tuple[SettingsDialog, list]:
    calls: list = []
    dialog = SettingsDialog(
        None,
        current_theme=current_theme,
        viewing=viewing or _viewing(),
        measurements=measurements or _measurements(),
        on_theme_changed=_noop,
        on_apply=lambda v, m: calls.append((v, m)),
        on_reset=lambda: _settings(),
    )
    return dialog, calls


def test_dialog_lists_every_theme(qapp: QApplication) -> None:
    dialog, _ = _make_dialog()
    combo = dialog.findChild(QComboBox, "themeCombo")
    assert combo is not None
    assert combo.count() == 2


def test_preset_combo_lists_none_and_every_preset(qapp: QApplication) -> None:
    dialog, _ = _make_dialog()
    combo = dialog.findChild(QComboBox, "presetCombo")
    assert combo is not None
    assert combo.count() == len(WINDOW_PRESETS) + 1
    assert combo.currentIndex() == 0


def test_cache_spin_is_bounded_and_seeded(qapp: QApplication) -> None:
    dialog, _ = _make_dialog(viewing=ViewingSettings(max_cache_size=6))
    spin = dialog.findChild(QSpinBox, "cacheSpin")
    assert spin is not None
    assert spin.minimum() == 1
    assert spin.maximum() == 16
    assert spin.value() == 6


def test_rendering_toggles_reflect_settings(qapp: QApplication) -> None:
    viewing = ViewingSettings(
        smooth_scaling=False,
        show_statistics_overlay=False,
        show_measurement_overlay=True,
        show_info_overlay=False,
    )
    dialog, _ = _make_dialog(viewing=viewing)
    assert not dialog.findChild(QCheckBox, "smoothCheck").isChecked()
    assert not dialog.findChild(QCheckBox, "statisticsCheck").isChecked()
    assert dialog.findChild(QCheckBox, "measurementOverlayCheck").isChecked()
    assert not dialog.findChild(QCheckBox, "infoOverlayCheck").isChecked()


def test_cine_fps_spin_is_bounded_and_seeded(qapp: QApplication) -> None:
    dialog, _ = _make_dialog(viewing=ViewingSettings(cine_fps=30))
    spin = dialog.findChild(QSpinBox, "cineFpsSpin")
    assert spin is not None
    assert spin.minimum() == MIN_CINE_FPS
    assert spin.maximum() == MAX_CINE_FPS
    assert spin.value() == 30


def test_colour_edit_reflects_settings(qapp: QApplication) -> None:
    dialog, _ = _make_dialog(measurements=MeasurementSettings(color="#ff0000"))
    edit = dialog.findChild(QLineEdit, "colorEdit")
    assert edit is not None
    assert edit.text() == "#ff0000"


def test_theme_change_notifies_the_callback(qapp: QApplication) -> None:
    changes: list[str] = []
    dialog = SettingsDialog(
        None,
        current_theme="dark",
        viewing=_viewing(),
        measurements=_measurements(),
        on_theme_changed=changes.append,
        on_apply=_noop,
        on_reset=lambda: _settings(),
    )
    combo = dialog.findChild(QComboBox, "themeCombo")
    assert combo is not None
    combo.setCurrentIndex(1)
    assert changes == ["light"]


def test_accept_applies_the_selected_preferences(qapp: QApplication) -> None:
    dialog, calls = _make_dialog()
    dialog.findChild(QComboBox, "presetCombo").setCurrentIndex(1)
    dialog.findChild(QSpinBox, "cacheSpin").setValue(5)
    dialog.findChild(QCheckBox, "smoothCheck").setChecked(False)
    dialog.findChild(QCheckBox, "statisticsCheck").setChecked(False)
    dialog.findChild(QCheckBox, "infoOverlayCheck").setChecked(False)
    dialog.findChild(QSpinBox, "cineFpsSpin").setValue(30)
    dialog.findChild(QLineEdit, "colorEdit").setText("#ff0000")
    ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    ok.click()
    assert calls == [
        (
            ViewingSettings(
                default_window_preset=WINDOW_PRESETS[0].name,
                max_cache_size=5,
                smooth_scaling=False,
                show_statistics_overlay=False,
                show_measurement_overlay=True,
                show_info_overlay=False,
                cine_fps=30,
            ),
            MeasurementSettings(color="#ff0000"),
        )
    ]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_accept_rejects_an_invalid_colour(qapp: QApplication) -> None:
    dialog, calls = _make_dialog()
    dialog.findChild(QLineEdit, "colorEdit").setText("red")
    ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    ok.click()
    assert calls == []
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.findChild(QLineEdit, "colorEdit") is not None


def test_reset_restores_defaults_into_the_controls(qapp: QApplication) -> None:
    reset_settings = _settings(
        appearance=AppearanceSettings(theme="light"),
        viewing=ViewingSettings(
            default_window_preset="CT Lung",
            max_cache_size=7,
            show_info_overlay=False,
            cine_fps=45,
        ),
        measurements=MeasurementSettings(color="#00ff00"),
    )
    dialog = SettingsDialog(
        None,
        current_theme="dark",
        viewing=_viewing(),
        measurements=_measurements(),
        on_theme_changed=_noop,
        on_apply=_noop,
        on_reset=lambda: reset_settings,
    )
    reset_button = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.RestoreDefaults
    )
    reset_button.click()
    assert dialog.findChild(QComboBox, "themeCombo").currentText() == "Light"
    assert dialog.findChild(QComboBox, "presetCombo").currentText() == "CT Lung"
    assert dialog.findChild(QSpinBox, "cacheSpin").value() == 7
    assert not dialog.findChild(QCheckBox, "infoOverlayCheck").isChecked()
    assert dialog.findChild(QSpinBox, "cineFpsSpin").value() == 45
    assert dialog.findChild(QLineEdit, "colorEdit").text() == "#00ff00"
