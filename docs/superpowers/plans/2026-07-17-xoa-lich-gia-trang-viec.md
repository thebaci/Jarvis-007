# Phase 1: Delete the fake Calendar, merge into a single "Scheduled" page - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the Calendar registry (no executor reads it), close the `bypassPermissions` hole in `/automations/sync`, and merge loops + reminders into one single "Scheduled" page (called "Việc" in the original Vietnamese plan; "Việc" = "jobs").

**Architecture:** Pure deletion + renaming, **no new endpoint**. `automations.json` has never been read by the scheduler (`main.py:3613-3656` has no branch for it), and 0 `automations.json` files exist on all 4 brains, so there is nothing on the user data side to migrate.

The key point (found in pre-flight, the plan was corrected accordingly): `_loops_as_routines` (`main.py:3169`) and `pending_as_automations` (`reminders.py:278`) are **not shared helpers** - they are **a projection layer into the shape of the fake Calendar**, and the only caller of both is `main.py:3199`, i.e. the very `/automations` GET about to be deleted. When the Calendar dies they die with it. The Scheduled page uses the **real endpoints that already exist** directly: loops from `GET /loops` (`console.js:812` already uses it), reminders from `GET /reminders` (`reminders.py:498`, returns `{pending, history, counts}` with a `_view()` richer than the projection) and cancel through `POST /reminders/cancel` (`reminders.py:551`). The first plan draft invented a new `/jobs` API layer just to preserve a projection layer that only exists because of the fake thing - that is YAGNI, dropped.

The requirement still stands: deleting the Calendar rail without merging reminders into the Scheduled page = the user **loses the place to see reminders**, because right now they only show in the Calendar tab.

**Tech Stack:** Python 3.12, FastAPI, vanilla JS (dashboard), plain-script tests (no pytest).

Spec: `docs/superpowers/specs/2026-07-17-hop-nhat-viec-dinh-ky-design.md`

## Global Constraints

- **NEVER use the em dash character (U+2014)** in any file: code, comments, tests, docs, commit messages. Use "-" or rewrite the sentence. (CLAUDE.md, principle 8.)
- English is the main language for comments, docstrings, display names and error messages.
- Tests are **plain scripts, not pytest**. House convention: `server/test_*.py`, with a `def check(name, cond)`, collecting `_fails`, and `sys.exit(1)` on failure. CI runs `for f in test_*.py; do python "$f"; done` (`.github/workflows/ci.yml:35-37`), so every `server/test_*.py` file automatically goes into CI.
- Run tests with the venv: `.venv/Scripts/python.exe` (the system python lacks libs).
- Tests must isolate themselves: `os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="..."))` **before** importing any Jarvis 007 module.
- **`dashboard/console.js` helpers** (used by Task 2): only `esc(s)` (`:116`) and `fbrain()` (`:363`), calling HTTP with bare `fetch()` and a `FormData` built in place. There is **NO** `api()`, `fd()`, `brain()` - those are `studio.js` helpers and cannot be used in console.js.
- Do not touch `Javis/loops/*.md`, `loop-state.json`, or `system_sync.LEGACY_HASHES` in this phase. Loops keep their behavior.
- Do not edit `self_improve.py:105-113` (`_isolate`). It is a dead branch in production (`main.py:3029` always injects `apply_mcp`) but `test_loop_ambient.py` relies on it.

## File Structure

| File | Responsibility after phase 1 |
|---|---|
| `server/main.py` | Remove the 5 `/automations*` routes, 3 registry helpers, the `_loops_as_routines` projection layer, the caps block. **Add no endpoint.** |
| `server/reminders.py` | Remove the `pending_as_automations` projection layer (its only caller is `/automations` GET). The rest stays intact. |
| `server/test_jobs.py` | **New.** Covers: route + helpers + dead projection layers, caps clean and still running, and the REAL endpoints the Scheduled page depends on (`/loops`, `/reminders`, `/reminders/cancel`) still exist. |
| `dashboard/studio.js` | Remove the `automations` page (loader, `editAutomation` form, sync button). |
| `dashboard/console.js` | Remove the `automations` rail. The `selfimprove` rail changes its label "Loop" → "Scheduled" (Vietnamese "Việc"), additionally renders the reminders block, fixes copy that points at the Calendar tab. |
| `dashboard/index.html` | Only remove the old dead loop panel (`:160-192`, Task 3). There is **no** `panel-automations` here - it is built dynamically by `console.js:222` from `STUDIO_PAGES`. |
| `dashboard/app.js` | Remove the `/loop/config` fetch of the dead panel (`:1497`). |

