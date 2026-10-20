# Resonance A2: adaptive heartbeat driven by reasons

**Status:** design passed review in round 4 (`cb11fc23`); the A2 code passed review at `b5975b7e`, integration check passed (record: `docs/dev/resonance-a2-verification.md`); shipped in 0.88.0 (`c101d108`). Guide to use and roll back: `docs/dev/resonance-a2-heartbeat.md`. Branch `claude/resonance-a2-heartbeat`, version number reserved 0.88.0.

- **Base:** at design time, the A1 branch at `077bcf73` (0.87.0). A1 was squashed into `main` as `fdfec7c5` on 2026-10-09; the A2 branch has moved onto `main`.
- **Roadmap:** [agent scope roadmap](2026-10-08-resonance-agent-scope-roadmap.md), section 5.
- **Round 1** (`7504bf6a`) was reviewed: 2 P1, 2 P2, 5 points to clarify. **Round 2** (`e95a3260`): 4 P2 and 2 notes. **Round 3** (`fe92e753`): 1 P2. Section 15 lists each point and where it was fixed.
- No model was called to produce this design. There is no A2 pilot yet.

## 1. Goals and out of scope

**Goals:**
- The assistant wakes only when there is a specific reason.
- Call the model only when there is a first step not yet done, new news from the user, or an automatic retry within the ceiling.
- When waiting, sleep.
- Every wake records its reason and decision.
- A wake that calls no model must also be cheap for the server (section 11).

**Unchanged:**
- One scheduler: `tick` in the 30-second background loop, taking the schedule by CAS (`claim_wake`), the turn lease (`claim_lease`), and reconciliation when the process dies midway (`_reconcile`).
- The handoff gate, the call budget, the outbox that prevents duplicate notices, the file protection of `_publish`.
- Old tables keep their columns (the `PRE_A1` test still locks them). A2 only adds side tables.

**Out of scope:**
- Learning from reactions and feedback: left to A3.
- Adapters for external event sources (MCP, webhook, instant file watching).
- Permission to replace a file the user edited, and the auto-generated proposal on conflict (section 5).
- Linking the `javis_schedule` schedule to a goal, and blocking duplicate schedules (section 9).
- A per-assistant or per-day budget (section 14, question 3).
- The path for assigning work from ordinary chat to an assistant.

## 2. Current state and gaps (code at `077bcf73`)

| # | Current state | Consequence |
|---|---|---|
| G1 | `tick` calls `advance(..., {"kind": "wake"})` for every `work` schedule. The reason is only wording in `wakeups.reason`, overwritten at every scheduling | `advance` does not know why it is awake |
| G2 | Every `wake` with an unmet result that is not just waiting for the user goes into `_work_step` (calls the model). This includes review wakes (`_bounded_review`), the re-check after enabling the assistant, and recovery after an interrupted turn | The model is called when there is nothing new |
| G3 | `RETRY_NOT_MET_S` of 15 minutes repeats until the budget runs out, ignoring progress | Turns are wasted when stuck |
| G4 | `ERROR_BACKOFF_S` stops at 24 hours and then repeats forever. Errors are counted across all revisions | A permanent error still calls the model every day |
| G5 | `due_wakeups` skips paused goals, so the `observe` schedule stops too. `_gate` returns early before rescheduling `observe` | Pausing loses guard monitoring and nobody knows. Switching the assistant off means the guard is silently no longer watched |
| G6 | There is no ledger of wakes | Cannot answer why a wake called the model |
| G7 | The card shows `next_wake.reason`, a raw Vietnamese sentence | Out of line with i18n |
| G8 | A wake runs on the event loop: synchronous SQLite and file reads | Many goals due at once can slow the tab, even without calling a model |

## 3. Wake reasons: identity, class, lifecycle

### Two sources of reasons, one eligibility time

Every reason has two timestamps:
- `created_at`: when it was taken in;
- `due_at`: when it becomes **eligible** to be considered.

The snapshot and the schedule rely only on `due_at`, for both sources. Being present in the store does not mean it is time to act.

**Event** (`origin=event`): produced by something that has happened.
- Each event has a stable `source_ref`, taken from the source itself: the id of a `goal_events` row, `rev:<n>`, `handoff:<rev>`, the id of an assistant event.
- Redelivering the same event (HTTP retry, two tabs, restart) yields the same `source_ref`. A partial unique index blocks a second row, whether the first is still waiting or already served.
- A served row is not deleted while the goal is active, so later redelivery is still recognized. No TTL is used to prevent duplicates.
- `due_at = created_at`, except `user_schedule`: there `due_at` is the time the user scheduled.
  - A future-scheduled event has a stable id at write time.
  - Before that time it does not enter the snapshot, does not pull the schedule, and is not served.
  - A restart still keeps the time, because the time lives in the store.

**Timer** (`origin=timer`): produced by the policy or the gate scheduling.
- Each scheduling is a **new instance**, `source_ref = tm_<random>`, with no uniqueness constraint. Two consecutive periodic reviews are two different rows.
- Each timer belongs to one **duty** (`slot`):
  - `retry`: `retry_not_met`, `error_retry`, `recovery`;
  - `check`: `review`, `deadline`, `drift_recheck`, `agent_recheck`, `guard_recheck`, `handoff_wait`;
  - `observe`: `guard_observe`.
- Each goal has at most one pending timer for **each duty**. A new timer only replaces an old one of the same duty (`superseded`, same transaction).
  - A deadline check does not delete a pending retry, and vice versa.
