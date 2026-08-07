"""Generate a multi-resolution Windows .ico from the application icon SVG.

This script renders the source SVG at the standard Windows icon sizes and
writes them into a single ICO file. It is used by the packaging/release
scripts and can be run manually:

    uv run python scripts/make_icon.py

Smaller entries are encoded as uncompressed 32-bit bitmaps (classic ICO) so
they render in every Windows context; the 256px entry is stored as PNG.

The output is written to ``packaging/DICOMStudio.ico``.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QImageWriter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SVG = _REPO_ROOT / "packaging" / "app-icon.svg"
_OUTPUT_ICO = _REPO_ROOT / "packaging" / "DICOMStudio.ico"
_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


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


def _bmp_entry(pixmap: QPixmap) -> bytes:
    """Encode a pixmap as a 32-bit ICO bitmap entry (XOR + AND mask)."""
    size = pixmap.width()
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    raw = bytes(image.constBits())
    # BGRA rows, top to bottom (ARGB32 in little-endian memory order).
    rows = [raw[row * size * 4 : (row + 1) * size * 4] for row in range(size)]

    header = struct.pack(
        "<IiiHHIIiiII",
        40,  # biSize
        size,
        size * 2,  # biHeight: XOR + AND planes
        1,  # biPlanes
        32,  # biBitCount
        0,  # biCompression (BI_RGB)
        size * size * 4,  # biSizeImage
        0,
        0,
        0,
        0,
    )
    xor = b"".join(reversed(rows))  # bottom-up
    mask_row_bytes = ((size + 31) // 32) * 4
    and_mask = b"\x00" * (mask_row_bytes * size)
    return header + xor + and_mask


def _png_entry(pixmap: QPixmap) -> bytes:
    """Encode a pixmap as a PNG payload for the 256px ICO entry."""
    image = pixmap.toImage()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buffer, b"png")
    if not writer.write(image):
        raise RuntimeError("Failed to encode PNG icon entry")
    buffer.close()
    return bytes(data)


def build_ico(source: Path, output: Path, sizes: tuple[int, ...]) -> None:
    """Render each size and pack them into a single ICO file."""
    entries: list[tuple[int, bytes]] = []
    for size in sizes:
        pixmap = _render_svg(source, size)
        if pixmap.isNull():
            raise RuntimeError(f"Failed to rasterize icon at {size}px")
        if size >= 256:
            entries.append((size, _png_entry(pixmap)))
        else:
            entries.append((size, _bmp_entry(pixmap)))

    header = struct.pack("<HHH", 0, 1, len(entries))
    icondir = b""
    offset = 6 + 16 * len(entries)
    for size, blob in entries:
        dim = size if size < 256 else 0
        icondir += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    output.write_bytes(header + icondir + b"".join(blob for _, blob in entries))


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
