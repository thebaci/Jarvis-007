"""Plugin bundled: tool `javis_task` - giao việc Kanban và xem tiến độ, từ MỌI engine.

Vì sao tool này tồn tại
=======================
`CLAUDE.md` và `docs/10-models-va-engine.md` đều hứa mọi bộ não được cấp cùng một bộ đồ nghề,
trong đó có "giao việc Kanban", và khác biệt duy nhất là chạy được lệnh máy hay không.

Lời hứa đó SAI cho tới bản này. Đường duy nhất để giao việc là `POST /kanban/task`, mà gọi được
nó thì phải có Bash và curl - tức là chỉ Claude Code với Codex. Năm engine API đứng ngoài. Tệ
hơn, chính `CLAUDE.md` còn dặn Javis "đừng bao giờ nói mình không làm task được, sai sự thật",
nên một engine API sẽ TỰ TIN nhận lời rồi im lặng không làm gì - kiểu hỏng tệ nhất, vì người
dùng đợi một việc không bao giờ chạy.

Hai cách sửa: hạ tài liệu xuống cho khớp mã, hoặc nâng mã lên cho khớp tài liệu. Chủ repo chọn
cách hai (2026-08-04), vì giao việc là thứ dùng thật và để nó chỉ chạy trên hai engine thì lời
hứa "đổi não thoải mái không mất chức năng" thủng đúng chỗ đáng tiếc nhất.

Gọi THẲNG, không đi vòng qua HTTP
=================================
`javis-schedule` POST tới `/reminders` được vì route đó CỐ Ý miễn đăng nhập cho localhost
(`main._AUTH_LOCAL_EXACT`). `/kanban/task` thì không, và cách duy nhất để nó gọi được qua HTTP
là thêm vào danh sách miễn auth đó - nghĩa là bất kỳ tiến trình nào trên cùng máy chủ cũng giao
được việc cho Javis mà không cần credential. Không đáng, khi plugin vốn đã chạy IN-PROCESS:
`tasks.current()` cho ngay hàng đợi thật, không hở thêm cửa nào.

Mức quyền
=========
- Mặc định `full`: việc tự thao tác THẬT ra ngoài (tạo đơn, thanh toán, chạy quảng cáo, gửi
  tin) như lúc người dùng đang ngồi chat. Chủ repo bỏ luật "không giao tự động tiền/đơn/đăng
  bài/nhắn khách" ngày 2026-09-10; trước đó tool này từ chối thẳng `mode="full"` và mặc định
  `suggest`. Muốn việc nhẹ hơn thì truyền `mode="auto"` (ghi nháp) hoặc `"suggest"` (chỉ đọc).

Hai luật còn giữ, vì chúng không liên quan tới mức quyền mà tới việc chạy ĐÚNG brain và về ĐÚNG
người:
- `vault_root` rỗng -> báo lỗi rõ, TUYỆT ĐỐI không âm thầm rơi về Brain Default. Giao việc nhầm
  brain là việc chạy trên dữ liệu của người khác.
- `chat_id` rỗng thì CẢNH BÁO trong kết quả trả về chứ không nuốt: kết quả việc sẽ đi về ID
  Telegram đầu tiên trong whitelist, mà máy chưa đấu Telegram thì MẤT HÚT. Model phải lấy mã
  phiên từ khối "KÊNH HỘI THOẠI HIỆN TẠI" và truyền vào.

Phạm vi v1: `add` và `list`. Chuyển cột, huỷ, duyệt việc chờ phê duyệt vẫn làm ở trang Việc -
đó là những thao tác cần nhìn thấy bảng, và mô tả tool nói thẳng như vậy thay vì để model đoán.

`route` (0.107.0): `auto` hoặc `wf:<slug>` của một quy trình CÓ THẬT. Trước bản này tool không
có tham số này, trong khi mô tả của `javis_workflow` lại bảo "dùng javis_task với route
wf:<slug>" - nên chat không có cách nào giao một lần chạy quy trình thật. Ngày 13/10 việc S07
được giao với route auto, tên quy trình chỉ nằm trong mô tả, và sáu agent của quy trình chưa
từng được gọi lần nào. Giờ route sai slug bị từ chối rõ, còn route auto mà tên việc nhắc đúng
một quy trình có thật thì kết quả trả về cảnh báo để model giao lại cho đúng.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import tasks as tasks_mod
import workflow_graph

try:
    from skill_router import read_frontmatter_only
except Exception:          # chạy lẻ ngoài máy chủ
    read_frontmatter_only = None

try:
    import luot_dang_chay
except Exception:          # chạy ngoài máy chủ (test lẻ): không có sổ thì thôi đoán
    luot_dang_chay = None

# Trần ký tự cho phần liệt kê việc. Kết quả tool đi thẳng vào ngữ cảnh của lượt chat, và engine
# API còn bị cắt ở 8000 ký tự (engine._clip_tool_result) - liệt kê 200 việc là đẩy văng phần
# quan trọng của câu hỏi ra ngoài.
_LIST_MAX = 40

# Cột đáng báo cáo, theo thứ tự người dùng quan tâm: đang chạy trước, xong rồi để cuối.
_COT = [
    ("running", "running"),
    ("review", "awaiting review"),
    ("blocked", "blocked"),
    ("ready", "ready"),
    ("todo", "waiting for turn"),
    ("triage", "newly received"),
    ("done", "done"),
]

_MODE_CHO_PHEP = ("suggest", "auto", "full")
_MODE_MAC_DINH = "full"

# Chỉ mức điều phối "auto" mới có dispatcher lấy việc ra chạy (`tasks.TaskRunner._dispatch`).
# "off" (mặc định của MỌI brain mới) và "manual" đều để việc nằm im vô thời hạn.
_CANH_BAO_DIEU_PHOI = (
    "IMPORTANT NOTE: background orchestration for this brain is set to \"{muc}\", so the task only sits "
    "in the queue, will NOT run by itself, and no result will come back on its own. Tell the user "
    "this plainly and ask them to turn on \"AI self-driving\" on the Work page. Do not promise the task is running."
)


def _dieu_phoi_chay(muc) -> bool:
    return str(muc or "").strip().lower() == "auto"


def _workflows(f, vault_root) -> dict:
    """{slug: (name, status)} of the brain's workflows. Empty when unreadable."""
    try:
        d = Path(f.deps.workflows_dir(vault_root))
    except Exception:
        return {}
    out = {}
    try:
        files = sorted(d.glob("*.md")) if d.is_dir() else []
    except OSError:
        files = []
    for fp in files:
        meta = {}
        if read_frontmatter_only is not None:
            try:
                meta = read_frontmatter_only(fp)[0] or {}
            except Exception:
                meta = {}
        out[fp.stem] = (str(meta.get("name") or fp.stem), workflow_graph.workflow_status(meta))
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _workflow_nhac_toi(wfs: dict, title: str, intent: str) -> list:
    """Slugs of workflows the job text names (by slug or by display name)."""
    text = _norm(title + " " + intent)
    hits = []
    for slug, (name, _status) in wfs.items():
        if ((len(slug) >= 6 and slug.lower() in text)
                or (len(_norm(name)) >= 6 and _norm(name) in text)):
            hits.append(slug)
    return hits


