"""Plugin bundled: tool `javis_goal` - bộ não tự lập hoặc cập nhật mục tiêu bền (Javis Resonance, M2).

Vì sao là tool của bộ não
=========================
Kế hoạch MVP cấm gọi thêm model để phân loại mọi tin nhắn. Bộ não vốn đang suy nghĩ về tin đó trong
lượt chat, và đã có sẵn cách tự quyết giao việc nền bằng `javis_task`. Nên quyết định "việc này cần
theo đuổi sau lượt chat" cũng thuộc về bộ não, bằng một lời gọi tool, không phải bằng từ khoá.

Host làm phần code làm chắc hơn model
=====================================
- Kiểm đề xuất theo SMART (`resonance.validate_proposal`): câu căn cứ phải trích đúng lời người dùng,
  phải có tiêu chí kiểm được và chân trời; hạn chót hay chỉ tiêu không có căn cứ thì không giữ nguyên.
- Biết ĐÚNG lượt nào đang gọi nhờ ngữ cảnh lượt do host gắn (`turn_context`, A1): phiên, id tin và agent của phiên.
  Engine trong tiến trình đọc thẳng; engine CLI mang khoá `X-Javis-Turn` qua hub. Không có ngữ cảnh, lượt không thuộc
  một agent, hay agent chưa bật Cộng hưởng thì từ chối trước mọi lần ghi kho. Không đoán "lượt duy nhất của brain".
- Một tin nhắn chỉ tạo một mục tiêu; cập nhật cần đúng `expected_revision`. Mục tiêu thuộc đúng agent của lượt:
  list và update không thấy mục tiêu của agent khác.

Hiện tool (`visible_fn`) chỉ là gợi ý: trong lượt thì theo agent của lượt, ngoài lượt thì khi brain có ít nhất một
agent bật. Cổng thật nằm trong handler. Công tắc theo brain cũ (`Javis/resonance.json`) không còn cấp quyền.
Từ M3 mục tiêu được làm tiếp ở NỀN (resonance.advance qua scheduler) trong hạn mức lượt gọi riêng; kết quả,
việc chờ xác nhận hay lý do phải dừng tự về đúng khung chat. Kết quả trả về dặn bộ não nói đúng điều đó và
không hứa thời điểm. Bộ thực thi nền CHỈ có lời người dùng và khung mục tiêu, không đọc được file hay dữ liệu.
"""
from __future__ import annotations

from pathlib import Path

_NOTE = ("Note: Jarvis 007 will keep working on the goal in the BACKGROUND, step by step, within a budget of {budget} model calls; "
         "the result, anything that needs the user's confirmation, or the reason it had to stop will appear in this chat on its own. Say exactly that, "
         "and do not promise a specific time. The background executor only has the user's words and the goal frame, it CANNOT read files "
         "or other data: do any part that needs data right now, in this turn.")


def _brain_id(vault_root) -> str:
    return str(Path(vault_root).resolve()) if vault_root else ""


def _store_exists() -> bool:
    from config import STATE_DIR
    return (Path(STATE_DIR) / "resonance.sqlite3").is_file()


def _visible(vault_root) -> bool:
    """Gợi ý hiện tool. Trong lượt: lượt thuộc một agent đang bật. Ngoài lượt (danh sách hub dùng chung): brain có ít
    nhất một agent bật. Không tạo kho chỉ để trả lời câu này."""
    try:
        import resonance as R
        import resonance_store as RS
        import turn_context
        if not vault_root or not _store_exists():
            return False
        store, bid = RS.GoalStore(), _brain_id(vault_root)
        t = turn_context.current()
        if t is not None:
            ag = t.get("agent") or {}
            return bool(ag.get("key")) and not R.agent_gate(store, bid, ag["key"])[1]
        return any(a["enabled"] and a["status"] == "active" for a in store.agents(bid))
    except Exception:  # noqa: BLE001
        return False


def _proposal(args: dict) -> dict:
    # remove_targets đã gỡ khỏi schema (M2 chưa bỏ được chỉ tiêu người dùng) nhưng lời gọi cũ vẫn có thể mang
    # nó: chuyển tiếp để validator báo "chưa hỗ trợ" thay vì lặng lẽ bỏ qua.
    keys = ("understanding", "criteria", "relevant_quote", "horizon", "stage", "mode", "assumptions",
            "constraints", "targets", "open_questions", "guards", "remove_targets")
    return {k: args.get(k) for k in keys if k in args}


