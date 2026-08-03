"""Tests for application path resolution."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.infrastructure.persistence.app_paths import AppPaths


def test_paths_are_derived_from_root_when_override_is_set(tmp_path: Path) -> None:
    paths = AppPaths("TestApp", root=tmp_path)
    assert paths.config_dir == tmp_path / "config"
    assert paths.data_dir == tmp_path / "data"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.cache_dir == tmp_path / "cache"
    assert paths.settings_file == tmp_path / "config" / "settings.toml"


def test_ensure_dirs_creates_every_directory(tmp_path: Path) -> None:
    paths = AppPaths("TestApp", root=tmp_path)
    paths.ensure_dirs()
    assert paths.config_dir.is_dir()
    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.cache_dir.is_dir()
