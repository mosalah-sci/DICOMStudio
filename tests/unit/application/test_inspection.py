"""Tests for the tag inspection search use case."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.application.inspection import filter_tags
from dicomviewer.domain.tags import TagDocument, TagEntry

_ENTRIES = (
    TagEntry("(0010,0010)", "PatientName", "Patient's Name", "PN", "DOE^JOHN"),
    TagEntry("(0008,0008)", "ImageType", "Image Type", "CS", "ORIGINAL\\PRIMARY"),
    TagEntry("(0009,0010)", "", "Private tag", "LO", "acme-secret"),
)

_DOCUMENT = TagDocument(Path("a.dcm"), _ENTRIES)


def test_blank_query_returns_the_document_unchanged() -> None:
    result = filter_tags(_DOCUMENT, "   ")
    assert result is _DOCUMENT


def test_matching_is_case_insensitive_over_tag_and_keyword() -> None:
    result = filter_tags(_DOCUMENT, "patientname")
    assert result.entry_count == 1
    assert result.entries[0].tag == "(0010,0010)"


def test_matching_covers_name_value_and_vr() -> None:
    assert filter_tags(_DOCUMENT, "DOE^JOHN").entry_count == 1
    assert filter_tags(_DOCUMENT, "private").entry_count == 1
    assert filter_tags(_DOCUMENT, "acme").entry_count == 1
    assert filter_tags(_DOCUMENT, "PN").entry_count == 1


def test_no_match_yields_an_empty_document() -> None:
    result = filter_tags(_DOCUMENT, "nonexistent")
    assert result.entry_count == 0
    assert not result.has_content()
    assert result.source == Path("a.dcm")
