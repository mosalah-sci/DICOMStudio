"""Tests for the pydicom-backed tag inspection service."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.application.inspection import InspectionError
from dicomviewer.infrastructure.dicom.tag_inspector import PydicomTagInspector
from tests.dicom_utils import write_rich_ct_dataset


@pytest.fixture
def rich_file(tmp_path: Path) -> Path:
    path = tmp_path / "rich.dcm"
    write_rich_ct_dataset(path)
    return path


def test_inspect_surfaces_every_element_including_private_tags(rich_file: Path) -> None:
    document = PydicomTagInspector().inspect(rich_file)
    assert document.has_content()
    by_tag = {entry.tag: entry for entry in document.entries}
    assert by_tag["(0010,0010)"].keyword == "PatientName"
    assert by_tag["(0009,0010)"].is_private


def test_inspect_orders_entries_by_numeric_tag(rich_file: Path) -> None:
    document = PydicomTagInspector().inspect(rich_file)
    tags = [entry.tag for entry in document.entries]
    assert tags == sorted(tags, key=lambda tag: _numeric_tag(tag))


def test_inspect_formats_values_for_display(rich_file: Path) -> None:
    document = PydicomTagInspector().inspect(rich_file)
    by_keyword = {entry.keyword: entry for entry in document.entries}
    assert by_keyword["PixelSpacing"].value == "0.5\\0.5"
    assert by_keyword["KVP"].value == "120"
    assert by_keyword["SliceThickness"].value == "1.5"
    assert by_keyword["LUTData"].value == "<binary 128 bytes>"


def test_inspect_raises_for_a_non_dicom_file(tmp_path: Path) -> None:
    path = tmp_path / "not_dicom.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(InspectionError):
        PydicomTagInspector().inspect(path)


def _numeric_tag(tag: str) -> tuple[int, int]:
    group, element = tag[1:-1].split(",")
    return int(group, 16), int(element, 16)
