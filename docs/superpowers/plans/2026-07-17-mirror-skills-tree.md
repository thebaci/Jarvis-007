# B4: recursive mirror_skills + signature gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let skills that carry `references/`/`scripts/` reach the path Claude Code loads natively, and cut the `mirror_skills` cost from ~52ms to ~6ms per chat turn.

**Architecture:** Add a two-tier gate to `mirror_skills`. Tier one computes a signature from `stat` ONLY (no byte is read) and compares it with an in-memory cache keyed by root; if nothing changed it returns immediately - this is the path 99% of chat turns hit. Tier two, only when the signature changed, copies the whole tree recursively. The mirror has its own lock, taken non-blocking, so it never queues up and blocks the event loop and never forms a cycle with `_LOCK`.

**Tech Stack:** Python 3.12, stdlib (`os.scandir`, `hashlib`, `shutil`, `threading`, `pathlib`). No pytest.

## Global Constraints

- Full spec: `docs/superpowers/specs/2026-07-17-mirror-skills-tree-design.md`. Read the "Risks" section before starting.
- **Language:** every comment, docstring and error message is written in English.
- **NEVER use the em dash character (U+2014)** in any file. Use "-". Hard user rule.
- **Do NOT use pytest.** Tests are plain scripts that run directly, using `check(name, cond)` + `_fails` + `sys.exit(1)`. Standard template: `server/test_loop_ambient.py:23-30` and `:117-120`.
- **Do NOT take `test_plugins_host.py` as a template** - it uses bare asserts, so it stops at the FIRST failure.
- **Test command:** `cd server && ../.venv/Scripts/python.exe test_system_sync.py`. The venv is at the repo ROOT, NOT `server/.venv`.
- **New tests must be named `server/test_*.py`** so the CI glob (`.github/workflows/ci.yml:29-39`) picks them up.
- **Test preamble, order is load-bearing** (env BEFORE import):
  ```python
  os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-synctest-"))
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import system_sync  # noqa: E402
  ```
- **`mirror_skills` must NEVER take `_LOCK`** (`system_sync.py:280`). It is called from `sync_brain` WHILE `_LOCK` is held, and `threading.Lock` is not reentrant, so it would deadlock on the very first chat turn.
- **`skill_hash` must NOT change** signature or semantics. `sync_brain`, `LEGACY_HASHES` and the `--hash` CLI depend on its exact output. Only STOP USING it inside `mirror_skills`.
- Tests build a fake brain in `tempfile.mkdtemp`. NEVER touch the real `brains/`.
- Leave no stray files/folders outside temp.

---

## File Structure

**Create:**
- `server/test_system_sync.py` - tests for `mirror_skills`. Today NO test in the repo touches this function.

**Modify:**
- `server/system_sync.py` - add `import os`; add `_mirror_signature`, `_MIRROR_SIG`, `_MIRROR_LOCKS`; rewrite the body of `mirror_skills` (currently at lines 235-264).

---

### Task 1: Build test_system_sync.py, pin the current behavior and the new requirements

**Files:**
- Create: `server/test_system_sync.py`

**Interfaces:**
- Consumes: `system_sync.mirror_skills(root) -> None` (already exists, `system_sync.py:235`).
- Produces: nothing. Task 2 turns this test from red to green.

- [ ] **Step 1: Write the test**

Create `server/test_system_sync.py`:

```python
"""Test mirror_skills: copy the whole subtree + the stat signature gate. Run by hand / CI:

    cd server && ../.venv/Scripts/python.exe test_system_sync.py

No pytest needed, no network. Builds a fake brain in a temp directory.
Covers: copying subfolders (references/ scripts/), a sibling side file changing so the mirror
picks it up (PRE-EXISTING bug), skipping .disabled, add-only never deleting stray files, no
change means NO re-copy at all and NO file content read, two concurrent threads not hanging,
binary files passing through intact.
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
    """Fake brain: 1 skill with a subtree + 1 disabled skill. Returns (root, skill_dir, mirror_dir)."""
    root = Path(tempfile.mkdtemp(prefix=prefix))
    sk = root / "skills" / "has-docs"
    (sk / "references").mkdir(parents=True)
    (sk / "scripts").mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: Has docs\ndescription: Subtree test.\n---\nbody\n",
                                 encoding="utf-8")
    (sk / "references" / "details.md").write_text("details v1\n", encoding="utf-8")
    (sk / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    (sk / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n binary")
    dis = root / "skills" / ".disabled" / "turned-off"
    dis.mkdir(parents=True)
    (dis / "SKILL.md").write_text("---\nname: Turned off\n---\nx\n", encoding="utf-8")
    return root, sk, root / ".claude" / "skills" / "has-docs"


# ---- recursive copy ----
_ROOT, _SK, _MIR = _mk_brain("javis-mirror-")
system_sync.mirror_skills(_ROOT)
check("mirror has SKILL.md", (_MIR / "SKILL.md").is_file())
check("mirror has references/details.md", (_MIR / "references" / "details.md").is_file())
check("mirror has scripts/run.py", (_MIR / "scripts" / "run.py").is_file())
check("mirror keeps the bytes of the binary file intact",
      (_MIR / "image.png").is_file()
      and (_MIR / "image.png").read_bytes() == b"\x89PNG\r\n\x1a\n binary")
check("does NOT mirror the disabled skill", not (_ROOT / ".claude" / "skills" / "turned-off").exists())

# ---- references/ changes while SKILL.md does not -> the mirror MUST pick it up (PRE-EXISTING bug) ----
(_SK / "references" / "details.md").write_text("details v2\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("references/ changed (SKILL.md unchanged) -> mirror gets the new version",
      (_MIR / "references" / "details.md").read_text(encoding="utf-8") == "details v2\n")

# ---- a SIBLING side file changes while SKILL.md does not -> the mirror MUST pick it up (PRE-EXISTING bug) ----
(_SK / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n CHANGED")
system_sync.mirror_skills(_ROOT)
check("sibling side file changed (SKILL.md unchanged) -> mirror gets the new version",
      (_MIR / "image.png").read_bytes() == b"\x89PNG\r\n\x1a\n CHANGED")

# ---- add-only: a stray file in the mirror is NOT deleted ----
(_MIR / "user-added.md").write_text("keep me\n", encoding="utf-8")
(_SK / "SKILL.md").write_text("---\nname: Has docs\ndescription: Changed to force a copy.\n---\nbody 2\n",
                              encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("add-only: stray file in the mirror is not deleted", (_MIR / "user-added.md").is_file())

# ---- nothing changed -> NO re-copy at all ----
# Do NOT check with mtime: shutil.copy2 keeps the SOURCE mtime, so the destination always has the
# same mtime whether or not it was re-copied -> a test like that is green even when the code is
# wrong. We must COUNT real copy2 calls.
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
check(f"nothing changed -> NO re-copy at all (counted {len(_copies)})", len(_copies) == 0)

# ---- nothing changed -> no longer read-and-hash SKILL.md like the old version ----
# WHAT THIS PROVES EXACTLY: the old version read SKILL.md through Path.read_text to hash it, twice
# per skill (source + destination), on every call - that was the 52ms. This spy catches exactly
# that path disappearing.
# WHAT IT DOES *NOT* PROVE: "no file is read at all". shutil.copy2 reads through open(), not
# Path.read_text, so if a copy still ran this spy would STAY silent. Proving that no copy happens
# is the job of the _copies check above. The two checks complement each other, do not merge them.
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
check(f"nothing changed -> no more read-and-hash of SKILL.md (counted {len(_reads)} read_text/read_bytes calls)",
      len(_reads) == 0)

# ---- two concurrent threads on the same root -> no hang ----
_R2, _SK2, _MIR2 = _mk_brain("javis-mirrorpar-")
_done = []


def _race():
    system_sync.mirror_skills(_R2)
    _done.append(1)


_ts = [threading.Thread(target=_race) for _ in range(4)]
[t.start() for t in _ts]
[t.join(timeout=20) for t in _ts]
check("4 concurrent threads -> no hang, all 4 finish", len(_done) == 4)
check("4 concurrent threads -> mirror is still correct", (_MIR2 / "references" / "details.md").is_file())

# ---- cleanup ----
for _d in (_ROOT, _R2):
    shutil.rmtree(_d, ignore_errors=True)

if _fails:
    print(f"\nFAIL - test_system_sync: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_system_sync: all pass")
```

