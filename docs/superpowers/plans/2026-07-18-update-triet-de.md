# Update triệt để cho Jarvis 007 - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nút "Cập nhật ngay" chắc chắn trên mọi môi trường, hiện tiến trình rõ ràng, tự rollback bản git khi bản mới lỗi và hướng dẫn lùi bản trên Docker.

**Architecture:** Tách logic thuần (so sánh phiên bản, đọc/ghi trạng thái update, quyết định rollback) vào module `server/update_state.py` để unit-test. Một updater Python đa nền `server/updater.py` do `POST /update` spawn tách rời làm chuỗi stop -> pull -> pip -> start -> health-check -> rollback cho bản git (Windows + native). Docker giữ Watchtower/Redeploy (Hướng B: tag phiên bản + hướng dẫn lùi). Frontend đọc `GET /update/status` để vẽ tiến trình.

**Tech Stack:** Python 3.12 + FastAPI (server), urllib/subprocess (updater, stdlib only), vanilla JS (dashboard/console.js), GitHub Actions (CI), Docker/GHCR.

## Global Constraints

- TUYỆT ĐỐI không dùng ký tự em dash (U+2014) ở bất kỳ đâu (chat/file/code/comment). Dùng "-".
- Tiếng Việt cho comment + chuỗi hiển thị.
- Test là script standalone chạy `cd server && .venv\Scripts\python.exe test_update.py` (KHÔNG pytest), theo khuôn `check(name, cond)` + `sys.exit(1)` khi có FAIL (xem `server/test_path_exists.py`).
- Chạy test bằng `.venv` (python hệ thống thiếu lib).
- `config.STATE_DIR = Path(os.getenv("JAVIS_STATE_DIR", <server dir>))`. Test set `JAVIS_STATE_DIR` sang temp TRƯỚC khi import module.
- App trong Docker KHÔNG có docker socket - không tự đổi/lùi image (giữ nguyên).
- Không làm auto-update nền, không viết updater sidecar Docker.
- Repo: `blogminhquy/javis-os`. Image GHCR: `ghcr.io/blogminhquy/javis-os`.
- Xong toàn bộ + test xanh mới bump VERSION + CHANGELOG + commit + push origin/main.

---

## File Structure

- Create `server/update_state.py` - module thuần: version compare + đọc/ghi `update_state.json` + `update_outcome()` + `record_boot_version()`. Dùng chung bởi main.py và updater.py.
- Create `server/updater.py` - updater đa nền chạy tách rời (stop/pull/pip/start/health/rollback).
- Create `server/test_update.py` - test cho update_state + endpoint + updater dry-run.
- Modify `server/main.py` - dùng update_state; thêm `previous_version` vào `/version`; thêm `GET /update/status`; viết lại `POST /update`; hook boot ghi version; bỏ sinh `_selfupdate.bat`.
- Modify `.github/workflows/docker-publish.yml` - thêm tag `:<version>`.
- Modify `dashboard/console.js` - panel phiên bản + changelog snippet + thanh tiến trình + panel lùi bản.
- Modify `VERSION`, `CHANGELOG.md` - bump khi hoàn tất.

---

## Task 1: Module thuần `update_state.py`

**Files:**
- Create: `server/update_state.py`
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `config.STATE_DIR` (từ `server/config.py`).
- Produces:
  - `STATE_DIR: Path`, `STATE_FILE: Path`
  - `ver_tuple(s: str) -> tuple|None`
  - `ver_newer(latest: str, cur: str) -> bool`
  - `read_state() -> dict`
  - `write_state(patch: dict) -> dict`
  - `record_boot_version(current: str) -> dict`
  - `update_outcome(health_ok: bool, current: str, old: str, target: str|None) -> str` (trả `"success"|"version_mismatch"|"need_rollback"`)

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_update.py`:

```python
"""Test tầng cập nhật: update_state (thuần) + endpoint /update/status + updater dry-run.
Chạy:  cd server && .venv\\Scripts\\python.exe test_update.py    (KHÔNG mạng)."""
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
check("ver_newer bằng nhau → False", us.ver_newer("1.0.0", "1.0.0") is False)
check("ver_newer local ahead → False", us.ver_newer("0.9.78", "0.9.79") is False)
check("ver_tuple rác → coi như (0,0,0), không crash", us.ver_tuple("abc") == (0, 0, 0))

# --- state round-trip ---
us.write_state({"phase": "installing", "old_version": "0.9.78"})
st = us.read_state()
check("write/read state giữ phase", st.get("phase") == "installing")
check("write/read state giữ old_version", st.get("old_version") == "0.9.78")
us.write_state({"phase": "done"})
check("write_state merge (không mất field cũ)", us.read_state().get("old_version") == "0.9.78")

