"""配置、账号与 Chrome 启动参数（纯逻辑，不依赖 Qt，可独立测试）。

数据目录：exe 旁边的 MuseChromeData/ 文件夹。
- MuseChromeData/config.json          全局设置
- MuseChromeData/accounts.json        账号列表 [{id, name, browser}]
- MuseChromeData/chrome-profiles/<id> 每个账号独立的 Chrome 配置目录
- MuseChromeData/edge-profiles/<id>   每个账号独立的 Edge 配置目录（与 Chrome 分开）
- MuseChromeData/notices_cache.json   公告缓存（拉不到时显示上次内容）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

from . import DEFAULT_HOME_URL

DATA_DIR_NAME = "MuseChromeData"

DEFAULT_CONFIG = {
    "proxy_enabled": True,
    "proxy_mode": "local",  # local 本地代理 / system 跟随系统代理 / off 直连（TUN）
    "proxy_type": "http",  # http | socks5 —— v2rayN 的 10808 两种都收
    "proxy_host": "127.0.0.1",
    "proxy_port": 10808,
    "home_url": DEFAULT_HOME_URL,
    "chrome_path": "",  # 空 = 自动找
    "edge_path": "",  # 空 = 自动找
    "lang_en": True,  # 启动参数 --lang=en-US
    "webrtc_protect": True,  # 禁止 WebRTC 走非代理 UDP，防真实 IP 泄漏
    "notice_seen": "",  # 已点开看过的最新公告指纹，用于公告按钮的（新）标记
    "patch_tag": "",  # 已装过的同版本补丁标签（如 v1.9.1.1），防重复提示
    "theme": "light",  # dark 曜黑 / light 黑白分明（默认浅色，Smith 2026-11-22 定）
    "ui_v190_defaulted": False,  # v1.9.0 首次启动把外观强制回默认深色一次（老测试版存下的浅色不作数）
    "win_geo": None,  # [x, y, w, h] 外观切换进程重启时把窗口放回原位用
    "open_stats": {"date": "", "count": 0},  # 今日打开次数（总览页统计用）
}


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    d = base_dir() / DATA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir() -> Path:
    d = data_dir() / "chrome-profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_dir_for(acc_id: str) -> Path:
    d = profiles_dir() / acc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def edge_profiles_dir() -> Path:
    d = data_dir() / "edge-profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def edge_profile_dir_for(acc_id: str) -> Path:
    d = edge_profiles_dir() / acc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_dir_for_browser(acc_id: str, browser: str) -> Path:
    """按账号选的浏览器给配置目录：Chrome 与 Edge 各用各的，互不干扰。"""
    if browser == "edge":
        return edge_profile_dir_for(acc_id)
    return profile_dir_for(acc_id)


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    saved = _read_json(data_dir() / "config.json", {})
    if isinstance(saved, dict):
        cfg.update({k: saved[k] for k in DEFAULT_CONFIG if k in saved})
    try:
        cfg["proxy_port"] = int(cfg["proxy_port"])
        if not (1 <= cfg["proxy_port"] <= 65535):
            raise ValueError
    except Exception:
        cfg["proxy_port"] = DEFAULT_CONFIG["proxy_port"]
    if cfg["proxy_type"] not in ("http", "socks5"):
        cfg["proxy_type"] = "http"
    if not str(cfg["home_url"]).startswith(("http://", "https://")):
        cfg["home_url"] = DEFAULT_HOME_URL
    for key in ("proxy_enabled", "lang_en", "webrtc_protect"):
        cfg[key] = bool(cfg[key])
    # 代理模式：老配置没有这个字段时，按原来的开关推导（开=本地代理，关=直连）
    # 注意要看「存盘文件里有没有」而不是合并后的值——默认值里有 local，会把推导挡住
    if isinstance(saved, dict) and saved.get("proxy_mode") in ("local", "system", "off"):
        cfg["proxy_mode"] = saved["proxy_mode"]
    else:
        cfg["proxy_mode"] = "local" if cfg["proxy_enabled"] else "off"
    cfg["proxy_host"] = str(cfg["proxy_host"]).strip() or "127.0.0.1"
    cfg["chrome_path"] = str(cfg["chrome_path"]).strip()
    cfg["edge_path"] = str(cfg["edge_path"]).strip()
    cfg["notice_seen"] = str(cfg["notice_seen"])
    cfg["patch_tag"] = str(cfg.get("patch_tag") or "")
    return cfg


def save_config(cfg: dict) -> None:
    _write_json(data_dir() / "config.json", cfg)


def load_accounts() -> list[dict]:
    saved = _read_json(data_dir() / "accounts.json", [])
    accounts = []
    if isinstance(saved, list):
        for item in saved:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                browser = str(item.get("browser") or "chrome")
                if browser not in ("chrome", "edge"):
                    browser = "chrome"
                proxy = item.get("proxy") or ""
                if isinstance(proxy, dict):
                    try:
                        port = int(proxy.get("port"))
                        if not (1 <= port <= 65535):
                            raise ValueError
                        proxy = {
                            "type": proxy.get("type") if proxy.get("type") in ("http", "socks5") else "http",
                            "host": str(proxy.get("host") or "127.0.0.1").strip() or "127.0.0.1",
                            "port": port,
                        }
                    except Exception:
                        proxy = ""
                elif proxy != "direct":
                    proxy = ""
                note = str(item.get("note") or "")[:60]
                color = str(item.get("color") or "")
                if color and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                    color = ""
                raw_exts = item.get("builtin_exts") or []
                builtin_exts = [
                    str(s) for s in raw_exts if isinstance(s, str) and len(s) <= 40
                ] if isinstance(raw_exts, list) else []
                accounts.append({
                    "id": str(item["id"]),
                    "name": str(item["name"]),
                    "browser": browser,
                    "proxy": proxy,
                    "note": note,
                    "color": color,
                    "builtin_exts": builtin_exts,
                    # 旧版本（自动代装插件那套）留下的记录，现在只作存档，
                    # 插件装没装以浏览器登记册为准（见 extensions.store_state_map）
                    "builtin_exts_set": "builtin_exts" in item,
                })
    return accounts


def save_accounts(accounts: list[dict]) -> None:
    _write_json(data_dir() / "accounts.json", accounts)


def load_notices_cache() -> dict:
    saved = _read_json(data_dir() / "notices_cache.json", {})
    if isinstance(saved, dict) and isinstance(saved.get("text"), str):
        return {"text": saved["text"], "fetched_at": str(saved.get("fetched_at") or "")}
    return {"text": "", "fetched_at": ""}


def save_notices_cache(text: str, fetched_at: str) -> None:
    _write_json(
        data_dir() / "notices_cache.json", {"text": text, "fetched_at": fetched_at}
    )


def notice_image_path(url: str) -> Path:
    """公告图片的本地缓存路径（按地址哈希命名，下过一次就不再重复下载）。"""
    import hashlib

    ext = ".png"
    tail = url.split("?")[0].rsplit(".", 1)
    if len(tail) == 2 and tail[1].lower() in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "." + tail[1].lower()
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] + ext
    return data_dir() / "notice_images" / name


def new_account_id() -> str:
    return uuid.uuid4().hex[:12]


def next_account_name(accounts: list[dict]) -> str:
    n = len(accounts) + 1
    names = {a["name"] for a in accounts}
    while f"账号 {n}" in names:
        n += 1
    return f"账号 {n}"


def delete_profile_dir(acc_id: str) -> None:
    """删账号时连它的 Chrome 配置一起删（浏览器开着时可能删不净，忽略残留）。"""
    shutil.rmtree(profiles_dir() / acc_id, ignore_errors=True)


def delete_edge_profile_dir(acc_id: str) -> None:
    """同上，Edge 的配置目录。"""
    shutil.rmtree(edge_profiles_dir() / acc_id, ignore_errors=True)


def export_backup(dest: str, include_profiles: bool) -> None:
    """把数据打包成 zip 备份。

    轻量备份只有 config.json + accounts.json；完整备份再加上两个浏览器的
    配置目录（含登录态——等于钥匙，界面上会提醒用户自己收好）。
    """
    import zipfile

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("config.json", "accounts.json"):
            f = data_dir() / name
            if f.is_file():
                z.write(f, f"MuseChromeData/{name}")
        if include_profiles:
            for base in ("chrome-profiles", "edge-profiles"):
                root = data_dir() / base
                if root.is_dir():
                    for f in sorted(root.rglob("*")):
                        if f.is_file():
                            z.write(f, f"MuseChromeData/{base}/{f.relative_to(root)}")


def import_backup(src: str) -> dict:
    """导入备份 zip，返回 {"accounts": 账号数, "profiles": 是否含登录态}。

    覆盖前先把当前的 config/accounts 复制一份到 backup-before-import-*
    文件夹，出问题能手动找回。解压做路径校验，防 zip 里藏越界路径。
    """
    import time
    import zipfile

    with zipfile.ZipFile(src) as z:
        names = [n for n in z.namelist() if n.startswith("MuseChromeData/") and not n.endswith("/")]
        if "MuseChromeData/accounts.json" not in names:
            raise ValueError("这个文件里没有 MuseChrome 的账号数据，不是有效的备份")
        safety = data_dir() / f"backup-before-import-{time.strftime('%Y%m%d-%H%M%S')}"
        safety.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "accounts.json"):
            cur = data_dir() / name
            if cur.is_file():
                shutil.copy2(cur, safety / name)
        has_profiles = False
        base = data_dir().resolve()
        for name in names:
            rel = name[len("MuseChromeData/"):]
            target = (data_dir() / rel).resolve()
            if base not in target.parents and target != base:
                continue  # 越界路径跳过
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
            if "/profiles/" in name or "-profiles/" in name:
                has_profiles = True
    return {"accounts": len(load_accounts()), "profiles": has_profiles}


def proxy_server_url(cfg: dict) -> str | None:
    """本地代理模式下返回代理地址；跟随系统/直连模式返回 None（不给浏览器传代理参数）。

    跟随系统模式不传参数，是因为 Chromium 默认就用 Windows 系统代理；
    直连模式面向开了 TUN 的用户，流量在网络层就走了。
    """
    if cfg.get("proxy_mode", "local") != "local":
        return None
    if cfg.get("proxy_enabled") is False:
        return None  # 老配置/手拼配置里开关关着就是关着
    scheme = "socks5" if cfg.get("proxy_type") == "socks5" else "http"
    return f"{scheme}://{cfg['proxy_host']}:{cfg['proxy_port']}"


def system_proxy_url() -> str | None:
    """读 Windows 系统代理设置，返回 http://host:port；没启用/读不到返回 None。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            try:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except OSError:
                return None
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except (ImportError, OSError):
        return None
    server = str(server or "").strip()
    if not server:
        return None
    if "=" in server:  # 形如 http=127.0.0.1:7890;https=127.0.0.1:7890
        parts = dict(p.split("=", 1) for p in server.split(";") if "=" in p)
        server = parts.get("https") or parts.get("http") or ""
    if not server:
        return None
    if "://" not in server:
        server = "http://" + server
    return server