- [ ] **Step 2: Run the test, confirm it FAILS in the right places**

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`

Expected: FAIL. These lines must be red:
- `mirror has references/details.md` - the current version only copies top-level files.
- `mirror has scripts/run.py` - same reason.
- `references/ changed (SKILL.md unchanged) -> mirror gets the new version`
- `sibling side file changed (SKILL.md unchanged) -> mirror gets the new version` - PRE-EXISTING bug: the skip gate only hashes SKILL.md.
- `nothing changed -> no more read-and-hash of SKILL.md` - the current version reads SKILL.md on every call.

These lines must be GREEN from the start (they pin invariants that must not break in Task 2): `mirror has SKILL.md`, `does NOT mirror the disabled skill`, `add-only: stray file in the mirror is not deleted`, `4 concurrent threads -> no hang`.

The line `nothing changed -> NO re-copy at all` may already be GREEN (the old version skips by the SKILL.md hash so it does not copy either). That is normal - it is a regression net for Task 2, not meant to catch the current bug.

- [ ] **Step 3: Commit**

```bash
git add server/test_system_sync.py
git commit -m "test(sync): dung test_system_sync tu so 0 - chot hanh vi mirror_skills"
```

---

### Task 2: Stat signature gate + recursive copy + dedicated lock

**Files:**
- Modify: `server/system_sync.py:39-47` (add `import os`), `:276-281` (add constants next to `_LOCK`), `:235-264` (rewrite `mirror_skills`)
- Test: `server/test_system_sync.py` (Task 1)

**Interfaces:**
- Produces: `system_sync._mirror_signature(canonical: Path) -> str` - a stat-only signature of the tree, an empty string if the directory does not exist.
- `system_sync.mirror_skills(root) -> None` keeps its public signature UNCHANGED. The 7 existing call sites change nothing.

- [ ] **Step 1: Add `import os`**

`system_sync.py` currently does NOT import `os` (checked). In the import block (lines 39-47), add `import os` between `import json` and `import re` to keep alphabetical order:

```python
import hashlib
import json
import os
import re
import shutil
import sys
import threading
```

- [ ] **Step 2: Add the constants + `_mirror_signature`**

Right BEFORE the line `_LOCK = threading.Lock()` (currently at line 280), insert:

```python
# -- Signature gate for mirror_skills -----------------------------------------------
# mirror_skills is called on the HOT PATH: build_system_prompt (main.py:184) runs on every
# dashboard chat turn, every Telegram message, every Kanban task, every loop iteration, every
# reminder, every learn spawn. The old version read + hashed SKILL.md twice for EVERY skill on
# every call: measured on a 27-skill brain it is ~52ms PER TURN, blocking the event loop
# directly. The signature uses stat only (no byte is read) so it is ~6ms, 9 times cheaper, and
# it also covers subfolders for free.
_MIRROR_SIG: dict = {}                    # resolved root -> signature of the last mirror run
_MIRROR_LOCKS: dict = {}                  # resolved root -> dedicated Lock for the mirror
_MIRROR_LOCKS_GUARD = threading.Lock()    # only protects CREATING locks in _MIRROR_LOCKS


def _mirror_lock(key: str) -> threading.Lock:
    """Per-root dedicated lock for the mirror. It must NEVER be _LOCK: mirror_skills is called
    from sync_brain WHILE _LOCK is held, and threading.Lock is not reentrant, so taking _LOCK
    here deadlocks on the very first chat turn. This lock is only taken INSIDE mirror_skills and
    no other lock is taken while holding it -> no cycle -> no deadlock."""
    with _MIRROR_LOCKS_GUARD:
        lk = _MIRROR_LOCKS.get(key)
        if lk is None:
            lk = threading.Lock()
            _MIRROR_LOCKS[key] = lk
        return lk


def _mirror_signature(canonical: Path) -> str:
    """Signature of the skill tree, computed ONLY from stat - reads NO file content.

    Folds (relative path in posix form, st_mtime_ns, st_size) of EVERY file into 1 sha256.
    Skips .disabled (disabled skills must not be mirrored). follow_symlinks=False on both is_dir
    and stat: the disk currently has no symlinks, but rglob on a tree with symlinks can loop
    forever. Returns an empty string if the directory does not exist. OSError on one entry ->
    skip that entry, never raise.
    """
    if not canonical.is_dir():
        return ""
    h = hashlib.sha256()
    stack = [canonical]
    rows = []
    while stack:
        d = stack.pop()
        try:
            # The context manager is REQUIRED: os.scandir holds the directory's file handle until
            # closed. On Windows, a dangling handle keeps the directory from being deleted or
            # renamed until GC cleans up - enough to break tests that use tempfile and even to
            # break the skill toggle (rmtree of the mirror).
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
    for row in sorted(rows):   # sort so the signature does not depend on the OS traversal order
        h.update(row.encode("utf-8", "replace"))
        h.update(b"\x01")
    return h.hexdigest()
