# Thorough update for Jarvis 007 - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "Update now" button reliable in every environment, show clear progress, automatically roll back the git version when the new version is broken, and give instructions for going back a version on Docker.

**Architecture:** Split the pure logic (version comparison, reading/writing update state, rollback decision) into the module `server/update_state.py` so it can be unit-tested. A cross-platform Python updater `server/updater.py`, spawned detached by `POST /update`, runs the chain stop -> pull -> pip -> start -> health-check -> rollback for the git version (Windows + native). Docker keeps Watchtower/Redeploy (Direction B: version tag + instructions for going back). The frontend reads `GET /update/status` to draw progress.

**Tech Stack:** Python 3.12 + FastAPI (server), urllib/subprocess (updater, stdlib only), vanilla JS (dashboard/console.js), GitHub Actions (CI), Docker/GHCR.

## Global Constraints

- NEVER use the em dash character (U+2014) anywhere (chat/file/code/comment). Use "-".
- English for comments + displayed strings.
- Tests are standalone scripts run with `cd server && .venv\Scripts\python.exe test_update.py` (NOT pytest), following the mold `check(name, cond)` + `sys.exit(1)` on FAIL (see `server/test_path_exists.py`).
- Run tests with `.venv` (the system python is missing libs).
- `config.STATE_DIR = Path(os.getenv("JAVIS_STATE_DIR", <server dir>))`. Tests set `JAVIS_STATE_DIR` to a temp dir BEFORE importing the module.
- The app inside Docker has NO docker socket - it does not change/roll back the image itself (keep as is).
- No background auto-update, no Docker updater sidecar.
- Repo: `blogminhquy/javis-os`. GHCR image: `ghcr.io/blogminhquy/javis-os`.
- Only after everything is done + tests green: bump VERSION + CHANGELOG + commit + push origin/main.

---

## File Structure

- Create `server/update_state.py` - pure module: version compare + read/write `update_state.json` + `update_outcome()` + `record_boot_version()`. Shared by main.py and updater.py.
- Create `server/updater.py` - cross-platform updater that runs detached (stop/pull/pip/start/health/rollback).
- Create `server/test_update.py` - tests for update_state + endpoint + updater dry-run.
- Modify `server/main.py` - use update_state; add `previous_version` to `/version`; add `GET /update/status`; rewrite `POST /update`; boot hook that records the version; stop generating `_selfupdate.bat`.
- Modify `.github/workflows/docker-publish.yml` - add the tag `:<version>`.
- Modify `dashboard/console.js` - version panel + changelog snippet + progress bar + go-back panel.
- Modify `VERSION`, `CHANGELOG.md` - bump when finished.

---

## Task 1: Pure module `update_state.py`

**Files:**
- Create: `server/update_state.py`
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `config.STATE_DIR` (from `server/config.py`).
- Produces:
  - `STATE_DIR: Path`, `STATE_FILE: Path`
  - `ver_tuple(s: str) -> tuple|None`
  - `ver_newer(latest: str, cur: str) -> bool`
  - `read_state() -> dict`
  - `write_state(patch: dict) -> dict`
  - `record_boot_version(current: str) -> dict`
  - `update_outcome(health_ok: bool, current: str, old: str, target: str|None) -> str` (returns `"success"|"version_mismatch"|"need_rollback"`)

- [ ] **Step 1: Write the failing test**

Create `server/test_update.py`:

```python
"""Test the update layer: update_state (pure) + the /update/status endpoint + updater dry-run.
Run:  cd server && .venv\\Scripts\\python.exe test_update.py    (NO network)."""
import os, sys, tempfile
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-update-test-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)

import update_state as us  # noqa: E402

# --- version compare ---
check("ver_newer 0.9.79 > 0.9.78", us.ver_newer("0.9.79", "0.9.78") is True)
check("ver_newer equal → False", us.ver_newer("1.0.0", "1.0.0") is False)
check("ver_newer local ahead → False", us.ver_newer("0.9.78", "0.9.79") is False)
check("ver_tuple garbage → treated as (0,0,0), no crash", us.ver_tuple("abc") == (0, 0, 0))

# --- state round-trip ---
us.write_state({"phase": "installing", "old_version": "0.9.78"})
st = us.read_state()
check("write/read state keeps phase", st.get("phase") == "installing")
check("write/read state keeps old_version", st.get("old_version") == "0.9.78")
us.write_state({"phase": "done"})
check("write_state merges (does not lose old fields)", us.read_state().get("old_version") == "0.9.78")

# --- record_boot_version ---
us.STATE_FILE.unlink(missing_ok=True)
us.record_boot_version("0.9.78")
check("first boot: last_good = current", us.read_state().get("last_good_version") == "0.9.78")
check("first boot: no previous yet", us.read_state().get("previous_version") is None)
us.record_boot_version("0.9.79")
check("boot onto a new version: last_good updated", us.read_state().get("last_good_version") == "0.9.79")
check("boot onto a new version: previous = the old version", us.read_state().get("previous_version") == "0.9.78")

# --- update_outcome ---
check("health red → need_rollback", us.update_outcome(False, "0.9.79", "0.9.78", "0.9.79") == "need_rollback")
check("health green + right target → success", us.update_outcome(True, "0.9.79", "0.9.78", "0.9.79") == "success")
check("health green + version advanced (empty target) → success", us.update_outcome(True, "0.9.79", "0.9.78", None) == "success")
check("health green but version unchanged → version_mismatch", us.update_outcome(True, "0.9.78", "0.9.78", "0.9.79") == "version_mismatch")

print()
if _fails:
    print(f"{len(_fails)} FAIL: {_fails}"); sys.exit(1)
print("ALL PASS")
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'update_state'`.

