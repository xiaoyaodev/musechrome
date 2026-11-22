"""环境自检：浏览器/代理/出口逐项检查的后台线程与页面。"""

from __future__ import annotations

import json
import socket
import time
import urllib.parse
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import store
from .netutil import _make_opener, _timed_probe, probe_http_proxy, probe_proxy
from .fxbuttons import FxButton
from .widgets import AnimButton, Spinner
from .theme import C, themed


class HealthChecker(QThread):
    """环境自检：浏览器在不在、代理通不通、出口在哪，一项项报给自检页。"""

    item = pyqtSignal(str, str, str)  # 项目名, ok/warn/fail, 说明
    scan_found = pyqtSignal(list)  # 扫描到的可用代理端口
    all_done = pyqtSignal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self):
        cfg = self.cfg
        chrome = store.find_chrome(cfg)
        self.item.emit("谷歌 Chrome", "ok" if chrome else "warn",
                       chrome or "没找到（不用 Chrome 可忽略；设置页里可以手动指定路径）")
        edge = store.find_edge(cfg)
        self.item.emit("微软 Edge", "ok" if edge else "warn",
                       edge or "没找到（不用 Edge 可忽略；设置页里可以手动指定路径）")

        mode = cfg.get("proxy_mode", "local")
        exit_proxy: str | None = None  # 拿出口信息时走的代理（None = 直连）
        exit_skip = ""
        if mode == "local":
            ptype, host, port = cfg["proxy_type"], cfg["proxy_host"], int(cfg["proxy_port"])
            # 冷连接经远端节点建连经常超过 3 秒（真机踩过：第一次误报超时、
            # 再测一次就通），所以放宽到 8 秒并自动重试一次。
            ok, detail, ms = _timed_probe(ptype, host, port, timeout=8)
            if not ok:
                ok, detail, ms = _timed_probe(ptype, host, port, timeout=8)
            if ok:
                self.item.emit("本地代理", "ok", f"{ptype.upper()} {host}:{port} 可用")
                self.item.emit("代理延迟", "ok" if ms < 800 else "warn",
                               f"约 {ms} ms（经代理取测试页的往返时间，仅供参考，可能有误差）")
                exit_proxy = store.proxy_server_url(cfg)
                if ptype == "socks5":
                    exit_skip = "SOCKS5 代理下自检拿不到出口信息，可点下面按钮在浏览器里看"
            else:
                # 再换另一种协议试一遍：端口通着但协议设错时也是干等超时，
                # 探出来直接告诉用户改哪个，别只报一句不可用。
                alt = "socks5" if ptype == "http" else "http"
                alt_ok, _alt_detail = probe_proxy(alt, host, port, timeout=8)
                if alt_ok:
                    self.item.emit("本地代理", "warn",
                                   f"{host}:{port} 通的是 {alt.upper()}，不是 {ptype.upper()}——去设置里把代理类型改成 {alt.upper()} 再测")
                    if alt == "socks5":
                        exit_skip = "SOCKS5 代理下自检拿不到出口信息，可点下面按钮在浏览器里看"
                    else:
                        exit_proxy = f"http://{host}:{port}"
                else:
                    self.item.emit("本地代理", "fail",
                                   f"{ptype.upper()} {host}:{port} 不可用（{detail}）——先确认代理工具开着")
                    found = []
                    for p in store.COMMON_PROXY_PORTS:
                        if p == port:
                            continue
                        if probe_http_proxy("127.0.0.1", p, timeout=2.5)[0]:
                            found.append(p)
                    self.scan_found.emit(found)
                    self.item.emit("常见端口扫描", "ok" if found else "fail",
                                   ("在端口 " + "、".join(str(p) for p in found) + " 找到可用代理，点下面按钮一键改用")
                                   if found else "常见端口都没找到可用代理，你的工具可能用的冷门端口，去设置里手动填")
        elif mode == "system":
            sp = store.system_proxy_url()
            if not sp:
                self.item.emit("系统代理", "fail",
                               "没读到已启用的系统代理——在你的代理工具里打开「系统代理」开关，或改用本地代理模式")
            else:
                u = urllib.parse.urlparse(sp)
                t0 = time.monotonic()
                ok, detail = probe_http_proxy(u.hostname or "", u.port or 80, timeout=8)
                ms = int((time.monotonic() - t0) * 1000)
                self.item.emit("系统代理", "ok" if ok else "fail",
                               f"系统代理是 {sp}" + ("，可用" if ok else f"，但不可用（{detail}）"))
                if ok:
                    self.item.emit("代理延迟", "ok" if ms < 800 else "warn",
                                   f"约 {ms} ms（经代理取测试页的往返时间，仅供参考，可能有误差）")
                    exit_proxy = sp
        else:
            ok, detail = False, ""
            try:
                with socket.create_connection(("www.gstatic.com", 80), timeout=3) as s:
                    s.settimeout(3)
                    s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n")
                    line = s.recv(200).decode("latin-1", errors="replace").splitlines()[0]
                ok = " 204" in line or " 200" in line
                detail = line.strip()
            except Exception as exc:
                detail = str(exc)[:60]
            self.item.emit("直连", "ok" if ok else "warn",
                           "直连能打开外网，TUN 应该在工作" if ok
                           else f"直连打不开外网（{detail}）——没开 TUN 的话请改用本地代理或跟随系统代理")

        if exit_skip:
            self.item.emit("出口信息", "warn", exit_skip)
        else:
            try:
                opener = _make_opener(exit_proxy)
                req = urllib.request.Request(
                    "http://ip-api.com/json/?fields=status,query,country,regionName,city,isp",
                    headers={"User-Agent": "MuseChrome"},
                )
                with opener.open(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                if data.get("status") == "success":
                    where = " ".join(x for x in [data.get("country", ""), data.get("regionName", ""), data.get("city", "")] if x)
                    self.item.emit("出口信息", "ok", f"{data.get('query', '')} · {where} · {data.get('isp', '')}")
                else:
                    self.item.emit("出口信息", "warn", "拿不到出口信息（不影响使用）")
            except Exception:
                self.item.emit("出口信息", "warn", "拿不到出口信息（不影响使用）")
        self.all_done.emit()


class HealthPage(QWidget):
    """环境自检页：逐项列出检查结果，扫描到可用端口时给一键改用按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel("环境自检")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")
        intro = QLabel("打不开账号，先在这里查一遍：浏览器在不在、代理通不通、出口 IP 在哪。")
        themed(intro, "color: @dim@;")
        intro.setWordWrap(True)
        self.btn_start = FxButton("开始检测")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_leak = FxButton("在当前账号浏览器里打开指纹检测页")
        self.btn_back = FxButton("返回账号列表")
        row = QHBoxLayout()
        self.spinner = Spinner(20)
        self.spinner.hide()
        row.addWidget(self.spinner)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_leak)
        row.addWidget(self.btn_back)
        row.addStretch(1)
        self._results_host = QWidget()
        self._results = QVBoxLayout(self._results_host)
        self._results.setContentsMargins(0, 0, 0, 0)
        self._results.setSpacing(8)
        self._actions_host = QWidget()
        self._actions = QHBoxLayout(self._actions_host)
        self._actions.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self._results_host)
        layout.addWidget(self._actions_host)
        layout.addStretch(1)
        self.on_apply_port = None  # MainWindow 挂进来

    def clear_results(self):
        while self._results.count():
            item = self._results.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.clear_actions()

    def clear_actions(self):
        while self._actions.count():
            item = self._actions.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def add_result(self, name: str, status: str, text: str):
        color = {"ok": "#2e7d32", "warn": "#e8930c", "fail": "#c62828"}.get(status, "#8a7f6e")
        row = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        dot.setFixedWidth(20)
        lbl_name = QLabel(name)
        themed(lbl_name, "font-weight: bold; color: @text@;")
        lbl_name.setFixedWidth(110)
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        themed(lbl_text, "color: @body@;")
        row.addWidget(dot)
        row.addWidget(lbl_name)
        row.addWidget(lbl_text, 1)
        host = QWidget()
        host.setLayout(row)
        self._results.addWidget(host)

    def set_scan_actions(self, ports: list):
        self.clear_actions()
        if not ports:
            return
        lbl = QLabel("一键改用：")
        themed(lbl, "color: @dim@; font-size: 12px;")
        self._actions.addWidget(lbl)
        for p in ports[:3]:
            btn = FxButton(f"端口 {p}")
            btn.setObjectName("primaryBtn")
            btn.clicked.connect(lambda _c=False, port=p: self.on_apply_port and self.on_apply_port(port))
            self._actions.addWidget(btn)
        self._actions.addStretch(1)