```

- [ ] **Step 3: Rewrite `mirror_skills`**

Replace the WHOLE `mirror_skills` function (currently at lines 235-264) with:

```python
def mirror_skills(root) -> None:
    """ONE-WAY mirror of <root>/skills -> <root>/.claude/skills (ONLY enabled skills), RECURSIVE
    over references/ scripts/ templates/ - a skill is a PACKAGE, not a single file.
    Purpose: Claude Code contexts that run with cwd=brain (workflow/loop/learn/lint) still load
    skills NATIVELY as a bonus. Add/update-only, SKIPS .disabled (mirroring a disabled skill =
    accidentally re-enabling it natively). Does NOT delete stray entries in .claude (removing the
    mirror when a skill is disabled/deleted is handled by the endpoint).
    This is a derived copy - if it breaks, the main router is not harmed.

    HOT PATH: called on every chat turn via build_system_prompt. Tier 1 is the stat-only signature
    gate (~6ms) - 99% of turns exit here. Tier 2 (the real copy) only runs when the source tree
    CHANGED.

    KNOWN UP FRONT: the signature is computed on the SOURCE and the cache lives in memory, so a
    mirror that is damaged from OUTSIDE while the source is unchanged will not heal itself until
    the process restarts. A deliberate trade-off (see spec 2026-07-17-mirror-skills-tree-design.md).
    Disabling a skill moves the source to .disabled so the signature changes -> still covered."""
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
            return   # TIER 1: source tree unchanged -> nothing to do (the 99% chat-turn path)
        lk = _mirror_lock(key)
        if not lk.acquire(blocking=False):
            return   # another thread is mirroring this exact root -> it does the work, no queueing
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
            # Write the cache AFTER the copy finishes. The copy may change mtime at the
            # destination but not at the source, so recompute the source signature to be safe
            # (cheap) instead of trusting the old sig.
            _MIRROR_SIG[key] = _mirror_signature(canonical)
        finally:
            lk.release()
    except Exception as e:
        print(f"[skill mirror] {root}: {type(e).__name__}: {e}", file=sys.stderr)
```

- [ ] **Step 4: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`
Expected: PASS, prints `OK - test_system_sync: all pass`.

- [ ] **Step 5: Prove the signature gate really bites (mutation)**

Temporarily remove tier 1 by commenting out two lines:

```python
        # if sig and _MIRROR_SIG.get(key) == sig:
        #     return
```

Run: `cd server && ../.venv/Scripts/python.exe test_system_sync.py`
Expected: FAIL at `nothing changed -> NO re-copy at all` and `nothing changed -> no more read-and-hash of SKILL.md`.

**Restore it exactly**, then run again and confirm green. Confirm `git diff server/system_sync.py` shows only the intended changes.

- [ ] **Step 6: Run the whole suite**

Run: `cd server && st=0; for f in test_*.py; do ../.venv/Scripts/python.exe "$f" >/dev/null 2>&1 || { echo "FAIL: $f"; st=1; }; done; echo "EXIT=$st"`
Expected: `EXIT=0`. Pay special attention to `test_skill_caps.py` (it calls `system_sync.system_skill_slugs`) and `test_skill_usage.py`.

- [ ] **Step 7: Commit**

```bash
git add server/system_sync.py
git commit -m "perf(sync): cong chu ky stat + mirror de quy - 52ms/luot xuong ~6ms"
```

---

### Task 3: Re-measure on the real brain + bump 0.9.64

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `system_sync.mirror_skills`, `system_sync._mirror_signature` (Task 2).

- [ ] **Step 1: Re-measure on the real brain**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys, time
from pathlib import Path
sys.path.insert(0, '.')
import system_sync
for r in ['../brains/My Bullet Journal', '../brains/Brain Default', '../brains/Ngọc Thu Phạm']:
    if not Path(r).is_dir(): continue
    system_sync.mirror_skills(r)          # warm the cache + mirror
    t0 = time.perf_counter()
    for _ in range(5): system_sync.mirror_skills(r)
    print(f'{Path(r).name:22} {(time.perf_counter()-t0)/5*1000:6.2f} ms/turn')
"
```
Expected: each brain under ~10ms. Baseline numbers before this plan: My Bullet Journal 52.48ms, Ngọc Thu Phạm 44.23ms, Brain Default 11.62ms.

- [ ] **Step 2: Confirm references/ reaches the real brain**

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
        print(('OK  ' if mir.is_dir() else 'MISSING'), b.name, '/', d.name)
print('skills with references/:', n)
"
```
Expected: every line `OK`. Before this plan, every line would be `MISSING`.

Note: this step writes into the real `brains/`, but `brains/` is already gitignored in the root repo (`.gitignore:51`) so it does not end up in the commit.