- `wakeups` still has only one `work` row and one `observe` row per goal. That is the **physical schedule**, recomputed from the duties (section "Physical schedule" below).

**Source revision:** every reason records `revision`.
- An event takes its revision from the source row: feedback carries `expected_revision`, `rev:<n>` carries `n`.
- A timer takes the revision at scheduling time.
- A reason from an old revision does not open a model turn and does not reset the ceiling of the new revision. When considered, it is settled `served` with `settled_by = stale_revision`. The new revision already has its own `revised` reason.

### Classes

| Class | Codes | May open a model turn? |
|---|---|---|
| First step | `created`, `revised`, `assigned` | Yes, only when the current revision has no work turn yet and no draft taken in from chat |
| New news | `feedback` (every feedback except a reaction), `user_schedule` | Yes, within the budget |
| Automatic retry | `retry_not_met`, `error_retry`, `recovery` | Yes, under the ceiling in section 4 |
| Check only | `handoff_wait`, `handoff_done`, `resumed`, `agent_enabled`, `agent_recheck`, `agent_changed`, `guard_recheck`, `review`, `deadline`, `drift_recheck`, **unknown code** | Never |
| Observe | `guard_observe` | Never. Does not publish the product |

- **Only a reason can open a model turn.** A revision with no output yet does not become a reason by itself: if the snapshot has only `review`, `deadline`, observation or an unknown code, the model is not called.
- **A goal that predates A2** has no reason rows. The first time A2 opens the store, for each active goal, the store rebuilds reasons from `goal_events` itself:
  - the current revision has no work turn: one `created` reason, `source_ref = migrate:rev:<n>`;
  - feedback (`feedback.*`) written after the latest work turn of the revision: one `feedback` reason per feedback, `source_ref` is the event row id, the same key as at normal write time.
  - An old `wakeups` schedule with no reason row counts that wake as `review` (check only).

### Lifecycle

`pending` to `served` (with `settled_by`), or `pending` to `superseded` (timers only).

1. **Snapshot:** `advance` holds the turn lease and then reads the `pending` reasons with `due_at <= now`, both events and timers.
   - Only ids in the snapshot are considered and served.
   - A reason arriving while a turn is running stays `pending` for the next time.
2. **Blocked by a gate** (assistant off, paused, understanding rejected, guard `unknown`, waiting for handoff): **no reason that can open a model turn is served** (first step, new news, retry).
   - Write a `wake_log` with the ids seen.
   - Those reasons stay intact, including their original eligibility time. When the block is lifted (`resumed`, `agent_enabled`, `guard_recheck` finding the guard readable again), the next wake sees them again.
   - A `check` timer that has come due (review, deadline) has been considered:
     - if the gate has a re-check timer, that timer replaces the old one, same `check` duty;
     - if the gate has no re-check timer (paused, budget exhausted, guard already hit), it is settled `served`.
     - Nothing is lost: the first wake after the block is lifted recomputes the `check` timer from the goal state (review schedule, deadline).
3. **`work` decision:** `begin_action` marks `served` every id in the snapshot, in the same transaction that writes the action intent. The intent carries the list of ids.
   - If the model turn fails, the error rule applies.
   - The feedback text is not lost: the prompt reads the intent chain and feedback from the store, not from the reasons.
4. **Other decisions** (through a gate, no model call), in the same transaction that writes `wake_log`:
   - **Check only** and **automatic retry** reasons are served, because they have been considered.
   - **First step** and **new news** reasons are only served when the conclusion is that nothing needs doing: already met, only waiting for user confirmation, or the chat draft just taken in satisfies it.
   - Blocked by budget exhaustion: keep `pending`.
5. **Observe** serves only its own `guard_observe` timer and does not touch `work` reasons.

### Physical schedule

One common principle for events and timers: **a stored duty is not necessarily placed on a schedule that can run.**

After every wake, the `work` `wakeups.due_at` is computed from the state at the end of the wake:

- **Not parked:** the earliest of
  - the `due_at` of pending timers, in both the `retry` and `check` duties;
  - the `due_at` of pending events.
- **Parked:** only the `due_at` of the **unpark timer** just set in the `check` duty (`agent_recheck`, `guard_recheck`, `drift_recheck`, `handoff_wait`).
  - Pending events and `retry` timers are not counted, even if overdue.
  - With no unpark timer, delete the `work` row. The goal waits for an active event.

If no time remains, delete the `work` row.

**Parked:** a duty remains but cannot be served right away, so it does not pull the schedule, even when its eligibility time has passed.
- Park when a wake ends in a state that cannot serve a reason that opens a turn:
  - `blocked` (blocked by a gate, budget exhausted, permanent error);
  - waiting for the handoff chat turn (the schedule is a 30-second `handoff_wait` timer, as in the MVP);
  - `waiting`/`source_drift`.
- Ways to unpark:
  - the gate's re-check timer (`agent_recheck`, `guard_recheck`), or `drift_recheck` (section 5);
  - an unblocking action (`resumed`, `agent_enabled`);
  - a new event. A new event sets the schedule to its own `due_at` at write time, so it wakes **exactly once** to check, then parks again if it still cannot be served.
- Budget exhaustion and a permanent error have no re-check timer. Only a new event can unpark, as in the MVP.
- A **parked `retry` timer** keeps its record, eligibility time, revision and error or stall streak. On unparking, the first wake reconsiders it under the permission, revision, guard and budget of that moment:
  - if overdue, consider it right away, exactly once, under the ceiling in section 4;
  - if not yet due, still wait for the exact backoff time;
  - re-enabling the assistant or the guard recovering does not reset the error or stall streak;
  - `served` is not used to pretend a turn that was never called has run.
