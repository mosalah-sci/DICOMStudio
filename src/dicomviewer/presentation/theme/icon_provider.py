"""Theme-aware icon rendering from bundled SVG resources."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from dicomviewer.shared.constants import TOOLBAR_ICON_SIZE


class IconProvider:
    """Renders and caches the bundled icon set tinted with a theme color.

    The source SVGs use ``currentColor`` as their stroke; the active theme's
    icon color is substituted before rendering so a single art file serves
    every theme.
    """

    def __init__(self, icon_dir: Path) -> None:
        """Render icons from ``icon_dir`` (containing ``<name>.svg`` files)."""
        self._icon_dir = icon_dir
        self._color = "#FFFFFF"
        self._cache: dict[tuple[str, str, int], QIcon] = {}

    def set_color(self, color: str) -> None:
        """Switch the tint color, invalidating the cached icons."""
        if color != self._color:
            self._color = color
            self._cache.clear()

    def icon(self, name: str, size: int = TOOLBAR_ICON_SIZE) -> QIcon:
        """Return the named icon in the current theme color at a logical size."""
        key = (name, self._color, size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        icon = self._render(name, self._color, size)
        self._cache[key] = icon
        return icon

    def _render(self, name: str, color: str, size: int) -> QIcon:
        """Rasterize the named SVG at double density for crisp high-DPI icons."""
        source = self._load_svg(name, color)
        if source is None:
            return QIcon()
        renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
        if not renderer.isValid():
            logger.warning("Invalid SVG for icon '{}'", name)
            return QIcon()
        pixel_size = 2 * size
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            renderer.render(painter, QRectF(0.0, 0.0, float(pixel_size), float(pixel_size)))
        finally:
            painter.end()
        pixmap.setDevicePixelRatio(2.0)
        return QIcon(pixmap)

    def _load_svg(self, name: str, color: str) -> str | None:
        """Read the SVG text with the tint color substituted, or ``None``."""
        path = self._icon_dir / f"{name}.svg"
        try:
            return path.read_text(encoding="utf-8").replace("currentColor", color)
        except OSError as exc:
            logger.warning("Missing icon resource '{}': {}", name, exc)
            return None