- [ ] **Step 3: Write `server/update_state.py`**

```python
"""Pure layer shared by the update flow: version comparison + read/write update_state.json +
rollback decision. Does not depend on FastAPI/main → importable from both main.py and updater.py."""
import json
import re
from pathlib import Path

import config as cfgmod

STATE_DIR = cfgmod.STATE_DIR
STATE_FILE = STATE_DIR / "update_state.json"


def ver_tuple(s):
    try:
        parts = [int(x) for x in re.split(r"[.\-]", (s or "").strip().lstrip("vV"))[:3] if x.isdigit()]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return None


def ver_newer(latest, cur) -> bool:
    """Semver comparison: is latest NEWER than cur? (avoids a false alarm when local is ahead / the format differs)."""
    lt, ct = ver_tuple(latest), ver_tuple(cur)
    if lt is None or ct is None:
        return False
    return lt > ct


def read_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def write_state(patch: dict) -> dict:
    """Merge patch into the existing state and write it. Returns the state after writing."""
    st = read_state()
    st.update(patch)
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return st


def record_boot_version(current: str) -> dict:
    """Runs on every startup: maintains last_good_version + previous_version so every mode knows
    'where to go back to'. When it has just come up on a newer version, previous = the old last_good."""
    st = read_state()
    last_good = st.get("last_good_version")
    patch = {}
    if last_good and last_good != current and ver_newer(current, last_good):
        patch["previous_version"] = last_good
    patch["last_good_version"] = current
    return write_state(patch)


def update_outcome(health_ok: bool, current: str, old: str, target=None) -> str:
    """The result after trying to bring up the new version. Separated so it can be tested (the health poll lives in the updater)."""
    if not health_ok:
        return "need_rollback"
    ct, tt = ver_tuple(current), ver_tuple(target)
    if target and ct and tt and ct >= tt:
        return "success"
    if ver_newer(current, old):
        return "success"
    return "version_mismatch"
```

- [ ] **Step 4: Run the test to confirm PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/update_state.py server/test_update.py
git commit -m "feat(update): pure module update_state (version compare + state + outcome) + test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Wire main.py to use update_state + previous_version + boot hook

**Files:**
- Modify: `server/main.py` (import ~line 29; delete the old `_ver_tuple`/`_ver_newer` ~3626-3642; `version_info` ~3688; startup `_start_scheduler` ~3462-3469)
- Test: `server/test_update.py` (add cases)

**Interfaces:**
- Consumes: `update_state.ver_tuple/ver_newer/read_state/write_state/record_boot_version/update_outcome` (Task 1).
- Produces: the aliases `_ver_tuple`, `_ver_newer`, `_read_update_state`, `_write_update_state`, `_record_boot_version`, `_update_outcome` in main (keeping the old names for existing code); `/version` additionally returns `previous_version`.

- [ ] **Step 1: Add the import + aliases in main.py**

After the line `import config as cfgmod` (main.py:29) add:

```python
import update_state
_ver_tuple = update_state.ver_tuple
_ver_newer = update_state.ver_newer
_read_update_state = update_state.read_state
_write_update_state = update_state.write_state
_record_boot_version = update_state.record_boot_version
_update_outcome = update_state.update_outcome
```

- [ ] **Step 2: Delete the 2 duplicate defs in main.py**

Delete the whole function `def _ver_tuple(...)` (main.py ~3626-3633) and `def _ver_newer(...)` (~3636-3642). The places that call `_ver_tuple`/`_ver_newer` stay as they are (the aliases from Step 1 already exist).

- [ ] **Step 3: `/version` additionally returns previous_version**

In `version_info()` (main.py ~3708), change the return to:

```python
    st = _read_update_state()
    return {"current": cur, "latest": latest, "update_available": avail,
            "mode": mode, "can_self_update": can, "error": err,
            "previous_version": st.get("previous_version")}
```

- [ ] **Step 4: Boot hook that records the version**

In `_start_scheduler()` (main.py:3462), after the line `_sync_system_all_brains()` (3469) add:

```python
    try:
        _record_boot_version(_read_version())   # maintain last_good/previous for the go-back-a-version feature
    except Exception:
        pass
```

- [ ] **Step 5: Add test cases for /version + import main**

