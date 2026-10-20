"""Plugin bundled: tool javis_schedule - tạo/liệt kê/huỷ việc định kỳ + nhắc hẹn từ chat.

Trước tool này, chat muốn tạo việc định kỳ phải TỰ GÕ YAML frontmatter vào Javis/loops/<slug>.md,
hoặc shell ra curl POST /reminders (reminders.py:17 mô tả đúng đường đó). Tool này gói cả hai kho
lại sau MỘT tool duy nhất, tự route đúng chỗ theo bản chất lịch:

    - Lịch LẶP + BỀN ("120m", "mỗi 2 tiếng", "2h", "90 phút") -> ghi thẳng file
      <vault_root>/Javis/loops/<slug>.md. Loop VỐN LÀ 1 file .md (self_improve.py) - scheduler
      nền tự đọc thư mục, không cần gọi API nào. KHÔNG dùng POST /loops vì route đó cần đăng
      nhập, plugin (chạy in-process từ mọi engine, kể cả localhost không có session) gọi không
      tới (main.py không liệt /loops vào _AUTH_LOCAL_EXACT).
    - Lịch giờ CỐ ĐỊNH lặp lại (cron 5 trường "0 7 * * *", macro "@daily"...) hoặc MỘT LẦN
      ("30 phút nữa", "8h30", ngày giờ đầy đủ) -> gọi HTTP POST /reminders trên 127.0.0.1 (đường
      này CỐ Ý miễn đăng nhập cho localhost - main.py:70 _AUTH_LOCAL_EXACT).

An toàn (BẮT BUỘC, không nhận tham số để đổi):
    - Loop tạo qua chat LUÔN enabled: false (người dùng bật ở trang Việc) và mặc định mode: full
      (chủ repo bỏ luật "không giao tự động tiền/đơn/đăng bài/nhắn khách" ngày 2026-09-10).
      Muốn nhẹ hơn thì truyền muc_quyen=auto|suggest, áp cho cả loop lẫn nhắc hẹn.
    - ctx.vault_root RỖNG -> báo lỗi rõ, TUYỆT ĐỐI không âm thầm rơi về Brain Default (đây chính
      là bug Task 1 vừa vá ở image_gen/_plugins_server - đừng tái tạo).
    - Trùng slug (đã có việc lặp cùng tên) -> báo lỗi, KHÔNG ghi đè: self_improve.py lấy định
      danh loop theo TÊN FILE, đẻ bản ascii song song thì bản gốc vẫn chạy -> thành 2 loop.
    - op=list PHẢI nhìn CẢ HAI kho (loops + reminders) - nhìn thiếu 1 kho thì model sẽ báo "không
      có việc nào" trong khi việc nằm ở kho kia.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
import json
import yaml

# Múi giờ đọc từ cấu hình; rơi về UTC+7 khi plugin chạy ngoài tiến trình server.
def _tz():
    try:
        import localefmt
        return localefmt.tz()
    except Exception:
        return timezone(timedelta(hours=7))

# Frontmatter loop: ---\n<yaml>\n---\n<body> (khớp _FM_RE của self_improve.py)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

# Đơn vị chu kỳ/thời lượng chấp nhận, đã bỏ dấu tiếng Việt -> hệ số quy đổi ra PHÚT. Thứ tự
# trong _UNIT_ALT CÓ Ý NGHĨA: chuỗi dài/cụ thể hơn phải đứng TRƯỚC chuỗi ngắn là tiền tố của nó
# (vd "phut" trước "p", "hour" trước "h", "minute"/"min" trước "m") - regex alternation của
# Python khớp theo THỨ TỰ xuất hiện, không phải khớp dài nhất. "ngay"/"tuan"/"thang" không phải
# tiền tố của token nào khác nên chèn ở đâu cũng an toàn.
_UNIT_MINUTES = {
    "phut": 1, "minute": 1, "min": 1, "p": 1, "m": 1,
    "tieng": 60, "hour": 60, "gio": 60, "h": 60,
    "ngay": 1440, "tuan": 10080, "thang": 43200,
}
_UNIT_ALT = "phut|tieng|gio|hour|ngay|tuan|thang|minute|min|p|h|m"
# Đơn vị đứng MỘT MÌNH không kèm số ("mỗi ngày", "mỗi tuần", "mỗi tháng") -> ngầm định số lượng 1.
_BARE_UNIT_RE = re.compile(rf"\b({_UNIT_ALT})\b")

_CRON_TOKEN_RE = re.compile(r"^[\dA-Za-z*/,\-]+$")
# Chu kỳ THUẦN dạng "<số><đơn vị>" (không khoảng trắng, không chữ thừa) - vd "120m", "2h", "90phut".
_INTERVAL_FULL_RE = re.compile(rf"^\d+(?:[.,]\d+)?(?:{_UNIT_ALT})$")
# Tìm số + đơn vị BẤT KỲ ĐÂU trong chuỗi (cho phép có tiền tố "mỗi", khoảng trắng giữa số/đơn vị).
_INTERVAL_SEARCH_RE = re.compile(rf"(\d+(?:[.,]\d+)?)\s*({_UNIT_ALT})")
# Mốc TƯƠNG ĐỐI kiểu "<số><đơn vị>[nữa|tới|sau]" (hậu tố tuỳ chọn) - dùng khi tạo nhắc một lần.
_RELATIVE_DELAY_RE = re.compile(rf"^(\d+(?:[.,]\d+)?)({_UNIT_ALT})(?:nua|toi|sau)?$")

# Mốc GIỜ CỐ ĐỊNH kiểu "7h", "7h30", "07:00" - dùng để dò lịch "mỗi sáng 7h" cần LẶP HẰNG NGÀY
# ở đúng 1 giờ trong ngày (cron), khác hẳn "mỗi 7 tiếng" (duration thuần, lặp theo khoảng cách).
_CLOCK_RE = re.compile(r"\b(\d{1,2})[h:](\d{2})?\b")
_DAYPART_WORDS = ("sang", "trua", "chieu", "toi")


def _port() -> int:
    try:
        return int(os.getenv("JAVIS_PORT", "7777"))
    except (TypeError, ValueError):
        return 7777


def _today() -> str:
    return datetime.now(_tz()).strftime("%Y-%m-%d")


def _strip_diacritics(s: str) -> str:
    """Bỏ dấu tiếng Việt + hạ chữ thường (khớp cách _ascii_slug của self_improve.py làm)."""
    s = (s or "").lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _slugify_vn(name: str) -> str:
    """Tên tiếng Việt bất kỳ -> slug ascii an toàn cho tên file. Rỗng -> 'viec'."""
    t = _strip_diacritics(name)
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = t.strip("-")
    return t or "viec"


def _is_cron(schedule: str) -> bool:
    """Cron 5 trường (phút giờ ngày tháng thứ) hoặc macro '@daily'... (cron_util.py)."""
    s = (schedule or "").strip()
    if not s:
        return False
    if s.startswith("@"):
        return True
    parts = s.split()
    return len(parts) == 5 and all(_CRON_TOKEN_RE.match(p) for p in parts)


def _daily_cron(schedule: str) -> Optional[str]:
    """Dò lịch dạng MỐC GIỜ CỐ ĐỊNH lặp HẰNG NGÀY ('mỗi sáng 7h', 'mỗi ngày lúc 8h', '7h sáng
    hằng ngày') -> cron 5 trường 'M H * * *'. Trả None nếu KHÔNG phải dạng này (vd 'mỗi 7 tiếng'
    hay 'mỗi 2 tiếng' - duration thuần lặp theo KHOẢNG CÁCH, không có tín hiệu mốc-giờ-trong-ngày).

    Phân biệt bằng 2 tín hiệu PHẢI CÓ CẢ HAI: (a) chuỗi có ý LẶP HẰNG NGÀY - từ "mỗi" + một
    buổi trong ngày (sáng/trưa/chiều/tối) hoặc từ "ngày", hoặc cụm "hằng ngày"; VÀ (b) có một
    mốc giờ đồng hồ (7h, 7h30, 07:00) trong chuỗi. Thiếu 1 trong 2 -> None, để chỗ gọi tự rơi về
    nhánh cũ (duration/relative-delay) - KHÔNG đoán bừa."""
    norm = _strip_diacritics(schedule or "")
    has_moi = bool(re.search(r"\bmoi\b", norm))
    has_hang_ngay = "hang ngay" in norm
    if not (has_moi or has_hang_ngay):
        return None
    has_daypart = any(re.search(rf"\b{w}\b", norm) for w in _DAYPART_WORDS)
    has_ngay = bool(re.search(r"\bngay\b", norm))
    if not (has_daypart or has_ngay):
        return None   # "mỗi 7h"/"mỗi 2 tiếng" - không có tín hiệu HẰNG NGÀY, để nguyên là duration
    m = _CLOCK_RE.search(norm)
    if not m:
        return None   # có ý lặp hằng ngày nhưng KHÔNG có mốc giờ cụ thể ("mỗi sáng") -> chưa đủ để làm cron
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    if re.search(r"\b(chieu|toi)\b", norm) and hour < 12:
        hour += 12   # "7h tối"/"7h chiều" nói theo giờ 12h -> quy về giờ 24h
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{minute} {hour} * * *"


def _route_kind(schedule: str, notify_only: bool = False) -> str:
    """Phân loại 1 chuỗi lịch: 'loop' (lặp + bền, ghi file) hay 'reminder' (kho nhắc hẹn có sẵn).

    notify_only=True luôn ép về reminder (chỉ muốn nhắc 1 lần, dù chuỗi trông giống chu kỳ)."""
    if notify_only:
        return "reminder"
    s = (schedule or "").strip()
    if _is_cron(s):
        return "reminder"          # cron đã có sẵn kho reminders lo, không cần ghi loop
    if _daily_cron(s):
        return "reminder"          # mốc giờ cố định lặp hằng ngày ("mỗi sáng 7h") -> cron ở kho reminders
    norm = _strip_diacritics(s)
    if re.search(r"\bmoi\b", norm):
        return "loop"               # "mỗi 2 tiếng" - từ "mỗi" tự thân đã là dấu hiệu LẶP ĐỊNH KỲ
    compact = norm.replace(" ", "")
    if _INTERVAL_FULL_RE.fullmatch(compact):
        return "loop"               # chu kỳ thuần "120m"/"2h"/"90phut" - không lẫn chữ thừa
    return "reminder"                # còn lại: mốc một lần ("30 phút nữa", "8h30", ISO...)


def _interval_min(schedule: str) -> Optional[int]:
    """Rút số phút từ 1 chuỗi chu kỳ ('120m'->120, '2 tiếng'/'2h'->120, 'mỗi ngày'->1440,
    'mỗi tuần'->10080, 'mỗi tháng'->43200 - đơn vị đứng một mình không kèm số thì ngầm định
    số lượng 1). Tối thiểu 5 phút (khớp trần cứng self_improve.py:257).

    Trả None khi KHÔNG rút được đơn vị/số nào rõ ràng (lịch mơ hồ, vd 'mỗi sáng' không kèm giờ
    hay đơn vị). Nơi gọi BẮT BUỘC coi None là lỗi cần hỏi lại model - TUYỆT ĐỐI không tự rơi về
    một số phút mặc định: chạy nhầm mỗi 5 phút là đốt tiền + spam Telegram thật (fail loudly)."""
    norm = _strip_diacritics(schedule)
    m = _INTERVAL_SEARCH_RE.search(norm)
    if m:
        try:
            num = float(m.group(1).replace(",", "."))
        except ValueError:
            return None
        factor = _UNIT_MINUTES.get(m.group(2), 1)
        return max(5, int(round(num * factor)))
    bare = _BARE_UNIT_RE.search(norm)
    if bare:
        return max(5, _UNIT_MINUTES.get(bare.group(1), 1))
    return None


def _yaml_scalar(s: str) -> str:
    """Trích dẫn 1 giá trị chuỗi thành scalar YAML AN TOÀN TUYỆT ĐỐI, dùng cho MỌI giá trị chuỗi
    do người/model nhập (tên việc, owner_chat...). KHÔNG liệt kê ký tự chỉ-thị cần escape (đó là
    trò đuổi bắt không bao giờ hết - bỏ sót 1 ký tự như '-' đầu chuỗi, '@', '*', '!', '%', '?',
    '|', '&', '>' là ghi ra frontmatter vỡ, yaml.safe_load ném ScannerError/ConstructorError, và
    self_improve.list_loops() nuốt lỗi bằng try/except nên loop CHẾT ÂM THẦM, biến mất khỏi tab
    Việc mà tool vẫn báo "đã tạo thành công").

    Thay vào đó LUÔN trả về chuỗi nháy kép kiểu JSON: YAML 1.2 là superset của JSON nên chuỗi
    nháy kép JSON LUÔN là scalar YAML hợp lệ trong mọi trường hợp, và json.dumps tự lo escape
    dấu ngoặc kép, dấu gạch chéo ngược, xuống dòng - không cần tự viết regex escape."""
    return json.dumps(str(s or ""), ensure_ascii=False)


def _loops_dir(vault_root: str) -> Path:
    return Path(vault_root) / "Javis" / "loops"


_LOOP_MODES = ("suggest", "auto", "full")
import os as _os
_LOOP_MODE_MAC_DINH = "full" if _os.getenv("JAVIS_UPSTREAM_DEFAULTS", "").strip().lower() in ("1", "true", "yes", "on") else "auto"  # Jarvis 007: drafts-only by default


def _create_loop_file(vault_root: str, name: str, prompt: str, schedule: str,
                      owner_chat: str = "", brain_name: str = "", mode: str = "") -> str:
    """Ghi 1 loop mới vào <vault_root>/Javis/loops/<slug>.md. enabled luôn false (người dùng bật
    ở trang Việc); mode mặc định full, hạ xuống auto/suggest khi model truyền. Trùng slug (việc đã có) -> báo lỗi rõ, KHÔNG
    ghi đè - self_improve.py lấy định danh loop theo TÊN FILE nên đẻ bản ascii song song sẽ để
    bản gốc vẫn chạy, thành 2 loop làm cùng 1 việc."""
    if not vault_root:
        return "ERROR: cannot determine the active brain"
    name = (name or "").strip() or "Việc mới"
    prompt = (prompt or "").strip()
    if not prompt:
        return "ERROR: missing 'prompt' - each loop run needs to know what to do (write it self-contained, not dependent on the chat)"
    slug = _slugify_vn(name)
    d = _loops_dir(vault_root)
    fp = d / f"{slug}.md"
    if fp.exists():
        return (f"ERROR: a task named '{name}' already exists (Javis/loops/{slug}.md) - "
                 f"edit it instead of creating a copy (e.g. change that file's schedule/content)")
    mode = str(mode or "").strip().lower() or _LOOP_MODE_MAC_DINH
    if mode not in _LOOP_MODES:
        mode = _LOOP_MODE_MAC_DINH
    interval = _interval_min(schedule)
    if interval is None:
        return (f"ERROR: unclear interval '{schedule}' - state a number + unit (e.g. '120m', '2 hours', "
                 f"'every day', 'every week', 'every month'), or for a fixed time of day use a 5-field cron "
                 f"(e.g. '0 7 * * *' = 7am every day). NEVER guess 5 minutes.")
    frontmatter = (
        "---\n"
        "type: loop\n"
        f"name: {_yaml_scalar(name)}\n"
        f"slug: {slug}\n"
        "enabled: false\n"
        f"mode: {mode}\n"
        # goal: custom - BẮT BUỘC, KHÔNG được để self_improve.py mặc định 'business' (đọc
        # self_improve.py:250,546). goal='business' bỏ qua HOÀN TOÀN loop["body"] (chỉ đọc số
        # liệu MCP), nên nếu thiếu dòng này, prompt user vừa gõ (thân file dưới đây) không bao
        # giờ được loop đọc tới - loop tạo ra "thành công" nhưng KHÔNG làm đúng việc user yêu cầu.
        "goal: custom\n"
        f"interval_min: {interval}\n"
        f"owner_chat: {_yaml_scalar((owner_chat or '').strip())}\n"
        f"updated: {_today()}\n"
        "---\n"
        "\n"
        f"{prompt}\n"
    )
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(".md.tmp")
        tmp.write_text(frontmatter, encoding="utf-8")
        tmp.replace(fp)
    except Exception as e:
        return f"ERROR: failed to write the loop file: {type(e).__name__}: {e}"
    where = f" in brain {brain_name}" if brain_name else ""
    ten_mode = {"full": "full access, acts on the outside world on its own", "auto": "writes draft files only",
                "suggest": "read-only, then suggests"}[mode]
    return (f"Created recurring task '{name}'{where} (Javis/loops/{slug}.md), runs every {interval} minutes, "
             f"permission level {mode} ({ten_mode}). It is currently OFF (enabled: false): the user must open the Work "
             f"tab in the dashboard and click Enable before it runs.")


def _list_loops(vault_root: str) -> list:
    """Đọc rút gọn mọi loop trong <vault_root>/Javis/loops. Không import self_improve.py (tránh
    kéo theo main.py) - tự đọc frontmatter tối giản, đủ để liệt kê cho model đọc lại."""
    out = []
    if not vault_root:
        return out
    d = _loops_dir(vault_root)
    if not d.is_dir():
        return out
    for fp in sorted(d.glob("*.md")):
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        m = _FM_RE.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            fm = {}
        if not isinstance(fm, dict):
            fm = {}
        out.append({
            "id": fp.stem,
            "name": str(fm.get("name") or fp.stem),
            "enabled": bool(fm.get("enabled", False)),
            "mode": str(fm.get("mode", _LOOP_MODE_MAC_DINH) or _LOOP_MODE_MAC_DINH),
            "interval_min": fm.get("interval_min", 0),
        })
    return out


def _cancel_loop_file(vault_root: str, slug: str) -> str:
    d = _loops_dir(vault_root)
    fp = d / f"{slug}.md"
    try:
        if fp.resolve().parent != d.resolve():
            return "ERROR: invalid id"
    except Exception:
        return "ERROR: invalid id"
    if not fp.is_file():
        return f"ERROR: recurring task '{slug}' not found in Javis/loops"
    try:
        fp.unlink()
    except Exception as e:
        return f"ERROR: failed to delete the file: {type(e).__name__}: {e}"
    return f"Deleted recurring task '{slug}'."


def _reminder_time_payload(schedule: str) -> dict:
    """Suy tham số thời gian cho POST /reminders từ 1 chuỗi lịch. Cron -> {'cron'}. Mốc giờ cố
    định lặp hằng ngày ('mỗi sáng 7h') -> {'cron'} suy từ _daily_cron. Mốc tương đối kiểu
    '<n> <đơn vị> [nữa|tới|sau]' -> {'delay_min'}. Còn lại (HH:MM, '8h30', ngày giờ đầy đủ) ->
    {'at': schedule nguyên văn}, để reminders.resolve_due tự hiểu (cùng định dạng nó vốn chấp
    nhận khi engine gọi curl trực tiếp)."""
    s = (schedule or "").strip()
    if _is_cron(s):
        return {"cron": s}
    cron = _daily_cron(s)
    if cron:
        return {"cron": cron}
    norm = _strip_diacritics(s).replace(" ", "")
    m = _RELATIVE_DELAY_RE.match(norm)
    if m:
        try:
            num = float(m.group(1).replace(",", "."))
        except ValueError:
            num = None
        if num is not None:
            factor = _UNIT_MINUTES.get(m.group(2), 1)
            return {"delay_min": num * factor}
    return {"at": s}


# C1 (bảo mật/ổn định server): 3 hàm gọi HTTP dưới đây BẮT BUỘC là async + httpx.AsyncClient.
# Handler plugin chạy TRÊN event loop chính của uvicorn (plugins_host._make_call gọi
# `res = handler(args, ctx)` rồi mới await - KHÔNG bọc asyncio.to_thread). httpx.post ĐỒNG BỘ ở
# đây gọi vào CHÍNH server đang chạy nó (127.0.0.1:_port()) -> khoá luôn event loop đang cần
# rảnh để tự trả lời request đó -> deadlock/ReadTimeout, treo TOÀN BỘ server (mọi user, mọi tool)
# cho tới khi hết timeout. Xem mẫu async đúng: system/plugins/meta-ads-graph/plugin.py `_get()`,
# system/plugins/image-chatgpt/plugin.py `_gen()`. test_javis_schedule.py có lưới hồi quy
# (inspect.iscoroutinefunction) chặn ai đó quay lại lối sync.
async def _post_reminder(payload: dict, brain_name: str = "") -> str:
    """Tạo 1 nhắc hẹn/job qua HTTP POST /reminders trên localhost (miễn đăng nhập -
    main.py:70 _AUTH_LOCAL_EXACT, đúng đường agent vốn gọi bằng curl - reminders.py:17)."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"http://127.0.0.1:{_port()}/reminders", json=payload)
        data = r.json()
    except Exception as e:
        return f"ERROR: reminder store call failed: {type(e).__name__}: {e}"
    if not data.get("ok"):
        if data.get("can_force"):
            # THIẾU ĐIỀU KIỆN, không phải lỗi cú pháp. Model TUYỆT ĐỐI không được tự vượt rào:
            # phải nói thiếu gì rồi để user quyết. Đây đúng cái khách phàn nàn - Javis dựng cron
            # "báo qua Telegram" trong khi Telegram còn chưa đấu, rồi im lặng không nói gì.
            return (f"ERROR: {data.get('error')}\n"
                    "→ TELL THE USER exactly what is missing above and ASK: connect Telegram first, "
                    "or create it anyway even though nobody will receive the report? If the user agrees to create it, call the tool again "
                    "with allow_no_channel=true. Do NOT decide for them.")
        return f"ERROR: {data.get('error') or 'failed to create the reminder'}"
    where = f" (brain {brain_name})" if brain_name else ""
    if data.get("cron"):
        lich = data.get("cron_human") or data["cron"]
        ra = (f"Set a recurring schedule {lich} (cron {data['cron']}){where} (id {data.get('id')}), "
              f"next run {data.get('due_human') or '?'}.")
        ra += _next_runs_line(data.get("next_runs"))
    else:
        ra = f"Set a reminder for {data.get('due_human') or '?'}{where} (id {data.get('id')})."
    mq = str(data.get("muc_quyen") or "").strip().lower()
    if data.get("mode") == "task" and mq:
        ten = {"full": "full access, acts on the outside world on its own", "auto": "writes draft files only",
               "suggest": "read-only, then reports back"}.get(mq, mq)
        ra += f" Permission level {mq} ({ten})."
    if data.get("remember_last"):
        ra += " Each run will receive the previous run's result."
    if data.get("speak"):
        ra += " The result will come with a voice message read aloud."
    if data.get("call"):
        ra += (" When the time comes Jarvis 007 will CALL IN on the page where Jarvis 007 is open: click Listen to join the call and Jarvis 007 reads"
               " the result aloud; if Jarvis 007 is not open the result still arrives as a normal message.")
    return ra