- **Parking is a state stored in the store** (`goals.run_state`, together with the pending timers). A restart does not turn the dense wake loop back on.
- A parked goal does not hold a time in the past, so it does not take a `TICK_LIMIT` slot from another goal.

**Consequences:**
- An event arriving while a turn runs, not parked, pulls the schedule to `now` after the turn.
- A future timer (`user_schedule`, retry) does not pull the schedule earlier.
- If a deadline check happens before the retry time, the retry is not in the snapshot (not yet eligible). The retry still waits, and the schedule after the check goes back to exactly the retry time. An early check does not make a retry run before its backoff time.
- When waiting or blocked there is no 30-second wake loop, except while waiting for handoff (a 30-second `handoff_wait` timer, as in the MVP, only while the chat turn runs).

**At the same moment:** if both the `check` and `retry` timers have come due they enter one snapshot, and there is only one decision.
- The decision order (section 4) considers the retry.
- The check part (assessment, deadline) always runs first, in that same wake.
- Both are served together.

**Reconciliation after rolling back to the old version:**
- Version 0.87 may have done work without recording reason ids. When the store is opened, `pending` events of the same revision whose `created_at` is **before the work turn started** (`actions.created_at`, not when the turn ended) are settled `served`, with `settled_by` set to that turn.
- Only those events could have been seen in the input of the old turn. An event arriving after the turn started stays `pending`.
- This is only a reconciliation path for this case; it does not replace the snapshot rule.

## 4. Policy `heartbeat.v1`

A pure function `decide(goal, snapshot, history, assessment, now, policy) -> Decision` in a new module `server/resonance_heartbeat.py`. No I/O, tested by table.

### Decision order

1. `_gate` (section 7) blocks: `blocked`, nothing is served.
2. The handoff gate is still waiting: a `handoff_wait` timer, nothing is served.
3. `_publish_latest`, then code assessment, then the out-of-band edit check (section 5). No step calls a model.
4. Already met, or only waiting for the user: `evaluate`. Serve the whole snapshot, schedule per the table below.
5. Waiting because of an out-of-band edit (section 5): `evaluate`, keep the first-step and new-news reasons `pending`.
6. The snapshot has **new news**: `work`, if turns remain (regardless of the reserve).
7. The snapshot has a **first step** and the revision has no work turn or intake yet: `work`, if turns remain.
8. The snapshot has an **automatic retry** and the ceiling allows: `work`.
9. Otherwise: `evaluate` or `sleep`. **0 model turns.**

At step 6 or 7, if no turns remain: `blocked`/`budget`, keep the reason `pending`, do not schedule `work`.

### Progress and stall

- **Best mark:** the highest number of met criteria after the work turns within the same revision, counted from the latest new news (or from the start of the revision).
- **Progress:** a new turn that exceeds the best mark. A turn that drops and then recovers to the old mark does not count as progress, so oscillation does not reset the streak.
- **Stall streak** (`stall`): the number of consecutive work turns that do not exceed the mark, also counted from the latest new news.
- `stall >= STALL_AFTER` stops automatic tries: `waiting`/`stalled`, reported **once** per revision (`goal.stalled`).
  - This is not a failure. The goal stays active.
  - New news (feedback, a new revision) reopens it by the rules, and the streak restarts from 0.
  - The success criteria do not change.

### Automatic retry ceiling (one common rule)

A `retry_not_met`, `error_retry` or `recovery` turn may only run when **both** conditions hold:

- **A reserve turn remains:** `budget_calls - calls_used > AUTO_RESERVE_CALLS`. The last turn is kept for when the user gives feedback. New news and first steps can use that turn.
- **The branch's own ceiling is not reached:**
  - `retry_not_met`: `stall < STALL_AFTER`.
  - `error_retry` and `recovery`: the number of failed work turns counted from the latest new news in the revision is below `ERROR_MAX_FAILS`, and the latest error is not in the permanent group.
  - `ERROR_MAX_FAILS = 3` means **three failed turns in total**, including the first, so at most two retries. An interrupted turn that has been reconciled counts as one failed turn.

**Permanent and transient errors:** the code table is fixed at coding time, from the codes the real engine returns.
- Permanent: broken engine build (`engine_build`), wrong write area (`output_scope`), budget exhausted (`budget_exhausted`).
- Transient: timeout, interrupted (`interrupted`), overload, a subscription plan limit that reopens at a known time.
- An unknown code is treated as transient, still under the ceiling.
- Ceiling reached or a permanent error: `blocked` by code, reported once, no `work` scheduled. New news reopens it.

### Scheduling the next wake

| Situation | `work` schedule | Code |
|---|---|---|
| Not met, can retry | `retry`: `now + RETRY_BASE_S × 2^stall` | `retry_not_met` |
| Transient error, can retry | `retry`: the limit reopening time + 60 seconds if known; otherwise `ERROR_BACKOFF_S[fails-1]` | `error_retry` |
| Stalled, ceiling reached, permanent error, budget exhausted | No schedule | |
| Waiting for the user (confirmation, understanding rejected, exploration done) | No schedule | |
| Out-of-band edit not meeting the bar | `check`: `DRIFT_RECHECK_MIN_S`, doubling up to `DRIFT_RECHECK_MAX_S` (section 5) | `drift_recheck` |
| Met in maintenance mode, or no reason to work | `check`: review with growing intervals | `review` |
| A deadline not yet reached | `check`: see the near-deadline part | `deadline` |

