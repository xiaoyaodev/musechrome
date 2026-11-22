"""主题：黑白渐变 + 苹果式简约（v1.9.0 设计定稿）。

两套外观是一对：dark = 曜黑（深色），light = 黑白分明（浅色），
靠边栏底部的月亮/太阳按钮切换（进程级重启，和手动重开一样稳）。
界面底图由 FrostedRoot 绘制：竖向渐变 + 高斯柔光团 + 细颗粒，
卡片和边栏用半透明色盖在上面，就是毛玻璃的感觉。
"""

from __future__ import annotations

import random

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPalette, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QWidget

PALETTES = {
    "dark": {
        "bg": "#131316", "bg_top": "#1d1d20", "bg_bottom": "#0a0a0c", "canvas": "#101013",
        "surface": "#1b1b1f", "card_rgba": "rgba(27,27,31,0.92)",
        "card_sel_rgba": "rgba(38,38,44,0.95)",
        "border": "#2e2e35", "border2": "#3d3d46",
        "text": "#f5f5f7", "body": "#d9d9de", "dim": "#98989f",
        "hover": "#26262c", "pressed": "#30303a",
        "selbg": "#2e2e35", "cardSel": "#26262c", "selborder": "#9a9aa2",
        "segbg": "rgba(255,255,255,0.07)", "segborder": "#33333c",
        "noticeBg": "rgba(255,255,255,0.06)", "noticeText": "#e8e8ec",
        "accent": "#f5f5f7", "accent_text": "#111113",
        "rail_top": "#2e2e33", "rail_bottom": "#121214",
        "rail_icon": "#aeaeb6", "rail_active_bg": "#f5f5f7", "rail_active_fg": "#111113",
        "ok": "#30d158", "blob1": (255, 255, 255, 13), "blob2": (255, 255, 255, 5),
        "grain_alpha": 0.055,
    },
    "light": {
        "bg": "#f2f2f5", "bg_top": "#fdfdfd", "bg_bottom": "#e9e9ed", "canvas": "#f1f1f4",
        "surface": "#ffffff", "card_rgba": "rgba(255,255,255,0.88)",
        "card_sel_rgba": "rgba(255,255,255,0.97)",
        "border": "#dedee3", "border2": "#c6c6cd",
        "text": "#1d1d1f", "body": "#3a3a3e", "dim": "#86868b",
        "hover": "#f0f0f3", "pressed": "#e2e2e8",
        "selbg": "#ececf0", "cardSel": "#f6f6f8", "selborder": "#4a4a50",
        "segbg": "rgba(0,0,0,0.05)", "segborder": "#dedee3",
        "noticeBg": "rgba(0,0,0,0.045)", "noticeText": "#3a3a3e",
        "accent": "#111113", "accent_text": "#ffffff",
        "rail_top": "#ffffff", "rail_bottom": "#e7e7eb",
        "rail_icon": "#6e6e73", "rail_active_bg": "#111113", "rail_active_fg": "#ffffff",
        "ok": "#34c759", "blob1": (255, 255, 255, 75), "blob2": (190, 190, 200, 30),
        "grain_alpha": 0.045,
    },
}

# 当前主题的颜色表：建界面时读它；set_theme 原地换内容，
# 已经 import 了 C 的模块不用重新导入就能读到新值。
C = dict(PALETTES["dark"])


def set_theme(name: str | None) -> None:
    C.clear()
    C.update(PALETTES.get(name or "dark", PALETTES["dark"]))


