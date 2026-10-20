# Partners page + workflow run history store - Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One "Partners" page replaces the two pages Agents and Workflows. You can chat with each agent and each workflow in the app's existing chat frame, every workflow run is saved, and Jarvis 007 can look runs up.

**Architecture:** Everything is a chat session: a session on channel `agent:<slug>` swaps the system prompt for that agent's prompt, and a session on channel `workflow:<slug>` turns each message into one `execute_workflow` run and returns the result as a chat turn. The `workflow_runs.sqlite3` store records every run (from the Partners page and from Kanban). The dashboard reuses the existing chat frame and adds a left column (list) and a right column (settings / progress / history).

**Tech Stack:** Python 3 + FastAPI + sqlite3 (server/), vanilla JS + Alpine (dashboard/), tests run with `python tests/run.py <filter>` (picks .venv automatically), JS tests with node.

**Spec:** `docs/superpowers/specs/2026-09-15-cong-su-workspace-design.md`

## Global Constraints

- Do NOT use the em dash character (U+2014) anywhere: code, strings, comments, docs, CHANGELOG. Use "-" or rewrite the sentence.
- User-facing strings must be Vietnamese with diacritics, taken from the dictionary `dashboard/i18n/vi.json` (with `en.json` alongside), never hard-coded in JS.
- New function/variable names on the server follow the repo style (Vietnamese without diacritics, or short English); comments are in Vietnamese and explain WHY.
- A new page must be registered in all three places: `RAIL_ITEMS` (dashboard/console.js), `PAGES` (dashboard/ui-actions.js), `PAGES` (server/ui_targets.py). `tests/js/test_ui_actions.js` guards this.
- Python tests follow the repo mould: file `tests/python/test_<name>.py`, start with `from _paths import ROOT, SERVER`, set `os.environ["JAVIS_STATE_DIR"]` to a temp folder BEFORE importing the server module, a `check(name, cond)` function that prints `ok`/`FAIL`, and `sys.exit(1 if fails else 0)` at the end.
- Run tests: `python tests/run.py <filter-name>` (on Windows it uses .venv automatically). On this machine 13 Python files are already red on a clean main (see memory); only care about your own tests.
- Small commits, one commit per task, and end the commit message with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Working branch: `feat/cong-su-workspace` (already exists, contains the spec).

---

### Task 1: Run history store `server/workflow_runs.py`

**Files:**
- Create: `server/workflow_runs.py`
- Test: `tests/python/test_workflow_runs.py`

**Interfaces:**
- Produces:
  - `workflow_runs.get_store() -> WorkflowRunStore` (singleton, DB at `config.STATE_DIR / "workflow_runs.sqlite3"`)
  - `WorkflowRunStore.bat_dau(*, brain, slug, name, input, source, session_id="") -> str` (run_id)
  - `WorkflowRunStore.ghi_buoc(run_id, i, **fields)` with fields among `agent, task, output, verified, error`
  - `WorkflowRunStore.ket_thuc(run_id, status, *, output="", error="", task_id="")`
  - `WorkflowRunStore.lay(run_id) -> dict | None`
  - `WorkflowRunStore.gan_nhat(brain, *, slug=None, session_id=None, status=None, limit=20) -> list[dict]`
  - `WorkflowRunStore.dem_theo_phien(session_id) -> int`
  - `WorkflowRunStore.tim_theo_task(task_id) -> dict | None`
  - `WorkflowRunStore.moc_moi_nhat_theo_slug(brain) -> dict[str, float]`
  - Constants: `TRANG_THAI = ("running", "done", "error", "waiting")`, `NHAN_TRANG_THAI = {"running": "đang chạy", "done": "xong", "error": "lỗi", "waiting": "chờ duyệt"}` (Vietnamese status labels: running, done, error, awaiting review)

- [ ] **Step 1: Write the failing test**

```python
"""Workflow run history store (server/workflow_runs.py).

    python tests/run.py workflow_runs

Why this store exists: before, pressing Run on the Workflows page streamed the result into a
temporary drawer, and closing it lost everything. Asking Jarvis 007 "how did the latest
workflow run go" had nothing to look up.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-wfruns-")

import workflow_runs  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


st = workflow_runs.get_store()

# 1. Start a run -> has an id, status running
rid = st.bat_dau(brain="/b1", slug="viet-bai", name="Viết bài", input="chủ đề A",
                 source="web", session_id="s1")
r = st.lay(rid)
check("bat_dau tra id va running", bool(rid) and r["status"] == "running")
check("bat_dau giu input/source/session", r["input"] == "chủ đề A" and r["source"] == "web"
      and r["session_id"] == "s1" and r["name"] == "Viết bài")

# 2. Write steps: create new, then update the same index
st.ghi_buoc(rid, 0, agent="Nhà nghiên cứu", task="tìm hiểu")
st.ghi_buoc(rid, 0, output="kết quả bước 0", verified=True)
st.ghi_buoc(rid, 1, agent="Người viết", task="viết", error="hết hạn")
steps = st.lay(rid)["steps"]
check("ghi_buoc gop cung chi so", len(steps) == 2 and steps[0]["agent"] == "Nhà nghiên cứu"
      and steps[0]["output"] == "kết quả bước 0" and steps[0]["verified"] is True)
check("ghi_buoc giu loi buoc", steps[1]["error"] == "hết hạn")

# 3. Finish: done + output, finished_at is set
st.ket_thuc(rid, "done", output="bài hoàn chỉnh")
r = st.lay(rid)
check("ket_thuc done", r["status"] == "done" and r["output"] == "bài hoàn chỉnh" and r["finished_at"] > 0)

# 4. Truncation: input 4000, task 2000, step output 4000, final output 20000
rid2 = st.bat_dau(brain="/b1", slug="viet-bai", name="Viết bài", input="x" * 9000, source="kanban")
st.ghi_buoc(rid2, 0, task="t" * 5000, output="o" * 9000)
st.ket_thuc(rid2, "error", output="k" * 30000, error="lỗi thật")
r2 = st.lay(rid2)
check("cat input 4000", len(r2["input"]) == 4000)
check("cat task 2000 va output buoc 4000", len(r2["steps"][0]["task"]) == 2000
      and len(r2["steps"][0]["output"]) == 4000)
check("cat output cuoi 20000", len(r2["output"]) == 20000 and r2["error"] == "lỗi thật")

# 5. gan_nhat: newest first, filter by slug/session/status, limit
rid3 = st.bat_dau(brain="/b1", slug="ban-tin", name="Bản tin", input="", source="web", session_id="s2")
ds = st.gan_nhat("/b1")
check("gan_nhat moi nhat truoc", [x["id"] for x in ds] == [rid3, rid2, rid])
check("gan_nhat loc slug", [x["id"] for x in st.gan_nhat("/b1", slug="ban-tin")] == [rid3])
check("gan_nhat loc session+status", [x["id"] for x in st.gan_nhat("/b1", session_id="s1", status="done")] == [rid])
check("gan_nhat limit", len(st.gan_nhat("/b1", limit=2)) == 2)
check("gan_nhat khac brain rong", st.gan_nhat("/khac") == [])
check("gan_nhat khong mang output day du", "output_tom_tat" in ds[1] and "output" not in ds[1]
      and len(ds[1]["output_tom_tat"]) == 200)

# 6. dem_theo_phien, tim_theo_task, moc_moi_nhat_theo_slug
check("dem_theo_phien", st.dem_theo_phien("s1") == 1 and st.dem_theo_phien("s9") == 0)
st.ket_thuc(rid3, "waiting", task_id="task-77")
check("tim_theo_task", (st.tim_theo_task("task-77") or {}).get("id") == rid3
      and st.tim_theo_task("khong-co") is None)
moc = st.moc_moi_nhat_theo_slug("/b1")
check("moc_moi_nhat_theo_slug", set(moc) == {"viet-bai", "ban-tin"} and moc["ban-tin"] >= moc["viet-bai"])

# 7. All Vietnamese status labels are present
check("nhan trang thai", set(workflow_runs.NHAN_TRANG_THAI) == set(workflow_runs.TRANG_THAI))

print("\nFAIL:" if fails else "\nOK - workflow_runs", fails or "")
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run the test, it must be red because the module is missing**

Run: `python tests/run.py workflow_runs`
Expected: FAIL / ModuleNotFoundError: workflow_runs

- [ ] **Step 3: Write `server/workflow_runs.py`**

```python
"""Workflow run history store - SQLite inside JAVIS_STATE_DIR.

Why it exists: up to 0.58.5, pressing Run on the Workflows page only streamed the result into a
temporary drawer, closing it lost everything, and Jarvis 007 had nowhere to look up "how did the
latest workflow run go". This store records EVERY run, whether it was started from the Partners
page, Kanban, a reminder or a loop, because it is wrapped right inside `execute_workflow`
(main.py) rather than at each call site.

Why its own SQLite and not the shared kanban.sqlite3: task_store is a queue with its own state
transition rules; run history is just an append-only log. Separate files keep the two from
dragging each other along.

Note: do NOT use the em dash character anywhere in this file.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import STATE_DIR

TRANG_THAI = ("running", "done", "error", "waiting")
NHAN_TRANG_THAI = {"running": "đang chạy", "done": "xong", "error": "lỗi", "waiting": "chờ duyệt"}

# Character caps. Tool results go straight into the chat context (the API engines cut at 8000),
# so the store keeps enough to read back rather than the original: input 4000, task per step 2000,
# output per step 4000, final output 20000, summary in the list 200.
TRAN_INPUT = 4000
TRAN_TASK = 2000
TRAN_OUT_BUOC = 4000
TRAN_OUT_CUOI = 20000
TRAN_TOM_TAT = 200

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id          TEXT PRIMARY KEY,
    brain       TEXT NOT NULL,
    slug        TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    session_id  TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT 'other',
    input       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'running',
    started_at  REAL NOT NULL,
    finished_at REAL NOT NULL DEFAULT 0,
    steps_json  TEXT NOT NULL DEFAULT '[]',
    output      TEXT NOT NULL DEFAULT '',
    error       TEXT NOT NULL DEFAULT '',
    task_id     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_wfruns_brain_started ON workflow_runs(brain, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_wfruns_session ON workflow_runs(session_id);
CREATE INDEX IF NOT EXISTS ix_wfruns_task ON workflow_runs(task_id);
"""

_COT = ("id", "brain", "slug", "name", "session_id", "source", "input", "status",
        "started_at", "finished_at", "steps_json", "output", "error", "task_id")


def _cat(s: Any, n: int) -> str:
    return str(s or "")[:n]


class WorkflowRunStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._db.executescript(_SCHEMA)

    # ---- write ----
    def bat_dau(self, *, brain: str, slug: str, name: str, input: str, source: str,
                session_id: str = "") -> str:
        rid = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                "INSERT INTO workflow_runs (id, brain, slug, name, session_id, source, input, "
                "status, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, str(brain), str(slug), str(name or slug), str(session_id or ""),
                 str(source or "other"), _cat(input, TRAN_INPUT), "running", time.time()))
            self._db.commit()
        return rid

    def ghi_buoc(self, run_id: str, i: int, **fields: Any) -> None:
        """Merge into step `i` (create it if missing). Only accepts agent, task, output, verified, error."""
        with self._lock:
            row = self._db.execute("SELECT steps_json FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return
            steps = json.loads(row["steps_json"] or "[]")
            while len(steps) <= int(i):
                steps.append({"i": len(steps), "agent": "", "task": "", "output": "", "verified": None, "error": ""})
            b = steps[int(i)]
            if "agent" in fields:
                b["agent"] = str(fields["agent"] or "")
            if "task" in fields:
                b["task"] = _cat(fields["task"], TRAN_TASK)
            if "output" in fields:
                b["output"] = _cat(fields["output"], TRAN_OUT_BUOC)
            if "verified" in fields:
                b["verified"] = fields["verified"]
            if "error" in fields:
                b["error"] = _cat(fields["error"], TRAN_OUT_BUOC)
            self._db.execute("UPDATE workflow_runs SET steps_json=? WHERE id=?",
                             (json.dumps(steps, ensure_ascii=False), run_id))
            self._db.commit()

    def ket_thuc(self, run_id: str, status: str, *, output: str = "", error: str = "",
                 task_id: str = "") -> None:
        if status not in TRANG_THAI:
            status = "error"
        with self._lock:
            self._db.execute(
                "UPDATE workflow_runs SET status=?, finished_at=?, output=CASE WHEN ?<>'' THEN ? ELSE output END, "
                "error=?, task_id=CASE WHEN ?<>'' THEN ? ELSE task_id END WHERE id=?",
                (status, time.time(), _cat(output, TRAN_OUT_CUOI), _cat(output, TRAN_OUT_CUOI),
                 _cat(error, TRAN_OUT_BUOC), str(task_id or ""), str(task_id or ""), run_id))
            self._db.commit()

    # ---- read ----
    @staticmethod
    def _row(r: sqlite3.Row, day_du: bool) -> Dict[str, Any]:
        d = {k: r[k] for k in _COT}
        d["steps"] = json.loads(d.pop("steps_json") or "[]")
        d["nhan"] = NHAN_TRANG_THAI.get(d["status"], d["status"])
        if not day_du:
            d["output_tom_tat"] = _cat(d.pop("output"), TRAN_TOM_TAT)
            d["steps"] = [{"i": s.get("i"), "agent": s.get("agent"), "verified": s.get("verified"),
                           "error": bool(s.get("error"))} for s in d["steps"]]
        return d

    def lay(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._db.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
        return self._row(r, True) if r else None

    def gan_nhat(self, brain: str, *, slug: Optional[str] = None, session_id: Optional[str] = None,
                 status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        where, params = ["brain=?"], [str(brain)]
        if slug:
            where.append("slug=?"); params.append(slug)
        if session_id:
            where.append("session_id=?"); params.append(session_id)
        if status:
            where.append("status=?"); params.append(status)
        params.append(int(limit))
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM workflow_runs WHERE {' AND '.join(where)} ORDER BY started_at DESC LIMIT ?",
                params).fetchall()
        return [self._row(r, False) for r in rows]

    def dem_theo_phien(self, session_id: str) -> int:
        with self._lock:
            r = self._db.execute("SELECT COUNT(*) FROM workflow_runs WHERE session_id=?", (session_id,)).fetchone()
        return int(r[0]) if r else 0

    def tim_theo_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        if not task_id:
            return None
        with self._lock:
            r = self._db.execute("SELECT * FROM workflow_runs WHERE task_id=? ORDER BY started_at DESC LIMIT 1",
                                 (task_id,)).fetchone()
        return self._row(r, True) if r else None

    def moc_moi_nhat_theo_slug(self, brain: str) -> Dict[str, float]:
        with self._lock:
            rows = self._db.execute("SELECT slug, MAX(started_at) AS m FROM workflow_runs WHERE brain=? GROUP BY slug",
                                    (str(brain),)).fetchall()
        return {r["slug"]: float(r["m"] or 0) for r in rows}


_STORE: Optional[WorkflowRunStore] = None
_STORE_LOCK = threading.Lock()


def get_store() -> WorkflowRunStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = WorkflowRunStore(Path(STATE_DIR) / "workflow_runs.sqlite3")
        return _STORE
```

Note: the test checks `moc["ban-tin"] >= moc["viet-bai"]`; two consecutive `bat_dau` calls may get the same `time.time()`, so use `>=`, exactly as the test does.

- [ ] **Step 4: Run the test, it must be green**

Run: `python tests/run.py workflow_runs`
Expected: every line `ok`, ending with `OK - workflow_runs`

- [ ] **Step 5: Commit**

```bash
git add server/workflow_runs.py tests/python/test_workflow_runs.py
git commit -m "Workflow run history store (workflow_runs.py)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Record history right inside `execute_workflow` + history read API

**Files:**
- Modify: `server/main.py` (around `execute_workflow` :7600, `execute_workflow_resume` :7743, `workflows_index` :6544, `agents_index` :5405, route `/workflows/run` :7827)
- Modify: `server/tasks.py:720` (pass `source="kanban"`)
- Test: `tests/python/test_workflow_runs_api.py`

**Interfaces:**
- Consumes: `workflow_runs.get_store()` (Task 1)
- Produces:
  - `execute_workflow(brain, slug, input="", tools=None, session_id="", source="other")`: the `start` event gains a `run_id`
  - `execute_workflow_resume(brain, slug, task_id, node_id, code, tools=None, session_id="", source="other")`
  - `_ghi_lich_su(gen, *, brain, slug, name, input, source, session_id, run_id=None)` async wrapper generator
  - `GET /workflows/runs?slug=&brain=&limit=` -> `{"runs": [...]}`
  - `GET /workflows/runs/{run_id}` -> full record or 404
  - `GET /workflows` each item gains `last_run_at` (float, 0 if never run)
  - `GET /agents` each item gains `last_chat_at` (float, 0 if never chatted)

- [ ] **Step 1: Write the failing test for the wrapper generator and the two routes**

```python
"""Record run history right inside execute_workflow + routes that read the history.

    python tests/run.py workflow_runs_api

Does not run a real engine: wraps a fake generator that emits exactly the event sequence of execute_workflow.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-wfapi-")

import main  # noqa: E402
import workflow_runs  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


async def gia_done():
    yield {"type": "start", "workflow": "Viết bài", "steps": 2}
    yield {"type": "step_start", "i": 0, "agent": "Nhà nghiên cứu", "task": "tìm"}
    yield {"type": "step_text", "i": 0, "content": "..."}
    yield {"type": "step_done", "i": 0, "agent": "Nhà nghiên cứu", "output": "dữ liệu", "verified": None}
    yield {"type": "step_start", "i": 1, "agent": "Người viết", "task": "viết"}
    yield {"type": "step_done", "i": 1, "agent": "Người viết", "output": "bài xong", "verified": True}
    yield {"type": "done", "result": "bài xong"}


async def gia_error():
    yield {"type": "start", "workflow": "Viết bài", "steps": 1}
    yield {"type": "step_start", "i": 0, "agent": "A", "task": "t"}
    yield {"type": "step_error", "i": 0, "content": "engine chết"}
    yield {"type": "error", "content": "dừng vì lỗi"}


async def gia_wait():
    yield {"type": "start", "workflow": "Đăng bài", "steps": 2}
    yield {"type": "wait_user", "node": "dang", "prompt": "duyệt đăng?", "task_id": "tk1", "code": "AB12"}


async def gom(gen):
    return [e async for e in gen]


st = workflow_runs.get_store()

evs = asyncio.run(gom(main._ghi_lich_su(gia_done(), brain="/b", slug="viet-bai", name="Viết bài",
                                        input="chủ đề", source="web", session_id="s1")))
check("start co run_id, cac su kien giu nguyen", evs[0]["type"] == "start" and evs[0].get("run_id")
      and [e["type"] for e in evs[1:]] == ["step_start", "step_text", "step_done", "step_start", "step_done", "done"])
r = st.lay(evs[0]["run_id"])
check("ban ghi done du buoc", r["status"] == "done" and r["output"] == "bài xong"
      and [s["agent"] for s in r["steps"]] == ["Nhà nghiên cứu", "Người viết"] and r["steps"][1]["verified"] is True)

evs = asyncio.run(gom(main._ghi_lich_su(gia_error(), brain="/b", slug="viet-bai", name="Viết bài",
                                        input="", source="kanban", session_id="")))
r = st.lay(evs[0]["run_id"])
check("ban ghi error", r["status"] == "error" and r["error"] == "dừng vì lỗi" and r["steps"][0]["error"] == "engine chết"
      and r["source"] == "kanban")

evs = asyncio.run(gom(main._ghi_lich_su(gia_wait(), brain="/b", slug="dang-bai", name="Đăng bài",
                                        input="", source="web", session_id="s2")))
r = st.lay(evs[0]["run_id"])
check("ban ghi waiting + task_id", r["status"] == "waiting" and r["task_id"] == "tk1")

# Resume: passing the old run_id updates that exact record instead of creating a new one
truoc = len(st.gan_nhat("/b"))
evs = asyncio.run(gom(main._ghi_lich_su(gia_done(), brain="/b", slug="dang-bai", name="Đăng bài",
                                        input="", source="web", session_id="s2", run_id=r["id"])))
check("resume cap nhat ban ghi cu", len(st.gan_nhat("/b")) == truoc and st.lay(r["id"])["status"] == "done")


# Stopped midway (client closed): the record is not left stuck at running
async def dung_som():
    gen = main._ghi_lich_su(gia_done(), brain="/b", slug="viet-bai", name="Viết bài",
                            input="", source="web", session_id="s3")
    first = await gen.__anext__()
    await gen.aclose()
    return first["run_id"]

rid = asyncio.run(dung_som())
check("dong som -> error 'dung giua chung'", st.lay(rid)["status"] == "error")

# Read routes
c = TestClient(main.app)
ds = c.get("/workflows/runs", params={"brain": "/b", "limit": 5}).json()["runs"]
check("GET /workflows/runs tra danh sach gon", len(ds) == 5 and "output_tom_tat" in ds[0] and "output" not in ds[0])
ds2 = c.get("/workflows/runs", params={"brain": "/b", "slug": "dang-bai"}).json()["runs"]
check("GET /workflows/runs loc slug", all(x["slug"] == "dang-bai" for x in ds2) and ds2)
one = c.get(f"/workflows/runs/{ds[0]['id']}").json()
check("GET /workflows/runs/{id} day du", one["id"] == ds[0]["id"] and "output" in one and "steps" in one)
check("GET /workflows/runs/{id} 404", c.get("/workflows/runs/khong-co").status_code == 404)

print("\nFAIL:" if fails else "\nOK - workflow_runs_api", fails or "")
sys.exit(1 if fails else 0)
```

Note on the route: `brain` here is an arbitrary string; the route must key it with `_brain_key(brain)`. With the fake brain "/b", whatever `_brain_root("/b")` returns is exactly the string the store uses; the test only needs the route and the wrapper generator to use the SAME key function. So in the test, the brain passed to `_ghi_lich_su` must go through the same keying: fix the test to match by setting `B = main._brain_key("/b")` and passing `brain=B` into `_ghi_lich_su`, while the route gets `brain="/b"` (the route keys it itself). Do this as soon as you write the test.

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py workflow_runs_api`
Expected: AttributeError: module 'main' has no attribute '_ghi_lich_su'

- [ ] **Step 3: Add the wrapper generator and rename the old function in main.py**

Rename the current `execute_workflow` function (line ~7600) to `_execute_workflow_raw` (keep the body as is, docstring included). Right below it add:

```python
async def _ghi_lich_su(gen, *, brain, slug, name, input, source, session_id, run_id=None):
    """Wrap the event stream of one workflow run so the history store (workflow_runs) gets written.

    It swallows no event and changes none; it only attaches `run_id` to the `start` event. It lives here
    (not at each call site) so the Partners page, Kanban, reminders and loops are all recorded
    without anyone having to remember. `run_id` is passed in when RESUMING a run that was waiting for
    approval: it updates the old record instead of spawning a new one.

    If the stream is closed midway (the user stops it, the client drops), `finally` marks the record
    as an error "stopped midway" so it is never stuck at "running" forever.
    """
    import workflow_runs
    st = workflow_runs.get_store()
    rid = run_id or st.bat_dau(brain=brain, slug=slug, name=name, input=input or "",
                               source=source or "other", session_id=session_id or "")
    ket = None
    try:
        async for ev in gen:
            t = ev.get("type")
            if t == "start":
                ev = dict(ev, run_id=rid)
            elif t == "step_start":
                st.ghi_buoc(rid, int(ev.get("i", 0)), agent=ev.get("agent", ""), task=ev.get("task", ""))
            elif t == "step_done":
                st.ghi_buoc(rid, int(ev.get("i", 0)), output=ev.get("output", ""), verified=ev.get("verified"))
            elif t == "step_error":
                st.ghi_buoc(rid, int(ev.get("i", 0)), error=ev.get("content", ""))
            elif t == "wait_user":
                ket = "waiting"
                st.ket_thuc(rid, "waiting", task_id=str(ev.get("task_id") or ""))
            elif t == "error":
                ket = "error"
                st.ket_thuc(rid, "error", error=str(ev.get("content") or ""))
            elif t == "done":
                ket = "done"
                st.ket_thuc(rid, "done", output=str(ev.get("result") or ""))
            yield ev
    finally:
        if ket is None:
            try:
                st.ket_thuc(rid, "error", error="dừng giữa chừng")
            except Exception:
                pass


async def execute_workflow(brain, slug, input="", tools=None, session_id="", source="other"):
    """Run a workflow and RECORD HISTORY. Every call site (Partners page, Kanban, reminders) goes through here.
    `source`: web | kanban | reminder | loop | other, only used for filtering when reading back."""
    wf_file = _workflows_dir(brain) / f"{slug}.md"
    if not wf_file.exists():
        yield {"type": "error", "content": "workflow not found"}
        return
    meta, _ = _read_md(wf_file)
    async for ev in _ghi_lich_su(
            _execute_workflow_raw(brain, slug, input, tools, session_id),
            brain=_brain_key(brain), slug=slug, name=meta.get("name", slug), input=input,
            source=source, session_id=session_id):
        yield ev
```

Do the same with `execute_workflow_resume` (line ~7743): rename the old body to `_execute_workflow_resume_raw(brain, slug, task_id, node_id, code, tools=None, session_id="")` and add:

```python
async def execute_workflow_resume(brain, slug, task_id, node_id, code, tools=None,
                                  session_id="", source="other"):
    """Resume a run that is waiting for approval, writing into the EXACT history record that is `waiting`."""
    import workflow_runs
    cu = workflow_runs.get_store().tim_theo_task(task_id)
    wf_file = _workflows_dir(brain) / f"{slug}.md"
    meta, _ = _read_md(wf_file) if wf_file.exists() else ({}, "")
    async for ev in _ghi_lich_su(
            _execute_workflow_resume_raw(brain, slug, task_id, node_id, code, tools, session_id),
            brain=_brain_key(brain), slug=slug, name=meta.get("name", slug), input=(cu or {}).get("input", ""),
            source=source, session_id=session_id or (cu or {}).get("session_id", ""),
            run_id=(cu or {}).get("id")):
        yield ev
```

Use grep to check that no call site is left that calls `execute_workflow(` with positional arguments beyond `tools` (tasks.py:720 passes 4 positionals, which is valid). `deps=execute_workflow` at main.py:8290 stays as is (it now points at the wrapper function).

- [ ] **Step 4: Add the two read routes and the sort fields**

Right above `@app.get("/workflows/run")` (line ~7827) add (declaring `/workflows/runs/{run_id}` AFTER `/workflows/runs` is fine because the paths differ, but both must be declared BEFORE any dynamic `/workflows/{something}` route if one is added later):

```python
@app.get("/workflows/runs")
async def workflow_runs_list(brain: str = Query("brain"), slug: str = Query(""), limit: int = Query(20)):
    """Workflow run history, newest first, compact form (without the full result)."""
    import workflow_runs
    return {"runs": workflow_runs.get_store().gan_nhat(
        _brain_key(brain), slug=slug or None, limit=max(1, min(int(limit or 20), 100)))}


@app.get("/workflows/runs/{run_id}")
async def workflow_runs_get(run_id: str):
    import workflow_runs
    r = workflow_runs.get_store().lay(run_id)
    if not r:
        return JSONResponse({"error": "not found"}, status_code=404)
    return r
```

In `workflows_index(brain)` (line ~6544): after the loop, attach the latest run timestamp:

```python
    try:
        import workflow_runs
        moc = workflow_runs.get_store().moc_moi_nhat_theo_slug(_brain_key(brain))
    except Exception:
        moc = {}
    for w in out:
        w["last_run_at"] = float(moc.get(w["slug"], 0) or 0)
    return out
```

In `agents_index(brain)` (line ~5405): after the loop:

```python
    try:
        moc = get_store().moc_cap_nhat_theo_kenh(_brain_keys(brain), "agent:")
    except Exception:
        moc = {}
    for a in out:
        a["last_chat_at"] = float(moc.get("agent:" + a["slug"], 0) or 0)
    return out
```

`moc_cap_nhat_theo_kenh` is a new `SessionStore` method (written in Task 3). So that Task 2 can run on its own, Task 2 only adds the snippet above for agents once Task 3 is done; if you do Task 2 first, leave that `try/except` as is (it falls back to `{}`), but REMEMBER to come back in Task 3 so the method really exists.

In `server/tasks.py:720`, call `self.deps.execute_workflow(task["brain_root"], slug, intent, tools, source="kanban")`. Check that `TaskDeps` (grep `execute_workflow` in tasks.py) is a `Callable` with untyped parameters; if it is a dataclass with a fixed signature, add `source` to that signature.

- [ ] **Step 5: Run the test, it must be green; also run the related old tests**

Run: `python tests/run.py workflow_runs_api`, then `python tests/run.py workflow_graph` and `python tests/run.py tasks_autonomous`
Expected: the new test is green; the two old tests keep the same result as on main (do not use `git stash`, see the memory about the shared working tree: if in doubt, run that test on a clean worktree).

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/tasks.py tests/python/test_workflow_runs_api.py
git commit -m "Record history for every workflow run, add /workflows/runs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Partner-channel sessions in the session store

**Files:**
- Modify: `server/sessions.py` (`list_sessions` :562)
- Modify: `server/main.py` (`sessions_list` :12412, add `POST /sessions/new` right below it)
- Test: `tests/python/test_sessions_kenh_cong_su.py`

**Interfaces:**
- Produces:
  - `SessionStore.list_sessions(..., channel: Optional[str] = None)`: a specific `channel` filters to exactly that channel; `None` excludes channels with the prefixes `agent:` and `workflow:`
  - `SessionStore.moc_cap_nhat_theo_kenh(brain, tien_to) -> dict[channel, updated_at]`
  - `GET /sessions?channel=` ; `POST /sessions/new` (Form: `brain`, `channel`) -> `{"id", "channel"}`; 400 if the channel is malformed; 404 if the agent/workflow has no file.
  - Constant in `sessions.py`: `KENH_CONG_SU = ("agent:", "workflow:")`

- [ ] **Step 1: Write the failing test**

```python
"""Chat sessions by partner channel: agent:<slug>, workflow:<slug>.

    python tests/run.py sessions_kenh_cong_su
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="javis-kenh-")
os.environ["JAVIS_STATE_DIR"] = _TMP
os.environ["JAVIS_SESSIONS_DB"] = str(Path(_TMP) / "conv.db")

import sessions  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


st = sessions.SessionStore(Path(_TMP) / "conv.db")
a = st.create_session(brain="/b", engine="cli", channel="web")
b = st.create_session(brain="/b", engine="cli", channel="agent:nguoi-viet")
c = st.create_session(brain="/b", engine="cli", channel="workflow:viet-bai")
d = st.create_session(brain="/b", engine="cli", channel="telegram")
for sid in (a, b, c, d):
    st.append_message(sid, "user", "xin chào")

ids = {s["id"] for s in st.list_sessions(brain="/b")}
check("mac dinh loai kenh cong su, giu web + telegram", ids == {a, d})
check("loc dung kenh agent", [s["id"] for s in st.list_sessions(brain="/b", channel="agent:nguoi-viet")] == [b])
check("loc dung kenh workflow", [s["id"] for s in st.list_sessions(brain="/b", channel="workflow:viet-bai")] == [c])
moc = st.moc_cap_nhat_theo_kenh(["/b"], "agent:")
check("moc_cap_nhat_theo_kenh", set(moc) == {"agent:nguoi-viet"} and moc["agent:nguoi-viet"] > 0)

# Route: POST /sessions/new
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
cl = TestClient(main.app)
r = cl.post("/sessions/new", data={"brain": "brain", "channel": "agent:khong-ton-tai"})
check("POST /sessions/new agent khong co -> 404", r.status_code == 404)
r = cl.post("/sessions/new", data={"brain": "brain", "channel": "gi-do"})
check("POST /sessions/new kenh sai dang -> 400", r.status_code == 400)
# Create a real agent in the test brain, then open a session
ag_dir = main._agents_dir("brain"); ag_dir.mkdir(parents=True, exist_ok=True)
(ag_dir / "nguoi-viet.md").write_text("---\nname: Người viết\nrole: viết\nmodel: gpt-5\nmodel_provider: openai-oauth\n---\nViết hay.\n", encoding="utf-8")
r = cl.post("/sessions/new", data={"brain": "brain", "channel": "agent:nguoi-viet"})
check("POST /sessions/new agent that -> id", r.status_code == 200 and r.json().get("id"))
row = main.get_store().get_session(r.json()["id"])
check("phien ghi dung kenh va ghim model cua agent", row["channel"] == "agent:nguoi-viet"
      and row.get("pinned_model") == "gpt-5" and row.get("pinned_provider") == "openai-oauth")
r = cl.get("/sessions", params={"brain": "brain", "channel": "agent:nguoi-viet"}).json()
check("GET /sessions?channel= tra dung phien", [s["id"] for s in r["sessions"]] == [row["id"]])

print("\nFAIL:" if fails else "\nOK - sessions_kenh_cong_su", fails or "")
sys.exit(1 if fails else 0)
```

Note: `main.get_store()` must point at the same DB as `sessions.get_store()` (env `JAVIS_SESSIONS_DB` set before the import). If `_agents_dir("brain")` points into the machine's real brain, switch the test to create a temporary brain: set `os.environ["JAVIS_BRAINS_DIR"]` or whatever equivalent variable `_brain_root` reads (grep `def _brain_root` to find the env variable), SET BEFORE `import main`. Never write files into the machine's real brain.

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py sessions_kenh_cong_su`
Expected: TypeError: list_sessions() got an unexpected keyword argument 'channel'

- [ ] **Step 3: Edit `sessions.py`**

Add a constant near the top of the file (after the `WEB` constant, if any):

```python
# Channels of "partner" sessions: chat with ONE agent or ONE workflow (Partners page, 0.59).
# The history bar of the Chat page does not list these channels: they belong to the right column of the
# Partners page, and mixing them in here would show the user two records for one job.
KENH_CONG_SU = ("agent:", "workflow:")
```

In `list_sessions`, add the parameter `channel: Optional[str] = None` and in the part that builds `where`:

```python
        if channel:
            where.append("s.channel = ?")
            params.append(channel)
        else:
            for tien_to in KENH_CONG_SU:
                where.append("s.channel NOT LIKE ?")
                params.append(tien_to + "%")
```

Add a new method next to `list_sessions`:

```python
    def moc_cap_nhat_theo_kenh(self, brain: Any, tien_to: str) -> Dict[str, float]:
        """{channel: latest updated_at} for channels that start with `tien_to` (e.g. "agent:").
        The Partners page uses it to put the agent chatted with most recently at the top."""
        cond, bparams = loc_brain(brain)
        sql = "SELECT channel, MAX(updated_at) AS m FROM sessions s WHERE s.channel LIKE ?"
        params: list = [tien_to + "%"]
        if cond:
            sql += " AND " + cond
            params += bparams
        sql += " GROUP BY channel"
        return {r["channel"]: float(r["m"] or 0) for r in self._read(sql, tuple(params))}
```

Check the signature of `self._read(sql, params)` in the file (grep `def _read`) and call it in the form it accepts.

- [ ] **Step 4: Edit the routes in main.py**

`sessions_list`: add `channel: str = Query("")` and pass `channel=channel or None`.

Right below `sessions_list` (BEFORE `@app.get("/sessions/{session_id}")`; since `/sessions/new` is a POST it does not collide, but put it nearby for readability):

```python
_KENH_CONG_SU_RE = re.compile(r"^(agent|workflow):([a-z0-9][a-z0-9-]*)$")


@app.post("/sessions/new")
async def sessions_new(brain: str = Form("brain"), channel: str = Form("web")):
    """Open an EMPTY session with a preset channel. The Partners page calls it before the first message: the
    session store must know which agent/workflow this session chats with so the first turn takes the right path.
    Normal chat sessions still mint their id on the client as before; this route is only for partner channels."""
    ch = (channel or "").strip()
    m = _KENH_CONG_SU_RE.match(ch)
    if not m:
        return JSONResponse({"error": "channel phải là agent:<slug> hoặc workflow:<slug>"}, status_code=400)
    loai, slug = m.group(1), m.group(2)
    thu_muc = _agents_dir(brain) if loai == "agent" else _workflows_dir(brain)
    if not (thu_muc / f"{slug}.md").exists():
        return JSONResponse({"error": f"{loai} '{slug}' không có trong brain này"}, status_code=404)
    store = get_store()
    sid = store.create_session(brain=_brain_key(brain), engine="cli", channel=ch)
    if loai == "agent":
        meta, _ = _read_md(thu_muc / f"{slug}.md")
        mdl, prov = (meta.get("model") or "").strip(), (meta.get("model_provider") or "").strip()
        if mdl and prov:
            try:
                store.set_pinned_model(sid, prov, mdl)
            except Exception:
                pass
    return {"id": sid, "channel": ch}
```

This route requires login like the other `/sessions` routes (do not add it to the auth-exempt list).

- [ ] **Step 5: Finish `agents_index.last_chat_at` (Task 2 Step 4) if not done yet, then run the tests**

Run: `python tests/run.py sessions_kenh_cong_su` and `python tests/run.py telegram_sessions`
Expected: green; the old test is unchanged.

- [ ] **Step 6: Commit**

```bash
git add server/sessions.py server/main.py tests/python/test_sessions_kenh_cong_su.py
git commit -m "Chat sessions by agent:/workflow: channel, POST /sessions/new

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Pure module `server/workflow_chat.py` (input assembly, message building, event consumption)

**Files:**
- Create: `server/workflow_chat.py`
- Test: `tests/python/test_workflow_chat.py`

**Interfaces:**
- Produces:
  - `persona_cua_phien(row) -> tuple[str, str] | None` ("agent"|"workflow", slug)
  - `ghep_dau_vao(user_message, ket_qua_truoc) -> str`
  - `tin_xong(so_lan, so_buoc, giay, ket_qua) -> str`
  - `tin_loi(i, agent, loi) -> str`
  - `tin_cho_duyet(node, prompt) -> str`
  - `async chay(events, emit) -> dict` with keys `trang_thai` ("done"|"error"|"waiting"), `ket_qua`, `so_buoc`, `loi` ({"i","agent","content"} or None), `wait` (the wait_user event dict or None), `run_id`
  - Constant `TRAN_KET_QUA_TRUOC = 8000`

- [ ] **Step 1: Write the failing test**

```python
"""workflow_chat: the pure part of "run a workflow as a chat turn".

    python tests/run.py workflow_chat
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import sys

import workflow_chat as wc  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# persona
check("persona agent", wc.persona_cua_phien({"channel": "agent:nguoi-viet"}) == ("agent", "nguoi-viet"))
check("persona workflow", wc.persona_cua_phien({"channel": "workflow:viet-bai"}) == ("workflow", "viet-bai"))
check("persona web/None/rong", wc.persona_cua_phien({"channel": "web"}) is None and wc.persona_cua_phien(None) is None
      and wc.persona_cua_phien({"channel": "agent:"}) is None)

# assemble input
check("ghep khong co ket qua truoc", wc.ghep_dau_vao("viết về A", "") == "viết về A")
g = wc.ghep_dau_vao("sửa đoạn 2", "x" * 9000)
check("ghep co ket qua truoc, cat 8000", g.startswith("sửa đoạn 2\n\n# Kết quả lần trước\n") and g.endswith("x" * 8000)
      and len(g) == len("sửa đoạn 2\n\n# Kết quả lần trước\n") + 8000)

# messages
check("tin_xong", wc.tin_xong(2, 3, 42, "bài") == "Lần chạy #2 · 3 bước · 42 giây\n\nbài")
check("tin_xong rong", "không có nội dung" in wc.tin_xong(1, 1, 0, ""))
check("tin_loi", wc.tin_loi(1, "Người viết", "engine chết") == "Quy trình dừng ở bước 2 (Người viết): engine chết")
check("tin_loi khong ro buoc", wc.tin_loi(None, "", "hỏng") == "Quy trình dừng vì lỗi: hỏng")
check("tin_cho_duyet", wc.tin_cho_duyet("dang", "đăng bài?") ==
      "Quy trình đang chờ duyệt bước \"dang\": đăng bài?. Bấm Duyệt ở cột phải để chạy tiếp.")
check("tin_cho_duyet khong prompt", wc.tin_cho_duyet("dang", "") ==
      "Quy trình đang chờ duyệt bước \"dang\". Bấm Duyệt ở cột phải để chạy tiếp.")


# chay(): consumes events, emits the right frames
async def gia(evs):
    for e in evs:
        yield e


def run(evs):
    frames = []

    async def emit(f):
        frames.append(f)
    kq = asyncio.run(wc.chay(gia(evs), emit))
    return kq, frames


kq, fr = run([
    {"type": "start", "workflow": "W", "steps": 2, "run_id": "r1"},
    {"type": "step_start", "i": 0, "agent": "A", "task": "t"},
    {"type": "step_text", "i": 0, "content": "abc"},
    {"type": "step_done", "i": 0, "agent": "A", "output": "o0"},
    {"type": "step_start", "i": 1, "agent": "B", "task": "t2"},
    {"type": "step_done", "i": 1, "agent": "B", "output": "o1"},
    {"type": "done", "result": "o1"},
])
check("chay done", kq["trang_thai"] == "done" and kq["ket_qua"] == "o1" and kq["so_buoc"] == 2 and kq["run_id"] == "r1")
loai = [f["type"] for f in fr]
check("chay emit wf_event cho moi su kien tru step_text", loai.count("wf_event") == 6
      and not any(f.get("type") == "wf_event" and f.get("event", {}).get("type") == "step_text" for f in fr))
st = [f for f in fr if f["type"] == "status"]
check("chay emit status moi buoc", [f["content"] for f in st] == ["Bước 1/2: A đang làm...", "Bước 2/2: B đang làm..."])

kq, fr = run([
    {"type": "start", "workflow": "W", "steps": 1},
    {"type": "step_start", "i": 0, "agent": "A", "task": "t"},
    {"type": "step_error", "i": 0, "content": "engine chết"},
    {"type": "error", "content": "dừng"},
])
check("chay error giu buoc + agent", kq["trang_thai"] == "error" and kq["loi"] == {"i": 0, "agent": "A", "content": "dừng"})

kq, fr = run([
    {"type": "start", "workflow": "W", "steps": 2},
    {"type": "wait_user", "node": "dang", "prompt": "?", "task_id": "tk", "code": "AB"},
])
check("chay waiting", kq["trang_thai"] == "waiting" and kq["wait"]["task_id"] == "tk" and kq["wait"]["code"] == "AB")

kq, fr = run([{"type": "start", "workflow": "W", "steps": 1}])
check("chay luong dut -> error", kq["trang_thai"] == "error" and "không kết thúc" in kq["loi"]["content"])


# chay() closes the generator when cancelled
class Dem:
    dong = False


async def gia_cham():
    try:
        yield {"type": "start", "workflow": "W", "steps": 1}
        await asyncio.sleep(10)
        yield {"type": "done", "result": ""}
    finally:
        Dem.dong = True


async def huy():
    async def emit(f):
        pass
    t = asyncio.ensure_future(wc.chay(gia_cham(), emit))
    await asyncio.sleep(0.05)
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        return True
    return False

check("chay bi huy thi dong generator", asyncio.run(huy()) and Dem.dong)

print("\nFAIL:" if fails else "\nOK - workflow_chat", fails or "")
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py workflow_chat`
Expected: ModuleNotFoundError: workflow_chat

- [ ] **Step 3: Write `server/workflow_chat.py`**

```python
"""Chat with partners: the PURE part (no I/O) of the Partners page.

Two jobs:
1. `persona_cua_phien`: reads the `channel` column of a session into ("agent"|"workflow", slug). main.py
   uses it in the turn dispatcher to branch: an agent session swaps the system prompt, a workflow
   session runs `execute_workflow` instead of asking the main brain.
2. A workflow run as a chat turn: `chay()` consumes the event stream of execute_workflow,
   pushes WebSocket frames to the chat frame (status) and the right column (wf_event), then returns the result
   so main.py can build the reply with `tin_xong` / `tin_loi` / `tin_cho_duyet`. Split out of
   main.py so it can be tested with a fake generator, no engine needed.

Key rule: a run NEVER ends without a message in the chat. A broken stream
(the engine died before it could emit `error`) still becomes `trang_thai="error"` with a clear error sentence.

Note: do NOT use the em dash character.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

TRAN_KET_QUA_TRUOC = 8000
_LOAI = ("agent", "workflow")


def persona_cua_phien(row: Optional[dict]) -> Optional[Tuple[str, str]]:
    ch = str((row or {}).get("channel") or "")
    for loai in _LOAI:
        tien_to = loai + ":"
        if ch.startswith(tien_to) and len(ch) > len(tien_to):
            return loai, ch[len(tien_to):]
    return None


def ghep_dau_vao(user_message: str, ket_qua_truoc: str) -> str:
    """Later messages in the same conversation can still understand "edit paragraph 2": append the previous result."""
    u = str(user_message or "")
    k = str(ket_qua_truoc or "")
    if not k:
        return u
    return f"{u}\n\n# Kết quả lần trước\n{k[:TRAN_KET_QUA_TRUOC]}"


def tin_xong(so_lan: int, so_buoc: int, giay: int, ket_qua: str) -> str:
    than = str(ket_qua or "").strip() or "(quy trình xong nhưng không có nội dung)"
    return f"Lần chạy #{int(so_lan)} · {int(so_buoc)} bước · {int(giay)} giây\n\n{than}"


def tin_loi(i: Optional[int], agent: str, loi: str) -> str:
    loi = str(loi or "").strip() or "không rõ lý do"
    if i is None:
        return f"Quy trình dừng vì lỗi: {loi}"
    ten = f" ({agent})" if agent else ""
    return f"Quy trình dừng ở bước {int(i) + 1}{ten}: {loi}"


def tin_cho_duyet(node: str, prompt: str) -> str:
    p = str(prompt or "").strip()
    dau = f"Quy trình đang chờ duyệt bước \"{node}\""
    return (dau + (f": {p}" if p else "") + ". Bấm Duyệt ở cột phải để chạy tiếp.")


async def chay(events, emit: Callable[[dict], Awaitable[None]]) -> Dict[str, Any]:
    """Consume the event stream of one run. `emit(frame)` sends a frame back to the browser.

    Frames emitted:
    - `status` whenever a step starts (the "working" chip of the chat frame);
    - `wf_event` for EVERY event except `step_text` (the right column draws progress; step_text is too
      dense and the right column does not show per-step text).
    It does not emit `stream`: main.py sends the whole reply once after the result is in, so the live
    bubble and the saved copy are identical.
    """
    kq: Dict[str, Any] = {"trang_thai": "error", "ket_qua": "", "so_buoc": 0, "loi": None,
                          "wait": None, "run_id": ""}
    agent_cua_buoc: Dict[int, str] = {}
    buoc_dang_chay: Optional[int] = None
    da_ket = False
    try:
        async for ev in events:
            t = ev.get("type")
            if t == "start":
                kq["so_buoc"] = int(ev.get("steps") or 0)
                kq["run_id"] = str(ev.get("run_id") or "")
            elif t == "step_start":
                i = int(ev.get("i") or 0)
                buoc_dang_chay = i
                agent_cua_buoc[i] = str(ev.get("agent") or "")
                tong = kq["so_buoc"] or (i + 1)
                await emit({"type": "status", "content": f"Bước {i + 1}/{tong}: {agent_cua_buoc[i]} đang làm..."})
            elif t == "done":
                kq["trang_thai"] = "done"
                kq["ket_qua"] = str(ev.get("result") or "")
                da_ket = True
            elif t == "error":
                kq["trang_thai"] = "error"
                kq["loi"] = {"i": buoc_dang_chay, "agent": agent_cua_buoc.get(buoc_dang_chay or -1, ""),
                             "content": str(ev.get("content") or "")}
                da_ket = True
            elif t == "wait_user":
                kq["trang_thai"] = "waiting"
                kq["wait"] = dict(ev)
                da_ket = True
            if t != "step_text":
                await emit({"type": "wf_event", "event": dict(ev)})
    finally:
        aclose = getattr(events, "aclose", None)
        if aclose:
            try:
                await aclose()
            except Exception:
                pass
    if not da_ket:
        kq["trang_thai"] = "error"
        kq["loi"] = {"i": buoc_dang_chay, "agent": agent_cua_buoc.get(buoc_dang_chay or -1, ""),
                     "content": "luồng chạy không kết thúc (engine dừng mà không báo)"}
    return kq
```

- [ ] **Step 4: Run the test, it must be green**

Run: `python tests/run.py workflow_chat`
Expected: OK - workflow_chat

- [ ] **Step 5: Commit**

```bash
git add server/workflow_chat.py tests/python/test_workflow_chat.py
git commit -m "workflow_chat: the pure part of chatting with workflows

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Agent sessions swap the system prompt in `_do_turn`

**Files:**
- Modify: `server/main.py`: add `_agent_chat_prompt` near `_workflow_agent_helpers` (:7348); edit `_do_turn` (:10870 onward: `_row0`, `_legacy_system_prompt` :10948, `_subscription_system_prompt` :10960, the `_phase8_plan.action == "use"` spot :11536, the turn-saving spot :11819)
- Test: `tests/python/test_agent_chat_prompt.py`

**Interfaces:**
- Consumes: `workflow_chat.persona_cua_phien` (Task 4), `_workflow_agent_helpers` (existing), `_log_agent_run`, `_ghi_bai_hoc`/`_boc_bai_hoc` (existing)
- Produces: `_agent_chat_prompt(brain, slug) -> str` (raises `FileNotFoundError` if the agent has no file); `_ket_luot_agent(brain, slug, user_message, final_text) -> str` (strips JAVIS_LESSON, writes memory + log, returns clean text)

- [ ] **Step 1: Write the failing test**

```python
"""Chat with one agent on the Partners page: the system prompt is the agent's prompt, not Jarvis 007's.

    python tests/run.py agent_chat_prompt

Does not run an engine. Checks two pure functions in main.py and guards (by reading the code) that the turn
dispatcher branches on persona at every place that picks a prompt.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-agchat-")

import main  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# Temporary brain (see the Task 3 note about the env variable that picks the brains folder; set BEFORE import main if needed)
ag_dir = main._agents_dir("brain"); ag_dir.mkdir(parents=True, exist_ok=True)
(ag_dir / "nguoi-viet.md").write_text("---\nname: Người viết\nrole: viết bài\nskills: [viet-email]\n---\nViết súc tích.\n",
                                       encoding="utf-8")

p = main._agent_chat_prompt("brain", "nguoi-viet")
check("prompt la cua tro ly", "Bạn là agent **Người viết**" in p and "Viết súc tích." in p and "JAVIS_LESSON" in p)
check("prompt noi ro dang chat truc tiep", "trò chuyện trực tiếp" in p)
check("prompt KHONG keo CLAUDE.md cua Jarvis 007", "SWAPPABLE BRAIN" not in p and "# === LỚP AGENTIC" not in p)
try:
    main._agent_chat_prompt("brain", "khong-co")
    check("tro ly khong co -> FileNotFoundError", False)
except FileNotFoundError:
    check("tro ly khong co -> FileNotFoundError", True)

sach = main._ket_luot_agent("brain", "nguoi-viet", "viết giúp", "Bài đây.\nJAVIS_LESSON: chủ thích câu ngắn")
check("ket luot boc JAVIS_LESSON", sach.strip() == "Bài đây.")
mem = (main._brain_memory_dir("brain") / "agents" / "nguoi-viet" / "MEMORY.md")
check("bai hoc vao bo nho agent", mem.exists() and "chủ thích câu ngắn" in mem.read_text(encoding="utf-8"))
runs = list((main._brain_memory_dir("brain") / "agents" / "nguoi-viet" / "runs").glob("*.md"))
check("nhat ky run cua agent co dong", runs and "viết giúp" in runs[0].read_text(encoding="utf-8"))

# Code guard: _do_turn branches on persona at the places that pick a prompt
src = (SERVER / "main.py").read_text(encoding="utf-8")
than = src[src.index("async def _do_turn("):src.index("async def run_turn(")]
check("_do_turn doc persona tu phien", "_persona = workflow_chat.persona_cua_phien(_row0)" in than)
check("_legacy_system_prompt dung prompt tro ly", "_agent_chat_prompt(brain, _persona[1])" in than)
check("_subscription_system_prompt bo qua nen ngu canh khi co persona",
      re.search(r"def _subscription_system_prompt\(.*?\):\s*\"\"\".*?\"\"\"\s*if _persona:\s*return _legacy_system_prompt\(\), None", than, re.S) is not None)
check("nhanh phase8 API khong dung plan khi co persona", 'action == "use" and not _persona' in than)
check("cuoi luot goi _ket_luot_agent", "_ket_luot_agent(brain, _persona[1], user_message, final_text)" in than)

print("\nFAIL:" if fails else "\nOK - agent_chat_prompt", fails or "")
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py agent_chat_prompt`
Expected: AttributeError: _agent_chat_prompt

- [ ] **Step 3: Add two functions to main.py right below `_workflow_agent_helpers`**

```python
def _agent_chat_prompt(brain, slug) -> str:
    """System prompt when the OWNER chats directly with one agent on the Partners page.

    It is EXACTLY the prompt the workflow uses for that agent (role, file body, skills, private memory,
    JAVIS_LESSON rule), plus one sentence saying clearly that this is a conversation, not a workflow step.
    It deliberately does NOT append CLAUDE.md, the owner's memory or the channel block: the user wants to talk to
    "Người viết" (the Writer), not to Jarvis 007 wearing a Writer hat.
    """
    if not (_agents_dir(brain) / f"{slug}.md").exists():
        raise FileNotFoundError(slug)
    _mk, _agent_sysprompt, _log, _learn = _workflow_agent_helpers(brain, None)
    _name, sysprompt, _model, _prov = _agent_sysprompt(slug)
    return (sysprompt + "\n\n# Kênh: bạn đang trò chuyện trực tiếp với chủ trên dashboard Jarvis 007 "
            "(trang Cộng sự). Trả lời như đang nói chuyện, theo ngôn ngữ chủ đang dùng; "
            "không cần báo cáo dạng nhiệm vụ trừ khi được giao việc cụ thể.")


def _ket_luot_agent(brain, slug, user_message, final_text) -> str:
    """End of a chat turn with an agent: move JAVIS_LESSON into the agent's memory, write the agent's run
    log (memory/agents/<slug>/runs), return the CLEAN text to store in the session and show in chat."""
    _mk, _agent_sysprompt, _log, _learn = _workflow_agent_helpers(brain, None)
    sach = _learn(slug, final_text or "")
    _log(slug, user_message or "", sach or "")
    return sach
```

- [ ] **Step 4: Branch inside `_do_turn`**

(a) Right after the line `_row0 = store.get_session(conv_sid) or {}` add:

```python
            # Partner session (Partners page, 0.59): channel agent:<slug> swaps the system prompt for that
            # agent's prompt. Read ONCE here; every prompt-picking spot below asks `_persona`.
            _persona = workflow_chat.persona_cua_phien(_row0)
            if _persona and _persona[0] == "agent" and not (_agents_dir(brain) / f"{_persona[1]}.md").exists():
                await ws.send_text(json.dumps({"type": "error",
                    "content": f"Trợ lý '{_persona[1]}' không còn trong brain này. Mở trang Cộng sự để chọn trợ lý khác."}))
                return ""
```

Add `import workflow_chat` in the import block at the top of main.py (next to `import chatbot_runtime`).

(b) `_legacy_system_prompt`:

```python
            def _legacy_system_prompt():
                nonlocal sysprompt
                if sysprompt is None:
                    if _persona and _persona[0] == "agent":
                        sysprompt = _agent_chat_prompt(brain, _persona[1])
                    else:
                        sysprompt = build_system_prompt(
                            brain, lang=_lang_qd, project_id=_row0.get("project_id") or "",
                            session_id=conv_sid or ""
                        ) + channel_context.build_channel_block(
                            "dashboard", {"session_id": conv_sid}, telegram_running=bool(_TG_BOT),
                            port=_javis_port(), brain_root=_brain_root(brain),
                        )
                return sysprompt
```

(c) `_subscription_system_prompt`: the first line AFTER the docstring:

```python
                if _persona:
                    return _legacy_system_prompt(), None
```

(d) At line ~11536 (`... if _phase8_plan.action == "use" else _legacy_system_prompt()`), change the condition to `if _phase8_plan.action == "use" and not _persona else _legacy_system_prompt()`. Read 30 lines around it: if `_phase8_plan` is built with an expensive `prepare(...)`, wrap the whole build in `if not _persona`.

(e) Fast Path: grep `used_fast_path = True` in `_do_turn`; add `and not _persona` to the condition for entering the fast path (the fast path drops memory and history, and uses its own prompt, which does not suit an agent).

(f) The turn-saving spot (line ~11819 `if final_text:`), right BEFORE `await _persist_turn(...)`:

```python
                if _persona and _persona[0] == "agent":
                    final_text = _ket_luot_agent(brain, _persona[1], user_message, final_text)
```

(g) Check that `channel_context.strip_control_blocks` does not strip anything extra; leave it as is.

- [ ] **Step 5: Run the tests**

Run: `python tests/run.py agent_chat_prompt`, then `python tests/run.py agent_tu_boi_dap` and `python tests/run.py chat_runtime`
Expected: green; the two old tests unchanged.

- [ ] **Step 6: Commit**

```bash
git add server/main.py tests/python/test_agent_chat_prompt.py
git commit -m "Session agent:<slug> chats using the agent's own prompt

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Workflow turn over WebSocket (`run_workflow_turn`) + resume on approval (`wf_resume`)

**Files:**
- Modify: `server/main.py`: in `websocket_endpoint` (:10815): add `run_workflow_turn` next to `run_turn` (:11850); the message-receiving loop (:12150 onward): add the action `wf_resume`, branch when the persona is a workflow before creating `run_turn`
- Test: `tests/python/test_workflow_turn_ws.py`

**Interfaces:**
- Consumes: `workflow_chat.chay/ghep_dau_vao/tin_*` (Task 4), `execute_workflow(..., source="web")`, `execute_workflow_resume(..., source="web")` (Task 2), `workflow_runs.get_store()` (Task 1), `_persist_turn`, `_SendProxy`, `_CHAT_RUNTIME`
- Produces: WS frames `{"type":"wf_event","event":{...},"session_id"}`, `{"type":"status"}`, `{"type":"stream"}`, `{"type":"turn_done"}`; client action `{"action":"wf_resume","session_id","task_id","node","code"}`

- [ ] **Step 1: Write the failing test (checked by reading code + running the core function via monkeypatch)**

`run_workflow_turn` is a closure inside `websocket_endpoint` so it cannot be called directly. Split the CORE into a module-level function `_luot_quy_trinh(store, conv_sid, user_message, brain, slug, emit, resume=None) -> str` (returns the saved text), and the closure only wraps tracing, job registration and `turn_done`. The test calls `_luot_quy_trinh` with a fake `execute_workflow`.

```python
"""Workflow turn over WebSocket: every message in a workflow:<slug> session is one run.

    python tests/run.py workflow_turn_ws
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="javis-wfturn-")
os.environ["JAVIS_STATE_DIR"] = _TMP
os.environ["JAVIS_SESSIONS_DB"] = str(Path(_TMP) / "conv.db")

import main  # noqa: E402
import workflow_runs  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


store = main.get_store()
sid = store.create_session(brain=main._brain_key("brain"), engine="cli", channel="workflow:viet-bai")
goi = []


async def gia_execute(brain, slug, input="", tools=None, session_id="", source="other"):
    goi.append({"input": input, "source": source, "session_id": session_id})
    rid = workflow_runs.get_store().bat_dau(brain=main._brain_key(brain), slug=slug, name="Viết bài",
                                           input=input, source=source, session_id=session_id)
    yield {"type": "start", "workflow": "Viết bài", "steps": 1, "run_id": rid}
    yield {"type": "step_start", "i": 0, "agent": "Người viết", "task": "viết"}
    yield {"type": "step_done", "i": 0, "agent": "Người viết", "output": "BÀI 1"}
    workflow_runs.get_store().ket_thuc(rid, "done", output="BÀI 1")
    yield {"type": "done", "result": "BÀI 1"}


main.execute_workflow = gia_execute   # _luot_quy_trinh looks it up through the module at call time


def run(msg, resume=None):
    frames = []

    async def emit(f):
        frames.append(f)
    store.append_message(sid, "user", msg)
    text = asyncio.run(main._luot_quy_trinh(store, sid, msg, "brain", "viet-bai", emit, resume=resume))
    return text, frames


text, fr = run("viết về A")
check("tin tra loi co dong dau + ket qua", text.startswith("Lần chạy #1 · 1 bước · ") and text.endswith("\n\nBÀI 1"))
check("emit status, wf_event, stream (khong turn_done: closure lo)",
      [f["type"] for f in fr].count("status") == 1 and any(f["type"] == "wf_event" for f in fr)
      and fr[-1]["type"] == "stream" and fr[-1]["content"] == text)
msgs = store.get_messages(sid)
check("phien luu tin assistant", msgs[-1]["role"] == "assistant" and msgs[-1]["content"] == text)
check("lan dau khong noi ket qua truoc", goi[0]["input"] == "viết về A" and goi[0]["source"] == "web"
      and goi[0]["session_id"] == sid)

text2, _ = run("sửa ngắn lại")
check("lan hai noi ket qua truoc + dem lan chay", goi[1]["input"].startswith("sửa ngắn lại\n\n# Kết quả lần trước\nBÀI 1")
      and text2.startswith("Lần chạy #2"))


async def gia_loi(brain, slug, input="", tools=None, session_id="", source="other"):
    yield {"type": "start", "workflow": "Viết bài", "steps": 1}
    yield {"type": "step_start", "i": 0, "agent": "Người viết", "task": "viết"}
    yield {"type": "error", "content": "engine chết"}

main.execute_workflow = gia_loi
text3, fr3 = run("lại đi")
check("loi van thanh tin trong chat", text3 == "Quy trình dừng ở bước 1 (Người viết): engine chết"
      and store.get_messages(sid)[-1]["content"] == text3)


async def gia_cho(brain, slug, input="", tools=None, session_id="", source="other"):
    yield {"type": "start", "workflow": "Viết bài", "steps": 2}
    yield {"type": "wait_user", "node": "dang", "prompt": "đăng?", "task_id": "tk9", "code": "ZZ"}

main.execute_workflow = gia_cho
text4, fr4 = run("đăng bài")
check("cho duyet thanh tin + wf_event mang code", "chờ duyệt bước \"dang\"" in text4
      and any(f["type"] == "wf_event" and f["event"].get("code") == "ZZ" for f in fr4))


async def gia_resume(brain, slug, task_id, node_id, code, tools=None, session_id="", source="other"):
    goi.append({"resume": (task_id, node_id, code)})
    yield {"type": "start", "workflow": "Viết bài", "steps": 2}
    yield {"type": "step_start", "i": 1, "agent": "Người đăng", "task": "đăng"}
    yield {"type": "step_done", "i": 1, "agent": "Người đăng", "output": "ĐÃ ĐĂNG"}
    yield {"type": "done", "result": "ĐÃ ĐĂNG"}

main.execute_workflow_resume = gia_resume
text5, _ = run("Đã duyệt bước dang.", resume={"task_id": "tk9", "node": "dang", "code": "ZZ"})
check("resume goi execute_workflow_resume dung tham so", goi[-1].get("resume") == ("tk9", "dang", "ZZ")
      and text5.endswith("ĐÃ ĐĂNG"))

# Code guard for the message-receiving loop
src = (SERVER / "main.py").read_text(encoding="utf-8")
ws = src[src.index("async def websocket_endpoint("):src.index("@app.get(\"/tts/voices\")") if "@app.get(\"/tts/voices\")" in src else len(src)]
check("vong nhan tin re nhanh workflow", "run_workflow_turn(" in ws and 'action == "wf_resume"' in ws)

print("\nFAIL:" if fails else "\nOK - workflow_turn_ws", fails or "")
sys.exit(1 if fails else 0)
```

If `@app.get("/tts/voices")` does not come after `websocket_endpoint`, change the cut marker to a string that is certain to come after it (e.g. `"# Phiên hội thoại - list / view / search"`, a Vietnamese section comment meaning "Conversation sessions - list / view / search").

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py workflow_turn_ws`
Expected: AttributeError: _luot_quy_trinh

- [ ] **Step 3: Add the module-level core to main.py (put it right above `_persist_turn`)**

```python
async def _luot_quy_trinh(store, conv_sid, user_message, brain, slug, emit, resume=None) -> str:
    """CORE of one turn in a workflow:<slug> session: run the workflow, push frames to the browser, save
    the reply. Returns the saved text. It does not register a job and does not send turn_done: the closure in
    websocket_endpoint handles that, so this function can be called from tests with a fake execute_workflow.

    `resume` = {"task_id","node","code"} when the user pressed Approve: continue the run that is waiting.
    Looks up `execute_workflow` through globals() AT CALL TIME so tests can replace it.
    """
    import workflow_runs
    st = workflow_runs.get_store()
    t0 = time.time()
    if resume:
        events = globals()["execute_workflow_resume"](
            brain, slug, resume["task_id"], resume["node"], resume["code"],
            session_id=conv_sid, source="web")
    else:
        truoc = st.gan_nhat(_brain_key(brain), slug=slug, session_id=conv_sid, status="done", limit=1)
        ket_truoc = ""
        if truoc:
            day_du = st.lay(truoc[0]["id"]) or {}
            ket_truoc = day_du.get("output", "")
        dau_vao = workflow_chat.ghep_dau_vao(user_message, ket_truoc)
        events = globals()["execute_workflow"](brain, slug, dau_vao, session_id=conv_sid, source="web")
    kq = await workflow_chat.chay(events, emit)
    giay = int(time.time() - t0)
    if kq["trang_thai"] == "done":
        so_lan = st.dem_theo_phien(conv_sid) or 1
        text = workflow_chat.tin_xong(so_lan, kq["so_buoc"], giay, kq["ket_qua"])
    elif kq["trang_thai"] == "waiting":
        w = kq["wait"] or {}
        text = workflow_chat.tin_cho_duyet(str(w.get("node") or ""), str(w.get("prompt") or ""))
    else:
        loi = kq["loi"] or {}
        text = workflow_chat.tin_loi(loi.get("i"), loi.get("agent", ""), loi.get("content", ""))
    await emit({"type": "stream", "content": text})
    await _persist_turn(store, conv_sid, brain, user_message, text)
    return text
```

Check that `time` is already imported at the top of main.py (grep `^import time`); if not, add it.

- [ ] **Step 4: Closure `run_workflow_turn` in `websocket_endpoint`, right below `run_turn`**

```python
        async def run_workflow_turn(conv_sid, user_message, brain, turn_tag, runtime_trace, slug, resume=None):
            """A turn in a workflow:<slug> session. Same frame as run_turn (trace, Stop, turn_done)
            but the body is _luot_quy_trinh. An unexpected error still becomes a message in chat: the rule of
            the Partners page is that a workflow run never ends in silence."""
            ws = _SendProxy(conv_sid, runtime_trace)
            _trace_token = context_runtime.bind_trace(runtime_trace)

            async def emit(frame):
                await ws.send_text(json.dumps(frame, ensure_ascii=False))
            try:
                await _luot_quy_trinh(store, conv_sid, user_message, brain, slug, emit, resume=resume)
                _CONTEXT_RUNTIME.finish(runtime_trace, "COMPLETED")
            except asyncio.CancelledError:
                _CONTEXT_RUNTIME.finish(runtime_trace, "CANCELLED", "cancelled")
                _cau = "Đã dừng lần chạy này theo yêu cầu."
                try:
                    await _persist_turn(store, conv_sid, brain, user_message, _cau)
                except Exception:
                    pass
                await send_raw({"type": "system", "content": _cau, "session_id": conv_sid,
                                **context_runtime.event_fields(runtime_trace)})
            except Exception as e:
                _CONTEXT_RUNTIME.note_error(runtime_trace, type(e).__name__)
                _CONTEXT_RUNTIME.finish(runtime_trace, "FAILED", type(e).__name__)
                _cau = workflow_chat.tin_loi(None, "", f"{type(e).__name__}: {e}")
                try:
                    await _persist_turn(store, conv_sid, brain, user_message, _cau)
                except Exception:
                    pass
                await send_raw({"type": "error", "content": _cau, "session_id": conv_sid,
                                **context_runtime.event_fields(runtime_trace)})
            finally:
                context_runtime.reset_trace(_trace_token)
                await send_raw({"type": "turn_done", "session_id": conv_sid,
                                **context_runtime.event_fields(runtime_trace)})
```

Read the `finally` part of `run_turn` (line ~11876 onward) and copy exactly any other cleanup it does after `turn_done` (e.g. `_CHAT_RUNTIME` removing the job, updating the background-work strip) into this `finally`, so the two closures do not drift apart.

- [ ] **Step 5: Branch in the message-receiving loop**

(a) Right after `store.append_message(conv_sid, "user", user_message)` and the block that creates `turn_tag`/`runtime_trace`, BEFORE the Voice V2 `_vconf` block, add:

```python
            _pers = workflow_chat.persona_cua_phien(store.get_session(conv_sid) or {})
            if _pers and _pers[0] == "workflow":
                task = asyncio.create_task(run_workflow_turn(
                    conv_sid, user_message, brain, turn_tag, runtime_trace, _pers[1]))
                _CHAT_RUNTIME.register_job(
                    conv_sid, task, turn_tag,
                    runtime_task_id=runtime_trace.task_id if runtime_trace else "",
                    runtime_step_id=runtime_trace.step_id if runtime_trace else "",
                )
                continue
```

(b) Add a new action next to `if action == "stop":`:

```python
            if action == "wf_resume":
                # Approve button in the right column of the Partners page: continue the run that is waiting, result returns to the same session.
                _sid = str(payload.get("session_id") or "")
                _row = store.get_session(_sid) or {}
                _pers = workflow_chat.persona_cua_phien(_row)
                if not (_pers and _pers[0] == "workflow"):
                    await send_raw({"type": "error", "session_id": _sid, "content": "Phiên này không phải phiên quy trình."})
                    continue
                if _CHAT_RUNTIME.get_job(_sid):
                    await send_raw({"type": "error", "session_id": _sid, "content": "Quy trình đang chạy, đợi xong đã."})
                    continue
                _node = str(payload.get("node") or "")
                _msg = f"Đã duyệt bước \"{_node}\"."
                store.append_message(_sid, "user", _msg)
                _brain_r = _row.get("brain") or payload.get("brain") or "brain"
                _tag = f"chat:{_sid[:12]}:{uuid.uuid4().hex[:8]}"
                _trace = _CONTEXT_RUNTIME.start_turn(_sid, _brain_r, "dashboard")
                task = asyncio.create_task(run_workflow_turn(
                    _sid, _msg, _brain_r, _tag, _trace, _pers[1],
                    resume={"task_id": str(payload.get("task_id") or ""), "node": _node,
                            "code": str(payload.get("code") or "")}))
                _CHAT_RUNTIME.register_job(_sid, task, _tag,
                    runtime_task_id=_trace.task_id if _trace else "",
                    runtime_step_id=_trace.step_id if _trace else "")
                continue
```

`_row.get("brain")` is the resolved key (an absolute path); `_brain_root` also accepts absolute paths (see `_brain_key`). If not, use the `payload.get("brain")` that the client sends along.

- [ ] **Step 6: Run the tests**

Run: `python tests/run.py workflow_turn_ws`, then `python tests/run.py chat_runtime` and `python tests/run.py viec_nen`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add server/main.py tests/python/test_workflow_turn_ws.py
git commit -m "Session workflow:<slug>: every message is one run, result returns to chat

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Plugin `javis-workflow` + a "latest run" line in the system prompt

**Files:**
- Create: `system/plugins/javis-workflow/plugin.yaml`, `system/plugins/javis-workflow/plugin.py`
- Modify: `server/main.py` `_javis_capability_summary` (:9024)
- Test: `tests/python/test_javis_workflow_plugin.py`

**Interfaces:**
- Consumes: `workflow_runs.get_store()` (Task 1)
- Produces: tool `javis_workflow` (op `runs` [slug?, limit?], op `show` [id]); function `_dong_lan_chay_gan_nhat(brain) -> str` in main.py

- [ ] **Step 1: Write the failing test**

```python
"""Plugin javis-workflow: Jarvis 007 can look up workflow run history from every engine.

    python tests/run.py javis_workflow_plugin
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-wfplug-")

import workflow_runs  # noqa: E402
import plugins_host  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


spec = importlib.util.spec_from_file_location(
    "javis_workflow_plugin", ROOT / "system" / "plugins" / "javis-workflow" / "plugin.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

VAULT = tempfile.mkdtemp(prefix="javis-vault-")
B = str(Path(VAULT).resolve())
ctx = plugins_host.PluginContext("javis-workflow", "bundled", ROOT / "system/plugins/javis-workflow", VAULT)
m.register(ctx)
tool = ctx._tools[0]
check("dang ky tool javis_workflow readonly", tool["name"] == "javis_workflow" and tool["min_mode"] == "readonly")

st = workflow_runs.get_store()
r1 = st.bat_dau(brain=B, slug="viet-bai", name="Viết bài", input="A", source="web", session_id="s")
st.ghi_buoc(r1, 0, agent="Người viết", task="viết", output="xong A")
st.ket_thuc(r1, "done", output="BÀI A")
r2 = st.bat_dau(brain=B, slug="ban-tin", name="Bản tin", input="", source="kanban")
st.ket_thuc(r2, "error", error="engine chết")

h = tool["handler"]
out = asyncio.run(h({"op": "runs"}, ctx))
check("runs liet ke moi nhat truoc, co ten/trang thai/id", out.index("Bản tin") < out.index("Viết bài")
      and "lỗi" in out and "xong" in out and r1 in out and r2 in out)
out = asyncio.run(h({"op": "runs", "slug": "viet-bai"}, ctx))
check("runs loc slug", "Viết bài" in out and "Bản tin" not in out)
out = asyncio.run(h({"op": "show", "id": r1}, ctx))
check("show co dau vao, buoc, ket qua", "A" in out and "Người viết" in out and "BÀI A" in out)
check("show id la -> loi ro", "ERROR" in asyncio.run(h({"op": "show", "id": "xxx"}, ctx)))
check("op la -> loi ro", "ERROR" in asyncio.run(h({"op": "bay"}, ctx)))
ctx2 = plugins_host.PluginContext("javis-workflow", "bundled", ROOT / "system/plugins/javis-workflow", None)
check("khong co vault_root -> loi ro", "ERROR" in asyncio.run(h({"op": "runs"}, ctx2)))

# The line in the system prompt
import main  # noqa: E402
d = main._dong_lan_chay_gan_nhat(B)
check("dong lan chay gan nhat", d.startswith("Lần chạy quy trình gần nhất: Bản tin") and "lỗi" in d and "javis_workflow" in d)
check("brain chua chay -> rong", main._dong_lan_chay_gan_nhat("/khong-co") == "")
src = (SERVER / "main.py").read_text(encoding="utf-8")
than = src[src.index("def _javis_capability_summary("):src.index("def _skill_router_block(")]
check("capability summary goi dong lan chay", "_dong_lan_chay_gan_nhat(" in than)

print("\nFAIL:" if fails else "\nOK - javis_workflow_plugin", fails or "")
sys.exit(1 if fails else 0)
```

In `_dong_lan_chay_gan_nhat(B)`, the test passes `B` as a resolved absolute path; the function must key it with `_brain_key(brain)`, and `_brain_key` given an absolute path must return that same path (see `_brain_root`). If `_brain_root` rejects paths outside the brains folder, the test uses `main._brain_key("brain")` as `B` and writes the records with that key.

- [ ] **Step 2: Run the test, it must be red**

Run: `python tests/run.py javis_workflow_plugin`
Expected: FileNotFoundError plugin.py

- [ ] **Step 3: Write the plugin**

`system/plugins/javis-workflow/plugin.yaml`:

```yaml
name: Lịch sử quy trình
slug: javis-workflow
version: 1.0.0
description: Xem các lần chạy quy trình gần đây và kết quả từng lần, ngay từ chat. Trước tool này, chạy quy trình xong là kết quả mất, hỏi "quy trình chạy gần nhất ra sao" Jarvis 007 không có gì để tra.
author: Jarvis 007 (bundled)
enabled: true
min_mode: readonly
tools:
  - javis_workflow
hooks: []
```

`system/plugins/javis-workflow/plugin.py`:

```python
"""Bundled plugin: tool `javis_workflow` - read workflow run history, from EVERY engine.

Why it exists: the `workflow_runs` store (server/workflow_runs.py) records every workflow run, but
the main brain has no path to it. When the user asked "how did the workflow that just ran go", Jarvis 007
answered with nothing, exactly the bug the project owner reported on 2026-09-15. This tool only READS (min_mode readonly), so it
works even in suggest mode. To run a workflow, hand it off as Kanban work (javis_task, route
wf:<slug>) or go to the Partners page.

Brain key: the store writes `_brain_key` = the resolved absolute path of the brain, so here we also
resolve `ctx.vault_root` the same way. An empty `vault_root` gives a clear error, never falling back to another brain.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import workflow_runs

_LIST_MAX = 20
_TRAN_OUT = 6000     # final result printed by the tool: the API engines cut at 8000, leave room for the rest


def _khoa(ctx) -> str:
    return str(Path(ctx.vault_root).resolve())


def _gio(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M %d/%m")
    except Exception:
        return "?"


def _liet_ke(args, ctx) -> str:
    if not ctx.vault_root:
        return "ERROR: chưa biết đang làm việc trên brain nào nên không xem được lịch sử."
    slug = str((args or {}).get("slug") or "").strip() or None
    try:
        limit = max(1, min(int((args or {}).get("limit") or 10), _LIST_MAX))
    except Exception:
        limit = 10
    ds = workflow_runs.get_store().gan_nhat(_khoa(ctx), slug=slug, limit=limit)
    if not ds:
        return "Chưa có lần chạy quy trình nào" + (f" của '{slug}'" if slug else "") + "."
    dong = []
    for r in ds:
        dong.append(f"- {_gio(r['started_at'])} · {r['name']} ({r['slug']}) · {r['nhan']} · nguồn {r['source']}"
                    f" · id {r['id']}" + (f"\n  {r['output_tom_tat']}" if r.get("output_tom_tat") else "")
                    + (f"\n  lỗi: {r['error']}" if r.get("error") else ""))
    dong.append("Xem đủ một lần: op=show với id ở trên.")
    return "\n".join(dong)


def _xem(args, ctx) -> str:
    rid = str((args or {}).get("id") or "").strip()
    if not rid:
        return "ERROR: op=show cần id của lần chạy (lấy từ op=runs)."
    r = workflow_runs.get_store().lay(rid)
    if not r:
        return f"ERROR: không có lần chạy id {rid}."
    ra = [f"{r['name']} ({r['slug']}) · {r['nhan']} · bắt đầu {_gio(r['started_at'])}"
          + (f" · xong {_gio(r['finished_at'])}" if r.get("finished_at") else ""),
          f"Đầu vào: {r['input'] or '(trống)'}"]
    for s in r.get("steps") or []:
        kc = "" if s.get("verified") is None else (" · kiểm chứng đạt" if s.get("verified") else " · kiểm chứng CHƯA đạt")
        ra.append(f"Bước {int(s.get('i', 0)) + 1} · {s.get('agent') or '?'}{kc}: {s.get('task') or ''}")
        if s.get("output"):
            ra.append("  -> " + str(s["output"])[:800])
        if s.get("error"):
            ra.append("  lỗi: " + str(s["error"]))
    if r.get("error"):
        ra.append(f"Lỗi: {r['error']}")
    ra.append("Kết quả cuối:\n" + (str(r.get("output") or "")[:_TRAN_OUT] or "(không có)"))
    return "\n".join(ra)


async def _chay(args, ctx) -> str:
    op = str((args or {}).get("op") or "").strip().lower()
    if op == "runs":
        return _liet_ke(args, ctx)
    if op == "show":
        return _xem(args, ctx)
    return "ERROR: op phải là 'runs' (liệt kê lần chạy) hoặc 'show' (xem một lần)."


def register(ctx):
    ctx.register_tool(
        "javis_workflow",
        "Lịch sử chạy quy trình (workflow). op=runs: các lần chạy gần nhất, mới trước, lọc theo "
        "slug nếu có, limit mặc định 10. op=show: một lần chạy đầy đủ (đầu vào, từng bước, kết quả) "
        "theo id. Dùng khi người dùng hỏi quy trình vừa chạy ra sao, kết quả lần trước, hay quy "
        "trình nào đang chờ duyệt. Chỉ đọc; muốn chạy quy trình thì dùng javis_task với route "
        "wf:<slug> hoặc trang Cộng sự.",
        _chay,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["runs", "show"]},
                "slug": {"type": "string", "description": "Lọc theo quy trình (op=runs)"},
                "limit": {"type": "integer", "description": "Số lần tối đa (op=runs)"},
                "id": {"type": "string", "description": "Id lần chạy (op=show)"},
            },
            "required": ["op"],
        },
        min_mode="readonly",
        emoji="🧾",
    )
```

- [ ] **Step 4: The line in the system prompt**

In main.py, right above `_javis_capability_summary`:

```python
def _dong_lan_chay_gan_nhat(brain) -> str:
    """One line for the system prompt: the brain's latest workflow run, empty if there is none.
    Thanks to this line, when someone asks "how did the latest workflow run go" in the main chat frame, Jarvis 007 knows right away
    there is something to look up and which tool to use."""
    try:
        import workflow_runs
        from datetime import datetime
        ds = workflow_runs.get_store().gan_nhat(_brain_key(brain), limit=1)
    except Exception:
        return ""
    if not ds:
        return ""
    r = ds[0]
    try:
        luc = datetime.fromtimestamp(float(r["started_at"])).strftime("%H:%M %d/%m")
    except Exception:
        luc = "?"
    return (f"Lần chạy quy trình gần nhất: {r['name']} lúc {luc} ({r['nhan']}). "
            "Chi tiết hay các lần khác: tool javis_workflow (op=runs, op=show).")
```

In `_javis_capability_summary`, after the `if c["workflows"]:` block:

```python
    _lc = _dong_lan_chay_gan_nhat(brain)
    if _lc:
        parts.append(_lc)
```

- [ ] **Step 5: Run the tests**

Run: `python tests/run.py javis_workflow_plugin`, then `python tests/run.py plugins_host`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add system/plugins/javis-workflow server/main.py tests/python/test_javis_workflow_plugin.py
git commit -m "Tool javis_workflow + latest-run line in the system prompt

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Register the `workspace` page, remove the two old pages, aliases, dictionary

**Files:**
- Modify: `dashboard/console.js` (`VIEW_ICON` :27, `RAIL_ITEMS` :81, `RAIL_GROUPS` :104, `VIEW_META` :150, `STUDIO_PAGES` :163, `TRANG_GOP` :254, `renderPage` :396, `LOAI_KHO` :433)
- Modify: `dashboard/ui-actions.js:17`, `server/ui_targets.py` (`PAGES` :20, `ALIASES` :28)
- Modify: `dashboard/packs.js:191-193`, `dashboard/chatbots.js:699`
- Modify: `dashboard/i18n/vi.json`, `dashboard/i18n/en.json`
- Modify: `tests/python/test_ui_bridge.py:100-102`
- Test: `tests/js/test_ui_actions.js` (existing), `tests/python/test_ui_bridge.py`

**Interfaces:**
- Produces: page id `workspace`; `renderPage` calls `renderWorkspace(el)` (written in Task 9, a temporary placeholder in this task); i18n keys `page.workspace.label|title|sub`

- [ ] **Step 1: Fix the test's alias expectations (red first)**

In `tests/python/test_ui_bridge.py` lines 100-102 change the expectations for `"agents"` and `"workflows"` to `"workspace"`, and add one line (the Vietnamese "cộng sự" is the old page name, meaning "partners"):

```python
    check("resolve_page: 'cộng sự' -> workspace", m.resolve_page("cộng sự") == "workspace")
```

Run: `python tests/run.py ui_bridge` -> FAIL on those three lines.

- [ ] **Step 2: Edit server/ui_targets.py**

`PAGES`: replace `"workflows", "agents"` with `"workspace"` (in the position of "workflows", drop "agents"):

```python
PAGES = (
    "home", "chat", "settings", "workspace", "skills", "chatbots", "files",
    "terminal", "selfimprove", "learn", "kanban", "models", "channels", "mcp", "plugins",
    "packs", "logs", "account", "usage", "pet",
)
```

`ALIASES`: change every value `"workflows"` and `"agents"` to `"workspace"`, and add `"cong su": "workspace", "workspace": "workspace", "tro ly va quy trinh": "workspace"` (the keys are Vietnamese spoken aliases without diacritics: "partners", "workspace", "agents and workflows"). Add a comment: the Agents and Workflows pages merged into Partners in 0.59.0, and the old aliases stay so that habitual spoken commands do not die.

- [ ] **Step 3: Edit dashboard/ui-actions.js**

```js
  var PAGES = ["home", "chat", "settings", "workspace", "skills", "chatbots", "files",
               "terminal", "selfimprove", "learn", "kanban", "models", "channels", "mcp", "plugins",
               "packs", "logs", "account", "usage", "pet"];
```

- [ ] **Step 4: Edit dashboard/console.js**

- `VIEW_ICON`: remove `workflows` and `agents`, add `workspace: "bot"` (the `bot` icon exists in the manifest; `users` does not, and no new icon is added in this task).
- `RAIL_ITEMS`: `"home", "chat", "settings", "workspace", "skills", "chatbots", "files", ...` (remove workflows, agents).
- `RAIL_GROUPS` group `nang_luc`: `ids: ["workspace", "chatbots", "skills", "plugins"]`.
- `VIEW_META`: replace the id list accordingly.
- `STUDIO_PAGES = ["skills"]`.
- `TRANG_GOP = { runtime: "usage", agents: "workspace", workflows: "workspace" }` with a comment: the two pages merged in 0.59.0; anyone who clicks an old button in chat or an old bookmark still arrives at the right place.
- `LOAI_KHO`: remove the two keys `agents`, `workflows` (the Partners page has its own Store button).
- `renderPage`: add the line `if (id === "workspace") return renderWorkspace(el);` RIGHT BEFORE the `STUDIO_PAGES` line.
- Add a temporary function (Task 9 replaces the real body):

```js
  // Partners page: built by workspace.js, borrows the chat frame like the Chat page.
  function renderWorkspace(el) {
    if (!window.JavisWorkspace) { el.innerHTML = placeholder("workspace", window.t("cs.mod_not_ready", { ten: "workspace.js" })); return; }
    _injectChatCss();
    if (_chatSlots.length) _returnChatNodes();
    document.body.classList.add("on-chat");
    window.JavisWorkspace.render(el, { borrow: _borrowChatNodes });
    _pageLeave = _returnChatNodes;
  }
```

- `packs.js:191-193`: `trang: "workspace"` for `agent` and `workflow`.
- `chatbots.js:699`: `window.JavisNav.go("workspace")`.
- Grep all of `dashboard/*.js` and `server/*.py` for `"agents"`/`"workflows"` used as a PAGE ID (not the API path `/agents`): change any that remain.

- [ ] **Step 5: Dictionary**

`vi.json`: remove the 6 keys `page.workflows.*`, `page.agents.*`; add:

```json
  "page.workspace.label": "Cộng sự",
  "page.workspace.title": "Cộng sự (Agents & Workflows)",
  "page.workspace.sub": "Trò chuyện với từng trợ lý, chạy quy trình, xem lại lịch sử",
```

`en.json`: `"Partners"`, `"Partners (Agents & Workflows)"`, `"Chat with each agent, run workflows, review run history"`. Check `tests/js/test_i18n.mjs` (it may guard that both files have the same key set).

- [ ] **Step 6: Run the tests**

Run: `node tests/js/test_ui_actions.js`, `python tests/run.py ui_bridge`, `node tests/js/test_i18n.mjs`, `node tests/js/test_nhom_agent_workflow.js`
Expected: green. If `test_nhom_agent_workflow.js` guards the `agents`/`workflows` pages by strings in console.js, update the expectation to `workspace` (read the test before editing).

- [ ] **Step 7: Commit**

```bash
git add dashboard/console.js dashboard/ui-actions.js dashboard/packs.js dashboard/chatbots.js dashboard/i18n/vi.json dashboard/i18n/en.json server/ui_targets.py tests/python/test_ui_bridge.py tests/js/test_nhom_agent_workflow.js
git commit -m "Partners page replaces the Agents and Workflows pages in the sidebar

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `dashboard/workspace.js` (three columns) + `wf_event` frame + inline editor

**Files:**
- Create: `dashboard/workspace.js`
- Modify: `dashboard/index.html` (add `<script src="/static/workspace.js?v=1">` RIGHT AFTER `studio.js`, BEFORE `console.js`)
- Modify: `dashboard/app.js` (the `else if (data.type === "system")` chain ~:678: add a `wf_event` branch)
- Modify: `dashboard/studio.js` (`editAgent(a)` :541, `editWorkflow(w)` :380, `window.JavisStudio` :76)
- Modify: `dashboard/i18n/vi.json`, `en.json` (`ws.*` keys)
- Test: `tests/js/test_workspace.js`

**Interfaces:**
- Consumes: `POST /sessions/new`, `GET /sessions?channel=`, `GET /agents` (`last_chat_at`), `GET /workflows` (`last_run_at`), `GET /workflows/runs`, `window.JavisSessions.open/new/current/brain`, `window.JavisWsSend(obj)`, `window.JavisPacks.moKho(kind, fromPage, label)`, `window.JavisStudio.editAgent(a, opts)` / `editWorkflow(w, opts)`
- Produces: `window.JavisWorkspace = { render(el, {borrow}), onWfEvent(frame), state() }`; WS frame sent `{"action":"wf_resume", session_id, task_id, node, code, brain}`

- [ ] **Step 1: Edit studio.js so the editor can render into any host**

In `editAgent(a)` change the signature to `editAgent(a, opts)`; `opts = opts || {}`:
- `const box = opts.host || document.getElementById("editorBox");`
- Replace every `editor.classList.add("open")` / `remove("open")` with `moDong(true|false)` where `const moDong = (mo) => { if (!opts.host) editor.classList.toggle("open", mo); };`
- Cancel button: `box.querySelector("#cancelEd").onclick = () => { if (opts.host) return; moDong(false); };` and when there is a host, hide the Cancel button: add `style="display:none"` if `opts.host`.
- After saving: `moDong(false); if (opts.onSaved) opts.onSaved(); else loadAgents();`
- Because the form uses ids (`#agName`...) and the whole page has only ONE agent form open at a time, keep the ids.

`editWorkflow(w)` -> `editWorkflow(w, opts)`: after saving `editor.classList.remove("open"); if (opts && opts.onSaved) opts.onSaved(); else loadWorkflows();`. The `#studioEditor` modal is still used (it lives in the global index.html).

Add `editAgent, editWorkflow, exportItem` to `window.JavisStudio`.

- [ ] **Step 2: app.js forwards the `wf_event` frame**

In the `if/else` chain that handles `data.type` (near line 678), add BEFORE the `"system"` branch:

```js
  } else if (data.type === "wf_event") {
    // Per-step progress of a workflow run (the Partners page draws it in the right column). The chat frame
    // draws nothing: the status chip already travels in its own status frame.
    try { if (window.JavisWorkspace) window.JavisWorkspace.onWfEvent(data); } catch (e) {}
```

- [ ] **Step 3: Write the failing JS test**

`tests/js/test_workspace.js`:

```js
/* Partners page (dashboard/workspace.js): ordering, session picking, workflow progress.

       node tests/js/test_workspace.js

   Runs under node with a minimal fake DOM: workspace.js exposes its pure part through window.JavisWorkspace. */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "..");

