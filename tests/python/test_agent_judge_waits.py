"""T3 phần J (0.156.0): chờ và gỡ chờ trong nhóm (thiết kế 7.4; GOAL 8.1 "quyết định chờ phải có đường gỡ chờ", 12 ca 27).

    python tests/run.py agent_judge_waits -v

Kho SQLite tạm thật, bộ chạy nhóm thật, engine giả. Điều kiện gỡ: tin mới của chủ trong nhóm, người đang nói chốt lượt
(`_settle_reply_out`), việc liên quan đổi trạng thái, mốc tối đa 30 phút (vòng 5 giây). Gỡ chờ tạo lý do `wait_unblocked`;
mỗi (agent, tin gốc) xét lại tối đa một lần; hết hạn thì im có lý do hay một câu hỏi lại gửi trưởng nhóm/chủ.
"""
import os

os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)

from _judge_world import World, batch, check, finish, keys_in  # noqa: E402

ROLES = {"lan": "Điều phối", "minh": "Quảng cáo", "hoa": "Kho hàng"}


def first_waits(world, kinds, clarify=""):
    """Lô đầu: Minh chờ với điều kiện `kinds`; các lô sau (xét lại, tin sau): Minh nói."""
    state = {"n": 0}

    def decide(p):
        state["n"] += 1
        ks = keys_in(p)
        if state["n"] == 1:
            return batch(**{k: (("wait", 0.7, kinds, clarify) if k == world.k("minh") else ("silent", 0.1)) for k in ks})
        return batch(**{k: (("speak", 0.9) if k == world.k("minh") else ("silent", 0.1)) for k in ks})
    return decide


# ═════ người đang nói chốt lượt gỡ chờ, xét lại một lần, nói ═════
w = World("speaker-done", roles=ROLES)
w.jeng.decide = first_waits(w, ["speaker_done"])
w.send("Mọi người ơi tuần này ưu tiên gì?")
wt = w.js.waits_of(w.k("minh"))
check("Minh chọn chờ: một lần chờ đang mở, tối đa 30 phút", len(wt) == 1 and wt[0]["status"] == "waiting"
      and abs(wt[0]["until_ts"] - w.now[0] - 1800) < 1, wt)
check("chờ không phải nói: chưa có lượt tự lên tiếng", w.eng.roles("member_volunteer") == [])
w.now[0] += 30
w.send("Lan ơi cho ý kiến", mentions=["lan"])
wt = w.js.waits_of(w.k("minh"))
check("Lan (người đang nói) chốt lượt: lần chờ được gỡ rồi xét lại (rejudged)", wt[0]["status"] == "rejudged"
      and wt[0]["release_event"] == "speaker_done", wt)
r = w.wake.reasons(agent_key=w.k("minh"), code="wait_unblocked")
check("gỡ chờ tạo đúng một lý do wait_unblocked, khép sau lô xét lại", len(r) == 1 and r[0]["status"] == "served", r)
again = [d for d in w.decisions("minh") if d["kind"] == "wait"]
check("xét lại: quyết định loại wait, chọn nói thì tự lên tiếng trả lời tin gốc", again and again[0]["volunteer"]
      and [c["agent"] for c in w.eng.roles("member_volunteer")] == [w.k("minh")], again)

# ═════ tin mới của chủ gỡ chờ ═════
w2 = World("owner-msg", roles=ROLES)
w2.jeng.decide = first_waits(w2, ["owner_message"])
w2.send("Mọi người ơi tuần này ưu tiên gì?")
w2.now[0] += 30
w2.send("Bổ sung: ngân sách còn 5 triệu.")
wt2 = w2.js.waits_of(w2.k("minh"))
check("tin mới của chủ gỡ lần chờ owner_message", wt2[0]["status"] == "rejudged" and wt2[0]["release_event"] == "owner_message",
      wt2)

# ═════ việc liên quan đổi trạng thái ═════
w3 = World("job-change", roles=ROLES)
tid, _ = w3.ts.enqueue_team(str(w3.dir), w3.team_id, "Ads tuần này", "Chạy ads tuần này", source_ref="manual:1",
                            assignee_key=w3.k("minh"), coordinator_key=w3.k("lan"), chat_id=f"team:{w3.team_id}")
