"""Unit tests for the animated sidebar drawer and its arrow control."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from dicomviewer.presentation.widgets.sidebar_drawer import (
    DRAWER_ANIMATION_MS,
    DRAWER_RAIL_WIDTH,
    SidebarArrow,
    SidebarDrawer,
)


@pytest.fixture
def panel() -> QWidget:
    """A tiny stand-in panel with a deterministic width."""
    widget = QWidget()
    widget.setObjectName("panelStub")
    widget.setMinimumSize(0, 0)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel("content"))
    return widget


def _wait_for_idle(qapp: QApplication, drawer: SidebarDrawer) -> None:
    """Pump the event loop until the drawer animation has stopped."""
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        qapp.processEvents()
        if drawer._animation.state() == QAbstractAnimation.State.Stopped:
            return
        time.sleep(0.01)
    qapp.processEvents()


def test_left_drawer_starts_open_at_the_given_width(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "Study Explorer", panel, side="left", open_width=240)
    assert drawer.is_open
    assert drawer.width() == 240
    assert drawer.open_width == 240
    assert drawer.rail_width == DRAWER_RAIL_WIDTH
    drawer.deleteLater()


def test_open_width_uses_the_requested_side(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "Metadata", panel, side="right", open_width=300)
    assert drawer.width() == 300
    drawer.deleteLater()


def test_animation_uses_short_out_cubic_slide(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    assert drawer._animation.duration() == DRAWER_ANIMATION_MS
    assert drawer._animation.easingCurve().type() == QEasingCurve.Type.OutCubic
    assert drawer._animation.propertyName() == b"drawerWidth"
    drawer.deleteLater()


def test_collapse_hides_content_and_shrinks_to_the_rail(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    changes: list[bool] = []
    drawer.open_changed.connect(changes.append)
    drawer.set_open(False, animate=False)
    assert not drawer.is_open
    assert drawer.width() == DRAWER_RAIL_WIDTH
    assert drawer._content.isHidden()
    assert changes == [False]
    drawer.deleteLater()


def test_expand_restores_the_open_width_and_content(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    drawer.set_open(False, animate=False)
    changes: list[bool] = []
    drawer.open_changed.connect(changes.append)
    drawer.set_open(True, animate=False)
    assert drawer.is_open
    assert drawer.width() == 240
    assert not drawer._content.isHidden()
    assert changes == [True]
    drawer.deleteLater()


def test_arrow_points_at_the_direction_of_motion(qapp, panel) -> None:
    left = SidebarDrawer(None, "L", panel, side="left", open_width=240)
    right = SidebarDrawer(None, "R", panel, side="right", open_width=300)
    left_arrow = left.findChild(SidebarArrow)
    right_arrow = right.findChild(SidebarArrow)
    # Open: collapse toward the outer edge.
    assert not left_arrow._arrow_right
    assert right_arrow._arrow_right
    left.set_open(False, animate=False)
    right.set_open(False, animate=False)
    # Collapsed: expand toward the viewer edge.
    assert left_arrow._arrow_right
    assert not right_arrow._arrow_right
    left.deleteLater()
    right.deleteLater()


def test_toggle_flips_the_state_and_animates(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    drawer.show()
    qapp.processEvents()
    drawer.toggle()
    assert not drawer.is_open
    assert drawer._animation.state() == QAbstractAnimation.State.Running
    _wait_for_idle(qapp, drawer)
    assert drawer.width() == DRAWER_RAIL_WIDTH
    drawer.toggle()
    assert drawer.is_open
    _wait_for_idle(qapp, drawer)
    assert drawer.width() == 240
    drawer.deleteLater()


def test_no_animation_when_the_drawer_is_hidden(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    drawer.set_open(False)  # animate defaults to True but the widget is hidden
    assert drawer.width() == DRAWER_RAIL_WIDTH
    drawer.deleteLater()


def test_set_open_width_updates_a_live_drawer(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "S", panel, side="left", open_width=240)
    drawer.set_open_width(320)
    assert drawer.open_width == 320
    assert drawer.width() == 320
    drawer.set_open(False, animate=False)
    drawer.set_open_width(280)
    assert drawer.width() == DRAWER_RAIL_WIDTH
    drawer.set_open(True, animate=False)
    assert drawer.width() == 280
    drawer.deleteLater()


def test_right_drawer_anchors_content_on_the_outer_edge(qapp, panel) -> None:
    drawer = SidebarDrawer(None, "R", panel, side="right", open_width=300)
    drawer.show()
    qapp.processEvents()
    # Content occupies the right portion; the rail hugs the inner (left) edge.
    assert drawer._content.x() == drawer.rail_width
    assert drawer._arrow.x() == 0
    drawer.deleteLater()


def test_arrow_emits_clicked_on_release(qapp, panel) -> None:
    arrow = SidebarArrow(None)
    arrow.resize(DRAWER_RAIL_WIDTH, 60)
    clicks: list[int] = []
    arrow.clicked.connect(lambda: clicks.append(1))
    QTest.mouseClick(arrow, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert clicks == [1]
    arrow.deleteLater()