def fetch_proxy_url(cfg: dict) -> str | None:
    """软件自己联网（公告、检查更新）该用的代理。

    本地模式用配置的地址；跟随系统模式去读系统代理（不读的话人在国内
    连 GitHub 检查更新会失败）；直连模式不用代理。
    """
    mode = cfg.get("proxy_mode", "local")
    if mode == "local":
        return proxy_server_url(cfg)
    if mode == "system":
        return system_proxy_url()
    return None


# 常见代理工具的本地端口（自检时逐个探活，用户用的不是 v2rayN 也能找到）
COMMON_PROXY_PORTS = [10808, 10809, 7890, 7897, 1080, 1081, 6152, 6153,
                      20171, 2080, 8080, 8118, 8888, 7070]
# 设置页的工具预设：点一下把类型/地址/端口填好
PROXY_PRESETS = [
    ("v2rayN", "http", "127.0.0.1", 10808),
    ("Clash", "http", "127.0.0.1", 7890),
    ("Shadowsocks", "socks5", "127.0.0.1", 1080),
]


def effective_cfg(cfg: dict, acc: dict) -> dict:
    """把账号自己的代理覆盖合并进全局设置，得到这个账号实际用的设置。

    acc["proxy"]："" 跟随全局 / "direct" 这个账号直连 /
    {"type","host","port"} 这个账号用自己的本地代理。
    """
    proxy = (acc or {}).get("proxy") or ""
    if proxy == "direct":
        return {**cfg, "proxy_mode": "off"}
    if isinstance(proxy, dict):
        return {
            **cfg,
            "proxy_mode": "local",
            "proxy_enabled": True,
            "proxy_type": proxy.get("type", "http"),
            "proxy_host": proxy.get("host", "127.0.0.1"),
            "proxy_port": proxy.get("port", 10808),
        }
    return cfg


