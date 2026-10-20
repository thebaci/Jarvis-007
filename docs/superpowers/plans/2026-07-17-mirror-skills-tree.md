# B4: mirror_skills đệ quy + cổng chữ ký Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho skill mang theo `references/`/`scripts/` tới được đường Claude Code nạp native, đồng thời cắt chi phí `mirror_skills` từ ~52ms xuống ~6ms mỗi lượt chat.

**Architecture:** Thêm cổng hai tầng vào `mirror_skills`. Tầng một cộng chữ ký CHỈ bằng `stat` (không đọc byte nào) rồi so với cache trong bộ nhớ theo root; không đổi thì trả về ngay - đây là đường 99% lượt chat chạm. Tầng hai, chỉ khi chữ ký đổi, mới copy đệ quy cả cây. Lock riêng cho mirror, lấy kiểu không-chờ, nên không bao giờ xếp hàng chặn event loop và không tạo chu trình với `_LOCK`.

**Tech Stack:** Python 3.12, stdlib (`os.scandir`, `hashlib`, `shutil`, `threading`, `pathlib`). Không pytest.

## Global Constraints

- Spec đầy đủ: `docs/superpowers/specs/2026-07-17-mirror-skills-tree-design.md`. Đọc mục "Rủi ro" trước khi bắt đầu.
- **Ngôn ngữ:** mọi comment, docstring, thông báo lỗi viết tiếng Việt.
- **TUYỆT ĐỐI không dùng ký tự em dash (U+2014)** trong bất kỳ file nào. Dùng "-". Luật cứng của người dùng.
- **KHÔNG dùng pytest.** Test là script chạy thẳng, dùng `check(name, cond)` + `_fails` + `sys.exit(1)`. Mẫu chuẩn: `server/test_loop_ambient.py:23-30` và `:117-120`.
- **KHÔNG lấy `test_plugins_host.py` làm mẫu** - nó dùng bare assert nên dừng ở lỗi ĐẦU TIÊN.
- **Lệnh chạy test:** `cd server && ../.venv/Scripts/python.exe test_system_sync.py`. Venv ở GỐC repo, KHÔNG phải `server/.venv`.
- **Test mới phải đặt tên `server/test_*.py`** thì CI (`.github/workflows/ci.yml:29-39`) mới glob thấy.
- **Preamble test, thứ tự load-bearing** (env TRƯỚC import):
  ```python
  os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-synctest-"))
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import system_sync  # noqa: E402
  ```
- **`mirror_skills` TUYỆT ĐỐI không được lấy `_LOCK`** (`system_sync.py:280`). Nó bị gọi từ `sync_brain` KHI ĐANG giữ `_LOCK`, mà `threading.Lock` không reentrant nên sẽ deadlock ngay lượt chat đầu.
- **`skill_hash` KHÔNG được đổi** chữ ký hay ngữ nghĩa. `sync_brain`, `LEGACY_HASHES` và CLI `--hash` phụ thuộc output chính xác của nó. Chỉ THÔI DÙNG nó trong `mirror_skills`.
- Test tự dựng brain giả trong `tempfile.mkdtemp`. TUYỆT ĐỐI không chạm `brains/` thật.
- Không để lại file/thư mục rác ngoài temp.

---

## File Structure

**Tạo mới:**
- `server/test_system_sync.py` - test cho `mirror_skills`. Hôm nay KHÔNG một test nào trong repo chạm hàm này.

**Sửa:**
- `server/system_sync.py` - thêm `import os`; thêm `_mirror_signature`, `_MIRROR_SIG`, `_MIRROR_LOCKS`; viết lại thân `mirror_skills` (hiện ở dòng 235-264).

---

### Task 1: Dựng test_system_sync.py, chốt hành vi hiện tại và đòi hỏi mới

**Files:**
- Create: `server/test_system_sync.py`

**Interfaces:**
- Consumes: `system_sync.mirror_skills(root) -> None` (đã có, `system_sync.py:235`).
- Produces: không có. Task 2 làm test này chuyển từ đỏ sang xanh.

- [ ] **Step 1: Viết test**

Tạo `server/test_system_sync.py`:

```python
"""Test mirror_skills: copy cả cây con + cổng chữ ký stat. Chạy tay / CI:

    cd server && ../.venv/Scripts/python.exe test_system_sync.py

Không cần pytest, không chạm mạng. Tự dựng brain giả trong thư mục tạm.
Phủ: copy thư mục con (references/ scripts/), file phụ ngang hàng đổi thì mirror nhận
(bug CÓ SẴN), bỏ qua .disabled, add-only không xoá file lạ, không đổi gì thì KHÔNG copy
lại lần nào và KHÔNG đọc nội dung file nào, hai luồng đồng thời không treo, file nhị phân
qua nguyên vẹn.
"""
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-synctest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import system_sync  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


def _mk_brain(prefix):
    """Brain giả: 1 skill có cây con + 1 skill đã tắt. Trả (root, skill_dir, mirror_dir)."""
    root = Path(tempfile.mkdtemp(prefix=prefix))
    sk = root / "skills" / "co-tai-lieu"
    (sk / "references").mkdir(parents=True)
    (sk / "scripts").mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: Có tài liệu\ndescription: Thử cây con.\n---\nthân\n",
                                 encoding="utf-8")
    (sk / "references" / "chi-tiet.md").write_text("chi tiết v1\n", encoding="utf-8")
    (sk / "scripts" / "chay.py").write_text("print('hi')\n", encoding="utf-8")
    (sk / "anh.png").write_bytes(b"\x89PNG\r\n\x1a\n binary")
    dis = root / "skills" / ".disabled" / "da-tat"
    dis.mkdir(parents=True)
    (dis / "SKILL.md").write_text("---\nname: Đã tắt\n---\nx\n", encoding="utf-8")
    return root, sk, root / ".claude" / "skills" / "co-tai-lieu"


# ---- copy đệ quy ----
_ROOT, _SK, _MIR = _mk_brain("javis-mirror-")
system_sync.mirror_skills(_ROOT)
check("mirror có SKILL.md", (_MIR / "SKILL.md").is_file())
check("mirror có references/chi-tiet.md", (_MIR / "references" / "chi-tiet.md").is_file())
check("mirror có scripts/chay.py", (_MIR / "scripts" / "chay.py").is_file())
check("mirror giữ nguyên byte của file nhị phân",
      (_MIR / "anh.png").is_file()
      and (_MIR / "anh.png").read_bytes() == b"\x89PNG\r\n\x1a\n binary")
check("KHÔNG mirror skill đã tắt", not (_ROOT / ".claude" / "skills" / "da-tat").exists())

# ---- đổi references/ mà SKILL.md không đổi -> mirror PHẢI nhận (bug CÓ SẴN) ----
(_SK / "references" / "chi-tiet.md").write_text("chi tiết v2\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("đổi references/ (SKILL.md không đổi) -> mirror nhận bản mới",
      (_MIR / "references" / "chi-tiet.md").read_text(encoding="utf-8") == "chi tiết v2\n")

# ---- đổi file phụ NGANG HÀNG mà SKILL.md không đổi -> mirror PHẢI nhận (bug CÓ SẴN) ----
(_SK / "anh.png").write_bytes(b"\x89PNG\r\n\x1a\n DOI ROI")
system_sync.mirror_skills(_ROOT)
check("đổi file phụ ngang hàng (SKILL.md không đổi) -> mirror nhận bản mới",
      (_MIR / "anh.png").read_bytes() == b"\x89PNG\r\n\x1a\n DOI ROI")

# ---- add-only: file lạ trong mirror KHÔNG bị xoá ----
(_MIR / "nguoi-dung-them.md").write_text("giữ tôi lại\n", encoding="utf-8")
(_SK / "SKILL.md").write_text("---\nname: Có tài liệu\ndescription: Đổi để ép copy.\n---\nthân 2\n",
                              encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("add-only: không xoá file lạ ở mirror", (_MIR / "nguoi-dung-them.md").is_file())

# ---- không đổi gì -> KHÔNG copy lại lần nào ----
# KHÔNG kiểm bằng mtime: shutil.copy2 giữ nguyên mtime của NGUỒN nên đích luôn cùng mtime
# dù có copy lại hay không -> test kiểu đó xanh cả khi code sai. Phải ĐẾM copy2 thật sự.
_copies = []
_orig_copy2 = shutil.copy2


def _spy_copy2(src, dst, *a, **kw):
    _copies.append(str(dst))
    return _orig_copy2(src, dst, *a, **kw)


shutil.copy2 = _spy_copy2
try:
    system_sync.mirror_skills(_ROOT)
    system_sync.mirror_skills(_ROOT)
finally:
    shutil.copy2 = _orig_copy2
check(f"không đổi gì -> KHÔNG copy lại lần nào (đếm được {len(_copies)})", len(_copies) == 0)

# ---- không đổi gì -> KHÔNG còn đọc-và-băm SKILL.md như bản cũ ----
# CHÍNH XÁC ĐIỀU NÀY CHỨNG MINH: bản cũ đọc SKILL.md qua Path.read_text để băm, mỗi skill
# hai lần (nguồn + đích), mỗi lượt gọi - đó là 52ms. Spy này bắt đúng đường đó biến mất.
# ĐIỀU NÓ *KHÔNG* CHỨNG MINH: "không đọc file nào cả". shutil.copy2 đọc bằng open() chứ
# không qua Path.read_text, nên nếu copy vẫn chạy thì spy này VẪN im. Việc chứng minh không
# copy là của check _copies ở trên. Hai check bù nhau, đừng gộp.
_reads = []
_orig_rt = Path.read_text
_orig_rb = Path.read_bytes


def _spy_rt(self, *a, **kw):
    _reads.append(str(self))
    return _orig_rt(self, *a, **kw)


def _spy_rb(self, *a, **kw):
    _reads.append(str(self))
    return _orig_rb(self, *a, **kw)


Path.read_text = _spy_rt
Path.read_bytes = _spy_rb
try:
    system_sync.mirror_skills(_ROOT)
finally:
    Path.read_text = _orig_rt
    Path.read_bytes = _orig_rb
check(f"không đổi gì -> KHÔNG còn đọc-và-băm SKILL.md (đếm được {len(_reads)} lượt read_text/read_bytes)",
      len(_reads) == 0)

# ---- hai luồng đồng thời trên cùng root -> không treo ----
_R2, _SK2, _MIR2 = _mk_brain("javis-mirrorpar-")
_done = []


def _race():
    system_sync.mirror_skills(_R2)
    _done.append(1)


_ts = [threading.Thread(target=_race) for _ in range(4)]
[t.start() for t in _ts]
[t.join(timeout=20) for t in _ts]
check("4 luồng đồng thời -> không treo, cả 4 xong", len(_done) == 4)
check("4 luồng đồng thời -> mirror vẫn đúng", (_MIR2 / "references" / "chi-tiet.md").is_file())

# ---- dọn ----
for _d in (_ROOT, _R2):
    shutil.rmtree(_d, ignore_errors=True)

if _fails:
    print(f"\nFAIL - test_system_sync: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_system_sync: tất cả pass")
```