def app_style(theme: str | None) -> str:
    p = PALETTES.get(theme or "dark", PALETTES["dark"])
    return f"""
QMainWindow {{ background: {p['bg']}; color: {p['text']}; }}
QDialog {{ background: {p['surface']}; color: {p['text']}; }}
QListWidget {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 12px; outline: 0; }}
QListWidget::item {{ padding: 8px; color: {p['text']}; border: none; }}
QListWidget::item:selected {{ background: {p['selbg']}; color: {p['text']}; border: none; }}
QListWidget::item:focus {{ background: {p['selbg']}; border: none; outline: none; }}
QPushButton {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border2']};
              border-radius: 10px; padding: 7px 14px; }}
QPushButton:hover {{ background: {p['hover']}; }}
QPushButton:pressed {{ background: {p['pressed']}; }}
QPushButton#primaryBtn {{ background: {p['accent']}; color: {p['accent_text']}; border: none;
              font-weight: bold; padding: 9px 20px; border-radius: 12px; }}
QPushButton#primaryBtn:hover {{ opacity: 0.85; }}
QPushButton#addAccountBtn {{ background: {p['accent']}; color: {p['accent_text']}; border: none;
              font-weight: bold; padding: 9px 20px; border-radius: 12px; }}
QPushButton#darkBtn {{ background: {p['accent']}; color: {p['accent_text']}; border: none;
              font-weight: bold; padding: 9px; border-radius: 12px; }}
QPushButton#segBtn {{ background: transparent; color: {p['dim']}; border: none; border-radius: 8px; padding: 4px 10px; font-size: 12px; }}
QPushButton#segBtn:hover {{ color: {p['text']}; }}
QPushButton#segBtn:checked {{ background: {p['accent']}; color: {p['accent_text']}; font-weight: bold; }}
QPushButton#miniBtn {{ background: transparent; color: {p['dim']}; border: none; padding: 4px 6px; }}
QPushButton#miniBtn:hover {{ color: {p['text']}; background: {p['hover']}; border-radius: 7px; }}
QPushButton#titleBtn {{ background: transparent; color: {p['text']}; border: none; border-radius: 0; padding: 0; font-size: 13px; }}
QPushButton#titleBtn:hover {{ background: {p['hover']}; }}
QPushButton#presetBtn {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border2']};
              border-radius: 10px; padding: 6px 14px; font-size: 12.5px; }}
QPushButton#presetBtn:hover {{ background: {p['hover']}; }}
QLineEdit, QSpinBox, QComboBox {{ background: {p['surface']}; color: {p['text']};
              border: 1px solid {p['border2']}; border-radius: 10px; padding: 6px 10px; }}
QLineEdit#searchBox {{ border-radius: 10px; padding: 7px 14px; background: {p['segbg']}; border: 1px solid transparent; }}
QPlainTextEdit {{ background: {p['surface']}; color: {p['body']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QLabel {{ color: {p['text']}; }}
QFrame#browserSeg {{ background: {p['segbg']}; border: 1px solid {p['segborder']}; border-radius: 10px; }}
QFrame#card {{ background: {p['card_rgba']}; border: 1px solid {p['border']}; border-radius: 16px; }}
QFrame#cardSel {{ background: {p['card_sel_rgba']}; border: 1.5px solid {p['selborder']}; border-radius: 16px; }}
QFrame#noticeBar {{ background: {p['noticeBg']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 12px; background: transparent; top: -1px; }}
QTabBar::tab {{ background: {p['segbg']}; color: {p['dim']}; border: 1px solid {p['border']};
              border-radius: 9px; padding: 7px 18px; margin-right: 6px; }}
QTabBar::tab:selected {{ background: {p['accent']}; color: {p['accent_text']}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ background: {p['selbg']}; color: {p['text']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border2']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def _paint_bg(widget: QWidget) -> None:
    """让容器不刷自己的底色，露出下层 FrostedRoot 画的渐变毛玻璃底图。"""
    widget.setAutoFillBackground(False)


class FrostedHost(QWidget):
    """自己画毛玻璃底的内容宿主（卡片区用）：平铺纯色画布太闷，
    宿主自画渐变＋柔光＋颗粒，空区域也有层次。"""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_frosted(
            painter, self.rect(), C["bg_top"], C["bg_bottom"],
            C["blob1"], C["blob2"], C["grain_alpha"],
        )
        super().paintEvent(event)


def fix_scroll(scroll: QWidget, host: QWidget | None = None) -> None:
    """滚动区在真 Windows 上透不出下层底图（会露一块纯黑，Smith 真机实测），
    给视口和内容宿主刷一层与底图同色系的纯色画布，卡片摆在上面像一块内嵌面板。
    只改视口调色板在 Wine 下不生效（实测），宿主本身也要刷。"""
    vp = scroll.viewport()
    if isinstance(host, FrostedHost):
        # 毛玻璃宿主自画底图：视口只兜底渐变末端色，宿主不刷纯色
        pal = vp.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(C["bg_bottom"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(C["bg_bottom"]))
        vp.setPalette(pal)
        vp.setAutoFillBackground(True)
        host.setAutoFillBackground(False)
        return
    color = QColor(C["canvas"])
    pal = vp.palette()
    pal.setColor(QPalette.ColorRole.Window, color)
    pal.setColor(QPalette.ColorRole.Base, color)
    vp.setPalette(pal)
    vp.setAutoFillBackground(True)
    if host is not None:
        hpal = host.palette()
        hpal.setColor(QPalette.ColorRole.Window, color)
        hpal.setColor(QPalette.ColorRole.Base, color)
        host.setPalette(hpal)
        host.setAutoFillBackground(True)


_grain_cache: dict[int, QPixmap] = {}


def grain_tile(seed: int = 7) -> QPixmap:
    """细颗粒噪点小图（256×256），平铺盖在底图上就是颗粒感。"""
    if seed in _grain_cache:
        return _grain_cache[seed]
    from PyQt6.QtGui import QImage

    rnd = random.Random(seed)
    size = 256
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    for y in range(size):
        for x in range(size):
            v = rnd.randint(0, 255)
            img.setPixelColor(x, y, QColor(v, v, v, 255))
    pm = QPixmap.fromImage(img)
    _grain_cache[seed] = pm
    return pm


def paint_frosted(painter: QPainter, rect, top: str, bottom: str,
                  blob1: tuple, blob2: tuple, grain_alpha: float) -> None:
    """在 rect 里画：竖向渐变 + 两团高斯柔光（径向渐变模拟）+ 颗粒。"""
    grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
    grad.setColorAt(0, QColor(top))
    grad.setColorAt(1, QColor(bottom))
    painter.fillRect(rect, grad)
    w, h = rect.width(), rect.height()
    for (cx, cy, r, rgba) in [
        (w * 0.78, h * 0.06, w * 0.55, blob1),
        (w * 0.12, h * 1.02, w * 0.5, blob2),
    ]:
        rg = QRadialGradient(cx, cy, r)
        rg.setColorAt(0, QColor(*rgba))
        rg.setColorAt(1, QColor(rgba[0], rgba[1], rgba[2], 0))
        painter.fillRect(rect, rg)
    tile = grain_tile()
    painter.setOpacity(grain_alpha)
    x = rect.left()
    while x < rect.right():
        y = rect.top()
        while y < rect.bottom():
            painter.drawPixmap(x, y, tile)
            y += tile.height()
        x += tile.width()
    painter.setOpacity(1.0)


class FrostedRoot(QWidget):
    """主窗口的底：自己画渐变毛玻璃，上面盖什么都透着这层底。"""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_frosted(
            painter, self.rect(), C["bg_top"], C["bg_bottom"],
            C["blob1"], C["blob2"], C["grain_alpha"],
        )
        super().paintEvent(event)


# ---- 可刷新样式：切换主题时原地重套，不用重建窗口 ----
# 用法：themed(widget, "color: @dim@; font-size: 12px;")，@键@ 在套用时
# 按当前主题的 C 取值替换；refresh_themed() 在切换主题后统一重套一遍。
_themed_styles: list = []


def _fill_tpl(tpl: str) -> str:
    out = tpl
    for k, v in C.items():
        if isinstance(v, str):
            out = out.replace("@" + k + "@", v)
    return out


def themed(widget, tpl: str) -> None:
    import weakref

    _themed_styles.append((weakref.ref(widget), tpl))
    widget.setStyleSheet(_fill_tpl(tpl))


def refresh_themed() -> None:
    alive = []
    for ref, tpl in _themed_styles:
        w = ref()
        if w is not None:
            w.setStyleSheet(_fill_tpl(tpl))
            alive.append((ref, tpl))
    _themed_styles[:] = alive