Append to the end of `server/test_update.py` (before the result `print()`):

```python
# --- main.py uses update_state + /version has previous_version ---
import asyncio  # noqa: E402
import main  # noqa: E402
check("main alias _ver_newer works", main._ver_newer("0.9.79", "0.9.78") is True)
us.STATE_FILE.unlink(missing_ok=True)
us.write_state({"previous_version": "0.9.77"})
_v = asyncio.run(main.version_info())
check("/version has the key previous_version", "previous_version" in _v)
check("/version previous_version has the right value", _v.get("previous_version") == "0.9.77")
```

- [ ] **Step 6: Run the tests**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS` (note: `version_info` calls the GitHub network to get latest; with no network `latest=None`, but the test case only checks `previous_version` so it still PASSES).

- [ ] **Step 7: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "refactor(update): main uses update_state; /version adds previous_version; boot hook

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Endpoint `GET /update/status`

**Files:**
- Modify: `server/main.py` (add the endpoint next to `/version`, ~after line 3709)
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `_read_update_state()` (Task 2); `cfgmod.STATE_DIR`.
- Produces: `GET /update/status -> {"state": dict, "log_tail": str}`; the function `update_status()` can be called directly in tests.

- [ ] **Step 1: Write the failing test**

Append to the end of `server/test_update.py` (before `print()`):

```python
# --- /update/status ---
us.write_state({"phase": "health_check", "result": None})
(us.STATE_DIR / "update.log").write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
_s = asyncio.run(main.update_status())
check("/update/status returns state.phase", _s["state"].get("phase") == "health_check")
check("/update/status returns log_tail", "line 3" in _s["log_tail"])
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL with `AttributeError: module 'main' has no attribute 'update_status'`.

- [ ] **Step 3: Add the endpoint to main.py**

After `version_info()` (main.py ~3709), add:

```python
@app.get("/update/status")
async def update_status():
    """Update status (the UI polls it to draw progress). Reads update_state.json + the last ~50 lines of
    update.log. The files survive a restart, so after the server comes back up it can still report the result."""
    st = _read_update_state()
    tail = ""
    try:
        logf = cfgmod.STATE_DIR / "update.log"
        if logf.exists():
            lines = logf.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-50:])
    except Exception:
        tail = ""
    return {"state": st, "log_tail": tail}
```

- [ ] **Step 4: Run the test to confirm PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "feat(update): endpoint GET /update/status (state + log tail) for the progress bar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Rewrite `POST /update` (dispatch + guard)

**Files:**
- Modify: `server/main.py` (replace the whole `do_update()` ~3712-3764)
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `_deploy_mode()`, `_read_version()`, `_is_git_checkout()`, `_watchtower_reachable()`, `_read_update_state()`, `_write_update_state()`, `PROJECT_ROOT`, `GITHUB_REPO`.
- Produces: the new `do_update()`: git mode spawns `server/updater.py` detached; docker keeps Watchtower/guided; guard against duplicate runs (409); the function `_git_head(root)`.

- [ ] **Step 1: Write the failing test (duplicate-run guard)**

Append to the end of `server/test_update.py` (before `print()`):

```python
# --- POST /update guards against duplicate runs ---
from fastapi.responses import JSONResponse  # noqa: E402
us.write_state({"phase": "pulling", "started_at": "2026-07-18T10:00:00"})
_r = asyncio.run(main.do_update())
check("update already running → returns 409", isinstance(_r, JSONResponse) and _r.status_code == 409)
us.write_state({"phase": "idle"})  # clean up so it does not get stuck
check("has the function _git_head", callable(getattr(main, "_git_head", None)))
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL on the 409 guard case (the old function has no guard yet) or missing `_git_head`.

- [ ] **Step 3: Replace `do_update()` in main.py**

Replace the whole function `do_update()` (main.py ~3712-3764) with:

```python
_UPDATE_ACTIVE = {"preparing", "pulling", "installing", "restarting", "health_check", "rolling_back"}


def _git_head(root: str) -> str:
    try:
        import subprocess
        r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


