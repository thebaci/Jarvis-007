# Resonance A4: submitting a product through the host contract, scope allowed by the project owner

A guide for people editing the code. Settled design: [2026-10-10-resonance-a4-handoff-grants-design.md](../superpowers/specs/2026-10-10-resonance-a4-handoff-grants-design.md) (D1: **no write permission is granted from chat text**). Verification record: [resonance-a4-verification.md](resonance-a4-verification.md).

## In one sentence

Every engine submits a product through the same gate: the host identifies the turn, pins the permission to the turn, reads and hashes the bytes itself, stores the submission with a receipt, then posts it to the target file itself in four steps with a commit point that is sequenced against revocation. A target only has permission once the project owner clicks Allow on the card (or the legacy permission was frozen when the store was upgraded).

## Where the code is

| Part | File |
|---|---|
| Pure rules: the path key, `narrow`, `allows`, the fingerprint, the engine capability table | `server/resonance_grants.py` (new) |
| Store: six A4 tables, the `.pre-0.96.0` snapshot, freezing legacy, scope per revision, bindings, submissions, the four posting steps, Allow, No, Revoke, re-grant, republish | `server/resonance_store.py` (the "A4" section at the end of the class) |
| `host_publish`, posting reconciliation, `_publish_latest` by submission, `_work_post_core` inserting the submission before posting, the end-of-turn handoff, `submit_deliverable`, the scope gate in `_gate`, owner commands, the card's `scope` block | `server/resonance.py` |
| The hub tool `javis_submit_deliverable`, the scope note and the `handoff` code in the `javis_goal` result | `system/plugins/javis-goal/plugin.py`, `plugin.yaml` |
| The snapshot of permission order at the start of a turn, the turn's provider | `server/turn_context.py`, `server/main.py` (`_resonance_turn_agent`) |
| Handing over every goal of one message; registering dependencies for the in-process tool | `server/main.py` (`_resonance_after_turn`, `resonance.set_deps_provider`) |
| Preview of a draft | `server/resonance_api.py` (`GET /goals/{id}/drafts/{submission_id}`) |
| The card: the permission line, Allow / No / Preview / Revoke permission | `dashboard/chat-resonance.js`, `dashboard/resonance-agent.js`, `dashboard/style.css`, `dashboard/i18n/*.json` |
| Downgrade to 0.95.1 | `tools/resonance_restore_pre_a4.py` |

## Lifecycle

