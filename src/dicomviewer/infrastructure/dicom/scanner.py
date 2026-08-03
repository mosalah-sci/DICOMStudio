"""Recursive DICOM folder scanner built on pydicom.

The scanner walks a folder tree, validates each candidate file as DICOM by
reading only its header, and groups the valid instances into the
patient/study/series hierarchy defined in the Domain layer. Invalid or
unreadable files are skipped and counted, never raised.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from dicomviewer.application.discovery import DiscoveryError
from dicomviewer.domain.studies import Image, Patient, Series, Study, StudyTree

_NON_DICOM_EXTENSIONS = frozenset(
    {
        ".7z",
        ".avi",
        ".bmp",
        ".bz2",
        ".csv",
        ".doc",
        ".docx",
        ".gif",
        ".gz",
        ".jpeg",
        ".jpg",
        ".json",
        ".log",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".rar",
        ".tif",
        ".tiff",
        ".txt",
        ".webp",
        ".xls",
        ".xlsx",
        ".xml",
        ".zip",
    }
)

_PATIENT_TAGS = {
    "patient_id": (0x0010, 0x0020),
    "name": (0x0010, 0x0010),
    "birth_date": (0x0010, 0x0030),
    "sex": (0x0010, 0x0040),
}

_STUDY_TAGS = {
    "study_uid": (0x0020, 0x000D),
    "study_date": (0x0008, 0x0020),
    "study_id": (0x0020, 0x0010),
    "description": (0x0008, 0x1030),
}

_SERIES_TAGS = {
    "series_uid": (0x0020, 0x000E),
    "series_number": (0x0020, 0x0011),
    "modality": (0x0008, 0x0060),
    "description": (0x0008, 0x103E),
}

_IMAGE_TAGS = {
    "instance_number": (0x0020, 0x0013),
    "sop_uid": (0x0008, 0x0018),
}


class PydicomStudyScanner:
    """Scans folders recursively and groups DICOM instances into a study tree."""

    def scan(
        self,
        folder: Path,
        should_cancel: Callable[[], bool] | None = None,
    ) -> StudyTree:
        """Scan ``folder`` and return the discovered study tree.

        Files that are not DICOM, cannot be read, or lack the grouping tags
        are skipped and counted as invalid.
        """
        folder = Path(folder)
        if not folder.is_dir():
            raise DiscoveryError(f"Folder not found: {folder}")

        patients: dict[str, _PatientAccumulator] = {}
        invalid_files = 0
        scanned = 0

        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                if should_cancel is not None and should_cancel():
                    logger.info("Scan of {} cancelled after {} files", folder, scanned)
                    return _build_tree(folder, patients, invalid_files)
                path = Path(root) / name
                if path.suffix.lower() in _NON_DICOM_EXTENSIONS:
                    continue
                scanned += 1
                instance = self._parse_instance(path)
                if instance is None:
                    invalid_files += 1
                    continue
                self._accumulate(patients, instance)

        logger.info(
            "Scan of {} complete: {} files, {} invalid, {} patients",
            folder,
            scanned,
            invalid_files,
            len(patients),
        )
        return _build_tree(folder, patients, invalid_files)

    def _parse_instance(self, path: Path) -> _Instance | None:
        """Extract grouping metadata from a file, or ``None`` if invalid."""
        dataset = _read_header(path)
        if dataset is None:
            return None
        study_uid = _text(dataset, _STUDY_TAGS["study_uid"])
        series_uid = _text(dataset, _SERIES_TAGS["series_uid"])
        modality = _text(dataset, _SERIES_TAGS["modality"])
        sop_uid = _text(dataset, _IMAGE_TAGS["sop_uid"])
        if not study_uid or not series_uid or not modality:
            logger.debug("File lacks required DICOM grouping tags: {}", path)
            return None
        return _Instance(
            path=path,
            patient_id=_text(dataset, _PATIENT_TAGS["patient_id"]),
            patient_name=_text(dataset, _PATIENT_TAGS["name"]),
            patient_birth_date=_text(dataset, _PATIENT_TAGS["birth_date"]),
            patient_sex=_text(dataset, _PATIENT_TAGS["sex"]),
            study_uid=study_uid,
            study_date=_text(dataset, _STUDY_TAGS["study_date"]),
            study_id=_text(dataset, _STUDY_TAGS["study_id"]),
            study_description=_text(dataset, _STUDY_TAGS["description"]),
            series_uid=series_uid,
            series_number=_int(dataset, _SERIES_TAGS["series_number"]),
            modality=modality,
            series_description=_text(dataset, _SERIES_TAGS["description"]),
            instance_number=_int(dataset, _IMAGE_TAGS["instance_number"]),
            sop_uid=sop_uid,
        )

    def _accumulate(self, patients: dict[str, _PatientAccumulator], instance: _Instance) -> None:
        """Fold a parsed instance into the patient/study/series accumulators."""
        patient_key = instance.patient_id or f"patient:{instance.patient_name or 'unknown'}"
        patient = patients.setdefault(
            patient_key,
            _PatientAccumulator(
                patient_id=instance.patient_id,
                name=instance.patient_name,
                birth_date=instance.patient_birth_date,
                sex=instance.patient_sex,
            ),
        )
        study = patient.studies.setdefault(
            instance.study_uid,
            _StudyAccumulator(
                study_uid=instance.study_uid,
                study_date=instance.study_date,
                study_id=instance.study_id,
                description=instance.study_description,
            ),
        )
        series = study.series.setdefault(
            instance.series_uid,
            _SeriesAccumulator(
                series_uid=instance.series_uid,
                series_number=instance.series_number,
                modality=instance.modality,
                description=instance.series_description,
            ),
        )
        series.images.append(
            Image(
                path=instance.path,
                instance_number=instance.instance_number or len(series.images) + 1,
                sop_instance_uid=instance.sop_uid,
            )
        )


def _read_header(path: Path) -> Any | None:
    """Read only a file's DICOM header, or ``None`` if it is not usable."""
    import importlib  # lazy import keeps startup fast

    pydicom = importlib.import_module("pydicom")
    try:
        return pydicom.dcmread(path, stop_before_pixels=True, defer_size="1 KB")
    except Exception:  # malformed files can raise arbitrary pydicom errors
        logger.debug("Skipping non-DICOM or unreadable file: {}", path)
        return None


