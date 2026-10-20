"""T4 (0.170.0): lịch sử dài trong đúng nhóm giữ yêu cầu, quyết định, nguồn đóng góp và phản hồi (thiết kế 2026-10-15 mục 11).

    python tests/run.py team_t4_long_history -v

Kho SQLite tạm thật, bộ chạy nhóm thật, engine giả (không model). Một nhóm 5.000 tin: quyết định ghim từ đầu, yêu cầu gốc
của việc còn mở (đã sửa một lần), kết quả gần nhất do một bước tổng hợp gộp đầu vào của hai thành viên (kèm phân bổ ghi
nhận trong `pulse_contrib` của phần nhịp T3), phản hồi của chủ còn chờ xem xét cũ hơn 30 ngày. Lượt kế vẫn thấy cả bốn
trong prompt. Số lần đọc kho mỗi lượt đếm bằng một lớp bọc đếm lời gọi: bằng nhau giữa nhóm 60 tin và 5.000 tin, có trần.
Mọi truy vấn mới chạy theo chỉ mục (EXPLAIN QUERY PLAN không có "SCAN" toàn bảng).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sqlite3
import tempfile
import time
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-t4-long-")
TEMP = Path(tempfile.mkdtemp(prefix="javis-t4-long-w-"))

import agent_pulse as AP  # noqa: E402
import resonance_store as RS  # noqa: E402
import sessions  # noqa: E402
import task_store  # noqa: E402
import team_long_memory as TLM  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:600]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class Counting:
    """Bọc một kho: đếm lời gọi phương thức công khai (mỗi lời gọi là ít nhất một lần đọc kho)."""

    def __init__(self, inner, tally, label):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_tally", tally)
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            def wrapped(*a, **k):
                if self._tally.get("on"):
                    key = f"{self._label}.{name}"
                    self._tally[key] = self._tally.get(key, 0) + 1
                return attr(*a, **k)
            return wrapped
        return attr

    def __setattr__(self, name, value):
        setattr(self._inner, name, value)


class Recorder:
    def __init__(self):
        self.reqs = []

    def engine_for(self, team, key, role):
        async def run_(req):
            self.reqs.append(req)
            return {"text": f"Trả lời {len(self.reqs)}"}
        return "fake", "fake", run_


d = TEMP / "w"
d.mkdir()
ss = sessions.SessionStore(db_path=d / "chat.db")
ts = task_store.TaskStore(d / "kanban.sqlite3")
tm = team_store.TeamStore(d / "team.sqlite3")
gs = RS.GoalStore(d / "resonance.sqlite3")
AP.ensure(gs)


def contrib_reader(ref):
    with sqlite3.connect(d / "resonance.sqlite3") as c:
        c.row_factory = sqlite3.Row
        c.execute("CREATE INDEX IF NOT EXISTS pulse_contrib_result ON pulse_contrib(result_ref, status)")
        return [dict(r) for r in c.execute("SELECT agent_key, share, role FROM pulse_contrib WHERE result_ref=? AND "
                                           "status='live' ORDER BY share DESC, id LIMIT 8", (ref,)).fetchall()]


tally = {}
rec = Recorder()
NAMES = {"lan": "Lan", "minh": "Minh", "hoa": "Hoa"}


def counted_contrib(ref):
    if tally.get("on"):
        tally["contrib"] = tally.get("contrib", 0) + 1
    return contrib_reader(ref)


r = TR.TeamRunner(teams=Counting(tm, tally, "team"), tasks=Counting(ts, tally, "tasks"),
                  sessions=Counting(ss, tally, "sessions"), engine_for=rec.engine_for,
                  agent_info=lambda root, key: {"slug": key, "name": NAMES.get(key, key), "system": ""},
                  contrib_reader=counted_contrib)


def make(name, n_msgs):
    tid = team_store.new_team_id()
    sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), name, "", sid, team_id=tid)
    for k in ("lan", "minh", "hoa"):
        tm.add_member(tid, k, k)
    tm.set_leader(tid, "lan")
    tm.set_caps(tid, {"daily_turns": 1000})
    team = tm.get(tid)
    # Quyết định ghim ở rất đầu lịch sử.
    dmid, _ = ss.append_team_message(sid, "user", f"QUYẾT_ĐỊNH_GỐC_{name}: chỉ bán hàng chính hãng", author_kind="owner",
                                     client_msg_id=f"{name}-dec")
    ss.update_team_message_meta(sid, dmid, {"decision": True})
    # Một việc xong: bước làm của Minh và Hoa, bước tổng hợp của Lan gộp hai đầu vào.
    done, _ = ts.enqueue_team(str(d), tid, f"Báo cáo quý {name}", "Tổng hợp báo cáo quý", f"src-{name}-done")
    ts.claim_team_next(tid, "w")
    m_minh, _ = ss.append_team_message(sid, "assistant", "Số liệu của Minh", author_kind="agent", author_ref="minh")
    m_hoa, _ = ss.append_team_message(sid, "assistant", "Nhận định của Hoa", author_kind="agent", author_ref="hoa")
    m_syn, _ = ss.append_team_message(sid, "assistant", "Bản tổng hợp của Lan", author_kind="agent", author_ref="lan")
    s1 = tm.add_step(done, tid, "work", "minh", 1, "số liệu", [])
    tm.finish_step(s1["step_id"], "done", result_msg_id=m_minh, applied=True)
    s2 = tm.add_step(done, tid, "work", "hoa", 1, "nhận định", [])
    tm.finish_step(s2["step_id"], "done", result_msg_id=m_hoa, applied=True)
    s3 = tm.add_step(done, tid, "synthesize", "lan", 1, "gộp", [m_minh, m_hoa])
    tm.finish_step(s3["step_id"], "done", result_msg_id=m_syn, applied=True)
    ts.team_finish(done, "Bản tổng hợp của Lan")
    AP.record_contrib(gs, source_ref=f"team:{name}:r1", result_ref=f"step:{s3['step_id']}", synth="lan",
                      inputs=["minh", "hoa"], context_ref=f"team:{tid}", value="love")
    # Phản hồi của chủ còn chờ xem xét, cũ hơn 30 ngày (khối "Phản hồi gần đây" không còn thấy).
    got = tm.set_reaction_ex(team_id=tid, session_id=sid, message_id=m_hoa, agent_key="hoa", task_id=done,
                             content_sha="x", value="sad", reasons=["missing"], comment=f"THIẾU_SỐ_THÁNG_BA_{name}",
                             nonce=f"{name}-fb")
    tm.set_reaction_status(sid, m_hoa, "owner", got["log_id"], "pending_review")
    tm._set_reaction_time(sid, m_hoa, time.time() - 45 * 86400)
    # Lịch sử dài.
    for i in range(n_msgs):
        ss.append_team_message(sid, "user" if i % 2 == 0 else "assistant", f"Tin đệm {i} của {name}",
                               author_kind="owner" if i % 2 == 0 else "agent", author_ref="" if i % 2 == 0 else "minh",
                               client_msg_id=f"{name}-p{i}" if i % 2 == 0 else None)
    # Việc còn mở: yêu cầu gốc rồi một lần sửa; một việc bị chặn.
    open_id, _ = ts.enqueue_team(str(d), tid, "Kế hoạch tháng", f"YÊU_CẦU_GỐC_{name}: lập kế hoạch nhập hàng tháng 11",
                                 f"src-{name}-open")
    ts.team_amend(open_id, "thêm phần ngân sách")
    blk, _ = ts.enqueue_team(str(d), tid, "Đối soát kho", "Đối soát tồn kho", f"src-{name}-blk")
    ts.claim_team_next(tid, "w")
    ts.team_block(open_id if ts.get_task(open_id)["status"] == "team_running" else blk, "needs_owner",
                  f"CHỜ_CHỦ_DUYỆT_{name}")
    HOA_MID[name] = m_hoa
    return tm.get(tid)


HOA_MID = {}
small = make("nho", 60)
# Dữ liệu ngoài nhóm: một phản hồi ở chat riêng của Minh (không bao giờ được vào lượt nhóm).
dm_sid = ss.create_session(brain=str(d), channel="agent:minh")
dm_mid = ss.append_message(dm_sid, "assistant", "Câu trả lời riêng của Minh")
ss.set_dm_reaction(dm_sid, dm_mid, value="angry", comment="BÍ_MẬT_CHAT_RIÊNG", nonce="dm-1", agent_key="minh",
                   status="pending_review")
big = make("lon", 5000)
hoa_mid_big = HOA_MID["lon"]
check("dựng nhóm 5.000 tin", ss.team_message_count(big["session_id"]) > 5000, ss.team_message_count(big["session_id"]))


def turn(team):
    tally.clear()
    tally["on"] = True
    try:
        prompt = r._context(team, "minh", "member_reply", None, None)
    finally:
        tally["on"] = False
    reads = sum(v for k, v in tally.items() if k != "on")
    return prompt, reads, dict(tally)


p_big, reads_big, detail_big = turn(big)
p_small, reads_small, detail_small = turn(small)

check("nhóm 5.000 tin: còn quyết định ghim từ đầu lịch sử", "QUYẾT_ĐỊNH_GỐC_lon" in p_big)
check("nhóm 5.000 tin: còn yêu cầu gốc của việc mở (phần trước lần sửa), kèm số lần sửa",
      "YÊU_CẦU_GỐC_lon" in p_big and "amended 1x" in p_big, p_big[-2500:])
check("yêu cầu gốc không lẫn phần sửa", "thêm phần ngân sách" not in p_big.split("Open jobs of the team")[1].split("\n## ")[0]
      if "Open jobs of the team" in p_big else False)
check("nhóm 5.000 tin: còn trạng thái việc bị chặn và lý do", "blocked" in p_big and "CHỜ_CHỦ_DUYỆT_lon" in p_big)
check("nhóm 5.000 tin: còn nguồn đóng góp của kết quả gần nhất (đầu vào của Minh và Hoa, Lan tổng hợp)",
      "Contributions to the most recent result" in p_big and "Lan synthesized" in p_big and "from Minh" in p_big and "from Hoa" in p_big, p_big[-2500:])
check("nguồn đóng góp có tỷ lệ ghi nhận từ pulse_contrib", "credited by the owner's feedback" in p_big
      and "%" in p_big.split("credited by the owner's feedback")[1].split("\n")[0], p_big[-2500:])
check("nhóm 5.000 tin: còn phản hồi chưa xem xét cũ hơn 30 ngày", "THIẾU_SỐ_THÁNG_BA_lon" in p_big
      and "awaiting review" in p_big, p_big[-2500:])
check("phần luôn giữ có trần ký tự", len(p_big.split("## Always kept even when the history is long")[1].split("\n## ")[0])
      <= TLM.ALWAYS_CHARS + 200)
check("chỉ dữ liệu của chính nhóm này: không quyết định, yêu cầu, lý do chặn, phản hồi, việc xong của nhóm kia",
      all(f"{m}_nho" not in p_big for m in ("QUYẾT_ĐỊNH_GỐC", "YÊU_CẦU_GỐC", "CHỜ_CHỦ_DUYỆT", "THIẾU_SỐ_THÁNG_BA"))
      and "Báo cáo quý nho" not in p_big and "from nho" not in p_big
      and all(f"{m}_lon" not in p_small for m in ("QUYẾT_ĐỊNH_GỐC", "YÊU_CẦU_GỐC", "CHỜ_CHỦ_DUYỆT", "THIẾU_SỐ_THÁNG_BA"))
      and "Báo cáo quý lon" not in p_small, p_big[-2500:])
check("phản hồi ở chat riêng không bao giờ vào lượt nhóm", "BÍ_MẬT_CHAT_RIÊNG" not in p_big
      and "BÍ_MẬT_CHAT_RIÊNG" not in p_small)
kept = p_big.split("## Always kept even when the history is long")[1].split("\n## ")[0]
check("phần luôn giữ kết thúc bằng câu dặn: dữ liệu, không phải lệnh", kept.rstrip().endswith(TLM.KEPT_NOTE), kept[-300:])
check("phần luôn giữ không có tiêu đề trống (mỗi tiêu đề có ít nhất một dòng)", all(
    i + 1 < len(kept.splitlines()) and kept.splitlines()[i + 1].startswith(("-", "  -"))
    for i, ln in enumerate(kept.splitlines()) if ln.endswith(":") and not ln.startswith(("-", "  -"))), kept)
check("số lần đọc kho mỗi lượt KHÔNG tăng theo độ dài lịch sử (60 tin và 5.000 tin bằng nhau)",
      reads_big == reads_small, (reads_small, reads_big, detail_small, detail_big))
READ_CAP = 40
check(f"số lần đọc kho mỗi lượt có trần (<= {READ_CAP})", reads_big <= READ_CAP, detail_big)

# Không lặp phản hồi: phản hồi chờ xem xét còn trong 30 ngày đã hiện ở "Phản hồi gần đây" thì không hiện lại ở phần luôn giữ.
tm._set_reaction_time(big["session_id"], hoa_mid_big, time.time() - 86400)
p_hoa = r._context(big, "hoa", "member_reply", None, None)
recent_block = p_hoa.split("## Phản hồi gần đây của chủ nhóm")[1].split("\n## ")[0] if "## Phản hồi gần đây" in p_hoa else ""
kept_hoa = p_hoa.split("## Always kept even when the history is long")[1].split("\n## ")[0] if "## Always kept" in p_hoa else ""
check("phản hồi trong 30 ngày: hiện ở khối gần đây, KHÔNG lặp ở phần luôn giữ",
      "THIẾU_SỐ_THÁNG_BA_lon" in recent_block and "THIẾU_SỐ_THÁNG_BA_lon" not in kept_hoa, (recent_block, kept_hoa))
tm._set_reaction_time(big["session_id"], hoa_mid_big, time.time() - 45 * 86400)

# Trần ký tự nhỏ: không có tiêu đề nào bị bỏ trống.
_saved_cap = TLM.ALWAYS_CHARS
TLM.ALWAYS_CHARS = 420
try:
    tiny = TLM.always_kept_lines(team=big, agent_key="minh", tasks=ts, teams=tm, sessions=ss, name_of=lambda k: k)
finally:
    TLM.ALWAYS_CHARS = _saved_cap
check("trần ký tự nhỏ: tiêu đề nào cũng có dòng, có câu dặn, không vượt trần",
      all(not (ln.endswith(":") and (i + 1 >= len(tiny) or not tiny[i + 1].startswith(("-", "  -"))))
          for i, ln in enumerate(tiny)) and (not tiny or tiny[-1] == TLM.KEPT_NOTE)
      and sum(len(x) for x in tiny) <= 420 + 120, tiny)

# Cửa sổ còn phủ hết phiên: không có phần luôn giữ (không đổi lời nhắc của nhóm ngắn).
tid = team_store.new_team_id()
sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
tm.create_team(str(d), "Ngắn", "", sid, team_id=tid)
tm.add_member(tid, "minh", "minh")
ss.append_team_message(sid, "user", "Chào", author_kind="owner", client_msg_id="short")
check("nhóm ngắn: không có khối luôn giữ", "Always kept even when the history is long" not in r._context(tm.get(tid), "minh",
                                                                                   "member_reply", None, None))

# Lượt thật qua bộ chạy (engine giả) nhận đúng các mục đó.
asyncio.run(r.run_replies(r.submit(big["team_id"], "Tóm lại giúp", mentions=["minh"], client_msg_id="ask-big")))
check("lượt thật qua run_replies: prompt có phần luôn giữ", rec.reqs and "Always kept even when the history is long" in rec.reqs[-1]["prompt"]
      and "YÊU_CẦU_GỐC_lon" in rec.reqs[-1]["prompt"])

# Lỗi đọc một mục không làm hỏng lượt.
broken = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=rec.engine_for,
                       agent_info=lambda root, key: {"slug": key, "name": NAMES.get(key, key), "system": ""},
                       contrib_reader=lambda ref: (_ for _ in ()).throw(RuntimeError("kho nhịp lỗi")))
pb = broken._context(big, "minh", "member_reply", None, None)
check("kho nhịp lỗi: vẫn dựng được khối, chỉ mất tỷ lệ ghi nhận", "YÊU_CẦU_GỐC_lon" in pb and "Lan synthesized" in pb
      and "credited by the owner" not in pb, pb[-2500:])

# Kế hoạch truy vấn: mọi truy vấn của phần luôn giữ và hai truy vấn lịch sử chạy theo chỉ mục.


def plan(db, sql, args):
    with sqlite3.connect(db) as c:
        return " | ".join(row[-1] for row in c.execute("EXPLAIN QUERY PLAN " + sql, args).fetchall())


qs = [
    (d / "kanban.sqlite3", "SELECT id FROM tasks WHERE lane='team' AND team_id=? AND status IN (?,?,?) LIMIT 9",
     ("t", "team_queued", "team_running", "team_blocked"), "idx_tasks_team_queue"),
    (d / "kanban.sqlite3", "SELECT id FROM tasks WHERE lane='team' AND team_id=? AND status='done' "
     "ORDER BY updated_at DESC LIMIT 1", ("t",), "idx_tasks_team_queue"),
    (d / "team.sqlite3", "SELECT * FROM team_reactions WHERE team_id=? AND status IN (?,?,?) AND reactor='owner' "
     "ORDER BY updated_at DESC LIMIT 12", ("t", "pending_review", "reviewing", "waiting_quota"),
     "team_reactions_status"),
    (d / "chat.db", f"SELECT id FROM messages WHERE session_id = ? AND meta_json LIKE '{sessions.TEAM_DECISION_LIKE}' "
     "ORDER BY id DESC LIMIT 20", ("s",), "idx_messages_team_decision"),
    (d / "chat.db", "SELECT MAX(id) FROM messages WHERE session_id = ? AND author_ref = ?", ("s", "minh"),
     "idx_messages_team_author"),
    (d / "resonance.sqlite3", "SELECT agent_key FROM pulse_contrib WHERE result_ref=? AND status='live' LIMIT 8",
     ("step:x",), "pulse_contrib_result"),
]
for db, sql, args, idx in qs:
    pl = plan(db, sql, args)
    check(f"truy vấn theo chỉ mục {idx}", idx in pl, pl)

check("hàm thuần: yêu cầu gốc tách khỏi phần sửa", TLM.original_request("A\n\n[Sửa yêu cầu, bản 2] B\n\n[Sửa yêu cầu, "
                                                                        "bản 3] C") == ("A", 2))

if fails:
    print(f"\n{len(fails)} FAIL")
    raise SystemExit(1)
print("\nOK")
raise SystemExit(0)
