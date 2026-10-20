"""Kho của bộ phán xử theo agent (T3 phần J, 0.156.0). Thiết kế 2026-10-15 mục 7.1; hợp đồng docs/dev/team-chat-t3-contract.md.

Kho riêng `agent_judge.sqlite3` (dữ liệu nội bộ, tách khỏi kho phán xử khách Zalo `chatbot_reply_policy_store`). Tạo ở lần
dùng đầu tiên (host mở lười), mọi bảng `CREATE TABLE IF NOT EXISTS`. Bản cũ (trước 0.156.0) không biết kho này nên bỏ qua
nó; hạ phiên bản không cần khôi phục gì. Công cụ khôi phục về trước 0.140.0 (`tools/team_chat_restore_pre.py`) cất kho này
sang bên như `team.sqlite3` (trước nâng cấp không có kho).

Bảng (mục 7.1, thêm vài cột để lần theo nguồn, không thu hẹp thiết kế):
- `profiles(agent_key, role_text, eagerness, role_hash, eagerness_source, updated_at)`: hồ sơ RIÊNG từng agent.
- `decisions(...)`: mỗi quyết định nói/chờ/im (cả ca im không có tin), `address` certain|none, nguồn, sổ lượt, nhãn.
- `offsets(agent_key, context_ref, offset, updated_at)`: độ lệch ngưỡng THEO NGỮ CẢNH, kẹp ±0.25, nửa đời 14 ngày.
- `cases(...)`: ca đã học theo (agent, ngữ cảnh). Ca chỉ được đọc trong đúng ngữ cảnh của nó.
- `waits(...)`: quyết định chờ kèm điều kiện gỡ, tối đa một lần xét lại mỗi (agent, tin gốc).
- `changes(...)`: trước/sau của mọi lần đổi chính sách (nhãn dịch ngưỡng, `offset_set`, `eagerness_set`).
- `review_state(agent_key, last_review_at)`: mốc tự rà soát (phần L dùng).
- `chains(context_ref, message_id, root_ref, depth, author_key, via_key)`: chuỗi tin trong nhóm để chặn độ sâu và A->B->A.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable, Optional

STORE_NAME = "agent_judge.sqlite3"
OFFSET_LIMIT = 0.25
OFFSET_HALF_LIFE_S = 14 * 86400.0
EAGERNESS = ("low", "medium", "high")
DEFAULT_EAGERNESS = "medium"
VERDICTS = ("speak", "wait", "silent")
KINDS = ("direct", "message", "related", "wait", "proactive", "clarify")
LABELS = ("should_speak", "should_silent")
WAIT_KINDS = ("owner_message", "speaker_done", "job_change")
WAIT_STATUSES = ("waiting", "released", "expired", "rejudged", "cancelled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles(
  agent_key TEXT PRIMARY KEY, role_text TEXT NOT NULL DEFAULT '', eagerness TEXT NOT NULL DEFAULT 'medium',
  role_hash TEXT NOT NULL DEFAULT '', eagerness_source TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent_key TEXT NOT NULL, context_ref TEXT NOT NULL,
  source_event TEXT NOT NULL, root_ref TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'message',
  verdict TEXT NOT NULL, address TEXT NOT NULL DEFAULT 'none', score REAL, threshold REAL,
  reason TEXT NOT NULL DEFAULT '', silence_code TEXT NOT NULL DEFAULT '', wait_until_json TEXT NOT NULL DEFAULT '{}',
  ask_clarify TEXT NOT NULL DEFAULT '', volunteer INTEGER NOT NULL DEFAULT 0, ledger_ref TEXT NOT NULL DEFAULT '',
  message_ref TEXT NOT NULL DEFAULT '', features_json TEXT NOT NULL DEFAULT '{}', excerpt TEXT NOT NULL DEFAULT '',
  label TEXT NOT NULL DEFAULT '', label_source TEXT NOT NULL DEFAULT '', label_at REAL,
  label_effect TEXT NOT NULL DEFAULT '', label_delta REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS decisions_agent ON decisions(agent_key, context_ref, id);
CREATE INDEX IF NOT EXISTS decisions_root ON decisions(context_ref, root_ref, kind);
CREATE INDEX IF NOT EXISTS decisions_msg ON decisions(message_ref);
CREATE UNIQUE INDEX IF NOT EXISTS decisions_once ON decisions(agent_key, context_ref, source_event, kind)
  WHERE kind IN ('direct', 'message', 'related');
CREATE TABLE IF NOT EXISTS offsets(
  agent_key TEXT NOT NULL, context_ref TEXT NOT NULL, offset REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL,
  PRIMARY KEY(agent_key, context_ref));
CREATE TABLE IF NOT EXISTS cases(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent_key TEXT NOT NULL, context_ref TEXT NOT NULL,
  text_sha TEXT NOT NULL DEFAULT '', features_json TEXT NOT NULL DEFAULT '{}', label TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1, decision_id INTEGER, source TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS cases_ctx ON cases(agent_key, context_ref, id);
CREATE TABLE IF NOT EXISTS waits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, decision_id INTEGER NOT NULL UNIQUE, agent_key TEXT NOT NULL,
  context_ref TEXT NOT NULL, root_ref TEXT NOT NULL DEFAULT '', source_event TEXT NOT NULL DEFAULT '',
  until_kinds TEXT NOT NULL DEFAULT '[]', until_ts REAL NOT NULL, job_refs_json TEXT NOT NULL DEFAULT '[]',
  payload_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'waiting', rejudged INTEGER NOT NULL DEFAULT 0,
  reason_id INTEGER, release_event TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS waits_open ON waits(status, context_ref);
CREATE TABLE IF NOT EXISTS changes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent_key TEXT NOT NULL, context_ref TEXT NOT NULL DEFAULT '*',
  kind TEXT NOT NULL, before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT '', source_ref TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS changes_agent ON changes(agent_key, id);
CREATE TABLE IF NOT EXISTS review_state(agent_key TEXT PRIMARY KEY, last_review_at REAL);
CREATE TABLE IF NOT EXISTS chains(
  context_ref TEXT NOT NULL, message_id INTEGER NOT NULL, root_ref TEXT NOT NULL, depth INTEGER NOT NULL,
  author_key TEXT NOT NULL DEFAULT '', via_key TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
  PRIMARY KEY(context_ref, message_id));
"""


