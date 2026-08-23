"""Tests for the annotation application state."""

from __future__ import annotations

from dicomviewer.application.annotation import AnnotationCollection
from dicomviewer.domain.annotation import Annotation, AnnotationKind
from dicomviewer.domain.measurement import Point


def _point(x: float, y: float) -> Annotation:
    return Annotation(kind=AnnotationKind.POINT, anchor=Point(x, y))


def test_collection_stores_annotations_per_slice() -> None:
    collection = AnnotationCollection()
    annotation = _point(1, 2)
    collection.add(0, annotation)
    collection.add(2, _point(3, 4))
    assert collection.for_slice(0) == [annotation]
    assert len(collection.for_slice(2)) == 1
    assert collection.for_slice(1) == []
    assert collection.has_any()


def test_collection_remove_exact_annotation() -> None:
    collection = AnnotationCollection()
    annotation = _point(5, 5)
    collection.add(0, annotation)
    assert collection.remove(0, annotation) is True
    assert collection.for_slice(0) == []
    assert collection.remove(0, annotation) is False
    assert not collection.has_any()


def test_collection_clear_slice_and_clear_all() -> None:
    collection = AnnotationCollection()
    collection.add(0, _point(1, 1))
    collection.add(1, _point(2, 2))
    collection.clear(0)
    assert collection.for_slice(0) == []
    assert collection.has_any()
    collection.clear_all()
    assert not collection.has_any()


def test_annotation_at_finds_topmost_within_tolerance() -> None:
    collection = AnnotationCollection()
    near = _point(10, 10)
    top = _point(11.5, 10)
    collection.add(0, near)
    collection.add(0, top)
    assert collection.annotation_at(0, Point(11.8, 10), tolerance=1.0) is top
    assert collection.annotation_at(0, Point(10, 11), tolerance=1.0) is near
    assert collection.annotation_at(0, Point(500, 500)) is None
    assert collection.annotation_at(7, Point(11.5, 10)) is None
