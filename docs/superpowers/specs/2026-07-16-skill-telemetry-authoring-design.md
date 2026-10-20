# Skill telemetry + skill authoring standard (A+B)

Date: 2026-07-16
Status: design approved, waiting for the implementation plan

## Background

Comparing Jarvis 007 with `NousResearch/hermes-agent` shows that Jarvis 007 creates
skills/agents/workflows just as well, but has no **lifecycle after creation** at all: no
measuring, no merging, no cleanup. Jarvis 007 has a strong immune system (read-only learn fork,
Python as the only writer, provenance tiers, secret/injection scan, git undo) but no
metabolism. Hermes is the opposite.

Direction: graft Hermes's metabolism mechanisms onto Jarvis 007's existing safety framework,
not the other way around.

The full roadmap has 4 subsystems. This spec covers ONLY A and B.

- **A. Skill lifecycle** - telemetry, state, display.
- **B. Skill authoring standard** - description limit, authoring standard set, skill package.
- C. Umbrella-merging curator (later round, depends on A and B).
- D. `/learn` from a source (later round, independent).

C depends on both A and B: without telemetry the curator merges blind, without a standard it
does not know what shape to merge into.

## Guiding finding: the description truncation bug

This bug is REAL, running today and measurable, not a guess inferred from Hermes.

Jarvis 007 truncates descriptions in **three** places, with **three** different limits:

- `server/mcp_hub.py:256` - `(s['description'] or '')[:60]`, `metas[:20]`
- `server/main.py:3471` - `(s.get("description") or "")[:100]`, `metas[:15]`
- `server/skill_router.py:90` - `[:140]`, used when the frontmatter has no `description`, in
  which case the first line of the file body is taken as the fallback description

A skill author has no way to know which ruler they are being measured against.

Note the consequence: `SKILL_DESC_MAX = 150` does NOT match any value currently running. It
changes behavior in all three places (60 to 150, 100 to 150, 140 to 150) and changes the
`main.py` list cap from 15 to 20. This is a deliberate behavior change, not a neutral refactor.

Measured with `skill_router.list_enabled_meta` itself on the `Brain Default` brain, **6 of 6
enabled skills are truncated**:

- `html-to-webcake` 376 characters, 316 lost (84%)
- `javis-builder` 333, 273 lost (82%)
- `ingest-source` 266, 206 lost
- `query-wiki` 249, 189 lost
- `lint-wiki` 213, 153 lost
- `tao-anh-minh-hoa-2d` 139, 79 lost

More serious than the numbers: 5 of 6 skills open with the exact phrase
`"Kích hoạt khi người dùng muốn"` (Vietnamese for "Activate when the user wants"), 29
characters long. Nearly half of the 60-character budget is burned on identical boilerplate,
leaving about 31 characters that actually tell one skill from another. Every trigger example
(`vd "..."`, i.e. "e.g. ..."), which is exactly the part that makes routing work, is thrown away.

Worst of all, **the documentation actively teaches the wrong thing**. CLAUDE.md says the
description must "spell out the trigger", `javis-builder` says "write it in detail", while the
runtime truncates. Hermes warns about exactly this and calls it a non-cosmetic bug: an
over-limit description is silently cut and the skill never routes.

Relation to A: a skill that cannot route will have `use_count` stuck at 0, and the telemetry
in A would misread that as a "dead skill". **B is the precondition for A to mean anything.**

## Decisions made

1. Scope: A + B in one spec. C and D are left for later rounds.
2. Automation level: **measure and display, automate nothing**. Every disable/archive is done
   by a person clicking.
3. Description limit: **150 characters**, one single constant for both cut points.

About the number 150: Hermes uses 60, too tight for Vietnamese with diacritics. 300 was
considered and rejected, because at 15 skills it costs about 3,000 tokens per turn per engine
and grows linearly as learn.py auto-generates more skills, while 4 of the 6 current
descriptions would fit, which means it would not cure the root disease. The root disease is not
truncation (that is a symptom) but that descriptions are being written like documentation when
they are a one-line table of contents. 150 is 2.5 times Hermes's limit so Vietnamese can
breathe and fit 1 trigger example, yet still tight enough to force sharp writing.

Proof that no information is lost, rewriting `html-to-webcake` (original 376 characters):