def _when(ts) -> str:
    try:
        import time
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except Exception:  # noqa: BLE001
        return "?"


def _summary(g, head: str) -> str:
    h = g.horizon or {}
    if h.get("kind") == "deadline":
        hz = f"deadline {_when(h.get('at'))} (the user said: \"{h.get('quote')}\")"
    elif h.get("kind") == "review":
        hz = f"internal review point {_when(h.get('at'))}, NOT a user deadline"
    elif h.get("kind") == "event":
        hz = f"waiting for event: {h.get('event')}"
    else:
        hz = "maintain until the user stops it"
    lines = [f"{head} {g.id} (revision {g.revision}, stage {g.stage}, mode {g.mode}).",
             f"Understanding: {g.understanding or '(not clear yet, still in discovery)'}",
             "Criteria: " + "; ".join(f"{c['id']} {c['description']} [{c['evaluator']}]" for c in g.criteria),
             f"Horizon: {hz}"]
    if g.targets:
        lines.append("Targets the user stated: " + "; ".join(f"{t.get('text')} (\"{t.get('quote')}\")"
                                                         for t in g.targets))
    if g.assumptions:
        lines.append("Assumptions: " + "; ".join(g.assumptions))
    if g.constraints:
        lines.append("User constraints: " + "; ".join(g.constraints))
    if g.open_questions:
        lines.append("Open questions (only ask if really needed): " + "; ".join(g.open_questions))
    if g.guards:
        lines.append("Guard (the host checks these periodically, and stops the goal if one trips): "
                     + "; ".join(f"{x.get('id')} {x.get('description')}" for x in g.guards))
    lines.append(_NOTE.format(budget=g.budget_calls))
    return "\n".join(lines)


def _hold_until() -> float:
    """Lập hay cập nhật trong lượt chat: lịch việc nền giữ tới khi host bàn giao cuối lượt (review pilot lần 3), để
    việc nền không chen vào khi bộ não còn đang viết. Lượt bị cắt thì lịch tự tới hạn sau HANDOFF_HOLD_S."""
    import time
    import resonance as R
    return time.time() + R.HANDOFF_HOLD_S


_PLAIN = " Do not set a goal; answer the user normally."


def _scope_note(store, p, g, mref: str) -> str:
    """A4: phạm vi ghi của revision này và mã bàn giao (`handoff`) của lượt, để bộ não nộp sản phẩm qua
    javis_submit_deliverable và nói ĐÚNG với người dùng. Javis không cấp quyền ghi từ lời chat: đích mới luôn chờ
    chủ dự án bấm Cho phép trên thẻ."""
    try:
        import resonance as R
        sc = store.scope_state(p, g.id)
        b = store.turn_binding(p, g.id, g.revision, mref)
    except Exception:  # noqa: BLE001
        return ""
    path = R._deliverable_rel(g)
    st = sc.get("state")
    lines = []
    if st == "granted":
        lines.append(f"Write scope: allowed for {path}.")
    elif st == "pending":
        lines.append(f"Write scope: NOT allowed yet. The goal card will ask the project owner whether writing to {path} is allowed. "
                     "Say exactly that; do not say it was written or will be written automatically. What you submit now is only kept as a draft; "
                     "when the project owner clicks Allow, Jarvis 007 publishes exactly that version.")
    elif st in ("revoked", "denied", "missing"):
        lines.append("Write scope: no write permission right now (the project owner revoked it or has not allowed it).")
    if b is not None and b.get("status") == "live" and path:
        lines.append(f"Handoff code for this turn: handoff={b['id']}. To submit the deliverable, call javis_submit_deliverable "
                     f"with path={path}, content as the FULL TEXT, and this handoff. Do not Write directly to the target file.")
    return ("\n" + "\n".join(lines)) if lines else ""


