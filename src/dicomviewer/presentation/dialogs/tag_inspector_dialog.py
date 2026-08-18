"""Searchable DICOM dataset inspector dialog.

Opens a read-only, searchable table of the raw DICOM elements of one file.
Every element — public and private — is shown with its Tag, Keyword/Name, VR
and formatted Value. Inspection only: no editing, anonymization or networking.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.application.inspection import (
    InspectionError,
    TagInspector,
    filter_tags,
)
from dicomviewer.domain.tags import TagDocument, TagEntry

_COLUMN_COUNT = 5
_COLUMN_TAG = 0
_COLUMN_KEYWORD = 1
_COLUMN_NAME = 2
_COLUMN_VR = 3
_COLUMN_VALUE = 4

_ENTRY_ROLE = Qt.ItemDataRole.UserRole


class TagInspectorDialog(QDialog):
    """Read-only, searchable table of a single DICOM file's elements."""

    def __init__(
        self,
        parent: QWidget | None,
        path: Path,
        inspector: TagInspector,
        *,
        title: str = "DICOM Dataset Inspector",
    ) -> None:
        """Build the dialog for ``path`` and start loading its elements."""
        super().__init__(parent)
        self._path = Path(path)
        self._inspector = inspector
        self._document = TagDocument(source=self._path)
        self.setWindowTitle(title)
        self.resize(860, 560)

        self._source_label = QLabel(self)
        self._source_label.setObjectName("inspectorSource")
        self._source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search tags, keywords or values…")
        self._search.setClearButtonEnabled(True)
        self._search.setToolTip("Filter the DICOM elements as you type")
        self._search.textChanged.connect(self._on_search_changed)

        top_row = QHBoxLayout()
        top_row.addWidget(self._search, 1)

        self._table = QTableWidget(0, _COLUMN_COUNT, self)
        self._table.setHorizontalHeaderLabels(["Tag", "Keyword", "Name", "VR", "Value"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COLUMN_TAG, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COLUMN_KEYWORD, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COLUMN_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COLUMN_VR, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COLUMN_VALUE, QHeaderView.ResizeMode.Stretch)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("inspectorSummary")

        layout = QVBoxLayout(self)
        layout.addWidget(self._source_label)
        layout.addLayout(top_row)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._summary_label)

        self._document = self._load()
        self._populate()
        self._search.setFocus()

    @property
    def path(self) -> Path:
        """The file whose elements are displayed."""
        return self._path

    def _load(self) -> TagDocument:
        """Read the elements of the inspected file, degrading gracefully."""
        try:
            document = self._inspector.inspect(self._path)
        except InspectionError:
            return TagDocument(source=self._path)
        except Exception:
            # A malformed file must never crash the dialog.
            return TagDocument(source=self._path)
        return document

    def _populate(self) -> None:
        """Rebuild the table from the (possibly filtered) document."""
        filtered = filter_tags(self._document, self._search.text())
        self._table.setRowCount(0)
        self._table.setRowCount(len(filtered.entries))
        for row, entry in enumerate(filtered.entries):
            self._set_row(row, entry)
        self._source_label.setText(str(self._path))
        if filtered.has_content():
            self._summary_label.setText(
                f"{len(filtered.entries)} of {self._document.entry_count} elements"
            )
        else:
            self._summary_label.setText("No matching elements" if self._search.text() else "")
        self._table.clearSelection()

    def _set_row(self, row: int, entry: TagEntry) -> None:
        """Fill row ``row`` with the display values of ``entry``."""
        cells = (
            (entry.tag, _COLUMN_TAG),
            (entry.keyword or "", _COLUMN_KEYWORD),
            (entry.name, _COLUMN_NAME),
            (entry.value_representation, _COLUMN_VR),
            (entry.value, _COLUMN_VALUE),
        )
        for text, column in cells:
            item = QTableWidgetItem(text)
            if column == _COLUMN_TAG:
                item.setToolTip("Copy: right-click for options")
            item.setData(_ENTRY_ROLE, entry)
            self._table.setItem(row, column, item)

    def _on_search_changed(self, text: str) -> None:
        """Re-filter the table when the search box changes."""
        del text
        self._populate()

    def _show_context_menu(self, position: QPoint) -> None:
        """Offer copy actions for the row under the cursor."""
        item = self._table.itemAt(position)
        entry = item.data(_ENTRY_ROLE) if item is not None else None
        if not isinstance(entry, TagEntry):
            return
        menu = QMenu(self)
        menu.addAction("Copy Tag", lambda: _copy(entry.tag))
        menu.addAction("Copy Name", lambda: _copy(entry.name))
        menu.addAction("Copy Value", lambda: _copy(entry.value))
        menu.exec(self._table.viewport().mapToGlobal(position))


def _copy(text: str) -> None:
    """Copy ``text`` to the system clipboard."""
    QApplication.clipboard().setText(text)
