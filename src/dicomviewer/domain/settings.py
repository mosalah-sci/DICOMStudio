"""Typed settings model and validation.

The model is pure data and lives in the Domain layer so that every layer can
rely on the same validated configuration snapshot without depending on the
TOML persistence details owned by Infrastructure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from dicomviewer.domain.exceptions import DicomViewerError

VALID_LOG_LEVELS = frozenset({"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"})
VALID_THEMES = frozenset({"dark", "light"})


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
class Settings:
    """Immutable snapshot of the full application configuration."""

    logging: LoggingSettings
    appearance: AppearanceSettings = AppearanceSettings()

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
        return cls(logging=logging_settings, appearance=appearance_settings)

    def to_mapping(self) -> dict[str, Any]:
        """Return the full settings as a TOML-serializable mapping."""
        return {"logging": self.logging.to_mapping(), "appearance": self.appearance.to_mapping()}


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


def _validate_non_empty(field: str, value: Any) -> str:
    """Reject blank values for settings that must be non-empty."""
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"Invalid value for '{field}': {value!r}")
    return value
