"""Test: curator chỉ soi phần wiki THẬT SỰ đổi, không quét lại cả kho mỗi vòng.

    python tests/run.py curator_scope

Bối cảnh (đo trên brain thật "My Bullet Journal"): curator quét lại toàn bộ wiki mỗi vòng như
chưa từng thấy, nên chi phí bám theo ĐỘ LỚN brain chứ không theo lượng thay đổi. Đầu tháng 7
tốn 2,46M/vòng, cuối tháng 7 tốn 5,22M/vòng - gấp đôi trong ba tuần - dù số lượt chỉ tăng 16%
(37 -> 43): ngữ cảnh mỗi lượt phình ra vì vòng nào cũng đọc lại cả kho. Trong khi thực tế
7/14 ngày gần nhất wiki KHÔNG đổi note nào, ngày có đổi cũng chỉ 2-7 note trên 174.

Phủ:
- Lần đầu (chưa có mốc) -> quét toàn bộ.
- Không đổi gì -> BỎ HẲN vòng (không spawn agent).
- Có note đổi -> chỉ soi đúng những note đó.
- Xoá/đổi tên note -> quét toàn bộ (wikilink gãy không thấy được qua mtime).
- Đến hẹn thì vẫn quét toàn bộ (vấn đề liên-trang tích tụ dần).
- Bỏ qua vòng thì GIỮ mốc cũ - nếu dời mốc, thay đổi trước đó bị nuốt vĩnh viễn.
- Wiki rỗng -> bỏ qua, không spawn.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="javis-cscope-")
os.environ["JAVIS_STATE_DIR"] = _TMP

import learn  # noqa: E402

fails = []


def check(name, cond):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        fails.append(name)


BRAIN = str(Path(_TMP) / "brain")
WIKI = Path(BRAIN) / "Wiki"
WIKI.mkdir(parents=True, exist_ok=True)


def note(name, days_ago=0):
    f = WIKI / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("noi dung", encoding="utf-8")
    t = time.time() - days_ago * 86400
    os.utime(f, (t, t))
    return f


deps = learn.LearnDeps(
    build_system_prompt=lambda b: "SYS",
    brain_root=lambda b: b,
    brain_memory_dir=lambda b: Path(b) / "Memory",
    resolve_subfolder=lambda root, pat, default: str(Path(root) / "Wiki"),
    aux_model=lambda: None,
    atomic_write_text=lambda p, t: Path(p).write_text(t, encoding="utf-8"),
    sessions_store=None,
    state_dir=Path(_TMP),
    readonly_tools=["Read", "Glob", "Grep"],
)
feat = learn.LearnFeature(deps)

note("a.md", days_ago=10)
note("b.md", days_ago=10)
note("sub/c.md", days_ago=10)

# ---- 1. lần đầu: chưa có mốc -> quét toàn bộ ----
cfg = {"curator": {"full_every_days": 30, "state": {}}}
s = feat._curator_scope(cfg, BRAIN)
check("lan dau -> quet toan bo", s["mode"] == "full")
check("lan dau: neu ro ly do", "first run" in s["reason"])

# ghi lại mốc như run_curator làm sau một vòng full
now = time.time()
cfg["curator"]["state"][BRAIN] = {"last_scan": now, "last_full": now, "sig": s["sig"], "n": s["n"]}

# ---- 2. không đổi gì -> bỏ hẳn vòng ----
s2 = feat._curator_scope(cfg, BRAIN)
check("khong doi gi -> BO HAN vong", s2["mode"] == "skip")
check("khong doi: neu ro ly do", "no wiki note changed" in s2["reason"])

# ---- 3. sửa 1 note -> chỉ soi note đó ----
time.sleep(0.02)
note("b.md")
s3 = feat._curator_scope(cfg, BRAIN)
check("co note doi -> chi soi phan doi", s3["mode"] == "incremental")
check("dung 1 note trong danh sach", s3["changed"] == ["b.md"])
check("neu ro bao nhieu tren bao nhieu", "1/3" in s3["reason"])

# note mới cũng phải bị bắt
time.sleep(0.02)
note("moi.md")
s4 = feat._curator_scope(cfg, BRAIN)
check("note MOI cung bi bat", sorted(s4["changed"]) == ["b.md", "moi.md"])
check("them note KHONG bi ep quet toan bo (viec thuong ngay)", s4["mode"] == "incremental")

# ---- 4. xoá note -> quét toàn bộ (wikilink gãy) ----
cfg["curator"]["state"][BRAIN]["sig"] = s4["sig"]           # coi như vòng trước đã ghi nhận
cfg["curator"]["state"][BRAIN]["n"] = s4["n"]
cfg["curator"]["state"][BRAIN]["last_scan"] = time.time()
(WIKI / "moi.md").unlink()
s5 = feat._curator_scope(cfg, BRAIN)
check("xoa note -> quet toan bo", s5["mode"] == "full")
check("xoa note: neu ro vi wikilink", "deleted" in s5["reason"] or "renamed" in s5["reason"])

# đổi tên cũng vậy (mtime của các file còn lại không đổi)
files, sig_now = feat._wiki_scan(BRAIN)
cfg["curator"]["state"][BRAIN] = {"last_scan": time.time(), "last_full": time.time(),
                                  "sig": sig_now, "n": len(files)}
os.rename(WIKI / "a.md", WIKI / "a-doi-ten.md")
check("doi ten -> quet toan bo", feat._curator_scope(cfg, BRAIN)["mode"] == "full")

# ---- 5. đến hẹn thì vẫn quét toàn bộ ----
files, sig_now = feat._wiki_scan(BRAIN)
old = time.time() - 31 * 86400
cfg["curator"]["state"][BRAIN] = {"last_scan": time.time(), "last_full": old,
                                  "sig": sig_now, "n": len(files)}
s6 = feat._curator_scope(cfg, BRAIN)
check("den hen -> quet toan bo du khong doi gi", s6["mode"] == "full")
check("den hen: neu ro ly do", "full scan" in s6["reason"])
# tắt được bằng full_every_days=0
cfg["curator"]["full_every_days"] = 0
check("full_every_days=0 -> khong ep quet toan bo", feat._curator_scope(cfg, BRAIN)["mode"] == "skip")
cfg["curator"]["full_every_days"] = 30

# ---- 6. wiki rỗng -> bỏ qua ----
empty = str(Path(_TMP) / "brain-rong")
(Path(empty) / "Wiki").mkdir(parents=True, exist_ok=True)
check("wiki rong -> bo qua", feat._curator_scope(cfg, empty)["mode"] == "skip")

# ---- 7. BẪY: bỏ qua vòng thì phải GIỮ mốc cũ ----
# Nếu vòng "skip" cũng dời last_scan lên hiện tại, note sửa TRƯỚC đó mà chưa kịp soi sẽ rơi ra
# khỏi cửa sổ vĩnh viễn - im lặng mất, không bao giờ được lint.
src = SERVER.joinpath("learn.py").read_text(encoding="utf-8")
check("run_curator chi doi moc khi THAT SU quet", 'if not skipped:\n                st["last_scan"]' in src)
check("run_curator co goi _curator_scope", "scope = self._curator_scope(cfg, brain)" in src)
check("prompt quet-phan-doi co dan danh sach note", "RECENTLY CHANGED NOTES:" in src)
check("prompt quet-phan-doi cam quet ca wiki", "do NOT rescan the whole wiki" in src)
check("config mac dinh co full_every_days", '"full_every_days": 30' in src)
check("run_curator luu ca so luong note", 'st["n"] = scope.get("n", 0)' in src)

print()
if fails:
    print(f"FAILED {len(fails)}: " + "; ".join(fails))
    sys.exit(1)
print("PASS - tat ca")
