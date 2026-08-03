"""Tests for the pydicom pixel decoder."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dicomviewer.application.viewing import UnsupportedPixelFormatError
from dicomviewer.domain.studies import Image
from dicomviewer.infrastructure.dicom.pixel_reader import PydicomPixelDecoder
from tests.dicom_utils import write_ct_dataset, write_pixel_dataset

DECODER = PydicomPixelDecoder()


def test_decodes_grayscale_frame_with_metadata(tmp_path: Path) -> None:
    path = tmp_path / "ct.dcm"
    pixels = np.arange(48, dtype=np.uint16).reshape(6, 8)
    write_pixel_dataset(path, pixels, rescale_slope=2.0, rescale_intercept=-1.0)
    decoded = DECODER.decode(Image(path, 1))
    assert decoded.width == 8 and decoded.height == 6
    assert not decoded.is_color
    assert decoded.bits_allocated == 16
    assert decoded.photometric_interpretation == "MONOCHROME2"
    assert decoded.rescale_slope == 2.0
    assert decoded.rescale_intercept == -1.0
    np.testing.assert_array_equal(decoded.pixels, pixels)


def test_decodes_monochrome1_photometric(tmp_path: Path) -> None:
    path = tmp_path / "mri.dcm"
    write_pixel_dataset(
        path,
        np.zeros((4, 4), dtype=np.uint16),
        photometric_interpretation="MONOCHROME1",
    )
    decoded = DECODER.decode(Image(path, 1))
    assert decoded.is_monochrome1


def test_reads_dicom_window_metadata(tmp_path: Path) -> None:
    path = tmp_path / "windowed.dcm"
    write_pixel_dataset(
        path,
        np.zeros((4, 4), dtype=np.uint16),
        window_center=40.0,
        window_width=400.0,
    )
    decoded = DECODER.decode(Image(path, 1))
    assert decoded.window_center == 40.0
    assert decoded.window_width == 400.0


def test_decodes_color_frame(tmp_path: Path) -> None:
    path = tmp_path / "color.dcm"
    pixels = np.zeros((8, 8, 3), dtype=np.uint16)
    write_pixel_dataset(path, pixels, photometric_interpretation="RGB", samples=3)
    decoded = DECODER.decode(Image(path, 1))
    assert decoded.is_color
    assert decoded.width == 8 and decoded.height == 8


def test_raises_without_pixel_data(tmp_path: Path) -> None:
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
    with pytest.raises(UnsupportedPixelFormatError):
        DECODER.decode(Image(path, 1))


def test_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedPixelFormatError):
        DECODER.decode(Image(tmp_path / "missing.dcm", 1))
