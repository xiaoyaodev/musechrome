"""Muse 账号管理器入口：组装日志、翻译、图标，拉起主窗口。

具体功能都拆在各模块里（v1.9.0 起按 Smith 的要求分文件，方便修 bug）：
- mainwin.py   主窗口与账号操作
- pages.py     设置 / 插件助手 / 关于页面
- notices.py   公告解析、拉取与公告页
- health.py    环境自检
- updater.py   检查更新与自更新
- dialogs.py   账号编辑 / 代理对话框
- theme.py     黑白渐变主题与毛玻璃底图
- widgets.py   图标栏与涟漪按钮；icons.py 线性图标
- extensions.py 内置推荐插件
- applog.py    运行日志；logpage.py 日志页
- store.py     配置与账号数据
- splash.py    启动动画（入场→颗粒→衔接主页）
- fxbuttons.py 按钮动效；themeswitch.py 日夜开关
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QLibraryInfo, QTimer, Qt, QTranslator
from PyQt6.QtWidgets import QApplication

from . import APP_NAME, __version__, store
from .applog import init as _init_log
from .applog import install_hooks
from .iconutil import app_icon, icon_path
from .mainwin import MainWindow

# 兼容旧引用（测试与工具脚本从 app 导入这些名字）
from .dialogs import AccountEditDialog, AccountProxyDialog  # noqa: F401
from .notices import NoticeFetcher, NoticePage, parse_notices  # noqa: F401
from .pages import AboutPage, PluginPage, SettingsPage  # noqa: F401
from .theme import app_style, set_theme  # noqa: F401
from .updater import (  # noqa: F401
    DownloadThread,
    UpdateChecker,
    _pick_update_asset,
    build_rename_bat,
    build_setup_bat,
    build_updater_bat,
)

__all__ = ["run", "MainWindow", "app_icon", "icon_path"]


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    cfg = store.load_config()
    if not cfg.get("ui_v191_defaulted"):
        # 默认外观改浅色（Smith 2026-11-22 拍板：打开就是图二那种浅色）；
        # 只迁一次，之后用户自己切的深浅都按用户的来
        cfg["theme"] = "light"
        cfg["ui_v190_defaulted"] = True
        cfg["ui_v191_defaulted"] = True
        store.save_config(cfg)
    log = _init_log(store.data_dir() / "logs")
    install_hooks(log)
    log.info(f"MuseChrome v{__version__} 启动")
    # 颜色方案跟随外观设置：浅色时强制浅色（系统深色下调色板文字会变白，
    # 压到浅色底上看不见，插件名单就这么丢过）；选了深色就让对话框也走深色
    try:
        app.styleHints().setColorScheme(
            Qt.ColorScheme.Dark if cfg.get("theme") == "dark" else Qt.ColorScheme.Light
        )
    except Exception:
        pass
    # 让系统对话框按钮显示中文（关闭/取消/保存）；加载失败就保持英文，不影响功能
    translator = QTranslator(app)
    if translator.load(
        "qtbase_zh_CN",
        QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
    ):
        app.installTranslator(translator)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow(cfg)
    # 启动动画（splash.py）：入场→化颗粒→颗粒在主页上空散尽衔接；
    # 动画出任何问题就直接显示主窗口，不挡正事
    try:
        from PyQt6.QtCore import QVariantAnimation

        from .splash import SplashScreen, WelcomeOverlay

        splash = SplashScreen()
        # 居中（主窗口默认也居中，两者大致同心，颗粒正好落在主页中央）
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            splash.move(
                geo.center().x() - splash.width() // 2,
                geo.center().y() - splash.height() // 2,
            )

        def _reveal_main():
            # 主页放慢淡入（0.8s），颗粒同时在上空散
            from PyQt6.QtCore import QEasingCurve

            window.setWindowOpacity(0.0)
            window.show()
            anim = QVariantAnimation(window)
            anim.setDuration(800)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.valueChanged.connect(
                lambda v: window.setWindowOpacity(float(v))
            )
            window._reveal_anim = anim  # 保命引用，防被回收
            anim.start()
            # 衔接尾段：欢迎语在主页中央淡入再消失
            def _welcome():
                ov = WelcomeOverlay(window)
                ov.play()
                window._welcome_ov = ov

            QTimer.singleShot(600, _welcome)

        splash.reveal.connect(_reveal_main)
        splash.show()
        splash.start()
        log.info("启动动画播放中")
    except Exception:
        log.error("启动动画初始化失败，直接显示主窗口")
        window.show()
    log.info("主窗口已显示")
    return app.exec()