The two duties `retry` and `check` are scheduled independently. One wake can set both.

**Review with growing intervals:**
- Start at `REVIEW_MIN_S`. If a review sees no change, double, up to `REVIEW_MAX_S`.
- If it sees a change, go back to `REVIEW_MIN_S`. "Change" includes the assessment result, the product hash, the guard state.
- A review only runs code. The intervals grow to reduce chores for the server, not to reduce model turns.

**Near a deadline** (`horizon.kind = deadline`, `at` is the deadline), by priority:
1. More than `2 × CHECK_MIN_S` left: a `check` timer at the earliest of the review schedule and `now + (at - now) / 2`.
2. Between 0 and `2 × CHECK_MIN_S` left: a single check exactly at `at`. Latency in section 11.
3. Past the deadline and not met:
   - record a `deadline_passed` event and report **once** per revision (`goal.deadline_passed`);
   - do not extend it by itself, do not conclude success or failure, do not open a model turn because of the deadline;
   - afterwards go back to the normal review schedule.

`deadline` belongs to the check-only class and occupies only the `check` duty. A pending retry or backoff is not moved earlier or later because of the deadline.

### Parameters (version `heartbeat.v1`)

| Name | Default | Note |
|---|---|---|
| `RETRY_BASE_S` | 900 | 15 minutes as in the MVP |
| `STALL_AFTER` | 2 | review accepted this as the default |
| `AUTO_RESERVE_CALLS` | 1 | |
| `ERROR_MAX_FAILS` | 3 | three failed turns in total, counted from the latest new news |
| `ERROR_BACKOFF_S` | 1, 4, 24 hours | as in the MVP |
| `REVIEW_MIN_S` | 6 hours | as in the MVP |
| `REVIEW_MAX_S` | 7 days | new; the MVP stops at 24 hours |
| `CHECK_MIN_S` | 15 minutes | near a deadline |
| `GUARD_OBSERVE_S` | 1 hour | as in the MVP, no growth |
| `DRIFT_RECHECK_MIN_S` | 1 hour | re-check while waiting for a hand-edited file |
| `DRIFT_RECHECK_MAX_S` | 24 hours | |

- These are versioned constants in the policy module, not settings fields.
- Every wake records `policy_version`. Changing a default bumps the version.
- Tests replace parameters through the arguments of `decide`.

## 5. Files edited out of band

Today, `_publish` does not replace a file when the hash on disk differs from the published mark (`published`), and reports `goal.publish_conflict` once per hash. A2 keeps this protection and **separates the observation mark from the mark that permits replacing the file**.

- **The mark that permits replacing the file:** still the `published` table. A2 never writes this table just because of observation, so it cannot bypass the protection.
- **The observation mark:** a side table `source_observations(goal_id, path, sha256, first_seen_at, verdict)`.
  - A review reads the bytes and computes the hash of the product file, without a cached hash (section 11). A hash different from `published` is an **out-of-band edit**.
  - A hash not yet in the table: write a row (H1, then H2 is another row), report once using the existing idem `publish_conflict:<path>:<hash>`.
  - A hash already there: no write, no report.
- **Decision:**
  - **Do not call a model** because of an out-of-band edit. The host has no permission to replace that file, so a version the model wrote could not be published either.
  - If the user's version still meets the criteria: record it, `healthy`, review as usual.
  - If the user's version does not meet them: `waiting`/`source_drift`.
    - First-step and new-news reasons stay `pending` and **parked** (section 3), so they do not pull the schedule to `now`.
    - The only schedule is a `drift_recheck` timer in the `check` duty.
- **The recovery path** is a re-check by code, with spacing:
  - `drift_recheck` starts at `DRIFT_RECHECK_MIN_S` (1 hour), doubling each time the file is still edited out of band, up to `DRIFT_RECHECK_MAX_S` (24 hours).
  - Each time it reads one file of at most 1 MB, with no model call.
  - A new event (feedback, resume) triggers an immediate single check.
  - The card says it clearly: "The file was edited outside Jarvis 007. Jarvis 007 re-checks it at <time>; give feedback to check now." The slowest detection time is `DRIFT_RECHECK_MAX_S`.
- **Leaving the waiting state:**
  - The user restores the file to the published mark: the out-of-band edit is gone, assess as usual. Parked feedback is handled exactly once in that wake.
  - The user deletes the file: there is no conflict any more. If the version in effect is a background work turn, `_publish_latest` republishes without calling a model. If the version in effect is a draft taken in from chat, there is currently no republish path (`_publish_latest` returns `superseded`), so A2 treats it as an out-of-band edit: wait, report once, no model call.
  - The user edits the understanding or changes the path: it becomes a new revision, normal flow.
  - Any option that grants permission to overwrite, or lets the model write a proposed version beside the file, is a new permission. A2 does not do it, noted in out of scope.
- **The guard** still observes that file under existing permissions (section 7).

## 6. Store

Three side tables. No old table changes columns.

