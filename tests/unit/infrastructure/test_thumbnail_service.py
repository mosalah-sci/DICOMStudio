"""Tests for the pydicom thumbnail service."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dicomviewer.domain.studies import Image
from dicomviewer.infrastructure.dicom.thumbnail_service import PydicomThumbnailService
from tests.dicom_utils import (
    Thumbnail,
    write_ct_dataset,
    write_pixel_dataset,
)

SERVICE = PydicomThumbnailService()


@pytest.fixture
def pixel_file(tmp_path: Path) -> Path:
    """Create a 16x12 grayscale DICOM file with a known gradient."""
    pixels = np.tile(np.arange(16, dtype=np.uint16), (12, 1))
    path = tmp_path / "slice.dcm"
    write_pixel_dataset(path, pixels)
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
    write_pixel_dataset(windowed_path, pixels, window_center=8, window_width=4)
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
    write_pixel_dataset(
        path,
        pixels,
        photometric_interpretation="RGB",
        samples=3,
    )
    thumbnail = SERVICE.generate(Image(path, 1), size=64)
    assert thumbnail is not None
    assert isinstance(thumbnail, Thumbnail)
    assert thumbnail.width == 64 and thumbnail.height == 64


def test_generate_samples_before_windowing_for_byte_identical_output(
    tmp_path: Path,
) -> None:
    pixels = np.tile(np.arange(16, dtype=np.uint16), (12, 1))
    path = tmp_path / "windowed.dcm"
    write_pixel_dataset(path, pixels, window_center=8, window_width=4)
    thumbnail = SERVICE.generate(Image(path, 1), size=64)
    assert thumbnail is not None

    data = np.frombuffer(thumbnail.data, dtype=np.uint8).reshape(thumbnail.height, thumbnail.width)
    assert data.shape == (48, 64)
    assert data.min() <= 128 <= data.max()


def test_generate_downscales_large_frames_to_the_bounding_box(
    tmp_path: Path,
) -> None:
    rng = np.random.default_rng(5)
    pixels = rng.integers(0, 4096, (1024, 512)).astype(np.uint16)
    path = tmp_path / "large.dcm"
    write_pixel_dataset(path, pixels, window_center=2048, window_width=2048)
    thumbnail = SERVICE.generate(Image(path, 1), size=64)
    assert thumbnail is not None
    assert thumbnail.width == 32
    assert thumbnail.height == 64