# --- record_boot_version ---
us.STATE_FILE.unlink(missing_ok=True)
us.record_boot_version("0.9.78")
check("boot lần đầu: last_good = current", us.read_state().get("last_good_version") == "0.9.78")
check("boot lần đầu: chưa có previous", us.read_state().get("previous_version") is None)
us.record_boot_version("0.9.79")
check("boot lên bản mới: last_good cập nhật", us.read_state().get("last_good_version") == "0.9.79")
check("boot lên bản mới: previous = bản cũ", us.read_state().get("previous_version") == "0.9.78")

# --- update_outcome ---
check("health đỏ → need_rollback", us.update_outcome(False, "0.9.79", "0.9.78", "0.9.79") == "need_rollback")
check("health xanh + đúng target → success", us.update_outcome(True, "0.9.79", "0.9.78", "0.9.79") == "success")
check("health xanh + version tiến (target rỗng) → success", us.update_outcome(True, "0.9.79", "0.9.78", None) == "success")
check("health xanh nhưng version chưa đổi → version_mismatch", us.update_outcome(True, "0.9.78", "0.9.78", "0.9.79") == "version_mismatch")

print()
if _fails:
    print(f"{len(_fails)} FAIL: {_fails}"); sys.exit(1)
print("TẤT CẢ PASS")
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL với `ModuleNotFoundError: No module named 'update_state'`.

- [ ] **Step 3: Viết `server/update_state.py`**

```python
"""Tầng thuần dùng chung cho cập nhật: so sánh phiên bản + đọc/ghi update_state.json +
quyết định rollback. Không phụ thuộc FastAPI/main → import được từ cả main.py lẫn updater.py."""
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
    """So sánh semver: latest MỚI HƠN cur? (tránh báo nhầm khi local ahead / lệch định dạng)."""
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
    """Merge patch vào state hiện có rồi ghi. Trả state sau khi ghi."""
    st = read_state()
    st.update(patch)
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return st


def record_boot_version(current: str) -> dict:
    """Chạy mỗi lần khởi động: duy trì last_good_version + previous_version để mọi mode biết
    'lùi về đâu'. Vừa lên bản mới hơn thì previous = last_good cũ."""
    st = read_state()
    last_good = st.get("last_good_version")
    patch = {}
    if last_good and last_good != current and ver_newer(current, last_good):
        patch["previous_version"] = last_good
    patch["last_good_version"] = current
    return write_state(patch)


def update_outcome(health_ok: bool, current: str, old: str, target=None) -> str:
    """Kết quả sau khi thử bật bản mới. Tách riêng để test được (poll health nằm ở updater)."""
    if not health_ok:
        return "need_rollback"
    ct, tt = ver_tuple(current), ver_tuple(target)
    if target and ct and tt and ct >= tt:
        return "success"
    if ver_newer(current, old):
        return "success"
    return "version_mismatch"
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/update_state.py server/test_update.py
git commit -m "feat(update): module thuần update_state (version compare + state + outcome) + test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Nối main.py dùng update_state + previous_version + hook boot

**Files:**
- Modify: `server/main.py` (import ~line 29; xoá `_ver_tuple`/`_ver_newer` cũ ~3626-3642; `version_info` ~3688; startup `_start_scheduler` ~3462-3469)
- Test: `server/test_update.py` (thêm ca)

**Interfaces:**
- Consumes: `update_state.ver_tuple/ver_newer/read_state/write_state/record_boot_version/update_outcome` (Task 1).
- Produces: alias `_ver_tuple`, `_ver_newer`, `_read_update_state`, `_write_update_state`, `_record_boot_version`, `_update_outcome` trong main (giữ tên cũ cho code hiện có); `/version` trả thêm `previous_version`.

- [ ] **Step 1: Thêm import + alias trong main.py**

Sau dòng `import config as cfgmod` (main.py:29) thêm:

```python
import update_state
_ver_tuple = update_state.ver_tuple
_ver_newer = update_state.ver_newer
_read_update_state = update_state.read_state
_write_update_state = update_state.write_state
_record_boot_version = update_state.record_boot_version
_update_outcome = update_state.update_outcome
```

- [ ] **Step 2: Xoá 2 def trùng trong main.py**

Xoá nguyên hàm `def _ver_tuple(...)` (main.py ~3626-3633) và `def _ver_newer(...)` (~3636-3642). Các chỗ gọi `_ver_tuple`/`_ver_newer` giữ nguyên (đã có alias ở Step 1).

- [ ] **Step 3: `/version` trả thêm previous_version**

Trong `version_info()` (main.py ~3708), đổi return thành:

```python
    st = _read_update_state()
    return {"current": cur, "latest": latest, "update_available": avail,
            "mode": mode, "can_self_update": can, "error": err,
            "previous_version": st.get("previous_version")}
