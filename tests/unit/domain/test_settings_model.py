"""Tests for the domain settings model."""

from __future__ import annotations

from pathlib import Path

import pytest

from dicomviewer.domain.image_processing import WindowPreset
from dicomviewer.domain.settings import (
    MAX_CINE_FPS,
    MAX_CUSTOM_PRESETS,
    MAX_RECENT_FOLDERS,
    MAX_SIDEBAR_WIDTH,
    MIN_CINE_FPS,
    MIN_SIDEBAR_WIDTH,
    AppearanceSettings,
    LoggingSettings,
    MeasurementSettings,
    PresetsSettings,
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


def test_viewing_info_overlay_defaults_on_and_validates() -> None:
    assert ViewingSettings().show_info_overlay is True
    assert ViewingSettings.from_mapping({"show_info_overlay": False}).show_info_overlay is False
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"show_info_overlay": "no"})


def test_viewing_cine_fps_clamps_to_supported_range() -> None:
    assert ViewingSettings().cine_fps == 15
    assert ViewingSettings.from_mapping({"cine_fps": 30}).cine_fps == 30
    assert ViewingSettings.from_mapping({"cine_fps": MIN_CINE_FPS - 5}).cine_fps == MIN_CINE_FPS
    assert ViewingSettings.from_mapping({"cine_fps": MAX_CINE_FPS + 5}).cine_fps == MAX_CINE_FPS
    with pytest.raises(SettingsError):
        ViewingSettings.from_mapping({"cine_fps": "fast"})


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


def test_custom_presets_default_to_empty() -> None:
    assert PresetsSettings().custom == ()


def test_custom_presets_round_trip_through_mapping() -> None:
    presets = PresetsSettings(
        custom=(WindowPreset("My Liver", 30.0, 200.0), WindowPreset("Narrow", -20, 5))
    )
    assert PresetsSettings.from_mapping(presets.to_mapping()) == presets


def test_custom_presets_names_are_stripped_and_deduplicated() -> None:
    presets = PresetsSettings.from_mapping(
        {
            "custom": [
                {"name": "  Liver  ", "center": 30, "width": 200},
                {"name": "Liver", "center": 99, "width": 99},
            ]
        }
    )
    assert len(presets.custom) == 1
    assert presets.custom[0].name == "Liver"
    assert presets.custom[0].center == 30.0


def test_custom_presets_reject_bad_entries() -> None:
    with pytest.raises(SettingsError):
        PresetsSettings.from_mapping({"custom": [{"name": "", "center": 0, "width": 10}]})
    with pytest.raises(SettingsError):
        PresetsSettings.from_mapping({"custom": [{"name": "X", "center": "a", "width": 10}]})
    with pytest.raises(SettingsError):
        PresetsSettings.from_mapping({"custom": [{"name": "X", "center": 0, "width": 0}]})
    with pytest.raises(SettingsError):
        PresetsSettings.from_mapping({"custom": ["not a mapping"]})
    with pytest.raises(SettingsError):
        PresetsSettings.from_mapping({"custom": "nope"})


def test_custom_presets_are_capped() -> None:
    entries = [{"name": f"Preset {index}", "center": index, "width": 100} for index in range(64)]
    presets = PresetsSettings.from_mapping({"custom": entries})
    assert len(presets.custom) == MAX_CUSTOM_PRESETS


def test_custom_presets_upsert_and_remove_and_find() -> None:
    presets = PresetsSettings()
    first = WindowPreset("Liver", 30.0, 200.0)
    presets = presets.upsert(first)
    assert presets.find("Liver") == first
    revised = WindowPreset("Liver", 40.0, 150.0)
    presets = presets.upsert(revised)
    assert presets.custom == (revised,)
    assert presets.remove("Liver").custom == ()
    assert presets.remove("Missing") == presets


def test_settings_round_trip_preserves_presets() -> None:
    settings = Settings(
        logging=LoggingSettings(),
        presets=PresetsSettings(custom=(WindowPreset("Dense", 800.0, 2500.0),)),
    )
    rebuilt = Settings.from_mapping(settings.to_mapping())
    assert rebuilt == settings
