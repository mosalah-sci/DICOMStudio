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
    ROTATE_CW = "rotate_cw"
    ROTATE_CCW = "rotate_ccw"
    FLIP_HORIZONTAL = "flip_horizontal"
    FLIP_VERTICAL = "flip_vertical"
    INVERT = "invert_grayscale"
    PLAY_CINE = "play_cine"
    MEASURE = "measure"
    ANNOTATE_POINT = "annotate_point"
    ANNOTATE_ARROW = "annotate_arrow"
    ANNOTATE_TEXT = "annotate_text"
    CLEAR_MEASUREMENTS = "clear_measurements"
    CLEAR_ANNOTATIONS = "clear_annotations"
    TOGGLE_INFO_OVERLAY = "toggle_info_overlay"
    MANAGE_WINDOW_PRESETS = "manage_window_presets"
    COPY_IMAGE = "copy_image"
    SCREENSHOT = "screenshot"
    INSPECT_DICOM = "inspect_dicom"
    SETTINGS = "settings"
    TOGGLE_STUDY_EXPLORER = "toggle_study_explorer"
    TOGGLE_METADATA = "toggle_metadata"
    RESTORE_LAYOUT = "restore_layout"
    FULLSCREEN = "fullscreen"
    ABOUT = "about"
    EXIT = "exit"
