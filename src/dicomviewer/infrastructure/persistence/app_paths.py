"""Platform-specific application paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir, user_log_dir


@dataclass(frozen=True)
class AppPaths:
    r"""Well-known directories used by the application.

    When ``root`` is provided, every directory is resolved beneath it. Tests
    use this override to keep their behavior hermetic and independent of the
    real user profile. Without an override, directories follow Windows
    conventions (for example ``%APPDATA%\\DicomViewer``).
    """

    app_name: str
    root: Path | None = None

    @property
    def config_dir(self) -> Path:
        """Directory for user configuration files."""
        if self.root is not None:
            return self.root / "config"
        return Path(user_config_dir(self.app_name, appauthor=False))

    @property
    def data_dir(self) -> Path:
        """Directory for application data."""
        if self.root is not None:
            return self.root / "data"
        return Path(user_data_dir(self.app_name, appauthor=False))

    @property
    def logs_dir(self) -> Path:
        """Directory for application log files."""
        if self.root is not None:
            return self.root / "logs"
        return Path(user_log_dir(self.app_name, appauthor=False))

    @property
    def cache_dir(self) -> Path:
        """Directory for cached data such as thumbnails."""
        if self.root is not None:
            return self.root / "cache"
        return Path(user_cache_dir(self.app_name, appauthor=False))

    @property
    def settings_file(self) -> Path:
        """Path of the user settings file."""
        return self.config_dir / "settings.toml"

    def ensure_dirs(self) -> None:
        """Create every directory the application needs at runtime."""
        for directory in (self.config_dir, self.data_dir, self.logs_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