```

- [ ] **Step 4: Hook ghi version lúc boot**

Trong `_start_scheduler()` (main.py:3462), sau dòng `_sync_system_all_brains()` (3469) thêm:

```python
    try:
        _record_boot_version(_read_version())   # duy trì last_good/previous cho tính năng lùi bản
    except Exception:
        pass
```

- [ ] **Step 5: Thêm ca test cho /version + import main**

Nối cuối `server/test_update.py` (trước phần in kết quả `print()`):

```python
# --- main.py dùng update_state + /version có previous_version ---
import asyncio  # noqa: E402
import main  # noqa: E402
check("main alias _ver_newer chạy", main._ver_newer("0.9.79", "0.9.78") is True)
us.STATE_FILE.unlink(missing_ok=True)
us.write_state({"previous_version": "0.9.77"})
_v = asyncio.run(main.version_info())
check("/version có khoá previous_version", "previous_version" in _v)
check("/version previous_version đúng giá trị", _v.get("previous_version") == "0.9.77")
```

- [ ] **Step 6: Chạy test**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS` (lưu ý: `version_info` gọi mạng GitHub để lấy latest; mất mạng thì `latest=None` nhưng ca test chỉ kiểm `previous_version` nên vẫn PASS).

- [ ] **Step 7: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "refactor(update): main dùng update_state; /version thêm previous_version; hook boot

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Endpoint `GET /update/status`

**Files:**
- Modify: `server/main.py` (thêm endpoint cạnh `/version`, ~sau dòng 3709)
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `_read_update_state()` (Task 2); `cfgmod.STATE_DIR`.
- Produces: `GET /update/status -> {"state": dict, "log_tail": str}`; hàm `update_status()` gọi trực tiếp được trong test.

- [ ] **Step 1: Viết test thất bại**

Nối cuối `server/test_update.py` (trước `print()`):

```python
# --- /update/status ---
us.write_state({"phase": "health_check", "result": None})
(us.STATE_DIR / "update.log").write_text("dong 1\ndong 2\ndong 3\n", encoding="utf-8")
_s = asyncio.run(main.update_status())
check("/update/status trả state.phase", _s["state"].get("phase") == "health_check")
check("/update/status trả log_tail", "dong 3" in _s["log_tail"])
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL với `AttributeError: module 'main' has no attribute 'update_status'`.

- [ ] **Step 3: Thêm endpoint vào main.py**

Sau `version_info()` (main.py ~3709), thêm:

```python
@app.get("/update/status")
async def update_status():
    """Trạng thái cập nhật (UI poll để vẽ tiến trình). Đọc update_state.json + ~50 dòng cuối
    update.log. File sống qua restart nên sau khi server lên lại vẫn báo được kết quả."""
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

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "feat(update): endpoint GET /update/status (state + đuôi log) cho thanh tiến trình

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Viết lại `POST /update` (dispatch + guard)

**Files:**
- Modify: `server/main.py` (thay nguyên `do_update()` ~3712-3764)
- Test: `server/test_update.py`

**Interfaces:**
- Consumes: `_deploy_mode()`, `_read_version()`, `_is_git_checkout()`, `_watchtower_reachable()`, `_read_update_state()`, `_write_update_state()`, `PROJECT_ROOT`, `GITHUB_REPO`.
- Produces: `do_update()` mới: git mode spawn `server/updater.py` tách rời; docker giữ Watchtower/guided; guard chạy trùng (409); hàm `_git_head(root)`.

- [ ] **Step 1: Viết test thất bại (guard chạy trùng)**

Nối cuối `server/test_update.py` (trước `print()`):

