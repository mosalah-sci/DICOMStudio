"""Tests for logging configuration."""

from __future__ import annotations

from pathlib import Path

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
