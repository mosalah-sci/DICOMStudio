"""Discovered DICOM study catalog.

Pure data describing the patient/study/series/image hierarchy found by a
scanner. The model carries no DICOM parsing or persistence concerns so it can
be shared by every layer without coupling to Infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Image:
    """A single DICOM instance in a series."""

    path: Path
    instance_number: int
    sop_instance_uid: str | None = None


@dataclass(frozen=True)
class Series:
    """A series inside a study, with its ordered images."""

    series_instance_uid: str
    modality: str
    series_number: int
    description: str
    images: tuple[Image, ...] = ()

    @property
    def image_count(self) -> int:
        """Return the number of images in the series."""
        return len(self.images)


@dataclass(frozen=True)
class Study:
    """A study inside a patient, with its ordered series."""

    study_instance_uid: str
    study_date: str
    study_id: str
    description: str
    series: tuple[Series, ...] = ()

    @property
    def series_count(self) -> int:
        """Return the number of series in the study."""
        return len(self.series)

    @property
    def image_count(self) -> int:
        """Return the total number of images across all series."""
        return sum(series.image_count for series in self.series)


@dataclass(frozen=True)
class Patient:
    """A patient with their ordered studies."""

    patient_id: str
    name: str
    birth_date: str
    sex: str
    studies: tuple[Study, ...] = ()

    @property
    def study_count(self) -> int:
        """Return the number of studies for the patient."""
        return len(self.studies)

    @property
    def image_count(self) -> int:
        """Return the total number of images across all studies."""
        return sum(study.image_count for study in self.studies)


@dataclass(frozen=True)
class StudyTree:
    """The full discovered hierarchy for a scanned folder."""

    root_folder: Path
    patients: tuple[Patient, ...] = ()
    invalid_files: int = 0

    @classmethod
    def empty(cls, root_folder: Path) -> StudyTree:
        """Return a tree with no patients, used as the initial state."""
        return cls(root_folder=root_folder)

    @property
    def patient_count(self) -> int:
        """Return the number of patients in the tree."""
        return len(self.patients)

    @property
    def study_count(self) -> int:
        """Return the total number of studies in the tree."""
        return sum(patient.study_count for patient in self.patients)

    @property
    def series_count(self) -> int:
        """Return the total number of series in the tree."""
        return sum(study.series_count for patient in self.patients for study in patient.studies)

    @property
    def image_count(self) -> int:
        """Return the total number of images in the tree."""
        return sum(patient.image_count for patient in self.patients)

    def has_content(self) -> bool:
        """Return whether any valid DICOM study was discovered."""
        return len(self.patients) > 0

    def find_series_context(self, series_uid: str) -> tuple[Patient, Study] | None:
        """Return the ``(patient, study)`` owning ``series_uid``, or ``None``.

        The series instance UID identifies a series within the discovered
        catalog; the first match in patient and study order wins.
        """
        for patient in self.patients:
            for study in patient.studies:
                if any(member.series_instance_uid == series_uid for member in study.series):
                    return patient, study
        return None
