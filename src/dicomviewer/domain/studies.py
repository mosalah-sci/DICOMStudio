"""Discovered DICOM study catalog.

Pure data describing the patient/study/series/image hierarchy found by a
scanner. The model carries no DICOM parsing or persistence concerns so it can
be shared by every layer without coupling to Infrastructure.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Image:
    """A single DICOM instance in a series."""

    path: Path
    instance_number: int
    sop_instance_uid: str | None = None
    # Geometry metadata used for physically meaningful slice ordering.
    # ``position`` is ImagePositionPatient (x, y, z) in mm;
    # ``orientation`` is ImageOrientationPatient's six direction cosines
    # (row x/y/z, column x/y/z); ``slice_location`` is the standalone
    # (0020,1041) value. All three are optional and fall back to
    # InstanceNumber-based ordering when absent.
    position: tuple[float, float, float] | None = None
    orientation: tuple[float, ...] | None = None
    slice_location: float | None = None


@dataclass(frozen=True)
class Series:
    """A series inside a study, with its ordered images."""

    series_instance_uid: str
    modality: str
    series_number: int
    description: str
    images: tuple[Image, ...] = ()
    body_part: str = ""

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


# ---------------------------------------------------------------------------
# Slice ordering (v1.4 M2)
# ---------------------------------------------------------------------------

# Parallelism tolerance for slice normals: |dot(n_i, n_0) - 1| must stay
# below this bound for the geometry tier to apply to a whole series.
_NORMAL_PARALLEL_TOLERANCE = 1e-3
# A direction-cosine triplet must be (close to) unit length to define a
# trustworthy normal.
_NORMAL_UNIT_TOLERANCE = 1e-3


def _slice_normal(orientation: tuple[float, ...] | None) -> tuple[float, float, float] | None:
    """Return the unit slice normal for ``orientation``, or ``None``.

    The normal is the cross product of the row and column direction cosines
    (ImageOrientationPatient). Degenerate or non-unit inputs are rejected so
    malformed geometry falls back instead of producing arbitrary order.
    """
    if orientation is None or len(orientation) < 6:
        return None
    row = orientation[0:3]
    column = orientation[3:6]
    normal = (
        row[1] * column[2] - row[2] * column[1],
        row[2] * column[0] - row[0] * column[2],
        row[0] * column[1] - row[1] * column[0],
    )
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if abs(length - 1.0) > _NORMAL_UNIT_TOLERANCE:
        return None
    return normal


def sort_series_images(images: Sequence[Image]) -> tuple[Image, ...]:
    """Return ``images`` in display order using a tiered, deterministic policy.

    Tiers (first applicable wins; every tier is deterministic):

    1. **Geometry**: when *every* image carries ImagePositionPatient and
       ImageOrientationPatient, and all slice normals are unit-length and
       mutually parallel, images are ordered by their projection onto that
       normal — i.e. physical position along the slice axis. Ties (duplicate
       positions) break by InstanceNumber, then by path.
    2. **SliceLocation**: otherwise, when *every* image carries (0020,1041),
       order by it with the same tie-breakers.
    3. **InstanceNumber**: otherwise the legacy behavior applies — sort by
       InstanceNumber, stable on ties (preserving file/discovery order).

    Partially-geometried series deliberately fall through to a later tier:
    mixing positioned and unpositioned slices cannot be ordered safely, and
    guessing would risk silently interleaving unrelated content.
    """
    ordered = list(images)
    if len(ordered) <= 1:
        return tuple(ordered)

    fully_positioned = all(
        image.position is not None and image.orientation is not None for image in ordered
    )
    if fully_positioned:
        reference = _slice_normal(ordered[0].orientation)
        if reference is not None and all(
            _normals_parallel(reference, _slice_normal(image.orientation)) for image in ordered[1:]
        ):

            def geometry_key(image: Image) -> tuple[float, int, str]:
                position = image.position
                assert position is not None
                projection = sum(
                    component * axis for component, axis in zip(position, reference, strict=True)
                )
                return (projection, image.instance_number, str(image.path))

            return tuple(sorted(ordered, key=geometry_key))

    if all(image.slice_location is not None for image in ordered):

        def location_key(image: Image) -> tuple[float, int, str]:
            location = image.slice_location
            assert location is not None
            return (location, image.instance_number, str(image.path))

        return tuple(sorted(ordered, key=location_key))

    return tuple(sorted(ordered, key=lambda image: image.instance_number))


def _normals_parallel(
    first: tuple[float, float, float] | None,
    second: tuple[float, float, float] | None,
) -> bool:
    """Return whether two unit normals point along the same axis."""
    if first is None or second is None:
        return False
    dot = first[0] * second[0] + first[1] * second[1] + first[2] * second[2]
    return abs(dot - 1.0) <= _NORMAL_PARALLEL_TOLERANCE
