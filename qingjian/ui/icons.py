"""Line icons drawn with QPainter.

Drawing them keeps the build free of QtSvg and free of glyph fonts that may or
may not be installed, and it lets every icon take the colour of the control it
sits in. Each recipe is a list of strokes in a 24x24 space, the same grid the
design uses.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap

# name -> (polylines, circles, rects) in a 24x24 coordinate space.
_SHAPES: dict[str, dict] = {
    "folder": {"paths": [[(3, 7), (3, 18), (21, 18), (21, 9), (11, 9), (9, 7), (3, 7)]]},
    "refresh": {"paths": [[(20, 5), (20, 11), (14, 11)]],
                "arcs": [(3, 3, 18, 18, 40 * 16, 260 * 16)]},
    "gear": {"circles": [(12, 12, 3.2)],
             "paths": [[(12, 3), (12, 6)], [(12, 18), (12, 21)], [(3, 12), (6, 12)],
                       [(18, 12), (21, 12)], [(5.6, 5.6), (7.7, 7.7)], [(16.3, 16.3), (18.4, 18.4)],
                       [(18.4, 5.6), (16.3, 7.7)], [(7.7, 16.3), (5.6, 18.4)]]},
    "search": {"circles": [(11, 11, 6.5)], "paths": [[(16, 16), (21, 21)]]},
    "chevron-down": {"paths": [[(6, 9.5), (12, 15.5), (18, 9.5)]]},
    "chevron-left": {"paths": [[(14.5, 5), (8.5, 12), (14.5, 19)]]},
    "chevron-right": {"paths": [[(9.5, 5), (15.5, 12), (9.5, 19)]]},
    "undo": {"paths": [[(20, 5), (14, 5), (14, 11)]],
             "arcs": [(3.5, 4, 17, 17, 200 * 16, -250 * 16)]},
    "redo": {"paths": [[(4, 5), (10, 5), (10, 11)]],
             "arcs": [(3.5, 4, 17, 17, -20 * 16, 250 * 16)]},
    "single": {"rects": [(3, 4.5, 18, 15, 2)]},
    "grid": {"rects": [(3, 3, 7.6, 7.6, 1.6), (13.4, 3, 7.6, 7.6, 1.6),
                       (3, 13.4, 7.6, 7.6, 1.6), (13.4, 13.4, 7.6, 7.6, 1.6)]},
    "compare": {"rects": [(3, 4, 8, 16, 1.5), (13, 4, 8, 16, 1.5)]},
    "duplicate": {"rects": [(3, 3, 11, 11, 1.6), (10, 10, 11, 11, 1.6)]},
    "history": {"circles": [(12, 12, 8.5)], "paths": [[(12, 7), (12, 12.5), (16, 14.5)]]},
    "stats": {"paths": [[(4, 20), (4, 12)], [(10, 20), (10, 5)], [(16, 20), (16, 9)],
                        [(21, 20), (3, 20)]]},
    "shield": {"paths": [[(12, 3), (20, 6), (20, 12), (12, 21), (4, 12), (4, 6), (12, 3)],
                         [(9, 12), (11, 14), (15, 10)]]},
    "camera": {"paths": [[(4, 8), (8, 8), (9.5, 6), (14.5, 6), (16, 8), (20, 8), (20, 19),
                          (4, 19), (4, 8)]], "circles": [(12, 13, 3.6)]},
    "film": {"rects": [(3, 5, 18, 14, 2)],
             "paths": [[(7, 5), (7, 19)], [(17, 5), (17, 19)], [(3, 12), (21, 12)]]},
    "trash": {"paths": [[(4, 6.5), (20, 6.5)], [(9, 6.5), (9, 4), (15, 4), (15, 6.5)],
                        [(6, 6.5), (7, 20), (17, 20), (18, 6.5)]]},
    "tag": {"paths": [[(4, 4), (12, 4), (20, 12), (12, 20), (4, 12), (4, 4)]],
            "circles": [(8, 8, 1.4)]},
    "sidecar": {"paths": [[(4, 6), (13, 6), (16, 9), (20, 9), (20, 18), (4, 18), (4, 6)],
                          [(8, 12.5), (13, 12.5)]]},
    "zoom": {"circles": [(11, 11, 6.5)], "paths": [[(16, 16), (21, 21)], [(8, 11), (14, 11)]]},
    "info": {"circles": [(12, 12, 8.6)], "paths": [[(12, 11), (12, 16.5)], [(12, 7.8), (12, 8.2)]]},
    "warning": {"paths": [[(12, 4), (21, 20), (3, 20), (12, 4)], [(12, 10), (12, 14.5)],
                          [(12, 17), (12, 17.4)]]},
    "check": {"paths": [[(5, 13), (9.5, 17.5), (19, 7)]]},
    "close": {"paths": [[(6, 6), (18, 18)], [(18, 6), (6, 18)]]},
    "plus": {"paths": [[(12, 5), (12, 19)], [(5, 12), (19, 12)]]},
    "play": {"fills": [[(8, 5), (19, 12), (8, 19)]]},
    "pause": {"rects": [(8, 5, 3, 14, 1), (13, 5, 3, 14, 1)]},
    "star": {"fills": [[(12, 2.4), (14.6, 8.6), (21.2, 9.2), (16.2, 13.6), (17.6, 20.2),
                        (12, 16.8), (6.4, 20.2), (7.8, 13.6), (2.8, 9.2), (9.4, 8.6)]]},
    "language": {"circles": [(12, 12, 8.6)],
                 "paths": [[(3.4, 12), (20.6, 12)],
                           [(12, 3.4), (8.6, 8), (8.6, 16), (12, 20.6)],
                           [(12, 3.4), (15.4, 8), (15.4, 16), (12, 20.6)]]},
    "volume": {"fills": [[(4, 9.5), (8, 9.5), (12.5, 5), (12.5, 19), (8, 14.5), (4, 14.5)]],
               "arcs": [(13.5, 7.5, 6, 9, -80 * 16, 160 * 16),
                        (15.5, 5.5, 8, 13, -80 * 16, 160 * 16)]},
    "mute": {"fills": [[(4, 9.5), (8, 9.5), (12.5, 5), (12.5, 19), (8, 14.5), (4, 14.5)]],
             "paths": [[(15.5, 9.5), (20.5, 14.5)], [(20.5, 9.5), (15.5, 14.5)]]},
    "sliders": {"paths": [[(4, 7), (20, 7)], [(4, 12), (20, 12)], [(4, 17), (20, 17)]],
                "circles": [(9, 7, 2.2), (15, 12, 2.2), (7, 17, 2.2)]},
}

_CACHE: dict[tuple, QIcon] = {}


def pixmap(name: str, size: int = 18, color: str = "#C7CEDC", width: float = 1.9,
           ratio: float = 1.0) -> QPixmap:
    shapes = _SHAPES.get(name)
    canvas = QPixmap(int(size * ratio), int(size * ratio))
    canvas.setDevicePixelRatio(ratio)
    canvas.fill(Qt.GlobalColor.transparent)
    if not shapes:
        return canvas
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = size / 24.0
    painter.scale(scale, scale)
    pen = painter.pen()
    pen.setColor(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    for points in shapes.get("paths", ()):
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)
    for cx, cy, radius in shapes.get("circles", ()):
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
    for rect in shapes.get("rects", ()):
        x, y, w, h, radius = rect
        painter.drawRoundedRect(QRectF(x, y, w, h), radius, radius)
    for x, y, w, h, start, span in shapes.get("arcs", ()):
        painter.drawArc(QRectF(x, y, w, h), int(start), int(span))
    if shapes.get("fills"):
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        for points in shapes["fills"]:
            path = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                path.lineTo(QPointF(*point))
            path.closeSubpath()
            painter.drawPath(path)
    painter.end()
    return canvas


def icon(name: str, size: int = 18, color: str = "#C7CEDC", width: float = 1.9) -> QIcon:
    key = (name, size, color, width)
    cached = _CACHE.get(key)
    if cached is None:
        cached = QIcon(pixmap(name, size, color, width))
        _CACHE[key] = cached
    return cached


def app_icon(size: int = 256) -> QIcon:
    """The window and taskbar icon: a card with a picture in it."""
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    background = QPainterPath()
    background.addRoundedRect(QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92),
                              size * 0.22, size * 0.22)
    painter.fillPath(background, QColor("#7357F5"))
    card = QPainterPath()
    card.addRoundedRect(QRectF(size * 0.23, size * 0.22, size * 0.54, size * 0.56),
                        size * 0.085, size * 0.085)
    painter.fillPath(card, QColor("#F4F1FF"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#7357F5"))
    painter.drawEllipse(QRectF(size * 0.32, size * 0.32, size * 0.12, size * 0.12))
    mountain = QPainterPath()
    mountain.moveTo(size * 0.29, size * 0.67)
    for point in ((0.45, 0.49), (0.56, 0.60), (0.64, 0.52), (0.72, 0.67)):
        mountain.lineTo(size * point[0], size * point[1])
    mountain.closeSubpath()
    painter.fillPath(mountain, QColor("#7357F5"))
    painter.end()
    result = QIcon()
    for step in (16, 24, 32, 48, 64, 128, 256):
        result.addPixmap(canvas.scaled(QSize(step, step), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
    return result


def available() -> list[str]:
    return sorted(_SHAPES)
