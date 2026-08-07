# Release script.
#
# Builds the standalone Windows application (folder + launcher executable)
# into dist/DICOMStudio/ using PyInstaller. This folder runs without a Python
# installation and is the payload for the installer and portable archives.

$ErrorActionPreference = "Stop"

# Regenerate the version resource and application icon so the executable
# embeds the current version and a freshly built multi-size icon.
uv run python scripts/make_version_info.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run python scripts/make_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pyinstaller --noconfirm --clean packaging\dicomviewer.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Standalone build complete. Application is in .\dist\DICOMStudio\"
