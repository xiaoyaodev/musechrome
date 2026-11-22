"""主区页面：设置、插件助手、关于软件（关于页带检查更新按钮）。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, REPO_URL, __version__, store

GUIDE_URL = "https://github.com/xiaoyaodev/browser-privacy-dual-guide/blob/master/chrome.md"
from .iconutil import icon_path
from .fxbuttons import FxButton
from .widgets import AnimButton, HoverListWidget, SwitchRow, ToggleSwitch
from .theme import C, _paint_bg, themed


NOTE_TEXT = """使用说明：
• 点「打开」→ 弹出这个账号自己的浏览器窗口（第一次是全新浏览器，登录一次 Muse 即可，之后免登录）。
• 每个账号的登录、Cookie、插件都存在它自己的目录里，账号之间完全隔离。
• 每个账号可以在卡片上单独选浏览器：谷歌 Chrome 或微软 Edge，哪个账号用哪个互不影响；两个浏览器各用各的配置目录，第一次用某个浏览器打开某账号时要登录一次。
• 代理在打开时通过启动参数带给浏览器（本地代理默认 127.0.0.1:10808；也可以在设置里选跟随系统代理，或开了 TUN 时选直连）；打开前先确认你的代理工具开着。打不开先去左侧「环境自检」查一遍。
• 插件要每个账号装一次：点账号卡片上的「插件助手」（浏览器插件助手页），把你日常 Chrome 的插件清单读出来，逐个打开商店页点「添加」即可，装好就一直都在。
• 账号多了不用一个个点：右上角「打开全部」会把没打开的账号排队逐个打开；卡片上的「编辑」可以给账号写备注、选颜色标记，靠备注和颜色认号。
• 左侧边栏下方的月亮按钮能一键切换深浅外观；环境自检会顺带显示代理延迟。
• 同一个账号重复点「打开」不会开两个号，只会再给它开一个窗口。
• 代理/语言这类参数只在浏览器第一次打开时生效；改了设置，先把该账号的浏览器窗口全关掉再打开。"""


class SettingsPage(QWidget):
    """设置页：在主区里切换显示，不再是独立弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel("设置")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("本地代理（自己填地址端口）", "local")
        self.cmb_mode.addItem("跟随系统代理（Clash 等工具开系统代理时选这个）", "system")
        self.cmb_mode.addItem("直连（开了 TUN 模式时选这个）", "off")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("HTTP", "http")
        self.cmb_type.addItem("SOCKS5", "socks5")
        self.edt_host = QLineEdit()
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        # 常用工具预设：点一下填好地址端口，不用查自己用的工具是哪个端口。
        # 这一行直接以布局进表单（不再套一层盒子控件——套盒子时表单按
        # 盒子的尺寸提示排版，真机上把按钮压得贴近下一行的边框，
        # Smith 三次指出）；布局自带边距：上 2 下 12，按钮下方留足
        # 呼吸，跟下面输入框的边框拉开距离
        self.preset_btns: list[AnimButton] = []
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 2, 0, 0)
        preset_row.setSpacing(8)
        for name, ptype, phost, pport in store.PROXY_PRESETS:
            btn = FxButton(name)
            # 固定高度＋全局样式里的 #presetBtn 规则（自带样式表会让
            # 文字错位，本地截图实证，走全局规则）
            btn.setObjectName("presetBtn")
            btn.setFixedHeight(34)
            btn.clicked.connect(
                lambda _c=False, t=ptype, h=phost, p=pport: self._apply_preset(t, h, p)
            )
            preset_row.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self.preset_btns.append(btn)
        preset_row.addStretch(1)
        # 按钮下方垫一条固定高间隔：表单在高度紧张时会先吃
        # 布局的下边距（实测边距 12 被吃到只剩 3px，按钮贴着下一行
        # 输入框的边框——Smith 三次指出的就是这个），固定间隔不缩
        from PyQt6.QtWidgets import QSizePolicy, QSpacerItem, QVBoxLayout

        preset_field = QVBoxLayout()
        preset_field.setContentsMargins(0, 0, 0, 0)
        preset_field.setSpacing(0)
        preset_field.addLayout(preset_row)
        preset_field.addSpacerItem(
            QSpacerItem(1, 6, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        self._preset_row = preset_field
        self.edt_home = QLineEdit()
        self.edt_chrome = QLineEdit()
        btn_browse = FxButton("浏览…")
        btn_browse.clicked.connect(self._browse_chrome)
        chrome_row = QHBoxLayout()
        chrome_row.addWidget(self.edt_chrome, 1)
        chrome_row.addWidget(btn_browse)
        self.edt_edge = QLineEdit()
        btn_browse_edge = FxButton("浏览…")
        btn_browse_edge.clicked.connect(self._browse_edge)
        edge_row = QHBoxLayout()
        edge_row.addWidget(self.edt_edge, 1)
        edge_row.addWidget(btn_browse_edge)
        self.chk_lang = ToggleSwitch()
        self.chk_webrtc = ToggleSwitch()
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem("浅色", "light")
        self.cmb_theme.addItem("深色", "dark")

        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.addRow("代理方式", self.cmb_mode)
        form.addRow("代理类型", self.cmb_type)
        form.addRow("代理地址", self.edt_host)
        form.addRow("代理端口", self.spn_port)
        form.addRow("常用工具", self._preset_row)
        form.addRow("主页地址", self.edt_home)
        form.addRow("Chrome 路径", chrome_row)
        form.addRow("Edge 路径", edge_row)
        self._lang_lbl = QLabel("浏览器和插件用英文（--lang=en-US，与代理出口地区一致）；关掉则用中文")
        themed(self._lang_lbl, "color: @text@;")
        form.addRow(SwitchRow(self.chk_lang, self._lang_lbl))
        self._webrtc_lbl = QLabel("WebRTC 防泄漏（禁止 WebRTC 走非代理 UDP，避免真实 IP 从 WebRTC 泄漏）")
        themed(self._webrtc_lbl, "color: @text@;")
        form.addRow(SwitchRow(self.chk_webrtc, self._webrtc_lbl))
        form.addRow("外观", self.cmb_theme)

        note = QLabel("Chrome / Edge 路径留空 = 自动查找；自动找不到时再手动选对应的 exe。")
        note.setWordWrap(True)
        themed(note, "color: @dim@; font-size: 12px;")

        self.btn_export = FxButton("导出备份")
        self.btn_import = AnimButton("导入恢复")
        backup_note = QLabel("换电脑/重装时用：导出一个 zip，另一台导入即可。完整备份含登录态，别外传。")
        themed(backup_note, "color: @dim@; font-size: 12px;")
        backup_row = QHBoxLayout()
        backup_row.addWidget(self.btn_export)
        backup_row.addWidget(self.btn_import)
        backup_row.addWidget(backup_note)
        backup_row.addStretch(1)

        self.btn_save = FxButton("保存设置")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_back = FxButton("返回账号列表")
        self.lbl_saved = QLabel("")
        self.lbl_saved.setStyleSheet("color: #2e7d32; font-weight: bold;")
        row = QHBoxLayout()
        row.addWidget(self.btn_save)
        row.addWidget(self.btn_back)
        row.addWidget(self.lbl_saved)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 14, 22, 8)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(backup_row)
        layout.addLayout(row)
        layout.addStretch(1)

    def load(self, cfg: dict):
        mode = cfg.get("proxy_mode", "local")
        idx = self.cmb_mode.findData(mode)
        self.cmb_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self._on_mode_changed()
        self.cmb_type.setCurrentIndex(1 if cfg["proxy_type"] == "socks5" else 0)
        self.edt_host.setText(str(cfg["proxy_host"]))
        self.spn_port.setValue(int(cfg["proxy_port"]))
        self.edt_home.setText(str(cfg["home_url"]))
        self.edt_chrome.setText(str(cfg["chrome_path"]))
        self.edt_edge.setText(str(cfg["edge_path"]))
        self.chk_lang.setChecked(bool(cfg["lang_en"]))
        self.chk_webrtc.setChecked(bool(cfg["webrtc_protect"]))
        tidx = self.cmb_theme.findData(cfg.get("theme", "light"))
        self.cmb_theme.setCurrentIndex(tidx if tidx >= 0 else 0)
        self.lbl_saved.setText("")

    def collect(self) -> dict:
        mode = self.cmb_mode.currentData()
        return dict(
            proxy_enabled=mode == "local",
            proxy_mode=mode,
            proxy_type=self.cmb_type.currentData(),
            proxy_host=self.edt_host.text().strip() or "127.0.0.1",
            proxy_port=self.spn_port.value(),
            home_url=self.edt_home.text().strip(),
            chrome_path=self.edt_chrome.text().strip(),
            edge_path=self.edt_edge.text().strip(),
            lang_en=self.chk_lang.isChecked(),
            webrtc_protect=self.chk_webrtc.isChecked(),
            theme=self.cmb_theme.currentData(),
        )

    def _on_mode_changed(self):
        local = self.cmb_mode.currentData() == "local"
        for w in (self.cmb_type, self.edt_host, self.spn_port, *self.preset_btns):
            w.setEnabled(local)

    def _apply_preset(self, ptype: str, host: str, port: int):
        self.cmb_type.setCurrentIndex(1 if ptype == "socks5" else 0)
        self.edt_host.setText(host)
        self.spn_port.setValue(port)

    def _browse_chrome(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 chrome.exe", self.edt_chrome.text() or r"C:\Program Files\Google\Chrome\Application",
            "chrome.exe (chrome.exe)",
        )
        if path:
            self.edt_chrome.setText(path)

    def _browse_edge(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 msedge.exe", self.edt_edge.text() or r"C:\Program Files (x86)\Microsoft\Edge\Application",
            "msedge.exe (msedge.exe)",
        )
        if path:
            self.edt_edge.setText(path)


class PluginPage(QWidget):
    """插件助手页：两个分页——「我的插件」读你日常 Chrome 的清单去商店装；
    「推荐插件」是软件内置的五个，点一键安装后打开账号浏览器就已经装好了。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel("浏览器插件助手")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")
        self.lbl_target = QLabel("")
        themed(self.lbl_target, "color: @dim@;")

        # ---- 分页一：我的插件 ----
        tab_mine = QWidget()
        _paint_bg(tab_mine)
        intro = QLabel(
            "你日常 Chrome 里装的插件，默认不勾，用哪个勾哪个。勾好点「打开商店页安装」，"
            "我在这个账号的浏览器里逐个打开商店页，你逐页点「添加」。\n"
            "SwitchyOmega 在「推荐插件」页里，装法一样。"
        )
        intro.setWordWrap(True)
        self.list = HoverListWidget()
        self.list.checkable_rows = True
        self.lbl_empty = QLabel(
            "没在你的日常 Chrome 里读到插件清单。\n"
            "（日常 Chrome 装在默认位置才读得到；也可以在账号的 Chrome 里直接去应用商店装。）"
        )
        self.lbl_empty.setWordWrap(True)
        self.btn_go = FxButton("打开商店页安装")
        self.btn_go.setObjectName("primaryBtn")
        mine_row = QHBoxLayout()
        mine_row.addWidget(self.btn_go)
        mine_row.addStretch(1)
        mine_layout = QVBoxLayout(tab_mine)
        mine_layout.setContentsMargins(4, 10, 4, 4)
        mine_layout.setSpacing(10)
        mine_layout.addWidget(intro)
        mine_layout.addWidget(self.lbl_empty)
        mine_layout.addWidget(self.list, 1)
        mine_layout.addLayout(mine_row)

        # ---- 分页二：推荐插件 ----
        tab_rec = QWidget()
        _paint_bg(tab_rec)
        rec_intro = QLabel(
            "《浏览器隐私双路线指南》Chrome 篇的推荐清单。勾好点「打开商店页安装」，"
            "我把商店页在这个账号的浏览器里打开，你逐个点「添加到 Chrome」。"
            "装一次永久生效、自动更新，之后打开浏览器不再弹任何东西。"
            "（新版 Chrome 不让软件代装插件，商店安装是唯一能长期保留的装法。）"
        )
        rec_intro.setWordWrap(True)
        self.rec_list = HoverListWidget()
        self.rec_list.checkable_rows = True
        self.lbl_rec_status = QLabel("")
        themed(self.lbl_rec_status, "color: @dim@; font-size: 12px;")
        self.lbl_rec_status.setWordWrap(True)
        self.btn_install = FxButton("打开商店页安装")
        self.btn_install.setObjectName("primaryBtn")
        rec_row = QHBoxLayout()
        rec_row.addWidget(self.btn_install)
        rec_row.addStretch(1)
        rec_layout = QVBoxLayout(tab_rec)
        rec_layout.setContentsMargins(4, 10, 4, 4)
        rec_layout.setSpacing(10)
        rec_layout.addWidget(rec_intro)
        rec_layout.addWidget(self.rec_list, 1)
        rec_layout.addWidget(self.lbl_rec_status)
        rec_layout.addLayout(rec_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(tab_mine, "我的插件")
        self.tabs.addTab(tab_rec, "推荐插件")

        self.btn_back = FxButton("返回账号列表")
        row = QHBoxLayout()
        row.addWidget(self.btn_back)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(self.lbl_target)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(row)

    def refresh(self, account_name: str, exts: list[dict], acc: dict | None = None):
        self.lbl_target.setText(f"给账号「{account_name}」安装插件：")
        keep = {
            str(self.list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        }
        self.list.clear()
        for ext in exts:
            item = QListWidgetItem(f"{ext['name']}")
            item.setForeground(QBrush(QColor(C["text"])))
            item.setData(Qt.ItemDataRole.UserRole, ext["id"])
            # 默认全不勾：用户用哪个勾哪个（Smith 定的，免得误开一堆
            # 商店页）；切页刷新时把原来勾着的带回来
            item.setCheckState(
                Qt.CheckState.Checked
                if str(ext["id"]) in keep
                else Qt.CheckState.Unchecked
            )
            self.list.addItem(item)
        has = bool(exts)
        self.list.setVisible(has)
        self.lbl_empty.setVisible(not has)
        self.btn_go.setEnabled(has)
        self.refresh_rec(acc)

    def refresh_rec(self, acc: dict | None):
        from . import extensions as ext_mod

        states = ext_mod.store_state_map(acc)
        keep = {
            str(self.rec_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.rec_list.count())
            if self.rec_list.item(i).checkState() == Qt.CheckState.Checked
        }
        self.rec_list.clear()
        for ext in ext_mod.BUILTIN:
            installed = states.get(ext["slug"], False)
            state = "已安装" if installed else "未安装"
            item = QListWidgetItem(f"{ext['name']}（{state}）\n{ext['desc']}")
            item.setForeground(QBrush(QColor(C["text"])))
            item.setData(Qt.ItemDataRole.UserRole, ext["slug"])
            # 默认全不勾（Smith 定）：要哪个自己勾；但切页刷新时
            # 把原来勾着的带回来，不能用户勾完一切页就没了
            item.setCheckState(
                Qt.CheckState.Checked
                if ext["slug"] in keep
                else Qt.CheckState.Unchecked
            )
            self.rec_list.addItem(item)

    def selected_ids(self) -> list[str]:
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def selected_rec_slugs(self) -> list[str]:
        out = []
        for i in range(self.rec_list.count()):
            item = self.rec_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def selected_rec_ids(self) -> list[str]:
        from . import extensions as ext_mod

        return [ext_mod.BY_SLUG[s]["id"] for s in self.selected_rec_slugs()]


ABOUT_TEXT = """Muse 账号管理器

给每个 Muse 账号准备一个完全独立的浏览器配置目录，点「打开」就用你电脑上的真 Chrome 或 Edge 启动它（每个账号可以在卡片上单独选）：独立的登录状态、Cookie、插件和浏览数据，账号之间互不串号。

打开时自动带上本地代理（默认 127.0.0.1:10808）、WebRTC 防泄漏和英文语言标识，指纹与原装浏览器一致。管理器本身不含浏览器、不联网、不收集任何数据；所有账号数据只存在软件旁边的 MuseChromeData 文件夹里。

「浏览器插件助手」可以读出你日常 Chrome 的插件清单，在账号的浏览器里逐个打开商店页，点「添加」即装好同款插件。"""

DISCLAIMER_TEXT = """1. 永久免费，认准官方渠道：本软件永久免费、开源发布（MIT 许可），官方版本不含病毒和恶意代码。请只从官方 GitHub 仓库的 Releases 页面下载；任何收费出售本软件的都是骗局，从非官方渠道下载的版本可能被篡改或捆绑恶意程序，由此造成的损失作者概不负责。

2. 责任限制：本软件按「现状」提供，不作任何明示或暗示的担保。因使用本软件而引致的任何意外、疏忽、合同纠纷、名誉损害、版权或知识产权侵犯及其所造成的损失，以及账号受限、数据丢失等后果，作者概不负责，亦不承担任何法律责任，由使用者自行承担。

3. 合规使用：请遵守你所在地区的法律法规，并遵守 Muse 等目标平台的服务条款。因违规使用本软件导致的任何法律纠纷或损失，由使用者自行承担。

4. 数据在本地，自行保管：所有账号数据只保存在你本机的 MuseChromeData 文件夹，作者不收集、不上传。请自行备份；导出的完整备份包含登录状态，等同账号钥匙，切勿外传。

5. 无官方关联：本软件是独立的第三方工具，名称中的「Muse」仅用于表明用途（管理 Muse 账号），与 Google、Microsoft 及 Muse 官方没有任何隶属、合作或授权关系；Chrome、Edge、Muse 等商标归各自权利人所有。"""


class AboutPage(QWidget):
    """关于软件页：在主区里切换显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        title = QLabel(f"{APP_NAME} v{__version__}")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")
        head = QHBoxLayout()
        p = icon_path()
        if p:
            pix = QLabel()
            pix.setPixmap(QPixmap(str(p)).scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            head.addWidget(pix)
        head.addWidget(title, 1)

        body = QLabel(ABOUT_TEXT)
        body.setWordWrap(True)

        link = QLabel(f'GitHub 项目地址：<a href="{REPO_URL}">{REPO_URL}</a>')
        link.setOpenExternalLinks(True)
        link.setWordWrap(True)

        guide = QLabel(
            '谷歌推荐插件使用配置方法：'
            f'<a href="{GUIDE_URL}">{GUIDE_URL}</a>'
        )
        guide.setOpenExternalLinks(True)
        guide.setWordWrap(True)

        disc_title = QLabel("免责声明")
        themed(disc_title, "font-size: 14px; font-weight: bold; color: @text@;")
        disc = QLabel(DISCLAIMER_TEXT)
        disc.setWordWrap(True)
        disc.setStyleSheet("font-size: 12px; color: #6b6259;")

        self.btn_update = FxButton("检查更新")
        self.btn_back = FxButton("返回账号列表")
        row = QHBoxLayout()
        row.addWidget(self.btn_update)
        row.addWidget(self.btn_back)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(body)
        layout.addWidget(link)
        layout.addWidget(guide)
        layout.addWidget(disc_title)
        layout.addWidget(disc)
        layout.addLayout(row)
        layout.addStretch(1)
