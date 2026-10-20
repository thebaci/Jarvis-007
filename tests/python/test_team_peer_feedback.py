"""T3 phần L (0.156.0): góp ý của đồng đội trong nhóm (thiết kế 2026-10-15 mục 8.2; GOAL 8.2, 12 ca 3, 27).

    python tests/run.py team_peer_feedback -v

Bộ chạy nhóm thật, kho thật tạm, engine GIẢ theo từng trợ lý (không model):
- lệnh `{"op": "peer_feedback", "message_id", "note"}`: host gán nguồn (trưởng nhóm hay đồng đội) theo lượt, gắn tin, việc, bản;
- vào lượt KẾ TIẾP của người nhận trong ĐÚNG nhóm dưới mục "Góp ý của đồng đội (không phải yêu cầu của chủ, không phải sự
  thật đã kiểm)", một lần; không hiện ở nhóm khác;
- góp ý lên tin của chính mình, tin của chủ, tin không thuộc nhóm: bỏ kèm ghi chú;
- đầu ra đến muộn (người góp ý bị bỏ khỏi nhóm giữa lượt) và góp ý trỏ việc đã huỷ hay bản đã đổi: chỉ là bằng chứng;
- không thành luật của chủ, không thành bài học, không thành tín hiệu hữu ích; nhiều trợ lý đồng ý không là bằng chứng độc lập.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
from contextlib import closing
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-peer-")
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)
TEMP = Path(tempfile.mkdtemp(prefix="javis-peer-w-"))

import agent_lessons as ALS  # noqa: E402
import resonance_store as RS  # noqa: E402
import sessions  # noqa: E402
import task_store  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:600]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


d = TEMP / "w"
d.mkdir()
gs = RS.GoalStore(d / "resonance.sqlite3")
ss = sessions.SessionStore(db_path=d / "chat.db")
ts = task_store.TaskStore(d / "kanban.sqlite3")
tm = team_store.TeamStore(d / "team.sqlite3")
owner = RS.Principal("owner", "owner", str(d))
A = gs.agent_register(owner, "truong")["agent_key"]
B = gs.agent_register(owner, "thanh-vien")["agent_key"]
C = gs.agent_register(owner, "ban")["agent_key"]
NAMES = {A: "Trưởng", B: "Thành viên", C: "Bạn C"}
tasks_state = {}
learning = ALS.TeamLearning(lambda: gs, task_state=lambda tid: tasks_state.get(tid))
box = {"texts": {}, "prompts": {A: [], B: [], C: []}, "during": None}


def engine_for(team, key, role):
    async def run_(req):
        box["prompts"][key].append(req["prompt"])
        if box["during"]:
            box["during"](key)
        t = box["texts"].get(key, "Đã rõ.")
        return {"text": t(req) if callable(t) else t}
    return "fake", "fake", run_


r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=engine_for, publish=lambda e: None,
                  agent_info=lambda root, k: {"slug": k, "name": NAMES[k], "system": ""}, learning=learning)


def make_team(name, members, leader):
    tid = team_store.new_team_id()
    sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), name, "", sid, team_id=tid)
    for k in members:
        tm.add_member(tid, k, k)
    tm.set_leader(tid, leader)
    return tm.get(tid)


T1 = make_team("Nhóm 1", [A, B, C], A)
T2 = make_team("Nhóm 2", [A, B], A)
_c = [0]


def say(T, key, text="Làm tiếp nhé"):
    _c[0] += 1
    asyncio.run(r.run_replies(r.submit(T["team_id"], text, mentions=[key], client_msg_id=f"c{_c[0]}")))
    return ss.last_message_id_by(T["session_id"], key)


def pf(mid, note):
    return f'Nhận xét xong.\n<!-- JAVIS_TEAM: {{"op": "peer_feedback", "message_id": {mid}, "note": "{note}"}} -->'


mB = say(T1, B)
check("tin của B có trong nhóm", mB and ss.team_message(T1["session_id"], mB)["author_ref"] == B)
box["texts"][A] = pf(mB, "Thiếu nguồn số liệu ở đoạn hai")
mA = say(T1, A)
rows = ALS.peer_feedback(gs, T1["team_id"], B)
check("trưởng nhóm góp ý: host gán nguồn leader, gắn tin, lượt", len(rows) == 1 and rows[0]["author_role"] == "leader"
      and rows[0]["author_key"] == A and rows[0]["message_id"] == mB and rows[0]["turn_ref"].startswith("turn:")
      and rows[0]["status"] == "active", rows)
check("lệnh bóc khỏi tin đăng (không hiện khối điều khiển)", "JAVIS_TEAM" not in ss.team_message(T1["session_id"],
                                                                                              mA)["content"])
box["texts"][A] = "Đã rõ."
say(T1, B)
p = box["prompts"][B][-1]
check("lượt kế tiếp của B trong nhóm 1 có mục góp ý đúng tiêu đề, người gửi, vai, mã tin",
      ALS.PEER_HEADER in p and "Thiếu nguồn số liệu ở đoạn hai" in p and "Trưởng" in p and "team lead" in p
      and f"#{mB}" in p, p[-1200:])
check("khối nói rõ không phải yêu cầu của chủ, nhiều trợ lý đồng ý không là bằng chứng độc lập",
      "request from the team owner" in p and "not independent evidence" in p)
say(T1, B)
check("đã giao thì lượt sau không hiện lại", "Thiếu nguồn số liệu" not in box["prompts"][B][-1])
say(T2, B)
check("góp ý ở nhóm 1 không hiện ở nhóm 2", "Thiếu nguồn số liệu" not in box["prompts"][B][-1])

# Thành viên góp ý: nguồn teammate; lệnh sai bị bỏ kèm ghi chú.
mB2 = ss.last_message_id_by(T1["session_id"], B)
owner_mid = ss.team_messages_after(T1["session_id"], 0, 200)[0]["id"]
box["texts"][C] = pf(mB2, "Nên thêm bảng")
mC0 = say(T1, C)
rowsC = [x for x in ALS.peer_feedback(gs, T1["team_id"]) if x["author_key"] == C]
check("đồng đội góp ý: nguồn teammate", len(rowsC) == 1 and rowsC[0]["author_role"] == "teammate"
      and rowsC[0]["receiver_key"] == B)
box["texts"][C] = pf(mC0, "tự khen") + "\n" + pf(owner_mid, "góp ý chủ") + "\n" + pf(999999, "không có tin")
mC = say(T1, C)
check("không ghi góp ý sai nào", len([x for x in ALS.peer_feedback(gs, T1["team_id"]) if x["author_key"] == C]) == 1)
notes = (ss.team_message(T1["session_id"], mC).get("meta") or {}).get("notes") or []
check("góp ý lên tin của chính mình / tin của chủ / tin không có: bỏ kèm ghi chú",
      sum("peer_feedback" in n for n in notes) == 3, notes)
box["texts"][C] = "Đã rõ."

# Trần mỗi lượt.
box["texts"][A] = "\n".join(pf(mB2, f"Góp ý {i}") for i in range(5))
mA2 = say(T1, A)
check(f"tối đa {TR.PEERS_PER_TURN} góp ý mỗi lượt", len([x for x in ALS.peer_feedback(gs, T1["team_id"])
                                                         if x["note"].startswith("Góp ý ")]) == TR.PEERS_PER_TURN)
box["texts"][A] = "Đã rõ."
say(T1, B)   # giao hết góp ý đang chờ

# Đầu ra đến muộn: người góp ý bị bỏ khỏi nhóm giữa lượt -> chỉ bằng chứng.
box["texts"][C] = pf(mB2, "Góp ý đến muộn")


def remove_c(key):
    if key == C:
        tm.remove_member(T1["team_id"], C)


box["during"] = remove_c
say(T1, C)
box["during"] = None
late = [x for x in ALS.peer_feedback(gs, T1["team_id"]) if x["note"] == "Góp ý đến muộn"]
check("đầu ra đến muộn (bỏ thành viên giữa lượt): góp ý chỉ là bằng chứng", len(late) == 1
      and late[0]["status"] == "evidence" and late[0]["evidence_reason"] == "member_left", late)
say(T1, B)
check("bằng chứng không vào lượt của người nhận", "Góp ý đến muộn" not in box["prompts"][B][-1])

# Góp ý trỏ việc đã huỷ hay bản đã đổi: hạ thành bằng chứng lúc dựng lượt.
mJ1 = ss.append_team_message(T1["session_id"], "assistant", "Kết quả bước", author_kind="agent", author_ref=B,
                             task_id="t_x", meta={"revision": 1})[0]
mJ2 = ss.append_team_message(T1["session_id"], "assistant", "Kết quả bước 2", author_kind="agent", author_ref=B,
                             task_id="t_y", meta={"revision": 1})[0]
mJ3 = ss.append_team_message(T1["session_id"], "assistant", "Kết quả bước 3", author_kind="agent", author_ref=B,
                             task_id="t_z", meta={"revision": 2})[0]
tasks_state.update({"t_x": ("team_running", 1), "t_y": ("cancelled", 1), "t_z": ("team_running", 3)})
box["texts"][A] = "\n".join([pf(mJ1, "Bước ổn, thêm nguồn"), pf(mJ2, "Việc đã huỷ"), pf(mJ3, "Bản cũ")])
say(T1, A)
box["texts"][A] = "Đã rõ."
fx = {x["note"]: x for x in ALS.peer_feedback(gs, T1["team_id"])}
check("góp ý gắn việc và bản của tin", fx["Bước ổn, thêm nguồn"]["task_id"] == "t_x"
      and fx["Bước ổn, thêm nguồn"]["revision"] == 1 and fx["Bản cũ"]["revision"] == 2)
say(T1, B)
p = box["prompts"][B][-1]
fx = {x["note"]: x for x in ALS.peer_feedback(gs, T1["team_id"])}
check("việc còn chạy đúng bản: góp ý hiện kèm bản", "Bước ổn, thêm nguồn" in p and "revision 1" in p)
check("việc đã huỷ / bản đã đổi: không hiện, hạ thành bằng chứng",
      "Việc đã huỷ" not in p and "Bản cũ" not in p and fx["Việc đã huỷ"]["status"] == "evidence"
      and fx["Việc đã huỷ"]["evidence_reason"] == "late_cancelled" and fx["Bản cũ"]["evidence_reason"] ==
      "old_revision", fx)

# Không thành luật của chủ, bài học hay tín hiệu hữu ích.
check("góp ý không tạo bài học nào", ALS.lessons(gs, B, status=None) == [])
with closing(gs._conn()) as c:
    has_sig = c.execute("SELECT name FROM sqlite_master WHERE name='pulse_signals'").fetchone()
    n_sig = c.execute("SELECT COUNT(*) FROM pulse_signals").fetchone()[0] if has_sig else 0
check("góp ý không tạo tín hiệu hữu ích (không vào ước lượng, không tự thưởng)", n_sig == 0)
check("lời nhắc có hướng dẫn lệnh góp ý", TR.PEER_HINT.split(":")[0] in box["prompts"][B][-1])

print(f"\n{'ĐỎ' if fails else 'XANH'}: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
