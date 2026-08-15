"""Tests for the interactive image viewer widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.application.viewing import UnsupportedPixelFormatError
from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.domain.measurement import MeasurementKind
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import FitMode
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _series(count: int = 3) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _viewer(
    decoder: FakePixelDecoder | None = None,
    renderer: FakeViewRenderer | None = None,
    analyzer: FakeImageAnalyzer | None = None,
    max_cache: int = 3,
) -> ImageViewerWidget:
    return ImageViewerWidget(
        None,
        decoder or FakePixelDecoder(),
        renderer or FakeViewRenderer(),
        analyzer=analyzer or FakeImageAnalyzer(),
        max_cache=max_cache,
    )


def _wheel(
    widget: ImageViewerWidget,
    qapp,
    delta: int,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qapp.sendEvent(widget, event)


def test_viewer_starts_empty(qapp) -> None:
    viewer = _viewer()
    assert not viewer.has_image
    assert viewer._qimage is None


def test_load_series_renders_first_slice(qapp) -> None:
    viewer = _viewer()
    changes: list[bool] = []
    slices: list[tuple[int, int]] = []
    viewer.content_changed.connect(changes.append)
    viewer.slice_changed.connect(lambda i, n: slices.append((i, n)))
    viewer.load_series(_series())
    assert viewer.has_image
    assert viewer.current_slice == 0
    assert viewer.slice_count == 3
    assert viewer._qimage is not None
    assert not viewer._qimage.isNull()
    assert changes == [True]
    assert slices == [(0, 3)]


def test_load_series_supports_start_index(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series(), index=2)
    assert viewer.current_slice == 2


def test_slice_navigation_and_clamping(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.next_slice()
    assert viewer.current_slice == 1
    viewer.next_slice()
    viewer.next_slice()
    assert viewer.current_slice == 2
    viewer.previous_slice()
    assert viewer.current_slice == 1
    viewer.set_slice(10)
    assert viewer.current_slice == 2


def test_slice_changed_signal_emits(qapp) -> None:
    viewer = _viewer()
    slices: list[tuple[int, int]] = []
    viewer.slice_changed.connect(lambda i, n: slices.append((i, n)))
    viewer.load_series(_series())
    viewer.set_slice(2)
    assert slices == [(0, 3), (2, 3)]


def test_zoom_in_and_out_change_viewport(qapp) -> None:
    viewer = _viewer()
    viewer.resize(8, 6)
    viewer.load_series(_series())
    zooms: list[float] = []
    viewer.zoom_changed.connect(zooms.append)
    viewer.zoom_in()
    assert viewer.viewport.fit_mode == FitMode.FREE
    assert viewer.viewport.zoom == 1.25
    viewer.zoom_out()
    assert viewer.viewport.zoom == 1.0
    assert zooms == [1.25, 1.0]


def test_zoom_in_steps_from_the_fit_scale(qapp) -> None:
    viewer = _viewer()
    viewer.resize(80, 60)
    viewer.load_series(_series())
    viewer.zoom_in()
    assert viewer.viewport.fit_mode == FitMode.FREE
    assert viewer.viewport.zoom == 12.5


def test_zoom_is_clamped(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    for _ in range(200):
        viewer.zoom_in()
    assert viewer.viewport.zoom <= 32.0


def test_fit_and_actual_size_set_modes(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.zoom_in()
    viewer.fit_to_window()
    assert viewer.viewport.fit_mode == FitMode.FIT
    viewer.zoom_in()
    viewer.actual_size()
    assert viewer.viewport.fit_mode == FitMode.ACTUAL
    assert viewer.viewport.zoom == 1.0


def test_reset_view_keeps_slice(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.set_slice(1)
    viewer.zoom_in()
    viewer.reset_view()
    assert viewer.viewport.fit_mode == FitMode.FIT
    assert viewer.viewport.zoom == 1.0
    assert viewer.viewport.window_width == 0.0
    assert viewer.current_slice == 1


def test_reset_window_level_restores_auto(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer._viewport = viewer.viewport.with_window(40.0, 400.0)
    viewer.reset_window_level()
    assert viewer.viewport.window_width == 0.0
    assert viewer.viewport.window_center is None


def test_left_drag_pans_the_image(qapp) -> None:
    viewer = _viewer()
    viewer.resize(80, 60)
    viewer.load_series(_series())
    QTest.mousePress(viewer, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    QTest.mouseMove(viewer, QPoint(30, 20))
    QTest.mouseRelease(viewer, Qt.MouseButton.LeftButton, pos=QPoint(30, 20))
    assert viewer.viewport.fit_mode == FitMode.FREE
    # Panning keeps the fit scale, so a 20x10 px drag moves the image by
    # 20/10 x 10/10 image pixels (scale 10 for an 8x6 image in an 80x60 view).
    assert viewer.viewport.pan_x == 2.0
    assert viewer.viewport.pan_y == 1.0


def test_pan_from_fit_keeps_the_displayed_scale(qapp) -> None:
    viewer = _viewer()
    viewer.resize(80, 60)
    viewer.load_series(_series())
    assert viewer.viewport.fit_mode == FitMode.FIT
    QTest.mousePress(viewer, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    QTest.mouseMove(viewer, QPoint(30, 20))
    QTest.mouseRelease(viewer, Qt.MouseButton.LeftButton, pos=QPoint(30, 20))
    assert viewer.viewport.fit_mode == FitMode.FREE
    assert viewer.viewport.zoom == 10.0


def test_right_drag_adjusts_window_level(qapp) -> None:
    viewer = _viewer()
    viewer.resize(400, 300)
    viewer.load_series(_series())
    windows: list[tuple[object, float]] = []
    viewer.window_level_changed.connect(lambda c, w: windows.append((c, w)))
    QTest.mousePress(viewer, Qt.MouseButton.RightButton, pos=QPoint(10, 10))
    QTest.mouseMove(viewer, QPoint(30, 20))
    QTest.mouseRelease(viewer, Qt.MouseButton.RightButton, pos=QPoint(30, 20))
    assert viewer.viewport.window_center == 60.0
    assert viewer.viewport.window_width == 105.0
    assert windows and windows[-1] == (60.0, 105.0)


def test_wheel_scrolls_slices(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.set_slice(1)
    _wheel(viewer, qapp, 120)
    assert viewer.current_slice == 0
    _wheel(viewer, qapp, -120)
    assert viewer.current_slice == 1


def test_control_wheel_zooms(qapp) -> None:
    viewer = _viewer()
    viewer.resize(8, 6)
    viewer.load_series(_series())
    _wheel(viewer, qapp, 120, Qt.KeyboardModifier.ControlModifier)
    assert viewer.viewport.zoom == 1.25


def test_arrow_keys_navigate_slices(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    QTest.keyClick(viewer, Qt.Key.Key_Down)
    assert viewer.current_slice == 1
    QTest.keyClick(viewer, Qt.Key.Key_Up)
    assert viewer.current_slice == 0
    QTest.keyClick(viewer, Qt.Key.Key_End)
    assert viewer.current_slice == 2
    QTest.keyClick(viewer, Qt.Key.Key_Home)
    assert viewer.current_slice == 0


def test_plus_and_minus_keys_zoom(qapp) -> None:
    viewer = _viewer()
    viewer.resize(8, 6)
    viewer.load_series(_series())
    QTest.keyClick(viewer, Qt.Key.Key_Plus)
    assert viewer.viewport.zoom == 1.25
    QTest.keyClick(viewer, Qt.Key.Key_Minus)
    assert viewer.viewport.zoom == 1.0


def test_f_key_fits_to_window(qapp) -> None:
    viewer = _viewer()
    viewer.resize(8, 6)
    viewer.load_series(_series())
    viewer.zoom_in()
    assert viewer.viewport.fit_mode is not FitMode.FIT
    QTest.keyClick(viewer, Qt.Key.Key_F)
    assert viewer.viewport.fit_mode is FitMode.FIT


def test_r_key_resets_the_view(qapp) -> None:
    viewer = _viewer()
    viewer.resize(8, 6)
    viewer.load_series(_series())
    viewer.zoom_in()
    viewer.reset_window_level()
    QTest.keyClick(viewer, Qt.Key.Key_R)
    assert viewer.viewport.fit_mode is FitMode.FIT
    assert viewer.viewport.window_width == 0.0


def test_w_key_resets_window_level(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.set_window(40.0, 400.0)
    QTest.keyClick(viewer, Qt.Key.Key_W)
    assert viewer.viewport.window_center is None
    assert viewer.viewport.window_width == 0.0


def test_m_key_toggles_measure_mode(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    assert viewer.measure_mode is None
    QTest.keyClick(viewer, Qt.Key.Key_M)
    assert viewer.measure_mode is MeasurementKind.DISTANCE
    QTest.keyClick(viewer, Qt.Key.Key_M)
    assert viewer.measure_mode is None


def test_escape_without_a_tool_emits_escape_pressed(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    escapes: list[bool] = []
    viewer.escape_pressed.connect(lambda: escapes.append(True))
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert escapes == [True]


def test_escape_with_a_tool_exits_the_tool_without_fullscreen(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    escapes: list[bool] = []
    viewer.escape_pressed.connect(lambda: escapes.append(True))
    viewer.set_measure_mode(MeasurementKind.DISTANCE)
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer.measure_mode is None
    assert escapes == []


def test_decode_failure_shows_a_friendly_error_without_crashing(qapp) -> None:
    decoder = FakePixelDecoder(error=UnsupportedPixelFormatError("unsupported pixels"))
    viewer = _viewer(decoder=decoder)
    viewer.load_series(_series())
    assert viewer.has_image
    assert viewer._qimage is None
    assert viewer._last_error == "This image could not be decoded."


def test_decode_cache_stays_bounded(qapp) -> None:
    viewer = _viewer(max_cache=3)
    viewer.load_series(_series(count=5))
    for index in range(5):
        viewer.set_slice(index)
    assert len(viewer._cache) <= 3
    assert viewer.current_slice in viewer._cache


def test_empty_series_shows_empty(qapp) -> None:
    viewer = _viewer()
    changes: list[bool] = []
    viewer.content_changed.connect(changes.append)
    viewer.load_series(())
    assert not viewer.has_image
    assert changes == [False]


def test_set_window_applies_and_emits(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    windows: list[tuple[object, float]] = []
    viewer.window_level_changed.connect(lambda c, w: windows.append((c, w)))
    viewer.set_window(40.0, 400.0)
    assert viewer.viewport.window_center == 40.0
    assert viewer.viewport.window_width == 400.0
    assert windows[-1] == (40.0, 400.0)


def test_apply_preset_sets_the_window(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.apply_preset(WindowPreset("CT Lung", -500.0, 1500.0))
    assert viewer.viewport.window_center == -500.0
    assert viewer.viewport.window_width == 1500.0


def test_set_window_with_auto_width_resets(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(_series())
    viewer.set_window(40.0, 400.0)
    viewer.set_window(40.0, 0.0)
    assert viewer.viewport.window_center is None
    assert viewer.viewport.window_width == 0.0


def test_statistics_are_available_after_loading(qapp) -> None:
    analyzer = FakeImageAnalyzer()
    viewer = _viewer(analyzer=analyzer)
    viewer.load_series(_series())
    assert viewer.statistics is not None
    assert viewer.statistics.mean == 127.5
    assert analyzer.statistics_calls
    assert viewer.histogram is not None
    assert viewer.histogram.bin_count == 2
    assert analyzer.histogram_calls
    assert analyzer.histogram_calls[0][1] == 128


def test_analysis_is_cached_per_slice(qapp) -> None:
    analyzer = FakeImageAnalyzer()
    viewer = _viewer(analyzer=analyzer)
    viewer.load_series(_series(count=2))
    assert viewer.statistics is not None
    assert viewer.statistics is not None
    assert len(analyzer.statistics_calls) == 1
    viewer.set_slice(1)
    assert viewer.statistics is not None
    assert len(analyzer.statistics_calls) == 2


def test_no_analysis_without_pixels(qapp) -> None:
    viewer = _viewer()
    viewer.load_series(())
    assert viewer.statistics is None
    assert viewer.histogram is None


def test_render_cache_reuses_frames_for_same_window(qapp) -> None:
    renderer = FakeViewRenderer()
    viewer = _viewer(renderer=renderer)
    viewer.load_series(_series())
    assert len(renderer.calls) == 1
    viewer.set_slice(1)
    assert len(renderer.calls) == 2
    viewer.set_slice(0)
    assert len(renderer.calls) == 2


def test_render_cache_is_bounded(qapp) -> None:
    renderer = FakeViewRenderer()
    viewer = _viewer(renderer=renderer, max_cache=3)
    viewer.load_series(_series(count=5))
    for index in range(5):
        viewer.set_slice(index)
    assert len(viewer._frame_cache) <= 3


def test_frame_cache_evicts_old_window_level_entries(qapp) -> None:
    viewer = _viewer(max_cache=3)
    viewer.load_series(_series(count=2))
    for center, width in ((40.0, 400.0), (80.0, 200.0), (120.0, 100.0), (160.0, 50.0)):
        viewer.set_window(center, width)
    assert len(viewer._frame_cache) <= 3


def test_preference_setters_update_viewer_state(qapp) -> None:
    viewer = _viewer()
    assert viewer._smooth_scaling is True
    assert viewer._show_statistics_overlay is True
    assert viewer._show_measurement_overlay is True
    assert viewer._measurement_color == "#22d3ee"

    viewer.set_smooth_scaling(False)
    viewer.set_show_statistics_overlay(False)
    viewer.set_show_measurement_overlay(False)
    viewer.set_measurement_color("#ff0000")
    assert viewer._smooth_scaling is False
    assert viewer._show_statistics_overlay is False
    assert viewer._show_measurement_overlay is False
    assert viewer._measurement_color == "#ff0000"


def test_set_max_cache_evicts_older_slices(qapp) -> None:
    viewer = _viewer(max_cache=3)
    viewer.load_series(_series(count=5))
    for index in range(5):
        viewer.set_slice(index)
    assert len(viewer._cache) <= 3
    viewer.set_max_cache(1)
    assert len(viewer._cache) == 1
    assert viewer.current_slice in viewer._cache


def test_overlay_toggles_survive_constructor(qapp) -> None:
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
        smooth_scaling=False,
        show_statistics_overlay=False,
        show_measurement_overlay=False,
    )
    assert viewer._smooth_scaling is False
    assert viewer._show_statistics_overlay is False
    assert viewer._show_measurement_overlay is False