@app.post("/update")
async def do_update():
    """Update to the latest version. Git checkout (windows/native) → spawn updater.py DETACHED
    (stop/pull/pip/start/health/rollback). Docker → Watchtower if present, otherwise Redeploy instructions."""
    import sys as _sys
    import subprocess
    import datetime as _dt
    now = lambda: _dt.datetime.now().isoformat(timespec="seconds")

    st = _read_update_state()
    if st.get("phase") in _UPDATE_ACTIVE:
        return JSONResponse({"ok": False, "error": "An update is already running, wait a moment.",
                             "phase": st.get("phase")}, status_code=409)

    mode = _deploy_mode()
    cur = _read_version()
    latest = None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/VERSION")
            if r.status_code == 200:
                latest = (r.text or "").strip() or None
    except Exception:
        latest = None

    if mode == "docker":
        if not await _watchtower_reachable():
            return JSONResponse({"ok": False,
                "error": "The Docker version updates by REDEPLOY to pull the new image: on Hostinger press Redeploy in Docker Manager; on a VPS run the command below. If the new version is broken, pin the old version tag and Redeploy to go back.",
                "manual": "docker compose up -d --pull always",
                "current": cur, "latest": latest,
                "previous_version": st.get("previous_version")}, status_code=400)
        token = os.getenv("WATCHTOWER_TOKEN", "")
        _write_update_state({"phase": "restarting", "old_version": cur, "target_version": latest,
                             "old_sha": None, "result": None, "error": None, "stashed": False,
                             "started_at": now(), "finished_at": None})
        import asyncio
        import httpx

        async def _trigger():
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    await client.post("http://watchtower:8080/v1/update",
                                      headers={"Authorization": f"Bearer {token}"})
            except Exception as e:
                print(f"[update] watchtower trigger: {e}", file=_sys.stderr)
        t = asyncio.create_task(_trigger())
        _UPDATE_TASKS.add(t)
        t.add_done_callback(_UPDATE_TASKS.discard)
        return {"ok": True, "mode": "docker", "message": "Pulling the new image + restarting (~20-40s)."}

    # git checkout (windows / native)
    root = str(PROJECT_ROOT)
    if not _is_git_checkout(root):
        return JSONResponse({"ok": False,
            "error": "The install folder is not a git checkout → cannot self-update. Reinstall with 'git clone' or update manually.",
            "manual": "./update.sh"}, status_code=400)
    old_sha = _git_head(root)
    _write_update_state({"phase": "preparing", "old_version": cur, "old_sha": old_sha,
                         "target_version": latest, "result": None, "error": None, "stashed": False,
                         "started_at": now(), "finished_at": None})
    try:
        py = _sys.executable
        updater = str(PROJECT_ROOT / "server" / "updater.py")
        port = os.getenv("JAVIS_PORT", "7777")
        args = [py, updater, "--old-sha", old_sha, "--old-version", cur,
                "--target", latest or "", "--port", str(port)]
        if mode == "windows":
            subprocess.Popen(args, cwd=root, creationflags=0x00000008 | 0x00000200)  # DETACHED|NEW_GROUP
        else:
            subprocess.Popen(args, cwd=root, start_new_session=True)
        return {"ok": True, "mode": mode,
                "message": "Updating + restarting (follow it on the progress bar)."}
    except Exception as e:
        _write_update_state({"phase": "error", "result": "error", "error": str(e), "finished_at": now()})
        return JSONResponse({"ok": False, "error": str(e), "manual": "./update.sh"}, status_code=500)
```

- [ ] **Step 4: Run the test to confirm PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "feat(update): POST /update spawns updater.py for git mode + duplicate-run guard + guided docker

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Cross-platform updater `server/updater.py`

**Files:**
- Create: `server/updater.py`
- Delete (old logic): main.py no longer generates `_selfupdate.bat` (dropped in Task 4). The old `server/_selfupdate.bat` file (untracked in STATE_DIR) does not need to be deleted by hand.
- Test: `server/test_update.py` (dry-run case)

**Interfaces:**
- Consumes: `update_state` (Task 1); CLI args `--old-sha --old-version --target --port [--dry-run]`.
- Produces: a detached program that writes `update_state.json` + `update.log`. `--dry-run` prints "PLAN:" and exits 0 (for tests).

- [ ] **Step 1: Write the failing test (dry-run)**

Append to the end of `server/test_update.py` (before `print()`):

```python
# --- updater.py --dry-run (does not execute git/pip) ---
import subprocess as _sp  # noqa: E402
_upd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "updater.py")
_p = _sp.run([sys.executable, _upd, "--dry-run", "--port", "7777"],
             capture_output=True, text=True, env={**os.environ})
check("updater --dry-run exits 0", _p.returncode == 0)
check("updater --dry-run prints PLAN", "PLAN:" in (_p.stdout or ""))
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL (updater.py does not exist yet → returncode != 0).

- [ ] **Step 3: Write `server/updater.py`**

