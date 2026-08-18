"""Tests for the DICOM dataset inspector dialog."""

from __future__ import annotations

from pathlib import Path

from tests.dicom_utils import FakeTagInspector

from dicomviewer.application.inspection import InspectionError
from dicomviewer.domain.tags import TagDocument, TagEntry
from dicomviewer.presentation.dialogs.tag_inspector_dialog import TagInspectorDialog

_ENTRIES = (
    TagEntry("(0010,0010)", "PatientName", "Patient's Name", "PN", "DOE^JOHN"),
    TagEntry("(0008,0008)", "ImageType", "Image Type", "CS", "ORIGINAL\\PRIMARY"),
    TagEntry("(0009,0010)", "", "Private tag", "LO", "acme-secret"),
)

_DOCUMENT = TagDocument(Path("a.dcm"), _ENTRIES)


def _dialog(icon_provider, document=_DOCUMENT) -> tuple[TagInspectorDialog, FakeTagInspector]:
    inspector = FakeTagInspector(document=document)
    dialog = TagInspectorDialog(None, Path("a.dcm"), inspector)
    return dialog, inspector


def test_dialog_populates_a_row_per_entry(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    assert dialog._table.rowCount() == 3
    assert dialog._source_label.text() == "a.dcm"
    assert dialog._summary_label.text() == "3 of 3 elements"


def test_rows_show_tag_keyword_name_vr_and_value(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    row = next(
        i
        for i in range(dialog._table.rowCount())
        if dialog._table.item(i, 0).text() == "(0010,0010)"
    )
    assert dialog._table.item(row, 1).text() == "PatientName"
    assert dialog._table.item(row, 2).text() == "Patient's Name"
    assert dialog._table.item(row, 3).text() == "PN"
    assert dialog._table.item(row, 4).text() == "DOE^JOHN"


def test_search_filters_the_rows_and_updates_the_summary(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    dialog._search.setText("acme")
    assert dialog._table.rowCount() == 1
    assert dialog._table.item(0, 0).text() == "(0009,0010)"
    assert dialog._summary_label.text() == "1 of 3 elements"


def test_blank_search_restores_all_rows(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    dialog._search.setText("acme")
    dialog._search.setText("")
    assert dialog._table.rowCount() == 3


def test_no_matching_rows_shows_a_no_matches_summary(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    dialog._search.setText("nonexistent")
    assert dialog._table.rowCount() == 0
    assert dialog._summary_label.text() == "No matching elements"


def test_inspection_failure_leaves_the_dialog_empty_but_usable(qapp, icon_provider) -> None:
    inspector = FakeTagInspector(error=InspectionError("boom"))
    dialog = TagInspectorDialog(None, Path("a.dcm"), inspector)
    assert dialog._table.rowCount() == 0
    assert dialog._summary_label.text() == ""


def test_dialog_exposes_the_inspected_path(qapp, icon_provider) -> None:
    dialog, _ = _dialog(icon_provider)
    assert dialog.path == Path("a.dcm")
