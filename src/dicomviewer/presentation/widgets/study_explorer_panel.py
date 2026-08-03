"""Study Explorer dock panel: the discovered DICOM study tree."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QHeaderView,
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
from dicomviewer.presentation.widgets.empty_state import EmptyState
from dicomviewer.presentation.workers.thumbnail_loader import ThumbnailLoader
from dicomviewer.shared.constants import PADDING_12

THUMBNAIL_SIZE = 64
MAX_THUMBNAILS_PER_SERIES = 64

_PAGE_INITIAL = 0
_PAGE_SCANNING = 1
_PAGE_NONE = 2
_PAGE_TREE = 3

_KIND_ROLE = Qt.ItemDataRole.UserRole


class StudyExplorerPanel(QWidget):
    """Left sidebar hosting the patient/study/series/image hierarchy.

    The panel shows one of four states: an initial prompt, a scanning
    indicator, a no-results message, or the populated tree. Thumbnails are
    generated in the background when a series is expanded.
    """

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        *,
        thumbnail_service: ThumbnailService,
        thumbnail_loader: ThumbnailLoader | None = None,
    ) -> None:
        """Build the panel with its stacked states and background loader."""
        super().__init__(parent)
        self._icon_provider = icon_provider
        self._loader = thumbnail_loader or ThumbnailLoader(thumbnail_service, self)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)

        self._image_items: dict[Path, QTreeWidgetItem] = {}
        self._series_images: dict[str, tuple[Image, ...]] = {}
        self._requested_series: set[str] = set()
        self._thumbnail_cache: dict[Path, Thumbnail] = {}

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(16)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemExpanded.connect(self._on_item_expanded)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="folder-plus",
                title="No studies loaded",
                description="Open a folder to browse DICOM studies.",
            )
        )
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="activity",
                title="Scanning folder…",
                description="Discovering DICOM studies. This may take a moment.",
            )
        )
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="folder",
                title="No DICOM studies found",
                description="The selected folder contains no valid DICOM files.",
            )
        )
        self._stack.addWidget(self._tree)
        self._stack.setCurrentIndex(_PAGE_INITIAL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PADDING_12, PADDING_12, PADDING_12, PADDING_12)
        layout.addWidget(self._stack)

    def show_initial(self) -> None:
        """Return to the initial 'open a folder' state."""
        self._loader.cancel_pending()
        self._clear_tree()
        self._stack.setCurrentIndex(_PAGE_INITIAL)

    def show_scanning(self) -> None:
        """Show the scanning indicator and drop any pending thumbnails."""
        self._loader.cancel_pending()
        self._clear_tree()
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

    def _clear_tree(self) -> None:
        """Reset the tree and all cached lookup structures."""
        self._tree.clear()
        self._image_items.clear()
        self._series_images.clear()
        self._requested_series.clear()
        self._thumbnail_cache.clear()

    def _add_patient(self, patient: Patient) -> None:
        """Add a patient node and its studies to the tree."""
        item = QTreeWidgetItem(self._tree)
        item.setIcon(0, self._icon_provider.icon("user"))
        item.setText(0, _display_name(patient))
        item.setText(1, f"{patient.study_count} studies")
        item.setToolTip(0, _patient_tooltip(patient))
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
        for series in study.series:
            self._add_series(item, series)

    def _add_series(self, parent: QTreeWidgetItem, series: Series) -> None:
        """Add a series node and its images to the tree."""
        item = QTreeWidgetItem(parent)
        item.setIcon(0, self._icon_provider.icon("image"))
        title = series.modality
        if series.description:
            title = f"{title}  ·  {series.description}"
        item.setText(0, title)
        item.setText(1, f"{series.image_count} images")
        item.setData(0, _KIND_ROLE, ("series", series.series_instance_uid))
        item.setToolTip(0, _series_tooltip(series))
        self._series_images[series.series_instance_uid] = series.images
        for image in series.images:
            self._add_image(item, image)

    def _add_image(self, parent: QTreeWidgetItem, image: Image) -> None:
        """Add an image leaf node to the tree."""
        item = QTreeWidgetItem(parent)
        item.setIcon(0, self._icon_provider.icon("image"))
        item.setText(0, f"Image {image.instance_number}")
        item.setToolTip(0, str(image.path))
        self._image_items[image.path] = item

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Start background thumbnail generation for an expanded series."""
        kind_data = item.data(0, _KIND_ROLE)
        if not isinstance(kind_data, tuple):
            return
        kind, series_uid = cast(tuple[str, str], kind_data)
        if kind == "series":
            self._request_thumbnails(series_uid)

    def _request_thumbnails(self, series_uid: str) -> None:
        """Queue thumbnail generation for the images of a series, once."""
        if series_uid in self._requested_series:
            return
        self._requested_series.add(series_uid)
        for image in self._series_images.get(series_uid, ())[:MAX_THUMBNAILS_PER_SERIES]:
            if image.path in self._thumbnail_cache:
                continue
            self._loader.request(series_uid, image, THUMBNAIL_SIZE)

    def _on_thumbnail_ready(self, series_uid: str, path: Path, thumbnail: Thumbnail) -> None:
        """Apply a generated thumbnail to its image node."""
        self._thumbnail_cache[path] = thumbnail
        item = self._image_items.get(path)
        if item is None or not thumbnail.validate():
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
        item.setIcon(0, QIcon(QPixmap.fromImage(image)))


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