def _next_runs_line(runs) -> str:
    """Three upcoming dates, so the reply confirms the schedule in dates rather than cron syntax."""
    days = [str(r.get("human") or "") for r in (runs or []) if isinstance(r, dict) and r.get("human")]
    return (" Next three runs: " + "; ".join(days) + ". Read these dates back to the user to confirm.") if days else ""


async def _get_reminders(vault_root: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"http://127.0.0.1:{_port()}/reminders", params={"brain": vault_root})
        d = r.json()
        return d if isinstance(d, dict) else {"pending": [], "history": []}
    except Exception as e:
        return {"pending": [], "history": [], "error": f"{type(e).__name__}: {e}"}


async def _cancel_reminder(vault_root: str, rid: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"http://127.0.0.1:{_port()}/reminders/cancel",
                             data={"id": rid, "brain": vault_root})
        data = r.json()
    except Exception as e:
        return f"ERROR: failed to cancel the reminder: {type(e).__name__}: {e}"
    if data.get("ok"):
        return f"Cancelled reminder {rid}."
    return f"ERROR: could not cancel ({data.get('error') or 'unknown reason (the id may be wrong or it already finished)'})."


async def _do_create(vault_root: str, args: dict) -> str:
    name = str(args.get("name") or "").strip()
    prompt = str(args.get("prompt") or "").strip()
    schedule = str(args.get("schedule") or "").strip()
    if not name or not prompt or not schedule:
        return "ERROR: 'name', 'prompt' and 'schedule' are all required to create a task."
    notify_only = bool(args.get("notify_only") or False)
    chat_id = str(args.get("chat_id") or args.get("owner_chat") or "").strip()
    brain_name = Path(vault_root).name   # tên brain phiên → nói cho user biết việc rơi vào đâu
    kind = _route_kind(schedule, notify_only)
    if kind == "loop":
        return _create_loop_file(vault_root, name=name, prompt=prompt, schedule=schedule,
                                 owner_chat=chat_id, brain_name=brain_name,
                                 mode=str(args.get("muc_quyen") or ""))
    # I2: notify_only=True nghĩa là CHỈ nhắc bằng lời (mode "notify" - reminders.py:342 "⏰ Nhắc
    # anh: ..."), KHÔNG dựng nguyên engine Claude + MCP để "làm hộ" (mode "task" - reminders.py:
    # 418 _run_task, tốn tới max_wall_s=300). Trước đây hard-code "task" nên notify_only vô nghĩa -
    # mọi nhắc đều chạy LLM dù model chỉ được yêu cầu NHẮC.
    payload = {"text": prompt, "label": name, "mode": ("notify" if notify_only else "task"),
               "brain": vault_root, "chat_id": chat_id, "created_by": "javis_schedule",
               "allow_no_channel": bool(args.get("allow_no_channel") or False)}
    # Bỏ trống thì máy chủ tự đặt mặc định; chỉ gửi khi model có ý hạ/nâng mức rõ ràng.
    if str(args.get("muc_quyen") or "").strip():
        payload["muc_quyen"] = str(args["muc_quyen"]).strip().lower()
    if args.get("remember_last") and not notify_only:
        payload["remember_last"] = True
    if args.get("speak"):
        payload["speak"] = True
    if args.get("call"):
        payload["call"] = True
    payload.update(_reminder_time_payload(schedule))
    return await _post_reminder(payload, brain_name=brain_name)


