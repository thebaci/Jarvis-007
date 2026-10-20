# Media là vùng cache - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coi `attachments/` và `inbox/` của mỗi brain là vùng cache: không lên git, tự hết hạn sau 30 ngày hoặc khi vượt trần 300MB, và chỗ ảnh đã mất hiện ô xám "Ảnh đã hết hạn" thay cho icon vỡ.

**Architecture:** Một module mới `server/media_gc.py` tách phần quyết định (hàm thuần `plan_deletions`, test không chạm đĩa) khỏi phần chạm đĩa (`scan` + `sweep`, dùng `os.scandir`). Scheduler nền gọi `sweep` qua `asyncio.to_thread` mỗi 6 tiếng. `server/git_brain.py` thêm dòng gitignore và một bước gỡ index chạy một lần cho brain cũ. Dashboard bắt sự kiện `error` của `<img>` để thay bằng ô xám.

**Tech Stack:** Python stdlib (os.scandir, subprocess/git), FastAPI (scheduler có sẵn), JavaScript thuần (dashboard không có framework).

Spec: [docs/superpowers/specs/2026-07-29-media-cache-retention-design.md](../specs/2026-07-29-media-cache-retention-design.md)

## Global Constraints

- **Tuyệt đối không dùng ký tự em dash (U+2014)** trong bất kỳ file nào: code, comment, docstring, CHANGELOG, commit message. Dùng dấu gạch nối `-`.
- **Chuỗi hiển thị cho user phải là tiếng Việt CÓ DẤU**, kể cả khi viết trong code backend. Đã mắc lỗi này hai lần trước (`file-editor.js`, `usage_index.py`). Chuỗi duy nhất user thấy trong plan này là **"Ảnh đã hết hạn"**.
- Comment trong `dashboard/chat-render.js` và `dashboard/style.css` viết KHÔNG dấu, theo đúng style đang có của hai file đó. Chỉ chuỗi hiển thị mới cần dấu.
- Test chạy bằng `.venv` của dự án: luôn gọi `python tests/run.py <tên>` (script tự tìm `.venv`), KHÔNG gọi `python tests/python/test_x.py` bằng python hệ thống (thiếu fastapi/yaml).
- Quét đĩa phải dùng `os.scandir`, không dùng `glob`. `glob(...)[:N]` đi hết cây rồi mới cắt nên không phải trần thật; và quét đồng bộ trong event loop từng làm container unhealthy tới mức Traefik gỡ route.
- Giá trị mặc định chốt cứng: `max_age_days = 30`, `max_mb = 300`, `enabled = true`.
- Không viết code đẩy Google Drive trong plan này. Không viết lại lịch sử git của brain.

---

### Task 1: `plan_deletions` - phần quyết định, hàm thuần

**Files:**
- Create: `server/media_gc.py`
- Test: `tests/python/test_media_gc.py`

**Interfaces:**
- Consumes: không có (task đầu tiên).
- Produces: `media_gc.plan_deletions(entries, now, max_age_days, max_mb) -> list[str]`.
  `entries` là `list[tuple[str, int, float]]` gồm `(path, size_bytes, mtime)`.
  `now` là `float` (giây epoch). `max_age_days` và `max_mb` là `int`.
  Trả về list `path` theo đúng thứ tự xoá.

- [ ] **Step 1: Viết test đỏ**

Tạo `tests/python/test_media_gc.py`:

```python
"""Test media_gc (dọn media quá hạn trong vùng cache của brain). Chạy tay / CI:

    python tests/run.py media_gc

plan_deletions là hàm THUẦN nên phần lớn test không chạm đĩa; phần quét/xoá dùng thư mục tạm.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path
import sys

import media_gc   # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


NOW = 1_800_000_000.0
DAY = 86400.0
MB = 1024 * 1024


def muc(path, mb, tuoi_ngay):
    """Một mục (path, size, mtime) với mtime cách NOW đúng tuoi_ngay ngày."""
    return (path, int(mb * MB), NOW - tuoi_ngay * DAY)


# ---- 1. Còn mới và tổng dưới trần: không xoá gì ----
r = media_gc.plan_deletions([muc("a.png", 1, 1), muc("b.png", 2, 5)], NOW, 30, 300)
check("moi + duoi tran -> khong xoa gi", r == [])

# ---- 2. Quá hạn tuổi thì xoá, trong hạn thì giữ ----
r = media_gc.plan_deletions([muc("cu.png", 1, 40), muc("moi.png", 1, 5)], NOW, 30, 300)
check("qua han tuoi -> chi xoa file cu", r == ["cu.png"])

# ---- 3. Vượt trần dù mọi file còn trong hạn: xoá từ cũ tới mới, dừng đúng lúc ----
r = media_gc.plan_deletions(
    [muc("x3.png", 200, 3), muc("x2.png", 200, 2), muc("x1.png", 200, 1)], NOW, 30, 300)
check("vuot tran -> xoa cu truoc, dung khi du", r == ["x3.png", "x2.png"])

# ---- 4. Vừa quá hạn vừa vượt trần: cộng dồn, không đếm trùng ----
r = media_gc.plan_deletions(
    [muc("cu.png", 10, 40), muc("y2.png", 200, 3), muc("y1.png", 200, 1)], NOW, 30, 300)
check("qua han + vuot tran -> cong don, khong trung",
      r == ["cu.png", "y2.png"] and len(r) == len(set(r)))

# ---- 5. File .md không bao giờ bị xoá ----
r = media_gc.plan_deletions([muc("ghi-chu.md", 400, 99), muc("anh.png", 1, 40)], NOW, 30, 300)
check("chua file .md", r == ["anh.png"])

# ---- 6. Tắt từng luật bằng 0 / số âm ----
check("max_age_days=0 -> tat luat tuoi",
      media_gc.plan_deletions([muc("cu.png", 1, 999)], NOW, 0, 300) == [])
check("max_mb=0 -> tat luat tran",
      media_gc.plan_deletions([muc("to.png", 999, 1)], NOW, 30, 0) == [])
check("tat ca hai -> khong xoa gi",
      media_gc.plan_deletions([muc("cu-va-to.png", 999, 999)], NOW, -1, -1) == [])

# ---- 7. Danh sách rỗng ----
check("danh sach rong", media_gc.plan_deletions([], NOW, 30, 300) == [])

print()
if _fails:
    print(f"{len(_fails)} test ĐỎ: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả test media_gc xanh.")
```

- [ ] **Step 2: Chạy test cho chắc là nó đỏ**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: ĐỎ với `ModuleNotFoundError: No module named 'media_gc'`.

- [ ] **Step 3: Viết `server/media_gc.py` vừa đủ cho test xanh**

```python
"""
media_gc.py - Dọn vùng cache media của brain.

Vì sao tồn tại: ảnh Jarvis 007 tự tạo (image_gen.py:202) và file user gửi qua Telegram
(main.py:6242) rơi vào `<brain>/attachments/` và `<brain>/inbox/` rồi nằm đó vĩnh viễn.
Không ai dọn, mà trước đây chúng còn được commit vào git của brain nên xoá file cũng
không lấy lại được dung lượng. Quyết định: hai thư mục đó là VÙNG CACHE, không phải tri
thức. Tri thức là file .md. Cái gì trong đó cũng có thể biến mất mà brain vẫn nguyên vẹn.

Tách làm hai tầng để test được:
  - plan_deletions: THUẦN. Nhận sẵn danh sách (path, size, mtime), trả danh sách cần xoá.
    Không chạm đĩa, không đọc đồng hồ -> test không cần fixture.
  - scan / media_dirs / sweep: chạm đĩa. Dùng os.scandir và phải gọi qua asyncio.to_thread.

Stdlib-only.
"""
from __future__ import annotations

import os
import re
import time


def plan_deletions(entries, now, max_age_days, max_mb):
    """Quyết định file nào phải xoá. HÀM THUẦN.

    entries      : list[(path, size_bytes, mtime)] - mọi file trong vùng cache của MỘT brain.
    now          : mốc thời gian tham chiếu (time.time()).
    max_age_days : file già hơn ngần này ngày thì xoá. <= 0 = tắt luật tuổi.
    max_mb       : trần dung lượng vùng cache. <= 0 = tắt luật trần.

    Trả list path theo ĐÚNG thứ tự xoá: nhóm quá hạn trước, rồi nhóm bị trần cắt (cũ tới mới).

    File .md không bao giờ bị xoá: vùng cache có thể lạc note vào, mà note là tri thức.
    """
    giu = [t for t in entries if not str(t[0]).lower().endswith(".md")]
    xoa, con_lai = [], []
    if max_age_days and max_age_days > 0:
        han = now - max_age_days * 86400.0
        for t in giu:
            (xoa if t[2] < han else con_lai).append(t)
    else:
        con_lai = list(giu)
    if max_mb and max_mb > 0:
        tran = max_mb * 1024 * 1024
        tong = sum(t[1] for t in con_lai)
        # Trần là van an toàn cho trường hợp sinh cả trăm ảnh trong một ngày: lúc đó
        # luật tuổi chưa kịp cứu. Xoá từ CŨ NHẤT và dừng ngay khi xuống dưới trần.
        for t in sorted(con_lai, key=lambda x: x[2]):
            if tong <= tran:
                break
            xoa.append(t)
            tong -= t[1]
    return [t[0] for t in xoa]
```

- [ ] **Step 4: Chạy test cho xanh**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: `1/1 xanh`, và output có đủ 9 dòng `ok`.

- [ ] **Step 5: Commit**

