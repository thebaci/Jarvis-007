# Tool `javis_schedule`: create recurring jobs from chat - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Jarvis 007 a tool to create, list and cancel recurring jobs and reminders straight from chat, replacing hand-typed YAML or a shell call to `curl`.

**Architecture:** `javis_schedule` is a **bundled plugin** (`system/plugins/javis-schedule/`), NOT a tool in the hub. It routes by the nature of the job: reminders/cron/one-shot go to the `reminders` store (already running, full cron support); a repeating job that must be durable and have a prompt editable in Obsidian becomes a `.md` file in `Javis/loops/`. The user and the model see ONE concept, a "job"; which store it lands in is an implementation detail.

**Tech Stack:** Python 3.12, the Jarvis 007 plugin system (`plugins_host.py`), plain-script tests.

Spec: `docs/superpowers/specs/2026-07-17-hop-nhat-viec-dinh-ky-design.md` (section "Tool `javis_schedule`")

---

## The spec is wrong in three places, this plan corrects them

The spec says: *"Add it to the hub next to `javis_use_skill` (`mcp_hub.py:272`)"*. **Wrong, and wrong in a way that would ship an invisible tool.** Reading the real code:

**1. The HTTP hub does not serve that builtin group to Claude/Codex.** `_handle_one` (`mcp_hub.py:391`) calls `discover_all(mode, include_plugins=...)`, i.e. `vault_root=None` (the default at `mcp_hub.py:293`). And `_builtin_tools` **early-returns right after `javis_connections`** (`mcp_hub.py:213-214`: `if not vault_root: return tools, route`). Putting `javis_schedule` next to `javis_use_skill` means Claude Code never sees it.

**2. The hub is only attached when there is at least one MCP connector.** `claude_config_path` (`mcp_hub.py:~450`) returns `None` when `not _has_connections()`. A user who has not connected any MCP has no hub, so no tool. A core capability must not depend on whether the user has connected a connector.

**3. The right path is a plugin, and CLAUDE.md itself teaches that.** `claude_sdk_engine._plugins_server` (`:162-186`) builds an **IN-PROCESS MCP server** from `plugins_host.plugin_tools(mode, None)`, calling the Python handler directly, **not through the hub**, so it hits neither barrier. Codex and the API engines still get plugins through the hub (`mcp_hub.py:334-347`). A bundled plugin reaches every engine. `system/plugins/image-chatgpt/` is the exact precedent: `enabled: true`, `min_mode: safe`, registers `javis_generate_image`, runs on every engine.

**Known limitation, accepted:** `_mcp_servers` (`claude_sdk_engine.py:188-191`) wires in-process plugins only when the engine is **NOT gated**; gated forks (`allowed_tools` has a value: loop mode suggest/auto, reminders mode task, workflow) are deliberately kept isolated and do **not** get plugins. So `javis_schedule` is available in **normal chat** (`main.py:1731` calls `claude_engine` without passing `allowed_tools`, so it is ungated), which is exactly the use case Quy described, but a background loop will not be able to schedule jobs by itself. That is the CORRECT behavior (a loop spawning its own schedules is something we do not want), do not "fix" it.

## An existing bug to fix first, or this tool will write to the wrong brain

`PluginContext.vault_root` (`plugins_host.py:218`) takes the `vault_root` parameter directly. The SDK path passes `None` (`claude_sdk_engine.py:169`, comment "None = global plugin"). So **every plugin called from Claude Code has `ctx.vault_root is None`**.

The consequence is happening TODAY (not hypothetical): `image-chatgpt` passes `vault_root=cctx.vault_root` (`plugin.py:33`) down to `image_gen._resolve_vault` (`image_gen.py:95-98`), which sees it empty and **falls back to `brains/Brain Default`**. In other words: Quy is working in the brain "My Bullet Journal", asks Jarvis 007 to create an image, **the image is saved into Brain Default** and the `![](attachments/...)` link in chat points at a file that is not there. A silent bug that nobody has reported.

If `javis_schedule` copies this pattern it will write loops into the wrong brain and put reminders into the wrong store. **Task 1 fixes that plumbing**, and fixes `image-chatgpt` as a side effect.

## Global Constraints

- **NEVER use the em dash character (U+2014)** in any file: code, comments, tests, docs, commit messages. Use "-" or rewrite the sentence. (CLAUDE.md, principle 8.)
- English for comments, docstrings, tool descriptions and error messages.
- Tests are **plain scripts, not pytest**: `server/test_*.py`, with a `def check(name, cond)`, collecting `_fails`, and `sys.exit(1)` on failure. CI runs `for f in test_*.py; do python "$f"; done` (`.github/workflows/ci.yml:35-37`).
- Run tests with the venv: `.venv/Scripts/python.exe`. Tests isolate themselves with `os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="..."))` BEFORE importing any Jarvis 007 module.
- **The tool description must say clearly WHEN to call it**, because that is the only thing the model reads to decide. Follow the `image-chatgpt` voice.
- Bundled plugins (`system/plugins/`) ship with the app, `enabled: true`. The rule "a plugin created from chat is `enabled: false`" does **not** apply; that rule is for plugins the user writes themselves.
- Do not touch the executor part of `server/self_improve.py` (`_eligible_overdue`, `run_cycle`). This plan only CREATES jobs, it does not change how they run.
- Reminder from phase 1: `dashboard/style.css` still has LIVE `.loop-sel` and `.loop-row`. This plan does not touch CSS.

