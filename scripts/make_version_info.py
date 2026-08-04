"""Generate the Windows version resource consumed by PyInstaller.

Reads the single source of truth for version and metadata and writes
``packaging/version_info.txt`` in the VSVersionInfo format expected by
PyInstaller's ``version`` parameter.

    uv run python scripts/make_version_info.py
"""

from __future__ import annotations

from pathlib import Path

from dicomviewer._version import __version__
from dicomviewer.shared.constants import (
    APP_COPYRIGHT,
    APP_DESCRIPTION,
    APP_NAME,
    ORGANIZATION_NAME,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT = _REPO_ROOT / "packaging" / "version_info.txt"


def _triple(version: str) -> tuple[int, int, int]:
    """Return the leading three numeric components of a version string."""
    parts = version.split(".")
    numbers = []
    for part in parts[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        numbers.append(int(digits) if digits else 0)
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def build_version_info(version: str, output: Path) -> None:
    """Render and write the VSVersionInfo resource text."""
    major, minor, patch = _triple(version)
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{ORGANIZATION_NAME}'),
         StringStruct('FileDescription', '{APP_DESCRIPTION}'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'DicomViewer'),
         StringStruct('LegalCopyright', '{APP_COPYRIGHT}'),
         StringStruct('OriginalFilename', 'DicomViewer.exe'),
         StringStruct('ProductName', '{APP_NAME}'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    output.write_text(content, encoding="utf-8")


def main() -> int:
    """Generate the version resource and report the result."""
    build_version_info(__version__, _OUTPUT)
    print(f"Wrote {_OUTPUT} for version {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