```python
# --- POST /update chống chạy trùng ---
from fastapi.responses import JSONResponse  # noqa: E402
us.write_state({"phase": "pulling", "started_at": "2026-07-18T10:00:00"})
_r = asyncio.run(main.do_update())
check("update đang chạy → trả 409", isinstance(_r, JSONResponse) and _r.status_code == 409)
us.write_state({"phase": "idle"})  # dọn để không kẹt
check("có hàm _git_head", callable(getattr(main, "_git_head", None)))
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL ở ca guard 409 (hàm cũ chưa có guard) hoặc thiếu `_git_head`.

- [ ] **Step 3: Thay `do_update()` trong main.py**

Thay nguyên hàm `do_update()` (main.py ~3712-3764) bằng:

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
    """Cập nhật lên bản mới nhất. Git checkout (windows/native) → spawn updater.py TÁCH RỜI
    (stop/pull/pip/start/health/rollback). Docker → Watchtower nếu có, không thì hướng dẫn Redeploy."""
    import sys as _sys
    import subprocess
    import datetime as _dt
    now = lambda: _dt.datetime.now().isoformat(timespec="seconds")

    st = _read_update_state()
    if st.get("phase") in _UPDATE_ACTIVE:
        return JSONResponse({"ok": False, "error": "Đang cập nhật rồi, chờ chút.",
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
                "error": "Bản Docker cập nhật bằng REDEPLOY để kéo image mới: trên Hostinger bấm Redeploy trong Docker Manager; trên VPS chạy lệnh dưới. Nếu bản mới lỗi, pin tag phiên bản cũ rồi Redeploy để lùi.",
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
        return {"ok": True, "mode": "docker", "message": "Đang kéo image mới + khởi động lại (~20-40s)."}

    # git checkout (windows / native)
    root = str(PROJECT_ROOT)
    if not _is_git_checkout(root):
        return JSONResponse({"ok": False,
            "error": "Thư mục cài đặt không phải git checkout → không tự cập nhật được. Cài lại bằng 'git clone' hoặc cập nhật thủ công.",
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
                "message": "Đang cập nhật + khởi động lại (theo dõi ở thanh tiến trình)."}
    except Exception as e:
        _write_update_state({"phase": "error", "result": "error", "error": str(e), "finished_at": now()})
        return JSONResponse({"ok": False, "error": str(e), "manual": "./update.sh"}, status_code=500)
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/test_update.py
git commit -m "feat(update): POST /update spawn updater.py cho git mode + guard chạy trùng + guided docker

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Updater đa nền `server/updater.py`

**Files:**
- Create: `server/updater.py`
- Delete (logic cũ): trong main.py không còn sinh `_selfupdate.bat` (đã bỏ ở Task 4). File `server/_selfupdate.bat` cũ (untracked ở STATE_DIR) không cần xoá tay.
- Test: `server/test_update.py` (ca dry-run)

**Interfaces:**
- Consumes: `update_state` (Task 1); CLI args `--old-sha --old-version --target --port [--dry-run]`.
- Produces: chương trình chạy tách rời ghi `update_state.json` + `update.log`. `--dry-run` in "PLAN:" và thoát 0 (để test).

- [ ] **Step 1: Viết test thất bại (dry-run)**

Nối cuối `server/test_update.py` (trước `print()`):

```python
# --- updater.py --dry-run (không thực thi git/pip) ---
import subprocess as _sp  # noqa: E402
_upd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "updater.py")
_p = _sp.run([sys.executable, _upd, "--dry-run", "--port", "7777"],
             capture_output=True, text=True, env={**os.environ})
check("updater --dry-run thoát 0", _p.returncode == 0)
check("updater --dry-run in PLAN", "PLAN:" in (_p.stdout or ""))
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: FAIL (updater.py chưa tồn tại → returncode != 0).

- [ ] **Step 3: Viết `server/updater.py`**

