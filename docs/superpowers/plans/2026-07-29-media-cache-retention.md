# Media is a cache zone - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat each brain's `attachments/` and `inbox/` as a cache zone: not in git, expiring automatically after 30 days or when the total exceeds 300MB, and where an image is gone, show a gray box "Image expired" instead of a broken icon.

**Architecture:** A new module `server/media_gc.py` separates the decision part (the pure function `plan_deletions`, tested without touching the disk) from the disk-touching part (`scan` + `sweep`, using `os.scandir`). The background scheduler calls `sweep` through `asyncio.to_thread` every 6 hours. `server/git_brain.py` gains gitignore lines and a one-time step that removes the media from the index for old brains. The dashboard catches the `error` event of `<img>` and replaces it with a gray box.

**Tech Stack:** Python stdlib (os.scandir, subprocess/git), FastAPI (existing scheduler), plain JavaScript (the dashboard has no framework).

Spec: [docs/superpowers/specs/2026-07-29-media-cache-retention-design.md](../specs/2026-07-29-media-cache-retention-design.md)

## Global Constraints

- **Never use the em dash character (U+2014)** in any file: code, comments, docstrings, CHANGELOG, commit messages. Use the hyphen `-`.
- **Strings shown to the user must be proper, complete text, never ASCII-stripped Vietnamese**, even when written in backend code. This mistake was made twice before (`file-editor.js`, `usage_index.py`). The only string the user sees in this plan is **"Image expired"**.
- Comments in `dashboard/chat-render.js` and `dashboard/style.css` are written in plain ASCII (no diacritics), matching the existing style of those two files. Only displayed strings may use non-ASCII characters.
- Tests run with the project's `.venv`: always call `python tests/run.py <name>` (the script finds `.venv` itself), do NOT call `python tests/python/test_x.py` with the system python (fastapi/yaml are missing).
- Disk scanning must use `os.scandir`, not `glob`. `glob(...)[:N]` walks the whole tree before cutting, so it is not a real cap; and a synchronous scan inside the event loop once made the container unhealthy to the point that Traefik removed the route.
- Defaults are fixed: `max_age_days = 30`, `max_mb = 300`, `enabled = true`.
- Do not write Google Drive upload code in this plan. Do not rewrite the brain's git history.

---

### Task 1: `plan_deletions` - the decision part, a pure function

**Files:**
- Create: `server/media_gc.py`
- Test: `tests/python/test_media_gc.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `media_gc.plan_deletions(entries, now, max_age_days, max_mb) -> list[str]`.
  `entries` is a `list[tuple[str, int, float]]` of `(path, size_bytes, mtime)`.
  `now` is a `float` (epoch seconds). `max_age_days` and `max_mb` are `int`.
  Returns the list of `path` in exactly the order to delete.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_media_gc.py`:

```python
"""Test media_gc (cleans expired media in a brain's cache zone). Run by hand / CI:

    python tests/run.py media_gc

plan_deletions is a PURE function, so most tests do not touch the disk; the scan/delete part uses a temp dir.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - loads server/ into sys.path
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
    """One entry (path, size, mtime) whose mtime is exactly tuoi_ngay days before NOW."""
    return (path, int(mb * MB), NOW - tuoi_ngay * DAY)


# ---- 1. Still fresh and total under the cap: delete nothing ----
r = media_gc.plan_deletions([muc("a.png", 1, 1), muc("b.png", 2, 5)], NOW, 30, 300)
check("fresh + under cap -> delete nothing", r == [])

# ---- 2. Past the age limit gets deleted, within the limit is kept ----
r = media_gc.plan_deletions([muc("cu.png", 1, 40), muc("moi.png", 1, 5)], NOW, 30, 300)
check("past age limit -> delete only the old file", r == ["cu.png"])

# ---- 3. Over the cap even though every file is within the limit: delete oldest to newest, stop in time ----
r = media_gc.plan_deletions(
    [muc("x3.png", 200, 3), muc("x2.png", 200, 2), muc("x1.png", 200, 1)], NOW, 30, 300)
check("over cap -> delete oldest first, stop when enough", r == ["x3.png", "x2.png"])

# ---- 4. Both past the limit and over the cap: add up, no double counting ----
r = media_gc.plan_deletions(
    [muc("cu.png", 10, 40), muc("y2.png", 200, 3), muc("y1.png", 200, 1)], NOW, 30, 300)
check("past limit + over cap -> add up, no duplicates",
      r == ["cu.png", "y2.png"] and len(r) == len(set(r)))

# ---- 5. .md files are never deleted ----
r = media_gc.plan_deletions([muc("ghi-chu.md", 400, 99), muc("anh.png", 1, 40)], NOW, 30, 300)
check("spare .md files", r == ["anh.png"])

# ---- 6. Turn each rule off with 0 / a negative number ----
check("max_age_days=0 -> age rule off",
      media_gc.plan_deletions([muc("cu.png", 1, 999)], NOW, 0, 300) == [])
check("max_mb=0 -> cap rule off",
      media_gc.plan_deletions([muc("to.png", 999, 1)], NOW, 30, 0) == [])
check("both off -> delete nothing",
      media_gc.plan_deletions([muc("cu-va-to.png", 999, 999)], NOW, -1, -1) == [])

# ---- 7. Empty list ----
check("empty list", media_gc.plan_deletions([], NOW, 30, 300) == [])

print()
if _fails:
    print(f"{len(_fails)} tests RED: " + ", ".join(_fails))
    sys.exit(1)
print("All media_gc tests green.")
```