**Decomposition note:** the registry block + the caps block **must be in the same task**. `_gather_capabilities` (`main.py:3352`) calls `_read_automations`; deleting the helper but leaving the call makes `rebuild_javis_index` throw `NameError` **on every scheduler tick** (`main.py:3650-3651`). A reviewer cannot approve one and reject the other, so they are one deliverable.

---

### Task 1: Delete the Calendar registry + sync + two projection layers + the caps block (pure deletion)

**Files:**
- Modify: `server/main.py:3140-3262` (delete `_automations_path`/`_read_automations`/`_write_automations`, `_loops_as_routines`, and ALL 5 `/automations*` routes including `/automations/sync` at `:3264-3313`)
- Modify: `server/main.py:3324, 3352-3354, 3411-3413` (delete the dead caps block)
- Modify: `server/reminders.py:278-296` (delete `pending_as_automations`)
- Test: `server/test_jobs.py` (new)

**Interfaces:**
- Consumes: none. This is a **pure deletion task, adding no endpoint**.
- Produces: `_gather_capabilities(brain)` returns a dict **without** the `"automations"` key. Task 2 (UI) consumes **nothing** from this task - it uses the real endpoints that already exist: `GET /loops`, `GET /reminders`, `POST /reminders/cancel`.

**Why delete both projection layers:** `grep -rn "_loops_as_routines\|pending_as_automations" server/` shows the **only** caller of both is `main.py:3199` (`/automations` GET). They are projections of loops/reminders into the shape of a Calendar row (`{id: "__loop__:<slug>", schedule: "mỗi N phút", ...}`; the Vietnamese `schedule` string means "every N minutes"), where the `schedule` string is **made up at GET time** (`main.py:3187`). Without the Calendar there is no reason for them to exist. Keeping them = dead code.

**MERGE TASK 2 INTO THIS ONE (corrected at run time, 2026-07-17):** the earlier plan split `/automations/sync` into a separate Task 2 on the grounds that "a reviewer can reject this part and still approve Task 1". That reason is WRONG: `automations_sync` (`:3264-3313`) reads/writes `automations.json` itself (`:3299`, `:3308`), so it **cannot survive** once the registry is deleted. The two tasks were never independent, and Task 1's assert `not any(p.startswith("/automations"))` would FAIL if sync stayed alive. Delete all 5 endpoints in one task.

If we want to keep the claude.ai routine sync feature it has to be **rewritten** (a separate button on the Model page, with `allowed_tools`), there is no way to keep it as is - because the store it writes into is gone.

- [ ] **Step 1: Write the failing test**

Create `server/test_jobs.py`:

```python
"""Test: the fake Calendar registry is fully deleted, the real sources of the Scheduled page are intact. Run by hand / CI:

    cd server && python test_jobs.py

Background: automations.json NEVER had an executor - _scheduler_loop (main.py:3613-3656) has no
branch that reads it, and 0 automations.json files exist on all 4 brains. Phase 1 deletes it,
adds NO endpoint: the Scheduled page uses the existing /loops + /reminders directly.

Covers:
- The 4 /automations* paths are gone from app.routes.
- The 3 registry helpers + 2 projection layers are deleted (their only caller was /automations GET).
- caps: the 'automations' key is deleted, and _gather_capabilities/_render_javis_index still run
  (if the helper is deleted but the call is left, rebuild_javis_index raises NameError EVERY scheduler tick).
- The REAL endpoints the Scheduled page depends on are still alive.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-jobstest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


src = (Path(__file__).parent / "main.py").read_text(encoding="utf-8")
paths = {getattr(r, "path", "") for r in main.app.routes}

# ---- 1. The dead Calendar routes ----
check("route: every /automations* deleted", not any(p.startswith("/automations") for p in paths))

# ---- 2. Registry helpers fully deleted (no path left that writes automations.json) ----
check("helper: _read_automations deleted", not hasattr(main, "_read_automations"))
check("helper: _write_automations deleted", not hasattr(main, "_write_automations"))
check("helper: _automations_path deleted", not hasattr(main, "_automations_path"))
# Assert EXACTLY on the expression that builds the path, NOT the bare string "automations.json":
# main.py:121 mentions that file name in an unrelated comment (about atomic file writes), and the
# new comment at the head of the block also mentions it to explain why it was deleted. A bare
# assert would be IMPOSSIBLE even when the code is right.
check("source: no code left that builds a path to automations.json",
      '"Javis" / "automations.json"' not in src)

# ---- 2b. The two projection layers into the fake Calendar shape die too ----
# The only caller of both is /automations GET (main.py:3199). They project loops/reminders
# into a Calendar row with a schedule string MADE UP at GET time (main.py:3187). No Calendar, no reason.
check("projection: _loops_as_routines deleted", not hasattr(main, "_loops_as_routines"))
check("projection: pending_as_automations deleted",
      not hasattr(main.reminders_feature, "pending_as_automations"))

# ---- 3. caps clean AND still runnable ----
# This is the most important assert of the task: delete _read_automations but leave the call in
# _gather_capabilities:3352 → rebuild_javis_index (main.py:3650-3651) raises NameError every tick.
caps = main._gather_capabilities("brain")
check("caps: no 'automations' key left", "automations" not in caps)
check("caps: _gather_capabilities still runs (no NameError)", isinstance(caps, dict))
check("caps: _render_javis_index still runs", isinstance(main._render_javis_index(caps), str))
# ("Lịch (automations)" is the Vietnamese heading of the old index section, "Calendar (automations)".)
check("caps: the index no longer has the 'Lịch (automations)' section",
      "Lịch (automations)" not in main._render_javis_index(caps))

# ---- 4. The REAL endpoints the Scheduled page depends on must stay alive ----
# Deleting the Calendar must NOT drag the two real sources along with it. Task 2 (UI) calls exactly these three; if this task
# deletes one by mistake the Scheduled page goes blank and only the UI test would notice - catching it right here is far cheaper.
check("route: GET /loops still there (the Scheduled page gets loops from here)", "/loops" in paths)
check("route: GET /reminders still there (the Scheduled page gets reminders from here)", "/reminders" in paths)
check("route: POST /reminders/cancel still there (the Cancel reminder button)", "/reminders/cancel" in paths)


if _fails:
    print(f"\nFAIL - test_jobs: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_jobs: all pass")
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_jobs.py`

Expected: FAIL. Specifically: `route: every /automations* deleted` fails (4 paths still alive), the three `helper: *` asserts fail, the two `projection: *` asserts fail, `caps: no 'automations' key left` fails. The last assert group (`route: GET /loops still there`, `/reminders`, `/reminders/cancel`) **must PASS from the start** - they assert things that already exist and must not be deleted by mistake.

- [ ] **Step 3: Delete the 3 registry helpers + projection layer + 4 old routes**

In `server/main.py`, delete:
- The whole block from `def _automations_path(brain):` (`:3145`) through the end of `_write_automations` (`:3166`).
- The whole function `_loops_as_routines` (`:3169-3193`) - the projection layer, its only caller is the route about to be deleted.
- 4 routes: `automations_list` (`:3196-3202`), `automations_save` (`:3205-3221`), `automations_toggle` (`:3224-3249`), `automations_delete` (`:3251-3261`).

Change the comment at the head of the block (`:3140-3144`) to:

```python
# ============================================================
# Scheduled page = loops (durable jobs, run the engine on a cycle) + reminders (ephemeral jobs, one-shot).
# NO hand-kept registry and NO merged endpoint: the dashboard reads the two real sources directly,
# GET /loops and GET /reminders. The old Calendar tab (5 /automations* routes) was deleted because it never
# had an executor - _scheduler_loop does not read it. See spec 2026-07-17-hop-nhat-viec-dinh-ky.
# ============================================================
```

- [ ] **Step 4: Delete the `pending_as_automations` projection layer in reminders.py**

In `server/reminders.py`, delete the whole method `pending_as_automations` (`:278-296`, anchor: `def pending_as_automations(self, brain: str) -> List[dict]:`).

Keep everything else in the file intact, especially `cancel` (`:300`), `_view` (`:263`), and the `/reminders*` routes (`:498+`) - the Scheduled page depends on them.

Check whether `List` is still used elsewhere before touching the import:

Run: `cd /d/Project/Javis-OS && grep -c "List\[" server/reminders.py`

If the result is > 0 then **keep** `from typing import ... List`. Do not delete an import that still has users.

