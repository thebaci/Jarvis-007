"""Test: Việc định kỳ xuyên brain (spec 2026-07-19). Chạy tay / CI:

    python tests/run.py viec_xuyen_brain

Phủ 5 mảnh:
- Di chuyển loop giữa brain: thành công (file dời + state theo), va chạm slug (từ chối, KHÔNG
  ghi đè), brain trùng (từ chối).
- Di chuyển nhắc hẹn: record sang đúng brain đích, giữ id + chat_id; brain trùng từ chối.
- javis_schedule: câu xác nhận create có TÊN BRAIN (mảnh 4 - bịt rối ngay lúc tạo).
- Nhớ bền /brain Telegram: set -> đọc lại sau "restart" trả đúng brain; brain xoá -> về mặc
  định + dọn entry (mảnh 5).
- GET /viec/all: mỗi item gắn đúng brain_name/brain_path (mảnh 1 - gộp mọi brain).

KHÔNG chạm mạng: mọi test gọi hàm thuần / ghi file thư mục tạm.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

# PHẢI set BRAINS_DIR + STATE_DIR sang thư mục tạm TRƯỚC khi import main (main đọc env lúc import).
_STATE = tempfile.mkdtemp(prefix="javis-viec-state-")
_BRAINS = tempfile.mkdtemp(prefix="javis-viec-brains-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ["BRAINS_DIR"] = _BRAINS
sys.path.insert(0, str(ROOT / "system" / "plugins" / "javis-schedule"))

import main            # noqa: E402
import self_improve    # noqa: E402
import reminders as reminders_mod   # noqa: E402
import plugin as sched  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


def _atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ══════════════════════ A. Di chuyển loop giữa brain ══════════════════════
_loop_deps = self_improve.LoopDeps(
    build_system_prompt=lambda brain: "SYS",
    brain_root=lambda brain: brain,   # identity: path vault = "brain"
    aux_model=lambda: None,
    atomic_write_text=_atomic_write,
    project_root=Path("."),
    state_dir=Path(_STATE),
    safe_tools=[], readonly_tools=[],
)
_lf = self_improve.LoopFeature(_loop_deps)

_bA = tempfile.mkdtemp(prefix="javis-brainA-")
_bB = tempfile.mkdtemp(prefix="javis-brainB-")

sched._create_loop_file(_bA, name="Quet don", prompt="Moi vong quet don moi.", schedule="120m")
_slug = "quet-don"
check("A: loop tạo ở brain A đọc được", bool(_lf.get_loop(_bA, _slug)))
_lf._update_state(_bA, _slug, last_run=12345.0, runs_today=2)

_mv = _lf.move_loop(_bA, _bB, _slug)
check("A: move_loop trả ok", _mv.get("ok") is True)
check("A: loop BIẾN MẤT khỏi brain nguồn", _lf.get_loop(_bA, _slug) is None)
check("A: loop XUẤT HIỆN ở brain đích", bool(_lf.get_loop(_bB, _slug)))
check("A: file .md nguồn đã xoá", not (Path(_bA) / "Javis" / "loops" / f"{_slug}.md").exists())
check("A: file .md đích tồn tại", (Path(_bB) / "Javis" / "loops" / f"{_slug}.md").exists())
check("A: state runtime (last_run) theo sang đích",
      _lf.read_state(_bB).get(_slug, {}).get("last_run") == 12345.0)

# Va chạm: đích ĐÃ có slug này -> tạo lại ở A rồi move -> phải TỪ CHỐI, không ghi đè.
sched._create_loop_file(_bA, name="Quet don", prompt="ban sao.", schedule="120m")
_mv2 = _lf.move_loop(_bA, _bB, _slug)
check("A: move vào brain đích đã có slug -> TỪ CHỐI (không ghi đè)", _mv2.get("ok") is False)
check("A: lỗi va chạm nói rõ 'đã có'", "đã có" in (_mv2.get("error") or ""))
check("A: bản gốc ở A vẫn còn sau khi move bị từ chối", bool(_lf.get_loop(_bA, _slug)))

# Brain nguồn == đích -> từ chối.
_mv3 = _lf.move_loop(_bA, _bA, _slug)
check("A: move nguồn==đích -> từ chối", _mv3.get("ok") is False)

# Slug không tồn tại -> từ chối rõ.
_mv4 = _lf.move_loop(_bA, _bB, "khong-ton-tai")
check("A: move loop không tồn tại -> lỗi", _mv4.get("ok") is False)


# ══════════════════════ B. Di chuyển nhắc hẹn giữa brain ══════════════════════
async def _fake_send(chat_id, text):
    return True, ""


_rem_deps = reminders_mod.RemindersDeps(
    brain_root=lambda brain: brain,
    atomic_write_text=_atomic_write,
    send_telegram=_fake_send,
    build_system_prompt=lambda brain: "SYS",
    aux_model=lambda: None,
    safe_tools=[], readonly_tools=[],
    scheduler_brains=lambda: [],
)
_rf = reminders_mod.RemindersFeature(_rem_deps)

_rA = tempfile.mkdtemp(prefix="javis-remA-")
_rB = tempfile.mkdtemp(prefix="javis-remB-")
_rem = _rf._create(_rA, "goi khach X", delay_min=30, chat_id="777", label="Goi khach")
_rid = _rem["id"]
check("B: nhắc tạo ở brain A đọc được",
      any(r["id"] == _rid for r in _rf._load(_rA).get("reminders", [])))

_rmv = _rf.move(_rA, _rB, _rid)
check("B: move nhắc trả ok", _rmv.get("ok") is True)
check("B: nhắc BIẾN MẤT khỏi brain nguồn",
      not any(r["id"] == _rid for r in _rf._load(_rA).get("reminders", [])))
_recs_b = [r for r in _rf._load(_rB).get("reminders", []) if r["id"] == _rid]
check("B: nhắc XUẤT HIỆN ở brain đích, giữ id", len(_recs_b) == 1)
check("B: giữ nguyên chat_id (báo về đúng người)",
      bool(_recs_b) and _recs_b[0].get("chat_id") == "777")
check("B: move nguồn==đích -> từ chối", _rf.move(_rB, _rB, _rid).get("ok") is False)
check("B: move id không tồn tại -> lỗi", _rf.move(_rA, _rB, "khong-co").get("ok") is False)


# ══════════════════════ C. javis_schedule báo tên brain (mảnh 4) ══════════════════════
_vault_kk = os.path.join(tempfile.mkdtemp(prefix="javis-vault-kk-"), "KimKhiHaLoc")
os.makedirs(_vault_kk)
_res_loop = asyncio.run(sched._do_create(_vault_kk, {
    "name": "Quet don kho", "prompt": "quet don moi 2 tieng", "schedule": "120m"}))
check("C: câu tạo LOOP nêu tên brain", "KimKhiHaLoc" in _res_loop)
check("C: _create_loop_file có brain_name -> chuỗi chứa brain",
      "in brain MyBrain" in sched._create_loop_file(
          tempfile.mkdtemp(prefix="javis-vault-mb-"), name="Viec X",
          prompt="lam gi do", schedule="120m", brain_name="MyBrain"))


# ══════════════════════ D. Nhớ bền /brain Telegram (mảnh 5) ══════════════════════
_tb = Path(main.BRAINS_DIR) / "TestBrainX"
_tb.mkdir(parents=True, exist_ok=True)
main._tg_set_brain("chat999", str(_tb))
check("D: set brain -> ghi map bền (tên brain)", main._TG_BRAIN_MAP.get("chat999") == "TestBrainX")
check("D: map bền có ghi ra file", (Path(_STATE) / "tg_brain.json").exists())

# Giả lập RESTART: xoá phiên sống + nạp lại map từ đĩa.
main._TG_SESS.clear()
main._TG_BRAIN_MAP.clear()
main._TG_BRAIN_MAP.update(main._tg_load_brain_map())
_resolved = main._tg_brain("chat999")
check("D: sau restart, /brain vẫn nhớ -> resolve đúng brain",
      Path(_resolved).name == "TestBrainX")

# Brain bị xoá -> _tg_brain rơi về mặc định + dọn entry cũ (không kẹt).
shutil.rmtree(_tb)
main._TG_SESS.clear()
_resolved2 = main._tg_brain("chat999")
check("D: brain đã xoá -> KHÔNG kẹt vào brain không còn", Path(_resolved2).name != "TestBrainX")
check("D: entry brain đã xoá được dọn khỏi map", "chat999" not in main._TG_BRAIN_MAP)


# ══════════════════════ E. GET /viec/all gắn đúng brain cho item (mảnh 1) ══════════════════════
_vb = Path(main.BRAINS_DIR) / "ViecBrain"
(_vb / "Javis" / "loops").mkdir(parents=True, exist_ok=True)
(_vb / "Javis" / "loops" / "test-loop.md").write_text(
    "---\ntype: loop\nname: Test Loop\nslug: test-loop\nenabled: false\n"
    "goal: custom\nmode: suggest\ninterval_min: 120\n---\n\nlam viec gi do moi vong\n",
    encoding="utf-8")
_all = asyncio.run(main.viec_all())
_grp = next((b for b in _all.get("brains", []) if b.get("name") == "ViecBrain"), None)
check("E: /viec/all trả nhóm brain ViecBrain", _grp is not None)
check("E: nhóm có loop vừa tạo", bool(_grp and _grp.get("loops")))
_lp0 = (_grp or {}).get("loops", [{}])[0] if _grp and _grp.get("loops") else {}
check("E: item loop gắn brain_name đúng", _lp0.get("brain_name") == "ViecBrain")
check("E: item loop gắn brain_path đúng", _lp0.get("brain_path") == _grp.get("path"))


# ══════════════════════ Tổng kết ══════════════════════
print()
if _fails:
    print(f"FAIL - {len(_fails)} test hỏng: " + "; ".join(_fails))
    sys.exit(1)
print("OK - test_viec_xuyen_brain: tất cả pass")