> Chuyển HTML sang file Webcake .pke để upload/sửa trên Webcake.
> (Vietnamese: "Convert HTML into a Webcake .pke file to upload/edit on Webcake.")

62 characters, and it distinguishes BETTER than the first 60 characters of the original (the
original is cut mid-word at `"...CHUYỂN một file/đoạn HTML thàn"` ("...CONVERT a file/snippet
of HTML int"), losing the deciding keyword "Webcake" too). The remaining 316 characters are
trigger examples, whose place is the body of SKILL.md under "When to use".

Architecture: **the index is for finding, the body is for doing.**

## A. Measuring skills

### A1. Storage

File `<brain>/Javis/skill-usage.json`. New module `server/skill_usage.py`.

It lives in `Javis/` rather than `skills/.usage.json` as in Hermes, to follow the convention
Jarvis 007 already has. `server/self_improve.py` states plainly: "runtime STATE kept separate,
owned by the server: `<vault>/Javis/loop-state.json`". Telemetry is runtime state, the same
kind as loop-state, so it sits next to it.

It is not stuffed into the SKILL.md frontmatter: the brain is a git repo (`git_brain`), so
every skill use would spawn a junk commit and create conflict pressure on a file the author
writes. This is also why Hermes chose a sidecar.

Keyed by slug. Each record: `use_count`, `last_used_at`, `first_used_at`, `created_at`,
`created_by`, `pinned`.

Writes are atomic through the existing `atomic_write_text`. Every operation is best-effort: a
missing or corrupt sidecar returns empty and moves on. **A corrupt sidecar must never break a
skill call.**

### A2. Counting point

The `_skill` handler in `server/mcp_hub.py:259` (tool `javis_use_skill`). One single place,
every engine goes through it (Claude Code, Codex, OpenRouter, OpenAI, Anthropic API). Bump when
the skill loads successfully, do not bump on a wrong slug.

### A3. Blind spot (stated plainly, accepted)

`system_sync.mirror_skills` mirrors skills into `<brain>/.claude/skills` so Claude Code loads
them NATIVELY. The native path does NOT go through the hub so it cannot be counted. Dropping
the mirror would lose a real feature, so it stays.

Mandatory consequence, applying to this whole spec and every later round:

> `use_count` is a **one-way positive signal**. A count means the skill was definitely used.
> `use=0` only means "no evidence", and must NEVER be interpreted as useless, and must NEVER
> be used as grounds to auto-disable or auto-archive anything.

Hermes arrives at the same rule on its own for a different reason (its counter is still new):
"use=0 is not evidence a skill is valuable; it's absence of evidence either way. Corollary:
use=0 is ALSO not a reason to PRUNE." For Jarvis 007 the rule is even more mandatory because
the blind spot is real.

### A4. No state machine

Since "measure and display, automate nothing" is decided, the state machine is dropped
entirely. No `state` stored in the file, no background job, no scheduler.

`stale` is a **pure function** computed at read time from `(created_at, last_used_at, pinned, now)`.

The exact condition: `pinned == False` AND `use_count == 0` AND `now - created_at > SKILL_STALE_AFTER_DAYS`.

The constant `SKILL_STALE_AFTER_DAYS = 30` lives in `skill_usage.py`, NOT in
`skill_router.py`. The first draft of this spec said to put it next to `SKILL_DESC_MAX`, which
was wrong: `skill_router` has not a single line of time logic (it does not import `datetime`,
no `time`, does not read `st_mtime`), and it cannot see the usage data. A constant placed there
would sit dead. The stale function needs both `created_at` and `use_count`, both of which belong
to the sidecar, so it belongs in `skill_usage.py`.

Where `created_at` comes from: the sidecar writes it the first time it sees the skill. For a
skill that existed before this feature (no sidecar record yet), the fallback is the `mtime` of
`SKILL.md`, wrapped in `try/except OSError`. This fallback is used only to compute stale and is
not written back into the sidecar.

The 30-day threshold follows Hermes's rule: a newly created skill may simply not have met its
trigger yet, so until it is old enough it must not get any label. A skill with `use_count > 0`
is never stale, no matter how long ago the last use was (because the native blind spot makes
`last_used_at` unreliable as grounds for a negative).

All of A shrinks to: one sidecar, one bump point, one compute function. Hermes's complex
lifecycle (active/stale/archived, transition walk, `.archive/`) is saved for C, once real
telemetry data exists to test against.

### A5. Display

`GET /skills` returns an extra usage field. The Skill page shows the use count, the last use,
and a "not seen used yet" label for a skill that is old enough but has no positive signal.

This label MUST carry a note that the native path cannot be counted, so it is for reference
only. It must not be presented as a verdict.

## B. Skill authoring standard

### B1. One ruler

Add to `server/skill_router.py`:

- `SKILL_DESC_MAX = 150`
- `SKILL_LIST_MAX = 20` (merges the two current caps of 15 and 20 into one; 20 was chosen
  because descriptions drop from 300 to 150 so there is spare budget, and 20 covers every real
  skill count today)
- `SKILL_STALE_AFTER_DAYS = 30` (used by A4)

Both `main.py:3471` and `mcp_hub.py:256` import from here. No more two rulers.

Noted (NOT fixed in this spec): these two places render the same skill list, so the context
cost is paid twice every turn. Both have a reason to exist (`_skill_router_block` serves
engines without tools, the tool description serves engines with tools). Optimizing this is a
separate job, do not merge it in here.

`skill_router` is the right home because it already describes itself as "the SINGLE source of
truth for skill discovery, shared by main.py and mcp_hub.py so the two places NEVER drift
apart". The limit constants belong to that very responsibility.

### B2. Enforce at write time

`POST /skills` rejects a description over `SKILL_DESC_MAX` and rejects an opening boilerplate
phrase.

learn.py applies the same check in `_promote_sync`. A violation goes into `rep["blocked"]`
exactly as the secret-scan and injection-scan do, rather than writing blindly and letting the
runtime truncate.

Banned boilerplate: opening variants such as `Kích hoạt khi (người dùng) muốn` ("Activate when
(the user) wants"), `Dùng khi cần` ("Use when you need"), `Sử dụng skill này khi` ("Use this
skill when"). These are Vietnamese literals that the check matches, so they stay in Vietnamese.
They burn up to 29 characters without distinguishing anything, since every skill opens that way.

### B3. Shared standard set

One text constant (following the `_AUTHORING_STANDARDS` pattern of
`hermes/agent/learn_prompt.py`), embedded in both the learn prompt (`learn.py:_build_prompt`)
and `javis-builder/SKILL.md`.

Content:

- The 150 limit **with its reason**: the router cuts at exactly 150, writing longer is a silent
  loss and the skill cannot route. After writing, COUNT YOURSELF. (Hermes stresses this is the
  most violated rule and not a matter of aesthetics.)
- No opening boilerplate. State the capability, not the activation context.
- Full trigger examples go in the "When to use" section of the body, not in the description.
- Fixed section order: When to use / Prerequisites / How to run / Procedure / Pitfalls / Verification.
- Never invent flags, paths or APIs not seen in the source.
- Body length ceiling: about 100 lines for a simple skill, 200 for a complex one. Longer
  content moves down to `references/`.
- No router-style skills that only point to another skill.
- Large content goes down into `scripts/` and `references/`, referenced by relative path.
- Keep Jarvis 007's existing rules: `group` is mandatory, ASCII slug without diacritics, no em dash.

### B4. Skills as packages

Allow `references/`, `scripts/`, `templates/` inside the skill folder.

**FIX TO THIS SPEC ITSELF (the first draft was wrong, re-verified by reading
`system_sync.py:235-264` in full):** `mirror_skills` is NOT "copy only SKILL.md". Lines 258-260
copy **every top-level file** in the skill folder via `d.iterdir()` + `if f.is_file()`. What
actually gets dropped is **SUBFOLDERS**, because `f.is_file()` is false for a directory and
there is no recursion.

So the job is "flat files become a recursive tree", not "one file becomes a folder".

**Companion bug to fix at the same time:** the hash-skip gate (lines 251-256) hashes only the
content of `SKILL.md`. If `references/x.md` changes but `SKILL.md` does not, the hashes match,
`continue` runs, and the change NEVER reaches the mirror. This bug already exists with sibling
asset files, and will get worse with subfolders. The skip must become tree-aware.

Trap when making it tree-aware: the mirror is add-only, so a mirror holding EXTRA files will
never match the source's digest, causing endless re-copying on every call. The destination
digest must be computed **only over the set of paths that exist in the source**. And binary
files must not pass through `read_text`/`skill_hash` (`errors="replace"` would corrupt silently,
and `_norm_text` normalizes dates) - use sha256 on raw bytes for non-text files.

Constraints to keep: add/update-only, never delete foreign entries in `.claude`, skip
`.disabled`, and `mirror_skills` must NOT take `_LOCK` itself (`sync_brain:356` calls it while
holding the lock, and `threading.Lock` is not reentrant so it would deadlock).

**This is the highest-risk spot in the whole spec**, and needs its own tests.

**Scope:** `references/`/`scripts/`/`templates/` apply ONLY to brain skills (created by the
user or by learn). SYSTEM skills stay a single `SKILL.md` file, because `_system_items`
(`system_sync.py:142-160`) ships content as plain strings and its tuple
`(key, kind, slug, content)` is consumed by both `sync_brain` and the CLI `--hash`; loosening
it would break both. Not worth it, and not needed yet.

### B5. Rewrite 6 descriptions

No information is lost: trigger examples move down to the "When to use" section of the body,
where nothing is truncated and which is read only once the skill is loaded.

In practice only **5** need rewriting, not 6. `tao-anh-minh-hoa-2d` re-measures at exactly 139
characters, so it is ALREADY under 150 and has no trigger example in its description to move.
Leave it alone.

The 5 system skills are fixed at the SOURCE `<project>/.claude/skills/`, NOT in the mirror
copy in the brain:

- `html-to-webcake` 376 characters, 226 over (heaviest, highest risk)
- `javis-builder` 333, 183 over
- `ingest-source` 266, 116 over
- `query-wiki` 249, 99 over
- `lint-wiki` 213, 63 over (lightest)

Also fix the two places where the docs teach wrongly: CLAUDE.md (the description section
"spell out the trigger") and `javis-builder` (the description section "write it in detail").

### B6. Drift bug found while reading

`javis-builder` teaches writing skills into `.claude/skills/`, while CLAUDE.md and
`skill_router` say the canonical location is `skills/<slug>/SKILL.md` and `.claude/skills` is
only a derived mirror. The skill builder is teaching to write into the mirror.

Not 1 place but **3 places** in the same file, all three must be fixed or the file contradicts
itself:

- line 54: `### Skill -> \`.claude/skills/<slug>/SKILL.md\``
- lines 23-24: the duplicate-check step tells you to read the `.claude/skills/` folder
- line 38: the note for the `skills:` field says "only assign skills that already exist in .claude/skills"

## Testing

**House convention (must follow, verified):** this repo does NOT use pytest. There is no
conftest.py, pytest.ini, pyproject.toml or tox.ini. Every test is a Python script run directly,
using a hand-written helper `check(name, cond)` that collects failures into `_fails` and then
calls `sys.exit(1)` at the end (canonical pattern: `server/test_loop_ambient.py:23-30` and
`:117-120`).

Mandatory preamble, with load-bearing order (env BEFORE import, because module state reads
`JAVIS_STATE_DIR` at import time):

```python
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-<x>test-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import <module>  # noqa: E402
```

Do NOT use `server/test_plugins_host.py` as a template: it uses bare asserts so it stops at the
FIRST failure, whereas the description lint must list EVERY violating skill in one run. The run
command in that file's docstring (`.venv/Scripts/python`) is also wrong: `server/.venv` does not
exist, the venv is at the repo root.

The correct run command: `cd server && ../.venv/Scripts/python.exe test_<name>.py`

CI (`.github/workflows/ci.yml:29-39`) globs `test_*.py` in `server/` and runs each file with
plain `python`. So a new test **only needs to be named `server/test_*.py` to enter CI
automatically**, with no ci.yml edit. Conversely, a test placed outside `server/` will NOT run
in CI.

`test_skill_usage.py`: bump increments correctly, atomic write, missing file, corrupt file
(garbage JSON), parallel calls, a corrupt sidecar does not break a skill call.

`test_skill_router.py`: asserts that `main.py` and `mcp_hub.py` both use `SKILL_DESC_MAX`, and
that no stray constants (60 or 100) are left scattered around.

`test_system_sync.py`: `mirror_skills` copies `references/`, `scripts/`, `templates/` in full;
still skips `.disabled`; still does not rewrite when the hash matches.

**The most important CI test:** scan every system skill in `<project>/.claude/skills/`, FAIL if
any description exceeds `SKILL_DESC_MAX` or contains boilerplate. This is what keeps today's bug
from ever coming back, and the main reason B is worth doing rather than being a one-off cleanup.

Tests must run with the `.venv` (the system Python lacks libs).

## Risks

Changing system prompt content breaks the prompt cache once, on the first turn after deploy.
Acceptable.

Rewriting descriptions changes real routing behavior. Expected to improve, but it is still a
behavior change that needs monitoring.

`mirror_skills` copying directories is the most bug-prone spot. Concrete risks: deleting the
wrong file in `.claude/skills`, or overwriting something the user edited by hand. Keep the
current spirit (add/update-only, never delete foreign entries).

`Javis/skill-usage.json` is runtime state, not knowledge, so it MUST be gitignored in the
brain. This is not a judgment call: the brain's `.gitignore` already states the firm principle
"Git versions only DISTILLED KNOWLEDGE (facts/wiki/skills/MEMORY.md)" and already excludes
learn-log, loop-log, conversations, lock. Telemetry falls squarely into the excluded group.

Exact locations (the first draft had them off, re-verified):

- The template is the constant `_GITIGNORE` at `server/git_brain.py:62-72` (lines 63-64 are
  comments, the real ignore entries are at 65-71).
- The "parallel path list" does not live inside any function. It is the module constant
  `_BACKUP_SKIP_SUBSTR` at `git_brain.py:267-268`, consumed by the helper `_backup_skip()`
  (271-276), used in 4 places: `_sync_mirror` (289), `_apply_back` (467),
  `_brains_has_content` (532), `_sync_brains_locked` (604).

These two spots live in **two DIFFERENT path spaces**, which is easy to get wrong:

- `.gitignore` is relative to the BRAIN root, so write `Javis/skill-usage.json` (no leading slash).
- `_BACKUP_SKIP_SUBSTR` does substring matching on a rel path relative to the brain's PARENT
  directory, and `_backup_skip` wraps the rel in two slashes. So it must be written as
  `"/Javis/skill-usage.json/"` in exactly that form (both leading and trailing slash), like
  every existing entry.

**The old-brain question has a definitive answer: NO, an old brain will never receive the new
template.** `ensure_git_repo` has two independent guards:

1. Line 82 `if is_git_checkout(root): return {...}` returns BEFORE touching any `.gitignore`
   code. A brain that is already a git repo never re-reads the template.
2. Lines 92-93 `if not gi.exists(): gi.write_text(_GITIGNORE)` - even on the init branch, an
   existing `.gitignore` is not touched.

So `ensure_git_repo` is idempotent in the sense of "calling it again does not break anything",
but it does NOT reconcile.

The fix: split out a helper `_ensure_gitignore_lines(root) -> bool` that reads the existing
`.gitignore`, only APPENDS the lines of `_GITIGNORE` that are missing (merge by line, ABSOLUTELY
never overwrite, or user-added entries get deleted), and returns whether anything changed. Call
it on both branches. On the old-brain branch, if it changed anything, commit with
`commit_paths` using the prefix `chore:` (NOT `learn:`/`curator:`, because
`LEARN_COMMIT_PREFIXES` at line 31 decides what appears in the Review UI and what
`revert_last_learn` will undo). Add no new `add -A`: line 95 itself states this is the ONLY
place `-A` is allowed.

Two remaining things to handle: (a) an old brain may ALREADY track `Javis/skill-usage.json`
because of the baseline `add -A`, and gitignore has no effect on an already-tracked file, so a
one-time `git rm --cached` is needed when the path is both ignored and tracked; (b) no caller
runs at server startup (only `/learn/enable` and `/reflect` call it), so reconciliation only
happens when one of those two endpoints is called.

## DEFERRED: B4 (recursive mirror_skills) - needs its own spec

On 2026-07-17, after fanning out 6 readers to map the risk, **B4 was deferred** (Quy decided).
Recorded here because the build ledger is gitignored and the findings would be lost with it.

**This spec was WRONG in three places about B4:**

1. *"SYSTEM skills stay a single SKILL.md file"* - **wrong**. `.claude/skills/html-to-webcake`
   already ships `tools/` (4 files) + `examples/` (9 files) right now.
2. *"7 hot paths"* - **wrong**. There is only ONE truly hot spot: `main.py:184` in
   `build_system_prompt`, which runs every chat turn (dashboard, Telegram, Kanban task, loop,
   reminder, learn spawn). The other six are endpoints a person triggers, plus
   `system_sync.py:356` which runs once per brain per process.
3. The symlink and binary file warning - **no basis**. The disk has no symlinks/reparse points
   and no binary files (even `.pke` is base64 ASCII).

**Six blockers that stop B4 from working as written:**

- `main.py:184` has NO gate (unlike `ensure_synced` right above it, which is guarded by
  `_SYNCED_ROOTS`). This is deliberate so a skill written mid-session shows up without a
  restart. Going recursive = rglob + hash every file in every skill dir EVERY CHAT TURN.
  Measured real numbers: `brains/My Bullet Journal/skills` = 27 dirs / 41 files / 496 KB. And
  the cost grows with exactly the things this feature encourages adding (`references/`, `scripts/`).
- `build_system_prompt` is a SYNCHRONOUS function, called bare from async handlers
  (`main.py:4359`, `:4641`). Walking a directory tree would block the event loop -> every
  WebSocket, Telegram poller, scheduler loop and reminder tick stalls. Not just that chat turn.
  The repo knows to use `asyncio.to_thread` elsewhere.
- `_LOCK` is a non-reentrant `threading.Lock`. `sync_brain:356` calls `mirror_skills` WHILE
  holding the lock, but 7 places in `main.py` call it WITHOUT holding any lock. So the recursive
  version cannot take the lock (deadlock) and cannot drop the lock either (an unsynchronized
  tree copy races with the locked one). It needs a redesign, not a few-line fix.
- On the first call for each brain, `mirror_skills` runs TWICE back to back (`sync_brain` step 3,
  then `main.py:184`). Cheap today, but it doubles the whole-tree hashing right at startup.
- NOT ONE test in the repo touches `mirror_skills`. The `test_system_sync.py` this spec assumed
  exists does NOT EXIST. The rewrite has no safety net.
- The benefit B4 promises it CANNOT deliver: `html-to-webcake` is broken because `_system_items`
  (`system_sync.py:142-160`) only ships the SKILL.md string, sitting ABOVE `mirror_skills`.

**A real bug found along the way (recorded, to be handled later - Quy decided):**

`html-to-webcake` **is broken in EVERY brain right now**. Its SKILL.md tells the agent to run
`tools/` and read `examples/`, but the subtree has never reached any brain because
`_system_items` ships only SKILL.md and `_atomic_write` is text-only. A PRE-EXISTING bug, not
caused by this plan. Fixing it requires: `_system_items` shipping the whole tree + the manifest
moving from per-item to per-file (it is currently one `hash` string per skill, even though the
key is named `"files"`). The manifest decides whether the app auto-updates over a skill the
user edited, so touching it needs separate care.

**A second real bug (also pre-existing):** the `mirror_skills` hash-skip gate hashes only
SKILL.md, but the copy loop copies EVERY top-level file. So if a sibling asset changes but
SKILL.md does not, the mirror NEVER receives it. True today, and gets worse if there is a subtree.

**Real data:** 11 of 59 skill dirs already have subfolders (10 x `references/` in brains, plus
`html-to-webcake`). So the need is REAL, not imagined - only the approach in this spec was wrong.

Remaining work when writing the separate B4 spec: gate the cost at `main.py:184` first, solve
the lock problem, build `test_system_sync.py` from zero, and only then touch recursion. And fix
`_system_items` if system skills should be able to ship subtrees.

## Out of scope (deliberate)

Umbrella-merging curator (C). `/learn` from a source (D). Auto-archive and `.archive/`.
`related_skills` as a graph. A full lifecycle state machine. Skill templating in the style of
`${HERMES_SKILL_DIR}` and inline shell.

## References

Hermes repo read at commit `53adb3f`. Files worth re-reading when doing C:
`agent/learn_prompt.py` (authoring standard), `tools/skill_usage.py` (telemetry sidecar,
lifecycle), `agent/curator.py` (umbrella-merge prompt, hard rules), `agent/background_review.py`
(post-turn review fork), `agent/learning_graph.py` (display graph).
