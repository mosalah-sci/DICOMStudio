"""Mapping exceptions to clear user-facing dialogs.

Per the error-handling strategy (ADR-010), users see a friendly message while
technical detail is written to logs only.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtWidgets import QMessageBox, QWidget


class ErrorPresenter:
    """Shows non-blocking dialogs for recoverable failures."""

    def show_error(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        """Present a critical error, logging the technical detail."""
        logger.error("{}: {}", title, detail if detail is not None else message)
        QMessageBox.critical(parent, title, message)

    def show_warning(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        """Present a warning, logging the technical detail."""
        logger.warning("{}: {}", title, detail if detail is not None else message)
        QMessageBox.warning(parent, title, message)