```sql
CREATE TABLE IF NOT EXISTS wake_reasons(
  id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL, brain_id TEXT NOT NULL,
  wake_kind TEXT NOT NULL,                 -- work | observe
  code TEXT NOT NULL, origin TEXT NOT NULL, -- event | timer
  slot TEXT NOT NULL DEFAULT '',           -- retry | check | observe (timers); empty for events
  revision INTEGER NOT NULL,               -- source revision
  source_ref TEXT NOT NULL,
  due_at REAL NOT NULL,                    -- when it becomes eligible to be considered (event: write time, except user_schedule)
  state TEXT NOT NULL DEFAULT 'pending',   -- pending | served | superseded
  created_at REAL NOT NULL, settled_at REAL, settled_by TEXT NOT NULL DEFAULT '');
CREATE UNIQUE INDEX IF NOT EXISTS wake_reasons_event
  ON wake_reasons(goal_id, code, source_ref) WHERE origin='event';
CREATE INDEX IF NOT EXISTS wake_reasons_pending ON wake_reasons(goal_id, state, due_at);
CREATE TABLE IF NOT EXISTS wake_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL, brain_id TEXT NOT NULL,
  revision INTEGER NOT NULL, wake_kind TEXT NOT NULL,
  seen_json TEXT NOT NULL, served_json TEXT NOT NULL,     -- reason ids seen and served
  policy_version TEXT NOT NULL,
  decision TEXT NOT NULL,                                 -- work | evaluate | observe | sleep | blocked
  why TEXT NOT NULL DEFAULT '', action_id TEXT NOT NULL DEFAULT '', model_calls INTEGER NOT NULL DEFAULT 0,
  next_due_at REAL, next_code TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS source_observations(
  goal_id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, first_seen_at REAL NOT NULL,
  verdict TEXT NOT NULL DEFAULT '', PRIMARY KEY(goal_id, path, sha256));
```

**Writing reasons:**
- Events: `INSERT OR IGNORE`. The partial index only applies to `origin='event'`, so the redelivery guard does not block timers.
- Timers: `UPDATE ... SET state='superseded'` the pending timers of the **same `slot`**, then `INSERT` the new instance, in one transaction.
- Both recompute `wakeups` per the "Physical schedule" section, in the same transaction.

**Keeping the ledgers:**
- `wake_log`: at most 200 rows per goal, trimmed at write time. This is a review ledger, not used to prevent duplicates.
- `wake_reasons`:
  - `superseded` rows and `served` timers older than 30 days are deleted at write time;
  - events are kept until the goal ends, then deleted at the same time as the final status change, because an ended goal receives no more events.
- **Backup:** the first time the store is opened in 0.88.0 it copies `resonance.sqlite3.pre-a2.bak`, only once, like A1.

**`_wake`** gains `code`, `origin`, `source_ref`. The `reason` sentence in `wakeups` is still written for version 0.87 to read.

**`due_wakeups`:** takes the `observe` schedule of a paused goal (section 7). The `work` schedule of a paused goal is still skipped as before.

## 7. Gates: the work branch and the observe branch

`_gate` splits into two gates that share the identity and permission checks.

| Check | Work branch (`work`) | Observe branch (`observe`) |
|---|---|---|
| Goal still active | block | block |
| No assistant assigned | block, no schedule | stop observing |
| Assistant off, file missing, retired, version changed | block, `agent_recheck` timer | stop observing, report `monitoring_lost` (below) |
| User paused | block | **continue** |
| Understanding rejected | block | **continue** |
| Guard already hit | block | stop (already reported) |
| Waiting for handoff | block | **continue** |
| Read the guard | yes, then block if hit or `unknown` | yes |

**The observe branch** only runs `observe_guards`:
- Guard hit: `blocked`/`guard`, clear the schedule, report as in the MVP.
- Guard `unknown`: record the assessment, keep `guard_unknown` if the work branch has set it.
- Never publishes a product, calls a model, or serves a `work` reason.

**Switching the assistant off** (the review accepted the proposal, section 14):
- Stop observing and clear the `observe` schedule.
- A goal that has a guard reports `goal.monitoring_lost` **once per loss-of-permission episode**, idem by the assistant's off or file-missing event. The report lists the guards no longer being watched.
- The card keeps the line "Guards are no longer being watched" until they are watched again. It is not shown as safe.
- Turning on again: `wake_agent_goals` schedules `observe` right away with the reason `agent_enabled`. The work branch reads the guard in the gate before any effect.

**Pausing a goal:** different from switching the assistant off. It still observes by code, and a guard hit is still reported.

## 8. Flow of one wake

1. `tick` (section 11) takes at most `limit` due schedules and calls `advance(goal_id, {"kind": "wake"|"observe"}, deps)`.
2. `advance` holds the turn lease, runs `_reconcile` (settles an unfinished turn; a `work` turn that was interrupted becomes the error `interrupted`), then takes the reason snapshot.
3. Observe branch: section 7, write `wake_log`, schedule a new `guard_observe`.
4. Work branch: the decision order in section 4, then `_work_step` if the result is `work`, then `_settle`.
5. Write `wake_log`: seen, served, decision, `action_id`, number of model turns (0 or 1), next schedule. Recompute `wakeups` per section 3.

**`advance` takes events directly:**
- `reaction` still does nothing.
- `user_schedule` writes an event reason and then schedules.
- `start`, `user_message`, `resume` from old call sites become the corresponding reasons.

**Notices do not trigger themselves:**
- `drain_outbox` and `_resonance_notify` do not write `wake_reasons`.
- A notice from the assistant in chat is an `assistant` message and does not create a chat turn.
- Only words and actions of the user or the project owner produce new-news-class reasons.

## 9. One side owns the schedule: a narrower commitment

The review pointed out that blocking `javis_schedule` by a whole-turn flag (`goal_touched`) both wrongly blocks an independent reminder and misses a duplicate schedule created in another turn. A2 **drops** that block.

