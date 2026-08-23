"""Typed settings model and validation.

The model is pure data and lives in the Domain layer so that every layer can
rely on the same validated configuration snapshot without depending on the
TOML persistence details owned by Infrastructure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from dicomviewer.domain.exceptions import DicomViewerError
from dicomviewer.domain.image_processing import WindowPreset, find_window_preset

VALID_LOG_LEVELS = frozenset({"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"})
VALID_THEMES = frozenset({"dark", "light"})
MAX_RECENT_FOLDERS = 8
MIN_CACHE_SIZE = 1
MAX_CACHE_SIZE = 16
# Cine playback speed bounds in frames per second.
MIN_CINE_FPS = 1
MAX_CINE_FPS = 60
# Sidebar width bounds (pixels). The app persists live dock widths here, so
# values outside this range are clamped to keep the panels usable on any
# monitor size rather than being rejected.
MIN_SIDEBAR_WIDTH = 120
MAX_SIDEBAR_WIDTH = 1200
# Custom window presets are user-defined (center, width) combinations.
MAX_CUSTOM_PRESETS = 32
_MIN_PRESET_WIDTH = 1e-3
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class SettingsError(DicomViewerError):
    """Raised when settings cannot be loaded or validated."""


@dataclass(frozen=True)
class LoggingSettings:
    """Configuration of the logging system."""

    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> LoggingSettings:
        """Build settings from a TOML ``[logging]`` mapping."""
        level = _validate_level(data.get("level", "INFO"))
        rotation = _validate_non_empty("rotation", data.get("rotation", "10 MB"))
        retention = _validate_non_empty("retention", data.get("retention", "7 days"))
        return cls(level=level, rotation=rotation, retention=retention)

    def to_mapping(self) -> dict[str, str]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {"level": self.level, "rotation": self.rotation, "retention": self.retention}


@dataclass(frozen=True)
class AppearanceSettings:
    """Configuration of the user interface appearance."""

    theme: str = "dark"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AppearanceSettings:
        """Build settings from a TOML ``[appearance]`` mapping."""
        theme = _validate_theme(data.get("theme", "dark"))
        return cls(theme=theme)

    def to_mapping(self) -> dict[str, str]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {"theme": self.theme}


@dataclass(frozen=True)
class RecentFoldersSettings:
    """Recently opened study folders, most recent first."""

    folders: tuple[Path, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> RecentFoldersSettings:
        """Build settings from a TOML ``[recent]`` mapping."""
        return cls(folders=_validate_path_list(data.get("folders", ())))

    def to_mapping(self) -> dict[str, list[str]]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {"folders": [str(folder) for folder in self.folders]}

    def add(self, folder: Path) -> RecentFoldersSettings:
        """Return a copy with ``folder`` moved to the front, de-duplicated."""
        folders = [folder, *(item for item in self.folders if item != folder)]
        return RecentFoldersSettings(folders=tuple(folders[:MAX_RECENT_FOLDERS]))

    def remove(self, folder: Path) -> RecentFoldersSettings:
        """Return a copy without ``folder``."""
        return RecentFoldersSettings(folders=tuple(item for item in self.folders if item != folder))

    def clear(self) -> RecentFoldersSettings:
        """Return a copy with no recent folders."""
        return RecentFoldersSettings()


@dataclass(frozen=True)
class ViewingSettings:
    """Default viewer behaviour applied when a series is displayed."""

    default_window_preset: str = ""
    max_cache_size: int = 3
    smooth_scaling: bool = True
    show_statistics_overlay: bool = True
    show_measurement_overlay: bool = True
    show_info_overlay: bool = True
    cine_fps: int = 15

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ViewingSettings:
        """Build settings from a TOML ``[viewing]`` mapping."""
        return cls(
            default_window_preset=_validate_preset(data.get("default_window_preset", "")),
            max_cache_size=_validate_cache_size(data.get("max_cache_size", 3)),
            smooth_scaling=_validate_bool("smooth_scaling", data.get("smooth_scaling", True)),
            show_statistics_overlay=_validate_bool(
                "show_statistics_overlay", data.get("show_statistics_overlay", True)
            ),
            show_measurement_overlay=_validate_bool(
                "show_measurement_overlay", data.get("show_measurement_overlay", True)
            ),
            show_info_overlay=_validate_bool(
                "show_info_overlay", data.get("show_info_overlay", True)
            ),
            cine_fps=_validate_cine_fps(data.get("cine_fps", 15)),
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {
            "default_window_preset": self.default_window_preset,
            "max_cache_size": self.max_cache_size,
            "smooth_scaling": self.smooth_scaling,
            "show_statistics_overlay": self.show_statistics_overlay,
            "show_measurement_overlay": self.show_measurement_overlay,
            "show_info_overlay": self.show_info_overlay,
            "cine_fps": self.cine_fps,
        }


@dataclass(frozen=True)
class PresetsSettings:
    """User-defined window presets persisted across sessions.

    Custom presets live alongside the built-in clinical presets and are
    addressed by name, so entries are de-duplicated by name (first wins)
    and capped at :data:`MAX_CUSTOM_PRESETS`.
    """

    custom: tuple[WindowPreset, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PresetsSettings:
        """Build settings from a TOML ``[presets]`` mapping."""
        return cls(custom=_validate_custom_presets(data.get("custom", ())))

    def to_mapping(self) -> dict[str, Any]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {
            "custom": [
                {"name": preset.name, "center": preset.center, "width": preset.width}
                for preset in self.custom
            ]
        }

    def find(self, name: str) -> WindowPreset | None:
        """Return the custom preset whose name matches, or ``None``."""
        for preset in self.custom:
            if preset.name == name:
                return preset
        return None

    def upsert(self, preset: WindowPreset) -> PresetsSettings:
        """Return a copy with ``preset`` added, or replacing its namesake."""
        remaining = tuple(item for item in self.custom if item.name != preset.name)
        return PresetsSettings(custom=(*remaining, preset)[:MAX_CUSTOM_PRESETS])

    def remove(self, name: str) -> PresetsSettings:
        """Return a copy without the preset named ``name``."""
        return PresetsSettings(custom=tuple(item for item in self.custom if item.name != name))


@dataclass(frozen=True)
class MeasurementSettings:
    """Presentation preferences for measurement overlays."""

    color: str = "#22d3ee"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> MeasurementSettings:
        """Build settings from a TOML ``[measurements]`` mapping."""
        return cls(color=_validate_color(data.get("color", "#22d3ee")))

    def to_mapping(self) -> dict[str, str]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {"color": self.color}


@dataclass(frozen=True)
class WorkspaceSettings:
    """Sidebar visibility and dimensions restored on every launch.

    Only non-sensitive workspace preferences are persisted here; the window
    geometry itself lives in the window-state store as an opaque Qt payload.
    """

    study_explorer_visible: bool = True
    metadata_visible: bool = True
    study_explorer_width: int = 260
    metadata_width: int = 300

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> WorkspaceSettings:
        """Build settings from a TOML ``[workspace]`` mapping."""
        return cls(
            study_explorer_visible=_validate_bool(
                "study_explorer_visible", data.get("study_explorer_visible", True)
            ),
            metadata_visible=_validate_bool("metadata_visible", data.get("metadata_visible", True)),
            study_explorer_width=_validate_sidebar_width(
                "study_explorer_width", data.get("study_explorer_width", 260)
            ),
            metadata_width=_validate_sidebar_width(
                "metadata_width", data.get("metadata_width", 300)
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return the settings as a plain TOML-serializable mapping."""
        return {
            "study_explorer_visible": self.study_explorer_visible,
            "metadata_visible": self.metadata_visible,
            "study_explorer_width": self.study_explorer_width,
            "metadata_width": self.metadata_width,
        }


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the full application configuration."""

    logging: LoggingSettings
    appearance: AppearanceSettings = AppearanceSettings()
    recent: RecentFoldersSettings = RecentFoldersSettings()
    viewing: ViewingSettings = ViewingSettings()
    measurements: MeasurementSettings = MeasurementSettings()
    workspace: WorkspaceSettings = WorkspaceSettings()
    presets: PresetsSettings = PresetsSettings()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Settings:
        """Build the full settings snapshot from a TOML mapping."""
        logging_data = as_str_mapping(data.get("logging"))
        logging_settings = (
            LoggingSettings.from_mapping(logging_data)
            if logging_data is not None
            else LoggingSettings()
        )
        appearance_data = as_str_mapping(data.get("appearance"))
        appearance_settings = (
            AppearanceSettings.from_mapping(appearance_data)
            if appearance_data is not None
            else AppearanceSettings()
        )
        recent_data = as_str_mapping(data.get("recent"))
        recent_settings = (
            RecentFoldersSettings.from_mapping(recent_data)
            if recent_data is not None
            else RecentFoldersSettings()
        )
        viewing_data = as_str_mapping(data.get("viewing"))
        viewing_settings = (
            ViewingSettings.from_mapping(viewing_data)
            if viewing_data is not None
            else ViewingSettings()
        )
        measurements_data = as_str_mapping(data.get("measurements"))
        measurements_settings = (
            MeasurementSettings.from_mapping(measurements_data)
            if measurements_data is not None
            else MeasurementSettings()
        )
        workspace_data = as_str_mapping(data.get("workspace"))
        workspace_settings = (
            WorkspaceSettings.from_mapping(workspace_data)
            if workspace_data is not None
            else WorkspaceSettings()
        )
        presets_data = as_str_mapping(data.get("presets"))
        presets_settings = (
            PresetsSettings.from_mapping(presets_data)
            if presets_data is not None
            else PresetsSettings()
        )
        return cls(
            logging=logging_settings,
            appearance=appearance_settings,
            recent=recent_settings,
            viewing=viewing_settings,
            measurements=measurements_settings,
            workspace=workspace_settings,
            presets=presets_settings,
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return the full settings as a TOML-serializable mapping."""
        return {
            "logging": self.logging.to_mapping(),
            "appearance": self.appearance.to_mapping(),
            "recent": self.recent.to_mapping(),
            "viewing": self.viewing.to_mapping(),
            "measurements": self.measurements.to_mapping(),
            "workspace": self.workspace.to_mapping(),
            "presets": self.presets.to_mapping(),
        }


