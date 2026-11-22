"""内置推荐插件清单：只管清单和"装没装"的检测，安装走商店页。

为什么不自动装（2026-11-22 在真 Chrome 158 上逐条实测的结论）：
新版 Chrome 把软件侧载插件的路全堵死了——调试通道装的只活当次会话、
--load-extension 被停用、外部安装文件夹不认——关机重开全没，
还每次弹欢迎页。只有用户在商店页点「添加到 Chrome」的正经安装
能装一次、永久保留、自动更新，跟他自己浏览器里装的一样。
所以这里的流程是：软件把商店页在账号的浏览器里打开，用户点一次，
之后靠读浏览器配置的登记册（store.profile_store_ext_ids）认状态，
装过的永远不再打扰。
"""

from __future__ import annotations

from . import store

# slug, 商店ID, 显示名, 一句话作用（顺序就是推荐页里的顺序）
BUILTIN = [
    {
        "slug": "zeroomega",
        # 商店现行 ID：老 ID padekgcemlokbadohgkifijomclgjgif 的页面已下线
        # （2026-11-22 实测打开是「此商品不可用」），发布者把清单迁到了这个
        # 新 ID（还是 suziwen1，源码仓 zero-peak/ZeroOmega，v3.5.2）
        "id": "pfnededegaaopdmhkdmcofjmoldfiped",
        "legacy_ids": ["padekgcemlokbadohgkifijomclgjgif"],
        "name": "Proxy SwitchyOmega 3（ZeroOmega）",
        "desc": "浏览器层分流开关：把流量交给本机代理客户端（127.0.0.1:10808）",
    },
    {
        "slug": "spoof-timezone",
        "id": "kcabmhnajflfolhelachlflngdbfhboe",
        "name": "Spoof Timezone",
        "desc": "时区跟随出口 IP 自动对齐，防时区和 IP 对不上",
    },
    {
        "slug": "webrtc-leak-prevent",
        # 用原作者本尊的商店页（Smith 2026-11-22 给的链接核对过，v2.0.0）；
        # bppamach… 那个是别人搬运改名的「WebRTC Leak Shield」，只作
        # 已装识别的兼容 ID，不再往那儿开商店页
        "id": "eiadekoaikejlgdbkbdfeijglgfdalml",
        "legacy_ids": ["bppamachkoflopbagkdoflbgfjflfnfl"],
        "name": "WebRTC Leak Prevent",
        "desc": "堵住 WebRTC 泄漏，防真实 IP 从 WebRTC 暴露",
    },
    {
        "slug": "adguard",
        "id": "bgnkhhnnamicmpeenaelnjfhikgbkllg",
        "name": "AdGuard 广告拦截器",
        "desc": "拦广告 + 跟踪保护，顺手清掉 URL 里的跟踪参数",
    },
    {
        "slug": "privacy-badger",
        "id": "pkehgijcmpdhfbdbbnkijodmdjhbjlgp",
        "name": "Privacy Badger（隐私獾）",
        "desc": "自动学习拦截跨站跟踪，和 AdGuard 互补",
    },
]

BY_SLUG = {e["slug"]: e for e in BUILTIN}


def store_state_map(acc: dict | None) -> dict[str, bool]:
    """这个账号的浏览器里，五个推荐插件各装没装（按商店 ID 查登记册）。"""
    if not acc:
        return {e["slug"]: False for e in BUILTIN}
    profile = store.profile_dir_for_browser(
        acc.get("id", ""), acc.get("browser") or "chrome"
    )
    have = store.profile_store_ext_ids(profile)
    return {
        e["slug"]: (e["id"] in have or any(x in have for x in e.get("legacy_ids", [])))
        for e in BUILTIN
    }
