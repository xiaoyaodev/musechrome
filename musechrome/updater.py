"""检查更新与软件内自更新：查 Release、下载校验、生成替换脚本。"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from . import REPO_URL, store
from .netutil import _make_opener, _update_error_detail, fetch_bytes


class _DownloadCancelled(Exception):
    """下载被用户中断（内部信号，不当错误处理）。"""


LATEST_API = (
    REPO_URL.replace("https://github.com/", "https://api.github.com/repos/")
    + "/releases/latest"
)
def _pick_update_asset(release: dict) -> tuple[str, int, str]:
    """从 Release JSON 里挑更新资产，返回 (下载地址, 字节数, sha256摘要)。
    安装包（名字带 setup 的 exe）优先——更新时静默运行它原地替换程序
    文件；没有安装包才退回便携版主 exe；都没有返回空。"""
    setup_hit = None
    exe_hit = None
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        if not name.lower().endswith(".exe"):
            continue
        digest = str(asset.get("digest") or "")
        sha = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
        hit = (
            str(asset.get("browser_download_url") or ""),
            int(asset.get("size") or 0),
            sha,
        )
        if "setup" in name.lower():
            setup_hit = setup_hit or hit
        else:
            exe_hit = exe_hit or hit
    return setup_hit or exe_hit or ("", 0, "")


def build_updater_bat(src: Path, dst: Path) -> str:
    """生成替换脚本：等旧 exe 退出后把新文件覆盖过去，再启动新版，最后自删。"""
    lines = [
        "@echo off",
        "setlocal",
        f'set "SRC={src}"',
        f'set "DST={dst}"',
        "for /L %%i in (1,1,40) do (",
        '  copy /y "%SRC%" "%DST%" >nul 2>&1 && goto done',
        "  timeout /t 1 /nobreak >nul",
        ")",
        ":done",
        "timeout /t 2 /nobreak >nul",
        'start "" "%DST%"',
        'del "%SRC%" >nul 2>&1',
        'del "%~f0"',
    ]
    return "\r\n".join(lines) + "\r\n"


def build_rename_bat(new_exe: Path, old_exe: Path) -> str:
    """生成换名更新脚本：新版已下载到旧 exe 同目录（新文件名），
    等旧 exe 退出后删掉旧文件，稍等片刻再启动新版，最后自删。
    延时启动是给杀毒软件留出扫描新文件的时间，免得首次启动解压被挡。"""
    lines = [
        "@echo off",
        "setlocal",
        f'set "NEW={new_exe}"',
        f'set "OLD={old_exe}"',
        "timeout /t 2 /nobreak >nul",
        "for /L %%i in (1,1,40) do (",
        '  del "%OLD%" >nul 2>&1 && goto startnew',
        "  timeout /t 1 /nobreak >nul",
        ")",
        ":startnew",
        "timeout /t 1 /nobreak >nul",
        'start "" "%NEW%"',
        'del "%~f0"',
    ]
    return "\r\n".join(lines) + "\r\n"


def build_setup_bat(setup_exe: Path, app_dir: Path, app_exe: Path) -> str:
    """生成安装包更新脚本：等旧程序退出后静默运行安装包，把程序文件
    原地替换到当前目录（账号数据 MuseChromeData 保留），再启动新版，
    最后删安装包和脚本自身。NSIS 的 /D 参数必须是最后一个且不能加引号。"""
    lines = [
        "@echo off",
        "setlocal",
        f'set "SETUP={setup_exe}"',
        f'set "APPDIR={app_dir}"',
        "timeout /t 2 /nobreak >nul",
        '"%SETUP%" /S /D=%APPDIR%',
        "timeout /t 1 /nobreak >nul",
        f'start "" "{app_exe}"',
        'del "%SETUP%" >nul 2>&1',
        'del "%~f0"',
    ]
    return "\r\n".join(lines) + "\r\n"


def _probe_asset(url: str, proxy_url: str | None) -> int:
    """HEAD 探一下资产在不在，返回大小（字节），不在或探不到返回 0。

    API 被限流时用发布页跳转拿到版本号，再按仓库固定的资产命名
    （MuseChrome-Setup-<tag>.exe）探真实地址——探到了才报给界面，
    探不到宁可让界面引导去发布页，也不给一个会 404 的地址。
    """
    routes = [proxy_url, None] if proxy_url else [None]
    for px in routes:
        try:
            opener = _make_opener(px)
            req = urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": "MuseChrome"}
            )
            with opener.open(req, timeout=10) as resp:
                size = int(resp.headers.get("Content-Length") or 0)
                if resp.status == 200 and size > 0:
                    return size
        except Exception:
            continue
    return 0


class UpdateChecker(QThread):
    """后台查 GitHub 最新 Release；走软件里配置的本地代理（关代理则直连）。

    证书校验用随软件打包的 CA 包；先查 API，失败再退到网页版
    /releases/latest 的跳转地址解析版本号（不受 API 限流影响）。
    """

    # 成功?, 最新 tag, 发布页地址, 失败原因, exe 下载地址, exe 字节数, exe sha256
    done = pyqtSignal(bool, str, str, str, str, int, str)

    def __init__(self, proxy_url: str | None, parent=None):
        super().__init__(parent)
        self.proxy_url = proxy_url

    def run(self):
        try:
            raw, _final = fetch_bytes(
                LATEST_API, self.proxy_url, timeout=12,
                allow_direct=True, log_tag="检查更新",
            )
            data = json.loads(raw.decode("utf-8"))
            tag = str(data.get("tag_name") or "")
            if tag:
                asset_url, size, sha = _pick_update_asset(data)
                self.done.emit(
                    True, tag, str(data.get("html_url") or ""), "", asset_url, size, sha
                )
                return
            raise RuntimeError("GitHub 没返回版本号")
        except Exception as api_exc:
            try:
                _raw, final_url = fetch_bytes(
                    REPO_URL + "/releases/latest", self.proxy_url,
                    timeout=12, allow_direct=True, log_tag="检查更新(发布页)",
                )
                m = re.search(r"/tag/([^/?#]+)", final_url)
                if m:
                    tag = m.group(1)
                    # 按固定命名探安装包资产：探到才给地址（带大小校验），
                    # 探不到就留空，界面引导去发布页——不重蹈拼错 404。
                    asset_url, size = "", 0
                    for name in (f"MuseChrome-Setup-{tag}.exe", f"MuseChrome-{tag}.exe"):
                        cand = f"{REPO_URL}/releases/download/{tag}/{name}"
                        probed = _probe_asset(cand, self.proxy_url)
                        if probed > 0:
                            asset_url, size = cand, probed
                            break
                    self.done.emit(True, tag, final_url, "", asset_url, size, "")
                    return
                raise RuntimeError("没解析出版本号")
            except Exception:
                self.done.emit(False, "", "", _update_error_detail(api_exc), "", 0, "")


class DownloadThread(QThread):
    """后台下载新版 exe：走本地代理，带进度；下完校验大小和 sha256（有值才验）。"""

    progress = pyqtSignal(int)  # 0-100，不知总长时发 -1
    done = pyqtSignal(bool, str, str)  # 成功?, 保存路径, 失败原因

    def __init__(self, url: str, dest: Path, proxy_url: str | None,
                 expect_size: int = 0, expect_sha: str = "", parent=None):
        super().__init__(parent)
        self.url = url
        self.dest = dest
        self.proxy_url = proxy_url
        self.expect_size = expect_size
        self.expect_sha = expect_sha

    def run(self):
        # 代理这条路断了（节点掐 TLS）自动换直连再下一次
        routes = [self.proxy_url, None] if self.proxy_url else [None]
        last_exc: Exception | None = None
        for px in routes:
            try:
                self._download_once(_make_opener(px))
                return
            except _DownloadCancelled:
                self.done.emit(False, "", "已取消")
                return
            except Exception as exc:
                last_exc = exc
        self.done.emit(False, "", _update_error_detail(last_exc) if last_exc else "下载失败")

    def _download_once(self, opener):
        import hashlib

        part = self.dest.with_suffix(self.dest.suffix + ".part")
        try:
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(self.url, headers={"User-Agent": "MuseChrome"})
            h = hashlib.sha256()
            got = 0
            with opener.open(req, timeout=30) as resp, open(part, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0) or self.expect_size
                while True:
                    if self.isInterruptionRequested():
                        f.close()
                        part.unlink(missing_ok=True)
                        raise _DownloadCancelled()
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    self.progress.emit(int(got * 100 / total) if total else -1)
            if self.expect_size and got != self.expect_size:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"下载不完整（{got}/{self.expect_size} 字节）")
            if self.expect_sha and h.hexdigest().lower() != self.expect_sha.lower():
                part.unlink(missing_ok=True)
                raise RuntimeError("下载文件校验失败，已丢弃")
            part.replace(self.dest)
            self.done.emit(True, str(self.dest), "")
        except Exception:
            part.unlink(missing_ok=True)
            raise