- [ ] **Step 2: Run the test to make sure it is red**

```bash
python tests/run.py media_gc -v
```

Expected: RED with `ModuleNotFoundError: No module named 'media_gc'`.

- [ ] **Step 3: Write `server/media_gc.py`, just enough to turn the test green**

```python
"""
media_gc.py - Cleans a brain's media cache zone.

Why it exists: images Jarvis 007 generates itself (image_gen.py:202) and files the user sends via Telegram
(main.py:6242) land in `<brain>/attachments/` and `<brain>/inbox/` and then stay there forever.
Nobody cleans them, and until now they were also committed into the brain's git, so deleting the files
did not give the space back either. Decision: those two folders are a CACHE ZONE, not knowledge. Knowledge
is the .md files. Anything in them may vanish and the brain stays intact.

Split into two layers so it can be tested:
  - plan_deletions: PURE. Takes a ready list of (path, size, mtime), returns the list to delete.
    Touches no disk and reads no clock -> tests need no fixtures.
  - scan / media_dirs / sweep: touch the disk. Use os.scandir and must be called through asyncio.to_thread.

Stdlib-only.
"""
from __future__ import annotations

import os
import re
import time


def plan_deletions(entries, now, max_age_days, max_mb):
    """Decide which files must be deleted. PURE FUNCTION.

    entries      : list[(path, size_bytes, mtime)] - every file in ONE brain's cache zone.
    now          : the reference point in time (time.time()).
    max_age_days : files older than this many days are deleted. <= 0 = age rule off.
    max_mb       : size cap of the cache zone. <= 0 = cap rule off.

    Returns the list of paths in EXACTLY the order to delete: the expired group first, then the group cut by the cap (oldest to newest).

    .md files are never deleted: the cache zone may get a note strayed into it, and a note is knowledge.
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
        # The cap is a safety valve for the case of generating hundreds of images in one day: the
        # age rule cannot save us then. Delete from the OLDEST and stop as soon as we are under the cap.
        for t in sorted(con_lai, key=lambda x: x[2]):
            if tong <= tran:
                break
            xoa.append(t)
            tong -= t[1]
    return [t[0] for t in xoa]
```

- [ ] **Step 4: Run the test to make it green**

```bash
python tests/run.py media_gc -v
```

Expected: `1/1` green, and the output has all 9 `ok` lines.

- [ ] **Step 5: Commit**

```bash
git add server/media_gc.py tests/python/test_media_gc.py
git commit -m "media_gc: pure function plan_deletions (age limit + size cap)"
```

---

### Task 2: Disk scan and real deletion + config defaults

**Files:**
- Modify: `server/media_gc.py` (add `media_dirs`, `scan`, `sweep` after `plan_deletions`)
- Modify: `server/config.py:83` (add the `media` key to `_DEFAULT`, right after the `image` key)
- Test: `tests/python/test_media_gc.py` (append part 8 at the end, BEFORE the final `print()` block)

