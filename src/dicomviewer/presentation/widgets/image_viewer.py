"""Interactive medical image viewer widget.

The widget renders a decoded slice through the injected renderer and lets the
user pan, zoom, adjust window/level and navigate slices. All pixel decoding
and rendering happens behind the application ports; this class only interprets
input and paints the resulting frame.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from dicomviewer.application.viewing import (
    PixelArray,
    PixelDecoder,
    RenderedImage,
    RenderingError,
    UnsupportedPixelFormatError,
    ViewRenderer,
)
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import FitMode, Viewport, clamp_slice
from dicomviewer.presentation.imaging.rendered_image import to_qimage

_DRAG_NONE = 0
_DRAG_PAN = 1
_DRAG_WINDOW_LEVEL = 2

_ZOOM_STEP = 1.25
_WL_LEVEL_PER_PIXEL = 0.5
_WL_WIDTH_PER_PIXEL = 0.5
_WL_MIN_WIDTH = 1.0
_DEFAULT_CACHE_SIZE = 3


class ImageViewerWidget(QWidget):
    """Displays one slice of a loaded series with full viewport interaction."""

    content_changed = Signal(bool)
    slice_changed = Signal(int, int)  # current index, total count
    zoom_changed = Signal(float)
    window_level_changed = Signal(object, float)  # center (None = auto), width

    def __init__(
        self,
        parent: QWidget,
        decoder: PixelDecoder,
        renderer: ViewRenderer,
        *,
        max_cache: int = _DEFAULT_CACHE_SIZE,
    ) -> None:
        """Create a viewer backed by ``decoder`` and ``renderer``."""
        super().__init__(parent)
        self._decoder = decoder
        self._renderer = renderer
        self._max_cache = max_cache
        self._images: tuple[Image, ...] = ()
        self._cache: dict[int, PixelArray] = {}
        self._viewport = Viewport.initial()
        self._rendered: RenderedImage | None = None
        self._qimage: QImage | None = None
        self._last_error: str | None = None
        self._drag_mode = _DRAG_NONE
        self._drag_start = QPointF()
        self._drag_viewport: Viewport | None = None
        self._wl_baseline: tuple[float, float] | None = None

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
        self._last_error = None
        self._viewport = Viewport(
            slice_index=clamp_slice(index, len(self._images)),
            fit_mode=FitMode.FIT,
        )
        self._render_current()
        self.update()
        if self.has_image:
            self.content_changed.emit(True)
            self.slice_changed.emit(self._viewport.slice_index, len(self._images))
        else:
            self.content_changed.emit(False)

    def clear(self) -> None:
        """Unload the series and return to the empty state."""
        self._images = ()
        self._cache.clear()
        self._rendered = None
        self._qimage = None
        self._last_error = None
        self._viewport = Viewport.initial()
        self.update()
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
        """Zoom in one step and exit fit mode."""
        self._viewport = self._viewport.with_zoom(self._viewport.zoom * _ZOOM_STEP)
        self.zoom_changed.emit(self._viewport.zoom)
        self.update()

    def zoom_out(self) -> None:
        """Zoom out one step and exit fit mode."""
        self._viewport = self._viewport.with_zoom(self._viewport.zoom / _ZOOM_STEP)
        self.zoom_changed.emit(self._viewport.zoom)
        self.update()

    def fit_to_window(self) -> None:
        """Fit the image to the current widget size."""
        self._viewport = self._viewport.fit()
        self.zoom_changed.emit(1.0)
        self.update()

    def actual_size(self) -> None:
        """Show the image at 100% pixel scale, centered."""
        self._viewport = self._viewport.actual()
        self.zoom_changed.emit(1.0)
        self.update()

    def reset_view(self) -> None:
        """Reset zoom, pan and window/level, keeping the current slice."""
        self._viewport = Viewport(
            slice_index=self._viewport.slice_index,
            fit_mode=FitMode.FIT,
        )
        self._render_current()
        self.zoom_changed.emit(1.0)
        self.window_level_changed.emit(None, 0.0)
        self.update()

    def reset_window_level(self) -> None:
        """Return the window/level to the automatic setting."""
        self._viewport = self._viewport.with_window(None, 0.0)
        self._render_current()
        self.window_level_changed.emit(None, 0.0)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Begin a pan or window/level drag."""
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton and self.has_image:
            self._begin_drag(_DRAG_PAN, event.position())
        elif event.button() == Qt.MouseButton.RightButton and self.has_image:
            self._begin_drag(_DRAG_WINDOW_LEVEL, event.position())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the active pan or window/level drag."""
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
        self._end_drag()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Scroll slices, or zoom when a zoom modifier is held."""
        modifiers = event.modifiers()
        delta = event.angleDelta().y()
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
        """Navigate slices and zoom from the keyboard."""
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
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the rendered frame with the current zoom and pan transform."""
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window().color())
        image = self._qimage
        if image is not None and not image.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(self._target_rect(image), image)
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
            self._viewport = self._viewport.to_free()
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
            self._last_error = str(exc)
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

    def _render_current(self) -> None:
        """Decode and render the current slice, tolerating failures."""
        pixels = self._current_pixels()
        if pixels is None:
            self._rendered = None
            self._qimage = None
            return
        try:
            rendered = self._renderer.render(pixels, self._viewport)
        except RenderingError as exc:
            self._last_error = str(exc)
            return
        self._last_error = None
        self._rendered = rendered
        self._qimage = to_qimage(rendered)

    def _effective_scale(self) -> float:
        """Return the scale factor that maps image pixels to widget pixels."""
        image = self._qimage
        if image is None or image.isNull():
            return 1.0
        if self._viewport.fit_mode == FitMode.FIT:
            width, height = self.width(), self.height()
            if image.width() <= 0 or image.height() <= 0:
                return 1.0
            return min(width / image.width(), height / image.height())
        if self._viewport.fit_mode == FitMode.ACTUAL:
            return 1.0
        return self._viewport.zoom

    def _target_rect(self, image: QImage) -> QRectF:
        """Return the destination rectangle for the rendered frame."""
        scale = self._effective_scale()
        target_width = image.width() * scale
        target_height = image.height() * scale
        center_x = self.width() / 2.0 + self._viewport.pan_x * scale
        center_y = self.height() / 2.0 + self._viewport.pan_y * scale
        return QRectF(
            center_x - target_width / 2.0,
            center_y - target_height / 2.0,
            target_width,
            target_height,
        )

    def _paint_overlay(self, painter: QPainter) -> None:
        """Draw window, slice and zoom information in the corner."""
        painter.save()
        painter.setPen(Qt.GlobalColor.gray)
        info: list[str] = []
        if self._viewport.window_width > 0 and self._viewport.window_center is not None:
            info.append(
                f"W: {self._viewport.window_width:.0f} L: {self._viewport.window_center:.0f}"
            )
        else:
            info.append("W/L: Auto")
        if self.has_image:
            info.append(f"{self._viewport.slice_index + 1} / {len(self._images)}")
        info.append(f"{self._effective_scale() * 100.0:.0f}%")
        painter.drawText(QPointF(12.0, self.height() - 12.0), "   ".join(info))
        painter.restore()

    def _paint_message(self, painter: QPainter, message: str) -> None:
        """Draw a centered diagnostic message."""
        painter.save()
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)
        painter.restore()
