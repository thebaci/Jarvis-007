# Brain Deletion Propagating to Every Machine via Sync - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deliberate brain deletion propagates to every synced machine (it is not "resurrected"), and each machine keeps a copy in a local trash for 30 days.

**Architecture:** On delete, write a small repo-synced "death notice" (tombstone); the `_apply_tombstones` step in sync reads the tombstones and definitively deletes that brain on every machine, overriding the "delete does not win" policy only for deliberate deletions. Brain data moves into a local trash (outside the sync area), cleaned automatically after 30 days.

**Tech Stack:** Python 3 stdlib (git_brain.py, stdlib-only), FastAPI (main.py), vanilla JS (brains-ui.js), git CLI. Tests = standalone scripts run with `python test_*.py`, fake remote = a local `file://` repo.

## Global Constraints

- **No em dash (U+2014)** anywhere (code/comments/chat/UI). Use "-" or rewrite the sentence.
- `git_brain.py` uses **stdlib only**, no new dependencies.
- Keep the **sync safety invariant**: never push when applying to the machine is incomplete (on error -> roll back the mirror + defer the push).
- Tombstones are kept **180 days** (`_TOMBSTONE_TTL`); the trash is kept **30 days**. Internal constants, not exposed in the UI.
- The **default** brain ("Brain Default") is immune to every tombstone (two layers of blocking).
- Tests must run with `.venv` (`../.venv/Scripts/python.exe` from `server/`); the system python lacks libs.
- Comments, names and strings match the style of the existing files.

---

## File Structure

- `server/git_brain.py` (Modify): add tombstone + trash helpers + `_apply_tombstones`, extend `sync_brains`/`_sync_brains_locked` to accept `trash_dir`/`protected_names`, GC at the start of sync, apply tombstones after integrate.
- `server/main.py` (Modify): rewrite `/brains/delete` (move-to-trash + tombstone + eager sync); `/brains/new` removes the tombstone of the same name; `_do_backup` passes `trash_dir`/`protected_names`.
- `server/test_brain_tombstone.py` (Create): tests for the tombstone helpers.
- `server/test_brain_trash.py` (Create): tests for the trash helpers + `_dir_newer_than`.
- `server/test_brain_delete_sync.py` (Create): integration test with 2 mirrors + a `file://` remote (delete propagation, time cutoff, protection without a tombstone, default brain).
- `server/test_brain_delete_endpoint.py` (Create): tests for the `/brains/delete` + `/brains/new` endpoints.
- `dashboard/brains-ui.js` (Modify): change the delete confirmation text.
- `dashboard/index.html` (Modify): bump `brains-ui.js?v=6 -> v=7`.
- `CHANGELOG.md`, `VERSION` (Modify): entry 0.9.76.

---

## Task 1: Tombstone helpers in git_brain.py

**Files:**
- Modify: `server/git_brain.py` (add after the BACKUP block, before `class BrainLock`; add `import json` at the top of the file)
- Test: `server/test_brain_tombstone.py`

**Interfaces:**
- Produces:
  - `TOMBSTONE_DIR = ".javis-tombstones"` (str, constant)
  - `write_tombstone(brains_dir: str, name: str) -> None`
  - `clear_tombstone(brains_dir: str, name: str) -> None`
  - `_read_tombstones(root: str) -> list[dict]` (each dict has `name`, `deleted_at`, `host`, `v`, and `_file` = file name)
  - `gc_tombstones(brains_dir: str, ttl: int = _TOMBSTONE_TTL) -> int`
  - `_TOMBSTONE_TTL = 180 * 86400` (int)

- [ ] **Step 1: Write the failing test** - `server/test_brain_tombstone.py`