**Interfaces:**
- Consumes: `media_gc.plan_deletions` from Task 1.
- Produces:
  - `media_gc.media_dirs(brain_root: str) -> list[str]` - absolute paths of the top-level cache zone folders.
  - `media_gc.scan(dirs: list[str]) -> list[tuple[str, int, float]]`.
  - `media_gc.sweep(brain_root: str, max_age_days: int = 30, max_mb: int = 300, now: float | None = None) -> dict` returns `{"files": int, "bytes": int}`.
  - `config._DEFAULT["media"] == {"enabled": True, "max_age_days": 30, "max_mb": 300}`.

- [ ] **Step 1: Write the failing test**

Insert into `tests/python/test_media_gc.py` RIGHT BEFORE the `print()` line of the closing block at the end of the file:

```python
# ---- 8. Disk scan + real deletion (temp dir) ----
import os        # noqa: E402
import tempfile  # noqa: E402

import config    # noqa: E402

_brain = tempfile.mkdtemp(prefix="javis-mediagc-")


def _tao(rel, mb, tuoi_ngay):
    """Create a real file with the wanted size and mtime."""
    p = os.path.join(_brain, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\0" * int(mb * MB))
    t = time.time() - tuoi_ngay * DAY
    os.utime(p, (t, t))
    return p


_cu = _tao("05 - attachments/cu.png", 0.001, 40)          # name variant with a numeric prefix
_moi = _tao("05 - attachments/moi.png", 0.001, 1)
_note = _tao("05 - attachments/ghi-chu.md", 0.001, 999)
_tg = _tao("inbox/telegram/photo_1.jpg", 0.001, 40)
_wiki = _tao("Wiki/khai-niem.md", 0.001, 999)             # outside the cache zone -> must not be touched

d = media_gc.media_dirs(_brain)
check("media_dirs picks up exactly 2 folders", len(d) == 2 and any("attachments" in x for x in d)
      and any(x.endswith("inbox") for x in d))
check("media_dirs skips other folders", not any("Wiki" in x for x in d))

check("scan walks recursively", len(media_gc.scan(d)) == 4)

kq = media_gc.sweep(_brain, max_age_days=30, max_mb=300)
check("sweep deletes the right number of files", kq["files"] == 2)
check("sweep returns the bytes cleaned", kq["bytes"] > 0)
check("sweep deletes expired files", not os.path.exists(_cu) and not os.path.exists(_tg))
check("sweep keeps fresh files", os.path.exists(_moi))
check("sweep keeps .md files in the cache zone", os.path.exists(_note))
check("sweep does not touch files outside the cache zone", os.path.exists(_wiki))

kq2 = media_gc.sweep(_brain, max_age_days=30, max_mb=300)
check("sweep rerun deletes nothing more", kq2["files"] == 0)

check("sweep on a nonexistent brain does not blow up",
      media_gc.sweep(os.path.join(_brain, "khong-co-that")) == {"files": 0, "bytes": 0})

# ---- 9. Config defaults ----
_m = config._DEFAULT.get("media") or {}
check("config default media.enabled", _m.get("enabled") is True)
check("config default 30 days", _m.get("max_age_days") == 30)
check("config default 300MB cap", _m.get("max_mb") == 300)
```

Add `import time` to the import block at the TOP of the file (next to `import sys`).

- [ ] **Step 2: Run the test to make sure it is red**

```bash
python tests/run.py media_gc -v
```

Expected: RED with `AttributeError: module 'media_gc' has no attribute 'media_dirs'`.

- [ ] **Step 3: Add the disk-touching part to `server/media_gc.py`**

Append at the end of the file, after `plan_deletions`:

```python
# Same rule for recognizing the attachments folder as image_gen.py:40 and main.py:1931: the name can be
# "attachments", "Attachments", or have a numeric prefix like "05 - attachments".
_ATTACH_RE = r"^(\d+\s*[-_.]\s*)?attachments$"


def media_dirs(brain_root):
    """The top-level CACHE ZONE folders of the brain: attachments (every name variant) + inbox."""
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
    """Walk the folders recursively -> list[(path, size, mtime)].

    Uses os.scandir, NOT glob: glob walks the whole tree before cutting so it has no real cap,
    and the stat that comes with a scandir entry is much cheaper than a separate stat per file. An error on
    a single file (locked, just deleted, missing permission) is skipped instead of breaking the whole scan.
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
    """Clean the cache zone of ONE brain. BLOCKING because it touches the disk - must be called through asyncio.to_thread.

    Returns {"files": number of files deleted, "bytes": total bytes freed}.
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
            continue      # file was just deleted by hand or is locked -> clean it next time
        n += 1
        b += co.get(p, 0)
    return {"files": n, "bytes": b}
```

