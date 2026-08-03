"""Loading and persisting application settings."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomlkit

from dicomviewer.domain.settings import Settings, SettingsError, as_str_mapping
from dicomviewer.infrastructure.persistence.app_paths import AppPaths


def load_default_settings() -> Settings:
    """Load the default settings bundled with the package.

    The bundled file is the single source of truth for default values.
    """
    from importlib.resources import files

    resource = files("dicomviewer.infrastructure.configuration").joinpath("defaults.toml")
    try:
        document = tomlkit.parse(resource.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SettingsError("Could not load the bundled default settings") from exc
    return Settings.from_mapping(dict(document))


def build_settings_service(paths: AppPaths) -> SettingsService:
    """Create the settings service for the given application paths."""
    return SettingsService(defaults=load_default_settings(), user_settings_path=paths.settings_file)


class SettingsService:
    """Provides validated settings merged from defaults and a user file.

    Defaults are injected so the service can be constructed with any defaults
    in tests. User overrides, when present, take precedence per section.
    """

    def __init__(self, defaults: Settings, user_settings_path: Path) -> None:
        """Store the injected defaults and the user settings file location."""
        self._defaults = defaults
        self._user_settings_path = user_settings_path

    @property
    def user_settings_path(self) -> Path:
        """Path of the user-editable settings file."""
        return self._user_settings_path

    def load(self) -> Settings:
        """Return the defaults merged with any persisted user overrides."""
        if not self._user_settings_path.exists():
            return self._defaults
        overrides = _read_toml(self._user_settings_path)
        merged = _deep_merge(self._defaults.to_mapping(), overrides)
        return Settings.from_mapping(merged)

    def save(self, settings: Settings) -> None:
        """Persist settings to the user file, creating parent directories."""
        self._user_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._user_settings_path.write_text(_dumps(settings), encoding="utf-8")


def _read_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file into a plain mapping."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SettingsError(f"Could not read settings file: {path}") from exc
    return dict(tomlkit.parse(raw))


def _deep_merge(defaults: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Merge mappings recursively, with overrides winning on conflicts."""
    merged = dict(defaults)
    for key, value in overrides.items():
        existing = as_str_mapping(merged.get(key))
        nested = as_str_mapping(value)
        if existing is not None and nested is not None:
            merged[key] = _deep_merge(existing, nested)
        else:
            merged[key] = value
    return merged


def _dumps(settings: Settings) -> str:
    """Serialize settings into TOML text preserving a stable structure."""
    document = tomlkit.document()
    logging_table = tomlkit.table()
    logging_table["level"] = settings.logging.level
    logging_table["rotation"] = settings.logging.rotation
    logging_table["retention"] = settings.logging.retention
    document["logging"] = logging_table
    appearance_table = tomlkit.table()
    appearance_table["theme"] = settings.appearance.theme
    document["appearance"] = appearance_table
    return tomlkit.dumps(document)