```bash
git add server/media_gc.py tests/python/test_media_gc.py
git commit -m "media_gc: hàm thuần plan_deletions (hạn tuổi + trần dung lượng)"
```

---

### Task 2: Quét đĩa và xoá thật + mặc định cấu hình

**Files:**
- Modify: `server/media_gc.py` (thêm `media_dirs`, `scan`, `sweep` sau `plan_deletions`)
- Modify: `server/config.py:83` (thêm khoá `media` vào `_DEFAULT`, ngay sau khoá `image`)
- Test: `tests/python/test_media_gc.py` (nối thêm phần 8 vào cuối, TRƯỚC khối `print()` tổng kết)

**Interfaces:**
- Consumes: `media_gc.plan_deletions` từ Task 1.
- Produces:
  - `media_gc.media_dirs(brain_root: str) -> list[str]` - đường dẫn tuyệt đối các thư mục vùng cache cấp 1.
  - `media_gc.scan(dirs: list[str]) -> list[tuple[str, int, float]]`.
  - `media_gc.sweep(brain_root: str, max_age_days: int = 30, max_mb: int = 300, now: float | None = None) -> dict` trả `{"files": int, "bytes": int}`.
  - `config._DEFAULT["media"] == {"enabled": True, "max_age_days": 30, "max_mb": 300}`.

- [ ] **Step 1: Viết test đỏ**

Chèn vào `tests/python/test_media_gc.py` NGAY TRƯỚC dòng `print()` ở khối tổng kết cuối file:

```python
# ---- 8. Quét đĩa + xoá thật (thư mục tạm) ----
import os        # noqa: E402
import tempfile  # noqa: E402

import config    # noqa: E402

_brain = tempfile.mkdtemp(prefix="javis-mediagc-")


def _tao(rel, mb, tuoi_ngay):
    """Tạo file thật với dung lượng và mtime mong muốn."""
    p = os.path.join(_brain, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\0" * int(mb * MB))
    t = time.time() - tuoi_ngay * DAY
    os.utime(p, (t, t))
    return p


_cu = _tao("05 - attachments/cu.png", 0.001, 40)          # biến thể tên có số thứ tự
_moi = _tao("05 - attachments/moi.png", 0.001, 1)
_note = _tao("05 - attachments/ghi-chu.md", 0.001, 999)
_tg = _tao("inbox/telegram/photo_1.jpg", 0.001, 40)
_wiki = _tao("Wiki/khai-niem.md", 0.001, 999)             # ngoài vùng cache -> không được đụng

d = media_gc.media_dirs(_brain)
check("media_dirs bat dung 2 thu muc", len(d) == 2 and any("attachments" in x for x in d)
      and any(x.endswith("inbox") for x in d))
check("media_dirs bo qua thu muc khac", not any("Wiki" in x for x in d))

check("scan duyet de quy", len(media_gc.scan(d)) == 4)

kq = media_gc.sweep(_brain, max_age_days=30, max_mb=300)
check("sweep xoa dung so file", kq["files"] == 2)
check("sweep tra so byte da don", kq["bytes"] > 0)
check("sweep xoa file qua han", not os.path.exists(_cu) and not os.path.exists(_tg))
check("sweep giu file moi", os.path.exists(_moi))
check("sweep giu file .md trong vung cache", os.path.exists(_note))
check("sweep khong dung file ngoai vung cache", os.path.exists(_wiki))

kq2 = media_gc.sweep(_brain, max_age_days=30, max_mb=300)
check("sweep chay lai khong xoa them", kq2["files"] == 0)

check("sweep brain khong ton tai khong no",
      media_gc.sweep(os.path.join(_brain, "khong-co-that")) == {"files": 0, "bytes": 0})

# ---- 9. Mặc định cấu hình ----
_m = config._DEFAULT.get("media") or {}
check("config mac dinh media.enabled", _m.get("enabled") is True)
check("config mac dinh 30 ngay", _m.get("max_age_days") == 30)
check("config mac dinh tran 300MB", _m.get("max_mb") == 300)
```

Thêm `import time` vào khối import ở ĐẦU file (cạnh `import sys`).

- [ ] **Step 2: Chạy test cho chắc là nó đỏ**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: ĐỎ với `AttributeError: module 'media_gc' has no attribute 'media_dirs'`.

- [ ] **Step 3: Thêm phần chạm đĩa vào `server/media_gc.py`**

Nối vào cuối file, sau `plan_deletions`:

```python
# Cùng luật nhận diện thư mục attachments với image_gen.py:40 và main.py:1931: tên có thể là
# "attachments", "Attachments", hay có tiền tố số thứ tự kiểu "05 - attachments".
_ATTACH_RE = r"^(\d+\s*[-_.]\s*)?attachments$"


def media_dirs(brain_root):
    """Các thư mục VÙNG CACHE cấp 1 của brain: attachments (mọi biến thể tên) + inbox."""
    ra = []
    try:
        with os.scandir(brain_root) as it:
            for d in it:
                try:
                    if not d.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                ten = d.name.strip()
                if ten.lower() == "inbox" or re.match(_ATTACH_RE, ten, re.IGNORECASE):
                    ra.append(d.path)
    except OSError:
        pass
    return ra


def scan(dirs):
    """Duyệt đệ quy các thư mục -> list[(path, size, mtime)].

    Dùng os.scandir chứ KHÔNG dùng glob: glob đi hết cây rồi mới cắt nên không có trần thật,
    và stat đi kèm entry của scandir thì rẻ hơn hẳn stat riêng từng file. Lỗi từng file
    (đang bị khoá, vừa bị xoá, thiếu quyền) thì bỏ qua chứ không làm hỏng cả lượt quét.
    """
    ra = []
    for d in dirs:
        stack = [d]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for x in it:
                        try:
                            if x.is_dir(follow_symlinks=False):
                                stack.append(x.path)
                            elif x.is_file(follow_symlinks=False):
                                st = x.stat()
                                ra.append((x.path, st.st_size, st.st_mtime))
                        except OSError:
                            continue
            except OSError:
                continue
    return ra


def sweep(brain_root, max_age_days=30, max_mb=300, now=None):
    """Dọn vùng cache của MỘT brain. CHẶN vì đụng đĩa - phải gọi qua asyncio.to_thread.

    Trả {"files": số file đã xoá, "bytes": tổng byte đã giải phóng}.
    """
    entries = scan(media_dirs(brain_root))
    co = {t[0]: t[1] for t in entries}
    can_xoa = plan_deletions(entries, float(now if now is not None else time.time()),
                             max_age_days, max_mb)
    n, b = 0, 0
    for p in can_xoa:
        try:
            os.remove(p)
        except OSError:
            continue      # file vừa bị xoá tay hoặc đang bị khoá -> lần sau dọn
        n += 1
        b += co.get(p, 0)
    return {"files": n, "bytes": b}
```

- [ ] **Step 4: Thêm mặc định vào `server/config.py`**

Chèn NGAY SAU dòng `"image": {"strip_c2pa": False},` (hiện là dòng 83):

```python
    # Vùng cache media của brain: attachments/ + inbox/. Ảnh là NGUYÊN LIỆU đi qua, không
    # phải tri thức - đọc xong rút thành .md là đủ dùng, nên chúng tự hết hạn thay vì nằm
    # mãi làm phình đĩa VPS. Muốn giữ ảnh lâu dài thì đấu kho ngoài (Drive), đừng để Jarvis 007 ôm.
    # max_age_days / max_mb <= 0 = tắt luật tương ứng. enabled=False = không dọn gì cả.
    "media": {"enabled": True, "max_age_days": 30, "max_mb": 300},
```

- [ ] **Step 5: Chạy test cho xanh**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: `1/1 xanh`, có đủ các dòng `ok` của mục 8 và 9.

- [ ] **Step 6: Commit**

```bash
git add server/media_gc.py server/config.py tests/python/test_media_gc.py
git commit -m "media_gc: quét scandir + xoá thật + mặc định 30 ngày/300MB"
```

---

### Task 3: Móc janitor vào scheduler nền

**Files:**
- Modify: `server/main.py` (import `media_gc`; thêm biến mốc; thêm mục 6 vào `_scheduler_loop` tại `server/main.py:4261-4266`)

**Interfaces:**
- Consumes: `media_gc.sweep(brain_root, max_age_days, max_mb)` từ Task 2; `config._DEFAULT["media"]` từ Task 2.
- Produces: không có API mới. Hiệu ứng: mỗi 6 tiếng, mọi brain trong `loop_feature.scheduler_brains()` được dọn vùng cache.

- [ ] **Step 1: Thêm import**

Tìm khối import module server ở đầu `server/main.py` (chỗ đã có `import image_gen`) và thêm cạnh nó:

```python
import media_gc
```

- [ ] **Step 2: Thêm biến mốc thời gian**

Đặt ngay TRƯỚC dòng `async def _start_scheduler():` (hiện là `server/main.py:4173`):

```python
# Mốc lần dọn media gần nhất. Dùng list 1 phần tử để hàm lồng bên trong _scheduler_loop
# gán được mà không cần `global`. Khởi tạo 0.0 -> chạy ngay ở tick đầu sau khi server lên.
_MEDIA_GC_LAST = [0.0]
```

- [ ] **Step 3: Thêm mục 6 vào vòng lặp**

Chèn NGAY SAU khối `# 5) Jarvis 007 index` (kết thúc ở `server/main.py:4266`), vẫn nằm trong `try` ngoài cùng của vòng lặp:

```python
                # 6) Dọn media quá hạn: attachments/ + inbox/ là VÙNG CACHE chứ không phải
                #    tri thức. Nhịp riêng 6 TIẾNG (không theo nhịp 30s của vòng lặp) vì đây là
                #    quét đĩa, và to_thread vì quét đồng bộ trong event loop từng làm container
                #    unhealthy tới mức Traefik gỡ route. Đặt mốc TRƯỚC khi chạy: lỡ có hỏng thì
                #    đợi lượt sau chứ không quay vòng nóng.
                try:
                    if time.time() - _MEDIA_GC_LAST[0] >= 6 * 3600:
                        _MEDIA_GC_LAST[0] = time.time()
                        mcfg = cfgmod.read_settings().get("media", {}) or {}
                        if mcfg.get("enabled", True):
                            tuoi = int(mcfg.get("max_age_days", 30))
                            tran = int(mcfg.get("max_mb", 300))
                            for _mb in loop_feature.scheduler_brains():
                                kq = await asyncio.to_thread(media_gc.sweep, _mb, tuoi, tran)
                                if kq.get("files"):
                                    print(f"[media gc] {_mb}: dọn {kq['files']} tệp, "
                                          f"{kq['bytes'] // (1024 * 1024)}MB")
                except Exception as me:
                    print(f"[media gc] {type(me).__name__}: {me}", file=__import__('sys').stderr)
```

- [ ] **Step 4: Kiểm tra cú pháp và server khởi động được**

```bash
python -c "import ast,sys; ast.parse(open('server/main.py',encoding='utf-8').read()); print('cú pháp ok')"
```

Kỳ vọng: in `cú pháp ok`.

Rồi chạy toàn bộ test Python để chắc không vỡ gì:

```bash
python tests/run.py --py
```

Kỳ vọng: tất cả xanh (số test bằng lúc trước cộng 1).

- [ ] **Step 5: Commit**

```bash
git add server/main.py
git commit -m "Scheduler: dọn vùng cache media mỗi 6 tiếng qua to_thread"
```

---

### Task 4: Chặn git - gitignore + gỡ index một lần

**Files:**
- Modify: `server/git_brain.py:19-27` (thêm `import re`)
- Modify: `server/git_brain.py:63-74` (thêm dòng vào `_GITIGNORE`)
- Modify: `server/git_brain.py` (thêm hàm `untrack_media` sau `_ensure_gitignore_lines`)
- Modify: `server/git_brain.py:133-148` (gọi `untrack_media` trong nhánh brain cũ của `ensure_git_repo`)
- Test: `tests/python/test_media_gc.py` (nối thêm phần 10)

**Interfaces:**
- Consumes: không có từ task trước.
- Produces: `git_brain.untrack_media(root: str) -> int` trả số thư mục đã gỡ khỏi index.

- [ ] **Step 1: Viết test đỏ**

Chèn vào `tests/python/test_media_gc.py` NGAY TRƯỚC khối `print()` tổng kết:

```python
# ---- 10. Gitignore + gỡ index ----
import subprocess   # noqa: E402

import git_brain    # noqa: E402

for _dong in ("attachments/", "Attachments/", "*attachments/", "*Attachments/", "inbox/"):
    check(f"gitignore co dong {_dong}", _dong + "\n" in git_brain._GITIGNORE)

if git_brain.has_git():
    _repo = tempfile.mkdtemp(prefix="javis-mediagit-")

    def _g(*a):
        return subprocess.run(["git", "-C", _repo, *a], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    _g("init")
    _g("config", "user.email", "t@t"); _g("config", "user.name", "T")
    os.makedirs(os.path.join(_repo, "attachments"), exist_ok=True)
    os.makedirs(os.path.join(_repo, "inbox", "telegram"), exist_ok=True)
    os.makedirs(os.path.join(_repo, "Wiki"), exist_ok=True)
    for _p, _noi_dung in ((("attachments", "a.png"), b"x"),
                          (("inbox", "telegram", "b.jpg"), b"x"),
                          (("Wiki", "note.md"), b"x")):
        with open(os.path.join(_repo, *_p), "wb") as _f:
            _f.write(_noi_dung)
    _g("add", "-A"); _g("commit", "-m", "seed")

    _truoc = (_g("ls-files").stdout or "")
    check("seed co theo doi media", "attachments/a.png" in _truoc)

    n = git_brain.untrack_media(_repo)
    _sau = (_g("ls-files").stdout or "")
    check("untrack_media go attachments", "attachments/a.png" not in _sau)
    check("untrack_media go inbox", "inbox/telegram/b.jpg" not in _sau)
    check("untrack_media khong dung file khac", "Wiki/note.md" in _sau)
    check("untrack_media giu file tren dia",
          os.path.exists(os.path.join(_repo, "attachments", "a.png")))
    check("untrack_media dem dung so thu muc", n == 2)

    _g("commit", "-m", "untrack")
    check("untrack_media chay lai khong lam gi", git_brain.untrack_media(_repo) == 0)

    # Brain cũ đã có .gitignore riêng: merge thêm dòng mới, KHÔNG mất dòng user tự đặt.
    with open(os.path.join(_repo, ".gitignore"), "w", encoding="utf-8") as _f:
        _f.write("# luat rieng cua user\nrac-cua-toi/\n")
    git_brain._ensure_gitignore_lines(_repo)
    with open(os.path.join(_repo, ".gitignore"), encoding="utf-8") as _f:
        _gi = _f.read()
    check("merge gitignore giu dong cu", "rac-cua-toi/" in _gi)
    check("merge gitignore them dong media", "attachments/" in _gi and "inbox/" in _gi)
else:
    print("BỎ QUA test git: máy không có git trong PATH")
```

