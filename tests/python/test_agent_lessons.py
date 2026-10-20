"""T3 phần L (0.156.0): kho bài học có phạm vi (thiết kế 2026-10-15 mục 8.1, 12; GOAL 12 ca 1, 26).

    python tests/run.py agent_lessons -v

Kho thật (resonance.sqlite3 tạm). Phần đi qua main.py dùng engine GIẢ: hàm dựng engine thật bị thay bằng hàm ném lỗi ngay,
nên test không bao giờ gọi model thật.
- phạm vi: lượt nhóm nạp `team:<id>` + `*`, chat riêng nạp `dm:<agent_key>` + `*`, không bao giờ phạm vi khác;
- JAVIS_LESSON: lượt nhóm ghi `team:<id>` (nguồn self, gắn lượt/việc), chat riêng ghi `dm:<agent_key>` (không vào MEMORY.md);
  JAVIS_RULE vẫn vào "Luật chủ dặn";
- thu hồi giữ lịch sử; nâng lên `*` chỉ do chủ hay tự rà soát có bằng chứng ≥ 2 ngữ cảnh; khôi phục;
- bài học cũ trong MEMORY.md đọc được để giao diện ghi "bài học cũ chưa có phạm vi".
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-lessons-")
os.environ.pop("JAVIS_RESONANCE_CALL_CEILING", None)
TEMP = Path(tempfile.mkdtemp(prefix="javis-lessons-w-"))

import agent_lessons as AL  # noqa: E402
import resonance_store as RS  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {str(extra)[:400]}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


st = RS.GoalStore(TEMP / "resonance.sqlite3")
K, K2 = "agent_k1", "agent_k2"
T0 = 2_000_000_000.0

# ═════ phạm vi ═════
a = AL.add(st, agent_key=K, scope="team:A", kind="method", text="Trong nhóm A, báo số liệu kèm nguồn.", source="self",
           source_refs=["turn:t1"], at=T0)
b = AL.add(st, agent_key=K, scope="team:B", kind="presentation", text="Nhóm B thích câu ngắn.", source="self", at=T0)
d = AL.add(st, agent_key=K, scope=f"dm:{K}", kind="method", text="Chủ muốn hỏi lại trước khi làm việc lớn.",
           source="self", at=T0)
s = AL.add(st, agent_key=K, scope="*", kind="presentation", text="Không dùng gạch đầu dòng quá ba cấp.", source="owner",
           at=T0)
other = AL.add(st, agent_key=K2, scope="team:A", kind="method", text="Bài học của trợ lý khác.", source="self", at=T0)


def ids(rows):
    return sorted(r["id"] for r in rows)


check("lượt nhóm A nạp team:A + * (không team:B, không dm, không trợ lý khác)",
      ids(AL.for_prompt(st, K, AL.scopes_for("team:A", K))) == sorted([a, s]))
check("lượt nhóm B nạp team:B + *", ids(AL.for_prompt(st, K, AL.scopes_for("team:B", K))) == sorted([b, s]))
check("chat riêng nạp dm:<agent_key> + * (không bài học nhóm nào)",
      ids(AL.for_prompt(st, K, AL.scopes_for(f"dm:{K}", K))) == sorted([d, s]))
check("ngữ cảnh chat riêng của trợ lý khác bị từ chối", raises(lambda: AL.scopes_for(f"dm:{K2}", K), ValueError))
check("phạm vi dm của trợ lý khác không ghi được",
      raises(lambda: AL.add(st, agent_key=K, scope=f"dm:{K2}", kind="method", text="x", source="self"), ValueError))
check("for_prompt bỏ phạm vi không hợp lệ (không đọc dm của người khác)",
      ids(AL.for_prompt(st, K, [f"dm:{K2}", "*"])) == [s])
check("loại, nguồn sai bị từ chối",
      raises(lambda: AL.add(st, agent_key=K, scope="*", kind="xx", text="x", source="self"), ValueError)
      and raises(lambda: AL.add(st, agent_key=K, scope="*", kind="method", text="x", source="boss"), ValueError))
blk = AL.prompt_block(st, K, "team:A")
check("khối lời nhắc nhóm có mã, phạm vi và nguồn", f"[L{a}]" in blk and "this team" in blk and "turn:t1" in blk
      and "everywhere" in blk and "Nhóm B" not in blk, blk)
check("khối lời nhắc chat riêng không có bài học nhóm",
      "Nhóm B" not in AL.prompt_block(st, K, f"dm:{K}") and "hỏi lại" in AL.prompt_block(st, K, f"dm:{K}"))

# ═════ chống trùng, trần ═════
dup = AL.add(st, agent_key=K, scope="team:A", kind="method", text="trong nhóm a báo số liệu kèm nguồn!!", source="self",
             source_refs=["turn:t2"], at=T0 + 1)
check("trùng chữ (khác hoa thường, dấu câu) không thêm dòng, chỉ nối nguồn",
      dup == a and AL.get(st, a)["source_refs"] == ["turn:t1", "turn:t2"])
for i in range(AL.SCOPE_ACTIVE_CAP + 3):
    AL.add(st, agent_key=K, scope="team:C", kind="method", text=f"Bài học số {i}", source="self", at=T0 + i)
live_c = AL.lessons(st, K, scope="team:C")
check(f"trần {AL.SCOPE_ACTIVE_CAP} bài học đang dùng mỗi phạm vi, cũ nhất bị thay (vẫn còn lịch sử)",
      len(live_c) == AL.SCOPE_ACTIVE_CAP and "Bài học số 0" not in [r["text"] for r in live_c]
      and len(AL.lessons(st, K, status="superseded", scope="team:C")) == 3)

# ═════ thu hồi giữ lịch sử ═════
r = AL.revoke(st, b, by="owner", reason="sai", agent_key=K)
check("thu hồi: revoked, không nạp nữa", r and r["status"] == "revoked"
      and b not in ids(AL.for_prompt(st, K, AL.scopes_for("team:B", K))))
check("thu hồi lần hai: không còn gì", AL.revoke(st, b, by="owner") is None)
check("thu hồi bài học của trợ lý khác qua route: từ chối", AL.revoke(st, other, by="owner", agent_key=K) is None
      and AL.get(st, other)["status"] == "active")
evs = [e["kind"] for e in AL.events(st, b)]
check("nhật ký giữ lịch sử (thêm rồi thu hồi), dòng không bị xoá", evs == ["add", "revoke"] and AL.get(st, b) is not None,
      evs)
check("khôi phục bài học đã thu hồi", AL.restore(st, b, by="auto")["status"] == "active")

# ═════ nâng lên phạm vi chung ═════
check("tự rà soát nâng với bằng chứng 1 ngữ cảnh: từ chối",
      raises(lambda: AL.promote(st, a, by="review", evidence_contexts=["team:A"]), ValueError))
check("người khác chủ/tự rà soát (trưởng nhóm) không nâng được",
      raises(lambda: AL.promote(st, a, by="leader", evidence_contexts=["team:A", "team:B"]), PermissionError))
check("bằng chứng `*` không tính là ngữ cảnh",
      raises(lambda: AL.promote(st, a, by="review", evidence_contexts=["team:A", "*"]), ValueError))
na = AL.promote(st, a, by="review", evidence_contexts=["team:A", f"dm:{K}"], source_refs=["decision:3"])
check("tự rà soát nâng với bằng chứng 2 ngữ cảnh: bài học `*` mới, gốc thành superseded",
      AL.get(st, na)["scope"] == "*" and AL.get(st, na)["promoted_from"] == a and AL.get(st, a)["status"] == "superseded")
check("sau khi nâng, nhóm B và chat riêng cũng thấy", na in ids(AL.for_prompt(st, K, AL.scopes_for("team:B", K)))
      and na in ids(AL.for_prompt(st, K, AL.scopes_for(f"dm:{K}", K))))
own = AL.promote(st, d, by="owner")
check("chủ nâng không cần bằng chứng", AL.get(st, own)["scope"] == "*" and AL.get(st, own)["source"] == "owner")
check("nâng bài học đã ở `*`: từ chối", raises(lambda: AL.promote(st, own, by="owner"), ValueError))

# ═════ MEMORY.md cũ ═════
mem = ("# Ghi chú của chủ\n- Khách quen tên Ba.\n\n## Luật chủ dặn\n- Không dùng markdown.\n\n"
       "## Bài học (tự học)\n- Bài học cũ một.\n- Bài học cũ hai.\n")
check("bài học cũ trong MEMORY.md đọc được (chỉ mục tự học, không luật chủ)",
      AL.legacy_lessons(mem) == ["Bài học cũ một.", "Bài học cũ hai."])
check("tách JAVIS_LESSON khỏi văn bản", AL.split_lessons("Xong.\nJAVIS_LESSON: A\nJAVIS_LESSON: B\n") == (["A", "B"], "Xong."))

# ═════ góp ý của đồng đội: giao một lần, bằng chứng không bao giờ hiện ═════
f1 = AL.record_peer_feedback(st, team_id="A", receiver_key=K, author_key=K2, author_role="teammate", message_id=5,
                             note="Thiếu nguồn số liệu", nonce="n1", at=T0)
f2 = AL.record_peer_feedback(st, team_id="A", receiver_key=K, author_key=K2, author_role="leader", message_id=6,
                             note="Đến muộn", nonce="n2", evidence_reason="late_cancelled", at=T0)
check("nonce trùng: không ghi lần hai", AL.record_peer_feedback(st, team_id="A", receiver_key=K, author_key=K2,
                                                               author_role="teammate", message_id=5, note="x",
                                                               nonce="n1") is None)
check("nguồn chỉ là teammate/leader", raises(lambda: AL.record_peer_feedback(
    st, team_id="A", receiver_key=K, author_key=K2, author_role="owner", message_id=5, note="x", nonce="n3"), ValueError))
pend = AL.pending_peer_feedback(st, "A", K, 0)
check("góp ý bằng chứng (đến muộn) không vào lượt người nhận", [x["id"] for x in pend] == [f1])
check("góp ý nhóm A không hiện ở nhóm B", AL.pending_peer_feedback(st, "B", K, 0) == [])
AL.mark_peer_delivered(st, [f1], "turn:t9")
check("đã giao thì lượt sau không hiện lại", AL.pending_peer_feedback(st, "A", K, 0) == [])

# ═════ qua main.py: chat riêng và lượt nhóm (engine GIẢ, dựng engine thật thì ném ngay) ═════
import main  # noqa: E402
import team_engine  # noqa: E402


def _no_real_engine(*a, **k):
    raise AssertionError("test không được dựng engine thật")


main._reply_policy_sandbox_engine = lambda *a, **k: object()
team_engine.build = _no_real_engine

brain = str(TEMP / "brain")
Path(brain, "agents").mkdir(parents=True)
Path(brain, "agents", "viet.md").write_text("---\ntype: agent\nname: Viết\nrole: Viết bài\n---\nThân.\n",
                                            encoding="utf-8")
memf = Path(brain, "memory", "agents", "viet", "MEMORY.md")
memf.parent.mkdir(parents=True)
memf.write_text("## Bài học (tự học)\n- Bài học cũ trộn nhóm.\n", encoding="utf-8")
out = main._ket_luot_agent(brain, "viet", "Viết giúp anh đoạn mở bài",
                           "Đây là đoạn mở.\nJAVIS_LESSON: Chủ thích mở bài bằng câu hỏi.\n", conv_sid="")
gs = main._resonance_store()
key = main._dm_agent_key(brain, "viet")
check("chat riêng: output đã bóc JAVIS_LESSON", "JAVIS_LESSON" not in out and "Đây là đoạn mở." in out)
check("chat riêng: JAVIS_LESSON vào agent_lessons phạm vi dm:<agent_key> (đổi so với MEMORY.md)",
      [r["text"] for r in AL.lessons(gs, key, scope=f"dm:{key}")] == ["Chủ thích mở bài bằng câu hỏi."]
      and AL.lessons(gs, key, scope=f"dm:{key}")[0]["source"] == "self")
check("chat riêng: MEMORY.md không nhận bài học mới, bài học cũ giữ nguyên",
      memf.read_text(encoding="utf-8") == "## Bài học (tự học)\n- Bài học cũ trộn nhóm.\n")
main._ket_luot_agent(brain, "viet", "Từ giờ luôn ký tên cuối thư", "Dạ.\nJAVIS_RULE: Luôn ký tên cuối thư.\n")
check("JAVIS_RULE không đổi: vào mục Luật chủ dặn của MEMORY.md",
      "Luôn ký tên cuối thư." in memf.read_text(encoding="utf-8")
      and "Luôn ký tên cuối thư." not in [r["text"] for r in AL.lessons(gs, key)])
AL.add(gs, agent_key=key, scope="team:Z", kind="method", text="Bài học riêng nhóm Z.", source="self")
AL.add(gs, agent_key=key, scope="*", kind="method", text="Bài học chung đã nâng.", source="owner")
sp = main._agent_turn_system_prompt(brain, "viet", "")
check("lời nhắc chat riêng nạp dm + * (có mã nguồn), không nạp bài học nhóm",
      "Chủ thích mở bài bằng câu hỏi." in sp and "Bài học chung đã nâng." in sp and "Bài học riêng nhóm Z." not in sp
      and "[L" in sp and "lesson store of the PRIVATE CHAT" in sp, sp[-800:])

team = {"brain_id": main._brain_key(brain), "team_id": "Z", "session_id": "s-z"}


class FakeEng:
    def query(self, prompt):
        async def gen():
            yield {"type": "final", "content": "Kết quả nhóm.\nJAVIS_LESSON: Nhóm Z cần bảng tóm tắt.\n"}
        return gen()


team_engine.build = lambda spec, base, tag, settings=None: FakeEng()
_prov, _model, run = main._team_engine_for(team, key, "member_reply")


async def _started():
    return None

res = asyncio.run(run({"team_id": "Z", "turn_id": "turn-77", "system": "s", "prompt": "p", "engine_started": _started,
                       "task_id": "t_9", "step_id": "st_1"}))
team_engine.build = _no_real_engine
check("lượt nhóm: bài học chỉ được BÓC ở đây, chưa ghi gì (R3)", res["lessons"] == ["Nhóm Z cần bảng tóm tắt."]
      and "Nhóm Z cần bảng tóm tắt." not in [r["text"] for r in AL.lessons(gs, key)])
res["commit"]()
zl = [r for r in AL.lessons(gs, key, scope="team:Z") if r["text"] == "Nhóm Z cần bảng tóm tắt."]
check("lượt nhóm: commit ghi team:<id>, nguồn self, gắn lượt/việc/bước",
      len(zl) == 1 and zl[0]["source"] == "self" and set(zl[0]["source_refs"]) >= {"turn:turn-77", "task:t_9",
                                                                                     "step:st_1"}, zl)
check("lượt nhóm: MEMORY.md không nhận bài học nhóm", "Nhóm Z cần bảng" not in memf.read_text(encoding="utf-8"))
check("lượt nhóm sau không đổi chat riêng: lời nhắc chat riêng không có bài học nhóm Z",
      "Nhóm Z cần bảng tóm tắt." not in main._agent_turn_system_prompt(brain, "viet", ""))
team_engine.build = lambda spec, base, tag, settings=None: FakeEng()
_p, _m, run2 = main._pulse_engine_for(key, f"dm:{key}", "scan")
res2 = asyncio.run(run2({"team_id": f"dm:{key}", "turn_id": "scan-1", "system": "s", "prompt": "p",
                         "engine_started": _started}))
team_engine.build = _no_real_engine
before = len(AL.lessons(gs, key, status=None))
res2["commit"]()
check("engine của lượt quét/xem xét (đội giả không có session_id): commit không ghi bài học nhóm nào",
      len(AL.lessons(gs, key, status=None)) == before)
check("bài học cũ của MEMORY.md đọc được qua móc hiển thị", main._learn_legacy(key) == ["Bài học cũ trộn nhóm."])

print(f"\n{'ĐỎ' if fails else 'XANH'}: {len(fails)} lỗi")
raise SystemExit(1 if fails else 0)
