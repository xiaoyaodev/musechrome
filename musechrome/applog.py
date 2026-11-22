"""运行日志：软件里点过什么、报过什么错，全记下来。

- 内存里留最近 4000 条，日志页实时看；
- 同时落盘到 MuseChromeData/logs/musechrome.log（超过 2MB 自动换新文件，
  旧的留一份 .old），用户反馈问题时把这个文件发回来就能定位。
- 未捕获的异常和 Qt 的警告/错误也一并收进来。
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

LEVELS = ("操作", "信息", "警告", "错误")


class AppLog(QObject):
    line_added = pyqtSignal(str, str)  # 级别, 整行文本

    def __init__(self, log_dir: Path):
        super().__init__()
        self._lock = threading.Lock()
        self._lines: deque[str] = deque(maxlen=4000)
        self._dir = Path(log_dir)
        self._file: Path | None = None
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._file = self._dir / "musechrome.log"
            if self._file.exists() and self._file.stat().st_size > 2_000_000:
                old = self._dir / "musechrome.old.log"
                old.unlink(missing_ok=True)
                self._file.rename(old)
        except Exception:
            self._file = None

    # ---------- 写入 ----------
    def log(self, level: str, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} [{level}] {msg}"
        with self._lock:
            self._lines.append(line)
            if self._file is not None:
                try:
                    with open(self._file, "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d')} {line}\n")
                except Exception:
                    pass
        self.line_added.emit(level, line)

    def action(self, msg: str) -> None:
        """用户的一次点击/操作。"""
        self.log("操作", msg)

    def info(self, msg: str) -> None:
        self.log("信息", msg)

    def warn(self, msg: str) -> None:
        self.log("警告", msg)

    def error(self, msg: str) -> None:
        self.log("错误", msg)

    # ---------- 读取 ----------
    def lines(self, level: str = "") -> list[str]:
        with self._lock:
            all_lines = list(self._lines)
        if not level:
            return all_lines
        tag = f"[{level}]"
        return [ln for ln in all_lines if tag in ln]

    def file_path(self) -> Path | None:
        return self._file

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()
            if self._file is not None:
                try:
                    self._file.write_text("", encoding="utf-8")
                except Exception:
                    pass


_instance: AppLog | None = None


def init(log_dir: Path) -> AppLog:
    global _instance
    _instance = AppLog(log_dir)
    return _instance


def get_log() -> AppLog:
    """还没 init 时给一个只写内存的临时实例，免得各处判空。"""
    global _instance
    if _instance is None:
        _instance = AppLog(Path("."))
        _instance._file = None
    return _instance


def install_hooks(log: AppLog) -> None:
    """把未捕获异常和 Qt 警告以上级别的消息都收进日志。"""

    def _excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb)).strip()
        log.error(f"未捕获异常：{text.splitlines()[-1] if text else exc}")
        log.log("错误", text.replace("\n", " ⏎ "))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

        def _qt_handler(mode, _ctx, msg):
            if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                log.warn(f"Qt：{msg}")

        qInstallMessageHandler(_qt_handler)
    except Exception:
        pass
