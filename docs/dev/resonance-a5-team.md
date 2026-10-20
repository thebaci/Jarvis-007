# Resonance A5: one agent does the work, another agent reviews it

A guide for whoever changes the code. Final design: [2026-10-11-resonance-a5-maker-reviewer-design.md](../superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md) (passed design review round 3 at `56f7ab50`; the project owner chose option A for hand-edited files). Verification record: [resonance-a5-verification.md](resonance-a5-verification.md).

## In one sentence

The project owner picks another Resonance agent to act as the reviewer for a maker agent. From then on, every NEW goal of the maker agent has a team: a version that passes the objective check must get a `pass` verdict from the reviewer on exactly the version that was accepted before it can be closed. Review runs as background work, on the shared text-only engine, in a separate call ledger for each role (8 calls, 4/4, at most 2 fix rounds).

## Where the code is

| Part | File |
|---|---|
| The four A5 tables, the `.pre-0.109.0` snapshot, team attachment in `create`, the role ledger in `begin_action`, the single refund path `_refund_not_run`, `release_call` by `action_id`, `begin_experiment` refusal when a team exists, the guard in `finish`, `record_review`, `review_interrupted`, `team_detach`, `team_pair_set`, `team_reviewer_enable`, the `mark_engine` mark and `abort_action(..., recheck_at)`, `wake_agent_goals` for the reviewer | `server/resonance_store.py` (the "A5" section at the end of the class, plus the places it hooks in) |
| `parse_review`, `accepted_snapshot`, `bundle_ref`, `_review_state`, `_team_review`, `_team_settle`, `_review_pre`/`_review_step`/`_review_post`, the reviewer gate inside `_gate`, the team branch in `_wake_work` and `_settle`, feedback folded into `_work_prompt`, `_prepare_failed`, the `team` block of the goal view, the `goal.review_*` messages, the `team_detach` command | `server/resonance.py` |
| `heartbeat.v3`: code `review_due` (START), `review_retry` (AUTO), `review_changes` (new class `FIX`), `review_recheck`, `prepare_recheck`; permanent errors `too_large`, `snapshot_mismatch` | `server/resonance_heartbeat.py` |
| `POST /resonance/agents/reviewer` and `POST /goals/{id}/reviewer/enable` (registered last, `register_a5`), the `reviewer` field of the assistant list | `server/resonance_api.py`, `server/main.py` |
| The Reviewer field; the team row, feedback, the "Turn the reviewer back on" and "Drop the review requirement" buttons on the card; i18n keys | `dashboard/resonance-agent.js`, `dashboard/chat-resonance.js`, `dashboard/i18n/vi.json`, `en.json` |
| Downgrade to 0.108.0 | `tools/resonance_restore_pre_a5.py` |

## Lifecycle