- [ ] **Step 4: Add the defaults to `server/config.py`**

Insert RIGHT AFTER the line `"image": {"strip_c2pa": False},` (currently line 83):

```python
    # The brain's media cache zone: attachments/ + inbox/. Images are RAW MATERIAL passing through, not
    # knowledge - reading them and distilling into a .md is enough, so they expire on their own instead of
    # staying forever and bloating the VPS disk. To keep images long-term, connect an external store (Drive), do not let Jarvis 007 hoard them.
    # max_age_days / max_mb <= 0 = turn the matching rule off. enabled=False = clean nothing at all.
    "media": {"enabled": True, "max_age_days": 30, "max_mb": 300},
```

- [ ] **Step 5: Run the test to make it green**

```bash
python tests/run.py media_gc -v
```

Expected: `1/1` green, with all the `ok` lines of parts 8 and 9.

- [ ] **Step 6: Commit**

```bash
git add server/media_gc.py server/config.py tests/python/test_media_gc.py
git commit -m "media_gc: scandir scan + real deletion + defaults of 30 days/300MB"
```

---

### Task 3: Hook the janitor into the background scheduler

**Files:**
- Modify: `server/main.py` (import `media_gc`; add the timestamp variable; add item 6 to `_scheduler_loop` at `server/main.py:4261-4266`)

**Interfaces:**
- Consumes: `media_gc.sweep(brain_root, max_age_days, max_mb)` from Task 2; `config._DEFAULT["media"]` from Task 2.
- Produces: no new API. Effect: every 6 hours, every brain in `loop_feature.scheduler_brains()` gets its cache zone cleaned.

- [ ] **Step 1: Add the import**

Find the server-module import block at the top of `server/main.py` (where `import image_gen` already is) and add next to it:

```python
import media_gc
```

- [ ] **Step 2: Add the timestamp variable**

Place it RIGHT BEFORE the line `async def _start_scheduler():` (currently `server/main.py:4173`):

```python
# Timestamp of the most recent media cleanup. A 1-element list so the nested function inside _scheduler_loop
# can assign it without needing `global`. Initialized to 0.0 -> runs right away on the first tick after the server is up.
_MEDIA_GC_LAST = [0.0]
```

- [ ] **Step 3: Add item 6 to the loop**

Insert RIGHT AFTER the `# 5) Jarvis 007 index` block (ending at `server/main.py:4266`), still inside the loop's outermost `try`:

```python
                # 6) Clean expired media: attachments/ + inbox/ are a CACHE ZONE, not
                #    knowledge. Its own 6-HOUR cadence (not the loop's 30s tick) because this is
                #    a disk scan, and to_thread because a synchronous scan inside the event loop once made the container
                #    unhealthy to the point that Traefik removed the route. Set the timestamp BEFORE running: if it breaks,
                #    wait for the next round instead of spinning hot.
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
                                    print(f"[media gc] {_mb}: cleaned {kq['files']} files, "
                                          f"{kq['bytes'] // (1024 * 1024)}MB")
                except Exception as me:
                    print(f"[media gc] {type(me).__name__}: {me}", file=__import__('sys').stderr)
```

- [ ] **Step 4: Check the syntax and that the server starts**

```bash
python -c "import ast,sys; ast.parse(open('server/main.py',encoding='utf-8').read()); print('syntax ok')"
```

Expected: prints `syntax ok`.

Then run the whole Python test suite to make sure nothing broke:

```bash
python tests/run.py --py
```

Expected: all green (test count equals the previous count plus 1).

- [ ] **Step 5: Commit**

```bash
git add server/main.py
git commit -m "Scheduler: clean the media cache zone every 6 hours via to_thread"
```

---

### Task 4: Block git - gitignore + one-time index removal

**Files:**
- Modify: `server/git_brain.py:19-27` (add `import re`)
- Modify: `server/git_brain.py:63-74` (add lines to `_GITIGNORE`)
- Modify: `server/git_brain.py` (add the function `untrack_media` after `_ensure_gitignore_lines`)
- Modify: `server/git_brain.py:133-148` (call `untrack_media` in the old-brain branch of `ensure_git_repo`)
- Test: `tests/python/test_media_gc.py` (append part 10)

**Interfaces:**
- Consumes: nothing from the previous tasks.
- Produces: `git_brain.untrack_media(root: str) -> int` returns the number of folders removed from the index.