def _turn(vault_root):
    """Danh tính của lời gọi, CHỈ từ ngữ cảnh lượt do host gắn: (store, agent, session_id, msg_id, user_text), hoặc
    chuỗi lỗi. Không nhận agent hay phiên từ tham số của model. Lời người dùng đọc từ sổ lượt theo ĐÚNG khoá
    (web:<phiên>, id tin) của ngữ cảnh, là bản lời host đã dùng cho lượt này."""
    import luot_dang_chay
    import resonance as R
    import resonance_store as RS
    import turn_context
    t = turn_context.current()
    if t is None:
        return ("ERROR: Could not identify the chat turn calling this tool (this engine did not carry the turn context to "
                "Jarvis 007)." + _PLAIN)
    ag = t.get("agent") or {}
    if not ag.get("key"):
        return ("ERROR: Resonance is only available in a conversation with an assistant that has Resonance enabled (Partners page)."
                + _PLAIN)
    sid, mid = str(t.get("session_id") or ""), int(t.get("message_id") or 0)
    if not sid or mid <= 0:
        return "ERROR: This turn has no user message id." + _PLAIN
    if not _store_exists():
        return "ERROR: No assistant has Resonance enabled yet." + _PLAIN
    store = RS.GoalStore()
    _a, why = R.agent_gate(store, _brain_id(vault_root), ag["key"], ag.get("config_version"))
    if why:
        return (f"ERROR: Resonance for this assistant is off or was just changed ({why}). The project owner can turn it back on in the Partners page, "
                "then send the message again." + _PLAIN)
    text = luot_dang_chay.loi_cua_luot(f"web:{sid}", mid, vault_root)
    if text is None:
        return "ERROR: The chat turn for this message is no longer running." + _PLAIN
    return store, ag, sid, mid, text, t.get("authority_seq")


async def javis_goal(args, ctx):
    import resonance as R
    import resonance_store as RS
    args = args or {}
    vault = getattr(ctx, "vault_root", None)
    op = str(args.get("op") or "").strip().lower()
    if op not in ("create", "update", "list"):
        return "ERROR: op must be create, update or list."
    if not vault:
        return "ERROR: Could not identify the brain." + _PLAIN
    turn = _turn(vault)
    if isinstance(turn, str):
        return turn
    store, ag, sid, mid, user_text, aseq = turn
    p = RS.Principal("agent", ag["key"], _brain_id(vault))
    if op == "list":
        goals = store.list_open(p, agent_key=ag["key"])
        if not goals:
            return "This assistant has no open goals yet."
        return "\n\n".join(_summary(g, "Goal") for g in goals[:10])
    mref = R.message_ref(sid, mid)
    constraints = [str(x) for x in (args.get("constraints") or []) if str(x).strip()]
    unsure = bool(args.get("user_unsure"))
    if op == "create":
        deps = R.GoalDeps(engine_factory=lambda s, t: (None, {"blocked": "the tool does not call a model"}),
                          budget=R.CallBudget(0), store=store)
        try:
            g = await R.form_goal(mref, {"principal": p, "brain_root": vault, "session_id": sid, "message_id": mid,
                                         "user_text": user_text, "constraints": constraints,
                                         "proposal": _proposal(args), "user_unsure": unsure,
                                         "hold_until": _hold_until(), "agent_key": ag["key"],
                                         "agent_version": ag.get("config_version"), "authority_seq": aseq}, deps)
        except R.GoalRejected as e:
            return f"ERROR: Could not set the goal: {e}. Fix the proposal and call again, or answer normally if this does not need follow-up after the chat turn."
        except RS.AgentStateError as e:
            return f"ERROR: Resonance for this assistant was just turned off or changed ({e})." + _PLAIN
        if g.agent_key != ag["key"]:
            # Tin này đã có mục tiêu từ trước mà không thuộc trợ lý của lượt: không trả nó ra, không ghi gì thêm.
            return "ERROR: This message is already attached to a goal that does not belong to this assistant." + _PLAIN
        return _summary(g, "Goal created") + _scope_note(store, p, g, mref)
    gid = str(args.get("goal_id") or "")
    try:
        exp = int(args.get("expected_revision"))
    except (TypeError, ValueError):
        return "ERROR: update needs expected_revision (the revision number you are currently seeing)."
    cur = store.get(p, gid)
    if cur is None or cur.agent_key != ag["key"]:
        # Kiểm TRƯỚC khi đọc hay so gì: mục tiêu của agent khác trả lời như không tồn tại, không lộ nội dung.
        return "ERROR: This goal is not among the assistant's goals. Call op=list to see them."
    try:
        # Đọc revision hiện tại trước khi kiểm: hạn và chỉ tiêu người dùng nêu ở tin trước được giữ nguyên.
        g, relation, kept = R.revise_goal(store, p, gid, exp, _proposal(args), {
            "message_ref": mref, "session_id": sid, "message_id": mid, "user_text": user_text,
            "constraints": constraints, "user_unsure": unsure, "reason": args.get("reason"),
            "hold_until": _hold_until(), "agent_key": ag["key"], "agent_version": ag.get("config_version"),
            "authority_seq": aseq})
    except RS.ConflictError as e:
        return f"ERROR: The goal was changed earlier ({e}). Call op=list to see the current revision."
    except RS.ScopeError as e:
        return f"ERROR: {e}."
    except RS.AgentStateError as e:
        return f"ERROR: Resonance for this assistant was just turned off or changed ({e})." + _PLAIN
    except R.GoalRejected as e:
        return f"ERROR: Could not update the goal: {e}."
    if relation == "none":
        out = _summary(g, "NO changes were applied, the goal stays as it was")
    else:
        out = _summary(g, "Goal updated")
    out += _scope_note(store, p, g, mref)
    if kept:
        out += ("\nThe host kept the old instructions; the following were NOT applied (this version does not support them yet). Tell the user plainly they could not be changed, "
                "and do not report them as changed:\n" + "\n".join("- " + k for k in kept))
    return out


