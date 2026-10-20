"""Nhóm chat team T4: lịch sử dài (spec mục 12.5, 19; ca TC38 phần chức năng).

    python tests/run.py team_history -v

Tóm tắt phần cũ bằng code (không model), tìm trong nhóm (không phân biệt hoa thường và dấu, không lẫn nhóm khác), mở nhóm
chỉ tải trang đầu. Số đo hiệu năng ở tools/team_perf_bench.py (không phải test). Kho thật trên SQLite tạm, engine giả.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-team-hist-")
TEMP = Path(tempfile.mkdtemp(prefix="javis-team-hist-w-"))

import sessions  # noqa: E402
import task_store  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:400]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class Recorder:
    def __init__(self):
        self.reqs = []

    def engine_for(self, team, key, role):
        async def run_(req):
            self.reqs.append(req)
            return {"text": f"Kết quả {len(self.reqs)}"}
        return "fake", "fake", run_


d = TEMP / "w"
d.mkdir()
ss = sessions.SessionStore(db_path=d / "chat.db")
ts = task_store.TaskStore(d / "kanban.sqlite3")
tm = team_store.TeamStore(d / "team.sqlite3")
rec = Recorder()
r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=rec.engine_for,
                  agent_info=lambda root, key: {"slug": key, "name": key.title(), "system": ""})


def make(name):
    tid = team_store.new_team_id()
    sid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), name, "", sid, team_id=tid)
    tm.add_member(tid, "lan", "lan")
    tm.set_leader(tid, "lan")
    tm.set_caps(tid, {"daily_turns": 1000})
    return tm.get(tid)


A, B = make("A"), make("B")

# ═════ Tóm tắt phần cũ bằng code ═════
asyncio.run(r.run_replies(r.submit(A["team_id"], "Câu đầu", client_msg_id="c0")))
check("cửa sổ còn phủ hết phiên: không có khối tóm tắt", "Summary of the team's older history" not in rec.reqs[-1]["prompt"])
for i in range(3):
    j = r.submit(A["team_id"], f"Việc số {i}", mentions=["lan"], as_job=True, client_msg_id=f"j{i}")["task_id"]
    asyncio.run(r.dispatch_once())
    check(f"việc {i} xong", ts.get_task(j)["status"] == "done")
for i in range(40):
    ss.append_team_message(A["session_id"], "user", f"Tin đệm {i}", author_kind="owner", client_msg_id=f"pad{i}")
jb = r.submit(B["team_id"], "Việc NHÓM_B_BÍ_MẬT", mentions=["lan"], as_job=True, client_msg_id="b")["task_id"]
asyncio.run(r.dispatch_once())
asyncio.run(r.run_replies(r.submit(A["team_id"], "Tóm lại giúp", client_msg_id="c1")))
p = rec.reqs[-1]["prompt"]
check("lịch sử dài: có khối tóm tắt phần cũ do máy dựng, nói số tin cũ", "Summary of the team's older history" in p
      and "summarized by code, not by a model" in p and "messages older than the history" in p, p[-1500:])
check("tóm tắt liệt kê việc đã xong kèm trích kết quả, mới trước",
      p.index('Job "Việc số 2"') < p.index('Job "Việc số 0"') and "Kết quả" in p, p[-1500:])
check("tóm tắt chỉ của nhóm này", "NHÓM_B_BÍ_MẬT" not in p)
check("tóm tắt có trần ký tự", len(p.split("## Summary of the team's older history")[1].split("\n## ")[0]) <= TR.SUMMARY_CHARS + 400)
check("tóm tắt không mở lượt nào thêm (chỉ dựng chuỗi)", len(tm.turns(A["team_id"])) == 5, len(tm.turns(A["team_id"])))

# ═════ Tìm trong nhóm ═════
ss.append_team_message(A["session_id"], "user", "Doanh thu tháng Mười tăng ĐỀU ở Việt Nam", author_kind="owner",
                       client_msg_id="s1")
ss.append_team_message(B["session_id"], "user", "Doanh thu nhóm B cũng tăng", author_kind="owner", client_msg_id="s2")
res = r.search(A["team_id"], "doanh thu viet nam")
check("tìm không phân biệt hoa thường và dấu, khớp mọi từ", len(res) == 1 and "Việt Nam" in res[0]["snippet"], res)
check("tìm chỉ trong đúng nhóm", all("nhóm B" not in x["snippet"] for x in r.search(A["team_id"], "doanh thu")))
check("tìm 'deu' khớp 'ĐỀU' (đ thành d)", len(r.search(A["team_id"], "tang deu")) == 1)
check("đoạn trích quanh chỗ khớp, có id để nhảy tới", res[0]["id"] and res[0]["snippet"].startswith("Doanh thu"))
long_text = "mở đầu " * 40 + "TỪ_KHOÁ_GIỮA " + "kết thúc " * 40
ss.append_team_message(A["session_id"], "user", long_text, author_kind="owner", client_msg_id="s3")
snip = r.search(A["team_id"], "từ_khoá_giữa")[0]["snippet"]
check("tin dài: đoạn trích bao quanh chỗ khớp, có dấu ...", snip.startswith("...") and "TỪ_KHOÁ_GIỮA" in snip
      and snip.endswith("...") and len(snip) <= 210, snip)
for bad in ("", " ", "a"):
    try:
        r.search(A["team_id"], bad)
        ok = False
    except team_store.TeamError:
        ok = True
    check(f"câu tìm quá ngắn bị từ chối: {bad!r}", ok)
for i in range(80):
    ss.append_team_message(A["session_id"], "user", f"lặp lại số {i}", author_kind="owner", client_msg_id=f"rep{i}")
many = r.search(A["team_id"], "lap lai", limit=30)
check("giới hạn số kết quả, mới nhất trước", len(many) == 30 and "79" in many[0]["snippet"])

# ═════ Review T4 ═════
import unicodedata  # noqa: E402

nfd = unicodedata.normalize("NFD", "Đầu tin " + "chữ có dấu " * 60 + "hôm qua cửa hàng MẤT ĐIỆN cả buổi " + "đuôi " * 60)
ss.append_team_message(A["session_id"], "user", nfd, author_kind="owner", client_msg_id="nfd")
sn = r.search(A["team_id"], "mat dien")[0]["snippet"]
check("review #2: tin gõ tổ hợp (NFD): đoạn trích vẫn chứa chỗ khớp", "MẤT ĐIỆN" in unicodedata.normalize("NFC", sn), sn)
found = ss.team_search(A["session_id"], "lap lai so 3", limit=5, batch=7)
check("review #3: tìm đọc theo lô nhỏ vẫn ra đủ, mới trước", [m["content"] for m in found] == [
    "lặp lại số 73", "lặp lại số 63", "lặp lại số 53", "lặp lại số 43", "lặp lại số 39"], [m["content"] for m in found])
asyncio.run(r.run_replies(r.submit(A["team_id"], "Hỏi tiếp", client_msg_id="c9")))
p = rec.reqs[-1]["prompt"]
check("review #4: tóm tắt chỉ đúng hướng (lịch sử ở dưới)", "the history below" in p and "above" not in p.split(
    "## Summary of the team's older history")[1].split("\n## ")[0], p[-2000:])

# ═════ Mở nhóm chỉ tải trang đầu ═════
page = ss.get_team_messages_page(A["session_id"])
check("mở nhóm: trang đầu 30 tin, có còn tin cũ hơn", len(page["messages"]) == 30 and page["has_more"])

print(f"\n{'FAIL' if fails else 'PASS'} - test_team_history: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