async def _update_reminder(vault_root: str, rid: str, fields: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"http://127.0.0.1:{_port()}/reminders/update",
                             data=dict({"id": rid, "brain": vault_root}, **fields))
        data = r.json()
    except Exception as e:
        return f"ERROR: failed to edit the schedule: {type(e).__name__}: {e}"
    if not data.get("ok"):
        return f"ERROR: {data.get('error') or 'could not edit'}"
    rem = data.get("reminder") or {}
    when = rem.get("cron_human") or rem.get("cron") or ""
    return (f"Edited schedule {rid}" + (f" to '{when}'" if when else "")
            + f", next run {rem.get('due_human') or '?'}."
            + _next_runs_line(rem.get("next_runs")))


def _update_loop_file(vault_root: str, slug: str, fields: dict) -> str:
    """Sửa loop bằng cách ghi lại frontmatter. Chỉ nhận name/prompt/schedule - enabled/mode đổi
    trên dashboard, nơi người dùng nhìn thấy cả danh sách loop."""
    fp = _loops_dir(vault_root) / f"{slug}.md"
    try:
        if fp.resolve().parent != _loops_dir(vault_root).resolve() or not fp.is_file():
            return f"ERROR: recurring task '{slug}' not found"
        text = fp.read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR: failed to read the loop file: {type(e).__name__}: {e}"
    m = _FM_RE.match(text)
    if not m:
        return f"ERROR: loop file '{slug}' has no valid frontmatter"
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception as e:
        return f"ERROR: bad frontmatter: {e}"
    if not isinstance(fm, dict):
        return "ERROR: bad frontmatter"
    body = m.group(2)
    if fields.get("name"):
        fm["name"] = str(fields["name"])
    if fields.get("prompt"):
        body = str(fields["prompt"]).strip() + "\n"
    if fields.get("schedule"):
        interval = _interval_min(str(fields["schedule"]))
        if interval is None:
            return (f"ERROR: unclear interval '{fields['schedule']}' - state a number + unit "
                    f"(e.g. '120m', '2 hours', 'every day')")
        fm["interval_min"] = interval
    fm["updated"] = _today()
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: " + (_yaml_scalar(v) if isinstance(v, str) else json.dumps(v)))
    lines += ["---", "", body.strip(), ""]
    try:
        tmp = fp.with_suffix(".md.tmp")
        tmp.write_text("\n".join(lines), encoding="utf-8")
        tmp.replace(fp)
    except Exception as e:
        return f"ERROR: ghi file loop lỗi: {type(e).__name__}: {e}"
    return (f"Edited recurring task '{fm.get('name') or slug}' (every {fm.get('interval_min')} minutes). "
            f"The on/off state is unchanged.")


