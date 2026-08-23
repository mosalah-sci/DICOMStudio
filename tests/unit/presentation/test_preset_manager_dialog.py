"""Tests for the window preset manager dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from dicomviewer.domain.image_processing import WINDOW_PRESETS, WindowPreset
from dicomviewer.domain.settings import PresetsSettings
from dicomviewer.presentation.dialogs.preset_manager_dialog import PresetManagerDialog


def _dialog(
    presets: PresetsSettings | None = None,
) -> tuple[PresetManagerDialog, list[PresetsSettings]]:
    applied: list[PresetsSettings] = []
    dialog = PresetManagerDialog(
        None,
        presets=presets or PresetsSettings(),
        on_apply=lambda settings: applied.append(settings),
    )
    return dialog, applied


def test_lists_builtin_and_custom_presets(qapp) -> None:
    del qapp
    presets = PresetsSettings(custom=(WindowPreset("My Liver", 30.0, 200.0),))
    dialog, _applied = _dialog(presets)
    texts = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    assert any("CT Brain" in text for text in texts)
    assert any("My Liver" in text for text in texts)
    headers = [text for text in texts if "(" not in text or "Custom" in text]
    assert any("Built-in" in text for text in texts)
    assert any("Custom" in text and "presets" in text for text in texts)
    del headers


def test_new_preset_publishes_and_selects(qapp) -> None:
    del qapp
    dialog, applied = _dialog()
    created = WindowPreset("Dense Bone", 800.0, 2500.0)
    updated = dialog._presets.upsert(created)
    dialog._publish(updated, select_name=created.name)
    assert len(applied) == 1
    assert applied[0].find("Dense Bone") == created
    assert dialog.selected_custom_preset() == created
    assert not dialog._warning.isVisible()


def test_delete_removes_the_selected_custom_preset(qapp) -> None:
    del qapp
    presets = PresetsSettings(custom=(WindowPreset("Temp", 10.0, 20.0),))
    dialog, applied = _dialog(presets)
    row = next(
        index
        for index in range(dialog._list.count())
        if dialog._list.item(index).text().startswith("Temp")
    )
    dialog._list.setCurrentRow(row)
    assert dialog.selected_custom_preset() is not None
    dialog._on_delete()
    assert applied[-1].custom == ()
    assert dialog.selected_custom_preset() is None


def test_builtin_presets_are_not_editable(qapp) -> None:
    del qapp
    dialog, _applied = _dialog()
    builtin_name = WINDOW_PRESETS[0].name
    row = next(
        index
        for index in range(dialog._list.count())
        if dialog._list.item(index).text().startswith(builtin_name)
    )
    dialog._list.setCurrentRow(row)
    assert dialog.selected_custom_preset() is None
    assert not dialog._edit_button.isEnabled()
    assert not dialog._delete_button.isEnabled()
    assert dialog._apply_button.isEnabled()


def test_apply_button_emits_selected_preset(qapp) -> None:
    del qapp
    dialog, _applied = _dialog()
    emitted: list[object] = []
    dialog.preset_selected.connect(emitted.append)
    builtin_name = WINDOW_PRESETS[2].name
    row = next(
        index
        for index in range(dialog._list.count())
        if dialog._list.item(index).text().startswith(builtin_name)
    )
    dialog._list.setCurrentRow(row)
    dialog._on_apply_selected()
    assert emitted == [WINDOW_PRESETS[2]]


def test_new_button_disables_at_capacity(qapp) -> None:
    del qapp
    from dicomviewer.domain.settings import MAX_CUSTOM_PRESETS

    custom = tuple(
        WindowPreset(f"Preset {index}", float(index), 100.0) for index in range(MAX_CUSTOM_PRESETS)
    )
    dialog, _applied = _dialog(PresetsSettings(custom=custom))
    assert not dialog._new_button.isEnabled()


def test_edit_form_rejects_duplicate_names(qapp) -> None:
    del qapp
    from dicomviewer.presentation.dialogs.preset_manager_dialog import PresetEditDialog

    dialog = PresetEditDialog(
        None,
        preset=None,
        taken_names={WINDOW_PRESETS[0].name},
    )
    dialog._name_edit.setText(WINDOW_PRESETS[0].name)
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog._warning.isVisibleTo(dialog)


def test_edit_form_accepts_valid_input(qapp) -> None:
    del qapp
    from dicomviewer.presentation.dialogs.preset_manager_dialog import PresetEditDialog

    dialog = PresetEditDialog(None, preset=None, taken_names=set())
    dialog._name_edit.setText("  Custom Lung  ")
    dialog._center_spin.setValue(-500.0)
    dialog._width_spin.setValue(1500.0)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
