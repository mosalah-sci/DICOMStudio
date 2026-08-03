"""Tests for the domain study catalog model."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree


def _sample_tree() -> StudyTree:
    images_a = (Image(Path("a1.dcm"), 1), Image(Path("a2.dcm"), 2))
    images_b = (Image(Path("b1.dcm"), 1),)
    series_ct = Series("s-ct", "CT", 1, "Chest", images_a)
    series_us = Series("s-us", "US", 2, "Abdomen", images_b)
    study = Study("st-1", "20260801", "1", "Chest exam", (series_ct, series_us))
    patient = Patient("p-1", "DOE^JOHN", "19800101", "M", (study,))
    return StudyTree(Path("."), (patient,))


def test_study_tree_counts() -> None:
    tree = _sample_tree()
    assert tree.has_content()
    assert tree.patient_count == 1
    assert tree.study_count == 1
    assert tree.series_count == 2
    assert tree.image_count == 3


def test_study_tree_counts_aggregate() -> None:
    series = Series("s", "CT", 1, "", (Image(Path("x"), 1), Image(Path("y"), 2)))
    study = Study("st", "20260101", "1", "", (series,))
    tree = StudyTree(Path("."), (Patient("p", "A^B", "", "", (study,)),))
    assert study.series_count == 1
    assert study.image_count == 2
    assert tree.image_count == 2


def test_empty_tree_has_no_content() -> None:
    tree = StudyTree.empty(Path("."))
    assert not tree.has_content()
    assert tree.patient_count == 0
    assert tree.study_count == 0
    assert tree.series_count == 0
    assert tree.image_count == 0