async def _do_update(vault_root: str, args: dict) -> str:
    rid = str(args.get("id") or "").strip()
    if not rid:
        return "ERROR: 'id' is required to edit (get it from op=list)."
    fields = {}
    if str(args.get("name") or "").strip():
        fields["name"] = str(args["name"]).strip()
    if str(args.get("prompt") or "").strip():
        fields["prompt"] = str(args["prompt"]).strip()
    if str(args.get("schedule") or "").strip():
        fields["schedule"] = str(args["schedule"]).strip()
    if isinstance(args.get("remember_last"), bool):
        fields["remember_last"] = args["remember_last"]
    call = args.get("call") if isinstance(args.get("call"), bool) else None
    if not fields and call is None:
        return "ERROR: nothing to edit - pass at least one of name / prompt / schedule."
    if (_loops_dir(vault_root) / f"{rid}.md").is_file():
        if not fields:
            return "ERROR: a recurring task cannot place a call; 'call' is for reminders only."
        return _update_loop_file(vault_root, rid, fields)
    # Kho nhắc hẹn: đổi lịch thì dịch chuỗi lịch sang tham số thời gian như lúc tạo.
    payload = {}
    if "name" in fields:
        payload["label"] = fields["name"]
    if "prompt" in fields:
        payload["text"] = fields["prompt"]
    if "schedule" in fields:
        payload.update(_reminder_time_payload(fields["schedule"]))
    if "remember_last" in fields:
        payload["remember_last"] = "true" if fields["remember_last"] else "false"
    if call is not None:
        payload["call"] = "true" if call else "false"
    return await _update_reminder(vault_root, rid, payload)