- [ ] **Step 5: Delete the dead caps block (must be in the same task, see the decomposition note)**

Three edits in `server/main.py`:

1. Line `:3324`, drop the `"automations"` key:

```python
    caps = {"agents": [], "skills": [], "workflows": [], "loops": [], "plugins": []}
```

2. Delete the 3 lines `:3352-3354`:

```python
    for a in _read_automations(brain):
        caps["automations"].append({"id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
            "schedule": a.get("schedule", ""), "status": a.get("status", "active")})
```

3. Delete the 4 lines `:3411-3413`:

```python
    if caps["automations"]:
        L.append("\n## Lịch (automations)")
        for a in caps["automations"]:
            L.append(f"- **{a['name']}** - {a['type']} · {a['schedule']} · {a['status']}")
```

Note: this block does **not** pollute the system prompt. It goes into `Javis/index.md` through `rebuild_javis_index` (`main.py:3462`), and since the list is always empty, `if caps["automations"]:` is always falsy → the section never rendered. This is dead-code cleanup. `_javis_capability_summary` (`:3477`) never mentions automations.

- [ ] **Step 6: Run the test to confirm it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_jobs.py`

Expected: PASS, prints `OK - test_jobs: all pass`.

- [ ] **Step 7: Confirm nothing in server/ still calls what was deleted**

Run: `cd /d/Project/Javis-OS && grep -rn "/automations\|_read_automations\|_loops_as_routines\|pending_as_automations" server/ --include=*.py`

Expected: **0 hits** (except `server/test_jobs.py`, where they are strings in asserts). If real code hits remain, delete them before committing.

- [ ] **Step 8: Commit**

```bash
git add server/main.py server/reminders.py server/test_jobs.py
git commit -m "refactor(jobs): delete the fake Calendar registry + its two projection layers

automations.json never had an executor: _scheduler_loop (main.py:3613-3656)
has no branch that reads it, and 0 automations.json files exist on all 4 brains.

Delete the 3 registry helpers + 4 /automations* routes + the dead caps block. Caps must be deleted
IN THE SAME PASS: _gather_capabilities:3352 calls _read_automations, leaving it is a NameError
on every scheduler tick.

Also delete _loops_as_routines + pending_as_automations: the only caller of both
is /automations GET. They are not shared helpers but a PROJECTION layer into the shape
of the fake Calendar (a made-up 'every N minutes' schedule string at GET time, main.py:3187). No
Calendar, no reason to exist.

Add NO endpoint: the Scheduled page reads /loops + /reminders directly, they already exist.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: One "Scheduled" page - delete the Calendar studio page, merge reminders into the selfimprove rail

**Files:**
- Modify: `dashboard/console.js:23, 46, 49, 64-65, 94, 97, 107` (rail + labels), `:683` (copy), `:708` (add host), `:809-826` (`loadLoops`: call the reminders render)
- Modify: `dashboard/studio.js` (delete loader + form + sync button) - **anchor by function name, NOT by line number**, see the warning below
- Modify: `dashboard/index.html:113-116` (delete the ROUTINES stat cell) - **added at run time**, see below
- Modify: `dashboard/app.js` `loadBrainStats()` (delete the `/automations` fetch + `_setStat("statRoutines"...)`) - **added at run time**