**Scope.** `grants` has two layers: the root (`kind=root`, one target, source `owner_approved` or `legacy_frozen`) and the revision permission (the `narrow` of the root with the revision's target). `scope_state` returns one of: `none` (the goal is not assigned to an assistant or has no product path: no scope needed), `granted`, `pending`, `denied`, `revoked`, `missing`. `_gate` blocks every state other than `none`/`granted` with `block_reason` `scope_pending`, `scope_denied`, `grant_revoked`, `grant_missing` (a real block: `run_state=blocked`, no schedule set, no model call).

**New revision.** Inside the very transaction that creates a revision (`create`, `revise`, `drop_directive`, `assign_goal`), `_scope_sync`:
- same target as the active root: grants the new revision's permission, without asking;
- a different target, or no root yet: writes `scope_requests` (`create`/`expand`), grants nothing;
- the old revision's permission and requests become `superseded`; `_retire_old_revision` moves the old revision's unposted submissions to `superseded` and closes the old bindings.

**Bindings.** `bindings` pin a permission to one turn: `handoff` (a chat turn, key `message_ref`), `action`, `followup`, `experiment`, `approval`, `republish`. The key is `UNIQUE(goal_id, revision, origin_kind, origin_ref)`; reopening the same key returns the existing row, never REPLACE. States: `live` (accepts a submission), `sealed` (only completes a submission already received), `closed`, `dead` (revoked). Two checks: `_binding_block(finishing=False)` is `binding_accepts`, `finishing=True` is `binding_may_finish` (only the `grant` authority).

**Permission order.** `authority_clock.seq` increases in every transaction that creates a root, revokes, approves or re-grants. `_resonance_turn_agent` reads it before the engine runs and puts it into `turn.authority_seq`. The first `grant` binding of a message for a goal only accepts a root whose `seq` does not exceed the snapshot; every later binding of the same message must pin the same root. No exceptions (D1).

**Submissions.** `submissions`: `awaiting_scope` (a draft under a `draft` binding), `candidate`, `publishing`, `published` (+ `adopted_at`), `adopted_in_place`, `promoted`, `conflict`, `stale`, `superseded`, `rejected`. Sources: `submit_tool`, `background_text`, `observed_write`, `approved_draft`, `republish`. The bytes to post are always re-read from the draft file, with long dashes normalized, and must match the sha in the ledger.

**Posting (`host_publish`).** A guard on the submission's bytes, then:
1. `publish_intent` (checks the binding, the `publish` permission, pause, the guard settlement, the baseline; the `same` branch writes the marker immediately);
2. write the temp file `.<name>.<action_id>.tmp`;
3. `publish_commit` (`BEGIN IMMEDIATE`, recheck, re-read the target hash inside the transaction, write `commit_at`);
4. `os.replace`, `publish_finish` (does not recheck permission), then `adopt_submission` for chat-sourced and approved-draft submissions.

**Reconciliation** (`_reconcile`, `_reconcile_publish`): a posting not yet committed is cancelled, the submission goes back to `candidate` or `stale`; one already committed is completed from the draft; a posted submission not yet adopted is adopted exactly once (event key `adopt:<submission_id>`). A temporary read or write error after the commit does not settle a conflict: `publish_retry` keeps the action running and reschedules with spacing. The commit marker sets its own physical schedule `settle`, which comes due even when the goal is paused, revoked, cancelled or finished; the `settle` wake only completes a posting that has been settled.

**Completion obligation** (I13 to I16): if the draft file is temporarily unreadable the obligation is kept, if it is lost or has a wrong hash it is dropped with its own reason (`draft_missing`, `draft_hash_mismatch`); the `settle` schedule is only dropped when there is no half-finished committed posting AND no posted-but-unadopted submission left; while an obligation remains, the work schedule blocks with `publish_settling`, with no model call. The work wake rechecks the obligation also AFTER posting by itself: an error arising within that same beat blocks too. If the draft file is not yet readable before the commit marker, the submission is held (`hold_until`), the `settle` schedule rereads with spacing, and once readable the hold is dropped so the work schedule posts exactly that version.

**Intervening before the commit marker** (`_publish_held`): pause, a guard settlement, and feedback on the latest understanding being "Not quite" (`Chưa đúng ý` in the Vietnamese UI) all block a posting not yet committed, checked right inside the intent transaction and the commit-marker transaction.

**Owner commands** (`POST /goals/{id}/commands`): `approve_scope` (CAS on the request, revision, path, assistant, latest draft with the right sha), `deny_scope`, `revoke_grant`, `resume` (when revoking, re-grants a new root).

## Behavior changes versus 0.95.1

- A new goal with a product path always waits for the project owner's Allow, even when the assignment text names the target. A write by the brain in the goal-SETTING turn is not accepted (that turn had no scope at its start); a submission through the tool is kept as a draft and Allow posts it.
- Turning off an assistant's Resonance does not revoke the scope (I1): turning it back on carries on under the old root. But turning it off and on in the middle of a work turn makes that turn's submission `stale`, not reposted under the new version (previously A1 reposted held output using the new intent). The next wake redoes one turn.
- `_publish_latest` only posts a `candidate` submission; it no longer posts the bare output of an action. If the target file was deleted, it reposts the already posted submission under a new `republish` binding (current permission).
- Codex and the API engines receive the chat handoff through `javis_submit_deliverable` (`engine_support` gains `submit_tool`, `observed_write`).

## Downgrading

The first time the A4 code opens a pre-existing store, `_backup_before("grants", ".pre-0.96.0")` copies the store with the SQLite backup API, and then one transaction creates the tables and freezes legacy. Downgrading to 0.95.1 is only supported with `tools/resonance_restore_pre_a4.py --yes` while Jarvis 007 is off: it copies the current store to `resonance.sqlite3.post-0.96.0-<timestamp>`, then writes the snapshot in. Running 0.95.1 on an A4 store without restoring is not supported (the old code lifts the pause of a revoked goal; test G48 records exactly this limit).
