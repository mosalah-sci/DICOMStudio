"""Compact, responsive thumbnail grid for the Study Explorer.

The grid replaces the per-image vertical tree list: a selected Series shows a
multi-column grid of small DICOM thumbnails with a minimal image index, a
clear selected-image highlight and smooth scrolling. Thumbnail pixels are
delivered lazily by the panel through :meth:`ThumbnailGrid.set_thumbnail`, so
the grid itself only manages layout and selection.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.domain.studies import Series
from dicomviewer.shared.constants import PADDING_4

GRID_THUMBNAIL_SIZE = 48
GRID_INDEX_HEIGHT = 16
GRID_CELL_HEIGHT = GRID_THUMBNAIL_SIZE + GRID_INDEX_HEIGHT
GRID_SPACING = PADDING_4
GRID_SCROLL_STEP = 16


class FlowLayout(QLayout):
    """Left-to-right wrapping layout that reflows to the available width."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = GRID_SPACING) -> None:
        """Create a flow layout with a fixed ``spacing`` between items."""
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 - Qt virtual override
        """Append ``item`` to the layout."""
        self._items.append(item)

    def count(self) -> int:
        """Return the number of managed items."""
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt virtual override
        """Return the item at ``index`` or ``None``."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt virtual override
        """Remove and return the item at ``index``."""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def take_all(self) -> None:
        """Remove every item and schedule its widget for deletion."""
        while self.count():
            item = self.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 - Qt virtual override
        """Only the width can absorb extra space."""
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt virtual override
        """Height depends on width, so height-for-width is supported."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt virtual override
        """Return the height needed to lay out items at ``width``."""
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt virtual override
        """Lay out all items inside ``rect``."""
        super().setGeometry(rect)
        self._do_layout(rect, dry_run=False)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt virtual override
        """Return a generous default size hint."""
        return QSize(0, 0)

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt virtual override
        """Return the smallest usable size."""
        return QSize(GRID_THUMBNAIL_SIZE + GRID_SPACING, GRID_CELL_HEIGHT + GRID_SPACING)

    def _do_layout(self, rect: QRect, *, dry_run: bool) -> int:
        """Arrange items in rows and return the required height."""
        spacing = self.spacing()
        x = rect.x()
        y = rect.y()
        row_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and row_height > 0:
                x = rect.x()
                y += row_height + spacing
                next_x = x + hint.width() + spacing
                row_height = 0
            if not dry_run:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()