> **A GAP THE PLAN MISSED (found by the Task 2 implementer, 2026-07-17):** the plan only grepped `console.js`/`studio.js`/`index.html`, **never grepped `dashboard/app.js`**. In fact there are two more places:
> - `index.html:113` has `<button class="bstat" data-tab="automations">` labelled **ROUTINES**, clicking it calls `openStudio("automations")` (`app.js:1211-1214`) - the tab just deleted, so it becomes a dead button.
> - `app.js:1201` in `loadBrainStats()` still does `fetch('/automations?brain=')` to count for exactly that cell. The route was deleted in Task 1, so this is a silent 404 (swallowed by `.catch(() => ({}))`), and the ROUTINES number is permanently 0.
>
> The irony: the ROUTINES cell is exactly the **lying badge** this whole spec was born to kill (it counts "running" from a registry that runs nothing), and the plan missed it. Decision: **delete the ROUTINES cell outright**, do not replace it with another cell. The remaining three cells (AGENTS/SKILLS/WORKFLOWS) are all studio pages so they are consistent; the Scheduled page is a console rail and no longer belongs to that row.
>
> Correction to the sentence "do NOT touch `dashboard/index.html`": the narrow meaning is do not go looking for `panel-automations` in it (it is not there) and do not touch the dead loop panel `:160-192` (that is Task 3's job). index.html is NOT untouchable.

> **CONTENTION WARNING (read before editing `studio.js`):** another session is editing `dashboard/studio.js` in parallel. When this plan was drafted, commit `0fcb34f` (not part of this plan) had edited `studio.js` + `index.html` + `VERSION` + `CHANGELOG.md`, and the working tree still had `M dashboard/studio.js` (+43/-10 lines, around lines 211-273) uncommitted. **Every `studio.js` line number in this plan has drifted and is not trustworthy.** Before editing, run `git status` and `grep -n` to get the real positions. If the working tree still holds someone else's half-finished edit, ask before committing over it.
>
> The correct positions **at the time the plan was reviewed** (already drifted from the first draft): `loadAutomations` at `:341` (draft said 306), the `/automations/sync` button at `:350` (draft said 314), `editAutomation` at `:395` (draft said 358). Use `grep -n "function loadAutomations\|function editAutomation"` to get the current numbers.
>
> `panel-automations` is **not in `index.html`**. It is built dynamically by `console.js:222` (`el.innerHTML = '<div class="stab-panel" id="panel-${id}"></div>'`) from `STUDIO_PAGES`. Dropping `"automations"` from `STUDIO_PAGES` (`:107`) is enough. Two files `dashboard/_wf_harness*.html` contain `panel-automations` but they are untracked test harnesses from another session - **do not touch**.

**Interfaces:**
- Consumes: `GET /reminders?brain=` → `{"pending": [...], "history": [...], "counts": {...}}`, each `pending` element has the `_view()` shape (`reminders.py:263`): `{id, text, label, mode, due_at, due_human, chat_id, repeat_min, cron, script, result, error}`. And `POST /reminders/cancel` with form `{id, brain}` → `{ok, error}`. **Both already exist**, Task 1 creates nothing.
- Produces: no new API. The `automations` rail disappears; the `selfimprove` rail **keeps its id** (the id is not changed so deep links/localStorage do not break) but changes its label to "Scheduled" (Vietnamese "Việc").

**Note on `id`:** `_view()` returns the **raw** `id` (no `__reminder__:` prefix like the old projection), and `POST /reminders/cancel` takes exactly that raw `id`. Do not add/strip a prefix.

**Why not simply delete the Calendar rail:** reminders **only** show in the Calendar tab, through `pending_as_automations` (`reminders.py:278`). Deleting the rail without merging = the user loses the place to see pending reminders. This is the regression easiest to slip through in the whole plan.

**Reminder of the helper constraint:** console.js **only** has `esc()` (`:116`) and `fbrain()` (`:363`). Use bare `fetch()` + a `FormData` built in place. `api()`/`fd()`/`brain()` belong to studio.js, calling them here gives `ReferenceError`.

- [ ] **Step 1: Snapshot the state before + check for contention**

Run:

```bash
cd /d/Project/Javis-OS
git status --short dashboard/
grep -rc "automations" dashboard/console.js dashboard/studio.js dashboard/index.html
```

Write down the three numbers. At the end of the task all three must be **0**.

If `git status` shows `dashboard/studio.js` (or another dashboard file in this task) has uncommitted edits that are **not yours**, STOP and ask the reviewer. Another session is working on this very file.

- [ ] **Step 2: Remove the `automations` rail from console.js**

In `dashboard/console.js`:

1. Delete line `:49`: `{ id: "automations", icon: ICON.automations, label: "Lịch" },` (the label "Lịch" is the Vietnamese for "Calendar").
2. Delete `ICON.automations` (`:23`).
3. Delete the `automations:` entry in the description map (`:97`).
4. Drop `"automations"` from `STUDIO_PAGES` (`:107`) - leaving `["workflows", "agents", "skills"]`.
5. Fix the rail groups (`:64-65`):

```js
    { label: "Capabilities", ids: ["agents", "skills", "workflows", "plugins"] },
    { label: "Work",         ids: ["kanban", "selfimprove"] },
```

6. Fix the `selfimprove` rail label (`:46`):

```js
    { id: "selfimprove", icon: ICON.selfimprove, label: "Scheduled" },
```

7. Fix the description (`:94`):

```js
    selfimprove: { icon: "♻", label: "Scheduled", sub: "Recurring jobs + pending reminders" },
```

- [ ] **Step 3: Fix the copy that points at the Calendar tab (easy to miss)**

`dashboard/console.js:683` currently ends with: `Loop bật sẽ hiện ở tab <b>Lịch</b>.` (Vietnamese for "An enabled loop will show in the <b>Calendar</b> tab."). That tab is about to not exist. Remove exactly that last sentence, keep the rest of the paragraph.

Verification run: `cd /d/Project/Javis-OS && grep -n "tab <b>Lịch</b>" dashboard/console.js`

Expected after the fix: 0 hits.

- [ ] **Step 4: Add the host for the reminders block**

`dashboard/console.js:708` is currently `<div id="lpCards">Loading...</div>` (originally "Đang tải..."). Add the host right after it, before `<div class="si-log">`:

```html
      <div id="lpCards">Loading...</div>
      <div id="lpReminders"></div>
```

- [ ] **Step 5: Write `loadReminders` + call it from `loadLoops`**

Add this function inside `renderSelfImprove`, right before `async function loadLoops()` (`:809`):

```js
    // Pending reminders: before, they ONLY showed in the Calendar tab (deleted). If not merged here the user
    // loses the place to see them. Loop = durable job (.md, edited in Obsidian); reminder = ephemeral job.
    // Read /reminders directly (the real source), NOT through the projection layer: that layer only existed because of the Calendar tab.
    async function loadReminders() {
      if (myGen !== _renderGen) return;
      const box = el.querySelector("#lpReminders");
      if (!box) return;
      let d = { pending: [] };
      try { d = await (await fetch(`/reminders?brain=${encodeURIComponent(fbrain())}`)).json(); } catch (e) {}
      if (myGen !== _renderGen) return;
      const rem = d.pending || [];
      if (!rem.length) { box.innerHTML = ""; return; }
      const MODE_LBL = { notify: "reminder", task: "do it + report", script: "script" };
      box.innerHTML = `<h3 style="font-size:15px;color:#cdd8ee;margin:18px 0 8px">Pending reminders</h3>`;
      rem.forEach(r => {
        const title = r.label || r.text || "Reminder";
        const when = r.cron ? `cron ${r.cron}` : (r.due_human || "");
        const kind = MODE_LBL[r.mode] || "reminder";
        const div = document.createElement("div");
        div.className = "si-card";
        div.innerHTML = `<b>${esc(title)}</b>
          <div class="dim" style="font-size:12px;color:#6b7894">${esc(when)} · ${esc(kind)}</div>
          <button class="s-btn-ghost rmCancel" style="margin-top:8px">Cancel</button>`;
        div.querySelector(".rmCancel").onclick = async () => {
          if (!confirm(`Cancel "${title}"?`)) return;
          const f = new FormData();
          f.append("id", r.id);        // RAW id, /reminders/cancel takes exactly this form
          f.append("brain", fbrain());
          await fetch("/reminders/cancel", { method: "POST", body: f });
          loadReminders();
        };
        box.appendChild(div);
      });
    }
```

Then call it at the end of `loadLoops` (`:809-826`), right before the line `clearTimeout(pollTimer);`:

```js
      loadReminders();
```

- [ ] **Step 6: Delete the `automations` studio page**

First get the real positions (the line numbers in the plan have drifted, see the contention warning at the top of the task):

```bash
cd /d/Project/Javis-OS
git status --short dashboard/studio.js
grep -n "function loadAutomations\|function editAutomation\|automations" dashboard/studio.js
```

If `git status` shows `studio.js` has someone else's half-finished edit, **stop and ask** before touching it.

In `dashboard/studio.js` (the first three spots are still at the old lines because they sit above the drifted area):
- Remove `automations: loadAutomations` from the map (`:46`).
- Remove `"automations"` from the array `["workflows", "agents", "skills", "automations"]` (`:55`).
- Delete the branch `else if (tab === "automations") loadAutomations();` (`:58`).
- Delete the whole function `loadAutomations` (anchor: `async function loadAutomations() {`) through the end of its body, including the button that calls `/automations/sync` inside it.
- Delete the whole function `editAutomation` (anchor: `function editAutomation(a) {`) through the end of its body.

Do **not** touch `dashboard/index.html`: `panel-automations` is built dynamically by `console.js:222` from `STUDIO_PAGES`, and Step 2.4 already dropped `"automations"` from that array.

- [ ] **Step 7: Confirm no references remain**

Run: `cd /d/Project/Javis-OS && grep -rn "automations" dashboard/console.js dashboard/studio.js dashboard/index.html`

Expected: **0 hits** in these three files. (Compare with the three numbers noted in Step 1.)

Deliberately **not** grepping all of `dashboard/*.js`: `_studio_old.js` and `_wf_harness*.html` are old/untracked harness files that still contain `panel-automations`, and are outside this task's scope.

- [ ] **Step 8: Check by eye in the real app**

Run the server, open the dashboard:
1. The left rail **no longer has** the "Calendar" item (Vietnamese "Lịch").
2. The item formerly called "Loop" is now called "Scheduled" (Vietnamese "Việc"), inside the "Work" group together with Kanban.
3. Open the Scheduled page: see the loop list; the description at the top of the page **no longer has** the sentence "An enabled loop will show in the Calendar tab" (Vietnamese "Loop bật sẽ hiện ở tab Lịch").
4. The browser console has **no** 404 errors to `/automations`, no `ReferenceError`.
5. Create a reminder through chat ("remind me in 30 minutes to test"), reload the Scheduled page: see the "Pending reminders" block with exactly that reminder. Click Cancel: the reminder disappears and does not come back after a reload.

- [ ] **Step 9: Commit**

```bash
git add dashboard/console.js dashboard/studio.js dashboard/index.html
git commit -m "feat(dashboard): one Scheduled page replacing Loop + Calendar

Delete the Calendar studio page (a 4-field form that leads to no executor) and the
automations rail. The selfimprove rail is relabeled Scheduled, additionally renders the pending
reminders block, and drops the copy sentence pointing at the deleted Calendar tab.

Merging reminders is mandatory: pending_as_automations (reminders.py:278) used to
show them ONLY in the Calendar tab, deleting the rail without merging = the user loses the place to see them.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Clean up the dead loop panel in index.html

**Files:**
- Modify: `dashboard/index.html:160-192` (delete the `display:none` panel)
- Modify: `dashboard/app.js:1497` (delete the `/loop/config` fetch serving that panel)

**Interfaces:**
- Consumes: none.
- Produces: none. A pure deletion task, split out so a reviewer can reject it independently.

**Background:** the old loop panel at `index.html:160-192` has `display:none` (nobody sees it) but `app.js:1497` still fetches `/loop/config` on every page load. The route `/loop/config` is a legacy shim (`self_improve.py:988-1036`) and phase 2 will touch it, so clean up the client first to keep things tidy.

- [ ] **Step 1: Confirm the panel is really dead**

Run: `cd /d/Project/Javis-OS && sed -n '160,192p' dashboard/index.html | grep -n "display:none"; grep -rn "loop/config" dashboard/*.js`

Expected: see `display:none` in the panel, and the `loop/config` hit at `app.js:1497`. If you do **not** see `display:none`, STOP - the panel is alive, this task's assumption is wrong, report back to the reviewer.

- [ ] **Step 2: Delete the panel + fetch**

Delete the block `dashboard/index.html:160-192`. Delete the `/loop/config` fetch and the code that handles its result at `dashboard/app.js:1497`.

- [ ] **Step 3: Confirm the legacy route still exists (backend not deleted yet)**

Run:

```bash
cd server && ../.venv/Scripts/python.exe -c "
import os, sys, tempfile
os.environ.setdefault('JAVIS_STATE_DIR', tempfile.mkdtemp())
sys.path.insert(0, '.')
import main
paths = {getattr(r,'path','') for r in main.app.routes}
print('/loop/config still there:', '/loop/config' in paths)
"
```

Expected: `True`. Phase 1 does **not** delete the backend shim, only drops the dead client. Phase 2 decides the shim's fate.

- [ ] **Step 4: Check by eye**

Reload the dashboard. The Network tab has no request to `/loop/config`, the console has no JS errors, the Scheduled page still shows correctly.

- [ ] **Step 5: Commit**

```bash
git add dashboard/index.html dashboard/app.js
git commit -m "chore(dashboard): delete the dead loop panel + redundant /loop/config fetch

The index.html:160-192 panel has display:none (nobody sees it) but app.js:1497 still
fetches /loop/config on every page load. Backend shim left as is, phase 2
decides its fate.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Run the whole test suite + update docs

**Files:**
- Modify: `CLAUDE.md` (drop the mention of the Calendar tab in the orchestration section)
- Modify: `.claude/skills/javis-builder/SKILL.md` (if it mentions automations/Calendar)
- Modify: `CHANGELOG.md`, `VERSION`

**Interfaces:**
- Consumes: every previous task.
- Produces: none.

- [ ] **Step 1: Run the whole test suite like CI**

Run: `cd server && for f in test_*.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: every file prints `OK - ...`. No file FAILS. Pay special attention to `test_loop_ambient.py` (relies on `_isolate`) and `test_system_sync.py` (relies on `LEGACY_HASHES`) - phase 1 must not touch those two things.

- [ ] **Step 2: Run compileall like CI**

Run: `cd /d/Project/Javis-OS && .venv/Scripts/python.exe -m compileall -q server system/plugins`

Expected: no output (success).

- [ ] **Step 3: Run the CI JS test**

Run: `cd /d/Project/Javis-OS && node dashboard/test_chat_ask.js`

Expected: pass. (CI runs exactly this command at `.github/workflows/ci.yml:27`.)

- [ ] **Step 4: Edit CLAUDE.md**

Run: `cd /d/Project/Javis-OS && grep -n "tab Lịch\|automations" CLAUDE.md`

In the "Orchestration" section, level 6 currently reads: `**Tạo Lịch** - nhắc nhở / job có MỐC GIỜ cố định → qua automations (tab Lịch).` (in English: "**Create a Calendar entry** - a reminder / job at a FIXED TIME → through automations (Calendar tab)."). Change it to:

```markdown
6. **Create a Reminder** - a reminder / job at a FIXED TIME → `POST /reminders` (see the Scheduled page).
```

Keep the 8 levels as they are, do not renumber, so other places that reference this scale do not break.

- [ ] **Step 5: Check the javis-builder skill**

Run: `cd /d/Project/Javis-OS && grep -rn "automations\|tab Lịch" .claude/skills/javis-builder/SKILL.md skills/javis-builder/SKILL.md 2>/dev/null`

If there are hits, fix them the same way as Step 4. If there are no hits, skip this step.

- [ ] **Step 6: Bump VERSION + CHANGELOG**

Read `VERSION`, bump the patch. Add the first entry to `CHANGELOG.md`:

```markdown
## <new version>

- Removed the Calendar tab: the `automations.json` registry never had an executor (the scheduler does not read it), 0 files exist on any brain. Replaced by a single **Scheduled** page showing loops + pending reminders.
- Security: removed `/automations/sync`, a route that called the engine without passing `allowed_tools` so it ran with `bypassPermissions` + loaded `setting_sources`; its "list only" guarantee was only words in the prompt.
- Removed the 5 `/automations*` routes **without** adding any endpoint: the Scheduled page reads `GET /loops` and `GET /reminders` directly, which already existed. Also removed the two projection layers `_loops_as_routines` + `pending_as_automations` (they only existed to build the Calendar row shape).
```

- [ ] **Step 7: Commit + push**

```bash
git add CLAUDE.md CHANGELOG.md VERSION .claude/skills/javis-builder/SKILL.md
git commit -m "docs: update docs after deleting the Calendar tab

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

---

## Left for phase 2 (separate plan)

Not done in this plan, written down so it is not forgotten:

- A shared `parse_schedule()`: one `schedule` field → `{kind: once|interval|cron}` in the Hermes style.
- `cron` in `_eligible_overdue` (`self_improve.py:455-466`) + jitter by `hash(slug)`.
- Hub `X-Javis-Connectors` + `connectors: [...]` in loop frontmatter (highest risk: the hub is a hard layer, it must fail closed).
- `allow_real_actions` replacing the 3-notch dial, mapped into the existing `effective_perm` (`mcp_hub.py:314`).
- Tool `javis_schedule` routing the two stores; `op: list`/`cancel` must look at the union of both.
- The fate of the 5 legacy shim routes `/loop/*` (`self_improve.py:988-1036`).

## Independent bug found while drafting the plan (split into its own issue)

`main.py:3631` calls `tasks_feature.tick(["brain"])` with a **hardcoded** brain, while `tick(brains)` takes a list. A Kanban board in any brain other than `"brain"` is never dispatched. Not part of this plan.
