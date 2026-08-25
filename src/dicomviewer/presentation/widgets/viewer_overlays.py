"""Painting helpers for the viewer's informational overlays.

Small pure formatters plus thin QPainter routines so the viewer widget stays
focused on input handling and paint coordination. Everything is deterministic
and covered by offscreen unit tests.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import atan2, cos, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen, QPolygonF

from dicomviewer.application.measurement import measurement_label
from dicomviewer.domain.annotation import Annotation, AnnotationKind
from dicomviewer.domain.measurement import Measurement, MeasurementKind, Point
from dicomviewer.domain.viewport import Viewport

_HISTOGRAM_WIDTH = 120.0
_HISTOGRAM_HEIGHT = 36.0

# Completed-overlay style constants (verbatim from the previous in-widget
# implementations; changing any of them changes rendered output).
ANNOTATION_COLOR = "#a78bfa"
SELECTION_HALO_COLOR = "#ffffff"
MEASUREMENT_PEN_WIDTH = 1.5
ENDPOINT_RADIUS = 3.0
POINT_RADIUS = 3.5
SELECTION_HALO_RADIUS = 7.0
ARROWHEAD_WIDGET_LENGTH = 10.0

PointMapper = Callable[[Point], QPointF]


@dataclass(frozen=True)
class SeriesOverlayInfo:
    """Demographic and study metadata shown by the info overlay."""

    patient_name: str = ""
    patient_id: str = ""
    birth_date: str = ""
    patient_sex: str = ""
    study_description: str = ""
    series_description: str = ""
    modality: str = ""
    body_part: str = ""
    series_number: int | None = None


def patient_lines(info: SeriesOverlayInfo) -> tuple[str, ...]:
    """Return the left-aligned patient identification lines."""
    lines: list[str] = []
    name = info.patient_name.strip()
    identifier = info.patient_id.strip()
    header = "  ".join(part for part in (name, f"[{identifier}]" if identifier else "") if part)
    if header:
        lines.append(header)
    demographics = "  ".join(
        part for part in (info.birth_date.strip(), info.patient_sex.strip()) if part
    )
    if demographics:
        lines.append(demographics)
    return tuple(lines)


def study_lines(info: SeriesOverlayInfo) -> tuple[str, ...]:
    """Return the right-aligned study and series description lines."""
    lines: list[str] = []
    for candidate in (
        info.study_description,
        info.series_description,
        _series_identity(info),
    ):
        text = candidate.strip()
        if text:
            lines.append(text)
    return tuple(lines)


def _series_identity(info: SeriesOverlayInfo) -> str:
    """Return the ``SER n · MODALITY · BODY PART`` identity string."""
    parts: list[str] = []
    if info.series_number is not None:
        parts.append(f"Ser {info.series_number}")
    modality = info.modality.strip().upper()
    if modality:
        parts.append(modality)
    body_part = info.body_part.strip()
    if body_part:
        parts.append(body_part)
    return " · ".join(parts)


def orientation_badges(viewport: Viewport) -> tuple[str, ...]:
    """Return short labels describing the applied display orientation."""
    badges: list[str] = []
    if viewport.rotation:
        badges.append(f"Rot {viewport.rotation}°")
    if viewport.flip_h:
        badges.append("Flip H")
    if viewport.flip_v:
        badges.append("Flip V")
    if viewport.invert:
        badges.append("Inverted")
    return tuple(badges)


def technical_line(
    viewport: Viewport,
    slice_count: int,
    zoom_percent: float,
) -> str:
    """Return the bottom-left ``W/L · slice · zoom`` status line."""
    parts: list[str] = []
    if viewport.window_width > 0 and viewport.window_center is not None:
        parts.append(f"W: {viewport.window_width:.0f} L: {viewport.window_center:.0f}")
    else:
        parts.append("W/L: Auto")
    if slice_count > 0:
        parts.append(f"{min(viewport.slice_index + 1, slice_count)} / {slice_count}")
    parts.append(f"{zoom_percent:.0f}%")
    return "   ".join(parts)


def draw_overlay_text(painter: QPainter, position: QPointF, text: str) -> None:
    """Draw one gray status text line at ``position``."""
    painter.save()
    painter.setPen(QColor("#b8b8b8"))
    painter.drawText(position, text)
    painter.restore()


def draw_label_box(painter: QPainter, text: str, position: QPointF) -> None:
    """Draw ``text`` on a rounded dark backdrop centred at ``position``."""
    font = painter.font()
    font.setBold(True)
    painter.setFont(font)
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(text) + 6.0
    height = metrics.height() + 4.0
    box = QRectF(position.x() - width / 2.0, position.y() - height / 2.0, width, height)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 150))
    painter.drawRoundedRect(box, 3.0, 3.0)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


def draw_right_aligned_block(painter: QPainter, rect: QRectF, lines: tuple[str, ...]) -> None:
    """Draw gray ``lines`` stacked from the top-right corner of ``rect``."""
    painter.save()
    painter.setPen(QColor("#b8b8b8"))
    metrics = QFontMetricsF(painter.font())
    offset = 12.0
    for line in lines:
        baseline = rect.top() + offset + metrics.ascent()
        painter.drawText(
            QPointF(rect.right() - 12.0 - metrics.horizontalAdvance(line), baseline), line
        )
        offset += metrics.height() + 2.0
    painter.restore()


def draw_left_aligned_block(painter: QPainter, rect: QRectF, lines: tuple[str, ...]) -> None:
    """Draw gray ``lines`` stacked from the top-left corner of ``rect``."""
    painter.save()
    painter.setPen(QColor("#b8b8b8"))
    metrics = QFontMetricsF(painter.font())
    offset = 12.0
    for line in lines:
        baseline = rect.top() + offset + metrics.ascent()
        painter.drawText(QPointF(rect.left() + 12.0, baseline), line)
        offset += metrics.height() + 2.0
    painter.restore()


def paint_histogram_bars(
    painter: QPainter,
    origin: QPointF,
    counts: Sequence[int],
    width: float = _HISTOGRAM_WIDTH,
    height: float = _HISTOGRAM_HEIGHT,
) -> None:
    """Draw a small bar histogram with ``counts`` buckets at ``origin``."""
    total_bins = len(counts)
    if total_bins <= 0:
        return
    maximum = max(counts)
    if maximum <= 0:
        return
    bar_width = width / total_bins
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#9ca3af"))
    for index, count in enumerate(counts):
        bar_height = height * count / maximum
        bar = QRectF(
            origin.x() + index * bar_width,
            origin.y() + (height - bar_height),
            bar_width + 0.5,
            bar_height,
        )
        painter.drawRect(bar)
    painter.restore()


def paint_series_info(
    painter: QPainter,
    rect: QRectF,
    info: SeriesOverlayInfo,
) -> None:
    """Draw the demographic block top-left and the study block top-right."""
    draw_left_aligned_block(painter, rect, patient_lines(info))
    draw_right_aligned_block(painter, rect, study_lines(info))


def draw_measurement(
    painter: QPainter,
    measurement: Measurement,
    *,
    pixel_spacing: tuple[float, float] | None,
    color: str,
    map_point: PointMapper,
) -> None:
    """Draw one completed measurement with its handle points and label.

    ``map_point`` converts image pixel coordinates to widget space using the
    viewer's current transform.
    """
    points = [map_point(point) for point in measurement.points]
    painter.save()
    pen_color = QColor(color)
    painter.setPen(QPen(pen_color, MEASUREMENT_PEN_WIDTH))
    painter.setBrush(pen_color)
    for point in points:
        painter.drawEllipse(point, ENDPOINT_RADIUS, ENDPOINT_RADIUS)
    label = measurement_label(measurement, pixel_spacing)
    if measurement.kind is MeasurementKind.DISTANCE:
        painter.drawLine(points[0], points[1])
        midpoint = QPointF(
            (points[0].x() + points[1].x()) / 2.0,
            (points[0].y() + points[1].y()) / 2.0,
        )
        draw_label_box(painter, label, midpoint)
    else:
        painter.drawLine(points[0], points[1])
        painter.drawLine(points[0], points[2])
        label_point = QPointF(
            (points[0].x() + (points[1].x() + points[2].x()) / 2.0) / 2.0,
            (points[0].y() + (points[1].y() + points[2].y()) / 2.0) / 2.0,
        )
        draw_label_box(painter, label, label_point)
    painter.restore()


def arrowhead_corner(anchor: QPointF, tip: QPointF, side: float) -> QPointF:
    """Return one arrowhead base corner beside ``tip`` in widget space."""
    length = ARROWHEAD_WIDGET_LENGTH
    dx = tip.x() - anchor.x()
    dy = tip.y() - anchor.y()
    angle = atan2(dy, dx)
    spread = atan2(length, length * 2.0) * side
    return QPointF(
        tip.x() - length * cos(angle + spread),
        tip.y() - length * sin(angle + spread),
    )


def draw_annotation(
    painter: QPainter,
    annotation: Annotation,
    *,
    is_selected: bool,
    map_point: PointMapper,
) -> None:
    """Draw one completed annotation in image-anchored widget space."""
    anchor = map_point(annotation.anchor)
    color = QColor(ANNOTATION_COLOR)
    painter.save()
    painter.setBrush(color)
    if is_selected:
        halo = QPen(QColor(SELECTION_HALO_COLOR), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(halo)
        painter.drawEllipse(anchor, SELECTION_HALO_RADIUS, SELECTION_HALO_RADIUS)
    painter.setPen(QPen(color, MEASUREMENT_PEN_WIDTH))
    if annotation.kind is AnnotationKind.POINT:
        painter.drawEllipse(anchor, POINT_RADIUS, POINT_RADIUS)
    elif annotation.tip is not None:
        tip = map_point(annotation.tip)
        painter.drawLine(anchor, tip)
        head = QPolygonF(
            [
                tip,
                arrowhead_corner(anchor, tip, +1.0),
                arrowhead_corner(anchor, tip, -1.0),
            ]
        )
        painter.drawPolygon(head)
    else:
        draw_label_box(painter, annotation.text, anchor)
    painter.restore()