```python
"""Tests for the git_brain tombstone helpers. Run:
    cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py
NO network."""
import os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

BR = Path(tempfile.mkdtemp(prefix="jv-tomb-")).resolve()

# write -> read back the right content, file has the right name
gb.write_tombstone(str(BR), "Ngọc Thu Phạm")
p = BR / gb.TOMBSTONE_DIR / "Ngọc Thu Phạm.json"
check("write_tombstone creates the right file", p.is_file())
ts = gb._read_tombstones(str(BR))
check("read_tombstones returns 1 entry", len(ts) == 1)
check("entry has the right name (diacritics kept)", ts and ts[0]["name"] == "Ngọc Thu Phạm")
check("entry has deleted_at as a number > 0", ts and isinstance(ts[0]["deleted_at"], int) and ts[0]["deleted_at"] > 0)

# clear -> gone
gb.clear_tombstone(str(BR), "Ngọc Thu Phạm")
check("clear_tombstone removes the file", not p.exists())
check("read after clear = empty", gb._read_tombstones(str(BR)) == [])
check("clear on a missing name does not raise", (gb.clear_tombstone(str(BR), "Không Có") or True))

# gc_tombstones: expired entries are removed, new ones kept
gb.write_tombstone(str(BR), "Cu")
old = BR / gb.TOMBSTONE_DIR / "Cu.json"
import json
d = json.loads(old.read_text(encoding="utf-8")); d["deleted_at"] = int(time.time()) - (181 * 86400)
old.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
gb.write_tombstone(str(BR), "Moi")
n = gb.gc_tombstones(str(BR))
check("gc removes exactly 1 expired entry", n == 1)
names = {t["name"] for t in gb._read_tombstones(str(BR))}
check("gc keeps the new entry, drops the old one", names == {"Moi"})

print(); print("ALL PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Run the test to make sure it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py`
Expected: FAIL/AttributeError because `git_brain` has no `write_tombstone`/`TOMBSTONE_DIR` yet.

- [ ] **Step 3: Add `import json` at the top of `git_brain.py`**

Edit the import block at the top of the file (it currently has `import os, shutil, subprocess, time`), adding `import json`:

```python
import json
import os
import shutil
import subprocess
import time
```

- [ ] **Step 4: Add the tombstone helpers** to `git_brain.py`, placed RIGHT BEFORE the `# ============================================================` line of the `BrainLock` block (around line 698):

```python
# ============================================================
# TOMBSTONE (death notice) - marks a brain DELIBERATELY deleted so the deletion propagates to every machine.
# One file per brain in <brains_dir>/.javis-tombstones/<brain name>.json. Synced with the repo
# (not in _backup_skip), NOT shown as a brain (/brains skips names starting with '.').
# ============================================================
TOMBSTONE_DIR = ".javis-tombstones"
_TOMBSTONE_TTL = 180 * 86400   # keep 180 days: longer than the trash so a machine that was offline for a long time does not resurrect it


def _tombstone_path(brains_dir: str, name: str) -> Path:
    return Path(brains_dir) / TOMBSTONE_DIR / (name + ".json")


def write_tombstone(brains_dir: str, name: str) -> None:
    """Write the tombstone for brain <name> (deliberately deleted). Atomic write (.tmp -> replace)."""
    if not name:
        return
    p = _tombstone_path(brains_dir, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"name": name, "deleted_at": int(time.time()), "host": _host_tag(), "v": 1}
    tmp = Path(str(p) + ".tmp")   # .tmp suffix -> covered by _backup_skip, never ends up in the backup
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(p))


def clear_tombstone(brains_dir: str, name: str) -> None:
    """Remove the tombstone of brain <name> (when a brain of the same name is recreated) so it is not deleted by mistake."""
    try:
        _tombstone_path(brains_dir, name).unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[tombstone clear] {name}: {e}", file=__import__('sys').stderr)


def _read_tombstones(root: str) -> List[dict]:
    """Read every tombstone in <root>/.javis-tombstones/. Skip broken files. Attach _file = file name."""
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
    """Delete expired tombstones (default 180 days). Returns the number of files deleted."""
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

- [ ] **Step 5: Run the test to make sure it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py`
Expected: `ALL PASS`

- [ ] **Step 6: Commit**

