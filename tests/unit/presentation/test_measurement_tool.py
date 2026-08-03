"""Tests for the measurement point-collection tool."""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF

from dicomviewer.domain.measurement import MeasurementKind, Point, required_point_count
from dicomviewer.presentation.widgets.measurement_tool import MeasurementTool


class _StubViewer(QObject):
    """Minimal viewer double exposing only the tool's dependencies."""

    def __init__(self) -> None:
        super().__init__()
        self.current_slice = 0
        self.has_image = True

    def widget_to_image(self, position: QPointF) -> Point:
        return Point(position.x(), position.y())

    def image_to_widget(self, point: Point) -> QPointF:
        return QPointF(point.x, point.y)


def _press(tool: MeasurementTool, x: float, y: float) -> None:
    tool.handle_press(QPointF(x, y))


def test_tool_is_inactive_by_default() -> None:
    tool = MeasurementTool(_StubViewer())
    assert not tool.is_active()
    assert tool.kind is None


def test_activate_sets_the_kind() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.DISTANCE)
    assert tool.is_active()
    assert tool.kind is MeasurementKind.DISTANCE


def test_deactivate_discards_drafts() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.DISTANCE)
    _press(tool, 1.0, 1.0)
    tool.deactivate()
    assert tool.kind is None
    assert tool.draft_points() == []


def test_two_presses_commit_a_distance() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.DISTANCE)
    commits: list[object] = []
    tool.commit_requested.connect(commits.append)
    _press(tool, 0.0, 0.0)
    assert not commits
    _press(tool, 3.0, 4.0)
    assert len(commits) == 1
    assert commits[0].kind is MeasurementKind.DISTANCE
    assert commits[0].points == (Point(0.0, 0.0), Point(3.0, 4.0))
    assert tool.draft_points() == []


def test_three_presses_commit_an_angle() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.ANGLE)
    commits: list[object] = []
    tool.commit_requested.connect(commits.append)
    for x, y in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)):
        _press(tool, x, y)
    assert len(commits) == 1
    assert commits[0].kind is MeasurementKind.ANGLE


def test_move_moves_the_preview_point() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.DISTANCE)
    _press(tool, 1.0, 1.0)
    assert tool.draft_points() == [Point(1.0, 1.0)]
    tool.handle_move(QPointF(3.0, 5.0))
    assert tool.draft_points() == [Point(1.0, 1.0)]
    assert tool.preview_point() == Point(3.0, 5.0)


def test_move_is_ignored_when_the_draft_is_complete() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.DISTANCE)
    _press(tool, 0.0, 0.0)
    _press(tool, 1.0, 1.0)
    tool.handle_move(QPointF(9.0, 9.0))
    assert tool.draft_points() == []
    assert tool.preview_point() is None


def test_cancel_draft_clears_the_current_slice() -> None:
    tool = MeasurementTool(_StubViewer())
    tool.activate(MeasurementKind.ANGLE)
    _press(tool, 0.0, 0.0)
    _press(tool, 1.0, 0.0)
    tool.cancel_draft()
    assert tool.draft_points() == []


def test_drafts_are_keyed_by_current_slice() -> None:
    viewer = _StubViewer()
    tool = MeasurementTool(viewer)
    tool.activate(MeasurementKind.ANGLE)
    viewer.current_slice = 0
    _press(tool, 0.0, 0.0)
    _press(tool, 1.0, 0.0)
    viewer.current_slice = 2
    assert tool.draft_points() == []
    viewer.current_slice = 0
    assert len(tool.draft_points()) == 2


def test_press_is_ignored_without_an_image() -> None:
    viewer = _StubViewer()
    viewer.has_image = False
    tool = MeasurementTool(viewer)
    tool.activate(MeasurementKind.DISTANCE)
    commits: list[object] = []
    tool.commit_requested.connect(commits.append)
    _press(tool, 0.0, 0.0)
    _press(tool, 1.0, 1.0)
    assert not commits
    assert tool.draft_points() == []


def test_required_point_counts() -> None:
    assert required_point_count(MeasurementKind.DISTANCE) == 2
    assert required_point_count(MeasurementKind.ANGLE) == 3
