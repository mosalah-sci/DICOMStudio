"""Tests for the annotation domain model."""

from __future__ import annotations

import pytest

from dicomviewer.domain.annotation import (
    DEFAULT_HIT_TOLERANCE,
    Annotation,
    AnnotationKind,
    annotation_at,
    arrowhead_points,
    distance_to_annotation,
    distance_to_segment,
    required_point_count,
)
from dicomviewer.domain.measurement import Point


def test_point_annotation_holds_anchor_only() -> None:
    annotation = Annotation(kind=AnnotationKind.POINT, anchor=Point(1, 2))
    assert annotation.tip is None
    assert required_point_count(AnnotationKind.POINT) == 1


def test_arrow_annotation_requires_tip() -> None:
    annotation = Annotation(kind=AnnotationKind.ARROW, anchor=Point(0, 0), tip=Point(10, 10))
    assert annotation.tip == Point(10, 10)
    with pytest.raises(ValueError):
        Annotation(kind=AnnotationKind.ARROW, anchor=Point(0, 0))


def test_text_annotation_requires_text_and_rejects_tip() -> None:
    annotation = Annotation(kind=AnnotationKind.TEXT, anchor=Point(3, 4), text="Lesion")
    assert annotation.text == "Lesion"
    with pytest.raises(ValueError):
        Annotation(kind=AnnotationKind.TEXT, anchor=Point(3, 4), text="   ")
    with pytest.raises(ValueError):
        Annotation(
            kind=AnnotationKind.TEXT, anchor=Point(3, 4), text="x", tip=Point(1, 1)  # type: ignore[arg-type]
        )


def test_point_annotation_rejects_payload_mismatches() -> None:
    with pytest.raises(ValueError):
        Annotation(kind=AnnotationKind.POINT, anchor=Point(0, 0), tip=Point(1, 1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Annotation(kind=AnnotationKind.POINT, anchor=Point(0, 0), text="nope")
    with pytest.raises(ValueError):
        Annotation(kind="lesion", anchor=Point(0, 0))  # type: ignore[arg-type]


def test_required_point_count_covers_all_kinds() -> None:
    assert required_point_count(AnnotationKind.POINT) == 1
    assert required_point_count(AnnotationKind.ARROW) == 2
    assert required_point_count(AnnotationKind.TEXT) == 1


def test_distance_to_segment_handles_parallel_and_degenerate() -> None:
    start, end = Point(0, 0), Point(10, 0)
    assert distance_to_segment(Point(5, 3), start, end) == pytest.approx(3.0)
    assert distance_to_segment(Point(-4, 0), start, end) == pytest.approx(4.0)
    assert distance_to_segment(Point(12, 4), start, end) == pytest.approx(4.4721359)
    assert distance_to_segment(Point(3, 4), Point(2, 1), Point(2, 1)) == pytest.approx(10**0.5)


def test_distance_to_annotation_matches_arrow_shaft_and_ends() -> None:
    arrow = Annotation(kind=AnnotationKind.ARROW, anchor=Point(0, 0), tip=Point(100, 0))
    assert distance_to_annotation(arrow, Point(50, 7)) == pytest.approx(7.0)
    assert distance_to_annotation(arrow, Point(105, 0)) == pytest.approx(5.0)


def test_distance_to_annotation_for_point_and_text_is_anchor_distance() -> None:
    point = Annotation(kind=AnnotationKind.POINT, anchor=Point(10, 10))
    text = Annotation(kind=AnnotationKind.TEXT, anchor=Point(0, 0), text="hi")
    assert distance_to_annotation(point, Point(13, 14)) == pytest.approx(5.0)
    assert distance_to_annotation(text, Point(3, 4)) == pytest.approx(5.0)


def test_annotation_at_prefers_topmost_within_tolerance() -> None:
    near = Annotation(kind=AnnotationKind.POINT, anchor=Point(10, 10))
    far = Annotation(kind=AnnotationKind.POINT, anchor=Point(12, 10))
    annotations = [near, far]
    hit = annotation_at(annotations, Point(11.5, 10), tolerance=1.0)
    assert hit is far
    assert annotation_at(annotations, Point(200, 200), tolerance=DEFAULT_HIT_TOLERANCE) is None
    assert annotation_at(annotations, Point(10, 12.5), tolerance=2.6) is near


def test_arrowhead_points_are_behind_the_tip() -> None:
    anchor, tip = Point(0, 0), Point(10, 0)
    left, right = arrowhead_points(anchor, tip, head_length=3.0)
    assert left.x < tip.x and right.x < tip.x
    assert left.y == pytest.approx(-right.y)
    assert abs(left.y) > 0
