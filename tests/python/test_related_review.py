"""T3 phần J (0.156.0): lượt xem xét liên quan từ đồng đội (thiết kế 7.5; GOAL 8.1, 12 ca 10, 27).

    python tests/run.py related_review -v

Cập nhật điều khoản T1 "tin của agent không đánh thức ai" thành hợp đồng có kiểm soát: chỉ quan hệ CÓ CẤU TRÚC (người
nhận/điều phối việc, bước có `input_refs` trỏ tới tin, người nhờ hỗ trợ, lệnh `ask_peer` host kiểm danh tính) mở lượt xem xét
liên quan, và người nhận đi qua bộ phán xử của chính họ. Chặn: tự gọi mình, trích dẫn (bỏ trước khi phán xử), chữ @ trong văn
bản, độ sâu > 2 từ tin gốc của chủ, quá một lượt mỗi (agent, tin gốc), A->B->A, trần của nhóm.
"""
import json
import os

os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)

from _judge_world import World, batch, check, finish, keys_in  # noqa: E402


def op(**kw):
    return f"\n<!-- JAVIS_TEAM: {json.dumps(kw, ensure_ascii=False)} -->"


ROLES = {"lan": "Điều phối", "minh": "Quảng cáo", "hoa": "Kho hàng"}

# ═════ ask_peer: người được nhờ đi qua phán xử của chính họ ═════
w = World("ask-peer", roles=ROLES)
w.eng.script[(w.k("lan"), "leader_reply")] = [
    "> Chủ nhóm: trích dẫn cũ không được tính\nMình đề xuất tăng ads 10%." + op(op="ask_peer", agent_key=w.k("minh"))]


def rel_only(p):
    """Chỉ lô xem xét liên quan chọn nói; lô của tin chủ thì mọi người im (để đếm đúng lượt tự lên tiếng)."""
    v = ("speak", 0.9) if "(a teammate) just posted a message" in p else ("silent", 0.1)
    return batch(**{k: v for k in keys_in(p)})


w.jeng.decide = rel_only
w.send("Tuần này làm gì?")
rel = w.decisions("minh", "related")
check("ask_peer: người được nhờ có một quyết định loại related", len(rel) == 1, rel)
reasons = w.wake.reasons(agent_key=w.k("minh"), code="related_review")
check("ask_peer: tạo lý do related_review (served bởi chính lô phán xử)", len(reasons) == 1
      and reasons[0]["status"] == "served", reasons)
rel_prompt = [p for p in w.jeng.prompts if "(a teammate)" in p and "structured relation" in p]
check("lô xem xét liên quan: prompt có đúng người được nhờ, kèm quan hệ", rel_prompt
      and keys_in(rel_prompt[0]) == [w.k("minh")] and "asked by a teammate to take a look" in rel_prompt[0], w.jeng.prompts)
check("trích dẫn bị bỏ trước khi phán xử", rel_prompt and "trích dẫn cũ" not in rel_prompt[0].split("## Message to consider")[1])
vt = w.eng.roles("member_volunteer")
check("người được nhờ chọn nói: chạy lượt member_volunteer trả lời tin của đồng đội",
      [c["agent"] for c in vt] == [w.k("minh")] and "Lan" in vt[0]["prompt"], vt)
lan_mid = int(rel[0]["source_event"].split(":")[1])
minh_msg = [m for m in w.messages() if m["author_ref"] == w.k("minh")]
ch = w.js.chain(w.ctx, minh_msg[0]["id"]) if minh_msg else None
check("chuỗi tin: tin của người được nhờ có độ sâu 2, đánh thức bởi Lan", ch and ch["depth"] == 2
      and ch["via_key"] == w.k("lan") and ch["root_ref"].startswith("msg:"), ch)

# ═════ chặn: A->B->A, độ sâu, chữ @, tự nhờ mình, người ngoài ═════
w2 = World("blocks", roles=ROLES)
w2.eng.script[(w2.k("lan"), "leader_reply")] = ["Ý kiến của Lan. @Hoa xem giúp nhé." + op(op="ask_peer", agent_key=w2.k("minh"))]
w2.eng.script[(w2.k("minh"), "member_volunteer")] = [
    "Minh trả lời." + op(op="ask_peer", agent_key=w2.k("lan")) + op(op="ask_peer", agent_key=w2.k("hoa"))]
w2.jeng.decide = rel_only
w2.send("Tuần này làm gì?")
hoa_rel = w2.decisions("hoa", "related")
lan_mid2 = min(int(x["id"]) for x in w2.messages() if x["author_ref"] == w2.k("lan"))
check("chữ @Hoa trong văn bản không mở lượt nào cho Hoa ở tin của Lan (không quyết định, không lý do)",
      not [d for d in hoa_rel if d["source_event"] == f"related:{lan_mid2}"]
      and not [s for r in w2.wake.reasons(agent_key=w2.k("hoa")) for s in w2.wake.sources(r["id"])
               if s["source_ref"].endswith(f":{lan_mid2}:{w2.k('hoa')}")], hoa_rel)