```bash
git add server/git_brain.py server/test_brain_tombstone.py
git commit -m "feat(sync): tombstone (death notice) helpers in git_brain

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Trash helpers + `_dir_newer_than` in git_brain.py

**Files:**
- Modify: `server/git_brain.py` (add right after the tombstone block from Task 1)
- Test: `server/test_brain_trash.py`

**Interfaces:**
- Produces:
  - `move_to_trash(brain_dir: str, trash_dir: str, name: str) -> Optional[str]` (returns the destination path in the trash, or None if the source is not a directory; retries 3 times for Windows file-in-use)
  - `gc_trash(trash_dir: str, days: int = 30) -> int`
  - `_dir_newer_than(root: str, ts: int) -> bool` (is any file in root newer than ts + 1s by mtime)

- [ ] **Step 1: Write the failing test** - `server/test_brain_trash.py`

```python
"""Tests for the git_brain trash helpers + _dir_newer_than. Run:
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

# move_to_trash: the source disappears, the destination shows up in the trash
dest = gb.move_to_trash(str(brain), str(TRASH), "Foo")
check("move_to_trash returns the destination path", bool(dest))
check("source is gone from brains", not brain.exists())
check("destination is in the trash and still has note", dest and Path(dest, "note.md").read_text(encoding="utf-8") == "hi")
check("move of a missing source -> None", gb.move_to_trash(str(BR / "KhongCo"), str(TRASH), "KhongCo") is None)

# _dir_newer_than
d2 = BR / "Bar"; d2.mkdir(parents=True)
f = d2 / "x.md"; f.write_text("x", encoding="utf-8")
past = int(time.time()) - 1000; future = int(time.time()) + 1000
check("_dir_newer_than: a file is newer than a past cutoff", gb._dir_newer_than(str(d2), past) is True)
check("_dir_newer_than: no file is newer than a future cutoff", gb._dir_newer_than(str(d2), future) is False)
check("_dir_newer_than: ts<=0 -> False", gb._dir_newer_than(str(d2), 0) is False)

# gc_trash: entries older than 30 days are cleaned, new ones kept
oldt = TRASH / "Old__20200101-000000"; oldt.mkdir(parents=True)
os.utime(oldt, (time.time() - 40 * 86400, time.time() - 40 * 86400))
newt = TRASH / "New__20990101-000000"; newt.mkdir(parents=True)
n = gb.gc_trash(str(TRASH), 30)
check("gc_trash cleans entries older than 30 days", not oldt.exists() and n >= 1)
check("gc_trash keeps new entries", newt.exists())

print(); print("ALL PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Run the test to make sure it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: FAIL/AttributeError (`move_to_trash` does not exist yet).

- [ ] **Step 3: Add the trash helpers** to `git_brain.py`, right after `gc_tombstones` (Task 1):

```python
# ============================================================
# LOCAL TRASH - keeps a copy of a deleted brain (30 days) for rescue. OUTSIDE the sync area (never goes to git).
# ============================================================
def move_to_trash(brain_dir: str, trash_dir: str, name: str) -> Optional[str]:
    """Move the brain folder into the trash <trash_dir>/<name>__<ts>/. Returns the destination path, or None if
    the source is not a directory. shutil.move also handles a different drive. Retries 3 times: Windows can
    hold a handle (an engine has a file in the brain open) - wait briefly and try again."""
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
    """Delete trash entries older than <days> days (by folder mtime). Returns the number of entries deleted."""
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
    """Is any file in root newer than ts by mtime (tolerance +1s)? Skips nested .git. Used for the time
    cutoff: a brain rebuilt/edited AFTER the tombstone is not deleted by mistake."""
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

- [ ] **Step 4: Run the test to make sure it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add server/git_brain.py server/test_brain_trash.py
git commit -m "feat(sync): local trash helpers + _dir_newer_than

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `_apply_tombstones` + hook into the sync flow

**Files:**
- Modify: `server/git_brain.py` (new `_apply_tombstones`; extend `sync_brains` + `_sync_brains_locked`)
- Modify: `server/main.py` (`_do_backup` passes `trash_dir`/`protected_names`, lines ~1208-1209)
- Test: `server/test_brain_delete_sync.py`

**Interfaces:**
- Consumes: `write_tombstone`, `_read_tombstones`, `move_to_trash`, `gc_trash`, `gc_tombstones`, `_dir_newer_than` (Tasks 1-2); `_git`, `_rollback_mirror`, `_host_tag`, `_BACKUP_SKIP_DIRS`.
- Produces:
  - `_apply_tombstones(brains_dir, mirror_dir, trash_dir, protected_names) -> dict` returns `{"deleted": [str], "superseded": [str], "failed": [str]}`
  - `sync_brains(..., trash_dir=None, protected_names=None)` - two added kwargs (defaults keep compatibility)
  - `rep["brains_deleted"]: list[str]` in the sync result

- [ ] **Step 1: Write the failing integration test** - `server/test_brain_delete_sync.py`

```python
"""Integration test: deleting a brain propagates to another machine via sync (local file:// remote). Run:
    cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py
Needs git in PATH. NO real network."""
import os, sys, time, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_brain as gb  # noqa: E402

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: _fails.append(name)

if not gb.has_git():
    print("SKIP: this machine has no git"); sys.exit(0)

ROOT = Path(tempfile.mkdtemp(prefix="jv-delsync-")).resolve()
REMOTE = ROOT / "remote.git"
subprocess.run(["git", "init", "--bare", str(REMOTE)], capture_output=True)
URL = "file:///" + str(REMOTE).replace("\\", "/").lstrip("/")
TOKEN = "x"  # file:// does not use a token but sync_brains requires non-empty

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

# --- Setup: A creates Foo and pushes; B pulls -> both + the remote have Foo ---
Ab, Am, At = machine("A"); Bb, Bm, Bt = machine("B")
seed(Ab, "Foo"); sync(Ab, Am, At)
sync(Bb, Bm, Bt)
check("B received Foo from the remote", (Path(Bb) / "Foo" / "note.md").exists())

# --- A deletes Foo (move trash + tombstone) then syncs ---
gb.move_to_trash(str(Path(Ab) / "Foo"), At, "Foo")
gb.write_tombstone(Ab, "Foo")
r = sync(Ab, Am, At)
check("A: sync after delete ok", r.get("ok"))
check("A: Foo is no longer in brains", not (Path(Ab) / "Foo").exists())

# --- B syncs -> Foo is deleted on B + goes to B's trash, remote is clean ---
r2 = sync(Bb, Bm, Bt)
check("B: sync ok", r2.get("ok"))
check("B: Foo was removed from brains", not (Path(Bb) / "Foo").exists())
trashed = list(Path(Bt).glob("Foo__*")) if Path(Bt).is_dir() else []
check("B: Foo is in B's trash", len(trashed) == 1 and (trashed[0] / "note.md").exists())

# --- Time cutoff: recreate a NEW Foo on A (new mtime) then sync -> NOT deleted, tombstone removed ---
seed(Ab, "Foo", "moi")
os.utime(Path(Ab) / "Foo" / "note.md", None)  # mtime = now > deleted_at
r3 = sync(Ab, Am, At)
check("A: a rebuilt Foo is NOT deleted (time cutoff)", (Path(Ab) / "Foo" / "note.md").exists())
check("A: Foo's tombstone was removed", not (Path(Ab) / gb.TOMBSTONE_DIR / "Foo.json").exists())

# --- Protection WITHOUT a tombstone: hand-delete Bar from B's brains -> sync restores it, nothing lost ---
Cb, Cm, Ct = machine("C")
seed(Cb, "Bar"); sync(Cb, Cm, Ct)   # push Bar to the remote
Db, Dm, Dt = machine("D"); sync(Db, Dm, Dt)  # D pulls Bar
import shutil as _sh; _sh.rmtree(str(Path(Db) / "Bar"))  # deleted BY HAND, NO tombstone
sync(Db, Dm, Dt)
check("Protection: Bar vanished without a tombstone -> restored", (Path(Db) / "Bar").exists())

# --- Default brain is immune: a fake tombstone pointing at 'Brain Default' -> not deleted ---
Eb, Em, Et = machine("E")
seed(Eb, "Brain Default"); gb.write_tombstone(Eb, "Brain Default")
sync(Eb, Em, Et)
check("Default brain is immune to tombstones", (Path(Eb) / "Brain Default").exists())

print(); print("ALL PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Run the test to make sure it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py`
Expected: FAIL - `sync_brains()` does not accept `trash_dir`/`protected_names` yet (TypeError) or delete propagation does not work yet.

- [ ] **Step 3: Add `_apply_tombstones`** to `git_brain.py`, placed right BEFORE `def sync_brains(` (around line 601):

```python
def _apply_tombstones(brains_dir: str, mirror_dir: str, trash_dir: str,
                      protected_names) -> dict:
    """Apply tombstones: DEFINITIVELY delete brains that have a tombstone (overriding the 'delete does not win'
    policy), only for deliberate deletions. Reads tombstones from the MIRROR after the merge (= union of all machines).
    - Time cutoff: a still-living brain that has a file with mtime > deleted_at was deliberately rebuilt/edited ->
      SKIP + remove the tombstone (superseded, propagating the removal).
    - Delete: brains_dir/<name> -> trash; mirror/<name> -> git rm -r (staged) so it gets pushed.
    - Safety: skip the default brain (protected_names) + the name must be a DIRECT child of brains_dir.
    Returns {deleted, superseded, failed}."""
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
            if bp.resolve().parent != base:   # only direct children of brains_dir
                continue
        except Exception:
            continue
        # Time cutoff: deliberately rebuilt -> keep + remove the tombstone
        if bp.is_dir() and _dir_newer_than(str(bp), deleted_at):
            _git(mirror_dir, "rm", "-f", "--", f"{TOMBSTONE_DIR}/{t['_file']}")
            try:
                (Path(brains_dir) / TOMBSTONE_DIR / t["_file"]).unlink()
            except Exception:
                pass
            changed_mirror = True
            rep["superseded"].append(name)
            continue
        # Definitive delete
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
        _git(mirror_dir, "commit", "-m", f"sync: apply tombstones ({_host_tag()})")
    return rep
```

- [ ] **Step 4: Extend `sync_brains` to accept 2 kwargs** - edit the signature (line ~601) and the `_sync_brains_locked` call (line ~613):

From:
```python
def sync_brains(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str = "main") -> dict:
```
To:
```python
def sync_brains(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str = "main",
                trash_dir: Optional[str] = None, protected_names=None) -> dict:
```
And in the body, change the call:
```python
        return _sync_brains_locked(str(brains_dir), str(mirror_dir), repo_url, token, branch)
```
to:
```python
        return _sync_brains_locked(str(brains_dir), str(mirror_dir), repo_url, token, branch,
                                   trash_dir, protected_names)
```

- [ ] **Step 5: Extend `_sync_brains_locked`** - signature (line ~620), rep init (add `brains_deleted`), GC at the start of the function, and insert `_apply_tombstones` after integrate.

Signature, from:
```python
def _sync_brains_locked(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str) -> dict:
```
to:
```python
def _sync_brains_locked(brains_dir: str, mirror_dir: str, repo_url: str, token: str, branch: str,
                        trash_dir: Optional[str] = None, protected_names=None) -> dict:
```

Right after the `rep = {...}` line (lines 621-623), add the trash_dir preparation + GC block (placed before `Path(mirror_dir).mkdir(...)`):
```python
    if not trash_dir:
        trash_dir = str(Path(mirror_dir).parent / "brain-trash")   # next to the mirror (both inside STATE_DIR)
    gc_trash(trash_dir, 30)              # clean trash older than 30 days
    gc_tombstones(brains_dir, _TOMBSTONE_TTL)   # clean tombstones older than 180 days
```
And add `"brains_deleted": []` to the `rep` dict (for example next to `"deleted_sample": []`).

Insert `_apply_tombstones` RIGHT AFTER the integrate block (after the line `changed = _changed_by_integration(mirror_dir, pre_head)`, line ~662) and BEFORE the self-heal block (line ~663 `# Tự vá...`, i.e. "Self-heal..."):
```python
        # Apply tombstones: definitively delete brains that have a tombstone (overriding 'delete does not win')
        # BEFORE _apply_back gets the chance to restore them into brains. Placing it before self-heal + _apply_back is deliberate.
        tomb = _apply_tombstones(brains_dir, mirror_dir, trash_dir, protected_names)
        if tomb["failed"]:
            _rollback_mirror(mirror_dir, pre_head)
            return {**rep, "error": "Applying tombstones failed (" + ", ".join(tomb["failed"][:2]) +
                    ") - push deferred, will retry next time"}
        if tomb["deleted"]:
            rep["brains_deleted"] = (rep["brains_deleted"] + tomb["deleted"])[:50]
```

- [ ] **Step 6: `_do_backup` passes trash_dir + protected_names** - `server/main.py` lines ~1208-1209:

From:
```python
    mirror = str(cfgmod.STATE_DIR / "brains-backup")   # separate mirror repo (avoids a nested git per brain)
    res = git_brain.sync_brains(BRAINS_DIR, mirror, b["repo_url"], b["token"], b.get("branch") or "main")
```
To:
```python
    mirror = str(cfgmod.STATE_DIR / "brains-backup")   # separate mirror repo (avoids a nested git per brain)
    res = git_brain.sync_brains(BRAINS_DIR, mirror, b["repo_url"], b["token"], b.get("branch") or "main",
                                trash_dir=str(cfgmod.STATE_DIR / "brain-trash"),
                                protected_names={_default_brain_dir().name})
```

- [ ] **Step 7: Run the integration test to make sure it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_sync.py`
Expected: `ALL PASS` (if the machine has no git it prints `SKIP`).

- [ ] **Step 8: Re-run the 2 unit tests (no regression)**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_tombstone.py && ../.venv/Scripts/python.exe test_brain_trash.py`
Expected: both `ALL PASS`.

- [ ] **Step 9: Commit**

```bash
git add server/git_brain.py server/main.py server/test_brain_delete_sync.py
git commit -m "feat(sync): _apply_tombstones - brain deletion propagates to every machine, time cutoff + protection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Rewrite the `/brains/delete` endpoint (move-to-trash + tombstone + eager sync)

**Files:**
- Modify: `server/main.py` (`/brains/delete` lines ~2037-2058; add `_DELETE_SYNC_TASKS = set()` right above the endpoint)
- Test: `server/test_brain_delete_endpoint.py`

**Interfaces:**
- Consumes: `git_brain.move_to_trash`, `git_brain.write_tombstone`, `_do_backup`, `cfgmod.STATE_DIR`, `_default_brain_dir`, `_safe_brain_name`.
- Produces: `/brains/delete` returns `{"ok": True, "name": safe, "trashed": bool}`; creates a tombstone + moves the brain into `<STATE_DIR>/brain-trash/`.

- [ ] **Step 1: Write the failing test** - `server/test_brain_delete_endpoint.py`

```python
"""Tests for the /brains/delete + /brains/new endpoints (tombstone). Run:
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
(BR / "Brain Default").mkdir(parents=True)         # default brain (cannot be deleted)
foo = BR / "Foo"; foo.mkdir(parents=True); (foo / "n.md").write_text("hi", encoding="utf-8")

# Delete Foo validly (confirm matches) -> goes to the trash + tombstone, no longer in brains
r = asyncio.run(main.delete_brain(name="Foo", confirm="Foo"))
ok = getattr(r, "body", None) is None  # only an error JSONResponse has .body; a success dict does not
check("deleting Foo returns ok", isinstance(r, dict) and r.get("ok"))
check("Foo vanishes from brains", not foo.exists())
check("Foo's tombstone is written", (BR / gb.TOMBSTONE_DIR / "Foo.json").exists())
import config as cfgmod
trash = Path(cfgmod.STATE_DIR) / "brain-trash"
check("Foo is in the trash", trash.is_dir() and len(list(trash.glob("Foo__*"))) == 1)

# Block deleting the default brain
r2 = asyncio.run(main.delete_brain(name="Brain Default", confirm="Brain Default"))
check("deleting the default brain is blocked", hasattr(r2, "status_code") and r2.status_code == 400)

# wrong confirm -> blocked
bar = BR / "Bar"; bar.mkdir(parents=True)
r3 = asyncio.run(main.delete_brain(name="Bar", confirm="sai"))
check("wrong confirm -> blocked, Bar left intact", hasattr(r3, "status_code") and bar.exists())

# /brains/new removes the tombstone of the same name (rebuilding Foo)
gb.write_tombstone(str(BR), "Foo")
r4 = asyncio.run(main.new_brain(name="Foo"))
check("recreating Foo -> removes Foo's tombstone", not (BR / gb.TOMBSTONE_DIR / "Foo.json").exists())

print(); print("ALL PASS" if not _fails else f"{len(_fails)} FAIL: {_fails}")
sys.exit(1 if _fails else 0)
```

- [ ] **Step 2: Run the test to make sure it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: FAIL - `/brains/delete` still uses `rmtree` (no tombstone/trash); `/brains/new` does not remove the tombstone yet.

- [ ] **Step 3: Add the ref-holding set + rewrite the endpoint** - `server/main.py`. Right BEFORE `@app.post("/brains/delete")` add:

```python
_DELETE_SYNC_TASKS = set()   # strong ref for the eager sync after a brain delete (keeps GC from swallowing the task)
```

Replace the ENTIRE body of `delete_brain` (keep the old guards, change the execution part):

```python
@app.post("/brains/delete")
async def delete_brain(name: str = Form(...), confirm: str = Form("")):
    """Delete a brain: MOVE it into the local trash (kept 30 days) + write a tombstone so the deletion
    propagates to every synced machine. Requires confirm == name. Blocks deleting the default brain + only inside BRAINS_DIR."""
    safe = _safe_brain_name(name)
    if not safe:
        return JSONResponse({"ok": False, "error": "Invalid brain name"}, status_code=400)
    if (confirm or "").strip() != safe:
        return JSONResponse({"ok": False, "error": "Confirmation does not match the brain name"}, status_code=400)
    root = (Path(BRAINS_DIR) / safe).resolve()
    base = Path(BRAINS_DIR).resolve()
    if root == base or base not in root.parents:
        return JSONResponse({"ok": False, "error": "Brain is outside the managed area"}, status_code=400)
    if root == _default_brain_dir().resolve():
        return JSONResponse({"ok": False, "error": "Cannot delete the default Brain"}, status_code=400)
    if not root.is_dir():
        return JSONResponse({"ok": False, "error": "Brain does not exist"}, status_code=404)
    trash_dir = str(cfgmod.STATE_DIR / "brain-trash")

    def _trash_and_mark():
        dest = git_brain.move_to_trash(str(root), trash_dir, safe)   # has a retry for Windows
        git_brain.write_tombstone(BRAINS_DIR, safe)                  # tombstone -> propagates the deletion
        return dest

    try:
        dest = await asyncio.to_thread(_trash_and_mark)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Could not delete (is the brain busy?): {e}"},
                            status_code=500)

    # Eager sync (background, best-effort): push the deletion + tombstone to the remote NOW instead of waiting for the 6h cycle.
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