def _j(v: Any) -> str:
    return json.dumps(v if v is not None else {}, ensure_ascii=False, sort_keys=True)


def _now(now: Optional[float]) -> float:
    return time.time() if now is None else float(now)


def decay(value: float, updated_at: float, now: float) -> float:
    """Độ lệch co dần về 0 theo nửa đời 14 ngày kể từ lần cập nhật. Tuổi âm (lệch đồng hồ) kẹp về 0."""
    age = max(0.0, float(now) - float(updated_at))
    return float(value) * (0.5 ** (age / OFFSET_HALF_LIFE_S))


def clamp_offset(v: float) -> float:
    return max(-OFFSET_LIMIT, min(OFFSET_LIMIT, float(v)))


class JudgeStore:
    """Thao tác trên `agent_judge.sqlite3`. Mọi thao tác ghi đi qua `_Tx` (BEGIN IMMEDIATE)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with closing(self._conn()) as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    class _Tx:
        def __init__(self, store: "JudgeStore"):
            self.c = store._conn()

        def __enter__(self):
            self.c.execute("BEGIN IMMEDIATE")
            return self.c

        def __exit__(self, et, ev, tb):
            try:
                self.c.execute("ROLLBACK" if et else "COMMIT")
            finally:
                self.c.close()
            return False

    # ───────────── hồ sơ ─────────────

    def profile(self, agent_key: str) -> dict:
        """Hồ sơ của agent; chưa có thì trả mặc định (không ghi)."""
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM profiles WHERE agent_key=?", (str(agent_key),)).fetchone()
        if r is None:
            return {"agent_key": str(agent_key), "role_text": "", "eagerness": DEFAULT_EAGERNESS, "role_hash": "",
                    "eagerness_source": "", "updated_at": None}
        return dict(r)

    def upsert_profile(self, agent_key: str, *, role_text: Optional[str] = None, role_hash: Optional[str] = None,
                       eagerness: Optional[str] = None, source: str = "", now: Optional[float] = None) -> dict:
        t = _now(now)
        cur = self.profile(agent_key)
        role = cur["role_text"] if role_text is None else str(role_text)[:2000]
        rh = cur["role_hash"] if role_hash is None else str(role_hash)
        eag = cur["eagerness"] if eagerness is None else str(eagerness)
        if eag not in EAGERNESS:
            raise ValueError("invalid eagerness")
        src = cur["eagerness_source"] if eagerness is None else str(source or "")
        with self._Tx(self) as c:
            c.execute("INSERT INTO profiles(agent_key,role_text,eagerness,role_hash,eagerness_source,updated_at) "
                      "VALUES(?,?,?,?,?,?) ON CONFLICT(agent_key) DO UPDATE SET role_text=excluded.role_text, "
                      "eagerness=excluded.eagerness, role_hash=excluded.role_hash, "
                      "eagerness_source=excluded.eagerness_source, updated_at=excluded.updated_at",
                      (str(agent_key), role, eag, rh, src, t))
        return self.profile(agent_key)

    # ───────────── quyết định ─────────────

    @staticmethod
    def _decision(r) -> Optional[dict]:
        if r is None:
            return None
        d = dict(r)
        for k in ("wait_until_json", "features_json"):
            try:
                d[k[:-5]] = json.loads(d.pop(k) or "{}")
            except ValueError:
                d[k[:-5]] = {}
        d["volunteer"] = bool(d.get("volunteer"))
        return d

    def add_decision(self, d: dict, now: Optional[float] = None) -> int:
        """Ghi một quyết định. Loại `direct`/`message`/`related` có tối đa một dòng mỗi (agent, ngữ cảnh, nguồn, loại):
        gọi lại trả đúng dòng cũ (chạy lại an toàn)."""
        if d.get("verdict") not in VERDICTS:
            raise ValueError("invalid verdict")
        kind = str(d.get("kind") or "message")
        if kind not in KINDS:
            raise ValueError("invalid decision kind")
        t = _now(now if now is not None else d.get("created_at"))
        with self._Tx(self) as c:
            if kind in ("direct", "message", "related"):
                old = c.execute("SELECT id FROM decisions WHERE agent_key=? AND context_ref=? AND source_event=? AND kind=?",
                                (d["agent_key"], d["context_ref"], d["source_event"], kind)).fetchone()
                if old is not None:
                    return int(old["id"])
            cur = c.execute(
                "INSERT INTO decisions(agent_key,context_ref,source_event,root_ref,kind,verdict,address,score,threshold,"
                "reason,silence_code,wait_until_json,ask_clarify,volunteer,ledger_ref,message_ref,features_json,excerpt,"
                "created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(d["agent_key"]), str(d["context_ref"]), str(d["source_event"]), str(d.get("root_ref") or ""), kind,
                 d["verdict"], str(d.get("address") or "none"), d.get("score"), d.get("threshold"),
                 str(d.get("reason") or "")[:300], str(d.get("silence_code") or "")[:40],
                 _j(d.get("wait_until") or {}), str(d.get("ask_clarify") or "")[:300], 1 if d.get("volunteer") else 0,
                 str(d.get("ledger_ref") or ""), str(d.get("message_ref") or ""), _j(d.get("features") or {}),
                 str(d.get("excerpt") or "")[:240], t))
            return int(cur.lastrowid)

    def get_decision(self, decision_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            return self._decision(c.execute("SELECT * FROM decisions WHERE id=?", (int(decision_id),)).fetchone())

    def decision_by_message(self, message_ref: str) -> Optional[dict]:
        """Quyết định đã sinh ra tin `message_ref` (mới nhất)."""
        with closing(self._conn()) as c:
            return self._decision(c.execute("SELECT * FROM decisions WHERE message_ref=? ORDER BY id DESC LIMIT 1",
                                            (str(message_ref),)).fetchone())

    def find_decision(self, agent_key: str, context_ref: str, source_event: str, kind: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            return self._decision(c.execute(
                "SELECT * FROM decisions WHERE agent_key=? AND context_ref=? AND source_event=? AND kind=? "
                "ORDER BY id DESC LIMIT 1", (agent_key, context_ref, source_event, kind)).fetchone())

    def decisions(self, agent_key: Optional[str] = None, context_ref: Optional[str] = None, limit: int = 50,
                  kinds: Optional[Iterable[str]] = None) -> list:
        q, args = "SELECT * FROM decisions WHERE 1=1", []
        if agent_key is not None:
            q += " AND agent_key=?"
            args.append(str(agent_key))
        if context_ref is not None:
            q += " AND context_ref=?"
            args.append(str(context_ref))
        if kinds:
            ks = list(kinds)
            q += f" AND kind IN ({','.join('?' * len(ks))})"
            args.extend(ks)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(500, int(limit))))
        with closing(self._conn()) as c:
            return [self._decision(r) for r in c.execute(q, args).fetchall()]

    def root_decisions(self, context_ref: str, root_ref: str, kinds: Iterable[str]) -> list:
        ks = list(kinds)
        with closing(self._conn()) as c:
            rows = c.execute(f"SELECT * FROM decisions WHERE context_ref=? AND root_ref=? AND kind IN "
                             f"({','.join('?' * len(ks))}) ORDER BY id", [context_ref, root_ref] + ks).fetchall()
        return [self._decision(r) for r in rows]

    def latest_silent(self, context_ref: str, agent_key: Optional[str] = None, since: float = 0.0) -> Optional[dict]:
        q = ("SELECT * FROM decisions WHERE context_ref=? AND verdict IN ('silent','wait') AND address='none' "
             "AND created_at>=?")
        args: list = [context_ref, float(since)]
        if agent_key:
            q += " AND agent_key=?"
            args.append(agent_key)
        with closing(self._conn()) as c:
            return self._decision(c.execute(q + " ORDER BY id DESC LIMIT 1", args).fetchone())

    def set_message(self, decision_id: int, message_ref: str) -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE decisions SET message_ref=? WHERE id=?", (str(message_ref), int(decision_id)))

    def set_outcome(self, decision_id: int, verdict: str, silence_code: str = "", reason: Optional[str] = None,
                    volunteer: Optional[bool] = None) -> None:
        """Hạ một quyết định (vd. tự lên tiếng mà lượt bị chặn): ghi kết cục thật, không xoá dòng."""
        if verdict not in VERDICTS:
            raise ValueError("invalid verdict")
        with self._Tx(self) as c:
            c.execute("UPDATE decisions SET verdict=?, silence_code=?, reason=COALESCE(?, reason), "
                      "volunteer=COALESCE(?, volunteer) WHERE id=?",
                      (verdict, str(silence_code or "")[:40], None if reason is None else str(reason)[:300],
                       None if volunteer is None else (1 if volunteer else 0), int(decision_id)))

    def merge_features(self, decision_id: int, extra: dict) -> None:
        """Gộp thêm khoá vào `features` của một quyết định (vd. `volunteer_origin` khi lượt tự lên tiếng bị hạ)."""
        with self._Tx(self) as c:
            r = c.execute("SELECT features_json FROM decisions WHERE id=?", (int(decision_id),)).fetchone()
            if r is None:
                return
            try:
                feats = json.loads(r["features_json"] or "{}")
            except ValueError:
                feats = {}
            feats.update(extra or {})
            c.execute("UPDATE decisions SET features_json=? WHERE id=?", (_j(feats), int(decision_id)))

    def set_label(self, decision_id: int, label: str, source: str, at: float, effect: str, delta: float) -> None:
        with self._Tx(self) as c:
            c.execute("UPDATE decisions SET label=?, label_source=?, label_at=?, label_effect=?, label_delta=? WHERE id=?",
                      (str(label or ""), str(source or ""), float(at), str(effect or ""), float(delta),
                       int(decision_id)))

    def count_labels_after(self, agent_key: str, since: float) -> int:
        with closing(self._conn()) as c:
            return int(c.execute("SELECT COUNT(*) FROM decisions WHERE agent_key=? AND label<>'' AND label_at>=? "
                                 "AND label_effect='applied'", (agent_key, float(since))).fetchone()[0])

    def prune(self, max_age_s: float = 90 * 86400.0, now: Optional[float] = None) -> int:
        """Bỏ quyết định im cũ không nhãn (giữ mọi dòng có nhãn, có tin hay đang chờ)."""
        t = _now(now)
        with self._Tx(self) as c:
            return c.execute("DELETE FROM decisions WHERE created_at<? AND label='' AND message_ref='' "
                             "AND id NOT IN (SELECT decision_id FROM waits WHERE status='waiting')",
                             (t - float(max_age_s),)).rowcount

    # ───────────── độ lệch ngưỡng ─────────────

    def get_offset(self, agent_key: str, context_ref: str, now: Optional[float] = None) -> float:
        with closing(self._conn()) as c:
            r = c.execute("SELECT offset, updated_at FROM offsets WHERE agent_key=? AND context_ref=?",
                          (str(agent_key), str(context_ref))).fetchone()
        if r is None:
            return 0.0
        return decay(float(r["offset"]), float(r["updated_at"]), _now(now))

    def adjust_offset(self, agent_key: str, context_ref: str, delta: float, now: Optional[float] = None) -> tuple:
        """Cộng `delta` vào độ lệch (đã tính phần nhạt dần), kẹp ±0.25. Trả (trước, sau)."""
        t = _now(now)
        with self._Tx(self) as c:
            r = c.execute("SELECT offset, updated_at FROM offsets WHERE agent_key=? AND context_ref=?",
                          (str(agent_key), str(context_ref))).fetchone()
            before = decay(float(r["offset"]), float(r["updated_at"]), t) if r else 0.0
            after = clamp_offset(before + float(delta))
            c.execute("INSERT INTO offsets(agent_key,context_ref,offset,updated_at) VALUES(?,?,?,?) "
                      "ON CONFLICT(agent_key,context_ref) DO UPDATE SET offset=excluded.offset, "
                      "updated_at=excluded.updated_at", (str(agent_key), str(context_ref), after, t))
        return before, after

    def set_offset(self, agent_key: str, context_ref: str, value: float, now: Optional[float] = None) -> tuple:
        t = _now(now)
        before = self.get_offset(agent_key, context_ref, t)
        after = clamp_offset(value)
        with self._Tx(self) as c:
            c.execute("INSERT INTO offsets(agent_key,context_ref,offset,updated_at) VALUES(?,?,?,?) "
                      "ON CONFLICT(agent_key,context_ref) DO UPDATE SET offset=excluded.offset, "
                      "updated_at=excluded.updated_at", (str(agent_key), str(context_ref), after, t))
        return before, after

    def offsets(self, agent_key: str, now: Optional[float] = None) -> dict:
        t = _now(now)
        with closing(self._conn()) as c:
            rows = c.execute("SELECT context_ref, offset, updated_at FROM offsets WHERE agent_key=?",
                             (str(agent_key),)).fetchall()
        return {r["context_ref"]: decay(float(r["offset"]), float(r["updated_at"]), t) for r in rows}

    # ───────────── ca ─────────────

    def add_case(self, agent_key: str, context_ref: str, *, text_sha: str, features: dict, label: str, weight: float,
                 decision_id: Optional[int], source: str, now: Optional[float] = None) -> int:
        with self._Tx(self) as c:
            cur = c.execute("INSERT INTO cases(agent_key,context_ref,text_sha,features_json,label,weight,decision_id,"
                            "source,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                            (str(agent_key), str(context_ref), str(text_sha), _j(features), str(label), float(weight),
                             decision_id, str(source or ""), _now(now)))
            return int(cur.lastrowid)

    def delete_cases_by_decision(self, decision_id: int) -> int:
        with self._Tx(self) as c:
            return c.execute("DELETE FROM cases WHERE decision_id=?", (int(decision_id),)).rowcount

    def cases(self, agent_key: str, context_ref: str, limit: int = 3) -> list:
        """Ca của ĐÚNG (agent, ngữ cảnh), mới nhất trước. Không bao giờ đọc ca của ngữ cảnh khác."""
        with closing(self._conn()) as c:
            rows = c.execute("SELECT * FROM cases WHERE agent_key=? AND context_ref=? ORDER BY id DESC LIMIT ?",
                             (str(agent_key), str(context_ref), max(1, int(limit)))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["features"] = json.loads(d.pop("features_json") or "{}")
            except ValueError:
                d["features"] = {}
            out.append(d)
        return out

    # ───────────── chờ ─────────────

    @staticmethod
    def _wait(r) -> Optional[dict]:
        if r is None:
            return None
        d = dict(r)
        for k, dv in (("until_kinds", []), ("job_refs_json", []), ("payload_json", {})):
            try:
                v = json.loads(d.get(k) or json.dumps(dv))
            except ValueError:
                v = dv
            d[k.replace("_json", "")] = v
            if k.endswith("_json"):
                d.pop(k, None)
        return d

    def add_wait(self, *, decision_id: int, agent_key: str, context_ref: str, root_ref: str, source_event: str,
                 until_kinds: list, until_ts: float, job_refs: list, payload: dict, rejudged: bool = False,
                 now: Optional[float] = None) -> int:
        t = _now(now)
        with self._Tx(self) as c:
            old = c.execute("SELECT id FROM waits WHERE decision_id=?", (int(decision_id),)).fetchone()
            if old is not None:
                return int(old["id"])
            cur = c.execute("INSERT INTO waits(decision_id,agent_key,context_ref,root_ref,source_event,until_kinds,"
                            "until_ts,job_refs_json,payload_json,status,rejudged,created_at,updated_at) "
                            "VALUES(?,?,?,?,?,?,?,?,?,'waiting',?,?,?)",
                            (int(decision_id), agent_key, context_ref, root_ref, source_event,
                             json.dumps(list(until_kinds)), float(until_ts), json.dumps(list(job_refs)),
                             _j(payload), 1 if rejudged else 0, t, t))
            return int(cur.lastrowid)

    def get_wait(self, wait_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            return self._wait(c.execute("SELECT * FROM waits WHERE id=?", (int(wait_id),)).fetchone())

    def open_waits(self, context_ref: Optional[str] = None) -> list:
        q, args = "SELECT * FROM waits WHERE status='waiting'", []
        if context_ref and context_ref != "*":
            q += " AND context_ref=?"
            args.append(context_ref)
        with closing(self._conn()) as c:
            return [self._wait(r) for r in c.execute(q + " ORDER BY id", args).fetchall()]

    def stale_released(self, before: float) -> list:
        """Lần chờ đã gỡ (`released`) mà chưa xét lại, gỡ trước mốc `before`."""
        with closing(self._conn()) as c:
            return [self._wait(r) for r in c.execute("SELECT * FROM waits WHERE status='released' AND updated_at<? "
                                                     "ORDER BY id", (float(before),)).fetchall()]

    def waits_of(self, agent_key: str, context_ref: Optional[str] = None) -> list:
        q, args = "SELECT * FROM waits WHERE agent_key=?", [agent_key]
        if context_ref:
            q += " AND context_ref=?"
            args.append(context_ref)
        with closing(self._conn()) as c:
            return [self._wait(r) for r in c.execute(q + " ORDER BY id", args).fetchall()]

    def move_wait(self, wait_id: int, status: str, *, frm: str = "waiting", release_event: str = "",
                  reason_id: Optional[int] = None, now: Optional[float] = None) -> bool:
        """CAS trạng thái của một lần chờ. Trả True khi đổi được (một người gỡ duy nhất)."""
        if status not in WAIT_STATUSES:
            raise ValueError("invalid wait status")
        with self._Tx(self) as c:
            return c.execute("UPDATE waits SET status=?, release_event=CASE WHEN ?='' THEN release_event ELSE ? END, "
                             "reason_id=COALESCE(?, reason_id), updated_at=? WHERE id=? AND status=?",
                             (status, release_event, release_event, reason_id, _now(now), int(wait_id),
                              frm)).rowcount == 1

    def wait_by_reason(self, reason_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            return self._wait(c.execute("SELECT * FROM waits WHERE reason_id=? ORDER BY id DESC LIMIT 1",
                                        (int(reason_id),)).fetchone())

    # ───────────── nhật ký đổi chính sách ─────────────

    def add_change(self, agent_key: str, context_ref: str, kind: str, before: Any, after: Any, source: str,
                   source_ref: str = "", now: Optional[float] = None) -> int:
        with self._Tx(self) as c:
            cur = c.execute("INSERT INTO changes(agent_key,context_ref,kind,before_json,after_json,source,source_ref,"
                            "created_at) VALUES(?,?,?,?,?,?,?,?)",
                            (agent_key, context_ref or "*", kind, _j(before), _j(after), str(source or ""),
                             str(source_ref or ""), _now(now)))
            return int(cur.lastrowid)

    def changes(self, agent_key: str, limit: int = 20) -> list:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT * FROM changes WHERE agent_key=? ORDER BY id DESC LIMIT ?",
                             (agent_key, max(1, int(limit)))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("before_json", "after_json"):
                try:
                    d[k[:-5]] = json.loads(d.pop(k) or "{}")
                except ValueError:
                    d[k[:-5]] = {}
            out.append(d)
        return out

    # ───────────── tự rà soát (phần L dùng) ─────────────

    def last_review_at(self, agent_key: str) -> Optional[float]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT last_review_at FROM review_state WHERE agent_key=?", (agent_key,)).fetchone()
        return float(r["last_review_at"]) if r and r["last_review_at"] is not None else None

    def set_review_at(self, agent_key: str, at: Optional[float] = None) -> None:
        with self._Tx(self) as c:
            c.execute("INSERT INTO review_state(agent_key,last_review_at) VALUES(?,?) ON CONFLICT(agent_key) "
                      "DO UPDATE SET last_review_at=excluded.last_review_at", (agent_key, _now(at)))

    # ───────────── chuỗi tin trong nhóm ─────────────

    def set_chain(self, context_ref: str, message_id: int, root_ref: str, depth: int, author_key: str = "",
                  via_key: str = "", now: Optional[float] = None) -> None:
        with self._Tx(self) as c:
            c.execute("INSERT OR IGNORE INTO chains(context_ref,message_id,root_ref,depth,author_key,via_key,created_at) "
                      "VALUES(?,?,?,?,?,?,?)", (context_ref, int(message_id), root_ref, int(depth), author_key,
                                                via_key, _now(now)))

    def chain(self, context_ref: str, message_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM chains WHERE context_ref=? AND message_id=?",
                          (context_ref, int(message_id))).fetchone()
        return dict(r) if r else None
