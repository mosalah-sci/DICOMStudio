"""Shared test doubles and DICOM sample builders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from dicomviewer.application.processing import Histogram, PixelStatistics
from dicomviewer.application.viewing import PixelArray, RenderedImage
from dicomviewer.domain.export import ExportFormat
from dicomviewer.domain.metadata import MetadataDocument, MetadataElement, MetadataGroup
from dicomviewer.domain.studies import Image, StudyTree
from dicomviewer.domain.tags import TagDocument
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

    def scan(self, folder: Path, should_cancel=None, on_progress=None) -> StudyTree:
        self.calls.append(Path(folder))
        if self.error is not None:
            raise self.error
        if should_cancel is not None and should_cancel():
            return self.tree
        if on_progress is not None:
            on_progress(1, 0)
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


class FakeImageExporter:
    """ImageExporter double that records encodes and writes real files."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.writes: list[tuple[RenderedImage, ExportFormat, Path, int]] = []
        self.encodes: list[tuple[RenderedImage, ExportFormat, int]] = []

    def encode(
        self,
        image: RenderedImage,
        format: ExportFormat,
        quality: int = 90,
    ) -> bytes:
        if self.error is not None:
            raise self.error
        self.encodes.append((image, format, quality))
        return b"encoded"

    def write(
        self,
        image: RenderedImage,
        format: ExportFormat,
        path: Path,
        quality: int = 90,
    ) -> None:
        if self.error is not None:
            raise self.error
        self.writes.append((image, format, Path(path), quality))
        Path(path).write_bytes(b"encoded")


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

    def analyze(self, pixels: PixelArray, bins: int = 256) -> tuple[PixelStatistics, Histogram]:
        self.statistics_calls.append(pixels)
        self.histogram_calls.append((pixels, bins))
        return self.statistics_result, self.histogram_result


def sample_metadata_document(
    *,
    source: Path = Path("sample.dcm"),
    patient_name: str = "DOE^JOHN",
    study_description: str = "Chest exam",
    modality: str = "CT",
) -> MetadataDocument:
    """Return a small grouped metadata document for panel tests."""
    patient = MetadataGroup(
        "Patient",
        (
            MetadataElement(
                "(0010,0010)", "PatientName", "Patient", "Patient's Name", patient_name
            ),
            MetadataElement("(0010,0020)", "PatientID", "Patient", "Patient ID", "P-1"),
        ),
    )
    study = MetadataGroup(
        "Study",
        (
            MetadataElement(
                "(0008,1030)",
                "StudyDescription",
                "Study",
                "Study Description",
                study_description,
            ),
        ),
    )
    series = MetadataGroup(
        "Series",
        (MetadataElement("(0008,0060)", "Modality", "Series", "Modality", modality),),
    )
    return MetadataDocument(source=source, groups=(patient, study, series))


class FakeMetadataService:
    """MetadataService double returning a fixed document or raising an error."""

    def __init__(
        self,
        document: MetadataDocument | None = None,
        error: Exception | None = None,
    ) -> None:
        self.document = document or sample_metadata_document()
        self.error = error
        self.extracted: list[Image] = []

    def extract(self, image: Image) -> MetadataDocument:
        self.extracted.append(image)
        if self.error is not None:
            raise self.error
        return self.document


class FakeTagInspector:
    """TagInspector double returning a fixed document or raising an error."""

    def __init__(
        self,
        document: TagDocument | None = None,
        error: Exception | None = None,
    ) -> None:
        self.document = document or TagDocument(source=Path("sample.dcm"))
        self.error = error
        self.inspected: list[Path] = []

    def inspect(self, path: Path) -> TagDocument:
        self.inspected.append(Path(path))
        if self.error is not None:
            raise self.error
        return self.document


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
    pixel_spacing: tuple[float, float] | None = None,
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
    if pixel_spacing is not None:
        dataset.PixelSpacing = list(pixel_spacing)
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
    image_position: tuple[float, float, float] | None = None,
    image_orientation: tuple[float, ...] | None = None,
    slice_location: float | None = None,
    body_part: str = "",
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
    if body_part:
        dataset.BodyPartExamined = body_part
    if image_position is not None:
        dataset.ImagePositionPatient = [float(v) for v in image_position]
    if image_orientation is not None:
        dataset.ImageOrientationPatient = [float(v) for v in image_orientation]
    if slice_location is not None:
        dataset.SliceLocation = float(slice_location)
    dataset.Rows = rows
    dataset.Columns = columns
    dataset.SamplesPerPixel = 1
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.save_as(path, enforce_file_format=True)


