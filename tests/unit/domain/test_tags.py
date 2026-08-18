"""Tests for the tag inspection domain model."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.domain.tags import TagDocument, TagEntry


def test_entry_identifier_combines_tag_and_keyword() -> None:
    entry = TagEntry("(0010,0010)", "PatientName", "Patient's Name", "PN", "DOE^JOHN")
    assert entry.identifier == "(0010,0010) PatientName"


def test_entry_identifier_without_keyword_drops_the_blank() -> None:
    entry = TagEntry("(0009,0010)", "", "Private tag", "LO", "value", is_private=True)
    assert entry.identifier == "(0009,0010)"


def test_document_counts_and_content_flag() -> None:
    entry = TagEntry("(0010,0010)", "PatientName", "Patient's Name", "PN", "DOE^JOHN")
    document = TagDocument(Path("a.dcm"), (entry,))
    assert document.entry_count == 1
    assert document.has_content()


def test_empty_document_has_no_content() -> None:
    document = TagDocument(Path("a.dcm"))
    assert document.entry_count == 0
    assert not document.has_content()
