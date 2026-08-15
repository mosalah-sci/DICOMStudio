"""Tests for the domain settings model."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.domain.settings import (
    MAX_RECENT_FOLDERS,
    MAX_SIDEBAR_WIDTH,
    MIN_SIDEBAR_WIDTH,
    AppearanceSettings,
    LoggingSettings,
    MeasurementSettings,
    RecentFoldersSettings,
    Settings,
    SettingsError,
    ViewingSettings,
    WorkspaceSettings,
)


def test_appearance_defaults_to_dark() -> None:
    assert AppearanceSettings().theme == "dark"


def test_theme_is_normalized_to_lowercase() -> None:
    assert AppearanceSettings.from_mapping({"theme": "LIGHT"}).theme == "light"


def test_unknown_theme_is_rejected() -> None:
    with pytest.raises(SettingsError):
        AppearanceSettings.from_mapping({"theme": "solarized"})


def test_settings_from_mapping_merges_sections() -> None:
    settings = Settings.from_mapping(
        {"logging": {"level": "DEBUG"}, "appearance": {"theme": "light"}}
    )
    assert settings.logging.level == "DEBUG"
    assert settings.appearance.theme == "light"


def test_settings_to_mapping_round_trips() -> None:
    settings = Settings(
        logging=LoggingSettings(level="DEBUG"),
        appearance=AppearanceSettings(theme="light"),
    )
    rebuilt = Settings.from_mapping(settings.to_mapping())
    assert rebuilt == settings


def test_settings_defaults_include_new_sections() -> None:
    settings = Settings(logging=LoggingSettings())
    assert settings.recent.folders == ()
    assert settings.viewing.max_cache_size == 3
    assert settings.measurements.color == "#22d3ee"


def test_settings_round_trip_preserves_all_sections() -> None:
    settings = Settings(
        logging=LoggingSettings(level="DEBUG"),
        appearance=AppearanceSettings(theme="light"),
        recent=RecentFoldersSettings(folders=(Path("a"), Path("b"))),
        viewing=ViewingSettings(default_window_preset="CT Lung", max_cache_size=6),
        measurements=MeasurementSettings(color="#ff0000"),
    )
    rebuilt = Settings.from_mapping(settings.to_mapping())
    assert rebuilt == settings


def test_recent_folders_default_to_empty() -> None:
    assert RecentFoldersSettings().folders == ()


def test_recent_folders_are_normalized_and_deduplicated() -> None:
    settings = RecentFoldersSettings.from_mapping({"folders": ["C:\\a", "C:\\a", "C:\\b"]})
    assert settings.folders == (Path("C:\\a"), Path("C:\\b"))


def test_recent_folders_add_moves_to_front() -> None:
    settings = RecentFoldersSettings(folders=(Path("a"), Path("b")))
    updated = settings.add(Path("b")).add(Path("c"))
    assert updated.folders == (Path("c"), Path("b"), Path("a"))


def test_recent_folders_are_capped() -> None:
    settings = RecentFoldersSettings()
    for index in range(MAX_RECENT_FOLDERS + 5):
        settings = settings.add(Path(f"folder{index}"))
    assert len(settings.folders) == MAX_RECENT_FOLDERS


def test_recent_folders_remove_and_clear() -> None:
    settings = RecentFoldersSettings(folders=(Path("a"), Path("b")))
    assert settings.remove(Path("a")).folders == (Path("b"),)
    assert settings.clear().folders == ()


def test_recent_folders_reject_non_string_entries() -> None:
    with pytest.raises(SettingsError):
        RecentFoldersSettings.from_mapping({"folders": [123]})


def test_viewing_settings_have_sane_defaults() -> None:
    viewing = ViewingSettings()
    assert viewing.default_window_preset == ""
    assert viewing.max_cache_size == 3
    assert viewing.smooth_scaling is True
    assert viewing.show_statistics_overlay is True
    assert viewing.show_measurement_overlay is True


def test_viewing_preset_accepts_known_name_and_empty() -> None:
    assert (
        ViewingSettings.from_mapping({"default_window_preset": "CT Lung"}).default_window_preset
        == "CT Lung"
    )
    assert ViewingSettings.from_mapping({"default_window_preset": ""}).default_window_preset == ""


def test_viewing_preset_rejects_unknown_name() -> None:
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"default_window_preset": "Nonsense"})


def test_viewing_cache_size_is_validated() -> None:
    assert ViewingSettings.from_mapping({"max_cache_size": 8}).max_cache_size == 8
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"max_cache_size": 0})
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"max_cache_size": "big"})


def test_viewing_booleans_are_validated() -> None:
    assert ViewingSettings.from_mapping({"smooth_scaling": False}).smooth_scaling is False
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"smooth_scaling": "yes"})


def test_measurement_color_is_normalized_to_lowercase() -> None:
    assert MeasurementSettings.from_mapping({"color": "#FF0000"}).color == "#ff0000"


def test_measurement_color_rejects_invalid_hex() -> None:
    with pytest.raises(SettingsError):
        MeasurementSettings.from_mapping({"color": "red"})
    with pytest.raises(SettingsError):
        MeasurementSettings.from_mapping({"color": "#12"})


def test_workspace_defaults_show_both_sidebars() -> None:
    workspace = WorkspaceSettings()
    assert workspace.study_explorer_visible is True
    assert workspace.metadata_visible is True
    assert workspace.study_explorer_width == 260
    assert workspace.metadata_width == 300


def test_workspace_round_trips_through_mapping() -> None:
    workspace = WorkspaceSettings(
        study_explorer_visible=False,
        metadata_visible=False,
        study_explorer_width=340,
        metadata_width=420,
    )
    assert WorkspaceSettings.from_mapping(workspace.to_mapping()) == workspace


def test_workspace_booleans_are_validated() -> None:
    assert (
        WorkspaceSettings.from_mapping({"study_explorer_visible": False}).study_explorer_visible
        is False
    )
    with pytest.raises(SettingsError):
        WorkspaceSettings.from_mapping({"metadata_visible": "no"})


def test_workspace_widths_are_bounded() -> None:
    assert (
        WorkspaceSettings.from_mapping(
            {"study_explorer_width": MIN_SIDEBAR_WIDTH - 5}
        ).study_explorer_width
        == MIN_SIDEBAR_WIDTH
    )
    assert (
        WorkspaceSettings.from_mapping(
            {"study_explorer_width": MAX_SIDEBAR_WIDTH + 5}
        ).study_explorer_width
        == MAX_SIDEBAR_WIDTH
    )
    assert WorkspaceSettings.from_mapping({"metadata_width": 200}).metadata_width == 200


def test_workspace_widths_reject_non_integers() -> None:
    with pytest.raises(SettingsError):
        WorkspaceSettings.from_mapping({"study_explorer_width": "wide"})


def test_settings_round_trip_preserves_workspace() -> None:
    settings = Settings(
        logging=LoggingSettings(),
        workspace=WorkspaceSettings(
            study_explorer_visible=False,
            metadata_width=500,
        ),
    )
    rebuilt = Settings.from_mapping(settings.to_mapping())
    assert rebuilt == settings
    assert rebuilt.workspace.study_explorer_visible is False
    assert rebuilt.workspace.metadata_width == 500