**A2 guarantees:**
- The schedule that pursues a goal lives only in Resonance's `wakeups`.
- Each goal has only one pending `work` timer and one `observe` timer.
- Two schedulers do not take the same schedule.
- Timers for a goal go through `javis_goal` (`user_schedule`).

**A2 does not guarantee against:** the user or the model creating an extra loop or a separate reminder for the same work.
- There is no host-checked link between a schedule and a goal, and a model is not used to guess whether two requests mean the same thing.
- `_RESONANCE_GOAL_HINT` adds one hint sentence (non-binding): "once work has become a goal, Jarvis 007 keeps the schedule itself; only create a reminder when it is a different task".
- Independent reminders and loops are used as before, in any order.

An explicit link from a schedule to a goal (a `goal_id` field checked by the host in `javis_schedule`) is a later item, out of scope.

## 10. API and UI

**`goal_view`** adds:
- `next_wake.code`;
- `observe`: `{"state": "on"|"lost"|"none", "next_at", "lost_reason"}`;
- `wakes_recent`: the 5 most recent `wake_log` rows (time, main reason code, decision, whether a model was called);
- `source_drift`: the hash and the time seen if waiting because of an out-of-band edit.

`next_wake.reason` (the raw sentence) is kept for the old page.

**The goal card** (`chat-resonance.js`, shared in the A1 assistant panel):
- "Next wake" shows a label by code, through `vi.json`/`en.json` (`resonance.wake.<code>`).
- A collapsible section "Recent wake-ups", for example "10/09 02:00 · periodic review · no model call".
- Labels and messages for `stalled`, `source_drift`, `deadline_passed`, plus the line "Guards are no longer being watched".

No settings field is added.

## 11. Performance

Not calling a model does not mean cheap for the server. A2 must keep these invariants:

- **No scanning before it is due.** Each 30-second beat has a single indexed query on `wakeups_due`. No file reads, no hashing, no reading the reasons of a goal that is not yet due.
- **A limit per beat:** `tick` handles at most `TICK_LIMIT = 3` schedules as in the MVP. Each wake only checks:
  - one product file (at most `PUBLISH_MAX_BYTES`, 1 MB);
  - the goal's own guard files (at most `GUARDS_MAX`, 5);
  - a fixed number of SQLite statements, independent of the number of goals.
- **Do not hold the event loop:** the code-only part of a wake (gate, file reads, hash, assessment, ledger writes) runs in `asyncio.to_thread`. Only the model turn is `await`ed on the loop, as today. Use the same timer-latency measurement as PR #592.
- **No cached hash in A2.** The same `(path, mtime_ns, size)` does not guarantee the same bytes: copying a file while keeping its timestamps is one example.
  - Every decision point reads the real bytes: detecting an out-of-band edit, permission to publish (`_publish`), `artifact_ref`, user confirmation, the guard.
  - The cost already has a ceiling: only when the schedule is due, at most one 1 MB product and 5 guard files per wake. If a cache is needed later, the cache is only a hint, has a schedule to re-verify the bytes, and is not used at the decision points above.
- **Latency when many schedules are due at once:** `due_wakeups` orders by `due_at`, so the oldest schedule is always taken first and none is starved.
  - With N schedules due at the same moment the last one is late by at most `ceil(N / TICK_LIMIT)` beats.
  - The "late by at most one beat" mark at a deadline only holds when no more than `TICK_LIMIT` schedules are due in the same beat. A2 does not raise `TICK_LIMIT` or the number of model turns to meet this mark.
- **No whole-app optimization pulled in.** The rest of VPS performance is in PR #592 and infrastructure work.

**Tests:**
- 200 goals, only 3 due: one beat reads no file of the other 197 goals (counted by patching `Path.read_bytes`/`open`).
- 50 goals due at the same time: exactly 3 per beat.
- Event loop timer latency while a beat handles 3 goals with 1 MB files: under 50 ms (compared with a control run directly on the loop). This is a measurement in a deterministic test environment, not a promise for every VPS.
- 10 schedules due at the same time: taken in `due_at` order, the last one late by at most 4 beats, none starved.
- A file that is unchanged and not yet due: not read in any beat.
- The number of SQLite statements per wake does not grow with the number of goals.

## 12. Rolling back and upgrading again

- **Rolling back to 0.87.0:** runs on the upgraded store.
  - The old version ignores the three new tables. `wakeups` is still valid.
  - Version 0.87 reruns the MVP policy: it may call the model at a review as before A2. The rollback guide states this clearly.
- **Upgrading again:** the reconciliation in section 3 settles the events that the old version already handled with a work turn that carried no reason.
- **The `pre-a2.bak` copy:** used like `pre-a1.bak` (`docs/dev/resonance-a1-migration.md`).

## 13. Acceptance (fake clock, no model)

Each case counts the number of engine builds (`engine_factory`) and reads `wake_log`.

**Beat and model turns**