_DESC = (
    "Create or update a durable GOAL (Resonance system). op=create ONLY when the user hands over responsibility for "
    "pursuing a result AFTER this chat turn (do it, self-check, fix from feedback, maintain, monitor, wait for an event, keep the work "
    "open until it is met) and you can state how to tell it is done (criteria) and the horizon (horizon). Do NOT call it for: "
    "questions, advice, planning, work finished within this turn, or a plan you proposed yourself. One-off "
    "background work that ends your responsibility once done: javis_task. Reminders at a fixed time: "
    "javis_schedule. relevant_quote must quote the user's words VERBATIM. Do not invent deadlines or targets: "
    "if the user gave no deadline, use horizon.kind=review (an internal review point). If the user says they do not know what they want, "
    "set user_unsure=true, stage=discovery. When the user adds something to an open goal: op=update with goal_id "
    "and expected_revision (see it with op=list); send only the changed fields, omitted fields stay as they were. This version "
    "CANNOT yet change or drop a deadline, target or constraint the user already stated: the host keeps them and reports back; in "
    "that case tell the user plainly that you cannot change them, and that they can remove them with the Remove button on the goal card in the chat. "
    "Adding new targets or constraints is fine."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": ["create", "update", "list"]},
        "understanding": {"type": "string", "description": "The result to produce, one sentence. Empty if not clear yet."},
        "criteria": {"type": "array", "description": "How to tell it is done. At least one item.", "items": {
            "type": "object", "properties": {
                "description": {"type": "string",
                                "description": "What to check, specific. The host rejects it if empty."},
                "evaluator": {"type": "string", "enum": ["artifact_contract", "human_confirmation"]},
                "params": {"type": "object", "description": "artifact_contract: path (relative to the brain), "
                                                            "min_chars, must_contain"}},
            "required": ["description", "evaluator"]}},
        "relevant_quote": {"type": "string", "description": "Quote a passage of the user's words verbatim as the basis."},
        "horizon": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["deadline", "review", "event", "maintain"]},
            "at_iso": {"type": "string", "description": "ISO 8601 time for deadline/review."},
            "from_user": {"type": "boolean"},
            "quote": {"type": "string", "description": "Quote where the user stated the deadline (required for deadline)."},
            "event": {"type": "string"},
            "reason": {"type": "string"}}},
        "stage": {"type": "string", "enum": ["discovery", "delivery"]},
        "mode": {"type": "string", "enum": ["achieve", "maintain"]},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"},
                        "description": "Constraints the user stated (for example: delete nothing)."},
        "targets": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "quote": {"type": "string"}}}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "guards": {"type": "array", "description": "Protective conditions the host checks periodically in code; if one trips, "
                   "the goal stops and the user is told. Example, for the constraint 'do not delete the old note': artifact_contract with "
                   "the path of that note.", "items": {"type": "object", "properties": {
                       "description": {"type": "string"},
                       "evaluator": {"type": "string", "enum": ["artifact_contract"]},
                       "params": {"type": "object"}}, "required": ["description", "evaluator"]}},
        "user_unsure": {"type": "boolean"},
        "goal_id": {"type": "string"},
        "expected_revision": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["op"],
}


