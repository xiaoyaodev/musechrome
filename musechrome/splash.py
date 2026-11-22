"""启动动画（单独成文件，Smith 2026-11-22 要求）。

流程三段：
1. 入场（约 0.95s）：毛玻璃卡上，软件图标自上而下描画显现，
   标题淡入上浮，一道细线在标题下展开，卡片边框上有一颗亮点
   沿边绕行（账号卡选中态那颗亮点的同款动作）；
2. 化颗粒（约 0.95s）：整张卡截成一张图、按像素采样成两千多
   颗颗粒，从左到右起浪，颗粒向外轻散、缓缓下沉并淡出——卡
   本身同时隐去，只剩颗粒；
3. 衔接主页：颗粒开始散的同时发 reveal 信号，主窗口在颗粒
   层下方淡入，颗粒在主页上空散尽后启动层关闭——动画和主页
   是叠着交接的，不是先关动画再开主页。
点击可跳过：入场时点一下直达颗粒段，颗粒时点一下直接结束。
颜色全部取自 theme.C，跟随当前外观（深/浅）。
"""
import random

from PyQt6.QtCore import (
    QElapsedTimer,
    QPointF,
    QRectF,
    QTimer,
    QVariantAnimation,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from . import APP_NAME, __version__
from .iconutil import icon_path
from .theme import C, paint_frosted

W, H = 460, 300
INTRO_MS = 800
HOLD_MS = 150
DISSOLVE_MS = 900


class SplashScreen(QWidget):
    reveal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._phase = "intro"  # intro → hold → dissolve → done
        self._clock = QElapsedTimer()
        self._particles: list[dict] = []
        self._icon = QPixmap()
        p = icon_path()
        if p:
            self._icon = QPixmap(str(p))
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        # 兜底：4 秒后无论如何交接，不让动画卡住软件
        QTimer.singleShot(4500, self._force_finish)

    # ---------- 流程 ----------
    def start(self):
        self._clock.start()
        self._timer.start()

    def _tick(self):
        ms = self._clock.elapsed()
        if self._phase == "intro" and ms >= INTRO_MS:
            self._phase = "hold"
        elif self._phase == "hold" and ms >= INTRO_MS + HOLD_MS:
            self._begin_dissolve()
        elif self._phase == "dissolve" and ms >= self._dissolve_end:
            self._finish()
            return
        self.update()

    def _begin_dissolve(self):
        # 先把当前画面截下来采样成颗粒，再切到颗粒阶段
        shot = QPixmap(self.size())
        shot.fill(Qt.GlobalColor.transparent)
        pp = QPainter(shot)
        self._paint_card(pp, intro_t=1.0)
        pp.end()
        img = shot.toImage()
        # 颗粒颜色往当前主题的前景色靠 22%：卡和主页底色接近，
        # 不靠这一下，颗粒散到主页上会看不见
        fg = QColor(C["accent"])
        step = 3
        pts = []
        for y in range(0, H, step):
            for x in range(0, W, step):
                c = img.pixelColor(x, y)
                if c.alpha() > 26:
                    c = QColor(
                        int(c.red() + (fg.red() - c.red()) * 0.22),
                        int(c.green() + (fg.green() - c.green()) * 0.22),
                        int(c.blue() + (fg.blue() - c.blue()) * 0.22),
                        c.alpha(),
                    )
                    pts.append((x, y, c))
        random.shuffle(pts)
        pts = pts[:3600]
        rng = random.Random(20261122)
        self._particles = [
            {
                "x": float(x), "y": float(y), "c": c,
                "delay": (x / W) * 0.25,
                "vx": rng.uniform(-8, 9), "vy": rng.uniform(-5, 2),
                "r": rng.uniform(1.0, 2.4),
            }
            for (x, y, c) in pts
        ]
        self._phase = "dissolve"
        self._dissolve_start = self._clock.elapsed()
        self._dissolve_end = self._dissolve_start + DISSOLVE_MS
        # 主页这时开始在下面淡入，颗粒在它上空散尽（衔接）
        self.reveal.emit()

    def _finish(self):
        if self._phase == "done":
            return
        self._phase = "done"
        self._timer.stop()
        self.hide()
        self.close()

    def _force_finish(self):
        if self._phase in ("intro", "hold"):
            self._begin_dissolve()
        self._finish()

    def mousePressEvent(self, event):
        # 点击跳过：入场→直接化颗粒；颗粒中→立刻结束
        if self._phase in ("intro", "hold"):
            self._begin_dissolve()
        elif self._phase == "dissolve":
            self._finish()
        event.accept()

    # ---------- 绘制 ----------
    def _intro_t(self) -> float:
        if self._phase != "intro":
            return 1.0
        t = min(1.0, self._clock.elapsed() / INTRO_MS)
        return 1.0 - (1.0 - t) ** 3  # OutCubic

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._phase == "dissolve":
            self._paint_particles(p)
        else:
            self._paint_card(p, self._intro_t())
        p.end()

    def _paint_card(self, p: QPainter, intro_t: float):
        card = QPainterPath()
        card.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 20, 20)
        p.save()
        p.setClipPath(card)
        paint_frosted(
            p, self.rect(), C["bg_top"], C["bg_bottom"],
            C["blob1"], C["blob2"], C["grain_alpha"],
        )
        p.restore()
        p.setPen(QPen(QColor(C["selborder"]), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(card)
        # 边框绕行亮点（与账号卡选中态同款）
        if intro_t > 0.05:
            frac = (self._clock.elapsed() % 3400) / 3400.0
            pt = card.pointAtPercent(frac)
            for r, a in ((7.0, 46), (3.6, 110)):
                col = QColor(C["accent"])
                col.setAlpha(a)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawEllipse(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r))
            core = QColor(C["accent"])
            p.setBrush(core)
            p.drawEllipse(QRectF(pt.x() - 2.0, pt.y() - 2.0, 4, 4))
        cx = W / 2
        # 图标：自上而下显现（纵向揭开）＋淡入
        if not self._icon.isNull():
            size = 88.0
            p.save()
            p.setOpacity(intro_t)
            reveal_h = size * intro_t
            p.setClipRect(QRectF(cx - size / 2, 56, size, reveal_h))
            p.drawPixmap(
                QRectF(cx - size / 2, 56, size, size),
                self._icon,
                QRectF(0, 0, self._icon.width(), self._icon.height()),
            )
            p.restore()
        # 标题：淡入＋上浮
        rise = (1.0 - intro_t) * 9
        p.save()
        p.setOpacity(intro_t)
        f = QFont(self.font())
        f.setPointSize(19)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(C["text"]))
        p.drawText(
            QRectF(0, 158 + rise, W, 30),
            Qt.AlignmentFlag.AlignCenter,
            APP_NAME,
        )
        # 标题下细线：从中间向两边展开
        line_w = 118 * intro_t
        pen = QPen(QColor(C["accent"]), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(
            QPointF(cx - line_w / 2, 202 + rise),
            QPointF(cx + line_w / 2, 202 + rise),
        )
        f2 = QFont(self.font())
        f2.setPointSize(10)
        p.setFont(f2)
        p.setPen(QColor(C["dim"]))
        p.drawText(
            QRectF(0, 216 + rise, W, 20),
            Qt.AlignmentFlag.AlignCenter,
            f"v{__version__}",
        )
        p.restore()

    def _paint_particles(self, p: QPainter):
        tau_total = (self._clock.elapsed() - self._dissolve_start) / 1000.0
        p.setPen(Qt.PenStyle.NoPen)
        for pt in self._particles:
            tau = tau_total - pt["delay"]
            if tau <= 0:
                # 浪还没扫到：先按原样画一个点（卡面逐点变颗粒）
                p.setBrush(pt["c"])
                p.drawEllipse(
                    QRectF(pt["x"] - pt["r"] / 2, pt["y"] - pt["r"] / 2,
                           pt["r"], pt["r"])
                )
                continue
            life = 0.6
            k = tau / life
            if k >= 1.0:
                continue
            dx = pt["vx"] * tau
            dy = pt["vy"] * tau + 14 * tau * tau  # 缓缓下沉
            col = QColor(pt["c"])
            col.setAlpha(int(pt["c"].alpha() * (1.0 - k) ** 1.4))
            r = pt["r"] * (1.0 - 0.45 * k)
            p.setBrush(col)
            p.drawEllipse(
                QRectF(pt["x"] + dx - r / 2, pt["y"] + dy - r / 2, r, r)
            )


class WelcomeOverlay(QWidget):
    """进主页后的欢迎语（Smith 2026-11-22 要求）：「欢迎使用」在主页
    中央淡入、停留、淡出消失，苹果式的克制——大字、细体、宽字距、
    微微上浮，全程约 1.7s，不挡操作（鼠标穿透），放完自毁。"""

    TOTAL_MS = 1100

    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self.TOTAL_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self.deleteLater)

    def play(self):
        self.show()
        self.raise_()
        self._anim.start()

    def _on_value(self, value):
        self._t = float(value)
        self.update()

    def _alpha(self) -> float:
        t = self._t
        if t < 0.26:  # 淡入
            k = t / 0.26
            return 1.0 - (1.0 - k) ** 3
        if t < 0.65:  # 停留
            return 1.0
        k = (t - 0.65) / 0.35  # 淡出
        return max(0.0, 1.0 - k * k * (3 - 2 * k))

    def paintEvent(self, event):
        a = self._alpha()
        if a <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rise = (1.0 - self._t) * 10
        f = QFont(self.font())
        f.setPointSize(30)
        f.setWeight(QFont.Weight.Light)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 118)
        p.setFont(f)
        col = QColor(C["text"])
        col.setAlpha(int(255 * a))
        p.setPen(col)
        p.drawText(
            QRectF(0, -rise, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            "欢迎使用",
        )
        p.end()