- [ ] **Step 4: Run the test to make sure it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_brain_delete_endpoint.py
git commit -m "feat(brain): deleting a brain moves it to the trash + writes a tombstone + eager sync

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `/brains/new` removes the tombstone of the same name

**Files:**
- Modify: `server/main.py` (`/brains/new` lines ~2021-2034)
- Test: already covered in `server/test_brain_delete_endpoint.py` (the "/brains/new removes the tombstone" case).

**Interfaces:**
- Consumes: `git_brain.clear_tombstone`.
- Produces: `/brains/new` removes the tombstone of the name just created (prevents deleting a rebuilt brain by mistake).

- [ ] **Step 1: Edit `new_brain`** - add `clear_tombstone` after the scaffold is created successfully. From:

```python
    try:
        _ensure_brain_scaffold(root)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "name": safe, "path": str(root)}
```
To:
```python
    try:
        _ensure_brain_scaffold(root)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    git_brain.clear_tombstone(BRAINS_DIR, safe)   # rebuilt a brain of the same name -> remove the tombstone so it is not deleted by mistake
    return {"ok": True, "name": safe, "path": str(root)}
```

- [ ] **Step 2: Re-run the endpoint test (it already has this case)**

Run: `cd server && ../.venv/Scripts/python.exe test_brain_delete_endpoint.py`
Expected: `ALL PASS` (the "recreating Foo -> removes Foo's tombstone" case is green).

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat(brain): recreating a brain of the same name removes the tombstone (prevents mistaken deletion)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Delete confirmation text in the frontend + cache bump