```python
#!/usr/bin/env python
"""Updater tách rời của Jarvis 007 cho bản GIT checkout (Windows + native Linux). Server spawn DETACHED:

    python updater.py --old-sha <sha> --old-version <v> --target <v> --port <p>

Chuỗi: stop server -> git pull (stash nếu cây bẩn) -> pip install -> start -> chờ /health ~90s.
/health không lên → git reset --hard <old-sha> -> pip -> start (rollback tự động).
Chỉ dùng stdlib (chạy được cả khi bản mới hỏng dependency)."""
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
        print(f"PLAN: stop -> pull(stash nếu bẩn) -> pip -> start -> health({a.port}) "
              f"-> rollback(reset {a.old_sha or '?'}) nếu không lên")
        return 0

    target = a.target or None
    us.write_state({"phase": "restarting", "started_at": _now(), "finished_at": None,
                    "result": None, "error": None, "old_sha": a.old_sha,
                    "old_version": a.old_version, "target_version": target})

    if os.name != "nt" and not has_systemd():
        log("Không thấy systemd service 'javis' → không tự khởi động lại được. Hãy restart tay.")
        us.write_state({"phase": "error", "result": "error",
                        "error": "Không có systemd service 'javis' để tự khởi động lại.",
                        "finished_at": _now()})
        return 1

    log("Dừng server cũ…")
    stop_server()
    time.sleep(2)

    us.write_state({"phase": "pulling"})
    if git_dirty():
        log("Cây git có sửa đổi cục bộ → git stash (giữ lại, không mất).")
        run(["git", "stash"])
        us.write_state({"stashed": True})
    pull = run(["git", "pull", "--ff-only"])
    if pull.returncode != 0:
        log("git pull LỖI:\n" + (pull.stderr or pull.stdout or ""))
        start_server()
        us.write_state({"phase": "error", "result": "pull_failed",
                        "error": (pull.stderr or "git pull thất bại")[:500], "finished_at": _now()})
        return 1

    us.write_state({"phase": "installing"})
    log("Cài thư viện…")
    pip_install()

    us.write_state({"phase": "restarting"})
    log("Khởi động bản mới…")
    start_server()

    us.write_state({"phase": "health_check"})
    log("Kiểm tra sức khoẻ…")
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
                        "error": "Server lên nhưng phiên bản chưa đổi (pull chưa áp?). Xem update.log.",
                        "finished_at": _now()})
        return 1

    # need_rollback
    log("Bản mới KHÔNG lên được → tự lùi về bản cũ…")
    us.write_state({"phase": "rolling_back"})
    if not a.old_sha:
        us.write_state({"phase": "error", "result": "rollback_failed",
                        "error": "Không có commit cũ để lùi.", "finished_at": _now()})
        return 1
    run(["git", "reset", "--hard", a.old_sha])
    pip_install()
    start_server()
    if poll_health(a.port, 90):
        us.write_state({"phase": "done", "result": "rolled_back",
                        "error": "Bản mới lỗi, đã tự quay về bản cũ.", "finished_at": _now()})
        return 0
    us.write_state({"phase": "error", "result": "rollback_failed",
                    "error": "Bản mới lỗi và lùi bản cũng chưa lên. Xem update.log.", "finished_at": _now()})
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS`.

- [ ] **Step 5: Smoke test tay trên Windows (KHÔNG tự động)**

Chỉ chạy khi có bản mới thật trên GitHub. Mở app, trang Tổng quan, bấm "Cập nhật ngay". Quan sát `STATE_DIR/update.log` + thanh tiến trình. Xác nhận: pull + `pip install` chạy, server lên lại đúng bản mới. (Nếu muốn thử rollback: tạo 1 commit lỗi cố ý trên nhánh test rồi trỏ tới - KHÔNG làm trên main.)

- [ ] **Step 6: Commit**

```bash
git add server/updater.py server/test_update.py
git commit -m "feat(update): updater.py đa nền - stop/pull/pip/start/health + tự rollback bản git

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: CI tag phiên bản trên GHCR

**Files:**
- Modify: `.github/workflows/docker-publish.yml` (step "Build & push", ~dòng 42-44)

**Interfaces:**
- Consumes: file `VERSION` ở gốc repo.
- Produces: image GHCR có thêm tag `:<version>` (vd `:0.9.79`) cạnh `:latest` và `:<sha>`.

- [ ] **Step 1: Thêm bước đọc VERSION**

Trong `.github/workflows/docker-publish.yml`, sau step "Set lowercase image name" (dòng 25-26), thêm:

```yaml
      - name: Read app version
        run: echo "APP_VERSION=$(cat VERSION | tr -d ' \n\r')" >> "$GITHUB_ENV"
```

- [ ] **Step 2: Thêm tag phiên bản vào step Build & push**

Đổi khối `tags:` (dòng 42-44) thành:

```yaml
          tags: |
            ${{ env.IMAGE }}:latest
            ${{ env.IMAGE }}:${{ github.sha }}
            ${{ env.IMAGE }}:${{ env.APP_VERSION }}
