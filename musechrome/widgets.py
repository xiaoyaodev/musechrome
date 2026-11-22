"""图标栏组件：毛玻璃边栏 + 带点击涟漪的图标按钮。

点击效果（Smith 定的）：按下时先垫一个半透明圆，再往外扩两圈
透明涟漪，松开就消。当前页的图标是实心圆角块（跟着主题走）。
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QListWidget, QPushButton, QStyleOptionViewItem, QStyledItemDelegate, QWidget

from .icons import draw_icon
from .theme import C, grain_tile, paint_frosted  # noqa: F401  (paint_frosted 供外部复用)


class RippleButton(QPushButton):
    """只画图标的按钮：悬停淡圈、选中实心块、点击涟漪。"""

    def __init__(self, icon_name: str, tooltip: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_bg: str | None = None  # moon 图标挖月牙用的底色
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ripple_r = 0.0
        self._ripple_a = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_ripple)
        self._pressed_flash = 0.0
        # 悬停动画：鼠标落上去时垫圈淡入着长大、图标微微放大，移开再收回去
        self._hover_t = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(190)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, value):
        self._hover_t = float(value)
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def set_icon(self, name: str, bg: str | None = None):
        self._icon_name = name
        self._icon_bg = bg
        self.update()

    def _on_ripple(self, value):
        v = float(value)
        self._ripple_r = 10 + v * 26
        self._ripple_a = 90 * (1 - v)
        self._pressed_flash = 46 * (1 - v)
        self.update()

    def mousePressEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(C["rail_active_bg"]))
            painter.drawRoundedRect(rect, 13, 13)
            fg = C["rail_active_fg"]
        else:
            fg = C["rail_icon"]
            if self._hover_t > 0.01:
                t = self._hover_t
                grow = 0.80 + 0.20 * t
                hw = (self.width() - 2) * grow / 2
                hh = (self.height() - 2) * grow / 2
                cxh, cyh = self.width() / 2, self.height() / 2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, int(26 * t)))
                painter.drawRoundedRect(
                    QRectF(cxh - hw, cyh - hh, 2 * hw, 2 * hh), 13, 13
                )
        # 点击涟漪：半透明垫圈 + 扩散圆环（画在图标下层）
        cx, cy = self.width() / 2, self.height() / 2
        if self._pressed_flash > 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(self._pressed_flash)))
            painter.drawEllipse(QRectF(cx - 20, cy - 20, 40, 40))
        if self._ripple_a > 1:
            r = self._ripple_r
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(self._ripple_a * 0.35)))
            painter.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            pen = painter.pen()
            from PyQt6.QtGui import QPen

            pen = QPen(QColor(255, 255, 255, int(self._ripple_a)), 1.6)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            r2 = r * 0.72
            pen.setColor(QColor(255, 255, 255, int(self._ripple_a * 0.7)))
            painter.setPen(pen)
            painter.drawEllipse(QRectF(cx - r2, cy - r2, 2 * r2, 2 * r2))
        bg = C["rail_active_bg"] if self.isChecked() else None
        isz = 24 * (1 + 0.13 * self._hover_t)
        draw_icon(painter, self._icon_name, cx - isz / 2, cy - isz / 2, isz, fg,
                  bg=(self._icon_bg or bg) if self._icon_name == "moon" else None)
        painter.end()


class AnimButton(QPushButton):
    """普通按钮 + 悬停动画：鼠标落上去，垫色从中间轻轻长开、淡入，
    移开再收回去。和图标栏按钮同一套动效语言，全软件统一。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_t = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_anim)
        self._shine_t = -1.0
        self._flood = False
        self._flood_t = 0.0
        self._flood_anim = QVariantAnimation(self)
        self._flood_anim.setDuration(900)
        self._flood_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._flood_anim.valueChanged.connect(self._on_flood_anim)
        self._shine_anim = QVariantAnimation(self)
        self._shine_anim.setDuration(480)
        self._shine_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shine_anim.valueChanged.connect(self._on_shine_anim)
        self._shine_anim.finished.connect(lambda: setattr(self, "_shine_t", -1.0))

    def _on_hover_anim(self, value):
        self._hover_t = float(value)
        self.update()

    def _on_shine_anim(self, value):
        self._shine_t = float(value)
        self.update()

    def enable_flood_fx(self):
        """开启洪泛圆点特效（Uiverse purple-kangaroo-17）：五个圆点
        平时散在按钮外，悬停时汇聚到中心放大、把按钮淹没成反色，
        文字随之反色。原组件是蓝圆点黑按钮；这里圆点用按钮的反色
        （黑底白点/白底黑点），保持全软件黑白纪律。"""
        self._flood = True

    def _on_flood_anim(self, value):
        self._flood_t = float(value)
        self.update()

    def _run_flood(self, target: float):
        self._flood_anim.stop()
        self._flood_anim.setDuration(900 if target > self._flood_t else 550)
        self._flood_anim.setStartValue(self._flood_t)
        self._flood_anim.setEndValue(target)
        self._flood_anim.start()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        if self._flood and self.isEnabled():
            self._run_flood(1.0)
        # 主按钮（黑底那类）悬停时一道单色微光斜扫过去，Uiverse 按钮
        # 常见的 shine 动效；只在进入时扫一次，低透明、不发光不花哨
        if self.objectName() in ("primaryBtn", "darkBtn") and self.isEnabled():
            self._shine_anim.stop()
            self._shine_anim.setStartValue(0.0)
            self._shine_anim.setEndValue(1.0)
            self._shine_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        if self._flood:
            self._run_flood(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self._flood:
            self._paint_flood(event)
            return
        super().paintEvent(event)
        if self._hover_t <= 0.01 or not self.isEnabled():
            return
        t = self._hover_t
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grow = 0.86 + 0.14 * t
        w, h = float(self.width()), float(self.height())
        ow, oh = w * grow, h * grow
        col = QColor(C["text"])
        col.setAlpha(int(22 * t))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        painter.drawRoundedRect(QRectF((w - ow) / 2, (h - oh) / 2, ow, oh), 9, 9)
        painter.end()
        if self._shine_t >= 0.0 and self.isEnabled():
            import math

            from PyQt6.QtGui import QPainterPath, QPolygonF
            from PyQt6.QtCore import QPointF

            st = self._shine_t
            sp = QPainter(self)
            sp.setRenderHint(QPainter.RenderHint.Antialiasing)
            radius = 12.0 if self.objectName() in ("primaryBtn", "darkBtn") else 10.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
            sp.setClipPath(path)
            cx = -0.35 * w + st * 1.75 * w
            alpha = int(30 * math.sin(math.pi * min(1.0, max(0.0, st))))
            sp.setPen(Qt.PenStyle.NoPen)
            sp.setBrush(QColor(255, 255, 255, alpha))
            sp.drawPolygon(
                QPolygonF(
                    [
                        QPointF(cx - 16, h),
                        QPointF(cx + 2, 0),
                        QPointF(cx + 20, 0),
                        QPointF(cx + 2, h),
                    ]
                )
            )
            sp.end()


    def _paint_flood(self, event):
        # 先让系统画底色（文字临时清空，免得被圆点盖住的那份文字透出来）
        txt = self.text()
        self.setText("")
        super().paintEvent(event)
        self.setText(txt)
        w, h = float(self.width()), float(self.height())
        t = self._flood_t
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtGui import QPainterPath

        # 裁剪比按钮本体大一圈：样式表底色画在满幅矩形上，裁剪小了
        # 边缘会露出一线原色（Smith 真机图：淹满了还漏一圈白边）
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(-1, -1, w + 2, h + 2), 13, 13)
        painter.setClipPath(clip)
        cx, cy = w / 2, h / 2
        sx = max(1.0, w / 150.0)
        flood_col = QColor(C["accent_text"])
        painter.setPen(Qt.PenStyle.NoPen)
        # 满幅打底：进度过半后先铺一层纯色（透明度随进度涨满），
        # 圆点只负责动势——铺满这件事不再指望圆的几何覆盖
        if t > 0.5:
            base = QColor(flood_col)
            base.setAlpha(int(255 * min(1.0, (t - 0.5) / 0.35)))
            painter.setBrush(base)
            painter.drawRoundedRect(QRectF(-1, -1, w + 2, h + 2), 13, 13)
        painter.setBrush(flood_col)
        # 起始偏移放大 1.4 倍：静止时所有圆都完整地待在按钮外，
        # 不再有圆边偷偷探进按钮底沿（Smith 图二按钮下那条杠）
        offsets = [(-74, -90), (-134, 29), (-4, 41), (78, 31), (78, -85)]
        # 终半径必须盖住按钮的半对角线：test29 真机上按钮较宽，
        # 旧半径盖不满，左右边缘各剩一条没淹到的楔形（Smith 图二三）
        import math

        r_start = 15.0 * sx
        r_end = math.hypot(w, h) / 2 + 6
        for ox, oy in offsets:
            x = cx + ox * sx * (1.0 - t)
            y = cy + oy * (1.0 - t)
            r = r_start + (r_end - r_start) * t
            painter.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
        # 文字：颜色随洪泛进度在反色和原色之间走（淹满时完成反色）
        a = QColor(C["accent_text"])
        b = QColor(C["accent"])
        col = QColor(
            int(a.red() + (b.red() - a.red()) * t),
            int(a.green() + (b.green() - a.green()) * t),
            int(a.blue() + (b.blue() - a.blue()) * t),
        )
        painter.setPen(col)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, txt)
        painter.end()


