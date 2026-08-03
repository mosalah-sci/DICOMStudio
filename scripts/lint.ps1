# Development script.

# Lints the source and test code with Ruff.
$ErrorActionPreference = "Stop"
& uv run ruff check src tests