- [ ] **Step 2: Chạy test cho chắc là nó đỏ**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: ĐỎ ở các dòng `gitignore co dong ...` và `AttributeError: ... 'untrack_media'`.

- [ ] **Step 3: Thêm `import re` vào `server/git_brain.py`**

Trong khối import (dòng 21-27), thêm `re` giữ đúng thứ tự bảng chữ cái:

```python
import json
import os
import re
import shutil
import subprocess
import time
```

- [ ] **Step 4: Thêm dòng vào `_GITIGNORE`**

Sửa hằng `_GITIGNORE` (dòng 63-74) thành:

```python
_GITIGNORE = (
    "# Jarvis 007 brain - KHÔNG commit: khoá, log thô (có thể chứa secret), nhật ký nền.\n"
    "# Git chỉ version TRI THỨC ĐÃ CHƯNG CẤT (facts/wiki/skills/MEMORY.md) → undo sạch, an toàn.\n"
    ".javis-learn.lock\n"
    "Javis/learn-staging/\n"
    "Javis/learn-log/\n"
    "Javis/loop-log/\n"
    "Javis/skill-usage.json\n"
    "memory/conversations/\n"
    "Memory/conversations/\n"
    "*.tmp\n"
    "# Vùng cache media: ảnh sinh ra + file user gửi lên. Là NGUYÊN LIỆU đi qua, không phải\n"
    "# tri thức, và media_gc.py tự dọn theo hạn. Nếu commit thì mỗi tấm ảnh là một blob nằm\n"
    "# vĩnh viễn trong lịch sử git - xoá file về sau cũng không lấy lại được dung lượng.\n"
    "# Bốn dòng attachments vì tên thư mục có thể là attachments / Attachments / 05 - attachments\n"
    "# (git phân biệt hoa thường trên Linux, còn dấu * phủ mọi tiền tố số thứ tự).\n"
    "attachments/\n"
    "Attachments/\n"
    "*attachments/\n"
    "*Attachments/\n"
    "inbox/\n"
)
```

- [ ] **Step 5: Thêm hàm `untrack_media`**

Chèn ngay sau hàm `_ensure_gitignore_lines` (kết thúc quanh dòng 104), trước `def ensure_git_repo`:

```python
# Cùng luật nhận diện thư mục attachments với media_gc.py và image_gen.py:40.
_ATTACH_RE = r"^(\d+\s*[-_.]\s*)?attachments$"


def untrack_media(root: str) -> int:
    """Gỡ attachments/ + inbox/ khỏi INDEX git, GIỮ NGUYÊN file trên đĩa.

    Vì sao cần: .gitignore không có tác dụng với file git ĐÃ theo dõi từ trước, nên brain cũ
    (đã lỡ commit ảnh) vẫn tiếp tục commit ảnh mới dù template ignore đã vá. Phải gỡ một lần.

    Hệ quả đã được chấp nhận: commit kế tiếp ghi nhận "đã xoá ảnh", và kéo brain về máy khác
    thì ảnh cũ không đi theo. Blob cũ vẫn nằm trong lịch sử - plan này KHÔNG viết lại history.

    Idempotent: brain chưa từng commit media thì không có gì để gỡ, trả 0.
    Trả về số thư mục đã thực sự gỡ.
    """
    n = 0
    try:
        for name in sorted(os.listdir(root)):
            if not os.path.isdir(os.path.join(root, name)):
                continue
            ten = name.strip()
            if ten.lower() != "inbox" and not re.match(_ATTACH_RE, ten, re.IGNORECASE):
                continue
            # Hỏi trước bằng ls-files: không có gì được theo dõi thì khỏi gọi git rm, và
            # quan trọng hơn là khỏi đếm nhầm thư mục vốn đã sạch (giữ tính idempotent).
            r = _git(root, "ls-files", "--", name)
            if not (r.stdout or "").strip():
                continue
            _git(root, "rm", "-r", "--cached", "--ignore-unmatch", "-q", "--", name)
            n += 1
    except Exception as e:
        print(f"[untrack_media] {root}: {type(e).__name__}: {e}", file=__import__('sys').stderr)
    return n
```