```

- [ ] **Step 3: Kiểm tra cú pháp workflow**

Run: `git diff .github/workflows/docker-publish.yml`
Expected: chỉ thêm step "Read app version" và 1 dòng tag `:${{ env.APP_VERSION }}`. Không đụng phần khác. (Xác minh thật diễn ra khi push: xem Actions build xanh + GHCR có tag phiên bản.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docker-publish.yml
git commit -m "ci(update): tag image GHCR theo phiên bản (:x.y.z) để có bản cũ mà lùi

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Frontend - panel phiên bản + tiến trình + lùi bản

**Files:**
- Modify: `dashboard/console.js` (HTML card ~1319-1331; handler ~1379-1445)

**Interfaces:**
- Consumes: `GET /version` (thêm `previous_version`), `GET /changelog`, `POST /update`, `GET /update/status`.
- Produces: card phiên bản mới với changelog snippet, thanh tiến trình theo bước, panel lùi bản (docker).

- [ ] **Step 1: Thay HTML card phiên bản**

Trong `dashboard/console.js`, thay khối `<div class="cview-section"><h3>Phiên bản</h3>...</div>` (dòng 1320-1331) bằng:

```javascript
      <div class="cview-section">
        <h3>Phiên bản</h3>
        <div class="gcard" style="max-width:640px">
          <div class="gcard-top"><span class="gcard-name">Jarvis 007</span><span class="gcard-tag" id="ovVerTag">…</span></div>
          <div class="gcard-meta" id="ovVerMeta">Đang kiểm tra bản mới…</div>
          <div id="ovVerChangelog" style="display:none;margin:8px 0;padding:8px 10px;border-left:3px solid var(--accent,#6aa);background:rgba(120,140,160,.08);border-radius:6px;font-size:13px;line-height:1.6"></div>
          <div class="js-actions">
            <button class="gcard-btn ghost" id="ovVerCheck">Kiểm tra lại</button>
            <button class="gcard-btn" id="ovVerUpdate" style="display:none">⬆ Cập nhật ngay</button>
          </div>
          <div id="ovVerProgress" style="display:none;margin-top:10px"></div>
          <div class="gcard-meta" id="ovVerStatus"></div>
          <div id="ovVerRollback" style="display:none;margin-top:10px;padding:10px;border:1px solid #c55;border-radius:8px;background:rgba(200,80,80,.08);font-size:13px;line-height:1.6"></div>
        </div>
      </div>
```

- [ ] **Step 2: Thêm hằng bước + hàm vẽ tiến trình**

Ngay TRƯỚC hàm `async function ovLoadVersion()` (dòng 1379) thêm:

```javascript
    const UPD_STEPS = [
      { key: "preparing", label: "Chuẩn bị" },
      { key: "pulling", label: "Tải code" },
      { key: "installing", label: "Cài thư viện" },
      { key: "restarting", label: "Khởi động lại" },
      { key: "health_check", label: "Kiểm tra sức khoẻ" },
      { key: "done", label: "Xong" },
    ];
    function updStepIndex(phase) {
      if (phase === "rolling_back") return 4;        // vẫn ở giai đoạn kiểm tra/khôi phục
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
        + (phase === "rolling_back" ? `<div style="margin-top:6px;color:#c55">↩ Bản mới lỗi, đang tự quay về bản cũ…</div>` : "")
        + (extra ? `<div style="margin-top:6px;opacity:.85">${esc(extra)}</div>` : "");
    }
