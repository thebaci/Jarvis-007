"""T3 phần J (0.156.0): bộ phán xử theo agent trong chat nhóm (thiết kế 2026-10-15 mục 7.2, 9, 9.1; GOAL 12 ca 2, 10, 19).

    python tests/run.py agent_judge_team -v

Kho SQLite tạm thật, bộ chạy nhóm thật, engine lượt nhóm và engine phán xử đều GIẢ (không có đường tới model thật).
- Lời gọi trực tiếp đi đường trả lời, không qua phán xử, ghi `address=certain`; không nằm trong prompt của lô.
- Cổng code: không tín hiệu thì `silent`/`no_signal` không model; có tín hiệu thì vào lô.
- MỘT lô (một lời gọi engine, một dòng `agent_calls` purpose `judge_batch`, agent_key rỗng, obligation 0, counted 1) mỗi tin;
  mỗi quyết định trỏ `ledger_ref` về dòng đó.
- K: điểm cao nhất tự lên tiếng (lượt `member_volunteer`, tự phát trong sổ lượt), không round-robin; K = 0 tắt.
- Hồ sơ riêng từng agent (hăng hái khác nhau ra ngưỡng khác nhau).
- Lỗi phán xử (lỗi engine, hết giờ, JSON sai, engine chưa sẵn sàng): ứng viên `silent` có lý do, lời gọi trực tiếp vẫn được
  trả lời.
- Trần `judge_daily`, trần chung của máy chủ, chế độ khi Cộng hưởng tắt (lọc code + lô / chỉ lọc code).
"""
import os

os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)

from _judge_world import World, batch, check, finish, keys_in  # noqa: E402

ROLES = {"lan": "Điều phối", "minh": "Quảng cáo Facebook, ngân sách ads", "hoa": "Kho hàng, tồn kho, nhập hàng"}

# ═════ lời gọi trực tiếp, cổng code, một lô ═════
w = World("direct", roles=ROLES)
w.jeng.decide = lambda p: batch(**{k: ("silent", 0.2) for k in keys_in(p)})
w.send("Hoa ơi kiểm tồn kho áo thun giúp", mentions=["hoa"])
direct = w.decisions("hoa", "direct")
check("được @ trực tiếp: một quyết định address=certain, không ngưỡng",
      len(direct) == 1 and direct[0]["address"] == "certain" and direct[0]["verdict"] == "speak"
      and direct[0]["threshold"] is None, direct)
check("được @ trực tiếp: trả lời qua đường member_reply như cũ",
      [c["agent"] for c in w.eng.roles("member_reply")] == [w.k("hoa")], w.eng.calls)
check("người đã được gọi KHÔNG nằm trong prompt của lô", all(w.k("hoa") not in keys_in(p) for p in w.jeng.prompts),
      w.jeng.prompts)
nosig = w.decisions("lan", "message")
check("không tín hiệu (không vai khớp, không câu hỏi chung): silent/no_signal, không vào lô",
      len(nosig) == 1 and nosig[0]["silence_code"] == "no_signal" and nosig[0]["ledger_ref"] == "", nosig)

w2 = World("one-batch", roles=ROLES)
w2.jeng.decide = lambda p: batch(**{k: ("silent", 0.2) for k in keys_in(p)})
w2.send("Mọi người ơi, tuần này nên làm gì với ngân sách ads và tồn kho?")
calls = w2.judge_calls()
check("một tin: đúng MỘT lời gọi engine phán xử", len(w2.jeng.prompts) == 1, len(w2.jeng.prompts))
check("một dòng agent_calls judge_batch: agent_key rỗng, ngữ cảnh nhóm, obligation 0, counted 1, ok",
      len(calls) == 1 and calls[0]["agent_key"] == "" and calls[0]["context_ref"] == w2.ctx
      and calls[0]["obligation"] == 0 and calls[0]["counted"] == 1 and calls[0]["status"] == "ok"
      and calls[0]["engine"] == "fake-aux", calls)
cands = [d for d in w2.decisions(kind="message") if d["ledger_ref"]]
check("mỗi ứng viên một quyết định trỏ ledger_ref về dòng đó",
      len(cands) == 2 and all(d["ledger_ref"] == f"call:{calls[0]['id']}" for d in cands), cands)