```python
#!/usr/bin/env python
"""Detached updater of Jarvis 007 for the GIT checkout version (Windows + native Linux). The server spawns it DETACHED:

    python updater.py --old-sha <sha> --old-version <v> --target <v> --port <p>

Chain: stop server -> git pull (stash if the tree is dirty) -> pip install -> start -> wait for /health ~90s.
/health does not come up → git reset --hard <old-sha> -> pip -> start (automatic rollback).
Uses stdlib only (so it still runs even when the new version breaks a dependency)."""
import argparse
import datetime
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
import update_state as us  # noqa: E402


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(us.STATE_DIR / "update.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)


def venv_python():
    p = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(p) if p.exists() else sys.executable


def has_systemd():
    try:
        r = subprocess.run(["systemctl", "list-unit-files"], capture_output=True, text=True)
        return r.returncode == 0 and "javis.service" in (r.stdout or "")
    except Exception:
        return False


def stop_server():
    if os.name == "nt":
        run(["cmd", "/c", str(ROOT / "stop-javis.bat")])
    else:
        subprocess.run(["systemctl", "stop", "javis"], capture_output=True, text=True)


def start_server():
    if os.name == "nt":
        subprocess.Popen(["wscript.exe", "//nologo", str(ROOT / "start-javis.vbs")],
                         cwd=str(ROOT), creationflags=0x00000008)  # DETACHED_PROCESS
    else:
        subprocess.run(["systemctl", "start", "javis"], capture_output=True, text=True)


def git_dirty():
    r = run(["git", "status", "--porcelain", "--untracked-files=no"])
    return bool((r.stdout or "").strip())


def pip_install():
    return run([venv_python(), "-m", "pip", "install", "-r", "requirements.txt", "-q"])


def read_current_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def poll_health(port, timeout_s=90):
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=4) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-sha", default="")
    ap.add_argument("--old-version", default="")
    ap.add_argument("--target", default="")
    ap.add_argument("--port", default=os.getenv("JAVIS_PORT", "7777"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        print(f"PLAN: stop -> pull(stash if dirty) -> pip -> start -> health({a.port}) "
              f"-> rollback(reset {a.old_sha or '?'}) if it does not come up")
        return 0

    target = a.target or None
    us.write_state({"phase": "restarting", "started_at": _now(), "finished_at": None,
                    "result": None, "error": None, "old_sha": a.old_sha,
                    "old_version": a.old_version, "target_version": target})

    if os.name != "nt" and not has_systemd():
        log("No systemd service 'javis' found → cannot restart by itself. Please restart by hand.")
        us.write_state({"phase": "error", "result": "error",
                        "error": "There is no systemd service 'javis' to restart automatically.",
                        "finished_at": _now()})
        return 1

    log("Stopping the old server…")
    stop_server()
    time.sleep(2)

    us.write_state({"phase": "pulling"})
    if git_dirty():
        log("The git tree has local changes → git stash (kept, not lost).")
        run(["git", "stash"])
        us.write_state({"stashed": True})
    pull = run(["git", "pull", "--ff-only"])
    if pull.returncode != 0:
        log("git pull FAILED:\n" + (pull.stderr or pull.stdout or ""))
        start_server()
        us.write_state({"phase": "error", "result": "pull_failed",
                        "error": (pull.stderr or "git pull failed")[:500], "finished_at": _now()})
        return 1

    us.write_state({"phase": "installing"})
    log("Installing libraries…")
    pip_install()

    us.write_state({"phase": "restarting"})
    log("Starting the new version…")
    start_server()

    us.write_state({"phase": "health_check"})
    log("Checking health…")
    healthy = poll_health(a.port, 90)
    current = read_current_version()
    outcome = us.update_outcome(healthy, current, a.old_version, target)
    log(f"health={healthy} current={current} → {outcome}")

    if outcome == "success":
        us.record_boot_version(current)
        us.write_state({"phase": "done", "result": "success", "finished_at": _now()})
        return 0
    if outcome == "version_mismatch":
        us.write_state({"phase": "done", "result": "error",
                        "error": "The server came up but the version did not change (pull not applied?). See update.log.",
                        "finished_at": _now()})
        return 1

    # need_rollback
    log("The new version could NOT come up → automatically going back to the old version…")
    us.write_state({"phase": "rolling_back"})
    if not a.old_sha:
        us.write_state({"phase": "error", "result": "rollback_failed",
                        "error": "There is no old commit to go back to.", "finished_at": _now()})
        return 1
    run(["git", "reset", "--hard", a.old_sha])
    pip_install()
    start_server()
    if poll_health(a.port, 90):
        us.write_state({"phase": "done", "result": "rolled_back",
                        "error": "The new version was broken, automatically returned to the old version.", "finished_at": _now()})
        return 0
    us.write_state({"phase": "error", "result": "rollback_failed",
                    "error": "The new version was broken and going back to the old one did not come up either. See update.log.", "finished_at": _now()})
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to confirm PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS`.

- [ ] **Step 5: Manual smoke test on Windows (NOT automated)**

Only run when there is a real new version on GitHub. Open the app, the Overview page, press "Update now". Watch `STATE_DIR/update.log` + the progress bar. Confirm: pull + `pip install` run, and the server comes back up on the right new version. (To try the rollback: create a deliberately broken commit on a test branch and point at it - do NOT do this on main.)

- [ ] **Step 6: Commit**

```bash
git add server/updater.py server/test_update.py
git commit -m "feat(update): cross-platform updater.py - stop/pull/pip/start/health + automatic rollback for the git version

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: CI version tag on GHCR

**Files:**
- Modify: `.github/workflows/docker-publish.yml` (step "Build & push", ~lines 42-44)

**Interfaces:**
- Consumes: the `VERSION` file at the repo root.
- Produces: the GHCR image gets an extra tag `:<version>` (e.g. `:0.9.79`) next to `:latest` and `:<sha>`.

- [ ] **Step 1: Add a step that reads VERSION**

In `.github/workflows/docker-publish.yml`, after the step "Set lowercase image name" (lines 25-26), add:

```yaml
      - name: Read app version
        run: echo "APP_VERSION=$(cat VERSION | tr -d ' \n\r')" >> "$GITHUB_ENV"