def _feature():
    f = tasks_mod.current()
    if f is None:
        return None, ("ERROR: the task queue is not ready yet (is the server still starting?). "
                      "Try again in a few seconds, or add the task on the Work page of the dashboard.")
    return f, ""


def _them(args, ctx) -> str:
    if not ctx.vault_root:
        return ("ERROR: it is not known which brain we are working on, so the task cannot be added. "
                "Add it on the Work page of the dashboard, where the brain is clear.")
    tieu_de = str((args or {}).get("title") or "").strip()
    if not tieu_de:
        return "ERROR: missing title - a task needs a name so the user can follow it."

    mode = str((args or {}).get("mode") or _MODE_MAC_DINH).strip().lower()
    # Mode lạ (model gõ sai, hoặc bịa ra tên mức) kẹp về mặc định thay vì để enqueue tự xử.
    if mode not in _MODE_CHO_PHEP:
        mode = _MODE_MAC_DINH

    f, loi = _feature()
    if loi:
        return loi

    route = str((args or {}).get("route") or "auto").strip() or "auto"
    wfs = _workflows(f, ctx.vault_root)
    canh_bao_route = ""
    if route != "auto":
        slug = route[3:].strip() if route.startswith("wf:") else ""
        if not slug:
            return ("ERROR: route only accepts 'auto' or 'wf:<slug>' of a real workflow. "
                    "Existing workflows: " + (", ".join(sorted(wfs)) or "(no workflows yet)") + ".")
        if slug not in wfs:
            return (f"ERROR: there is no workflow '{slug}' in this brain, so the task was not added. "
                    "Existing workflows: " + (", ".join(sorted(wfs)) or "(no workflows yet)")
                    + ". Ask the user again if you are not sure which workflow.")
        route = f"wf:{slug}"
        if wfs[slug][1] != "active":
            canh_bao_route = (f"NOTE: workflow '{wfs[slug][0]}' is OFF, so this task will stop and wait "
                              "as soon as its turn comes. Tell the user to turn the workflow on at the Team "
                              "page, then rerun the task on the Work page.")
    else:
        nhac = _workflow_nhac_toi(wfs, tieu_de, str((args or {}).get("intent") or ""))
        if nhac:
            canh_bao_route = (
                "WARNING: this task mentions workflow " + ", ".join(f"wf:{s}" for s in nhac)
                + " but was added with route auto, so ONE generic worker will do everything instead of running "
                "the workflow's own agents. If the user wants to run that workflow, add it again "
                "with route=wf:<slug> (give the task a different name, because a duplicate name will be rejected).")

    chat_id = str((args or {}).get("chat_id") or "").strip()
    # Model quên chat_id thì hỏi sổ lượt đang chạy (0.64.49): đúng một khung chat đang hỏi trên
    # brain này thì đó chính là người giao việc. Không chắc thì để trống như cũ và cảnh báo.
    tu_gan = False
    if not chat_id and luot_dang_chay is not None:
        try:
            chat_id = luot_dang_chay.doan_chat_id(ctx.vault_root)
            tu_gan = bool(chat_id)
        except Exception:
            chat_id = ""
    deps = [d.strip() for d in str((args or {}).get("deps") or "").split(",") if d.strip()]
    try:
        tid = f.enqueue(
            ctx.vault_root,
            tieu_de,
            str((args or {}).get("intent") or "").strip() or tieu_de,
            route,
            2,
            deps,
            False,
            "chat",
            chat_id,
            "auto",
            mode,
            "",
        )
    except Exception as e:
        return f"ERROR: could not add the task ({type(e).__name__}: {e})."

    # Kho việc TRẢ VỀ việc cũ khi trùng tên với một việc còn sống (kể cả đang kẹt hay chờ
    # duyệt) chứ không tạo việc mới. Bản trước tool vẫn báo "Đã giao việc" với mã cũ, người
    # dùng đợi một việc không bao giờ chạy. Nói thẳng để họ đổi tên hoặc xử lý việc cũ.
    try:
        _cu = f.store.get_task(tid) or {}
    except Exception:
        _cu = {}
    if _cu and (time.time() - float(_cu.get("created_at") or time.time())) > 5:
        return (f"NO NEW TASK CREATED: a task with the same name \"{tieu_de}\" (id {tid}) already exists with status "
                f"{_cu.get('status')}. Tell the user clearly, then either give the task a different name, "
                "or handle the old task on the Work page (rerun / cancel) before adding it again.")

    ten_mode = {"suggest": "read-only, suggestions only", "auto": "may write draft files in the brain",
                "full": "full permission, acts on the outside world by itself"}[mode]
    ra = [f"Task added: {tieu_de}", f"Task id: {tid}", f"Permission level: {mode} ({ten_mode})"]
    if route != "auto":
        ra.append(f"Runs workflow: {route} ({wfs.get(route[3:], (route[3:], ''))[0]}), "
                  "each step is done by the workflow's own agent.")
    if canh_bao_route:
        ra.append(canh_bao_route)
    if deps:
        ra.append("Waits for: " + ", ".join(deps))
    if tu_gan:
        ra.append(f"Result recipient: automatically attached to the chat that is asking ({chat_id}).")
    if not chat_id:
        # Không nuốt: đây là lý do số một khiến người dùng "giao việc rồi không thấy gì".
        ra.append("WARNING: no recipient attached (chat_id), so the result will go to the first Telegram ID "
                  "in the whitelist - and if Telegram is not connected on this machine it is lost. Next time pass "
                  "the chat_id taken from the KÊNH HỘI THOẠI HIỆN TẠI block.")

    # Lý do số hai, và là lý do LẶNG LẼ nhất: điều phối mặc định TẮT ở mọi brain mới, nên
    # "đã giao việc" và "việc đang chạy" là hai chuyện hoàn toàn khác nhau. Trước bản này tool
    # kết thúc bằng câu "Việc chạy nền. Kết quả tự về" trong MỌI trường hợp - một lời hứa sai
    # mà model không có cách nào biết là sai, rồi nó chuyển tiếp nguyên văn cho người dùng.
    muc = "off"
    try:
        muc = f.board_view(ctx.vault_root).get("orchestration") or "off"
    except Exception:
        pass
    if _dieu_phoi_chay(muc):
        ra.append("Running in the background. The result comes back on its own; see progress on the Work page.")
    else:
        ra.append(_CANH_BAO_DIEU_PHOI.format(muc=muc))
    return "\n".join(ra)


