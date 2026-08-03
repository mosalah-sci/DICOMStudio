"""Tests for the DICOM metadata domain model."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.domain.metadata import (
    GROUP_ORDER,
    MetadataDocument,
    MetadataElement,
    MetadataGroup,
    classify_metadata_group,
)


def test_classify_patient_tags() -> None:
    assert classify_metadata_group(0x0010, "PatientName") == "Patient"
    assert classify_metadata_group(0x0010, "PatientID") == "Patient"


def test_classify_study_tags() -> None:
    assert classify_metadata_group(0x0008, "StudyDescription") == "Study"
    assert classify_metadata_group(0x0020, "StudyInstanceUID") == "Study"


def test_classify_series_tags() -> None:
    assert classify_metadata_group(0x0008, "Modality") == "Series"
    assert classify_metadata_group(0x0020, "SeriesInstanceUID") == "Series"


def test_classify_image_tags() -> None:
    assert classify_metadata_group(0x0008, "SOPInstanceUID") == "Image"
    assert classify_metadata_group(0x0020, "InstanceNumber") == "Image"


def test_classify_acquisition_tags() -> None:
    assert classify_metadata_group(0x0018, "KVP") == "Acquisition"
    assert classify_metadata_group(0x0018, "SliceThickness") == "Acquisition"


def test_classify_pixel_tags() -> None:
    assert classify_metadata_group(0x0028, "Rows") == "Image Pixel"
    assert classify_metadata_group(0x0028, "WindowCenter") == "Image Pixel"


def test_classify_equipment_tags() -> None:
    assert classify_metadata_group(0x0008, "Manufacturer") == "Equipment"
    assert classify_metadata_group(0x0008, "StationName") == "Equipment"


def test_classify_file_meta_and_unknown_tags() -> None:
    assert classify_metadata_group(0x0002, "TransferSyntaxUID") == "File Meta"
    assert classify_metadata_group(0x0019, "UnknownPrivateGroup") == "Acquisition"


def test_group_order_lists_every_presentation_group() -> None:
    assert "Patient" in GROUP_ORDER
    assert "Study" in GROUP_ORDER
    assert "Series" in GROUP_ORDER
    assert "Image" in GROUP_ORDER
    assert "Acquisition" in GROUP_ORDER
    assert "Image Pixel" in GROUP_ORDER
    assert "Other" in GROUP_ORDER


def test_document_counts_and_content() -> None:
    group = MetadataGroup(
        "Patient",
        (MetadataElement("(0010,0010)", "PatientName", "Patient", "Patient's Name", "DOE^JOHN"),),
    )
    document = MetadataDocument(source=Path("a.dcm"), groups=(group,))
    assert document.has_content()
    assert document.group_count == 1
    assert document.element_count == 1


def test_empty_document_has_no_content() -> None:
    document = MetadataDocument(source=Path("a.dcm"))
    assert not document.has_content()
    assert document.element_count == 0
