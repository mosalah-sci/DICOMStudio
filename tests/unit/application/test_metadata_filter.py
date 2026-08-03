"""Tests for the metadata search/filter use case."""

from __future__ import annotations

from pathlib import Path

from tests.dicom_utils import sample_metadata_document

from dicomviewer.application.metadata import filter_metadata


def test_blank_query_returns_the_document_unchanged() -> None:
    document = sample_metadata_document()
    assert filter_metadata(document, "   ") is document
    assert filter_metadata(document, "") is document


def test_query_matches_a_value_case_insensitively() -> None:
    document = sample_metadata_document(patient_name="DOE^JOHN")
    filtered = filter_metadata(document, "doe")
    assert filtered.has_content()
    assert filtered.element_count == 1
    assert filtered.groups[0].name == "Patient"


def test_query_matches_a_keyword() -> None:
    document = sample_metadata_document()
    filtered = filter_metadata(document, "patientid")
    assert filtered.element_count == 1
    assert filtered.groups[0].elements[0].keyword == "PatientID"


def test_query_matches_a_group_name() -> None:
    document = sample_metadata_document()
    filtered = filter_metadata(document, "study")
    assert filtered.has_content()
    assert any(group.name == "Study" for group in filtered.groups)


def test_query_matches_a_tag() -> None:
    document = sample_metadata_document()
    filtered = filter_metadata(document, "(0010,0020)")
    assert filtered.element_count == 1
    assert filtered.groups[0].elements[0].tag == "(0010,0020)"


def test_groups_without_matches_are_dropped() -> None:
    document = sample_metadata_document()
    filtered = filter_metadata(document, "P-1")
    assert filtered.has_content()
    assert [group.name for group in filtered.groups] == ["Patient"]


def test_query_without_matches_has_no_content() -> None:
    document = sample_metadata_document()
    filtered = filter_metadata(document, "nonexistent")
    assert not filtered.has_content()
    assert filtered.element_count == 0


def test_filtered_document_keeps_the_source() -> None:
    document = sample_metadata_document(source=Path("scan.dcm"))
    filtered = filter_metadata(document, "ct")
    assert filtered.source == Path("scan.dcm")