global.window = { t: (k) => k, ic: () => "", addEventListener() {}, matchMedia: () => ({ matches: false }) };
global.document = { getElementById: () => null, createElement: () => ({ classList: { add() {}, remove() {} }, appendChild() {} }), body: { classList: { add() {}, remove() {} } } };
global.localStorage = { getItem: () => null, setItem() {} };
require(path.join(root, "dashboard", "workspace.js"));
const W = window.JavisWorkspace;

let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

// Ordering: most recent timestamp first, items with no timestamp sorted after by name
const wfs = [{ slug: "a", name: "Bản tin", last_run_at: 0 }, { slug: "b", name: "Viết bài", last_run_at: 50 }, { slug: "c", name: "Ads", last_run_at: 99 }, { slug: "d", name: "Zalo", last_run_at: 0 }];
check("xep quy trinh theo lan chay gan nhat", W.sapXep(wfs, "last_run_at").map(x => x.slug).join(",") === "c,b,a,d");
const ags = [{ slug: "x", name: "Người viết", last_chat_at: 0 }, { slug: "y", name: "Jarvis 007", last_chat_at: 3 }];
check("xep tro ly theo lan chat gan nhat", W.sapXep(ags, "last_chat_at").map(x => x.slug).join(",") === "y,x");

// Filter: diacritic-insensitive search + group
const ds = [{ slug: "a", name: "Người viết", role: "viết", group: "Marketing" }, { slug: "b", name: "Kế toán", role: "sổ sách", group: "Finance" }];
check("loc theo chu khong dau", W.loc(ds, "nguoi viet", "").map(x => x.slug).join() === "a");
check("loc theo nhom", W.loc(ds, "", "Finance").map(x => x.slug).join() === "b");