## File Structure

| File | Responsibility |
|---|---|
| `server/claude_sdk_engine.py:162-186` | `_plugins_server` passes the REAL vault_root instead of `None`. |
| `server/plugins_host.py` | `plugin_tools(mode, vault_root)` separates "which plugins to load" from "which vault the ctx sees". |
| `server/test_plugin_vault.py` | **New.** Regression guard: a plugin's ctx must see the right brain and not fall back to Brain Default. |
| `system/plugins/javis-schedule/plugin.yaml` | **New.** Declares the plugin, `min_mode: safe`. |
| `system/plugins/javis-schedule/plugin.py` | **New.** Tool `javis_schedule`: op create/list/cancel, routing to the two stores. |
| `server/test_javis_schedule.py` | **New.** Covers: routing to the right store, schedule parsing, list sees BOTH stores, cancel. |
| `CLAUDE.md` | Orchestration section: tell Jarvis 007 this tool exists, stop typing YAML by hand. |

---

### Task 1: Plugins must see the right brain (fix the wrong-brain write to Brain Default)

**Files:**
- Modify: `server/claude_sdk_engine.py:162-186` (`_plugins_server`)
- Modify: `server/plugins_host.py` (`plugin_tools`)
- Test: `server/test_plugin_vault.py` (new)

**Interfaces:**
- Consumes: the CURRENT signature, verified: `plugin_tools(mode: str = "full", vault_root: Optional[str] = None) -> Tuple[List[dict], Dict[str, dict]]` (`plugins_host.py:415`). This task ADDS a keyword-only `scope_vault: bool = True`.
- Produces: `ctx.vault_root` **is no longer None** on the chat path. **The REAL mechanism (corrected at run time, differs from the plan draft):** the brain travels EXPLICITLY through `_apply_mcp(cli, mode="full", brain=None)` (`main.py:693`), which sets `cli.javis_vault = _brain_root(brain) if brain else None`, in the same mold as the existing `cli.javis_mode`; `_plugins_server` reads `self.javis_vault`. The plan draft said to infer it from `cwd` (`_brain_root()` checks `(cwd/"Javis").is_dir()`) - **WRONG and removed entirely**: `CLAUDE_CWD` (`main.py:318`) is the project root, which has no `Javis/`, and chat (`main.py:4213`, `:4537`) uses exactly that cwd, so inferring from cwd always misses on the very chat path.

**Why a separate task:** this is an existing bug, independent of `javis_schedule`, and a reviewer can approve or reject it on its own. It also fixes `image-chatgpt` (currently saving images to the wrong brain) without touching that plugin's files.

- [ ] **Step 1: Prove the bug exists before fixing it**

Create `server/test_plugin_vault.py`:

```python
"""Test: a plugin must see the RIGHT brain, not silently fall back to Brain Default. Run by hand / CI:

    cd server && python test_plugin_vault.py

Bug background: claude_sdk_engine._plugins_server calls plugin_tools(mode, None), so
PluginContext.vault_root (plugins_host.py:218) = None for EVERY plugin called from Claude Code.
image-chatgpt passes cctx.vault_root down to image_gen._resolve_vault (image_gen.py:95-98),
which sees it empty and falls back to brains/Brain Default -> the image is saved to the WRONG brain, silently.

Covers:
- PluginContext keeps the vault_root it was given.
- plugin_tools(mode, vault) builds a ctx with that vault (not None).
- _resolve_vault: with a valid vault it does NOT fall back to Brain Default (asserts the premise of the bug).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-pvault-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plugins_host  # noqa: E402
import image_gen     # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_BRAIN = tempfile.mkdtemp(prefix="javis-brain-that-")

# ---- 1. Premise of the bug: _resolve_vault falls back to Brain Default when the vault is empty ----
# If this assert goes red the bug was fixed elsewhere and the test needs rewriting.
fallback = str(image_gen._resolve_vault(None))
check("premise: _resolve_vault(None) falls back to Brain Default",
      fallback.endswith("Brain Default"))
check("premise: _resolve_vault(<real vault>) respects the vault",
      str(image_gen._resolve_vault(_BRAIN)) == _BRAIN)

# ---- 2. PluginContext keeps vault_root ----
# REAL signature (plugins_host.py:214): __init__(self, slug, source, plugin_dir, vault_root)
ctx = plugins_host.PluginContext(slug="thu-nghiem", source="bundled",
                                 plugin_dir=Path(_BRAIN), vault_root=_BRAIN)
check("ctx: keeps the vault_root it was given", ctx.vault_root == _BRAIN)
check("ctx: data_dir is a property, not a hand-assigned field", isinstance(ctx.data_dir, Path))

# ---- 3. _load_all builds a ctx that SEES the vault (this is where the bug lives) ----
# Assert on the REAL ctx of the loaded plugin, not on a return type. LoadedPlugin holds ctx
# (plugins_host.py:257 __slots__ has "ctx"), so it can be read directly. An assert like
# `isinstance(tools, list)` is a TAUTOLOGY: always true even when the ctx is blind to the vault.
ent = plugins_host._load_all(_BRAIN)
loaded = ent["plugins"]
check("load: at least 1 bundled plugin to inspect the ctx of", len(loaded) > 0)
check("ctx: EVERY loaded plugin sees the right brain (not None, not Brain Default)",
      all(lp.ctx.vault_root == _BRAIN for lp in loaded))

# Prove the bug: passing None leaves the ctx blind -> this is exactly what the SDK path is doing.
ent_none = plugins_host._load_all(None)
check("bug: _load_all(None) -> ctx.vault_root is None (premise of the wrong-brain save)",
      all(lp.ctx.vault_root is None for lp in ent_none["plugins"]))


if _fails:
    print(f"\nFAIL - test_plugin_vault: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_plugin_vault: all pass")
```

