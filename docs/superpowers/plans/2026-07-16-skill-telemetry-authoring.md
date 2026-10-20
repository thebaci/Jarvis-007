# Skill telemetry + skill authoring standard (A+B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the description truncation bug that is silently breaking routing for every skill, and let Jarvis 007 know which skills are actually used.

**Architecture:** Gather the three scattered description cut points into a single constant in `skill_router.py`, then enforce that constant at every WRITE point (API, learn). Add a telemetry sidecar `Javis/skill-usage.json` owned by `skill_usage.py`, bumped at a single choke point, the `_skill` handler in `mcp_hub.py`. No state machine, no background job: `stale` is a pure function computed at read time.

**Tech Stack:** Python 3.12, FastAPI, PyYAML, stdlib (`hashlib`, `shutil`, `tempfile`). No pytest. Vanilla JS for the dashboard.

## Global Constraints

- **Language:** every comment, docstring and user-facing error message is written in English.
- **NEVER use the em dash character (U+2014)** in any file. Use "-".
- **Do NOT use pytest.** Tests are plain scripts that run directly, using `check(name, cond)` + `_fails` + `sys.exit(1)`. Standard template: `server/test_loop_ambient.py:23-30` and `:117-120`.
- **Test command:** `cd server && ../.venv/Scripts/python.exe test_<name>.py`. The venv is at the repo ROOT, NOT `server/.venv`.
- **New tests must be named `server/test_*.py`** so the CI glob (`.github/workflows/ci.yml:29-39`) picks them up. Put anywhere else and CI skips them.
- **Test preamble, order is load-bearing** (env BEFORE import, because the module reads `JAVIS_STATE_DIR` at import time):
  ```python
  os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-<x>test-"))
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import <module>  # noqa: E402
  ```
- `SKILL_DESC_MAX = 150`, `SKILL_LIST_MAX = 20`, `SKILL_STALE_AFTER_DAYS = 30`.
- **`skill_router.py` is READ-ONLY** (contract in the docstring at line 16). Only add constants and PURE functions. Every write operation belongs to `system_sync.py`.
- **`use_count` is a one-way positive signal.** `use=0` must NEVER be read as useless, and a skill is never auto-disabled/archived.
- Full spec: `docs/superpowers/specs/2026-07-16-skill-telemetry-authoring-design.md`.

---

## File Structure

**Create:**
- `server/skill_usage.py` - telemetry sidecar. Owns reading/writing `<brain>/Javis/skill-usage.json`, `SKILL_STALE_AFTER_DAYS`, and the `is_stale` function. Does NOT import `main`.
- `server/test_skill_caps.py` - description cap, validator, system skill lint.
- `server/test_skill_usage.py` - the sidecar.
- `server/test_mirror_tree.py` - recursive mirror.

**Modify:**
- `server/skill_router.py` - add constants + `validate_description`; `_meta_of:90` uses the shared cap.
- `server/main.py` - `_skill_router_block:3464,3470,3471,3473,3474`; `POST /skills:2213-2238`; `GET /skills:2151`.
- `server/mcp_hub.py` - `listing:256-258`; `_skill:237-245`.
- `server/learn.py` - prompt schema `:356-359`; authoring standard in `_build_prompt`; enforce the cap in `_promote_sync:544-568`.
- `server/system_sync.py` - `mirror_skills:235-264` becomes recursive + tree hash.
- `server/git_brain.py` - `_GITIGNORE:62-72`; `_BACKUP_SKIP_SUBSTR:267-268`; `ensure_git_repo:75-99`.
- `dashboard/studio.js` - `renderSkillList:463-477`.
- `CLAUDE.md:249` - description template.
- `.claude/skills/{html-to-webcake,ingest-source,javis-builder,lint-wiki,query-wiki}/SKILL.md`.

---

### Task 1: Constants + validator in skill_router

**Files:**
- Modify: `server/skill_router.py:21-31` (import + constants), `:90` (the `[:140]` fallback)
- Test: `server/test_skill_caps.py` (create)

**Interfaces:**
- Produces: `skill_router.SKILL_DESC_MAX: int`, `skill_router.SKILL_LIST_MAX: int`, `skill_router.validate_description(desc: str) -> Optional[str]` (None = valid, string = rejection reason in English). Used by Tasks 2, 4, 5.

- [ ] **Step 1: Write the failing test**

Create `server/test_skill_caps.py`:

```python
"""Test the skill description cap + router constants. Run by hand / CI:

    cd server && ../.venv/Scripts/python.exe test_skill_caps.py

No pytest needed, no network.
Covers: the constants SKILL_DESC_MAX/SKILL_LIST_MAX, validate_description (too long,
boilerplate, valid, empty), the _meta_of fallback sharing the cap.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-capstest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skill_router  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---- constants ----
check("SKILL_DESC_MAX = 150", getattr(skill_router, "SKILL_DESC_MAX", None) == 150)
check("SKILL_LIST_MAX = 20", getattr(skill_router, "SKILL_LIST_MAX", None) == 20)

# ---- validate_description ----
v = skill_router.validate_description
check("valid description -> None", v("Turn HTML into a Webcake .pke file.") is None)
check("empty description -> None (the body fallback handles it)", v("") is None)
check("None description -> None", v(None) is None)

long_desc = "x" * 151
r = v(long_desc)
check("151-character description -> rejected", isinstance(r, str))
check("rejection reason states the real character count", r is not None and "151" in r)
check("rejection reason states the cap", r is not None and "150" in r)
check("exactly 150-character description -> passes", v("x" * 150) is None)

# The boilerplate lexicon is Vietnamese on purpose (it matches how Vietnamese skills open):
# "Kích hoạt khi" = "Activates when", "Sử dụng skill này khi" = "Use this skill when",
# "Dùng khi cần" = "Use when you need" (a legitimate short opening).
check("catches boilerplate 'Kích hoạt khi' (Activates when)",
      isinstance(v("Kích hoạt khi người dùng muốn tạo ảnh"), str))
check("catches boilerplate 'Sử dụng skill này khi' (Use this skill when)",
      isinstance(v("Sử dụng skill này khi cần vẽ"), str))
check("catches English boilerplate 'Activate when'",
      isinstance(v("Activate when the user wants to draw"), str))
check("does NOT catch 'Dùng khi cần' (Use when you need; a valid, short opening)",
      v("Dùng khi cần tạo ảnh minh hoạ phong cách flat 2D") is None)

# ---- _meta_of fallback shares the cap ----
tmp = Path(tempfile.mkdtemp(prefix="javis-capsbrain-"))
d = tmp / "skills" / "no-desc"
d.mkdir(parents=True)
(d / "SKILL.md").write_text("---\nname: No description\n---\n" + ("y" * 400) + "\n",
                            encoding="utf-8")
metas = skill_router.list_enabled_meta(tmp)
got = next((m for m in metas if m["slug"] == "no-desc"), None)
check("_meta_of fallback returns the skill", got is not None)
check("fallback cuts at SKILL_DESC_MAX, not 140",
      got is not None and len(got["description"]) == skill_router.SKILL_DESC_MAX)

if _fails:
    print(f"\nFAIL - test_skill_caps: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_skill_caps: all pass")
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL. `SKILL_DESC_MAX = 150` fails (the constant does not exist yet, `getattr` returns None), and `validate_description` raises `AttributeError: module 'skill_router' has no attribute 'validate_description'`.

- [ ] **Step 3: Add the constants + validator**

In `server/skill_router.py`, after line 31 (`_READ_BASES = ...`), BEFORE the two blank lines leading to `def skills_base`, insert:

```python

# Cap on description length when injected into the router (system prompt + the javis_use_skill
# tool description). Longer is CUT SILENTLY -> the tail never reaches the engine, and the skill
# cannot be routed. So this cap is ENFORCED at every WRITE point (POST /skills, learn.py), not
# just truncated at display time. Full trigger examples belong in the '## When to use' section in
# the body, which is never cut.
SKILL_DESC_MAX = 150

# Maximum number of skills listed in the router. More than this -> point to Javis/index.md.
SKILL_LIST_MAX = 20

# Filler opening phrases: every skill opens identically, so they burn the character budget
# without telling one skill from another. Banned at write time. The lexicon is Vietnamese on
# purpose (it matches how Vietnamese skills open): "kích hoạt khi" = "activates when",
# "sử dụng skill này khi" / "dùng skill này khi" = "use this skill when",
# "skill này dùng / được dùng" = "this skill is used".
_DESC_BOILERPLATE_RE = re.compile(
    r"^\s*(kích\s+hoạt\s+khi"
    r"|sử\s+dụng\s+skill\s+này\s+khi"
    r"|dùng\s+skill\s+này\s+khi"
    r"|skill\s+này\s+(dùng|được\s+dùng)"
    r"|use\s+this\s+skill\s+when"
    r"|activate\s+when)",
    re.I,
)


def validate_description(desc) -> Optional[str]:
    """None = valid. A string = rejection reason (English, shown straight to the user).
    A PURE function (no I/O) so it still honors the module's read-only contract."""
    d = (desc or "").strip()
    if not d:
        return None    # empty is valid: POST /skills has a body fallback
    if len(d) > SKILL_DESC_MAX:
        return (f"description is {len(d)} characters, over the {SKILL_DESC_MAX} limit. The router "
                f"cuts at exactly {SKILL_DESC_MAX}, so the rest is LOST SILENTLY and the skill "
                "cannot be routed. Move trigger examples into a '## When to use' section in the "
                "body.")
    if _DESC_BOILERPLATE_RE.match(d):
        return ("description opens with filler (e.g. 'Activates when ...'). Every skill opens "
                "that way, so it burns the budget without telling skills apart. State the "
                "capability directly, e.g. 'Turn HTML into a Webcake .pke file.'")
    return None