class RailWidget(QWidget):
    """左侧 68px 图标栏：自己画渐变 + 颗粒（和主底图同款毛玻璃）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(68)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtGui import QLinearGradient

        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(C["rail_top"]))
        grad.setColorAt(1, QColor(C["rail_bottom"]))
        painter.fillRect(self.rect(), grad)
        tile = grain_tile()
        painter.setOpacity(C["grain_alpha"])
        x = 0
        while x < self.width():
            y = 0
            while y < self.height():
                painter.drawPixmap(x, y, tile)
                y += tile.height()
            x += tile.width()
        painter.setOpacity(1.0)
        painter.end()


class _HoverDelegate(QStyledItemDelegate):
    """列表行绘制：勾选框和底色走系统样式，文字自己画（两行、留足间距），
    再叠一层动画垫色（悬停长开、按下闪一下，跟按钮同一套动效）。

    文字自己画是因为系统代理画两行文字时会把行高算矮、文字压到
    勾选框上（test17 真机截图实证），自己画才能把版式钉死。
    """

    def editorEvent(self, event, model, option, index):
        # 勾选完全由 HoverListWidget.mousePressEvent 手动翻转；
        # 这里把鼠标事件都确认处理掉，防止原生代理在松开鼠标时
        # 按样式的勾选框矩形再翻一次（点框子时两边抵消＝勾不上）
        if event.type() in (
            event.Type.MouseButtonPress,
            event.Type.MouseButtonRelease,
            event.Type.MouseButtonDblClick,
        ):
            return True
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option, index):
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QFontMetrics

        fm = QFontMetrics(option.font)
        return QSize(option.rect.width(), fm.height() * 2 + 18)

    def paint(self, painter, option, index):
        from PyQt6.QtGui import QFontMetrics
        from PyQt6.QtWidgets import QStyle

        lst = self.parent()
        # 本体：让样式只画底色，文字和勾选框都自己画——系统勾选框在
        # 浅色主题下淡得看不见（Smith 图四实证），自己画才能两边都清楚
        opt = option.__class__(option)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        opt.text = ""
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        widget = option.widget
        style = widget.style() if widget is not None else QApplication_style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        check = index.data(Qt.ItemDataRole.CheckStateRole)
        if check is not None:
            from PyQt6.QtGui import QPen

            # data() 给的是 int（2=勾上），不能直接跟枚举比（永远 False，
            # 勾上也画成空框——Smith 一直说「勾选不了」的真凶之一）
            try:
                checked = Qt.CheckState(check) == Qt.CheckState.Checked
            except Exception:
                checked = check == 2
            box = QRectF(
                option.rect.x() + 9,
                option.rect.y() + (option.rect.height() - 18) / 2,
                18, 18,
            )
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # 描画进度：勾上时对勾一笔笔划出来（Uiverse checkbox 的
            # stroke-dash 动画译成 Qt），取消时反向收回
            prog = 1.0 if checked else 0.0
            if lst is not None and hasattr(lst, "check_progress"):
                prog = lst.check_progress(index.row(), checked)
            if prog > 0.01:
                painter.setPen(Qt.PenStyle.NoPen)
                fill = QColor(C["accent"])
                fill.setAlphaF(0.25 + 0.75 * prog)
                painter.setBrush(fill)
                painter.drawRoundedRect(box, 5, 5)
                pen = QPen(QColor(C["accent_text"]))
                pen.setWidthF(2.0)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                from PyQt6.QtCore import QPointF

                cx, cy = box.center().x(), box.center().y()
                p1 = QPointF(cx - 4.5, cy - 0.3)
                p2 = QPointF(cx - 1.2, cy + 3.2)
                p3 = QPointF(cx + 4.8, cy - 3.4)
                len1, len2 = 4.81, 8.92
                drawn = prog * (len1 + len2)
                if drawn > 0:
                    k = min(1.0, drawn / len1)
                    painter.drawLine(
                        p1, QPointF(p1.x() + (p2.x() - p1.x()) * k,
                                    p1.y() + (p2.y() - p1.y()) * k)
                    )
                if drawn > len1:
                    k = min(1.0, (drawn - len1) / len2)
                    painter.drawLine(
                        p2, QPointF(p2.x() + (p3.x() - p2.x()) * k,
                                    p2.y() + (p3.y() - p2.y()) * k)
                    )
            if prog < 0.99:
                pen = QPen(QColor(C["border2"]))
                pen.setWidthF(1.5)
                painter.setPen(pen)
                if prog <= 0.01:
                    painter.setBrush(QColor(C["surface"]))
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box, 5, 5)
            painter.restore()
        # 文字：勾选框右侧起，两行（第一行主色、第二行弱色小一号）
        lines = text.split("\n")
        fm = QFontMetrics(option.font)
        x = option.rect.x() + 36
        y = option.rect.y() + 9 + fm.ascent()
        painter.save()
        painter.setFont(option.font)
        painter.setPen(QColor(C["text"]))
        painter.drawText(x, y, lines[0] if lines else "")
        if len(lines) > 1:
            small = painter.font()
            small.setPointSizeF(max(8.0, small.pointSizeF() - 1.5))
            painter.setFont(small)
            painter.setPen(QColor(C["dim"]))
            painter.drawText(x, y + fm.height() + 2, lines[1])
        painter.restore()
        # 动画垫色
        if lst is None:
            return
        row = index.row()
        t = 0.0
        if row == lst._hover_row:
            t = max(t, lst._hover_t)
        if row == lst._press_row:
            t = max(t, lst._press_t)
        if t <= 0.01:
            return
        rect = option.rect.adjusted(2, 1, -2, -1)
        grow = 0.86 + 0.14 * t
        ow, oh = rect.width() * grow, rect.height() * grow
        col = QColor(C["text"])
        col.setAlpha(int(24 * t))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        painter.drawRoundedRect(
            QRectF(
                rect.x() + (rect.width() - ow) / 2,
                rect.y() + (rect.height() - oh) / 2,
                ow, oh,
            ),
            8, 8,
        )
        painter.restore()


def QApplication_style():
    from PyQt6.QtWidgets import QApplication

    return QApplication.style()


class TitleBar(QWidget):
    """自绘标题栏（配无边框窗口）：黑白横向渐变＋颗粒，左边软件图标和
    标题，右边最小化/关闭按钮；按住空白处拖动可以移动窗口。"""

    def __init__(self, title: str, icon_pixmap=None, parent=None):
        from PyQt6.QtWidgets import QHBoxLayout, QLabel

        super().__init__(parent)
        self.setFixedHeight(38)
        self._drag_from = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(8)
        if icon_pixmap is not None:
            ic = QLabel()
            ic.setPixmap(icon_pixmap)
            lay.addWidget(ic)
        lb = QLabel(title)
        lb.setStyleSheet("font-size: 12.5px;")
        lay.addWidget(lb)
        lay.addStretch(1)
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("titleBtn")
        self.btn_min.setFixedSize(46, 38)
        self.btn_min.clicked.connect(lambda: self.window().showMinimized())
        lay.addWidget(self.btn_min)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("titleBtn")
        self.btn_close.setFixedSize(46, 38)
        self.btn_close.clicked.connect(lambda: self.window().close())
        lay.addWidget(self.btn_close)

    def paintEvent(self, event):
        from PyQt6.QtGui import QLinearGradient

        painter = QPainter(self)
        rect = self.rect()
        top = QColor(C["bg_top"]).lighter(118)
        bottom = QColor(C["bg_bottom"])
        grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        painter.fillRect(rect, grad)
        tile = grain_tile()
        painter.setOpacity(C.get("grain_alpha", 0.05))
        x = rect.left()
        while x < rect.right():
            y = rect.top()
            while y < rect.bottom():
                painter.drawPixmap(x, y, tile)
                y += tile.height()
            x += tile.width()
        painter.setOpacity(1.0)
        painter.setPen(QColor(C["border"]))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_from is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_from)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_from = None
        super().mouseReleaseEvent(event)


class HoverListWidget(QListWidget):
    """带鼠标落点动画的列表：悬停行垫色长开，按下闪一下。

    和 AnimButton 同一套动效语言（170ms、OutCubic、垫色自 C['text']），
    用在插件助手两个列表上，Smith 要求全软件的点击/落点都有反馈。
    """

    # checkable_rows=True 时：点一行任意处切换该行勾选，纯手动实现，
    # 不依赖系统样式的勾选框矩形、也不依赖 ItemIsUserCheckable 标志
    # （真机上系统那条路出现过怎么点都勾不上，Smith 实证）
    checkable_rows = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._hover_row = -1
        self._hover_t = 0.0
        self._press_row = -1
        self._press_t = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_anim)
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(280)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press_anim)
        self.setItemDelegate(_HoverDelegate(self))
        self.itemPressed.connect(self._on_item_pressed)
        # 勾选动画进度：{行号: (起始时刻ms, 起始进度, 目标进度, 时长ms)}
        import time as _time

        self._time = _time
        self._check_prog: dict[int, tuple] = {}
        from PyQt6.QtCore import QTimer

        self._check_timer = QTimer(self)
        self._check_timer.setInterval(15)
        self._check_timer.timeout.connect(self._tick_check_prog)

    def check_progress(self, row: int, checked: bool) -> float:
        """某行对勾的描画进度 0..1：动画中按时间插值，否则跟勾选状态。"""
        anim = self._check_prog.get(row)
        if anim is None:
            return 1.0 if checked else 0.0
        t0, p0, p1, dur = anim
        k = (self._time.monotonic() * 1000 - t0) / max(1.0, dur)
        if k >= 1.0:
            return p1
        eased = 1.0 - (1.0 - k) ** 3
        return p0 + (p1 - p0) * eased

    def _tick_check_prog(self):
        now = self._time.monotonic() * 1000
        done = [r for r, a in self._check_prog.items() if now - a[0] >= a[3]]
        for r in done:
            del self._check_prog[r]
        if not self._check_prog:
            self._check_timer.stop()
        self.viewport().update()

    def _start_check_anim(self, row: int, to_checked: bool):
        cur = self.check_progress(row, not to_checked)
        self._check_prog[row] = (
            self._time.monotonic() * 1000,
            cur,
            1.0 if to_checked else 0.0,
            260.0 if to_checked else 180.0,
        )
        if not self._check_timer.isActive():
            self._check_timer.start()

    def clear(self):
        self._check_prog.clear()
        super().clear()

    def _on_hover_anim(self, value):
        self._hover_t = float(value)
        self.viewport().update()

    def _on_press_anim(self, value):
        self._press_t = float(value)
        self.viewport().update()

    def _on_item_pressed(self, item):
        self._press_row = self.row(item)
        self._press_anim.stop()
        self._press_anim.setStartValue(1.0)
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()

    def mousePressEvent(self, event):
        # 点行里任何地方都能勾选/取消（Smith 要求）：纯手动翻转，一次点击只翻一次。
        # 不再走系统勾选通道——它依赖样式算出的勾选框矩形和可勾选标志，
        # 真机上出过「点文字、点框子都勾不上」，这条路整个绕开
        if self.checkable_rows and event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item is not None:
                to_checked = item.checkState() != Qt.CheckState.Checked
                item.setCheckState(
                    Qt.CheckState.Checked if to_checked else Qt.CheckState.Unchecked
                )
                self._start_check_anim(self.row(item), to_checked)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        row = self.row(item) if item is not None else -1
        if row != self._hover_row:
            self._hover_row = row
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_t)
            self._hover_anim.setEndValue(1.0 if row >= 0 else 0.0)
            self._hover_anim.start()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_row = -1
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)


class ToggleSwitch(QWidget):
    """滑动开关（Uiverse Toggle-switches 的动效译成 Qt）：轨道变色＋
    圆钮滑动，260ms OutCubic。给设置页两个开关选项用，替掉系统原生
    复选框——全软件自绘风格保持一致。API 与 QCheckBox 对齐
    （isChecked/setChecked/toggled），调用方不用改。"""

    from PyQt6.QtCore import pyqtSignal as _sig

    toggled = _sig(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._checked = False
        self._t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value):
        self._t = float(value)
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, value, animate=False):
        value = bool(value)
        if value == self._checked and not animate:
            self._t = 1.0 if value else 0.0
            self.update()
            return
        self._checked = value
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._t)
            self._anim.setEndValue(1.0 if value else 0.0)
            self._anim.start()
        else:
            self._t = 1.0 if value else 0.0
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked, animate=True)
            self.toggled.emit(self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked, animate=True)
            self.toggled.emit(self._checked)
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._t
        off = QColor(C["border2"])
        on = QColor(C["accent"])
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        tw, th = float(self.width()), float(self.height())
        painter.drawRoundedRect(QRectF(0.5, 0.5, tw - 1, th - 1), (th - 1) / 2, (th - 1) / 2)
        knob_d = th - 6.0
        x = 3.0 + t * (tw - knob_d - 6.0)
        knob_col = QColor(C["accent_text"]) if t > 0.5 else QColor(C["surface"])
        pen = QPen(QColor(C["border2"]))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(knob_col)
        painter.drawEllipse(QRectF(x, 3.0, knob_d, knob_d))
        painter.end()


class Spinner(QWidget):
    """单色圆环加载动画（Uiverse loaders 的圆环译成 Qt）：一段 270°
    圆弧匀速转，给检测/更新这类等待一个动态反馈。"""

    def __init__(self, size=20, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        from PyQt6.QtCore import QTimer

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle - 6) % 360
        self.update()

    def start(self):
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(C["accent"]))
        pen.setWidthF(2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 2.0
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        painter.drawArc(rect, -self._angle * 16, 270 * 16)
        painter.end()


class SwitchRow(QWidget):
    """开关＋说明文字一整行：点行里任何地方（开关、文字、空白）都切换。

    必须是正经子类、把 mousePressEvent 写在类上——把方法挂到实例
    属性上 Qt 的事件派发不认（test26 真机实证：整行点不动）。
    文字是 QLabel，它不处理鼠标按下、事件会上传到本行，正好触发切换；
    开关自己处理按下时会 accept，不会上传造成二次翻转。"""

    def __init__(self, switch: ToggleSwitch, label: QWidget, parent=None):
        super().__init__(parent)
        self._switch = switch
        from PyQt6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(10)
        row.addWidget(switch)
        row.addWidget(label)
        row.addStretch(1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._switch.setChecked(not self._switch.isChecked(), animate=True)
            self._switch.toggled.emit(self._switch.isChecked())
            event.accept()
            return
        super().mousePressEvent(event)
