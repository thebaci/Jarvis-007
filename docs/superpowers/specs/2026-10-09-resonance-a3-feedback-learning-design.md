# Resonance A3: the feedback loop and verified learning

**Status:** the design PASSED review round 3 (`d6239d54`, report `exports/reviews/PR-598-A3-r3-d6239d54-review.md`, outside git). Implemented on the same branch, awaiting code review; implementation notes in section 19. Round 1 (`a6418e45`): 1 P1, 2 P2, D4 not met (section 17). Round 2 (`ef56b61f`): 2 P2 on the call-hold ledger (section 18). Branch `claude/resonance-a3-feedback-learning`, version number reserved: 0.89.0.

- **Base:** `main` at `83bff6bc` (0.88.1). A1 shipped as 0.87.0 (`fdfec7c5`), A2 shipped as 0.88.0 (`c101d108`).
- **Roadmap:** [agent scope roadmap](2026-10-08-resonance-agent-scope-roadmap.md), section 6.
- **Record #597:** the documentation part of PR #597 (A1/A2 release minutes) was merged into this branch, dropping #597's own VERSION and CHANGELOG.
- No model is called to produce this design.

## 1. Goals and out of scope

**Goal:** turn sourced feedback into small, verified changes, as a loop:

> record sourced feedback → propose a small change → try it within budget → compare against the old way → apply within the verified scope, or keep the old way → keep observing.

A3 has two separate learning lanes, because the two kinds of change have different yardsticks:

| Lane | What changes | Signal that opens a proposal | How it is compared with the old way | Who decides to apply | Model calls |
|---|---|---|---|---|---|
| **P (presentation)** | How the host writes and reports the assistant's notices: full or brief, with or without a notification sound | Reaction on the assistant's notice | Preview of the old and new versions of the SAME notice, built by the host from a fixed template | The user clicks Apply | 0, forever |
| **M (method)** | The M5 method (`METHODS`) of one goal, within that exact revision | Objective stall: the criteria the host checks make no further progress (A2) | The M5 `compare_methods` trial keeps its rules (including a separate holdout case), and the host scores both sides with the same yardstick | The host, only when the trial comes out `eligible` | The trial inside the exploration share, plus one deliverable-making call with the new method held in advance, plus the reserve call; if any is missing, no trial |

