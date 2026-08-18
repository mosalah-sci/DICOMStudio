"""Tests for the metadata panel dock widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidgetItem
from tests.dicom_utils import FakeMetadataService, sample_metadata_document

from dicomviewer.application.metadata import MetadataExtractionError
from dicomviewer.domain.metadata import MetadataDocument
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.widgets.metadata_panel import MetadataPanel


class SliceMetadataService:
    """MetadataService double returning a document per image path."""

    def __init__(self, documents: dict[Path, MetadataDocument]) -> None:
        self.documents = documents
        self.extracted: list[Image] = []

    def extract(self, image: Image) -> MetadataDocument:
        self.extracted.append(image)
        document = self.documents.get(image.path)
        if document is None:
            raise MetadataExtractionError(f"Missing {image.path}")
        return document


def _panel(icon_provider, service=None) -> MetadataPanel:
    return MetadataPanel(
        None,
        icon_provider,
        service or FakeMetadataService(),
        max_cache=4,
    )


def _collect_texts(item: QTreeWidgetItem) -> list[str]:
    texts = [item.text(0), item.text(1)]
    for index in range(item.childCount()):
        texts.extend(_collect_texts(item.child(index)))
    return texts


def _element_item(panel: MetadataPanel) -> QTreeWidgetItem | None:
    for index in range(panel._tree.topLevelItemCount()):
        group = panel._tree.topLevelItem(index)
        if group.childCount():
            return group.child(0)
    return None


def test_panel_starts_on_the_initial_state(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    assert panel._stack.currentIndex() == 0
    assert not panel._controls.isVisible()


def test_show_series_populates_grouped_tree(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    assert panel._stack.currentIndex() == 1
    assert panel._tree.topLevelItemCount() == 3
    assert panel._tree.topLevelItem(0).text(0) == "Patient"
    assert panel._tree.topLevelItem(1).text(0) == "Study"
    texts = _collect_texts(panel._tree.topLevelItem(0))
    assert "Patient's Name" in texts
    assert "DOE^JOHN" in texts


def test_show_series_clears_controls_for_no_images(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series(())
    assert panel._stack.currentIndex() == 0
    assert not panel._controls.isVisible()


def test_show_slice_switches_metadata(qapp, icon_provider) -> None:
    first = sample_metadata_document(source=Path("a.dcm"), patient_name="DOE^JOHN")
    second = sample_metadata_document(source=Path("b.dcm"), patient_name="ROE^JANE")
    service = SliceMetadataService({Path("a.dcm"): first, Path("b.dcm"): second})
    panel = _panel(icon_provider, service)
    images = (Image(Path("a.dcm"), 1), Image(Path("b.dcm"), 2))
    panel.show_series(images, 0)
    assert "DOE^JOHN" in _collect_texts(panel._tree.topLevelItem(0))
    panel.show_slice(1)
    assert "ROE^JANE" in _collect_texts(panel._tree.topLevelItem(0))


def test_metadata_is_cached_per_image(qapp, icon_provider) -> None:
    first = sample_metadata_document(source=Path("a.dcm"))
    second = sample_metadata_document(source=Path("b.dcm"))
    service = SliceMetadataService({Path("a.dcm"): first, Path("b.dcm"): second})
    panel = _panel(icon_provider, service)
    images = (Image(Path("a.dcm"), 1), Image(Path("b.dcm"), 2))
    panel.show_series(images, 0)
    panel.show_slice(1)
    panel.show_slice(0)
    assert len(service.extracted) == 2


def test_search_filters_the_tree(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    panel._search.setText("P-1")
    assert panel._stack.currentIndex() == 1
    assert panel._tree.topLevelItemCount() == 1
    assert panel._tree.topLevelItem(0).text(0) == "Patient"


def test_search_with_no_matches_shows_the_no_matches_page(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    panel._search.setText("nonexistent")
    assert panel._stack.currentIndex() == 2


def test_clearing_the_search_restores_the_tree(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    panel._search.setText("P-1")
    panel._search.clear()
    assert panel._stack.currentIndex() == 1
    assert panel._tree.topLevelItemCount() == 3


def test_expand_and_collapse_all(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    panel._collapse_all()
    assert not panel._tree.topLevelItem(0).isExpanded()
    panel._expand_all()
    assert panel._tree.topLevelItem(0).isExpanded()


def test_copy_writes_to_the_clipboard(qapp: QApplication, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel._copy("(0010,0010)")
    assert QApplication.clipboard().text() == "(0010,0010)"


def test_element_items_carry_their_element_for_copy(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    item = _element_item(panel)
    assert item is not None
    element = item.data(0, Qt.ItemDataRole.UserRole)
    assert element.keyword == "PatientName"
    assert element.tag == "(0010,0010)"


def test_rows_show_property_and_value(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    item = _element_item(panel)
    assert item is not None
    assert item.text(0) == "Patient's Name"
    assert item.text(1) == "DOE^JOHN"
    assert panel._tree.columnCount() == 2


def test_extraction_failure_shows_the_unavailable_page(qapp, icon_provider) -> None:
    service = SliceMetadataService({})
    panel = _panel(icon_provider, service)
    panel.show_series((Image(Path("a.dcm"), 1),))
    assert panel._stack.currentIndex() == 3


def test_show_initial_clears_everything(qapp, icon_provider) -> None:
    panel = _panel(icon_provider)
    panel.show_series((Image(Path("a.dcm"), 1),))
    panel._search.setText("P-1")
    panel.show_initial()
    assert panel._stack.currentIndex() == 0
    assert not panel._controls.isVisible()
    assert panel._cache == {}
