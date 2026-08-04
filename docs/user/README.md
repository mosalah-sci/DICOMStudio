# DICOM Viewer Professional — Installation Guide

DICOM Viewer Professional is a standalone Windows application: it does not
require Python or any other runtime to be installed.

## Installation

Run the installer `DicomViewer-Professional-<version>-Setup.exe` and follow
the on-screen steps. The installer:

- installs the application for your user account (no administrator rights
  required);
- adds a **DICOM Viewer Professional** entry to the Start Menu;
- offers an optional **desktop shortcut** (unchecked by default);
- associates `.dcm` files so double-clicking a DICOM image opens it in the
  viewer (it opens the image's containing folder);
- provides an **uninstaller** in the Start Menu and via Windows Settings.

### Portable use

Prefer not to install? Extract
`DicomViewer-Professional-<version>-Portable.zip` anywhere (a USB drive, for
example) and run `DicomViewer.exe` from the extracted folder. Everything runs
from that folder; nothing is written outside your user profile.

### Command line

```
DicomViewer.exe [--version] [--smoke-test] [--theme <name>] [<file-or-folder>]
```

- `--version` — print the version and exit.
- `--smoke-test` — launch and auto-close (used for automated checks).
- `--theme <name>` — start with a specific theme (`dark` or `light`).
- `<file-or-folder>` — open a DICOM file (its parent folder) or a folder of
  DICOM studies on startup.

## First steps

1. Use **File → Open Folder...** (Ctrl+O) to choose a folder of DICOM studies.
2. The **Study Explorer** lists patients, studies and series; double-click a
   series to view it.
3. The **Metadata panel** shows patient, study and series information.
4. Use the toolbar to zoom, fit, measure, and export images.

## Data and privacy

Settings and recent folders are stored in your user profile
(`%LOCALAPPDATA%\DicomViewer`); nothing is uploaded anywhere. The app is
provided under the MIT License.
