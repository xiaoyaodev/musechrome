"""特效按钮（Uiverse wicked-lionfish-83 的动效语言，Qt 原生重写）。

原组件（ShrinilDhorda/wicked-lionfish-83）三个招牌：
1. 按下时整个按钮缩到 0.92——这里用 QVariantAnimation 驱动
   _press_t，paintEvent 把按钮先画进一张位图再按比例缩小绘制，
   布局不受影响；
2. 悬停时背景换成一道横向渐变——原版是蓝青渐变，与全软件黑白
   纪律冲突，改成同色系的明暗渐变（黑按钮扫一道浅灰渐变、白
   按钮扫一道深灰渐变），颜色全部取自 theme.C，切主题自动跟随；
3. 按钮下方一圈大范围彩色光晕——改成中性软影（黑按钮/白按钮
   都用黑色低透明影），深浅两个主题下都不违和。
原组件还有一条 -webkit-box-reflect 倒影，卡片和工具栏里按钮
下方没有留倒影的位置，没有搬。

自成一个文件：按钮动效的增改都在这里，不往 widgets.py 里堆。
"""
from PyQt6.QtCore import QEasingCurve, QRectF, QVariantAnimation, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QPushButton

from .theme import C
from .widgets import AnimButton

_DARK_NAMES = ("primaryBtn", "darkBtn")


class FxButton(AnimButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._press_t = 0.0
        self._rendering = False
        self._shadow_done = False
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press_anim)
        self.pressed.connect(lambda: self._run_press(1.0))
        self.released.connect(lambda: self._run_press(0.0))

    # ---------- 按下缩小 ----------
    def _run_press(self, target: float):
        self._press_anim.stop()
        self._press_anim.setDuration(130 if target > self._press_t else 200)
        self._press_anim.setStartValue(self._press_t)
        self._press_anim.setEndValue(target)
        self._press_anim.start()

    def _on_press_anim(self, value):
        self._press_t = float(value)
        self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        if self._press_t > 0.003 and not self._rendering:
            # 先把正常状态画进位图，再整体缩小绘制（布局尺寸不变）
            self._rendering = True
            dpr = self.devicePixelRatioF()
            pix = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
            pix.setDevicePixelRatio(dpr)
            pix.fill(Qt.GlobalColor.transparent)
            pp = QPainter(pix)
            self.render(pp)
            pp.end()
            self._rendering = False
            painter = QPainter(self)
            s = 1.0 - 0.08 * self._press_t
            w2, h2 = self.width() * s, self.height() * s
            painter.drawPixmap(
                QRectF((self.width() - w2) / 2, (self.height() - h2) / 2, w2, h2),
                pix,
                QRectF(0, 0, self.width(), self.height()),
            )
            painter.end()
            return
        self._paint_body(event)

    def _paint_body(self, event):
        # 主按钮（黑底那类）挂一层中性软影，模拟原组件的光晕；
        # objectName 是构造之后才设的，所以第一次绘制时再补
        if not self._shadow_done:
            self._shadow_done = True
            if self.objectName() in _DARK_NAMES and self.graphicsEffect() is None:
                fx = QGraphicsDropShadowEffect(self)
                fx.setBlurRadius(14)
                fx.setOffset(0, 3)
                fx.setColor(QColor(0, 0, 0, 46))
                self.setGraphicsEffect(fx)
        QPushButton.paintEvent(self, event)
        if self._hover_t <= 0.01 or not self.isEnabled():
            return
        # 悬停渐变扫过：颜色取自当前主题，切外观自动跟随
        dark_btn = self.objectName() in _DARK_NAMES
        base = QColor(C["accent_text"] if dark_btn else C["accent"])
        t = self._hover_t
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        r = 12.0 if dark_btn else 10.0
        clip.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), r, r)
        painter.setClipPath(clip)
        grad = QLinearGradient(0, 0, self.width(), 0)
        # 三段渐变（弱→强→中）：test29 真机反馈"渐变不够明显"，
        # 峰值 alpha 提到原来的两倍左右，中段最亮、两头收
        a0 = int((10 if dark_btn else 8) * t)
        a1 = int((95 if dark_btn else 64) * t)
        c0 = QColor(base)
        c0.setAlpha(a0)
        c1 = QColor(base)
        c1.setAlpha(a1)
        c2 = QColor(base)
        c2.setAlpha(int(a0 + (a1 - a0) * 0.35))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.55, c1)
        grad.setColorAt(1.0, c2)
        painter.fillRect(self.rect(), grad)
        painter.end()