w3.jeng.decide = first_waits(w3, ["job_change"])
w3.send("Mọi người ơi ads tuần này thế nào?")
wt3 = w3.js.waits_of(w3.k("minh"))
check("lần chờ job_change mang việc mở của agent", wt3 and tid in wt3[0]["job_refs"], wt3)
w3.now[0] += 30
w3.do(w3.runner._judge_job_changed, "tk_khac", w3.team_id)
check("việc KHÁC đổi trạng thái không gỡ chờ", w3.js.waits_of(w3.k("minh"))[0]["status"] == "waiting")
w3.do(w3.runner._block, tid, "failed", "lỗi thử")
wt3 = w3.js.waits_of(w3.k("minh"))
check("việc liên quan bị chặn: gỡ chờ job_change và xét lại", wt3[0]["status"] == "rejudged"
      and wt3[0]["release_event"] == "job_change", wt3)

# ═════ lần chờ đã gỡ mà bị bỏ dở (mất việc nền) được xét lại ở vòng tick ═════
w7 = World("stale-released", roles=ROLES)
w7.jeng.decide = first_waits(w7, ["owner_message"])
w7.send("Mọi người ơi tuần này ưu tiên gì?")
w7.now[0] += 30
got = w7.judge.release_waits(w7.ctx, {"kind": "owner_message"})   # gỡ ngoài event loop: không ai xét lại ngay
check("gỡ chờ mà chưa xét lại: lần chờ nằm released", got and w7.js.waits_of(w7.k("minh"))[0]["status"] == "released")
w7.now[0] += 121
w7.do(w7.runner.judge_tick)
check("quá 120 giây: vòng tick xét lại lần chờ bỏ dở (đúng một lần)",
      w7.js.waits_of(w7.k("minh"))[0]["status"] == "rejudged" and len(w7.eng.roles("member_volunteer")) == 1)

# ═════ xét lại tối đa một lần ═════
w4 = World("rejudge-once", roles=ROLES)
w4.jeng.decide = lambda p: batch(**{k: (("wait", 0.7, ["owner_message"]) if k == w4.k("minh") else ("silent", 0.1))
                                    for k in keys_in(p)})
w4.send("Mọi người ơi tuần này ưu tiên gì?")
w4.now[0] += 30
w4.send("Thêm thông tin nè.")
lim = [d for d in w4.decisions("minh") if d["silence_code"] == "rejudge_limit"]
root1 = [x for x in w4.js.waits_of(w4.k("minh")) if x["root_ref"] == lim[0]["root_ref"]] if lim else []
check("xét lại mà vẫn chọn chờ: im/rejudge_limit, không mở lần chờ thứ hai cho cùng tin gốc", lim and len(root1) == 1,
      [(x["root_ref"], x["status"]) for x in w4.js.waits_of(w4.k("minh"))])

# ═════ hết hạn 30 phút ═════
w5 = World("expire", roles=ROLES)
w5.jeng.decide = first_waits(w5, ["speaker_done"], clarify="Anh muốn ưu tiên ads hay kho?")
w5.send("Mọi người ơi tuần này ưu tiên gì?")
w5.now[0] += 1801
items = w5.do(w5.runner.judge_tick)
check("quá 30 phút: vòng 5 giây đánh hết hạn", len(items) == 1 and items[0]["action"] == "expired", items)
cl = [d for d in w5.decisions("minh") if d["kind"] == "clarify"]
vt = w5.eng.roles("member_volunteer")
check("hết hạn có ask_clarify: đúng MỘT câu hỏi lại qua lượt của chính agent (agent tự viết)",
      len(cl) == 1 and len(vt) == 1 and "Anh muốn ưu tiên ads hay kho?" in vt[0]["prompt"]
      and "EXACTLY ONE short question" in vt[0]["prompt"], (cl, vt))
w5.now[0] += 1801
check("không hỏi lại lần hai", w5.do(w5.runner.judge_tick) == [] and len(w5.eng.roles("member_volunteer")) == 1)

w6 = World("expire-silent", roles=ROLES)
w6.jeng.decide = first_waits(w6, ["speaker_done"])
w6.send("Mọi người ơi tuần này ưu tiên gì?")
w6.now[0] += 1801
w6.do(w6.runner.judge_tick)
ex = [d for d in w6.decisions("minh") if d["silence_code"] == "wait_expired"]
check("hết hạn không câu hỏi lại: im/wait_expired có lý do, không tin nào", ex
      and w6.eng.roles("member_volunteer") == [], ex)

finish()
