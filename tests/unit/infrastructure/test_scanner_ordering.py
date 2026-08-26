"""Scanner-level ordering and body-part propagation tests (v1.4 M2).

These verify the full scan path: DICOM geometry tags are parsed from real
files, carried through the metadata carrier, and applied by the domain
ordering policy. Exact resulting order is asserted, never just scan success.
"""

from __future__ import annotations

from pathlib import Path

from dicomviewer.infrastructure.dicom.scanner import PydicomStudyScanner

_AXIAL = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def _write(
    name: str,
    path: Path,
    *,
    number: int,
    position: tuple[float, float, float] | None = None,
    orientation: tuple[float, ...] | None = None,
    location: float | None = None,
    body_part: str = "",
) -> None:
    from tests.dicom_utils import write_ct_dataset

    write_ct_dataset(
        path,
        patient_id="P1",
        patient_name="DOE^A",
        study_uid="st-1",
        series_uid="se-1",
        sop_uid=f"sop-{name}",
        modality="CT",
        instance_number=number,
        image_position=position,
        image_orientation=orientation,
        slice_location=location,
        body_part=body_part,
    )


def _scan(folder: Path):
    return PydicomStudyScanner().scan(folder)


def test_shuffled_files_are_reordered_by_geometry(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    # Written in reverse physical order; instance numbers deliberately
    # agree with write order (1,2,3) and contradict the geometry, proving
    # the geometry tier decides.
    for index, z in enumerate((30.0, 20.0, 10.0), start=1):
        _write(
            f"s{index}",
            folder / f"s{index}.dcm",
            number=index,
            position=(0.0, 0.0, z),
            orientation=_AXIAL,
        )

    tree = _scan(folder)

    series = tree.patients[0].studies[0].series[0]
    assert [image.path.name for image in series.images] == ["s3.dcm", "s2.dcm", "s1.dcm"]
    assert [image.instance_number for image in series.images] == [3, 2, 1]


def test_missing_geometry_falls_back_to_instance_numbers(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    _write("c", folder / "c.dcm", number=3, position=None, orientation=None, location=None)
    _write("a", folder / "a.dcm", number=1, position=None, orientation=None, location=None)
    _write("b", folder / "b.dcm", number=2, position=None, orientation=None, location=None)

    series = _scan(folder).patients[0].studies[0].series[0]
    assert [image.path.name for image in series.images] == ["a.dcm", "b.dcm", "c.dcm"]


def test_slice_location_orders_when_geometry_absent(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    _write("l50", folder / "l50.dcm", number=1, location=50.0)
    _write("l10", folder / "l10.dcm", number=2, location=10.0)

    series = _scan(folder).patients[0].studies[0].series[0]
    assert [image.path.name for image in series.images] == ["l10.dcm", "l50.dcm"]


def test_mixed_geometry_and_non_geometry_never_interleaves(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    # Positioned file has a large z but a small instance number; the legacy
    # tier must win so the positioned slice is not moved by its geometry.
    _write("geo", folder / "geo.dcm", number=2, position=(0.0, 0.0, 90.0), orientation=_AXIAL)
    _write("plain", folder / "plain.dcm", number=1)

    series = _scan(folder).patients[0].studies[0].series[0]
    assert [image.path.name for image in series.images] == ["plain.dcm", "geo.dcm"]


def test_duplicate_positions_keep_instance_order(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    _write("dup_b", folder / "dup_b.dcm", number=9, position=(0.0, 0.0, 4.0), orientation=_AXIAL)
    _write("dup_a", folder / "dup_a.dcm", number=8, position=(0.0, 0.0, 4.0), orientation=_AXIAL)

    series = _scan(folder).patients[0].studies[0].series[0]
    assert [image.path.name for image in series.images] == ["dup_a.dcm", "dup_b.dcm"]


def test_body_part_examined_propagates_to_series(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    _write(
        "s",
        folder / "s.dcm",
        number=1,
        position=None,
        orientation=None,
        location=None,
        body_part="CHEST",
    )

    series = _scan(folder).patients[0].studies[0].series[0]
    assert series.body_part == "CHEST"


def test_missing_body_part_defaults_to_empty_string(tmp_path: Path) -> None:
    folder = tmp_path / "series"
    folder.mkdir()
    _write("s", folder / "s.dcm", number=1, position=None, orientation=None, location=None)

    series = _scan(folder).patients[0].studies[0].series[0]
    assert series.body_part == ""
