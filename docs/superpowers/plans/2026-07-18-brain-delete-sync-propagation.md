# Xóa não lan sang mọi máy qua Sync - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một lần xóa não có chủ đích lan sang mọi máy đồng bộ (không bị "hồi sinh"), mỗi máy giữ bản sao trong thùng rác cục bộ 30 ngày.

**Architecture:** Ghi "giấy báo tử" (tombstone) nhỏ đồng bộ theo repo khi xóa; bước `_apply_tombstones` trong sync đọc tombstone và xóa dứt khoát não đó ở mọi máy, ghi đè đúng chính sách "xóa không thắng" chỉ cho lần xóa cố ý. Dữ liệu não chuyển vào thùng rác cục bộ (ngoài vùng đồng bộ), tự dọn sau 30 ngày.

**Tech Stack:** Python 3 stdlib (git_brain.py, stdlib-only), FastAPI (main.py), vanilla JS (brains-ui.js), git CLI. Test = script standalone chạy `python test_*.py`, remote giả bằng repo `file://` cục bộ.

## Global Constraints

- **Không em dash (U+2014)** ở bất kỳ đâu (code/comment/chat/UI). Dùng "-" hoặc viết lại câu.
- `git_brain.py` chỉ dùng **stdlib**, không thêm dependency.
- Giữ nguyên **bất biến an toàn sync**: không bao giờ push khi áp về máy chưa trọn (lỗi -> rollback mirror + hoãn push).
- Tombstone giữ **180 ngày** (`_TOMBSTONE_TTL`); thùng rác giữ **30 ngày**. Hằng số nội bộ, không lộ UI.
- Não **mặc định** ("Brain Default") miễn nhiễm mọi tombstone (chặn 2 lớp).
- Test phải chạy bằng `.venv` (`../.venv/Scripts/python.exe` từ `server/`), python hệ thống thiếu lib.
- Comment/tên/chuỗi tiếng Việt là chính, khớp phong cách file hiện có.

---

## File Structure

- `server/git_brain.py` (Modify): thêm helpers tombstone + thùng rác + `_apply_tombstones`, nới `sync_brains`/`_sync_brains_locked` để nhận `trash_dir`/`protected_names`, GC đầu sync, áp tombstone sau integrate.
- `server/main.py` (Modify): viết lại `/brains/delete` (move-to-trash + tombstone + eager sync); `/brains/new` gỡ tombstone cùng tên; `_do_backup` truyền `trash_dir`/`protected_names`.
- `server/test_brain_tombstone.py` (Create): test helpers tombstone.
- `server/test_brain_trash.py` (Create): test helpers thùng rác + `_dir_newer_than`.
- `server/test_brain_delete_sync.py` (Create): test tích hợp 2 mirror + remote `file://` (lan xóa, chốt thời gian, bảo vệ khi không tombstone, não mặc định).
- `server/test_brain_delete_endpoint.py` (Create): test endpoint `/brains/delete` + `/brains/new`.
- `dashboard/brains-ui.js` (Modify): đổi lời xác nhận xóa.
- `dashboard/index.html` (Modify): bump `brains-ui.js?v=6 -> v=7`.
- `CHANGELOG.md`, `VERSION` (Modify): mục 0.9.76.

---

## Task 1: Helpers giấy báo tử (tombstone) trong git_brain.py

**Files:**
- Modify: `server/git_brain.py` (thêm sau khối BACKUP, trước `class BrainLock`; thêm `import json` ở đầu file)
- Test: `server/test_brain_tombstone.py`

**Interfaces:**
- Produces:
  - `TOMBSTONE_DIR = ".javis-tombstones"` (str, hằng)
  - `write_tombstone(brains_dir: str, name: str) -> None`
  - `clear_tombstone(brains_dir: str, name: str) -> None`
  - `_read_tombstones(root: str) -> list[dict]` (mỗi dict có `name`, `deleted_at`, `host`, `v`, và `_file` = tên file)
  - `gc_tombstones(brains_dir: str, ttl: int = _TOMBSTONE_TTL) -> int`
  - `_TOMBSTONE_TTL = 180 * 86400` (int)

- [ ] **Step 1: Viết test thất bại** — `server/test_brain_tombstone.py`

```python
"""Test helpers giấy báo tử (tombstone) của git_brain. Chạy:
    cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py
KHÔNG mạng."""
import os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

BR = Path(tempfile.mkdtemp(prefix="jv-tomb-")).resolve()

# write -> đọc lại đúng nội dung, file đúng tên
gb.write_tombstone(str(BR), "Ngọc Thu Phạm")
p = BR / gb.TOMBSTONE_DIR / "Ngọc Thu Phạm.json"
check("write_tombstone tạo đúng file", p.is_file())
ts = gb._read_tombstones(str(BR))
check("read_tombstones trả 1 mục", len(ts) == 1)
check("mục có name đúng (giữ dấu)", ts and ts[0]["name"] == "Ngọc Thu Phạm")
check("mục có deleted_at là số > 0", ts and isinstance(ts[0]["deleted_at"], int) and ts[0]["deleted_at"] > 0)

# clear -> hết
gb.clear_tombstone(str(BR), "Ngọc Thu Phạm")
check("clear_tombstone gỡ file", not p.exists())
check("read sau clear = rỗng", gb._read_tombstones(str(BR)) == [])
check("clear tên không tồn tại không ném", (gb.clear_tombstone(str(BR), "Không Có") or True))

# gc_tombstones: mục quá hạn bị xóa, mục mới giữ
gb.write_tombstone(str(BR), "Cu")
old = BR / gb.TOMBSTONE_DIR / "Cu.json"
import json
d = json.loads(old.read_text(encoding="utf-8")); d["deleted_at"] = int(time.time()) - (181 * 86400)
old.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
gb.write_tombstone(str(BR), "Moi")
n = gb.gc_tombstones(str(BR))
check("gc xóa đúng 1 mục quá hạn", n == 1)
names = {t["name"] for t in gb._read_tombstones(str(BR))}
check("gc giữ mục mới, bỏ mục cũ", names == {"Moi"})

print(); print("TẤT CẢ PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Chạy test để chắc nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py`
Expected: FAIL/AttributeError vì `git_brain` chưa có `write_tombstone`/`TOMBSTONE_DIR`.