def ca_bundle_path() -> Path | None:
    """随软件打包的 CA 证书包位置（检查更新做 HTTPS 校验用）。

    打包后的 exe 不能依赖系统 Python 的证书路径（目标机器上往往不存在），
    所以把 Mozilla 根证书包跟软件一起带走。
    """
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets" / "cacert.pem")
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "cacert.pem")
    for c in candidates:
        if c.is_file():
            return c
    return None


def parse_version(s: str) -> tuple[int, ...]:
    """把 'v1.2.0' / '1.2' 解析成可比较的整数元组。"""
    out = []
    for part in str(s).strip().lstrip("vV").split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)


def is_newer(remote: str, local: str) -> bool:
    """远端版本号是否比本地新（检查更新用）。"""
    return parse_version(remote) > parse_version(local)


def main_chrome_user_data() -> Path | None:
    """用户日常 Chrome 的数据目录（插件助手从这里读已装插件清单）。"""
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    p = Path(local) / "Google" / "Chrome" / "User Data"
    return p if p.is_dir() else None


def _resolve_ext_name(profile_dir: Path, ext_id: str) -> str:
    """读插件 manifest 拿显示名（处理 __MSG_xx__ 国际化名字）。"""
    ext_root = profile_dir / "Extensions" / ext_id
    try:
        versions = sorted(d for d in ext_root.iterdir() if d.is_dir())
    except OSError:
        return ext_id
    if not versions:
        return ext_id
    vdir = versions[-1]
    try:
        manifest = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return ext_id
    name = str(manifest.get("name") or "").strip()
    if name.startswith("__MSG_") and name.endswith("__"):
        key = name[6:-2]
        locales = [manifest.get("default_locale"), "en_US", "en", "zh_CN", "zh_TW"]
        for loc in locales:
            if not loc:
                continue
            try:
                msgs = json.loads(
                    (vdir / "_locales" / loc / "messages.json").read_text(encoding="utf-8")
                )
            except Exception:
                continue
            entry = msgs.get(key) or msgs.get(key.lower())
            if isinstance(entry, dict) and entry.get("message"):
                return str(entry["message"])
        return key
    return name or ext_id


