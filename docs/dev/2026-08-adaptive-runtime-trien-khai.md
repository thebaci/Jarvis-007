# Adaptive Context Runtime v2 rollout plan

This document continues `2026-08-adaptive-context-runtime-spec.md`. The spec answers "what to
build". This document answers "how to get it to users without breaking anything".

Status at time of writing: all 12 phases are coded, and verified to **sit idle at the defaults**.
Not a single real request has gone through the new path yet.

## 0. The real starting point

Two things need saying before planning, because they change the amount of work:

- `main` **already carries** the Phase 0 to 12 code (PRs #53 to #57 are merged). What remains on
  the branch is only the 5 commits of PR #58. So the "get it into the main build" step is much
  smaller than it feels.
- The VPS update mechanism is `git pull` on the checked-out branch, with an **automatic
  rollback**: if `/health` does not come up within about 90 seconds, the updater runs
  `git reset --hard <old sha>`, reinstalls deps and restarts. This is the strongest safety net
  available, and it is free.

DB schema upgrades need **no manual work**: `runtime.db` and the registry both use
`CREATE TABLE IF NOT EXISTS` plus `ALTER TABLE ADD COLUMN`, run when the connection opens,
idempotent. A DB built by an older version upgrades itself to the new schema with no data loss.

## 1. Two operational properties verified by experiment

Both decide how the procedure below is written, so they were run rather than reasoned out.

### 1.1 Turning a canary on/off does NOT need a restart

`read_settings()` caches by `(mtime_ns, size)` of `settings.json`, and `_policy()` reads the
settings on every turn. Edit the file and the next turn picks it up immediately.

An important consequence: **rolling back a canary is instant**. Set the allocation to 0, save the
file, done. No deploy, no restart, no downtime window. This allows trying things more boldly than
usual.

### 1.2 The one-level merge trap (read before editing settings)

`read_settings()` merges the user config over the defaults with `.update()` **at one level
only**:

```python
for k, v in (data or {}).items():
    if isinstance(v, dict) and isinstance(cfg.get(k), dict):
        cfg[k].update(v)      # <-- one level, NOT recursive
```

The canary knobs sit **two levels** deep (`context_runtime.canary.allocation_basis_points`). So
if you hand-edit like this:

```json
{ "context_runtime": { "canary": { "allocation_basis_points": 100 } } }
```

the whole `canary` sub-dict is **replaced**, not extended. Run for real, the result:

```
canary after writing only 1 field: {"allocation_basis_points": 100}
=> quota_profiles still there: False
```

`quota_profiles` disappears. And the fail-closed design says a missing quota profile **falls back
to legacy**. Meaning you turn on 1 percent, think it is on, and **nothing happens at all**,
silently, with no error and no warning.

This is exactly the worst kind of failure: the knob turns, the light does not come on, and nobody
knows why.

**Rule when editing by hand:** you must write the **complete** canary sub-dict, copying every
field from `_DEFAULT` in `server/config.py` and only then changing the value you need to change.

**How to self-check after editing:** open the Diagnostics page and look at the canary section. It
shows `quota_rules` and `allowlist` as counts. Seeing `quota_rules: 0` means you just hit the
trap.

## 2. Roadmap

### Step 1: Get the code into the main build and onto the VPS

Turn nothing on. The only goal is to put the machine where it will run, and confirm it sits idle
exactly as designed.

1. Merge PR #58 (5 commits) into `main`.
2. Bump the version. Suggest `0.10.0` rather than a patch: this is a new foundation milestone,
   even though behavior is unchanged. Write the changelog **honestly**, say plainly that it runs
   in shadow and changes nothing for users, and that the Diagnostics page is the only thing
   visible.
3. Update the VPS using the existing update flow.

Acceptance for step 1, done right after the VPS is up:

- Open the Diagnostics page. The banner must say `mode: shadow`.
- The canary table must show **all** allocations at 0.
- Chat a few normal messages, go back to the Diagnostics page, and a new task must appear with
  `execution_path` of `legacy` or `unassigned`. Seeing it means the trace is really being
  recorded.
- If `/health` does not come up, the updater rolls back by itself. Nothing to do.

### Step 2: Collect a baseline (2 to 3 weeks, no code)

This is the unglamorous step and the one most often skipped. Without it there is no way to know
whether the new path is better or worse than the old one, and every later number is a feeling.

What to do: use Jarvis 007 as normal. Touch nothing.

Once a week, open the Diagnostics page and record four things:

- `estimate_error_pct`. This is the most important metric. It says how far the token estimator is
  off from reality. If it is far off, every budget decision after it is built on sand.
- `capsule` median and max. Tells you how big the capsule is compared with the current prompt.
- `miss_classes`. Why the resolver misses. If it mostly misses because the capability is not in
  the registry, then the problem is in the registry, not the resolver.
- `quality`. What the Quality Gate complains about in shadow.

Exit condition for step 2: a few hundred tasks in the observation window, and `estimate_error_pct`
stable rather than jumping around between weeks.

### Step 3: Fix the trap before turning anything on (do it while waiting for step 2)

Right now there is **no UI at all** to edit `context_runtime`. Searched all of `dashboard/`:
there is not a single reference other than the Diagnostics page reading it for display.

Together with the one-level merge trap in section 1.2, this means the current enabling procedure
is: SSH into the VPS, hand-edit two-level nested JSON, and if you edit it incompletely it breaks
silently.

Three options, ordered by effort:

1. **Just write the procedure.** Cheapest, but leaves the trap in place. Not recommended.
2. **Add an endpoint that sets the canary.** A `POST /runtime/canary` that takes a path name and
   an allocation, reads `_DEFAULT` itself, merges recursively the right way and then writes. Kills
   the trap at the root, no UI changes needed. **This is the option I recommend.**
3. **Add UI to the Diagnostics page.** Nicest but costliest, and there is only one user, the repo
   owner, so it is not yet worth it.

Whichever you choose, `read_settings()` should also be changed to merge **recursively**. This
trap does not only hurt `context_runtime`, it hurts every config nested two or more levels deep
in the future.

### Step 4: Turn on the first path

Turn on the **fast path** (`canary`) first, and nothing else. Reason: it is the simplest of the
11 paths, it affects only one chat turn, writes nothing outside, and has few steps in the
middle that can break. If something goes wrong, it goes wrong in the most readable place.

Sequence:

1. Declare the real `quota_profiles` for the model in use, including price and context window.
   Without real prices both the router and the budget fail closed, meaning turning it on is the
   same as not turning it on.
2. Set `allocation_basis_points` to **100** (1 percent), writing the complete sub-dict per the
   rule in section 1.2.
3. Open the Diagnostics page and confirm `quota_rules` is non-zero. This is the step that catches
   the silent failure.
4. Chat a few dozen turns. Check whether `fast` has appeared in the `paths` histogram. If it has
   not, read `fallback_reasons` to learn why it refuses.

Keep condition: quality is no worse than the step 2 baseline, and `estimate_error_pct` does not
get worse. Remove condition: any sign that answers got worse. Remove it by setting the allocation
to 0, which takes effect immediately, with no deploy.

Raise it gradually, 100 then 500 then 2000 basis points, letting each level run for at least a
few days.

### Step 5: Expand in order of risk

Turn on the next path only when the previous one is at a high, stable level. The order follows the
consequence of a mistake, light first and heavy last:

1. `canary` (fast path). One chat turn, no writes.
2. `readonly_canary`. Calls MCP but read-only.
3. `context_sources`, `memory_canary`, `lazy_skill_canary`. Changes how context is loaded.
4. `orchestrator_canary`. Multiple rounds, still read-only.
5. `model_router_canary`. Switches the model, needs a real price table.
6. `workflow_canary`, `agent_canary`. Have branches that stop and wait for a human.
7. `write_canary`. **Always last.** This is the only path that produces actions in the real world
   that cannot be undone.

Before reaching groups 6 and 7, a gold benchmark set must exist. A path with side effects that is
evaluated only by feel is gambling.

## 3. Safety nets already in place

Written down so nobody reinvents them:

- **Automatic deploy rollback** when `/health` does not come up.
- **Instant canary rollback** by editing settings, no restart needed (section 1.1).
- **Fail-closed everywhere**: an empty allowlist, a missing quota profile, or a missing price all
  fall back to legacy.
- **Invariant guard test** `test_repository_defaults_activate_no_canary_path` runs the real
  admission of all 8 paths using the constants in `config.py` itself. If anyone slips and turns a
  path on at the defaults, CI goes red.
- **The Diagnostics page** is the only place that shows the truth. Every step above is accepted by
  it, not by feel.

## 4. What is still missing

Said plainly so nobody thinks it is enough:

- No production baseline yet. Step 2 produces it.
- No `quota_profiles` and no operator-declared price table yet. Step 4 needs them.
- No gold benchmark yet. Groups 6 and 7 in step 5 need it.
- No safe UI or endpoint to set the canary yet. Step 3 solves it.

As long as these four are missing, the correct number for every allocation is still 0.
