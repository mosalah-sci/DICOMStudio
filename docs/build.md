# Building and Releasing

This document describes how to build distribution artifacts and perform a
release. Two complementary build paths exist:

1. **Python distributions** (wheel + sdist) — `scripts/build.ps1`.
2. **End-user Windows distributions** (standalone app, installer, portable
   archive) — `scripts/release.ps1`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) and Python 3.13.
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer, with
  `ISCC.exe` reachable at `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` or
  under `C:\Program Files*\Inno Setup *\`.

```powershell
uv sync              # install runtime + dev dependencies (incl. PyInstaller)
```

## Building the standalone application

```powershell
uv run pyinstaller --noconfirm --clean packaging\dicomviewer.spec
```

This produces `dist/DicomViewer/` (the `DicomViewer.exe` launcher plus its
support files). The spec:

- packages the `dicomviewer` package data (icons, styles, default settings);
- includes every pydicom submodule, because pydicom is imported lazily;
- embeds the application icon and a generated Windows version resource.

The icon and version resources are regenerated before each build:

```powershell
uv run python scripts/make_icon.py
uv run python scripts/make_version_info.py
```

## Building the installer

```powershell
& "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" `
    /DMyAppVersion=<version> packaging\dicomviewer.iss
```

Output: `dist/installer/DicomViewer-Professional-<version>-Setup.exe`.

## Building the portable archive

```powershell
.\scripts\build_portable.ps1
```

Output: `dist/DicomViewer-Professional-<version>-Portable.zip`.

## Release

`scripts/release.ps1` runs everything end to end:

1. Full test suite (headless Qt).
2. Standalone build (icon + version resource + PyInstaller).
3. Smoke test of the standalone executable.
4. Installer compilation.
5. Portable archive.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release.ps1
```

## Release checklist

- [ ] `uv run pytest` — all tests pass.
- [ ] `uv run black --check src tests`, `uv run ruff check src tests`,
      `uv run pyright` — quality gates pass.
- [ ] `scripts/release.ps1` completes with the three artifacts.
- [ ] On a clean machine: install, launch, open a DICOM folder, verify
      settings persist, verify resources load, uninstall cleanly.
- [ ] Bump `src/dicomviewer/_version.py`, update `CHANGELOG.md`, commit, and
      create an annotated tag (`v0.11.0`).
