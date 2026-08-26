"""Compressed transfer syntax and YBR decoding tests (v1.4 M1).

Codec-dependent tests are skipped with an explicit reason when the optional
codec extra is absent, keeping the suite deterministic on any installation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydicom.uid import JPEG2000Lossless, RLELossless

from dicomviewer.application.viewing import UnsupportedPixelFormatError
from dicomviewer.domain.studies import Image
from dicomviewer.infrastructure.dicom.pixel_reader import (
    PydicomPixelDecoder,
    _unsupported_message,
)
from tests.dicom_utils import (
    build_mono_dataset,
    build_rgb_dataset,
    jpeg_payload,
    write_encapsulated_dataset,
    write_rgb_dataset,
)

_JPEG_BASELINE = "1.2.840.10008.1.2.4.50"
_J2K_LOSSLESS = "1.2.840.10008.1.2.4.90"
_MPEG4_AVC = "1.2.840.10008.1.2.4.102"


def _decoder_available(uid: str) -> bool:
    from pydicom.pixels import decoders

    for name in dir(decoders):
        candidate = getattr(decoders, name)
        if name.endswith("Decoder") and getattr(candidate, "UID", "") == uid:
            return bool(getattr(candidate, "is_available", False))
    return False


def _decode(path: Path):
    return PydicomPixelDecoder().decode(Image(path, 1))


# --- uncompressed behavior preserved --------------------------------------


def test_uncompressed_rgb_decodes_identically(qapp, tmp_path: Path) -> None:
    del qapp
    original = np.zeros((6, 8, 3), dtype=np.uint8)
    original[:, :, 0] = np.arange(8)[None, :]
    original[:, :, 1] = 128
    original[:, :, 2] = 255 - np.arange(8)[None, :]
    path = tmp_path / "rgb.dcm"
    write_rgb_dataset(path, original)

    decoded = _decode(path)

    assert decoded.samples == 3
    assert decoded.photometric_interpretation == "RGB"
    assert decoded.width == 8 and decoded.height == 6
    np.testing.assert_array_equal(decoded.pixels, original)


def test_uncompressed_ybr_full_neutral_chroma_converts(qapp, tmp_path: Path) -> None:
    del qapp
    # Cb == Cr == 128 is the neutral axis of Y'CbCr: RGB collapses to Y.
    y_column = np.array([[40], [90], [200]], dtype=np.uint8)
    pixels = np.repeat(y_column, 2, axis=1)[:, :, None] * np.ones((3, 2, 3), dtype=np.uint8)
    pixels[..., 1] = 128
    pixels[..., 2] = 128
    path = tmp_path / "ybr.dcm"
    write_rgb_dataset(path, pixels, ybr=True)

    decoded = _decode(path)

    assert decoded.photometric_interpretation == "RGB"
    expected = np.repeat(y_column, 2, axis=1)
    np.testing.assert_array_equal(decoded.pixels[..., 0], expected)
    np.testing.assert_array_equal(decoded.pixels[..., 1], expected)
    np.testing.assert_array_equal(decoded.pixels[..., 2], expected)


def test_uncompressed_ybr_known_color_vector(qapp, tmp_path: Path) -> None:
    del qapp
    # Hand-computed full-range conversion for Y=128, Cb=128, Cr=255:
    #   R = 128 + 1.402*127 -> clip 255 ; G = 128 - 0.714136*127 -> 37 ;
    #   B = 128 + 1.772*0   -> 128
    pixels = np.full((1, 1, 3), 128, dtype=np.uint8)
    pixels[0, 0, 2] = 255
    path = tmp_path / "red.dcm"
    write_rgb_dataset(path, pixels, ybr=True)

    decoded = _decode(path)

    np.testing.assert_array_equal(decoded.pixels[0, 0], [255, 37, 128])


def test_uncompressed_ybr_planar_configuration_normalized(qapp, tmp_path: Path) -> None:
    del qapp
    y_column = np.array([[10], [250]], dtype=np.uint8)
    pixels = np.repeat(y_column, 3, axis=1)[:, :, None] * np.ones((2, 3, 3), dtype=np.uint8)
    pixels[..., 1] = 128
    pixels[..., 2] = 128
    path = tmp_path / "ybr_planar.dcm"
    write_rgb_dataset(path, pixels, ybr=True, planar=1)

    decoded = _decode(path)

    assert decoded.photometric_interpretation == "RGB"
    np.testing.assert_array_equal(decoded.pixels[..., 0], np.repeat(y_column, 3, axis=1))
    np.testing.assert_array_equal(decoded.pixels[..., 1], np.repeat(y_column, 3, axis=1))


# --- JPEG baseline ---------------------------------------------------------


@pytest.mark.skipif(not _decoder_available(_JPEG_BASELINE), reason="JPEG codec extra not installed")
def test_jpeg_baseline_rgb_decodes(qapp, tmp_path: Path) -> None:
    del qapp
    payload = jpeg_payload(8, 6)
    path = tmp_path / "jpeg.dcm"
    write_encapsulated_dataset(
        path,
        payload=payload,
        transfer_syntax_uid=_JPEG_BASELINE,
        rows=6,
        columns=8,
        samples=3,
        photometric="RGB",
    )

    decoded = _decode(path)

    assert decoded.samples == 3
    assert decoded.photometric_interpretation == "RGB"
    frame = np.asarray(decoded.pixels)
    assert frame.shape == (6, 8, 3)
    # Lossy compression: the decoded gradient must retain structure (non-flat
    # content) without asserting exact pixel equality.
    assert 0 < int(frame.std()) <= 255


@pytest.mark.skipif(not _decoder_available(_JPEG_BASELINE), reason="JPEG codec extra not installed")
def test_jpeg_baseline_ybr_full_422_handler_returns_rgb(qapp, tmp_path: Path) -> None:
    del qapp
    payload = jpeg_payload(8, 6)
    path = tmp_path / "jpeg_ybr.dcm"
    write_encapsulated_dataset(
        path,
        payload=payload,
        transfer_syntax_uid=_JPEG_BASELINE,
        rows=6,
        columns=8,
        samples=3,
        photometric="YBR_FULL_422",
    )

    decoded = _decode(path)

    # The codec handler delivers RGB planes for compressed YBR; the decoder
    # normalizes the declared photometric so the payload and metadata agree.
    assert decoded.samples == 3
    assert decoded.photometric_interpretation == "RGB"
    frame = np.asarray(decoded.pixels)
    assert frame.shape == (6, 8, 3)


# --- JPEG 2000 -------------------------------------------------------------


@pytest.mark.skipif(not _decoder_available(_J2K_LOSSLESS), reason="J2K codec extra not installed")
def test_j2k_lossless_rgb_round_trip_is_exact(qapp, tmp_path: Path) -> None:
    del qapp
    # OpenJPEG rejects frames smaller than its minimum resolution grid, so
    # the synthetic image uses a modestly sized 32x32 gradient.
    original = np.zeros((32, 32, 3), dtype=np.uint8)
    original[..., 0] = np.arange(32 * 32, dtype=np.uint8).reshape(32, 32)
    original[..., 1] = 200
    original[..., 2] = 55
    ds = build_rgb_dataset(original)
    ds.compress(JPEG2000Lossless)
    path = tmp_path / "j2k.dcm"
    ds.save_as(path, enforce_file_format=True)

    decoded = _decode(path)

    assert decoded.photometric_interpretation == "RGB"
    np.testing.assert_array_equal(np.asarray(decoded.pixels), original)


# --- grayscale compressed + rescale passthrough ----------------------------


@pytest.mark.skipif(not _decoder_available(RLELossless), reason="RLE decoder unavailable")
def test_rle_monochrome1_preserves_pixels_and_rescale(qapp, tmp_path: Path) -> None:
    del qapp
    pixels = (np.arange(24, dtype=np.uint16).reshape(4, 6) * 2711) % 60000
    ds = build_mono_dataset(pixels, monochrome1=True, rescale_slope=2.5, rescale_intercept=-1024)
    ds.compress(RLELossless)
    path = tmp_path / "rle_m1.dcm"
    ds.save_as(path, enforce_file_format=True)

    decoded = _decode(path)

    assert decoded.is_monochrome1 is True
    assert decoded.rescale_slope == 2.5
    assert decoded.rescale_intercept == -1024.0
    np.testing.assert_array_equal(decoded.pixels, pixels)


def test_monochrome2_rescale_unchanged_for_uncompressed(qapp, tmp_path: Path) -> None:
    del qapp
    ds = build_mono_dataset(
        np.full((4, 6), 500, dtype=np.uint16), rescale_slope=1.0, rescale_intercept=-1024
    )
    path = tmp_path / "mono2.dcm"
    ds.save_as(path, enforce_file_format=True)

    decoded = _decode(path)

    assert decoded.is_monochrome1 is False
    assert decoded.rescale_intercept == -1024.0


# --- unsupported / failure paths -------------------------------------------


def test_unsupported_transfer_syntax_is_typed_failure(qapp, tmp_path: Path) -> None:
    del qapp
    path = tmp_path / "mpeg.dcm"
    write_encapsulated_dataset(
        path,
        payload=b"\x00" * 64,
        transfer_syntax_uid=_MPEG4_AVC,
        rows=6,
        columns=8,
        samples=3,
        photometric="RGB",
    )

    with pytest.raises(UnsupportedPixelFormatError) as excinfo:
        _decode(path)

    message = str(excinfo.value)
    assert _MPEG4_AVC in message
    assert "codec-jpeg" not in message
    assert "codec-j2k" not in message


def test_failure_message_names_codec_extra() -> None:
    jpeg = _unsupported_message(Path("x"), _JPEG_BASELINE, Exception("boom"))
    j2k = _unsupported_message(Path("x"), _J2K_LOSSLESS, Exception("boom"))
    plain = _unsupported_message(Path("x"), "", Exception("boom"))

    assert "'codec-jpeg'" in jpeg and "boom" in jpeg
    assert "'codec-j2k'" in j2k
    assert plain == "Unsupported pixel format in x: boom"
    assert "codec-" not in plain