// Workflow progress from wf_event
const st = W.tienDoMoi(3);
W.apDung(st, { type: "step_start", i: 0, agent: "A" });
check("step_start -> buoc 0 dang lam", st.buoc[0].trang_thai === "dang" && st.hien_tai === 0);
W.apDung(st, { type: "step_done", i: 0 });
W.apDung(st, { type: "step_start", i: 1, agent: "B" });
check("step_done -> xong, sang buoc 1", st.buoc[0].trang_thai === "xong" && st.buoc[1].trang_thai === "dang");
W.apDung(st, { type: "wait_user", node: "dang", task_id: "tk", code: "AB" });
check("wait_user -> cho duyet + giu code", st.cho_duyet && st.cho_duyet.code === "AB" && st.trang_thai === "cho");
W.apDung(st, { type: "done" });
check("done -> xong het", st.trang_thai === "xong" && st.buoc.every(b => b.trang_thai === "xong"));
const st2 = W.tienDoMoi(2);
W.apDung(st2, { type: "step_start", i: 0, agent: "A" });
W.apDung(st2, { type: "error", content: "chết" });
check("error -> buoc dang lam thanh loi", st2.trang_thai === "loi" && st2.buoc[0].trang_thai === "loi");
check("phan tram", W.phanTram(W.tienDoMoi(4)) === 0 && W.phanTram(st) === 100);