**Files:**
- Modify: `dashboard/brains-ui.js` (`deleteBrain` function, the confirmation prompt)
- Modify: `dashboard/index.html` (`brains-ui.js?v=6 -> v=7`)

**Interfaces:** none (UI text only).

- [ ] **Step 1: Change the confirmation prompt text** in `deleteBrain` (`dashboard/brains-ui.js`). From:

```javascript
    const typed = window.prompt(
      "⚠️ XOÁ BRAIN \"" + name + "\"\n\n" +
      "Toàn bộ tri thức (sources, wiki, agents, workflows, bộ nhớ...) trong não này sẽ bị XOÁ VĨNH VIỄN, KHÔNG khôi phục được.\n\n" +
      "Gõ CHÍNH XÁC tên brain để xác nhận:"
    );
```
To:
```javascript
    const typed = window.prompt(
      "⚠️ DELETE BRAIN \"" + name + "\"\n\n" +
      "This brain will be moved to the TRASH (kept for 30 days, then deleted for good), and the deletion will be SYNCED to every other machine.\n\n" +
      "Type the brain name EXACTLY to confirm:"
    );
```

- [ ] **Step 2: Change the message after deleting** in `deleteBrain`. From:
```javascript
    alert('Đã xoá brain "' + name + '".');
```
To:
```javascript
    alert('Deleted brain "' + name + '" (moved to the trash for 30 days, deletion synced to other machines).');
```