- [ ] **Step 1: Write the failing test**

Insert into `tests/python/test_media_gc.py` RIGHT BEFORE the closing `print()` block:

```python
# ---- 10. Gitignore + index removal ----
import subprocess   # noqa: E402

import git_brain    # noqa: E402

for _dong in ("attachments/", "Attachments/", "*attachments/", "*Attachments/", "inbox/"):
    check(f"gitignore has line {_dong}", _dong + "\n" in git_brain._GITIGNORE)

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
    check("seed tracks the media", "attachments/a.png" in _truoc)

    n = git_brain.untrack_media(_repo)
    _sau = (_g("ls-files").stdout or "")
    check("untrack_media removes attachments", "attachments/a.png" not in _sau)
    check("untrack_media removes inbox", "inbox/telegram/b.jpg" not in _sau)
    check("untrack_media does not touch other files", "Wiki/note.md" in _sau)
    check("untrack_media keeps files on disk",
          os.path.exists(os.path.join(_repo, "attachments", "a.png")))
    check("untrack_media counts folders correctly", n == 2)

    _g("commit", "-m", "untrack")
    check("untrack_media rerun does nothing", git_brain.untrack_media(_repo) == 0)

    # An old brain already has its own .gitignore: merge in the new lines, do NOT lose the user's own lines.
    with open(os.path.join(_repo, ".gitignore"), "w", encoding="utf-8") as _f:
        _f.write("# the user's own rule\nrac-cua-toi/\n")
    git_brain._ensure_gitignore_lines(_repo)
    with open(os.path.join(_repo, ".gitignore"), encoding="utf-8") as _f:
        _gi = _f.read()
    check("gitignore merge keeps the old line", "rac-cua-toi/" in _gi)
    check("gitignore merge adds the media lines", "attachments/" in _gi and "inbox/" in _gi)
else:
    print("SKIPPING git tests: no git in PATH on this machine")
```

- [ ] **Step 2: Run the test to make sure it is red**

```bash
python tests/run.py media_gc -v
```

Expected: RED on the `gitignore has line ...` lines and `AttributeError: ... 'untrack_media'`.

- [ ] **Step 3: Add `import re` to `server/git_brain.py`**

In the import block (lines 21-27), add `re` keeping alphabetical order:

```python
import json
import os
import re
import shutil
import subprocess
import time
```

- [ ] **Step 4: Add the lines to `_GITIGNORE`**

Change the constant `_GITIGNORE` (lines 63-74) to:

```python
_GITIGNORE = (
    "# Jarvis 007 brain - do NOT commit: locks, raw logs (may contain secrets), background logs.\n"
    "# Git only versions DISTILLED KNOWLEDGE (facts/wiki/skills/MEMORY.md) → clean, safe undo.\n"
    ".javis-learn.lock\n"
    "Javis/learn-staging/\n"
    "Javis/learn-log/\n"
    "Javis/loop-log/\n"
    "Javis/skill-usage.json\n"
    "memory/conversations/\n"
    "Memory/conversations/\n"
    "*.tmp\n"
    "# Media cache zone: generated images + files the user uploads. It is RAW MATERIAL passing through, not\n"
    "# knowledge, and media_gc.py cleans it on a schedule. If committed, every image is a blob staying\n"
    "# forever in git history - deleting the file later does not give the space back.\n"
    "# Four attachments lines because the folder name can be attachments / Attachments / 05 - attachments\n"
    "# (git is case-sensitive on Linux, and the * covers any numeric prefix).\n"
    "attachments/\n"
    "Attachments/\n"
    "*attachments/\n"
    "*Attachments/\n"
    "inbox/\n"
)
```

- [ ] **Step 5: Add the function `untrack_media`**

Insert right after the function `_ensure_gitignore_lines` (ending around line 104), before `def ensure_git_repo`:

```python
# Same rule for recognizing the attachments folder as media_gc.py and image_gen.py:40.
_ATTACH_RE = r"^(\d+\s*[-_.]\s*)?attachments$"


def untrack_media(root: str) -> int:
    """Remove attachments/ + inbox/ from the git INDEX, KEEPING the files on disk.

    Why it is needed: .gitignore has no effect on files git was ALREADY tracking, so an old brain
    (that already committed images) keeps committing new images even though the ignore template is fixed. It must be removed once.

    Accepted consequence: the next commit records "images deleted", and pulling the brain onto another machine
    does not bring the old images along. The old blobs stay in history - this plan does NOT rewrite history.

    Idempotent: a brain that never committed media has nothing to remove, returns 0.
    Returns the number of folders actually removed.
    """
    n = 0
    try:
        for name in sorted(os.listdir(root)):
            if not os.path.isdir(os.path.join(root, name)):
                continue
            ten = name.strip()
            if ten.lower() != "inbox" and not re.match(_ATTACH_RE, ten, re.IGNORECASE):
                continue
            # Ask with ls-files first: if nothing is tracked, skip git rm, and more
            # importantly avoid miscounting a folder that is already clean (keeps it idempotent).
            r = _git(root, "ls-files", "--", name)
            if not (r.stdout or "").strip():
                continue
            _git(root, "rm", "-r", "--cached", "--ignore-unmatch", "-q", "--", name)
            n += 1
    except Exception as e:
        print(f"[untrack_media] {root}: {type(e).__name__}: {e}", file=__import__('sys').stderr)
    return n
```

- [ ] **Step 6: Call `untrack_media` in the old-brain branch**

In `ensure_git_repo`, change the commit block (currently lines 133-148) to:

```python
        changed = _ensure_gitignore_lines(root)
        dirty = bool((_git(root, "status", "--porcelain", "--", ".gitignore").stdout or "").strip())
        # untrack_media must sit INSIDE the lock and RIGHT BEFORE commit_paths: commit_paths runs
        # `git commit` = commits the WHOLE INDEX, so the index removal may only be staged when someone is sure to
        # commit it right after. If the lock is not acquired, skip both; the next click heals it.
        con_theo_doi = bool((_git(root, "ls-files", "--", "inbox").stdout or "").strip())
        if changed or dirty or con_theo_doi:
            with BrainLock(root, timeout=1.0) as lk:
                if getattr(lk, "acquired", False):
                    untrack_media(root)
                    commit_paths(root, [".gitignore"], "chore: update brain .gitignore")
        return {"ok": True, "created": False}
```

Note the condition: the added `ls-files -- inbox` check means a brain that already has the right `.gitignore` (so `changed` and `dirty` are both False) but is still tracking media gets cleaned this round too. Without it, an old brain would never have its index cleaned.

- [ ] **Step 7: Run the test to make it green**

```bash
python tests/run.py media_gc -v
```

Expected: `1/1` green, with all the `ok` lines of part 10.

Then run the tests that touch git_brain to make sure nothing broke:

```bash
python tests/run.py --py
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add server/git_brain.py tests/python/test_media_gc.py
git commit -m "git_brain: media no longer goes to git, one-time index removal for old brains"
```

---

### Task 5: Gray "Image expired" box on the dashboard

**Files:**
- Modify: `dashboard/chat-render.js:171-177` (`imgHtml`)
- Modify: `dashboard/style.css:1267` (add `.chat-img-gone` right after `.chat-img`)

**Interfaces:**
- Consumes: nothing from the previous tasks (pure frontend).
- Produces: the global function `window.jvImgGone(el)` and the CSS class `.chat-img-gone`.

**Background:** `/files/raw` returns 404 when the file is gone (`server/main.py:2864`), so `<img>` fires the `error` event. Catching it at the `onerror` level also covers the case of the user deleting or renaming the file by hand, not just the janitor. The project sets no Content-Security-Policy, so the inline `onerror` attribute works.

- [ ] **Step 1: Edit `imgHtml` in `dashboard/chat-render.js`**

Replace the function `imgHtml` (lines 171-177) with:

```js
  // Image failed to load (404 because it expired in the cache zone, was deleted by hand, or renamed)
  // -> replace it with a gray box with text, instead of leaving a broken icon. Attached to window because
  // the inline onerror string runs in the global scope and cannot see variables inside this IIFE.
  window.jvImgGone = function (el) {
    var box = document.createElement("span");
    box.className = "chat-img-gone";
    box.textContent = "Image expired";
    el.replaceWith(box);
  };
  function imgHtml(u, alt, rawpath) {
    var img = '<img class="chat-img" src="' + esc(u) + '" alt="' + esc(alt || "") + '"' +
      ' loading="lazy" onerror="jvImgGone(this)">';
    // Image in the vault: clicking opens its LOCATION in Files (instead of downloading the raw image); still shows the image inline.
    if (rawpath && isVaultRel(rawpath)) return '<a ' + vaultLoc(rawpath) + ">" + img + "</a>";
    var h = safeHref(u);
    return h ? '<a href="' + esc(h) + '" target="_blank" rel="noopener">' + img + "</a>" : img;
  }
```