- [ ] **Step 2: Run the test, confirm it runs and the premises come out right**

Run: `cd server && ../.venv/Scripts/python.exe test_plugin_vault.py`

Expected: both "premise" asserts PASS (proving the bug is real and `_resolve_vault` behaves as described). If `PluginContext(...)` raises `TypeError` because the signature differs, READ `plugins_host.py:209-220` and fix the test to match the REAL signature - do not change the code to fit the test at this step.

- [ ] **Step 3: Read the real signatures before fixing**

Run: `cd /d/Project/Javis-OS && sed -n '160,175p;209,225p' server/plugins_host.py && sed -n '160,172p' server/claude_sdk_engine.py`

Write down: what `plugin_tools` takes, what `PluginContext.__init__` takes, what `_plugins_server` is passing. This plan describes things as understood when it was written; **the real code wins**.

- [ ] **Step 4: Fix `_plugins_server` to pass the real vault**

In `server/claude_sdk_engine.py`, function `_plugins_server` (`:162`), the current line:

```python
        p_tools, p_route = plugins_host.plugin_tools(mode, None)   # None = global plugins, as the hub serves the CLI
```

The problem: one `None` parameter is carrying TWO meanings: "load global plugins (bundled + global, not the vault's own plugins)" AND "the ctx sees no vault". The first meaning is deliberate, the second is the bug.

Change it to:

```python
        # vault_root: ONLY so the plugin's ctx knows which brain it is working in (e.g. image-chatgpt saves
        # the image into the right attachments/). Before, None was passed so EVERY plugin called from Claude Code
        # had ctx.vault_root=None -> image_gen._resolve_vault fell back to "Brain Default" -> saved to the WRONG brain.
        # Still do NOT load the vault's own plugins (old behavior preserved): see _plugin_scope below.
        p_tools, p_route = plugins_host.plugin_tools(mode, self._brain_root())
```

And add a helper to the same class:

```python
    def _brain_root(self):
        """The brain being worked in, inferred from cwd. Returns None if cwd is not a valid brain
        (e.g. chat running with cwd = the project folder) - then the plugin handles its own fallback as before."""
        try:
            root = Path(self.cwd)
            return str(root) if (root / "Javis").is_dir() else None
        except Exception:
            return None
```

Make sure `from pathlib import Path` is at the top of the file (`grep -n "^from pathlib\|^import pathlib" server/claude_sdk_engine.py`); add it if missing.

- [ ] **Step 5: Separate the two meanings of the parameter in `plugins_host`**

Read `plugin_tools` and `_iter_plugin_dirs` (`plugins_host.py:129-140`). `_iter_plugin_dirs(vault_root)` uses `vault_root` to decide whether to load `vault_plugins_dir(vault_root)`. If Step 4 now passes the real vault, the vault's **own plugins** would start loading for the SDK engine - that is a **behavior change outside scope** and runs into the `JAVIS_ENABLE_USER_PLUGINS` gate.

So add a separate parameter to `plugin_tools`:

```python
def plugin_tools(mode, vault_root=None, *, scope_vault=True):
    """mode: the permission level of this turn. vault_root: the brain, so the plugin's ctx knows where it is.
    scope_vault=False: do NOT load the vault's own plugins (only bundled + global) but the ctx STILL
    sees vault_root. Two meanings are separated because before, a single None carried both, leaving the ctx blind to the brain."""
```

**The real wiring (verified, do not guess):** `plugin_tools` (`:415`) calls `_load_all(vault_root)`; `_load_all` is what calls `_iter_plugin_dirs(vault_root)` (`:129`) and builds `PluginContext(..., vault_root=vault_root)`. So `scope_vault` must pass through BOTH: `plugin_tools(..., scope_vault=...)` → `_load_all(vault_root, scope_vault=...)` → `_iter_plugin_dirs(vault_root if scope_vault else None)`, while `PluginContext` still receives the REAL `vault_root`.

