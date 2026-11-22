# -*- mode: python ; coding: utf-8 -*-
# MuseChrome 打包：文件夹版（onedir），窗口程序（纯 PyQt6，不含 WebEngine）。
# 不用单文件版的原因：单文件 exe 运行时要把内置文件解压到系统临时目录，
# 在用户机器上出现过临时文件被清掉、导致公告/插件/自检中途失效的问题（v1.9.0 实测）。

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/icon.png', 'assets'), ('assets/cacert.pem', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MuseChrome',
    icon='assets/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MuseChrome',
)
