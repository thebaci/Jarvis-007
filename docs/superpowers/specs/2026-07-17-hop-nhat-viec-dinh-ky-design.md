# Merging Loop + Schedule into one "Recurring job" primitive

Date: 2026-07-17
Status: design approved, waiting for the implementation plan

The project owner's opening question: "Loop and Schedule are almost the same, should we merge
them into one? Loop has 3 modes but in practice everyone who runs a loop wants full control
anyway. Users work in chat and do not actively manage loops."

Investigated with 12 agents reading the whole subsystem in parallel, plus three critic lenses
(skeptic / migration / UX), plus research on `nousresearch/hermes-agent` and prior art (ChatGPT
Tasks, Claude Code CronCreate + /loop, Anthropic Routines). Every claim below was re-verified
by hand at file:line.

## The finding that flips the question

**Loop and Schedule are not "almost the same". Loop really runs, Schedule runs nothing at all.**

`_read_automations` (`server/main.py:3149`) has exactly 6 call sites: `main.py:3198, 3211,
3242, 3259, 3299, 3352`. All of them are HTTP handlers or the index builder. The system's only
scheduler, `_scheduler_loop` (`server/main.py:3613-3656`), ticks exactly 6 jobs:

| # | Job | Called at | Real executor? |
|---|---|---|---|
| 1 | loop | `main.py:3620` → `self_improve.py:485` | Yes |
| 2 | learn (debounce + curator) | `main.py:3625-3626` → `learn.py:306, 872` | Yes |
| 3 | kanban | `main.py:3631` → `tasks.py:296` | Yes |
| 4 | reminders | `main.py:3636` → `reminders.py:312` | Yes |
| 5 | GitHub backup | `main.py:3641-3645` | Yes |
| 6 | javis index | `main.py:3650-3651` | Yes |
| - | **automations** | **nowhere** | **NO** |

Concrete consequence: create a `type: cron, status: active` row in the Schedule tab and it
shows a green "running" badge (`main.py:3201` counts `status=='active'`) and **never fires**.
The schedule field is free text (`dashboard/studio.js:367`, example "7am every day") and not a
single line of code parses it.

**Why it looks like loop: because it mostly ALREADY displays loops.** `_loops_as_routines`
(`main.py:3169-3193`) projects every loop into fake rows with a made-up schedule string at
`main.py:3187` (`f"mỗi {v['interval_min']} phút"`, i.e. "every N minutes"), and reminders are
projected in through `reminders.pending_as_automations` (`reminders.py:278`).

**Verified on disk:** `find brains -name automations.json` returns **0 hits** across all 4
brains (Brain Default, My Bullet Journal, Ngọc Thu Phạm, PostCasterAI). A hand-made Schedule row
has never existed. Everything ever seen in the Schedule tab was a loop or a reminder projected in.

`grep -rln "automation" server/test_*.py` = **0 files**. No test covers this feature.

So this is not a problem of merging two features. It is **deleting a fake feature and renaming
the real one**. The Schedule side has no user data to migrate.

### A security hole sitting in the very part being deleted

`/automations/sync` (`main.py:3264-3269`) calls:

```python
cli = claude_engine(system_prompt=None, cwd=CLAUDE_CWD, tag="routines")
```

No `allowed_tools` is passed. According to `claude_sdk_engine.py:290-301`, the `else` branch
when `allowed_tools` is empty sets `permission_mode="bypassPermissions"` (parity with
`--dangerously-skip-permissions`) **and** loads `setting_sources=["user","project","local"]`.
This is the least fenced engine call in the whole codebase. Its guarantee "ONLY LIST, do NOT
create/edit/delete/run anything" (`main.py:3273`) is just words in the prompt, with no
enforcement behind it.

It also syncs routines that run **on Anthropic's infrastructure**, a concept entirely different
from a local schedule, so it does not belong in this merge.

## The real problem: the chat path has no tool

The project owner says users live in chat. The chat path for creating recurring jobs today:

The hub's entire tool surface is `javis_connections`, `javis_read_file`, `javis_list_dir`,
`javis_write_file`, `javis_use_skill` (`server/mcp_hub.py:207-272`). **There is no
`javis_schedule`.** `grep -rn "javis_schedule\|create_loop\|javis_remind\|javis_task"` = 0 hits.

So today:
- Creating a loop = the model **hand-types YAML frontmatter** into `Javis/loops/<slug>.md`
  through `javis_write_file`.