async def _do_list(vault_root: str) -> str:
    lines = []
    loops = _list_loops(vault_root)
    if loops:
        lines.append("RECURRING tasks (Javis/loops):")
        for lp in loops:
            trang = "on" if lp["enabled"] else "off"
            lines.append(f"- [{lp['id']}] {lp['name']} - every {lp['interval_min']} minutes, "
                         f"currently {trang}, mode {lp['mode']}")
    rem = await _get_reminders(vault_root)
    pending = rem.get("pending") or []
    if pending:
        lines.append("Reminders / schedules (reminders store):")
        for r in pending:
            # Nói lịch bằng LỜI ("7:00 mỗi ngày") kèm biểu thức thô - model kể lại cho user thì
            # user hiểu ngay, không phải tự dịch "0 7 * * *".
            extra = (f" (repeats {r.get('cron_human') or r.get('cron')} - cron {r.get('cron')})"
                     if r.get("cron") else "")
            lines.append(f"- [{r.get('id')}] {r.get('label') or r.get('text')} - "
                         f"next {r.get('due_human')}{extra}")
    if rem.get("error"):
        lines.append(f"(could not read the reminders store: {rem['error']})")
    if not lines:
        return "No recurring tasks or reminders yet (both the loop store and the reminders store are empty)."
    return "\n".join(lines)