def _build_tree(
    folder: Path,
    patients: dict[str, _PatientAccumulator],
    invalid_files: int,
) -> StudyTree:
    """Convert accumulators into an ordered, immutable study tree."""
    ordered_patients: list[Patient] = []
    for accumulator in patients.values():
        studies: list[Study] = []
        for study_accumulator in sorted(
            accumulator.studies.values(), key=_study_sort_key, reverse=True
        ):
            series: list[Series] = []
            for series_accumulator in sorted(
                study_accumulator.series.values(), key=_series_sort_key
            ):
                images: list[Image] = sorted(
                    series_accumulator.images, key=lambda image: image.instance_number
                )
                series.append(
                    Series(
                        series_instance_uid=series_accumulator.series_uid,
                        modality=series_accumulator.modality,
                        series_number=series_accumulator.series_number or 0,
                        description=series_accumulator.description,
                        images=tuple(images),
                    )
                )
            studies.append(
                Study(
                    study_instance_uid=study_accumulator.study_uid,
                    study_date=study_accumulator.study_date,
                    study_id=study_accumulator.study_id,
                    description=study_accumulator.description,
                    series=tuple(series),
                )
            )
        ordered_patients.append(
            Patient(
                patient_id=accumulator.patient_id or "",
                name=accumulator.name,
                birth_date=accumulator.birth_date,
                sex=accumulator.sex,
                studies=tuple(studies),
            )
        )
    ordered_patients.sort(key=_patient_sort_key)
    return StudyTree(folder, tuple(ordered_patients), invalid_files)


def _study_sort_key(study: _StudyAccumulator) -> str:
    """Sort studies by date, with missing dates last when descending."""
    return study.study_date


def _series_sort_key(series: _SeriesAccumulator) -> int:
    """Sort series by number, with missing numbers last."""
    return series.series_number if series.series_number is not None else _MAX_INT


def _patient_sort_key(patient: Patient) -> tuple[str, str]:
    """Sort patients by name, then by ID."""
    return patient.name.casefold(), patient.patient_id.casefold()


class _Instance:
    """Intermediate metadata for one validated DICOM file."""

    __slots__ = (
        "instance_number",
        "modality",
        "path",
        "patient_birth_date",
        "patient_id",
        "patient_name",
        "patient_sex",
        "series_description",
        "series_number",
        "series_uid",
        "sop_uid",
        "study_date",
        "study_description",
        "study_id",
        "study_uid",
    )

    def __init__(
        self,
        *,
        path: Path,
        patient_id: str,
        patient_name: str,
        patient_birth_date: str,
        patient_sex: str,
        study_uid: str,
        study_date: str,
        study_id: str,
        study_description: str,
        series_uid: str,
        series_number: int | None,
        modality: str,
        series_description: str,
        instance_number: int | None,
        sop_uid: str | None,
    ) -> None:
        self.path = path
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.patient_birth_date = patient_birth_date
        self.patient_sex = patient_sex
        self.study_uid = study_uid
        self.study_date = study_date
        self.study_id = study_id
        self.study_description = study_description
        self.series_uid = series_uid
        self.series_number = series_number
        self.modality = modality
        self.series_description = series_description
        self.instance_number = instance_number
        self.sop_uid = sop_uid


class _PatientAccumulator:
    """Mutable accumulation target for one patient."""

    __slots__ = ("birth_date", "name", "patient_id", "sex", "studies")

    def __init__(
        self,
        *,
        patient_id: str,
        name: str,
        birth_date: str,
        sex: str,
    ) -> None:
        self.patient_id = patient_id
        self.name = name
        self.birth_date = birth_date
        self.sex = sex
        self.studies: dict[str, _StudyAccumulator] = {}


class _StudyAccumulator:
    """Mutable accumulation target for one study."""

    __slots__ = ("description", "series", "study_date", "study_id", "study_uid")

    def __init__(
        self,
        *,
        study_uid: str,
        study_date: str,
        study_id: str,
        description: str,
    ) -> None:
        self.study_uid = study_uid
        self.study_date = study_date
        self.study_id = study_id
        self.description = description
        self.series: dict[str, _SeriesAccumulator] = {}


class _SeriesAccumulator:
    """Mutable accumulation target for one series."""

    __slots__ = ("description", "images", "modality", "series_number", "series_uid")

    def __init__(
        self,
        *,
        series_uid: str,
        series_number: int | None,
        modality: str,
        description: str,
    ) -> None:
        self.series_uid = series_uid
        self.series_number = series_number
        self.modality = modality
        self.description = description
        self.images: list[Image] = []


_MAX_INT = 1 << 62


def _text(dataset: Any, tag: tuple[int, int]) -> str:
    """Return a tag value as text, or an empty string when absent."""
    element = dataset.get(tag)
    if element is None or element.value is None:
        return ""
    value = element.value
    if isinstance(value, bytes):
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _int(dataset: Any, tag: tuple[int, int]) -> int | None:
    """Return an integer tag value, or ``None`` when absent or malformed."""
    value = _text(dataset, tag)
    try:
        return int(float(value)) if value else None
    except ValueError:
        return None
