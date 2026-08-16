"""Animated collapsible sidebars for the main workspace.

Each sidebar is a fixed-width drawer that slides open and closed along its
window edge. The drawer owns its collapse interaction through one integrated
arrow control: a slim full-height rail on the inner edge that also acts as
the collapsed rail. The panel is clipped while the drawer slides, so the
viewer next to it resizes continuously without any layout jump.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from dicomviewer.shared.constants import PADDING_4, PADDING_8

DRAWER_ANIMATION_MS = 250
DRAWER_RAIL_WIDTH = 28


class SidebarArrow(QWidget):
    """A slim full-height chevron that collapses or expands its drawer.

    Rendered from the active palette so it follows the dark and light themes
    without any stylesheet rules of its own.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build the arrow control."""
        super().__init__(parent)
        self._arrow_right = True
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_points_right(self, points_right: bool) -> None:
        """Point the chevron right when ``points_right`` is true."""
        if self._arrow_right != points_right:
            self._arrow_right = points_right
            self.update()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 - Qt virtual override
        """Mark the rail as hovered for a subtle highlight."""
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt virtual override
        """Clear the hover highlight."""
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt virtual override
        """Emit ``clicked`` when the rail is released over itself."""
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt virtual override
        """Draw the rail background and a chevron towards the action."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, self.palette().color(QPalette.ColorRole.Button))
        if self._hovered:
            highlight = QColor(self.palette().color(QPalette.ColorRole.Highlight))
            highlight.setAlpha(70)
            painter.fillRect(rect, highlight)
        pen = QPen(self.palette().color(QPalette.ColorRole.WindowText), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        radius = 5.0
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0
        if self._arrow_right:
            tip = QPointF(cx + radius, cy)
            painter.drawLine(tip, QPointF(cx - radius, cy - radius))
            painter.drawLine(tip, QPointF(cx - radius, cy + radius))
        else:
            tip = QPointF(cx - radius, cy)
            painter.drawLine(tip, QPointF(cx + radius, cy - radius))
            painter.drawLine(tip, QPointF(cx + radius, cy + radius))


class SidebarDrawer(QWidget):
    """A left or right drawer that slides open and closed on its window edge.

    The drawer animates its width between the open panel width and a slim
    rail that only contains the arrow control. The content panel stays
    anchored to the window edge while it slides, so the release of space is
    handed directly to the viewer beside it.
    """

    open_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget,
        title: str,
        panel: QWidget,
        *,
        side: str,
        open_width: int,
    ) -> None:
        """Build the drawer with ``panel`` as its content."""
        super().__init__(parent)
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        self._side = side
        self._title = title
        self._open_width = int(open_width)
        self._is_open = True
        self._rail_width = DRAWER_RAIL_WIDTH

        self.setObjectName("sidebarDrawer")

        self._content = QWidget(self)
        self._content.setObjectName("drawerContent")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        header = QWidget(self._content)
        header.setObjectName("drawerHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(PADDING_8, PADDING_4, PADDING_4, PADDING_4)
        header_layout.setSpacing(PADDING_4)
        title_label = QLabel(title, header)
        title_label.setObjectName("drawerHeaderTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        content_layout.addWidget(header)
        content_layout.addWidget(panel, 1)

        self._arrow = SidebarArrow(self)
        self._arrow.setObjectName("drawerRail")
        self._arrow.clicked.connect(self.toggle)

        self._animation = QPropertyAnimation(self, b"drawerWidth", self)
        self._animation.setDuration(DRAWER_ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)

        self.setFixedWidth(self._open_width)
        self._update_arrow()

    @property
    def is_open(self) -> bool:
        """True while the drawer shows its full panel."""
        return self._is_open

    @property
    def open_width(self) -> int:
        """The width of the drawer when fully open."""
        return self._open_width

    @property
    def rail_width(self) -> int:
        """The width of the collapsed rail."""
        return self._rail_width

    def toggle(self) -> None:
        """Slide the drawer into its opposite state."""
        self.set_open(not self._is_open)

    def set_open(self, open_: bool, *, animate: bool = True) -> None:
        """Open or collapse the drawer, optionally with a slide animation."""
        if self._is_open == open_:
            return
        self._is_open = open_
        self._update_arrow()
        if open_:
            self._content.setVisible(True)
        target = self._open_width if open_ else self._rail_width
        if animate and self.isVisible():
            self._animation.stop()
            self._animation.setStartValue(self.width())
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._animation.stop()
            self.setFixedWidth(target)
            if not open_:
                self._content.setVisible(False)
        self.open_changed.emit(open_)

    def set_open_width(self, width: int) -> None:
        """Change the open width, keeping the current open/collapsed state."""
        self._open_width = int(width)
        if self._is_open:
            self._animation.stop()
            self.setFixedWidth(self._open_width)
        self._relayout_children()

    def _on_animation_finished(self) -> None:
        """Hide the panel once a collapse animation has completed."""
        if not self._is_open:
            self._content.setVisible(False)

    def _update_arrow(self) -> None:
        """Point the chevron at the direction the drawer will slide next."""
        if self._side == "left":
            self._arrow.set_points_right(not self._is_open)
        else:
            self._arrow.set_points_right(self._is_open)
        verb = "Collapse" if self._is_open else "Expand"
        self._arrow.setToolTip(f"{verb} {self._title}")

    def _get_drawer_width(self) -> int:
        """Return the current drawer width for the width animation."""
        return self.width()

    def _set_drawer_width(self, width: int) -> None:
        """Resize the drawer to the animated width."""
        self.setFixedWidth(int(width))

    drawerWidth = Property(  # noqa: N815 - Qt property name
        int, _get_drawer_width, _set_drawer_width
    )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt virtual override
        """Anchor the panel on the outer edge and the rail on the inner edge."""
        super().resizeEvent(event)
        self._relayout_children()

    def _relayout_children(self) -> None:
        """Place the panel and rail according to the current drawer size.

        The panel tracks the visible drawer width so it never paints outside
        the drawer; the rail stays on the inner edge. This avoids relying on
        child clipping, which some Qt platforms do not apply.
        """
        width = self.width()
        height = self.height()
        panel_width = max(0, width - self._rail_width)
        if self._side == "left":
            self._content.setGeometry(0, 0, panel_width, height)
            self._arrow.setGeometry(width - self._rail_width, 0, self._rail_width, height)
        else:
            self._content.setGeometry(width - panel_width, 0, panel_width, height)
            self._arrow.setGeometry(0, 0, self._rail_width, height)
