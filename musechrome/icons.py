"""线性图标：全部用 QPainter 现画（24×24 网格），不依赖图标文件。

边栏、按钮要什么图标就往 draw_icon 里加一个名字。
画法和设计稿里的 PIL 图标保持同一套形状。
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF


def draw_icon(painter: QPainter, name: str, x: float, y: float, size: float,
              color: str, bg: str | None = None) -> None:
    """在 (x, y, size, size) 的方框里画一个图标。color/bg 传十六进制色值。"""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    u = size / 24.0
    col = QColor(color)
    pen = QPen(col, max(1.2, 1.7 * u))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    def P(px, py):
        return QPointF(x + px * u, y + py * u)

    def line(pts):
        painter.drawPolyline(QPolygonF([P(px, py) for px, py in pts]))

    def rrect(rx, ry, rw, rh, r):
        painter.drawRoundedRect(QRectF(x + rx * u, y + ry * u, rw * u, rh * u), r * u, r * u)

    def ellipse(rx, ry, rw, rh):
        painter.drawEllipse(QRectF(x + rx * u, y + ry * u, rw * u, rh * u))

    if name == "grid":
        for cx, cy in [(3.5, 3.5), (13.5, 3.5), (3.5, 13.5), (13.5, 13.5)]:
            rrect(cx, cy, 6.5, 6.5, 1.8)
    elif name == "mega":
        path = QPainterPath()
        pts = [P(3, 10), P(3, 15), P(6.5, 16), P(17, 20.5), P(17, 5), P(6.5, 9)]
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()
        painter.drawPath(path)
        line([(8, 16.5), (9.5, 21)])
        painter.drawArc(QRectF(x + 15.5 * u, y + 8 * u, 7 * u, 9 * u), -55 * 16, 110 * 16)
    elif name == "puzzle":
        rrect(4, 6, 16, 14, 2)
        ellipse(9.5, 2.5, 5, 5)
    elif name == "shield":
        path = QPainterPath()
        pts = [P(12, 3), P(19, 5.5), P(19, 11), P(16.5, 17.5), P(12, 20.5),
               P(7.5, 17.5), P(5, 11), P(5, 5.5)]
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()
        painter.drawPath(path)
        line([(9, 11.5), (11.2, 13.7), (15.3, 9.4)])
    elif name == "log":
        rrect(5, 3.5, 14, 17, 2)
        line([(8.5, 8.5), (15.5, 8.5)])
        line([(8.5, 12), (15.5, 12)])
        line([(8.5, 15.5), (13, 15.5)])
    elif name == "moon":
        # 真透明镂空：大圆减去偏移小圆。旧写法拿底色盖小圆，背景一变
        # （渐变栏/悬停垫）就露出一块色斑（Smith 实证：深色下月亮按钮成白块黑斑）
        painter.setBrush(col)
        painter.setPen(Qt.PenStyle.NoPen)
        big = QPainterPath()
        big.addEllipse(QRectF(x + 4 * u, y + 4 * u, 16 * u, 16 * u))
        cut = QPainterPath()
        cut.addEllipse(QRectF(x + 9.5 * u, y + 2.5 * u, 12.5 * u, 12.5 * u))
        painter.drawPath(big.subtracted(cut))
    elif name == "sun":
        ellipse(8.5, 8.5, 7, 7)
        for a in range(0, 360, 45):
            r1, r2 = 5.4, 8.4
            line([(12 + r1 * math.cos(math.radians(a)), 12 + r1 * math.sin(math.radians(a))),
                  (12 + r2 * math.cos(math.radians(a)), 12 + r2 * math.sin(math.radians(a)))])
    elif name == "gear":
        cx, cy = x + 12 * u, y + 12 * u
        for a in range(0, 360, 45):
            r1, r2 = 6.0 * u, 9.2 * u
            painter.drawLine(QPointF(cx + r1 * math.cos(math.radians(a)), cy + r1 * math.sin(math.radians(a))),
                             QPointF(cx + r2 * math.cos(math.radians(a)), cy + r2 * math.sin(math.radians(a))))
        painter.drawEllipse(QRectF(cx - 6.4 * u, cy - 6.4 * u, 12.8 * u, 12.8 * u))
        painter.drawEllipse(QRectF(cx - 2.6 * u, cy - 2.6 * u, 5.2 * u, 5.2 * u))
    elif name == "info":
        ellipse(3.5, 3.5, 17, 17)
        painter.setBrush(col)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(x + 11 * u, y + 7 * u, 2.1 * u, 2.1 * u))
        line([(12, 10.8), (12, 16.5)])
    elif name == "refresh":
        painter.drawArc(QRectF(x + 4 * u, y + 4 * u, 16 * u, 16 * u), 40 * 16, 280 * 16)
        painter.setBrush(col)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([P(19.5, 2.8), P(21.2, 7.6), P(16.2, 7.4)]))
    elif name == "search":
        ellipse(4.5, 4.5, 13, 13)
        line([(15.8, 15.8), (20.5, 20.5)])
    elif name == "plus":
        line([(12, 5.5), (12, 18.5)])
        line([(5.5, 12), (18.5, 12)])
    elif name == "play":
        painter.setBrush(col)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([P(8.5, 6), P(8.5, 18), P(18, 12)]))
    elif name == "stop":
        painter.setBrush(col)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x + 6.5 * u, y + 6.5 * u, 11 * u, 11 * u), 2 * u, 2 * u)
    painter.restore()
