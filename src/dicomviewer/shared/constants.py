"""Project-wide constants that must remain stable across the application."""

from collections.abc import Mapping
from types import MappingProxyType

from dicomviewer._version import __version__

APP_NAME = "DICOM Viewer Professional"
APP_DIR_NAME = "DicomViewer"
ORGANIZATION_NAME = "DicomViewer"
APP_DESCRIPTION = "A professional-grade DICOM medical image viewer for Windows."
APP_COPYRIGHT = "Copyright © 2026 DICOM Viewer Professional Team"
LICENSE_NAME = "MIT License"

# The UI uses an 8-pixel spacing grid; these are the canonical spacing values.
PADDING_4 = 4
PADDING_8 = 8
PADDING_12 = 12
PADDING_16 = 16

# Icon size used for toolbar actions (points).
TOOLBAR_ICON_SIZE = 16

# Icon size used by informative empty states (points).
EMPTY_STATE_ICON_SIZE = 48

# Default widths (pixels) of the dockable side panels.
SIDEBAR_WIDTHS: Mapping[str, int] = MappingProxyType({"study_explorer": 260, "metadata": 300})

__all__ = [
    "APP_COPYRIGHT",
    "APP_DESCRIPTION",
    "APP_DIR_NAME",
    "APP_NAME",
    "EMPTY_STATE_ICON_SIZE",
    "LICENSE_NAME",
    "ORGANIZATION_NAME",
    "PADDING_4",
    "PADDING_8",
    "PADDING_12",
    "PADDING_16",
    "SIDEBAR_WIDTHS",
    "TOOLBAR_ICON_SIZE",
    "__version__",
]