// Wiring
const app = fs.readFileSync(path.join(root, "dashboard", "app.js"), "utf8");
check("app.js chuyen wf_event sang JavisWorkspace", /data\.type === "wf_event"/.test(app) && /JavisWorkspace\.onWfEvent\(/.test(app));
const html = fs.readFileSync(path.join(root, "dashboard", "index.html"), "utf8");
check("index.html nap workspace.js sau studio.js, truoc console.js",
  html.indexOf("studio.js") < html.indexOf("workspace.js") && html.indexOf("workspace.js") < html.indexOf("console.js"));
const con = fs.readFileSync(path.join(root, "dashboard", "console.js"), "utf8");
check("console.js co renderWorkspace muon khung chat", /function renderWorkspace\(el\)/.test(con) && /JavisWorkspace\.render\(el, \{ borrow: _borrowChatNodes \}\)/.test(con));
const studio = fs.readFileSync(path.join(root, "dashboard", "studio.js"), "utf8");
check("studio.js editAgent nhan host + onSaved", /function editAgent\(a, opts\)/.test(studio) && /opts\.host/.test(studio) && /opts\.onSaved/.test(studio));

if (fails.length) { console.log("\nFAIL:", fails.length, fails); process.exit(1); }
console.log("\nOK - workspace");
```

Run: `node tests/js/test_workspace.js` -> FAIL (the module does not exist yet).

- [ ] **Step 4: Write `dashboard/workspace.js`**

```js
/* workspace.js - Partners page: chat with each agent and each workflow in the same chat frame.

   Three columns: left = list (Agents | Workflows), middle = the app's BORROWED chat frame (console.js
   borrows/returns the nodes, this file only receives the slot), right = agent settings or progress + run history.

   Each partner has its own session in the session store (channel agent:<slug> / workflow:<slug>). Sending a message
   still goes over the normal WebSocket path of app.js; the server looks at the session's channel and branches. The
   wf_event frame (per-step progress) is forwarded by app.js into onWfEvent() here.

   The pure part (sapXep, loc, tienDoMoi, apDung, phanTram) is exposed so it can be tested with node.
   Note: do NOT use the em dash character. Displayed text comes from the window.t dictionary. */
(function () {
  "use strict";
  var t = function (k, v) { return (window.t ? window.t(k, v) : k); };
  var ic = function (n, o) { return (window.ic ? window.ic(n, o) : ""); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]; }); }
  function khongDau(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase(); }
  function brain() { try { return window.JavisSessions ? window.JavisSessions.brain() : "brain"; } catch (e) { return "brain"; } }
  async function api(url, opt) { var r = await fetch(url, opt); return r.json(); }
  function fd(o) { var f = new FormData(); Object.keys(o).forEach(function (k) { f.append(k, o[k]); }); return f; }

  // ---------- pure part ----------
  function sapXep(ds, khoa) {
    return ds.slice().sort(function (a, b) {
      var ma = Number(a[khoa] || 0), mb = Number(b[khoa] || 0);
      if (ma !== mb) return mb - ma;
      return String(a.name || "").localeCompare(String(b.name || ""), "vi");
    });
  }
  function loc(ds, q, nhom) {
    var nq = khongDau(q || "").trim();
    return ds.filter(function (x) {
      if (nhom && (x.group || "Chung") !== nhom) return false;
      if (!nq) return true;
      return khongDau([x.name, x.role, x.description, x.slug].join(" ")).indexOf(nq) >= 0;
    });
  }
  function tienDoMoi(n) {
    var buoc = [];
    for (var i = 0; i < n; i++) buoc.push({ i: i, agent: "", trang_thai: "cho", loi: "" });
    return { buoc: buoc, hien_tai: -1, trang_thai: "cho", cho_duyet: null, run_id: "" };
  }
  function apDung(st, ev) {
    var i = Number(ev.i);
    if (ev.type === "start") { st.run_id = ev.run_id || ""; if (Number(ev.steps) > st.buoc.length) { while (st.buoc.length < Number(ev.steps)) st.buoc.push({ i: st.buoc.length, agent: "", trang_thai: "cho", loi: "" }); } st.trang_thai = "dang"; }
    else if (ev.type === "step_start") { while (st.buoc.length <= i) st.buoc.push({ i: st.buoc.length, agent: "", trang_thai: "cho", loi: "" }); st.buoc[i].agent = ev.agent || st.buoc[i].agent; st.buoc[i].trang_thai = "dang"; st.hien_tai = i; st.trang_thai = "dang"; }
    else if (ev.type === "step_done") { if (st.buoc[i]) st.buoc[i].trang_thai = "xong"; }
    else if (ev.type === "step_error") { if (st.buoc[i]) { st.buoc[i].loi = ev.content || ""; } }
    else if (ev.type === "wait_user") { st.trang_thai = "cho"; st.cho_duyet = { node: ev.node || "", prompt: ev.prompt || "", task_id: ev.task_id || "", code: ev.code || "" }; }
    else if (ev.type === "error") { st.trang_thai = "loi"; if (st.hien_tai >= 0 && st.buoc[st.hien_tai] && st.buoc[st.hien_tai].trang_thai === "dang") { st.buoc[st.hien_tai].trang_thai = "loi"; st.buoc[st.hien_tai].loi = ev.content || ""; } }
    else if (ev.type === "done") { st.trang_thai = "xong"; st.cho_duyet = null; st.buoc.forEach(function (b) { b.trang_thai = "xong"; }); }
    return st;
  }
  function phanTram(st) {
    if (!st.buoc.length) return 0;
    if (st.trang_thai === "xong") return 100;
    return Math.round(st.buoc.filter(function (b) { return b.trang_thai === "xong"; }).length / st.buoc.length * 100);
  }

  // ---------- page state ----------
  var S = { loai: "agent", q: "", nhom: "", agents: [], workflows: [], chon: { agent: null, workflow: null },
            el: null, tienDo: {}, sessionCuaPhien: {} };   // tienDo[session_id] = progress of the run being viewed

  function danhSach() { return S.loai === "agent" ? S.agents : S.workflows; }
  function kenh(item) { return (S.loai === "agent" ? "agent:" : "workflow:") + item.slug; }
  function dangChon() { var slug = S.chon[S.loai]; return danhSach().find(function (x) { return x.slug === slug; }) || null; }

  async function taiDanhSach() {
    var b = encodeURIComponent(brain());
    var r = await Promise.all([api("/agents?brain=" + b), api("/workflows?brain=" + b)]);
    S.agents = sapXep(r[0].agents || [], "last_chat_at");
    S.workflows = sapXep((r[1].workflows || []).filter(function (w) { return w.status === "active"; }), "last_run_at");
  }

  // ---------- build the frame ----------
  function render(el, opts) {
    S.el = el;
    el.innerHTML =
      '<div class="wspage" id="wsPage">' +
        '<aside class="ws-left" id="wsLeft">' +
          '<div class="ws-seg"><button type="button" data-loai="agent">' + ic("bot") + ' ' + esc(t("ws.tab_agent")) + '</button>' +
          '<button type="button" data-loai="workflow">' + ic("workflow") + ' ' + esc(t("ws.tab_workflow")) + '</button></div>' +
          '<input class="ws-search" id="wsSearch" placeholder="' + esc(t("ws.search_ph")) + '">' +
          '<select class="ws-group" id="wsGroup"></select>' +
          '<div class="ws-list" id="wsList"></div>' +
          '<div class="ws-left-foot"><button type="button" class="ws-btn" id="wsNew">' + ic("plus") + ' ' + esc(t("ws.new_item")) + '</button>' +
          '<button type="button" class="ws-btn" id="wsStore">' + ic("package") + ' Jarvis 007 Store</button></div>' +
        '</aside>' +
        '<div class="ws-main">' +
          '<div class="ws-bar">' +
            '<button type="button" class="ws-ico" id="wsLeftBtn" title="' + esc(t("ws.toggle_list")) + '">' + ic("panel-left") + '</button>' +
            '<div class="ws-id" id="wsIdentity"></div>' +
            '<button type="button" class="ws-btn" id="wsNewChat">' + esc(t("sess.new_chat")) + '</button>' +
            '<button type="button" class="ws-ico" id="wsRightBtn" title="' + esc(t("ws.toggle_panel")) + '">' + ic("panel-right") + '</button>' +
          '</div>' +
          '<div class="ws-slot" id="wsSlot"></div>' +
        '</div>' +
        '<aside class="ws-right" id="wsRight"></aside>' +
      '</div>';
    if (opts && opts.borrow) opts.borrow(el.querySelector("#wsSlot"));
    el.querySelectorAll("[data-loai]").forEach(function (b) { b.onclick = function () { S.loai = b.dataset.loai; luuChon(); veTrai(); chonMacDinh(); }; });
    el.querySelector("#wsSearch").oninput = function (e) { S.q = e.target.value; veDanhSach(); };
    el.querySelector("#wsGroup").onchange = function (e) { S.nhom = e.target.value; veDanhSach(); };
    el.querySelector("#wsNew").onclick = taoMoi;
    el.querySelector("#wsStore").onclick = function () { if (window.JavisPacks && window.JavisPacks.moKho) window.JavisPacks.moKho(S.loai, "workspace", t("page.workspace.label")); };
    el.querySelector("#wsNewChat").onclick = function () { var x = dangChon(); if (x) moPhien(x, true); };
    el.querySelector("#wsLeftBtn").onclick = function () { el.querySelector("#wsPage").classList.toggle("left-open"); };
    el.querySelector("#wsRightBtn").onclick = function () { el.querySelector("#wsPage").classList.toggle("right-open"); };
    try { var l = localStorage.getItem("javis_ws_loai"); if (l === "agent" || l === "workflow") S.loai = l; S.chon.agent = localStorage.getItem("javis_ws_agent"); S.chon.workflow = localStorage.getItem("javis_ws_workflow"); } catch (e) {}
    taiDanhSach().then(function () { veTrai(); chonMacDinh(); });
  }
  function luuChon() { try { localStorage.setItem("javis_ws_loai", S.loai); if (S.chon.agent) localStorage.setItem("javis_ws_agent", S.chon.agent); if (S.chon.workflow) localStorage.setItem("javis_ws_workflow", S.chon.workflow); } catch (e) {} }

  function veTrai() {
    var el = S.el; if (!el) return;
    el.querySelectorAll("[data-loai]").forEach(function (b) { b.classList.toggle("on", b.dataset.loai === S.loai); });
    var nhoms = {}; danhSach().forEach(function (x) { nhoms[x.group || "Chung"] = 1; });
    var sel = el.querySelector("#wsGroup");
    sel.innerHTML = '<option value="">' + esc(t("ws.all_groups")) + '</option>' + Object.keys(nhoms).sort().map(function (g) { return '<option value="' + esc(g) + '"' + (g === S.nhom ? " selected" : "") + '>' + esc(g) + '</option>'; }).join("");
    el.querySelector("#wsNew").innerHTML = ic("plus") + " " + esc(S.loai === "agent" ? t("ws.new_agent") : t("ws.new_workflow"));
    veDanhSach();
  }
  function veDanhSach() {
    var el = S.el; if (!el) return;
    var ds = loc(danhSach(), S.q, S.nhom), chon = S.chon[S.loai];
    var host = el.querySelector("#wsList");
    if (!ds.length) { host.innerHTML = '<div class="ws-empty">' + esc(t("ws.empty")) + '</div>'; return; }
    host.innerHTML = ds.map(function (x) {
      var phu = S.loai === "agent" ? (x.group || "Chung") + " · " + (x.role || "") : (x.group || "Chung") + " · " + (x.steps || []).length + " " + t("studio.steps");
      return '<button type="button" class="ws-item' + (x.slug === chon ? " on" : "") + '" data-slug="' + esc(x.slug) + '">' +
        '<span class="ws-item-ic">' + ic(S.loai === "agent" ? "bot" : "workflow") + '</span>' +
        '<span class="ws-item-text"><strong>' + esc(x.name) + '</strong><small>' + esc(phu) + '</small></span></button>';
    }).join("");
    host.querySelectorAll("[data-slug]").forEach(function (b) { b.onclick = function () { S.chon[S.loai] = b.dataset.slug; luuChon(); veDanhSach(); moPhien(dangChon(), false); S.el.querySelector("#wsPage").classList.remove("left-open"); }; });
  }
  function chonMacDinh() {
    var ds = danhSach(); if (!ds.length) { veGiua(null); vePhai(null); return; }
    if (!ds.some(function (x) { return x.slug === S.chon[S.loai]; })) S.chon[S.loai] = ds[0].slug;
    veDanhSach(); moPhien(dangChon(), false);
  }

  // ---------- sessions ----------
  async function moPhien(item, moiHan) {
    veGiua(item); vePhai(item);
    if (!item) return;
    var b = encodeURIComponent(brain()), ch = kenh(item), id = null;
    if (!moiHan) {
      var r = await api("/sessions?brain=" + b + "&channel=" + encodeURIComponent(ch) + "&limit=1");
      if (r.sessions && r.sessions[0]) id = r.sessions[0].id;
    }
    if (!id) {
      var n = await api("/sessions/new", { method: "POST", body: fd({ brain: brain(), channel: ch }) });
      if (!n.id) { veLoi(n.error || t("ws.err_session")); return; }
      id = n.id;
    }
    S.sessionCuaPhien[id] = item.slug;
    if (window.JavisSessions) window.JavisSessions.open(id);
    if (S.loai === "workflow") taiLichSu(item);
  }
  function veLoi(msg) { var el = S.el && S.el.querySelector("#wsIdentity"); if (el) el.innerHTML += '<small class="ws-err">' + esc(msg) + '</small>'; }
  function veGiua(item) {
    var el = S.el && S.el.querySelector("#wsIdentity"); if (!el) return;
    if (!item) { el.innerHTML = '<strong>' + esc(t("ws.pick_one")) + '</strong>'; return; }
    var phu = S.loai === "agent" ? (item.group || "Chung") + " · " + (item.role || "") : t("ws.wf_sub", { n: (item.steps || []).length });
    el.innerHTML = ic(S.loai === "agent" ? "bot" : "workflow") + '<div><strong>' + esc(item.name) + '</strong><small>' + esc(phu) + '</small></div>';
    var inp = document.getElementById("chatInput");
    if (inp) inp.placeholder = S.loai === "agent" ? t("ws.ph_agent", { ten: item.name }) : t("ws.ph_workflow");
  }

  // ---------- right column ----------
  function vePhai(item) {
    var host = S.el && S.el.querySelector("#wsRight"); if (!host) return;
    if (!item) { host.innerHTML = ""; return; }
    if (S.loai === "agent") {
      host.innerHTML = '<div class="ws-rtitle">' + esc(t("ws.agent_settings")) + '</div><div class="ws-form" id="wsAgentForm"></div>' +
        '<div class="ws-acts"><button type="button" class="ws-btn" id="wsExport">' + esc(t("studio.export")) + '</button>' +
        '<button type="button" class="ws-btn danger" id="wsDel">' + esc(t("common.delete")) + '</button></div>' +
        '<div class="ws-rtitle">' + esc(t("ws.recent_chats")) + '</div><div class="ws-sess" id="wsSess"></div>';
      if (window.JavisStudio && window.JavisStudio.editAgent) {
        window.JavisStudio.editAgent(item, { host: host.querySelector("#wsAgentForm"), onSaved: async function () { await taiDanhSach(); veTrai(); veGiua(dangChon()); } });
      }
      host.querySelector("#wsExport").onclick = function () { window.JavisStudio && window.JavisStudio.exportItem("agent", item.slug); };
      host.querySelector("#wsDel").onclick = async function () {
        if (!confirm(t("studio.del_ag", { ten: item.name }))) return;
        await api("/agents/delete", { method: "POST", body: fd({ slug: item.slug, brain: brain() }) });
        S.chon.agent = null; await taiDanhSach(); veTrai(); chonMacDinh();
      };
      taiPhienGanDay(item);
    } else {
      var td = tienDoHienTai(item);
      host.innerHTML = '<div class="ws-rtitle">' + esc(t("ws.wf_progress")) + '</div>' +
        '<div class="ws-prog"><div style="width:' + phanTram(td) + '%"></div></div>' +
        '<div class="ws-status" id="wsWfStatus">' + esc(nhanTienDo(td)) + '</div>' +
        '<div class="ws-steps" id="wsSteps"></div>' +
        '<div class="ws-acts"><button type="button" class="ws-btn" id="wsEditWf">' + esc(t("ws.edit_steps")) + '</button>' +
        '<button type="button" class="ws-btn" id="wsExport">' + esc(t("studio.export")) + '</button>' +
        '<button type="button" class="ws-btn danger" id="wsDel">' + esc(t("common.delete")) + '</button></div>' +
        '<div class="ws-rtitle">' + esc(t("ws.run_history")) + '</div><div class="ws-runs" id="wsRuns"></div>';
      veBuoc(item, td);
      host.querySelector("#wsEditWf").onclick = function () { window.JavisStudio && window.JavisStudio.editWorkflow(item, { onSaved: async function () { await taiDanhSach(); veTrai(); vePhai(dangChon()); } }); };
      host.querySelector("#wsExport").onclick = function () { window.JavisStudio && window.JavisStudio.exportItem("workflow", item.slug); };
      host.querySelector("#wsDel").onclick = async function () {
        if (!confirm(t("studio.del_wf", { ten: item.name }))) return;
        await api("/workflows/delete", { method: "POST", body: fd({ slug: item.slug, brain: brain() }) });
        S.chon.workflow = null; await taiDanhSach(); veTrai(); chonMacDinh();
      };
    }
  }
  function tenAgent(slug) { var a = S.agents.find(function (x) { return x.slug === slug; }); return a ? a.name : slug; }
  function tienDoHienTai(item) {
    var sid = window.JavisSessions ? window.JavisSessions.current() : null;
    if (sid && S.tienDo[sid]) return S.tienDo[sid];
    var td = tienDoMoi((item.steps || []).length);
    td.buoc.forEach(function (b, i) { b.agent = tenAgent((item.steps[i] || {}).agent); });
    return td;
  }
  function nhanTienDo(td) {
    if (td.trang_thai === "dang") return t("ws.running_step", { a: td.hien_tai + 1, b: td.buoc.length });
    if (td.trang_thai === "xong") return t("ws.done");
    if (td.trang_thai === "loi") return t("ws.failed");
    if (td.cho_duyet) return t("ws.waiting");
    return t("ws.ready");
  }
  function veBuoc(item, td) {
    var host = S.el && S.el.querySelector("#wsSteps"); if (!host) return;
    host.innerHTML = td.buoc.map(function (b, i) {
      var task = ((item.steps || [])[i] || {}).task || "";
      var nhan = { cho: t("ws.step_wait"), dang: t("ws.step_doing"), xong: t("ws.step_done"), loi: t("ws.step_err") }[b.trang_thai];
      return '<div class="ws-step ' + b.trang_thai + '"><span class="ws-num">' + (b.trang_thai === "xong" ? ic("check") : (i + 1)) + '</span>' +
        '<strong>' + esc(task.slice(0, 80) || t("ws.step_n", { n: i + 1 })) + '</strong><small>' + esc(nhan) + (b.loi ? ": " + esc(b.loi) : "") + '</small>' +
        '<div class="ws-who">' + ic("bot") + ' ' + esc(b.agent || tenAgent((item.steps[i] || {}).agent)) + '</div></div>';
    }).join("") + (td.cho_duyet ? '<div class="ws-wait">' + esc(t("studio.wait1")) + ' "' + esc(td.cho_duyet.node) + '"' + (td.cho_duyet.prompt ? ": " + esc(td.cho_duyet.prompt) : "") +
      '<div><button type="button" class="ws-btn primary" id="wsApprove">' + esc(t("studio.approve")) + ' ' + esc(td.cho_duyet.code) + '</button><small>' + esc(t("studio.wait_warn")) + '</small></div></div>' : "");
    var ap = host.querySelector("#wsApprove");
    if (ap) ap.onclick = function () {
      ap.disabled = true;
      var sid = window.JavisSessions ? window.JavisSessions.current() : null;
      if (!sid || !window.JavisWsSend) return;
      window.JavisWsSend({ action: "wf_resume", session_id: sid, task_id: td.cho_duyet.task_id, node: td.cho_duyet.node, code: td.cho_duyet.code, brain: brain() });
      td.cho_duyet = null; td.trang_thai = "dang"; veBuoc(item, td);
    };
    var stt = S.el.querySelector("#wsWfStatus"); if (stt) stt.textContent = nhanTienDo(td);
    var pg = S.el.querySelector(".ws-prog > div"); if (pg) pg.style.width = phanTram(td) + "%";
  }
  async function taiLichSu(item) {
    var host = S.el && S.el.querySelector("#wsRuns"); if (!host) return;
    var r = await api("/workflows/runs?brain=" + encodeURIComponent(brain()) + "&slug=" + encodeURIComponent(item.slug) + "&limit=10");
    var ds = r.runs || [];
    if (!ds.length) { host.innerHTML = '<div class="ws-empty">' + esc(t("ws.no_runs")) + '</div>'; return; }
    host.innerHTML = ds.map(function (x) {
      var d = new Date(x.started_at * 1000);
      return '<button type="button" class="ws-run ' + esc(x.status) + '" data-sid="' + esc(x.session_id || "") + '">' +
        '<span>' + esc(d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })) + '</span>' +
        '<span class="ws-run-st">' + esc(x.nhan) + '</span><small>' + esc(x.input || "").slice(0, 60) + '</small></button>';
    }).join("");
    host.querySelectorAll("[data-sid]").forEach(function (b) { b.onclick = function () { if (b.dataset.sid && window.JavisSessions) window.JavisSessions.open(b.dataset.sid); }; });
  }
  async function taiPhienGanDay(item) {
    var host = S.el && S.el.querySelector("#wsSess"); if (!host) return;
    var r = await api("/sessions?brain=" + encodeURIComponent(brain()) + "&channel=" + encodeURIComponent("agent:" + item.slug) + "&limit=8");
    var ds = r.sessions || [];
    if (!ds.length) { host.innerHTML = '<div class="ws-empty">' + esc(t("ws.no_chats")) + '</div>'; return; }
    host.innerHTML = ds.map(function (s) { return '<button type="button" class="ws-run" data-sid="' + esc(s.id) + '"><strong>' + esc(s.title || s.preview || t("ws.untitled")) + '</strong></button>'; }).join("");
    host.querySelectorAll("[data-sid]").forEach(function (b) { b.onclick = function () { window.JavisSessions && window.JavisSessions.open(b.dataset.sid); }; });
  }

  // ---------- workflow events from the WebSocket ----------
  function onWfEvent(frame) {
    var sid = frame.session_id, ev = frame.event || {}; if (!sid) return;
    var item = dangChon();
    if (!S.tienDo[sid]) { var n = (item && S.loai === "workflow" && S.sessionCuaPhien[sid] === item.slug) ? (item.steps || []).length : Number(ev.steps || 0); S.tienDo[sid] = tienDoMoi(n); }
    apDung(S.tienDo[sid], ev);
    var cur = window.JavisSessions ? window.JavisSessions.current() : null;
    if (item && S.loai === "workflow" && cur === sid) { veBuoc(item, S.tienDo[sid]); if (ev.type === "done" || ev.type === "error" || ev.type === "wait_user") { taiLichSu(item); taiDanhSach().then(veTrai); } }
  }

  // ---------- create new ----------
  function taoMoi() {
    if (!window.JavisStudio) return;
    var sau = async function () { await taiDanhSach(); veTrai(); chonMacDinh(); };
    if (S.loai === "agent") window.JavisStudio.editAgent(null, { onSaved: sau });
    else window.JavisStudio.editWorkflow(null, { onSaved: sau });
  }

  window.JavisWorkspace = { render: render, onWfEvent: onWfEvent, sapXep: sapXep, loc: loc, tienDoMoi: tienDoMoi, apDung: apDung, phanTram: phanTram, state: function () { return S; } };
})();
```

When `editAgent(null, {onSaved})` has no `host`, it opens the modal as before (create new). Check that `window.JavisSessions.current()` exists (app.js:1084 has `current`).

- [ ] **Step 5: CSS**

Add to `dashboard/console.css` (end of file) a `.wspage` block following the `.chatpage` pattern in `_injectChatCss` (console.js:6257): three columns `display:flex; height:100%`, `.ws-left{width:260px}`, `.ws-right{width:320px; overflow:auto}`, `.ws-main{flex:1; min-width:0; display:flex; flex-direction:column}`, `.ws-slot{flex:1; min-height:0; display:flex; flex-direction:column}`, `.ws-seg` two buttons, `.ws-item.on` light orange background with a `#7d532d` border, `.ws-step` with a round `.ws-num`, `.ws-prog` a 4px bar in `var(--accent)` (use the theme's existing color variable, grep `--accent` or the equivalent in style.css), `.ws-run` a full-width button. On narrow screens `@media (max-width: 900px)`: `.ws-left`, `.ws-right` become `position:absolute` drawers, shown when `.wspage.left-open` / `.right-open`. Use the color variables `var(--surface-1)`, `var(--glass-brd)`, `var(--text2)` like `.chatpage`.