def _liet_ke(args, ctx) -> str:
    if not ctx.vault_root:
        return "ERROR: it is not known which brain we are working on, so the task list cannot be viewed."
    f, loi = _feature()
    if loi:
        return loi
    try:
        view = f.board_view(ctx.vault_root)
    except Exception as e:
        return f"ERROR: could not read the task board ({type(e).__name__}: {e})."

    cols = view.get("columns") or {}
    dong, con = [], 0
    for khoa, nhan in _COT:
        ds = cols.get(khoa) or []
        if not ds:
            continue
        for t in ds:
            if len(dong) >= _LIST_MAX:
                con += 1
                continue
            dong.append(f"[{nhan}] {t.get('id', '')} · {t.get('title', '')}")
    if not dong:
        return "There are no tasks in the queue yet."
    if con:
        dong.append(f"…(+{con} more tasks, see all on the Work page)")

    # Điều phối TẮT thì việc nằm im mãi mãi mà không có một dòng lỗi nào. Nói ngay ở đây, vì đây
    # là chỗ model đang nhìn khi người dùng hỏi "việc chạy tới đâu rồi".
    #
    # `board_mode` trả CHUỖI "off"/"manual"/"auto", không phải bool - nên `not view.get(...)`
    # là sai: "off" là chuỗi rỗng-khác-rỗng nên luôn truthy, và cảnh báo này chưa từng in ra
    # một lần nào kể từ khi được viết. Đúng cổng phải là so với "auto": chỉ mức đó mới có
    # dispatcher lấy việc ra chạy (xem `tasks.TaskRunner._dispatch`).
    if not _dieu_phoi_chay(view.get("orchestration")):
        dong.append(_CANH_BAO_DIEU_PHOI.format(muc=str(view.get("orchestration") or "off")))
    return "\n".join(dong)


