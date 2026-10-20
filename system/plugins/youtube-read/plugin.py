# -*- coding: utf-8 -*-
"""Plugin bundled: đọc nội dung video YouTube cho MỌI engine.

Đăng ký tool `javis_youtube_read`, gọi youtube_read.read() (lấy phụ đề qua InnerTube, dự phòng
cào trang watch). Vì sao là plugin bundled chứ không phải để engine tự xoay:
  - Sáu engine API không có WebFetch, tức KHÔNG mở được URL nào. Không có tool này thì chúng
    chỉ còn cách báo "không đọc được" - đúng lời phàn nàn của người dùng.
  - Ba engine CLI có WebFetch nhưng tải trang YouTube về chỉ được khung React rỗng, không có
    một chữ lời thoại nào. Nên WebFetch cũng KHÔNG phải lời giải, chỉ là thất bại chậm hơn.

min_mode=readonly: thuần đọc, không ghi file, không tiêu tiền, không đụng tài khoản. Nhờ vậy
loop/agent ở chế độ chỉ-đọc vẫn tóm tắt được video.

KHÔNG dùng cookie đăng nhập YouTube, có chủ ý: đổi lại là chịu thua video thật sự riêng tư,
nhưng Javis không phải giữ phiên đăng nhập của người dùng trên máy chủ - thứ mà lộ ra là
mất luôn tài khoản. Ca hay gặp trên VPS ("nghi máy chủ là robot") thì đã có sáu kiểu trình
phát và yt-dlp lo, không cần tới cookie.
"""
from __future__ import annotations

import youtube_read


def register(ctx):
    async def _read(args, cctx):
        args = args or {}
        url = str(args.get("url") or args.get("link") or "").strip()
        if not url:
            return "ERROR: missing 'url' (the YouTube video link to read)."
        lang = str(args.get("lang") or "").strip() or None
        try:
            start_min = float(args.get("start_min") or 0)
        except Exception:
            start_min = 0.0
        try:
            max_chars = int(args.get("max_chars") or youtube_read.MAX_CHARS_DEFAULT)
        except Exception:
            max_chars = youtube_read.MAX_CHARS_DEFAULT
        moc = args.get("timestamps")
        res = await youtube_read.read(
            url, lang=lang, timestamps=(True if moc is None else bool(moc)),
            start_min=start_min, max_chars=max_chars)
        return youtube_read.render(res)

    ctx.register_tool(
        name="javis_youtube_read",
        description=(
            "Read the SPOKEN TEXT (captions) of a YouTube video from its link, to summarise it or pull out key points. "
            "CALL THIS TOOL whenever the user sends a YouTube link (youtube.com, youtu.be, shorts) "
            "and wants a summary of, or has questions about, the video - do NOT use WebFetch for YouTube links, "
            "that page does not contain the spoken text. Parameters: url (required), lang (the caption language code "
            "to prefer, e.g. 'vi'/'en'), start_min (continue reading from which minute, for long videos that were "
            "truncated), timestamps (default true), max_chars. If the video has no captions the tool "
            "says so clearly - in that case do NOT invent content. The tool switches between several player types and then to "
            "yt-dlp when YouTube blocks the server, so only a truly broken link returns an error."),
        handler=_read, min_mode="readonly", emoji="🎬",
        schema={"type": "object", "properties": {
            "url": {"type": "string",
                    "description": "YouTube video link (watch, youtu.be, shorts, live, embed) or the 11-character video id"},
            "lang": {"type": "string",
                     "description": "Preferred caption language code, e.g. 'vi' or 'en'. If left empty, follows the interface language, then English."},
            "start_min": {"type": "number",
                          "description": "Read from which minute. Use when the previous read was truncated because the video is too long."},
            "timestamps": {"type": "boolean",
                           "description": "Whether to attach [min:sec] timestamps to the spoken text. Default true."},
            "max_chars": {"type": "integer",
                          "description": "Cap on the number of spoken-text characters returned (default 40000, max 120000)."}},
            "required": ["url"]},
    )
