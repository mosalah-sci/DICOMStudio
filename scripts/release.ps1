# Release script.
#
# Orchestrates the full Milestone 11 release: standalone application, portable
# archive and professional installer, plus verification smoke checks.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param([string]$Name, [scriptblock]$Block)
    Write-Host ""
    Write-Host "=== $Name ==="
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$Version = (uv run python -c "from dicomviewer import __version__; print(__version__)").Trim()
if (-not $Version) { throw "Could not determine the application version" }
Write-Host "Releasing DICOM Viewer Professional $Version"

$DistRoot = Join-Path (Get-Location) "dist"
$PortableDir = Join-Path $DistRoot "DicomViewer"
$PortableZip = Join-Path $DistRoot "DicomViewer-Professional-$Version-Portable.zip"
$SetupExe = Join-Path $DistRoot "installer\DicomViewer-Professional-$Version-Setup.exe"

# 1. Run the full test suite before packaging anything.
Invoke-Step "Running the test suite" {
    $env:QT_QPA_PLATFORM = "offscreen"
    uv run pytest -q
}

# 2. Build the standalone application with PyInstaller.
Invoke-Step "Building the standalone application" {
    uv run python scripts/make_version_info.py
    uv run python scripts/make_icon.py
    uv run pyinstaller --noconfirm --clean packaging\dicomviewer.spec
}

# 3. Smoke test the standalone executable.
Invoke-Step "Smoke testing the standalone executable" {
    $env:QT_QPA_PLATFORM = "windows"
    & (Join-Path $PortableDir "DicomViewer.exe") --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "Standalone smoke test failed with exit code $LASTEXITCODE" }
}

# 4. Build the professional installer with Inno Setup.
Invoke-Step "Building the professional installer" {
    $Iscc = Get-ChildItem "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $Iscc = Get-ChildItem "C:\Program Files*\Inno Setup*\ISCC.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
    }
    if (-not $Iscc) { throw "ISCC.exe not found. Install Inno Setup 6 first." }
    & $Iscc.FullName "/DMyAppVersion=$Version" "packaging\dicomviewer.iss"
}

# 5. Build the portable archive from the standalone folder.
Invoke-Step "Building the portable archive" {
    if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }
    Compress-Archive -Path (Join-Path $PortableDir "*") -DestinationPath $PortableZip -CompressionLevel Optimal
}

Write-Host ""
Write-Host "Release artifacts:"
Write-Host "  $PortableDir"
Write-Host "  $PortableZip"
Write-Host "  $SetupExe"
Write-Host "Release build complete."
