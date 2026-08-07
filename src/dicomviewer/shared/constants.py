"""Project-wide constants that must remain stable across the application."""

from collections.abc import Mapping
from types import MappingProxyType

from dicomviewer._version import __version__

APP_NAME = "DICOMStudio"
# The user-data directory keeps the original name so existing settings and
# recent folders survive the rebranding (no behavior or data migration).
APP_DIR_NAME = "DicomViewer"
ORGANIZATION_NAME = "DICOMStudio"
APP_SUBTITLE = "Modern Open-Source DICOM Workstation"
APP_DESCRIPTION = "A modern, lightweight desktop DICOM viewer built with Python and PySide6."
APP_COPYRIGHT = "Copyright © 2026 DICOMStudio Team"
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
    "APP_SUBTITLE",
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
