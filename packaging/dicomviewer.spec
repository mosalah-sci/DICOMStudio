# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the DICOM Viewer Professional Windows build.

Produces an onedir distribution (folder + launcher executable) that runs
without a Python installation. The same folder is the standalone application
and the payload for both the installer and the portable archive.

Build with:
    uv run pyinstaller --noconfirm --clean packaging/dicomviewer.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_REPO_ROOT = Path(SPECPATH).resolve().parent  # type: ignore[name-defined]
_SOURCE_DIR = _REPO_ROOT / "src"
_VERSION_FILE = _REPO_ROOT / "packaging" / "version_info.txt"
_ICON = _REPO_ROOT / "packaging" / "DicomViewer.ico"

datas = collect_data_files("dicomviewer")

# pydicom is imported lazily via importlib.import_module in the DICOM
# infrastructure, so static analysis cannot discover it on its own.
hiddenimports = collect_submodules("pydicom")

a = Analysis(
    [str(_SOURCE_DIR / "dicomviewer" / "main.py")],
    pathex=[str(_SOURCE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "dicomviewer.resources",
        *hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DicomViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_ICON),
    version=str(_VERSION_FILE),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DicomViewer",
)
