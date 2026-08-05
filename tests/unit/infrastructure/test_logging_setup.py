"""Tests for logging configuration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from loguru import logger

from dicomviewer.domain.settings import LoggingSettings
from dicomviewer.infrastructure.logging.setup import configure_logging


def test_configure_logging_writes_to_a_rotating_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(LoggingSettings(level="DEBUG"), log_dir)
    try:
        logger.info("log message for test")
        logger.complete()
        files = list(log_dir.glob("dicomviewer_*.log"))
        assert len(files) == 1
        assert "log message for test" in files[0].read_text(encoding="utf-8")
    finally:
        logger.remove()


@pytest.fixture
def detached_console(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Simulate a frozen windowed build with no attached console streams."""
    monkeypatch.setattr("sys.stderr", None)
    monkeypatch.setattr("sys.stdout", None)
    yield


def test_configure_logging_skips_console_without_error(
    detached_console: None, tmp_path: Path
) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(LoggingSettings(level="DEBUG"), log_dir)
    try:
        logger.info("log message for test")
        logger.complete()
        files = list(log_dir.glob("dicomviewer_*.log"))
        assert len(files) == 1
        assert "log message for test" in files[0].read_text(encoding="utf-8")
    finally:
        logger.remove()


def test_configure_logging_tolerates_missing_log_dir(
    detached_console: None,
) -> None:
    configure_logging(LoggingSettings(level="DEBUG"), None)
    try:
        logger.info("log message for test")
        logger.complete()
    finally:
        logger.remove()