```

- [ ] **Step 4: Make the `[:140]` fallback share the cap**

In `server/skill_router.py:90`, change:

```python
    desc = meta.get("description", "") or (body.split("\n")[0][:140] if body else "")
```

to:

```python
    desc = meta.get("description", "") or (body.split("\n")[0][:SKILL_DESC_MAX] if body else "")
```

- [ ] **Step 5: Update the docstring so it stops lying**

In `server/skill_router.py`, after lines 16-17 (the "Every function here ONLY READS..." paragraph), add one line:

```
This module also owns the DISPLAY CAPS (SKILL_DESC_MAX / SKILL_LIST_MAX) - previously each place
cut its own way (60 in the hub, 100 in the system prompt, 140 in the fallback) so whoever wrote a
skill did not know which ruler they were being measured against.
```

- [ ] **Step 6: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS, prints `OK - test_skill_caps: all pass`.

- [ ] **Step 7: Commit**

```bash
git add server/skill_router.py server/test_skill_caps.py
git commit -m "feat(skill): mot thuoc do duy nhat cho description (SKILL_DESC_MAX=150)"
```

---

### Task 2: main.py and mcp_hub share the constants

**Files:**
- Modify: `server/main.py:3464` (docstring), `:3470`, `:3471`, `:3473`, `:3474`
- Modify: `server/mcp_hub.py:256`, `:257`, `:258`
- Test: `server/test_skill_caps.py` (add to the Task 1 file)

**Interfaces:**
- Consumes: `skill_router.SKILL_DESC_MAX`, `skill_router.SKILL_LIST_MAX` (Task 1).

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_caps.py`, BEFORE the `if _fails:` block at the end:

```python
# ---- no scattered cut constants remain (guards against a "second ruler" growing back) ----
_SRC = Path(os.path.dirname(os.path.abspath(__file__)))


def _region(path, start_marker, end_marker):
    """Take the code between two markers so we only inspect the router render region."""
    text = (_SRC / path).read_text(encoding="utf-8")
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j]


hub = _region("mcp_hub.py", "metas = skill_router.list_enabled_meta(vault_root)",
              'add("javis_use_skill"')
check("mcp_hub no longer has the literal [:60]", "[:60]" not in hub)
check("mcp_hub no longer has the literal 20", "20" not in hub)
check("mcp_hub uses SKILL_DESC_MAX", "SKILL_DESC_MAX" in hub)
check("mcp_hub uses SKILL_LIST_MAX", "SKILL_LIST_MAX" in hub)

blk = _region("main.py", "def _skill_router_block", "@app.get(\"/javis/index\")")
check("main no longer has the literal [:100]", "[:100]" not in blk)
check("main no longer has the literal 15", "15" not in blk)
check("main uses SKILL_DESC_MAX", "SKILL_DESC_MAX" in blk)
check("main uses SKILL_LIST_MAX", "SKILL_LIST_MAX" in blk)
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL with 6 failures: `mcp_hub no longer has the literal [:60]`, `mcp_hub no longer has the literal 20`, `mcp_hub uses SKILL_DESC_MAX`, `mcp_hub uses SKILL_LIST_MAX`, `main no longer has the literal [:100]`, `main no longer has the literal 15`.

- [ ] **Step 3: Fix mcp_hub**

In `server/mcp_hub.py`, change the block at lines 254-258 from:

```python
    # Tool description = a miniature router: list slug + short description so the engine knows WHEN to call which skill.
    metas = skill_router.list_enabled_meta(vault_root)
    listing = "; ".join(f"{s['slug']}: {(s['description'] or '')[:60]}" for s in metas[:20])
    if len(metas) > 20:
        listing += f"; …(+{len(metas) - 20} more skills)"
```

to:

```python
    # Tool description = a miniature router: list slug + short description so the engine knows WHEN to call which skill.
    # The cap comes from skill_router (SHARED with the system prompt) - previously the hub cut at
    # 60 and the system prompt at 100, so whoever wrote a skill did not know which ruler applied.
    metas = skill_router.list_enabled_meta(vault_root)
    _cap = skill_router.SKILL_LIST_MAX
    listing = "; ".join(f"{s['slug']}: {(s['description'] or '')[:skill_router.SKILL_DESC_MAX]}"
                        for s in metas[:_cap])
    if len(metas) > _cap:
        listing += f"; …(+{len(metas) - _cap} more skills)"
```

- [ ] **Step 4: Fix main.py**

In `server/main.py`, change line 3464 (the last line of the `_skill_router_block` docstring) from:

```python
    Cap 15 skills so the context does not bloat (more than that → point to Javis/index.md)."""
```

to:

```python
    Cap skill_router.SKILL_LIST_MAX so the context does not bloat (more than that → point to Javis/index.md)."""
```

Change the block at lines 3470-3474 from:

```python
    for s in metas[:15]:
        desc = (s.get("description") or "").replace("\n", " ")[:100]
        lines.append(f"- {s['slug']} ({s['name']}): {desc}")
    if len(metas) > 15:
        lines.append(f"…(+{len(metas) - 15} more skills - see `Javis/index.md`)")
```

to:

```python
    cap = skill_router.SKILL_LIST_MAX
    for s in metas[:cap]:
        desc = (s.get("description") or "").replace("\n", " ")[:skill_router.SKILL_DESC_MAX]
        lines.append(f"- {s['slug']} ({s['name']}): {desc}")
    if len(metas) > cap:
        lines.append(f"…(+{len(metas) - cap} more skills - see `Javis/index.md`)")
```

- [ ] **Step 5: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/mcp_hub.py server/test_skill_caps.py
git commit -m "fix(skill): gom 3 diem cat description ve mot hang so chung"
```

---

### Task 3: CI lint + rewrite the 5 system descriptions

**Files:**
- Test: `server/test_skill_caps.py` (add the lint part)
- Modify: `.claude/skills/html-to-webcake/SKILL.md`, `.claude/skills/javis-builder/SKILL.md`, `.claude/skills/ingest-source/SKILL.md`, `.claude/skills/query-wiki/SKILL.md`, `.claude/skills/lint-wiki/SKILL.md`

**Interfaces:**
- Consumes: `skill_router.validate_description` (Task 1), `system_sync.SYSTEM_SKILLS_DIR` (`system_sync.py:52`).

**Note:** do NOT touch `brains/Brain Default/skills/tao-anh-minh-hoa-2d/SKILL.md`. It is 139 characters, already under the cap, and its opening "Dùng khi cần" ("Use when you need") is not the banned boilerplate.

- [ ] **Step 1: Write the failing lint**

Add `import system_sync  # noqa: E402` next to `import skill_router` at the top of `server/test_skill_caps.py`, then add this block BEFORE `if _fails:`:

```python
# ---- LINT: every SYSTEM skill must fit the cap + be free of boilerplate ----
# This is the guard against recurrence: the description truncation bug must not come back through
# a skill that ships with the app.
# Use system_sync.SYSTEM_SKILLS_DIR rather than hardcoding the path; and do NOT rglob the whole
# repo (it would hit the mirror copies in brains/ and .claude/worktrees/).
_sys_dir = system_sync.SYSTEM_SKILLS_DIR
check("found the system skills directory", _sys_dir.is_dir())
for _slug in sorted(system_sync.system_skill_slugs()):
    _f = _sys_dir / _slug / "SKILL.md"
    _meta, _ = skill_router.split_frontmatter(_f.read_text(encoding="utf-8"))
    _desc = _meta.get("description", "") or ""
    _err = skill_router.validate_description(_desc)
    check(f"system skill '{_slug}' has a valid description ({len(_desc)} characters)"
          + (f" -> {_err}" if _err else ""), _err is None)
```

- [ ] **Step 2: Run the lint, confirm it catches exactly 5 skills**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL, listing ALL 5 lines (not stopping at the first, since it uses `check` rather than a bare assert): `html-to-webcake` (376 characters), `javis-builder` (333), `ingest-source` (266), `query-wiki` (249), `lint-wiki` (213).

- [ ] **Step 3: Rewrite the descriptions + add a "When to use" section**

For EACH file below: replace the `description:` line in the frontmatter, then insert a `## When to use` section into the body right AFTER the H1 heading, holding exactly the trigger examples that were just taken out of the description. No information is lost, it only moves.

`.claude/skills/html-to-webcake/SKILL.md` (the Vietnamese trigger phrases stay verbatim below because they are example user input; each is glossed in English):
```yaml
description: Turn an HTML page into a .pke file the Webcake builder can open, keeping the original colours, type sizes, images and layout.
```
```markdown
## When to use

Activate when the user says things like: "chuyển file html này sang webcake" (convert this
html file to webcake), "đổi html thành pke" (turn html into pke), "tạo file webcake từ html"
(make a webcake file from html), "làm landing này thành file sửa được trên webcake" (turn this
landing page into a file editable on webcake), "html to webcake", "convert html sang webcake".

What the skill does: read the HTML, rebuild it as a page_source in the exact Webcake mold, then
export a .pke.
```

