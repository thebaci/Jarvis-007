"""Plugin bundled: tool `javis_job` - lời dặn "xong thì làm tiếp", xem và dừng việc chạy nền.

Vì sao có tool này (0.64.66)
============================
Chủ repo báo 2026-09-27: Javis nói "Đang render nền, xong mình ghép tiếng và gửi video" rồi im,
video xong mà phải hỏi tới lần thứ ba mới biết. Máy chủ giờ TỰ nhận theo dõi mọi lệnh chạy ngầm
mà engine bỏ lại khi hết lượt (`server/tien_trinh_nen.py`), không cần model làm gì. Tool này chỉ
cho model nói thêm MỘT điều mà máy chủ không đoán được: xong rồi thì làm tiếp cái gì.

Tool KHÔNG chạy lệnh. Cấp quyền chạy shell cho engine API qua đường vòng này là mở ra đúng thứ
CLAUDE.md nói chúng không có. Engine có shell tự chạy lệnh ngầm như thường (`cmd > log 2>&1 &`),
còn việc theo dõi là của máy chủ.

Ba op:
- then: dặn việc cần làm khi việc chạy nền của lượt NÀY xong. Gọi trong cùng lượt đã bật lệnh
  ngầm. Nếu khung chat đã có việc đang được theo dõi (lượt trước), lời dặn gắn luôn vào việc đó.
- list: việc chạy nền gần đây của khung chat (đang chạy, xong, dừng).
- cancel: dừng một việc theo mã.
"""
from __future__ import annotations

import time

try:
    import tien_trinh_nen
except Exception:          # chạy ngoài máy chủ
    tien_trinh_nen = None
try:
    import luot_dang_chay
except Exception:
    luot_dang_chay = None

_TEN_TRANG_THAI = {"run": "running", "xong": "done", "huy": "stopped",
                   "bo_theo_doi": "no longer tracked (still running)"}


def _chat(args, ctx) -> str:
    cid = str((args or {}).get("chat_id") or "").strip()
    if not cid and luot_dang_chay is not None and ctx.vault_root:
        try:
            cid = luot_dang_chay.doan_chat_id(ctx.vault_root) or ""
        except Exception:
            cid = ""
    return cid


def _then(args, ctx) -> str:
    text = str((args or {}).get("text") or "").strip()
    if not text:
        return "ERROR: missing text - state clearly what to do when the background job finishes."
    cid = _chat(args, ctx)
    if not cid:
        return ("ERROR: could not determine which chat is asking, so there is nowhere to follow up. "
                "Pass the chat_id taken from the KÊNH HỘI THOẠI HIỆN TẠI block.")
    v = tien_trinh_nen.gan_loi_dan_cho_viec_dang_chay(cid, text)
    if v:
        return (f"Attached the instruction to the running job {v['id']} (`{v.get('mo_ta', '')}`). When it finishes, Jarvis 007 "
                "will report to this chat on its own and carry out the instruction.")
    tien_trinh_nen.dat_loi_dan(cid, text)
    return ("Instruction saved. When this turn ends, Jarvis 007 will track any background command from this turn "
            "that is still alive; when it finishes, it reports to this chat on its own and opens a new turn "
            "to carry out the instruction. "
            "If NO background command is still running at the end of the turn, the instruction is dropped - make sure the command has "
            "been started in the background (e.g. `cmd > out.log 2>&1 &`) before the turn ends. You can tell the "
            "user the result will arrive here on its own.")


def _list(args, ctx) -> str:
    cid = _chat(args, ctx)
    ds = tien_trinh_nen.gan_day(cid) if cid else tien_trinh_nen.dang_chay(brain_root=ctx.vault_root or "")
    if not ds:
        return "There are no background jobs for this chat."
    now = time.time()
    dong = []
    for v in ds:
        tl = tien_trinh_nen.thoi_luong(float(v.get("ket_thuc") or now) - float(v.get("bat_dau") or now))
        dong.append(f"{v['id']} · {_TEN_TRANG_THAI.get(v.get('trang_thai'), v.get('trang_thai'))} · {tl} · "
                    f"{v.get('mo_ta', '')}" + (f" · then: {v['sau_khi_xong']}" if v.get("sau_khi_xong") else ""))
    return "\n".join(dong)


def _cancel(args, ctx) -> str:
    jid = str((args or {}).get("id") or "").strip()
    if not jid:
        return "ERROR: missing the id of the job to stop (see op=list)."
    v = tien_trinh_nen.huy(jid)
    if not v:
        return f"No running job has the id {jid}."
    return f"Stop command sent for {jid} (`{v.get('mo_ta', '')}`). Jarvis 007 will report when it has fully stopped."


def _chay(args, ctx) -> str:
    if tien_trinh_nen is None:
        return "ERROR: the background job tracker is not available on this server yet."
    if not tien_trinh_nen.POSIX:
        return ("ERROR: background job tracking does not support Windows yet. Run the command in this turn "
                "(not in the background) to return the result right away, or hand it to Kanban.")
    op = str((args or {}).get("op") or "").strip().lower()
    if op == "then":
        return _then(args, ctx)
    if op == "list":
        return _list(args, ctx)
    if op == "cancel":
        return _cancel(args, ctx)
    return "ERROR: op must be then, list or cancel."


def register(ctx):
    ctx.register_tool(
        "javis_job",
        "Background jobs that you started yourself in the shell (video render, build, large download). "
        "When the turn ends, Jarvis 007 AUTOMATICALLY tracks every background command still alive and reports to the chat when it finishes, "
        "so you do not need to promise 'I will tell you when it is done'. "
        "op=then: say what to do when the background job finishes (e.g. 'add the audio to the video, check 8 frames, "
        "send the file'); Jarvis 007 will open a new turn to do exactly that. Call it in the same turn "
        "that started the background command. op=list: see the chat's background jobs. op=cancel id=...: stop a "
        "job. This tool does not run commands.",
        _chay,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["then", "list", "cancel"]},
                "text": {"type": "string", "description": "What to do when the background job finishes (op=then)"},
                "id": {"type": "string", "description": "Job id (op=cancel)"},
                "chat_id": {"type": "string", "description": "Chat, e.g. web:<session id>; leave empty to detect automatically"},
            },
            "required": ["op"],
        },
        min_mode="safe",
        emoji="⏳",
    )
