"""软件图标的位置与加载（打包后在 _MEIPASS，源码运行时在仓库 assets/）。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon


def icon_path() -> Path | None:
    """图标文件位置：打包后在 _MEIPASS/assets，源码运行时在仓库 assets/。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets" / "icon.png")
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.png")
    for c in candidates:
        if c.is_file():
            return c
    return None


def app_icon() -> QIcon:
    p = icon_path()
    return QIcon(str(p)) if p else QIcon()