- [ ] **Step 6: `ws.*` dictionary**

vi.json:

```json
  "ws.tab_agent": "Trợ lý",
  "ws.tab_workflow": "Quy trình",
  "ws.search_ph": "Tìm cộng sự...",
  "ws.all_groups": "Tất cả nhóm",
  "ws.new_item": "Tạo mới",
  "ws.new_agent": "Tạo trợ lý",
  "ws.new_workflow": "Tạo quy trình",
  "ws.toggle_list": "Ẩn/hiện danh sách",
  "ws.toggle_panel": "Ẩn/hiện cột phải",
  "ws.empty": "Chưa có mục phù hợp. Tạo mới hoặc tìm trong Jarvis 007 Store.",
  "ws.pick_one": "Chọn một cộng sự ở cột trái",
  "ws.wf_sub": "Quy trình · {n} bước",
  "ws.ph_agent": "Nhắn cho {ten}...",
  "ws.ph_workflow": "Mô tả kết quả bạn muốn nhận, mỗi tin là một lần chạy...",
  "ws.err_session": "Không mở được hội thoại",
  "ws.agent_settings": "Cài đặt trợ lý",
  "ws.recent_chats": "Hội thoại gần đây",
  "ws.no_chats": "Chưa có hội thoại nào",
  "ws.untitled": "(chưa đặt tên)",
  "ws.wf_progress": "Tiến độ",
  "ws.edit_steps": "Sửa các bước",
  "ws.run_history": "Lịch sử chạy",
  "ws.no_runs": "Chưa chạy lần nào. Gửi một tin để chạy.",
  "ws.running_step": "Đang chạy · Bước {a}/{b}",
  "ws.done": "Đã hoàn tất",
  "ws.failed": "Dừng vì lỗi",
  "ws.waiting": "Đang chờ duyệt",
  "ws.ready": "Sẵn sàng nhận yêu cầu",
  "ws.step_wait": "Chờ đến lượt",
  "ws.step_doing": "Đang thực hiện...",
  "ws.step_done": "Đã hoàn tất",
  "ws.step_err": "Lỗi",
  "ws.step_n": "Bước {n}",
```