- [ ] **Step 6: Gọi `untrack_media` trong nhánh brain cũ**

Trong `ensure_git_repo`, sửa khối commit (dòng 133-148 hiện tại) thành:

```python
        changed = _ensure_gitignore_lines(root)
        dirty = bool((_git(root, "status", "--porcelain", "--", ".gitignore").stdout or "").strip())
        # untrack_media phải nằm TRONG khoá và NGAY TRƯỚC commit_paths: commit_paths chạy
        # `git commit` = commit CẢ INDEX, nên phần gỡ index chỉ được stage khi chắc chắn có
        # người commit nó ngay sau. Không giành được khoá thì bỏ qua cả hai, lần bấm sau lành.
        con_theo_doi = bool((_git(root, "ls-files", "--", "inbox").stdout or "").strip())
        if changed or dirty or con_theo_doi:
            with BrainLock(root, timeout=1.0) as lk:
                if getattr(lk, "acquired", False):
                    untrack_media(root)
                    commit_paths(root, [".gitignore"], "chore: cập nhật .gitignore brain")
        return {"ok": True, "created": False}
```

Lưu ý điều kiện: thêm phép thử `ls-files -- inbox` để brain nào đã có `.gitignore` đúng rồi (nên `changed` và `dirty` đều False) mà vẫn đang theo dõi media thì lượt này vẫn gỡ. Không có nó thì brain cũ mãi mãi không được dọn index.

- [ ] **Step 7: Chạy test cho xanh**

```bash
python tests/run.py media_gc -v
```

Kỳ vọng: `1/1 xanh`, có đủ dòng `ok` của mục 10.

Rồi chạy các test đụng tới git_brain để chắc không vỡ:

```bash
python tests/run.py --py
```

Kỳ vọng: tất cả xanh.

- [ ] **Step 8: Commit**

```bash
git add server/git_brain.py tests/python/test_media_gc.py
git commit -m "git_brain: media không lên git nữa, gỡ index một lần cho brain cũ"
```

---

### Task 5: Ô xám "Ảnh đã hết hạn" trên dashboard

**Files:**
- Modify: `dashboard/chat-render.js:171-177` (`imgHtml`)
- Modify: `dashboard/style.css:1267` (thêm `.chat-img-gone` ngay sau `.chat-img`)

**Interfaces:**
- Consumes: không có từ task trước (thuần frontend).
- Produces: hàm toàn cục `window.jvImgGone(el)` và class CSS `.chat-img-gone`.

**Bối cảnh:** `/files/raw` trả 404 khi file không còn (`server/main.py:2864`), nên `<img>` bắn sự kiện `error`. Bắt ở tầng `onerror` thì đúng luôn cả trường hợp user xoá tay hay đổi tên file, không riêng gì janitor. Dự án không đặt Content-Security-Policy nên thuộc tính `onerror` nội tuyến chạy được.

- [ ] **Step 1: Sửa `imgHtml` trong `dashboard/chat-render.js`**

Thay hàm `imgHtml` (dòng 171-177) bằng:

```js
  // Anh khong tai duoc (404 vi da het han trong vung cache, bi xoa tay, hay doi ten) -> thay
  // bang o xam co chu, thay vi de icon vo tro. Gan tren window vi chuoi onerror noi tuyen
  // chay o pham vi toan cuc, khong thay bien trong IIFE nay.
  window.jvImgGone = function (el) {
    var box = document.createElement("span");
    box.className = "chat-img-gone";
    box.textContent = "Ảnh đã hết hạn";
    el.replaceWith(box);
  };
  function imgHtml(u, alt, rawpath) {
    var img = '<img class="chat-img" src="' + esc(u) + '" alt="' + esc(alt || "") + '"' +
      ' loading="lazy" onerror="jvImgGone(this)">';
    // Anh trong vault: bam mo VI TRI trong Tep tin (thay vi tai anh tho); van hien anh inline.
    if (rawpath && isVaultRel(rawpath)) return '<a ' + vaultLoc(rawpath) + ">" + img + "</a>";
    var h = safeHref(u);
    return h ? '<a href="' + esc(h) + '" target="_blank" rel="noopener">' + img + "</a>" : img;
  }
```

- [ ] **Step 2: Thêm CSS**

Chèn ngay sau dòng `.chat-img { ... }` (`dashboard/style.css:1267`):

```css
/* Anh da bi don khoi vung cache (media_gc) hoac bi xoa tay. Vien dut de nhin ra ngay day la
   cho trong chu khong phai mot the anh that. */
.chat-img-gone { display: inline-block; margin: 6px 0; padding: 10px 14px; border-radius: 8px;
  border: 1px dashed var(--border); background: var(--bg3); color: var(--text3); font-size: 13px; }
```