check("điều phối được gọi (ô điều phối của tin thường) ghi direct, không vào lô",
      w2.decisions("lan", "direct") and w2.k("lan") not in keys_in(w2.jeng.prompts[0]))
check("không ai được chọn thì không có lượt tự lên tiếng", w2.eng.roles("member_volunteer") == [])
w2.send("Mọi người ơi, tuần này nên làm gì với ngân sách ads và tồn kho?")
check("gửi lại cùng nội dung là tin mới: thêm đúng một lô", len(w2.jeng.prompts) == 2)

# ═════ K, không round-robin, hồ sơ riêng ═════
w3 = World("k-select", roles=ROLES)
w3.jeng.decide = lambda p: batch(**{w3.k("minh"): ("speak", 0.9), w3.k("hoa"): ("speak", 0.8)})
w3.send("Ai biết nên tăng ngân sách ads hay nhập thêm kho?")
vol = [d for d in w3.decisions(kind="message") if d["volunteer"]]
check("K=1: chỉ người điểm cao nhất tự lên tiếng", len(vol) == 1 and vol[0]["agent_key"] == w3.k("minh"), vol)
ns = [d for d in w3.decisions("hoa", "message")]
check("người còn lại: silent/not_selected", ns and ns[0]["silence_code"] == "not_selected", ns)
vt = w3.eng.roles("member_volunteer")
check("người được chọn chạy lượt member_volunteer qua đường lượt nhóm", [c["agent"] for c in vt] == [w3.k("minh")], vt)
check("lời nhắc lượt tự lên tiếng nói rõ không ai gọi", vt and "Nobody addressed you" in vt[0]["prompt"])
mirror = [r for r in w3.ledger.rows() if r["mirror_ref"].startswith("team_turn:") and r["purpose"] == "reply"]
vol_turns = [t for t in w3.tm.turns_since(0) if t["role"] == "member_volunteer"]
vm = [r for r in mirror if r["mirror_ref"] == f"team_turn:{vol_turns[0]['turn_id']}"] if vol_turns else []
check("lượt tự lên tiếng là lượt TỰ PHÁT trong sổ lượt chung (obligation 0)", vm and vm[0]["obligation"] == 0, vm)
msgs = w3.messages()
check("tin tự lên tiếng đăng trong nhóm, quyết định trỏ message_ref",
      any(m["author_ref"] == w3.k("minh") for m in msgs) and vol[0]["message_ref"].startswith("msg:")
      if vol else False, vol)
rep = w3.tm.replies_of(w3.team_id, int(vol[0]["source_event"].split(":")[1])) if vol else []
check("lượt tự lên tiếng có dòng kết cục như lượt trả lời (done)",
      any(r["agent_key"] == w3.k("minh") and r["status"] == "done" for r in rep), rep)

w4 = World("no-rr", roles=ROLES)
w4.jeng.decide = lambda p: batch(**{k: ("speak", 0.8) for k in keys_in(p)})
for i in range(3):
    w4.send(f"Câu hỏi chung số {i}: ads hay kho trước?")
chosen = [d["agent_key"] for d in sorted(w4.decisions(kind="message"), key=lambda d: d["id"]) if d["volunteer"]]
check("không round-robin: cùng điểm thì luôn cùng một người (thứ tự thành viên)", len(chosen) == 3
      and len(set(chosen)) == 1 and chosen[0] == w4.k("minh"), chosen)

w5 = World("profiles", roles=ROLES)
w5.judge.set_eagerness(w5.k("minh"), "high", "owner")
w5.judge.set_eagerness(w5.k("hoa"), "low", "owner")
w5.jeng.decide = lambda p: batch(**{k: ("speak", 0.6) for k in keys_in(p)})
w5.send("Mọi người: ngân sách ads hay tồn kho đáng lo hơn?")
dm_, dh = w5.decisions("minh", "message")[0], w5.decisions("hoa", "message")[0]
check("hồ sơ riêng: hăng hái cao (ngưỡng 0.45) nói với điểm 0.6", dm_["threshold"] == 0.45 and dm_["volunteer"], dm_)
check("hồ sơ riêng: hăng hái thấp (ngưỡng 0.75) im below_threshold với cùng điểm",
      dh["threshold"] == 0.75 and dh["silence_code"] == "below_threshold", dh)
