"""日志页：实时显示运行日志，可按级别过滤、复制、导出、清空。

用户反馈问题时，让他打开这页点「导出日志」，把文件发回来即可。
"""

from __future__ import annotations

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .applog import get_log
from .fxbuttons import FxButton
from .widgets import AnimButton
from .theme import C, themed


class LogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel("运行日志")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")
        intro = QLabel("软件启动以来的全部记录：点过什么按钮、打开过哪个账号、报过什么错，都在这里。"
                       "出问题时点「导出日志」把文件发给作者，最快定位。")
        intro.setWordWrap(True)
        themed(intro, "color: @dim@;")
        self.cmb_level = QComboBox()
        self.cmb_level.addItem("全部级别", "")
        for lv in ("操作", "信息", "警告", "错误"):
            self.cmb_level.addItem(lv, lv)
        self.cmb_level.currentIndexChanged.connect(self._reload)
        self.chk_follow = QCheckBox("自动滚到底")
        self.chk_follow.setChecked(True)
        self.btn_copy = FxButton("复制全部")
        self.btn_copy.clicked.connect(self._copy)
        self.btn_export = FxButton("导出日志")
        self.btn_export.clicked.connect(self._export)
        self.btn_clear = FxButton("清空日志")
        self.btn_clear.clicked.connect(self._clear)
        self.btn_back = FxButton("返回账号列表")
        row = QHBoxLayout()
        row.addWidget(self.cmb_level)
        row.addWidget(self.chk_follow)
        row.addStretch(1)
        row.addWidget(self.btn_copy)
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_clear)
        row.addWidget(self.btn_back)
        self.txt = QPlainTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self.txt, 1)
        get_log().line_added.connect(self._on_line)
        self._reload()

    def _level(self) -> str:
        return str(self.cmb_level.currentData() or "")

    def _reload(self):
        self.txt.setPlainText("\n".join(get_log().lines(self._level())))
        if self.chk_follow.isChecked():
            bar = self.txt.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _on_line(self, level: str, line: str):
        want = self._level()
        if want and want != level:
            return
        self.txt.appendPlainText(line)
        if self.chk_follow.isChecked():
            bar = self.txt.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _copy(self):
        QGuiApplication.clipboard().setText(self.txt.toPlainText())
        get_log().action("日志页：复制全部日志")

    def _export(self):
        import time as _t

        default = f"MuseChrome-log-{_t.strftime('%Y%m%d-%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", default, "日志文件 (*.txt *.log)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(get_log().lines()))
            get_log().action(f"日志页：导出日志到 {path}")
            QMessageBox.information(self, "导出日志", "日志已导出。把这个文件发给作者即可。")
        except Exception as exc:
            QMessageBox.critical(self, "导出日志", f"导出失败：{exc}")

    def _clear(self):
        ret = QMessageBox.question(self, "清空日志", "连磁盘上的日志文件一起清掉吗？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        get_log().clear()
        self._reload()
        get_log().action("日志页：清空日志")
