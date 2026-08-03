"""Port for persisting and loading application settings."""

from __future__ import annotations

from typing import Protocol

from dicomviewer.domain.settings import Settings


class SettingsStore(Protocol):
    """Loads the current settings and persists updated snapshots.

    Infrastructure provides the concrete implementation (TOML-backed);
    application services depend on this contract only.
    """

    def load(self) -> Settings:
        """Return the current settings snapshot."""
        raise NotImplementedError

    def save(self, settings: Settings) -> None:
        """Persist the given settings snapshot."""
        raise NotImplementedError
