"""T3 phần L (0.156.0): lượt xem xét reaction thật (thiết kế 2026-10-15 mục 3.2-3.4, 4.4, 9; GOAL 6.2, 12 ca 4, 5, 13).

    python tests/run.py agent_review -v

Kho thật (resonance.sqlite3, phiên chat, kho nhóm, kanban tạm), bộ chiếu T2 thật, bộ chạy nhóm thật, host nhịp của P thật,
engine GIẢ và bộ phán xử GIẢ (tiêm, không model):
- mỗi kết cục keep / ask_back / revise / lesson với trạng thái theo kết quả host thật;
- sai khuôn (không JSON, khoá lạ, consumed rỗng hay lệch nguồn, thiếu bài học) thì lượt `error`, lý do về `pending`;
- consumed là tập con: nguồn chưa tiêu thụ sang lý do chờ mới; nguồn đến lúc đang xem xét được xem đúng một lần ở lượt sau;
- phán xử chọn im/chờ: không gửi, "Không cần đổi"; gửi lỗi: "Không cần đổi"; gỡ chờ rồi gửi: "Đã điều chỉnh";
- bài học xuất hiện trong lời nhắc lượt sau của ĐÚNG ngữ cảnh (chat riêng và nhóm) kèm mã nguồn;
- bận: lý do giữ `pending`, không tốn lần thử; hết hạn mức: "Chờ hạn mức", không sổ lượt;
- quyết định ghi vào `agent_pulse_events`; host nhịp của P điều phối lý do sang bộ xử lý đã đăng ký.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import tempfile
from contextlib import closing
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-review-")
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)
TEMP = Path(tempfile.mkdtemp(prefix="javis-review-w-"))

import agent_budget as AB  # noqa: E402
import agent_ledger as ALG  # noqa: E402
import agent_lessons as ALS  # noqa: E402
import agent_pulse as AP  # noqa: E402
import agent_pulse_host as PH  # noqa: E402
import agent_review as AR  # noqa: E402
import feedback_projector as FP  # noqa: E402
import resonance_store as RS  # noqa: E402
import sessions  # noqa: E402
import task_store  # noqa: E402
import team_runner as TR  # noqa: E402
import team_store  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:500]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


class Engine:
    """Engine GIẢ của trợ lý: ghi lời nhắc, ghi trạng thái sổ lượt lúc được gọi, trả chữ đặt sẵn (hay hàm theo req)."""

    def __init__(self, store, text=None):
        self.store = store
        self.text = text
        self.calls = []
        self.during = None
        self.fail = None

    def engine_for(self, key, ctx, purpose):
        async def run_(req):
            await req["engine_started"]()
            with closing(self.store._conn()) as c:
                req["ledger_seen"] = [dict(r) for r in c.execute(
                    "SELECT purpose, status, obligation, counted FROM agent_calls WHERE reason_ref=?",
                    (req["turn_id"],)).fetchall()]
            self.calls.append(req)
            if self.during:
                self.during(req)
            if self.fail:
                raise self.fail
            t = self.text(req) if callable(self.text) else self.text
            return {"text": t, "tokens_in": 5, "tokens_out": 7}
        run_.marks_engine = True
        return "fake", "fake-model", run_


class Judge:
    """Bộ phán xử GIẢ (giao diện `JudgeAdapter`)."""

    def __init__(self, verdict="speak"):
        self.verdict = verdict
        self.calls = []

    async def proactive(self, **kw):
        self.calls.append(kw)
        return {"verdict": self.verdict, "decision_id": 900 + len(self.calls), "reason": "giả"}


_n = [0]


def world(budget="fake", verdict="speak", send_ok=True):
    _n[0] += 1
    d = TEMP / f"{_n[0]:02d}"
    d.mkdir()
    gs = RS.GoalStore(d / "resonance.sqlite3")
    ss = sessions.SessionStore(db_path=d / "chat.db")
    ts = task_store.TaskStore(d / "kanban.sqlite3")
    tm = team_store.TeamStore(d / "team.sqlite3")
    owner = RS.Principal("owner", "owner", str(d))
    ag = gs.agent_set_enabled(owner, "viet", True)
    key = ag["agent_key"]
    box = {"sent": [], "busy": set(), "events": [], "rid": None}
    pj = FP.FeedbackProjector(resonance=lambda: gs, sessions=lambda: ss, teams=lambda: tm,
                              team_view=lambda t, s, m: box["runner"].team_message_view(t, s, m))
    learning = ALS.TeamLearning(lambda: gs)
    eng_team = []

    def team_engine_for(team, k, role):
        async def run_(req):
            eng_team.append(req)
            return {"text": "Trả lời nhóm"}
        return "fake", "fake", run_
    r = TR.TeamRunner(teams=tm, tasks=ts, sessions=ss, engine_for=team_engine_for, publish=lambda e: None,
                      agent_info=lambda root, k: {"slug": "viet", "name": "Viết", "system": ""}, projector=pj,
                      learning=learning)
    box["runner"] = r
    tid = team_store.new_team_id()
    tsid = ss.create_session(brain=str(d), channel=f"team:{tid}")
    tm.create_team(str(d), "Đội", "", tsid, team_id=tid)
    tm.add_member(tid, key, "viet")
    tm.set_leader(tid, key)
    dsid = ss.create_session(brain=str(d), channel="agent:viet")
    eng = Engine(gs)
    judge = Judge(verdict)

    def send(k, ctx, text, meta):
        box["sent"].append((k, ctx, text, meta))
        if not send_ok:
            return None
        if ctx.startswith("team:"):
            mid, _ = ss.append_team_message(tsid, "assistant", text, author_kind="agent", author_ref=k,
                                            reply_to=meta.get("reply_to"))
            return {"session_id": tsid, "message_id": mid}
        return {"session_id": dsid, "message_id": ss.append_message(dsid, "assistant", text)}

    deps = AR.ReviewDeps(store=lambda: gs, reactions=pj, engine_for=eng.engine_for, persona=lambda k: "Bạn là Viết.",
                         try_busy=lambda k, tok: k not in box["busy"], release_busy=lambda k, tok: None, send=send,
                         judge=judge, budget=(lambda k, p, at=None, reason_ref=None: (True, "")) if budget == "fake" else budget,
                         publish=lambda ev: box["events"].append(ev), contexts=lambda k: [f"team:{tid}", f"dm:{k}"])
    host = AR.ReviewHost(deps)
    W = ALG.WakeReasons(gs)
    return {"gs": gs, "ss": ss, "tm": tm, "pj": pj, "r": r, "key": key, "tid": tid, "tsid": tsid, "dsid": dsid,
            "eng": eng, "judge": judge, "host": host, "W": W, "box": box, "team": tm.get(tid), "eng_team": eng_team,
            "learning": learning}


def dm_react(w, text, value="sad", reasons=None, comment="", nonce=None):
    mid = w["ss"].append_message(w["dsid"], "assistant", text)
    got = w["ss"].set_dm_reaction(w["dsid"], mid, value=value, reasons=reasons or [], comment=comment,
                                  nonce=nonce or f"n{mid}", agent_key=w["key"])
    w["pj"].project("dm", got["log_id"])
    return mid, f"rx:dm:{got['log_id']}"


def pending(w, ctx=None):
    rs = w["W"].reasons(agent_key=w["key"], status="pending", code="reaction_review")
    return [x for x in rs if ctx is None or x["context_ref"] == ctx]


def run(coro):
    return asyncio.run(coro)


def out(outcome, consumed, message="", lesson=None, reason="lý do"):
    d = {"outcome": outcome, "message": message, "consumed": consumed, "reason": reason}
    if lesson is not None:
        d["lesson"] = lesson
    return json.dumps(d, ensure_ascii=False)


def dm_status(w, mid):
    return w["ss"].dm_reaction_of(w["dsid"], mid)


# ═════ keep ═════
w = world()
mid, src = dm_react(w, "Báo cáo tuần", value="haha")
rs = pending(w)
w["eng"].text = out("keep", [src], reason="Chủ chỉ vui, không cần đổi")
res = run(w["host"].serve_reaction_review(rs[0]))
check("keep: lượt chạy, lý do served", res.get("outcome") == "served" and w["W"].get(rs[0]["id"])["status"] == "served",
      res)
check("keep: không gửi gì, không qua phán xử", w["box"]["sent"] == [] and w["judge"].calls == [])
st = dm_status(w, mid)
check("keep: trạng thái 'Không cần đổi' kèm lý do ngắn", st["status"] == "no_change" and "không cần đổi" in
      st["status_reason"].lower(), st)
seen = w["eng"].calls[0]["ledger_seen"]
check("sổ lượt giữ chỗ TRƯỚC engine: purpose reaction_review, obligation 0, counted 1, đã qua mốc engine",
      seen == [{"purpose": "reaction_review", "status": "running", "obligation": 0, "counted": 1}], seen)
row = ALG.CallLedger(w["gs"]).rows(reason_ref=f"wr:{rs[0]['id']}")
check("sổ lượt chốt ok kèm token", len(row) == 1 and row[0]["status"] == "ok" and row[0]["tokens_out"] == 7, row)
prompt = w["eng"].calls[0]["prompt"]
check("lời nhắc có tin bị phản hồi, mã nguồn, cảm xúc; system có luật xem xét",
      "Báo cáo tuần" in prompt and src in prompt and "haha" in prompt
      and "OWNER FEEDBACK REVIEW TURN" in w["eng"].calls[0]["system"], prompt)
evs = AP.events(w["gs"], w["key"], kinds=("reaction_review",))
check("quyết định ghi vào agent_pulse_events kèm mã nguồn", evs and evs[0]["reason"] == "keep"
      and evs[0]["payload"]["consumed"] == [src] and evs[0]["payload"]["reason_id"] == rs[0]["id"], evs)
check("đẩy gói WS chat_reaction cho trạng thái", any(e.get("type") == "chat_reaction" for e in w["box"]["events"]))

# ═════ lesson (chat riêng): bài học vào phạm vi dm và có trong lời nhắc lượt sau ═════
mid2, src2 = dm_react(w, "Bản tin dài", value="sad", reasons=["too_long"])
rs = pending(w)
w["eng"].text = out("lesson", [src2], lesson={"text": "Bản tin cho chủ giữ dưới năm dòng.", "kind": "presentation"})
res = run(w["host"].serve_reaction_review(rs[0]))
les = ALS.lessons(w["gs"], w["key"], scope=f"dm:{w['key']}")
check("lesson: bài học phạm vi dm:<agent_key>, nguồn review, dẫn mã reaction", len(les) == 1 and les[0]["source"] ==
      "review" and src2 in les[0]["source_refs"] and les[0]["kind"] == "presentation", les)
check("lesson: 'Đã điều chỉnh'", dm_status(w, mid2)["status"] == "adjusted")
check("lesson: không gửi tin", w["box"]["sent"] == [])
blk = ALS.prompt_block(w["gs"], w["key"], f"dm:{w['key']}")
check("lượt chat riêng kế tiếp nạp bài học kèm mã nguồn", "Bản tin cho chủ giữ dưới năm dòng." in blk and src2 in blk,
      blk)
check("lượt nhóm KHÔNG nạp bài học chat riêng", not any("năm dòng" in x for x in
                                                        w["learning"].lesson_lines(w["tid"], w["key"])))

# ═════ ask_back: phán xử nói, tin MỚI được gửi ═════
mid3, src3 = dm_react(w, "Kế hoạch quý", value="wow", comment="ý em là quý mấy?")
rs = pending(w)
w["eng"].text = out("ask_back", [src3], message="Anh muốn kế hoạch cho quý 3 hay quý 4 ạ?")
n_before = len(w["ss"].get_messages(w["dsid"]))
res = run(w["host"].serve_reaction_review(rs[0]))
check("ask_back: qua bộ phán xử của agent với đúng ngữ cảnh và nguồn",
      len(w["judge"].calls) == 1 and w["judge"].calls[0]["context_ref"] == f"dm:{w['key']}"
      and w["judge"].calls[0]["source_event"] == f"wr:{rs[0]['id']}"
      and w["judge"].calls[0]["origin"] == "reaction_review", w["judge"].calls)
check("ask_back: gửi MỘT tin mới (không sửa đè tin cũ), trả lời tin bị phản hồi",
      len(w["box"]["sent"]) == 1 and w["box"]["sent"][0][3]["reply_to"] == mid3
      and len(w["ss"].get_messages(w["dsid"])) == n_before + 1
      and w["ss"].message_row(w["dsid"], mid3)["content"] == "Kế hoạch quý")
check("ask_back gửi thật: 'Đã điều chỉnh'", dm_status(w, mid3)["status"] == "adjusted"
      and res.get("message_id") is not None and res.get("decision_id") == 901, res)

# ═════ revise: phán xử chọn im ═════
w2 = world(verdict="silent")
mid, src = dm_react(w2, "Số liệu tháng", value="angry", reasons=["wrong_facts"])
w2["eng"].text = out("revise", [src], message="Bản sửa: doanh thu tháng là 120 triệu.")
res = run(w2["host"].serve_reaction_review(pending(w2)[0]))
st = dm_status(w2, mid)
check("revise + phán xử im: không gửi, 'Không cần đổi' kèm 'phán xử chọn im'",
      w2["box"]["sent"] == [] and st["status"] == "no_change" and "im" in st["status_reason"], st)
# phán xử chờ, rồi được gỡ và cho nói
w3 = world(verdict="wait")
mid, src = dm_react(w3, "Lịch họp", value="sad", comment="sai giờ")
w3["eng"].text = out("revise", [src], message="Bản sửa: họp lúc 9 giờ.")
run(w3["host"].serve_reaction_review(pending(w3)[0]))
st = dm_status(w3, mid)
check("phán xử chờ: chưa gửi, 'Không cần đổi' kèm lý do chờ", w3["box"]["sent"] == [] and st["status"] == "no_change"
      and "chờ" in st["status_reason"], st)
pay = w3["judge"].calls[0]["payload"]
run(w3["host"].on_judge_send({"decision_id": 5}, {"origin": "other"}, "send"))
check("bộ gửi bỏ qua tin không do lượt xem xét tạo", w3["box"]["sent"] == [])
run(w3["host"].on_judge_send({"decision_id": 5}, pay, "send"))
check("gỡ chờ rồi được nói: gửi tin mới, trạng thái 'Đã điều chỉnh'", len(w3["box"]["sent"]) == 1
      and w3["box"]["sent"][0][2] == "Bản sửa: họp lúc 9 giờ." and dm_status(w3, mid)["status"] == "adjusted")
# gửi lỗi
w4 = world(send_ok=False)
mid, src = dm_react(w4, "Tóm tắt", value="sad", reasons=["missing"])
w4["eng"].text = out("revise", [src], message="Bổ sung: ...")
run(w4["host"].serve_reaction_review(pending(w4)[0]))
st = dm_status(w4, mid)
check("phán xử nói nhưng gửi không được: 'Không cần đổi' (không báo đã điều chỉnh)", st["status"] == "no_change"
      and "gửi" in st["status_reason"], st)

# ═════ sai khuôn: lượt error, lý do về pending ═════
w5 = world()
mid, src = dm_react(w5, "Bài viết", value="sad")
bad = ["không có json nào", out("keep", []), out("keep", ["rx:dm:99999"]),
       json.dumps({"outcome": "keep", "message": "", "consumed": [src], "reason": "", "extra": 1}),
       out("lesson", [src]), out("ask_back", [src], message=""), out("maybe", [src]),
       out("lesson", [src], lesson={"text": "x", "kind": "speak"})]
codes = []
for i, text in enumerate(bad):
    rid = pending(w5)[0]["id"]
    with w5["gs"]._Tx(w5["gs"]) as c:   # thử từng khuôn sai trên cùng lý do (đặt lại số lần thử để không chạm `failed`)
        c.execute("UPDATE agent_wake_reasons SET attempt=0 WHERE id=?", (rid,))
    w5["eng"].text = text
    res = run(w5["host"].serve_reaction_review({"id": rid}))
    codes.append(res.get("error"))
check("mọi khuôn sai bị bắt đúng mã", codes == ["no_json", "bad_consumed", "consumed_not_subset", "unknown_keys",
                                                "bad_lesson", "empty_message", "bad_outcome", "bad_lesson"], codes)
r0 = pending(w5)
check("sai khuôn: lý do về pending (cùng lý do), nguồn chưa tiêu thụ", len(r0) == 1
      and w5["W"].sources(r0[0]["id"], live_only=True)[0]["source_ref"] == src)
rows = ALG.CallLedger(w5["gs"]).rows()
check("sai khuôn: lượt sổ chốt `error` (đã tới model nên vẫn tính)", rows and all(x["status"] == "error" for x in rows))
check("sai khuôn: không gửi, không bài học, trạng thái về 'Chờ xem xét'", w5["box"]["sent"] == []
      and ALS.lessons(w5["gs"], w5["key"]) == [] and dm_status(w5, mid)["status"] == "pending_review")
for _ in range(3):
    rid = (pending(w5) or [{"id": None}])[0]["id"]
    if rid is None:
        break
    w5["eng"].text = "sai"
    run(w5["host"].serve_reaction_review({"id": rid}))
check("sai khuôn quá 3 lần: lý do `failed` (chủ bấm thử lại)",
      any(x["status"] == "failed" for x in w5["W"].reasons(agent_key=w5["key"])))

# ═════ consumed là tập con; nguồn đến lúc đang xem xét ═════
w6 = world()
ma, sa = dm_react(w6, "Tin A", value="sad")
mb, sb = dm_react(w6, "Tin B", value="angry", reasons=["off_topic"])
first = pending(w6)[0]
arrived = {}


def during(req):
    if not arrived:
        arrived["x"] = dm_react(w6, "Tin C", value="sad", comment="tới giữa lượt")


w6["eng"].during = during
w6["eng"].text = out("keep", [sa])
res = run(w6["host"].serve_reaction_review(first))
w6["eng"].during = None
nxt = pending(w6)
check("consumed ⊆ nguồn: nguồn chưa tiêu thụ (B) và nguồn đến giữa lượt (C) sang MỘT lý do chờ mới",
      len(nxt) == 1 and nxt[0]["id"] != first["id"] and sorted(s["source_ref"] for s in w6["W"].sources(
          nxt[0]["id"], live_only=True)) == sorted([sb, arrived["x"][1]]), [nxt, w6["W"].sources(nxt[0]["id"])])
check("nguồn đã tiêu thụ 'Không cần đổi', nguồn chưa tiêu thụ 'Chờ xem xét'",
      dm_status(w6, ma)["status"] == "no_change" and dm_status(w6, mb)["status"] == "pending_review")
check("lượt đầu không thấy nguồn đến giữa lượt", arrived["x"][1] not in w6["eng"].calls[0]["prompt"])
w6["eng"].text = lambda req: out("keep", sorted(x for x in (sb, arrived["x"][1]) if x in req["prompt"]))
run(w6["host"].serve_reaction_review(nxt[0]))
check("lượt sau xem nguồn đến giữa lượt ĐÚNG một lần rồi hết lý do chờ",
      arrived["x"][1] in w6["eng"].calls[1]["prompt"] and pending(w6) == []
      and sum(arrived["x"][1] in c["prompt"] for c in w6["eng"].calls) == 1)

# ═════ bận, hạn mức, engine lỗi trước mốc ═════
w7 = world()
mid, src = dm_react(w7, "Tin", value="sad")
rid = pending(w7)[0]["id"]
w7["box"]["busy"].add(w7["key"])
res = run(w7["host"].serve_reaction_review({"id": rid}))
w7["box"]["busy"].clear()
check("bận: không nhận, lý do pending, attempt không tăng, không sổ lượt", res["outcome"] == "busy"
      and w7["W"].get(rid)["status"] == "pending" and w7["W"].get(rid)["attempt"] == 0
      and ALG.CallLedger(w7["gs"]).rows() == [])
w8 = world(budget=lambda k, p, at=None, reason_ref=None: (False, "agent_daily_calls"))
mid, src = dm_react(w8, "Tin", value="sad")
rid = pending(w8)[0]["id"]
res = run(w8["host"].serve_reaction_review({"id": rid}))
st = dm_status(w8, mid)
check("hết hạn mức: lý do pending, 'Chờ hạn mức', không sổ lượt, không engine", res["outcome"] == "quota"
      and w8["W"].get(rid)["status"] == "pending" and st["status"] == "waiting_quota"
      and ALG.CallLedger(w8["gs"]).rows() == [] and w8["eng"].calls == [], st)
check("hết hạn mức: ghi sự kiện quota", AP.events(w8["gs"], w8["key"], kinds=("quota",)))
# hạn mức thật của agent_budget: trần 0
w9 = world(budget=None)
AB.set_cap(w9["gs"], w9["key"], 0)
mid, src = dm_react(w9, "Tin", value="sad")
res = run(w9["host"].serve_reaction_review(pending(w9)[0]))
check("hạn mức thật (trần 0): 'Chờ hạn mức'", res["outcome"] == "quota" and dm_status(w9, mid)["status"] ==
      "waiting_quota", res)
AB.set_cap(w9["gs"], w9["key"], None)
w9["eng"].text = out("keep", [src])
res = run(w9["host"].serve_reaction_review(pending(w9)[0]))
check("chủ chọn Không giới hạn: lượt chạy", res.get("outcome") == "served", res)
w10 = world()
mid, src = dm_react(w10, "Tin", value="sad")
rid = pending(w10)[0]["id"]


def bad_engine(key, ctx, purpose):
    raise RuntimeError("engine chưa sẵn sàng")


w10["host"].deps.engine_for = bad_engine
res = run(w10["host"].serve_reaction_review({"id": rid}))
check("engine không dựng được (trước mốc): hoàn lượt, lý do pending, attempt không tăng",
      res["outcome"] == "engine_error" and w10["W"].get(rid)["status"] == "pending"
      and w10["W"].get(rid)["attempt"] == 0 and ALG.CallLedger(w10["gs"]).rows()[0]["status"] == "refunded",
      [res, w10["W"].get(rid)])

# ═════ nhóm: bài học phạm vi nhóm vào lượt nhóm kế tiếp; ask_back qua phán xử trong nhóm ═════
w11 = world()
tmid = w11["ss"].append_team_message(w11["tsid"], "assistant", "Kế hoạch nhóm", author_kind="agent",
                                     author_ref=w11["key"])[0]
w11["r"].react(w11["tid"], tmid, "sad", reasons=["unclear"], nonce="t1")
tr = pending(w11, f"team:{w11['tid']}")
check("reaction nhóm tạo lý do reaction_review ngữ cảnh team:<id>", len(tr) == 1)
tsrc = w11["W"].sources(tr[0]["id"])[0]["source_ref"]
w11["eng"].text = out("lesson", [tsrc], lesson={"text": "Trong nhóm này, nêu rõ ai làm gì.", "kind": "method"})
run(w11["host"].serve_reaction_review(tr[0]))
check("nhóm: bài học phạm vi team:<id>", [x["scope"] for x in ALS.lessons(w11["gs"], w11["key"])] ==
      [f"team:{w11['tid']}"])
check("nhóm: trạng thái reaction nhóm 'Đã điều chỉnh'",
      w11["tm"].reaction_of(w11["tsid"], tmid)["status"] == "adjusted")
check("nhóm: gói WS team_message", any(e.get("type") == "team_message" for e in w11["box"]["events"]))
run(w11["r"].run_replies(w11["r"].submit(w11["tid"], "Mọi người tiếp nhé", mentions=[w11["key"]], client_msg_id="c1")))
check("lượt nhóm kế tiếp nạp bài học kèm mã nguồn",
      w11["eng_team"] and "Trong nhóm này, nêu rõ ai làm gì." in w11["eng_team"][-1]["prompt"]
      and tsrc in w11["eng_team"][-1]["prompt"], w11["eng_team"][-1]["prompt"][-1500:] if w11["eng_team"] else "")
check("chat riêng KHÔNG nạp bài học nhóm", "ai làm gì" not in ALS.prompt_block(w11["gs"], w11["key"],
                                                                               f"dm:{w11['key']}"))
tmid2 = w11["ss"].append_team_message(w11["tsid"], "assistant", "Bản nháp", author_kind="agent",
                                      author_ref=w11["key"])[0]
w11["r"].react(w11["tid"], tmid2, "wow", comment="là bản nào?", nonce="t2")
tr = pending(w11, f"team:{w11['tid']}")
tsrc2 = w11["W"].sources(tr[0]["id"])[0]["source_ref"]
w11["eng"].text = out("ask_back", [tsrc2], message="Anh hỏi bản nháp số mấy ạ?")
run(w11["host"].serve_reaction_review(tr[0]))
check("nhóm: ask_back qua phán xử ngữ cảnh nhóm rồi gửi tin mới trả lời tin bị phản hồi",
      w11["judge"].calls[-1]["context_ref"] == f"team:{w11['tid']}" and w11["box"]["sent"][-1][1] ==
      f"team:{w11['tid']}" and w11["box"]["sent"][-1][3]["reply_to"] == tmid2
      and w11["tm"].reaction_of(w11["tsid"], tmid2)["status"] == "adjusted")

# ═════ Cộng hưởng tắt: reaction chỉ lưu, không có lượt xem xét ═════
w12 = world()
RS_owner = RS.Principal("owner", "owner", str(TEMP))
w12["gs"].agent_set_enabled(RS.Principal("owner", "owner", str(TEMP / f"{_n[0]:02d}")), "viet", False)
mid, src = dm_react(w12, "Tin", value="sad")
check("Cộng hưởng tắt: không lý do reaction_review nào", pending(w12) == []
      and dm_status(w12, mid)["status"] == "stored_only")

# ═════ tiến trình chết giữa lượt: lý do `claimed` không kẹt mãi ═════
w14 = world()
mid, src = dm_react(w14, "Tin bị kẹt", value="sad")
rid = pending(w14)[0]["id"]
cl = w14["W"].claim(rid, purpose="reaction_review", obligation=False)
w14["W"].ledger.mark_engine(cl["call_id"])
check("giả tiến trình chết: lý do claimed, dòng sổ running", w14["W"].get(rid)["status"] == "claimed")
check("chưa quá một lượt: không gỡ", w14["host"].recover_stale_claims() == [])
import time as _time  # noqa: E402
got = w14["host"].recover_stale_claims(now=_time.time() + AR.REVIEW_TIMEOUT_S + 120)
row = ALG.CallLedger(w14["gs"]).get(cl["call_id"])
check("quá một lượt: lý do về pending (attempt giữ), dòng sổ interrupted (vẫn tính), reaction 'Chờ xem xét'",
      got == [rid] and w14["W"].get(rid)["status"] == "pending" and w14["W"].get(rid)["attempt"] == 1
      and row["status"] == "interrupted" and dm_status(w14, mid)["status"] == "pending_review",
      [got, w14["W"].get(rid), row])
w14["eng"].text = out("keep", [src])
check("sau khi gỡ: lượt sau phục vụ bình thường", run(w14["host"].serve_reaction_review({"id": rid}))["outcome"] ==
      "served")

# ═════ host nhịp của P điều phối sang bộ xử lý đã đăng ký ═════
w13 = world()
mid, src = dm_react(w13, "Tin qua nhịp", value="sad")
w13["eng"].text = out("keep", [src])
AR.wire(w13["host"])
check("đăng ký vào sổ của P: bộ xử lý reaction_review, mục lessons, hàm quay lại",
      AR.register_with_pulse() and "reaction_review" in PH._REASON_HANDLERS and "lessons" in PH.view_parts())
pdeps = PH.PulseHostDeps(store=lambda: w13["gs"], agents=lambda: [{"agent_key": w13["key"], "brain_id": ""}],
                         contexts=lambda k: [f"dm:{k}"], spawn=asyncio.ensure_future)
phost = PH.PulseHost(pdeps, budget=lambda k, p, at=None: (True, ""))


async def tick_all():
    await phost.tick()
    await phost.wait_idle()

run(tick_all())
check("nhịp P spawn lượt xem xét cho lý do pending: served, 'Không cần đổi'",
      pending(w13) == [] and dm_status(w13, mid)["status"] == "no_change" and len(w13["eng"].calls) == 1)
v = PH.view(w13["gs"], w13["key"])
check("khung nhịp có mục lessons (sổ đăng ký của P)", v["parts"].get("lessons", {}).get("name") == "lessons",
      v["parts"])

print(f"\n{'ĐỎ' if fails else 'XANH'}: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