- [ ] **Step 3: Thêm `import json` vào đầu `git_brain.py`**

Sửa khối import đầu file (hiện có `import os, shutil, subprocess, time`), thêm `import json`:

```python
import json
import os
import shutil
import subprocess
import time
```

- [ ] **Step 4: Thêm helpers tombstone** vào `git_brain.py`, đặt NGAY TRƯỚC dòng `# ============================================================` của khối `BrainLock` (khoảng dòng 698):

```python
# ============================================================
# GIẤY BÁO TỬ (tombstone) - đánh dấu não bị xóa CÓ CHỦ ĐÍCH để lan việc xóa sang mọi máy.
# Một file cho mỗi não trong <brains_dir>/.javis-tombstones/<tên não>.json. Đồng bộ theo repo
# (không nằm trong _backup_skip), KHÔNG hiện thành não (/brains bỏ tên bắt đầu bằng '.').
# ============================================================
TOMBSTONE_DIR = ".javis-tombstones"
_TOMBSTONE_TTL = 180 * 86400   # giữ 180 ngày: lâu hơn thùng rác để máy offline lâu quay lại không hồi sinh


def _tombstone_path(brains_dir: str, name: str) -> Path:
    return Path(brains_dir) / TOMBSTONE_DIR / (name + ".json")


def write_tombstone(brains_dir: str, name: str) -> None:
    """Ghi giấy báo tử cho não <name> (đã bị xóa có chủ đích). Ghi nguyên tử (.tmp -> replace)."""
    if not name:
        return
    p = _tombstone_path(brains_dir, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"name": name, "deleted_at": int(time.time()), "host": _host_tag(), "v": 1}
    tmp = Path(str(p) + ".tmp")   # đuôi .tmp -> nằm trong _backup_skip, không lọt vào backup
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(p))


def clear_tombstone(brains_dir: str, name: str) -> None:
    """Gỡ giấy báo tử của não <name> (khi tạo lại não cùng tên) để không bị xóa oan."""
    try:
        _tombstone_path(brains_dir, name).unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[tombstone clear] {name}: {e}", file=__import__('sys').stderr)


def _read_tombstones(root: str) -> List[dict]:
    """Đọc mọi giấy báo tử trong <root>/.javis-tombstones/. Bỏ file hỏng. Gắn _file = tên file."""
    d = Path(root) / TOMBSTONE_DIR
    out: List[dict] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(j, dict) and j.get("name"):
                j["_file"] = f.name
                out.append(j)
        except Exception:
            continue
    return out


def gc_tombstones(brains_dir: str, ttl: int = _TOMBSTONE_TTL) -> int:
    """Xóa giấy báo tử quá hạn (mặc định 180 ngày). Trả số file đã xóa."""
    now = int(time.time())
    n = 0
    for t in _read_tombstones(brains_dir):
        if now - int(t.get("deleted_at", now)) > ttl:
            try:
                (Path(brains_dir) / TOMBSTONE_DIR / t["_file"]).unlink()
                n += 1
            except Exception:
                pass
    return n
```

- [ ] **Step 5: Chạy test để chắc nó PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py`
Expected: `TẤT CẢ PASS`

- [ ] **Step 6: Commit**

```bash
git add server/git_brain.py server/test_brain_tombstone.py
git commit -m "feat(sync): helpers giay bao tu (tombstone) trong git_brain

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Helpers thùng rác + `_dir_newer_than` trong git_brain.py

**Files:**
- Modify: `server/git_brain.py` (thêm ngay sau khối tombstone của Task 1)
- Test: `server/test_brain_trash.py`

**Interfaces:**
- Produces:
  - `move_to_trash(brain_dir: str, trash_dir: str, name: str) -> Optional[str]` (trả path đích trong thùng rác, hoặc None nếu nguồn không phải thư mục; retry 3 lần cho Windows file-in-use)
  - `gc_trash(trash_dir: str, days: int = 30) -> int`
  - `_dir_newer_than(root: str, ts: int) -> bool` (có file nào trong root có mtime > ts + 1s)

- [ ] **Step 1: Viết test thất bại** — `server/test_brain_trash.py`