Only `_iter_plugin_dirs` may receive `None`; `PluginContext` may not. That is exactly where the two meanings are separated.

**Cache:** `_load_all` caches by `vault_root` (`plugins_host.py:63`). Add `scope_vault` to the cache key, otherwise two runs with the same vault but different scope would use each other's cache. Read `:63-70` to see how the key is built and add it to match.

Then in `claude_sdk_engine._plugins_server` call:

```python
        p_tools, p_route = plugins_host.plugin_tools(mode, self._brain_root(), scope_vault=False)
```

- [ ] **Step 6: Add asserts for the new behavior**

Add to `server/test_plugin_vault.py` before the `if _fails:` block:

```python
# ---- 4. scope_vault=False: ctx STILL sees the vault but does NOT load the vault's own plugins ----
import inspect  # noqa: E402
sig = inspect.signature(plugins_host.plugin_tools)
check("plugin_tools: has a scope_vault parameter", "scope_vault" in sig.parameters)
check("plugin_tools: scope_vault defaults to True (keeps old behavior for the hub)",
      sig.parameters["scope_vault"].default is True)

import claude_sdk_engine  # noqa: E402
# The REAL class is named ClaudeSDK (claude_sdk_engine.py:124), NOT ClaudeSDKEngine.
check("SDK: has the _brain_root helper", hasattr(claude_sdk_engine.ClaudeSDK, "_brain_root"))

src_sdk = (Path(__file__).parent / "claude_sdk_engine.py").read_text(encoding="utf-8")
check("SDK: no longer passes a blind None into plugin_tools",
      "plugin_tools(mode, None)" not in src_sdk)
check("SDK: passes the real brain + scope_vault=False",
      "scope_vault=False" in src_sdk)
```

**Class name verified:** `ClaudeSDK` (`claude_sdk_engine.py:124`). Not `ClaudeSDKEngine`.

- [ ] **Step 7: Run the test**

Run: `cd server && ../.venv/Scripts/python.exe test_plugin_vault.py`

Expected: everything PASSES.

- [ ] **Step 8: Run regressions on the tests that touch plugins/engine**

Run: `cd server && for f in test_plugins_host.py test_sdk_engine.py test_image_gen.py test_loop_ambient.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: all 4 print `OK - ...`. If `test_plugins_host.py` goes red because of the signature change, fix the TEST to match the new signature (add `scope_vault`), do not drop the parameter.

- [ ] **Step 9: Commit**

```bash
git add server/claude_sdk_engine.py server/plugins_host.py server/test_plugin_vault.py
git commit -m "fix(plugins): ctx sees the right brain - before, every plugin called from Claude Code was blind

_plugins_server passed plugin_tools(mode, None), so PluginContext.vault_root
(plugins_host.py:218) = None for EVERY plugin called from Claude Code. image-chatgpt
passes cctx.vault_root down to image_gen._resolve_vault (image_gen.py:95-98), which
sees it empty and falls back to brains/Brain Default -> working in another brain but
the image is saved to Brain Default, and the attachments/ link points at a file that
is not there. A silent bug, nobody reported it.

One None was carrying TWO meanings: 'do not load the vault's own plugins' (deliberate)
and 'the ctx sees no vault' (the bug). Separated with the scope_vault parameter.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Plugin `javis-schedule` - tool to create/list/cancel jobs

**Files:**
- Create: `system/plugins/javis-schedule/plugin.yaml`
- Create: `system/plugins/javis-schedule/plugin.py`
- Test: `server/test_javis_schedule.py` (new)

**Interfaces:**
- Consumes: `ctx.vault_root` sees the right brain when called from **chat** (Task 1, mechanism: `_apply_mcp(cli, brain=...)` → `cli.javis_vault` → `plugin_tools(mode, self.javis_vault, scope_vault=False)`). **Note:** the background loop calls `apply_mcp` WITHOUT passing brain, so `javis_vault=None` there - but suggest/auto loops are gated by design and get no plugins, while `mode: full` loops do. Therefore the handler MUST report a clear error when `ctx.vault_root` is empty and MUST NOT fall back to Brain Default under any circumstances. The `reminders` HTTP API `POST /reminders` (`server/reminders.py:507`, localhost-exempt via `_AUTH_LOCAL_EXACT` at `main.py:70`), `GET /reminders`, `POST /reminders/cancel`.
- Produces: tool `javis_schedule(op, ...)`. No later task depends on it.

**Wiring decision, read carefully before coding:**

The plugin **does NOT import `main.py`** (import cycle, and the 5000-line `main.py` has side effects at import time). The two stores are reached by two different routes, because the auth rules differ:

- **Reminders** → call HTTP `POST /reminders` on `127.0.0.1`. This route is DELIBERATELY login-exempt for localhost (`main.py:70`, `_AUTH_LOCAL_EXACT = ("/telegram/send-file", "/reminders")`), the very route `reminders.py:17` describes agents already using with `curl`. The tool just wraps it properly.
- **Loops** → **write the `.md` file directly** to `<vault_root>/Javis/loops/<slug>.md`. Do NOT use `POST /loops` because that route **requires login** (it is not in `_AUTH_LOCAL_EXACT`), so a plugin cannot call it from localhost. Writing the file is the true nature of it: a loop IS a `.md` file (`self_improve.py:6`) and the scheduler reads the folder itself.

Server port: read from env `JAVIS_PORT` if present, default `7777`. Confirm with `grep -rn "7777\|JAVIS_PORT" server/main.py server/config.py | head`.

- [ ] **Step 1: Write the failing test**

Create `server/test_javis_schedule.py`:

```python
"""Test the javis_schedule tool (bundled plugin). Run by hand / CI:

    cd server && python test_javis_schedule.py

Background: before this tool, chat that wanted to create a recurring job had to TYPE the YAML frontmatter
into Javis/loops/<slug>.md itself, or shell out to curl POST /reminders (reminders.py:17). The tool wraps both
and routes automatically: reminder/cron/one-shot -> the reminders store; repeating + durable -> a .md file.

NO network: every test calls a pure function or writes a file in a temp folder.

Covers:
- _route_kind: classifies the schedule -> which store.
- _slugify_vn: Vietnamese name -> ascii slug, does not collide with an existing file.
- op=create repeating job -> writes the .md in the right place, frontmatter reads back, enabled=false.
- op=create reminder -> does NOT write a .md (must go through reminders).
- The tool registers with the right name + min_mode.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-schedtest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).parent.parent / "system" / "plugins" / "javis-schedule"))

import plugin as sched  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---- 1. Route: which schedule goes to which store ----
# (The Vietnamese schedule strings below are deliberate test input: "mỗi 2 tiếng" = "every 2 hours",
#  "30 phút nữa" = "in 30 minutes".)
check("route: '120m' -> loop (repeating, durable)", sched._route_kind("120m", False) == "loop")
check("route: 'mỗi 2 tiếng' -> loop", sched._route_kind("mỗi 2 tiếng", False) == "loop")
check("route: '0 7 * * *' -> reminder (cron, reminders already has it)",
      sched._route_kind("0 7 * * *", False) == "reminder")
check("route: '30 phút nữa' -> reminder (one-shot)", sched._route_kind("30 phút nữa", False) == "reminder")
check("route: notify_only forces reminder even for a repeating schedule",
      sched._route_kind("120m", True) == "reminder")

# ---- 2. Slug ----
# (Vietnamese input on purpose: the slug rule strips diacritics. "Đọc source mỗi 2 tiếng" = "Read source every 2 hours".)
check("slug: strips Vietnamese diacritics", sched._slugify_vn("Đọc source mỗi 2 tiếng") == "doc-source-moi-2-tieng")
check("slug: not empty when the name is all odd characters", sched._slugify_vn("!!!") != "")

# ---- 3. Create a repeating job -> write the .md ----
# (Vietnamese name and prompt on purpose: "Quét đơn mỗi 2 tiếng" = "Scan orders every 2 hours",
#  the prompt = "Each round, read today's order count through the POS MCP then write a draft.")
_vault = tempfile.mkdtemp(prefix="javis-vault-")
res = sched._create_loop_file(_vault, name="Quét đơn mỗi 2 tiếng",
                              prompt="Mỗi vòng đọc số đơn hôm nay qua MCP POS rồi ghi nháp.",
                              schedule="120m", owner_chat="123")
f = Path(_vault) / "Javis" / "loops" / "quet-don-moi-2-tieng.md"
check("loop: writes <vault>/Javis/loops/<slug>.md in the right place", f.is_file())
body = f.read_text(encoding="utf-8") if f.is_file() else ""
check("loop: frontmatter has type: loop", "type: loop" in body)
check("loop: DEFAULT enabled: false (CLAUDE.md safety rule)", "enabled: false" in body)
check("loop: DEFAULT mode: suggest (never sets full by itself)", "mode: suggest" in body)
check("loop: interval_min from '120m'", "interval_min: 120" in body)
check("loop: keeps owner_chat so the right person is notified", 'owner_chat: "123"' in body)
check("loop: the file body IS the prompt (self-contained, independent of the chat)", "MCP POS" in body)
check("loop: returns the path so the model knows where it was written", "quet-don-moi-2-tieng" in str(res))

# ---- 4. Do not overwrite an existing loop with a parallel ascii copy ----
# self_improve.py:273 takes the IDENTITY from the FILE NAME. A duplicate slug -> must report, not silently fork.
res2 = sched._create_loop_file(_vault, name="Quét đơn mỗi 2 tiếng", prompt="khác", schedule="60m")
# ("đã có" is the Vietnamese error text, "already exists", that the plugin returns.)
check("loop: duplicate slug -> clear error, no copy spawned",
      str(res2).startswith("ERROR:") or "đã có" in str(res2).lower())

# ---- 5. The tool registers correctly ----
_regs = []


class _FakeCtx:
    # data_dir is a @property on the real PluginContext (plugins_host.py:223) so it can NOT be assigned;
    # the fake ctx only needs what the handler actually reads.
    vault_root = _vault
    slug = "javis-schedule"

    def register_tool(self, **kw):
        _regs.append(kw)

    def register_hook(self, *a, **k):
        pass


sched.register(_FakeCtx())
check("register: exactly 1 tool", len(_regs) == 1)
check("register: name javis_schedule", _regs and _regs[0].get("name") == "javis_schedule")
check("register: min_mode=safe (creating a job is a WRITE, blocked in suggest)",
      _regs and _regs[0].get("min_mode") == "safe")
desc = (_regs[0].get("description") or "") if _regs else ""
check("register: the description says clearly WHEN to call", len(desc) > 60 and "op" in desc)
props = ((_regs[0].get("schema") or {}).get("properties") or {}) if _regs else {}
check("register: schema has op/name/schedule/prompt",
      {"op", "name", "schedule", "prompt"}.issubset(set(props)))


if _fails:
    print(f"\nFAIL - test_javis_schedule: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_javis_schedule: all pass")
```

