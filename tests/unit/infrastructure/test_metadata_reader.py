"""Tests for the pydicom-backed metadata extraction service."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.application.metadata import MetadataExtractionError
from dicomviewer.domain.studies import Image
from dicomviewer.infrastructure.dicom.metadata_reader import PydicomMetadataService
from tests.dicom_utils import write_ct_dataset, write_rich_ct_dataset


@pytest.fixture
def rich_file(tmp_path: Path) -> Path:
    path = tmp_path / "rich.dcm"
    write_rich_ct_dataset(path)
    return path


def test_extract_groups_metadata_logically(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    assert document.has_content()
    groups = {group.name: group for group in document.groups}
    assert "Patient" in groups
    assert "Study" in groups
    assert "Series" in groups
    assert "Image" in groups
    assert "Equipment" in groups


def test_extract_reads_expected_values(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    by_keyword = {
        element.keyword: element for group in document.groups for element in group.elements
    }
    assert by_keyword["PatientName"].value == "DOE^JOHN"
    assert by_keyword["PatientID"].value == "P-123"
    assert by_keyword["StudyDescription"].value == "Chest exam"
    assert by_keyword["Modality"].value == "CT"
    assert by_keyword["SeriesNumber"].value == "3"
    assert by_keyword["Manufacturer"].value == "Acme Imaging"


def test_extract_formats_multi_valued_and_float_values(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    by_keyword = {
        element.keyword: element for group in document.groups for element in group.elements
    }
    assert by_keyword["PixelSpacing"].value == "0.5\\0.5"
    assert by_keyword["KVP"].value == "120"
    assert by_keyword["SliceThickness"].value == "1.5"


def test_extract_skips_private_tags(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    keywords = [element.keyword for group in document.groups for element in group.elements]
    assert not any(keyword.startswith("(0009") for keyword in keywords)


def test_extract_bounds_binary_values(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    by_keyword = {
        element.keyword: element for group in document.groups for element in group.elements
    }
    assert by_keyword["LUTData"].value == "<binary 128 bytes>"


def test_extract_groups_are_in_display_order(rich_file: Path) -> None:
    service = PydicomMetadataService()
    document = service.extract(Image(rich_file, 1))
    names = [group.name for group in document.groups]
    assert names.index("Patient") < names.index("Study")
    assert names.index("Study") < names.index("Series")


def test_extract_from_missing_file_raises(tmp_path: Path) -> None:
    service = PydicomMetadataService()
    with pytest.raises(MetadataExtractionError):
        service.extract(Image(tmp_path / "missing.dcm", 1))


def test_extract_handles_minimal_datasets(tmp_path: Path) -> None:
    path = tmp_path / "minimal.dcm"
    write_ct_dataset(
        path,
        patient_id="P-1",
        patient_name="DOE^JANE",
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        sop_uid="1.2.3.4.5",
        modality="MR",
        instance_number=1,
    )
    document = PydicomMetadataService().extract(Image(path, 1))
    assert document.has_content()
    by_keyword = {
        element.keyword: element for group in document.groups for element in group.elements
    }
    assert by_keyword["PatientName"].value == "DOE^JANE"
