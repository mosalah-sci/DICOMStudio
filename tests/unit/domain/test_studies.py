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


def test_find_series_context_returns_owning_patient_and_study() -> None:
    tree = _sample_tree()
    context = tree.find_series_context("s-us")
    assert context is not None
    patient, study = context
    assert (patient.patient_id, study.study_instance_uid) == ("p-1", "st-1")


def test_find_series_context_returns_none_for_unknown_uid() -> None:
    tree = _sample_tree()
    assert tree.find_series_context("s-missing") is None


def test_find_series_context_returns_none_on_empty_tree() -> None:
    tree = StudyTree.empty(Path("."))
    assert tree.find_series_context("s-ct") is None


def test_find_series_context_resolves_across_patients_and_studies() -> None:
    series_p1_s1 = Series("s-p1-s1", "CT", 1, "", ())
    series_p1_s2 = Series("s-p1-s2", "MR", 2, "", ())
    study_p1_1 = Study("st-p1-1", "20260101", "1", "First", (series_p1_s1,))
    study_p1_2 = Study("st-p1-2", "20260202", "2", "Second", (series_p1_s2,))
    patient_p1 = Patient("p-1", "A^ONE", "19800101", "F", (study_p1_1, study_p1_2))
    series_p2 = Series("s-p2", "PT", 1, "", ())
    study_p2 = Study("st-p2-1", "20260303", "3", "Other", (series_p2,))
    patient_p2 = Patient("p-2", "B^TWO", "19900202", "M", (study_p2,))
    tree = StudyTree(Path("."), (patient_p1, patient_p2))

    context = tree.find_series_context("s-p2")
    assert context == (patient_p2, study_p2)

    context = tree.find_series_context("s-p1-s2")
    assert context == (patient_p1, study_p1_2)

    context = tree.find_series_context("s-p1-s1")
    assert context == (patient_p1, study_p1_1)