`.claude/skills/javis-builder/SKILL.md`:
```yaml
description: Create or edit a Jarvis 007 capability: agent, skill, workflow, loop, plugin. Ships file templates and the rules against duplicates.
```
```markdown
## When to use

Activate when the user says things like: "create an agent specialized in X", "add a skill for Y",
"build a research-then-write workflow", "create a loop that does Z every 2 hours", "write a
tool/plugin that computes ...", "make Jarvis 007 able to do ...".
```
NOTE: this `description` contains a colon. YAML will misread it as a mapping. You MUST wrap the whole value in double quotes:
```yaml
description: "Create or edit a Jarvis 007 capability: agent, skill, workflow, loop, plugin. Ships file templates and the rules against duplicates."
```

`.claude/skills/ingest-source/SKILL.md`:
```yaml
description: Digest one raw source into the Second Brain and distil it into wiki knowledge that compounds.
```
```markdown
## When to use

Activate when the user says things like: "digest this source", "process this article into the
wiki", "read this file and write down the knowledge", or when a new file is dropped into
`sources/`.

The skill follows the vault's 3 disciplines exactly.
```

`.claude/skills/query-wiki/SKILL.md` - remember the double quotes because of the colon:
```yaml
description: "Mine the knowledge held in the Second Brain: synthesis, comparison, hypotheses. Every answer carries citations."
```
```markdown
## When to use

Activate when the user asks about or mines the knowledge in the Second Brain, e.g. "synthesize
the frameworks about X", "compare A vs B vs C", "what does the wiki have on Y".

Five kinds of mining: synthesis, comparison, hypothesis, listing, visualization. Always answer
with citations and save results that are worth keeping.
```

`.claude/skills/lint-wiki/SKILL.md`:
```yaml
description: Audit the health of the Second Brain wiki and hand back a list of problems. Never mass-edits on its own.
```
```markdown
## When to use

Activate when the user says things like: "health check the wiki", "lint wiki", "is anything
wrong with the wiki", "audit the brain".
```

- [ ] **Step 4: Run the lint, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS. All 5 lines `system skill '<slug>' has a valid description` are `ok`.

- [ ] **Step 5: Verify YAML does not break because of the colon**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router, system_sync
for s in sorted(system_sync.system_skill_slugs()):
    f = system_sync.SYSTEM_SKILLS_DIR / s / 'SKILL.md'
    m, _ = skill_router.split_frontmatter(f.read_text(encoding='utf-8'))
    print(s, '|', type(m.get('description')).__name__, '|', (m.get('description') or '')[:50])
"
```
Expected: every line prints `str` (NOT `dict`). If `dict` shows up, a description with a colon has not been wrapped in double quotes.

- [ ] **Step 6: Commit**

```bash
git add server/test_skill_caps.py .claude/skills/
git commit -m "fix(skill): viet lai 5 description he thong cho lot tran 150 + lint CI chan tai phat"
```

---

### Task 4: javis-builder - fix the canonical path + embed the skill authoring standard

**Files:**
- Modify: `.claude/skills/javis-builder/SKILL.md:23-24`, `:38`, `:54`, insert after `:62`

**Interfaces:** none. This task is pure documentation, but it is the OTHER HALF of spec item B3 (the other half is the learn prompt in Task 7). Without it, skills created through chat remain shapeless.

**Depends on:** do AFTER Task 3 (Task 3 rewrote this very file's `description`).

`javis-builder` currently teaches writing skills into `.claude/skills/`, but that is the derived MIRROR copy. The canonical location is `skills/<slug>/SKILL.md` (see `skill_router.py:6` and `CLAUDE.md:245`). It is wrong in 3 places, and all three must be fixed or the file contradicts itself.

- [ ] **Step 1: Fix line 54**

Change:
```markdown
### Skill -> `.claude/skills/<slug>/SKILL.md`
```
to:
```markdown
### Skill -> `skills/<slug>/SKILL.md`
```
(flat canonical; Jarvis 007 mirrors it into `.claude/skills` on its own for Claude Code to load natively)

- [ ] **Step 2: Fix lines 23-24**

Change:
```markdown
3. **Check for duplicates.** BEFORE creating, read the matching folder (agents/ workflows/ .claude/skills/
   loops/). If something close already exists -> update the old one, do not spawn a copy.
```
to:
```markdown
3. **Check for duplicates.** BEFORE creating, read the matching folder (agents/ workflows/ skills/
   loops/). If something close already exists -> update the old one, do not spawn a copy.
```

- [ ] **Step 3: Fix line 38**

Change:
```markdown
skills: [slug-skill]      # [] if none assigned yet; only assign skills that already exist in .claude/skills
```
to:
```markdown
skills: [slug-skill]      # [] if none assigned yet; only assign skills that already exist in skills/
```

- [ ] **Step 4: Embed the SKILL AUTHORING STANDARD in javis-builder**

Spec item B3 requires the standard to exist in BOTH places that produce skills: the learn prompt (Task 7) and javis-builder (this task). Miss either one and skills created through chat still come out shapeless.

In `.claude/skills/javis-builder/SKILL.md`, right AFTER the Skill template block (which ends at line 62 with the closing ``` fence), insert:

```markdown
#### Skill authoring standard (mandatory, the server will BLOCK violations)

1. `description` is **AT MOST 150 characters**. The router cuts at exactly that point
   (`skill_router.SKILL_DESC_MAX`) in both the system prompt and the tool description, so
   anything longer has its tail LOST SILENTLY and the skill cannot be routed. After writing,
   COUNT, do not estimate. `POST /skills` returns 400 if it is over.
2. `description` states the capability DIRECTLY. Do NOT open with "Activate when...", "Use this
   skill when..." - every skill opens that way, so it burns 29 characters and distinguishes
   nothing. Good: `Turn HTML into a Webcake .pke file.` Bad: `Activate when the user wants to convert...`
3. If `description` contains a colon, the whole value must be wrapped in double quotes, or YAML
   reads it as a mapping.
4. Put the full trigger examples in the BODY, in the `## When to use` section - where nothing is
   cut and which is only read once the skill is loaded. The index is for FINDING, the body is for
   DOING.
5. Order of sections in the body: `## When to use` / `## Preparation` / `## How to run` /
   `## Procedure` / `## Pitfalls` / `## Verification`. Drop any section with no real content,
   do not invent filler.
6. Do NOT invent flags, paths or APIs you have not seen in the source. If you did not see it, do
   not write it.
7. Keep the body around 100 lines for a simple skill, 200 for a complex one. Longer than that,
   move the content down to `skills/<slug>/references/<topic>.md`, scripts down to
   `skills/<slug>/scripts/`, and point to them by relative path.
8. Do NOT write a router-style skill that only points to another skill.
```

- [ ] **Step 5: Verify no wrong references remain**

Run: `grep -n "\.claude/skills" .claude/skills/javis-builder/SKILL.md`
Expected: only lines that TALK ABOUT the mirror (if any), no line that tells you to WRITE there. An empty grep result also passes.

- [ ] **Step 6: Run the lint to make sure the frontmatter is not broken**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS. In particular the line `system skill 'javis-builder' has a valid description` must be `ok` - Task 3 rewrote this very file's description, and Step 4 here only adds to the BODY, so it must not push it back over the cap.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/javis-builder/SKILL.md
git commit -m "fix(docs): javis-builder tro dung canonical skills/ + nhung chuan viet skill"
```

---

### Task 5: CLAUDE.md stops teaching long descriptions

**Files:**
- Modify: `CLAUDE.md:249`, insert 1 more bullet after `:253`

**Interfaces:** none. Pure documentation.

- [ ] **Step 1: Fix the frontmatter template**

In `CLAUDE.md:249`, change:
```yaml
description: <SHORT description, decides WHEN the skill is activated - write the trigger clearly>
```
to:
```yaml
description: <state the capability DIRECTLY, AT MOST 150 characters - e.g. "Turn HTML into a Webcake .pke file.">
```

- [ ] **Step 2: Add the cap rule bullet**