```

- [ ] **Step 3: Nâng `ovLoadVersion()` để hiện changelog bản mới**

Thay nguyên hàm `ovLoadVersion()` (dòng 1379-1407) bằng:

```javascript
    async function ovLoadVersion() {
      const tag = document.getElementById("ovVerTag");
      const meta = document.getElementById("ovVerMeta");
      const upd = document.getElementById("ovVerUpdate");
      const cl = document.getElementById("ovVerChangelog");
      if (!tag) return;
      meta.textContent = "Đang kiểm tra bản mới…";
      let j = {};
      try { j = await (await fetch("/version", { cache: "no-store" })).json(); }
      catch (e) { meta.textContent = "⚠ Không kiểm tra được (mạng)."; return; }
      tag.textContent = "v" + (j.current || "?");
      window._ovVerCur = j.current || "";
      window._ovVerPrev = j.previous_version || "";
      window._ovVerMode = j.mode || "";
      const ml = MODE_LBL[j.mode] || j.mode || "";
      if (cl) { cl.style.display = "none"; cl.innerHTML = ""; }
      if (j.update_available) {
        const base = "🆕 Có bản mới <b>v" + esc(j.latest) + "</b> (đang chạy v" + esc(j.current) + ") · " + esc(ml);
        if (j.can_self_update) {
          meta.innerHTML = base;
          upd.style.display = "";
          ovLoadChangelogSnippet(j.current);
        } else {
          meta.innerHTML = base + '<div style="margin-top:8px;line-height:1.55">↻ Cập nhật bằng cách <b>Redeploy</b>: trên Hostinger bấm nút <b>Redeploy</b> trong Docker Manager; trên VPS chạy <code>docker compose up -d --pull always</code>. Bản mới lỗi thì pin tag <code>:' + esc(j.previous_version || "bản-cũ") + '</code> rồi Redeploy để lùi.</div>';
          upd.style.display = "none";
          ovLoadChangelogSnippet(j.current);
        }
      } else if (j.latest) {
        meta.innerHTML = "✅ Đang dùng bản mới nhất (v" + esc(j.current) + ") · " + esc(ml);
        upd.style.display = "none";
      } else {
        meta.innerHTML = "v" + esc(j.current) + " · " + esc(ml) + (j.error ? " · chưa so được với GitHub" : "");
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
      cl.innerHTML = "<b>Bản mới có gì:</b><br>" + fresh.map(r => {
        const items = (r.sections || []).flatMap(s => s.items || []).slice(0, 4);
        return "<div style='margin-top:4px'>v" + esc(r.version) + (r.date ? " · " + esc(r.date) : "") + "</div>"
          + "<ul style='margin:2px 0 0 16px;padding:0'>" + items.map(it => "<li>" + esc(it) + "</li>").join("") + "</ul>";
      }).join("");
    }
```

- [ ] **Step 4: Thay handler nút cập nhật (poll /update/status)**

Thay khối `if (verUpd) verUpd.onclick = async () => { ... };` (dòng 1411-1444) bằng:

```javascript
    if (verUpd) verUpd.onclick = async () => {
      if (!confirm("Cập nhật Jarvis 007 lên bản mới nhất?\nApp sẽ tự khởi động lại. Nếu bản mới lỗi, hệ thống sẽ tự quay về bản cũ (bản git) hoặc hiện cách lùi (Docker).")) return;
      const st = document.getElementById("ovVerStatus");
      const rb = document.getElementById("ovVerRollback");
      const oldCur = window._ovVerCur || "";
      verUpd.disabled = true;
      if (rb) { rb.style.display = "none"; rb.innerHTML = ""; }
      renderProgress("preparing", "Đang chuẩn bị cập nhật…");
      st.textContent = "";
      let resp;
      try { resp = await (await fetch("/update", { method: "POST" })).json(); }
      catch (e) { resp = { ok: true, _dropped: true }; }   // đứt kết nối = server đang restart
      if (resp && resp.ok === false) {
        verUpd.disabled = false;
        renderProgress("preparing", "");
        document.getElementById("ovVerProgress").style.display = "none";
        st.innerHTML = "⚠ " + esc(resp.error || "Không cập nhật được.") + (resp.manual ? " Chạy: <code>" + esc(resp.manual) + "</code>" : "");
        return;
      }
      st.textContent = "⏳ Đang cập nhật… đừng tắt trang.";
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        // 1) ưu tiên trạng thái chi tiết từ updater (bản git)
        let s = null;
        try { s = await (await fetch("/update/status", { cache: "no-store" })).json(); } catch (e) { s = null; }
        if (s && s.state && s.state.phase) {
          const ph = s.state.phase, res = s.state.result;
          renderProgress(ph);
          if (res === "success") { clearInterval(poll); st.textContent = "✅ Đã cập nhật xong. Đang tải lại trang…"; setTimeout(() => location.reload(), 1500); return; }
          if (res === "rolled_back") { clearInterval(poll); renderProgress("done"); st.innerHTML = "↩ Bản mới lỗi, đã <b>tự quay về bản cũ</b>. Xem <code>update.log</code>."; verUpd.disabled = false; return; }
          if (res === "pull_failed" || res === "rollback_failed" || res === "error") {
            clearInterval(poll);
            st.innerHTML = "⚠ " + esc(s.state.error || "Cập nhật lỗi.") + " Xem <code>update.log</code>.";
            verUpd.disabled = false; return;
          }
        }
        // 2) fallback: dò /version (docker qua Watchtower - updater.py không chạy)
        try {
          const v = await (await fetch("/version", { cache: "no-store" })).json();
          if (v && v.update_available === false && v.current && v.current !== oldCur) {
            clearInterval(poll); st.textContent = "✅ Đã cập nhật xong. Đang tải lại trang…"; setTimeout(() => location.reload(), 1500); return;
          }
          // docker bản mới có thể lỗi: server vẫn còn bản cũ sau khá lâu → hiện cách lùi
          if ((window._ovVerMode === "docker") && tries >= 12 && v && v.current === oldCur) {
            clearInterval(poll);
            const prev = window._ovVerPrev || (v.previous_version || "");
            st.innerHTML = "⚠ Bản mới chưa lên sau một lúc - có thể lỗi.";
            if (rb) {
              rb.style.display = "";
              rb.innerHTML = "<b>Cách lùi về bản cũ (Docker):</b><br>Pin tag phiên bản cũ rồi kéo lại:"
                + "<br><code>docker compose pull && docker compose up -d</code>"
                + (prev ? "<br>Hoặc sửa image thành <code>ghcr.io/blogminhquy/javis-os:" + esc(prev) + "</code> rồi Redeploy." : "");
            }
            verUpd.disabled = false; return;
          }
        } catch (e) { /* server đang restart - chờ tiếp */ }
        if (tries > 60) { clearInterval(poll); st.innerHTML = "Server chưa lên lại sau ~3 phút - thử tải lại trang."; verUpd.disabled = false; }
      }, 3000);
    };
