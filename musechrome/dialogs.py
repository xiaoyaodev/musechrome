"""对话框：账号代理设置、账号编辑（名字/备注/颜色标记）。"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from .widgets import AnimButton
from .theme import C


class AccountProxyDialog(QDialog):
    """单个账号的代理设置：跟随全局 / 直连 / 用自己的代理。"""

    def __init__(self, acc: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"代理设置 · {acc['name']}")
        self.setMinimumWidth(380)
        self.rb_global = QRadioButton("跟随全局设置（大多数账号用这个）")
        self.rb_direct = QRadioButton("这个账号直连（不走代理）")
        self.rb_custom = QRadioButton("这个账号用自己的代理：")
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("HTTP", "http")
        self.cmb_type.addItem("SOCKS5", "socks5")
        self.edt_host = QLineEdit()
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        form = QFormLayout()
        form.addRow("类型", self.cmb_type)
        form.addRow("地址", self.edt_host)
        form.addRow("端口", self.spn_port)
        note = QLabel("给某个账号单独指一个代理出口，几个账号就不必挤同一个 IP。\n改完后，把这个账号的浏览器关掉重开才生效。")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {C['dim']}; font-size: 12px;")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.rb_global)
        layout.addWidget(self.rb_direct)
        layout.addWidget(self.rb_custom)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

        proxy = acc.get("proxy") or ""
        if proxy == "direct":
            self.rb_direct.setChecked(True)
        elif isinstance(proxy, dict):
            self.rb_custom.setChecked(True)
            self.cmb_type.setCurrentIndex(1 if proxy.get("type") == "socks5" else 0)
            self.edt_host.setText(str(proxy.get("host", "127.0.0.1")))
            self.spn_port.setValue(int(proxy.get("port", 10808)))
        else:
            self.rb_global.setChecked(True)
            self.edt_host.setText("127.0.0.1")
            self.spn_port.setValue(10808)
        for rb in (self.rb_global, self.rb_direct, self.rb_custom):
            rb.toggled.connect(self._sync_enabled)
        self._sync_enabled()

    def _sync_enabled(self):
        custom = self.rb_custom.isChecked()
        for w in (self.cmb_type, self.edt_host, self.spn_port):
            w.setEnabled(custom)

    def result_proxy(self):
        if self.rb_direct.isChecked():
            return "direct"
        if self.rb_custom.isChecked():
            return {
                "type": self.cmb_type.currentData(),
                "host": self.edt_host.text().strip() or "127.0.0.1",
                "port": self.spn_port.value(),
            }
        return ""


ACCOUNT_COLORS = ["", "#e74c3c", "#e67e22", "#f1c40f", "#27ae60", "#2980b9", "#8e44ad", "#95a5a6"]


class AccountEditDialog(QDialog):
    """编辑账号：名字、备注、颜色标记（卡片头像的底色，账号多了靠颜色认）。"""

    def __init__(self, acc: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑账号 · {acc['name']}")
        self.setMinimumWidth(380)
        self.edt_name = QLineEdit(acc["name"])
        self.edt_note = QLineEdit(str(acc.get("note") or ""))
        self.edt_note.setPlaceholderText("备注（选填）：比如「主号」「备用」")
        self._color = str(acc.get("color") or "")
        color_row = QHBoxLayout()
        self._swatches: list[QPushButton] = []
        for col in ACCOUNT_COLORS:
            btn = AnimButton("无" if not col else "")
            btn.setCheckable(True)
            btn.setFixedSize(30, 30)
            if col:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {col}; border: 2px solid transparent; border-radius: 15px; }}"
                    f"QPushButton:checked {{ border: 2px solid {C['text']}; }}"
                )
            else:
                btn.setStyleSheet("font-size: 11px; border-radius: 15px; padding: 0;")
            btn.setChecked(col == self._color)
            btn.clicked.connect(lambda _c=False, v=col: self._pick_color(v))
            self._swatches.append(btn)
            color_row.addWidget(btn)
        color_row.addStretch(1)
        form = QFormLayout()
        form.addRow("名字", self.edt_name)
        form.addRow("备注", self.edt_note)
        form.addRow("颜色标记", color_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _pick_color(self, value: str):
        self._color = value
        for btn, col in zip(self._swatches, ACCOUNT_COLORS):
            btn.setChecked(col == value)

    def result_values(self) -> tuple[str, str, str]:
        return self.edt_name.text().strip(), self.edt_note.text().strip(), self._color
