"""Study Explorer dock panel: the discovered DICOM study tree and preview.

The panel hosts the patient/study/series hierarchy in one of four states
(initial prompt, scanning indicator, no-results message, or the populated
tree). Selecting a Series shows its images as a compact, scrollable thumbnail
grid beneath the tree; right-clicking a node opens a menu with only the
actions this application implements.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMenu,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dicomviewer.application.discovery import ThumbnailService
from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.empty_state import SidebarNote
from dicomviewer.presentation.widgets.thumbnail_grid import (
    GRID_THUMBNAIL_SIZE,
    ThumbnailGrid,
)
from dicomviewer.presentation.workers.thumbnail_loader import ThumbnailLoader

_PAGE_INITIAL = 0
_PAGE_SCANNING = 1
_PAGE_NONE = 2
_PAGE_TREE = 3

_KIND_ROLE = Qt.ItemDataRole.UserRole
_ENTITY_ROLE = Qt.ItemDataRole.UserRole + 1

_KIND_PATIENT = "patient"
_KIND_STUDY = "study"
_KIND_SERIES = "series"


class StudyExplorerPanel(QWidget):
    """Left sidebar hosting the patient/study/series hierarchy and preview.

    The panel shows one of four states: an initial prompt, a scanning
    indicator, a no-results message, or the populated tree. Selecting a
    Series reveals its images in a compact thumbnail grid; thumbnails are
    generated in the background only for cells that enter the viewport, so
    large series stay responsive. Right-clicking opens a menu with only
    actions this application implements.
    """

    series_activated = Signal(object, int)  # Series, requested slice index
    selection_changed = Signal(object)  # Patient | Study | Series | None
    inspect_requested = Signal(object)  # Image

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        *,
        thumbnail_service: ThumbnailService,
        thumbnail_loader: ThumbnailLoader | None = None,
    ) -> None:
        """Build the panel with its stacked states, tree and preview grid."""
        super().__init__(parent)
        self._icon_provider = icon_provider
        self._loader = thumbnail_loader or ThumbnailLoader(thumbnail_service, self)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)

        self._requested_paths: set[Path] = set()
        self._thumbnail_cache: dict[Path, Thumbnail] = {}
        self._active_series_uid: str | None = None
        self._active_index = 0

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(14)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemActivated.connect(self._on_item_activated)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

        self._grid = ThumbnailGrid(self)
        self._grid.image_activated.connect(self._on_grid_image_activated)
        self._grid.visible_changed.connect(self._request_visible_thumbnails)
        self._grid.setVisible(False)

        self._tree_page = QWidget(self)
        self._tree_page.setObjectName("explorerTreePage")
        splitter = QSplitter(Qt.Orientation.Vertical, self._tree_page)
        splitter.setObjectName("explorerSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._grid)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([180, 240])
        page_layout = QVBoxLayout(self._tree_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(splitter)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(SidebarNote(self, "No studies loaded"))
        self._scanning_state = SidebarNote(self)
        self._stack.addWidget(self._scanning_state)
        self._stack.addWidget(SidebarNote(self, "No DICOM studies found"))
        self._stack.addWidget(self._tree_page)
        self._stack.setCurrentIndex(_PAGE_INITIAL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack, stretch=1)

    def show_initial(self) -> None:
        """Return to the initial 'open a folder' state."""
        self._loader.cancel_pending()
        self._clear_tree()
        self._stack.setCurrentIndex(_PAGE_INITIAL)

    def show_scanning(self, folder: Path | None = None) -> None:
        """Show the scanning indicator, optionally naming the folder scanned."""
        self._loader.cancel_pending()
        self._clear_tree()
        if folder is not None:
            self._scanning_state.set_text(f"Scanning {folder}…")
        else:
            self._scanning_state.set_text("Scanning…")
        self._stack.setCurrentIndex(_PAGE_SCANNING)

    def set_study_tree(self, tree: StudyTree) -> None:
        """Replace the panel content with the discovered study tree."""
        self._loader.cancel_pending()
        self._clear_tree()
        if not tree.has_content():
            self._stack.setCurrentIndex(_PAGE_NONE)
            return
        for patient in tree.patients:
            self._add_patient(patient)
        self._stack.setCurrentIndex(_PAGE_TREE)

    def set_active_slice(self, index: int) -> None:
        """Highlight the thumbnail matching the currently displayed slice."""
        self._active_index = index
        if self._grid.series is not None:
            self._grid.set_selected_index(index)

    def _clear_tree(self) -> None:
        """Reset the tree, preview grid and cached lookup structures."""
        self._tree.clear()
        self._requested_paths.clear()
        self._thumbnail_cache.clear()
        self._grid.set_series(None)
        self._grid.setVisible(False)
        self._active_series_uid = None
        self._active_index = 0
        self._set_selection(None)

    def _add_patient(self, patient: Patient) -> None:
        """Add a patient node and its studies to the tree."""
        item = QTreeWidgetItem(self._tree)
        item.setIcon(0, self._icon_provider.icon("user"))
        item.setText(0, _display_name(patient))
        item.setText(1, f"{patient.study_count} studies")
        item.setToolTip(0, _patient_tooltip(patient))
        item.setData(0, _KIND_ROLE, _KIND_PATIENT)
        item.setData(0, _ENTITY_ROLE, patient)
        font = QFont(item.font(0))
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        item.setFont(0, font)
        for study in patient.studies:
            self._add_study(item, study)
        self._tree.expandItem(item)

    def _add_study(self, parent: QTreeWidgetItem, study: Study) -> None:
        """Add a study node and its series to the tree."""
        item = QTreeWidgetItem(parent)
        item.setIcon(0, self._icon_provider.icon("layers"))
        title = study.description or ("Study " + study.study_date if study.study_date else "Study")
        item.setText(0, title)
        item.setText(1, study.study_date)
        item.setToolTip(0, _study_tooltip(study))
        item.setData(0, _KIND_ROLE, _KIND_STUDY)
        item.setData(0, _ENTITY_ROLE, study)
        font = QFont(item.font(0))
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(0, font)
        for series in study.series:
            self._add_series(item, series)

    def _add_series(self, parent: QTreeWidgetItem, series: Series) -> None:
        """Add a series node to the tree."""
        item = QTreeWidgetItem(parent)
        item.setIcon(0, self._icon_provider.icon("image"))
        title = series.modality
        if series.description:
            title = f"{title}  ·  {series.description}"
        item.setText(0, title)
        item.setText(1, f"{series.image_count} images")
        item.setData(0, _KIND_ROLE, _KIND_SERIES)
        item.setData(0, _ENTITY_ROLE, series)
        item.setToolTip(0, _series_tooltip(series))

    def _on_item_activated(self, item: QTreeWidgetItem, column: int) -> None:
        """Open the activated node in the viewer."""
        del column
        entity = item.data(0, _ENTITY_ROLE)
        self._open_entity(entity)

    def _open_entity(self, entity: object) -> None:
        """Load the series implied by ``entity`` into the viewer."""
        if isinstance(entity, (Patient, Study)):
            first = _first_series(entity)
            if first is not None:
                self._activate(first, 0)
        elif isinstance(entity, Series):
            if entity.images:
                self._activate(entity, 0)

    def _activate(self, series: Series, index: int) -> None:
        """Mark ``series``/``index`` as active and emit the activation."""
        self._active_series_uid = series.series_instance_uid
        self._active_index = index
        if (
            self._grid.series is not None
            and self._grid.series.series_instance_uid == series.series_instance_uid
        ):
            self._grid.set_selected_index(index)
        self.series_activated.emit(series, index)

    def _on_grid_image_activated(self, index: int) -> None:
        """Display the image selected from the preview grid."""
        series = self._grid.series
        if series is None or not series.images:
            return
        self._activate(series, index)

    def _on_selection_changed(self) -> None:
        """Show the preview grid when a Series is selected."""
        items = self._tree.selectedItems()
        entity = items[0].data(0, _ENTITY_ROLE) if items else None
        self._set_selection(entity)

    def _set_selection(self, entity: object) -> None:
        """Sync the preview grid to the selected node and emit it."""
        self.selection_changed.emit(entity)
        if isinstance(entity, Series):
            self._grid.set_series(entity)
            self._grid.setVisible(True)
            if self._active_series_uid == entity.series_instance_uid:
                self._grid.set_selected_index(self._active_index)
            self._request_visible_thumbnails()
        else:
            self._grid.set_series(None)
            self._grid.setVisible(False)

    def _request_visible_thumbnails(self) -> None:
        """Queue thumbnail generation for the cells currently in the viewport."""
        series = self._grid.series
        if series is None:
            return
        for index in self._grid.visible_indices():
            if not 0 <= index < len(series.images):
                continue
            image = series.images[index]
            if image.path in self._requested_paths or image.path in self._thumbnail_cache:
                continue
            self._requested_paths.add(image.path)
            self._loader.request(series.series_instance_uid, image, GRID_THUMBNAIL_SIZE)

    def _on_thumbnail_ready(self, series_uid: str, path: Path, thumbnail: Thumbnail) -> None:
        """Apply a generated thumbnail to its preview cell."""
        del series_uid
        self._thumbnail_cache[path] = thumbnail
        if not thumbnail.validate():
            return
        image = QImage(
            bytes(thumbnail.data),
            thumbnail.width,
            thumbnail.height,
            thumbnail.width,
            QImage.Format.Format_Grayscale8,
        )
        if image.isNull():
            return
        self._grid.set_thumbnail(path, QPixmap.fromImage(image))

    def _show_context_menu(self, position: QPoint) -> None:
        """Show the context menu for the node under the cursor."""
        item = self._tree.itemAt(position)
        entity = item.data(0, _ENTITY_ROLE) if item is not None else None
        if not isinstance(entity, (Patient, Study, Series, Image)):
            return
        menu = self._build_context_menu(entity)
        menu.exec(self._tree.viewport().mapToGlobal(position))

    def _build_context_menu(self, entity: object) -> QMenu:
        """Return the context menu for ``entity`` without showing it."""
        menu = QMenu(self)
        if isinstance(entity, (Patient, Study)):
            menu.addAction(
                "Open First Study" if isinstance(entity, Patient) else "Open in Viewer",
                lambda: self._open_entity(entity),
            )
        elif isinstance(entity, Series):
            menu.addAction("Open in Viewer", lambda: self._open_entity(entity))
        elif isinstance(entity, Image):
            menu.addAction("Open", lambda: self._open_entity(entity))
        if isinstance(entity, (Study, Series, Image)):
            menu.addAction("Inspect DICOM Dataset...", lambda: self._inspect_entity(entity))
        menu.addSeparator()
        copy_action = QAction("Copy Summary", menu)
        copy_action.triggered.connect(lambda: _copy(_context_summary(entity)))
        menu.addAction(copy_action)
        menu.addSeparator()
        menu.addAction("Expand All", self._tree.expandAll)
        menu.addAction("Collapse All", self._tree.collapseAll)
        return menu

    def _inspect_entity(self, entity: object) -> None:
        """Request inspection of the first image implied by ``entity``."""
        image = _first_image(entity)
        if image is not None:
            self.inspect_requested.emit(image)


def _first_series(entity: object) -> Series | None:
    """Return the first series implied by ``entity``, or ``None``."""
    if isinstance(entity, Patient):
        for study in entity.studies:
            for series in study.series:
                return series
        return None
    if isinstance(entity, Study):
        return entity.series[0] if entity.series else None
    return None


def _first_image(entity: object) -> Image | None:
    """Return the first inspectable image implied by ``entity``."""
    if isinstance(entity, Image):
        return entity
    if isinstance(entity, Series):
        return entity.images[0] if entity.images else None
    if isinstance(entity, Study):
        series = _first_series(entity)
        return series.images[0] if series is not None and series.images else None
    if isinstance(entity, Patient):
        series = _first_series(entity)
        return series.images[0] if series is not None and series.images else None
    return None


def _context_summary(entity: object) -> str:
    """Return the concise one-line context summary for ``entity``."""
    if isinstance(entity, Patient):
        name = _display_name(entity)
        return f"Patient · {name}" f" · {entity.study_count} studies · {entity.image_count} images"
    if isinstance(entity, Study):
        title = entity.description or (
            "Study " + entity.study_date if entity.study_date else "Study"
        )
        parts = [f"Study · {title}"]
        if entity.study_date:
            parts.append(entity.study_date)
        parts.append(f"{entity.series_count} series · {entity.image_count} images")
        return " · ".join(parts)
    if isinstance(entity, Series):
        title = entity.modality
        if entity.description:
            title = f"{title} · {entity.description}"
        return f"Series · {title} · {entity.image_count} images"
    if isinstance(entity, Image):
        return f"Image {entity.instance_number} · {entity.path}"
    return ""


def _copy(text: str) -> None:
    """Copy ``text`` to the system clipboard."""
    if text:
        QApplication.clipboard().setText(text)


def _display_name(patient: Patient) -> str:
    """Return a readable patient label."""
    name = patient.name.replace("^", " ").strip()
    if name:
        return name
    if patient.patient_id:
        return patient.patient_id
    return "Unknown Patient"


def _patient_tooltip(patient: Patient) -> str:
    """Return a descriptive patient tooltip."""
    details = [
        f"Name: {patient.name or 'Unknown'}",
        f"ID: {patient.patient_id or 'Unknown'}",
    ]
    if patient.birth_date:
        details.append(f"Birth date: {patient.birth_date}")
    if patient.sex:
        details.append(f"Sex: {patient.sex}")
    return "\n".join(details)


def _study_tooltip(study: Study) -> str:
    """Return a descriptive study tooltip."""
    details = [f"Study: {study.description or 'Unnamed study'}"]
    if study.study_date:
        details.append(f"Date: {study.study_date}")
    details.append(f"Series: {study.series_count}  ·  Images: {study.image_count}")
    return "\n".join(details)


def _series_tooltip(series: Series) -> str:
    """Return a descriptive series tooltip."""
    details = [f"Modality: {series.modality or 'Unknown'}"]
    if series.description:
        details.append(f"Description: {series.description}")
    details.append(f"Images: {series.image_count}")
    return "\n".join(details)