- [ ] **Step 3: Kiểm tra thủ công**

Khởi động lại server local (cổng 7777) rồi:

1. Mở một cuộc chat có ảnh nhúng từ `attachments/`.
2. Xoá tay file ảnh đó trong vault.
3. Tải lại trang, cuộn tới tin nhắn đó.

Kỳ vọng: chỗ ảnh là ô xám viền đứt ghi **"Ảnh đã hết hạn"**, KHÔNG phải icon ảnh vỡ của trình duyệt. Chữ phải có dấu đầy đủ.

Không cần sửa `?v=` trong `dashboard/index.html`: `server/main.py:454` tự viết lại query `?v` của mọi file `.js`/`.css` theo VERSION, nên bump VERSION ở Task 6 là đủ để bể cache trình duyệt.

- [ ] **Step 4: Commit**

```bash
git add dashboard/chat-render.js dashboard/style.css
git commit -m "Dashboard: ảnh đã hết hạn hiện ô xám thay cho icon vỡ"
```

---

### Task 6: Chạy toàn bộ test, ra phiên bản

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: mọi thứ từ Task 1-5.
- Produces: một phiên bản đã đẩy lên `origin/main`.

- [ ] **Step 1: Chạy toàn bộ test**

```bash
python tests/run.py
```

Kỳ vọng: tất cả xanh, gồm cả `test_media_gc.py`. Nếu có test đỏ thì DỪNG, sửa, chạy lại - không bump phiên bản khi còn đỏ.

- [ ] **Step 2: Lấy số phiên bản kế tiếp từ REMOTE**

```bash
git fetch origin && git show origin/main:VERSION
```

Số mới = số vừa in ra cộng 1 ở chữ số cuối. Phải lấy từ `origin/main` chứ KHÔNG phải file `VERSION` cục bộ: PR của cloud agent có thể đã merge trên GitHub nên remote thường đi trước local.

- [ ] **Step 3: Ghi VERSION và CHANGELOG**

Ghi số mới vào `VERSION` (một dòng, không xuống dòng thừa).

Chèn khối mới vào `CHANGELOG.md` ngay dưới dòng `Định dạng: ...`, theo đúng khuôn các bản trước:

```markdown
## [x.y.z] - 2026-07-29
Ảnh và file gửi lên thôi nằm lại vĩnh viễn trong brain. Chúng là nguyên liệu đi qua, đọc xong rút thành ghi chú là đủ dùng.
### Cải thiện
- **Media không lên git nữa**: `attachments/` và `inbox/` giờ nằm ngoài git của brain. Trước đây mỗi tấm ảnh là một blob nằm vĩnh viễn trong lịch sử, xoá file về sau cũng không lấy lại được dung lượng, mà bản mirror còn nhân đôi. Brain cũ đã lỡ commit thì được gỡ khỏi chỉ mục một lần; phần lịch sử đã lỡ thì giữ nguyên, không viết lại.
- **Tự dọn vùng cache media**: ảnh quá 30 ngày tự xoá, và nếu tổng vượt 300MB thì dọn từ cũ tới mới cho tới khi xuống dưới trần. Chỉnh được qua khoá `media` trong `settings.json`, đặt `enabled: false` là thôi dọn. Ghi chú `.md` lạc vào hai thư mục đó thì được chừa ra.
- **Ảnh đã hết hạn hiện ô xám**: chỗ ảnh không còn hiện ô viền đứt ghi "Ảnh đã hết hạn" thay cho icon vỡ, đúng cả khi file bị xoá tay hay đổi tên.
```

Thay `x.y.z` bằng số thật ở Step 2.

- [ ] **Step 4: Commit và đẩy lên**

```bash
git add VERSION CHANGELOG.md && git commit -m "Media là vùng cache: không lên git, hết hạn 30 ngày/300MB (x.y.z)" && git push origin main
```

Thay `x.y.z` bằng số thật.

- [ ] **Step 5: Xác nhận đã lên**

```bash
git fetch origin && git log origin/main --oneline -1
```

Kỳ vọng: commit vừa đẩy nằm ở đầu `origin/main`.

---

## Ngoài phạm vi plan này

- Đẩy media lên Google Drive trước khi xoá. Sau này chèn một bước ngay trước `os.remove` trong `media_gc.sweep`.
- Viết lại lịch sử git của brain để lấy lại dung lượng blob cũ. Đã chốt là kệ.
- Dời media ra ngoài vault kiểu hermes. Đường dẫn `![](attachments/x.png)` giữ nguyên nên `/files/raw`, `console.js`, `file-editor.js` không phải đụng.
- Giao diện chỉnh `max_age_days` / `max_mb` trên trang Cài đặt. Hiện sửa thẳng `settings.json`.