check("đổi hăng hái ghi nhật ký changes (trước/sau)",
      [c["kind"] for c in w5.js.changes(w5.k("hoa"))] == ["eagerness_set"])
check("hồ sơ của agent này không đổi hồ sơ agent khác", w5.judge.get_profile(w5.k("lan"))["eagerness"] == "medium")

w6 = World("k-zero", roles=ROLES)
w6.tm.set_caps(w6.team_id, {"volunteer_k": 0})
w6.jeng.decide = lambda p: batch(**{k: ("speak", 0.9) for k in keys_in(p)})
w6.send("Mọi người ơi ads hay kho?")
check("K=0: tắt tự lên tiếng, ai muốn nói cũng silent/k_zero, không lượt tự lên tiếng",
      w6.eng.roles("member_volunteer") == [] and all(d["silence_code"] == "k_zero"
                                                    for d in w6.decisions(kind="message") if d["ledger_ref"]))
w6.tm.set_caps(w6.team_id, {"volunteer_k": 2})
w6.send("Mọi người ơi ads hay kho lần nữa?")
check("K=2: hai người tự lên tiếng", len(w6.eng.roles("member_volunteer")) == 2)

# ═════ lỗi phán xử: im có lý do, lời gọi trực tiếp vẫn trả lời ═════
for label, setup, code in (
        ("engine-error", lambda j: setattr(j, "raise_exc", RuntimeError("boom")), "policy_error"),
        ("bad-json", lambda j: setattr(j, "decide", lambda p: "tôi nghĩ là nên nói"), "bad_json"),
        ("timeout", lambda j: setattr(j, "delay", 5.0), "timeout"),
        ("unavailable", lambda j: setattr(j, "unavailable", True), "engine_unavailable")):
    we = World(label, roles=ROLES)
    setup(we.jeng)
    we.send("Mọi người ơi ads hay kho?", mentions=["lan"])
    cand = [d for d in we.decisions(kind="message") if d["agent_key"] != we.k("lan")]
    check(f"{label}: ứng viên silent/{code}", cand and all(d["verdict"] == "silent" and d["silence_code"] == code
                                                         for d in cand), cand)
    check(f"{label}: lời gọi trực tiếp vẫn được trả lời",
          [c["agent"] for c in we.eng.calls if c["role"] == "leader_reply"] == [we.k("lan")])
    check(f"{label}: không ai tự lên tiếng", we.eng.roles("member_volunteer") == [])
    row = we.judge_calls()
    # Engine chưa sẵn sàng: hoàn (chưa tới model). JSON sai: model đã trả lời (ok, tính). Lỗi, hết giờ: error (tính).
    want = {"engine_unavailable": "refunded", "bad_json": "ok"}.get(code, "error")
    check(f"{label}: dòng sổ lượt {want}", row and row[0]["status"] == want, row)

# ═════ trần judge_daily, trần chung, Cộng hưởng tắt ═════
w7 = World("judge-cap", roles=ROLES)
w7.tm.set_caps(w7.team_id, {"judge_daily": 1})
w7.send("Mọi người ơi ads hay kho?")
w7.send("Mọi người ơi ads hay kho, hỏi lại?")
check("judge_daily=1: chỉ một lô trong ngày", len(w7.jeng.prompts) == 1 and len(w7.judge_calls()) == 1)
last = [d for d in w7.decisions(kind="message") if d["silence_code"] == "judge_cap"]
check("hết judge_daily: ứng viên silent/judge_cap", len(last) == 2, w7.decisions(kind="message"))
check("judge_daily tách khỏi daily_turns: trả lời trực tiếp vẫn chạy",
      len([c for c in w7.eng.calls if c["role"] == "leader_reply"]) == 2)
w7.tm.set_caps(w7.team_id, {"judge_daily": None})
w7.send("Mọi người ơi ads hay kho, lần ba?")
check("judge_daily Không giới hạn (null): lô chạy lại", len(w7.jeng.prompts) == 2)

