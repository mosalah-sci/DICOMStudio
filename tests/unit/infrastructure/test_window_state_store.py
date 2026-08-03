"""Tests for the JSON window state store."""

from __future__ import annotations

from pathlib import Path

from dicomviewer.application.window_state_store import WindowState
from dicomviewer.infrastructure.persistence.window_state_store import JsonWindowStateStore


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    store = JsonWindowStateStore(tmp_path / "window_state.json")
    store.save(WindowState(geometry=b"geo-bytes", dock_state=b"dock-bytes"))
    state = store.load()
    assert state is not None
    assert state.geometry == b"geo-bytes"
    assert state.dock_state == b"dock-bytes"


def test_load_returns_none_when_no_file_exists(tmp_path: Path) -> None:
    store = JsonWindowStateStore(tmp_path / "window_state.json")
    assert store.load() is None


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    store = JsonWindowStateStore(tmp_path / "nested" / "dir" / "window_state.json")
    store.save(WindowState(geometry=b"g", dock_state=b"d"))
    assert store.load() is not None


def test_load_returns_none_for_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "window_state.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = JsonWindowStateStore(path)
    assert store.load() is None


def test_load_returns_none_when_keys_are_missing(tmp_path: Path) -> None:
    path = tmp_path / "window_state.json"
    path.write_text('{"geometry": "AQ=="}', encoding="utf-8")
    store = JsonWindowStateStore(path)
    assert store.load() is None


def test_load_returns_none_for_invalid_base64(tmp_path: Path) -> None:
    path = tmp_path / "window_state.json"
    path.write_text('{"geometry": "!!!", "dock_state": "!!!"}', encoding="utf-8")
    store = JsonWindowStateStore(path)
    assert store.load() is None