- [ ] **Step 2: Chạy test, xác nhận nó FAIL đúng chỗ**

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`

Expected: FAIL. Các dòng phải đỏ:
- `mirror có references/chi-tiet.md` - bản hiện tại chỉ copy file top-level.
- `mirror có scripts/chay.py` - cùng lý do.
- `đổi references/ (SKILL.md không đổi) -> mirror nhận bản mới`
- `đổi file phụ ngang hàng (SKILL.md không đổi) -> mirror nhận bản mới` - bug CÓ SẴN: cổng skip chỉ băm SKILL.md.
- `không đổi gì -> KHÔNG còn đọc-và-băm SKILL.md` - bản hiện tại đọc SKILL.md mỗi lần gọi.

Các dòng phải XANH ngay từ bây giờ (chốt bất biến, không được vỡ ở Task 2): `mirror có SKILL.md`, `KHÔNG mirror skill đã tắt`, `add-only: không xoá file lạ ở mirror`, `4 luồng đồng thời -> không treo`.

Dòng `không đổi gì -> KHÔNG copy lại lần nào` có thể XANH sẵn (bản cũ skip theo hash SKILL.md nên cũng không copy). Đó là bình thường - nó là lưới chặn regression cho Task 2, không phải để bắt lỗi hiện tại.

- [ ] **Step 3: Commit**

```bash
git add server/test_system_sync.py
git commit -m "test(sync): dung test_system_sync tu so 0 - chot hanh vi mirror_skills"
```

---

### Task 2: Cổng chữ ký stat + copy đệ quy + lock riêng

**Files:**
- Modify: `server/system_sync.py:39-47` (thêm `import os`), `:276-281` (thêm hằng số cạnh `_LOCK`), `:235-264` (viết lại `mirror_skills`)
- Test: `server/test_system_sync.py` (Task 1)

**Interfaces:**
- Produces: `system_sync._mirror_signature(canonical: Path) -> str` - chữ ký stat-only của cây, chuỗi rỗng nếu thư mục không tồn tại.
- `system_sync.mirror_skills(root) -> None` giữ NGUYÊN chữ ký công khai. 7 call site hiện có không đổi gì.

- [ ] **Step 1: Thêm `import os`**

`system_sync.py` hiện KHÔNG import `os` (đã kiểm). Trong khối import (dòng 39-47), thêm `import os` giữa `import json` và `import re` để giữ thứ tự bảng chữ cái:

```python
import hashlib
import json
import os
import re
import shutil
import sys
import threading
```

- [ ] **Step 2: Thêm hằng số + `_mirror_signature`**

Ngay TRƯỚC dòng `_LOCK = threading.Lock()` (hiện ở dòng 280), chèn:

```python
# ── Cổng chữ ký cho mirror_skills ──────────────────────────────────────────────
# mirror_skills bị gọi ở ĐƯỜNG NÓNG: build_system_prompt (main.py:184) chạy mỗi lượt chat
# dashboard, mỗi tin Telegram, mỗi task Kanban, mỗi vòng loop, mỗi nhắc hẹn, mỗi lần spawn
# learn. Bản cũ đọc + băm SKILL.md hai lần cho MỖI skill mỗi lần gọi: đo thật trên brain
# 27 skill là ~52ms MỖI LƯỢT, chặn thẳng event loop. Chữ ký chỉ dùng stat (không đọc byte
# nào) nên ~6ms, rẻ hơn 9 lần, và tiện thể phủ luôn thư mục con.
_MIRROR_SIG: dict = {}                    # root đã resolve -> chữ ký lần mirror gần nhất
_MIRROR_LOCKS: dict = {}                  # root đã resolve -> Lock riêng cho mirror
_MIRROR_LOCKS_GUARD = threading.Lock()    # chỉ bảo vệ việc TẠO lock trong _MIRROR_LOCKS