class ThumbnailCell(QFrame):
    """One clickable thumbnail with a minimal image index label."""

    clicked = Signal(int)  # index within the series

    def __init__(self, index: int, instance_number: int, parent: QWidget | None = None) -> None:
        """Build the cell for ``index`` showing ``instance_number``."""
        super().__init__(parent)
        self._index = index
        self._selected = False
        self.setObjectName("gridCell")
        self.setFixedSize(GRID_THUMBNAIL_SIZE, GRID_CELL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Image {instance_number}")

        self._thumb_label = QLabel(self)
        self._thumb_label.setObjectName("gridThumb")
        self._thumb_label.setFixedSize(GRID_THUMBNAIL_SIZE, GRID_THUMBNAIL_SIZE)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._index_label = QLabel(str(instance_number), self)
        self._index_label.setObjectName("gridIndex")
        self._index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._thumb_label)
        layout.addWidget(self._index_label)

    def index(self) -> int:
        """Return the image index of this cell."""
        return self._index

    def set_selected(self, selected: bool) -> None:
        """Highlight this cell when ``selected`` is true."""
        if self._selected == selected:
            return
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        """Display ``pixmap`` scaled to the cell."""
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            GRID_THUMBNAIL_SIZE,
            GRID_THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb_label.setPixmap(scaled)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt virtual override
        """Emit ``clicked`` when released over the cell."""
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ThumbnailGrid(QScrollArea):
    """A scrollable, responsive grid of thumbnails for one series."""

    image_activated = Signal(int)  # index within the current series
    visible_changed = Signal()  # viewport scrolled or resized

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the empty, hidden grid."""
        super().__init__(parent)
        self._series: Series | None = None
        self._cells_by_index: dict[int, ThumbnailCell] = {}
        self._cells_by_path: dict[Path, ThumbnailCell] = {}
        self._selected_index = -1

        self.setObjectName("thumbnailGrid")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalScrollBar().setSingleStep(GRID_SCROLL_STEP)

        self._container = QWidget(self)
        self._container.setObjectName("thumbnailGridContent")
        self._content = QWidget(self._container)
        self._layout = FlowLayout(self._content)

        self._empty_label = QLabel("Select a series to preview its images")
        self._empty_label.setObjectName("gridEmpty")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)

        self._pages = QStackedWidget(self._container)
        self._pages.addWidget(self._empty_label)
        self._pages.addWidget(self._content)
        self._pages.setCurrentIndex(0)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._pages)
        self.setWidget(self._container)

        self.verticalScrollBar().valueChanged.connect(self.visible_changed)

    @property
    def series(self) -> Series | None:
        """The series whose thumbnails are displayed, if any."""
        return self._series

    def set_series(self, series: Series | None) -> None:
        """Rebuild the grid for ``series`` or clear it when ``None``."""
        if series is self._series:
            return
        self._clear_cells()
        self._series = series
        self._selected_index = -1
        if series is None or not series.images:
            self._pages.setCurrentIndex(0)
            self.verticalScrollBar().setValue(0)
            self.visible_changed.emit()
            return
        self._pages.setCurrentIndex(1)
        for index, image in enumerate(series.images):
            cell = ThumbnailCell(index, image.instance_number, self._content)
            cell.clicked.connect(self._on_cell_clicked)
            self._layout.addWidget(cell)
            self._cells_by_index[index] = cell
            self._cells_by_path[image.path] = cell
        self.verticalScrollBar().setValue(0)
        self.visible_changed.emit()

    def cell(self, index: int) -> ThumbnailCell | None:
        """Return the cell for ``index`` or ``None``."""
        return self._cells_by_index.get(index)

    def set_selected_index(self, index: int) -> None:
        """Highlight the cell at ``index`` and scroll it into view."""
        if index == self._selected_index:
            return
        previous = self._cells_by_index.get(self._selected_index)
        if previous is not None:
            previous.set_selected(False)
        self._selected_index = index
        cell = self._cells_by_index.get(index)
        if cell is not None:
            cell.set_selected(True)
            self.ensureWidgetVisible(cell, 4, 4)

    def selected_index(self) -> int:
        """Return the highlighted image index, or -1."""
        return self._selected_index

    def set_thumbnail(self, path: Path, pixmap: QPixmap) -> None:
        """Display ``pixmap`` in the cell belonging to ``path``."""
        cell = self._cells_by_path.get(path)
        if cell is not None:
            cell.set_thumbnail(pixmap)

    def visible_indices(self) -> list[int]:
        """Return the image indices currently inside the viewport.

        Uses fixed cell metrics rather than widget geometry so it behaves the
        same before the grid has been shown or laid out.
        """
        total = len(self._cells_by_index)
        if total == 0:
            return []
        width = max(self.viewport().width(), GRID_THUMBNAIL_SIZE)
        columns = max(1, width // (GRID_THUMBNAIL_SIZE + GRID_SPACING))
        step = GRID_CELL_HEIGHT + GRID_SPACING
        first_row = max(0, self.verticalScrollBar().value() // step)
        viewport_height = max(self.viewport().height(), step)
        row_count = max(1, (viewport_height + step - 1) // step + 1)
        indices: list[int] = []
        for row in range(first_row, first_row + row_count):
            for column in range(columns):
                index = row * columns + column
                if index < total:
                    indices.append(index)
        return indices

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt virtual override
        """Re-request visible thumbnails after a resize."""
        super().resizeEvent(event)
        self.visible_changed.emit()

    def _on_cell_clicked(self, index: int) -> None:
        """Forward a cell click, updating the selection highlight."""
        self.set_selected_index(index)
        self.image_activated.emit(index)

    def _clear_cells(self) -> None:
        """Drop every thumbnail cell and rebuild the lookup tables."""
        self._cells_by_index.clear()
        self._cells_by_path.clear()
        self._layout.take_all()
