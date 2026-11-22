"""日夜切换开关（Uiverse honest-dolphin-65 "Solstice day/night
switch" 的 Qt 原生重写，单独成文件）。

原组件的招牌动作，这里逐条译过来：
- 圆钮从轨道一端滑到另一端，带回弹的缓动（CSS 的
  cubic-bezier(0.34, 1.4, 0.64, 1) → Qt 的 OutBack）；
- 钮里的太阳/月亮交叉淡入淡出，同时旋转＋缩放（一边转出缩小、
  一边转入放大）；
- 夜态时轨道里三颗小星星闪烁（正弦相位，钮滑到位后才开始闪）；
- 轨道背景在日/夜之间渐变。
颜色按全软件黑白纪律改成单色：日态浅灰轨道＋白钮黑太阳，
夜态深灰轨道＋浅钮黑月亮。功能就是真切换：clicked 信号连到
MainWindow.toggle_theme，状态由 set_dark 同步（不是只换皮）。
"""
import math
import time

from PyQt6.QtCore import (
    QEasingCurve,
    QRectF,
    QTimer,
    QVariantAnimation,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import QWidget

from .icons import draw_icon


def _mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
    )


class DayNightSwitch(QWidget):
    clicked = pyqtSignal()

    W, H = 54, 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._t = 0.0  # 0=日（浅色） 1=夜（深色）
        self._dark = False
        self._hover = False
        self._anim = QVariantAnimation(self)
        ease = QEasingCurve(QEasingCurve.Type.OutBack)
        ease.setOvershoot(1.2)
        self._anim.setEasingCurve(ease)
        self._anim.setDuration(520)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.finished.connect(self._sync_twinkle)
        self._twinkle = QTimer(self)
        self._twinkle.setInterval(60)
        self._twinkle.timeout.connect(self.update)

    # ---------- 状态 ----------
    def set_dark(self, dark: bool, animate: bool = True):
        self._dark = dark
        target = 1.0 if dark else 0.0
        if not animate or not self.isVisible():
            self._anim.stop()
            self._t = target
            self._sync_twinkle()
            self.update()
            return
        self._twinkle.stop()
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.start()

    def is_dark(self) -> bool:
        return self._dark

    def _on_anim(self, value):
        self._t = float(value)
        self.update()

    def _sync_twinkle(self):
        # 星星只在夜态落定后闪，动画途中和日态都停表省电
        if self._dark and abs(self._t - 1.0) < 0.01:
            self._twinkle.start()
        else:
            self._twinkle.stop()

    # ---------- 交互（功能本体：点击/按键都发 clicked） ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.clicked.emit()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        t = max(0.0, min(1.0, self._t))
        w, h = float(self.W), float(self.H)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QPainterPath()
        track.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), (h - 1) / 2, (h - 1) / 2)
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, _mix("#e9e9ed", "#0c0c0f", t))
        grad.setColorAt(1.0, _mix("#f7f7f9", "#26262c", t))
        p.fillPath(track, grad)
        p.save()
        p.setClipPath(track)
        # 悬停提亮（原组件 hover brightness 的单色版）
        if self._hover:
            p.fillRect(self.rect(), QColor(255, 255, 255, 14))
        # 星星：夜态浮现＋闪烁（相位各错开）
        now = time.time()
        for i, (sx, sy, r) in enumerate([(11, 8, 2.4), (19, 19, 1.8), (28, 9, 1.5)]):
            tw = 0.5 + 0.5 * math.sin(now * 2.6 + i * 2.1)
            alpha = int(235 * t * (0.45 + 0.55 * tw))
            if alpha > 4:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, alpha))
                p.drawEllipse(QRectF(sx - r / 2, sy - r / 2, r, r))
        p.restore()
        # 轨道描边
        edge = _mix("#c9c9cf", "#3d3d44", t)
        p.setPen(edge)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(track)
        # 圆钮：位置随 t 滑动（OutBack 动画值可略超 1，cx 已钳制 t，
        # 这里用未钳制的 _t 让回弹的过冲也能体现在位置上）
        d = 22.0
        cx = 3 + d / 2 + self._t * (w - 6 - d)
        cy = h / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 42))
        p.drawEllipse(QRectF(cx - d / 2, cy - d / 2 + 1.5, d, d))
        rg = QRadialGradient(cx - 6, cy - 7, d * 0.95)
        rg.setColorAt(0.0, QColor("#ffffff"))
        rg.setColorAt(1.0, _mix("#e8e8ec", "#d5d5dd", t))
        p.setBrush(rg)
        p.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))
        # 钮内图标交叉变形：太阳转出缩小、月亮转入放大（反之亦然）
        icon = 14.0
        p.save()
        p.translate(cx, cy)
        p.rotate(120 * t)
        p.scale(1 - 0.6 * t, 1 - 0.6 * t)
        p.setOpacity(1 - t)
        draw_icon(p, "sun", -icon / 2, -icon / 2, icon, "#17171a")
        p.restore()
        p.save()
        p.translate(cx, cy)
        p.rotate(-120 * (1 - t))
        s = 0.4 + 0.6 * t
        p.scale(s, s)
        p.setOpacity(t)
        draw_icon(p, "moon", -icon / 2, -icon / 2, icon, "#17171a")
        p.restore()
        p.end()