def as_str_mapping(value: Any) -> Mapping[str, Any] | None:
    """Return a value as a string-keyed mapping, or ``None`` if it is not one."""
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return None


def _validate_level(value: Any) -> str:
    """Normalize and validate a log level name, or reject it."""
    if not isinstance(value, str) or value.upper() not in VALID_LOG_LEVELS:
        raise SettingsError(f"Invalid log level: {value!r}")
    return value.upper()


def _validate_theme(value: Any) -> str:
    """Normalize and validate a theme name, or reject it."""
    if not isinstance(value, str) or value.lower() not in VALID_THEMES:
        raise SettingsError(f"Invalid theme: {value!r}")
    return value.lower()


def _validate_preset(value: Any) -> str:
    """Validate a default window preset name; empty means no preset."""
    if isinstance(value, str) and value == "":
        return ""
    if not isinstance(value, str) or find_window_preset(value) is None:
        raise SettingsError(f"Invalid window preset: {value!r}")
    return value


def _validate_cache_size(value: Any) -> int:
    """Validate and normalize the decode cache size."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"Invalid cache size: {value!r}")
    if not MIN_CACHE_SIZE <= value <= MAX_CACHE_SIZE:
        raise SettingsError(f"Cache size out of range: {value!r}")
    return value


def _validate_bool(field: str, value: Any) -> bool:
    """Reject non-boolean values for boolean settings."""
    if not isinstance(value, bool):
        raise SettingsError(f"Invalid value for '{field}': {value!r}")
    return value


def _validate_sidebar_width(field: str, value: Any) -> int:
    """Validate and clamp a sidebar width in pixels."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"Invalid value for '{field}': {value!r}")
    return min(MAX_SIDEBAR_WIDTH, max(MIN_SIDEBAR_WIDTH, value))


