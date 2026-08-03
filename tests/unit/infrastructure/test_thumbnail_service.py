"""Tests for the pydicom thumbnail service."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from dicomviewer.domain.studies import Image
from dicomviewer.domain.thumbnail import Thumbnail
from dicomviewer.infrastructure.dicom.thumbnail_service import PydicomThumbnailService
from tests.dicom_utils import CT_SOP_CLASS_UID, write_ct_dataset

SERVICE = PydicomThumbnailService()


def _write_pixel_file(path: Path, pixels: np.ndarray, **extra) -> None:
    """Write a DICOM file carrying a raw 16-bit pixel array."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = "1.2.3"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.Rows = pixels.shape[0]
    dataset.Columns = pixels.shape[1]
    dataset.SamplesPerPixel = 1
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.StudyInstanceUID = "1.2.3.4"
    dataset.SeriesInstanceUID = "1.2.3.4.5"
    dataset.SOPInstanceUID = "1.2.3.4.5.6"
    dataset.Modality = "CT"
    dataset.InstanceNumber = 1
    for key, value in extra.items():
        setattr(dataset, key, value)
    dataset.PixelData = pixels.astype("<u2").tobytes()
    dataset.PlanarConfiguration = 0
    dataset.save_as(path, enforce_file_format=True)


@pytest.fixture
def pixel_file(tmp_path: Path) -> Path:
    """Create a 16x12 grayscale DICOM file with a known gradient."""
    pixels = np.tile(np.arange(16, dtype=np.uint16), (12, 1))
    path = tmp_path / "slice.dcm"
    _write_pixel_file(path, pixels)
    return path


def test_generate_returns_bounded_grayscale_thumbnail(pixel_file: Path) -> None:
    thumbnail = SERVICE.generate(Image(pixel_file, 1), size=64)
    assert thumbnail is not None
    assert thumbnail.width == 64
    assert thumbnail.height == 48
    assert thumbnail.pixel_count == 64 * 48
    assert thumbnail.validate()


def test_generate_applies_the_voi_window(pixel_file: Path, tmp_path: Path) -> None:
    pixels = np.tile(np.arange(16, dtype=np.uint16), (12, 1))
    windowed_path = tmp_path / "windowed.dcm"
    _write_pixel_file(windowed_path, pixels, WindowCenter=8, WindowWidth=4)
    default = SERVICE.generate(Image(pixel_file, 1), size=64)
    windowed = SERVICE.generate(Image(windowed_path, 1), size=64)
    assert default is not None and windowed is not None
    assert default.data != windowed.data


def test_generate_returns_none_without_pixel_data(tmp_path: Path) -> None:
    path = tmp_path / "no-pixels.dcm"
    write_ct_dataset(
        path,
        patient_id="P1",
        patient_name="X",
        study_uid="1.2",
        series_uid="1.2.3",
        sop_uid="1.2.3.4",
        modality="CT",
        instance_number=1,
    )
    assert SERVICE.generate(Image(path, 1), size=64) is None


def test_generate_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert SERVICE.generate(Image(tmp_path / "missing.dcm", 1), size=64) is None


def test_generate_handles_color_pixels(tmp_path: Path) -> None:
    pixels = np.zeros((8, 8, 3), dtype=np.uint16)
    path = tmp_path / "color.dcm"
    _write_pixel_file(
        path,
        pixels,
        SamplesPerPixel=3,
        PhotometricInterpretation="RGB",
    )
    thumbnail = SERVICE.generate(Image(path, 1), size=64)
    assert thumbnail is not None
    assert isinstance(thumbnail, Thumbnail)
    assert thumbnail.width == 64 and thumbnail.height == 64