| Case | Expectation |
|---|---|
| Met and waiting for the user, simulated 30-day run | 0 model turns. Every wake has a ledger row |
| Maintenance met, product unchanged, 30 days | 0 model turns. Review intervals grow 6 hours, 12 hours, 24 hours... up to 7 days |
| Two consecutive periodic reviews | Both run, two different reason rows |
| Snapshot has only `review`, `deadline`, observation or an unknown code, revision has no output | 0 model turns |
| Two turns that do not exceed the best mark | Automatic tries stop, `stalled`, reported once, goal stays active |
| A turn that drops and recovers to the old mark | Not counted as progress, streak not reset |
| A turn that exceeds the best mark | May try again |
| Feedback after `stalled` | Exactly 1 turn, streak recomputed |
| 1 turn left | Neither `retry_not_met` nor `error_retry` uses it. Feedback can use it |
| Transient error | At most 3 failed turns in total, then `blocked`, reported once |
| Permanent error | No automatic retry |
| Dies in the middle of a model turn | Reconcile, count one failed turn, retry under the ceiling |
| Deadline in 20 minutes | One check exactly at the deadline, late by at most one beat when not overloaded |
| Retry scheduled for minute 15, deadline at minute 20 | Both duties remain. A deadline check at minute 5 or 10 does not delete it and does not run the retry early. Minute 15 retries, minute 20 checks the deadline |
| Error backoff 1 hour, deadline in 20 minutes | The deadline check at minute 20 calls no model. The retry stays at the 1 hour mark |
| Retry and deadline check due together | One snapshot, one decision, both served |
| Restart while both duties exist | Both remain, at the exact times |
| Past the deadline and not met | `deadline_passed` reported once, not extended, no model call because of the deadline |
| Budget exhausted | `blocked`/`budget`, keep the reason, 0 model turns |

**Reason lifecycle**

| Case | Expectation |
|---|---|
| Feedback, then pause before the wake, then resume | The feedback is handled exactly once after resuming |
| Feedback, then switch the assistant off, then on again | As above |
| Feedback while the guard is `unknown`, the guard becomes readable again | As above |
| Observation runs while paused | The feedback stays `pending` |
| Feedback arrives while a model turn is running | Stays `pending`, schedule goes to `now` after the turn, handled next time |
| Redelivery of the same feedback (before and after serving) | One row, handled once |
| The user schedules a review in 1 hour, a check-only wake happens at second 30 | That wake does not see the scheduled item, calls no model, does not serve it. The physical schedule stays at the 1 hour mark |
| As above, restart in the middle | The scheduled time is kept |
| A retry comes due while the guard is `unknown` | 0 model turns, the retry keeps waiting. The schedule is the `guard_recheck` time; the beats in between do not pick the goal up again |
| A retry comes due while the assistant is off | As above, the schedule is the `agent_recheck` time |
| A retry comes due while paused or budget exhausted | No `work` schedule; the retry keeps waiting |
| Restart while parked | The schedule keeps the unpark time, no dense waking |
| Unparked, the retry is overdue | Considered exactly once under the ceiling; error and stall streaks not reset |
| Unparked, the retry is not yet due | Waits for the exact backoff time |
| A `check` timer comes due while blocked | Replaced by a re-check timer, or settled; no schedule kept in the past |
| Waiting for handoff, `source_drift` with an old overdue retry | The schedule is the chosen wait timer, the retry does not win |
| 5 parked goals with old retries, plus 3 ready goals | The next beat takes all 3 ready goals; parked goals take no slot |
| The scheduled time arrives | Opens a turn if the state and budget allow |
| Resending the same scheduled item | Not duplicated |
| Feedback and timers of an old revision, after a new revision exists | Settled `stale_revision`, no turn opened, the new revision's ceiling not reset |
| Dies after taking the schedule, before writing the ledger; restart | The reason remains, handled exactly once |
| Dies after `begin_action` | A served reason is not redone; reconcile by the error rule |
| Roll back to 0.87 which does work, then upgrade again | Old events settled by the turn without a reason, no extra model call |
| An assistant notice in chat | Produces no reason, no wake |
| Two parallel `tick`s on the same store | One takes it, at most 1 model turn |

**Out-of-band edit**

| Case | Expectation |
|---|---|
| A hand edit H1 breaks the criteria, 10 reviews | 0 model turns, one observation row, reported once, `source_drift` |
| Feedback is pending and then the file is hand-edited, simulated 30 days | 0 model turns. Wakes follow only `drift_recheck` (1, 2, 4... up to 24 hours), not every 30 seconds |
| As above, the goal has no guard, the user restores the file to the old mark | Detected at the next `drift_recheck`, the feedback handled exactly once |
| As above, new feedback arrives while waiting | Check immediately once; if still edited out of band, park again |
| As above, switch the assistant off and on, or restart | The feedback is not lost |
| Same path, size, mtime but different bytes | Recognized at the next check |
| Publish permission, `artifact_ref`, confirmation after the file's bytes change | Use the hash read from the current bytes, not an old hash |
| Edited again into H2 | A second observation row, reported once more |
| A hand edit that still meets the bar | Recorded, `healthy`, 0 model turns |
| The file is restored to the published mark | `source_drift` ends, 0 model turns |
| The file is deleted, the version in effect is from background work | Republish the stored output, 0 model turns |
| The file is deleted, the version in effect is from chat | `source_drift`, reported once, 0 model turns |
| Upgrade to A2 while feedback is unhandled | A `feedback` reason built from `goal_events`, handled exactly once |
| The `published` table after all the cases above | Not changed by observation |
| A guard on a hand-edited file | Still observes |

**Guard**

| Case | Expectation |
|---|---|
| Paused, guard hit | Detected, `blocked`/`guard`, reported |
| Waiting for confirmation, guard hit | Detected |
| Understanding rejected, guard hit | Detected |
| Switch off an assistant that has a guard | `monitoring_lost` once, the card shows "Guards are no longer being watched". A second switch-off after turning on again: reported once more |
| Turn on again | Observe right away, read the guard before any effect |
| Guard `unknown` then readable again | Checked by code, 0 model turns while it cannot be read |

