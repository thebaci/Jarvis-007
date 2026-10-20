"""Bộ chiếu phản hồi (outbox của reaction, T2 0.154.0). Thiết kế 2026-10-15 mục 3.3, 3.5, 4.3.

Ghi reaction (kho của reaction: `conversations.db` cho chat riêng, `team.sqlite3` cho nhóm) kèm `effect_state = 'pending'`
trên dòng nhật ký. Bộ chiếu áp tác động sang `resonance.sqlite3` (không có giao dịch xuyên kho):

- Idempotent theo `source_ref` (`rx:dm:<log_id>`, `rx:team:<log_id>`): UNIQUE ở `agent_wake_sources`, INSERT OR IGNORE ở
  `wake_reasons` của A2. Chạy lại sau lỗi giữa chừng không tạo tác động kép.
- Mỗi cặp (tin, người phản hồi) chiếu theo đúng thứ tự mã nhật ký; dòng `pending` đã có dòng mới hơn của cùng cặp thì chỉ
  áp TRẠNG THÁI RÒNG của dòng mới nhất, các dòng cũ đánh `superseded`. Đổi hay bỏ thì nguồn cũ trong lý do còn chờ bị gỡ.
- Định tuyến (3.3): reaction trên tin gắn goal chỉ tạo lý do `feedback` của goal ở A2; tin không gắn goal tạo lý do
  `reaction_review` ở lớp 3 (ngữ cảnh `team:<id>` hay `dm:<agent_key>`). Chỉ khi agent tác giả bật Cộng hưởng và sự
  kiện sau `resumed_at`; Cộng hưởng tắt thì `stored_only`. Câu trả lời ở trang Trò chuyện chính (không agent): `received`.
  Reaction của agent (trưởng nhóm, thành viên) không bao giờ tạo lý do và không vào ước lượng hữu ích.
- Trạng thái hiển thị trên reaction do bộ chiếu ghi ngược theo trạng thái lý do (`refresh`).
- Chạy ngay sau khi ghi (lỗi thì nuốt và ghi log, dòng giữ `pending`), mỗi nhịp và lúc khởi động cho mọi dòng còn chờ.

Emoji là cảm xúc: bộ chiếu không chốt đạt, không đổi ưu tiên, không cấp quyền, không đổi trạng thái việc hay goal.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable, Optional

import reaction_values as RV

log = logging.getLogger("javis.feedback_projector")

REVIEW_CODE = "reaction_review"
A2_CODE = "feedback"
OPEN_STATUSES = ("pending_review", "reviewing")
FEEDBACK_LIMIT = 5
FEEDBACK_DAYS = 30
FEEDBACK_EXCERPT = 160
# Câu dặn đi kèm khối phản hồi ở chat riêng (gửi model, không dịch). Cùng ý với FEEDBACK_NOTE của nhóm.
DM_FEEDBACK_NOTE = ("An emoji is the owner's feeling, possibly about the event being described; do not treat it as a grade or a command. Adjust "
                    "only for quality reasons, the speak/stay-silent axis and written feedback. If unclear, keep your approach.")


def _chu(vi: str, en: str) -> str:
    try:
        import localefmt
        return localefmt.chu(vi, en)
    except Exception:  # noqa: BLE001
        return vi


_LOCKS: dict = {}   # khoá cặp -> [Lock, số người đang dùng]
_LOCKS_GUARD = threading.Lock()


class _pair_lock:
    """Khoá theo cặp (tin, người phản hồi) trong tiến trình, có đếm người dùng: chỉ dọn khoá không ai đang giữ HAY đang chờ,
    nên không có khe "lấy khoá rồi bị dọn trước khi acquire" làm hai lần chiếu cùng cặp chạy song song (review T2 vòng 2)."""

    def __init__(self, key: str):
        self.key = key

    def __enter__(self):
        with _LOCKS_GUARD:
            ent = _LOCKS.get(self.key)
            if ent is None:
                if len(_LOCKS) > 5000:
                    for k in [k for k, v in _LOCKS.items() if v[1] == 0][:2500]:
                        _LOCKS.pop(k, None)
                ent = _LOCKS[self.key] = [threading.Lock(), 0]
            ent[1] += 1
        ent[0].acquire()
        self._ent = ent
        return self

    def __exit__(self, *exc):
        self._ent[0].release()
        with _LOCKS_GUARD:
            self._ent[1] -= 1
        return False


def source_ref(kind: str, log_id: int) -> str:
    return f"rx:{kind}:{int(log_id)}"


def group_ref(kind: str, session_id: str, message_id: int, reactor: str) -> str:
    return f"{kind}:{session_id}:{int(message_id)}:{reactor}"


class FeedbackProjector:
    """`resonance`, `sessions`, `teams`: hàm trả kho (hay None khi chưa có kho). `team_view(team_id, session_id, mid)`:
    tin nhóm đã gắn reaction cho gói WS `team_message`. Mọi phương thức trả danh sách gói WS cần đẩy (người gọi đẩy)."""

    def __init__(self, *, resonance: Callable[[], Any], sessions: Optional[Callable[[], Any]] = None,
                 teams: Optional[Callable[[], Any]] = None,
                 team_view: Optional[Callable[[str, str, int], Optional[dict]]] = None,
                 clock: Callable[[], float] = time.time,
                 judge_label: Optional[Callable[..., Any]] = None):
        self._resonance = resonance
        # T3 phần J (0.156.0): `agent_judge.label` (trục nói/im của reaction dạy bộ phán xử). None: chỉ lưu như T2.
        self._judge_label = judge_label
        self._sessions = sessions or (lambda: None)
        self._teams = teams or (lambda: None)
        self._team_view = team_view
        self.clock = clock

    # ───────────── điểm nối cho T3 ─────────────

    def record_pulse_signal(self, kind: str, log_row: dict, agent_key: str, context_ref: str) -> Optional[dict]:
        """T3 (thiết kế 6.1, 6.3, 6.5): ghi tín hiệu hữu ích (`pulse_signals`, UNIQUE `(source_ref, agent_key)`) của một
        reaction HỢP LỆ của chủ (Cộng hưởng bật, sau `resumed_at`; bộ chiếu đã lọc trước khi gọi) rồi đánh thức nhịp của
        agent ở ngữ cảnh đó (`min(bậc, B3)`). Lý do chất lượng thắng emoji; chỉ trục nói/im hay chỉ góp ý thì không có tín
        hiệu (vẫn thức). Reaction trên BẢN TỔNG HỢP của việc nhóm được phân bổ theo tập đầu vào host đã ghi cho bước tổng
        hợp (`team_steps.input_refs`); tác giả tổng hợp không có thêm tín hiệu trực tiếp riêng. Idempotent. Lỗi kho nhịp
        không làm hỏng lần chiếu (nuốt, ghi log). Trả {"signal": bool, "alloc": {...}} hay None."""
        try:
            return self._record_pulse_signal(kind, log_row, agent_key, context_ref)
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse signal %s %s: %s: %s", kind, log_row.get("id"), type(ex).__name__, ex)
            return None

    def _record_pulse_signal(self, kind: str, log_row: dict, agent_key: str, context_ref: str) -> Optional[dict]:
        res = self._resonance()
        if res is None or not agent_key or str(log_row.get("source_kind") or "owner") != "owner":
            return None
        import agent_pulse as AP
        nxt = self._next_state(kind, log_row)
        if nxt is None:
            return None
        src = source_ref(kind, log_row["id"])
        value, reasons = nxt.get("value"), list(nxt.get("reasons") or [])
        sig = AP.reaction_signal(value, reasons)
        at = float(log_row.get("created_at") or self.clock())
        subject = f"{kind}:{log_row['session_id']}:{int(log_row['message_id'])}"
        reactor = str(log_row.get("reactor") or "owner")
        out = {"signal": False, "alloc": {}}
        if sig is not None:
            chain = self._synthesis_inputs(log_row) if kind == "team" else None
            if chain is not None:
                out["alloc"] = AP.record_contrib(res, source_ref=src, result_ref=chain[0], synth=agent_key,
                                                 inputs=chain[1], context_ref=context_ref, value=value, reasons=reasons,
                                                 reactor=reactor, at=at, subject_ref=subject, signal=sig)
                out["signal"] = bool(out["alloc"])
            else:
                out["signal"] = AP.record_reaction(res, source_ref=src, agent_key=agent_key, context_ref=context_ref,
                                                   value=value, reasons=reasons, reactor=reactor, at=at,
                                                   subject_ref=subject)
                out["alloc"] = {agent_key: 1.0}
        AP.wake(res, agent_key, context_ref, "reaction", at=at)
        return out

    def _synthesis_inputs(self, log_row: dict) -> Optional[tuple]:
        """Tin được phản hồi là kết quả của một bước `synthesize`: (result_ref, [agent của từng mục trong tập đầu vào host
        đã đưa cho bước đó]). Chỉ một tầng: trích dẫn, chuyển tiếp, tổng hợp nhiều tầng không nhân điểm. Không phải bản
        tổng hợp: None."""
        tm = self._teams()
        task_id = log_row.get("task_id")
        if tm is None or not task_id:
            return None
        steps = tm.steps(task_id)
        mid = int(log_row["message_id"])
        synth = next((s for s in steps if s.get("kind") == "synthesize" and s.get("result_msg_id") == mid), None)
        if synth is None:
            return None
        by_msg = {s.get("result_msg_id"): s for s in steps if s.get("result_msg_id") and s is not synth}
        inputs = [by_msg[ref]["agent_key"] for ref in (synth.get("input_refs") or []) if ref in by_msg]
        return f"step:{synth['step_id']}", inputs

    def record_task_event(self, event: str, *, context_ref: str, agents: dict, source_ref_: str,
                          subject_ref: str = "", wake_why: str = "") -> list:
        """Tín hiệu từ sự kiện host của việc (chấp nhận đề xuất, chốt quyết định, sửa yêu cầu sau kết quả, huỷ), chỉ cho
        agent đang bật Cộng hưởng. `agents`: {agent_key: share}. Lỗi kho không làm hỏng thao tác của chủ (nuốt, ghi log)."""
        try:
            res = self._resonance()
            if res is None or not agents:
                return []
            import agent_pulse as AP
            on = {}
            for key, share in agents.items():
                a = res.agent_any(key) if key else None
                if a and a.get("status") == "active" and a.get("enabled") and share > 0:
                    on[key] = float(share)
            if not on:
                return []
            total = sum(on.values())
            on = {k: v / total for k, v in on.items()}
            done = AP.record_host_event(res, event=event, source_ref=source_ref_, agents=on, context_ref=context_ref,
                                        subject_ref=subject_ref)
            if wake_why:
                for key in on:
                    AP.wake(res, key, context_ref, wake_why)
            return done
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse task event %s %s: %s: %s", event, source_ref_, type(ex).__name__, ex)
            return []

    def pulse_wake(self, agent_key: str, context_ref: str, why: str) -> bool:
        """Thức lại nhịp lớp 3 (5.2) khi chủ gọi trực tiếp hay giao việc mới. Tạm dừng, tắt: không đổi gì. Lỗi nuốt."""
        try:
            res = self._resonance()
            if res is None or not agent_key:
                return False
            import agent_pulse as AP
            return AP.wake(res, agent_key, context_ref, why)
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse wake %s %s: %s", agent_key, context_ref, ex)
            return False

    def pulse_proposal_decided(self, context_ref: str, message_id: int, decision: str, task_id: str = "") -> None:
        """Thẻ đề xuất trong nhóm do lượt quét tạo được chủ quyết ở thẻ: cập nhật sổ đề xuất của nhịp (không ghi tín hiệu
        lần hai: thẻ nhóm đã ghi theo nguồn của nó)."""
        try:
            res = self._resonance()
            if res is None:
                return
            import agent_pulse as AP
            prop = AP.proposal(res, context_ref=context_ref, message_id=int(message_id))
            if prop is not None and prop["status"] == "pending":
                AP.decide_proposal(res, prop["id"], decision, by="owner", task_id=task_id, signal=False)
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse proposal %s %s: %s", context_ref, message_id, ex)

    def void_task_event(self, source_ref_: str) -> None:
        """Chủ gỡ một sự kiện đã ghi (bỏ ghim quyết định): tín hiệu của nguồn đó thành `void`."""
        try:
            res = self._resonance()
            if res is not None:
                import agent_pulse as AP
                AP.void_signal(res, source_ref_)
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse void %s: %s", source_ref_, ex)

    def record_judge_label(self, kind: str, log_row: dict, agent_key: str, axis: str) -> Optional[dict]:
        """T3 phần J: trục "Đáng lẽ nên nói" / "Nên im (chen ngang)" của reaction CỦA CHỦ trên tin của agent tới
        `agent_judge.label` (nguồn `reaction`, thời điểm là lúc thả). Trục trống là bỏ nhãn do reaction đặt (nhãn chủ sửa
        trong lịch sử quyết định giữ nguyên). Bộ phán xử tự quyết hiệu lực: chỉ dịch ngưỡng khi Cộng hưởng bật và nhãn sau
        `resumed_at`; không có quyết định nào sinh ra tin này (lời trả lời trực tiếp ở chat riêng) thì không làm gì."""
        if self._judge_label is None or not agent_key:
            return None
        try:
            return self._judge_label(f"msg:{int(log_row['message_id'])}", axis or None, "owner",
                                     at=float(log_row.get("created_at") or self.clock()), source="reaction")
        except Exception as ex:  # noqa: BLE001 - nhãn phán xử hỏng không được làm hỏng việc chiếu reaction
            log.warning("feedback projector judge label %s failed: %s: %s", kind, type(ex).__name__, ex)
            return None

    # ───────────── kho ─────────────

    def _store(self, kind: str):
        return self._sessions() if kind == "dm" else self._teams()

    def _log_row(self, kind: str, log_id: int) -> Optional[dict]:
        st = self._store(kind)
        if st is None:
            return None
        return st.dm_reaction_log_row(log_id) if kind == "dm" else st.reaction_log_row(log_id)

    def _pair(self, kind: str, row: dict) -> list:
        st = self._store(kind)
        return (st.dm_pair_logs(row["session_id"], row["message_id"], row["reactor"]) if kind == "dm"
                else st.pair_logs(row["session_id"], row["message_id"], row["reactor"]))

    def _mark(self, kind: str, ids: list, state: str, refs: Optional[dict] = None) -> None:
        st = self._store(kind)
        if kind == "dm":
            st.mark_dm_reaction_effects(ids, state, refs)
        else:
            st.mark_reaction_effects(ids, state, refs)

    def _reaction(self, kind: str, row: dict) -> Optional[dict]:
        st = self._store(kind)
        return (st.dm_reaction_of(row["session_id"], row["message_id"], row["reactor"]) if kind == "dm"
                else st.reaction_of(row["session_id"], row["message_id"], row["reactor"]))

    def _set_status(self, kind: str, row: dict, log_id: Optional[int], status: str, reason: str) -> Optional[dict]:
        st = self._store(kind)
        if kind == "dm":
            return st.set_dm_reaction_status(row["session_id"], row["message_id"], row["reactor"], log_id, status,
                                             reason)
        return st.set_reaction_status(row["session_id"], row["message_id"], row["reactor"], log_id, status, reason)

    def _event(self, kind: str, row: dict) -> Optional[dict]:
        """Gói WS sau khi host đổi trạng thái: `chat_reaction` (chat riêng) hay `team_message` (nhóm)."""
        if kind == "dm":
            if row.get("reactor") != "owner":
                return None
            st = self._sessions()
            cur = st.dm_reaction_of(row["session_id"], row["message_id"]) if st else None
            return {"type": "chat_reaction", "session_id": row["session_id"], "message_id": int(row["message_id"]),
                    "reaction": RV.public(cur)}
        if self._team_view is None:
            return None
        msg = self._team_view(row.get("team_id") or "", row["session_id"], int(row["message_id"]))
        if not msg:
            return None
        return {"type": "team_message", "team_id": row.get("team_id") or "", "message": msg}

    # ───────────── chiếu ─────────────

    def project(self, kind: str, log_id: int) -> list:
        """Chiếu MỘT dòng nhật ký (và mọi dòng chờ của cùng cặp). Lỗi thì ghi log, dòng giữ `pending` để nhịp sau chiếu
        lại; không bao giờ ném ra ngoài (ghi reaction đã xong, lỗi tác động không được làm hỏng request)."""
        try:
            return self._project(kind, int(log_id))
        except Exception as ex:  # noqa: BLE001
            log.warning("feedback projector: %s log %s failed: %s: %s", kind, log_id, type(ex).__name__, ex)
            return []

    def _project(self, kind: str, log_id: int) -> list:
        row = self._log_row(kind, log_id)
        if row is None:
            return []
        # Một khoá cho mỗi cặp (tin, người phản hồi) trong tiến trình (review T2 P3): request và nhịp, hay hai lần đổi
        # nhanh, không chiếu xen nhau (đọc cặp cũ rồi thêm nguồn cũ SAU khi lần chiếu mới đã gỡ nó). Đọc lại cặp TRONG khoá.
        with _pair_lock(group_ref(kind, row["session_id"], row["message_id"], row["reactor"])):
            return self._project_locked(kind, row)

    def _project_locked(self, kind: str, row: dict) -> list:
        pair = self._pair(kind, row)
        if not pair:
            return []
        newest = pair[-1]
        older_pending = [x["id"] for x in pair[:-1] if x.get("effect_state") == "pending"]
        if older_pending:
            self._mark(kind, older_pending, "superseded", {"superseded_by": source_ref(kind, newest["id"])})
        if newest.get("effect_state") != "pending":
            return []
        older = [x["id"] for x in pair[:-1]]
        refs = self._apply(kind, newest, older)
        # T3 (6.3): đổi hay bỏ reaction thì tín hiệu của các lần cũ cùng cặp chuyển `superseded_by` lần mới nhất.
        self._supersede_signals(kind, newest, older)
        # Đổi hay bỏ: nguồn cũ của cùng cặp trong lý do còn chờ bị gỡ SAU khi nguồn mới đã vào (lý do không bị chốt
        # `superseded` giữa chừng chỉ vì đang thay nguồn).
        self._drop_old(kind, newest, older)
        self._mark(kind, [newest["id"]], "done", refs)
        ev = self._event(kind, newest)
        return [ev] if ev else []

    def _next_state(self, kind: str, row: dict) -> Optional[dict]:
        if kind == "dm":
            return row.get("next")
        st = {"value": row.get("value"), "reasons": row.get("reasons") or [], "axis": row.get("axis") or "",
              "comment": row.get("comment") or ""}
        return None if RV.is_empty(st) else st

    def _context_of(self, kind: str, row: dict, agent_key: str) -> str:
        return f"team:{row.get('team_id') or ''}" if kind == "team" else f"dm:{agent_key}"

    def _brain_of(self, kind: str, row: dict) -> str:
        if kind == "team":
            tm = self._teams()
            team = tm.get(row.get("team_id") or "") if tm is not None else None
            return (team or {}).get("brain_id") or ""
        return ""

    def _apply(self, kind: str, row: dict, older_ids: list) -> dict:
        """Áp trạng thái ròng của dòng mới nhất một cặp. Trả `effect_refs` (bằng chứng tác động)."""
        src = source_ref(kind, row["id"])
        grp = group_ref(kind, row["session_id"], row["message_id"], row["reactor"])
        old_refs = [source_ref(kind, i) for i in older_ids]
        agent_key = str(row.get("agent_key") or "")
        goal_id = str(row.get("goal_id") or "") if kind == "dm" else ""
        res = self._resonance() if (agent_key or goal_id) else None
        nxt = self._next_state(kind, row)
        if str(row.get("source_kind") or "owner") == "owner" and agent_key:
            self.record_judge_label(kind, row, agent_key, str((nxt or {}).get("axis") or ""))
        if nxt is None:
            return {"route": "cleared", "source_ref": src, "removed": old_refs}
        source_kind = str(row.get("source_kind") or "owner")
        if source_kind != "owner":
            # Reaction của agent: góp ý cộng tác, không tạo lý do, không vào ước lượng hữu ích (chống tự thưởng).
            self._set_status(kind, row, row["id"], "received", "")
            return {"route": "agent_reaction", "source_ref": src}
        if not agent_key:
            # Trang Trò chuyện chính (tác giả là Javis): lưu và hiện, không vào học hay phán xử của agent nào.
            self._set_status(kind, row, row["id"], "received", "")
            return {"route": "none", "source_ref": src}
        ctx = self._context_of(kind, row, agent_key)
        agent = res.agent_any(agent_key) if res is not None else None
        on = bool(agent and agent.get("status") == "active" and agent.get("enabled"))
        resumed = res.resumed_at(agent_key, ctx) if (res is not None and on) else None
        if not on or (resumed is not None and float(row.get("created_at") or 0) < float(resumed)):
            # Nhãn "Đã nhận, chỉ lưu" do giao diện dịch; lý do nói ĐÚNG vì sao (tắt, hay có trước lúc bật lại), không lặp nhãn.
            why = (_chu("Cộng hưởng của trợ lý đang tắt", "The assistant's Resonance is off") if not on else
                   _chu("Phản hồi có trước lúc bật lại Cộng hưởng", "Sent before Resonance was turned back on"))
            self._set_status(kind, row, row["id"], "stored_only", why)
            return {"route": "stored_only", "source_ref": src, "agent_key": agent_key}
        if goal_id:
            g = res.goal_brain(goal_id)
            if g is None or g.get("status") != "active":
                self._set_status(kind, row, row["id"], "no_change",
                                 _chu("Mục tiêu đã kết thúc", "The goal has already ended"))
                return {"route": "a2_closed", "source_ref": src, "goal_id": goal_id}
            import resonance_store as RS
            res.add_reason_event(RS.Principal("agent", "javis", g["brain_id"]), goal_id, A2_CODE, src)
            self.record_pulse_signal(kind, row, agent_key, ctx)
            refs = {"route": "a2", "source_ref": src, "goal_id": goal_id, "agent_key": agent_key}
            self._sync_one(kind, row, refs)
            return refs
        from agent_ledger import WakeReasons
        rid = WakeReasons(res).add_source(agent_key, ctx, REVIEW_CODE, src, grp)
        self.record_pulse_signal(kind, row, agent_key, ctx)
        refs = {"route": "l3", "source_ref": src, "reason_id": rid, "context_ref": ctx, "agent_key": agent_key}
        self._sync_one(kind, row, refs)
        return refs

    def _supersede_signals(self, kind: str, row: dict, older_ids: list) -> None:
        if not older_ids:
            return
        try:
            res = self._resonance()
            if res is None:
                return
            import agent_pulse as AP
            by = source_ref(kind, row["id"])
            for oid in older_ids:
                AP.supersede_signal(res, source_ref(kind, oid), by)
        except Exception as ex:  # noqa: BLE001
            log.warning("pulse supersede %s %s: %s", kind, row.get("id"), ex)

    def _drop_old(self, kind: str, row: dict, older_ids: list) -> list:
        """Gỡ nguồn của các lần đổi cũ hơn của cùng cặp khỏi lý do còn chờ (lớp 3) và lý do `feedback` còn chờ (A2)."""
        if not older_ids:
            return []
        agent_key = str(row.get("agent_key") or "")
        goal_id = str(row.get("goal_id") or "") if kind == "dm" else ""
        if not (agent_key or goal_id):
            return []
        res = self._resonance()
        if res is None:
            return []
        from agent_ledger import WakeReasons
        src = source_ref(kind, row["id"])
        removed = WakeReasons(res).remove_group(group_ref(kind, row["session_id"], row["message_id"], row["reactor"]),
                                                keep=[src])
        if goal_id:
            res.supersede_reason_events(goal_id, A2_CODE, [source_ref(kind, i) for i in older_ids])
        return removed

    # ───────────── trạng thái hiển thị ─────────────

    def _status_for(self, refs: dict, prefetched: Optional[dict] = None) -> Optional[tuple]:
        """(status, status_reason) theo trạng thái lý do thật; None khi không đổi gì. `prefetched`: {source_ref: nguồn}
        đã đọc theo lô (đối soát của nhịp); nguồn vắng trong đó nghĩa là không có."""
        res = self._resonance()
        if res is None:
            return None
        route = refs.get("route")
        if route == "a2":
            st = res.reason_event_state(refs.get("goal_id") or "", A2_CODE, refs.get("source_ref") or "")
            if st == "pending":
                return "pending_review", ""
            if st == "served":
                return "no_change", _chu("Mục tiêu đã đọc phản hồi ở lượt việc kế tiếp",
                                         "The goal read this feedback on its next work turn")
            return None
        if route == "l3":
            if prefetched is not None:
                s = prefetched.get(refs.get("source_ref") or "")
            else:
                from agent_ledger import WakeReasons
                s = WakeReasons(res).source(refs.get("source_ref") or "")
            if s is None or s.get("removed_at") is not None:
                return None
            rs = s.get("reason_status")
            if rs == "pending":
                return "pending_review", ""
            if rs == "claimed":
                return "reviewing", ""
            if rs == "failed":
                return "pending_review", _chu("Lượt xem xét lỗi nhiều lần, chờ bạn bấm thử lại",
                                              "The review failed several times and waits for you to retry")
            if rs == "served" and s.get("consumed_at") is not None:
                return "no_change", ""
            return None
        return None

    def _sync_one(self, kind: str, row: dict, refs: dict, *, cur: Any = None,
                  prefetched: Optional[dict] = None) -> Optional[dict]:
        got = self._status_for(refs, prefetched)
        if got is None:
            return None
        if cur is None:
            cur = self._reaction(kind, row)
        if cur is None or int(cur.get("log_id") or 0) != int(row["id"]):
            return None
        # Trạng thái do lượt xem xét thật ghi (T3: adjusted/no_change kèm lý do) không bị bộ chiếu ghi đè bằng mặc định.
        if got[0] == "no_change" and cur.get("status") in ("adjusted", "no_change") and not got[1]:
            return None
        if (cur.get("status"), cur.get("status_reason") or "") == got:
            return None
        return self._set_status(kind, row, row["id"], got[0], got[1])

    def refresh(self, kind: str, log_ids: list) -> list:
        """Ghi ngược trạng thái của các reaction theo trạng thái lý do hiện tại (gọi khi lý do đổi trạng thái)."""
        events = []
        for lid in log_ids or []:
            try:
                row = self._log_row(kind, int(lid))
                if row is None or row.get("effect_state") != "done":
                    continue
                if self._sync_one(kind, row, row.get("effect_refs") or {}) is not None:
                    ev = self._event(kind, row)
                    if ev:
                        events.append(ev)
            except Exception as ex:  # noqa: BLE001
                log.warning("feedback projector refresh %s %s: %s", kind, lid, ex)
        return events

    # ───────────── điểm nối cho lượt xem xét reaction (T3 phần L, `agent_review`) ─────────────

    def review_source(self, src: str) -> Optional[dict]:
        """Một nguồn `rx:<kind>:<log_id>` của lý do `reaction_review`, đủ để dựng lời nhắc: tin bị phản hồi, emoji, lý do,
        trục nói/im, góp ý. `current`: lần đổi này còn là trạng thái hiện tại của reaction (đổi sau đó thì không). None
        khi nguồn không đọc được (kho chưa có, dòng đã mất)."""
        m = re.match(r"^rx:(dm|team):(\d+)$", str(src or ""))
        if not m:
            return None
        kind, log_id = m.group(1), int(m.group(2))
        row = self._log_row(kind, log_id)
        if row is None:
            return None
        nxt = self._next_state(kind, row) or {}
        cur = self._reaction(kind, row)
        text = ""
        ss = self._sessions()
        if ss is not None:
            msg = (ss.message_row(row["session_id"], int(row["message_id"])) if kind == "dm"
                   else ss.team_message(row["session_id"], int(row["message_id"])))
            text = str((msg or {}).get("content") or "")
        return {"source_ref": src, "kind": kind, "log_id": log_id, "session_id": row["session_id"],
                "message_id": int(row["message_id"]), "reactor": row["reactor"], "team_id": row.get("team_id") or "",
                "agent_key": str(row.get("agent_key") or ""), "value": nxt.get("value"),
                "reasons": list(nxt.get("reasons") or []), "axis": nxt.get("axis") or "",
                "comment": nxt.get("comment") or "", "created_at": row.get("created_at"), "message_text": text,
                "current": bool(cur and int(cur.get("log_id") or 0) == log_id),
                "status": (cur or {}).get("status") or ""}

    def set_review_status(self, src: str, status: str, reason: str = "") -> list:
        """Lượt xem xét reaction ghi trạng thái theo KẾT QUẢ HOST THẬT lên reaction của nguồn (chỉ khi reaction còn ở đúng
        lần đổi đó). Trả gói WS cần đẩy (`chat_reaction` / `team_message`)."""
        m = re.match(r"^rx:(dm|team):(\d+)$", str(src or ""))
        if not m:
            return []
        kind, log_id = m.group(1), int(m.group(2))
        row = self._log_row(kind, log_id)
        if row is None:
            return []
        got = self._set_status(kind, row, log_id, status, reason)
        if got is None:
            return []
        ev = self._event(kind, row)
        return [ev] if ev else []

    def _refresh_open(self, kind: str, st: Any, limit: int) -> Optional[list]:
        """Đối soát trạng thái của các reaction đang chờ/đang xem xét THEO LÔ (T3 hiệu năng): một câu đọc reaction, một câu
        đọc nhật ký, một câu đọc nguồn lý do, rồi CHỈ ghi những reaction có trạng thái lý do đổi. Trước đây mỗi nhịp 30
        giây đọc lại từng dòng (ba kết nối SQLite mỗi dòng, tối đa 200 dòng) dù không có gì đổi. None khi kho không có
        hàm đọc theo lô (kho giả của test cũ): người gọi dùng đường từng dòng."""
        open_rows = getattr(st, "dm_open_reaction_rows" if kind == "dm" else "open_reaction_rows", None)
        log_rows = getattr(st, "dm_reaction_log_rows" if kind == "dm" else "reaction_log_rows", None)
        if open_rows is None or log_rows is None:
            return None
        res = self._resonance()
        if res is None:
            return []
        reactions = [r for r in open_rows(OPEN_STATUSES, limit) if r.get("log_id") is not None]
        if not reactions:
            return []
        logs = log_rows([int(r["log_id"]) for r in reactions])
        todo = []
        for cur in reactions:
            row = logs.get(int(cur["log_id"]))
            if row is None or row.get("effect_state") != "done":
                continue
            todo.append((row, cur, row.get("effect_refs") or {}))
        refs_l3 = [refs.get("source_ref") for _r, _c, refs in todo if refs.get("route") == "l3"]
        from agent_ledger import WakeReasons
        W = WakeReasons(res)
        prefetched = W.sources_by_ref(refs_l3) if hasattr(W, "sources_by_ref") else None
        events = []
        for row, cur, refs in todo:
            try:
                if self._sync_one(kind, row, refs, cur=cur, prefetched=prefetched) is not None:
                    ev = self._event(kind, row)
                    if ev:
                        events.append(ev)
            except Exception as ex:  # noqa: BLE001
                log.warning("feedback projector refresh %s %s: %s", kind, row.get("id"), ex)
        return events

    def project_pending(self, limit: int = 200) -> list:
        """Nhịp và lúc khởi động: chiếu mọi dòng còn `pending` (theo thứ tự mã nhật ký), rồi ghi ngược trạng thái của
        các reaction đang chờ hay đang xem xét. Kho nào chưa có thì bỏ qua."""
        events: list = []
        for kind in ("dm", "team"):
            try:
                st = self._store(kind)
                if st is None:
                    continue
                rows = st.pending_dm_reaction_logs(limit) if kind == "dm" else st.pending_reaction_logs(limit)
                done = set()
                for row in rows:
                    pair = (row["session_id"], row["message_id"], row["reactor"])
                    if pair in done:
                        continue
                    done.add(pair)
                    events.extend(self.project(kind, row["id"]))
                bulk = self._refresh_open(kind, st, limit)
                if bulk is not None:
                    events.extend(bulk)
                    continue
                open_ids = (st.dm_open_reaction_logs(OPEN_STATUSES, limit) if kind == "dm"
                            else st.open_reaction_logs(OPEN_STATUSES, limit))
                events.extend(self.refresh(kind, open_ids))
            except Exception as ex:  # noqa: BLE001
                log.warning("feedback projector pending %s: %s: %s", kind, type(ex).__name__, ex)
        return events


# ───────────── khối phản hồi cho lượt chat riêng ─────────────

def dm_feedback_lines(sessions: Any, agent_key: str, now: Optional[float] = None, limit: int = FEEDBACK_LIMIT) -> list:
    """Mục phản hồi gần đây của CHỦ trên câu trả lời của ĐÚNG agent này ở chat riêng (ngữ cảnh `dm:<agent_key>`): tối đa
    `limit` mục trong 30 ngày, emoji gốc kèm tên loại, lý do, trục nói/im, góp ý, đoạn trích. Mục đã bỏ không còn trong kho
    nên tự rời khối. Không đọc gì của ngữ cảnh khác."""
    if not agent_key or sessions is None:
        return []
    t = time.time() if now is None else float(now)
    rows = sessions.recent_dm_feedback(agent_key, t - FEEDBACK_DAYS * 86400, limit * 3)
    msgs = sessions.messages_by_ids([r["message_id"] for r in rows])
    out = []
    for fb in rows:
        if len(out) >= limit:
            break
        m = msgs.get(int(fb["message_id"]))
        if m is None or m.get("session_id") != fb["session_id"]:
            continue
        excerpt = re.sub(r"\s+", " ", str(m.get("content") or "")).strip()
        if len(excerpt) > FEEDBACK_EXCERPT:
            excerpt = excerpt[:FEEDBACK_EXCERPT] + "..."
        parts = [f'- [#{fb["message_id"]}] "{excerpt}"']
        if fb.get("value"):
            parts.append(f"reaction: {RV.REACTION_EMOJI.get(fb['value'], '')} ({fb['value']})")
        if fb.get("reasons"):
            parts.append("reasons: " + ", ".join(RV.REASON_LABEL.get(x, x) for x in fb["reasons"]))
        if fb.get("axis"):
            parts.append("speak/silent: " + RV.AXIS_LABEL.get(fb["axis"], fb["axis"]))
        if fb.get("comment"):
            parts.append('comment: "' + re.sub(r"\s+", " ", fb["comment"]).strip() + '"')
        out.append(" · ".join(parts))
    return out


def dm_feedback_block(sessions: Any, agent_key: str, now: Optional[float] = None) -> str:
    lines = dm_feedback_lines(sessions, agent_key, now)
    if not lines:
        return ""
    return ("\n\n## Recent feedback from the owner (about your replies in the private chat)\n" + "\n".join(lines) + "\n"
            + DM_FEEDBACK_NOTE + "\n")