def _mirror_lock(key: str) -> threading.Lock:
    """Lock riêng theo root cho mirror. TUYỆT ĐỐI không phải _LOCK: mirror_skills bị gọi từ
    sync_brain KHI ĐANG giữ _LOCK, mà threading.Lock không reentrant nên lấy _LOCK ở đây là
    deadlock ngay lượt chat đầu. Lock này chỉ được lấy BÊN TRONG mirror_skills và không có
    lock nào khác bị lấy khi đang giữ nó -> không có chu trình -> không deadlock."""
    with _MIRROR_LOCKS_GUARD:
        lk = _MIRROR_LOCKS.get(key)
        if lk is None:
            lk = threading.Lock()
            _MIRROR_LOCKS[key] = lk
        return lk


def _mirror_signature(canonical: Path) -> str:
    """Chữ ký cây skill, cộng CHỈ bằng stat - KHÔNG đọc nội dung file nào.

    Gộp (đường dẫn tương đối dạng posix, st_mtime_ns, st_size) của MỌI file thành 1 sha256.
    Bỏ qua .disabled (skill đã tắt không được mirror). follow_symlinks=False ở cả is_dir lẫn
    stat: đĩa hiện không có symlink nào, nhưng rglob trên cây có symlink có thể lặp vô hạn.
    Trả chuỗi rỗng nếu thư mục không tồn tại. OSError trên 1 entry -> bỏ qua entry đó, không ném.
    """
    if not canonical.is_dir():
        return ""
    h = hashlib.sha256()
    stack = [canonical]
    rows = []
    while stack:
        d = stack.pop()
        try:
            # context manager BẮT BUỘC: os.scandir giữ file handle của thư mục cho tới khi
            # đóng. Trên Windows, handle hở làm thư mục không xoá/đổi tên được cho tới khi
            # GC dọn - đủ để phá test dùng tempfile và phá cả toggle skill (rmtree mirror).
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name != ".disabled":
                        stack.append(Path(e.path))
                    continue
                st = e.stat(follow_symlinks=False)
                rel = Path(e.path).relative_to(canonical).as_posix()
                rows.append(f"{rel}\x00{st.st_mtime_ns}\x00{st.st_size}")
            except OSError:
                continue
    for row in sorted(rows):   # sort để chữ ký không phụ thuộc thứ tự duyệt của OS
        h.update(row.encode("utf-8", "replace"))
        h.update(b"\x01")
    return h.hexdigest()