- [ ] **Step 2: Add the CSS**

Insert right after the line `.chat-img { ... }` (`dashboard/style.css:1267`):

```css
/* Image was swept out of the cache zone (media_gc) or deleted by hand. The dashed border makes it
   obvious at a glance that this is a text placeholder and not a real image tag. */
.chat-img-gone { display: inline-block; margin: 6px 0; padding: 10px 14px; border-radius: 8px;
  border: 1px dashed var(--border); background: var(--bg3); color: var(--text3); font-size: 13px; }
```

- [ ] **Step 3: Manual check**

Restart the local server (port 7777) then:

1. Open a chat with an image embedded from `attachments/`.
2. Delete that image file by hand in the vault.
3. Reload the page and scroll to that message.

Expected: where the image was is a dashed-border gray box reading **"Image expired"**, NOT the browser's broken-image icon.

No need to edit `?v=` in `dashboard/index.html`: `server/main.py:454` rewrites the `?v` query of every `.js`/`.css` file according to VERSION on its own, so bumping VERSION in Task 6 is enough to bust the browser cache.

- [ ] **Step 4: Commit**

```bash
git add dashboard/chat-render.js dashboard/style.css
git commit -m "Dashboard: an expired image shows a gray box instead of a broken icon"
```

---

### Task 6: Run the whole test suite, cut a version

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: a version pushed to `origin/main`.

- [ ] **Step 1: Run the whole test suite**

```bash
python tests/run.py
```

Expected: all green, including `test_media_gc.py`. If any test is red, STOP, fix, rerun - do not bump the version while anything is red.

- [ ] **Step 2: Get the next version number from the REMOTE**

```bash
git fetch origin && git show origin/main:VERSION
```

New number = the number just printed plus 1 on the last digit. It must come from `origin/main`, NOT the local `VERSION` file: a cloud agent's PR may already be merged on GitHub, so the remote is often ahead of local.

- [ ] **Step 3: Write VERSION and CHANGELOG**

Write the new number into `VERSION` (one line, no extra newline).

Insert a new block into `CHANGELOG.md` right under the `Format: ...` line, following the shape of earlier versions:

```markdown
## [x.y.z] - 2026-07-29
Images and uploaded files no longer stay in the brain forever. They are raw material passing through; reading them and distilling a note is enough.
### Improvements
- **Media no longer goes to git**: `attachments/` and `inbox/` now sit outside the brain's git. Before, every image was a blob staying forever in history, deleting the file later did not give the space back, and the mirror even doubled it. An old brain that already committed them gets them removed from the index once; the history already written is kept as is, not rewritten.
- **Automatic cleanup of the media cache zone**: images older than 30 days are deleted automatically, and if the total exceeds 300MB, cleanup goes from oldest to newest until it is under the cap. Adjustable through the `media` key in `settings.json`, set `enabled: false` to stop cleaning. `.md` notes that strayed into those two folders are spared.
- **Expired images show a gray box**: where an image is gone, a dashed-border box reading "Image expired" shows instead of a broken icon, correct even when the file was deleted or renamed by hand.
```

Replace `x.y.z` with the real number from Step 2.

- [ ] **Step 4: Commit and push**

```bash
git add VERSION CHANGELOG.md && git commit -m "Media is a cache zone: not in git, expires at 30 days/300MB (x.y.z)" && git push origin main
```

Replace `x.y.z` with the real number.

- [ ] **Step 5: Confirm it landed**

```bash
git fetch origin && git log origin/main --oneline -1
```

Expected: the commit just pushed is at the top of `origin/main`.

---

## Out of scope for this plan

- Pushing media to Google Drive before deleting. Later, insert a step right before `os.remove` in `media_gc.sweep`.
- Rewriting the brain's git history to reclaim the old blobs' space. Decided to leave it.
- Moving media outside the vault, hermes style. The path `![](attachments/x.png)` stays the same, so `/files/raw`, `console.js`, `file-editor.js` need no changes.
- A UI for editing `max_age_days` / `max_mb` on the Settings page. For now, edit `settings.json` directly.
