"""Google Material Symbols(SVG) 아이콘 로더.

resources/icons/<name>.svg 를 읽어 원하는 색으로 칠해 QIcon/QPixmap 으로 렌더한다.
(이모지 대신 일관된 구글 아이콘 사용)
"""

from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from . import paths

_RENDER_SCALE = 2  # 고DPI 에서 또렷하게 렌더


@lru_cache(maxsize=64)
def _svg_text(name: str) -> str:
    return (paths.resource_dir() / "icons" / f"{name}.svg").read_text(encoding="utf-8")


def pixmap(name: str, color: str = "#ffffff", size: int = 20) -> QPixmap:
    """아이콘을 color 로 칠해 size(논리 px) 정사각 QPixmap 으로."""
    svg = _svg_text(name).replace("<path ", f'<path fill="{color}" ')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    px = int(size * _RENDER_SCALE)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(_RENDER_SCALE)
    return pm


def icon(name: str, color: str = "#ffffff", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))
