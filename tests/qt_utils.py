"""Small Qt event-loop helpers used by tests that cross threads."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtWidgets import QApplication


def pump_until(
    qapp: QApplication,
    predicate: Callable[[], bool],
    timeout: float = 3.0,
) -> bool:
    """Process events until ``predicate`` holds or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return predicate()