```python
"""Test helpers thùng rác + _dir_newer_than của git_brain. Chạy:
    cd server && ../.venv/Scripts/python.exe test_brain_trash.py"""
import os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

TMP = Path(tempfile.mkdtemp(prefix="jv-trash-")).resolve()
BR = TMP / "brains"; TRASH = TMP / "trash"
brain = BR / "Foo"; (brain / "sub").mkdir(parents=True)
(brain / "note.md").write_text("hi", encoding="utf-8")

# move_to_trash: nguồn biến mất, đích xuất hiện trong thùng rác
dest = gb.move_to_trash(str(brain), str(TRASH), "Foo")
check("move_to_trash trả path đích", bool(dest))
check("nguồn đã biến khỏi brains", not brain.exists())
check("đích nằm trong thùng rác + còn note", dest and Path(dest, "note.md").read_text(encoding="utf-8") == "hi")
check("move nguồn không tồn tại -> None", gb.move_to_trash(str(BR / "KhongCo"), str(TRASH), "KhongCo") is None)

# _dir_newer_than
d2 = BR / "Bar"; d2.mkdir(parents=True)
f = d2 / "x.md"; f.write_text("x", encoding="utf-8")
past = int(time.time()) - 1000; future = int(time.time()) + 1000
check("_dir_newer_than: có file mới hơn mốc quá khứ", gb._dir_newer_than(str(d2), past) is True)
check("_dir_newer_than: không file nào mới hơn mốc tương lai", gb._dir_newer_than(str(d2), future) is False)
check("_dir_newer_than: ts<=0 -> False", gb._dir_newer_than(str(d2), 0) is False)

# gc_trash: mục quá 30 ngày bị dọn, mục mới giữ
oldt = TRASH / "Old__20200101-000000"; oldt.mkdir(parents=True)
os.utime(oldt, (time.time() - 40 * 86400, time.time() - 40 * 86400))
newt = TRASH / "New__20990101-000000"; newt.mkdir(parents=True)
n = gb.gc_trash(str(TRASH), 30)
check("gc_trash dọn mục >30 ngày", not oldt.exists() and n >= 1)
check("gc_trash giữ mục mới", newt.exists())

print(); print("TẤT CẢ PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Chạy test để chắc nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: FAIL/AttributeError (`move_to_trash` chưa có).

- [ ] **Step 3: Thêm helpers thùng rác** vào `git_brain.py`, ngay sau `gc_tombstones` (Task 1):

```python
# ============================================================
# THÙNG RÁC CỤC BỘ - giữ bản sao não đã xóa (30 ngày) để cứu hộ. NGOÀI vùng đồng bộ (không lên git).
# ============================================================
def move_to_trash(brain_dir: str, trash_dir: str, name: str) -> Optional[str]:
    """Chuyển thư mục não vào thùng rác <trash_dir>/<name>__<ts>/. Trả path đích hoặc None nếu
    nguồn không phải thư mục. shutil.move xử lý cả khác ổ đĩa. Retry 3 lần: Windows có thể kẹt
    handle (engine đang mở file trong não) - chờ ngắn rồi thử lại."""
    src = Path(brain_dir)
    if not src.is_dir():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = Path(trash_dir) / f"{name}__{stamp}"
    i = 1
    while dst.exists():
        dst = Path(trash_dir) / f"{name}__{stamp}-{i}"
        i += 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for _ in range(3):
        try:
            shutil.move(str(src), str(dst))
            return str(dst)
        except Exception as e:
            last = e
            time.sleep(0.3)
    raise last


def gc_trash(trash_dir: str, days: int = 30) -> int:
    """Xóa các mục trong thùng rác cũ hơn <days> ngày (theo mtime thư mục). Trả số mục đã xóa."""
    d = Path(trash_dir)
    if not d.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    n = 0
    for sub in d.iterdir():
        try:
            if sub.is_dir() and sub.stat().st_mtime < cutoff:
                shutil.rmtree(str(sub))
                n += 1
        except Exception:
            pass
    return n


def _dir_newer_than(root: str, ts: int) -> bool:
    """Có file nào trong root có mtime > ts (dung sai +1s) không? Bỏ .git nested. Dùng cho chốt
    thời gian: não dựng/sửa lại SAU khi có tombstone thì không bị xóa oan."""
    if ts <= 0:
        return False
    for dp, dn, fns in os.walk(root):
        dn[:] = [x for x in dn if x not in _BACKUP_SKIP_DIRS]
        for fn in fns:
            try:
                if os.path.getmtime(os.path.join(dp, fn)) > ts + 1:
                    return True
            except Exception:
                continue
    return False
```

- [ ] **Step 4: Chạy test để chắc nó PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: `TẤT CẢ PASS`

- [ ] **Step 5: Commit**

```bash
git add server/git_brain.py server/test_brain_trash.py
git commit -m "feat(sync): helpers thung rac cuc bo + _dir_newer_than

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `_apply_tombstones` + đấu vào luồng sync

**Files:**
- Modify: `server/git_brain.py` (`_apply_tombstones` mới; nới `sync_brains` + `_sync_brains_locked`)
- Modify: `server/main.py` (`_do_backup` truyền `trash_dir`/`protected_names`, dòng ~1208-1209)
- Test: `server/test_brain_delete_sync.py`

**Interfaces:**
- Consumes: `write_tombstone`, `_read_tombstones`, `move_to_trash`, `gc_trash`, `gc_tombstones`, `_dir_newer_than` (Task 1-2); `_git`, `_rollback_mirror`, `_host_tag`, `_BACKUP_SKIP_DIRS`.
- Produces:
  - `_apply_tombstones(brains_dir, mirror_dir, trash_dir, protected_names) -> dict` trả `{"deleted": [str], "superseded": [str], "failed": [str]}`
  - `sync_brains(..., trash_dir=None, protected_names=None)` - thêm 2 kwarg (mặc định giữ tương thích)
  - `rep["brains_deleted"]: list[str]` trong kết quả sync