```

- [ ] **Step 3: Viết lại `mirror_skills`**

Thay TOÀN BỘ hàm `mirror_skills` (hiện ở dòng 235-264) bằng:

```python
def mirror_skills(root) -> None:
    """Mirror MỘT CHIỀU <root>/skills → <root>/.claude/skills (CHỈ skill đang BẬT), ĐỆ QUY
    cả references/ scripts/ templates/ - skill là PACKAGE, không phải một file.
    Mục đích: các ngữ cảnh Claude Code chạy cwd=brain (workflow/loop/learn/lint) vẫn nạp skill
    NATIVE như bonus. Add/update-only, BỎ QUA .disabled (mirror skill đã tắt = vô tình bật lại
    native). KHÔNG xoá entry lạ ở .claude (việc gỡ mirror khi tắt/xoá skill do endpoint xử lý).
    Đây là bản phái sinh - hỏng cũng không phá router chính.

    ĐƯỜNG NÓNG: gọi mỗi lượt chat qua build_system_prompt. Tầng 1 là cổng chữ ký stat-only
    (~6ms) - 99% lượt thoát ở đây. Tầng 2 (copy thật) chỉ chạy khi cây nguồn ĐỔI.

    BIẾT TRƯỚC: chữ ký tính trên NGUỒN và cache nằm trong bộ nhớ, nên bản mirror bị phá từ
    BÊN NGOÀI mà nguồn không đổi sẽ không tự lành cho tới khi khởi động lại tiến trình. Đánh
    đổi có chủ đích (xem spec 2026-07-17-mirror-skills-tree-design.md). Tắt skill thì nguồn
    dời sang .disabled nên chữ ký đổi -> vẫn phủ."""
    root = Path(root)
    canonical = root / "skills"
    mirror = root / ".claude" / "skills"
    if not canonical.is_dir():
        return
    try:
        key = str(root.resolve())
    except OSError:
        key = str(root)
    try:
        sig = _mirror_signature(canonical)
        if sig and _MIRROR_SIG.get(key) == sig:
            return   # TẦNG 1: cây nguồn không đổi -> khỏi làm gì (đường 99% lượt chat)
        lk = _mirror_lock(key)
        if not lk.acquire(blocking=False):
            return   # luồng khác đang mirror đúng root này -> nó làm rồi, khỏi xếp hàng
        try:
            for d in sorted(p for p in canonical.iterdir()
                            if p.is_dir() and p.name != ".disabled" and (p / "SKILL.md").is_file()):
                try:
                    dst_dir = mirror / d.name
                    rels = sorted(p.relative_to(d).as_posix()
                                  for p in d.rglob("*") if p.is_file())
                    for rel in rels:
                        dst_f = dst_dir / rel
                        dst_f.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(d / rel), str(dst_f))
                except Exception as e:
                    print(f"[skill mirror] {d.name}: {type(e).__name__}: {e}", file=sys.stderr)
            # Ghi cache SAU khi copy xong. Copy có thể đổi mtime ở đích chứ không đổi nguồn,
            # nên tính lại chữ ký nguồn cho chắc (rẻ) thay vì tin sig cũ.
            _MIRROR_SIG[key] = _mirror_signature(canonical)
        finally:
            lk.release()
    except Exception as e:
        print(f"[skill mirror] {root}: {type(e).__name__}: {e}", file=sys.stderr)
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`
Expected: PASS, in `OK - test_system_sync: tất cả pass`.

- [ ] **Step 5: Chứng minh cổng chữ ký thật sự bite (mutation)**

Tạm bỏ tầng 1 bằng cách comment hai dòng:

```python
        # if sig and _MIRROR_SIG.get(key) == sig:
        #     return
