"""Metadata panel dock widget: grouped, searchable DICOM metadata."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.application.metadata import (
    MetadataExtractionError,
    MetadataService,
    filter_metadata,
)
from dicomviewer.domain.metadata import MetadataDocument, MetadataElement
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.empty_state import EmptyState
from dicomviewer.shared.constants import PADDING_8

_PAGE_EMPTY = 0
_PAGE_TREE = 1
_PAGE_NO_MATCHES = 2
_PAGE_UNAVAILABLE = 3

_ELEMENT_ROLE = Qt.ItemDataRole.UserRole


class MetadataPanel(QWidget):
    """Right sidebar hosting a grouped, searchable DICOM metadata browser.

    The panel shows the metadata of the currently displayed image. Elements
    are grouped logically (Patient, Study, Series, ...), can be filtered with
    a live search box, expanded or collapsed in bulk, and copied by tag or by
    value from the context menu.
    """

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        metadata_service: MetadataService,
        *,
        max_cache: int = 8,
    ) -> None:
        """Build the panel with its search box, tree and metadata service."""
        super().__init__(parent)
        self._service = metadata_service
        self._max_cache = max_cache
        self._images: tuple[Image, ...] = ()
        self._current_index = 0
        self._cache: dict[Path, MetadataDocument] = {}
        self._document: MetadataDocument | None = None

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search metadata…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)

        self._expand_button = QPushButton("Expand all", self)
        self._expand_button.clicked.connect(self._expand_all)
        self._collapse_button = QPushButton("Collapse all", self)
        self._collapse_button.clicked.connect(self._collapse_all)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, PADDING_8)
        controls_layout.addWidget(self._expand_button)
        controls_layout.addWidget(self._collapse_button)
        controls_layout.addStretch()

        self._controls = QWidget(self)
        controls = QVBoxLayout(self._controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(PADDING_8)
        controls.addWidget(self._search)
        controls.addLayout(controls_layout)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Property", "Value"])
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(16)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="info",
                title="No metadata available",
                description="Select a series to inspect its DICOM metadata.",
            )
        )
        self._stack.addWidget(self._tree)
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="info",
                title="No matching metadata",
                description="No elements match your search.",
            )
        )
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="info",
                title="Metadata unavailable",
                description="The metadata could not be read from the selected image.",
            )
        )
        self._stack.setCurrentIndex(_PAGE_EMPTY)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._controls)
        layout.addWidget(self._stack, stretch=1)

        self._controls.setVisible(False)

    def show_series(self, images: Sequence[Image], index: int = 0) -> None:
        """Display the metadata of the image at ``index`` within ``images``."""
        self._images = tuple(images)
        self._current_index = 0 if not self._images else max(0, min(index, len(self._images) - 1))
        self._controls.setVisible(bool(self._images))
        if not self._images:
            self._document = None
            self._stack.setCurrentIndex(_PAGE_EMPTY)
            return
        self._populate()

    def show_slice(self, index: int) -> None:
        """Display the metadata of the image at ``index`` in the current series."""
        if not self._images:
            return
        self._current_index = max(0, min(index, len(self._images) - 1))
        self._populate()

    def show_initial(self) -> None:
        """Return to the initial empty state and drop cached metadata."""
        self._images = ()
        self._current_index = 0
        self._cache.clear()
        self._document = None
        self._search.clear()
        self._controls.setVisible(False)
        self._stack.setCurrentIndex(_PAGE_EMPTY)

    def _populate(self) -> None:
        """Reload the current image's metadata and rebuild the tree."""
        document = self._document_for(self._current_index)
        self._document = document
        if document is None or not document.has_content():
            self._tree.clear()
            self._stack.setCurrentIndex(_PAGE_UNAVAILABLE)
            return
        filtered = filter_metadata(document, self._search.text())
        if not filtered.has_content():
            self._tree.clear()
            self._stack.setCurrentIndex(_PAGE_NO_MATCHES)
            return
        self._rebuild_tree(filtered)
        self._stack.setCurrentIndex(_PAGE_TREE)

    def _document_for(self, index: int) -> MetadataDocument | None:
        """Return the metadata document for the image at ``index``, cached."""
        image = self._images[index]
        cached = self._cache.get(image.path)
        if cached is not None:
            return cached
        try:
            document = self._service.extract(image)
        except MetadataExtractionError:
            return None
        except Exception:
            # A malformed file must not crash the panel; treat it as
            # unavailable and surface the problem to the user.
            logger.exception("Unexpected metadata extraction failure for %s", image.path)
            return None
        self._cache[image.path] = document
        self._evict_cache()
        return document

    def _evict_cache(self) -> None:
        """Drop the oldest cached documents, keeping the current image."""
        while len(self._cache) > self._max_cache:
            current = self._images[self._current_index].path
            for key in list(self._cache):
                if key != current:
                    del self._cache[key]
                    break
            else:
                break

    def _rebuild_tree(self, document: MetadataDocument) -> None:
        """Populate the tree from a (possibly filtered) metadata document.

        The expanded/collapsed state of existing groups is preserved so that
        navigating slices or typing a search does not forcibly re-expand
        groups the user collapsed.
        """
        expanded: set[str] = set()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item is not None and item.isExpanded():
                expanded.add(item.text(0))
        self._tree.clear()
        for group in document.groups:
            group_item = QTreeWidgetItem(self._tree)
            group_item.setText(0, group.name)
            group_item.setFirstColumnSpanned(True)
            font = QFont(group_item.font(0))
            font.setBold(True)
            group_item.setFont(0, font)
            for element in group.elements:
                self._add_element(group_item, element)
            group_item.setExpanded(group.name in expanded)

    def _add_element(self, parent: QTreeWidgetItem, element: MetadataElement) -> None:
        """Add one metadata element row under ``parent``."""
        item = QTreeWidgetItem(parent)
        item.setText(0, element.name)
        item.setText(1, element.value)
        item.setToolTip(0, _element_tooltip(element))
        item.setData(0, _ELEMENT_ROLE, element)

    def _on_search_changed(self, text: str) -> None:
        """Re-filter the current document when the search box changes."""
        del text
        self._populate()

    def _expand_all(self) -> None:
        """Expand every group in the tree."""
        self._tree.expandAll()

    def _collapse_all(self) -> None:
        """Collapse every group in the tree."""
        self._tree.collapseAll()

    def _show_context_menu(self, position: QPoint) -> None:
        """Show the copy actions for the element under the cursor."""
        item = self._tree.itemAt(position)
        element = item.data(0, _ELEMENT_ROLE) if item is not None else None
        if not isinstance(element, MetadataElement):
            return
        menu = QMenu(self)
        menu.addAction("Copy Tag", lambda: self._copy(element.tag))
        menu.addAction("Copy Value", lambda: self._copy(element.value))
        menu.exec(self._tree.viewport().mapToGlobal(position))

    def _copy(self, text: str) -> None:
        """Copy ``text`` to the system clipboard."""
        QApplication.clipboard().setText(text)


def _element_tooltip(element: MetadataElement) -> str:
    """Return the detailed tooltip for a metadata element."""
    parts = [element.tag, element.keyword, element.name]
    if element.value_representation:
        parts.append(f"VR {element.value_representation}")
    return "\n".join(parts)