- [ ] **Step 1: Viết test tích hợp thất bại** — `server/test_brain_delete_sync.py`

```python
"""Test tích hợp: xóa não lan sang máy khác qua sync (remote file:// cục bộ). Chạy:
    cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py
Cần git trong PATH. KHÔNG mạng thật."""
import os, sys, time, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

if not gb.has_git():
    print("SKIP: máy không có git"); sys.exit(0)

ROOT = Path(tempfile.mkdtemp(prefix="jv-delsync-")).resolve()
REMOTE = ROOT / "remote.git"
subprocess.run(["git", "init", "--bare", str(REMOTE)], capture_output=True)
URL = "file:///" + str(REMOTE).replace("\\", "/").lstrip("/")
TOKEN = "x"  # file:// không dùng token nhưng sync_brains yêu cầu non-empty

def machine(tag):
    b = ROOT / tag / "brains"; m = ROOT / tag / "mirror"; t = ROOT / tag / "trash"
    b.mkdir(parents=True, exist_ok=True)
    return str(b), str(m), str(t)

def seed(brains, name, text="hi"):
    d = Path(brains) / name; d.mkdir(parents=True, exist_ok=True)
    (d / "note.md").write_text(text, encoding="utf-8")

def sync(brains, mirror, trash):
    return gb.sync_brains(brains, mirror, URL, TOKEN, "main",
                          trash_dir=trash, protected_names={"Brain Default"})

# --- Dựng: A tạo Foo, đẩy lên; B kéo về -> cả hai + remote đều có Foo ---
Ab, Am, At = machine("A"); Bb, Bm, Bt = machine("B")
seed(Ab, "Foo"); sync(Ab, Am, At)
sync(Bb, Bm, Bt)
check("B nhận được Foo từ remote", (Path(Bb) / "Foo" / "note.md").exists())

# --- A xóa Foo (move trash + tombstone) rồi sync ---
gb.move_to_trash(str(Path(Ab) / "Foo"), At, "Foo")
gb.write_tombstone(Ab, "Foo")
r = sync(Ab, Am, At)
check("A: sync sau xóa ok", r.get("ok"))
check("A: Foo không còn trong brains", not (Path(Ab) / "Foo").exists())

# --- B sync -> Foo bị xóa ở B + vào thùng rác B, remote sạch ---
r2 = sync(Bb, Bm, Bt)
check("B: sync ok", r2.get("ok"))
check("B: Foo bị xóa khỏi brains", not (Path(Bb) / "Foo").exists())
trashed = list(Path(Bt).glob("Foo__*")) if Path(Bt).is_dir() else []
check("B: Foo nằm trong thùng rác B", len(trashed) == 1 and (trashed[0] / "note.md").exists())

# --- Chốt thời gian: tạo LẠI Foo mới ở A (mtime mới) rồi sync -> KHÔNG bị xóa, tombstone gỡ ---
seed(Ab, "Foo", "moi")
os.utime(Path(Ab) / "Foo" / "note.md", None)  # mtime = bây giờ > deleted_at
r3 = sync(Ab, Am, At)
check("A: Foo dựng lại KHÔNG bị xóa (chốt thời gian)", (Path(Ab) / "Foo" / "note.md").exists())
check("A: tombstone Foo đã gỡ", not (Path(Ab) / gb.TOMBSTONE_DIR / "Foo.json").exists())

# --- Bảo vệ khi KHÔNG tombstone: xóa tay Bar khỏi brains B -> sync khôi phục, không mất ---
Cb, Cm, Ct = machine("C")
seed(Cb, "Bar"); sync(Cb, Cm, Ct)   # đẩy Bar lên remote
Db, Dm, Dt = machine("D"); sync(Db, Dm, Dt)  # D kéo Bar về
import shutil as _sh; _sh.rmtree(str(Path(Db) / "Bar"))  # xóa TAY, KHÔNG tombstone
sync(Db, Dm, Dt)
check("Bảo vệ: Bar biến mất không tombstone -> được khôi phục", (Path(Db) / "Bar").exists())

# --- Não mặc định miễn nhiễm: tombstone giả trỏ 'Brain Default' -> không bị xóa ---
Eb, Em, Et = machine("E")
seed(Eb, "Brain Default"); gb.write_tombstone(Eb, "Brain Default")
sync(Eb, Em, Et)
check("Não mặc định miễn nhiễm tombstone", (Path(Eb) / "Brain Default").exists())

print(); print("TẤT CẢ PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Chạy test để chắc nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py`
Expected: FAIL - `sync_brains()` chưa nhận `trash_dir`/`protected_names` (TypeError) hoặc lan xóa chưa hoạt động.

- [ ] **Step 3: Thêm `_apply_tombstones`** vào `git_brain.py`, đặt ngay TRƯỚC `def sync_brains(` (khoảng dòng 601):

