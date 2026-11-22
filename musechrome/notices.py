"""公告：解析 Gitee 上的公告文件、后台拉取、公告页与公告图片。"""

from __future__ import annotations

import re
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import store
from .netutil import _update_error_detail, fetch_bytes
from .fxbuttons import FxButton
from .widgets import AnimButton
from .theme import C, _paint_bg, fix_scroll, themed


NOTICE_URL = "https://gitee.com/xiaoyaodev/musechrome/raw/master/announcements.md"


def parse_notices(text: str) -> list[dict]:
    """把公告文本切成一条条公告。

    约定格式：公告之间用单独一行 --- 隔开；每条里「标题：」「日期：」
    开头的行是标题和日期，其余行是正文；最新的公告放最上面。
    以 <!-- 开头的说明块跳过。解析尽量宽容：缺标题就拿正文第一行顶上。
    """
    import hashlib

    # 统一换行：公告文件经 Gitee 网页编辑器保存后是 CRLF（Windows 换行），
    # 不先归一化，分隔行 --- 后面挂着 \r，正则切不开，两条公告会黏成一条
    # （v1.7.0 真出过这个 bug，用户截图为证）。
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")

    # 先整段抹掉 <!-- --> 注释（文件头部的格式说明就写在注释里，
    # 它后面紧跟第一条公告，不能按块跳过，否则会连公告一起吃掉）
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    notices = []
    for block in re.split(r"(?m)^[ \t]*---[ \t]*$", text):
        block = block.strip()
        if not block or block.startswith("<!--"):
            continue
        title, date, body_lines, images = "", "", [], []
        for line in block.splitlines():
            s = line.strip()
            if s.startswith(("标题：", "标题:")) and not title:
                title = s[3:].strip()
            elif s.startswith(("日期：", "日期:")) and not date:
                date = s[3:].strip()
            else:
                url = _notice_image_url(s)
                if url:
                    images.append(url)
                else:
                    body_lines.append(line.rstrip())
        body = "\n".join(body_lines).strip()
        if not title and not body:
            continue
        if not title:
            lines = body.splitlines()
            title = lines[0][:30]
            body = "\n".join(lines[1:]).strip()
        notices.append({
            "title": title,
            "date": date,
            "body": body,
            "images": images,
            "id": hashlib.sha256(
                f"{title}\n{date}\n{body}".encode("utf-8")
            ).hexdigest()[:16],
        })
    return notices


_MD_IMG_RE = re.compile(r"^!\[[^\]]*\]\((https?://[^)\s]+)\)$")
_IMG_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp)(\?\S*)?$", re.I)


def _notice_image_url(s: str) -> str:
    """公告正文里单独一行的图片地址（三种写法都认），不是图片行就返回空字符串。

    写法：①「图片：https://…」 ② Markdown 的 ![](https://…) ③ 一行就是图片
    地址本身（带图片扩展名）。普通链接行不会被误吃。
    """
    m = _MD_IMG_RE.match(s)
    if m:
        return m.group(1)
    if s.startswith(("图片：", "图片:")):
        rest = s[3:].strip()
        if rest.startswith(("http://", "https://")) and " " not in rest:
            return rest
        return ""
    if re.fullmatch(r"https?://\S+", s) and _IMG_EXT_RE.search(s):
        return s
    return ""


class NoticeFetcher(QThread):
    """后台拉公告文本：走软件里配置的本地代理（关代理则直连），证书用打包的 CA 包。"""

    done = pyqtSignal(bool, str, str)  # 成功?, 公告原文, 失败原因

    def __init__(self, proxy_url: str | None, parent=None):
        super().__init__(parent)
        self.proxy_url = proxy_url

    def run(self):
        try:
            data, _final = fetch_bytes(
                NOTICE_URL, self.proxy_url, timeout=12,
                allow_direct=True, log_tag="公告拉取",
            )
            text = data.decode("utf-8", errors="replace")
            self.done.emit(True, text, "")
        except Exception as exc:
            self.done.emit(False, "", _update_error_detail(exc))
