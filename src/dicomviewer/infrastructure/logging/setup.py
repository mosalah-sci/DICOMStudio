"""Loguru configuration for the application."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from dicomviewer.domain.settings import LoggingSettings

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"


def configure_logging(settings: LoggingSettings, log_dir: Path) -> None:
    """Reset and configure all log sinks.

    Messages are written to the console and to a rotating file under
    ``log_dir``. The logging policy forbids patient-identifiable information
    in any message; compliance is enforced during code review.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=settings.level, format=_CONSOLE_FORMAT)
    logger.add(
        log_dir / "dicomviewer_{time:YYYY-MM-DD}.log",
        level=settings.level,
        format=_FILE_FORMAT,
        rotation=settings.rotation,
        retention=settings.retention,
        encoding="utf-8",
        enqueue=True,
    )