```python
def _apply_tombstones(brains_dir: str, mirror_dir: str, trash_dir: str,
                      protected_names) -> dict:
    """Áp giấy báo tử: xóa DỨT KHOÁT các não có tombstone (ghi đè chính sách 'xóa không thắng'),
    chỉ cho lần xóa cố ý. Đọc tombstone từ MIRROR sau hoà nhập (= union mọi máy).
    - Chốt thời gian: não còn sống mà có file mtime > deleted_at -> dựng/sửa lại có chủ đích ->
      BỎ QUA + gỡ tombstone (superseded, propagate việc gỡ).
    - Xóa: brains_dir/<name> -> thùng rác; mirror/<name> -> git rm -r (stage) để đẩy đi.
    - An toàn: bỏ qua não mặc định (protected_names) + tên phải là con TRỰC TIẾP của brains_dir.
    Trả {deleted, superseded, failed}."""
    rep = {"deleted": [], "superseded": [], "failed": []}
    protected = set(protected_names or ())
    tombs = _read_tombstones(mirror_dir)
    if not tombs:
        return rep
    base = Path(brains_dir).resolve()
    changed_mirror = False
    for t in tombs:
        name = t.get("name") or ""
        deleted_at = int(t.get("deleted_at", 0))
        if not name or name in protected:
            continue
        bp = Path(brains_dir) / name
        mp = Path(mirror_dir) / name
        try:
            if bp.resolve().parent != base:   # chỉ con trực tiếp của brains_dir
                continue
        except Exception:
            continue
        # Chốt thời gian: dựng lại có chủ đích -> giữ + gỡ tombstone
        if bp.is_dir() and _dir_newer_than(str(bp), deleted_at):
            _git(mirror_dir, "rm", "-f", "--", f"{TOMBSTONE_DIR}/{t['_file']}")
            try:
                (Path(brains_dir) / TOMBSTONE_DIR / t["_file"]).unlink()
            except Exception:
                pass
            changed_mirror = True
            rep["superseded"].append(name)
            continue
        # Xóa dứt khoát
        ok = True
        if bp.is_dir():
            try:
                move_to_trash(str(bp), trash_dir, name)
            except Exception as e:
                ok = False
                print(f"[tombstone] move trash {name}: {type(e).__name__}: {e}",
                      file=__import__('sys').stderr)
        if ok and mp.exists():
            r = _git(mirror_dir, "rm", "-r", "-f", "--", name)
            if r.returncode == 0:
                changed_mirror = True
            else:
                ok = False
        if ok:
            rep["deleted"].append(name)
        else:
            rep["failed"].append(name)
    if changed_mirror:
        _git(mirror_dir, "commit", "-m", f"sync: áp giấy báo tử ({_host_tag()})")
    return rep
```

- [ ] **Step 4: Nới `sync_brains` nhận 2 kwarg** - sửa signature (dòng ~601) và lời gọi `_sync_brains_locked` (dòng ~613):

Từ:
```python
def sync_brains(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str = "main") -> dict:
```
Thành:
```python
def sync_brains(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str = "main",
                trash_dir: Optional[str] = None, protected_names=None) -> dict:
```
Và trong thân, đổi lời gọi:
```python
        return _sync_brains_locked(str(brains_dir), str(mirror_dir), repo_url, token, branch)
```
thành:
```python
        return _sync_brains_locked(str(brains_dir), str(mirror_dir), repo_url, token, branch,
                                   trash_dir, protected_names)
```

- [ ] **Step 5: Nới `_sync_brains_locked`** - signature (dòng ~620), rep init (thêm `brains_deleted`), GC đầu hàm, và chèn `_apply_tombstones` sau integrate.

Signature từ:
```python
def _sync_brains_locked(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str) -> dict:
```
thành:
```python
def _sync_brains_locked(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str,
                        trash_dir: Optional[str] = None, protected_names=None) -> dict:
```

Ngay sau dòng `rep = {...}` (dòng 621-623), thêm khối chuẩn bị trash_dir + GC (đặt trước `Path(mirror_dir).mkdir(...)`):
```python
    if not trash_dir:
        trash_dir = str(Path(mirror_dir).parent / "brain-trash")   # cạnh mirror (đều trong STATE_DIR)
    gc_trash(trash_dir, 30)              # dọn thùng rác quá 30 ngày
    gc_tombstones(brains_dir, _TOMBSTONE_TTL)   # dọn giấy báo tử quá 180 ngày
```
Và thêm `"brains_deleted": []` vào dict `rep` (ví dụ cạnh `"deleted_sample": []`).

Chèn `_apply_tombstones` NGAY SAU khối integrate (sau dòng `changed = _changed_by_integration(mirror_dir, pre_head)`, dòng ~662) và TRƯỚC khối tự-vá (dòng ~663 `# Tự vá...`):
```python
        # Áp giấy báo tử: xóa dứt khoát não có tombstone (ghi đè 'xóa không thắng') TRƯỚC khi
        # _apply_back kịp khôi phục chúng về brains. Đặt trước tự-vá + _apply_back là cố ý.
        tomb = _apply_tombstones(brains_dir, mirror_dir, trash_dir, protected_names)
        if tomb["failed"]:
            _rollback_mirror(mirror_dir, pre_head)
            return {**rep, "error": "Áp giấy báo tử lỗi (" + ", ".join(tomb["failed"][:2]) +
                    ") - hoãn push, lần sau tự thử lại"}
        if tomb["deleted"]:
            rep["brains_deleted"] = (rep["brains_deleted"] + tomb["deleted"])[:50]
```

- [ ] **Step 6: `_do_backup` truyền trash_dir + protected_names** - `server/main.py` dòng ~1208-1209:

Từ:
```python
    mirror = str(cfgmod.STATE_DIR / "brains-backup")   # repo mirror riêng (tránh nested git từng brain)
    res = git_brain.sync_brains(BRAINS_DIR, mirror, b["repo_url"], b["token"], b.get("branch") or "main")
```
Thành:
```python
    mirror = str(cfgmod.STATE_DIR / "brains-backup")   # repo mirror riêng (tránh nested git từng brain)
    res = git_brain.sync_brains(BRAINS_DIR, mirror, b["repo_url"], b["token"], b.get("branch") or "main",
                                trash_dir=str(cfgmod.STATE_DIR / "brain-trash"),
                                protected_names={_default_brain_dir().name})
```

- [ ] **Step 7: Chạy test tích hợp để chắc nó PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py`
Expected: `TẤT CẢ PASS` (nếu máy không git thì in `SKIP`).

- [ ] **Step 8: Chạy lại 2 test đơn vị (không hồi quy)**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: cả hai `TẤT CẢ PASS`.

- [ ] **Step 9: Commit**

```bash
git add server/git_brain.py server/main.py server/test_brain_delete_sync.py
git commit -m "feat(sync): _apply_tombstones - xoa nao lan sang moi may, chot thoi gian + bao ve

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Viết lại endpoint `/brains/delete` (move-to-trash + tombstone + eager sync)

**Files:**
- Modify: `server/main.py` (`/brains/delete` dòng ~2037-2058; thêm `_DELETE_SYNC_TASKS = set()` ngay trên endpoint)
- Test: `server/test_brain_delete_endpoint.py`

**Interfaces:**
- Consumes: `git_brain.move_to_trash`, `git_brain.write_tombstone`, `_do_backup`, `cfgmod.STATE_DIR`, `_default_brain_dir`, `_safe_brain_name`.
- Produces: `/brains/delete` trả `{"ok": True, "name": safe, "trashed": bool}`; tạo tombstone + chuyển vào `<STATE_DIR>/brain-trash/`.

- [ ] **Step 1: Viết test thất bại** — `server/test_brain_delete_endpoint.py`

```python
"""Test endpoint /brains/delete + /brains/new (tombstone). Chạy:
    cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py"""
import os, sys, asyncio, tempfile
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="jv-del-state-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

BR = Path(tempfile.mkdtemp(prefix="jv-del-brains-")).resolve()
main.BRAINS_DIR = str(BR)
(BR / "Brain Default").mkdir(parents=True)         # não mặc định (không xóa được)
foo = BR / "Foo"; foo.mkdir(parents=True); (foo / "n.md").write_text("hi", encoding="utf-8")

# Xóa Foo hợp lệ (confirm khớp) -> vào thùng rác + tombstone, không còn trong brains
r = asyncio.run(main.delete_brain(name="Foo", confirm="Foo"))
ok = getattr(r, "body", None) is None  # JSONResponse lỗi mới có .body; dict thành công thì không
check("xóa Foo trả ok", isinstance(r, dict) and r.get("ok"))
check("Foo biến khỏi brains", not foo.exists())
check("tombstone Foo được ghi", (BR / gb.TOMBSTONE_DIR / "Foo.json").exists())
import config as cfgmod
trash = Path(cfgmod.STATE_DIR) / "brain-trash"
check("Foo nằm trong thùng rác", trash.is_dir() and len(list(trash.glob("Foo__*"))) == 1)

# Chặn xóa não mặc định
r2 = asyncio.run(main.delete_brain(name="Brain Default", confirm="Brain Default"))
check("chặn xóa não mặc định", hasattr(r2, "status_code") and r2.status_code == 400)

# confirm sai -> chặn
bar = BR / "Bar"; bar.mkdir(parents=True)
r3 = asyncio.run(main.delete_brain(name="Bar", confirm="sai"))
check("confirm sai -> chặn, Bar còn nguyên", hasattr(r3, "status_code") and bar.exists())

# /brains/new gỡ tombstone cùng tên (dựng lại Foo)
gb.write_tombstone(str(BR), "Foo")
r4 = asyncio.run(main.new_brain(name="Foo"))
check("tạo lại Foo -> gỡ tombstone Foo", not (BR / gb.TOMBSTONE_DIR / "Foo.json").exists())

print(); print("TẤT CẢ PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Chạy test để chắc nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: FAIL - `/brains/delete` còn `rmtree` (không tạo tombstone/thùng rác); `/brains/new` chưa gỡ tombstone.

- [ ] **Step 3: Thêm set giữ ref + viết lại endpoint** - `server/main.py`. Ngay TRƯỚC `@app.post("/brains/delete")` thêm:

```python
_DELETE_SYNC_TASKS = set()   # giữ ref mạnh cho eager-sync sau khi xóa não (tránh GC nuốt task)
```

Thay TOÀN BỘ thân `delete_brain` (giữ các guard cũ, đổi phần thực thi):

```python
@app.post("/brains/delete")
async def delete_brain(name: str = Form(...), confirm: str = Form("")):
    """Xoá 1 brain: CHUYỂN vào thùng rác cục bộ (giữ 30 ngày) + ghi giấy báo tử để lan việc xoá
    sang mọi máy đồng bộ. Yêu cầu confirm == name. Chặn xoá não mặc định + chỉ trong BRAINS_DIR."""
    safe = _safe_brain_name(name)
    if not safe:
        return JSONResponse({"ok": False, "error": "Tên brain không hợp lệ"}, status_code=400)
    if (confirm or "").strip() != safe:
        return JSONResponse({"ok": False, "error": "Xác nhận không khớp tên brain"}, status_code=400)
    root = (Path(BRAINS_DIR) / safe).resolve()
    base = Path(BRAINS_DIR).resolve()
    if root == base or base not in root.parents:
        return JSONResponse({"ok": False, "error": "Brain ngoài phạm vi quản lý"}, status_code=400)
    if root == _default_brain_dir().resolve():
        return JSONResponse({"ok": False, "error": "Không thể xoá Brain mặc định"}, status_code=400)
    if not root.is_dir():
        return JSONResponse({"ok": False, "error": "Brain không tồn tại"}, status_code=404)
    trash_dir = str(cfgmod.STATE_DIR / "brain-trash")

    def _trash_and_mark():
        dest = git_brain.move_to_trash(str(root), trash_dir, safe)   # có retry cho Windows
        git_brain.write_tombstone(BRAINS_DIR, safe)                  # giấy báo tử -> lan việc xoá
        return dest

    try:
        dest = await asyncio.to_thread(_trash_and_mark)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Không xoá được (brain đang bận?): {e}"},
                            status_code=500)

    # Eager sync (nền, best-effort): đẩy lệnh xoá + tombstone lên remote NGAY thay vì chờ chu kỳ 6h.
    try:
        _b = cfgmod.read_settings().get("backup", {}) or {}
        if _b.get("enabled") and _b.get("repo_url") and _b.get("token") and git_brain.has_git():
            _t = asyncio.create_task(asyncio.to_thread(_do_backup))
            _DELETE_SYNC_TASKS.add(_t)
            _t.add_done_callback(_DELETE_SYNC_TASKS.discard)
    except Exception:
        pass

    return {"ok": True, "name": safe, "trashed": bool(dest)}
