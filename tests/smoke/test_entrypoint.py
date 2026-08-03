"""Integration tests for the application entry point."""

from __future__ import annotations

import os
import subprocess
import sys


def _run_dicomviewer(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    return subprocess.run(
        [sys.executable, "-m", "dicomviewer", *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
        check=False,
    )


def test_version_flag_prints_the_version() -> None:
    result = _run_dicomviewer("--version")
    assert result.returncode == 0
    assert "0.6.0" in result.stdout


def test_smoke_test_starts_and_exits_cleanly() -> None:
    result = _run_dicomviewer("--smoke-test")
    assert result.returncode == 0


def test_theme_flag_is_accepted() -> None:
    result = _run_dicomviewer("--smoke-test", "--theme", "light")
    assert result.returncode == 0


def test_invalid_theme_is_rejected() -> None:
    result = _run_dicomviewer("--theme", "neon")
    assert result.returncode == 2


def test_missing_theme_value_is_rejected() -> None:
    result = _run_dicomviewer("--theme")
    assert result.returncode == 2
