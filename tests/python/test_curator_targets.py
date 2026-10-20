"""Test: curator chỉ chạy trên brain CÒN DÙNG. Chạy tay / CI:

    python tests/run.py curator_targets

Bối cảnh: danh sách learn_config['brains'] chỉ NỐI THÊM (mỗi lần chat một brain mới là
append, không bao giờ bớt - learn.py enqueue). Mỗi vòng curator chạy LINT Wiki, tức một
phiên agent đầy đủ, cho TỪNG brain trong danh sách. Đo thực tế: tháng 7 curator chạy 22
lần hết 97M token trên 4 brain, trong đó 1 brain là đường dẫn không tồn tại và 2 brain
người dùng đã bỏ gần 3 tuần.

Bẫy đã tránh: KHÔNG đo độ mới bằng mtime thư mục brain, vì chính curator ghi
Javis/learn-log mỗi vòng - lấy mtime thư mục thì brain nào cũng "vừa hoạt động" và
curator tự nuôi lý do chạy tiếp mãi. Chỉ đọc Memory/conversations (dấu vết người thật).

Phủ:
- Bỏ brain có thư mục không tồn tại.
- Bỏ brain im lặng quá stale_days.
- Giữ brain vừa trò chuyện.
- learn-log mới KHÔNG cứu được brain đã nguội (chốt đúng cái bẫy trên).
- stale_days = 0 thì tắt lọc theo thời gian (vẫn bỏ brain không tồn tại).
- Lý do bỏ qua được nêu rõ để in ra log.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="javis-curator-")
os.environ["JAVIS_STATE_DIR"] = _TMP

import learn  # noqa: E402

fails = []


def check(name, cond):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        fails.append(name)


ROOT = Path(_TMP) / "brains"


def make_brain(name, conv_days_ago=None, learnlog_days_ago=None):
    """Dựng brain giả. conv_days_ago=None → không có Memory/conversations."""
    root = ROOT / name
    (root / "Javis").mkdir(parents=True, exist_ok=True)
    if conv_days_ago is not None:
        d = root / "Memory" / "conversations"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "2026-07-01.md"
        f.write_text("chat", encoding="utf-8")
        t = time.time() - conv_days_ago * 86400
        os.utime(f, (t, t))
    if learnlog_days_ago is not None:
        d = root / "Javis" / "learn-log"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "2026-07-25.md"
        f.write_text("curator ghi", encoding="utf-8")
        t = time.time() - learnlog_days_ago * 86400
        os.utime(f, (t, t))
    return str(root)


b_active = make_brain("active", conv_days_ago=0)
b_stale = make_brain("stale", conv_days_ago=21)
# Brain nguội NHƯNG có learn-log mới tinh do chính curator vừa ghi - không được cứu nó.
b_stale_freshlog = make_brain("stale-freshlog", conv_days_ago=30, learnlog_days_ago=0)
b_missing = str(ROOT / "khong-ton-tai")

deps = learn.LearnDeps(
    build_system_prompt=lambda brain: "SYS",
    brain_root=lambda brain: brain,          # test truyền thẳng đường dẫn tuyệt đối
    brain_memory_dir=lambda brain: Path(brain) / "Memory",
    resolve_subfolder=lambda *a: "Wiki",
    aux_model=lambda: None,
    atomic_write_text=lambda p, t: Path(p).write_text(t, encoding="utf-8"),
    sessions_store=None,
    state_dir=Path(_TMP),
    readonly_tools=["Read", "Glob", "Grep"],
)
feat = learn.LearnFeature(deps)

cfg = {"brains": [b_active, b_stale, b_stale_freshlog, b_missing],
       "curator": {"stale_days": 14}}
run, skip = feat._curator_targets(cfg)

check("giu brain vua tro chuyen", b_active in run)
check("bo brain im lang 21 ngay", b_stale not in run)
check("bo brain co thu muc khong ton tai", b_missing not in run)
check("learn-log moi KHONG cuu duoc brain da nguoi", b_stale_freshlog not in run)
check("chi con dung 1 brain duoc chay", len(run) == 1)
check("neu ro ly do bo qua (3 muc)", len(skip) == 3)
check("ly do 'khong con' cho brain thieu", any("no longer exists" in s for s in skip))
check("ly do 'im lang' cho brain nguoi", any("silent" in s for s in skip))

# stale_days = 0 → tắt lọc theo thời gian, nhưng brain không tồn tại vẫn bị bỏ
run0, skip0 = feat._curator_targets({"brains": [b_active, b_stale, b_missing],
                                     "curator": {"stale_days": 0}})
check("stale_days=0: giu ca brain nguoi", b_stale in run0 and b_active in run0)
check("stale_days=0: van bo brain khong ton tai", b_missing not in run0)

# Không có Memory/conversations (brain mới tinh, chưa chat lần nào) → không bị coi là nguội
b_new = make_brain("brand-new")
run1, _ = feat._curator_targets({"brains": [b_new], "curator": {"stale_days": 14}})
check("brain chua co conversations thi khong bi loai oan", b_new in run1)

# Cấu hình mặc định phải khai stale_days, và curator_tick phải đi qua bộ lọc này
src = SERVER.joinpath("learn.py").read_text(encoding="utf-8")
check("config mac dinh co stale_days", '"stale_days": 14' in src)
check("curator_tick dung bo loc", "_curator_targets(cfg)" in src)

print()
if fails:
    print(f"FAILED {len(fails)}: " + "; ".join(fails))
    sys.exit(1)
print("PASS - tat ca")
