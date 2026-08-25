"""Rendering characterization for completed overlays in the image viewer.

These tests pin the observable output of completed measurement/annotation
painting through the public ``capture_view`` path around the R1.5
relocation into ``viewer_overlays``. Strategy: exact-color pixel probes at
solid-fill features (endpoint/anchor dots are aliased — no antialiasing is
enabled on this painter — so their interiors are exact), plus deterministic
capture-diff checks for blended elements (labels, selection halos) and
visibility gating. Two consecutive captures being byte-identical is asserted
upfront to validate the probe premise in this environment.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage
from tests.dicom_utils import FakeImageAnalyzer, FakePixelDecoder, FakeViewRenderer

from dicomviewer.domain.annotation import Annotation, AnnotationKind
from dicomviewer.domain.measurement import Measurement, MeasurementKind, Point
from dicomviewer.domain.studies import Image
from dicomviewer.domain.viewport import FitMode, Viewport
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget

_MEASUREMENT_COLOR = "#22d3ee"
_ANNOTATION_COLOR = "#a78bfa"


def _series(count: int = 1) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


def _viewer() -> ImageViewerWidget:
    viewer = ImageViewerWidget(
        None,
        FakePixelDecoder(),
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )
    viewer.resize(120, 90)
    viewer.load_series(_series())
    return viewer


def _capture(viewer: ImageViewerWidget) -> QImage:
    rendered = viewer.capture_view()
    image = QImage(
        rendered.data,
        rendered.width,
        rendered.height,
        rendered.stride,
        QImage.Format.Format_ARGB32,
    )
    return image.copy()


def _has_exact_pixel(image: QImage, cx: float, cy: float, hex_color: str, radius: int = 4) -> bool:
    """Return whether any pixel within ``radius`` matches ``hex_color`` exactly."""
    target = QColor(hex_color)
    base_x, base_y = round(cx), round(cy)
    for x in range(base_x - radius, base_x + radius + 1):
        for y in range(base_y - radius, base_y + radius + 1):
            if 0 <= x < image.width() and 0 <= y < image.height():
                found = image.pixelColor(x, y)
                if (
                    found.red() == target.red()
                    and found.green() == target.green()
                    and found.blue() == target.blue()
                ):
                    return True
    return False


def _images_differ(first: QImage, second: QImage) -> bool:
    return bytes(first.bits()) != bytes(second.bits())


def test_capture_is_byte_deterministic(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer._measurements.add(
        0, Measurement(MeasurementKind.DISTANCE, ((Point(1.0, 1.0), Point(6.0, 4.0))))
    )
    assert not _images_differ(_capture(viewer), _capture(viewer))


def test_completed_distance_draws_endpoints_and_label(qapp) -> None:
    del qapp
    viewer = _viewer()
    measurement = Measurement(MeasurementKind.DISTANCE, ((Point(1.0, 1.0), Point(6.0, 4.0))))
    viewer._measurements.add(0, measurement)
    image = _capture(viewer)

    for point in measurement.points:
        widget_point = viewer.image_to_widget(point)
        assert _has_exact_pixel(image, widget_point.x(), widget_point.y(), _MEASUREMENT_COLOR)

    # The label backdrop is a blended element: toggling the measurement
    # overlay must change the capture (the label disappears with it).
    viewer.set_show_measurement_overlay(False)
    assert _images_differ(image, _capture(viewer))


def test_completed_angle_draws_three_handles_and_label(qapp) -> None:
    del qapp
    viewer = _viewer()
    measurement = Measurement(
        MeasurementKind.ANGLE, ((Point(2.0, 2.0), Point(5.0, 2.0), Point(2.0, 5.0)))
    )
    viewer._measurements.add(0, measurement)
    image = _capture(viewer)

    for point in measurement.points:
        widget_point = viewer.image_to_widget(point)
        assert _has_exact_pixel(image, widget_point.x(), widget_point.y(), _MEASUREMENT_COLOR)

    viewer.set_show_measurement_overlay(False)
    assert _images_differ(image, _capture(viewer))


def test_completed_point_arrow_and_text_annotations_render(qapp) -> None:
    del qapp
    viewer = _viewer()
    point_note = Annotation(kind=AnnotationKind.POINT, anchor=Point(4.0, 3.0))
    arrow_note = Annotation(kind=AnnotationKind.ARROW, anchor=Point(1.0, 5.0), tip=Point(5.0, 1.0))
    text_note = Annotation(kind=AnnotationKind.TEXT, anchor=Point(6.0, 5.0), text="lesion")
    for annotation in (point_note, arrow_note, text_note):
        viewer._annotations.add(0, annotation)
    baseline = _capture(viewer)

    for image_point in (point_note.anchor, arrow_note.anchor, arrow_note.tip):
        widget_point = viewer.image_to_widget(image_point)
        assert _has_exact_pixel(baseline, widget_point.x(), widget_point.y(), _ANNOTATION_COLOR)

    # Removing every annotation must change the output (text label, arrow
    # polygon and dots all disappear together).
    viewer._annotations.clear_all()
    assert _images_differ(baseline, _capture(viewer))


def test_selected_annotation_adds_a_halo(qapp) -> None:
    del qapp
    viewer = _viewer()
    annotation = Annotation(kind=AnnotationKind.POINT, anchor=Point(4.0, 3.0))
    viewer._annotations.add(0, annotation)
    unselected = _capture(viewer)

    viewer._annotation_tool.set_selected(annotation)
    selected = _capture(viewer)
    assert _images_differ(unselected, selected)


def test_overlays_follow_zoom_pan_and_orientation(qapp) -> None:
    del qapp
    viewer = _viewer()
    # A long span keeps the endpoint dots clear of the blended label box,
    # which always sits at the segment midpoint.
    measurement = Measurement(MeasurementKind.DISTANCE, ((Point(0.5, 0.5), Point(7.5, 5.5))))
    viewer._measurements.add(0, measurement)

    viewports = (
        Viewport(fit_mode=FitMode.FREE, zoom=6.0, pan_x=-4.0, pan_y=-4.0),
        Viewport(rotation=90),
        Viewport(rotation=180, flip_v=True),
    )
    for viewport in viewports:
        viewer._viewport = viewport
        viewer.update()
        image = _capture(viewer)
        for point in measurement.points:
            widget_point = viewer.image_to_widget(point)
            assert _has_exact_pixel(
                image, widget_point.x(), widget_point.y(), _MEASUREMENT_COLOR
            ), str(viewport)


def test_multiple_overlays_coexist(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer._measurements.add(
        0, Measurement(MeasurementKind.DISTANCE, ((Point(1.0, 1.0), Point(6.0, 4.0))))
    )
    # Anchors placed away from the measurement label band (midpoint of the
    # segment above) so the solid dots stay exact-color probes.
    viewer._annotations.add(0, Annotation(kind=AnnotationKind.POINT, anchor=Point(0.5, 5.5)))
    viewer._annotations.add(
        0, Annotation(kind=AnnotationKind.ARROW, anchor=Point(2.0, 5.0), tip=Point(6.0, 1.0))
    )
    image = _capture(viewer)

    expected = [
        (_MEASUREMENT_COLOR, Point(1.0, 1.0)),
        (_MEASUREMENT_COLOR, Point(6.0, 4.0)),
        (_ANNOTATION_COLOR, Point(0.5, 5.5)),
        (_ANNOTATION_COLOR, Point(2.0, 5.0)),
    ]
    for color, image_point in expected:
        widget_point = viewer.image_to_widget(image_point)
        assert _has_exact_pixel(image, widget_point.x(), widget_point.y(), color)


def test_measurement_visibility_toggle_hides_only_measurements(qapp) -> None:
    del qapp
    viewer = _viewer()
    viewer._measurements.add(
        0, Measurement(MeasurementKind.DISTANCE, ((Point(1.0, 1.0), Point(6.0, 4.0))))
    )
    viewer._annotations.add(0, Annotation(kind=AnnotationKind.POINT, anchor=Point(4.0, 3.0)))
    before = _capture(viewer)

    viewer.set_show_measurement_overlay(False)
    after = _capture(viewer)
    assert _images_differ(before, after)

    # The annotation dot survives the toggle.
    anchor_widget = viewer.image_to_widget(Point(4.0, 3.0))
    assert _has_exact_pixel(after, anchor_widget.x(), anchor_widget.y(), _ANNOTATION_COLOR)
