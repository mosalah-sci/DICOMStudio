"""Tests for the pydicom study scanner."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydicom.uid import generate_uid

from dicomviewer.application.discovery import DiscoveryError
from dicomviewer.infrastructure.dicom.scanner import PydicomStudyScanner
from tests.dicom_utils import write_ct_dataset


@pytest.fixture
def scanner() -> PydicomStudyScanner:
    """Provide a fresh scanner per test."""
    return PydicomStudyScanner()


def _build_folder(root: Path) -> Path:
    """Create a nested folder of DICOM files plus some invalid ones."""
    folder = root / "studies"
    patient_a = folder / "P1"
    patient_b = folder / "P2"
    patient_a.mkdir(parents=True)
    patient_b.mkdir(parents=True)
    (patient_a / "nested").mkdir(parents=True)

    study_1 = generate_uid()
    study_2 = generate_uid()
    series_ct = generate_uid()
    series_us = generate_uid()
    series_mg = generate_uid()

    write_ct_dataset(
        patient_a / "a1.dcm",
        patient_id="P1",
        patient_name="DOE^JOHN",
        study_uid=study_1,
        series_uid=series_ct,
        sop_uid=generate_uid(),
        modality="CT",
        instance_number=2,
        study_date="20260102",
        study_description="Chest",
    )
    write_ct_dataset(
        patient_a / "a2.dcm",
        patient_id="P1",
        patient_name="DOE^JOHN",
        study_uid=study_1,
        series_uid=series_ct,
        sop_uid=generate_uid(),
        modality="CT",
        instance_number=1,
        study_date="20260102",
        study_description="Chest",
    )
    write_ct_dataset(
        patient_a / "nested" / "a3.dcm",
        patient_id="P1",
        patient_name="DOE^JOHN",
        study_uid=study_2,
        series_uid=series_us,
        sop_uid=generate_uid(),
        modality="US",
        instance_number=1,
        study_date="20260101",
    )
    write_ct_dataset(
        patient_a / "a4.dcm",
        patient_id="P1",
        patient_name="DOE^JOHN",
        study_uid=study_1,
        series_uid=series_mg,
        sop_uid=generate_uid(),
        modality="MG",
        instance_number=1,
        study_date="20260102",
    )
    write_ct_dataset(
        patient_b / "b1.dcm",
        patient_id="P2",
        patient_name="SMITH^JANE",
        study_uid=study_1,
        series_uid=series_ct,
        sop_uid=generate_uid(),
        modality="CT",
        instance_number=1,
        study_date="20260103",
    )

    (patient_a / "notes.txt").write_text("not a dicom file")
    (patient_a / "corrupt.dcm").write_bytes(b"\x01\x02not a real dicom file")

    return folder


def test_scan_groups_patients_studies_and_series(
    scanner: PydicomStudyScanner, tmp_path: Path
) -> None:
    folder = _build_folder(tmp_path)
    tree = scanner.scan(folder)

    assert tree.root_folder == folder
    assert tree.patient_count == 2
    assert tree.study_count == 3
    assert tree.series_count == 4
    assert tree.image_count == 5
    assert tree.invalid_files == 1

    patients = {patient.patient_id: patient for patient in tree.patients}
    john = patients["P1"]
    assert john.name == "DOE^JOHN"
    assert john.study_count == 2
    assert len(john.studies[0].series) == 2
    assert john.studies[0].series[0].modality == "CT"
    assert [image.instance_number for image in john.studies[0].series[0].images] == [1, 2]


def test_scan_finds_files_in_subfolders(scanner: PydicomStudyScanner, tmp_path: Path) -> None:
    folder = _build_folder(tmp_path)
    tree = scanner.scan(folder)
    paths = {
        image.path
        for patient in tree.patients
        for study in patient.studies
        for series in study.series
        for image in series.images
    }
    assert any("nested" in str(path) for path in paths)


def test_scan_sorts_studies_by_date_descending(
    scanner: PydicomStudyScanner, tmp_path: Path
) -> None:
    folder = _build_folder(tmp_path)
    tree = scanner.scan(folder)
    john = next(p for p in tree.patients if p.patient_id == "P1")
    dates = [study.study_date for study in john.studies]
    assert dates == sorted(dates, reverse=True)


def test_scan_ignores_files_missing_grouping_tags(
    scanner: PydicomStudyScanner, tmp_path: Path
) -> None:
    folder = tmp_path / "incomplete"
    folder.mkdir()
    write_ct_dataset(
        folder / "no-modality.dcm",
        patient_id="P1",
        patient_name="X",
        study_uid=generate_uid(),
        series_uid=generate_uid(),
        sop_uid=generate_uid(),
        modality="",
        instance_number=1,
    )
    tree = scanner.scan(folder)
    assert not tree.has_content()
    assert tree.invalid_files == 1


def test_scan_can_be_cancelled(scanner: PydicomStudyScanner, tmp_path: Path) -> None:
    folder = _build_folder(tmp_path)
    tree = scanner.scan(folder, should_cancel=lambda: True)
    assert tree.patients == ()


def test_scan_reports_throttled_progress(scanner: PydicomStudyScanner, tmp_path: Path) -> None:
    folder = _build_folder(tmp_path)
    reports: list[tuple[int, int]] = []
    tree = scanner.scan(
        folder, on_progress=lambda scanned, invalid: reports.append((scanned, invalid))
    )
    assert reports
    # 5 valid instances + 1 corrupt candidate; the text file is filtered by
    # extension and never counted. The final report reflects the totals.
    assert reports[-1] == (6, 1)
    assert tree.invalid_files == 1


def test_scan_reports_progress_even_with_no_valid_files(
    scanner: PydicomStudyScanner,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "junk"
    folder.mkdir()
    (folder / "corrupt.dcm").write_bytes(b"\x01\x02not a real dicom file")
    reports: list[tuple[int, int]] = []
    scanner.scan(folder, on_progress=lambda scanned, invalid: reports.append((scanned, invalid)))
    assert reports == [(1, 1)]


def test_scan_raises_for_missing_folder(scanner: PydicomStudyScanner, tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError):
        scanner.scan(tmp_path / "does-not-exist")
