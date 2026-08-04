# Release script.
#
# Builds the portable zip distribution from the standalone application folder
# produced by build_standalone.ps1.

$ErrorActionPreference = "Stop"

$Version = (uv run python -c "from dicomviewer import __version__; print(__version__)").Trim()
if (-not $Version) { throw "Could not determine the application version" }

$DistRoot = Join-Path (Get-Location) "dist"
$PortableDir = Join-Path $DistRoot "DicomViewer"
$PortableZip = Join-Path $DistRoot "DicomViewer-Professional-$Version-Portable.zip"

if (-not (Test-Path (Join-Path $PortableDir "DicomViewer.exe"))) {
    throw "Standalone application not found. Run scripts\build_standalone.ps1 first."
}
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }
Compress-Archive -Path (Join-Path $PortableDir "*") -DestinationPath $PortableZip -CompressionLevel Optimal

Write-Host "Portable archive created: $PortableZip"
