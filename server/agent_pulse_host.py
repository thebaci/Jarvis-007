"""Host của nhịp thích nghi lớp 3 (T3, 0.156.0): nhịp 30 giây, lần thức (code trước, model sau), lượt quét, sự kiện "đã
xem", route `GET/POST /agents/{slug}/pulse...` và `POST /seen`.

Thiết kế: docs/superpowers/specs/2026-10-15-team-adaptive-design.md mục 3.2-3.4, 5.1, 5.5, 6.2, 9.1, 10. Hợp đồng:
docs/dev/team-chat-t3-contract.md mục 1 và 4. Chính sách thuần ở `agent_pulse`.

- Một coroutine RIÊNG trong `_scheduler_loop` (cờ bận riêng, không nằm trong `_resonance_tick`). Mỗi nhịp chỉ làm việc
  nhanh bằng code ở luồng phụ: chiếu outbox còn chờ, quét tin chủ động đã xem bị bỏ qua, nhắc chờ chủ, đóng cửa sổ quan
  sát chính sách, tìm lịch tới hạn và lý do lớp 3 đang chờ, nhận lịch bằng CAS. Lượt cần model chạy ở tác vụ RIÊNG.
- Lần thức: cập nhật ước lượng và bậc, lập danh sách cơ hội trong phạm vi đã giao (mỗi cơ hội khoá `(source_ref,
  version)`, tiêu thụ một lần), rồi CHỈ khi cần mới gọi model (lượt `scan`). Thử khoá bận trước (bận thì dời 60 giây,
  không tốn lần thử), hỏi hạn mức ngày (`agent_budget`, phần L), giữ chỗ sổ lượt chung (`obligation = 0`) TRƯỚC engine.
- Hành động `say` luôn qua `agent_judge.judge_proactive` (phần J). Không có bộ phán xử thì KHÔNG gửi: ghi `silent` với lý
  do `judge_unavailable`.
- Nghĩa vụ (việc đã nhận, hạn chót, goal, lời gọi trực tiếp) không đi qua đây nên không bao giờ bị lớp 3 làm chậm.

Phần J và L cắm vào qua ba sổ đăng ký (không import chéo): `register_view_part(name, fn)` (mục của mình trong
`GET /agents/{slug}/pulse`), `register_reason_handler(code, fn)` (phục vụ lý do `reaction_review`, `related_review`,
`wait_unblocked`), và `agent_pulse.register_policy_reverter(kind, fn)`.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import secrets
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from fastapi import Request

import agent_pulse as AP
from io_offload import call_hook

TICK_S = 30.0
CONTEXT_REFRESH_S = 300.0
SCAN_TIMEOUT_S = 540.0     # một lượt tối đa 9 phút: dưới lease 15 phút và dưới mốc đối soát sổ lượt 10 phút
SEEN_MAX_IDS = 200
ACTIONS = ("none", "propose", "enqueue", "say")
REASON_CODES_SERVED_ELSEWHERE = ("reaction_review", "related_review", "wait_unblocked")

_VIEW_PARTS: dict = {}
_REASON_HANDLERS: dict = {}


def register_view_part(name: str, fn: Callable[[Any, str], Any]) -> None:
    """Phần J/L góp mục của mình vào `GET /agents/{slug}/pulse`: `fn(store, agent_key) -> dict`. Gọi lúc import module của
    phần đó. Lỗi của một mục không làm hỏng cả trang (mục đó trả {"error": ...})."""
    _VIEW_PARTS[str(name)] = fn


def register_reason_handler(code: str, fn: Callable[["PulseHost", dict], Any]) -> None:
    """Phần sở hữu một loại lý do lớp 3 đăng ký hàm phục vụ: `fn(host, reason)` (async hay thường). Host chỉ ĐIỀU PHỐI:
    hàm tự nhận lý do bằng `agent_ledger.WakeReasons.claim(..., try_busy, release_busy)` với cặp khoá của
    `host.busy_pair(agent_key)`. Loại chưa có ai đăng ký thì lý do nằm `pending`, không tốn lần thử."""
    _REASON_HANDLERS[str(code)] = fn


def view_parts() -> dict:
    return dict(_VIEW_PARTS)


def view(store, agent_key: str, at: Optional[float] = None) -> dict:
    """Khung của nhịp kèm mục của J/L (theo sổ đăng ký)."""
    out = AP.view(store, agent_key, at=at)
    parts = {}
    for name, fn in list(_VIEW_PARTS.items()):
        try:
            parts[name] = fn(store, agent_key)
        except Exception as ex:  # noqa: BLE001
            parts[name] = {"error": f"{type(ex).__name__}: {str(ex)[:200]}"}
    out["parts"] = parts
    return out


async def _maybe(v: Any) -> Any:
    return await v if inspect.isawaitable(v) else v


async def _judge_proactive(*, agent_key: str, context_ref: str, draft: str, source_event: str, origin: str = "pulse",
                           payload: Optional[dict] = None, engine: Any = None) -> dict:
    """Bộ chuyển tới `agent_judge.judge_proactive` (phần J), import lười. Thiếu module, lỗi, sai cấu trúc: `silent` có lý do,
    KHÔNG BAO GIỜ gửi khi chưa được phán xử.

    Host KHÔNG truyền `engine`: bộ phán xử dùng đường hỏi model của chính nó (`async (prompt, purpose, started) -> str`,
    model việc nền, có chốt test). Trước bản sửa review T3 J P1, host truyền một lambda không đối số trả (engine, model,
    run), sai chữ ký, nên mọi `say` thành im và tốn một lượt. `payload` mang `judge_daily` của nhóm (hợp đồng mục 2)."""
    try:
        import agent_judge  # noqa: WPS433
    except ImportError:
        return {"verdict": "silent", "reason": "judge_unavailable", "decision_id": None}
    fn = getattr(agent_judge, "judge_proactive", None)
    if fn is None:
        return {"verdict": "silent", "reason": "judge_unavailable", "decision_id": None}
    kw = {"agent_key": agent_key, "context_ref": context_ref, "draft": draft, "source_event": source_event,
          "origin": origin, "payload": payload}
    if engine is not None:
        kw["engine"] = engine
    try:
        d = await _maybe(fn(**kw))
    except Exception as ex:  # noqa: BLE001
        return {"verdict": "silent", "reason": f"judge_error: {type(ex).__name__}", "decision_id": None}
    if not isinstance(d, dict) or d.get("verdict") not in ("speak", "wait", "silent"):
        return {"verdict": "silent", "reason": "judge_invalid", "decision_id": None}
    return d


def _budget_try_spend(agent_key: str, purpose: str, at: Optional[float] = None) -> tuple:
    """Bộ chuyển tới `agent_budget.try_spend` (phần L, trần `agent_daily_calls`), import lười. Chưa có module thì cho qua
    (trần chung của máy chủ ở sổ lượt vẫn áp và lượt tự phát chỉ dùng tới 80%)."""
    try:
        import agent_budget  # noqa: WPS433
    except ImportError:
        return True, "budget_unavailable"
    try:
        got = agent_budget.try_spend(agent_key, purpose, at=at)
        return (bool(got[0]), str(got[1] or "")) if isinstance(got, (tuple, list)) else (bool(got), "")
    except Exception as ex:  # noqa: BLE001
        return False, f"budget_error: {type(ex).__name__}"


SCAN_RULES = (
    "\n\n# PROACTIVE WAKE-UP (scan turn)\n"
    "This is your own self-initiated wake-up, not the owner asking. Look at the list of opportunities within your assigned scope below and pick "
    "AT MOST ONE action. If nothing is worth doing, choose none (that is a good result and is not penalised). Do not create work just "
    "to look busy. Do not invent sources: propose and enqueue must point to the exact source_ref of an opportunity.\n"
    "Return ONLY one JSON block:\n"
    '{"action": "none"|"propose"|"enqueue"|"say", "source_ref": "...", "title": "...", "brief": "...", '
    '"text": "...", "reason": "..."}\n'
    "- propose: suggest a piece of work for the owner or team lead to approve (title, brief).\n"
    "- enqueue: put a piece of work on the shared queue (only if you have permission; without permission the host turns it into a proposal).\n"
    "- say: a short message to the owner (text); it still goes through the speak/wait/stay-silent judge before sending.\n"
)


def parse_action(text: str) -> Optional[dict]:
    """Khối JSON hành động của lượt quét (chấp nhận nằm trong ```json). Sai cấu trúc: None."""
    s = str(text or "")
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(d, dict) or d.get("action") not in ACTIONS:
        return None
    return d


@dataclass
class PulseHostDeps:
    store: Callable[[], Any]                                   # () -> GoalStore | None (chưa có kho: không làm gì)
    agents: Callable[[], list]                                 # () -> [{agent_key, brain_id, slug}] đang bật Cộng hưởng
    contexts: Callable[[str], list]                            # agent_key -> ["team:<id>", "dm:<agent_key>"]
    busy: Callable[[str], bool] = lambda key: False            # đang có lượt nhóm/A2 hay việc nhóm/goal xếp hàng
    # Một lần mỗi nhịp: () -> hàm agent_key -> bận (đọc kho MỘT lần cho mọi agent thay vì mỗi agent quét lại). None:
    # dùng `busy` từng agent.
    busy_snapshot: Optional[Callable[[], Callable[[str], bool]]] = None
    try_busy: Callable[[str, str], bool] = lambda key, tok: True
    release_busy: Callable[[str, str], Any] = lambda key, tok: None
    opportunities: Callable[[str, str, float], list] = lambda key, ctx, iv: []
    persona: Callable[[str], str] = lambda key: ""
    engine_for: Optional[Callable[[str, str, str], tuple]] = None   # (key, ctx, purpose) -> (engine, model, run)
    can_enqueue: Callable[[str, str], bool] = lambda key, ctx: False
    enqueue: Optional[Callable[[str, str, dict, str], Any]] = None
    propose: Optional[Callable[[str, str, dict, str], Any]] = None
    send: Optional[Callable[[str, str, str, dict], Any]] = None     # -> {"session_id", "message_id"} | None
    notify: Optional[Callable[[str, str, str], Any]] = None
    interacted: Callable[[dict], bool] = lambda p: False
    # ctx -> {"judge_daily": ...} cho lượt phán xử tin chủ động trong nhóm (trần của nhóm, kể cả Toàn quyền đè); {} ở chat riêng.
    judge_payload: Callable[[str], dict] = lambda ctx: {}
    project_pending: Optional[Callable[[], Any]] = None
    brain_of: Callable[[str], str] = lambda key: ""
    clock: Callable[[], float] = time.time
    spawn: Callable[[Any], Any] = field(default=asyncio.ensure_future)


class PulseHost:
    def __init__(self, deps: PulseHostDeps, judge: Optional[Callable[..., Any]] = None,
                 budget: Optional[Callable[..., tuple]] = None):
        self.deps = deps
        self.judge = judge or _judge_proactive
        self.budget = budget or _budget_try_spend
        self.host_id = "pulse-" + secrets.token_hex(4)
        self._busy = False
        self._ctx_at = 0.0
        self._inflight: set = set()
        self._tasks: set = set()
        self._local_busy: set = set()

    # ───────────── khoá bận ─────────────

    def busy_pair(self, agent_key: str, token: Optional[str] = None) -> tuple:
        """(try_fn, release_fn) cho `WakeReasons.claim`: thử khoá bận KHÔNG chờ của agent (khoá dùng chung với lượt nhóm)."""
        tok = token or f"{self.host_id}:{secrets.token_hex(4)}"
        return (lambda: bool(self.deps.try_busy(agent_key, tok)), lambda: self.deps.release_busy(agent_key, tok))

    def _spawn(self, coro) -> None:
        try:
            t = self.deps.spawn(coro)
        except Exception as ex:  # noqa: BLE001
            coro.close()
            print(f"[pulse] could not create the background task: {type(ex).__name__}: {ex}", file=sys.stderr)
            return
        if isinstance(t, asyncio.Future):
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)

    async def wait_idle(self, timeout: float = 30.0) -> None:
        """Test: chờ mọi lượt đã spawn xong."""
        end = time.time() + timeout
        while self._tasks and time.time() < end:
            await asyncio.wait(list(self._tasks), timeout=max(0.01, end - time.time()))

    # ───────────── nhịp ─────────────

    async def tick(self) -> dict:
        """Một nhịp (30 giây). Cờ bận riêng: hai nhịp không chồng nhau. Chỉ code ở đây; lượt model chạy ở tác vụ riêng."""
        if self._busy:
            return {"skipped": "busy"}
        self._busy = True
        try:
            if self.deps.project_pending is not None:
                try:
                    # Hàm thường (đọc/ghi kho) chạy ở luồng phụ; coroutine (như `_feedback_pulse_tick` của host) trên loop.
                    await call_hook(self.deps.project_pending)
                except Exception as ex:  # noqa: BLE001
                    print(f"[pulse project] {type(ex).__name__}: {ex}", file=sys.stderr)
            if await asyncio.to_thread(self.deps.store) is None:
                return {"skipped": "no_store"}
            now = float(self.deps.clock())
            claims, reasons = await asyncio.to_thread(self._code_pass, now)
            for cl in claims:
                self._spawn(self.wake_step(cl))
            for r in reasons:
                fn = _REASON_HANDLERS.get(r["code"])
                if fn is None:
                    continue
                self._inflight.add(r["id"])
                self._spawn(self._serve_reason(fn, r))
            return {"claims": len(claims), "reasons": len(reasons)}
        finally:
            self._busy = False

    async def _serve_reason(self, fn, reason: dict) -> None:
        try:
            await _maybe(fn(self, reason))
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse reason {reason.get('code')}] {type(ex).__name__}: {ex}", file=sys.stderr)
        finally:
            self._inflight.discard(reason["id"])

    def _code_pass(self, now: float) -> tuple:
        store = self.deps.store()
        AP.ensure(store)
        agents = {a["agent_key"]: a for a in (self.deps.agents() or []) if a.get("agent_key")}
        if now - self._ctx_at >= CONTEXT_REFRESH_S:
            self._ctx_at = now
            for key in agents:
                try:
                    for ctx in self.deps.contexts(key) or []:
                        AP.ensure_row(store, key, ctx, at=now)
                except Exception as ex:  # noqa: BLE001
                    print(f"[pulse contexts] {key}: {type(ex).__name__}: {ex}", file=sys.stderr)
        scope_cache: dict = {}

        def in_scope(key: str, ctx: str) -> Optional[bool]:
            """Ngữ cảnh còn trong phạm vi đã giao của agent (5.5): nhóm đang hoạt động mà agent là thành viên đang tham
            gia, hay chat riêng (review T3 P P2-1). None khi không đọc được phạm vi (lỗi tạm): bỏ qua lần này, không gỡ."""
            if key not in scope_cache:
                try:
                    scope_cache[key] = set(self.deps.contexts(key) or [])
                except Exception as ex:  # noqa: BLE001
                    print(f"[pulse scope] {key}: {type(ex).__name__}: {ex}", file=sys.stderr)
                    scope_cache[key] = None
            s = scope_cache[key]
            return None if s is None else (ctx in s)

        with closing(store._conn()) as c:
            nodue = [dict(r) for r in c.execute(
                "SELECT agent_key, context_ref, tier FROM agent_pulse WHERE next_due_at IS NULL AND context_ref<>'*' "
                "AND state IN ('active','awake','slowed')").fetchall()]
        if nodue:
            with store._Tx(store) as c:
                # Dòng có lịch mà chưa có mốc (tạo từ T2, hay vừa tiếp sau tạm dừng): đặt mốc theo bậc. Dòng của ngữ cảnh
                # ngoài phạm vi (đã rời nhóm, nhóm tạm dừng hay lưu trữ) giữ không lịch tới khi trở lại phạm vi.
                for r in nodue:
                    iv = AP.interval(int(r["tier"]))
                    if iv is None or (r["agent_key"] in agents and not in_scope(r["agent_key"], r["context_ref"])):
                        continue
                    c.execute("UPDATE agent_pulse SET next_due_at=? WHERE agent_key=? AND context_ref=? AND "
                              "next_due_at IS NULL", (now + iv, r["agent_key"], r["context_ref"]))
        try:
            AP.sweep_seen_ignored(store, self.deps.interacted, at=now)
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse seen] {type(ex).__name__}: {ex}", file=sys.stderr)
        self._remind_waiting(store, now)
        try:
            AP.observe_policy_changes(store, at=now)
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse policy] {type(ex).__name__}: {ex}", file=sys.stderr)
        claims = []
        with closing(store._conn()) as c:
            due = [dict(r) for r in c.execute(
                "SELECT * FROM agent_pulse WHERE context_ref<>'*' AND state IN ('active','awake','slowed') AND "
                "next_due_at IS NOT NULL AND next_due_at<=? AND (claim_until IS NULL OR claim_until<?) "
                "ORDER BY next_due_at LIMIT 50", (now, now)).fetchall()]
            pend = [dict(r) for r in c.execute(
                "SELECT r.*, p.state AS pulse_state FROM agent_wake_reasons r LEFT JOIN agent_pulse p ON "
                "p.agent_key=r.agent_key AND p.context_ref=r.context_ref WHERE r.status='pending' ORDER BY r.id "
                "LIMIT 100").fetchall()]
        busy_cache: dict = {}
        busy_fn = self.deps.busy
        if self.deps.busy_snapshot is not None and (due or pend):
            try:
                busy_fn = self.deps.busy_snapshot()
            except Exception as ex:  # noqa: BLE001
                print(f"[pulse busy] {type(ex).__name__}: {ex}", file=sys.stderr)
                busy_fn = lambda key: True  # noqa: E731 - kho lỗi: coi như bận, dời lịch (an toàn)

        def is_busy(key):
            if key not in busy_cache:
                try:
                    busy_cache[key] = bool(busy_fn(key)) or key in self._local_busy
                except Exception:  # noqa: BLE001
                    busy_cache[key] = True
            return busy_cache[key]

        for r in due:
            key = r["agent_key"]
            if key not in agents:
                continue
            scoped = in_scope(key, r["context_ref"])
            if scoped is None:
                continue
            if not scoped:
                # Ngoài phạm vi đã giao (review T3 P P2-1): không quét, không nói; gỡ lịch (trở lại phạm vi thì có lịch lại).
                with store._Tx(store) as c:
                    n = c.execute("UPDATE agent_pulse SET next_due_at=NULL WHERE agent_key=? AND context_ref=? AND "
                                  "next_due_at=?", (key, r["context_ref"], r["next_due_at"])).rowcount
                    if n:
                        AP._event(c, key, r["context_ref"], "out_of_scope", source="host", at=now)
                continue
            eff = AP.effective_due(r["next_due_at"], None, is_busy(key), now)
            if eff is None or eff > now:
                with store._Tx(store) as c:
                    c.execute("UPDATE agent_pulse SET next_due_at=? WHERE agent_key=? AND context_ref=? AND "
                              "next_due_at=?", (eff, key, r["context_ref"], r["next_due_at"]))
                continue
            tok = f"{self.host_id}:{secrets.token_hex(6)}"
            with store._Tx(store) as c:
                n = c.execute("UPDATE agent_pulse SET claim_token=?, claim_until=? WHERE agent_key=? AND context_ref=? "
                              "AND next_due_at=? AND state IN ('active','awake','slowed') AND "
                              "(claim_until IS NULL OR claim_until<?)",
                              (tok, now + AP.CLAIM_S, key, r["context_ref"], r["next_due_at"], now)).rowcount
            if n == 1:
                claims.append({"agent_key": key, "context_ref": r["context_ref"], "due_at": float(r["next_due_at"]),
                               "token": tok, "brain_id": agents[key].get("brain_id") or ""})
        reasons = []
        for r in pend:
            if r["id"] in self._inflight or r["agent_key"] not in agents or r["code"] not in _REASON_HANDLERS:
                continue
            if r.get("pulse_state") in ("paused", "off") or is_busy(r["agent_key"]):
                continue
            if not in_scope(r["agent_key"], r["context_ref"]):
                continue   # ngữ cảnh ngoài phạm vi: lý do giữ nguyên, không phục vụ
            reasons.append(r)
        try:
            import agent_budget
            # Thứ tự tiêu hạn mức (mục 9): reaction_review > related_review > wait_unblocked, cũ trước trong cùng loại.
            reasons = agent_budget.sort_by_priority(reasons)
        except ImportError:
            pass
        return claims, reasons

    def _remind_waiting(self, store, now: float) -> None:
        with closing(store._conn()) as c:
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM agent_pulse WHERE state='waiting_owner' AND waiting_since IS NOT NULL AND "
                "waiting_since<=? AND reminded_at IS NULL", (now - AP.WAITING_REMIND_S,)).fetchall()]
        for r in rows:
            with store._Tx(store) as c:
                n = c.execute("UPDATE agent_pulse SET reminded_at=? WHERE agent_key=? AND context_ref=? AND "
                              "reminded_at IS NULL", (now, r["agent_key"], r["context_ref"])).rowcount
                if n:
                    AP._event(c, r["agent_key"], r["context_ref"], "waiting_remind", source="host", at=now)
            if n and self.deps.notify is not None:
                try:
                    import localefmt
                    text = localefmt.chu("Trợ lý đang chờ bạn quyết một việc từ hơn một ngày trước.",
                                         "An assistant has been waiting for your decision for over a day.")
                except Exception:  # noqa: BLE001
                    text = "Trợ lý đang chờ bạn quyết một việc từ hơn một ngày trước."
                try:
                    self.deps.notify(r["agent_key"], r["context_ref"], text)
                except Exception as ex:  # noqa: BLE001
                    print(f"[pulse remind] {type(ex).__name__}: {ex}", file=sys.stderr)

    # ───────────── lần thức ─────────────

    def _finish(self, store, cl: dict, now: float, defer: Optional[float] = None) -> None:
        """Nhả lịch đã nhận: mốc kế tiếp theo bậc hiện tại (hay dời `defer` giây khi bận)."""
        with store._Tx(store) as c:
            r = AP._row(c, cl["agent_key"], cl["context_ref"])
            if r is None or r.get("claim_token") != cl["token"]:
                return
            iv = AP.interval(int(r["tier"]))
            if defer is not None:
                nd = now + defer
            elif r["state"] in AP.SCHEDULED and iv is not None:
                nd = now + iv
            else:
                nd = None
            c.execute("UPDATE agent_pulse SET next_due_at=?, claim_token='', claim_until=NULL, updated_at=? "
                      "WHERE agent_key=? AND context_ref=?", (nd, now, cl["agent_key"], cl["context_ref"]))

    def _wake_code(self, store, cl: dict, now: float) -> dict:
        """Phần CODE của một lần thức (luồng phụ, một lần chuyển luồng thay vì nhiều): ước lượng, bậc, cơ hội. Trả
        {"done": kết quả} khi không cần lượt quét, hay {"fresh", "bounded", "eval"} khi cần."""
        key, ctx = cl["agent_key"], cl["context_ref"]
        row = AP.row(store, key, ctx)
        iv = AP.interval(int(row["tier"])) or AP.TIERS[AP.INIT_TIER]
        try:
            raw = self.deps.opportunities(key, ctx, iv)
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse opportunities] {type(ex).__name__}: {ex}", file=sys.stderr)
            raw = []
        fresh = AP.fresh_opportunities(store, key, ctx, raw, now)
        with closing(store._conn()) as c:
            pending = c.execute("SELECT COUNT(*) FROM agent_wake_reasons WHERE agent_key=? AND context_ref=? AND "
                                "status='pending'", (key, ctx)).fetchone()[0]
        ev = AP.evaluate(store, key, ctx, at=now, has_opportunity=bool(fresh) or pending > 0, count_wake=True)
        row = AP.row(store, key, ctx)
        if row["state"] not in AP.SCHEDULED:
            self._finish(store, cl, now)
            return {"done": {"outcome": "no_schedule", "state": row["state"], "eval": ev}}
        bounded = (not fresh and row["state"] in ("active", "awake")
                   and int(row.get("scan_counter") or 0) >= AP.SCAN_EVERY
                   and (row.get("last_scan_at") is None or now - float(row["last_scan_at"]) >= AP.SCAN_MIN_GAP_S))
        if not fresh and not bounded:
            AP.record_event(store, key, ctx, "no_action", reason=ev["reason"], at=now)
            self._finish(store, cl, now)
            return {"done": {"outcome": "no_action", "eval": ev}}
        return {"fresh": fresh, "bounded": bounded, "eval": ev}

    async def wake_step(self, cl: dict) -> dict:
        """Một lần thức của (agent, ngữ cảnh) đã nhận lịch: code trước (ước lượng, bậc, cơ hội), model chỉ khi cần. Mọi
        đọc/ghi kho ở luồng phụ (GOAL mục 10)."""
        store = None
        key, ctx = cl["agent_key"], cl["context_ref"]
        now = float(self.deps.clock())
        try:
            store = await asyncio.to_thread(self.deps.store)
            got = await asyncio.to_thread(self._wake_code, store, cl, now)
            if "done" in got:
                return got["done"]
            out = await self._scan(store, cl, got["fresh"], got["bounded"], now)
            out["eval"] = got["eval"]
            return out
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse wake] {key} {ctx}: {type(ex).__name__}: {ex}", file=sys.stderr)
            try:
                if store is not None:
                    await asyncio.to_thread(self._finish, store, cl, now)
            except Exception:  # noqa: BLE001
                pass
            return {"outcome": "error", "error": f"{type(ex).__name__}: {ex}"}

    def _due_ref(self, cl: dict) -> str:
        return f"pulse:{cl['agent_key']}:{cl['context_ref']}:{int(round(cl['due_at'] * 1000))}"

    def _clear_quota(self, store, cl) -> None:
        with store._Tx(store) as c:
            c.execute("UPDATE agent_pulse SET quota_wait=0 WHERE agent_key=? AND context_ref=? AND quota_wait<>0",
                      (cl["agent_key"], cl["context_ref"]))

    def _set_quota(self, store, cl, now, why: str) -> None:
        with store._Tx(store) as c:
            c.execute("UPDATE agent_pulse SET quota_wait=1 WHERE agent_key=? AND context_ref=?",
                      (cl["agent_key"], cl["context_ref"]))
            AP._event(c, cl["agent_key"], cl["context_ref"], "quota", source="host", reason=why, at=now)

    async def _scan(self, store, cl: dict, fresh: list, bounded: bool, now: float) -> dict:
        import agent_ledger as AL
        key, ctx = cl["agent_key"], cl["context_ref"]
        due_ref = self._due_ref(cl)
        tok = cl["token"]
        if not await asyncio.to_thread(self.deps.try_busy, key, tok):
            # Bận (lượt nhóm, A2): dời 60 giây, không tốn lần thử, cơ hội chưa tiêu thụ.
            await asyncio.to_thread(self._finish, store, cl, now, AP.BUSY_DEFER_S)
            return {"outcome": "busy"}
        self._local_busy.add(key)
        try:
            ok, why = await asyncio.to_thread(self.budget, key, "scan", now)
            if ok:
                # Nhãn "Chờ hạn mức" chỉ đứng khi đang thật sự hết hạn mức (review T3 P P3: trước đây đứng mãi tới lượt
                # quét thành công kế tiếp).
                await asyncio.to_thread(self._clear_quota, store, cl)
            if not ok:
                await asyncio.to_thread(self._set_quota, store, cl, now, why or "agent_daily_calls")
                await asyncio.to_thread(self._finish, store, cl, now)
                return {"outcome": "quota", "reason": why}
            ledger = AL.CallLedger(store)
            prior = await asyncio.to_thread(ledger.rows, due_ref)
            if any(r["status"] in ("running", "ok", "error", "interrupted") for r in prior):
                # Khởi động lại sau khi lượt của lịch này đã tới model: không chạy lần hai.
                await asyncio.to_thread(AP.record_event, store, key, ctx, "scan_skipped", reason="already_ran",
                                        payload={"reason_ref": due_ref}, at=now)
                await asyncio.to_thread(self._finish, store, cl, now)
                return {"outcome": "already_ran"}
            try:
                cid = await asyncio.to_thread(lambda: ledger.reserve(
                    purpose="scan", reason_ref=due_ref, agent_key=key, brain_id=cl.get("brain_id") or "",
                    context_ref=ctx, obligation=False, now=now))
            except AL.ReasonBusy:
                # Lịch khác đang giữ đúng mã lượt này: nhả lịch (dời như khi bận), không kẹt tới khi lease hết hạn.
                await asyncio.to_thread(self._finish, store, cl, now, AP.BUSY_DEFER_S)
                return {"outcome": "ledger_busy"}
            if cid is None:
                await asyncio.to_thread(self._set_quota, store, cl, now, "server_ceiling")
                await asyncio.to_thread(self._finish, store, cl, now)
                return {"outcome": "quota", "reason": "server_ceiling"}
            return await self._run_scan(store, cl, ledger, cid, due_ref, fresh, bounded, now)
        finally:
            self._local_busy.discard(key)
            try:
                await asyncio.to_thread(self.deps.release_busy, key, tok)
            except Exception:  # noqa: BLE001
                pass

    async def _run_scan(self, store, cl, ledger, cid, due_ref, fresh, bounded, now) -> dict:
        key, ctx = cl["agent_key"], cl["context_ref"]
        state = {"started": False}
        try:
            if self.deps.engine_for is None:
                raise RuntimeError("no engine")
            # Dựng engine đọc file trợ lý và kho (brain, model riêng): luồng phụ.
            engine, model, run = await asyncio.to_thread(self.deps.engine_for, key, ctx, "scan")
        except Exception as ex:  # noqa: BLE001
            await asyncio.to_thread(ledger.refund, cid)
            await asyncio.to_thread(AP.record_event, store, key, ctx, "scan_error", reason=f"engine: {type(ex).__name__}",
                                    payload={"call_id": cid}, at=now)
            await asyncio.to_thread(self._finish, store, cl, now)
            return {"outcome": "engine_unavailable", "error": f"{type(ex).__name__}: {ex}"}

        async def engine_started():
            if not state["started"]:
                state["started"] = True
                await asyncio.to_thread(ledger.mark_engine, cid, engine, model)

        lines = [f"- [{o['source_ref']}] ({o.get('kind') or ''}) {str(o.get('summary') or '')[:400]}" for o in fresh]
        prompt = ("Context: " + ctx + "\n" + ("List of opportunities:\n" + "\n".join(lines) if lines else
                  "There are no new opportunities in the list. This is a periodic limited scan: only act when you truly "
                  "see work worth doing within your assigned scope; otherwise none."))
        system = (await asyncio.to_thread(self.deps.persona, key) or "") + SCAN_RULES
        req = {"system": system, "prompt": prompt, "engine_started": engine_started, "team_id": ctx,
               "turn_id": due_ref, "agent_key": key, "context_ref": ctx, "purpose": "scan"}
        try:
            out = await asyncio.wait_for(run(req), timeout=SCAN_TIMEOUT_S)
        except BaseException as ex:  # noqa: BLE001
            if state["started"]:
                await asyncio.to_thread(ledger.settle, cid, "interrupted" if isinstance(ex, asyncio.CancelledError)
                                        else "error")
            else:
                await asyncio.to_thread(ledger.refund, cid)
            await asyncio.to_thread(AP.record_event, store, key, ctx, "scan_error", reason=type(ex).__name__,
                                    payload={"call_id": cid}, at=now)
            await asyncio.to_thread(self._finish, store, cl, now)
            if isinstance(ex, asyncio.CancelledError):
                raise
            return {"outcome": "engine_error", "error": f"{type(ex).__name__}: {ex}"}
        if not state["started"]:
            await engine_started()
        out = out or {}
        act = parse_action(out.get("text") if isinstance(out, dict) else out)
        result = await self._act(store, cl, act, fresh, bounded, due_ref, now)
        await asyncio.to_thread(AP.consume_opportunities, store, key, ctx, fresh, f"call:{cid}", now)
        await asyncio.to_thread(ledger.settle, cid, "ok", (out or {}).get("tokens_in"), (out or {}).get("tokens_out"))

        def scanned():
            with store._Tx(store) as c:
                c.execute("UPDATE agent_pulse SET scan_counter=0, last_scan_at=?, quota_wait=0 WHERE agent_key=? AND "
                          "context_ref=?", (now, key, ctx))
                AP._event(c, key, ctx, "scan", source="bounded" if bounded else "opportunities",
                          reason=result.get("action", "none"),
                          payload={"call_id": cid, "result": result, "opportunities": [o["source_ref"] for o in fresh]},
                          at=now)
            self._finish(store, cl, now)
        await asyncio.to_thread(scanned)
        return {"outcome": "scanned", "call_id": cid, "result": result}

    def _judge_payload(self, ctx: str) -> dict:
        """Dữ liệu cho bộ phán xử (luồng phụ): `judge_daily` của nhóm. Lỗi thì rỗng (bộ phán xử dùng mặc định 40)."""
        try:
            got = self.deps.judge_payload(ctx)
            return dict(got) if isinstance(got, dict) else {}
        except Exception as ex:  # noqa: BLE001
            print(f"[pulse judge payload] {type(ex).__name__}: {ex}", file=sys.stderr)
            return {}

    async def _act(self, store, cl, act: Optional[dict], fresh: list, bounded: bool, due_ref: str, now: float) -> dict:
        key, ctx = cl["agent_key"], cl["context_ref"]
        if act is None:
            return {"action": "none", "reason": "invalid_output"}
        action = act["action"]
        refs = [o["source_ref"] for o in fresh]
        src = str(act.get("source_ref") or "")
        if action in ("propose", "enqueue"):
            if src not in refs:
                if not refs:
                    # Quét giới hạn không có cơ hội: không tạo việc khi không có nguồn (không tạo việc để giữ mình bận).
                    return {"action": "none", "reason": "no_source", "wanted": action}
                # Model trỏ nguồn bịa: KHÔNG thay bằng cơ hội đầu (gắn đề xuất vào sai nguồn và khoá nguồn đó), mà bỏ
                # (review T3 P P3).
                return {"action": "none", "reason": "bad_source", "wanted": action, "source_ref": src[:200]}
            ver = next((str(o.get("version") or "") for o in fresh if o["source_ref"] == src), "")
            if await asyncio.to_thread(AP.proposal_blocked, store, key, ctx, src, ver):
                # Đã đề xuất (hay đã bị bác) cho đúng nguồn và phiên bản này: không mở lại khi không có dữ kiện mới.
                return {"action": "none", "reason": "already_proposed", "wanted": action, "source_ref": src}
            item = {"title": str(act.get("title") or "")[:160].strip(), "brief": str(act.get("brief") or "")[:4000]}
            if not item["title"]:
                return {"action": "none", "reason": "no_title", "wanted": action}
            if action == "enqueue":
                allowed = False
                try:
                    allowed = bool(await asyncio.to_thread(self.deps.can_enqueue, key, ctx))
                except Exception:  # noqa: BLE001
                    allowed = False
                if allowed and self.deps.enqueue is not None:
                    tid = await asyncio.to_thread(self.deps.enqueue, key, ctx, item, src)
                    await asyncio.to_thread(AP.record_event, store, key, ctx, "enqueue", reason=src,
                                            payload={"task_id": tid, "title": item["title"]}, at=now)
                    return {"action": "enqueue", "task_id": tid, "source_ref": src}
                note = "no_permission"
            else:
                note = ""
            got = await asyncio.to_thread(self.deps.propose, key, ctx, item, src) if self.deps.propose else None
            got = got if isinstance(got, dict) else ({"ref": got} if got else {})
            pid = await asyncio.to_thread(lambda: AP.record_proposal(
                store, agent_key=key, context_ref=ctx, source_ref=src, version=ver, title=item["title"],
                brief=item["brief"], session_id=str(got.get("session_id") or ""), message_id=got.get("message_id"),
                at=now))
            ref = got.get("ref") or (f"msg:{got['message_id']}" if got.get("message_id") is not None else None)
            await asyncio.to_thread(AP.record_event, store, key, ctx, "propose", reason=src,
                                    payload={"ref": ref, "proposal_id": pid, "title": item["title"], "downgraded": note},
                                    at=now)
            return {"action": "propose", "ref": ref, "proposal_id": pid, "source_ref": src, "downgraded": note}
        if action == "say":
            text = str(act.get("text") or "").strip()[:4000]
            if not text:
                return {"action": "none", "reason": "empty_say"}
            payload = dict(await asyncio.to_thread(self._judge_payload, ctx), source_ref=src or due_ref)
            dec = await self.judge(agent_key=key, context_ref=ctx, draft=text, source_event=due_ref, origin="pulse",
                                   payload=payload)
            verdict = dec.get("verdict")
            if verdict != "speak":
                return {"action": "say", "verdict": verdict, "reason": dec.get("reason") or "",
                        "decision_id": dec.get("decision_id")}
            sent = (await asyncio.to_thread(self.deps.send, key, ctx, text, {"source_ref": src or due_ref,
                                                                             "decision_id": dec.get("decision_id")})
                    if self.deps.send else None)
            if sent and sent.get("message_id") is not None:
                await asyncio.to_thread(AP.record_proactive, store, key, ctx, sent.get("session_id") or "",
                                        int(sent["message_id"]), now)
                await asyncio.to_thread(AP.record_event, store, key, ctx, "said", reason=src or due_ref,
                                        payload={"message_id": sent["message_id"],
                                                 "decision_id": dec.get("decision_id")}, at=now)
                return {"action": "say", "verdict": "speak", "message_id": sent["message_id"],
                        "decision_id": dec.get("decision_id")}
            return {"action": "say", "verdict": "speak", "sent": False}
        return {"action": "none", "reason": str(act.get("reason") or "")[:300]}


# ═════════════════════════════ route ═════════════════════════════

@dataclass
class PulseRouteDeps:
    brain_key: Callable[[str], str]                         # brain trên dashboard -> đường dẫn đã resolve
    agent_exists: Callable[[str, str], bool]                # (root, slug) -> file trợ lý có thật
    agent_key: Callable[[str, str], Optional[str]]          # (root, slug) -> agent_key đang hoạt động | None
    store: Callable[[], Any]                                # () -> GoalStore | None (không tạo kho chỉ để đọc)
    seen_resolve: Callable[[str, list, str], list]          # (context_ref, ids, session_id) -> [(ctx, mid, key, sid)]
    # (đề xuất, "accepted"|"rejected") -> {"task_id"?}: chấp nhận thì xếp việc qua hàng đợi chung với quyền của chủ.
    proposal_action: Optional[Callable[[dict, str], Optional[dict]]] = None
    # agent_key -> ngữ cảnh trong phạm vi (nhóm đang tham gia, chat riêng). None: không kiểm thêm (test cũ).
    contexts: Optional[Callable[[str], list]] = None


def register(app, deps: PulseRouteDeps) -> None:
    """Route của nhịp. Middleware auth + CSRF của main chặn trước (route chỉ của chủ). Hành động chỉ báo thành công sau
    khi kho đã ghi (trả 200 kèm khung mới)."""
    from fastapi.responses import JSONResponse
    import localefmt

    def err(code, vi, en):
        return JSONResponse({"ok": False, "error": localefmt.chu(vi, en)}, status_code=code)

    async def body_of(request) -> dict:
        try:
            d = await request.json()
            return d if isinstance(d, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def resolve(slug: str, brain: str):
        root = deps.brain_key(brain)
        if not deps.agent_exists(root, slug):
            return None, None, err(404, "Không tìm thấy trợ lý", "Assistant not found")
        return root, deps.agent_key(root, slug), None

    def empty(slug):
        return {"ok": True, "agent_key": None, "resonance": False, "contexts": [], "aggregate": None, "changes": [],
                "recent": [], "feedback": [], "policy_changes": [], "parts": {}, "tiers": list(AP.TIERS)}

    @app.get("/agents/{slug}/pulse")
    async def agent_pulse_view(slug: str, brain: str = "brain"):
        root, key, e = await asyncio.to_thread(resolve, slug, brain)
        if e:
            return e
        store = await asyncio.to_thread(deps.store)
        if not key or store is None:
            return empty(slug)
        out = await asyncio.to_thread(view, store, key)
        out["ok"] = True
        return out

    async def act(slug: str, brain: str, request, fn):
        root, key, e = await asyncio.to_thread(resolve, slug, brain)
        if e:
            return e
        store = await asyncio.to_thread(deps.store)
        if not key or store is None:
            return err(409, "Trợ lý chưa có nhịp (chưa bật Auto lần nào)", "This assistant has no pulse yet")
        b = await body_of(request)
        try:
            res = await asyncio.to_thread(fn, store, key, b)
        except PermissionError:
            return err(403, "Chỉ chủ mới đổi được mục này", "Only the owner can change this")
        except ValueError as ex:
            return err(400, f"Yêu cầu không hợp lệ: {ex}", f"Invalid request: {ex}")
        if res is None or res is False:
            return err(409, "Không còn gì để đổi (đã đổi hay đã quay lại)", "Nothing to change (already done)")
        out = await asyncio.to_thread(view, store, key)
        return {"ok": True, "result": res if isinstance(res, (dict, int, bool)) else True, "view": out}

    def _ctxs(store, key, b, allow_all=True):
        ctx = str(b.get("context_ref") or "").strip()
        if ctx:
            if not (ctx.startswith("team:") or ctx == f"dm:{key}" or ctx == "*"):
                raise ValueError("context does not belong to the assistant")
            if ctx.startswith("team:") and deps.contexts is not None:
                # Chỉ nhóm agent đang tham gia, hay nhóm đã có dòng nhịp (để chủ vẫn tạm dừng, đặt lại được): không tạo
                # dòng có lịch cho nhóm không liên quan (review T3 P P3).
                known = {r["context_ref"] for r in AP.rows(store, key)}
                if ctx not in known and ctx not in set(deps.contexts(key) or []):
                    raise ValueError("the assistant is not in this team")
            return [ctx]
        if not allow_all:
            raise ValueError("choose a context")
        return [r["context_ref"] for r in AP.rows(store, key) if r["context_ref"] != "*"]

    @app.post("/agents/{slug}/pulse/wake")
    async def agent_pulse_wake(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            done = [c for c in _ctxs(store, key, b) if c != "*" and AP.wake(store, key, c, "manual")]
            return {"woken": done} if done else None
        return await act(slug, brain, request, fn)

    @app.post("/agents/{slug}/pulse/pause")
    async def agent_pulse_pause(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            ctx = str(b.get("context_ref") or "*")
            _ctxs(store, key, {"context_ref": ctx})
            return AP.set_state(store, key, ctx, "paused", by="owner") or None
        return await act(slug, brain, request, fn)

    @app.post("/agents/{slug}/pulse/resume")
    async def agent_pulse_resume(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            ctx = str(b.get("context_ref") or "*")
            _ctxs(store, key, {"context_ref": ctx})
            return AP.set_state(store, key, ctx, "resume", by="owner") or None
        return await act(slug, brain, request, fn)

    @app.post("/agents/{slug}/pulse/reset")
    async def agent_pulse_reset(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            ctx = _ctxs(store, key, b, allow_all=False)[0]
            if ctx == "*":
                raise ValueError("choose a context")
            return AP.reset(store, key, ctx, by="owner")
        return await act(slug, brain, request, fn)

    @app.post("/agents/{slug}/pulse/revert")
    async def agent_pulse_revert(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            if b.get("change_id") is not None:
                ch = AP.policy_changes(store, key, 200)
                if int(b["change_id"]) not in {x["id"] for x in ch}:
                    return None
                return AP.revert_policy_change(store, int(b["change_id"]), reason="owner", by="owner")
            if b.get("event_id") is None:
                raise ValueError("missing event_id or change_id")
            return AP.revert(store, key, int(b["event_id"]), by="owner")
        return await act(slug, brain, request, fn)

    def _proposal_route(decision):
        def fn(store, key, b, pid):
            prop = AP.proposal(store, pid)
            if prop is None or prop["agent_key"] != key or prop["status"] != "pending":
                return None
            if deps.proposal_action is None:
                raise ValueError("the proposal action is not wired up")
            return deps.proposal_action(prop, decision) or None
        return fn

    @app.post("/agents/{slug}/pulse/proposals/{pid}/accept")
    async def agent_pulse_proposal_accept(slug: str, pid: int, request: Request, brain: str = "brain"):
        """Chấp nhận một đề xuất của lượt quét (+0.6): xếp việc qua hàng đợi chung với quyền của chủ (việc nhóm qua thẻ
        Tạo việc của nhóm; chat riêng thành việc giao cho trợ lý như nút Giao việc). Chỉ báo xong sau khi đã xếp."""
        f = _proposal_route("accepted")
        return await act(slug, brain, request, lambda store, key, b: f(store, key, b, pid))

    @app.post("/agents/{slug}/pulse/proposals/{pid}/reject")
    async def agent_pulse_proposal_reject(slug: str, pid: int, request: Request, brain: str = "brain"):
        """Bác một đề xuất (-0.4). Cùng nguồn và phiên bản thì không đề xuất lại (5.5)."""
        f = _proposal_route("rejected")
        return await act(slug, brain, request, lambda store, key, b: f(store, key, b, pid))

    @app.post("/agents/{slug}/pulse/max_tier")
    async def agent_pulse_max_tier(slug: str, request: Request, brain: str = "brain"):
        def fn(store, key, b):
            return AP.set_max_tier(store, key, int(b.get("tier")), by="owner")
        return await act(slug, brain, request, fn)

    @app.post("/seen")
    async def pulse_seen(request: Request):
        """Tin của agent đã nằm trong khung nhìn ≥ 1,5 giây khi tab hiển thị (6.2). Chỉ tin của agent trong Javis; ghi lần
        đầu. Không theo dõi gì khác."""
        b = await body_of(request)
        ctx = str(b.get("context_ref") or "").strip()
        ids = b.get("message_ids")
        if not ctx or not isinstance(ids, list) or not ids or len(ids) > SEEN_MAX_IDS:
            return err(400, "Thiếu ngữ cảnh hay danh sách tin", "Missing context or message list")
        try:
            ids = sorted({int(x) for x in ids})
        except (TypeError, ValueError):
            return err(400, "Mã tin không hợp lệ", "Invalid message id")
        store = await asyncio.to_thread(deps.store)
        if store is None:
            return {"ok": True, "recorded": 0, "agent": False}

        def _do():
            recorded = 0
            got = deps.seen_resolve(ctx, ids, str(b.get("session_id") or "")) or []
            for c, mid, key, sid in got:
                recorded += AP.mark_seen(store, c, [mid], agent_key=key, session_id=sid)
            return recorded, bool(got)
        n, agent = await asyncio.to_thread(_do)
        # `agent: false`: không phải tin của trợ lý (vd. trang Trò chuyện chính): trang thôi gửi cho ngữ cảnh này.
        return {"ok": True, "recorded": n, "agent": agent}