```

- [ ] **Step 2: Add the version tag to the Build & push step**

Change the `tags:` block (lines 42-44) to:

```yaml
          tags: |
            ${{ env.IMAGE }}:latest
            ${{ env.IMAGE }}:${{ github.sha }}
            ${{ env.IMAGE }}:${{ env.APP_VERSION }}
```

- [ ] **Step 3: Check the workflow syntax**

Run: `git diff .github/workflows/docker-publish.yml`
Expected: only the step "Read app version" and 1 tag line `:${{ env.APP_VERSION }}` were added. Nothing else touched. (Real verification happens on push: see the Actions build go green + GHCR has the version tag.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docker-publish.yml
git commit -m "ci(update): tag the GHCR image by version (:x.y.z) so there is an old version to go back to

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Frontend - version panel + progress + go back a version

**Files:**
- Modify: `dashboard/console.js` (card HTML ~1319-1331; handler ~1379-1445)

**Interfaces:**
- Consumes: `GET /version` (adds `previous_version`), `GET /changelog`, `POST /update`, `GET /update/status`.
- Produces: the new version card with a changelog snippet, a step-by-step progress bar, and a go-back panel (docker).

- [ ] **Step 1: Replace the version card HTML**

In `dashboard/console.js`, replace the block `<div class="cview-section"><h3>Version</h3>...</div>` (lines 1320-1331) with:

```javascript
      <div class="cview-section">
        <h3>Version</h3>
        <div class="gcard" style="max-width:640px">
          <div class="gcard-top"><span class="gcard-name">Jarvis 007</span><span class="gcard-tag" id="ovVerTag">…</span></div>
          <div class="gcard-meta" id="ovVerMeta">Checking for a new version…</div>
          <div id="ovVerChangelog" style="display:none;margin:8px 0;padding:8px 10px;border-left:3px solid var(--accent,#6aa);background:rgba(120,140,160,.08);border-radius:6px;font-size:13px;line-height:1.6"></div>
          <div class="js-actions">
            <button class="gcard-btn ghost" id="ovVerCheck">Check again</button>
            <button class="gcard-btn" id="ovVerUpdate" style="display:none">⬆ Update now</button>
          </div>
          <div id="ovVerProgress" style="display:none;margin-top:10px"></div>
          <div class="gcard-meta" id="ovVerStatus"></div>
          <div id="ovVerRollback" style="display:none;margin-top:10px;padding:10px;border:1px solid #c55;border-radius:8px;background:rgba(200,80,80,.08);font-size:13px;line-height:1.6"></div>
        </div>
      </div>
```

- [ ] **Step 2: Add the step constant + the progress drawing function**

Right BEFORE the function `async function ovLoadVersion()` (line 1379) add:

```javascript
    const UPD_STEPS = [
      { key: "preparing", label: "Preparing" },
      { key: "pulling", label: "Downloading code" },
      { key: "installing", label: "Installing libraries" },
      { key: "restarting", label: "Restarting" },
      { key: "health_check", label: "Health check" },
      { key: "done", label: "Done" },
    ];
    function updStepIndex(phase) {
      if (phase === "rolling_back") return 4;        // still in the check/recovery stage
      const i = UPD_STEPS.findIndex(s => s.key === phase);
      return i < 0 ? 0 : i;
    }
    function renderProgress(phase, extra) {
      const box = document.getElementById("ovVerProgress");
      if (!box) return;
      box.style.display = "";
      const at = updStepIndex(phase);
      const dots = UPD_STEPS.map((s, i) => {
        const mark = i < at ? "✅" : (i === at ? "⏳" : "○");
        const w = i === at ? "font-weight:600" : "opacity:.7";
        return `<span style="${w}">${mark} ${esc(s.label)}</span>`;
      }).join('<span style="opacity:.4"> → </span>');
      box.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px">${dots}</div>`
        + (phase === "rolling_back" ? `<div style="margin-top:6px;color:#c55">↩ The new version failed, going back to the old one…</div>` : "")
        + (extra ? `<div style="margin-top:6px;opacity:.85">${esc(extra)}</div>` : "");
    }
