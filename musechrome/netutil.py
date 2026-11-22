"""网络小工具：代理探活、带代理与证书的 opener、错误翻译。"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request

from . import store


def probe_http_proxy(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    """用裸 socket 探一个 HTTP 代理活没活：让它去取 gstatic 的 204 测试页。"""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(
                b"GET http://www.gstatic.com/generate_204 HTTP/1.1\r\n"
                b"Host: www.gstatic.com\r\nConnection: close\r\n\r\n"
            )
            line = s.recv(200).decode("latin-1", errors="replace").splitlines()[0]
        if " 204" in line or " 200" in line:
            return True, line.strip()
        return False, f"代理有回应但不对：{line.strip()[:60]}"
    except Exception as exc:
        return False, str(exc)[:60]


def probe_socks5_proxy(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    """探 SOCKS5 代理：免密握手后让它连 gstatic:80 并取 204 测试页。"""
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(b"\x05\x01\x00")
            if s.recv(2) != b"\x05\x00":
                return False, "SOCKS5 握手被拒"
            target = b"www.gstatic.com"
            s.sendall(b"\x05\x01\x00\x03" + bytes([len(target)]) + target + (80).to_bytes(2, "big"))
            reply = s.recv(10)
            if len(reply) < 2 or reply[1] != 0:
                return False, "SOCKS5 连接目标失败"
            s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n")
            line = s.recv(200).decode("latin-1", errors="replace").splitlines()[0]
        if " 204" in line or " 200" in line:
            return True, line.strip()
        return False, f"代理有回应但不对：{line.strip()[:60]}"
    except Exception as exc:
        return False, str(exc)[:60]


def probe_proxy(ptype: str, host: str, port: int, timeout: float = 6.0) -> tuple[bool, str]:
    if ptype == "socks5":
        return probe_socks5_proxy(host, port, timeout=timeout)
    return probe_http_proxy(host, port, timeout=timeout)


def _timed_probe(ptype: str, host: str, port: int, timeout: float = 8) -> tuple[bool, str, int]:
    """探活并计时（毫秒）：自检页拿这个数当代理延迟展示。"""
    t0 = time.monotonic()
    ok, detail = probe_proxy(ptype, host, port, timeout=timeout)
    return ok, detail, int((time.monotonic() - t0) * 1000)
def _update_error_detail(exc: Exception) -> str:
    """把检查更新的异常翻成一句人话，方便定位（证书/代理/超时/限流）。"""
    if isinstance(exc, urllib.error.HTTPError):
        return f"GitHub 返回 {exc.code}"
    text = str(exc)
    low = text.lower()
    if "certificate" in low or "ssl" in low:
        return "证书校验失败"
    if "refused" in low or "10061" in text:
        return "连不上代理（先确认代理工具开着）"
    if "timed out" in low or "timeout" in low:
        return "连接超时"
    if "403" in text:
        return "GitHub 返回 403（可能被限流）"
    return text[:80] if text else "网络异常"


def _combined_context() -> ssl.SSLContext | None:
    """系统根证书库 + 随软件打包的 Mozilla 根证书，两边都装上。

    v1.9.0 实测：只用打包的 Mozilla 包时，Gitee 的证书链在个别机器上
    校验不过（它的根只在 Windows 系统库里）；只用系统库又怕有的机器
    系统库不全。合并之后两边都覆盖。
    """
    ctx = None
    try:
        ctx = ssl.create_default_context()  # Windows 上自动加载系统根证书库
    except Exception:
        ctx = None
    ca = store.ca_bundle_path()
    if ca is not None:
        try:
            if ctx is None:
                ctx = ssl.create_default_context(cafile=str(ca))
            else:
                ctx.load_verify_locations(cafile=str(ca))
        except Exception:
            pass
    return ctx


def _bundled_context() -> ssl.SSLContext | None:
    ca = store.ca_bundle_path()
    if ca is None:
        return None
    try:
        return ssl.create_default_context(cafile=str(ca))
    except Exception:
        return None


def _make_opener(proxy_url: str | None, ctx: ssl.SSLContext | None = None):
    handlers = []
    if proxy_url:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    if ctx is None:
        ctx = _combined_context()
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def fetch_bytes(
    url: str,
    proxy_url: str | None = None,
    timeout: float = 15,
    allow_direct: bool = False,
    log_tag: str = "下载",
) -> tuple[bytes, str]:
    """拉一个 URL 的内容，多条路轮着试，全程写日志，返回 (内容, 最终地址)。

    顺序：合并证书+代理 → 打包证书+代理 →（允许时）合并证书+直连
    → 打包证书+直连。代理这条路断了（节点掐 TLS 等）会自动切直连。
    每条路失败的完整原因都记进日志，用户反馈时一看便知卡在哪。
    """
    from .applog import get_log

    attempts: list[tuple[str, str | None, ssl.SSLContext | None]] = [
        ("合并证书+代理" if proxy_url else "合并证书+直连", proxy_url, _combined_context()),
        ("打包证书+代理" if proxy_url else "打包证书+直连", proxy_url, _bundled_context()),
    ]
    if allow_direct and proxy_url:
        attempts.append(("合并证书+直连", None, _combined_context()))
        attempts.append(("打包证书+直连", None, _bundled_context()))
    last_exc: Exception | None = None
    for label, px, ctx in attempts:
        try:
            opener = _make_opener(px, ctx)
            req = urllib.request.Request(url, headers={"User-Agent": "MuseChrome"})
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                final = resp.geturl()
            get_log().info(f"{log_tag}成功（{label}）：{url} → {len(data)} 字节")
            return data, final
        except Exception as exc:
            last_exc = exc
            get_log().warn(f"{log_tag}失败（{label}）：{url} → {exc!r}")
    raise last_exc if last_exc is not None else RuntimeError("没有可用的下载路径")