**Independent schedules**

| Case | Expectation |
|---|---|
| Create goal X and then reminder Y in the same turn | Y can be created |
| Create reminder Y and then goal X, in another turn | Both remain intact |

**Performance:** the cases in section 11.

**Rollback:** the real 0.87.0 code runs on the upgraded store, like the A1 rollback test.

The MVP tests that assert the old behavior (`no_source_uses_bounded_review`, the 15-minute retry repeating until the budget runs out) are updated to the new policy. Each change is recorded in the handoff; no case is deleted.

## 14. Default decisions

Proposed by the round 1 review, matching the design's proposal. The project owner can change them.

1. **Switching the assistant off:** stop watching guards, report once per loss-of-permission episode, the card shows clearly that watching has stopped. Pausing a goal still observes (section 7).
2. **Two turns without progress:** stop automatic tries and move to waiting, without concluding failure (section 4). No settings field is added.
3. **A per-assistant budget:** not done in A2, keep the existing ceilings.

## 15. Changes after the review rounds

### After review round 1

Review: `exports/reviews/PR-590-final-and-PR-593-A2-design-review.md` (outside git), at `7504bf6a`.

| Point | Fix |
|---|---|
| P1-1: a hand edit triggers the model without permission to publish | Removed `source_changed` from the new-news class. Separated the observation mark (`source_observations`) from the file-replacement mark (`published`). An out-of-band edit is only recorded, reported once per hash, and waited on; no model call (section 5) |
| P1-2: consuming reasons when blocked | `pending`/`served`/`superseded` lifecycle, snapshot by id. Blocked serves nothing. First steps and new news are only served by a work turn or a conclusion that nothing needs doing. The observe branch has its own gate and does not touch `work` reasons (sections 3, 7) |
| P2-1: the duplicate guard key blocks a later periodic instance | Separated events (partial unique index by the source's `source_ref`) from timers (a fresh id each time, a new timer replaces the old one). No TTL is used to prevent duplicates (sections 3, 6) |
| P2-2: `goal_touched` blocks the whole turn | Removed the block. Narrowed the commitment to the goal's internal schedule; linking schedules to goals is left for later (section 9) |
| Counting progress | Best mark within the revision, oscillation does not reset the streak; a stall is waiting, not failure (section 4) |
| Reserve turn and errors | One common rule for every automatic retry; three failed turns in total (section 4) |
| Near a deadline | Clear priority order, a single check exactly on time, report once after the deadline (section 4) |
| Unknown reasons | Only a reason can open a model turn; an unknown code belongs to the check-only class (sections 3, 4) |
| Performance | New section 11: no scanning before due, a limit per beat, runs off the event loop, measurable test cases |

### After review round 2

Review: `exports/reviews/PR-593-A2-design-r2-e95a3260-review.md` (outside git), at `e95a3260`.

| Point | Fix |
|---|---|
| P2-1: `user_schedule` runs before the scheduled time | Every reason has a `due_at` that is the eligibility time. The snapshot and the schedule rely only on `due_at`, for events too. A future-scheduled item has an id right away but does not enter the snapshot and does not pull the schedule (section 3) |
| P2-2: a deadline check replaces a retry | Timers are split into the duties `retry`, `check`, `observe`; a new timer only replaces one of the same duty. The physical schedule is computed from all pending duties. There is a rule for the same moment (sections 3, 4) |
| P2-3: waiting for a hand-edited file wakes every 30 seconds | Events are parked when `blocked` or `source_drift`, and do not pull the schedule to `now`. The recovery path is a code `drift_recheck`, 1 hour doubling to 24 hours; a new event checks immediately once; the card says it clearly (sections 3, 5) |
| P2-4: a hash cached by metadata | Removed the cached hash from A2. Every decision point reads the real bytes (section 11) |
| Revision note | Reasons record the source `revision`; reasons of an old revision are settled `stale_revision` (section 3). Reconciliation on upgrade only settles events that predate the moment the old turn **started** |
| Latency note | Taken by `due_at`, no starvation; late by at most `ceil(N / TICK_LIMIT)` beats; the one-beat mark only holds when not overloaded; 50 ms is a test environment measurement (section 11) |

### After review round 3

Review: `exports/reviews/PR-593-A2-design-r3-fe92e753-review.md` (outside git), at `fe92e753`.

| Point | Fix |
|---|---|
| P2: an overdue retry timer pulls the schedule into the past when blocked | One principle for events and timers: when parked, the physical schedule only takes the unpark timer. A retry timer keeps its record, time and streak; when unparked it is reconsidered under the current ceiling. A `check` timer that comes due while blocked is replaced or settled (section 3) |

## 16. Code plan (after the design passes review)

1. `resonance_heartbeat.py`: `decide` and table tests.
2. Store: three side tables, `_wake` by source and duty, physical schedule, reason lifecycle, parking events, reconciliation on upgrade, the `pre-a2` copy, `due_wakeups` for `observe` when paused.
3. `advance`: snapshot, two gates, `decide`, ledger writes, out-of-band edits, `stalled`, `deadline_passed`, `monitoring_lost`, run the code part in a worker thread.
4. `goal_view`, the card, i18n, the hint sentence in `_RESONANCE_GOAL_HINT`.
5. The section 13 acceptance tests, fix the MVP tests to the new policy, the rollback to 0.87.0 test.
6. Guide: the A2 section in the usage and rollback document.