def write_rich_ct_dataset(
    path: Path,
    *,
    patient_id: str = "P-123",
    patient_name: str = "DOE^JOHN",
    patient_birth_date: str = "19800101",
    patient_sex: str = "M",
    study_uid: str = "1.2.3.4.5",
    study_date: str = "20260801",
    study_description: str = "Chest exam",
    series_uid: str = "1.2.3.4.5.6",
    modality: str = "CT",
    series_number: int = 3,
    series_description: str = "Chest",
    sop_uid: str = "1.2.3.4.5.6.7",
    instance_number: int = 2,
) -> None:
    """Write a DICOM file carrying rich metadata across many groups."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.PatientID = patient_id
    dataset.PatientName = patient_name
    dataset.PatientBirthDate = patient_birth_date
    dataset.PatientSex = patient_sex
    dataset.StudyInstanceUID = study_uid
    dataset.StudyDate = study_date
    dataset.StudyDescription = study_description
    dataset.SeriesInstanceUID = series_uid
    dataset.SeriesNumber = series_number
    dataset.SeriesDescription = series_description
    dataset.Modality = modality
    dataset.SOPInstanceUID = sop_uid
    dataset.SOPClassUID = CT_SOP_CLASS_UID
    dataset.InstanceNumber = instance_number
    dataset.Manufacturer = "Acme Imaging"
    dataset.StationName = "CT01"
    dataset.SoftwareVersions = "1.0.0"
    dataset.SliceThickness = 1.5
    dataset.KVP = 120
    dataset.Rows = 8
    dataset.Columns = 6
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.PixelSpacing = [0.5, 0.5]
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.RescaleIntercept = -1024
    dataset.RescaleSlope = 1.0
    dataset.WindowCenter = 40
    dataset.WindowWidth = 400
    dataset.add_new((0x0009, 0x0010), "LO", "private-value")
    dataset.add_new((0x0028, 0x3006), "OW", b"\x00" * 128)
    dataset.save_as(path, enforce_file_format=True)


# ---------------------------------------------------------------------------
# v1.4 M1 — color/compression test builders
# ---------------------------------------------------------------------------


def build_rgb_dataset(
    pixels: np.ndarray,
    *,
    ybr: bool = False,
    planar: int = 0,
) -> Dataset:
    """Return an uncompressed 3-sample dataset carrying ``pixels`` (r, c, 3)."""
    rows, cols = pixels.shape[:2]
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = file_meta
    ds.Rows = rows
    ds.Columns = cols
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "YBR_FULL" if ybr else "RGB"
    ds.PlanarConfiguration = planar
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    if planar:
        ds.PixelData = np.ascontiguousarray(pixels.transpose(2, 0, 1)).tobytes()
    else:
        ds.PixelData = np.ascontiguousarray(pixels).tobytes()
    return ds


def write_rgb_dataset(
    path: Path, pixels: np.ndarray, *, ybr: bool = False, planar: int = 0
) -> None:
    """Write an uncompressed color dataset to ``path``."""
    build_rgb_dataset(pixels, ybr=ybr, planar=planar).save_as(path, enforce_file_format=True)


def build_mono_dataset(
    pixels: np.ndarray,
    *,
    monochrome1: bool = False,
    rescale_slope: float = 1.0,
    rescale_intercept: float = 0.0,
) -> Dataset:
    """Return an uncompressed grayscale dataset for compression round-trips."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = file_meta
    ds.Rows = pixels.shape[0]
    ds.Columns = pixels.shape[1]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME1" if monochrome1 else "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept
    ds.PixelData = np.asarray(pixels, dtype="<u2").tobytes()
    return ds


def write_encapsulated_dataset(
    path: Path,
    *,
    payload: bytes,
    transfer_syntax_uid: str,
    rows: int,
    columns: int,
    samples: int = 1,
    photometric: str = "MONOCHROME2",
    rescale_slope: float = 1.0,
    rescale_intercept: float = 0.0,
) -> None:
    """Write a dataset whose PixelData is an encapsulated compressed payload."""
    from pydicom.encaps import encapsulate
    from pydicom.uid import UID

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CT_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6"
    file_meta.TransferSyntaxUID = UID(transfer_syntax_uid)
    ds = Dataset()
    ds.file_meta = file_meta
    ds.Rows = rows
    ds.Columns = columns
    ds.SamplesPerPixel = samples
    ds.PhotometricInterpretation = photometric
    ds.PlanarConfiguration = 0
    ds.BitsAllocated = 8 if samples > 1 else 16
    ds.BitsStored = ds.BitsAllocated
    ds.HighBit = ds.BitsAllocated - 1
    ds.PixelRepresentation = 0
    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept
    ds.PixelData = encapsulate([payload])
    ds.save_as(path, enforce_file_format=True)


def jpeg_payload(width: int = 8, height: int = 6, quality: int = 90) -> bytes:
    """Encode a deterministic gradient frame as JFIF/JPEG bytes via Qt."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage, QPainter

    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    for x in range(width):
        shade = int(255 * x / max(width - 1, 1))
        painter.fillRect(x, 0, 1, height, QColor.fromRgb(shade, 40, 255 - shade))
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "JPEG", quality)
    return bytes(buffer.data())
