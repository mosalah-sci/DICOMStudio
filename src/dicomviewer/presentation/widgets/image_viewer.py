"""Interactive medical image viewer widget.

The widget renders a decoded slice through the injected renderer and lets the
user pan, zoom, adjust window/level and navigate slices. All pixel decoding
and rendering happens behind the application ports; this class only interprets
input and paints the resulting frame.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from math import atan2, cos, sin

from loguru import logger
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetricsF,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from dicomviewer.application.annotation import AnnotationCollection
from dicomviewer.application.measurement import MeasurementCollection, measurement_label
from dicomviewer.application.processing import Histogram, ImageAnalyzer, PixelStatistics
from dicomviewer.application.viewing import (
    PixelArray,
    PixelDecoder,
    RenderedImage,
    RenderingError,
    UnsupportedPixelFormatError,
    ViewRenderer,
)
from dicomviewer.domain.annotation import Annotation, AnnotationKind
from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.domain.measurement import Measurement, MeasurementKind, Point
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import FitMode, Viewport, clamp_slice
from dicomviewer.presentation.imaging.rendered_image import (
    rendered_image_from_qimage,
    to_qimage,
)
from dicomviewer.presentation.widgets import viewer_transform
from dicomviewer.presentation.widgets.annotation_tool import AnnotationTool
from dicomviewer.presentation.widgets.measurement_tool import MeasurementTool
from dicomviewer.presentation.widgets.viewer_overlays import (
    SeriesOverlayInfo,
    draw_label_box,
    draw_overlay_text,
    orientation_badges,
    paint_histogram_bars,
    paint_series_info,
    technical_line,
)

_DRAG_NONE = 0
_DRAG_PAN = 1
_DRAG_WINDOW_LEVEL = 2

_ZOOM_STEP = 1.25
_WL_LEVEL_PER_PIXEL = 0.5
_WL_WIDTH_PER_PIXEL = 0.5
_WL_MIN_WIDTH = 1.0
_DEFAULT_CACHE_SIZE = 3
# Rendered RGBA frames are far larger than decoded pixel arrays and are cheap
# to recreate (re-rendering reuses the decoded frame), so a small fixed cap
# keeps the render cache from competing with the user-configured decode cache.
_RENDER_CACHE_SIZE = 2
_HISTOGRAM_BINS = 128
_ANNOTATION_COLOR = "#a78bfa"
_ARROWHEAD_WIDGET_LENGTH = 10.0


class ImageViewerWidget(QWidget):
    """Displays one slice of a loaded series with full viewport interaction."""

    content_changed = Signal(bool)
    slice_changed = Signal(int, int)  # current index, total count
    zoom_changed = Signal(float)
    window_level_changed = Signal(object, float)  # center (None = auto), width
    measurements_changed = Signal(object)  # MeasurementCollection
    measure_mode_changed = Signal(object)  # MeasurementKind | None
    annotations_changed = Signal(object)  # AnnotationCollection
    annotation_mode_changed = Signal(object)  # AnnotationKind | None
    escape_pressed = Signal()  # Esc with no active tool, e.g. to leave fullscreen

    def __init__(
        self,
        parent: QWidget,
        decoder: PixelDecoder,
        renderer: ViewRenderer,
        *,
        analyzer: ImageAnalyzer,
        max_cache: int = _DEFAULT_CACHE_SIZE,
        smooth_scaling: bool = True,
        show_statistics_overlay: bool = True,
        show_measurement_overlay: bool = True,
        show_info_overlay: bool = True,
        measurement_color: str = "#22d3ee",
    ) -> None:
        """Create a viewer backed by ``decoder``, ``renderer`` and ``analyzer``."""
        super().__init__(parent)
        self._decoder = decoder
        self._renderer = renderer
        self._analyzer = analyzer
        self._max_cache = max_cache
        self._smooth_scaling = smooth_scaling
        self._show_statistics_overlay = show_statistics_overlay
        self._show_measurement_overlay = show_measurement_overlay
        self._show_info_overlay = show_info_overlay
        self._measurement_color = measurement_color
        self._images: tuple[Image, ...] = ()
        self._cache: dict[int, PixelArray] = {}
        self._slice_analysis: dict[int, tuple[PixelStatistics, Histogram]] = {}
        self._frame_cache: dict[tuple[int, float | None, float, bool], RenderedImage] = {}
        self._viewport = Viewport.initial()
        self._rendered: RenderedImage | None = None
        self._qimage: QImage | None = None
        self._last_error: str | None = None
        self._drag_mode = _DRAG_NONE
        self._drag_start = QPointF()
        self._drag_viewport: Viewport | None = None
        self._wl_baseline: tuple[float, float] | None = None
        self._measurements = MeasurementCollection()
        self._measure_tool = MeasurementTool(self)
        self._measure_tool.commit_requested.connect(self._on_measurement_committed)
        self._annotations = AnnotationCollection()
        self._annotation_tool = AnnotationTool(self)
        self._annotation_tool.commit_requested.connect(self._on_annotation_committed)
        self._annotation_tool.removal_requested.connect(self.remove_annotation)
        self._series_info: SeriesOverlayInfo | None = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    @property
    def viewport(self) -> Viewport:
        """Expose the current viewport for tests and diagnostics."""
        return self._viewport

    @property
    def has_image(self) -> bool:
        """Return whether a series is currently loaded."""
        return len(self._images) > 0

    @property
    def slice_count(self) -> int:
        """Return the number of images in the loaded series."""
        return len(self._images)

    @property
    def current_slice(self) -> int:
        """Return the index of the displayed slice."""
        return self._viewport.slice_index

    def load_series(self, images: Sequence[Image], index: int = 0) -> None:
        """Load ``images`` and display the slice at ``index``."""
        self._images = tuple(images)
        self._cache.clear()
        self._slice_analysis.clear()
        self._frame_cache.clear()
        self._last_error = None
        self._measurements = MeasurementCollection()
        self._measure_tool.reset()
        self._annotations = AnnotationCollection()
        self._annotation_tool.reset()
        self._viewport = Viewport(
            slice_index=clamp_slice(index, len(self._images)),
            fit_mode=FitMode.FIT,
        )
        self._render_current()
        self.update()
        self.measurements_changed.emit(self._measurements)
        self.annotations_changed.emit(self._annotations)
        if self.has_image:
            self.content_changed.emit(True)
            self.slice_changed.emit(self._viewport.slice_index, len(self._images))
        else:
            self.content_changed.emit(False)

    def clear(self) -> None:
        """Unload the series and return to the empty state."""
        self._images = ()
        self._cache.clear()
        self._slice_analysis.clear()
        self._frame_cache.clear()
        self._rendered = None
        self._qimage = None
        self._last_error = None
        self._measurements = MeasurementCollection()
        self._measure_tool.deactivate()
        self._annotations = AnnotationCollection()
        self._annotation_tool.deactivate()
        self._viewport = Viewport.initial()
        self.update()
        self.measurements_changed.emit(self._measurements)
        self.measure_mode_changed.emit(None)
        self.annotations_changed.emit(self._annotations)
        self.annotation_mode_changed.emit(None)
        self.content_changed.emit(False)

    def set_slice(self, index: int) -> None:
        """Display the slice at ``index``, clamped to the loaded range."""
        count = len(self._images)
        new_index = clamp_slice(index, count)
        if new_index == self._viewport.slice_index:
            return
        self._viewport = self._viewport.with_slice(new_index, count)
        self._render_current()
        self.update()
        self.slice_changed.emit(new_index, count)

    def next_slice(self) -> None:
        """Advance to the next slice."""
        self.set_slice(self._viewport.slice_index + 1)

    def previous_slice(self) -> None:
        """Move to the previous slice."""
        self.set_slice(self._viewport.slice_index - 1)

    def zoom_in(self) -> None:
        """Zoom in one step relative to the current display scale."""
        self._viewport = self._viewport.with_zoom(self._zoom_base() * _ZOOM_STEP)
        self.zoom_changed.emit(self._viewport.zoom)
        self.update()

    def zoom_out(self) -> None:
        """Zoom out one step relative to the current display scale."""
        self._viewport = self._viewport.with_zoom(self._zoom_base() / _ZOOM_STEP)
        self.zoom_changed.emit(self._viewport.zoom)
        self.update()

    def fit_to_window(self) -> None:
        """Fit the image to the current widget size."""
        self._viewport = self._viewport.fit()
        self.zoom_changed.emit(self._effective_scale())
        self.update()

    def actual_size(self) -> None:
        """Show the image at 100% pixel scale, centered."""
        self._viewport = self._viewport.actual()
        self.zoom_changed.emit(self._effective_scale())
        self.update()

    def reset_view(self) -> None:
        """Reset zoom, pan, orientation and window/level, keeping the slice."""
        self._viewport = Viewport(
            slice_index=self._viewport.slice_index,
            fit_mode=FitMode.FIT,
        )
        self._render_current()
        self.zoom_changed.emit(self._effective_scale())
        self.window_level_changed.emit(None, 0.0)
        self.update()

    def reset_window_level(self) -> None:
        """Return the window/level to the automatic setting."""
        self._viewport = self._viewport.with_window(None, 0.0)
        self._render_current()
        self.window_level_changed.emit(None, 0.0)
        self.update()

    def set_window(self, center: float, width: float) -> None:
        """Apply an explicit window (center, width) and re-render immediately."""
        self._viewport = self._viewport.with_window(center, width)
        self._render_current()
        self.window_level_changed.emit(center, width)
        self.update()

    def apply_preset(self, preset: WindowPreset) -> None:
        """Apply a named clinical window preset."""
        self.set_window(preset.center, preset.width)

    def rotate_cw(self) -> None:
        """Rotate the displayed frame 90 degrees clockwise."""
        self._viewport = self._viewport.rotate_cw()
        self.update()

    def rotate_ccw(self) -> None:
        """Rotate the displayed frame 90 degrees counter-clockwise."""
        self._viewport = self._viewport.rotate_ccw()
        self.update()

    def flip_horizontally(self) -> None:
        """Mirror the displayed frame horizontally."""
        self._viewport = self._viewport.toggle_flip_h()
        self.update()

    def flip_vertically(self) -> None:
        """Mirror the displayed frame vertically."""
        self._viewport = self._viewport.toggle_flip_v()
        self.update()

    def toggle_invert(self) -> None:
        """Toggle grayscale inversion and re-render the frame."""
        self._viewport = self._viewport.toggle_invert()
        self._render_current()
        self.update()

    @property
    def measurements(self) -> MeasurementCollection:
        """Return the per-slice measurement collection."""
        return self._measurements

    @property
    def measure_mode(self) -> MeasurementKind | None:
        """Return the active measurement kind, or ``None`` when inactive."""
        return self._measure_tool.kind

    def set_measure_mode(self, kind: MeasurementKind | None) -> None:
        """Activate or deactivate the measurement tool."""
        if kind is not None:
            self._annotation_tool.deactivate()
            self.annotation_mode_changed.emit(None)
        if kind is None:
            self._measure_tool.deactivate()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self._measure_tool.activate(kind)
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.measure_mode_changed.emit(kind)
        self.update()

    def remove_measurement(self, measurement: Measurement) -> None:
        """Remove one measurement from the current slice."""
        if self._measurements.remove(self.current_slice, measurement):
            self.measurements_changed.emit(self._measurements)
            self.update()

    def clear_measurements(self) -> None:
        """Remove every measurement from every slice."""
        self._measurements.clear_all()
        self._measure_tool.reset()
        self.measurements_changed.emit(self._measurements)
        self.update()

    @property
    def annotations(self) -> AnnotationCollection:
        """Return the per-slice annotation collection."""
        return self._annotations

    @property
    def annotation_mode(self) -> AnnotationKind | None:
        """Return the active annotation kind, or ``None`` when inactive."""
        return self._annotation_tool.kind

    def set_annotation_mode(self, kind: AnnotationKind | None) -> None:
        """Activate or deactivate the annotation tool.

        Activating an annotation kind leaves the measurement tool, which are
        mutually exclusive.
        """
        if kind is not None:
            self._measure_tool.deactivate()
            self.measure_mode_changed.emit(None)
        if kind is None:
            self._annotation_tool.deactivate()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self._annotation_tool.activate(kind)
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.annotation_mode_changed.emit(kind)
        self.update()

    def remove_annotation(self, annotation: Annotation) -> None:
        """Remove one annotation from the current slice."""
        if self._annotations.remove(self.current_slice, annotation):
            self.annotations_changed.emit(self._annotations)
            self.update()

    def clear_annotations(self) -> None:
        """Remove every annotation from every slice."""
        self._annotations.clear_all()
        self._annotation_tool.reset()
        self.annotations_changed.emit(self._annotations)
        self.update()

    def set_series_info(self, info: SeriesOverlayInfo | None) -> None:
        """Set the metadata block shown by the info overlay."""
        self._series_info = info
        self.update()

    def set_show_info_overlay(self, enabled: bool) -> None:
        """Show or hide the patient/study information overlay."""
        self._show_info_overlay = enabled
        self.update()

    def hit_tolerance_pixels(self) -> float:
        """Return the hit-test tolerance in image pixels for the pointer.

        The constant widget-space slop is converted with the current display
        scale and clamped so it stays usable at extreme zoom levels.
        """
        return viewer_transform.hit_tolerance(self._effective_scale())

    def set_max_cache(self, size: int) -> None:
        """Set the decode cache size and evict entries beyond it."""
        self._max_cache = max(size, 1)
        self._evict_cache()

    def set_smooth_scaling(self, enabled: bool) -> None:
        """Enable or disable smooth (interpolated) image scaling."""
        self._smooth_scaling = enabled
        self.update()

    def set_show_statistics_overlay(self, enabled: bool) -> None:
        """Show or hide the statistics and histogram overlay."""
        self._show_statistics_overlay = enabled
        self.update()

    def set_show_measurement_overlay(self, enabled: bool) -> None:
        """Show or hide the measurement overlay."""
        self._show_measurement_overlay = enabled
        self.update()

    def set_measurement_color(self, color: str) -> None:
        """Set the colour used to draw measurement overlays."""
        self._measurement_color = color
        self.update()

    def widget_to_image(self, position: QPointF) -> Point:
        """Map a widget coordinate into image pixel coordinates.

        The widget position is first expressed in display space, then run
        through the inverse of the orientation transform applied at paint
        time so annotations land on the same anatomy regardless of rotation
        or flips.
        """
        image = self._qimage
        if image is None or image.isNull():
            return Point(position.x(), position.y())
        return viewer_transform.widget_to_image(
            self._viewport,
            image.width(),
            image.height(),
            self.width(),
            self.height(),
            position,
        )

    def image_to_widget(self, point: Point) -> QPointF:
        """Map an image pixel coordinate into widget coordinates."""
        image = self._qimage
        if image is None or image.isNull():
            return QPointF(point.x, point.y)
        return viewer_transform.image_to_widget(
            self._viewport,
            image.width(),
            image.height(),
            self.width(),
            self.height(),
            point,
        )

    def capture_view(self) -> RenderedImage:
        """Return the current viewport (frame plus overlays) as a rendered frame.

        The capture matches what is displayed: the frame is painted with the
        current zoom, pan and window/level transform and the statistics,
        histogram and measurement overlays are included. The payload uses the
        ARGB32 byte order of the display pipeline so it can be exported or
        placed on the clipboard without a channel swap. Raises
        :class:`ValueError` when no series is loaded.
        """
        if not self.has_image:
            raise ValueError("No image is loaded to capture")
        image = QImage(self.size(), QImage.Format.Format_ARGB32)
        image.fill(self.palette().window().color())
        self.render(image)
        return rendered_image_from_qimage(image)

    @property
    def statistics(self) -> PixelStatistics | None:
        """Return the statistics of the current slice, or ``None`` if unknown."""
        analysis = self._analysis_for(self._viewport.slice_index)
        return analysis[0] if analysis is not None else None

    @property
    def histogram(self) -> Histogram | None:
        """Return the histogram of the current slice, or ``None`` if unknown."""
        analysis = self._analysis_for(self._viewport.slice_index)
        return analysis[1] if analysis is not None else None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Begin a pan/window drag or place a measurement/annotation point."""
        self.setFocus()
        if self._annotation_tool.is_active():
            if event.button() == Qt.MouseButton.LeftButton:
                self._annotation_tool.handle_press(event.position())
            elif event.button() == Qt.MouseButton.RightButton:
                self._annotation_tool.handle_right_press(event.position())
            self.update()
            return
        if self._measure_tool.is_active():
            if event.button() == Qt.MouseButton.LeftButton:
                self._measure_tool.handle_press(event.position())
                self.update()
            elif event.button() == Qt.MouseButton.RightButton:
                self._on_measure_right_press(event.position())
                self.update()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.has_image:
            self._begin_drag(_DRAG_PAN, event.position())
        elif event.button() == Qt.MouseButton.RightButton and self.has_image:
            self._begin_drag(_DRAG_WINDOW_LEVEL, event.position())
        else:
            super().mousePressEvent(event)

    def _on_measure_right_press(self, position: QPointF) -> None:
        """Cancel a measurement draft or remove the hit measurement."""
        if self._measure_tool.draft_points():
            self._measure_tool.cancel_draft()
            return
        hit = self._measurements.measurement_at(
            self.current_slice,
            self.widget_to_image(position),
            tolerance=self.hit_tolerance_pixels(),
        )
        if hit is not None:
            self.remove_measurement(hit)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the active drag or rubber-band a measurement draft."""
        if self._annotation_tool.is_active():
            self._annotation_tool.handle_move(event.position())
            self.update()
            return
        if self._measure_tool.is_active():
            self._measure_tool.handle_move(event.position())
            self.update()
            return
        if self._drag_mode == _DRAG_NONE or self._drag_viewport is None:
            return
        delta = event.position() - self._drag_start
        if self._drag_mode == _DRAG_PAN:
            scale = self._effective_scale()
            self._viewport = self._drag_viewport.with_pan(
                self._drag_viewport.pan_x + delta.x() / scale,
                self._drag_viewport.pan_y + delta.y() / scale,
            )
            self.update()
        elif self._drag_mode == _DRAG_WINDOW_LEVEL:
            baseline = self._wl_baseline
            if baseline is None:
                return
            center, width = baseline
            width = max(width + delta.y() * _WL_WIDTH_PER_PIXEL, _WL_MIN_WIDTH)
            center = center + delta.x() * _WL_LEVEL_PER_PIXEL
            self._viewport = self._drag_viewport.with_window(center, width)
            self._render_current()
            self.window_level_changed.emit(center, width)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End the active drag."""
        del event
        if not self._measure_tool.is_active() and not self._annotation_tool.is_active():
            self._end_drag()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Scroll slices, or zoom when a zoom modifier is held."""
        modifiers = event.modifiers()
        delta = event.angleDelta().y()
        if delta == 0:
            # Trackpads often report pixel deltas with a zero angle delta.
            delta = event.pixelDelta().y()
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
        else:
            if delta > 0:
                self.previous_slice()
            elif delta < 0:
                self.next_slice()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Navigate, zoom and run viewer shortcuts from the keyboard."""
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.previous_slice()
            event.accept()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self.next_slice()
            event.accept()
        elif key in (Qt.Key.Key_Home,):
            self.set_slice(0)
            event.accept()
        elif key in (Qt.Key.Key_End,):
            self.set_slice(len(self._images) - 1)
            event.accept()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
            event.accept()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
            event.accept()
        elif key == Qt.Key.Key_F and self.has_image:
            self.fit_to_window()
            event.accept()
        elif key == Qt.Key.Key_R and self.has_image:
            self.reset_view()
            event.accept()
        elif key == Qt.Key.Key_W and self.has_image:
            self.reset_window_level()
            event.accept()
        elif key == Qt.Key.Key_M and self.has_image:
            self.set_measure_mode(
                None if self._measure_tool.is_active() else MeasurementKind.DISTANCE
            )
            event.accept()
        elif key == Qt.Key.Key_Escape:
            if self._annotation_tool.is_active():
                if self._annotation_tool.has_draft():
                    self._annotation_tool.reset()
                elif self._annotation_tool.selected() is not None:
                    self._annotation_tool.set_selected(None)
                else:
                    self.set_annotation_mode(None)
            elif self._measure_tool.is_active():
                self.set_measure_mode(None)
            else:
                self.escape_pressed.emit()
            event.accept()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._annotation_tool.is_active() and self._annotation_tool.delete_selected():
                self.update()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the rendered frame with the current viewport transform."""
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window().color())
        image = self._qimage
        if image is not None and not image.isNull():
            if self._smooth_scaling:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            rect = self._target_rect(image)
            painter.save()
            painter.translate(rect.center())
            if self._viewport.rotation:
                # Qt angles are clockwise on screen because the y axis points
                # down, matching the domain's clockwise rotation convention.
                painter.rotate(float(self._viewport.rotation))
            painter.scale(
                -1.0 if self._viewport.flip_h else 1.0,
                -1.0 if self._viewport.flip_v else 1.0,
            )
            painter.translate(-rect.center())
            painter.drawImage(rect, image)
            painter.restore()
        if self._last_error:
            self._paint_message(painter, self._last_error)
        elif image is None:
            self._paint_message(painter, "No image")
        else:
            self._paint_overlay(painter)
        painter.end()

    def _begin_drag(self, mode: int, position: QPointF) -> None:
        """Store the drag baseline before interactive updates begin."""
        self._drag_mode = mode
        self._drag_start = position
        if mode == _DRAG_PAN:
            # Adopt the current display scale before leaving fit mode so the
            # image does not snap to 100% when the user starts panning.
            self._viewport = replace(
                self._viewport,
                zoom=self._zoom_base(),
                fit_mode=FitMode.FREE,
            )
            self._drag_viewport = self._viewport
            self.update()
        elif mode == _DRAG_WINDOW_LEVEL:
            self._drag_viewport = self._viewport
            center, width = self._effective_window_baseline()
            self._wl_baseline = (center, width)

    def _end_drag(self) -> None:
        """Clear the drag state."""
        self._drag_mode = _DRAG_NONE
        self._drag_viewport = None
        self._wl_baseline = None

    def _effective_window_baseline(self) -> tuple[float, float]:
        """Return a concrete window to adjust when the viewport is automatic."""
        pixels = self._current_pixels()
        if pixels is None:
            center = self._viewport.window_center
            width = self._viewport.window_width or 1.0
            return (center if center is not None else 0.0, width)
        return self._renderer.effective_window(pixels, self._viewport)

    def _current_pixels(self) -> PixelArray | None:
        """Return the decoded pixels for the current slice, or ``None``."""
        return self._slice_pixels(self._viewport.slice_index)

    def _slice_pixels(self, index: int) -> PixelArray | None:
        """Return decoded pixels for ``index``, decoding on demand with cache."""
        if not 0 <= index < len(self._images):
            return None
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        try:
            pixels = self._decoder.decode(self._images[index])
        except (UnsupportedPixelFormatError, OSError) as exc:
            self._report_error("This image could not be decoded.", exc)
            return None
        self._cache[index] = pixels
        self._evict_cache()
        return pixels

    def _evict_cache(self) -> None:
        """Drop oldest decoded slices, keeping the current one resident."""
        while len(self._cache) > self._max_cache:
            for key in list(self._cache):
                if key != self._viewport.slice_index:
                    del self._cache[key]
                    break
            else:
                break
        while len(self._slice_analysis) > self._max_cache:
            for key in list(self._slice_analysis):
                if key != self._viewport.slice_index:
                    del self._slice_analysis[key]
                    break
            else:
                break
        # Frame cache keys include the window/level settings, so a series of
        # window/level adjustments on one slice must still evict: always drop
        # the oldest entry (the just-rendered frame is the newest and stays).
        while len(self._frame_cache) > _RENDER_CACHE_SIZE:
            del self._frame_cache[next(iter(self._frame_cache))]

    def _analysis_for(self, index: int) -> tuple[PixelStatistics, Histogram] | None:
        """Return the cached analysis of ``index``, computing it on demand."""
        cached = self._slice_analysis.get(index)
        if cached is not None:
            return cached
        pixels = self._slice_pixels(index)
        if pixels is None:
            return None
        try:
            analysis = self._analyzer.analyze(pixels, bins=_HISTOGRAM_BINS)
        except Exception as exc:
            # Analysis is best-effort display metadata; a failure must not
            # interrupt painting or decoding of the frame itself.
            logger.warning("Image analysis failed for slice {}: {}", index, exc)
            return None
        self._slice_analysis[index] = analysis
        return analysis

    def _render_current(self) -> None:
        """Decode and render the current slice, tolerating failures."""
        pixels = self._current_pixels()
        if pixels is None:
            self._rendered = None
            self._qimage = None
            return
        self._measurements.pixel_spacing = pixels.pixel_spacing
        cache_key = (
            self._viewport.slice_index,
            self._viewport.window_center,
            self._viewport.window_width,
            self._viewport.invert,
        )
        rendered = self._frame_cache.get(cache_key)
        if rendered is None:
            try:
                rendered = self._renderer.render(pixels, self._viewport)
            except RenderingError as exc:
                self._report_error("This image could not be rendered.", exc)
                self._rendered = None
                self._qimage = None
                return
            self._frame_cache[cache_key] = rendered
            self._evict_cache()
        self._last_error = None
        self._rendered = rendered
        self._qimage = to_qimage(rendered)

    def _report_error(self, message: str, exc: BaseException) -> None:
        """Record a user-safe message while logging the technical detail.

        Raw exceptions are never painted on screen; the full detail goes to
        the log only, matching the project error-handling strategy.
        """
        logger.warning("Image display issue: {}", exc)
        self._last_error = message

    def _display_size(self, image: QImage) -> tuple[int, int]:
        """Return the on-screen size of ``image`` after orientation."""
        return oriented_size(image.width(), image.height(), self._viewport.rotation)

    def _effective_scale(self) -> float:
        """Return the scale factor that maps display pixels to widget pixels.

        Without a displayed frame the scale is defined as 1.0.
        """
        image = self._qimage
        if image is None or image.isNull():
            return 1.0
        return viewer_transform.effective_scale(
            self._viewport,
            image.width(),
            image.height(),
            self.width(),
            self.height(),
        )

    def _zoom_base(self) -> float:
        """Return the scale a relative zoom step should start from.

        In fit mode the stored zoom is a placeholder, so the effective display
        scale is used as the base; otherwise the current free zoom applies.
        """
        if self._viewport.fit_mode != FitMode.FIT:
            return self._viewport.zoom
        return self._effective_scale()

    def _target_rect(self, image: QImage) -> QRectF:
        """Return the destination rectangle for the rendered frame."""
        return viewer_transform.target_rect(
            self._viewport,
            image.width(),
            image.height(),
            self.width(),
            self.height(),
        )

    def _paint_overlay(self, painter: QPainter) -> None:
        """Draw info blocks, status line, badges, tools and overlays."""
        painter.save()
        if self._show_info_overlay and self._series_info is not None:
            paint_series_info(painter, QRectF(0, 0, self.width(), self.height()), self._series_info)
        line = technical_line(
            self._viewport,
            len(self._images),
            self._effective_scale() * 100.0,
        )
        draw_overlay_text(painter, QPointF(12.0, self.height() - 12.0), line)
        stats = self.statistics
        if self._show_statistics_overlay and stats is not None:
            text = (
                f"min {stats.minimum:.0f}  max {stats.maximum:.0f}  "
                f"mean {stats.mean:.1f}  SD {stats.standard_deviation:.1f}"
            )
            draw_overlay_text(painter, QPointF(12.0, self.height() - 30.0), text)
            self._paint_histogram(painter, QPointF(12.0, self.height() - 56.0))
        annotation_kind = self._annotation_tool.kind
        if self._annotation_tool.is_active() and annotation_kind is not None:
            hint = f"Annotating ({annotation_kind.value}) - click to place (Esc to stop)"
            draw_label_box(painter, hint, QPointF(self.width() / 2.0, 20.0))
        elif self._measure_tool.is_active():
            draw_label_box(
                painter,
                "Measuring - click to place points (Esc to stop)",
                QPointF(self.width() / 2.0, 20.0),
            )
        painter.restore()
        self._paint_orientation_badges(painter)
        if self._show_measurement_overlay:
            self._paint_measurements(painter)
        self._paint_annotations(painter)

    def _paint_orientation_badges(self, painter: QPainter) -> None:
        """Draw orientation badges right of the technical status line."""
        badges = orientation_badges(self._viewport)
        if not badges:
            return
        painter.save()
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        x = (
            12.0
            + metrics.horizontalAdvance(
                technical_line(
                    self._viewport,
                    len(self._images),
                    self._effective_scale() * 100.0,
                )
            )
            + 10.0
        )
        y = self.height() - 12.0 - metrics.height() / 2.0 + 3.0
        for badge in badges:
            draw_label_box(painter, badge, QPointF(x + metrics.horizontalAdvance(badge) / 2.0, y))
            x += metrics.horizontalAdvance(badge) + 12.0
        painter.restore()

    def _paint_measurements(self, painter: QPainter) -> None:
        """Draw completed measurements and the in-progress draft."""
        measurements = self._measurements.for_slice(self.current_slice)
        pixel_spacing = self._measurements.pixel_spacing
        for measurement in measurements:
            self._draw_measurement(painter, measurement, pixel_spacing)
        if self._show_measurement_overlay and self._measure_tool.is_active():
            draft = self._measure_tool.draft_points()
            preview = self._measure_tool.preview_point()
            if (
                self._measure_tool.kind is MeasurementKind.DISTANCE
                and len(draft) == 1
                and preview is not None
            ):
                provisional = Measurement(MeasurementKind.DISTANCE, (draft[0], preview))
                label = measurement_label(provisional, pixel_spacing)
                start = self.image_to_widget(draft[0])
                end = self.image_to_widget(preview)
                midpoint = QPointF(
                    (start.x() + end.x()) / 2.0,
                    (start.y() + end.y()) / 2.0,
                )
                draw_label_box(painter, label, midpoint)
            self._measure_tool.paint(painter)

    def _draw_measurement(
        self,
        painter: QPainter,
        measurement: Measurement,
        pixel_spacing: tuple[float, float] | None,
    ) -> None:
        """Draw one completed measurement with its handle points and label."""
        points = [self.image_to_widget(point) for point in measurement.points]
        painter.save()
        pen_color = QColor(self._measurement_color)
        painter.setPen(QPen(pen_color, 1.5))
        painter.setBrush(pen_color)
        for point in points:
            painter.drawEllipse(point, 3.0, 3.0)
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

    def _on_measurement_committed(self, measurement: Measurement) -> None:
        """Store a completed measurement and notify listeners."""
        self._measurements.add(self.current_slice, measurement)
        self.measurements_changed.emit(self._measurements)
        self.update()

    def _on_annotation_committed(self, annotation: Annotation) -> None:
        """Store a completed annotation and notify listeners."""
        self._annotations.add(self.current_slice, annotation)
        self.annotations_changed.emit(self._annotations)
        self.update()

    def _paint_annotations(self, painter: QPainter) -> None:
        """Draw completed annotations with selection halo and the draft."""
        annotations = self._annotations.for_slice(self.current_slice)
        selected = self._annotation_tool.selected()
        for annotation in annotations:
            self._draw_annotation(painter, annotation, is_selected=annotation is selected)
        if self._annotation_tool.is_active():
            self._annotation_tool.paint(painter)

    def _draw_annotation(
        self,
        painter: QPainter,
        annotation: Annotation,
        *,
        is_selected: bool,
    ) -> None:
        """Draw one completed annotation in image-anchored widget space."""
        anchor = self.image_to_widget(annotation.anchor)
        color = QColor(_ANNOTATION_COLOR)
        painter.save()
        painter.setBrush(color)
        if is_selected:
            halo = QPen(QColor("#ffffff"), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(halo)
            painter.drawEllipse(anchor, 7.0, 7.0)
        painter.setPen(QPen(color, 1.5))
        if annotation.kind is AnnotationKind.POINT:
            painter.drawEllipse(anchor, 3.5, 3.5)
        elif annotation.tip is not None:
            tip = self.image_to_widget(annotation.tip)
            painter.drawLine(anchor, tip)
            head = QPolygonF(
                [
                    tip,
                    self._arrowhead_corner(anchor, tip, +1.0),
                    self._arrowhead_corner(anchor, tip, -1.0),
                ]
            )
            painter.drawPolygon(head)
        else:
            draw_label_box(painter, annotation.text, anchor)
        painter.restore()

    def _arrowhead_corner(self, anchor: QPointF, tip: QPointF, side: float) -> QPointF:
        """Return one arrowhead base corner beside ``tip`` in widget space."""
        length = _ARROWHEAD_WIDGET_LENGTH
        dx = tip.x() - anchor.x()
        dy = tip.y() - anchor.y()
        angle = atan2(dy, dx)
        spread = atan2(length, length * 2.0) * side
        return QPointF(
            tip.x() - length * cos(angle + spread),
            tip.y() - length * sin(angle + spread),
        )

    def _paint_histogram(self, painter: QPainter, origin: QPointF) -> None:
        """Draw a small bar histogram for the current slice."""
        histogram = self.histogram
        if histogram is None:
            return
        paint_histogram_bars(painter, origin, histogram.counts)

    def _paint_message(self, painter: QPainter, message: str) -> None:
        """Draw a centered diagnostic message."""
        painter.save()
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)
        painter.restore()
