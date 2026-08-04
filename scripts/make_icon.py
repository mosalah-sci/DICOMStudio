"""Generate a multi-resolution Windows .ico from the application icon SVG.

This script renders the source SVG at the standard Windows icon sizes and
writes them into a single ICO file. It is used by the packaging/release
scripts and can be run manually:

    uv run python scripts/make_icon.py

The output is written to ``packaging/DicomViewer.ico``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImageWriter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SVG = _REPO_ROOT / "packaging" / "app-icon.svg"
_OUTPUT_ICO = _REPO_ROOT / "packaging" / "DicomViewer.ico"
_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render_svg(source: Path, size: int) -> QPixmap:
    """Rasterize the icon SVG at the requested square size."""
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG icon source: {source}")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter

    painter = QPainter(pixmap)
    try:
        renderer.render(painter, QRectF(0, 0, size, size))
    finally:
        painter.end()
    return pixmap


def build_ico(source: Path, output: Path, sizes: tuple[int, ...]) -> None:
    """Render each size and pack them into a single ICO file."""
    icondir = b""
    png_data: list[bytes] = []
    header = 6 + 16 * len(sizes)
    offset = header
    for size in sizes:
        pixmap = _render_svg(source, size)
        pixmap.setDevicePixelRatio(1.0)
        image = pixmap.toImage()
        if image.isNull():
            raise RuntimeError(f"Failed to rasterize icon at {size}px")
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        writer = QImageWriter(buffer, b"png")
        if not writer.write(image):
            raise RuntimeError(f"Failed to encode icon at {size}px")
        buffer.close()
        blob = bytes(data)
        png_data.append(blob)
        icondir += bytes(
            [
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,
                0,
                1,
                0,
                32,
                0,
            ]
        )
        icondir += (len(blob) & 0xFF).to_bytes(1, "little")
        icondir += ((len(blob) >> 8) & 0xFF).to_bytes(1, "little")
        icondir += ((len(blob) >> 16) & 0xFF).to_bytes(1, "little")
        icondir += ((len(blob) >> 24) & 0xFF).to_bytes(1, "little")
        icondir += (offset & 0xFF).to_bytes(1, "little")
        icondir += ((offset >> 8) & 0xFF).to_bytes(1, "little")
        icondir += ((offset >> 16) & 0xFF).to_bytes(1, "little")
        icondir += ((offset >> 24) & 0xFF).to_bytes(1, "little")
        offset += len(blob)
    ico_header = bytes([0, 0, 1, 0, len(sizes) & 0xFF, 0])
    output.write_bytes(ico_header + icondir + b"".join(png_data))


def main() -> int:
    """Render the icon and report the result."""
    if not _SOURCE_SVG.exists():
        print(f"Missing icon source: {_SOURCE_SVG}", file=sys.stderr)
        return 1
    app = QGuiApplication.instance() or QGuiApplication(["make_icon"])
    del app
    build_ico(_SOURCE_SVG, _OUTPUT_ICO, _ICON_SIZES)
    print(f"Wrote {_OUTPUT_ICO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