- Creating a reminder = the model **shells out to `curl` POST /reminders through Bash**
  (`reminders.py:17` says so outright: "the engine (Jarvis 007) calls POST /reminders itself
  through Bash curl from localhost").
- Creating a Kanban task = the same, curl.

The second path also contradicts itself: a loop in suggest/auto mode has Bash blocked
(`self_improve.py:112`, `disallowed_tools = ["Bash", "WebFetch", "WebSearch", "Task"]`), so
**a loop cannot set a reminder for itself**.

Deleting the tab does not fix this. This is the expensive part and the part most worth doing.

## What Hermes does (and the lesson)

One single mechanism. A job is a record in `~/.hermes/cron/jobs.json` (one JSON file, not one
markdown file per job). `parse_schedule()` normalizes **every** input ("30m", "every 2h",
"0 9 * * *", ISO timestamp) into a schedule dict with `kind ∈ {once, interval, cron}`.

The core lesson: **"every 2 hours" and "7am" are the same primitive; `kind` is just a field.**
Claude Code confirms this independently: it converts an interval to cron at creation time.

On the Jarvis 007 side today they are two code paths that share not a single line:
- Loop: interval-since-last-run (`self_improve.py:465`), so it **drifts** over time by the run
  duration.
- Reminders: absolute wall-clock `due_at`, repeating through `cron_next`
  (`reminders.py:391-399`) using `cron_util.next_after` (`cron_util.py:120`).

The irony: **a real cron engine already exists**. `cron_util.py` is a full 5-field Vixie parser
(`@daily` macros, OR semantics between dom and dow, Vietnam timezone UTC+7), except it is wired
into `reminders.py` and not into the tab called "Schedule".

The second important prior-art lesson: **no system makes the end user pick a permission
level.** Routines, ChatGPT Tasks, Claude Code have no mode picker. The alternative is *limiting
capability*: a routine can only reach the connectors attached to it.

The boundary to keep (the Paperclip RFC and Claude Code draw the same line): merge everything
on the **time** axis, but do not merge time-driven with event-driven. That belongs to
Monitor/webhook, not this spec.

## About the 3 modes: a misunderstanding to correct

Mode **has real enforcement**, it is not decoration. `_make_cli` (`self_improve.py:611-685`)
splits into 4 mutually exclusive branches that fully change the SDK's security posture:
- suggest → `allowed_tools = readonly_tools`
- auto → `allowed_tools = safe_tools`
- full → `allowed_tools = None` + `apply_mcp(cli, mode="full")` (`self_improve.py:639-642`)

But the decisive finding is a layer below: **the hub already has a scoping model.**

- Each connection already has its own `perm` field (readonly|safe|full, `mcp_store.py:154`,
  ranked in `mcp_catalog.PERM_RANK`).
- `mcp_hub.py:143` calls `mcp_catalog.allowed(connector, conn.get("perm"), mode, tool, args)`.
- `mcp_hub.py:314` calls `effective_perm(conn.get("perm"), mode)` = the **min of the
  connector's perm and the run's mode**.
- `mcp_hub.py:322-325` filters tools right at LIST time: readonly hides the write/danger
  classes, safe hides danger.

That means **a loop's `mode` was never a "permission dial". It is only one input to
`effective_perm`.** Removing the dial from the UI knocks down no fence; it only stops making
the user turn a parameter by hand that the system can infer.

Why not let every loop run `full` by default (rejecting the project owner's initial idea): a
loop **reads outside data on every round** (POS orders, ad comments, mail). That is text anyone
else can author. Routines have to wrap the payload in `<routine-fire-payload>` and tell the
model not to obey what is inside, for exactly this reason. A `full` loop + POS connector +
prompt injection is a straight path to real money, and a `full` loop gets `allowed_tools=None`
so it swallows Bash too.

## Design

### Phase 1: delete the fakes (touch no user data)

Delete:
- 5 endpoints: `/automations` GET (`main.py:3196`), POST (`:3205`), `/automations/toggle`
  (`:3224`), `/automations/delete` (`:3251`), `/automations/sync` (`:3264`).
- `_automations_path` (`:3145`), `_read_automations` (`:3149`), `_write_automations` (`:3161`).
- The `caps["automations"]` block (`_gather_capabilities`, `main.py:3324, 3352-3354`) and the
  "## Schedule (automations)" section in `_render_javis_index` (`main.py:3411-3413`). Correction
  made while reviewing the plan: this block does **not** pollute the system prompt. It goes into
  `Javis/index.md` through `rebuild_javis_index` (`main.py:3462`), and because the list is
  always empty, `if caps["automations"]:` is always falsy and the section never renders. It is
  dead code, cleaned up for tidiness, not a bug fix. (`_javis_capability_summary` at
  `main.py:3477` never mentions automations.)
- The `editAutomation` form (`dashboard/studio.js:358-370`), the `automations` rail
  (`dashboard/console.js:49, 65, 97, 107`).

Keep and change role:
- `_loops_as_routines` (`main.py:3169`) and `pending_as_automations` (`reminders.py:278`) go
  from being projections into a fake registry to being the **real source** of the new page.
- The `selfimprove` rail (`console.js:46, 94`, `renderSelfImprove` at `console.js:674`) is
  relabeled from "Loop" to **"Jobs"**, merging the group `"Jobs & schedule"` (`console.js:65`).

Cleanup along the way (already dead, confirmed during the investigation):
- The old loop panel `dashboard/index.html:160-192` (`display:none`) still fetches
  `/loop/config` through `app.js:1497`. Delete both the dead DOM and the fetch, or keep a
  deliberate shim.
- `_isolate()` (`self_improve.py:105-113`) only runs under unit tests: its only call site is the
  `else` branch of `if self.deps.apply_mcp` (`:683`), and `main.py:3029` **always** injects
  `apply_mcp`. Note it down rather than deleting it by mistake, `test_loop_ambient.py` depends
  on it.

`/automations/sync` is deleted outright (plugging the `bypassPermissions` hole). If syncing
claude.ai routines is needed later, rewrite it as a separate button on the Models page, with
proper `allowed_tools`.

### Phase 2: one "Job" record

**Storage boundary (an ambiguity found while self-reviewing the spec):** merging means merging
the **time model and the creation path**, NOT stuffing everything into one file store.

- **Durable jobs** (repeating, run the engine: loops today + the cron that never had an
  executor) → `.md` in `Javis/loops/`. They are documents: the user opens them in Obsidian,
  edits the prompt, commits with the brain.
- **One-off reminders** (`action: notify`, `kind: once`) → **stay in the `reminders.py` store**.
  Reason: "remind me to take my medicine in 30 minutes" spawning a `.md` file in the vault and
  then deleting it is junk, and it contradicts the very reason for choosing `.md` (so the user
  can open it in Obsidian). A reminder is ephemeral, not a document.

What is merged across the two stores:
1. **A shared `parse_schedule()`** for both (one `schedule` field, three `kind`s).
2. **`javis_schedule` creates both**, routing by `kind`/`action` (see below). The user and the
   model see just one concept, "Job"; which store it lands in is an implementation detail.
3. **A single "Jobs" page** displaying both, exactly as `_loops_as_routines` +
   `pending_as_automations` already do.

That is why `reminders.py` is kept rather than deleted: it does not duplicate loop, it covers
exactly the "ephemeral" half that loop should not cover.

**Durable job storage: keep `<brain>/Javis/loops/<slug>.md` as is.** Frontmatter editable in
Obsidian is Jarvis 007's real value (`self_improve.py:11` has a deliberate comment splitting
state out into `loop-state.json` to "avoid stepping on a user who has the file open in
Obsidian"). Renaming the folder would touch 6 loop files across 4 brains plus `LEGACY_HASHES`
(`system_sync.py:536`) and the builtin loop `tu-cai-tien-javis` present in all 4 brains, in
exchange for exactly zero. The path is an implementation detail; the user sees the word "Job".

New frontmatter:

```yaml
schedule: "0 7 * * *"      # ONE field: "120m" | "0 7 * * *" | ISO timestamp
                           #   -> parsed into {kind: interval|cron|once}, Hermes style
connectors: [pancake-pos]  # PERMISSION: this job can only reach these
allow_real_actions: false  # escalation switch, clearly named
```

The old fields keep their meaning: `name`, `slug`, `enabled`, `owner_chat`, `notify`,
`quiet_hours`, `max_runs_per_day`, `workspace`, `tools_profile`, `ambient_mcp`. The file body is
still the prompt.

There is no `action` field here: a `.md` file in `Javis/loops/` is **always** `action: run`.
`notify` and `script` belong to the reminder store (`reminders.py:48` already has the three
modes `notify|task|script`), not to durable jobs.

Backward compatibility, no user file has to be edited by hand:
- `interval_min: 120` → `schedule: "120m"`.
- `mode: full` → `allow_real_actions: true`; `suggest`/`auto` → `false`.
- Precedence when both are present: `schedule` wins over `interval_min` (the same rule
  `reminders.py:235` already uses).

**Identity is still the FILE NAME, not the frontmatter slug** (`self_improve.py:273`).
`save_loop:321-327` is deliberate: a raw slug that collides with an existing file overwrites
that exact file, and only a brand-new loop goes through `_ascii_slug`. The comment explains
why: otherwise toggling a loop with a Vietnamese name would **fork an ascii copy while the
original keeps running**. Keep this behavior through the merge.

**Time model:** change `_eligible_overdue` (`self_improve.py:455-466`) to compute
`next_run_at` by `kind`:
- `interval`: keep current semantics (overdue = `now - last_run - interval*60`).
- `cron`: `cron_util.next_after(last_run)` <= now. Reuse the existing parser, write no new one.
- `once`: appears only in the reminder store (`reminders.py` already handles it). A `.md` file
  with `kind: once` is a configuration error: fire once then set itself to `enabled: false`
  (do not delete the file, the user may want to look back at it), and warn on the Jobs page.

The 5-minute floor currently enforced in 3 places (`self_improve.py:257, 929, 213`) needs
re-reviewing for `cron`: "at least every 5 minutes" is an interval rule, not a cron rule.

**Jitter (for forks):** cron adds a jitter derived from `hash(slug)`, 0 to 5 minutes. If
Jarvis 007 is forked widely, every copy runs `0 7 * * *` and they all hit Pancake at 7:00:00.
Deterministic by slug so it is stable across runs.

### Permission model

`allow_real_actions` feeds `mode="full"` or `mode="safe"` into **the very `effective_perm`
running today** (`mcp_hub.py:314`). All enforcement stays; only the dial leaves the UI.
`mode: suggest` (readonly, no file writes) merges into `safe`: writing a draft file in the
vault is harmless, and it is exactly what a user wants when they turn a job on.

`connectors: [...]` is the **genuinely new** part, and the spec's main implementation risk:
- The hub needs an `X-Javis-Connectors` header (next to the existing `X-Javis-Mode` at
  `mcp_hub.py:457, 483`).
- `mcp_hub.py:304` (`mcp_store.resolved(enabled_only=True)`) additionally filters by that list.
- An empty list or a missing field = keep the old behavior (every enabled connector), so the 6
  existing loop files do not change behavior.

The value: a job with no POS connector attached has **no way** to create an order, whatever the
prompt injection says. `mode: suggest` is only a request; scoping is the fence.

### The `javis_schedule` tool (chat path)

Add to the hub next to `javis_use_skill` (`mcp_hub.py:272`):

```
javis_schedule(op: create|list|cancel, name, schedule, prompt,
               kind_hint?, connectors?, notify_only?)
```

`min_mode: safe`.

**Routing rule (one tool, two stores):**
- `notify_only: true` or a schedule that parses to `kind: once` → goes into the **reminder**
  store (`reminders.py`), **enabled immediately**. It only fires one Telegram message, and this
  is the current behavior users rely on ("remind me in 30 minutes...").
- Everything else (repeating, runs the engine) → write a `.md` into `Javis/loops/`,
  `enabled: false`, the user switches it on. Exactly the current CLAUDE.md rule.

`op: list` and `op: cancel` must see **both stores** (union), otherwise the model will tell the
user "there are no jobs" while the job sits in the store on the other side. This is the easiest
mistake to make during implementation.

This also removes the `curl`-through-Bash path and the model hand-typing YAML, and fixes the
loop-cannot-set-its-own-reminder paradox.

A job's prompt must be **self-sufficient**: each run has no memory of the chat that created it.
The current "file body = prompt" design is already right; keep it through the merge, and do not
let the new primitive start depending on chat context.

## Out of scope for this spec

- Merging time-driven with event-driven (webhook, Monitor). A deliberate boundary.
- Kanban tasks. It is a `todo -> ready -> running` state machine with **no clock**
  (`tasks.py:296`), so it is not on the time axis. (Noted separately: `main.py:3631` calls
  `tasks_feature.tick(["brain"])` with the brain **hardcoded**, while `tick(brains)` takes a
  list. Boards in other brains are never dispatched. This is an independent bug, so file a
  separate issue.)
- Mandatory TTL/auto-expire for forgotten jobs. Prior art says there should be one (Claude Code
  expires after 7 days, ChatGPT auto-pauses when the user stops interacting); Jarvis 007 only has
  an optional `max_runs_per_day` and auto-pause on `fail_streak`. Worth doing, but a later round.
- Wrapping data returned by MCP as untrusted (in the `<routine-fire-payload>` style). Worth
  doing, a later round.

## Risks

1. **`X-Javis-Connectors` is the only part that has to change the hub.** The hub is the hard
   layer of the security model; a mistake here breaks the fence for every engine, not just
   loop. It needs its own tests for: empty list = old behavior, a list with a wrong name =
   fail-closed, not fail-open.
2. **Changing `_eligible_overdue` touches the run loop of the builtin loop
   `tu-cai-tien-javis`** that lives in all 4 brains. It needs a migration test that reads both
   old and new frontmatter.
3. **Zero tests currently cover automations**, so deleting is safe, but it also means there is
   no safety net for the UI renaming. New tests are needed for the "Jobs" page.
4. `test_loop_ambient.py` depends on `_isolate()` (a dead branch in production). Do not clean
   it up by mistake.
