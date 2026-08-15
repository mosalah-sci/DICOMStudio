"""Central image viewer area, composed of an empty state and the viewer."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from dicomviewer.application.measurement import MeasurementCollection
from dicomviewer.application.processing import Histogram, ImageAnalyzer, PixelStatistics
from dicomviewer.application.viewing import PixelDecoder, RenderedImage, ViewRenderer
from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.domain.measurement import Measurement, MeasurementKind
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.widgets.empty_state import EmptyState
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget

_PAGE_EMPTY = 0
_PAGE_VIEWER = 1


class ViewerPanel(QWidget):
    """Hosts the interactive viewer and its empty state."""

    content_changed = Signal(bool)
    slice_changed = Signal(int, int)
    zoom_changed = Signal(float)
    window_level_changed = Signal(object, float)
    measurements_changed = Signal(object)
    measure_mode_changed = Signal(object)
    open_folder_requested = Signal()
    escape_pressed = Signal()

    def __init__(
        self,
        parent: QWidget,
        icon_provider: IconProvider,
        *,
        decoder: PixelDecoder,
        renderer: ViewRenderer,
        analyzer: ImageAnalyzer,
    ) -> None:
        """Build the viewer area with the given rendering services."""
        super().__init__(parent)
        self.setObjectName("viewerPanel")
        self._viewer = ImageViewerWidget(self, decoder, renderer, analyzer=analyzer)
        self._viewer.content_changed.connect(self.content_changed)
        self._viewer.slice_changed.connect(self.slice_changed)
        self._viewer.zoom_changed.connect(self.zoom_changed)
        self._viewer.window_level_changed.connect(self.window_level_changed)
        self._viewer.measurements_changed.connect(self.measurements_changed)
        self._viewer.measure_mode_changed.connect(self.measure_mode_changed)
        self._viewer.escape_pressed.connect(self.escape_pressed)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(
            EmptyState(
                self,
                icon_provider,
                icon_name="activity",
                title="Welcome to DICOMStudio",
                description=(
                    "Open a folder of DICOM studies to begin, or drag and drop "
                    "a DICOM file or folder anywhere in this window."
                ),
                action_text="Open Folder...",
                on_action=self.open_folder_requested.emit,
            )
        )
        self._stack.addWidget(self._viewer)
        self._stack.setCurrentIndex(_PAGE_EMPTY)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def load_series(self, images: Sequence[Image], index: int = 0) -> None:
        """Load ``images`` into the viewer and switch to it."""
        self._viewer.load_series(images, index)
        self._stack.setCurrentIndex(_PAGE_VIEWER)

    def show_empty(self) -> None:
        """Return to the empty state and unload any series."""
        self._viewer.clear()
        self._stack.setCurrentIndex(_PAGE_EMPTY)

    @property
    def has_image(self) -> bool:
        """Return whether a series is currently displayed."""
        return self._viewer.has_image

    def zoom_in(self) -> None:
        """Zoom the viewer in one step."""
        self._viewer.zoom_in()

    def zoom_out(self) -> None:
        """Zoom the viewer out one step."""
        self._viewer.zoom_out()

    def fit_to_window(self) -> None:
        """Fit the image to the viewer window."""
        self._viewer.fit_to_window()

    def actual_size(self) -> None:
        """Show the image at 100% pixel scale."""
        self._viewer.actual_size()

    def reset_view(self) -> None:
        """Reset zoom, pan and window/level."""
        self._viewer.reset_view()

    def reset_window_level(self) -> None:
        """Reset the window/level to automatic."""
        self._viewer.reset_window_level()

    def set_window(self, center: float, width: float) -> None:
        """Apply an explicit window (center, width)."""
        self._viewer.set_window(center, width)

    def apply_preset(self, preset: WindowPreset) -> None:
        """Apply a named clinical window preset."""
        self._viewer.apply_preset(preset)

    @property
    def statistics(self) -> PixelStatistics | None:
        """Return the statistics of the displayed slice, if known."""
        return self._viewer.statistics

    @property
    def histogram(self) -> Histogram | None:
        """Return the histogram of the displayed slice, if known."""
        return self._viewer.histogram

    def next_slice(self) -> None:
        """Advance to the next slice."""
        self._viewer.next_slice()

    def previous_slice(self) -> None:
        """Move to the previous slice."""
        self._viewer.previous_slice()

    def set_slice(self, index: int) -> None:
        """Display the slice at ``index``."""
        self._viewer.set_slice(index)

    @property
    def current_slice(self) -> int:
        """Return the displayed slice index."""
        return self._viewer.current_slice

    @property
    def slice_count(self) -> int:
        """Return the number of slices in the loaded series."""
        return self._viewer.slice_count

    @property
    def measurements(self) -> MeasurementCollection:
        """Return the viewer's measurement collection."""
        return self._viewer.measurements

    @property
    def measure_mode(self) -> MeasurementKind | None:
        """Return the active measurement tool, or ``None``."""
        return self._viewer.measure_mode

    def set_measure_mode(self, kind: MeasurementKind | None) -> None:
        """Activate or deactivate the measurement tool."""
        self._viewer.set_measure_mode(kind)

    def remove_measurement(self, measurement: Measurement) -> None:
        """Remove a single measurement from the current slice."""
        self._viewer.remove_measurement(measurement)

    def clear_measurements(self) -> None:
        """Remove every measurement from every slice."""
        self._viewer.clear_measurements()

    def set_max_cache(self, size: int) -> None:
        """Set the viewer's decode cache size."""
        self._viewer.set_max_cache(size)

    def set_smooth_scaling(self, enabled: bool) -> None:
        """Enable or disable smooth image scaling in the viewer."""
        self._viewer.set_smooth_scaling(enabled)

    def set_show_statistics_overlay(self, enabled: bool) -> None:
        """Show or hide the statistics and histogram overlay."""
        self._viewer.set_show_statistics_overlay(enabled)

    def set_show_measurement_overlay(self, enabled: bool) -> None:
        """Show or hide the measurement overlay."""
        self._viewer.set_show_measurement_overlay(enabled)

    def set_measurement_color(self, color: str) -> None:
        """Set the colour used for measurement overlays."""
        self._viewer.set_measurement_color(color)

    def capture_view(self) -> RenderedImage:
        """Return the current viewport (frame plus overlays) as RGBA bytes."""
        return self._viewer.capture_view()
