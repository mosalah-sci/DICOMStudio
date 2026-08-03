"""Identifiers for every application action."""

from __future__ import annotations

from enum import StrEnum


class ActionId(StrEnum):
    """Stable identifiers used to look up actions in the catalog."""

    OPEN_FOLDER = "open_folder"
    OPEN_FILES = "open_files"
    EXPORT_IMAGE = "export_image"
    FIT_TO_WINDOW = "fit_to_window"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    RESET_VIEW = "reset_view"
    WINDOW_LEVEL = "window_level"
    MEASURE = "measure"
    SCREENSHOT = "screenshot"
    SETTINGS = "settings"
    TOGGLE_STUDY_EXPLORER = "toggle_study_explorer"
    TOGGLE_METADATA = "toggle_metadata"
    RESTORE_LAYOUT = "restore_layout"
    FULLSCREEN = "fullscreen"
    ABOUT = "about"
    EXIT = "exit"