```

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`
Expected: FAIL ở `không đổi gì -> KHÔNG copy lại lần nào` và `không đổi gì -> KHÔNG đọc nội dung file nào`.

**Khôi phục nguyên trạng** rồi chạy lại, xác nhận xanh. Xác nhận `git diff server/system_sync.py` chỉ còn thay đổi có chủ đích.

- [ ] **Step 6: Chạy toàn bộ suite**

Run: `cd server && st=0; for f in test_*.py; do ../.venv/Scripts/python.exe "$f" >/dev/null 2>&1 || { echo "FAIL: $f"; st=1; }; done; echo "EXIT=$st"`
Expected: `EXIT=0`. Đặc biệt để mắt `test_skill_caps.py` (nó gọi `system_sync.system_skill_slugs`) và `test_skill_usage.py`.

- [ ] **Step 7: Commit**

```bash
git add server/system_sync.py
git commit -m "perf(sync): cong chu ky stat + mirror de quy - 52ms/luot xuong ~6ms"
```

---

### Task 3: Đo lại trên brain thật + bump 0.9.64

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `system_sync.mirror_skills`, `system_sync._mirror_signature` (Task 2).

- [ ] **Step 1: Đo lại trên brain thật**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys, time
from pathlib import Path
sys.path.insert(0, '.')
import system_sync
for r in ['../brains/My Bullet Journal', '../brains/Brain Default', '../brains/Ngọc Thu Phạm']:
    if not Path(r).is_dir(): continue
    system_sync.mirror_skills(r)          # lam am cache + mirror
    t0 = time.perf_counter()
    for _ in range(5): system_sync.mirror_skills(r)
    print(f'{Path(r).name:22} {(time.perf_counter()-t0)/5*1000:6.2f} ms/luot')
"
```
Expected: mỗi brain dưới ~10ms. Số nền trước khi làm plan này: My Bullet Journal 52,48ms, Ngọc Thu Phạm 44,23ms, Brain Default 11,62ms.

- [ ] **Step 2: Xác nhận references/ tới được brain thật**

Run:
```bash
cd "D:/Project/Javis-OS" && ./.venv/Scripts/python.exe -c "
from pathlib import Path
n = 0
for b in Path('brains').iterdir():
    src = b / 'skills'
    if not src.is_dir(): continue
    for d in src.iterdir():
        if not (d / 'references').is_dir(): continue
        mir = b / '.claude' / 'skills' / d.name / 'references'
        n += 1
        print(('OK  ' if mir.is_dir() else 'THIEU'), b.name, '/', d.name)
print('skill co references/:', n)
"
```
Expected: mọi dòng `OK`. Trước khi làm plan này, mọi dòng sẽ là `THIEU`.

Lưu ý: bước này ghi vào `brains/` thật, nhưng `brains/` đã bị gitignore ở repo gốc (`.gitignore:51`) nên không lọt vào commit.

- [ ] **Step 3: Bump VERSION**

`VERSION` hiện là `0.9.63`. Ghi `0.9.64`:

```bash
echo "0.9.64" > VERSION
```

- [ ] **Step 4: Viết CHANGELOG**

Thêm khối này vào `CHANGELOG.md`, NGAY TRƯỚC dòng `## [0.9.63] - 2026-07-17`:

```markdown
## [0.9.64] - 2026-07-17
### Sửa lỗi
- **Jarvis 007 tốn ~52ms mỗi lượt chat chỉ để đồng bộ skill, và nó chặn cả tiến trình**: hàm mirror skill đọc và băm lại `SKILL.md` của MỌI skill (cả bản nguồn lẫn bản đích) mỗi lần dựng system prompt, tức mỗi lượt chat, mỗi tin Telegram, mỗi task Kanban, mỗi vòng loop, mỗi nhắc hẹn. Đo thật trên brain 27 skill: 52,48ms mỗi lượt, chạy đồng bộ trên event loop nên làm đứng luôn các kết nối khác. Nay thay bằng cổng chữ ký chỉ dùng `stat` (không đọc nội dung file nào): còn khoảng 6ms, tức nhanh hơn 9 lần, và chỉ copy thật khi cây skill có thay đổi. Lỗi có sẵn, không ai biết cho tới khi đo.
- **File phụ trong skill đổi nội dung mà bản mirror không bao giờ nhận**: cổng bỏ qua chỉ băm `SKILL.md`, nên sửa một file ảnh hay tài liệu ngang hàng trong thư mục skill thì bản Claude Code nạp native vẫn giữ bản cũ mãi. Chữ ký mới phủ mọi file nên hết lỗi này.
### Thêm mới
- **Skill mang theo được `references/` và `scripts/`**: bản mirror sang `.claude/skills` nay copy cả cây con, nên skill có tài liệu tách riêng hay script đi kèm chạy được cả trên đường Claude Code nạp native, không chỉ đường router. 10 skill trong các brain hiện có đã dùng `references/` từ trước và tới giờ vẫn chưa tới được đường native.
### Đã biết, chưa sửa
- **Skill hệ thống vẫn chưa ship được cây con**: `html-to-webcake` ship kèm `tools/` và `examples/` nhưng cơ chế cài skill hệ thống chỉ chuyển mỗi `SKILL.md`, nên cây con chưa bao giờ tới brain nào. Bản này KHÔNG sửa lỗi đó: nó nằm ở tầng cài đặt, phía trên tầng mirror.
- **Bản mirror bị phá từ bên ngoài sẽ không tự lành cho tới khi khởi động lại**: cổng chữ ký tính trên cây nguồn và nhớ trong bộ nhớ, nên nếu ai đó xoá tay file trong `.claude/skills` mà không đụng vào skill gốc thì Jarvis 007 sẽ không nhận ra. Đánh đổi có chủ đích để lấy tốc độ; tắt/bật skill hay khởi động lại đều đưa nó về đúng.
```

- [ ] **Step 5: Kiểm em dash**

Run: `cd "D:/Project/Javis-OS" && ./.venv/Scripts/python.exe -c "import pathlib; print('em dash:', pathlib.Path('CHANGELOG.md').read_text(encoding='utf-8').count(chr(8212)))"`
Expected: `em dash: 0`

- [ ] **Step 6: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: 0.9.64 - mirror skill de quy + cat 52ms/luot xuong ~6ms"
git push origin main
```

---

## Ghi chú cho người thực thi

**Thứ tự phụ thuộc:** Task 1 -> Task 2 -> Task 3. Tuyến tính, không chen được.

**Chỗ dễ chết nhất là `_LOCK`.** `mirror_skills` bị gọi từ `sync_brain:356` KHI ĐANG giữ `_LOCK` (`system_sync.py:280`, không reentrant). Lấy `_LOCK` bên trong `mirror_skills` là deadlock ngay lượt chat đầu tiên, và test sẽ treo chứ không báo lỗi rõ ràng. Lock của mirror PHẢI là object khác.

**`mirror_skills` được gọi ở đúng 7 chỗ** (đã grep lại tại thời điểm viết plan này, KHÔNG bê số cũ):

- `main.py:185` - **đường nóng THẬT**, trong `build_system_prompt`, chạy mỗi lượt chat.
- `main.py:2213`, `:2268`, `:2310`, `:2684`, `:2736` - endpoint do người bấm (toggle, save, group, import, workflow).
- `system_sync.py:356` - trong `sync_brain`, chạy KHI ĐANG giữ `_LOCK`.

Lưu ý `system_sync.py:200` cũng khớp khi grep nhưng đó là **docstring**, không phải lời gọi.

⚠ Số dòng trong `main.py` TRÔI NHANH. Bản đồ rủi ro viết hôm 2026-07-16 ghi `184/2186/2241/2283/2657/2709`; tất cả đã lệch vì chính các commit của đợt A+B thêm dòng vào `main.py` (Task 10 thêm ~23 dòng, Task 6 thêm 6). Nếu bạn đọc plan này sau khi có thêm commit chạm `main.py`, **grep lại thay vì tin số ở trên**. Định vị theo NỘI DUNG, đừng theo số dòng.

**Không đụng `skill_hash`.** Nó vẫn được `sync_brain`, `LEGACY_HASHES` và CLI `--hash` dùng. Ta chỉ thôi dùng nó trong `mirror_skills`.

**Không mở rộng phạm vi.** `_system_items` (để skill hệ thống ship cây con, tức vá `html-to-webcake`) CỐ Ý nằm ngoài. Thấy chỗ đáng làm thì ghi lại, đừng làm.
