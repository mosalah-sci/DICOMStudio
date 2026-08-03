# Development script.

# Builds distribution artifacts (sdist + wheel) into dist/.
$ErrorActionPreference = "Stop"
& uv build
Write-Host "Build complete. Artifacts are in .\dist\"
