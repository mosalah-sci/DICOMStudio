"""Window preset manager dialog.

Lets users create, edit and delete custom window presets alongside the
read-only clinical built-ins. Mutations are pushed out immediately through
the injected ``on_apply`` callback so the main window can rebuild its preset
menu and persist the settings while the dialog stays open. Selecting a row
and pressing Apply applies that window to the active viewer.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.domain.image_processing import WINDOW_PRESETS, WindowPreset
from dicomviewer.domain.settings import MAX_CUSTOM_PRESETS, PresetsSettings
from dicomviewer.shared.constants import PADDING_12, PADDING_16

_CENTER_RANGE = 100_000.0
_WIDTH_RANGE = 100_000.0


class PresetManagerDialog(QDialog):
    """CRUD editor for custom window presets."""

    preset_selected = Signal(object)  # WindowPreset

    def __init__(
        self,
        parent: QWidget | None,
        *,
        presets: PresetsSettings,
        on_apply: Callable[[PresetsSettings], None],
    ) -> None:
        """Build the dialog over ``presets``, reporting edits via ``on_apply``."""
        super().__init__(parent)
        self.setWindowTitle("Manage Window Presets")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._presets = presets
        self._on_apply = on_apply

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_16, PADDING_16, PADDING_16, PADDING_16)
        layout.setSpacing(PADDING_12)

        self._list = QListWidget(self)
        self._list.setObjectName("presetList")
        layout.addWidget(self._list)

        self._warning = QLabel(self)
        self._warning.setObjectName("presetWarning")
        self._warning.setStyleSheet("color: #EF4444;")
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        button_row = QHBoxLayout()
        self._new_button = QPushButton("New...", self)
        self._new_button.setObjectName("presetNewButton")
        self._edit_button = QPushButton("Edit...", self)
        self._edit_button.setObjectName("presetEditButton")
        self._delete_button = QPushButton("Delete", self)
        self._delete_button.setObjectName("presetDeleteButton")
        for button in (
            self._new_button,
            self._edit_button,
            self._delete_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._apply_button = QPushButton("Apply to Viewer", self)
        self._apply_button.setObjectName("presetApplyButton")
        layout.addWidget(self._apply_button)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._new_button.clicked.connect(self._on_new)
        self._edit_button.clicked.connect(self._on_edit)
        self._delete_button.clicked.connect(self._on_delete)
        self._apply_button.clicked.connect(self._on_apply_selected)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._refresh_list()
        self._sync_buttons()

    # Population -----------------------------------------------------------

    def _refresh_list(self, select_name: str | None = None) -> None:
        """Rebuild the rows, optionally selecting ``select_name``."""
        self._list.blockSignals(True)
        try:
            self._list.clear()
            self._add_header("Built-in presets")
            for preset in WINDOW_PRESETS:
                item = self._make_item(preset)
                self._list.addItem(item)
                if preset.name == select_name:
                    self._list.setCurrentItem(item)
            self._add_header(f"Custom presets ({len(self._presets.custom)})")
            for preset in self._presets.custom:
                item = self._make_item(preset)
                self._list.addItem(item)
                if preset.name == select_name:
                    self._list.setCurrentItem(item)
        finally:
            self._list.blockSignals(False)
        if self._list.count() > 0 and self._list.currentRow() < 0:
            self._list.setCurrentRow(1)

    def _on_current_changed(
        self,
        _current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """Refresh button states after the selection moves."""
        self._sync_buttons()

    def _on_item_double_clicked(self, _item: QListWidgetItem) -> None:
        """Edit the double-clicked preset row."""
        self._on_edit()

    def _add_header(self, title: str) -> None:
        """Append a non-selectable section header row."""
        header = QListWidgetItem(title)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        self._list.addItem(header)

    def _make_item(self, preset: WindowPreset) -> QListWidgetItem:
        """Return a list item describing ``preset``."""
        return QListWidgetItem(f"{preset.name}   (C {preset.center:g} · W {preset.width:g})")

    def _sync_buttons(self) -> None:
        """Enable Edit/Delete only when a custom preset row is selected."""
        custom = self.selected_custom_preset()
        at_cap = len(self._presets.custom) >= MAX_CUSTOM_PRESETS
        self._new_button.setEnabled(not at_cap)
        self._edit_button.setEnabled(custom is not None)
        self._delete_button.setEnabled(custom is not None)
        self._apply_button.setEnabled(self.selected_preset() is not None)

    # Actions --------------------------------------------------------------

    def _on_new(self) -> None:
        """Create a preset from the edit form."""
        result = PresetEditDialog.edit(self, None, taken_names=self._taken_names())
        if result is None:
            return
        updated = self._presets.upsert(result)
        self._publish(updated, select_name=result.name)

    def _on_edit(self) -> None:
        """Edit the selected custom preset."""
        current = self.selected_custom_preset()
        if current is None:
            return
        result = PresetEditDialog.edit(
            self,
            current,
            taken_names=self._taken_names(exclude=current.name),
        )
        if result is None:
            return
        updated = self._presets.upsert(result)
        self._publish(updated, select_name=result.name)

    def _on_delete(self) -> None:
        """Remove the selected custom preset."""
        current = self.selected_custom_preset()
        if current is None:
            return
        self._publish(self._presets.remove(current.name))

    def _on_apply_selected(self) -> None:
        """Emit the selected preset for the viewer to apply."""
        preset = self.selected_preset()
        if preset is not None:
            self.preset_selected.emit(preset)

    # Helpers --------------------------------------------------------------

    def _publish(
        self,
        presets: PresetsSettings,
        select_name: str | None = None,
    ) -> None:
        """Store, hand off and re-render after one mutation."""
        self._presets = presets
        self._warning.hide()
        self._on_apply(presets)
        self._refresh_list(select_name)
        self._sync_buttons()

    def _taken_names(self, exclude: str | None = None) -> set[str]:
        """Return reserved preset names for uniqueness checks."""
        names = {preset.name for preset in WINDOW_PRESETS}
        names.update(preset.name for preset in self._presets.custom)
        names.discard(exclude or "")
        return names

    def selected_custom_preset(self) -> WindowPreset | None:
        """Return the selected custom preset, or ``None``."""
        name = self._raw_selection_name()
        if name is None:
            return None
        return self._presets.find(name)

    def selected_preset(self) -> WindowPreset | None:
        """Return the selected preset of either kind, or ``None``."""
        name = self._raw_selection_name()
        if name is None:
            return None
        for preset in WINDOW_PRESETS:
            if preset.name == name:
                return preset
        return self._presets.find(name)

    def _raw_selection_name(self) -> str | None:
        """Return the preset name encoded in the selected row, if any."""
        row = self._list.currentRow()
        if row < 0:
            return None
        item = self._list.item(row)
        if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return None
        # Rows are rendered as "<name>   (C ... · W ...)".
        return item.text().split("   (")[0]


class PresetEditDialog(QDialog):
    """Modal form for creating or renaming a single preset."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        preset: WindowPreset | None,
        taken_names: set[str],
    ) -> None:
        """Build the form pre-filled from ``preset`` when editing."""
        super().__init__(parent)
        self.setWindowTitle("Edit Preset" if preset else "New Preset")
        self.setModal(True)
        self.setMinimumWidth(300)
        self._taken_names = taken_names

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_16, PADDING_16, PADDING_16, PADDING_16)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._name_edit = QLineEdit(preset.name if preset else "", self)
        self._name_edit.setObjectName("presetNameEdit")
        form.addRow("Name", self._name_edit)

        self._center_spin = QDoubleSpinBox(self)
        self._center_spin.setObjectName("presetCenterSpin")
        self._center_spin.setRange(-_CENTER_RANGE, _CENTER_RANGE)
        self._center_spin.setDecimals(2)
        self._center_spin.setValue(preset.center if preset else 40.0)
        form.addRow("Window center", self._center_spin)

        self._width_spin = QDoubleSpinBox(self)
        self._width_spin.setObjectName("presetWidthSpin")
        self._width_spin.setRange(0.01, _WIDTH_RANGE)
        self._width_spin.setDecimals(2)
        self._width_spin.setValue(preset.width if preset else 400.0)
        form.addRow("Window width", self._width_spin)

        layout.addLayout(form)

        self._warning = QLabel(self)
        self._warning.setObjectName("presetEditWarning")
        self._warning.setStyleSheet("color: #EF4444;")
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @classmethod
    def edit(
        cls,
        parent: QWidget | None,
        preset: WindowPreset | None,
        *,
        taken_names: set[str],
    ) -> WindowPreset | None:
        """Run the form modally and return the resulting preset, if any."""
        dialog = cls(parent, preset=preset, taken_names=taken_names)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return WindowPreset(
            name=dialog._name(),
            center=dialog._center_spin.value(),
            width=dialog._width_spin.value(),
        )

    def accept(self) -> None:
        """Validate the form before allowing the dialog to close."""
        error = self._validation_error()
        if error is not None:
            self._warning.setText(error)
            self._warning.show()
            return
        self._warning.hide()
        super().accept()

    def _name(self) -> str:
        """Return the trimmed preset name."""
        return self._name_edit.text().strip()

    def _validation_error(self) -> str | None:
        """Return a user-facing validation message, or ``None`` when valid."""
        name = self._name()
        if not name:
            return "Enter a preset name."
        if name in self._taken_names:
            return f"'{name}' already exists. Choose another name."
        if self._width_spin.value() <= 0.0:
            return "Window width must be positive."
        return None