- [ ] **Step 3: Bump the cache** - `dashboard/index.html`:
```
  <script src="/static/brains-ui.js?v=7"></script>
```

- [ ] **Step 4: Check the JS syntax**

Run: `node -e "const fs=require('fs');new Function(fs.readFileSync('dashboard/brains-ui.js','utf8'));console.log('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add dashboard/brains-ui.js dashboard/index.html
git commit -m "feat(brain): delete confirmation mentions the 30-day trash + synced deletion (bump v=7)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: CHANGELOG + VERSION + restart and verify

**Files:**
- Modify: `CHANGELOG.md` (entry `## [0.9.76] - 2026-07-18` at the top, under the format header)
- Modify: `VERSION` (`0.9.75 -> 0.9.76`)

- [ ] **Step 1: Run ALL the new tests (no regression)**

Run:
```bash
cd server && for t in test_brain_tombstone test_brain_trash test_brain_delete_sync test_brain_delete_endpoint; do echo "== $t =="; ../.venv/Scripts/python.exe $t.py || echo "FAILED $t"; done
```
Expected: each test prints `ALL PASS` (or `SKIP` if git is missing).

- [ ] **Step 2: Add the CHANGELOG 0.9.76 entry** - insert right above `## [0.9.75]`:

```markdown
## [0.9.76] - 2026-07-18
Deleting a brain now PROPAGATES to every synced machine (no more "resurrection"), and keeps a copy in a local trash for 30 days. **The server must be restarted** (sync flow + delete endpoint changed); the UI reloads itself thanks to the `?v=7` bump.
### Added
- **Synced tombstone (death notice) to propagate brain deletion**: when you delete a brain (after typing the right confirmation name), Jarvis 007 writes a small file `<BRAINS_DIR>/.javis-tombstones/<name>.json` that syncs with the repo. The new `_apply_tombstones` step in sync reads the tombstones and definitively deletes that brain on every machine, overriding the "delete does not win over the living copy" policy - BUT only for deliberate deletions. There is a time cutoff: a brain created/edited again after the deletion is not killed by mistake (the tombstone removes itself). The default brain is immune.
- **30-day local trash**: deleting a brain now MOVES the data into `<STATE_DIR>/brain-trash/<name>__<time>/` (outside the sync area, one trash per machine) instead of hard-deleting; entries older than 30 days are cleaned at the start of each sync. The delete confirmation says this clearly. Restore by hand (move the folder from the trash back to `brains/`).
### Fixed
- **A deleted brain was "resurrected" on sync/update**: the old sync policy deliberately did not let a deletion win over the living copy (to prevent data loss), so a brain deleted on this machine was pushed back by another machine/the remote. Now a deliberate deletion propagates through the tombstone; the general data-loss shield stays intact for every case WITHOUT a tombstone (a folder vanishing because a volume is not mounted, an engine writing halfway...).
```