class NoticeImageFetcher(QThread):
    """后台把公告图片下载到本地缓存，下好一张报一张，页面随即补上。"""

    got = pyqtSignal(str)  # 图片地址（其本地缓存已就位）

    def __init__(self, urls: list[str], proxy_url: str | None, parent=None):
        super().__init__(parent)
        self.urls = urls
        self.proxy_url = proxy_url

    def run(self):
        for url in self.urls:
            path = store.notice_image_path(url)
            if path.exists() and path.stat().st_size > 0:
                continue
            try:
                data, _final = fetch_bytes(
                    url, self.proxy_url, timeout=15,
                    allow_direct=True, log_tag="公告图片",
                )
                if not data or len(data) > 8_000_000:  # 空图、超大图都不收
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                self.got.emit(url)
            except Exception:
                continue


class NoticePage(QWidget):
    """公告页：内容来自仓库里的公告文件，拉不到时显示上次缓存。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proxy_url: str | None = None
        self._notices: list[dict] = []
        self._img_fetch: NoticeImageFetcher | None = None
        title = QLabel("公告")
        themed(title, "font-size: 19px; font-weight: 600; color: @text@;")
        self.lbl_status = QLabel("")
        themed(self.lbl_status, "font-size: 12px; color: @dim@;")
        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.lbl_status)

        self._host = QWidget()
        _paint_bg(self._host)
        self._box = QVBoxLayout(self._host)
        self._box.setContentsMargins(2, 2, 2, 2)
        self._box.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._host)
        fix_scroll(scroll, self._host)

        self.btn_back = FxButton("返回账号列表")
        row = QHBoxLayout()
        row.addWidget(self.btn_back)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(scroll, 1)
        layout.addLayout(row)
        self.set_notices([], "")

    def set_proxy_url(self, url: str | None):
        self._proxy_url = url

    def set_notices(self, notices: list[dict], status: str):
        self._notices = notices
        self.lbl_status.setText(status)
        while self._box.count():
            item = self._box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)  # 只 deleteLater 时旧控件会残留在页面上（公告页真出过）
                w.deleteLater()
        if not notices:
            lbl = QLabel("暂无公告")
            themed(lbl, "font-size: 14px; color: @dim@;")
            self._box.addWidget(lbl)
        for n in notices:
            self._box.addWidget(self._make_card(n))
        if notices:
            end = QLabel("— 没有更多公告了 —")
            themed(end, "font-size: 12px; color: @dim@;")
            end.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._box.addWidget(end)
        self._box.addStretch(1)
        # 公告图片：本地还没有的，后台下载，下好一张就重排一次补上
        missing = []
        for n in notices:
            for url in n.get("images") or []:
                p = store.notice_image_path(url)
                if not (p.exists() and p.stat().st_size > 0):
                    missing.append(url)
        if missing:
            if self._img_fetch is not None and self._img_fetch.isRunning():
                self._img_fetch.got.disconnect(self._on_image_ready)
            self._img_fetch = NoticeImageFetcher(missing, self._proxy_url, self)
            self._img_fetch.got.connect(self._on_image_ready)
            self._img_fetch.start()

    def _on_image_ready(self, _url: str):
        self.set_notices(self._notices, self.lbl_status.text())

    @staticmethod
    def _make_card(n: dict) -> QFrame:
        card = QFrame()
        # 走 themed 登记：切换主题时跟着刷新，不然卡片底色停在旧主题
        # （Smith 实证：浅色下公告卡片还是黑的）
        themed(
            card,
            "QFrame { background: @surface@; border: 1px solid @border@; "
            "border-radius: 10px; }"
            "QLabel { border: none; background: transparent; }",
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(8)
        ct = QLabel(n["title"])
        themed(ct, "font-size: 16px; font-weight: bold; color: @text@;")
        ct.setWordWrap(True)
        cl.addWidget(ct)
        if n["date"]:
            cd = QLabel(n["date"])
            themed(cd, "font-size: 12px; color: @dim@;")
            cl.addWidget(cd)
        if n["body"]:
            cb = QLabel(n["body"])
            cb.setWordWrap(True)
            themed(cb, "color: @body@;")
            cl.addWidget(cb)
        for url in n.get("images") or []:
            path = store.notice_image_path(url)
            lbl = QLabel()
            pix = QPixmap(str(path)) if path.exists() and path.stat().st_size > 0 else QPixmap()
            if not pix.isNull():
                if pix.width() > 560:
                    pix = pix.scaledToWidth(560, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(pix)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                lbl.setText("图片加载中…")
                themed(lbl, "font-size: 12px; color: @dim@;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(lbl)
        return card