- [ ] **Step 2: Run the test to confirm it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_javis_schedule.py`

Expected: `ModuleNotFoundError: No module named 'plugin'` (the plugin is not created yet).

- [ ] **Step 3: Create `plugin.yaml`**

Create `system/plugins/javis-schedule/plugin.yaml`:

```yaml
name: Schedule recurring jobs and reminders
slug: javis-schedule
version: 1.0.0
description: Create, list and cancel recurring jobs and reminders straight from chat. Picks the store itself - a repeating, durable job is written to Javis/loops/<slug>.md so it can be edited in Obsidian; a one-time reminder or a cron schedule goes into the reminders store (which already has 5-field cron). Replaces hand-typed YAML or curl.
author: Jarvis 007 (bundled)
enabled: true
min_mode: safe
tools:
  - javis_schedule
hooks: []
```

- [ ] **Step 4: Write `plugin.py`**

Create `system/plugins/javis-schedule/plugin.py`. Read `system/plugins/image-chatgpt/plugin.py` first to follow the exact mold of `register(ctx)` / `ctx.register_tool` / returning `"ERROR: ..."` on failure.

Required content (write it in full; this is a mandatory behavior description, not a suggestion):

1. `_slugify_vn(name) -> str`: strip Vietnamese diacritics (use `unicodedata.normalize("NFD", s)` then filter `category != "Mn"`), lowercase, replace every character that is not `[a-z0-9]` with `-`, collapse repeated `-`, trim both ends. If empty return `"viec"` (Vietnamese for "job").
2. `_route_kind(schedule, notify_only) -> "loop" | "reminder"`:
   - `notify_only` True → `"reminder"`.
   - A string matching 5-field cron (5 tokens separated by whitespace, or starting with `@`) → `"reminder"`.
   - A string that indicates a repeating PERIOD (`"120m"`, `"90 phút"`, `"mỗi 2 tiếng"`, `"2h"`) → `"loop"`. (The Vietnamese units are deliberate input: "phút" = minutes, "mỗi 2 tiếng" = every 2 hours.)
   - Everything else (a one-time point: `"30 phút nữa"` = "in 30 minutes", `"9h sáng mai"` = "9am tomorrow", ISO) → `"reminder"`.
3. `_interval_min(schedule) -> int`: extract the minutes from a period string. `"2 tiếng"`/`"2h"` → 120. Minimum **5** (matching the hard floor at `self_improve.py:257`).
4. `_create_loop_file(vault_root, name, prompt, schedule, owner_chat="") -> str`: write `<vault_root>/Javis/loops/<slug>.md`. **File already exists → return `"ERROR: đã có việc tên ... , sửa nó thay vì tạo bản sao"`** (Vietnamese for "ERROR: a job named ... already exists, edit it instead of creating a copy"), do NOT overwrite (`self_improve.py:321-327` takes the identity from the file name; spawning a parallel ascii copy means the original KEEPS RUNNING). Frontmatter in the CLAUDE.md mold:

```
---
type: loop
name: <name>
slug: <slug>
enabled: false
mode: suggest
interval_min: <n>
owner_chat: "<chat_id>"
updated: <YYYY-MM-DD>
---
<prompt>
```

   `enabled: false` and `mode: suggest` are **MANDATORY**, with no parameter to change them. The CLAUDE.md rule: "A loop created from chat ALWAYS defaults to `mode: suggest` + `enabled: false`. NEVER set `mode: full` yourself."
5. `_post_reminder(payload) -> str`: `httpx.post(f"http://127.0.0.1:{_port()}/reminders", json=payload, timeout=10)`. `_port()` reads env `JAVIS_PORT`, default `7777`.
6. Handler `javis_schedule(args, cctx)`:
   - `op="create"`: needs `name` + `prompt` + `schedule`. Route with `_route_kind`. `"loop"` → `_create_loop_file(cctx.vault_root, ...)`; `"reminder"` → `_post_reminder`. If `cctx.vault_root` is empty → return `"ERROR: không xác định được brain đang làm việc"` (Vietnamese for "ERROR: cannot determine which brain is being worked in"; do NOT fall back to Brain Default - that is exactly the Task 1 bug just fixed).
   - `op="list"`: return the **union of BOTH stores** - read `<vault>/Javis/loops/*.md` (name + enabled + interval) and `GET /reminders` (pending). This is the easiest mistake to make: looking at only one store makes the model report "there are no jobs" while the jobs sit in the other store.
   - `op="cancel"`: an `id` starting with a loop slug → delete the `.md` file; otherwise → `POST /reminders/cancel`.
   - Return a human-readable STRING (the model will read it back), `"ERROR: ..."` on failure.
7. `register(ctx)` calls `ctx.register_tool(...)`. REAL signature, verified (`plugins_host.py:~230`):

```python
def register_tool(self, name: str, description: str, handler: Callable,
                  schema: Optional[dict] = None, parameters: Optional[dict] = None,
                  min_mode: str = "readonly", check_fn: Optional[Callable] = None,
                  emoji: str = "") -> None
```

   `handler(args: dict, ctx: PluginContext) -> str` (sync or async). The tool name must match `a-z0-9_` or it **raises ValueError**. Use `min_mode="safe"`, a schema with `op` (enum create|list|cancel), `name`, `schedule`, `prompt`, `notify_only`, `id`. The tool description must say clearly when to call it, with examples of valid schedules.

- [ ] **Step 5: Run the test until it PASSES**

Run: `cd server && ../.venv/Scripts/python.exe test_javis_schedule.py`

Expected: everything PASSES. If any assert is wrong because the `ctx.register_tool` signature differs from the real one, read `plugins_host.py:209-260` to get the real signature and fix the TEST.

- [ ] **Step 6: Confirm the plugin really loads (not just a passing unit test)**

Run:

```bash
cd server && ../.venv/Scripts/python.exe -c "
import os, sys, tempfile
os.environ.setdefault('JAVIS_STATE_DIR', tempfile.mkdtemp())
sys.path.insert(0, '.')
import plugins_host
d = plugins_host.describe(None)
p = [x for x in d if x['slug'] == 'javis-schedule']
print('description:', p)
t, r = plugins_host.plugin_tools('safe', None)
print('tool safe:', [x['fn'] for x in t])
t2, _ = plugins_host.plugin_tools('readonly', None)
print('tool readonly (must NOT include javis_schedule):', [x['fn'] for x in t2])
"
```

Expected: `javis-schedule` appears in `describe`, `loaded: True`, `error` empty. `javis_schedule` IS in the list for mode `safe` and is **NOT** in mode `readonly` (min_mode blocks it). If `loaded: False`, read the `error` field to see where the import broke.

- [ ] **Step 7: Run regressions**

Run: `cd server && for f in test_plugins_host.py test_plugin_vault.py test_javis_schedule.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: all 3 print `OK - ...`.

- [ ] **Step 8: Commit**

```bash
git add system/plugins/javis-schedule/ server/test_javis_schedule.py
git commit -m "feat(schedule): javis_schedule tool - chat can set recurring jobs, no more hand-typed YAML

Before: chat that wanted to create a recurring job had to TYPE the YAML frontmatter
into Javis/loops/<slug>.md itself, or shell out to curl POST /reminders (reminders.py:17
says exactly that). The second path also contradicts itself: suggest/auto loops are
blocked from Bash (self_improve.py:112), so a loop cannot set a reminder for itself.

It is a bundled PLUGIN, not a hub tool, because the hub does not reach every
engine: _builtin_tools early-returns when vault_root=None (mcp_hub.py:213), which is
how the HTTP path always calls it, and claude_config_path returns None when there is
no MCP connector yet. A plugin goes through the IN-PROCESS MCP server
(claude_sdk_engine.py:162-186) and hits neither barrier.

Two stores are routed: repeating + durable -> .md (editable in Obsidian); reminder/cron/one-shot
-> the reminders store (which already has 5-field cron). op=list must look at BOTH stores.

Safety: a loop created via chat is ALWAYS enabled:false + mode:suggest, with no parameter
to change that (CLAUDE.md rule). A duplicate slug reports an error and does not let a parallel
copy exist (self_improve.py:321-327: identity comes from the FILE NAME).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Teach Jarvis 007 to use the tool + docs

**Files:**
- Modify: `CLAUDE.md` (section "Orchestration", levels 2/6/7)
- Modify: `CHANGELOG.md`, `VERSION`

**Interfaces:**
- Consumes: tool `javis_schedule` (Task 2).
- Produces: nothing.

**Why this is needed:** if the tool exists but the system prompt still teaches "write the file `Javis/loops/<slug>.md`", the model will keep typing YAML by hand. The tool description competes directly with the instructions in the prompt, and the prompt usually wins.

- [ ] **Step 1: Read the current Orchestration section**

Run: `cd /d/Project/Javis-OS && sed -n '18,40p' CLAUDE.md`

Write down levels 2 (Kanban task), 6 (Reminder) and 7 (Loop) verbatim.

- [ ] **Step 2: Edit CLAUDE.md**

Level 6 currently (after phase 1): `6. **Create a Reminder** - a reminder / job at a FIXED TIME → `POST /reminders` (see the Work page).`

Change it to:

```markdown
6. **Create a Reminder** - a reminder / job at a FIXED TIME → call tool `javis_schedule` (op=create, notify_only=true if it only reminds). Review it on the Scheduled page.
```

Level 7 currently says a loop writes the file `Javis/loops/<slug>.md`. Add one sentence at the TOP of the loop format section:

```markdown
**Prefer calling tool `javis_schedule` (op=create) over writing the file yourself** - the tool sets the right slug, the right frontmatter, blocks duplicate names, and picks the store itself (repeating job → .md file; reminder/cron → the reminder store). Only hand-write a file when you need an advanced field the tool does not accept yet (quiet_hours, max_runs_per_day, workspace, ambient_mcp).
```

**Keep** the description of the loop file format below as it is: it is still correct, and both users and the model still need it to EDIT an existing loop.

- [ ] **Step 3: Check that nothing still teaches curl**

Run: `cd /d/Project/Javis-OS && grep -n "curl\|POST /reminders\|POST /kanban" CLAUDE.md`

For each hit: if it teaches the model to call HTTP itself to set a schedule/reminder, change it to call `javis_schedule`. If it is about something else (e.g. a Kanban task) leave it alone - this plan does not touch Kanban.

- [ ] **Step 4: Bump VERSION + CHANGELOG**

Read `VERSION`, bump the patch. Read the `## [0.9.69]` block in `CHANGELOG.md` to match the voice: the project owner writes the CHANGELOG **explaining the root cause with file:line evidence**, not just listing. Add a new block at the top, groups `### Added` and `### Fixed`, covering:
- Tool `javis_schedule`: before, chat had to type YAML by hand or use curl; why a plugin and not the hub (two barriers: `mcp_hub.py:213` early-return, `claude_config_path` returns None when there is no connector yet).
- The plugin brain-blindness bug (Task 1): `javis_generate_image` images called from Claude Code were always saved into Brain Default.

- [ ] **Step 5: Run the whole test suite like CI**

Run: `cd server && for f in test_*.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: every file prints `OK - ...`.

Run: `cd /d/Project/Javis-OS && .venv/Scripts/python.exe -m compileall -q server system/plugins`

Expected: no output.

- [ ] **Step 6: Commit + push**

```bash
git add CLAUDE.md CHANGELOG.md VERSION
git commit -m "docs(schedule): teach Jarvis 007 to call javis_schedule instead of typing YAML by hand

The tool exists but the system prompt still teaches 'write the file Javis/loops/<slug>.md', so the
model still types YAML by hand: the tool description competes directly with the
instructions in the prompt, and the prompt usually wins.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

---

## Visual check (MANDATORY before calling it done)

Phase 1 taught an expensive lesson: **every static check was green and we still nearly shipped a broken build** (the `?v=` cache-bust convention was not in the plan, no test caught it, only opening the browser exposed it). Tasks 1 and 2 here touch the REAL engine tool path, and no unit test can prove that Claude Code actually SEES and can CALL the tool.

So after Task 3, do this by hand:

1. Restart the server (new code), open the dashboard, log in.
2. Chat: *"create a job for me every 2 hours that reads new sources and proposes wiki notes"*. Expected: Jarvis 007 **calls the tool** (does not type YAML), reports it was created, and `brains/<brain in use>/Javis/loops/doc-source-*.md` appears with `enabled: false`.
3. Check the file lands in the **brain that is OPEN**, not Brain Default. This is the main point Task 1 fixes.
4. Chat: *"remind me in 30 minutes to call the customer"*. Expected: it goes into the reminders store (no .md file is spawned), and shows in the "Pending reminders" block on the Scheduled page.
5. Chat: *"which recurring jobs do I have right now"*. Expected: `op=list` lists **both** things just created.
6. Open the Scheduled page: see the new loop (switched off) + the pending reminder.
7. Clean up: switch off/delete the test loop, cancel the test reminder.

## Out of scope for this plan

- **Connector scoping + `allow_real_actions`** (dropping the 3-notch dial). A separate plan, the highest risk because it means editing the hub - a hard layer, and a mistake breaks the barrier for EVERY engine.
- **Cron on loops** (a single `schedule` field + jitter). **Deliberately deferred (YAGNI)**: `reminders.py` already has full 5-field cron (`cron_util.py`, next run computed at `reminders.py:364`) and mode `task` runs a real engine (`reminders.py:426`), so "run the report at 7am" can already be done. Only build it when a DURABLE job (a .md file edited in Obsidian) really needs to run on a clock - reminders are ephemeral and run hard-limited to `safe_tools`.
- The fate of the 5 legacy shim routes `/loop/*` (`self_improve.py:988-1036`).
- Kanban task (`op=create` does not route to Kanban - Kanban is a state machine, with no clock).