```

- [ ] **Step 3: Upgrade `ovLoadVersion()` to show the new version's changelog**

Replace the whole function `ovLoadVersion()` (lines 1379-1407) with:

```javascript
    async function ovLoadVersion() {
      const tag = document.getElementById("ovVerTag");
      const meta = document.getElementById("ovVerMeta");
      const upd = document.getElementById("ovVerUpdate");
      const cl = document.getElementById("ovVerChangelog");
      if (!tag) return;
      meta.textContent = "Checking for a new version…";
      let j = {};
      try { j = await (await fetch("/version", { cache: "no-store" })).json(); }
      catch (e) { meta.textContent = "⚠ Could not check (network)."; return; }
      tag.textContent = "v" + (j.current || "?");
      window._ovVerCur = j.current || "";
      window._ovVerPrev = j.previous_version || "";
      window._ovVerMode = j.mode || "";
      const ml = MODE_LBL[j.mode] || j.mode || "";
      if (cl) { cl.style.display = "none"; cl.innerHTML = ""; }
      if (j.update_available) {
        const base = "🆕 New version <b>v" + esc(j.latest) + "</b> available (running v" + esc(j.current) + ") · " + esc(ml);
        if (j.can_self_update) {
          meta.innerHTML = base;
          upd.style.display = "";
          ovLoadChangelogSnippet(j.current);
        } else {
          meta.innerHTML = base + '<div style="margin-top:8px;line-height:1.55">↻ Update by <b>Redeploy</b>: on Hostinger press the <b>Redeploy</b> button in Docker Manager; on a VPS run <code>docker compose up -d --pull always</code>. If the new version is broken, pin the tag <code>:' + esc(j.previous_version || "old-version") + '</code> and Redeploy to go back.</div>';
          upd.style.display = "none";
          ovLoadChangelogSnippet(j.current);
        }
      } else if (j.latest) {
        meta.innerHTML = "✅ Running the latest version (v" + esc(j.current) + ") · " + esc(ml);
        upd.style.display = "none";
      } else {
        meta.innerHTML = "v" + esc(j.current) + " · " + esc(ml) + (j.error ? " · could not compare with GitHub" : "");
        upd.style.display = "none";
      }
    }
    async function ovLoadChangelogSnippet(current) {
      const cl = document.getElementById("ovVerChangelog");
      if (!cl) return;
      let d = {};
      try { d = await (await fetch("/changelog", { cache: "no-store" })).json(); }
      catch (e) { return; }
      const fresh = (d.releases || []).filter(r => !r.installed).slice(0, 3);
      if (!fresh.length) return;
      cl.style.display = "";
      cl.innerHTML = "<b>What is new:</b><br>" + fresh.map(r => {
        const items = (r.sections || []).flatMap(s => s.items || []).slice(0, 4);
        return "<div style='margin-top:4px'>v" + esc(r.version) + (r.date ? " · " + esc(r.date) : "") + "</div>"
          + "<ul style='margin:2px 0 0 16px;padding:0'>" + items.map(it => "<li>" + esc(it) + "</li>").join("") + "</ul>";
      }).join("");
    }
```

- [ ] **Step 4: Replace the update button handler (poll /update/status)**

Replace the block `if (verUpd) verUpd.onclick = async () => { ... };` (lines 1411-1444) with:

```javascript
    if (verUpd) verUpd.onclick = async () => {
      if (!confirm("Update Jarvis 007 to the latest version?\nThe app will restart itself. If the new version is broken, the system will automatically go back to the old version (git version) or show how to go back (Docker).")) return;
      const st = document.getElementById("ovVerStatus");
      const rb = document.getElementById("ovVerRollback");
      const oldCur = window._ovVerCur || "";
      verUpd.disabled = true;
      if (rb) { rb.style.display = "none"; rb.innerHTML = ""; }
      renderProgress("preparing", "Preparing the update…");
      st.textContent = "";
      let resp;
      try { resp = await (await fetch("/update", { method: "POST" })).json(); }
      catch (e) { resp = { ok: true, _dropped: true }; }   // dropped connection = the server is restarting
      if (resp && resp.ok === false) {
        verUpd.disabled = false;
        renderProgress("preparing", "");
        document.getElementById("ovVerProgress").style.display = "none";
        st.innerHTML = "⚠ " + esc(resp.error || "Could not update.") + (resp.manual ? " Run: <code>" + esc(resp.manual) + "</code>" : "");
        return;
      }
      st.textContent = "⏳ Updating… do not close the page.";
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        // 1) prefer the detailed state from the updater (git version)
        let s = null;
        try { s = await (await fetch("/update/status", { cache: "no-store" })).json(); } catch (e) { s = null; }
        if (s && s.state && s.state.phase) {
          const ph = s.state.phase, res = s.state.result;
          renderProgress(ph);
          if (res === "success") { clearInterval(poll); st.textContent = "✅ Update finished. Reloading the page…"; setTimeout(() => location.reload(), 1500); return; }
          if (res === "rolled_back") { clearInterval(poll); renderProgress("done"); st.innerHTML = "↩ The new version failed, it <b>rolled back to the old one</b>. See <code>update.log</code>."; verUpd.disabled = false; return; }
          if (res === "pull_failed" || res === "rollback_failed" || res === "error") {
            clearInterval(poll);
            st.innerHTML = "⚠ " + esc(s.state.error || "Update failed.") + " See <code>update.log</code>.";
            verUpd.disabled = false; return;
          }
        }
        // 2) fallback: probe /version (docker via Watchtower - updater.py does not run)
        try {
          const v = await (await fetch("/version", { cache: "no-store" })).json();
          if (v && v.update_available === false && v.current && v.current !== oldCur) {
            clearInterval(poll); st.textContent = "✅ Update finished. Reloading the page…"; setTimeout(() => location.reload(), 1500); return;
          }
          // the docker new version may be broken: the server still has the old version after quite a while → show how to go back
          if ((window._ovVerMode === "docker") && tries >= 12 && v && v.current === oldCur) {
            clearInterval(poll);
            const prev = window._ovVerPrev || (v.previous_version || "");
            st.innerHTML = "⚠ The new version is not up after a while - it may be broken.";
            if (rb) {
              rb.style.display = "";
              rb.innerHTML = "<b>How to go back to the old version (Docker):</b><br>Pin the old version tag and pull again:"
                + "<br><code>docker compose pull && docker compose up -d</code>"
                + (prev ? "<br>Or change the image to <code>ghcr.io/blogminhquy/javis-os:" + esc(prev) + "</code> and Redeploy." : "");
            }
            verUpd.disabled = false; return;
          }
        } catch (e) { /* the server is restarting - keep waiting */ }
        if (tries > 60) { clearInterval(poll); st.innerHTML = "The server is not back up after ~3 minutes - try reloading the page."; verUpd.disabled = false; }
      }, 3000);
    };
