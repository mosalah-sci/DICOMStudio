"""JSON-backed storage for the serialized main window layout."""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path

from loguru import logger

from dicomviewer.application.window_state_store import WindowState


class JsonWindowStateStore:
    """Persists window geometry and dock state as a small JSON file.

    Qt serializes layouts as opaque byte payloads; base64 keeps them safe for
    JSON. Corrupt or unreadable files are ignored so a damaged file never
    prevents the application from starting with default layout.
    """

    def __init__(self, path: Path) -> None:
        """Use ``path`` as the layout file location."""
        self._path = path

    def load(self) -> WindowState | None:
        """Return the last saved layout, or ``None`` when none exists."""
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return WindowState(
                geometry=base64.b64decode(payload["geometry"], validate=True),
                dock_state=base64.b64decode(payload["dock_state"], validate=True),
            )
        except (OSError, ValueError, KeyError, binascii.Error) as exc:
            logger.warning("Ignoring unreadable window state at {}", self._path)
            logger.debug("Window state read failure: {}", exc)
            return None

    def save(self, state: WindowState) -> None:
        """Persist the given layout, creating parent directories."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "geometry": base64.b64encode(state.geometry).decode("ascii"),
            "dock_state": base64.b64encode(state.dock_state).decode("ascii"),
        }
        self._path.write_text(json.dumps(payload), encoding="utf-8")