**Unchanged:**
- M4 feedback (That's right / Not quite, Meets the bar / Needs changes) keeps its meaning and its write path. A3 only adds the source message to the data recorded alongside.
- M5 keeps its rules: `METHODS` declared in advance, scenario sets with a tuning set and a separate holdout, the trial reserves budget before calling, the gate is checked before each call and inside the apply transaction, scope is goal + revision, `revert_method`. A3 only adds to M5: the lesson identity in the two reserve and settle transactions (section 6.4), the held deliverable-making call (section 6.3), and a per-revision prompt for each scenario (section 6.2).
- A2 is unchanged: wake reasons, classes, lifecycle, `decide`. A3 adds exactly two reason codes (`method_trial`, `method_followup`) and two classes (`TRIAL`, `FOLLOWUP`) (section 6.3).
- Existing tables keep their columns. A3 only adds new tables (A1's rule).

**Out of scope:**
- Reactions on ordinary chat, on the assistant's replies in an agent session, and on external channels (Telegram, Zalo, Lark). Only notices written by the host accept reactions (section 3.2).
- Carrying a learned method over to another goal or another revision ("lesson transfer"). It needs holdout scenario sets across several goals; left for later.
- Using the trial's output as the goal's deliverable (section 14, D5).
- Auto-generating new methods or new presentation templates. Every choice is an entry declared in advance in code.
- A daily digest. "Less disturbance" in A3 only means turning off the notification sound for optional notice types.
- The existing `JAVIS_LESSON` mechanism (the assistant writing lessons itself into `memory/agents/<slug>/MEMORY.md`) is unchanged and is not used for A3: lessons there have no scope, evidence or revocation path under A3's rules.

## 2. Current state and the gap (code at `83bff6bc`)

| Already there | Where in the code | Gap A3 fills |
|---|---|---|
| M4 feedback is written to `goal_events` (`feedback.*`), owner only, revision CAS, dedupe key per click | `resonance_store.record_feedback`, `resonance.apply_feedback`, `POST /goals/{id}/feedback` | The source message is not recorded; there are no reactions |
| "Needs changes" with a note enters the next work turn through the `not_met` reason | `resonance._human_verdict`, `_work_prompt` | Enough for fixes within a revision; A3 does not change it |
| M5 trial: reserve budget, run both sides, score with `artifact_contract`, apply with CAS, revert | `compare_methods`, `begin_experiment`, `finish_experiment`, `_method_change_blocked`, `revert_method` | **Nothing calls `compare_methods` outside tests.** The caller has to supply the scenario set |
| Objective stall: two consecutive turns that do not beat the bar stop trying and wait | `resonance_heartbeat.auto_allowed`, the `goal.stalled` branch in `_settle` | There is no "try another way" step |
| Goal notices enter the chat box with a `report_receipts` receipt in the same transaction | `drain_outbox`, `main._resonance_notify`, `sessions.report_receipts` | There is no feedback button on notices |
| `_notify_owner(quiet=True)`: still enters the chat box and inbox, only no sound and no browser push notification | `main._notify_owner` | Used as the "less disturbance" value of lane P |
| `advance` skips `kind="reaction"` | `_advance_prepare` | Unchanged: a reaction never goes through `advance` |

**Actual budget:** a goal has 6 calls by default (`GOAL_DEFAULT_CALLS`), the 50% exploration share is 3 calls, the A2 reserve call is 1. Under `heartbeat.v1` a stall happens after 3 successful work turns at the earliest. At that point 3 calls remain. A full lane M cycle under M5's rules needs a trial with a separate holdout case (4 calls), one deliverable-making call with the new method, and the reserve call: 6 calls remaining in total, so a budget of at least 9 when the stall comes at turn 3. **A default 6-call goal will always skip lane M** (recording `skipped/budget`, 0 model calls). A3 states this limit plainly instead of loosening the evidence rules to fit the budget (section 14, D4). Lane P costs no calls, so it runs for every goal.

## 3. Four kinds of signal

### 3.1 Meaning and canonical source

| Signal | Canonical source | Used for | Never inferred |
|---|---|---|---|
| **Reaction** on the assistant's notice (thumbs up; thumbs down with a reason Too long / Too frequent / Unclear) | New table `reactions` (current value) and `reaction_log` (history) | Lane P: proposing how to report | Goal met or failed, method change, permissions, budget, wake schedule |
| **That's right / Not quite** | `goal_events` kind `feedback.goal_fit_*` (M4, unchanged) | The understanding of that exact revision. "Not quite" blocks every lane M trial and apply (already in `_method_change_blocked`) | Deliverable accepted |
| **Meets the bar / Needs changes** | `goal_events` kind `feedback.outcome_*` (M4, unchanged), tied to `criterion_id` and `artifact_ref` | The `human_confirmation` criterion of that exact deliverable; "Needs changes" opens a fix turn within the revision (M4/A2) | Passing a guard, replacing an objective check result, opening a lane M trial (section 14, D6) |
| **Objective evidence and cost** | `assessments`, `evidence_links`, `heartbeat_state` (A2), `experiments` (M5), `calls_used` | Lane M: stall detection, scoring the trial | Crediting an action when there is no comparison |

There is no total score. Each signal enters only its own "used for" cell, and each read path in the code reads only its canonical source.

### 3.2 Required data for each signal

Every A3 signal records: the source message, the authenticated responder, the assistant, the brain, and the goal, revision and deliverable where relevant.

| Field | Reaction | M4 feedback (added in A3) |
|---|---|---|
| Source message | `session_id`, `message_id`, `report_key` taken from `report_receipts` | `source_ref` = `msg:<session>:<id>` of the message that holds the card, if the dashboard sends it; checked like a reaction. Left empty when missing (old dashboard), and M4 works as before |
| Responder | `Principal.by` of the brain owner | as M4 |
| Assistant | `agent_key` and `agent_config_version` at write time, read from `goal_agents` and `resonance_agents` | as reaction |
| Brain | the principal's `brain_id`; the session must belong to this brain | as M4 |
| Goal, revision | `goal_id` from the receipt; `revision` from the outbox payload of that message (the revision at report time, not the current revision) | as M4 (CAS on the current revision) |
| Deliverable | `content_sha` of the message content at click time | `artifact_ref` (M4, already there) |

**Only notices written by the host accept reactions.** A message is valid when a `report_receipts` row points at exactly that `message_id`, `role` is `assistant`, the key has the form `outbox:<id>`, and the goal belongs to an assistant (`goal_agents`). Ordinary chat, a model's reply, or a `JAVIS_RESONANCE` block the model wrote itself has no receipt, so it is rejected (400). This is how A3 keeps ordinary chat out of the learning loop: no valid source, no signal.

### 3.3 Replacing, revoking, resending, restarting

- **One person, one message, one current value.** Unique key `(brain_id, session_id, message_id, responder)`. The API means **set the value**: each request carries an explicit `value`; a new request (new nonce) overwrites the current value and increments `seq`, even when the value is unchanged. Revoking means sending `value='none'`. The rule "clicking the button that is already lit revokes it" is a **UI** rule: the page sends `none` itself, and the API never inverts on its own. The full history lives in `reaction_log`.
- **Idempotent resend.** Each click carries a `nonce` (as in M4). `reaction_log` has the unique key `(reaction_id, nonce)`: resending the same request changes nothing and returns the current state.
- **No score multiplication.** The learner only counts the number of DIFFERENT messages whose current value meets the condition (section 5.3). Clicking ten times on one message is still one message. There is no accumulating score column.
- **Restart** changes nothing: all state is in SQLite; the learner is a pure function of that state; a proposal has a unique key for the open state (section 7), so rerunning never produces a duplicate proposal.

### 3.4 Late feedback, edited or deleted sources

| Case | Handling |
|---|---|
| Reaction on a notice from an old revision | Recorded, tagged with that notice's revision. Lane P does not depend on the revision, so it still counts. No effect on the goal |
| Reaction on a notice of a goal that is finished or cancelled | Recorded normally, still counts for that assistant's lane P |
| Reaction while the assistant has Resonance turned off | Recorded (passive, no effect). The learner creates no proposal for a disabled assistant; the proposal is reconsidered at the next reaction write after it is turned on |
| Assistant deleted (`status` other than `active`/`missing`) | Rejected with 409; there is no subject to receive the lesson |
| Message deleted (receipt lost through `ON DELETE CASCADE`) | The reaction becomes an **orphan**: the learner does not count it. An open proposal that loses enough messages expires on its own. A lesson already applied stays (the user decided), and the list shows "source deleted" |
| Message content changed since the `content_sha` at click time | Same as a deleted message: orphan, not counted |
| M4 feedback on the wrong revision or the wrong deliverable | M4 unchanged: 409, not recorded |
| M4 feedback for a goal that is no longer active | M4 unchanged: 400, not recorded |

The orphan check runs lazily (when the learner reads), only on the messages within one assistant's 30-day window, with one query by primary key of `report_receipts` and `messages`.

### 3.5 Silence

No reaction means unknown. The learner does not read absence: no rates, no penalties, and an expired proposal is never treated as "the user agreed". When a proposal expires, the old way stays.

## 4. A3's invariants

1. **A reaction opens no model call and changes no schedule.** The reaction write path does not call `advance`, does not write `wake_reasons`, does not touch `wakeups`, and does not build an engine. The learner runs as code inside the reaction write transaction.
2. **Feedback does not make a goal met.** Only `evaluate_artifact` against criteria and evidence (M3), and an M4 confirmation for the right criterion and the right deliverable, can change a criterion's result. No A3 path writes `assessments` or changes the goal's `status`.
3. **Learning opens no gate and grants no permission.** No A3 path writes the assistant's file, `resonance_agents`, `config_version`, the brain switch, guard, pause, budget (`budget_calls`), deadline or criteria.
4. **Less disturbance does not hide mandatory warnings.** Lane P can only change notices on the optional list declared in code (section 5.1). Mandatory notices are always full and always ring. Lane P does not touch the guard check schedule, the deadline schedule or the review schedule.
5. **Apply only within the verified scope.** Lane M: exactly the trial's goal + revision, through M5's `effective_method`. Lane P: exactly that assistant in that brain.
6. **A losing or unclear candidate keeps the old way.** An expired proposal, a skipped one, or a trial that is `rejected` or `inconclusive` changes nothing.
7. **Revoking stops applying immediately.** Lane P: the next notice build already reads the new state. Lane M: `revert_method` in the same transaction as marking the lesson.

## 5. Lane P: how notices are presented

### 5.1 Declared entries

Two keys, each with a fixed set of values in code (`PRESENTATION`, next to `METHODS`):

| Key | Default | Other values | Applies to notice types |
|---|---|---|---|
| `notice_detail` | `full` (the current sentence from `notice_text`) | `brief`: one short sentence from a fixed template, keeping the goal name and the deliverable link; the goal card still comes along | `goal.succeeded`, `goal.maintained` |
| `notice_ping` | `ping` | `quiet`: the notice still enters the chat box and inbox, only without a notification sound and without a browser push notification (`_notify_owner(quiet=True)`) | `goal.maintained` |

**Mandatory notices** (always `full`, always `ping`, lane P never touches them): `goal.guard`, `goal.monitoring_lost`, `goal.deadline_passed`, `goal.publish_conflict`, `goal.failed`, `goal.blocked`, `goal.waiting_human`, `goal.stalled`, `goal.discovery_done`, and the new `goal.method_changed` notice (section 6.6). This list is a constant in code; a test locks it.

Why the optional list is narrow: only the two types above do not ask the user to do anything. Every other notice is a warning, a question waiting for the user, or a report of a behavior change.

### 5.2 Lane P lesson lifecycle

```
proposed ──(owner Apply)──▶ active ──(owner Revoke)──▶ revoked
   │                          └──(owner applies another value for the same key)──▶ superseded
   ├──(owner Dismiss)──▶ dismissed
   ├──(past 14 days, or enough messages lost to orphaning)──▶ expired
   └──(at Apply time, the base configuration has changed)──▶ stale
```

- **Compared with the old way:** the proposal comes with a preview built by code from the very notice that received the feedback: the old sentence and the new sentence side by side, with the note "mandatory notices do not change". No model call.
- **Two separate latches** for each key, each scope: at most **one** `active` lesson (the configuration in use) and at most **one** pending proposal (`proposed`, or `trial_pending`/`trialing` in lane M). The two latches are two separate partial unique indexes (section 7.1). This way a configuration in use set to `brief` and a proposal to go back to `full` can exist at the same time; the configuration in use is never disabled just to make room for a proposal.
- **Base of a proposal:** each proposal records `base_lesson_id` (the `active` lesson when the proposal was created; empty if the default was in use then) and `from_value` (the value at that time).
- **Apply:** owner only, in one transaction:
  1. the proposal is still `proposed` (CAS on the `expected_status` and `expected_updated_at` the card is seeing);
  2. the current `active` lesson for the key is exactly `base_lesson_id` and still carries `from_value` (or there is no `active` lesson when `base_lesson_id` is empty);
  3. the base lesson becomes `superseded`, the proposal becomes `active`.

  If condition 2 fails (the owner revoked the base, or applied another value), the proposal becomes `stale` and the call returns 409 with the current configuration; it is never applied blindly. Applying a proposal whose `to_value` is the default value (for example going back to `full`) still creates an `active` lesson carrying that value: this is a clear choice by the owner, with a source, and revocable like any other lesson.
- **Dismiss:** the proposal becomes `dismissed`; the configuration in use is unchanged.
- **Revoke:** the `active` lesson becomes `revoked`; the key goes back to the default. A pending proposal based on this base becomes `stale` when the owner clicks Apply. From `learning.v2` (after the pilot), Revoke blocks the same (assistant, key, value) proposal for 14 days, like Dismiss.
- **Effective lesson** of an assistant = the `active` lesson of each key (at most one). With none, use the default.

### 5.3 Lane P learner (`learning.v2`, pure function)

Input: the non-orphan reactions of one assistant over 30 days, current values; the existing lane P lessons. Output: no proposal or one proposal.

| Proposal | Condition |
|---|---|
| `notice_detail: full → brief` | At least **2 different messages** of an applicable type with current value `down` + `too_long`; the key is at `full`; no open proposal, and no `dismissed` or `revoked` lesson within 14 days for the same key and value of this assistant |
| `notice_ping: ping → quiet` | At least 2 different `goal.maintained` messages with `down` + `too_often`; same remaining conditions |
| Revert proposal (`brief → full`) | At least 1 message that was built as `brief` with `down` + `unclear` |

`up` and `down` without a reason are recorded and shown in the statistics, but open no proposal: without a reason there is no way to know what to change. The learner never applies on its own. A revert proposal is also only a proposal; the Revoke button is always available.

### 5.4 Applying to the reporting path

`drain_outbox` reads the effective lesson of the assistant that owns the goal right before building the sentence and sending the message (one indexed query, section 11), then passes `presentation` into `notice_text` and the `quiet` flag into `notify`. The outbox payload and the receipt also record the `presentation` that was used, so a revert proposal knows which messages were `brief`. Mandatory notices skip this step.

## 6. Lane M: methods when there is an objective stall

### 6.1 When there is a proposal

A lane M proposal is created **in the same transaction** in which A2 writes `waiting/stalled` (the stall branch of `_settle`), when all of these conditions hold:

1. The stall reason is `stalled` (two consecutive turns that do not beat the bar on the criteria the host checks), not `reserve`.
2. The current revision has at least one `artifact_contract` criterion with `min_chars` or `must_contain`, meaning the host can score it itself.
3. There is a candidate under the `learning.v1` mapping table: if the effective method is `work.v1`, the candidate is `work.checklist.v1`. Other methods have no candidate yet (no proposal).
4. No trial exists yet for exactly this revision and exactly this baseline and candidate pair (table `experiments`).
5. A valid scenario set exists under M5's rules, including a separate holdout case (section 6.2).
6. There is enough **full-cycle budget** (section 6.3): the trial, one deliverable-making call with the new method, and the reserve call.
7. The assistant is on, the goal is active, not paused, no guard latch, and the understanding is not marked "Not quite".

When the conditions are met, write a `trial_pending` lesson and a wake reason event `method_trial` (`source_ref = lesson:<id>`, `due_at` = now). If condition 2, 5 or 6 is missing, write a `skipped` lesson with reason `untestable`, `no_holdout` or `budget` so the user can see why nothing was tried; 0 model calls. If any other condition is missing, write nothing.

"Needs changes" (a criterion scored by the user) does not open a lane M proposal: the host cannot score a trial for that criterion, so there is no evidence to compare. The "Needs changes" note still goes into the fix turn within the revision as in M4/A2 (section 14, D6).

### 6.2 Scenario set: keeping M5's rules

A3 does **not loosen** M5's evidence rules: the scenario set must have at least one tuning scenario (`tuning`) and one separate holdout scenario (`holdout`). No fake scenarios, and no running the same input twice and calling it a holdout.

The host builds the set from the goal's own record, with nobody typing anything in:

- **Tuning:** the current revision. `input` = the user's words in that revision; `expect` = the parameters of the first `artifact_contract` criterion that has parameters.
- **Holdout:** the nearest **earlier** revision of the same goal whose host-scored criteria set (the list of `artifact_contract` criteria with the same parameters, normalized) is **identical** to the current revision's. `input` = the user's words in that revision. At most one holdout scenario in A3.
- Each scenario carries its own source `revision`; the scenario's model call builds its prompt from that revision's record (understanding, constraints), while the yardstick is the shared criteria set pinned by `rubric_hash`, as in M5. This is the only change A3 needs in M5 (`_trial_run` receives the revision record per scenario); the conclusion rule `_trial_verdict` stays unchanged.
- **Inputs must really differ.** A different revision number is not enough. The host computes a `prompt_input_hash` for each scenario from exactly the part of the prompt build that is outside the criteria (understanding, user's words, constraints, assumptions; whitespace normalized; ids, labels, edit reasons and timestamps are not counted). An earlier revision whose `prompt_input_hash` equals the tuning set's cannot be chosen as the holdout; the host goes on to older revisions within the `M_HOLDOUT_SCAN` limit.
- **Pinning:** the trial payload records the `prompt_input_hash` and the hash of the revision record of each scenario, along with the `rubric_hash`.
- **Historical revisions are used only to build prompts.** Execution rights, budget, action, the turn gate and the apply transaction all belong to the trial at the current revision; a historical revision is never passed into those gates. Old user words are only data, not commands acting on the brain: the trial still only produces text inside the trial's work area and publishes no file.
- With no valid earlier revision, the lesson is `skipped/no_holdout`, 0 model calls.

**Evidence level:** `eligible` means that in exactly this attempt, the candidate passed the tuning scenario that the old method did not pass, and did not regress on the holdout scenario. Each side generates only once per scenario, so the conclusion cannot fully rule out variation between two generations. That is why the apply scope is only the current goal + revision (as in M5), there is a way back, and the deliverable-making call that follows is still scored by the host like any work turn. The goal + revision scope is M5's own scope, not a new protection compensating for the evidence.

**Practical consequence:** a valid holdout scenario exists only when the goal has had its understanding revised while keeping the host-scored criteria unchanged. This case is rare, so lane M will often record `skipped/no_holdout`. A3 accepts this limit; other scenario sources (the owner adding their own, or A5's reviewer) come later and must pass the same M5 rules.

### 6.3 Full-cycle budget and wake reasons (`heartbeat.v2`)

**Full-cycle budget**, checked when the proposal is created and checked again in the trial's reserve transaction:

- `trial_cost` = 2 × the number of scenarios that can run (A3: 2 × 2 = 4 calls);
- exploration share: `explore_used + trial_cost <= int(budget_calls × EXPLORE_SHARE)` (M5 rule);
- total: `calls_used + trial_cost + 1 + AUTO_RESERVE_CALLS <= budget_calls`. The 1 is the deliverable-making call with the new method (section 6.5).

Example: a stall after 3 work turns needs a budget of at least 9 (and an exploration share of at least 4, meaning a budget of at least 8). A default 6-call goal always records `skipped/budget`. A3 never asks for more or raises the budget on its own.

**Reserving the deliverable-making call:** the `begin_experiment` transaction reserves `trial_cost` exploration calls (as in M5) **and** one deliverable-making call at the same time. The deliverable-making call is recorded in the new table `call_holds` (section 7.1) and is added to `calls_used` at reservation time, so the goal ceiling and the global ceiling `JAVIS_RESONANCE_CALL_CEILING` already count it. It is not added to `explore_used`. If the trial is not applied, the reserved call is returned in the `finish_experiment` transaction.

**Policy `heartbeat.v2`** (bumps `POLICY_VERSION`; old `wake_log` rows keep their own version) adds two event codes:

| Code | New class | Opens a turn when | Cost |
|---|---|---|---|
| `method_trial` | `TRIAL` | Lesson is `trial_pending`, full-cycle budget is sufficient | `trial_cost` + reserve 1 |
| `method_followup` | `FOLLOWUP` | A `held` call exists for exactly this goal, revision and trial; the lesson is `active`; the effective method is exactly the candidate | Uses the call already held, reserves no more |

- Order in `decide`: met or just waiting for the user → `NEW` → `START` → **`FOLLOWUP`** → **`TRIAL`** → `AUTO`. A new message from the user always wins.
- `waiting/stalled` is **not** a parked state in A2 (parking covers only pause, `blocked`, "Not quite", `source_drift`, waiting for handoff, assistant off). So the event reason of a stalled goal is served normally, and `FOLLOWUP` opens exactly one work turn.
- When a goal is in a parked state, both reasons are parked like any other reason (only `UNPARK_CODES` count) and do not run; the held call stays held until the park lifts or until it is returned (section 6.6).
- A new message from the user before the **trial** runs: the fix turn runs with the old method; the A2 streak resets so the stall condition no longer holds; the `method_trial` reason is settled as `superseded`, and the lesson as `skipped/new_feedback`.
- A new message from the user **after apply**, before the `FOLLOWUP` turn: the fix turn **takes over** the held call (section 6.8) and runs with the new method (same revision), which is exactly the planned deliverable-making call, now with the feedback added. No additional call is reserved, so no ceiling blocks it; the `method_followup` reason is settled as `superseded`.
- The review schedule and the deadline are still `CHECK`: they open no model call, even after apply.

### 6.4 Running the trial and settling the lesson state in transactions

The `trial` decision goes through exactly the A2 wake frame: the prepare phase on a worker thread holding the turn lock, the model phase on the event loop, `_finish_wake` releasing the lock and writing `wake_log` (`decision='trial'`, `model_calls` = the number of calls counted). The body of `compare_methods` is split out into a function that accepts an already-held turn lock; the public `compare_methods` still takes the lock itself as before and passes no lesson (M5 behavior unchanged).

All M5 gates stay: reserve before calling, pin the assistant's code and version, `_trial_gate` and `agent_gate` before each call and right before concluding, `_method_change_blocked` in the apply transaction, refund calls that did not start.

A3 adds the **lesson identity** to two of M5's transactions, because a gate outside the transaction always leaves a gap before the transaction:

- **`begin_experiment(..., lesson_id)`:** in the same reserve transaction, `UPDATE lessons SET status='trialing', experiment_id=? WHERE id=? AND status='trial_pending' AND goal_id=? AND revision=?`. If it does not affect exactly one row, no trial is created and no call is reserved.
- **`finish_experiment(..., lesson_id)`:** in the same settle transaction, **before** `_set_method`:
  - `UPDATE lessons SET status='active' ... WHERE id=? AND status='trialing' AND experiment_id=? AND goal_id=? AND revision=?`, only when the verdict is `eligible` and `_method_change_blocked` lets it through.
  - If it does not affect exactly one row (the owner already clicked Dismiss, or the lesson has changed): the method does not change; the trial settles as `inconclusive` with reason `lesson_dismissed`; the owner's Dismiss decision is kept; calls already made still count; calls that did not start are refunded; the held deliverable-making call is returned.
  - Any verdict other than `eligible`: the `trialing` lesson becomes `rejected` or `unknown` through the same CAS; if the lesson is already `dismissed`, it stays `dismissed`. The held call is returned.

**Order versus Dismiss.** Every write transaction in the store is `BEGIN IMMEDIATE`, so two transactions on the same lesson always have a clear commit order:

| Commits first | Result |
|---|---|
| Dismiss (`trial_pending`/`trialing` → `dismissed`) | The next turn gate stops the trial; if the trial has already reached the settle step, the CAS in `finish_experiment` fails: the method stays, the trial is `inconclusive/lesson_dismissed` |
| Apply settle (`trialing` → `active`) | The stale Dismiss request gets 409 with the `active` state; the UI changes the button to "Revert method" (revoke, section 6.6) |

Dismiss does not require `expected_updated_at` to match (the lesson went from `trial_pending` to `trialing` while the owner was looking at the card); it only requires that the current state be `trial_pending` or `trialing`.

### 6.5 Outcome and the deliverable-making call

| M5 verdict | Lesson | Method | Held call | Next |
|---|---|---|---|---|
| `eligible`, lesson CAS and `_method_change_blocked` let it through | `active`, goal + revision scope, records `experiment_id` | Changed in the same `finish_experiment` transaction (M5) | Keep (`held`) | Write the `method_followup` reason in the same transaction |
| `eligible` but blocked (M5) | `unknown` | Keep | Return | None |
| `eligible` but the owner already clicked Dismiss | `dismissed` (kept) | Keep | Return | None |
| `rejected` | `rejected` | Keep | Return | The card shows "tried, the old method stays" |
| `inconclusive` | `unknown` | Keep | Return | The card shows the reason |

**The deliverable-making call (`FOLLOWUP`):** an ordinary A2 work turn, running exactly once:

- This turn's `begin_action` **uses the held call** (`held` → `attached` by CAS in the same transaction that writes the intent, with no addition to `calls_used`, a net increase of 0 when checking the ceiling) instead of reserving a new call. The held call becomes `used` when the action settles a result the model may have produced; if cancelled before the engine, it goes back to `held` to run again (section 6.8). When a held call is already `used`, the reason is settled and does not run a second time, even after a restart.
- The prompt uses the effective method (the candidate), the existing deliverable and the unmet criteria, like every fix turn.
- The deliverable is published through the existing handoff gate: it does not overwrite a version the user edited by hand (A2 section 5), and the guard, assistant permissions and confirmation of exactly the right `artifact_ref` (M4) stay unchanged.
- The result is scored by the host like any turn (`evaluate_artifact`). This turn counts toward the existing A2 streak and does not reset it: beating the old bar is progress; if it does not, the goal goes back to `waiting/stalled` and waits for feedback.
- If the process dies after the intent is written: A2's reconciliation settles the half-done turn like any work turn, then the hold reconciliation changes it to `used` (section 6.8). No call is issued again. A2's automatic retry is still subject to the reserve-call rule, so it does not spend more on its own.

**Total full-cycle cost** with the example budget of 9 and a stall after 3 turns: 3 + 4 (trial) + 1 (deliverable) = 8; exactly 1 reserve call is left for the user's feedback.

The trial's output is not published as the deliverable (D5); the deliverable always comes from the deliverable-making call.

### 6.6 The `goal.method_changed` notice

Mandatory, always full, sent **after** the deliverable-making call (or when the held call is returned before it runs). Content:
- which method was tried, on how many scenarios, and each side's result;
- applies only to the current understanding;
- the total number of calls spent;
- the result of the deliverable-making call with the new method (which criteria passed or did not), or the reason the deliverable was not remade;
- a Revert method button on the card.

Dedupe key `method_changed:<experiment_id>`. This notice does not change the wake schedule.

### 6.7 Revoking, going out of scope, returning the held call

| Event | Lesson | Method | Held call, `method_followup` reason |
|---|---|---|---|
| Owner clicks "Revert method" | `revoked` | `revert_method` (M5, unchanged) | Return the held call if still `held`; settle the reason. One transaction |
| Understanding revised (new revision) | `out_of_scope`, written in the `revise` transaction | `effective_method` automatically goes back to the default (M5) | Return the held call; the reason belongs to the old revision and is dropped. The method just learned is **not** used for the new revision |
| Goal cancelled | state kept for review | not relevant | The held call is recorded as `released` so the ledger matches; the reason is deleted along with the goal (A2) |
| New message from the user on the same revision before the `FOLLOWUP` turn | stays `active` | the new method | The fix turn takes over the held call (`attached`), no additional reserve; the reason is settled as `superseded` (section 6.8) |
| Wake cancelled before the engine | kept | kept | The held call goes back to `held`, the reason goes back to waiting; runs again once (section 6.8) |
| Pause, assistant off, guard | stays `active` | kept | The reason is parked, the call stays held; when the park lifts it runs. If the guard is already latched or the budget is exhausted, it does not run |

Clicking revoke again after it has been revoked returns the current state, with no error.

### 6.8 Call-hold ledger (`call_holds`): states, takeover, cancel, reconciliation

**States** (separating two moments that round 2 still merged):

| State | Meaning | `calls_used` |
|---|---|---|
| `held` | Reserved, not yet attached to any turn | Already includes this call |
| `attached` | Attached to an action (intent written), action has not settled a result | Unchanged |
| `used` | The action attached to it settled with any result other than `not_run`, meaning the model **may** have been called | Unchanged (the call is spent) |
| `released` | Returned, exactly once | Minus 1, in the same transaction as the state change |

Every state transition is a CAS on `(id, status, action_id)` in one transaction, so repeating or running in parallel never returns or holds twice. The `gen` column increments each time a held call goes back to `held` after being attached, or its reason is rebuilt; the `method_followup` reason carries `source_ref = hold:<id>:<gen>`, so rebuilding a reason does not touch the unique index of the old event reason (A2).

**Who may use the held call.** Only a work turn on the **same goal and same revision** as the held call, while the call is `held` and still valid: the trial was applied, the lesson is `active`, and the effective method is exactly the candidate. Two paths:

- **`FOLLOWUP`:** the deliverable-making call as in section 6.5.
- **`NEW` takeover** (same-revision feedback arriving before `FOLLOWUP`): the user's fix turn **receives the held call directly**, reserving no new call. In the same `begin_action` transaction: write the action, the held call goes `held` → `attached` with the fix turn's `action_id`, and the `method_followup` reason settles as `superseded` with `settled_by` = that action. No addition to `calls_used`. The shared ceiling check (`_under_ceiling`) and the goal ceiling compute the **net increase** = 0 for a turn that uses the held call, so a goal sitting at the ceiling can still receive feedback. The assistant permission gate, guard, revision and the content of the feedback are checked like any `NEW` turn.
- Gates **outside** the transaction (A2's `decide`: `left > 0`) treat a valid `held` call for the same revision as still usable for `NEW` and `FOLLOWUP`, rather than rejecting as for a new call.
- A held call from an old revision, or one already `used`/`released`, is never borrowed again. A `NEW` turn then reserves a new call as usual, subject to the ceiling as usual.

**Cancel before the engine** (`abort_action`, firm evidence of `not_run`): extends A2's existing transaction. If the action used a held call:
- do not subtract from `calls_used` (the call is still held);
- the held call goes `attached` → `held`, clear `action_id`, increment `gen`;
- the reason the action was serving goes back to `pending`, as A2 does today (including the `NEW` reason and the `method_followup` reason settled with `settled_by` = that action).

The next turn runs again exactly once. A repeated cancel sees the action is no longer `running` and does nothing. An action that does not use a held call keeps A2 behavior.

**The model may have run** (the action settles `succeeded`, `failed`, `unknown`, or A2's `_reconcile` settles a half-done turn): the held call goes `attached` → `used` in the same transaction that settles the action. A call is never reissued by guesswork. Automatic retries after that still follow A2's rule (keep the reserve call).

**Hold reconciliation** (`reconcile_holds`): no new background sweep. It runs in two places:
1. once when the store opens, after migration (also catching the case of just being upgraded again from 0.88), over `held`/`attached` rows (very few);
2. in the prepare phase of each wake of a goal, before serving the reason (only that goal's rows).

Rules, in order, one CAS transaction per rule:

| Situation | Handling |
|---|---|
| `attached`, action `cancelled/not_run` | Same as cancel before the engine: back to `held`, increment `gen` |
| `attached`, action settled with any other result | `used` |
| `attached`, action still `running`, lease still valid | Leave as is |
| `attached`, action `running`, lease expired | A2's `_reconcile` settles the action first, then apply the two rules above |
| `held`, trial still `running`, live lease | Leave as is |
| `held`, trial still `running` with no live lease (process died mid-trial) | Settle the trial `inconclusive/interrupted` through `finish_experiment` (refunding trial calls that had no intent written, as in M5), lesson `trialing` → `unknown`, then the held call `released` |
| `held`, no longer valid: goal not active, revision changed, lesson not `active`, effective method differs from the candidate (for example the old version did `revert_method`), or the trial was not applied | `released` exactly once; settle every `method_followup` reason of it still waiting; the lesson is rewritten according to the M5 truth (`revoked` with reason `reverted_outside`, or `out_of_scope`) |
| `held`, still valid, no `method_followup` reason waiting | Rebuild **exactly one** reason: increment `gen`, `source_ref = hold:<id>:<gen>` |
| `held`, still valid, a reason already waiting | Leave as is |

This closes the A3 → 0.88 → A3 cycle: version 0.88 treats `method_followup` as `CHECK`, settling the reason without calling the model and without touching the held call; the next store open under A3 rebuilds the reason (or returns the call if the old version cancelled, revised the understanding, or went back to the old method in the meantime).

## 7. Store

### 7.1 New tables

Only tables are added; no columns are added to old tables (the `PRE_A1` test still locks this).

**`reactions`**: one person's current value on one message.
- Columns: `id`, `brain_id`, `agent_key`, `agent_config_version`, `goal_id`, `revision` (the message's revision), `session_id`, `message_id`, `report_key`, `notice_kind`, `presentation` (how the message was built when sent), `content_sha`, `responder`, `value` (`up`/`down`/`none`), `reason` (empty/`too_long`/`too_often`/`unclear`), `seq`, `created_at`, `updated_at`.
- Unique key `(brain_id, session_id, message_id, responder)`; index `(brain_id, agent_key, updated_at)`.

**`reaction_log`**: every click. Columns `id`, `reaction_id`, `value`, `reason`, `nonce`, `created_at`. Unique key `(reaction_id, nonce)`.

**`lessons`**: proposals and lessons of both lanes.
- Columns: `id`, `brain_id`, `agent_key`, `lane` (`presentation`/`method`), `key` (`notice_detail`, `notice_ping`, `method`), `from_value`, `to_value`, `base_lesson_id` (the `active` lesson that served as the base when the proposal was created; empty = default), `scope` (`agent`/`goal_revision`), `goal_id` (empty for lane P), `revision` (0 for lane P), `status`, `status_reason`, `policy_version`, `evidence_json`, `experiment_id`, `expires_at`, `decided_by`, `decided_at`, `created_at`, `updated_at`.
- States: `proposed`, `trial_pending`, `trialing`, `active`, `superseded`, `revoked`, `dismissed`, `expired`, `stale`, `skipped`, `rejected`, `unknown`, `out_of_scope`.
- **Two** partial unique indexes on the same column set `(brain_id, agent_key, lane, key, goal_id, revision)`:
  - `lessons_active_one ... WHERE status='active'`: at most one configuration in use;
  - `lessons_pending_one ... WHERE status IN ('proposed','trial_pending','trialing')`: at most one pending proposal.

  The two indexes are the anti-duplicate latch on rerun or restart, and they allow the configuration in use and the proposal that replaces it to coexist (section 5.2).

**`call_holds`**: the deliverable-making call reserved for lane M. Columns `id`, `goal_id`, `revision`, `experiment_id`, `lesson_id`, `purpose` (`method_followup`), `status` (`held`/`attached`/`used`/`released`), `action_id` (the turn attached to it or that used it), `gen`, `created_at`, `updated_at`. Unique key `(experiment_id, purpose)`; index `(goal_id, status)`. A held call is added to `goals.calls_used` at reservation and subtracted exactly once at `released`; `attached` and `used` leave the counter unchanged. The full lifecycle is in section 6.8.

**`lesson_events`**: log of state changes. Columns `id`, `lesson_id`, `brain_id`, `kind`, `by`, `payload_json`, `created_at`.

`evidence_json` is a snapshot taken when the proposal is created: the list of `reaction:<id>@<seq>` with `content_sha` (lane P), or `assessment:<id>`, `heartbeat_state` and the stall reason (lane M). The snapshot is never edited afterwards; orphan state is computed at read time.

### 7.2 Canonical sources

| Question | Canonical source |
|---|---|
| One person's current reaction on one message | `reactions` |
| Click history | `reaction_log` |
| The assistant's effective presentation | `lessons` lane P `active` |
| The goal's effective method | The M5 columns of `goals` through `effective_method` (unchanged). Lane M `lessons` are only a record, always cross-checked: an `active` lesson whose M5 column no longer matches shows the state derived from M5 |
| M4 feedback | `goal_events` (unchanged) |
| The deliverable-making call reserved for lane M | `call_holds`; the number of calls counted is still `goals.calls_used` (the held call is already added to it) |

### 7.3 Migration and rollback

- The first time version 0.89 opens a store that has no A3 tables: back up `resonance.sqlite3` as `.pre-a3.bak` (the same `_backup_before` function as A2), then create the tables. No old data is migrated.
- **Rolling back to 0.88.x:** the old version ignores unfamiliar tables. Lane P stops taking effect (notices go back to full, with a notification sound). A method already applied in lane M still sits in the M5 column that 0.88 already understands, still within the goal + revision scope. The old version does not know the `method_trial` reason: an unfamiliar code belongs to the `CHECK` class of `heartbeat.v1`, which only checks and calls no model; the rollback test locks this.
- A held call still `held` at rollback: the old version does not know the `call_holds` table, so that call stays in `calls_used` (one call over-counted, on the safe side). The old version treats `method_followup` as an unfamiliar `CHECK`-class code: **it settles the reason without calling the model and without touching the held call**. The old version may also cancel the goal, revise the understanding or go back to the old method in the meantime.
- Upgrading again to 0.89: `reconcile_holds` runs when the store opens (section 6.8). A held call that is still valid gets exactly one `method_followup` reason rebuilt; a call that is no longer valid is returned exactly once; the lesson is rewritten according to the M5 truth.
- **Upgrading again to 0.89 after a rollback:** the A3 tables are intact; a lane M lesson may disagree with the M5 column (the user went back to the old method using the old version) and is shown according to M5, as in section 7.2.

## 8. Policy `learning.v2`

Versioned constants, not settings. Changing a default bumps the version; each lesson records `policy_version`. `learning.v1` is the version that passed code review and the pilot; `learning.v2` only adds `P_REVOKE_COOLDOWN_S` (decided by the project owner after the pilot, 2026-10-10).

| Parameter | Value | Meaning |
|---|---|---|
| `P_WINDOW_S` | 30 days | Older reactions open no proposal |
| `P_MIN_MESSAGES` | 2 | Minimum number of different messages for a shorten or silence proposal |
| `P_REVERT_MIN_MESSAGES` | 1 | Number of `brief` messages marked "Unclear" for a revert proposal |
| `P_PROPOSAL_TTL_S` | 14 days | A proposal nobody decides on expires, and the old way stays |
| `P_DISMISS_COOLDOWN_S` | 14 days | After Dismiss, the same change is not proposed again within this period |
| `P_REVOKE_COOLDOWN_S` | 14 days | `learning.v2`: Revoke also blocks proposing the same (assistant, key, value) again within this period. It does not block another change, another assistant or the method lane; it changes no goal, schedule, permission or budget. After the cooldown, it proposes again only if enough live feedback remains in the 30-day window, and never applies on its own |
| `M_CANDIDATES` | `work.v1 → work.checklist.v1` | The only candidate on a stall |
| `M_TRIALS_PER_REVISION` | 1 per baseline, candidate pair | The same pair is not retried within the same revision |
| `M_HOLDOUT_MAX` | 1 | One holdout scenario: the nearest earlier revision with the same host-scored criteria set and a truly different prompt input |
| `M_HOLDOUT_SCAN` | 5 | Maximum number of earlier revisions considered when looking for a holdout scenario |
| Trial cost | 2 × number of scenarios (A3: 4 calls) | Must fit in the remaining exploration share |
| Full-cycle budget | `calls_used + trial_cost + 1 + AUTO_RESERVE_CALLS <= budget_calls` | Adds 1 held deliverable-making call and the reserve call; if missing, `skipped/budget` |

## 9. Latches: stops and mid-turn events

| Event | Lane P | Lane M |
|---|---|---|
| Owner pauses the goal | No effect | The reason is parked; a running trial stops at the next turn gate, concludes `inconclusive/stopped`, and refunds what did not run (M5) |
| Assistant turned off | No new proposals; an `active` lesson still applies (the owner decided; mandatory notices stay full) | Same as pause; in addition the assistant version changes, so apply is blocked in the transaction (A1) |
| Guard trips | No effect | Blocks at the turn gate and in the apply transaction (M5) |
| Goal cancelled | No effect | The reason is deleted along with the goal (A2); the trial stops at the gate |
| Budget exhausted | No effect | Not enough full-cycle budget: does not run, lesson `skipped/budget` |
| Owner clicks Dismiss on a lesson being trialed | Not applicable (lane P has no trial) | Stops at the next turn gate; if it has already reached the settle step, the lesson CAS in `finish_experiment` blocks the method change (section 6.4). A call already started still counts; the held deliverable-making call is returned |
| Owner revokes | The next notice build uses the default | `revert_method` and returning the held call in the same transaction |
| Wake cancelled before the engine | Not relevant | The held call goes back to `held`, the reason goes back to waiting, and the counter is not returned twice (section 6.8) |
| Understanding revised | No effect | Lesson `out_of_scope`, held call returned, method back to the default (section 6.7) |
| Global ceiling `JAVIS_RESONANCE_CALL_CEILING` | Not relevant | Checked in the reserve transaction (M5, unchanged) |

## 10. API

Every new route goes through `_ctx(brain)` and the owner principal, as in M4; an agent cannot call them.

| Route | Body | Returns | Errors |
|---|---|---|---|
| `POST /resonance/reactions?brain=` | `message_ref` (`msg:<session>:<id>`), `value` (`up`/`down`/`none`), `reason` (with `down`), `nonce` | `reaction` (current value, `seq`), `proposal` (the proposal just created, if any) | 400 the message is not an assistant notice; 404 the session or message does not belong to the brain; 409 the assistant was deleted or the message content changed |
| `GET /resonance/lessons?brain=&agent_key=` | | The assistant's lessons by lane and state, with evidence (orphans marked), lane P preview, lane M trial link; 30-day reaction statistics | 404 |
| `POST /resonance/lessons/{id}/decision?brain=` | `action` (`apply` / `dismiss` / `revoke`), `expected_status`, `expected_updated_at` | The lesson after the decision, with the current effective configuration | 409 state has changed (for example Dismiss when the trial has already been applied: returns `status='active'` so the UI switches to Revoke), or the base configuration has changed (the proposal becomes `stale`); 400 the action does not fit the lane or state (`apply` only for lane P `proposed`; `dismiss` for `proposed`/`trial_pending`/`trialing`; `revoke` for `active`). `apply` requires `expected_status` and `expected_updated_at`; `dismiss` only requires that the current state be in the allowed set |
| `GET /goals/{id}` (existing) | | Adds a `learning` block: the lane M lesson of the current revision (state, reason, trial, revert button) | |

`POST /goals/{id}/feedback` accepts an optional extra `source_ref` (section 3.2). No route lets the model create, apply or revoke a lesson; the `javis_goal` tool is unchanged.

## 11. Interface

- **Notices in the chat box** (`chat-resonance.js`): under the card of a message that has a receipt, a small row of thumbs up / thumbs down. Clicking thumbs down opens three reason chips. It shows the current value; clicking the same value again revokes it. It does not appear on ordinary messages. After a click, if a proposal was just created, it shows a line "Jarvis 007 has a suggestion about how to report, see the assistant page".
- **Assistant page** (`resonance-agent.js`, the Resonance part from A1): a **Lessons** section in a single column (the settings page's rule is a single column):
  - Lane P proposal: the old sentence and the new sentence side by side (stacked vertically on a phone), the number of messages used as evidence, Apply / Dismiss buttons.
  - Lesson being applied: scope, source, date, Revoke button.
  - Short history: dismissed, expired, tried and lost, with the reason.
- **Goal card**: the method line (already there) gains "trying method X", "method X learned for this understanding · Revert method", or "tried X, old method kept: <reason>". When a trial is skipped because nothing could be scored or the budget is short, it shows the exact reason.
- New strings go through `vi.json` and `en.json`, and the `tw()` key is the verbatim string (a lookup table like A2's `WAKE_KEYS`).

## 12. Performance

- Writing a reaction: one SQLite transaction covering the receipt check (primary key), upsert, log write, and running the learner over one assistant's reactions in 30 days (index `(brain_id, agent_key, updated_at)`). Runs on a worker thread as in A2 section 11. Reads no brain files.
- `drain_outbox`: adds one query for one assistant's `active` lesson per message, using the index `lessons_active_one`.
- `GET /goals/{id}`: adds one lane M lesson query by goal + revision.
- No new background sweep. Proposal expiry is computed at read time and written back when a new reaction arrives or when the lessons list is opened.

## 13. Acceptance matrix (fake clock, fake engine, no real model)

Every case runs in A2's fake-world frame (`World`, `reopen()` for a real restart). The "Checks" column states what the test asserts.

### 13.1 Minimum set by GOAL

| ID | Scenario | Checks |
|---|---|---|
| G1 | A reaction does not make a goal met: the goal has an unmet host criterion, the owner clicks thumbs up on every notice, run a tick | `status` stays active; no new `assessments`; the criterion is still `not_met`; fake engine 0 calls |
| G2a | Wrong person: the `agent` principal calls the reaction write path and the lesson decision | `PermissionError` / 403; no rows |
| G2b | Wrong brain: the message belongs to a session of brain B, called with brain A | 404; no rows |
| G2c | Wrong revision: M4 feedback with an old `expected_revision` | 409; not recorded (locks M4 behavior) |
| G2d | Wrong hash: "Meets the bar" with an old `artifact_ref` | 409; not recorded |
| G2e | Not a notice: a reaction on an ordinary chat reply, and on a message with a `JAVIS_RESONANCE` block the model wrote itself (no receipt) | 400; the learner does not see it |
| G3a | Send 10 `down/too_long` requests on the same message, each with a new nonce (the API sets the value, no auto-inversion) | One `reactions` row, `seq` 10, 10 log rows, final value `down/too_long`; the learner counts 1 message; no proposal |
| G3d | UI re-click rule: click thumbs down Too long, click that same button again, click a third time | JS test: the second request carries `value='none'`, the third carries `down/too_long` again; store side: final value `down/too_long`, `seq` 3 |
| G3b | Resend the same `nonce` | No new log row; returns the same `seq` |
| G3c | Revoke then restart: 2 `too_long` messages create a proposal; revoke one reaction; `reopen()`; click another reaction | No second proposal (unique index); the old proposal expires when only 1 valid message remains |
| G4a | Candidate loses: the trial returns `rejected/regression` | `method_ref` unchanged; lesson `rejected`; the held deliverable-making call is returned in the same transaction (`calls_used` = before + 4); no `method_followup` reason; no `method_changed` notice |
| G4b | Candidate unclear: one side `unknown` | `inconclusive`; the method stays; lesson `unknown`; the held call is returned |
| G4c | Lane P proposal expires (fake clock passes 14 days) | State `expired`; notices are still built `full` |
| G5a | Revoke lane P: a `brief` lesson active, revoke, send the next `goal.succeeded` notice | Full sentence as by default; the receipt records `presentation=full` |
| G5b | Revoke lane M (before and after the deliverable-making call) | `effective_method` = old method in the same transaction; lesson `revoked`; a held call still `held` is returned and the `method_followup` reason is settled; the next work turn uses a prompt without the candidate's addition |
| G6a | Pause in the middle of the trial: the fake engine sets pause right after the first baseline call (a 4-call trial plus 1 held call) | The remaining calls do not run; `inconclusive/stopped`; 1 call counted, 3 trial calls with no intent written refunded, 1 held call returned: `calls_used` = before + 1 |
| G6b | Turn the assistant off in the middle of the trial | Same as G6a; apply is blocked even when it is turned off right before the apply transaction |
| G6c | Guard trips in the middle of the trial | Same as G6a; the guard latch stays |
| G6d | Budget insufficient for the full cycle when the reason comes due (the owner lowered the budget, or the global ceiling) | 0 model calls; lesson `skipped/budget`; `calls_used` unchanged; no trial created |
| G6e | Owner clicks Dismiss while the lesson is `trialing`, between two calls | Stops at the next call gate; a call already started still counts; see also R1 for the gap before the settle transaction |
| G7a | No valid reason means 0 calls: 50 reactions, 20 ticks, no stall | Fake engine 0 calls; `wake_reasons` and `wakeups` unchanged from before the clicks |
| G7b | Stall because of `reserve` (not `stalled`) | No proposal; 0 calls |
| G7c | A revision with no host-scorable criterion | Lesson `skipped/untestable`; 0 calls |

### 13.2 Additions from the design

| ID | Scenario | Checks |
|---|---|---|
| A1 | Full lane P flow: 2 `too_long` messages → proposal → preview → Apply → next `goal.succeeded` notice | `brief` sentence; mandatory notices (`goal.guard`, `goal.stalled`) still full |
| A2 | Silence the bell: a `quiet` lesson active | `goal.maintained` is sent with `quiet=True`; `goal.deadline_passed` and `goal.monitoring_lost` still ring |
| A3 | Less disturbance does not change schedules | `wakeups`, the guard watch schedule and the deadline schedule are identical before and after applying lane P |
| A4 | (replaced by R3a) | |
| A5 | A new message beats the trial | Feedback arrives before the tick: the fix turn uses the old method; the `method_trial` reason settles as `superseded`; lesson `skipped/new_feedback` |
| A6 | "Not quite" after a proposal exists | The reason is parked; does not run; apply is blocked if it is running |
| A7 | Revision changes after apply | Lesson `out_of_scope`; `effective_method` is the default |
| A8 | Learning writes no permissions | The hash of the assistant's file, the `resonance_agents` rows and `config_version` are identical before and after every case in 13.1 and 13.2 |
| A9 | Source deleted or edited | Deleting the message (receipt lost) or editing its content: the reaction is orphaned and not counted; an already applied lesson still applies, and the list shows "source deleted" |
| A10 | Late feedback | A reaction on a message of an old revision and of a cancelled goal: recorded, counted for lane P, the goal unchanged |
| A11 | Assistant off | A reaction is recorded, no proposal; after turning it back on and clicking more, a proposal appears |
| A12 | Rollback to 0.88.1 | Open the A3 store with the `83bff6bc` code (git archive): no error; the `method_trial` and `method_followup` reasons call no model; the lane M method stays within scope; a `held` call still counts in `calls_used` |
| A13 | Migration | Store goes from 0.88 to 0.89: `.pre-a3.bak` exists; old tables keep their columns; the second open makes no new backup |
| A14 | Rerun after dying mid-trial | See R5e |
| A15 | Interface | JS test: the reaction row is drawn only on messages with a receipt; requests carry `nonce`; clicking the same value again sends `none`; `tw()` keys verbatim; `test_i18n.mjs` green |
| A16 | No long dash characters | Every new string in code, i18n, docs |

### 13.3 Cases from review round 1

These cases are written as behavior tests on the real A3 code after the design passes. Case R1 injects the event with a test hook placed **after the last gate outside the transaction and right before `finish_experiment`**, not only between two model calls.

| ID | Scenario | Checks |
|---|---|---|
| R1a | Dismiss wins: the trial is eligible; the hook injects a Dismiss transaction after the last gate, before `finish_experiment` | `method_ref` unchanged; lesson `dismissed`; trial `finished`, `inconclusive/lesson_dismissed`, `applied=0`; calls already made stay in `calls_used`; the held deliverable-making call is `released`; no `method_followup` reason; no `method_changed` notice |
| R1b | Apply wins: `finish_experiment` commits first, then Dismiss is sent with the old `trialing` state | 409, `status='active'`; the method is the candidate; then Revoke: `revert_method` runs, lesson `revoked`, held call `released`, `method_followup` reason settled |
| R1c | Dismiss at `trial_pending`, before the trial starts | `begin_experiment` creates no trial and reserves no call (the CAS `trial_pending` → `trialing` fails); 0 model calls |
| R1d | The lesson's state is edited out of band (simulate `status='skipped'`) between two calls | The call gate stops; the settle CAS fails; the method stays |
| R1e | Public `compare_methods`, passing no lesson | M5 behavior unchanged: the old M5 test suite stays fully green |
| R2a | A `brief` configuration `active` and a `full` proposal `proposed` coexist | Both are written with no UNIQUE error; `goal.succeeded` notices are still built `brief` before the owner decides |
| R2b | Dismiss the `full` proposal | Proposal `dismissed`; `brief` still `active`; notices still `brief` |
| R2c | Apply the `full` proposal | In one transaction: `brief` becomes `superseded`, `full` becomes `active`; exactly one `active` row for the key; the next notice is built `full` |
| R2d | The owner revokes `brief`, and only then clicks Apply on the old `full` proposal | 409; proposal `stale`; the current configuration is the default; no `active` row is created |
| R2e | The owner applies another proposal for the same key (base changes) then clicks Apply on the old proposal | 409; the old proposal is `stale`; the configuration in use is unchanged |
| R2f | A second proposal for the same key when one is already waiting | The learner does not create it (pending index); a restart does not create another |
| R3a | Full cycle, budget 9: 3 work turns with no progress → stall → `method_trial` (tuning + holdout) → eligible → apply → `method_followup` → real work turn with the new method → publish deliverable → host scores | The deliverable turn's prompt has the candidate's addition; the deliverable is published through the handoff gate, with the assessment on the right revision; `calls_used` = 8 (3 + 4 + 1); 1 reserve call left; A2 does not retry on its own; the `method_changed` notice is sent after the deliverable turn, with the result |
| R3b | Default budget 6, stall at 3 | Lesson `skipped/budget`; 0 model calls; `calls_used` = 3; no trial created; the card shows the reason |
| R3c | Enough budget but no earlier revision with the same criteria set | `skipped/no_holdout`; 0 model calls |
| R3d | Understanding revised after apply, before the deliverable turn | New revision: `effective_method` default; lesson `out_of_scope`; held call `released` (`calls_used` minus 1); the old revision's `method_followup` reason does not run; the new revision's work turn uses the default method |
| R3e | Review schedule and deadline after apply (deliverable turn already done) | `CHECK` wake: 0 model calls |
| R3f | A new message from the user on the same revision arrives before the deliverable turn | The fix turn takes over the held call (`attached`, then `used`), uses the new method; no additional call reserved; `method_followup` reason settles `superseded`; `FOLLOWUP` does not run; `calls_used` = 8 (3 + 4 + 1); fake engine: exactly 1 call after the trial |
| R3g | Restart between apply and the deliverable turn | The deliverable turn runs exactly once; held call `used`; opening again builds no new reason and calls no model |
| R3h | Pause before the deliverable turn, then resume | At pause: the reason is parked, 0 calls, the held call stays `held`; on resume: the deliverable turn runs once |
| R3i1 | A hand-edited version by the user was detected **before** `FOLLOWUP` opens a turn | A2 parks the goal (`source_drift`): 0 model calls; the held call stays `held`; the reason waits for the park to lift |
| R3i2 | The user hand-edits **while** the deliverable turn is running | No overwrite (A2 section 5); the output stays in the work area, not published; held call `used`; the `method_changed` notice says plainly that it could not be published |

### 13.4 Cases from review round 2

Each R4 to R6 case checks five things: the held call's state and `gen`, the action state, `calls_used`, the reason currently waiting, and the number of fake engine calls. Shared setup: budget 9, stall after 3 work turns, an eligible 4-call trial, applied, the held call `held`, `calls_used` = 8.

| ID | Scenario | Checks |
|---|---|---|
| R4a | Global ceiling exactly 8 (`JAVIS_RESONANCE_CALL_CEILING=8`); same-revision feedback arrives before `FOLLOWUP` | The fix turn receives the held call in one transaction (net increase 0, not blocked by the ceiling); `calls_used` = 8; engine 1 call; held call `used`; `method_followup` reason `superseded`; `FOLLOWUP` does not run again |
| R4b | Same ceiling 8; the understanding is revised (new revision), then feedback on the new revision | The held call was already `released` at `revise` (`calls_used` = 7); the new revision's turn reserves a new call as usual (7 → 8, exactly at the ceiling); it does not borrow the old revision's held call |
| R4c | The held call is already `used`; further feedback with ceiling 8 and `calls_used` 8 | The new turn is blocked by the ceiling as A2 does today (0 model calls); it does not borrow the used held call again |
| R4d | Gate outside the transaction: after apply `left` = 1, exactly equal to the reserve call | `decide` does not demand headroom over the reserve call for `FOLLOWUP` (the call is already held): runs exactly 1 call using the held call; afterwards `left` is still 1, the reserve call intact |
| R5a | Cancel the `FOLLOWUP` wake after the prepare phase, before the engine (`abort_action`) | Action `cancelled/not_run`; held call back to `held`, `gen` +1; `calls_used` still 8 (does not become 7); the `method_followup` reason waits again; engine 0. Next tick: runs exactly 1 call, held call `used`, `calls_used` 8 |
| R5b | Call `abort_action` a second time for the same action | Returns False; held call, counter and reason unchanged |
| R5c | Cancel before the engine a feedback turn that took over the held call | Held call `held`; the feedback reason and the `method_followup` reason both go back to waiting; `calls_used` 8. Next tick: feedback wins and takes over again; `FOLLOWUP` does not run; engine total 1 |
| R5d | The process dies after the deliverable turn may have called the engine | On reopen: A2's `_reconcile` settles the action; held call `used`; reason settled; does not run again; `calls_used` 8 |
| R5e | The process dies after 2 of the trial's 4 calls | On reopen: trial `inconclusive/interrupted`, refunds the 2 calls with no intent written; lesson `unknown`; held call `released`; `calls_used` = 3 + 2 = 5; no `method_followup` reason; no second trial for the same pair and revision |
| R6a | Cycle A3 → 0.88 → A3: held call `held` and reason waiting; run `tick` with the real `83bff6bc` code (git archive) | Old code: 0 engine calls, the reason is settled, the held call stays `held`, `calls_used` 8. Reopen with A3: rebuilds exactly one reason (`gen` +1, new `source_ref`); tick: 1 deliverable turn, held call `used`. Third reopen: no new reason |
| R6b | Same as R6a, but the old code cancelled the goal | Reopen with A3: the held call is `released` once (`calls_used` 7); no reason waiting; engine 0; opening again does not return it a second time |
| R6c | Same as R6a, but the old code revised the understanding (new revision) | Held call `released`; lesson `out_of_scope`; method is the default; engine 0 for the old deliverable turn |
| R6d | Same as R6a, but the old code did `revert_method` | The effective method differs from the candidate: held call `released`; lesson `revoked`, reason `reverted_outside`; engine 0 |
| R7a | The earlier revision differs only in metadata (revision number, edit reason, timestamps), with the same understanding, user words, constraints and assumptions | `prompt_input_hash` matches: not chosen as a holdout; if no candidate remains then `skipped/no_holdout`, 0 calls |
| R7b | The earlier revision has a truly different understanding and user words, with the same host-scored criteria set | Chosen; the payload pins two `prompt_input_hash` values, the revision record hash and `rubric_hash`; the holdout scenario's prompt is built from the old revision; action, call gate and apply transaction all carry the current revision; no file is published |
| R7c | The nearest earlier revision differs only in metadata, an even older revision truly differs (within `M_HOLDOUT_SCAN`) | Choose the older revision |
| R7d | The earlier revision truly differs but its host-scored criteria set differs | Not chosen |

### 13.5 Not part of A3 acceptance

- Real-model pilot: runs only when the project owner approves a dedicated budget. Proposed pilot after the code passes review: at most 8 model calls (3 work turns to the stall, 4 trial calls, 1 deliverable-making call), the goal set to a budget of 9 to keep the reserve call, using an existing engine or subscription plan, one goal that has an earlier revision with the same criteria set so that a holdout scenario exists. No automatic switch to a paid API, no automatic retry or ceiling raise.
- VPS performance measurement: not part of A3.

## 14. Default decisions to review

| # | Question | Proposed default | Alternative |
|---|---|---|---|
| D1 | Where reactions attach | Only notices written by the host that have a receipt | Add the assistant's replies in an agent session: needs a trustworthy message source and a way to apply that does not go through the chat prompt; later |
| D2 | Who applies lane P | The owner clicks Apply after viewing the preview; silence means expiry | Auto-apply after N messages: faster, but changes behavior based on emoji, against the goal of "not chasing emoji" |
| D3 | Does lane M run on its own | Runs on its own at an objective stall, only when the full-cycle budget is enough (trial, held deliverable-making call, reserve call) within the budget already granted; goes through exactly the A2/M5 gates (round 1 review agreed with conditions) | Wait for the owner to click Try: one extra step at every stall |
| D4 | Lane M scenario set (**re-decided after review round 1**) | Keep M5's rules: a tuning set and a holdout. The only holdout in A3 is the earlier revision with the same host-scored criteria set. If none exists, `skipped/no_holdout`. A default 6-call goal always gets `skipped/budget` (sections 2, 6.3) | The round 1 version dropped the holdout to fit the budget: withdrawn, because fitting the budget is not a sufficient reason to lower the evidence level |
| D5 | Output of a winning trial | Not published as the deliverable; one deliverable-making call with the new method, held from the start of the trial, runs exactly once (`method_followup`) | Accept the trial output through the handoff gate: saves one call, but needs A4's handoff contract; after A4 |
| D6 | Does "Needs changes" open lane M | No, because the host cannot score a trial for a user-scored criterion | A hand-scored trial: the user scores the trial version. This is close to A5's review team |
| D7 | Lane P optional notices | `goal.succeeded` and `goal.maintained` may be shortened; only `goal.maintained` may be silenced | Broader: easy to hide notices that ask the user to do something |

## 15. Code plan (after the design passes review)

One commit with tests per step; run the old M4, M5, A1, A2 tests after each step.

1. **Store:** tables, indexes, `.pre-a3.bak` backup, `A3_TABLES`; migration test and a test locking old columns (`resonance_store.py`).
2. **Reactions:** `record_reaction` (receipt check, upsert, log, orphans), `POST /resonance/reactions`; message source for M4 feedback (`resonance_store.py`, `resonance_api.py`, `main.py` passing the `report_receipts` lookup into the store).
3. **Lane P learner:** pure functions in `resonance_learning.py` (new, no I/O, like `resonance_heartbeat.py`), lesson lifecycle, `GET /resonance/lessons`, `POST .../decision`.
4. **Applying lane P:** `PRESENTATION`, `notice_text(..., presentation)`, `drain_outbox` reading the lesson, `quiet` in `_resonance_notify`, writing `presentation` into the receipt.
5. **Lane M:**
   - proposal in the stall branch, checking the full-cycle budget and the holdout scenario;
   - `heartbeat.v2` (`TRIAL`, `FOLLOWUP`, `method_trial`, `method_followup`);
   - split out the body of `compare_methods`; `_trial_run` builds the prompt per scenario revision;
   - lesson CAS in `begin_experiment` and `finish_experiment`;
   - the `call_holds` table and the section 6.8 lifecycle: hold, attach (`FOLLOWUP` or feedback takeover, net increase 0 at the ceiling check), use, return; extend `abort_action`; `reconcile_holds` at store open and in the prepare phase;
   - choose the holdout scenario by `prompt_input_hash`;
   - the deliverable-making call through A2's wake frame and the existing handoff gate;
   - `goal.method_changed` sent after the deliverable turn;
   - revoke with `revert_method`; `out_of_scope` and returning the held call on `revise`.
6. **Interface:** reaction row (`chat-resonance.js`), Lessons section (`resonance-agent.js`), `learning` block on the card, i18n.
7. **Tests:** `tests/python/test_resonance_a3_learning.py` (matrix 13.1 to 13.4; test hook that injects a decision right before the settle transaction; R6 runs `tick` with the `83bff6bc` code fetched through git archive), `tests/python/test_resonance_a3_rollback.py` (`OLD_SHA` = `83bff6bc`), `tests/js/test_resonance_a3_ui.js`; CI also fetches commit `83bff6bc` for the rollback test.
8. **Docs:** guide `docs/dev/resonance-a3-learning.md`, minutes `docs/dev/resonance-a3-verification.md`, roadmap sections 6 and 8.

## 16. Handed over to A4, A5

- **A4:** accepting the winning trial output as the deliverable (D5) will use the shared handoff contract.
- **A5:** a hand-scored trial for user-scored criteria (D6) is close to the reviewer role; review is one source of evidence by criterion type, and does not replace the objective check.

## 17. Changes after review round 1 (`a6418e45`)

Review: `exports/reviews/PR-598-A3-design-a6418e45-review.md` (outside git), with independent check scripts on real SQLite, a real A2 store with a fake engine, and real M5 transactions.

| Review point | Fixed where | How it was fixed |
|---|---|---|
| **P1:** Dismissing a lesson was not latched in the method-change transaction; a gap remained between the last gate and `finish_experiment` | Sections 6.4, 6.5, 9, 10; cases R1a to R1e | Pass `lesson_id` into `begin_experiment` and `finish_experiment`. CAS `trial_pending` → `trialing` at reservation, CAS `trialing` → `active` before `_set_method` in the same settle transaction. If the CAS fails, keep the old way, keep the Dismiss decision, count calls already made, refund what was not called, return the held call. Order follows the commit order of `BEGIN IMMEDIATE`: Dismiss first means apply loses; apply first means the stale Dismiss gets 409 `active` and the UI switches to Revoke |
| **P2:** the unique index merged `active` with `proposed`, blocking the very proposal that changes a preference in use | Sections 5.2, 7.1, 10; cases R2a to R2f | Two partial unique indexes: one for `active`, one for the pending proposal. A proposal records `base_lesson_id` and `from_value`; Apply checks the base in the same transaction, and if the base changed it becomes `stale` with 409. The configuration in use is not disabled to make room for a proposal |
| **P2:** after a winning trial, the sentence "the next turn caused by a revised understanding or a review schedule uses the new method" was wrong against A2/M5; the cost of making the deliverable was not planned | Sections 2, 6.3, 6.5, 6.6, 6.7; cases R3a to R3i | The wrong sentence is removed. Added the full-cycle budget; one deliverable-making call is held in advance (`call_holds`) in the trial's reserve transaction; the `method_followup` reason (class `FOLLOWUP`) runs exactly one work turn with the new method through the existing handoff gate. Stated plainly: revising the understanding creates a new revision, so the method just learned stops applying; the review schedule is `CHECK` and calls no model |
| **D4** not met: dropped the holdout only to fit the budget | Sections 6.2, 14 | Keep M5's rules. The only valid holdout source is the earlier revision with the same criteria set; if none, `skipped/no_holdout`. The evidence level and its limit are stated; a default 6-call goal always skips lane M |
| D3, D5 agreed with conditions | Section 14 | D3 is tied to the full-cycle budget; D5 is kept, with the deliverable-making call held in advance |

Parts the review agreed to keep: the boundary between reactions and M4, D1, D2, D6, D7, lane P costing no model calls, the goal + revision scope with a way back.

## 18. Changes after review round 2 (`ef56b61f`)

Review: `exports/reviews/PR-598-A3-r2-ef56b61f-review.md` (outside git). The three round 1 points were accepted at design level; 2 P2 remain on the call-hold mechanism.

| Review point | Fixed where | How it was fixed |
|---|---|---|
| **P2-1:** feedback replacing `FOLLOWUP` reserved a new call first and only then returned the old call, so the global ceiling blocked it at 8/8 | Sections 6.3, 6.5, 6.7, 6.8; cases R3f, R4a to R4d | Same-revision feedback **takes over** a valid `held` call in one `begin_action` transaction: write the action, move the held call to `attached`, settle the `method_followup` reason. Net increase 0 at the global ceiling and goal ceiling checks. The gate outside the transaction treats the held call as usable. A held call from an old revision or one already used is never borrowed again |
| **P2-2a:** cancel before the engine returned the counter but the held call got stuck at `used` | Sections 6.8, 9; cases R5a to R5c | Separate `attached` (action attached) from `used` (the model may have run). `abort_action` for an action that used a held call: does not subtract from the counter, the held call goes back to `held`, `gen` +1, the reason goes back to waiting. A repeated cancel does nothing |
| **P2-2b:** version 0.88 settled the `method_followup` reason without touching the held call; upgrading again had nothing to rebuild the schedule | Sections 6.8, 7.3; cases R5d, R5e, R6a to R6d | `reconcile_holds` runs at store open and in the prepare phase of each wake: rebuilds exactly one reason (`source_ref = hold:<id>:<gen>`) for a held call that is still valid; returns exactly once a call that is no longer valid (cancelled, understanding revised, back to the old method, trial interrupted); never reissues a call when the model may have run |
| Historical holdout: must check that the input truly differs | Sections 6.2, 8; cases R7a to R7d | `prompt_input_hash` from the part of the prompt build outside the criteria; if it matches the tuning set, skip it and consider older revisions within `M_HOLDOUT_SCAN`. Pin the hashes of the two records and `rubric_hash`. A historical revision is used only to build prompts and never enters the call-hold or apply gates |
| Note: G6a carried the numbers of a one-scenario design | Case G6a | Expectation by number of calls started: 1 counted, 3 refunded, 1 held call returned |
| Note: G3a contradicted the re-click rule | Section 3.3; cases G3a, G3d | The API sets the value per request; the re-click rule belongs to the UI (sends `none`). Split the repeated-send test from the re-click test |
| Note: section 12 still had the old index name | Section 12 | `lessons_active_one` |
| Note: R3i merged two hand-edit scenarios | Cases R3i1, R3i2 | Detected before opening a turn: parked, 0 model calls. Edited while running: keep the output unpublished |

No new feature opened: the two lanes, D1 to D7 and the round 1 fixes are unchanged.

## 19. Implementation notes (after the design passed at `d6239d54`)

Behavior, permissions, budget and the evidence standard stay exactly as in the settled design. The items below are implementation choices or one addition that tests on the real code forced; the code reviewer reconsiders each one.

| # | Item | Design says | Code does | Reason |
|---|---|---|---|---|
| I1 | Lesson identity in the settle transaction | `finish_experiment(..., lesson_id)` | `begin_experiment(..., lesson_id)` as designed; `finish_experiment` finds the lesson by `experiment_id` inside the settle transaction | The same identity (the lesson records `experiment_id` at the reserve step). This way A2's reconciliation path (`_reconcile`, settling an interrupted trial) needs no extra parameter and still runs the lesson CAS. A trial with no lesson (public `compare_methods`) keeps M5 behavior |
| I2 | Wake after a trial is interrupted | Section 6.8 says reconciliation settles the half-done trial | Added a `trial_recovery` appointment (check class, no model call, its own `trial` obligation) at the time the trial's lock expires; when the trial finishes normally, only exactly that appointment is settled by id. The first version used `action_recovery` and then dropped the whole `check` obligation, losing `guard_recheck` (code review round 1, P2-1) | Test R5e on the real code showed an interrupted trial leaves no schedule (the reason was already served, the trial call has no recovery appointment), so no wake reconciles and the held call gets stuck at `held`. This is a real flaw in the contract, not only in the test |
| I3 | Source of a reaction | `message_ref` | Accepts `message_ref`, or the triple (session, report key, goal) already in the card block; the server looks the triple up through the `report_receipts` receipt and then checks it like `message_ref` | The message element in the chat box does not carry the session store's message id. Every check (receipt, `assistant` role, card block matching the key, brain, goal) is unchanged |
| I4 | Dismiss-the-trial button on the card | Section 11 names the Revert method button | The card gains a Dismiss-the-trial button when the lesson is `trial_pending`/`trialing`, calling exactly the decision route of section 10 | Sections 9 and 10 already have the Dismiss action for these two states; the card is where the user sees the trial waiting |
| I5 | Case R5e | Example "after 2 of 4 calls" | The test interrupts at the 3rd trial call and checks with the formula `calls_used = 3 + number of trial calls with intent written` | A call with intent written may have run the model, so it still counts; the formula is the invariant to lock, and the number is only an example |
| I6 | A2 interface test | Not mentioned | `tests/js/test_resonance_a2_ui.js` changes the count of labeled reason codes from 20 to 22 | A3 adds exactly two codes, `method_trial` and `method_followup` (section 6.3); the test still checks every labeled code in both languages |
| I7 | Lane P proposal expiry | Written back when a new reaction arrives or when the list is opened | As designed; plus expiry when the number of live evidence messages drops below the threshold (`evidence_gone`) | Section 3.4 says a proposal that loses enough messages expires on its own |
| I8 | Trial on the event loop | Not mentioned | Every store, file and evidence step of the trial runs on a worker thread, always awaited to completion even when cancelled; a trial call with intent written but cancelled before the engine is settled `not_run` and refunded at reconciliation; the four A3 routes run their store part on a worker thread | Code review round 1, P2-3: the trial is now opened by the scheduler itself, so it must not lose A2's non-blocking property |
| I9 | Applying a lane P proposal | 14-day limit, expires if evidence is lost | Check the limit and the live evidence RIGHT inside the Apply transaction (host clock), not only when reading the list | Code review round 1, P2-2 |
| I10 | System file error after reserving | Not mentioned | The reserve transaction is separated from creating the trial directory. If the directory fails after commit, the trial is settled `inconclusive/stopped` (refunding every reserved call); if settling also fails, the trial stays `running` and the `trial_recovery` appointment is kept (the appointment is settled only when no `running` trial remains). A failure before commit records `storage_error`, and is not mislabeled as a permission error | Code review round 2, P2-1 |
| I11 | Pinning the assistant permissions of a trial | Not mentioned | Reading the agent registry (`_agent_intent`) runs on a worker thread like every other store step | Code review round 2, P2-2 |
| I12 | Session of the feedback row | I3: the triple (session, report key, goal) | The page sends an EMPTY session; the server looks up the receipt by report key and goal, using it only when exactly one receipt exists. An explicit session is still checked strictly as before (wrong session 400) | UI inspection on the sandbox: when the message is drawn, the session "open" on the Partners page may not exist yet or may still be the previous assistant's session, so the server rejected it and the feedback row disappeared. The key `outbox:<id>` belongs to only one message, so dropping the session widens no permission: brain, role and card block are still checked |
| I13 | Lessons section after feedback | Section 11: the line "see the assistant page" | When feedback is recorded, the chat page fires the event `javis:resonance-lessons`; the assistant pane that is open reloads the Lessons section | UI inspection: without reloading, the assistant pane keeps saying "No lessons yet" until F5 |
| I14 | Lessons section display | Section 11 | The preview sentence drops markdown link syntax; method lessons show a translated label (`to_label`) and the goal's understanding (`goal_label`); a pending trial has its own block with a Dismiss button; the 409 conflict note survives a reload | UI inspection: before this it showed `[Inbox/p.md](Inbox/p.md)`, the code `work.checklist.v1`, and the 409 note vanished as soon as the list redrew |
| I15 | Cooldown after Revoke | Section 5.3: only Dismiss blocks re-proposing | `learning.v2`: the store puts `revoked` presentation-lane lessons in the block list too; `P_REVOKE_COOLDOWN_S` 14 days | UI inspection (screenshot d06) showed old feedback proposing exactly the change just revoked; the review recommended sharing the 14-day rule, and the project owner decided |

