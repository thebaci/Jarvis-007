"""Plugin bundled: tool `javis_ui` - bảo dashboard mở trang / file / việc, cuộn khung chat.

Vì sao là TOOL chứ không phải khối `<!-- JAVIS_UI -->` trong câu trả lời: tool có kết quả trả về
ngay trong lượt (dashboard đáp "đã mở" hay "không có tab nào"), đi qua hub nên mọi bộ não gọi
được như nhau, và tôn trọng ba mức quyền bằng code. Khối trong câu trả lời thì server đang lột
mọi `JAVIS_*` trước khi lưu, và không có đường báo kết quả về. Xem
docs/dev/2026-10-voice-call-spec.md phụ lục A6.

Đường đi: handler -> ui_bridge.request() -> frame `ui_action` qua /ws -> dashboard chạy và trả
`ui_result` -> ui_bridge.resolve() -> handler có kết quả. Không import main: main gắn runtime vào
ui_bridge lúc khởi động.

Kiểm target Ở CẢ HAI ĐẦU. Server chặn trước để model nhận lỗi rõ ràng thay vì đợi 4 giây; dashboard
kiểm lại lần nữa vì nó là bên thực hiện và không tin server tuyệt đối.
"""
from __future__ import annotations

import ui_bridge
import ui_targets   # bảng tên trang/nhóm + bí danh tiếng Việt, dùng CHUNG với đường tắt giọng nói

# Tên trang, tên nhóm và bí danh nằm ở server/ui_targets.py. Trước 0.57.6 bảng đó nằm ngay
# trong file này, nên đường tắt giọng nói (main.py, dòng JAVIS_UI:) không tra được và cứ nói
# tiếng Việt là dashboard trả "trang không tồn tại".
PAGES = ui_targets.PAGES
ALIASES = ui_targets.ALIASES
GROUPS = ui_targets.GROUPS
GROUP_ALIASES = ui_targets.GROUP_ALIASES
resolve_page = ui_targets.resolve_page
resolve_group = ui_targets.resolve_group
normalize_target = ui_targets.normalize_target
resolve_scroll = ui_targets.resolve_scroll
SCROLL_TARGETS = ui_targets.SCROLL_TARGETS
_khong_dau = ui_targets.khong_dau

ACTIONS = ("open_page", "open_file", "open_task", "scroll", "open_group", "sidebar")


def check_target(action: str, target: str) -> str:
    """Chuỗi lý do chặn, hoặc rỗng nếu ổn. Trả target đã chuẩn hoá qua `normalize_target`."""
    if action not in ACTIONS:
        return f"action '{action}' does not exist. Choose one of: {', '.join(ACTIONS)}."
    t = str(target or "").strip()
    if action == "open_page":
        if not resolve_page(t):
            return f"no page '{target}'. Valid pages: {', '.join(PAGES)}."
    elif action == "open_file":
        if not t:
            return "missing target: a relative file path inside the brain."
        bad = t.replace("\\", "/")
        if bad.startswith("/") or ":" in bad.split("/")[0] or ".." in bad.split("/") or bad.startswith("~"):
            return "target must be a RELATIVE path inside the brain (no '..', no absolute path, no scheme)."
    elif action == "open_task":
        if not t:
            return "missing target: a Kanban task id (get it from javis_task op=list)."
    elif action == "scroll":
        if not resolve_scroll(t):
            return ("scroll accepts target: " + " | ".join(SCROLL_TARGETS) + " (or Vietnamese such as "
                    "'xuống dưới', 'cuộn trang này lên', 'cuộn khung chat xuống').")
    elif action == "open_group":
        if not resolve_group(t):
            return f"no group '{target}'. Valid groups: {', '.join(GROUPS)}."
    elif action == "sidebar":
        if _khong_dau(t) not in ("open", "close", "mo", "dong", "bung", "thu", "thu gon"):
            return "sidebar only accepts target 'open' (expand the sidebar) or 'close' (collapse it)."
    return ""


async def _ui(args, ctx) -> str:
    action = str((args or {}).get("action") or "").strip().lower()
    target = str((args or {}).get("target") or "")
    why = check_target(action, target)
    if why:
        return "ERROR: [failed] " + why
    target = normalize_target(action, target)
    sid = str((args or {}).get("session_id") or "").strip()
    if sid.startswith("web:"):
        sid = sid[4:]
    res = await ui_bridge.request(action, target, session_id=sid)
    if not res.get("ok"):
        return "ERROR: [failed] " + (res.get("detail") or "the dashboard could not do it")
    detail = res.get("detail") or ""
    if action == "scroll":
        # `detail` là thứ dashboard THẬT SỰ cuộn ("nội dung trang" hay "khung chat"). Đừng đoán:
        # target 'bottom' là để dashboard tự chọn theo trang đang mở.
        return f"[done] Scrolled {detail or 'the chat panel'} to the {'top' if target.endswith('top') else 'bottom'}."
    if action == "sidebar":
        return "[done] Expanded the sidebar." if target == "open" else "[done] Collapsed the sidebar."
    if action == "open_group":
        return f"[done] Expanded group {target} on the sidebar."
    ten = {"open_page": "page", "open_file": "file", "open_task": "task"}[action]
    # [done]: the dashboard tab acknowledged the action (ui_bridge waits for its reply).
    return f"[done] Opened {ten} {target} on the dashboard." + (f" {detail}" if detail else "")


def register(ctx):
    ctx.register_tool(
        name="javis_ui",
        description=(
            "Control the Jarvis 007 DASHBOARD open in the user's browser: open a page, open a file, "
            "open a task, scroll. Use when the user says (in words or typed) 'open the Tasks page', 'open file X', "
            "'show me the task I just assigned', 'scroll down'. action=open_page (target: page id - "
            + ", ".join(PAGES) + " - or the EXACT Vietnamese name shown on the sidebar: 'việc', 'tệp tin', 'cài đặt', 'trợ lý' and 'quy trình' = workspace (the Teammates page), 'kỹ năng' = skills, 'công cụ' = plugins); "
            "open_file (target: relative path inside the brain); open_task (target: Kanban task id); "
            "scroll (scrolls WHAT THE USER IS LOOKING AT - target: top | bottom to let the dashboard choose "
            "based on the open page, page_top | page_bottom when they clearly say 'scroll this page', "
            "chat_top | chat_bottom when they clearly say 'scroll the chat panel'); open_group (EXPAND a collapsed sidebar group "
            "WITHOUT changing page, use when the user says 'open the Capabilities section', 'expand the Connections group', 'show me "
            "the hidden part of the menu' - target: " + ", ".join(GROUPS) + " or a Vietnamese name such as 'năng lực'); "
            "sidebar (target: open to expand the whole sidebar, close to collapse it to icons). session_id: the web session id "
            "in the KÊNH HỘI THOẠI HIỆN TẠI block "
            "(so the right tab acts; leave empty and every open tab acts). The tool returns '[done] Opened ...' when the "
            "dashboard confirms, or 'ERROR: [failed] ...' when no tab is open / the page does not exist."
        ),
        handler=_ui, min_mode="safe",
        schema={"type": "object", "properties": {
            "action": {"type": "string", "enum": list(ACTIONS)},
            "target": {"type": "string"},
            "session_id": {"type": "string"},
        }, "required": ["action", "target"]},
    )