w8 = World("ceiling", roles=ROLES)
os.environ["JAVIS_RESONANCE_CALL_CEILING"] = "4"
w8.send("Mọi người ơi ads hay kho?")
cap_rows = [d for d in w8.decisions(kind="message") if d["silence_code"] == "server_ceiling"]
check("trần chung: lô tự phát chỉ dùng tới 80% (4 -> 3): sau lượt nghĩa vụ vẫn còn chỗ", len(w8.jeng.prompts) == 1,
      w8.ledger.rows())
w8.send("Mọi người ơi ads hay kho lần hai?")
w8.send("Mọi người ơi ads hay kho lần ba?")
cap_rows = [d for d in w8.decisions(kind="message") if d["silence_code"] == "server_ceiling"]
check("trần chung đầy phần tự phát: ứng viên silent/server_ceiling, không gọi engine", cap_rows
      and len(w8.jeng.prompts) < 3, (len(w8.jeng.prompts), w8.ledger.rows()))
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)

w9 = World("off-modes", roles=ROLES, enabled=("hoa",))
w9.jeng.decide = lambda p: batch(**{k: ("silent", 0.1) for k in keys_in(p)})
w9.send("Mọi người ơi ads hay kho?")
check("Cộng hưởng tắt, chế độ mặc định (lọc code + lô): agent tắt vẫn vào lô",
      w9.k("minh") in keys_in(w9.jeng.prompts[-1]) and w9.k("hoa") in keys_in(w9.jeng.prompts[-1]))
w9.tm.set_caps(w9.team_id, {"judge_off_batch": 0})
w9.send("Mọi người ơi ads hay kho lần hai?")
co = w9.decisions("minh", "message")[0]
check("chế độ chỉ lọc code: agent tắt Cộng hưởng silent/code_only, không vào lô",
      co["silence_code"] == "code_only" and w9.k("minh") not in keys_in(w9.jeng.prompts[-1]), co)
check("chế độ chỉ lọc code: agent BẬT Cộng hưởng vẫn vào lô", w9.k("hoa") in keys_in(w9.jeng.prompts[-1]))
try:
    w9.tm.set_caps(w9.team_id, {"judge_off_batch": 2})
    bad = False
except Exception:
    bad = True
check("chế độ phán xử chỉ nhận 0 hay 1", bad)

# ═════ bảng giới hạn ═════
rows = {r["key"]: r for r in w9.runner.limits_table(w9.team_id) if r["category"] == "owner"}
check("bảng giới hạn có judge_daily (chủ, Không giới hạn được) và K (chủ)",
      rows.get("judge_daily", {}).get("category") == "owner" and rows["judge_daily"]["unlimited_ok"]
      and rows.get("volunteer_k", {}).get("category") == "owner", rows.keys())
lead = [r for r in w9.runner.limits_table(w9.team_id) if r["category"] == "leader"]
check("Toàn quyền chỉnh được judge_daily và K trong trần chủ đặt (dòng trưởng nhóm)",
      {"judge_daily", "volunteer_k"} <= {r["key"] for r in lead})
check("chế độ phán xử khi Cộng hưởng tắt chỉ chủ chỉnh (không có dòng trưởng nhóm)",
      "judge_off_batch" not in {r["key"] for r in lead} and rows["judge_off_batch"]["unit"] == "mode")
w9.runner.grant_authority(w9.team_id, {"caps": {}, "ceilings": {"judge_daily": 10, "volunteer_k": 2}})
w9.runner.grant_authority  # noqa: B018
notes = []
with w9.runner.accept_lock:
    w9.runner._apply_admin(w9.team_id, w9.k("lan"), {"op": "set_cap", "cap": "judge_daily", "value": 8}, notes, "t1")
    w9.runner._apply_admin(w9.team_id, w9.k("lan"), {"op": "set_cap", "cap": "volunteer_k", "value": 3}, notes, "t2")
eff = w9.runner.effective_caps(w9.team_id)
check("trưởng nhóm Toàn quyền đặt judge_daily trong trần (8 <= 10)", eff["judge_daily"] == 8, (eff, notes))
check("trưởng nhóm không vượt trần K chủ đặt (3 > 2 bị từ chối)", eff["volunteer_k"] != 3 and notes, notes)

finish()