en.json: the matching translations (Agents, Workflows, Search partners..., All groups, New, New agent, New workflow, Toggle list, Toggle panel, Nothing matches. Create one or browse Jarvis 007 Store., Pick a partner on the left, Workflow · {n} steps, Message {ten}..., Describe the result you want; each message is one run..., Could not open conversation, Agent settings, Recent chats, No chats yet, (untitled), Progress, Edit steps, Run history, No runs yet. Send a message to run., Running · Step {a}/{b}, Completed, Stopped on error, Waiting for approval, Ready, Waiting, In progress..., Done, Error, Step {n}).

- [ ] **Step 7: index.html**

After the line `studio.js?v=30` add `<script src="/static/workspace.js?v=1"></script>` (cache-busting follows the VERSION that the server attaches automatically; the v number is only a default).

- [ ] **Step 8: Run the tests and check in a browser**

Run: `node tests/js/test_workspace.js`, `node tests/js/test_ui_actions.js`, `node tests/js/test_i18n.mjs`, `node tests/js/test_studio_chon_model_agent.js`
Expected: green.

Start the server locally (memory: port 7777, start-javis.bat, kill directly + absolute path) then open `http://localhost:7777` and go to Partners:
1. Agents tab: pick an agent, send "hello, who are you?" -> the answer follows the agent's role. F5 -> the conversation is still there.
2. Edit the role in the right column, Save -> the header changes.
3. Workflows tab: pick a sample workflow (press Create sample on the Skills/Studio page to seed it if missing: `POST /studio/seed`), send an input -> the "Step 1/2..." chip shows, the right column lights up step by step, the result message "Lần chạy #1 · ..." appears. F5 midway -> you still see it continue.
4. Send a second message "make it half as long" -> the message "Lần chạy #2".
5. Run history has 2 rows; click a row -> it opens the right session.
6. Go back to the Workflows tab: the workflow that just ran is at the top of the list.
7. Chat page: the history bar has NO partner sessions. Ask Jarvis 007 "how did the latest workflow run go?" -> the answer has the workflow name and result (through the tool javis_workflow).
8. Say/type in the main chat "mở trang trợ lý" (Vietnamese for "open the agents page") -> it goes to Partners.
9. Shrink the window to 400px: the two columns become drawers, the chat frame is usable.

