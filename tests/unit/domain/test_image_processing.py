"""Tests for clinical window presets."""

from __future__ import annotations

from dicomviewer.domain.image_processing import (
    WINDOW_PRESETS,
    WindowPreset,
    find_window_preset,
)


def test_catalog_contains_the_expected_core_presets() -> None:
    names = {preset.name for preset in WINDOW_PRESETS}
    assert {"CT Brain", "CT Bone", "CT Lung", "CT Soft Tissue", "CT Abdomen"} <= names


def test_presets_have_positive_widths() -> None:
    assert all(preset.width > 0 for preset in WINDOW_PRESETS)


def test_presets_are_frozen_values() -> None:
    preset = WindowPreset("CT Brain", 40.0, 80.0)
    assert preset.center == 40.0
    assert preset.width == 80.0
    assert preset.name == "CT Brain"


def test_find_window_preset_looks_up_by_name() -> None:
    preset = find_window_preset("CT Lung")
    assert preset is not None
    assert preset.center == -500.0
    assert preset.width == 1500.0


def test_find_window_preset_returns_none_for_unknown() -> None:
    assert find_window_preset("Not A Preset") is None