```

- [ ] **Step 5: Smoke test frontend (KHÔNG tự động)**

Mở app → trang Tổng quan (Console view). Xác nhận: card Phiên bản hiện đúng version; khi có bản mới thì hiện changelog snippet + nút "Cập nhật ngay". (Kiểm tra hiển thị không cần bấm update thật.) Nếu có bản mới thật, bấm và quan sát thanh bước chuyển Chuẩn bị → Tải code → … và tự reload khi xong.

- [ ] **Step 6: Commit**

```bash
git add dashboard/console.js
git commit -m "feat(update): panel phiên bản + changelog bản mới + thanh tiến trình + hướng dẫn lùi bản

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Bump phiên bản + CHANGELOG + chạy toàn bộ test + push

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: mọi task trên.
- Produces: bản phát hành mới trên main.

- [ ] **Step 1: Chạy lại toàn bộ test cập nhật + vài test liên quan**

Run: `cd server && .venv\Scripts\python.exe test_update.py`
Expected: `TẤT CẢ PASS`.

Run thêm (đảm bảo không vỡ chỗ dùng version cũ): `cd server && .venv\Scripts\python.exe test_system_sync.py`
Expected: pass (hoặc trạng thái như trước khi sửa).

- [ ] **Step 2: Bump VERSION**

Đổi `VERSION` từ `0.9.78` thành `0.9.79`.

- [ ] **Step 3: Thêm mục CHANGELOG**

Thêm lên đầu `CHANGELOG.md` (theo khuôn `## [x.y.z] - ngày`, `### Nhóm`, `- việc` mà `_parse_changelog` đọc được):

```markdown
## [0.9.79] - 2026-07-18

### Cập nhật
- Nút "Cập nhật ngay" chắc hơn: bản Windows nay có bước cài thư viện (pip), xử lý cây git bẩn khỏi kẹt pull.
- Tự kiểm tra sức khoẻ sau khi cập nhật; bản git lỗi thì TỰ QUAY VỀ bản cũ.
- Thanh tiến trình theo bước + hiện "bản mới có gì" trước khi cập nhật.
- Docker: hiện hướng dẫn lùi bản rõ ràng; CI xuất thêm tag phiên bản để có bản cũ mà lùi.
```

- [ ] **Step 4: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore(release): 0.9.79 - Update triệt để (nút chắc + rollback + tiến trình)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 5: Xác minh sau push**

Mở GitHub Actions xác nhận workflow "Build & Publish Docker image" xanh và GHCR có tag `:0.9.79`. (Nếu là môi trường Docker thật, thử nút cập nhật / Redeploy để kiểm end-to-end.)

---

## Self-Review (đã rà)

**Spec coverage:**
- CI tag phiên bản → Task 6. ✓
- update_state (schema, last_good/previous, boot hook) → Task 1 + Task 2. ✓
- /update/status → Task 3. ✓
- /update viết lại (windows/native/docker + guard) → Task 4. ✓
- Updater pip + stash + health + rollback → Task 5 (gộp ps1/update.sh thành updater.py đa nền, có ghi chú). ✓
- /version previous_version → Task 2. ✓
- Frontend panel + changelog + tiến trình + lùi bản → Task 7. ✓
- Test → rải trong Task 1-5, tổng hợp Task 8. ✓
- Bump VERSION + CHANGELOG + push → Task 8. ✓

**Điều chỉnh có chủ đích so với spec:** spec nêu `win_update.ps1` + sửa `update.sh`; plan gộp thành `server/updater.py` đa nền (DRY + test được `update_outcome` và `--dry-run`). `update.sh` giữ nguyên làm lệnh thủ công CLI, native /update nay đi qua updater.py.

**Placeholder scan:** không có TBD/TODO; mọi step code có nội dung thật.

**Type consistency:** tên hàm nhất quán giữa các task - `read_state/write_state/record_boot_version/update_outcome` (update_state) dùng lại trong main (alias `_read_update_state`...) và updater (`us.*`); `phase`/`result` string thống nhất giữa updater.py (ghi) và console.js (đọc): `preparing/pulling/installing/restarting/health_check/rolling_back/done` và result `success/rolled_back/pull_failed/rollback_failed/error/version_mismatch(→result=error)`.