Right AFTER line 253 (the closing ``` of the block) and BEFORE the "Classify it yourself (group)" bullet at line 254, insert:

```markdown
- **`description` is AT MOST 150 characters - this is not cosmetic.** The router truncates at
  exactly 150 (`skill_router.SKILL_DESC_MAX`) in both the system prompt and the tool
  description, so writing longer means the tail is LOST SILENTLY and the skill cannot be
  routed. COUNT after writing. State the capability directly; do NOT open with filler like
  "Activates when the user wants to..." (every skill opens that way, so it burns 29 characters
  without distinguishing anything). Put full trigger examples in a `## When to use` section in
  the BODY, where nothing is truncated and which is only read once the skill is loaded. The
  index is for FINDING, the body is for DOING.
```

- [ ] **Step 3: Verify no em dash slipped in**

Run: `cd "D:/Project/Javis-OS" && ./.venv/Scripts/python.exe -c "import pathlib; t=pathlib.Path('CLAUDE.md').read_text(encoding='utf-8'); print('em dash:', t.count(chr(8212)))"`
Expected: `em dash: 0`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): neu ro tran 150 ky tu cho description skill kem ly do"
```

---

### Task 6: POST /skills enforces the standard at write time

**Files:**
- Modify: `server/main.py:2213-2238`
- Test: `server/test_skill_caps.py`

**Interfaces:**
- Consumes: `skill_router.validate_description` (Task 1).

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_caps.py` before `if _fails:`:

```python
# ---- POST /skills must enforce the cap BEFORE creating the directory ----
# The end marker is /skills/delete (main.py:2241) and NOT /skills/toggle: toggle sits at line
# 2161, BEFORE save_skill (2214), so using it as the later marker would raise ValueError.
_save = _region("main.py", "async def save_skill", '@app.post("/skills/delete")')
check("POST /skills calls validate_description", "validate_description" in _save)
check("POST /skills enforces BEFORE mkdir",
      _save.index("validate_description") < _save.index("d.mkdir("))
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL with `POST /skills calls validate_description`.

- [ ] **Step 3: Add the check to the endpoint**

In `server/main.py`, right AFTER the slug check (lines 2219-2220):

```python
    if not skill_router.valid_slug(slug):
        return JSONResponse({"error": "Invalid skill name"}, status_code=400)
```

insert:

```python
    # Enforce the description cap RIGHT NOW, before creating any directory -> a rejected request
    # leaves no empty skill folder on disk. The router cuts at SKILL_DESC_MAX so going over means
    # silently lost text; blocking here beats writing blindly and letting the runtime cut.
    desc_err = skill_router.validate_description(description)
    if desc_err:
        return JSONResponse({"error": desc_err}, status_code=400)
```

- [ ] **Step 4: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 5: Manually verify no stray folder is created on rejection**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router
print(skill_router.validate_description('x'*200)[:60])
print('empty ->', skill_router.validate_description(''))
"
```
Expected: line 1 prints a rejection reason containing `200`; line 2 prints `empty -> None`.

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/test_skill_caps.py
git commit -m "feat(skill): POST /skills tu choi description vuot tran hoac sao rong"
```

---

### Task 7: learn.py enforces the standard + embeds the standard in the prompt

**Files:**
- Modify: `server/learn.py:156` (constant), `:356-359` (schema), `_build_prompt` (insert the standard block), `:544-568` (enforce the cap)
- Test: `server/test_skill_caps.py`

**Interfaces:**
- Consumes: `skill_router.SKILL_DESC_MAX`, `skill_router.validate_description` (Task 1). `learn.py:35` already has `import skill_router`.

**Note on language:** the prompt text below is sent to the model and is matched by the tests, like the existing `khoi_prompt` blocks in `learn.py`, so it stays Vietnamese on purpose (the header `CHUẨN VIẾT SKILL` means "SKILL AUTHORING STANDARD"). Each prompt block is glossed in English right after it. Code, names and comments are English.

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_caps.py` before `if _fails:`:

```python
# ---- learn.py: skill authoring standard in the prompt + cap enforced at promote time ----
# "CHUẨN VIẾT SKILL" = "SKILL AUTHORING STANDARD" (the machine token the prompt carries)
_learn = (_SRC / "learn.py").read_text(encoding="utf-8")
check("learn.py embeds the skill authoring standard in the prompt", "CHUẨN VIẾT SKILL" in _learn)
check("learn.py interpolates SKILL_DESC_MAX into the prompt (no hardcoded number)",
      "SKILL_DESC_MAX" in _learn)
check("learn.py enforces the description cap on promote",
      "validate_description" in _learn)
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL on all 3 `learn.py ...` lines.

- [ ] **Step 3: Extend the skill schema in `_build_prompt`**

In `server/learn.py`, change the block at lines 356-359 from:

```python
        if caps.get("skill"):
            schema_bits.append(
                '"skills":[{"slug":"kebab","name":"..","description":"khi nào dùng","body":"quy trình các bước",'
                '"self_observed":true|false,"confidence":0..3}]')
```

to the following (in the schema the model sees, "năng lực, TỐI ĐA N ký tự" means "capability, AT MOST N characters", "tên nhóm" means "group name", and "markdown theo CHUẨN VIẾT SKILL bên dưới" means "markdown following the SKILL AUTHORING STANDARD below"):

```python
        if caps.get("skill"):
            schema_bits.append(
                '"skills":[{"slug":"kebab","name":"..",'
                f'"description":"năng lực, TỐI ĐA {skill_router.SKILL_DESC_MAX} ký tự",'
                '"group":"tên nhóm","body":"markdown theo CHUẨN VIẾT SKILL bên dưới",'
                '"self_observed":true|false,"confidence":0..3}]')
```

- [ ] **Step 4: Insert the SKILL AUTHORING STANDARD block into the prompt**

In `server/learn.py`, inside the `return (...)` of `_build_prompt`, insert it RIGHT BEFORE the line
`+ ("TASK (chống spam backlog): ...` (line 386), using the same conditional-fragment idiom used there:

```python
            + (f"CHUẨN VIẾT SKILL (bắt buộc, Python sẽ CHẶN nếu vi phạm):\n"
               f"  1. description TỐI ĐA {skill_router.SKILL_DESC_MAX} ký tự. Router cắt "
               f"đúng ở đó nên phần dư MẤT IM LẶNG và skill không route được. VIẾT XONG HÃY "
               "ĐẾM, đừng ước lượng.\n"
               "  2. description nêu THẲNG năng lực. KHÔNG mở đầu bằng 'Kích hoạt khi...', "
               "'Sử dụng skill này khi...' - mọi skill đều mở như vậy nên nó đốt ngân sách mà "
               "không phân biệt gì. Tốt: 'Chuyển HTML sang file Webcake .pke.'\n"
               "  3. Ví dụ trigger đầy đủ đưa vào body, mục '## Khi nào dùng' - KHÔNG nhét "
               "vào description.\n"
               "  4. body theo thứ tự mục: '## Khi nào dùng' / '## Chuẩn bị' / '## Cách chạy' "
               "/ '## Quy trình' / '## Bẫy' / '## Kiểm chứng'. Mục nào không có nội dung thật "
               "thì bỏ, đừng bịa.\n"
               "  5. KHÔNG bịa flag, đường dẫn, API chưa thấy trong hội thoại. Không thấy thì "
               "đừng viết.\n"
               "  6. body khoảng 100 dòng cho skill đơn giản, 200 cho skill phức tạp.\n"
               "  7. KHÔNG tạo skill kiểu router chỉ trỏ sang skill khác.\n"
               "  8. group BẮT BUỘC, chọn nhóm sát nhất với skill đã có.\n\n"
               if caps.get("skill") else "")
```

English gloss of that prompt block (the model-facing text stays Vietnamese like the neighbouring blocks):

```
SKILL AUTHORING STANDARD (mandatory, Python will BLOCK violations):
  1. description AT MOST {SKILL_DESC_MAX} characters. The router cuts exactly there so the excess is LOST SILENTLY and the skill cannot be routed. COUNT after writing, do not estimate.
  2. description states the capability DIRECTLY. Do NOT open with 'Activates when...', 'Use this skill when...' - every skill opens that way so it burns budget without distinguishing anything. Good: 'Turn HTML into a Webcake .pke file.'
  3. Put the full trigger examples in the body, in the '## When to use' section (the heading text is Vietnamese in the prompt) - do NOT cram them into the description.
  4. body in section order: '## When to use' / '## Preparation' / '## How to run' / '## Procedure' / '## Pitfalls' / '## Verification'. Drop any section with no real content, do not invent.
  5. Do NOT invent flags, paths or APIs not seen in the conversation. If you did not see it, do not write it.
  6. body about 100 lines for a simple skill, 200 for a complex one.
  7. Do NOT create a router-style skill that only points to another skill.
  8. group is MANDATORY, pick the group closest to the existing skills.
```

- [ ] **Step 5: Enforce the cap at promote time**

In `server/learn.py`, in the SKILLS block of `_promote_sync`, change lines 549-550 from:

```python
                    slug = _slugify(s.get("slug") or s.get("name") or "")
                    body = (s.get("body") or "").strip()
```

to:

```python
                    slug = _slugify(s.get("slug") or s.get("name") or "")
                    body = (s.get("body") or "").strip()
                    desc = (s.get("description") or "").strip()
```

Then RIGHT AFTER the secret/injection block (lines 553-554):

```python
                    if secret_hits(body) or injection_in_output(body):
                        rep["blocked"].append(f"skill '{slug}': unsafe content"); continue
```

insert:

```python
                    # Enforce the SKILL AUTHORING STANDARD: the prompt already says so, but the fork may
                    # ignore it -> block in Python (the only trusted writer), same idiom as secret/injection.
                    desc_err = skill_router.validate_description(desc)
                    if desc_err:
                        rep["blocked"].append(f"skill '{slug}': {desc_err}"); continue
```

And change lines 564-565 (frontmatter) from:

```python
                    fm = (f"---\nname: {s.get('name', slug)}\ndescription: {s.get('description','')}\n"
                          f"origin: javis-learned\nstatus: active\ncreated: {today}\n---\n")
```

to:

```python
                    fm = (f"---\nname: {s.get('name', slug)}\ndescription: {desc}\n"
                          f"group: {s.get('group') or 'Chung'}\n"
                          f"origin: javis-learned\nstatus: active\ncreated: {today}\n---\n")
```

(`'Chung'` is the default group name, the `NHOM_MAC_DINH` constant; it means "General" and is kept verbatim because the code matches it.)

- [ ] **Step 6: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 7: Verify learn.py still imports (catches f-string syntax errors)**

Run: `cd server && ../.venv/Scripts/python.exe -c "import py_compile; py_compile.compile('learn.py', doraise=True); print('learn.py compile OK')"`
Expected: `learn.py compile OK`

- [ ] **Step 8: Commit**

```bash
git add server/learn.py server/test_skill_caps.py
git commit -m "feat(learn): nhung chuan viet skill vao prompt + chan description vuot tran"
```

---

### Task 8: skill_usage.py - telemetry sidecar

**Files:**
- Create: `server/skill_usage.py`
- Test: `server/test_skill_usage.py` (create)

**Interfaces:**
- Produces:
  - `skill_usage.SKILL_STALE_AFTER_DAYS: int` = 30
  - `skill_usage.usage_path(brain_root) -> Path` = `<brain_root>/Javis/skill-usage.json`
  - `skill_usage.read_usage(brain_root) -> dict` - `{slug: {use_count, last_used_at, first_used_at, created_at, created_by, pinned}}`. Error/missing/corrupt -> `{}`.
  - `skill_usage.bump(brain_root, slug) -> None` - best-effort, never raises.
  - `skill_usage.is_stale(rec: dict, skill_md_mtime: Optional[float], now: float) -> bool`
- Used by Task 9 (bump in the hub) and Task 10 (GET /skills).

- [ ] **Step 1: Write the failing test**

Create `server/test_skill_usage.py`:

```python
"""Test the skill telemetry sidecar (skill_usage). Run by hand / CI:

    cd server && ../.venv/Scripts/python.exe test_skill_usage.py

No pytest needed, no network. Isolates itself into a temp directory.
Covers: bump increments correctly, atomic write, missing file, corrupt JSON file, parallel
calls, is_stale (pinned / has use_count / not old enough / old enough).
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-usagetest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skill_usage  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_ROOT = Path(tempfile.mkdtemp(prefix="javis-usagebrain-"))

# ---- missing file ----
check("brain has no sidecar yet -> read_usage returns {}", skill_usage.read_usage(_ROOT) == {})

# ---- bump ----
skill_usage.bump(_ROOT, "viet-email")
u = skill_usage.read_usage(_ROOT)
check("first bump creates a record", "viet-email" in u)
check("first bump -> use_count = 1", u.get("viet-email", {}).get("use_count") == 1)
check("first bump sets created_at", u.get("viet-email", {}).get("created_at"))
check("first bump sets first_used_at", u.get("viet-email", {}).get("first_used_at"))

skill_usage.bump(_ROOT, "viet-email")
u = skill_usage.read_usage(_ROOT)
check("second bump -> use_count = 2", u.get("viet-email", {}).get("use_count") == 2)

skill_usage.bump(_ROOT, "other-skill")
u = skill_usage.read_usage(_ROOT)
check("bumping another slug does not overwrite the old slug", u.get("viet-email", {}).get("use_count") == 2)
check("bumping another slug creates its own record", u.get("other-skill", {}).get("use_count") == 1)

# ---- right location ----
check("sidecar lives at Javis/skill-usage.json",
      skill_usage.usage_path(_ROOT) == _ROOT / "Javis" / "skill-usage.json")
check("sidecar really exists on disk", skill_usage.usage_path(_ROOT).is_file())

# ---- corrupt file: must NOT break ----
skill_usage.usage_path(_ROOT).write_text("{ this is not json", encoding="utf-8")
check("corrupt sidecar -> read_usage returns {} instead of raising", skill_usage.read_usage(_ROOT) == {})
try:
    skill_usage.bump(_ROOT, "viet-email")
    check("corrupt sidecar -> bump does not raise", True)
except Exception as e:
    check(f"corrupt sidecar -> bump does not raise (raised {e!r})", False)

# ---- no write permission / nonsensical path: still does not raise ----
try:
    skill_usage.bump(Path("/does/not/exist/anywhere"), "x")
    check("brain does not exist -> bump does not raise", True)
except Exception as e:
    check(f"brain does not exist -> bump does not raise (raised {e!r})", False)

# ---- parallel calls ----
import threading  # noqa: E402

_R2 = Path(tempfile.mkdtemp(prefix="javis-usagepar-"))


def _hammer():
    for _ in range(20):
        skill_usage.bump(_R2, "race-car")


_ts = [threading.Thread(target=_hammer) for _ in range(4)]
[t.start() for t in _ts]
[t.join() for t in _ts]
_n = skill_usage.read_usage(_R2).get("race-car", {}).get("use_count", 0)
check(f"4 threads x 20 bumps -> sidecar still readable, use_count={_n} (>0, <=80)", 0 < _n <= 80)

# ---- is_stale ----
_now = time.time()
_old = _now - 40 * 86400
_new = _now - 3 * 86400

check("pinned -> never stale",
      skill_usage.is_stale({"use_count": 0, "created_at": _old, "pinned": True}, None, _now) is False)
check("use_count > 0 -> never stale",
      skill_usage.is_stale({"use_count": 5, "created_at": _old, "pinned": False}, None, _now) is False)
check("use=0 but newly created -> not stale yet",
      skill_usage.is_stale({"use_count": 0, "created_at": _new, "pinned": False}, None, _now) is False)
check("use=0 + old enough -> stale",
      skill_usage.is_stale({"use_count": 0, "created_at": _old, "pinned": False}, None, _now) is True)
check("no record + old mtime -> stale (mtime fallback)",
      skill_usage.is_stale({}, _old, _now) is True)
check("no record + new mtime -> not stale yet",
      skill_usage.is_stale({}, _new, _now) is False)
check("no record + no mtime -> not stale (not enough grounds)",
      skill_usage.is_stale({}, None, _now) is False)

if _fails:
    print(f"\nFAIL - test_skill_usage: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_skill_usage: all pass")
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'skill_usage'`.

- [ ] **Step 3: Write the module**

Create `server/skill_usage.py`:

```python
"""
skill_usage.py - TELEMETRY sidecar for skills: measures which skills are ACTUALLY used.

Location: <brain>/Javis/skill-usage.json. Placed next to Javis/loop-state.json following the
existing Jarvis 007 convention ("runtime STATE kept separate, owned by the server" - see
self_improve.py). NOT stuffed into the SKILL.md frontmatter: the brain is a git repo, so every
skill use would spawn a junk commit and put conflict pressure on a file the author owns.

One-way POSITIVE SIGNAL. The counter is bumped only in the javis_use_skill tool (mcp_hub).
Claude Code loads skills NATIVELY through the mirror <brain>/.claude/skills, which does NOT go
through there, so:
  - use_count > 0  -> the skill is DEFINITELY used.
  - use_count == 0 -> NO evidence. NEVER infer "useless", never auto-disable, never
    auto-archive. The stale label is only a reference display for the person, who decides.

Every function is BEST-EFFORT: a sidecar that is missing/corrupt/unwritable yields empty and
moves on. A broken sidecar must NEVER break a skill call.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# A skill with no usage signal that is older than this many days gets the "not seen used" label.
# The threshold is deliberately generous: a new skill has simply not met its trigger yet (Hermes rule).
SKILL_STALE_AFTER_DAYS = 30

_LOCK = threading.Lock()   # serializes read-modify-write within the process


def usage_path(brain_root) -> Path:
    return Path(brain_root) / "Javis" / "skill-usage.json"


def read_usage(brain_root) -> dict:
    """{slug: {...}}. Missing file / corrupt JSON / read error -> {} (never raises)."""
    try:
        p = usage_path(brain_root)
        if not p.is_file():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_atomic(p: Path, text: str) -> None:
    """Atomic write: a .tmp next to the target, then os.replace (same drive -> atomic rename)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".skill-usage-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def bump(brain_root, slug: str, created_by: str = "") -> None:
    """Count 1 use of a skill. BEST-EFFORT: swallows every error, only logs to stderr.
    Called at the SUCCESS point of the _skill handler (mcp_hub) - not called for a wrong slug."""
    slug = str(slug or "").strip()
    if not slug:
        return
    try:
        now = time.time()
        with _LOCK:
            data = read_usage(brain_root)
            rec = data.get(slug)
            if not isinstance(rec, dict):
                rec = {"use_count": 0, "created_at": now, "created_by": created_by,
                       "first_used_at": None, "last_used_at": None, "pinned": False}
            rec["use_count"] = int(rec.get("use_count", 0) or 0) + 1
            rec["last_used_at"] = now
            if not rec.get("first_used_at"):
                rec["first_used_at"] = now
            if not rec.get("created_at"):
                rec["created_at"] = now
            data[slug] = rec
            _write_atomic(usage_path(brain_root),
                          json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[skill usage] bump {slug}: {type(e).__name__}: {e}", file=sys.stderr)


def is_stale(rec: dict, skill_md_mtime: Optional[float], now: Optional[float] = None) -> bool:
    """PURE function. True = "not seen used and old enough" - for DISPLAY only, NOT for auto-disabling.

    Rules:
      - pinned -> never stale.
      - use_count > 0 -> never stale, NO MATTER how old last_used_at is (the native blind spot
        makes last_used_at unreliable as grounds for a negative).
      - No created_at (a skill that existed before this feature) -> fall back to the mtime of
        SKILL.md. No mtime either -> False (without grounds, do not judge).
    """
    now = time.time() if now is None else now
    rec = rec if isinstance(rec, dict) else {}
    if rec.get("pinned"):
        return False
    if int(rec.get("use_count", 0) or 0) > 0:
        return False
    born = rec.get("created_at") or skill_md_mtime
    if not born:
        return False
    return (now - float(born)) > SKILL_STALE_AFTER_DAYS * 86400
```

- [ ] **Step 4: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS, prints `OK - test_skill_usage: all pass`.

- [ ] **Step 5: Commit**

```bash
git add server/skill_usage.py server/test_skill_usage.py
git commit -m "feat(skill): sidecar telemetry Javis/skill-usage.json (tin hieu duong mot chieu)"
```

---

### Task 9: Bump at the single choke point in mcp_hub

**Files:**
- Modify: `server/mcp_hub.py:237-245`
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Consumes: `skill_usage.bump` (Task 8).

**Constraint:** `_skill` is `async` and runs ON the event loop. `bump` does disk I/O. The skill dir is small and writes are very sparse (only when a skill is loaded), so a synchronous write is acceptable; `bump` must NEVER raise (it already swallows errors).

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_usage.py` before `if _fails:`:

```python
# ---- mcp_hub bumps in the right place: ONLY on the success path ----
_hub = (Path(os.path.dirname(os.path.abspath(__file__))) / "mcp_hub.py").read_text(encoding="utf-8")
check("mcp_hub imports skill_usage", "import skill_usage" in _hub)
check("mcp_hub calls skill_usage.bump", "skill_usage.bump" in _hub)
# 'ERROR: không có skill đó' = "ERROR: no such skill" (the exact marker string mcp_hub returns)
_i_err = _hub.index('ERROR: không có skill đó')
_i_bump = _hub.index("skill_usage.bump")
check("bump sits AFTER the wrong-slug error branch (typos are not counted)", _i_bump > _i_err)
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL with `mcp_hub imports skill_usage` and `mcp_hub calls skill_usage.bump`.

- [ ] **Step 3: Add the import**

In `server/mcp_hub.py`, next to `import skill_router` (line 27), add:

```python
import skill_usage
```

- [ ] **Step 4: Bump at the success point**

In `server/mcp_hub.py`, change line 245 from:

```python
        return f.read_text(encoding="utf-8", errors="replace")[:60_000]
```

to:

```python
        text = f.read_text(encoding="utf-8", errors="replace")[:60_000]
        # THE ONLY COUNTING POINT: every engine that loads a skill through this tool passes here.
        # Count only on the SUCCESS path - the branch above already filtered wrong slugs/disabled
        # skills so typos are not counted. Use f.parent.name (the canonical slug on disk), not the
        # raw `name` from the engine. bump swallows errors on its own -> a broken sidecar never
        # breaks skill loading.
        skill_usage.bump(vault_root, f.parent.name)
        return text
```

- [ ] **Step 5: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 6: Verify mcp_hub still imports**

Run: `cd server && ../.venv/Scripts/python.exe -c "import py_compile; py_compile.compile('mcp_hub.py', doraise=True); print('mcp_hub compile OK')"`
Expected: `mcp_hub compile OK`

- [ ] **Step 7: Commit**

```bash
git add server/mcp_hub.py server/test_skill_usage.py
git commit -m "feat(skill): dem luot dung tai handler javis_use_skill"
```

---

### Task 10: GET /skills exposes usage + dashboard displays it

**Files:**
- Modify: `server/main.py:2144-2152`
- Modify: `dashboard/studio.js:463-477`
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Consumes: `skill_usage.read_usage`, `skill_usage.is_stale` (Task 8).
- Produces: each item of `GET /skills` gains `use_count: int`, `last_used_at: float|None`, `stale: bool`.

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_usage.py` before `if _fails:`:

```python
# ---- GET /skills exposes usage ----
_main = (Path(os.path.dirname(os.path.abspath(__file__))) / "main.py").read_text(encoding="utf-8")
_list = _main[_main.index('@app.get("/skills")'):_main.index('def _skills_dir')]
check("GET /skills reads usage", "read_usage" in _list)
check("GET /skills computes stale", "is_stale" in _list)
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL on both `GET /skills ...` lines.

- [ ] **Step 3: Add the import to main.py**

In `server/main.py`, next to `import skill_router` (line 43), add:

```python
import skill_usage
```

- [ ] **Step 4: Extend the endpoint**

In `server/main.py`, change the body of `GET /skills` (lines 2149-2152) from:

```python
    root = _brain_root(brain)
    sys_slugs = system_sync.system_skill_slugs()   # SYSTEM skills (follow the app version)
    out = [{**s, "system": s["slug"] in sys_slugs} for s in skill_router.list_skills(root)]
    return {"skills": out}
```

to:

```python
    root = _brain_root(brain)
    sys_slugs = system_sync.system_skill_slugs()   # SYSTEM skills (follow the app version)
    usage = skill_usage.read_usage(root)           # telemetry (one-way POSITIVE signal)
    now = time.time()

    def _mtime(p):
        try:
            return Path(p).stat().st_mtime
        except OSError:
            return None

    out = []
    for s in skill_router.list_skills(root):
        rec = usage.get(s["slug"]) or {}
        out.append({**s,
                    "system": s["slug"] in sys_slugs,
                    "use_count": int(rec.get("use_count", 0) or 0),
                    "last_used_at": rec.get("last_used_at"),
                    "pinned": bool(rec.get("pinned", False)),
                    # stale = "not seen used + old enough". For reference display ONLY: skills
                    # loaded natively through .claude/skills do not pass through the counter, so
                    # use=0 does NOT mean useless. Nothing is auto-disabled based on this flag.
                    "stale": skill_usage.is_stale(rec, _mtime(s["path"]), now)})
    return {"skills": out}
```

- [ ] **Step 5: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 6: Display in the dashboard**

In `dashboard/studio.js`, inside `renderSkillList()`, right AFTER the `sysBadge` declaration and BEFORE `div.innerHTML = ...`, insert:

```javascript
      // Telemetry: use_count is a one-way POSITIVE signal. Skills loaded natively through
      // .claude/skills do not pass through the counter, so "not seen used" is a reference,
      // NOT a verdict.
      let usageHtml = "";
      if (s.use_count > 0) {
        const when = s.last_used_at ? new Date(s.last_used_at * 1000).toLocaleDateString("vi-VN") : "";
        usageHtml = ` · <span class="sk-usage">used ${s.use_count} times${when ? ", most recently " + when : ""}</span>`;
      } else if (s.stale) {
        usageHtml = ` · <span class="sk-usage sk-stale" title="Jarvis 007 can only count skills loaded through the javis_use_skill tool. Skills Claude Code loads natively through .claude/skills cannot be counted, so this is only a reference - it does not mean the skill is useless.">not seen used</span>`;
      }
```

Then in `div.innerHTML`, change the `gp` line from:

```javascript
<div class="gp">📂 ${esc(s.group || "Chung")} · ${esc(s.slug)}${s.source === ".agents" ? " · .agents" : ""}</div>
```

to (`"Chung"` is the default group name, "General", the same constant the server uses; it stays verbatim):

```javascript
<div class="gp">📂 ${esc(s.group || "Chung")} · ${esc(s.slug)}${s.source === ".agents" ? " · .agents" : ""}${usageHtml}</div>
```

NOTE: `usageHtml` is NOT wrapped in `esc()` because it is HTML we build ourselves. Every value interpolated into it (`s.use_count`, `s.last_used_at`) is a number generated by the server, not a string typed by a user, so there is no XSS path. Do not put `s.name` or `s.description` in here without `esc()`.

- [ ] **Step 7: Add the CSS**

In `dashboard/studio.js`, in the CSS string of `_injectSkillCss()` (lines 384-409), add:

```css
.sk-usage { font-size: 11px; color: var(--muted, #888); margin-left: 8px; }
.sk-stale { opacity: .75; font-style: italic; cursor: help; }
```

- [ ] **Step 8: Check by eye**

Open the Skill page on the dashboard. Expected: a skill that has never been used and is newly created shows no label; a skill that has been used shows `used N times`. Hover over `not seen used` and a tooltip explains the blind spot.

- [ ] **Step 9: Commit**

```bash
git add server/main.py dashboard/studio.js server/test_skill_usage.py
git commit -m "feat(skill): GET /skills tra use_count/stale, dashboard hien so luot dung"
```

---

### Task 11: mirror_skills copies the whole subtree

**Files:**
- Modify: `server/system_sync.py:235-264`
- Test: `server/test_mirror_tree.py` (create)

**Interfaces:**
- Produces: `system_sync.skill_tree_hash(d: Path, rel_paths=None) -> str`.

**Constraints that must hold (this is the highest-risk task of the plan):**
1. `mirror_skills` must NOT take `_LOCK` itself. `sync_brain:356` calls it while HOLDING the lock, and `threading.Lock` (`:280`) is not reentrant -> deadlock.
2. Add/update-only. Delete NOTHING in `mirror/<slug>` that the source does not have. Removing the mirror is handled by `main.py:2186-2188` (`rmtree`).
3. Skip `.disabled`.
4. Keep `(p / "SKILL.md").is_file()` as the entry gate.
5. **Subset-digest trap:** the mirror is add-only so a destination with EXTRA files will never match the source digest -> infinite re-copy on every call (and this function is called from 7 hot paths). The digest of the DESTINATION must be computed ONLY over the set of rel paths that exist in the SOURCE.
6. **Do NOT** pass binary files through `read_text`/`skill_hash`: `errors="replace"` corrupts silently, and `_norm_text` normalizes dates. Use sha256 of raw bytes for non-`.md` files.
7. Do NOT change the signature or semantics of `skill_hash`: `sync_brain:303`, `LEGACY_HASHES:388-405` and the CLI `--hash:409-414` depend on its exact output.

- [ ] **Step 1: Write the failing test**

Create `server/test_mirror_tree.py`:

```python
"""Test mirror_skills copying the whole subtree (references/, scripts/). Run by hand / CI:

    cd server && ../.venv/Scripts/python.exe test_mirror_tree.py

No pytest needed, no network. Builds a fake brain in a temp directory.
Covers: copying subfolders, changing references/ so the mirror picks it up, skipping .disabled,
add-only (stray files in the mirror are not deleted), no re-copy when nothing changed (guards
against an infinite loop).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-mirrortest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import system_sync  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_ROOT = Path(tempfile.mkdtemp(prefix="javis-mirrorbrain-"))
_sk = _ROOT / "skills" / "has-docs"
(_sk / "references").mkdir(parents=True)
(_sk / "scripts").mkdir(parents=True)
(_sk / "SKILL.md").write_text("---\nname: Has docs\ndescription: Subtree test.\n---\nbody\n",
                              encoding="utf-8")
(_sk / "references" / "details.md").write_text("details v1\n", encoding="utf-8")
(_sk / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
(_sk / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n binary")

# a DISABLED skill must not be mirrored
_dis = _ROOT / "skills" / ".disabled" / "turned-off"
_dis.mkdir(parents=True)
(_dis / "SKILL.md").write_text("---\nname: Turned off\n---\nx\n", encoding="utf-8")

_mir = _ROOT / ".claude" / "skills" / "has-docs"

system_sync.mirror_skills(_ROOT)
check("mirror has SKILL.md", (_mir / "SKILL.md").is_file())
check("mirror has references/details.md", (_mir / "references" / "details.md").is_file())
check("mirror has scripts/run.py", (_mir / "scripts" / "run.py").is_file())
check("mirror keeps the binary file intact",
      (_mir / "image.png").is_file() and (_mir / "image.png").read_bytes() == b"\x89PNG\r\n\x1a\n binary")
check("does NOT mirror the disabled skill",
      not (_ROOT / ".claude" / "skills" / "turned-off").exists())

# change references/ WITHOUT changing SKILL.md -> the mirror must still pick it up (old hash-skip bug)
(_sk / "references" / "details.md").write_text("details v2\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("references/ changed (SKILL.md unchanged) -> mirror gets the new version",
      (_mir / "references" / "details.md").read_text(encoding="utf-8") == "details v2\n")

# add-only: a stray file in the mirror is NOT deleted
(_mir / "user-added.md").write_text("keep me\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("add-only: stray file in the mirror is not deleted", (_mir / "user-added.md").is_file())

# nothing changed -> NO re-copy (guards against an infinite re-copy even though the mirror has an extra file)
# Do NOT check with mtime: shutil.copy2 keeps the SOURCE mtime, so the destination always has the
# same mtime whether or not it was re-copied -> a test like that is green even when the code is
# wrong. We must COUNT how many times copy2 is really called. At this moment the mirror holds an
# extra file (user-added.md), so this is also the test for the subset-digest trap: the destination
# digest must be computed ONLY over the source's rel paths.
import shutil as _sh  # noqa: E402

_copies = []
_orig_copy2 = _sh.copy2


def _spy_copy2(src, dst, *a, **kw):
    _copies.append(str(dst))
    return _orig_copy2(src, dst, *a, **kw)


_sh.copy2 = _spy_copy2
try:
    system_sync.mirror_skills(_ROOT)
    system_sync.mirror_skills(_ROOT)
finally:
    _sh.copy2 = _orig_copy2
check(f"nothing changed -> NO re-copy at all (counted {len(_copies)} copies)",
      len(_copies) == 0)

if _fails:
    print(f"\nFAIL - test_mirror_tree: {len(_fails)} failures: {_fails}")
    sys.exit(1)
print("\nOK - test_mirror_tree: all pass")
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_mirror_tree.py`
Expected: FAIL with `mirror has references/details.md`, `mirror has scripts/run.py`, and `references/ changed ... -> mirror gets the new version`.

The line `nothing changed -> NO re-copy at all` may be GREEN already at this step even though the code is unfixed (the old version skips by the SKILL.md hash so it does not copy either). That is normal: that line is not meant to catch the current bug, it is a regression net for the recursive version in Step 4, where a wrong digest would cause infinite re-copying on 7 hot paths.

- [ ] **Step 3: Add `skill_tree_hash`**

In `server/system_sync.py`, right AFTER `skill_hash` (lines 97-99), add:

```python
def skill_tree_hash(d: Path, rel_paths=None) -> str:
    """Digest of the WHOLE TREE of a skill folder (SKILL.md + assets + references/ + scripts/...).

    rel_paths=None -> hash every file present in d. rel_paths=<list> -> hash ONLY exactly those
    paths (used for the DESTINATION side: the mirror is add-only so extra files at the
    destination are normal; hashing the whole destination would never match the source -> infinite
    re-copy on every call).

    .md files are hashed through skill_hash (normalizing CRLF/BOM/dates like the original). Other
    files are hashed with sha256 of RAW BYTES - do NOT pass binary files through read_text
    (errors='replace' corrupts silently).
    """
    h = hashlib.sha256()
    if rel_paths is None:
        try:
            rel_paths = sorted(p.relative_to(d).as_posix()
                               for p in d.rglob("*") if p.is_file())
        except OSError:
            return ""
    for rel in sorted(rel_paths):
        f = d / rel
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        try:
            if f.suffix.lower() == ".md":
                h.update(skill_hash(f.read_text(encoding="utf-8", errors="replace")).encode())
            else:
                h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
        except OSError:
            h.update(b"<missing>")   # missing at the destination -> digest differs from the source -> will copy
        h.update(b"\x00")
    return h.hexdigest()
```

- [ ] **Step 4: Rewrite `mirror_skills` to be recursive**

In `server/system_sync.py`, change the loop body (lines 249-260) from:

```python
            try:
                dst_dir = mirror / d.name
                dst = dst_dir / "SKILL.md"
                src_text = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")
                if dst.is_file():
                    cur = dst.read_text(encoding="utf-8", errors="replace")
                    if skill_hash(cur) == skill_hash(src_text):
                        continue   # content already identical -> no need to rewrite
                dst_dir.mkdir(parents=True, exist_ok=True)
                for f in d.iterdir():   # SKILL.md + side files (assets) in the same skill folder
                    if f.is_file():
                        shutil.copy2(str(f), str(dst_dir / f.name))
            except Exception as e:
                print(f"[skill mirror] {d.name}: {type(e).__name__}: {e}", file=sys.stderr)
```

to:

```python
            try:
                dst_dir = mirror / d.name
                # The SOURCE file set, recursive (SKILL.md + assets + references/ + scripts/ + templates/).
                rels = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
                if not rels:
                    continue
                # Compare the digest of the WHOLE TREE. The destination is hashed only over EXACTLY the
                # source's rel paths -> a stray file in the mirror (add-only) does not leave the digest
                # permanently different and cause infinite re-copying.
                if dst_dir.is_dir() and skill_tree_hash(d, rels) == skill_tree_hash(dst_dir, rels):
                    continue   # whole tree identical -> no need to rewrite
                for rel in rels:
                    dst_f = dst_dir / rel
                    dst_f.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(d / rel), str(dst_f))
            except Exception as e:
                print(f"[skill mirror] {d.name}: {type(e).__name__}: {e}", file=sys.stderr)
```

- [ ] **Step 5: Update the `mirror_skills` docstring**

In `server/system_sync.py`, change line 236 from:

```python
    """ONE-WAY mirror <root>/skills → <root>/.claude/skills (ONLY skills that are ENABLED).
```

to:

```python
    """ONE-WAY mirror <root>/skills → <root>/.claude/skills (ONLY skills that are ENABLED), RECURSIVE
    over references/ scripts/ templates/ (a skill is a PACKAGE, not a single file).
```

- [ ] **Step 6: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_mirror_tree.py`
Expected: PASS.

- [ ] **Step 7: Run every test to make sure nothing broke**

Run: `cd server && for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || echo "^^ FAIL"; done`
Expected: every file prints `OK - ...`. Pay special attention to `test_loop_ambient.py` and `test_security.py`.

- [ ] **Step 8: Commit**

```bash
git add server/system_sync.py server/test_mirror_tree.py
git commit -m "fix(sync): mirror_skills copy ca cay con + hash theo cay (references/ khong con bi bo roi)"
```

---

### Task 12: gitignore for the sidecar + reconcile old brains

**Files:**
- Modify: `server/git_brain.py:62-72` (`_GITIGNORE`), `:267-268` (`_BACKUP_SKIP_SUBSTR`), `:75-99` (`ensure_git_repo`)
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Produces: `git_brain._ensure_gitignore_lines(root) -> bool` (True = something changed).

**Constraint:** the two places live in **two DIFFERENT path spaces**. `.gitignore` is relative to the BRAIN root -> `Javis/skill-usage.json`. `_BACKUP_SKIP_SUBSTR` does substring matching on the rel path relative to the PARENT directory of the brain, and `_backup_skip` wraps the rel path in two slashes -> it must be written `"/Javis/skill-usage.json/"` (both the leading and the trailing slash), like every existing entry.

- [ ] **Step 1: Write the failing test**

Add to `server/test_skill_usage.py` before `if _fails:`:

```python
# ---- the sidecar is runtime state -> must be gitignored + kept off the backup mirror ----
import git_brain  # noqa: E402

check("_GITIGNORE has Javis/skill-usage.json", "Javis/skill-usage.json" in git_brain._GITIGNORE)
check("_backup_skip skips the sidecar", git_brain._backup_skip("brain/Javis/skill-usage.json") is True)
check("_backup_skip does NOT wrongly skip a real skill",
      git_brain._backup_skip("brain/skills/viet-email/SKILL.md") is False)

# reconcile an old brain: an existing .gitignore missing the new line must get it appended, NOT overwritten
_gi_root = Path(tempfile.mkdtemp(prefix="javis-gitest-"))
(_gi_root / ".gitignore").write_text("# mine\nmy-own-folder/\n", encoding="utf-8")
_changed = git_brain._ensure_gitignore_lines(_gi_root)
_txt = (_gi_root / ".gitignore").read_text(encoding="utf-8")
check("reconcile reports a change", _changed is True)
check("reconcile KEEPS the line the user added", "my-own-folder/" in _txt)
check("reconcile adds the sidecar line", "Javis/skill-usage.json" in _txt)
check("reconcile run a second time is a no-op", git_brain._ensure_gitignore_lines(_gi_root) is False)
```

- [ ] **Step 2: Run the test, confirm FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL with `_GITIGNORE has Javis/skill-usage.json`, `_backup_skip skips the sidecar`, and an `AttributeError` at `_ensure_gitignore_lines`.

- [ ] **Step 3: Add the line to `_GITIGNORE`**

In `server/git_brain.py`, change the block 62-72 to (insert 1 line after `Javis/loop-log/`, keeping the `Javis/` group together; each entry MUST carry its own `\n` because these are concatenated string literals):

```python
_GITIGNORE = (
    "# Jarvis 007 brain - do NOT commit: locks, raw logs (may contain secrets), background journals.\n"
    "# Git only versions DISTILLED KNOWLEDGE (facts/wiki/skills/MEMORY.md) -> clean, safe undo.\n"
    ".javis-learn.lock\n"
    "Javis/learn-staging/\n"
    "Javis/learn-log/\n"
    "Javis/loop-log/\n"
    "Javis/skill-usage.json\n"
    "memory/conversations/\n"
    "Memory/conversations/\n"
    "*.tmp\n"
)
```

- [ ] **Step 4: Add to `_BACKUP_SKIP_SUBSTR`**

In `server/git_brain.py`, change lines 267-268 from:

```python
_BACKUP_SKIP_SUBSTR = ("/memory/conversations/", "/Memory/conversations/",
                       "/Javis/loop-log/", "/Javis/learn-log/", "/Javis/learn-staging/")
```

to:

```python
_BACKUP_SKIP_SUBSTR = ("/memory/conversations/", "/Memory/conversations/",
                       "/Javis/loop-log/", "/Javis/learn-log/", "/Javis/learn-staging/",
                       "/Javis/skill-usage.json/")
```

- [ ] **Step 5: Add the reconcile helper**

In `server/git_brain.py`, right BEFORE `def ensure_git_repo` (line 75), add:

```python
def _ensure_gitignore_lines(root) -> bool:
    """Merge the lines of _GITIGNORE into <root>/.gitignore, ONLY ADDING lines that are missing.
    Returns True if something changed. NEVER overwrites: an old brain may already hold lines the
    user added. Needed because ensure_git_repo returns early on the brain-is-already-a-repo branch
    -> old brains would stay frozen forever at the template from when they were born."""
    try:
        gi = Path(root) / ".gitignore"
        cur = gi.read_text(encoding="utf-8") if gi.exists() else ""
        have = {l.strip() for l in cur.splitlines() if l.strip()}
        missing = [l for l in _GITIGNORE.splitlines()
                   if l.strip() and not l.strip().startswith("#") and l.strip() not in have]
        if not missing:
            return False
        text = (cur.rstrip("\n") + "\n") if cur.strip() else _GITIGNORE.split(".javis-learn")[0]
        gi.write_text(text + "\n".join(missing) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        print(f"[gitignore] {root}: {type(e).__name__}: {e}", file=__import__('sys').stderr)
        return False
```

- [ ] **Step 6: Call reconcile on the old-brain branch**

In `server/git_brain.py`, change lines 81-82 from:

```python
    if is_git_checkout(root):
        return {"ok": True, "created": False}
```

to:

```python
    if is_git_checkout(root):
        # The brain IS already a repo: this used to return straight from here so the new .gitignore
        # template never reached old brains. Merge the missing lines, then commit separately with
        # the 'chore:' prefix - do NOT use 'learn:'/'curator:' (see LEARN_COMMIT_PREFIXES at line
        # 31) so a one-time .gitignore patch does not show up in the Review UI or get undone by
        # revert_last_learn.
        if _ensure_gitignore_lines(root):
            commit_paths(root, [".gitignore"], "chore: update brain .gitignore")
        return {"ok": True, "created": False}
```

And change lines 91-93 from:

```python
        gi = Path(root) / ".gitignore"
        if not gi.exists():
            gi.write_text(_GITIGNORE, encoding="utf-8")
```

to:

```python
        _ensure_gitignore_lines(root)   # merge rather than overwrite (the brain may already have a .gitignore)
```

- [ ] **Step 7: Run the test, confirm PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 8: Run every test**

Run: `cd server && for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || echo "^^ FAIL"; done`
Expected: every file `OK`.

- [ ] **Step 9: Commit**

```bash
git add server/git_brain.py server/test_skill_usage.py
git commit -m "fix(git): gitignore sidecar telemetry + reconcile .gitignore cho brain cu"
```

---

### Task 13: Real end-to-end run + version bump

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

- [ ] **Step 1: Run every test the way CI runs them**

Run: `cd server && status=0; for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || status=1; done; echo "EXIT=$status"`
Expected: `EXIT=0`.

- [ ] **Step 2: Re-measure the truncation damage, confirm it is gone**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router, pathlib
root = pathlib.Path('../brains/Brain Default')
bad = 0
for s in skill_router.list_enabled_meta(root):
    e = skill_router.validate_description(s['description'])
    print(('CUT ' if e else 'ok  '), len(s['description'] or ''), s['slug'])
    bad += 1 if e else 0
print('violations:', bad)
"
```
Expected: `violations: 0`. Every skill prints `ok` with length <= 150. Before this plan the number was 6/6 violations.

- [ ] **Step 3: Run the app, confirm skills still route**

Start the server, open chat, and ask something that matches a skill's trigger (e.g. "convert this html file to webcake"). Expected: Jarvis 007 loads the `html-to-webcake` skill. Then open the Skill page, expected: `html-to-webcake` shows `used 1 times`, proving the telemetry works end-to-end.

- [ ] **Step 4: Bump VERSION + CHANGELOG**

`VERSION` is currently `0.9.61`. Write `0.9.62`.

```bash
echo "0.9.62" > VERSION
```

Add an entry at the top of `CHANGELOG.md` in the same format as the existing entries, covering: the 3 description cut points (60 in the hub, 100 in the system prompt, 140 in the fallback) gathered into one constant `SKILL_DESC_MAX = 150`; the cap enforced at `POST /skills` and in learn.py; the 5 system skill descriptions rewritten (6/6 skills were being cut, losing 79 to 316 characters); telemetry `Javis/skill-usage.json` added, counted in `javis_use_skill`; `mirror_skills` copies the whole subtree and hashes by tree; the sidecar gitignored + `.gitignore` reconciled for old brains.

- [ ] **Step 5: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump phien ban - do skill + chuan viet skill (A+B)"
git push origin main
```

---

## Notes for the executor

**Dependency order:**

- Task 1 (constants + validator) blocks Tasks 2, 3, 6, 7.
- Task 3 (rewriting descriptions) blocks Task 4 (both touch `javis-builder/SKILL.md`: Task 3 edits the frontmatter, Task 4 edits the body).
- Task 8 (sidecar) blocks Tasks 9, 10.
- Task 5 (CLAUDE.md), Task 11 (mirror), Task 12 (gitignore) are independent and can be slotted in anywhere.
- Task 13 goes last.

**Spec item B3 lives in TWO tasks, do not do it halfway:** the skill authoring standard must be in both the learn prompt (Task 7) and javis-builder (Task 4 Step 4). Do only one place and the other skill-producing path keeps spawning shapeless skills.

**The riskiest task is 11** (recursive `mirror_skills`). If stuck, re-read section B4 of the spec: the subset-digest trap and the `_LOCK` deadlock trap are the two easiest places to die.

**If a test goes red and you think it is unrelated:** `mirror_skills` is called from 7 hot paths (`main.py:184`, `:2186`, `:2235`, `:2277`, `:2651`, `:2703`, `system_sync.py:356`). Changing it can echo far away.

**Do not widen the scope.** The curator merging umbrella skills, `/learn` from a source, auto-archive, and `related_skills` as a graph are all INTENTIONALLY out of scope. If you see something worth doing, write it down, do not do it.
