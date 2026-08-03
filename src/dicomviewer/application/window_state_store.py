"""Port for persisting the main window layout between sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WindowState:
    """Serialized window geometry and dock layout captured at close time."""

    geometry: bytes
    dock_state: bytes


class WindowStateStore(Protocol):
    """Loads and saves the serialized window layout.

    The Presentation layer produces the byte payloads (via Qt's
    ``saveGeometry`` / ``saveState``); Infrastructure decides how they are
    stored. The store never interprets the bytes.
    """

    def load(self) -> WindowState | None:
        """Return the last saved layout, or ``None`` when none exists."""
        raise NotImplementedError

    def save(self, state: WindowState) -> None:
        """Persist the given layout for the next session."""
        raise NotImplementedError