- [ ] **Step 3: Bump VERSION**

Set `VERSION` = `0.9.76`.

- [ ] **Step 4: Commit + push**

```bash
git add CHANGELOG.md VERSION
git commit -m "chore(release): 0.9.76 - brain deletion propagates to every machine + 30-day trash

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 5: Restart + verify live**

Run: `wscript //nologo start-javis.vbs` (wait ~8s) then check the server is up (`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7777/` = 200) and the log has no traceback (`tail -15 server/javis.log`).
Expected: the server comes up with a new PID, no errors. Confirm `curl -s http://127.0.0.1:7777/static/index.html | grep brains-ui` = `?v=7`.

---

## Self-Review

**Spec coverage:**
- Tombstone store (spec 4.1) -> Task 1. ✓
- Trash + GC (spec 4.2) -> Task 2 (+ GC called in Task 3). ✓
- `_apply_tombstones` + sync order (spec 4.3, 5.2, 5.3) -> Task 3. ✓
- Delete flow: move-to-trash + tombstone + eager sync + confirm (spec 5.1) -> Task 4 (backend) + Task 6 (confirm UI). ✓
- `/brains/new` removes the tombstone (spec 5.1 time cutoff layer 2) -> Task 5. ✓
- Safety guards (spec 6): direct child of brains_dir, default brain immune, time cutoff, no half-done push -> Task 3 (`_apply_tombstones` + failed->rollback). ✓
- Tests a-f (spec 7) -> Task 1/2 (unit), Task 3 (delete propagation, time cutoff, protection without a tombstone, default immune), Task 4 (endpoint; trash cleanup is covered in Task 2). ✓
- 180-day tombstone retention (spec 3, 8) -> `gc_tombstones` (Task 1) called in Task 3 Step 5. ✓

**Placeholder scan:** No TBD/TODO; every step has real code/commands + concrete expectations. ✓

**Type consistency:** `write_tombstone/clear_tombstone/_read_tombstones/gc_tombstones/move_to_trash/gc_trash/_dir_newer_than/_apply_tombstones` are declared in Tasks 1-3 and used with the right names/signatures in Tasks 3-5. `sync_brains(..., trash_dir, protected_names)` is declared in Task 3 Step 4, used in Task 3 Step 6 (`_do_backup`) and the test. `rep["brains_deleted"]` is declared + assigned in Task 3 Step 5. ✓