lan_rel = w2.decisions("lan", "related")
check("A->B->A: Minh (được Lan đánh thức) nhờ lại Lan thì bị chặn (loop)",
      any(d["silence_code"] in ("loop", "depth_limit") for d in lan_rel), lan_rel)
check("độ sâu > 2: Minh (độ sâu 2) nhờ Hoa thì bị chặn depth_limit",
      any(d["silence_code"] == "depth_limit" for d in hoa_rel), hoa_rel)
check("bị chặn: không lượt tự lên tiếng nào của Lan hay Hoa",
      [c["agent"] for c in w2.eng.roles("member_volunteer")] == [w2.k("minh")])

w3 = World("ask-self", roles=ROLES)
w3.eng.script[(w3.k("lan"), "leader_reply")] = [
    "Lan." + op(op="ask_peer", agent_key=w3.k("lan")) + op(op="ask_peer", agent_key="ag_khongco")]
w3.send("Tuần này làm gì?")
lan_msg = [m for m in w3.messages() if m["author_ref"] == w3.k("lan")][0]
notes = (lan_msg.get("meta") or {}).get("notes") or []
check("ask_peer trỏ chính mình hay người ngoài nhóm: bỏ kèm ghi chú, không lý do nào",
      sum("ask_peer" in n for n in notes) == 2 and w3.wake.reasons(code="related_review") == [], notes)
check("tin thường của agent không có quan hệ có cấu trúc: không đánh thức ai", w3.decisions(kind="related") == [])

# ═════ một lượt mỗi (agent, tin gốc), tự gọi mình (đơn vị) ═════
j = w.judge
root = rel[0]["root_ref"]
allowed, blocked = j.plan_related(w.ctx, 999, w.k("hoa"), {w.k("minh"): "ask_peer", w.k("hoa"): "job"},
                                  root_ref=root, depth=1, via_key="")
check("một lượt mỗi (agent, tin gốc): Minh đã xem xét liên quan trong tin gốc này thì không mở lần hai",
      (w.k("minh"), "once_per_root") in blocked and not [a for a in allowed if a["agent_key"] == w.k("minh")], blocked)
check("tác giả không tự xem xét tin của mình", (w.k("hoa"), "self") in blocked, blocked)

# ═════ quan hệ việc: người nhận và điều phối, input_refs, help ═════
w4 = World("job-rel", roles=ROLES)
tid, _ = w4.ts.enqueue_team(str(w4.dir), w4.team_id, "Chạy ads", "Chạy ads tuần này", source_ref="msg:x:1",
                            assignee_key=w4.k("minh"), coordinator_key=w4.k("lan"), chat_id=f"team:{w4.team_id}")
task = w4.ts.get_task(tid)
w4.tm.add_step(tid, w4.team_id, "synthesize", w4.k("hoa"), 1, "tổng hợp", ["4242"], None)
got = w4.runner._related_receivers(w4.team, w4.k("minh"), task, None, 4242, [])
check("quan hệ có cấu trúc từ việc: điều phối (job), bước có input_refs trỏ tin (input_ref); tác giả vẫn trong danh sách "
      "để bộ phán xử chặn `self`", got.get(w4.k("lan")) == "job" and got.get(w4.k("hoa")) == "input_ref", got)
parent = w4.tm.steps(tid)[0]
got2 = w4.runner._related_receivers(w4.team, w4.k("minh"), task,
                                    {"kind": "help", "parent_step": parent["step_id"]}, 777, [])
check("bước help: người đã nhờ hỗ trợ (bước cha) là quan hệ help", got2.get(w4.k("hoa")) in ("help", "input_ref"), got2)

# ═════ trần của nhóm ═════
w5 = World("rel-cap", roles=ROLES)
w5.tm.set_caps(w5.team_id, {"judge_daily": 1})
w5.eng.script[(w5.k("lan"), "leader_reply")] = ["Lan." + op(op="ask_peer", agent_key=w5.k("minh"))]
w5.jeng.decide = lambda p: batch(**{k: ("speak", 0.9) for k in keys_in(p)})
w5.send("Mọi người ơi tuần này làm gì?")
capped = [d for d in w5.decisions() if d["silence_code"] == "judge_cap"]
check("trần judge_daily của nhóm tính chung lô của tin chủ và lô xem xét liên quan: một lô chạy, lô kia judge_cap",
      len(w5.jeng.prompts) == 1 and capped, (len(w5.jeng.prompts), w5.decisions()))
rr = w5.wake.reasons(agent_key=w5.k("minh"), code="related_review")
check("lý do related_review vẫn khép (served), không để phần P chạy lại ngoài trần", rr and rr[0]["status"] == "served", rr)

finish()