**Pair and team.** `team_pairs` stores the pair by `agent_key` (not by slug, not by tag), and only the project owner changes it. `create` calls `_attach_team` RIGHT after the `goal_agents` row, in the same transaction: if the pair is enabled, it writes `goal_team` (pinning the reviewer's durable key), two `team_calls` rows (4/4) and sets `budget_calls = 8`. Both the `javis_goal` tool and `POST /goal-requests` go through `form_goal`, which means through `create`. `assign_goal` (old goals) does not attach a team; the event is recorded as `not_attached_legacy`.

**Role ledger.** `begin_action` infers the role from the action kind (`work` means `maker`, `review` means `reviewer`), checks `team_calls` BEFORE charging, then increments `calls_used` and the role's share in the same transaction, and writes `role` into the intent. Every refund path uses the recorded role.

**Refunding a call.** Only when the host is sure the engine has not run:
- `abort_action` (cancelled before the call) and, for a review call, `release_call(action_id)` (the engine could not be built) go through `_refund_not_run`: a CAS moves the `running` action to `cancelled/not_run`, subtracts the total and the role's share, marks the review row `cancelled` with `charged = 0`, and puts the reason it served back to `pending`. A repeated refund has no effect.
- A WORK call of a goal with a team, when the engine cannot be built, keeps the exact A2 behavior (the action is closed as an error right after) and also returns the maker share in the same transaction; the `refunded` flag in the intent prevents a double refund.
- The prepare phase FAILS after the slot was reserved (code review round 1, R1): `_prepare_failed` calls `abort_action(code='prepare_error', recheck_at=...)`, one transaction that refunds exactly that action and parks the goal with a recheck appointment by code (review call: `blocked/review_engine` + `review_recheck`; work call: `blocked/prepare_error` + `prepare_recheck`). A wake before the deadline does not reserve a slot again; a new user message still opens a work call.
- **Engine-call mark.** Every new `work`/`review` action carries `engine_mark = 1`. The last step of the prepare phase is `mark_engine`: it writes `engine_at` and moves the goal to `running` in one transaction; without the mark the engine is not called. Reconciliation after the lock expires: if `engine_mark` is set but `engine_at` is not, the engine DEFINITELY has not run, so refund through the not-run path (even when the immediate refund at the time of the error also failed); if `engine_at` exists, or the action is an old one without the flag, the old rule applies (it may have run).
- The model may have run (cancelled during the call, restart after the engine-call mark): no refund; the review row is `failed` with `charged = 1`.

**Pin set and review call.** `accepted_snapshot` takes the ACCEPTED version (the A4 registration mark of the product file and the evidence for those exact bytes, or the revision's latest output when there is no target file) and hashes it again; a mismatch is `snapshot_mismatch`, and anything over 60,000 characters is `too_large` (a permanent error: no slot is reserved, it waits for a person). `bundle_ref` = `rb:<revision>:<registration mark>:<sha>:<criteria hash>:<reviewer key>:<reviewer version>`. `begin_action(kind='review')` inserts a `reviews` row with an increasing `seq` (for tracing) and `charged = 1`. The attempt cap (3) and the backoff index count the rows with `charged = 1` of the pin set, not `seq`.

**Recording the verdict.** `parse_review` fails closed (exactly one JSON object, every criterion index present, `ok` a bool; a contradiction is `inconsistent`). `record_review` CASes the row from `running`; a verdict that does not match the action is `review_mismatch`; one that is stale against the current pin set (revision, registration mark or reviewer version changed) is `stale`: stored but not used, not counted as a round, and it only schedules one check-only wake. A valid verdict:
- `pass`: check-only reason `review_done`; the next wake closes the goal.
- `needs_changes`: count `k` AFTER writing; `k ≤ 2` gives `review_changes` (FIX), `k = 3` gives `blocked/review_rounds` and the `goal.review_exhausted` message.
- `unknown`: a permanent error gives `blocked/review_input`; a transient error schedules `review_retry rr:<id>` following `ERROR_BACKOFF_S[n-1]` when `n < 3` and the reviewer role has at least 2 calls left, otherwise `blocked/review_unknown`.

**Scheduling.** A review call only schedules `action_recovery` (reconciliation by code). When `_reconcile` finds an unfinished review call it calls `review_interrupted`: it closes the row as `failed/interrupted` first, then evaluates the retry rule. It never becomes a maker call. The maker's `decide` does not see `review_due`/`review_retry`; class `FIX` may use the maker's last call, while `AUTO` needs the role to have at least 2 calls left.

**Closing.** `_settle` (both from a wake and after a work call) calls `_team_settle` for EVERY version that passes the check (or is only waiting for human confirmation) of a goal with a team, in every mode and stage (code review round 1, R3), before the next step: finish, wait for human confirmation, `discovery_done`, or keeping a `maintain` goal at `healthy` (the `goal.maintained` message is only emitted after a `pass`). If the same pin set already has a `pass`, it goes straight through; the periodic check beat does not review again. Conditions: the bytes on disk must be exactly the accepted version (option A: a hand edit gives `waiting/source_drift`, even when the edited version passes the check; restoring the exact bytes reuses the old verdict), and the current pin set must have a valid `pass`. `store.finish` re-checks inside the finishing transaction itself (`_review_pass_block`).

**Reviewer gate.** `_gate` checks `agent_gate(reviewer_agent_key)` without passing a version: off gives `blocked/reviewer_off`, a missing file gives `reviewer_missing`, a retired key gives `reviewer_retired`. The version is pinned only per review; re-enabling the same key invalidates the old verdict (the pin set carries the new version) and the current version is reviewed again, costing one call; it does not reset calls, rounds or errors. A new agent with the same slug or the same tag is a different key and never replaces it. The "Turn the reviewer back on" button on the card sends the durable key to `POST /goals/{id}/reviewer/enable`; `team_reviewer_enable` checks in one transaction that the team is still in effect, still pins exactly that key and the key is still `active`, and only then enables it; a stale card gets a 409 with the new state (code review round 1, R2). The enable button on the assistants page still goes through `/resonance/agents/toggle`.

**A3 lane M.** Off on a goal with a team, checked in the store: `begin_experiment` returns None, a `trial_pending` lesson becomes `skipped/team_goal`; `_settle` does not propose an experiment on a deadlock.

**Detaching the team.** `team_detach` (project owner only, the "Drop the review requirement" button): `goal_team` becomes `detached`, `team_calls` is kept as a record, blocks that belong to the team are cleared, the pending review reason is dropped, and one wake is fired; from then on the goal closes under the A4/A2 rules.

## Behavior changes vs 0.108.0

- An agent with a reviewer: a new goal has 8 calls (4/4) instead of 6, and closes only after a review `pass`.
- A goal with a team does not close on a file edited outside Jarvis 007, even if the edited version passes the check (option A); to keep the edit, use "Drop the review requirement".
- `heartbeat.v3` (the A3 test that locks the policy version was updated to match).
- Every goal (with a team or not): a call that fails in the prepare phase, before the engine-call mark, is refunded instead of being closed as a counted `interrupted`; the three A2, A3 and MVP fixtures that simulate "dies in the middle of an engine call" now write the `mark_engine` mark like the real host.
- Nothing changes for an agent without a reviewer.

## Downgrading

Shut down Jarvis 007, run `python tools/resonance_restore_pre_a5.py --yes` (it keeps the current store as `post-0.109.0-<timestamp>`, then writes the `.pre-0.109.0` snapshot), then run 0.108.0. Downgrading WITHOUT restoring is unsupported: the 0.108.0 code ignores the A5 tables, so it closes goals that have a team as passed without any review (the test `test_resonance_a5_rollback.py` records exactly this).
