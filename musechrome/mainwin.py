"""主窗口：图标栏 + 账号卡片 + 各功能页的组装与全部账号操作。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, QVariantAnimation
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QUrl

from . import APP_NAME, REPO_URL, __version__, extensions, store
from .applog import get_log
from .cards import AccountCard
from .dialogs import AccountEditDialog, AccountProxyDialog
from .health import HealthChecker, HealthPage
from .logpage import LogPage
from .notices import NoticeFetcher, NoticePage, parse_notices
from .pages import AboutPage, PluginPage, SettingsPage
from .iconutil import icon_path
from .theme import C, FrostedHost, FrostedRoot, _paint_bg, app_style, fix_scroll, refresh_themed, set_theme, themed
from .updater import (
    DownloadThread,
    UpdateChecker,
    build_rename_bat,
    build_setup_bat,
    build_updater_bat,
)
from .fxbuttons import FxButton
from .themeswitch import DayNightSwitch
from .widgets import AnimButton, RailWidget, RippleButton, TitleBar


def _close_windows_for_pid(pid: int) -> int:
    """给某个进程的所有顶层窗口发关闭消息（优雅关闭），返回发出的窗口数。

    只在 Windows 上有意义；其他平台返回 0，调用方会退回结束进程。
    """
    if not sys.platform.startswith("win"):
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            proc_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        for hwnd in found:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        return len(found)
    except Exception:
        return 0


class MainWindow(QMainWindow):
    _last_theme_switch = 0.0  # 外观切换防连点锁（时间戳，全窗口共用）
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.accounts = store.load_accounts()
        if not self.accounts:
            self.accounts = [{"id": store.new_account_id(), "name": "账号 1", "browser": "chrome", "proxy": ""}]
            store.save_accounts(self.accounts)
        self._selected_id = self.accounts[0]["id"]
        self._launched: set[str] = set()
        self._launched_at: dict[str, float] = {}
        self._card_widgets: dict[str, QWidget] = {}
        self._cards_animated = False
        self._anims: list = []
        self._open_queue: list[str] = []
        self._open_total = 0
        self._open_timer = QTimer(self)
        self._open_timer.timeout.connect(self._open_next)
        self._procs: dict[str, subprocess.Popen] = {}
        # 每 2.5 秒看一眼已启动的 Chrome 主进程：退出了就把卡片状态改回「未打开」
        self._proc_timer = QTimer(self)
        self._proc_timer.timeout.connect(self._poll_procs)
        self._proc_timer.start(2500)

        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        # 无边框＋自绘标题栏（Smith 要黑白渐变标题栏，系统标题栏做不到渐变）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(1000, 640)
        geo = self.cfg.get("win_geo")  # 只记位置；窗口大小固定（Smith 定）
        if isinstance(geo, list) and len(geo) >= 2:
            try:
                self.move(int(geo[0]), int(geo[1]))
            except Exception:
                pass
        set_theme(self.cfg.get("theme"))
        self.setStyleSheet(app_style(self.cfg.get("theme")))
        self._filter_text = ""
        get_log().info(
            f"主窗口打开：主题 {self.cfg.get('theme', 'dark')}，账号 {len(self.accounts)} 个"
        )

        # ---- 左侧图标栏（68px 纯图标，点击带涟漪） ----
        rail = RailWidget()
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(11, 14, 11, 12)
        rl.setSpacing(6)
        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip = icon_path()
        if ip:
            logo.setPixmap(QPixmap(str(ip)).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        rl.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        rl.addSpacing(12)
        self.btn_nav_home = RippleButton("grid", "账号总览")
        self.btn_nav_home.clicked.connect(lambda: self._show_page(0))
        rl.addWidget(self.btn_nav_home, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_nav_notice = RippleButton("mega", "公告")
        self.btn_nav_notice.clicked.connect(self.show_notice_page)
        rl.addWidget(self.btn_nav_notice, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_nav_plugins = RippleButton("puzzle", "浏览器插件助手")
        self.btn_nav_plugins.clicked.connect(self.show_plugins_page)
        rl.addWidget(self.btn_nav_plugins, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_nav_health = RippleButton("shield", "环境自检")
        self.btn_nav_health.clicked.connect(lambda: self._show_page(4))
        rl.addWidget(self.btn_nav_health, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_nav_log = RippleButton("log", "运行日志")
        self.btn_nav_log.clicked.connect(lambda: self._show_page(6))
        rl.addWidget(self.btn_nav_log, 0, Qt.AlignmentFlag.AlignHCenter)
        rl.addStretch(1)
        self.btn_nav_about = RippleButton("info", "关于软件")
        self.btn_nav_about.clicked.connect(self.show_about_page)
        rl.addWidget(self.btn_nav_about, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_theme = DayNightSwitch()
        self.btn_theme.clicked.connect(self.toggle_theme)
        rl.addWidget(self.btn_theme, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_nav_settings = RippleButton("gear", "设置")
        self.btn_nav_settings.clicked.connect(self.show_settings_page)
        rl.addWidget(self.btn_nav_settings, 0, Qt.AlignmentFlag.AlignHCenter)
        self._sync_theme_btn()
        self._nav_map = {
            0: self.btn_nav_home, 1: self.btn_nav_notice, 2: self.btn_nav_plugins,
            3: self.btn_nav_settings, 4: self.btn_nav_health, 5: self.btn_nav_about,
            6: self.btn_nav_log,
        }

        # ---- 账号页 ----
        head = QHBoxLayout()
        lbl_head = QLabel("账号总览")
        themed(lbl_head, "font-size: 21px; font-weight: 600; color: @text@;")
        head.addWidget(lbl_head)
        head.addStretch(1)
        self.edt_search = QLineEdit()
        self.edt_search.setObjectName("searchBox")
        self.edt_search.setPlaceholderText("搜索账号…")
        self.edt_search.setFixedWidth(230)
        self.edt_search.textChanged.connect(self._on_search)
        head.addWidget(self.edt_search)
        self.btn_open_all = FxButton("打开全部")
        self.btn_open_all.clicked.connect(self.open_all_accounts)
        head.addWidget(self.btn_open_all)
        btn_add = AnimButton("＋ 添加账号")
        btn_add.setObjectName("addAccountBtn")
        btn_add.enable_flood_fx()
        btn_add.clicked.connect(self.add_account)
        head.addWidget(btn_add)

        stats = QHBoxLayout()
        stats.setSpacing(46)

        def _stat_block(caption):
            box = QVBoxLayout()
            box.setSpacing(0)
            val = QLabel("—")
            themed(val, "font-size: 15px; font-weight: 600; color: @text@;")
            cap = QLabel(caption)
            themed(cap, "font-size: 12px; color: @dim@;")
            box.addWidget(val)
            box.addWidget(cap)
            holder = QWidget()
            holder.setLayout(box)
            return holder, val

        b, self.stat_total = _stat_block("账号总数")
        stats.addWidget(b)
        b, self.stat_running = _stat_block("正在运行")
        stats.addWidget(b)
        b, self.stat_today = _stat_block("今日打开")
        stats.addWidget(b)
        b, self.stat_proxy = _stat_block("代理模式")
        stats.addWidget(b)
        b, self.stat_ver = _stat_block("当前版本")
        stats.addWidget(b)
        self.stat_ver.setText(f"v{__version__}")
        stats.addStretch(1)

        notice = QFrame()
        notice.setObjectName("noticeBar")
        nl = QHBoxLayout(notice)
        nl.setContentsMargins(14, 8, 14, 8)
        lbl_notice = QLabel(
            "使用前准备：本机装有 Chrome 或 Edge 即可，本软件用现成的浏览器打开账号，不自带浏览器；代理请提前开好。"
        )
        themed(lbl_notice, "color: @noticeText@;")
        lbl_notice.setWordWrap(True)
        nl.addWidget(lbl_notice)

        self._cards_host = FrostedHost()
        _paint_bg(self._cards_host)
        self._cards_grid = QGridLayout(self._cards_host)
        self._cards_grid.setContentsMargins(2, 2, 2, 2)
        self._cards_grid.setSpacing(12)
        self._cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_host)
        fix_scroll(scroll, self._cards_host)
        self._cards_scroll = scroll

        main = QVBoxLayout()
        main.setContentsMargins(26, 20, 26, 18)
        main.setSpacing(12)
        main.addLayout(head)
        main.addLayout(stats)
        main.addWidget(notice)
        main.addWidget(scroll, 1)
        accounts_page = QWidget()
        accounts_page.setLayout(main)
        _paint_bg(accounts_page)

        # ---- 其余页面 ----
        self.page_notice = NoticePage()
        self.page_notice.btn_back.clicked.connect(lambda: self._show_page(0))
        self.page_plugins = PluginPage()
        self.page_plugins.btn_go.clicked.connect(self.install_selected_plugins)
        self.page_plugins.btn_install.clicked.connect(self.install_rec_via_store)
        self.page_plugins.btn_back.clicked.connect(lambda: self._show_page(0))
        self.page_settings = SettingsPage()
        self.page_settings.btn_save.clicked.connect(self.save_settings)
        self.page_settings.btn_back.clicked.connect(lambda: self._show_page(0))
        self.page_settings.btn_export.clicked.connect(self.export_backup)
        self.page_settings.btn_import.clicked.connect(self.import_backup)
        self.page_health = HealthPage()
        self.page_health.btn_back.clicked.connect(lambda: self._show_page(0))
        self.page_health.btn_start.clicked.connect(self.start_health_check)
        self.page_health.btn_leak.clicked.connect(self.open_leak_page)
        self.page_health.on_apply_port = self.apply_scanned_port
        self.page_about = AboutPage()
        self.page_about.btn_back.clicked.connect(lambda: self._show_page(0))
        self.btn_update = self.page_about.btn_update
        self.btn_update.clicked.connect(self.check_update)
        self.page_log = LogPage()
        self.page_log.btn_back.clicked.connect(lambda: self._show_page(0))
        self.stack = QStackedWidget()
        _paint_bg(self.stack)
        # 设置页内容比窗口高（125% 缩放下更明显）：直接放进页面栈，
        # 表单会被压缩、行距和边距被吃掉（预设按钮贴下边框就是这么
        # 来的，Smith 三次指出）；装进滚动区，表单永远按完整高度排
        self._settings_scroll = QScrollArea()
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._settings_scroll.setWidget(self.page_settings)
        fix_scroll(self._settings_scroll, self.page_settings)
        for w in (accounts_page, self.page_notice, self.page_plugins,
                  self._settings_scroll, self.page_health, self.page_about, self.page_log):
            _paint_bg(w)
            self.stack.addWidget(w)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(rail)
        body.addWidget(self.stack, 1)
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        ip0 = icon_path()
        pix = None
        if ip0:
            pix = QPixmap(str(ip0)).scaled(
                18, 18, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        outer.addWidget(TitleBar(f"{APP_NAME} v{__version__}", pix))
        outer.addLayout(body)
        central = FrostedRoot()
        central.setLayout(outer)
        self.setCentralWidget(central)

        self._rebuild_cards()
        self._show_page(0)

    def _fit_cards_host(self):
        """卡片宿主至少撑满滚动区高度：宿主比视口矮时，露出来的视口底
        在真 Windows 上会渲成一块纯黑（Smith 图一实证），撑满就没这问题。"""
        h = self._cards_scroll.viewport().height()
        if h > 0:
            self._cards_host.setMinimumHeight(h)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_cards_host)

        # ---- 公告：先摆上次缓存，再后台拉最新 ----
        self._notices: list[dict] = []
        self._notice_fetch: NoticeFetcher | None = None
        cache = store.load_notices_cache()
        if cache["text"]:
            self._notices = parse_notices(cache["text"])
            self.page_notice.set_notices(self._notices, "正在更新…")
        self._refresh_notice_badge()
        self._fetch_notices()

    # ---------- 页面切换 ----------
    def _show_page(self, idx: int):
        """切到第 idx 页，图标栏只亮当前页对应的图标。新页 150ms
        淡入，不再硬切（Uiverse 式页面过渡的克制版）。"""
        self.stack.setCurrentIndex(idx)
        page = self.stack.widget(idx)
        old_fx = getattr(self, "_page_fx", None)
        if old_fx is not None:
            try:
                old_fx[1].stop()
                old_fx[0].setGraphicsEffect(None)
            except Exception:
                pass
        try:
            from PyQt6.QtWidgets import QGraphicsOpacityEffect

            fx = QGraphicsOpacityEffect(page)
            fx.setOpacity(0.25)
            page.setGraphicsEffect(fx)
            anim = QVariantAnimation(self)
            anim.setDuration(150)
            anim.setStartValue(0.25)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.valueChanged.connect(lambda v, f=fx: f.setOpacity(float(v)))
            anim.finished.connect(lambda pg=page: pg.setGraphicsEffect(None))
            self._page_fx = (page, anim)
            anim.start()
        except Exception:
            pass
        for i, btn in self._nav_map.items():
            btn.setChecked(i == idx)
        if idx == 0:
            self._cards_scroll.verticalScrollBar().setValue(0)
        names = {0: "账号总览", 1: "公告", 2: "浏览器插件助手", 3: "设置",
                 4: "环境自检", 5: "关于软件", 6: "运行日志"}
        get_log().action(f"切换页面：{names.get(idx, idx)}")

    # ---------- 统计与搜索 ----------
    def _refresh_stats(self):
        self.stat_total.setText(str(len(self.accounts)))
        self.stat_running.setText(str(len(self._launched)))
        stats = self.cfg.get("open_stats") or {}
        today = time.strftime("%Y-%m-%d")
        self.stat_today.setText(
            f"{int(stats.get('count', 0))} 次" if stats.get("date") == today else "0 次"
        )
        mode = self.cfg.get("proxy_mode", "local")
        self.stat_proxy.setText({
            "local": f"本地 {self.cfg.get('proxy_port', '')}",
            "system": "跟随系统", "off": "直连",
        }.get(mode, mode))

    def _bump_today_open(self):
        today = time.strftime("%Y-%m-%d")
        stats = self.cfg.get("open_stats") or {}
        if stats.get("date") != today:
            stats = {"date": today, "count": 0}
        stats["count"] = int(stats.get("count", 0)) + 1
        self.cfg["open_stats"] = stats
        store.save_config(self.cfg)
        self._refresh_stats()

    def _on_search(self, text: str):
        self._filter_text = text.strip()
        self._rebuild_cards()

    def show_notice_page(self):
        self._show_page(1)
        if self._notices:
            self.cfg["notice_seen"] = self._notices[0]["id"]
            store.save_config(self.cfg)
            self._refresh_notice_badge()
        self._fetch_notices()

    # ---------- 公告 ----------
    def _fetch_notices(self):
        if self._notice_fetch is not None and self._notice_fetch.isRunning():
            return
        self.page_notice.set_proxy_url(store.fetch_proxy_url(self.cfg))
        self._notice_fetch = NoticeFetcher(store.fetch_proxy_url(self.cfg), self)
        self._notice_fetch.done.connect(self._on_notices_fetched)
        self._notice_fetch.start()

    def _on_notices_fetched(self, ok: bool, text: str, why: str):
        if ok:
            stamp = time.strftime("%Y-%m-%d %H:%M")
            store.save_notices_cache(text, stamp)
            self._notices = parse_notices(text)
            self.page_notice.set_notices(self._notices, f"更新于 {stamp}")
        elif self._notices:
            get_log().error(f"拉公告失败：{why}")
            self.page_notice.set_notices(
                self._notices, f"暂时拉不到公告（{why}），显示的是上次内容"
            )
        else:
            get_log().error(f"拉公告失败：{why}")
            self.page_notice.set_notices([], f"暂时拉不到公告（{why}）")
        self._refresh_notice_badge()

    def _refresh_notice_badge(self):
        newest = self._notices[0]["id"] if self._notices else ""
        has_new = bool(newest) and newest != str(self.cfg.get("notice_seen") or "")
        self.btn_nav_notice.setToolTip("公告（有新公告）" if has_new else "公告")

    def show_plugins_page(self):
        acc = self._current_account()
        if acc is None:
            return
        self.page_plugins.refresh(acc["name"], store.list_source_extensions(), acc)
        self._show_page(2)

    def show_settings_page(self):
        self.page_settings.load(self.cfg)
        # 嵌套布局的尺寸提示在首次显示前可能是旧值（预设行曾被算成
        # 26px 高）：进页面时强制整页布局失效重排一次
        lay = self.page_settings.layout()
        if lay is not None:
            lay.invalidate()
            lay.activate()
        self._show_page(3)

    def show_about_page(self):
        self._show_page(5)

    # ---------- 环境自检 ----------
    def start_health_check(self):
        if getattr(self, "_health", None) is not None and self._health.isRunning():
            return
        self.page_health.clear_results()
        self.page_health.spinner.start()
        self.page_health.btn_start.setEnabled(False)
        self.page_health.btn_start.setText("检测中…")
        self._health = HealthChecker(self.cfg, self)
        self._health.item.connect(self.page_health.add_result)
        self._health.item.connect(
            lambda n, lv, d: get_log().info(f"自检[{n}] {lv}：{d}")
        )
        self._health.scan_found.connect(self.page_health.set_scan_actions)
        self._health.all_done.connect(self._on_health_done)
        self._health.start()

    def _on_health_done(self):
        self.page_health.spinner.stop()
        self.page_health.btn_start.setEnabled(True)
        self.page_health.btn_start.setText("开始检测")

    def apply_scanned_port(self, port: int):
        self.cfg["proxy_mode"] = "local"
        self.cfg["proxy_enabled"] = True
        self.cfg["proxy_type"] = "http"
        self.cfg["proxy_host"] = "127.0.0.1"
        self.cfg["proxy_port"] = int(port)
        store.save_config(self.cfg)
        self._refresh_proxy_label()
        QMessageBox.information(
            self, "环境自检", f"已改用 127.0.0.1:{port} 作为代理。\n回账号列表打开账号试试。"
        )

    def open_leak_page(self):
        self.open_account(extra_urls=["https://browserleaks.com/ip"])
        self._show_page(0)

    # ---------- 账号卡片 ----------
    def _rebuild_cards(self):
        # 账号总数不满 3 个时，卡片拉宽铺满整排（2 个各占一半、1 个占满）；
        # 3 个及以上按原版等宽三列，最后一排不满也保持三列宽（Smith 拍板）
        shown = [
            a for a in self.accounts
            if not self._filter_text
            or self._filter_text.lower() in (a["name"] + str(a.get("note") or "")).lower()
        ]
        n = len(shown)
        cols = 3 if n >= 3 else max(1, n)
        for c in range(3):
            self._cards_grid.setColumnStretch(c, 1 if c < cols else 0)
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._card_widgets = {}
        cards = []
        for idx, acc in enumerate(shown):
            card = self._make_card(acc)
            self._card_widgets[acc["id"]] = card
            cards.append(card)
            self._cards_grid.addWidget(card, idx // 3, idx % 3)
        # 只在软件刚打开、第一次摆卡片时做一次错落淡入，之后重排不再动
        if not self._cards_animated:
            self._cards_animated = True
            for i, card in enumerate(cards):
                self._fade_in_card(card, i * 45)
        if hasattr(self, "stat_total"):
            self._refresh_stats()
        QTimer.singleShot(0, self._fit_cards_host)

    def _fade_in_card(self, card: QWidget, delay_ms: int):
        eff = QGraphicsOpacityEffect(card)
        eff.setOpacity(0.0)
        card.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", card)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anims.append(anim)
        anim.finished.connect(lambda c=card: c.restore_shadow())
        if delay_ms:
            QTimer.singleShot(delay_ms, anim.start)
        else:
            anim.start()

    def _pulse_card(self, acc_id: str):
        """批量打开时给刚启动的卡片一个呼吸脉冲，眼睛能跟上进度。"""
        card = self._card_widgets.get(acc_id)
        if card is None:
            return
        eff = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", card)
        anim.setDuration(550)
        anim.setKeyValueAt(0, 0.3)
        anim.setKeyValueAt(0.35, 1.0)
        anim.setKeyValueAt(1, 1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anims.append(anim)
        anim.finished.connect(lambda c=card: c.restore_shadow())
        anim.start()

    def _make_card(self, acc: dict) -> AccountCard:
        selected = acc["id"] == self._selected_id
        card = AccountCard(acc["id"])
        card.set_selected(selected)
        card.setMinimumWidth(210)
        card.clicked.connect(self._select_account)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 12)
        cl.setSpacing(9)
        # 第一行：头像 + 名字/备注 + 运行状态
        top = QHBoxLayout()
        top.setSpacing(10)
        avatar = QLabel(acc["name"][:1] or "M")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background: {acc.get('color') or '#55555c'}; color: #ffffff; font-size: 17px; font-weight: bold; border-radius: 21px;"
        )
        top.addWidget(avatar)
        namecol = QVBoxLayout()
        namecol.setSpacing(1)
        name = QLabel(acc["name"])
        themed(name, "font-size: 15px; font-weight: bold; color: @text@;")
        namecol.addWidget(name)
        note_text = str(acc.get("note") or "").strip()
        sub = QLabel(note_text if note_text else "独立配置")
        themed(sub, "font-size: 12px; color: @dim@;")
        namecol.addWidget(sub)
        top.addLayout(namecol, 1)
        opened = acc["id"] in self._launched
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {C['ok'] if opened else C['border2']}; font-size: 11px;")
        top.addWidget(dot)
        if opened:
            started = self._launched_at.get(acc["id"])
            if started:
                mins = int((time.time() - started) // 60)
                if mins < 1:
                    status = "运行中 · 刚打开"
                elif mins < 60:
                    status = f"运行中 · {mins} 分钟"
                else:
                    status = f"运行中 · {mins // 60} 小时 {mins % 60} 分"
            else:
                status = "运行中"
        else:
            status = "未启动"
        lbl_status = QLabel(status)
        themed(lbl_status, "font-size: 12px; color: @dim@;")
        top.addWidget(lbl_status)
        cl.addLayout(top)
        # 第二行：浏览器分段开关 + 代理标记
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        seg = QFrame()
        seg.setObjectName("browserSeg")
        seg_l = QHBoxLayout(seg)
        seg_l.setContentsMargins(2, 2, 2, 2)
        seg_l.setSpacing(2)
        btn_seg_chrome = AnimButton("Chrome")
        btn_seg_chrome.setObjectName("segBtn")
        btn_seg_chrome.setCheckable(True)
        btn_seg_chrome.setMinimumWidth(80)
        btn_seg_edge = AnimButton("Edge")
        btn_seg_edge.setObjectName("segBtn")
        btn_seg_edge.setCheckable(True)
        btn_seg_edge.setMinimumWidth(62)
        is_edge = acc.get("browser") == "edge"
        btn_seg_chrome.setChecked(not is_edge)
        btn_seg_edge.setChecked(is_edge)
        seg_l.addWidget(btn_seg_chrome)
        seg_l.addWidget(btn_seg_edge)
        row2.addWidget(seg)
        if acc.get("proxy") == "direct":
            proxy_hint = "代理：直连"
        elif isinstance(acc.get("proxy"), dict):
            proxy_hint = f"代理：{acc['proxy']['host']}:{acc['proxy']['port']}"
        else:
            proxy_hint = "代理：跟随全局"
        lbl_proxy = QLabel(proxy_hint)
        themed(lbl_proxy, "font-size: 12px; color: @dim@;")
        row2.addWidget(lbl_proxy)
        row2.addStretch(1)
        cl.addLayout(row2)
        # 第三行：打开/关闭 + 插件助手 + 编辑/代理/删除
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        btn_open = FxButton(
            "关闭浏览器" if opened else ("打开 Edge" if is_edge else "打开 Chrome")
        )
        btn_open.setObjectName("darkBtn")
        btn_open.setFixedWidth(118)
        if opened:
            btn_open.clicked.connect(
                lambda _c=False, aid=acc["id"]: self.close_account_browser(aid)
            )
        else:
            btn_open.clicked.connect(
                lambda _c=False, aid=acc["id"]: (self._select_account(aid), self.open_account())
            )
        row3.addWidget(btn_open)
        btn_plugins = FxButton("插件助手")
        btn_plugins.clicked.connect(
            lambda _c=False, aid=acc["id"]: (self._select_account(aid), self.show_plugins_page())
        )
        row3.addWidget(btn_plugins)
        row3.addStretch(1)
        cl.addLayout(row3)
        # 第四行：编辑 / 代理 / 删除（窗口改小后第三行摆不下，单独一行）
        row4 = QHBoxLayout()
        row4.setSpacing(8)
        btn_rename = FxButton("编辑")
        btn_rename.setObjectName("miniBtn")
        btn_rename.clicked.connect(
            lambda _c=False, aid=acc["id"]: (self._select_account(aid), self.rename_account())
        )
        row4.addWidget(btn_rename)
        btn_proxy = FxButton("代理")
        btn_proxy.setObjectName("miniBtn")
        btn_proxy.clicked.connect(
            lambda _c=False, aid=acc["id"]: (self._select_account(aid), self.edit_account_proxy())
        )
        row4.addWidget(btn_proxy)
        btn_delete = FxButton("删除")
        btn_delete.setObjectName("miniBtn")
        btn_delete.clicked.connect(
            lambda _c=False, aid=acc["id"]: (self._select_account(aid), self.delete_account())
        )
        row4.addWidget(btn_delete)
        row4.addStretch(1)
        cl.addLayout(row4)
        btn_seg_chrome.clicked.connect(
            lambda _c=False, aid=acc["id"], bo=btn_open, bc=btn_seg_chrome, be=btn_seg_edge:
            self._set_account_browser(aid, "chrome", bo, bc, be)
        )
        btn_seg_edge.clicked.connect(
            lambda _c=False, aid=acc["id"], bo=btn_open, bc=btn_seg_chrome, be=btn_seg_edge:
            self._set_account_browser(aid, "edge", bo, bc, be)
        )
        return card

    def _select_account(self, acc_id: str):
        if acc_id != self._selected_id:
            self._selected_id = acc_id
            self._rebuild_cards()

    def _set_account_browser(self, acc_id: str, browser: str, btn_open: QPushButton,
                             btn_chrome: QPushButton, btn_edge: QPushButton):
        """卡片上切换该账号用的浏览器：存盘，并同步打开按钮的文字。
        Chrome 与 Edge 各用各的配置目录，切换后第一次打开要登录一次。"""
        for acc in self.accounts:
            if acc["id"] == acc_id:
                if acc.get("browser") != browser:
                    acc["browser"] = browser
                    store.save_accounts(self.accounts)
                break
        btn_chrome.setChecked(browser == "chrome")
        btn_edge.setChecked(browser == "edge")
        btn_open.setText("打开 Edge" if browser == "edge" else "打开 Chrome")

    # ---------- 账号管理 ----------
    def _current_account(self) -> dict | None:
        for acc in self.accounts:
            if acc["id"] == self._selected_id:
                return acc
        return self.accounts[0] if self.accounts else None

    def _sync_theme_btn(self):
        dark = self.cfg.get("theme") == "dark"
        self.btn_theme.set_dark(dark)
        self.btn_theme.setToolTip(
            "外观：深色（点击切换到浅色）" if dark else "外观：浅色（点击切换到深色）"
        )

    # 切换外观时退下来的旧窗口留在这里保命：不销毁，它的后台线程就不会
    # 在运行中被连窗口一起回收（v1.8.x 进程内切换闪退就是这个原因）
    _retired_windows: list = []

    def toggle_theme(self):
        """边栏月亮/太阳按钮：原地切换深浅外观——不重建窗口、不重启进程。

        旧做法（整窗重建）连点又慢又闪退（Smith 2026-11-22 真机反馈），
        改成原地换装：set_theme 换调色板 → 重套全局样式 → refresh_themed
        重套各处写死的主题色 → 卡片重画 → 滚动区底色重刷。自绘控件
        （图标栏、标题栏、按钮、列表）都现读 C 画图，update 一下即可。
        已打开的浏览器窗口不受影响。
        """
        new_theme = "light" if self.cfg.get("theme") == "dark" else "dark"
        self.cfg["theme"] = new_theme
        store.save_config(self.cfg)
        get_log().action(f"切换外观：{new_theme}")
        set_theme(new_theme)
        try:
            QApplication.instance().styleHints().setColorScheme(
                Qt.ColorScheme.Dark if new_theme == "dark" else Qt.ColorScheme.Light
            )
        except Exception:
            pass
        self.setStyleSheet(app_style(new_theme))
        refresh_themed()
        # 所有滚动区底色一起重刷（公告页的滚动区曾漏刷：切到深色后
        # 公告列表下方还是一片白，Smith 实证的公告 bug 之一）
        for sa in self.findChildren(QScrollArea):
            fix_scroll(sa, sa.widget())
        fix_scroll(self._cards_scroll, self._cards_host)
        self._fit_cards_host()
        self._rebuild_cards()
        self._sync_theme_btn()
        self.update()

    def _refresh_proxy_label(self):
        self._refresh_stats()

    def add_account(self):
        name, ok = QInputDialog.getText(
            self, "添加账号", "给新账号起个名字（如：工作号）：",
            text=store.next_account_name(self.accounts),
        )
        if not ok or not name.strip():
            return
        acc = {"id": store.new_account_id(), "name": name.strip(), "browser": "chrome",
               "proxy": "", "note": "", "color": ""}
        self.accounts.append(acc)
        store.save_accounts(self.accounts)
        self._selected_id = acc["id"]
        get_log().action(f"添加账号「{acc['name']}」")
        self._rebuild_cards()

    def rename_account(self):
        acc = self._current_account()
        if acc is None:
            return
        dlg = AccountEditDialog(acc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, note, color = dlg.result_values()
        if name:
            acc["name"] = name
        acc["note"] = note
        acc["color"] = color
        store.save_accounts(self.accounts)
        self._rebuild_cards()

    def open_all_accounts(self):
        """批量打开：还没打开的账号排队，每 0.7 秒开一个（一起涌会把机器压住），
        按钮上滚动进度，刚开的卡片脉冲一下，眼睛跟得上。"""
        pending = [a["id"] for a in self.accounts if a["id"] not in self._launched]
        if not pending:
            QMessageBox.information(self, "打开全部", "所有账号都已经打开了。")
            return
        self._open_queue = pending
        self._open_total = len(pending)
        self.btn_open_all.setEnabled(False)
        self.btn_open_all.setText(f"正在打开…（0/{self._open_total}）")
        self._open_timer.start(700)
        self._open_next()

    def _open_next(self):
        if not self._open_queue:
            self._open_timer.stop()
            self.btn_open_all.setEnabled(True)
            self.btn_open_all.setText("打开全部")
            return
        aid = self._open_queue.pop(0)
        done = self._open_total - len(self._open_queue)
        self.btn_open_all.setText(f"正在打开…（{done}/{self._open_total}）")
        self._selected_id = aid
        self.open_account()
        self._pulse_card(aid)

    def edit_account_proxy(self):
        acc = self._current_account()
        if acc is None:
            return
        dlg = AccountProxyDialog(acc, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            acc["proxy"] = dlg.result_proxy()
            store.save_accounts(self.accounts)
            self._rebuild_cards()

    def delete_account(self):
        acc = self._current_account()
        if acc is None:
            return
        if len(self.accounts) == 1:
            QMessageBox.information(self, "删除账号", "至少保留一个账号，不能删光。")
            return
        ret = QMessageBox.question(self, "删除账号", f"确定删除「{acc['name']}」吗？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        wipe = QMessageBox.question(
            self, "删除账号",
            "连这个账号的浏览器数据一起删掉吗？\n（Chrome 和 Edge 两边的登录状态、Cookie、插件都会没；选「否」只删列表项，数据保留。）",
        )
        self.accounts = [a for a in self.accounts if a["id"] != acc["id"]]
        store.save_accounts(self.accounts)
        if wipe == QMessageBox.StandardButton.Yes:
            store.delete_profile_dir(acc["id"])
            store.delete_edge_profile_dir(acc["id"])
        self._launched.discard(acc["id"])
        self._launched_at.pop(acc["id"], None)
        self._procs.pop(acc["id"], None)
        if self._current_account() is None or self._selected_id == acc["id"]:
            self._selected_id = self.accounts[0]["id"]
        self._rebuild_cards()

    # ---------- 插件助手 ----------
    def install_selected_plugins(self):
        ids = self.page_plugins.selected_ids()
        if not ids:
            QMessageBox.information(self, "浏览器插件助手", "先勾选要安装的插件。")
            return
        self.open_account(extra_urls=[store.store_url(i) for i in ids])
        self._show_page(0)

    # ---------- 推荐插件（商店安装） ----------
    def install_rec_via_store(self):
        """把勾选插件的商店页在这个账号的浏览器里打开，用户点「添加」装好。

        新版 Chrome 不让软件自动代装插件（实测各通道都装不持久），
        商店正经安装是唯一装一次、永久保留的路。装过的靠登记册识别，
        不再重复打开。
        """
        acc = self._current_account()
        if acc is None:
            return
        slugs = self.page_plugins.selected_rec_slugs()
        if not slugs:
            QMessageBox.information(self, "推荐插件", "先勾选要安装的插件。")
            return
        states = extensions.store_state_map(acc)
        todo = [s for s in slugs if not states.get(s)]
        if not todo:
            QMessageBox.information(
                self, "推荐插件", "勾选的插件都已经装好了，不用再装。"
            )
            return
        get_log().action(
            f"给账号「{acc['name']}」打开商店页安装插件：{', '.join(todo)}"
        )
        self.page_plugins.lbl_rec_status.setText(
            "商店页已在浏览器里打开，逐个点「添加到 Chrome」装好；"
            "装完回到这里，列表会自动标成已安装。"
        )
        ids = [extensions.BY_SLUG[s]["id"] for s in todo]
        self.open_account(extra_urls=[store.store_url(i) for i in ids])
        self._show_page(0)

    # ---------- 打开浏览器 ----------
    def open_account(self, extra_urls: list[str] | None = None):
        acc = self._current_account()
        if acc is None:
            return
        kind = acc.get("browser") or "chrome"
        is_edge = kind == "edge"
        label = "Edge" if is_edge else "Chrome"
        exe_name = "msedge.exe" if is_edge else "chrome.exe"
        cfg_key = "edge_path" if is_edge else "chrome_path"
        exe = store.find_browser_exe(self.cfg, kind)
        if not exe:
            ret = QMessageBox.warning(
                self, f"找不到 {label}",
                f"没在常见位置找到 {exe_name}。\n点「是」手动选一次 {exe_name}，我会记到设置里。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(self, f"选择 {exe_name}", "", f"{exe_name} ({exe_name})")
                if path:
                    self.cfg[cfg_key] = path
                    store.save_config(self.cfg)
                    exe = path
            if not exe:
                return
        profile = store.profile_dir_for_browser(acc["id"], kind)
        args = [exe, *store.build_chrome_args(store.effective_cfg(self.cfg, acc), profile, extra_urls)]
        # 打开浏览器就是干净打开：不代装任何插件。插件靠用户在商店页
        # 一次点好（见 install_rec_via_store），装完永久在册，跟真机一样。
        try:
            kwargs = {}
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            proc = subprocess.Popen(args, close_fds=True, **kwargs)
            old = self._procs.get(acc["id"])
            if old is None or old.poll() is not None:
                self._procs[acc["id"]] = proc
                self._launched_at[acc["id"]] = time.time()
            self._launched.add(acc["id"])
            self._bump_today_open()
            get_log().action(f"打开账号「{acc['name']}」（{label}）")
            self._rebuild_cards()
        except Exception as exc:  # 启动失败要如实报错，不装没事
            get_log().error(f"打开账号「{acc['name']}」失败：{exc}")
            QMessageBox.critical(self, "打开失败", f"{label} 启动失败：{exc}")

    def close_account_browser(self, acc_id: str):
        """关掉这个账号的浏览器：先给窗口发关闭消息（优雅关），3 秒没退就结束进程。"""
        proc = self._procs.get(acc_id)
        if proc is not None and proc.poll() is None:
            _close_windows_for_pid(proc.pid)
            for _ in range(30):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._procs.pop(acc_id, None)
        self._launched.discard(acc_id)
        self._launched_at.pop(acc_id, None)
        get_log().action(f"关闭账号浏览器（{acc_id}）")
        self._rebuild_cards()

    def _poll_procs(self):
        """Chrome 主进程退出了，对应账号卡片的状态就改回「未打开」。
        （重复打开同一账号时新进程会把窗口交给已运行的实例后立刻退出，
        所以只认第一次启动的那个进程句柄，不被后续短命进程顶掉。）"""
        changed = False
        for acc_id, proc in list(self._procs.items()):
            if proc.poll() is not None:
                del self._procs[acc_id]
                self._launched_at.pop(acc_id, None)
                if acc_id in self._launched:
                    self._launched.discard(acc_id)
                    changed = True
        if changed:
            self._rebuild_cards()

    # ---------- 检查更新 / 软件内更新 ----------
    def check_update(self):
        self.btn_update.setEnabled(False)
        self.btn_update.setText("检查中…")
        self._checker = UpdateChecker(store.fetch_proxy_url(self.cfg), self)
        self._checker.done.connect(self._on_update_result)
        self._checker.start()

    def _restore_update_btn(self):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("检查更新")

    def _on_update_result(self, ok: bool, tag: str, url: str, detail: str,
                          asset_url: str, size: int, sha: str):
        self._restore_update_btn()
        if not ok or not tag:
            QMessageBox.information(
                self, "检查更新",
                f"检查失败：{detail or '连不上 GitHub'}。\n（先确认代理工具开着、软件里的代理设置没关，再试一次。）",
            )
            return
        # 同版本补丁（标签形如 v1.9.1.1、软件版本号不变）：装过就不再提示
        if (store.parse_version(tag)[:3] == store.parse_version(__version__)
                and tag.lstrip("vV") != __version__
                and self.cfg.get("patch_tag", "") == tag):
            QMessageBox.information(
                self, "检查更新", f"已是最新版本（v{__version__}，补丁已装）。"
            )
            return
        if not store.is_newer(tag, __version__):
            QMessageBox.information(
                self, "检查更新", f"已是最新版本（v{__version__}）。"
            )
            return
        frozen = bool(getattr(sys, "frozen", False))
        is_setup = "setup" in asset_url.rsplit("/", 1)[-1].lower()
        is_patch = (store.parse_version(tag)[:3] == store.parse_version(__version__)
                    and tag.lstrip("vV") != __version__)
        box = QMessageBox(self)
        box.setWindowTitle("检查更新")
        if frozen and asset_url and is_setup:
            if is_patch:
                box.setText(
                    f"发现 v{__version__} 的补丁（{tag}，版本号不变）。\n"
                    "点「立即更新」直接在软件里下载补丁安装包，下载完自动安装、"
                    "原地替换程序文件（账号数据保留），装完自动重新打开。"
                )
            else:
                box.setText(
                    f"发现新版本 {tag}（你现在是 v{__version__}）。\n"
                    "点「立即更新」直接在软件里下载安装包，下载完自动安装、"
                    "原地替换程序文件（账号数据保留），装完自动重新打开。"
                )
            btn_go = box.addButton("立即更新", QMessageBox.ButtonRole.AcceptRole)
        elif frozen and asset_url:
            box.setText(
                f"发现新版本 {tag}（你现在是 v{__version__}）。\n"
                "点「立即更新」直接在软件里下载，下载完自动替换成新版并重新打开，不用去网页下。"
            )
            btn_go = box.addButton("立即更新", QMessageBox.ButtonRole.AcceptRole)
        else:
            box.setText(
                f"发现新版本 {tag}（你现在是 v{__version__}）。\n点「打开下载页」去下载新版。"
            )
            btn_go = box.addButton("打开下载页", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("以后再说", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not btn_go:
            return
        if frozen and asset_url:
            self._start_self_update(tag, asset_url, size, sha)
        else:
            QDesktopServices.openUrl(QUrl(url or (REPO_URL + "/releases")))

    def _start_self_update(self, tag: str, asset_url: str, size: int, sha: str):
        # 更新落点分两种：
        # - 安装版（当前文件名就是 MuseChrome.exe）：新版下到数据目录，
        #   更新时原地覆盖同名文件，桌面快捷方式永远有效。
        # - 便携版（文件名带版本号）：新版直接下到当前 exe 同目录、用新版文件名，
        #   更新后文件名跟版本走，不再把新内容塞进旧文件名里。
        cur = Path(sys.executable)
        if "setup" in asset_url.rsplit("/", 1)[-1].lower():
            # 安装包更新：下到数据目录的 update 里，装的时候指回当前目录
            dest = store.data_dir() / "update" / asset_url.rsplit("/", 1)[-1]
        elif cur.name.lower() == "musechrome.exe":
            dest = store.data_dir() / "update" / f"MuseChrome-{tag}.exe"
        else:
            dest = cur.parent / f"MuseChrome-{tag}.exe"
            if dest == cur:  # 同名兜底（理论上不会发生）：走覆盖模式
                dest = store.data_dir() / "update" / f"MuseChrome-{tag}.exe"
        dlg = QProgressDialog("正在下载新版本…", "取消", 0, 100, self)
        dlg.setWindowTitle("检查更新")
        dlg.setMinimumWidth(360)
        dlg.setValue(0)
        self._dl = DownloadThread(
            asset_url, dest, store.fetch_proxy_url(self.cfg), size, sha, self
        )
        self._dl_progress = dlg
        self._dl.progress.connect(lambda p: dlg.setValue(p if p >= 0 else 0))
        self._dl.done.connect(lambda ok2, path, why: self._on_download_done(ok2, path, why, tag))
        dlg.canceled.connect(self._dl.requestInterruption)
        self._dl.start()
        dlg.show()

    def _on_download_done(self, ok: bool, path: str, why: str, tag: str):
        if hasattr(self, "_dl_progress"):
            self._dl_progress.close()
        if not ok:
            if why != "已取消":
                QMessageBox.information(
                    self, "检查更新",
                    f"下载失败：{why}。\n（先确认代理工具开着，再试一次；也可以去 GitHub 发布页手动下载。）",
                )
            return
        # 补丁标签装机后记进配置文件，下次检查更新不再重复提示；
        # 装的是正式新版本时把补丁标记清掉
        try:
            cfg_now = store.load_config()
            if (store.parse_version(tag)[:3] == store.parse_version(__version__)
                    and tag.lstrip("vV") != __version__):
                cfg_now["patch_tag"] = tag
            elif cfg_now.get("patch_tag"):
                cfg_now["patch_tag"] = ""
            store.save_config(cfg_now)
        except Exception:
            pass
        new_exe = Path(path)
        cur_exe = Path(sys.executable)
        if "setup" in new_exe.name.lower():
            QMessageBox.information(
                self, "检查更新",
                f"新版本 {tag} 的安装包已下载并校验通过。\n"
                "点「确定」后软件会自动关闭、运行安装包原地替换程序文件"
                "（账号数据保留），装完自动重新打开。",
            )
            bat = new_exe.parent / "apply_update.bat"
            bat.write_text(
                build_setup_bat(new_exe, cur_exe.parent, cur_exe),
                encoding="mbcs",
            )
        elif new_exe.parent == cur_exe.parent and new_exe != cur_exe:
            QMessageBox.information(
                self, "检查更新",
                f"新版本 {tag} 已下载并校验通过（{new_exe.name}）。\n"
                "点「确定」后软件会自动关闭、删掉旧文件并打开新版。",
            )
            bat = new_exe.parent / "apply_update.bat"
            bat.write_text(build_rename_bat(new_exe, cur_exe), encoding="mbcs")
        else:
            QMessageBox.information(
                self, "检查更新",
                f"新版本 {tag} 已下载并校验通过。\n点「确定」后软件会自动关闭、替换成新版并重新打开。",
            )
            bat = new_exe.parent / "apply_update.bat"
            bat.write_text(build_updater_bat(new_exe, cur_exe), encoding="mbcs")
        try:
            kwargs = {}
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            subprocess.Popen(["cmd", "/c", str(bat)], close_fds=True, **kwargs)
        except Exception as exc:
            QMessageBox.critical(self, "检查更新", f"启动更新失败：{exc}\n新文件已下载在：{new_exe}")
            return
        QApplication.quit()

    # ---------- 设置 ----------
    def save_settings(self):
        seen = self.cfg.get("notice_seen", "")
        patch = self.cfg.get("patch_tag", "")
        old_theme = self.cfg.get("theme", "light")
        self.cfg = {**store.DEFAULT_CONFIG, **self.page_settings.collect()}
        self.cfg["notice_seen"] = seen  # 公告已读标记不在设置页里，别被保存设置冲掉
        self.cfg["patch_tag"] = patch  # 补丁标记同理
        store.save_config(self.cfg)
        self._refresh_proxy_label()
        get_log().action("保存设置")
        if self.cfg.get("theme") != old_theme:
            self.page_settings.lbl_saved.setText("已保存 ✓（外观下次打开软件时生效）")
        else:
            self.page_settings.lbl_saved.setText("已保存 ✓")

    # ---------- 备份 / 恢复 ----------
    def export_backup(self):
        box = QMessageBox(self)
        box.setWindowTitle("导出备份")
        box.setText("选备份范围：\n\n完整备份：账号、设置和每个账号的登录态全打包，换电脑导入后免登录。\n轻量备份：只打包账号列表和设置，导入后每个账号要重新登录一次。\n\n完整备份里含登录凭证，等于钥匙，请自己收好、不要外传。")
        btn_full = box.addButton("完整备份", QMessageBox.ButtonRole.AcceptRole)
        btn_light = box.addButton("轻量备份", QMessageBox.ButtonRole.ActionRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (btn_full, btn_light):
            return
        import time as _time
        default = f"MuseChrome-backup-{_time.strftime('%Y%m%d')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "保存备份", default, "Zip 备份 (*.zip)")
        if not path:
            return
        try:
            store.export_backup(path, include_profiles=clicked is btn_full)
            QMessageBox.information(self, "导出备份", "备份已保存。")
        except Exception as exc:
            QMessageBox.critical(self, "导出备份", f"导出失败：{exc}")

    def import_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择备份文件", "", "Zip 备份 (*.zip)")
        if not path:
            return
        ret = QMessageBox.question(
            self, "导入恢复",
            "导入会覆盖现在的账号列表和设置（覆盖前的版本会自动留一份在 MuseChromeData 里）。\n如果备份含登录态，正在打开的浏览器请先关掉。继续？",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            summary = store.import_backup(path)
        except Exception as exc:
            QMessageBox.critical(self, "导入恢复", f"导入失败：{exc}")
            return
        self.cfg = store.load_config()
        self.accounts = store.load_accounts()
        if not self.accounts:
            self.accounts = [{"id": store.new_account_id(), "name": "账号 1", "browser": "chrome", "proxy": ""}]
            store.save_accounts(self.accounts)
        self._selected_id = self.accounts[0]["id"]
        self._refresh_proxy_label()
        self.page_settings.load(self.cfg)
        self._rebuild_cards()
        tail = "含登录态，打开账号应该免登录。" if summary["profiles"] else "不含登录态，每个账号要重新登录一次。"
        QMessageBox.information(self, "导入恢复", f"已恢复 {summary['accounts']} 个账号。{tail}")
