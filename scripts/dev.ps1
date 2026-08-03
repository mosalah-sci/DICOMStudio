# Development scripts.

# Sets up the development environment (creates the venv and installs deps).
$ErrorActionPreference = "Stop"
& uv sync
Write-Host "Development environment ready. Run .\scripts\run.ps1 to launch the application."