```

- [ ] **Step 5: Frontend smoke test (NOT automated)**

Open the app → the Overview page (Console view). Confirm: the Version card shows the right version; when there is a new version it shows the changelog snippet + the "Update now" button. (Checking the display does not need a real update click.) If there is a real new version, click it and watch the step bar move Preparing → Downloading code → … and reload by itself when done.

- [ ] **Step 6: Commit**

```bash
git add dashboard/console.js
git commit -m "feat(update): version panel + new-version changelog + progress bar + go-back instructions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Bump version + CHANGELOG + run all tests + push

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: all the tasks above.
- Produces: a new release on main.

- [ ] **Step 1: Rerun the whole update test plus a few related tests**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `ALL PASS`.

Also run (to make sure the places using the old version did not break): `cd server && .venv\Scripts\python.exe test_system_sync.py`
Expected: pass (or the same state as before the change).

- [ ] **Step 2: Bump VERSION**

Change `VERSION` from `0.9.78` to `0.9.79`.

- [ ] **Step 3: Add the CHANGELOG entry**

Add to the top of `CHANGELOG.md` (following the mold `## [x.y.z] - date`, `### Group`, `- item` that `_parse_changelog` can read):

```markdown
## [0.9.79] - 2026-07-18

### Update
- The "Update now" button is more reliable: the Windows version now has a library install step (pip), and handles a dirty git tree so pull does not get stuck.
- Health is checked automatically after updating; if the git version is broken it AUTOMATICALLY GOES BACK to the old version.
- A step-by-step progress bar + shows "what is new" before updating.
- Docker: shows clear go-back-a-version instructions; CI also publishes a version tag so there is an old version to go back to.
```

- [ ] **Step 4: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore(release): 0.9.79 - Thorough update (reliable button + rollback + progress)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 5: Verify after the push**

Open GitHub Actions and confirm the workflow "Build & Publish Docker image" is green and GHCR has the tag `:0.9.79`. (On a real Docker environment, try the update button / Redeploy to check end-to-end.)

---

## Self-Review (done)

**Spec coverage:**
- CI version tag → Task 6. ✓
- update_state (schema, last_good/previous, boot hook) → Task 1 + Task 2. ✓
- /update/status → Task 3. ✓
- /update rewritten (windows/native/docker + guard) → Task 4. ✓
- Updater pip + stash + health + rollback → Task 5 (ps1/update.sh merged into a cross-platform updater.py, noted). ✓
- /version previous_version → Task 2. ✓
- Frontend panel + changelog + progress + go back a version → Task 7. ✓
- Tests → spread across Tasks 1-5, rolled up in Task 8. ✓
- Bump VERSION + CHANGELOG + push → Task 8. ✓

**Deliberate adjustment vs the spec:** the spec lists `win_update.ps1` + editing `update.sh`; the plan merges them into a cross-platform `server/updater.py` (DRY + `update_outcome` and `--dry-run` can be tested). `update.sh` stays as is as a manual CLI command, and native /update now goes through updater.py.

**Placeholder scan:** no TBD/TODO; every code step has real content.

**Type consistency:** function names are consistent across tasks - `read_state/write_state/record_boot_version/update_outcome` (update_state) are reused in main (aliases `_read_update_state`...) and the updater (`us.*`); the `phase`/`result` strings are consistent between updater.py (writes) and console.js (reads): `preparing/pulling/installing/restarting/health_check/rolling_back/done` and result `success/rolled_back/pull_failed/rollback_failed/error/version_mismatch(→result=error)`.
