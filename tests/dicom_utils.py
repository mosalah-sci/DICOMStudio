"""Shared test doubles and DICOM sample builders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from dicomviewer.application.processing import Histogram, PixelStatistics
from dicomviewer.application.viewing import PixelArray, RenderedImage
from dicomviewer.domain.studies import Image, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail
from dicomviewer.domain.viewport import Viewport

CT_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.2"


class FakeStudyScanner:
    """StudyScanner double returning a fixed tree or raising a fixed error."""

    def __init__(
        self,
        tree: StudyTree | None = None,
        error: Exception | None = None,
    ) -> None:
        self.tree = tree or StudyTree.empty(Path("."))
        self.error = error
        self.calls: list[Path] = []

    def scan(self, folder: Path, should_cancel=None) -> StudyTree:
        self.calls.append(Path(folder))
        if self.error is not None:
            raise self.error
        if should_cancel is not None and should_cancel():
            return self.tree
        return self.tree


class FakeThumbnailService:
    """ThumbnailService double returning a fixed thumbnail."""

    def __init__(self, thumbnail: Thumbnail | None = None) -> None:
        self.thumbnail = thumbnail or Thumbnail(width=2, height=2, data=bytes(4))
        self.generated: list[Image] = []

    def generate(self, image: Image, size: int) -> Thumbnail | None:
        self.generated.append(image)
        return self.thumbnail


class FakeErrorPresenter:
    """Records user-facing errors instead of showing modal dialogs."""

    def __init__(self) -> None:
        self.errors: list[tuple[str, str, str | None]] = []
        self.warnings: list[tuple[str, str, str | None]] = []

    def show_error(
        self,
        parent,
        title: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.errors.append((title, message, detail))

    def show_warning(
        self,
        parent,
        title: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.warnings.append((title, message, detail))


class FakePixelDecoder:
    """PixelDecoder double returning a fixed frame or raising a fixed error."""

    def __init__(
        self,
        pixels: PixelArray | None = None,
        error: Exception | None = None,
    ) -> None:
        self.pixels = pixels or sample_pixel_array()
        self.error = error
        self.decoded: list[Image] = []

    def decode(self, image: Image) -> PixelArray:
        self.decoded.append(image)
        if self.error is not None:
            raise self.error
        return self.pixels


class FakeViewRenderer:
    """ViewRenderer double returning an opaque RGBA frame of the right size."""

    def __init__(self) -> None:
        self.calls: list[tuple[PixelArray, Viewport]] = []

    def render(self, pixels: PixelArray, viewport: Viewport) -> RenderedImage:
        self.calls.append((pixels, viewport))
        data = b"\xff" * (pixels.width * pixels.height * 4)
        return RenderedImage(width=pixels.width, height=pixels.height, data=data)

    def effective_window(self, pixels: PixelArray, viewport: Viewport) -> tuple[float, float]:
        del pixels
        if viewport.window_width > 0:
            center = viewport.window_center if viewport.window_center is not None else 0.0
            return (center, viewport.window_width)
        return (50.0, 100.0)


class FakeImageAnalyzer:
    """ImageAnalyzer double returning fixed statistics and histograms."""

    def __init__(
        self,
        statistics: PixelStatistics | None = None,
        histogram: Histogram | None = None,
    ) -> None:
        self.statistics_result = statistics or PixelStatistics(
            minimum=0.0, maximum=255.0, mean=127.5, standard_deviation=10.0, pixel_count=48
        )
        self.histogram_result = histogram or Histogram(
            bin_count=2, minimum=0.0, maximum=255.0, counts=(24, 24)
        )
        self.statistics_calls: list[PixelArray] = []
        self.histogram_calls: list[tuple[PixelArray, int]] = []

    def statistics(self, pixels: PixelArray) -> PixelStatistics:
        self.statistics_calls.append(pixels)
        return self.statistics_result

    def histogram(self, pixels: PixelArray, bins: int = 256) -> Histogram:
        self.histogram_calls.append((pixels, bins))
        return self.histogram_result


def sample_pixel_array(width: int = 8, height: int = 6) -> PixelArray:
    """Return a small gradient grayscale frame for viewer tests."""
    grid = (np.arange(height)[:, None] * width + np.arange(width)).astype(np.uint16)
    return PixelArray(pixels=grid, width=width, height=height)


def write_pixel_dataset(
    path: Path,
    pixels: np.ndarray,
    *,
    photometric_interpretation: str = "MONOCHROME2",
    rescale_slope: float = 1.0,
    rescale_intercept: float = 0.0,
    window_center: float | None = None,
    window_width: float | None = None,
    bits_allocated: int = 16,
    samples: int = 1,
    sop_uid: str = "1.2.3.4.5.6",
) -> None:
    """Write a DICOM file carrying a raw pixel array with rendering metadata."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.Rows = pixels.shape[0]
    dataset.Columns = pixels.shape[1]
    dataset.SamplesPerPixel = samples
    dataset.PhotometricInterpretation = photometric_interpretation
    dataset.BitsAllocated = bits_allocated
    dataset.BitsStored = bits_allocated
    dataset.HighBit = bits_allocated - 1
    dataset.PixelRepresentation = 0
    dataset.RescaleSlope = rescale_slope
    dataset.RescaleIntercept = rescale_intercept
    if window_center is not None:
        dataset.WindowCenter = window_center
    if window_width is not None:
        dataset.WindowWidth = window_width
    dataset.StudyInstanceUID = "1.2.3.4"
    dataset.SeriesInstanceUID = "1.2.3.4.5"
    dataset.SOPInstanceUID = sop_uid
    dataset.Modality = "CT"
    dataset.InstanceNumber = 1
    if samples > 1:
        dataset.PlanarConfiguration = 0
    dtype = "<u2" if bits_allocated > 8 else "u1"
    dataset.PixelData = np.asarray(pixels, dtype=dtype).tobytes()
    dataset.save_as(path, enforce_file_format=True)


def write_ct_dataset(
    path: Path,
    *,
    patient_id: str,
    patient_name: str,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    modality: str,
    instance_number: int,
    study_date: str = "",
    study_description: str = "",
    series_description: str = "",
    rows: int = 8,
    columns: int = 6,
) -> None:
    """Write a minimal, valid CT-like DICOM file to ``path``."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.PatientID = patient_id
    dataset.PatientName = patient_name
    dataset.StudyInstanceUID = study_uid
    dataset.SeriesInstanceUID = series_uid
    dataset.SOPInstanceUID = sop_uid
    dataset.Modality = modality
    dataset.InstanceNumber = instance_number
    dataset.StudyDate = study_date
    dataset.StudyDescription = study_description
    dataset.SeriesDescription = series_description
    dataset.Rows = rows
    dataset.Columns = columns
    dataset.SamplesPerPixel = 1
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.save_as(path, enforce_file_format=True)