def list_source_extensions() -> list[dict]:
    """扫描日常 Chrome 各配置的已装插件，返回 [{id, name}]（按名排序、去重）。"""
    ud = main_chrome_user_data()
    if ud is None:
        return []
    profiles = [ud / "Default"] + sorted(ud.glob("Profile *"))
    found: dict[str, dict] = {}
    for prof in profiles:
        sp = prof / "Secure Preferences"
        if not sp.is_file():
            continue
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        settings = ((data.get("extensions") or {}).get("settings")) or {}
        for ext_id, st in settings.items():
            if ext_id in found or not isinstance(st, dict):
                continue
            if not (prof / "Extensions" / ext_id).is_dir():
                continue  # 内置组件插件不在配置目录里，跳过
            found[ext_id] = {"id": ext_id, "name": _resolve_ext_name(prof, ext_id)}
    return sorted(found.values(), key=lambda e: e["name"].lower())


def store_url(ext_id: str) -> str:
    return f"https://chromewebstore.google.com/detail/{ext_id}"


def find_local_extension_dir(ext_id: str) -> Path | None:
    """在用户日常 Chrome 的各配置里找某个插件已装好的文件目录（最新版）。

    找到就能整份复制出来当解压版插件用——用户自己浏览器里装着的，
    就是最可靠的来源，不用再去谷歌通道下载。
    """
    ud = main_chrome_user_data()
    if ud is None:
        return None
    profiles = [ud / "Default"] + sorted(ud.glob("Profile *"))
    best: Path | None = None
    for prof in profiles:
        root = prof / "Extensions" / ext_id
        if not root.is_dir():
            continue
        try:
            versions = sorted(
                (d for d in root.iterdir() if d.is_dir() and (d / "manifest.json").is_file()),
                key=lambda d: parse_version(d.name),
            )
        except OSError:
            continue
        if versions:
            best = versions[-1]
    return best