def register(ctx):
    ctx.register_tool(
        "javis_task",
        "Queue a background task on the Kanban board, or see how running tasks are progressing. "
        "ONLY use op=add when the USER asks for a specific job that this turn cannot finish. "
        "Do NOT queue tasks for a plan or 'next step' you just thought up yourself that the user has not "
        "approved (e.g. 'apply the plan just presented', 'update the timeline', 'follow up and remind me'): "
        "every task fires a notification to the bell and to the chat box when it finishes or gets stuck. "
        "op=add: needs title; should include chat_id (taken from the KÊNH HỘI THOẠI HIỆN TẠI block) so the result goes to "
        "the right person, and intent if the task needs a fuller description than the title. mode=full (default: full permission, "
        "acts on the outside world by itself as in chat), auto (only writes draft files in the brain) or suggest "
        "(read-only and suggestions); lower the level only when the user wants that. deps='id1,id2' makes this task "
        "wait for other tasks to finish. "
        "route: 'auto' (default, one generic worker does it) or 'wf:<slug>' to run EXACTLY one real workflow, "
        "each step done by the workflow's agents; to run a workflow you MUST set route, "
        "copying the workflow name into intent does not make it run. "
        "op=list: list tasks by column. "
        "Moving columns, cancelling tasks and approving tasks awaiting approval are done on the Work page; this tool does not have them.",
        _chay,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["add", "list"]},
                "title": {"type": "string", "description": "Short task name (op=add)"},
                "intent": {"type": "string", "description": "A fuller description if the title is not enough"},
                "mode": {"type": "string", "enum": ["suggest", "auto", "full"]},
                "chat_id": {"type": "string", "description": "Result recipient, e.g. web:<session id>"},
                "deps": {"type": "string", "description": "Ids of tasks that must finish first, separated by commas"},
                "route": {"type": "string",
                          "description": "auto, or wf:<slug> to run a real workflow"},
            },
            "required": ["op"],
        },
        min_mode="safe",
        emoji="🗂",
    )


async def _chay(args, ctx) -> str:
    op = str((args or {}).get("op") or "").strip().lower()
    if op == "add":
        return _them(args, ctx)
    if op == "list":
        return _liet_ke(args, ctx)
    return "ERROR: op must be 'add' (add a task) or 'list' (see existing tasks)."