```

- [ ] **Step 4: Chạy test để chắc nó PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: `TẤT CẢ PASS`

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_brain_delete_endpoint.py
git commit -m "feat(brain): xoa nao chuyen vao thung rac + ghi tombstone + eager sync

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `/brains/new` gỡ tombstone cùng tên

**Files:**
- Modify: `server/main.py` (`/brains/new` dòng ~2021-2034)
- Test: đã phủ ở `server/test_brain_delete_endpoint.py` (case "/brains/new gỡ tombstone").

**Interfaces:**
- Consumes: `git_brain.clear_tombstone`.
- Produces: `/brains/new` gỡ tombstone của tên vừa tạo (chống xóa oan não dựng lại).

- [ ] **Step 1: Sửa `new_brain`** - thêm `clear_tombstone` sau khi tạo scaffold thành công. Từ:

```python
    try:
        _ensure_brain_scaffold(root)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "name": safe, "path": str(root)}
```
Thành:
```python
    try:
        _ensure_brain_scaffold(root)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    git_brain.clear_tombstone(BRAINS_DIR, safe)   # dựng lại não cùng tên -> gỡ giấy báo tử để không bị xoá oan
    return {"ok": True, "name": safe, "path": str(root)}
```

- [ ] **Step 2: Chạy lại test endpoint (đã có case này)**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: `TẤT CẢ PASS` (case "tạo lại Foo -> gỡ tombstone Foo" xanh).

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat(brain): tao lai nao cung ten thi go tombstone (chong xoa oan)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Lời xác nhận xóa ở frontend + bump cache

**Files:**
- Modify: `dashboard/brains-ui.js` (hàm `deleteBrain`, phần prompt xác nhận)
- Modify: `dashboard/index.html` (`brains-ui.js?v=6 -> v=7`)

**Interfaces:** không có (chỉ text UI).

- [ ] **Step 1: Đổi lời prompt xác nhận** trong `deleteBrain` (`dashboard/brains-ui.js`). Từ:

```javascript
    const typed = window.prompt(
      "⚠️ XOÁ BRAIN \"" + name + "\"\n\n" +
      "Toàn bộ tri thức (sources, wiki, agents, workflows, bộ nhớ...) trong não này sẽ bị XOÁ VĨNH VIỄN, KHÔNG khôi phục được.\n\n" +
      "Gõ CHÍNH XÁC tên brain để xác nhận:"
    );
```
Thành:
```javascript
    const typed = window.prompt(
      "⚠️ XOÁ BRAIN \"" + name + "\"\n\n" +
      "Não này sẽ được chuyển vào THÙNG RÁC (giữ 30 ngày rồi tự xoá hẳn), và việc xoá sẽ ĐỒNG BỘ sang mọi máy khác.\n\n" +
      "Gõ CHÍNH XÁC tên brain để xác nhận:"
    );
```

- [ ] **Step 2: Đổi thông báo sau khi xóa** trong `deleteBrain`. Từ:
```javascript
    alert('Đã xoá brain "' + name + '".');
```
Thành:
```javascript
    alert('Đã xoá brain "' + name + '" (đưa vào thùng rác 30 ngày, đồng bộ xoá sang các máy khác).');
```

- [ ] **Step 3: Bump cache** - `dashboard/index.html`:
```
  <script src="/static/brains-ui.js?v=7"></script>
```

- [ ] **Step 4: Kiểm tra cú pháp JS**

Run: `node -e "const fs=require('fs');new Function(fs.readFileSync('dashboard/brains-ui.js','utf8'));console.log('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add dashboard/brains-ui.js dashboard/index.html
git commit -m "feat(brain): loi xac nhan xoa bao thung rac 30 ngay + dong bo xoa (bump v=7)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: CHANGELOG + VERSION + khởi động lại kiểm chứng