def _validate_color(value: Any) -> str:
    """Validate a #RRGGBB colour string, or reject it."""
    if not isinstance(value, str) or _HEX_COLOR_RE.match(value) is None:
        raise SettingsError(f"Invalid measurement colour: {value!r}")
    return value.lower()


def _validate_path_list(value: Any) -> tuple[Path, ...]:
    """Normalize and validate a list of folder paths."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SettingsError(f"Invalid recent folders list: {value!r}")
    folders: list[Path] = []
    for item in cast(Sequence[Any], value):
        if not isinstance(item, str) or not item.strip():
            raise SettingsError(f"Invalid recent folder entry: {item!r}")
        folder = Path(item)
        if folder not in folders:
            folders.append(folder)
    return tuple(folders[:MAX_RECENT_FOLDERS])


def _validate_non_empty(field: str, value: Any) -> str:
    """Reject blank values for settings that must be non-empty."""
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"Invalid value for '{field}': {value!r}")
    return value


def _validate_cine_fps(value: Any) -> int:
    """Validate and clamp the cine playback speed in frames per second."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"Invalid cine playback speed: {value!r}")
    return min(MAX_CINE_FPS, max(MIN_CINE_FPS, value))


def _validate_custom_presets(value: Any) -> tuple[WindowPreset, ...]:
    """Normalize and validate the list of user-defined window presets.

    Entries with blank names, non-numeric geometry or non-positive widths
    are rejected; duplicate names are de-duplicated (first wins) and the
    list is capped at :data:`MAX_CUSTOM_PRESETS`.
    """
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SettingsError(f"Invalid custom presets list: {value!r}")
    presets: list[WindowPreset] = []
    seen: set[str] = set()
    for item in cast(Sequence[Any], value):
        if not isinstance(item, Mapping):
            raise SettingsError(f"Invalid custom preset entry: {item!r}")
        entry = cast(Mapping[str, Any], item)
        name = entry.get("name")
        center = entry.get("center")
        width = entry.get("width")
        if not isinstance(name, str) or not name.strip():
            raise SettingsError(f"Invalid custom preset name: {name!r}")
        name = name.strip()
        if (
            isinstance(center, bool)
            or not isinstance(center, (int, float))
            or isinstance(width, bool)
            or not isinstance(width, (int, float))
            or width < _MIN_PRESET_WIDTH
        ):
            raise SettingsError(f"Invalid window geometry for preset '{name}'")
        if name in seen:
            continue
        seen.add(name)
        presets.append(WindowPreset(name=name, center=float(center), width=float(width)))
    return tuple(presets[:MAX_CUSTOM_PRESETS])
