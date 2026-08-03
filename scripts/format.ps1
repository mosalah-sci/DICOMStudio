# Development script.

# Formats the source and test code with Black.
$ErrorActionPreference = "Stop"
& uv run black src tests
