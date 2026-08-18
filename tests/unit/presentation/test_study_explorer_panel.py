"""Tests for the study explorer panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QTreeWidgetItem
from tests.dicom_utils import FakeThumbnailService

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail
from dicomviewer.presentation.widgets.study_explorer_panel import StudyExplorerPanel
from dicomviewer.presentation.widgets.thumbnail_grid import GRID_THUMBNAIL_SIZE

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


def _large_tree(image_count: int = 8) -> StudyTree:
    images = tuple(Image(Path(f"img-{i}.dcm"), i + 1) for i in range(image_count))
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


def _series_item(panel: StudyExplorerPanel) -> QTreeWidgetItem:
    return panel._tree.topLevelItem(0).child(0).child(0)


def _collect_texts(item: QTreeWidgetItem) -> list[str]:
    texts = [item.text(0)]
    for index in range(item.childCount()):
        texts.extend(_collect_texts(item.child(index)))
    return texts


def test_panel_starts_on_the_initial_state(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    assert panel._stack.currentIndex() == 0
    assert panel._grid.isHidden()


def test_panel_populates_the_tree(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    assert panel._stack.currentIndex() == 3
    texts = _collect_texts(panel._tree.topLevelItem(0))
    assert texts[0] == "DOE JOHN"
    assert any("Chest exam" in text for text in texts)
    assert any(text.startswith("CT") for text in texts)


def test_panel_shows_no_results_for_an_empty_tree(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(StudyTree.empty(Path(".")))
    assert panel._stack.currentIndex() == 2


def test_selecting_a_series_shows_the_preview_grid(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    assert not panel._grid.isHidden()
    assert panel._grid.series is not None
    assert panel._grid.series.series_instance_uid == "s-ct"


def test_selecting_a_patient_hides_the_preview_grid(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(panel._tree.topLevelItem(0))
    assert panel._grid.isHidden()
    assert panel._grid.series is None


def test_clearing_the_tree_hides_the_preview_grid(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    panel.set_study_tree(StudyTree.empty(Path(".")))
    assert panel._grid.isHidden()
    assert panel._grid.series is None


def test_selection_emits_the_selected_entity(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    selected: list = []
    panel.selection_changed.connect(lambda entity: selected.append(entity))
    panel._tree.setCurrentItem(_series_item(panel))
    assert len(selected) == 1
    assert isinstance(selected[0], Series)
    assert selected[0].series_instance_uid == "s-ct"


def test_selecting_a_series_requests_only_visible_thumbnails(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_large_tree(8))
    panel._tree.setCurrentItem(_series_item(panel))
    assert 1 <= len(loader.requests) < 8
    assert loader.requests[0][0] == "s-ct"
    assert loader.requests[0][2] == GRID_THUMBNAIL_SIZE


def test_thumbnails_are_requested_once(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    first = len(loader.requests)
    panel._tree.clearSelection()
    panel._tree.setCurrentItem(_series_item(panel))
    assert len(loader.requests) == first


def test_a_bigger_viewport_requests_more_thumbnails(qapp, icon_provider) -> None:
    panel, loader = _panel(icon_provider)
    panel.set_study_tree(_large_tree(12))
    panel._tree.setCurrentItem(_series_item(panel))
    small = len(loader.requests)
    panel._grid.resize(320, 320)
    panel._grid.show()
    qapp.processEvents()
    panel._request_visible_thumbnails()
    assert len(loader.requests) > small


def test_ready_thumbnail_is_applied_to_its_preview_cell(qapp, icon_provider) -> None:
    panel, _loader = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    panel._on_thumbnail_ready("s-ct", Path("a.dcm"), THUMBNAIL)
    cell = panel._grid.cell(0)
    assert cell is not None
    assert not cell._thumb_label.pixmap().isNull()


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
    panel._tree.itemActivated.emit(_series_item(panel), 0)
    assert len(activated) == 1
    series, index = activated[0]
    assert series.series_instance_uid == "s-ct"
    assert index == 0


def test_clicking_a_preview_cell_activates_the_series(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    activated: list = []
    panel.series_activated.connect(lambda series, index: activated.append((series, index)))
    panel._grid.cell(1).clicked.emit(1)
    assert len(activated) == 1
    series, index = activated[0]
    assert series.series_instance_uid == "s-ct"
    assert index == 1


def test_set_active_slice_selects_the_matching_thumbnail(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    panel._tree.setCurrentItem(_series_item(panel))
    panel.set_active_slice(2)
    assert panel._grid.selected_index() == 2
    assert panel._grid.cell(2).property("selected") is True


def test_set_active_slice_is_safe_without_a_series(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_active_slice(1)
    assert panel._grid.selected_index() == -1


def test_inspect_requested_emits_the_first_image_of_a_series(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    inspected: list = []
    panel.inspect_requested.connect(lambda image: inspected.append(image))
    panel._inspect_entity(_series_item(panel).data(0, _ENTITY_ROLE))
    assert len(inspected) == 1
    assert inspected[0].path == Path("a.dcm")


def test_inspect_requested_emits_the_image_itself(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    inspected: list = []
    panel.inspect_requested.connect(lambda image: inspected.append(image))
    series = _series_item(panel).data(0, _ENTITY_ROLE)
    panel._inspect_entity(series.images[1])
    assert len(inspected) == 1
    assert inspected[0].path == Path("b.dcm")


def test_inspect_requested_for_a_study_uses_its_first_series(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    inspected: list = []
    panel.inspect_requested.connect(lambda image: inspected.append(image))
    study_item = panel._tree.topLevelItem(0).child(0)
    panel._inspect_entity(study_item.data(0, _ENTITY_ROLE))
    assert len(inspected) == 1
    assert inspected[0].path == Path("a.dcm")


def test_inspect_requested_is_quiet_for_an_image_less_series(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    empty_series = Series("s-empty", "MR", 1, "None", ())
    panel.set_study_tree(_sample_tree())
    inspected: list = []
    panel.inspect_requested.connect(lambda image: inspected.append(image))
    panel._inspect_entity(empty_series)
    assert inspected == []


def test_context_menu_for_a_series_offers_open_and_inspect(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    menu = panel._build_context_menu(_series_item(panel).data(0, _ENTITY_ROLE))
    texts = [action.text() for action in menu.actions()]
    assert "Open in Viewer" in texts
    assert "Inspect DICOM Dataset..." in texts
    assert "Copy Summary" in texts
    assert "Expand All" in texts


def test_context_menu_for_a_patient_offers_open_first_study(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    patient_item = panel._tree.topLevelItem(0)
    menu = panel._build_context_menu(patient_item.data(0, _ENTITY_ROLE))
    texts = [action.text() for action in menu.actions()]
    assert "Open First Study" in texts
    assert "Inspect DICOM Dataset..." not in texts


def test_context_menu_for_an_image_offers_open_and_inspect(qapp, icon_provider) -> None:
    panel, _ = _panel(icon_provider)
    panel.set_study_tree(_sample_tree())
    series = _series_item(panel).data(0, _ENTITY_ROLE)
    menu = panel._build_context_menu(series.images[1])
    texts = [action.text() for action in menu.actions()]
    assert "Open" in texts
    assert "Inspect DICOM Dataset..." in texts


_ENTITY_ROLE = Qt.ItemDataRole.UserRole + 1
