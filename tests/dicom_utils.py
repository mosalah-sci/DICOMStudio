"""Shared test doubles and DICOM sample builders."""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from dicomviewer.domain.studies import Image, StudyTree
from dicomviewer.domain.thumbnail import Thumbnail

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