- [ ] **Step 3: Bump VERSION**

`VERSION` is currently `0.9.63`. Write `0.9.64`:

```bash
echo "0.9.64" > VERSION
```

- [ ] **Step 4: Write the CHANGELOG**

Add this block to `CHANGELOG.md`, RIGHT BEFORE the line `## [0.9.63] - 2026-07-17`:

```markdown
## [0.9.64] - 2026-07-17
### Fixes
- **Jarvis 007 spent ~52ms on every chat turn just to sync skills, and it blocked the whole process**: the skill mirror function re-read and re-hashed the `SKILL.md` of EVERY skill (both the source copy and the destination copy) each time the system prompt was built, i.e. every chat turn, every Telegram message, every Kanban task, every loop iteration, every reminder. Measured on a 27-skill brain: 52.48ms per turn, running synchronously on the event loop so other connections stalled too. It is now replaced by a signature gate that uses only `stat` (no file content is read): about 6ms, 9 times faster, and it only does a real copy when the skill tree has changed. A pre-existing bug nobody knew about until it was measured.
- **A side file inside a skill changed but the mirror never picked it up**: the skip gate only hashed `SKILL.md`, so editing an image or a sibling document in the skill folder left the copy that Claude Code loads natively stuck on the old version forever. The new signature covers every file, so this bug is gone.
### Added
- **Skills can now carry `references/` and `scripts/`**: the mirror into `.claude/skills` now copies the whole subtree, so a skill with separate documentation or a bundled script also works on the path Claude Code loads natively, not only on the router path. 10 skills in the existing brains already used `references/` and until now still had not reached the native path.
### Known, not fixed
- **System skills still do not ship their subtree**: `html-to-webcake` ships with `tools/` and `examples/`, but the system-skill install mechanism only carries `SKILL.md`, so the subtree has never reached any brain. This release does NOT fix that: it lives in the install layer, above the mirror layer.
- **A mirror damaged from outside will not heal itself until a restart**: the signature gate is computed on the source tree and remembered in memory, so if someone manually deletes a file in `.claude/skills` without touching the original skill, Jarvis 007 will not notice. A deliberate trade-off for speed; disabling/enabling the skill or restarting both bring it back to correct.
```

- [ ] **Step 5: Check for em dashes**

Run: `cd "D:/Project/Javis-OS" && ./.venv/Scripts/python.exe -c "import pathlib; print('em dash:', pathlib.Path('CHANGELOG.md').read_text(encoding='utf-8').count(chr(8212)))"`
Expected: `em dash: 0`

- [ ] **Step 6: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: 0.9.64 - mirror skill de quy + cat 52ms/luot xuong ~6ms"
git push origin main
```

---

## Notes for the executor

**Dependency order:** Task 1 -> Task 2 -> Task 3. Linear, cannot be interleaved.

**The deadliest spot is `_LOCK`.** `mirror_skills` is called from `sync_brain:356` WHILE `_LOCK` is held (`system_sync.py:280`, not reentrant). Taking `_LOCK` inside `mirror_skills` deadlocks on the very first chat turn, and the test will hang rather than report a clear error. The mirror's lock MUST be a different object.

**`mirror_skills` is called in exactly 7 places** (re-grepped when this plan was written, do NOT carry over the old number):

- `main.py:185` - the REAL hot path, inside `build_system_prompt`, runs on every chat turn.
- `main.py:2213`, `:2268`, `:2310`, `:2684`, `:2736` - endpoints triggered by a person clicking (toggle, save, group, import, workflow).
- `system_sync.py:356` - inside `sync_brain`, runs WHILE `_LOCK` is held.

Note that `system_sync.py:200` also matches the grep but it is a **docstring**, not a call.

⚠ Line numbers in `main.py` DRIFT fast. The risk map written on 2026-07-16 recorded `184/2186/2241/2283/2657/2709`; all have shifted because the commits of the A+B batch themselves added lines to `main.py` (Task 10 added ~23 lines, Task 6 added 6). If you read this plan after more commits touched `main.py`, **grep again instead of trusting the numbers above**. Locate by CONTENT, not by line number.

**Do not touch `skill_hash`.** It is still used by `sync_brain`, `LEGACY_HASHES` and the `--hash` CLI. We only stop using it inside `mirror_skills`.

**Do not widen the scope.** `_system_items` (so that system skills ship their subtree, i.e. patching `html-to-webcake`) is INTENTIONALLY out of scope. If you see something worth doing, write it down, do not do it.
