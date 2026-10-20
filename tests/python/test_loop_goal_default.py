"""Regression: loop THIẾU 'goal:' trong frontmatter phải mặc định 'custom' (chạy THÂN FILE),
KHÔNG rơi về 'business' (đọc số liệu MCP, bỏ hết thân file).

Bối cảnh lỗi thật: loop "Nhắc uống thuốc - kiểm tra xác nhận" (không có dòng goal:) bị
_norm_loop tự gán goal='business', nên _build_prompt bỏ qua thân file "nhắc uống thuốc" và
đi đọc POS + phân tích kinh doanh. Cả plugin javis_schedule lẫn form web đều mặc định 'custom';
chỉ parser self_improve._norm_loop còn lệch. Test này chốt parser cùng mặc định 'custom'.

Chạy tay / CI:

    python tests/run.py loop_goal_default

KHÔNG cần Claude CLI/SDK/mạng - chỉ test logic thuần _norm_loop + _build_prompt.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)
import asyncio
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-goaltest-"))

import self_improve  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_BRAIN_ROOT = tempfile.mkdtemp(prefix="javis-goalbrain-")


def _atomic_write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


deps = self_improve.LoopDeps(
    build_system_prompt=lambda brain: "SYS",
    brain_root=lambda brain: _BRAIN_ROOT,
    aux_model=lambda: None,
    atomic_write_text=_atomic_write,
    project_root=Path("."),
    state_dir=Path(os.environ["JAVIS_STATE_DIR"]),
    safe_tools=["Read", "Write", "Edit", "Glob", "Grep"],
    readonly_tools=["Read", "Glob", "Grep", "LS"],
)
feat = self_improve.LoopFeature(deps)

_BIZ_MARKER = "IMPROVE BUSINESS METRICS"
_MED_BODY = "Nhắc anh uống thuốc và kiểm tra đã xác nhận uống chưa."


# ── 1. _norm_loop: mặc định goal ──
check("norm: thiếu goal → 'custom' (KHÔNG phải 'business')",
      feat._norm_loop({"name": "L"}, _MED_BODY, "l")["goal"] == "custom")
check("norm: goal rỗng → 'custom'",
      feat._norm_loop({"name": "L", "goal": ""}, _MED_BODY, "l")["goal"] == "custom")
check("norm: goal None → 'custom'",
      feat._norm_loop({"name": "L", "goal": None}, _MED_BODY, "l")["goal"] == "custom")
check("norm: goal 'business' TƯỜNG MINH vẫn giữ 'business'",
      feat._norm_loop({"name": "L", "goal": "business"}, _MED_BODY, "l")["goal"] == "business")
check("norm: goal lạ → 'custom'",
      feat._norm_loop({"name": "L", "goal": "linhtinh"}, _MED_BODY, "l")["goal"] == "custom")


# ── 2. _build_prompt: loop có thân, thiếu goal → prompt bám THÂN FILE, không phải kinh doanh ──
loop_med = feat._norm_loop({"name": "Nhắc uống thuốc"}, _MED_BODY, "nhac-uong-thuoc")
prompt_med, skip_med = asyncio.run(feat._build_prompt(loop_med))
check("build: loop thiếu goal KHÔNG bị skip vì 'chưa có số liệu'", skip_med == "")
check("build: prompt CHỨA nội dung thân file (nhắc uống thuốc)", _MED_BODY in prompt_med)
check("build: prompt KHÔNG chứa marker kinh doanh", _BIZ_MARKER not in prompt_med)

# ── 3. đối chứng: khai goal:'business' tường minh thì MỚI vào nhánh kinh doanh ──
loop_biz = feat._norm_loop({"name": "KD", "goal": "business"}, _MED_BODY, "kd")
prompt_biz, skip_biz = asyncio.run(feat._build_prompt(loop_biz))
check("build (đối chứng): goal='business' tường minh → prompt có marker kinh doanh",
      _BIZ_MARKER in prompt_biz)


if _fails:
    print(f"\nFAIL - test_loop_goal_default: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_loop_goal_default: tất cả pass")