Record the result of each item; fix any item that fails before committing.

- [ ] **Step 9: Commit**

```bash
git add dashboard/workspace.js dashboard/console.js dashboard/console.css dashboard/app.js dashboard/studio.js dashboard/index.html dashboard/i18n/vi.json dashboard/i18n/en.json tests/js/test_workspace.js
git commit -m "Partners page: chat with agents and workflows, progress and history in the right column

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Docs, CHANGELOG, VERSION, PR and merge

**Files:**
- Modify: `docs/07-agents-va-workflows.md` (the section "Where to open it in Jarvis 007" and how to run), `docs/en/07-agents-and-workflows.md`
- Modify: `CHANGELOG.md`, `VERSION`

- [ ] **Step 1: Docs**

In `docs/07-agents-va-workflows.md`: change the "Where to open it" section to the Capabilities group having a **Partners** item (in the Vietnamese doc: **Cộng sự**) with two tabs Agents | Workflows (Trợ lý | Quy trình); add a section "Chat with an agent" (pick on the left column, chat in the middle, settings in the right column, each agent has several conversations); rewrite the section "Run a workflow": sending a message is one run, progress is in the right column, the result comes back to chat, later messages remember the previous result, the run history is in the right column and Jarvis 007 can look it up from a question in the main chat frame. Change the sentence "press ▶ Run directly on the Workflows page" to "send a message on the Partners page". Update the English edition correspondingly.

- [ ] **Step 2: CHANGELOG + VERSION**

`git fetch origin` then read the number on `origin/main` (memory: bump by the REMOTE number). If the remote is still 0.58.x then this release is `0.59.0` (new feature). Write VERSION and add this at the top of CHANGELOG (the CHANGELOG.md itself is Vietnamese, so the Vietnamese entry below is the text to paste; the English gloss follows it):

```markdown
## [0.59.0] - 2026-09-15
### Thêm mới
- **Trang Cộng sự thay cho hai trang Trợ lý và Quy trình.** Chọn một trợ lý là chat được ngay với đúng vai đó, mỗi trợ lý có hội thoại riêng và cài đặt nằm ở cột phải.
- **Quy trình chạy ngay trong khung chat.** Gửi một tin là một lần chạy, tiến độ từng bước hiện ở cột phải, kết quả về chat và tin sau vẫn nhớ kết quả trước để bạn góp ý tiếp.
- **Lịch sử chạy được lưu lại.** Cột phải liệt kê các lần chạy gần nhất, bấm vào là mở lại; hỏi Jarvis 007 "quy trình chạy gần nhất ra sao" ở khung chat chính là có câu trả lời thật. Quy trình vừa chạy tự lên đầu danh sách.
```

English gloss of that entry (for `CHANGELOG.en.md`):

```markdown
## [0.59.0] - 2026-09-15
### Added
- **The Partners page replaces the Agents and Workflows pages.** Pick an agent and you can chat with it right away in exactly that role; each agent has its own conversations and its settings sit in the right column.
- **Workflows run right inside the chat frame.** Sending a message is one run, per-step progress shows in the right column, the result comes back to chat, and later messages still remember the previous result so you can keep giving feedback.
- **Run history is saved.** The right column lists the most recent runs and clicking one reopens it; ask Jarvis 007 "how did the latest workflow run go" in the main chat frame and you get a real answer. The workflow that just ran moves to the top of the list on its own.
```

- [ ] **Step 3: Run the whole test suite**

Run: `python tests/run.py`
Expected: the new files are green; the only red files are the 13 files already red on this machine (compare with the list in the memory `reference_test-do-gia-tren-may-nay`, "reference: tests that are red on this machine"). State this clearly in the report.

- [ ] **Step 4: Commit, push, PR, merge**

```bash
git add docs CHANGELOG.md VERSION
git commit -m "Docs + CHANGELOG 0.59.0: Partners page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feat/cong-su-workspace
gh pr create --title "Partners page: chat with agents and workflows, save run history (0.59.0)" --body "$(cat <<'EOF'
Spec: docs/superpowers/specs/2026-09-15-cong-su-workspace-design.md
Plan: docs/superpowers/plans/2026-09-15-cong-su-workspace.md

- Page `workspace` (Partners) replaces `agents` + `workflows`; three columns, borrows the app's chat frame.
- A session on channel `agent:<slug>` uses the agent's prompt; a `workflow:<slug>` session turns each message into one `execute_workflow` run, with the result returned to chat, errors and waiting-for-approval included.
- The `workflow_runs.sqlite3` store records every run (Partners, Kanban); `GET /workflows/runs`; tool `javis_workflow`; a "latest run" line in the system prompt.
- `POST /sessions/new`, `GET /sessions?channel=`; the main chat history bar drops partner sessions.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Wait for CI to go green (use ccd_pr to watch), then squash-merge into main per the repo rule (CLAUDE.md: green CI means merge straight in, linear history). If CI is red, fix it first and do not merge.

---

## Self-review

**Spec coverage:**
- Section 3 three-column UI, drawers on narrow screens, Store, Create new, ordering: Task 9 (+ Task 8 page registration).
- Section 4 sessions by channel, `POST /sessions/new`, channel filter, model pinning: Task 3.
- Section 5 chat with an agent, JAVIS_LESSON, log, error when the agent is gone: Task 5.
- Section 6 workflow turn, status/wf_event/stream, done/error/waiting messages, appending the previous result, wf_resume: Task 4 + 6.
- Section 7 history store, wrapping `execute_workflow`, `source`, API, `last_run_at`/`last_chat_at`: Task 1 + 2 (+3).
- Section 8 plugin `javis_workflow`, system prompt line: Task 7.
- Section 9 testing: every task has a test; manual check in Task 9 Step 8.
- Section 11 docs, CHANGELOG, VERSION: Task 10.

**Type consistency:** `execute_workflow(..., source=)` (Task 2) is called by Task 6 with the right parameter name; the keys `trang_thai/ket_qua/so_buoc/loi/wait/run_id` returned by `workflow_chat.chay` (Task 4) are read correctly by `_luot_quy_trinh` (Task 6); the `output_tom_tat` returned by `gan_nhat` (Task 1) is read correctly by the plugin (Task 7) and workspace.js (Task 9, which uses `input`, `nhan`, `session_id`, `started_at`, `status`); `JavisStudio.editAgent(a, {host,onSaved})` (Task 9 Step 1) matches how it is called in workspace.js.

**Placeholder scan:** no "TBD" left; the "read then copy" steps (Task 6 Step 4 the `finally` part, Task 8 Step 4 grep for page ids) are concrete instructions about where to read and what to do.
