"""Loguru configuration for the application."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from loguru import logger

from dicomviewer.domain.settings import LoggingSettings

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"


def configure_logging(settings: LoggingSettings, log_dir: Path | None) -> None:
    """Reset and configure all log sinks.

    Messages are written to the console (when one is attached) and to a
    rotating file under ``log_dir``. The logging policy forbids
    patient-identifiable information in any message; compliance is enforced
    during code review.

    Loguru cannot sink to ``None``, so every destination is validated before
    it is registered. Windowed (no-console) builds, such as the frozen
    executable, leave ``sys.stdout`` and ``sys.stderr`` unset; in that case
    only the file sink is configured. If ``log_dir`` is missing, its parent
    directories are created and logging falls back to the console.
    """
    logger.remove()
    _add_console_sink(settings)
    _add_file_sink(settings, log_dir)


def _console_stream() -> TextIO | None:
    """Return the best available console stream, or ``None`` when detached.

    Frozen windowed executables have no attached console, so both
    ``sys.stdout`` and ``sys.stderr`` are ``None`` and must not be logged to.
    """
    for stream in (sys.stderr, sys.stdout):
        if stream is not None:
            return stream
    return None


def _add_console_sink(settings: LoggingSettings) -> None:
    """Register the console sink when a console stream is available."""
    stream = _console_stream()
    if stream is None:
        return
    logger.add(stream, level=settings.level, format=_CONSOLE_FORMAT)


def _add_file_sink(settings: LoggingSettings, log_dir: Path | None) -> None:
    """Register the rotating file sink, creating ``log_dir`` on demand.

    When no ``log_dir`` is available, file logging is skipped rather than
    calling ``logger.add`` with a ``None`` path.
    """
    if log_dir is None:
        return
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger.add(
        directory / "dicomviewer_{time:YYYY-MM-DD}.log",
        level=settings.level,
        format=_FILE_FORMAT,
        rotation=settings.rotation,
        retention=settings.retention,
        encoding="utf-8",
        enqueue=True,
    )