**Files:**
- Modify: `CHANGELOG.md` (mục `## [0.9.76] - 2026-07-18` trên đầu, dưới phần header format)
- Modify: `VERSION` (`0.9.75 -> 0.9.76`)

- [ ] **Step 1: Chạy TẤT CẢ test mới (không hồi quy)**

Run:
```bash
cd server && for t in test_brain_tombstone test_brain_trash test_brain_delete_sync test_brain_delete_endpoint; do echo "== $t =="; ../.venv/Scripts/python.exe $t.py || echo "FAILED $t"; done
```
Expected: mỗi test in `TẤT CẢ PASS` (hoặc `SKIP` nếu thiếu git).

- [ ] **Step 2: Thêm mục CHANGELOG 0.9.76** - chèn ngay trên `## [0.9.75]`:

```markdown
## [0.9.76] - 2026-07-18
Xoá não giờ LAN sang mọi máy đồng bộ (không còn bị "hồi sinh"), và giữ bản sao trong thùng rác cục bộ 30 ngày. **Cần khởi động lại server** (đổi luồng sync + endpoint xoá); giao diện tự nạp lại nhờ bump `?v=7`.
### Thêm mới
- **Giấy báo tử (tombstone) đồng bộ để lan việc xoá não**: khi xoá 1 não (đã gõ đúng tên xác nhận), Jarvis 007 ghi một file nhỏ `<BRAINS_DIR>/.javis-tombstones/<tên>.json` đồng bộ theo repo. Bước `_apply_tombstones` mới trong sync đọc tombstone và xoá dứt khoát não đó ở mọi máy, ghi đè đúng chính sách "xoá không thắng bản còn sống" - NHƯNG chỉ cho lần xoá cố ý. Có chốt thời gian: não được tạo/sửa lại sau khi xoá thì không bị giết oan (tombstone tự gỡ). Não mặc định miễn nhiễm.
- **Thùng rác cục bộ 30 ngày**: xoá não giờ CHUYỂN dữ liệu vào `<STATE_DIR>/brain-trash/<tên>__<thời-gian>/` (ngoài vùng đồng bộ, mỗi máy một thùng riêng) thay vì xoá cứng; tự dọn mục quá 30 ngày ở đầu mỗi lần sync. Lời xác nhận khi xoá báo rõ điều này. Khôi phục bằng tay (chuyển folder từ thùng rác về `brains/`).
### Sửa lỗi
- **Não đã xoá bị "hồi sinh" khi sync/update**: chính sách sync cũ cố tình không cho việc xoá thắng bản còn sống (chống mất dữ liệu), nên một não xoá ở máy này bị máy/remote khác đẩy ngược lại. Nay lần xoá cố ý lan đi qua tombstone; lá chắn chống mất dữ liệu chung vẫn nguyên vẹn cho mọi trường hợp KHÔNG có tombstone (folder biến mất do volume chưa mount, engine ghi dở...).
```

- [ ] **Step 3: Bump VERSION**

Ghi `VERSION` = `0.9.76`.

- [ ] **Step 4: Commit + push**

```bash
git add CHANGELOG.md VERSION
git commit -m "chore(release): 0.9.76 - xoa nao lan sang moi may + thung rac 30 ngay

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 5: Khởi động lại + kiểm chứng live**

Run: `wscript //nologo start-javis.vbs` (chờ ~8s) rồi kiểm tra server lên (`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7777/` = 200) và log không traceback (`tail -15 server/javis.log`).
Expected: server lên PID mới, không lỗi. Xác nhận `curl -s http://127.0.0.1:7777/static/index.html | grep brains-ui` = `?v=7`.

---

## Self-Review

**Spec coverage:**
- Tombstone store (spec 4.1) -> Task 1. ✓
- Thùng rác + GC (spec 4.2) -> Task 2 (+ GC gọi trong Task 3). ✓
- `_apply_tombstones` + thứ tự sync (spec 4.3, 5.2, 5.3) -> Task 3. ✓
- Luồng xoá: move-to-trash + tombstone + eager sync + confirm (spec 5.1) -> Task 4 (backend) + Task 6 (confirm UI). ✓
- `/brains/new` gỡ tombstone (spec 5.1 chốt thời gian lớp 2) -> Task 5. ✓
- Rào an toàn (spec 6): con trực tiếp brains_dir, não mặc định miễn nhiễm, chốt thời gian, không push nửa vời -> Task 3 (`_apply_tombstones` + failed->rollback). ✓
- Test a-f (spec 7) -> Task 1/2 (đơn vị), Task 3 (lan xoá, chốt thời gian, bảo vệ không-tombstone, mặc định miễn nhiễm), Task 4 (endpoint + dọn thùng rác đã phủ ở Task 2). ✓
- Retention 180 ngày tombstone (spec 3, 8) -> `gc_tombstones` (Task 1) gọi trong Task 3 Step 5. ✓

**Placeholder scan:** Không có TBD/TODO; mọi step có mã/lệnh thật + kỳ vọng cụ thể. ✓

**Type consistency:** `write_tombstone/clear_tombstone/_read_tombstones/gc_tombstones/move_to_trash/gc_trash/_dir_newer_than/_apply_tombstones` khai ở Task 1-3 và dùng đúng tên/chữ ký ở Task 3-5. `sync_brains(..., trash_dir, protected_names)` khai ở Task 3 Step 4, dùng ở Task 3 Step 6 (`_do_backup`) và test. `rep["brains_deleted"]` khai + gán ở Task 3 Step 5. ✓
