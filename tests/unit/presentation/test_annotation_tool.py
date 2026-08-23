"""Tests for the annotation tool interaction logic."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.domain.annotation import Annotation, AnnotationKind
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _viewer(text_provider=None) -> ImageViewerWidget:
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )
    viewer.resize(80, 60)
    viewer.load_series((Image(Path("slice.dcm"), 1),))
    if text_provider is not None:
        viewer._annotation_tool._text_provider = text_provider
    return viewer


def _center(viewer: ImageViewerWidget) -> QPointF:
    return QPointF(viewer.width() / 2.0, viewer.height() / 2.0)


def test_point_annotation_commits_on_first_click(qapp) -> None:
    del qapp
    viewer = _viewer()
    commits: list[Annotation] = []
    viewer._annotation_tool.commit_requested.connect(commits.append)
    viewer.set_annotation_mode(AnnotationKind.POINT)
    assert viewer.annotation_mode is AnnotationKind.POINT
    viewer._annotation_tool.handle_press(_center(viewer))
    assert len(commits) == 1
    assert commits[0].kind is AnnotationKind.POINT
    assert viewer.annotations.for_slice(0) == [commits[0]]


def test_arrow_annotation_needs_two_clicks(qapp) -> None:
    del qapp
    viewer = _viewer()
    tool = viewer._annotation_tool
    commits: list[Annotation] = []
    tool.commit_requested.connect(commits.append)
    viewer.set_annotation_mode(AnnotationKind.ARROW)
    tool.handle_press(QPointF(20.0, 30.0))
    assert not commits and tool.has_draft()
    tool.handle_press(QPointF(60.0, 30.0))
    assert len(commits) == 1
    assert commits[0].anchor.x < commits[0].tip.x  # type: ignore[union-attr]
    assert not tool.has_draft()


def test_text_annotation_uses_injected_provider(qapp) -> None:
    del qapp
    viewer = _viewer(text_provider=lambda title: "Lesion" if title else "")
    commits: list[Annotation] = []
    viewer._annotation_tool.commit_requested.connect(commits.append)
    viewer.set_annotation_mode(AnnotationKind.TEXT)
    viewer._annotation_tool.handle_press(_center(viewer))
    assert len(commits) == 1
    assert commits[0].text == "Lesion"
    cancelled = _viewer(text_provider=lambda title: None)
    cancelled.set_annotation_mode(AnnotationKind.TEXT)
    cancelled._annotation_tool.handle_press(_center(cancelled))
    assert cancelled.annotations.for_slice(0) == []


def test_clicking_near_annotation_selects_it(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer.set_annotation_mode(AnnotationKind.POINT)
    viewer._annotation_tool.handle_press(_center(viewer))
    existing = viewer.annotations.for_slice(0)[0]
    tool = viewer._annotation_tool
    selections: list[object] = []
    tool.selection_changed.connect(lambda: selections.append(tool.selected()))
    # Click again on the same spot: selects instead of drawing a new point.
    tool.handle_press(_center(viewer))
    assert tool.selected() is existing
    assert len(viewer.annotations.for_slice(0)) == 1
    assert len(selections) == 1


def test_right_click_removes_hit_annotation(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer.set_annotation_mode(AnnotationKind.POINT)
    viewer._annotation_tool.handle_press(_center(viewer))
    assert len(viewer.annotations.for_slice(0)) == 1
    consumed = viewer._annotation_tool.handle_right_press(_center(viewer))
    assert consumed
    assert viewer.annotations.for_slice(0) == []


def test_delete_key_removes_the_selection(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    viewer = _viewer()
    viewer.set_annotation_mode(AnnotationKind.POINT)
    viewer._annotation_tool.handle_press(_center(viewer))
    viewer._annotation_tool.set_selected(viewer.annotations.for_slice(0)[0])
    QTest.keyClick(viewer, Qt.Key.Key_Delete)
    assert viewer.annotations.for_slice(0) == []
    assert viewer._annotation_tool.selected() is None


def test_escape_exits_annotation_mode_in_stages(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    viewer = _viewer()
    escapes: list[bool] = []
    viewer.escape_pressed.connect(lambda: escapes.append(True))
    viewer.set_annotation_mode(AnnotationKind.ARROW)
    tool = viewer._annotation_tool
    tool.handle_press(QPointF(20.0, 30.0))
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert not tool.has_draft()  # first Esc cancels the draft
    assert viewer.annotation_mode is AnnotationKind.ARROW
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer.annotation_mode is None  # second Esc leaves the mode
    assert escapes == []


def test_measure_and_annotation_modes_are_exclusive(qapp) -> None:
    del qapp
    from dicomviewer.domain.measurement import MeasurementKind

    viewer = _viewer()
    modes: list[object] = []
    viewer.measure_mode_changed.connect(modes.append)
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    viewer.set_annotation_mode(AnnotationKind.POINT)
    assert viewer.measure_mode is None
    assert viewer.annotation_mode is AnnotationKind.POINT
    assert MeasurementKind.DISTANCE in [mode for mode in modes if mode]
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    assert viewer.annotation_mode is None


def test_clear_annotations_empties_every_slice(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer.set_annotation_mode(AnnotationKind.POINT)
    viewer._annotation_tool.handle_press(_center(viewer))
    viewer.clear_annotations()
    assert not viewer.annotations.has_any()


def test_load_series_resets_annotations(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer.set_annotation_mode(AnnotationKind.POINT)
    viewer._annotation_tool.handle_press(_center(viewer))
    viewer.load_series((Image(Path("other.dcm"), 1),))
    assert not viewer.annotations.has_any()
