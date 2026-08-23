"""Tests for viewer overlay formatting helpers."""

from __future__ import annotations

from dicomviewer.domain.viewport import Viewport
from dicomviewer.presentation.widgets.viewer_overlays import (
    SeriesOverlayInfo,
    orientation_badges,
    patient_lines,
    study_lines,
    technical_line,
)

_INFO = SeriesOverlayInfo(
    patient_name="DOE^JOHN",
    patient_id="P-1",
    birth_date="1980-01-01",
    patient_sex="M",
    study_description="Chest exam",
    series_description="Axial 2mm",
    modality="ct",
    body_part="CHEST",
    series_number=3,
)


def test_patient_lines_combine_name_and_id() -> None:
    assert patient_lines(_INFO) == ("DOE^JOHN  [P-1]", "1980-01-01  M")


def test_patient_lines_skip_missing_fields() -> None:
    empty = SeriesOverlayInfo()
    assert patient_lines(empty) == ()
    partial = SeriesOverlayInfo(patient_id="P-9")
    assert patient_lines(partial) == ("[P-9]",)


def test_study_lines_include_descriptions_and_identity() -> None:
    lines = study_lines(_INFO)
    assert lines == ("Chest exam", "Axial 2mm", "Ser 3 · CT · CHEST")


def test_study_lines_skip_missing_fields() -> None:
    bare = SeriesOverlayInfo(series_number=None)
    assert study_lines(bare) == ()


def test_orientation_badges_reflect_the_viewport() -> None:
    viewport = Viewport.initial()
    assert orientation_badges(viewport) == ()
    rotated = viewport.rotate_cw().rotate_cw().toggle_flip_v().toggle_invert()
    assert orientation_badges(rotated) == ("Rot 180°", "Flip V", "Inverted")


def test_technical_line_reports_window_slice_and_zoom() -> None:
    auto = technical_line(Viewport.initial(), 5, 125.0)
    assert auto == "W/L: Auto   1 / 5   125%"
    windowed = technical_line(Viewport.initial().with_window(40.0, 400.0).with_slice(2, 5), 5, 50.0)
    assert windowed == "W: 400 L: 40   3 / 5   50%"


def test_technical_line_handles_empty_series() -> None:
    line = technical_line(Viewport.initial(), 0, 100.0)
    assert "/ " not in line
    assert line.endswith("100%")
