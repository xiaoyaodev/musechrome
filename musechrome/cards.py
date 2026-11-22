"""账号卡片容器：点卡片任意处即选中该账号；鼠标落点有提亮动画（Smith 要求）。"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QVariantAnimation, pyqtSignal
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QCursor, QPainter
from PyQt6.QtWidgets import QFrame

from .theme import C


def _mix(a: str, b: str, t: float) -> tuple[int, int, int]:
    ca, cb = QColor(a), QColor(b)
    return tuple(
        round(getattr(ca, ch)() + (getattr(cb, ch)() - getattr(ca, ch)()) * t)
        for ch in ("red", "green", "blue")
    )


class AccountCard(QFrame):
    """账号卡片：点卡片任意处即选中该账号；悬停时底色提亮、边框变深。"""

    clicked = pyqtSignal(str)

    def __init__(self, acc_id: str, parent=None):
        super().__init__(parent)
        self._acc_id = acc_id
        self._hover_t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_hover_value)
        # 卡片动画（Uiverse Cards 的悬停浮起译成 Qt）：静止时一层很淡的
        # 软影，悬停时影子变大变深、卡片像被轻轻抬起来；按下时再收回去
        # 一点，像被按下去。布局管着位置不能真位移，用影子做浮起感。
        self._press_t = 0.0
        self.restore_shadow()
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(160)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press_value)

    def _on_press_value(self, v):
        self._press_t = float(v)
        self._apply_shadow()

    def restore_shadow(self):
        """入场/脉冲动画借用过图形效果后，把常驻的软影还回来
        （现造一个，不复用旧引用——旧的已被 Qt 删了）。"""
        if self._shadow_fx() is None:
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect

            fx = QGraphicsDropShadowEffect(self)
            fx.setColor(QColor(0, 0, 0, 42))
            fx.setBlurRadius(10)
            fx.setOffset(0, 2)
            self.setGraphicsEffect(fx)
            self._apply_shadow()

    # ---- 选中卡片的招牌动效（Uiverse moody-owl 卡片译成 Qt） ----
    # 原组件：一个亮点沿卡片边框不停绕行，卡内还有一圈内嵌细线和
    # 左上角一道斜射光。这里：亮点绕行＋内嵌细线给选中卡片，斜射光
    # 改成悬停时左上角泛起的柔光（跟着悬停进度淡入淡出）。
    def set_selected(self, selected: bool):
        self.setObjectName("cardSel" if selected else "card")
        if selected:
            if not hasattr(self, "_runner"):
                self._runner_t = 0.0
                self._runner = QVariantAnimation(self)
                self._runner.setDuration(5200)
                self._runner.setStartValue(0.0)
                self._runner.setEndValue(1.0)
                self._runner.setLoopCount(-1)
                self._runner.valueChanged.connect(self._on_runner)
            if self._runner.state() != QVariantAnimation.State.Running:
                self._runner.start()
        elif hasattr(self, "_runner"):
            self._runner.stop()
        self.update()

    def _on_runner(self, v):
        self._runner_t = float(v)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt6.QtGui import QLinearGradient, QPainterPath, QRadialGradient
        from PyQt6.QtGui import QPen

        w, h = float(self.width()), float(self.height())
        if w < 10 or h < 10:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        painter.setClipPath(clip)
        accent = QColor(C["accent"])
        # 悬停柔光：左上角一团光晕，跟着悬停进度
        if self._hover_t > 0.01:
            rg = QRadialGradient(w * 0.06, -h * 0.12, w * 0.72)
            glow = QColor(accent)
            glow.setAlpha(int(24 * self._hover_t))
            rg.setColorAt(0, glow)
            end = QColor(accent)
            end.setAlpha(0)
            rg.setColorAt(1, end)
            painter.fillRect(self.rect(), rg)
        if self.objectName() == "cardSel":
            # 内嵌细线：上边和左边各一条，渐变淡出
            pen = QPen()
            pen.setWidthF(1.0)
            grad = QLinearGradient(w * 0.1, 0, w * 0.9, 0)
            a1 = QColor(accent); a1.setAlpha(80)
            a2 = QColor(accent); a2.setAlpha(14)
            grad.setColorAt(0, a1); grad.setColorAt(1, a2)
            pen.setBrush(grad)
            painter.setPen(pen)
            painter.drawLine(QPointF(w * 0.1, h * 0.09), QPointF(w * 0.9, h * 0.09))
            grad2 = QLinearGradient(0, h * 0.1, 0, h * 0.9)
            grad2.setColorAt(0, a1); grad2.setColorAt(1, a2)
            pen.setBrush(grad2)
            painter.setPen(pen)
            painter.drawLine(QPointF(w * 0.055, h * 0.1), QPointF(w * 0.055, h * 0.9))
            # 绕行亮点：沿边框匀速走， halo＋核心两层
            path = QPainterPath()
            path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 15, 15)
            pt = path.pointAtPercent(getattr(self, "_runner_t", 0.0))
            painter.setPen(Qt.PenStyle.NoPen)
            halo = QColor(accent); halo.setAlpha(52)
            painter.setBrush(halo)
            painter.drawEllipse(pt, 7.5, 7.5)
            mid = QColor(accent); mid.setAlpha(120)
            painter.setBrush(mid)
            painter.drawEllipse(pt, 3.8, 3.8)
            painter.setBrush(accent)
            painter.drawEllipse(pt, 2.1, 2.1)
        painter.end()

    def _shadow_fx(self):
        """当前挂着的影子效果；被入场/脉冲动画换成透明效果时返回 None。
        注意：图形效果被替换时旧对象会被 Qt 删掉，绝不能缓存引用
        再用（test27 开发中实证：缓存引用导致进程硬崩）。"""
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        fx = self.graphicsEffect()
        return fx if isinstance(fx, QGraphicsDropShadowEffect) else None

    def _apply_shadow(self):
        fx = self._shadow_fx()
        if fx is None:
            return
        lift = self._hover_t * (1.0 - 0.55 * self._press_t)
        fx.setBlurRadius(10 + 16 * lift)
        fx.setOffset(0, 2 + 6 * lift)
        fx.setColor(QColor(0, 0, 0, int(42 + 30 * lift)))

    def _on_hover_value(self, v):
        self._hover_t = float(v)
        self._apply_hover()
        self._apply_shadow()

    def _apply_hover(self):
        t = self._hover_t
        if t <= 0.001:
            self.setStyleSheet("")
            return
        r, g, b = _mix(C["surface"], C["text"], 0.08 * t)
        alpha = 0.92 + 0.08 * t
        if self.objectName() == "cardSel":
            border = f"1.5px solid {C['accent']}"
        else:
            br, bg2, bb = _mix(C["border"], C["border2"], t)
            border = f"1px solid rgb({br},{bg2},{bb})"
        self.setStyleSheet(
            "QFrame#card, QFrame#cardSel { "
            f"background: rgba({r},{g},{b},{alpha:.2f}); "
            f"border: {border}; border-radius: 16px; }}"
        )

    def _fade(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover_t)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._fade(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 移到卡片里的按钮上也会触发 leave：光标还在卡片范围内不算离开
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self._fade(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press_t)
        self._press_anim.setEndValue(1.0)
        self._press_anim.start()
        self.clicked.emit(self._acc_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press_t)
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()
        super().mouseReleaseEvent(event)
