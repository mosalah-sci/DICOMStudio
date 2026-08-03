"""Tests for the study explorer panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QTreeWidgetItem
from tests.dicom_utils import FakeThumbnailService

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail
from dicomviewer.presentation.widgets.study_explorer_panel import StudyExplorerPanel

THUMBNAIL = Thumbnail(width=4, height=4, data=bytes(16))


class FakeThumbnailLoader(QObject):
    """QObject double that records thumbnail requests without working."""

    thumbnail_ready = Signal(str, Path, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.requests: list[tuple[str, Image, int]] = []
        self.cancelled = 0

    def request(self, series_uid: str, image: Image, size: int) -> None:
        self.requests.append((series_uid, image, size))

    def cancel_pending(self) -> None:
        self.cancelled += 1


def _sample_tree() -> StudyTree:
    images = (
        Image(Path("a.dcm"), 1),
        Image(Path("b.dcm"), 2),
        Image(Path("c.dcm"), 3),
    )
    series = Series("s-ct", "CT", 1, "Chest", images)
    study = Study("st-1", "20260801", "1", "Chest exam", (series,))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


def _panel(
    icon_provider, loader: FakeThumbnailLoader | None = None
) -> tuple[StudyExplorerPanel, FakeThumbnailLoader]:
    fake_loader = loader or FakeThumbnailLoader()
    panel = StudyExplorerPanel(
        None,
        icon_provider,
        thumbnail_service=FakeThumbnailService(),
        thumbnail_loader=fake_loader,
    )
    return panel, fake_loader


def _collect_texts(item: QTreeWidgetItem) -> list[str]:
    texts = [item.text(0)]
    for index in range(item.childCount()):
        texts.extend(_collect_texts(item.child(index)))
    return texts


def test_panel_starts_on_the_initial_state(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    assert panel._stack.currentIndex() == 0


def test_panel_populates_the_tree(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    assert panel._stack.currentIndex() == 3
    texts = _collect_texts(panel._tree.topLevelItem(0))
    assert texts[0] == "DOE JOHN"
    assert any("Chest exam" in text for text in texts)
    assert any(text.startswith("CT") for text in texts)
    assert "Image 2" in texts


def test_panel_shows_no_results_for_an_empty_tree(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(StudyTree.empty(Path(".")))
    assert panel._stack.currentIndex() == 2


def test_expanding_a_series_requests_thumbnails(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    series_item.setExpanded(True)
    assert len(loader.requests) == 3
    assert loader.requests[0][0] == "s-ct"
    assert loader.requests[0][2] == 64


def test_thumbnails_are_requested_once(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    series_item.setExpanded(True)
    series_item.setExpanded(False)
    series_item.setExpanded(True)
    assert len(loader.requests) == 3


def test_ready_thumbnail_is_applied_to_its_image_item(qapp, icon_provider) -> None:
    panel, _loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    path = Path("a.dcm")
    panel._on_thumbnail_ready("s-ct", path, THUMBNAIL)
    item = panel._image_items[path]
    assert not item.icon(0).isNull()


def test_thumbnail_for_unknown_path_is_ignored(qapp, icon_provider) -> None:
    panel, _loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._on_thumbnail_ready("s-ct", Path("unknown.dcm"), THUMBNAIL)
    assert panel._thumbnail_cache[Path("unknown.dcm")] is THUMBNAIL


def test_new_tree_cancels_pending_thumbnails(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    before = loader.cancelled
    panel.set_study_tree(StudyTree.empty(Path(".")))
    assert loader.cancelled > before


def test_activating_a_series_emits_it_with_zero_index(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    activated: list = []
    panel.series_activated.connect(lambda series, index: activated.append((series, index)))
    series_item = panel._tree.topLevelItem(0).child(0).child(0)
    panel._tree.itemActivated.emit(series_item, 0)
    assert len(activated) == 1
    series, index = activated[0]
    assert series.series_instance_uid == "s-ct"
    assert index == 0


def test_activating_an_image_emits_its_index(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    activated: list = []
    panel.series_activated.connect(lambda series, index: activated.append((series, index)))
    image_item = panel._tree.topLevelItem(0).child(0).child(0).child(1)
    panel._tree.itemActivated.emit(image_item, 0)
    assert len(activated) == 1
    series, index = activated[0]
    assert series.series_instance_uid == "s-ct"
    assert index == 1