async def _do_cancel(vault_root: str, args: dict) -> str:
    rid = str(args.get("id") or "").strip()
    if not rid:
        return "ERROR: 'id' is required to cancel (get it from the op=list result)."
    if (_loops_dir(vault_root) / f"{rid}.md").is_file():
        return _cancel_loop_file(vault_root, rid)
    return await _cancel_reminder(vault_root, rid)


async def javis_schedule(args: dict, cctx) -> str:
    args = args or {}
    vault_root = getattr(cctx, "vault_root", None)
    # An toàn CỨNG: đây chính là bug Task 1 vừa vá ở nơi khác (image_gen._resolve_vault rơi về
    # Brain Default khi vault_root rỗng, lưu nhầm brain suốt mà không ai biết). Không tái tạo.
    if not vault_root:
        return "ERROR: cannot determine the active brain"
    op = str(args.get("op") or "create").strip().lower()
    if op == "create":
        return await _do_create(vault_root, args)
    if op == "list":
        return await _do_list(vault_root)
    if op == "update":
        return await _do_update(vault_root, args)
    if op == "cancel":
        return await _do_cancel(vault_root, args)
    return f"ERROR: invalid op: {op!r} (use create|list|update|cancel)"


def register(ctx) -> None:
    ctx.register_tool(
        name="javis_schedule",
        description=(
            "Create/list/edit/cancel RECURRING tasks or REMINDERS straight from chat - instead of hand-writing YAML "
            "into Javis/loops or curling POST /reminders yourself. CALL it when the user says things like: 'create a "
            "task that scans orders every 2 hours' (op=create, schedule='120m' or 'every 2 hours'), 'remind me of "
            "revenue every day at 7am' (schedule='0 7 * * *'), 'remind me to call the customer in 30 "
            "minutes' (schedule='in 30 minutes'), 'is anything still running' (op=list), or "
            "'move that task to 8am' (op=update, id from op=list, schedule='0 8 * * *'), or "
            "'cancel the order scan' (op=cancel, get the id from op=list first). "
            "ONLY CREATE WHEN THE PRECONDITIONS HOLD: before op=create, ask yourself whether this task will have EVERYTHING "
            "it needs when it runs (is the data source connected, is there a channel to report results to). If something is missing, SAY "
            "PLAINLY what is missing and ask the user; do NOT create it first and stay silent while it fails every day. "
            "ONLY CALL when the user gives a clear order about Jarvis 007's automatic schedule; do NOT call just because the sentence has "
            "'schedule', booking, a 1-1 consultation, an appointment, or the talk is about product/UX/marketing. "
            "In those cases answer as a normal conversation, no op=list/create/cancel. "
            "The tool CHOOSES the store itself: REPEATING+DURABLE schedules ('120m'/'2h'/'every X hours'/'90 minutes') write the file Javis/loops/<slug>.md (editable "
            "in Obsidian, OFF by default + suggest-only, the user must switch it on in the Work tab); fixed-time "
            "repeating schedules (5-field cron '0 7 * * *', macro '@daily') or one-off ones ('in 30 "
            "minutes', '8:30', '2026-07-20 09:00') go to the existing reminders store."
        ),
        handler=javis_schedule,
        min_mode="safe",
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["create", "list", "update", "cancel"],
                       "description": ("create = create a new task (needs name/prompt/schedule); "
                                       "list = list EVERY existing task, both loops and reminders; "
                                       "update = edit an existing task by id (pass name/prompt/"
                                       "schedule - any field not passed is kept as is); "
                                       "cancel = cancel one task by id (get it from op=list).")},
                "name": {"type": "string",
                         "description": "Short name of the task, e.g. 'Scan orders every 2 hours' (op=create)."},
                "prompt": {"type": "string",
                           "description": ("What to do on each run/reminder (op=create) - write it "
                                           "SELF-CONTAINED, not dependent on the current chat context because it will "
                                           "run when nobody is asking.")},
                "schedule": {"type": "string",
                             "description": ("Schedule (op=create). Repeating+durable: '120m' (every 120 minutes), "
                                             "'2h', 'every 2 hours', '90 minutes'. Fixed-time repeating: "
                                             "5-field cron '0 7 * * *', macro '@daily'. One-off: "
                                             "'in 30 minutes', '8:30' (if already past today -> rolls to "
                                             "tomorrow), or a full date and time '2026-07-20 09:00'.")},
                "notify_only": {"type": "boolean",
                                 "description": ("true = force a ONE-TIME reminder (reminders store) even if "
                                                 "the schedule looks like a repeating interval. Default false.")},
                "muc_quyen": {"type": "string", "enum": ["suggest", "auto", "full"],
                              "description": ("Permission of the task when it runs, applies to both loops and "
                                              "reminders. 'full' (default) = may use every connected "
                                              "tool, including actions on the outside world (sending messages, publishing posts, "
                                              "creating orders, payments). 'auto' = read + write files, "
                                              "no outside actions. 'suggest' = read-only, then "
                                              "report back. Only lower the level when the user wants that.")},
                "speak": {"type": "boolean",
                          "description": "true = when the time comes, also send a VOICE MESSAGE reading the result aloud (the user wants to listen)."},
                "call": {"type": "boolean",
                         "description": ("true = when the time comes Jarvis 007 CALLS IN like a phone call on the page where Jarvis 007 is open; when the user clicks "
                                         "Listen, Jarvis 007 reads the result and keeps talking (\"call me at 7 to read the report\").")},
                "remember_last": {"type": "boolean",
                                  "description": ("true = each run receives the previous run's result (to track "
                                                  "and report what is new). Only for self-running reminders, not for loops.")},
                "chat_id": {"type": "string",
                             "description": "Telegram chat_id of the requester, so the report reaches the right person. Leave empty if unknown."},
                "allow_no_channel": {"type": "boolean",
                                      "description": ("Set true only when the tool has reported a MISSING DELIVERY CHANNEL, "
                                                      "you have told the user what is missing, and the user still "
                                                      "wants to create it. NEVER set true on "
                                                      "the first call on your own.")},
                "id": {"type": "string",
                       "description": "id of the task to edit/cancel (op=update|cancel) - get it from the op=list result."},
            },
            "required": ["op"],
        },
    )
