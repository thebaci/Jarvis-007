"""Plugin bundled: thời gian & ngày theo Việt Nam. Thuần stdlib, readonly.

Ví dụ MẪU cho tool plugin đơn giản nhất: register 2 tool đọc, không hook, không state.
Handler dạng handler(args: dict, ctx) -> str. ctx là PluginContext (slug, vault_root, data_dir, ...).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

# Múi giờ và tên thứ ĐỌC TỪ CẤU HÌNH, không còn ghim cứng Việt Nam. Người dùng đổi múi giờ ở
# trang Cài đặt thì tool này trả đúng giờ của họ ngay, không phải khởi động lại.
#
# SLUG giữ nguyên là `datetime-vn` có chủ ý, dù plugin nay không còn chỉ phục vụ VN: đổi slug
# là bắt mọi brain đang chạy phải di trú, đổi lấy đúng một cái tên đẹp hơn. Tên tool
# `javis_now` / `javis_date_add` cũng giữ - chúng đã nằm trong prompt và trong thói quen dùng.
#
# Rơi về UTC+7 khi chưa nạp được cấu hình (plugin có thể chạy ngoài tiến trình server), vì đó
# vẫn là mặc định của Javis và VN không có giờ mùa hè nên nó là hằng số đáng tin.
_TZ_DU_PHONG = timezone(timedelta(hours=7))
_WD_DU_PHONG = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _tz():
    try:
        import localefmt
        return localefmt.tz()
    except Exception:
        return _TZ_DU_PHONG


def _ten_tz():
    try:
        import localefmt
        return localefmt.ten_tz()
    except Exception:
        return "Asia/Ho_Chi_Minh (UTC+7)"


def _wd(n):
    """Tên thứ theo NGÔN NGỮ GIAO DIỆN đang chọn."""
    try:
        import config as cfgmod
        import lang_registry
        ma = (cfgmod.read_settings().get("locale") or {}).get("ui_lang") or ""
        tuan = lang_registry.get(ma).weekdays
        if tuan and len(tuan) == 7:
            return tuan[n]
    except Exception:
        pass
    return _WD_DU_PHONG[n]


def _now(args, ctx):
    n = datetime.now(_tz())
    return json.dumps({
        "iso": n.isoformat(timespec="seconds"),
        "date": n.strftime("%Y-%m-%d"),
        "time": n.strftime("%H:%M:%S"),
        "weekday": _wd(n.weekday()),
        "tz": _ten_tz(),
    }, ensure_ascii=False)


def _date_add(args, ctx):
    args = args or {}
    try:
        days = int(args.get("days", 0))
    except (TypeError, ValueError):
        return "ERROR: 'days' must be an integer (negative = go back)."
    base_s = args.get("from")
    if base_s:
        try:
            base = datetime.strptime(str(base_s), "%Y-%m-%d").replace(tzinfo=_tz())
        except ValueError:
            return "ERROR: 'from' must be in YYYY-MM-DD format."
    else:
        base = datetime.now(_tz())
    d = base + timedelta(days=days)
    return json.dumps({"date": d.strftime("%Y-%m-%d"), "weekday": _wd(d.weekday())}, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(
        name="javis_now",
        description=("Current date and time in the configured timezone: iso, date, time, day of the week. "
                     "Use it when you need to know 'today', 'what time is it now', to set a reminder, or to timestamp a report."),
        handler=_now, min_mode="readonly",
        schema={"type": "object", "properties": {}},
    )
    ctx.register_tool(
        name="javis_date_add",
        description=("Work out the date N days from today (or from the date 'from'). Parameters: days (integer, "
                     "negative = before), from (YYYY-MM-DD, optional). Use it for 'tomorrow', 'in 3 days', 'last week'."),
        handler=_date_add, min_mode="readonly",
        schema={"type": "object",
                "properties": {"days": {"type": "integer", "description": "Number of days to add (negative = go back)"},
                               "from": {"type": "string", "description": "Start date YYYY-MM-DD (empty = today)"}},
                "required": ["days"]},
    )
