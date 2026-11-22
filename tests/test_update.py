"""自更新纯逻辑测试：挑 exe 资产、替换脚本内容。运行：python tests/test_update.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from musechrome.app import _pick_update_asset, build_rename_bat, build_setup_bat, build_updater_bat

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


rel = {
    "assets": [
        {"name": "notes.txt", "browser_download_url": "https://x/notes.txt", "size": 10},
        {
            "name": "MuseChrome-v9.9.9.exe",
            "browser_download_url": "https://x/MuseChrome-v9.9.9.exe",
            "size": 12345,
            "digest": "sha256:ABCDEF",
        },
    ]
}
url, size, sha = _pick_update_asset(rel)
check("挑中 exe 资产", url.endswith(".exe") and size == 12345)
check("解析 sha256 摘要", sha == "ABCDEF")
check("无 exe 时返回空", _pick_update_asset({"assets": []}) == ("", 0, ""))
check("无 digest 时摘要为空", _pick_update_asset({"assets": [{"name": "a.exe", "browser_download_url": "u", "size": 1}]})[2] == "")
rel2 = {"assets": [
    {"name": "MuseChrome-Setup-v9.9.9.exe", "browser_download_url": "https://x/setup.exe", "size": 1, "digest": "sha256:FF"},
    {"name": "MuseChrome-v9.9.9.exe", "browser_download_url": "https://x/app.exe", "size": 2, "digest": "sha256:EE"},
]}
check("安装包资产优先", _pick_update_asset(rel2)[0] != "https://x/app.exe")

bat = build_updater_bat(Path(r"C:\app\MuseChromeData\update\MuseChrome-v9.9.9.exe"), Path(r"C:\app\MuseChrome.exe"))
check("替换脚本含源和目标", "MuseChrome-v9.9.9.exe" in bat and 'set "DST=C:\\app\\MuseChrome.exe"' in bat)
check("替换脚本带重试与自删", "for /L" in bat and 'del "%~f0"' in bat and 'start "" "%DST%"' in bat)

rbat = build_rename_bat(Path(r"C:\app\MuseChrome-v9.9.9.exe"), Path(r"C:\app\MuseChrome-v1.0.0.exe"))
check("换名脚本含新旧文件名", 'set "NEW=C:\\app\\MuseChrome-v9.9.9.exe"' in rbat and 'set "OLD=C:\\app\\MuseChrome-v1.0.0.exe"' in rbat)
check("换名脚本删旧启新带延时", 'del "%OLD%"' in rbat and 'start "" "%NEW%"' in rbat and "timeout /t 2" in rbat and 'del "%~f0"' in rbat)

sbat = build_setup_bat(Path(r"C:\app\MuseChromeData\update\MuseChrome-Setup-v9.9.9.exe"), Path(r"C:\app"), Path(r"C:\app\MuseChrome.exe"))
check("安装脚本带静默参数", "/S" in sbat)
check("安装脚本指回原目录", "/D=%APPDIR%" in sbat and 'set "APPDIR=C:\\app"' in sbat.replace("\\\\", "\\"))
check("安装脚本装完重启主程序", 'start "" "C:\\app\\MuseChrome.exe"' in sbat)

print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