_SUBMIT_MSG = {
    "no_turn": "Could not identify the chat turn making the call (this engine did not carry the turn context to Jarvis 007).",
    "not_agent_turn": "Submitting is only possible in a conversation with an assistant that has Resonance enabled.",
    "invalid_content": "content must be the full text of the deliverable, not empty.",
    "path_rejected": "Target path not accepted (outside the brain, contains . or .., extension is not .md/.txt, or a forbidden folder).",
    "too_large": "The deliverable is over 1MB.",
    "no_open_handoff": "This turn has no goal waiting for handoff (create or update a goal with javis_goal first).",
    "path_not_in_scope": "This path is not a deliverable of a goal in this turn.",
    "ambiguous_handoff": "Several goals share this target in this turn; include the handoff returned by javis_goal.",
    "submission_conflict": "This submission key was already used for different content.",
    "turn_closed": "The handoff turn is closed; new submissions are not accepted.",
    "grant_revoked": "The project owner revoked the permission for this goal.",
    "scope_decided": "The project owner already decided the scope; nothing more can be submitted in this turn.",
    "revision_changed": "The goal moved to another revision; submit with the new handoff.",
    "agent_changed": "The assistant switch just changed; the submission is not accepted.",
    "storage_error": "Jarvis 007 could not save the submission; try again later.",
}


async def javis_submit_deliverable(args, ctx):
    """A4 (mục 4.3): nộp TOÀN VĂN sản phẩm cho mục tiêu lượt này vừa lập hay cập nhật. Host tự đọc, băm, lưu bản nộp có
    biên nhận và tự đăng vào đích cuối lượt khi có quyền; chưa có quyền thì giữ làm nháp chờ chủ dự án. Model không
    truyền được mục tiêu, trợ lý hay quyền."""
    import resonance as R
    import resonance_store as RS
    import turn_context
    vault = getattr(ctx, "vault_root", None)
    if not vault or not _store_exists():
        return "ERROR: No assistant has Resonance enabled yet."
    deps = R.deps_for(_brain_id(vault))
    if deps is None:
        deps = R.GoalDeps(engine_factory=lambda s, t: (None, {}), budget=R.CallBudget(0), store=RS.GoalStore(),
                          principal=RS.Principal("agent", "javis", _brain_id(vault)), brain_root=_brain_id(vault))
    # Ghi file nháp, bằng chứng và SQLite chạy ở luồng phụ (thiết kế A4 mục 11), không giữ event loop. Danh tính lượt
    # đọc NGAY ở đây rồi truyền vào, không dựa vào việc chép ngữ cảnh.
    import asyncio
    res = await asyncio.to_thread(R.submit_deliverable, turn_context.current(), dict(args or {}), deps)
    if not res.get("ok"):
        code = res.get("code") or "storage_error"
        extra = ""
        if res.get("handoffs"):
            extra = " Handoffs: " + ", ".join(f"{h['handoff']} (goal {h['goal_id']})" for h in res["handoffs"])
        return f"ERROR {code}: {_SUBMIT_MSG.get(code, code)}{extra}"
    st = res["status"]
    what = {"candidate": "waiting for the host to publish to the target file at the end of the turn",
            "awaiting_scope": "kept as a DRAFT; the target file is not allowed yet, and when the project owner clicks Allow, Jarvis 007 publishes exactly "
                              "this version",
            "published": "published"}.get(st, st)
    return (f"Submission {res['submission_id']} received (sha256 {res['sha256'][:12]}, {res['size']} bytes): {what}."
            + (" This is the earlier receipt for the same content." if res.get("replay") else "")
            + " Do not tell the user the file was written until the host has finished publishing.")


_SUBMIT_DESC = (
    "Submit the FULL TEXT of the deliverable for the goal this turn just created or updated with javis_goal. Use it instead of writing directly "
    "to the target file: the host saves the submission with a receipt, publishes it to the target file once the project owner has allowed the scope, and "
    "does not overwrite user files. path is the goal's deliverable path (relative to the brain), content is the entire "
    "text, handoff is the code javis_goal returned (required when the turn has several goals sharing a target). Resubmitting the same content returns the "
    "earlier receipt.")

_SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Deliverable path of the goal, relative to the brain."},
        "content": {"type": "string", "description": "Full text of the deliverable."},
        "handoff": {"type": "string", "description": "Handoff code returned by javis_goal."},
        "submission_key": {"type": "string", "description": "Key to prevent duplicate submissions, optional."},
    },
    "required": ["path", "content"],
}


def register(ctx):
    ctx.register_tool(name="javis_goal", description=_DESC, handler=javis_goal, min_mode="safe",
                      schema=_SCHEMA, visible_fn=_visible)
    ctx.register_tool(name="javis_submit_deliverable", description=_SUBMIT_DESC, handler=javis_submit_deliverable,
                      min_mode="safe", schema=_SUBMIT_SCHEMA, visible_fn=_visible)
