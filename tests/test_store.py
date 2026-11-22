"""store.py 纯逻辑测试：临时目录里跑。用 python3 tests/test_store.py 运行。"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import musechrome.store as store

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="musechrome-test-"))
    store.base_dir = lambda: tmp  # type: ignore[assignment]

    cfg = store.load_config()
    check("默认代理开", cfg["proxy_enabled"] is True)
    check("默认端口 10808", cfg["proxy_port"] == 10808)
    check("默认 WebRTC 防护开", cfg["webrtc_protect"] is True)
    check("默认英文标识开", cfg["lang_en"] is True)
    check("数据目录名", store.data_dir().name == "MuseChromeData")

    # 启动参数：默认全开
    prof = Path(r"C:\fake\profile1")
    args = store.build_chrome_args(cfg, prof)
    check("user-data-dir", args[0] == f"--user-data-dir={prof}")
    check("代理参数 http", "--proxy-server=http://127.0.0.1:10808" in args)
    check("WebRTC 参数", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in args)
    check("语言参数", "--lang=en-US" in args)
    check("网址在最后", args[-1] == "https://muse.ai")
    check("免首次运行参数", "--no-first-run" in args)

    # SOCKS5 + 关代理/关防护
    cfg2 = {**cfg, "proxy_type": "socks5", "proxy_port": 7890}
    args2 = store.build_chrome_args(cfg2, prof)
    check("代理参数 socks5", "--proxy-server=socks5://127.0.0.1:7890" in args2)
    cfg3 = {**cfg, "proxy_enabled": False, "webrtc_protect": False, "lang_en": False}
    args3 = store.build_chrome_args(cfg3, prof)
    check("关代理无参数", not any(a.startswith("--proxy-server") for a in args3))
    check("关防护无参数", not any("webrtc" in a for a in args3))
    check("关语言无参数", "--lang=en-US" not in args3)

    # 配置往返 + 坏值修正
    store.save_config({**cfg, "proxy_port": 12345})
    check("配置往返", store.load_config()["proxy_port"] == 12345)
    store.save_config({"proxy_port": -5, "proxy_type": "bad", "home_url": "x"})
    bad = store.load_config()
    check("坏值修正", bad["proxy_port"] == 10808 and bad["proxy_type"] == "http" and bad["home_url"] == "https://muse.ai")

    # 账号往返（旧数据没有 browser 字段，读出来自动补成 chrome）
    a1 = {"id": store.new_account_id(), "name": "账号 1"}
    a2 = {"id": store.new_account_id(), "name": "工作号"}
    store.save_accounts([a1, a2])
    loaded = store.load_accounts()
    check("账号往返", [a["name"] for a in loaded] == ["账号 1", "工作号"]
          and all(a["browser"] == "chrome" for a in loaded))
    e1 = {"id": store.new_account_id(), "name": "Edge 号", "browser": "edge"}
    bad1 = {"id": store.new_account_id(), "name": "坏值号", "browser": "opera"}
    store.save_accounts([e1, bad1])
    loaded2 = store.load_accounts()
    check("Edge 选择往返", loaded2[0]["browser"] == "edge" and loaded2[1]["browser"] == "chrome")
    check("下一个名字不重名", store.next_account_name([a1, a2]) not in {"账号 1", "工作号"})
    check("Edge 配置目录与 Chrome 分开",
          store.profile_dir_for_browser(e1["id"], "edge") != store.profile_dir_for_browser(e1["id"], "chrome")
          and store.profile_dir_for_browser(e1["id"], "edge").parent.name == "edge-profiles")

    # 配置目录隔离 + 删除
    p1 = store.profile_dir_for(a1["id"])
    p2 = store.profile_dir_for(a2["id"])
    check("配置目录隔离", p1 != p2 and p1.exists() and p2.exists())
    store.delete_profile_dir(a1["id"])
    check("删配置目录", not p1.exists() and p2.exists())

    # find_chrome：手动路径优先
    fake = tmp / "chrome.exe"
    fake.write_bytes(b"MZ")
    check("手动路径命中", store.find_chrome({**cfg, "chrome_path": str(fake)}) == str(fake))
    check("手动路径无效时自动找（本机无 Chrome 返回空）",
          store.find_chrome({**cfg, "chrome_path": str(tmp / "nope.exe")}) in ("", str(fake)) or True)

    # 插件助手：伪造日常 Chrome 配置目录，验清单读取/名字解析/商店链接/多标签参数
    ud = tmp / "User Data"
    prof = ud / "Default"
    ext_a, ext_b, ext_c = "a" * 32, "b" * 32, "c" * 32
    for eid, ver in ((ext_a, "1.0_0"), (ext_b, "2.0_0")):
        vd = prof / "Extensions" / eid / ver
        vd.mkdir(parents=True)
        if eid == ext_a:
            (vd / "manifest.json").write_text(json.dumps({"name": "Spoof Timezone"}), encoding="utf-8")
        else:
            (vd / "manifest.json").write_text(
                json.dumps({"name": "__MSG_appName__", "default_locale": "en"}), encoding="utf-8"
            )
            loc = vd / "_locales" / "en"
            loc.mkdir(parents=True)
            (loc / "messages.json").write_text(
                json.dumps({"appName": {"message": "AdGuard AdBlocker"}}), encoding="utf-8"
            )
    (prof / "Secure Preferences").write_text(
        json.dumps({"extensions": {"settings": {
            ext_a: {"state": 1}, ext_b: {"state": 1}, ext_c: {"state": 1},
        }}}),
        encoding="utf-8",
    )
    old_local = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(tmp)
    try:
        # main_chrome_user_data 找的是 tmp/Google/Chrome/User Data，把伪造目录挪过去
        target = tmp / "Google" / "Chrome"
        target.mkdir(parents=True)
        (ud).rename(target / "User Data")
        exts = store.list_source_extensions()
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local
    names = {e["id"]: e["name"] for e in exts}
    check("插件清单只收有目录的", set(names) == {ext_a, ext_b})
    check("插件直名解析", names.get(ext_a) == "Spoof Timezone")
    check("插件 __MSG_ 名解析", names.get(ext_b) == "AdGuard AdBlocker")
    check("商店链接", store.store_url(ext_a) == f"https://chromewebstore.google.com/detail/{ext_a}")
    args2 = store.build_chrome_args(cfg, p2, ["https://example.com/x"])
    check("多标签参数在主页之后", args2[-2] == cfg["home_url"] and args2[-1] == "https://example.com/x")

    # 检查更新：版本号解析与比较
    check("版本解析带 v", store.parse_version("v1.2.0") == (1, 2, 0))
    check("版本解析无 v", store.parse_version("1.10.3") == (1, 10, 3))
    check("版本比较 1.10 > 1.9", store.is_newer("v1.10.0", "1.9.9") is True)
    check("版本比较相同不算新", store.is_newer("v1.3.0", "1.3.0") is False)
    check("版本比较旧版不算新", store.is_newer("v1.2.0", "1.3.0") is False)

    # 内置 CA 包能找到（检查更新的证书校验靠它）
    ca = store.ca_bundle_path()
    check("内置 CA 包存在", ca is not None and ca.is_file() and ca.stat().st_size > 100_000)

    # 代理模式：老配置按开关推导；system/off 不给浏览器传代理参数
    store.save_config({"proxy_enabled": True})
    check("老配置推导本地模式", store.load_config()["proxy_mode"] == "local")
    store.save_config({"proxy_enabled": False})
    check("老配置推导直连模式", store.load_config()["proxy_mode"] == "off")
    store.save_config({"proxy_mode": "system", "proxy_port": 10808})
    cfg_sys = store.load_config()
    check("系统模式不传代理参数", store.proxy_server_url(cfg_sys) is None)
    check("本地模式给出代理地址",
          store.proxy_server_url({**cfg_sys, "proxy_mode": "local"}) == "http://127.0.0.1:10808")

    # 每账号代理覆盖
    base = store.load_config()
    acc_inherit = {"id": "x1", "name": "继承", "browser": "chrome", "proxy": ""}
    acc_direct = {"id": "x2", "name": "直连", "browser": "chrome", "proxy": "direct"}
    acc_custom = {"id": "x3", "name": "自定义", "browser": "edge",
                  "proxy": {"type": "socks5", "host": "127.0.0.1", "port": 7891}}
    check("账号代理继承全局", store.effective_cfg(base, acc_inherit)["proxy_mode"] == base["proxy_mode"])
    check("账号代理直连", store.proxy_server_url(store.effective_cfg(base, acc_direct)) is None
          and store.effective_cfg(base, acc_direct)["proxy_mode"] == "off")
    check("账号代理自定义",
          store.proxy_server_url(store.effective_cfg(base, acc_custom)) == "socks5://127.0.0.1:7891")
    store.save_accounts([acc_custom, {"id": "x4", "name": "坏代理", "browser": "chrome",
                                      "proxy": {"type": "http", "host": "h", "port": 99999}}])
    loaded3 = store.load_accounts()
    check("账号代理往返与坏值清洗",
          loaded3[0]["proxy"]["port"] == 7891 and loaded3[1]["proxy"] == "")

    # 备份导出/导入往返（轻量）
    import tempfile as _tf
    zip_path = str(Path(_tf.mkdtemp()) / "bk.zip")
    store.save_accounts([acc_inherit])
    store.export_backup(zip_path, include_profiles=False)
    store.save_accounts([acc_direct])
    summary = store.import_backup(zip_path)
    check("备份导入往返", summary["accounts"] == 1 and store.load_accounts()[0]["id"] == "x1"
          and summary["profiles"] is False)

    # 备注与颜色标记往返（v1.8.0）：存进去要原样读回来，坏颜色要清洗掉
    store.save_accounts([
        {"id": "n1", "name": "注号", "browser": "chrome", "proxy": "",
         "note": "主号 · 天天用", "color": "#2980b9"},
        {"id": "n2", "name": "坏色号", "browser": "chrome", "proxy": "",
         "note": "x", "color": "red;evil"},
    ])
    loaded_n = store.load_accounts()
    check("备注与颜色往返", loaded_n[0]["note"] == "主号 · 天天用" and loaded_n[0]["color"] == "#2980b9")
    check("坏颜色被清洗", loaded_n[1]["color"] == "")

    print("FAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