def profile_store_ext_ids(profile_dir: Path) -> set[str]:
    """读浏览器配置的 Secure Preferences，返回已登记的插件 ID 集合。

    商店正经装的插件会登记在这里、跨重启保留——拿推荐插件的商店 ID
    对一下，就知道哪个账号已经装过哪几个了。只读，不改浏览器任何文件。
    """
    sp = profile_dir / "Default" / "Secure Preferences"
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return set()
    settings = ((data.get("extensions") or {}).get("settings")) or {}
    return {str(k) for k in settings.keys()}


def build_chrome_args(cfg: dict, profile_dir: Path, extra_urls: list[str] | None = None) -> list[str]:
    """组装启动浏览器的命令行参数（网址放最后）。

    Chrome 与 Edge 同为 Chromium 内核，这套参数两边通用：
    独立配置目录、本地代理、WebRTC 防泄漏、英文语言标识。
    """
    args = [
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    url = proxy_server_url(cfg)
    if url:
        args.append(f"--proxy-server={url}")
    if cfg.get("webrtc_protect"):
        args.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
    if cfg.get("lang_en"):
        args.append("--lang=en-US")
    else:
        # 不带英文标识时明确给中文：浏览器界面和插件语言都跟着走中文
        # （插件有没有中文看它自带语言包，AdGuard/ZeroOmega/隐私獾都有）
        args.append("--lang=zh-CN")
    args.append(str(cfg["home_url"]))
    for u in extra_urls or []:
        args.append(str(u))
    return args


def chrome_candidates() -> list[Path]:
    """常见的 Chrome 安装位置（按优先级）。"""
    out: list[Path] = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    for root in (pf, pf86, local):
        if root:
            out.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
    # 注册表 App Paths（chrome.exe 的标准登记处）
    try:
        import winreg

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                ) as key:
                    val, _ = winreg.QueryValueEx(key, None)
                    if val:
                        out.insert(0, Path(val))
            except OSError:
                pass
    except ImportError:
        pass
    return out


def find_chrome(cfg: dict) -> str:
    """返回可用的 chrome.exe 路径，找不到返回空串。"""
    manual = str(cfg.get("chrome_path", "")).strip()
    if manual and Path(manual).is_file():
        return manual
    for cand in chrome_candidates():
        if cand.is_file():
            return str(cand)
    return ""


def edge_candidates() -> list[Path]:
    """常见的 Edge 安装位置（按优先级）。"""
    out: list[Path] = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    for root in (pf, pf86, local):
        if root:
            out.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    # 注册表 App Paths（msedge.exe 的标准登记处）
    try:
        import winreg

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
                ) as key:
                    val, _ = winreg.QueryValueEx(key, None)
                    if val:
                        out.insert(0, Path(val))
            except OSError:
                pass
    except ImportError:
        pass
    return out


def find_edge(cfg: dict) -> str:
    """返回可用的 msedge.exe 路径，找不到返回空串。"""
    manual = str(cfg.get("edge_path", "")).strip()
    if manual and Path(manual).is_file():
        return manual
    for cand in edge_candidates():
        if cand.is_file():
            return str(cand)
    return ""


def find_browser_exe(cfg: dict, browser: str) -> str:
    """按账号选的浏览器找可执行文件：edge 找 Edge，其余找 Chrome。"""
    if browser == "edge":
        return find_edge(cfg)
    return find_chrome(cfg)
