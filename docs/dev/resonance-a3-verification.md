# Resonance A3: code verification record (09/10/2026)

**Status:** the A3 code is written on branch `claude/resonance-a3-feedback-learning` (PR #598, reserved number 0.89.0), **awaiting code review**. The design passed review round 3 at `d6239d54`. No real-model pilot yet, not merged, not released.

Design: [2026-10-09-resonance-a3-feedback-learning-design.md](../superpowers/specs/2026-10-09-resonance-a3-feedback-learning-design.md) (section 13 is the matrix; section 19 holds the implementation notes). Guide: [resonance-a3-learning.md](resonance-a3-learning.md).

## Code

| Part | File |
|---|---|
| Pure policy `learning.v1`, the presentation section, mandatory messages, the lane P learner | `server/resonance_learning.py` (new) |
| Store: five A3 tables, two lesson indexes, the turn-hold ledger, lesson CAS inside the M5 transaction, reconciliation of held turns | `server/resonance_store.py` |
| `heartbeat.v2`: the `FOLLOWUP` and `TRIAL` classes | `server/resonance_heartbeat.py` |
| Host-built scenario set, the trial inside the A2 wake, the product-making turn, the lane P report path, the card's `learning` block | `server/resonance.py` |
| Routes `/resonance/reactions`, `/resonance/lessons`, `/resonance/lessons/{id}/decision` | `server/resonance_api.py`, registered at the end of `server/main.py` |
| Receipt lookup by message | `server/sessions.py` (`report_receipt_by_message`) |
| UI | `dashboard/chat-resonance.js`, `dashboard/resonance-agent.js`, `dashboard/style.css`, `dashboard/i18n/vi.json`, `dashboard/i18n/en.json` (59 keys per language) |

## Tests run (local machine, the root checkout's `.venv`, no real model)

| File | Result |
|---|---|
| `tests/python/test_resonance_a3_learning.py` | 109 checks passed |
| `tests/python/test_resonance_a3_api.py` (main.app, real receipts) | 18 checks passed |
| `tests/python/test_resonance_a3_rollback.py` (real 0.88.1 code, `83bff6bc`) | 11 checks passed |
| `tests/js/test_resonance_a3_ui.js` | 24 checks passed |
| 27 older Resonance test files (M1 to M5, A1, A2), `test_route_table.py`, `test_version_khop_changelog.py`, `test_i18n.mjs`, three older Resonance UI tests | all passed |

Commands to rerun:

```bash
python tests/run.py resonance -v
python tests/run.py --js resonance i18n
python tests/run.py route_table version_khop_changelog
```

## Matrix cross-check (design section 13)

**13.1, the minimum set by GOAL:**

| Case | Where checked |
|---|---|
| G1 | `a3_learning` (a reaction opens no turn, no assessment, the goal stays active) |
| G2a, G2b, G2c | `a3_learning` (the agent cannot write a reaction or decide a lesson; wrong brain; M4 feedback with the wrong revision) |
| G2b, G2e | `a3_api` (a session of another brain, a user message, an ordinary reply, a card block the model wrote itself) |
| G2d | M4 behavior unchanged, locked in `test_resonance_mvp_feedback.py` |
| G3a, G3b, G3c, G3d | `a3_learning` (set value, nonce, second proposal, store reopen); G3d in `a3_ui` |
| G4a, G4b, G4c | `a3_learning` |
| G5a, G5b | `a3_learning` (revoking lane P; revoking lane M in R1b) |
| G6a, G6b, G6c, G6d, G6e | `a3_learning` (stopping mid-trial with a fake engine that calls the action on the 4th turn) |
| G7a, G7b, G7c | `a3_learning` |

**13.2, additions per the design:**

| Case | Where checked |
|---|---|
| A1, A2, A3 | `a3_learning` and `a3_api` (real drain_outbox, the `quiet` flag) |
| A4 | Replaced by R3a |
| A5, A6, A7 | `a3_learning` (A7 is R3d) |
| A8 | `a3_learning` (assistant file hash, the registry) and `a3_api` |
| A9 | `a3_learning` and `a3_api` (really deleting a message in the session store) |
| A10, A11, A13 | `a3_learning` |
| A12 | `a3_rollback` |
| A14 | R5e |
| A15 | `a3_ui` |
| A16 | `a3_learning` and `a3_ui` |

**13.3, 13.4, per review rounds 1 and 2:**

| Case | Where checked |
|---|---|
| R1a | `a3_learning`: a hook that inserts Dismiss after the final gate, before the settling transaction |
| R1b, R1c, R1d | `a3_learning` |
| R1e | The old M5 tests (`test_resonance_mvp_trial*.py`) pass unchanged |
| R2a to R2f | `a3_learning`; R2a also in `a3_api` |
| R3a to R3i2 | `a3_learning` |
| R4a to R4d | `a3_learning` (`JAVIS_RESONANCE_CALL_CEILING=8`); R4d inside R3a (the product turn runs when `left` equals exactly the reserve turn) |
| R5a, R5b, R5c | `a3_learning`, through the real cancel path: cancelling the wake exactly while the prepare phase is running |
| R5d, R5e | `a3_learning` |
| R6a to R6d | `a3_rollback`, real 0.88.1 code |
| R7a to R7d | `a3_learning` |

## Key figures verified

- **Full lane M cycle, quota 9 (R3a):**
  - 3 work turns, 4 trial turns, 1 product-making turn using the held turn: 8 engine turns in total, `calls_used` = 8, 1 reserve turn left.
  - The product turn used the new method, and the goal was achieved.
  - The four trial actions carry the current revision; the prompt of the separately kept scenario is built from the words of revision 1.
- **Default quota 6 (R3b):** `skipped/budget`, 0 extra turns.
- **Shared ceiling 8 (R4a):** feedback takes over the held turn, `calls_used` stays 8, and `FOLLOWUP` does not run any more.
- **Cancel before the engine (R5a):**
  - the held turn goes back to `held` with `gen` 2, `calls_used` stays 8;
  - a repeated cancel returns False;
  - the next tick runs exactly once.
- **Dying mid-trial (R5e):**
  - reopening the store does not settle the trial while no wake holds the lock;
  - the next wake settles it as `interrupted`, the lesson as `unknown`, and returns the held turn once;
  - `calls_used` = 3 + the number of trial turns whose intent was recorded.
- **A3 → 0.88.1 → A3 (R6a):**
  - the old code settles the product-making reason with 0 engine turns, without touching the held turn;
  - A3 rebuilds exactly one reason (`gen` 2), and runs once;
  - a third reopen adds nothing.

## Real bugs found while writing tests

- **R5e:** a trial interrupted midway left no wake schedule at all, so the held turn stayed stuck in `held` and the trial stuck in `running`. Fixed by scheduling an `action_recovery` (check only) at the moment the trial lock expires (design section 19, I2).
- **The `goal.method_changed` message was not sent:** `begin_action` did not yet return `hold_id`. Fixed, and R3a locks it in.
- **The Lessons section attached a click listener on every redraw:** one click would send several requests. Prevented with an attach-once flag.

## Limits

- No real-model pilot yet. The pilot proposal is in design section 13.5: at most 8 turns, quota 9, needing separate approval from you.
- The UI has not been inspected in a real browser; the UI was only checked through pure functions under node.
- The project's whole test suite (`python tests/run.py`, 626 files): 608 green, 18 red before the emoji fix. Told apart by running exactly those 18 files on a clean copy of `main` (`83bff6bc`, git archive):
  - 15 files are also red on `main`: agy_prompt_dai, antigravity_cli, ba_loi_mac_va_telegram, cai_windows, grok_cli, ignore_files, install_admin, khoi_dong_nhe, link_file_uri, machine_translations, memory_hoa_thuong, model_theo_phien, ollama_local, terminal, windows_no_console.
  - `test_icons`: a real A3 bug (an emoji on the feedback row), fixed into a text label, rerun green.
  - `test_project_khung`: run alone on the A3 branch it is green, red only fleetingly during the full-suite run.
  - `test_image_vision`: red because of a leftover `__pycache__` folder in the worktree (`system/plugins/zalo-image`), not because of A3 code.
- Lane M will often be skipped in real use (it needs a quota of 9 or more and an earlier understanding with the same criteria); this is a limit settled in D4, not a bug.

## After code review round 1 (`5b4f48a6`)

Report: `exports/reviews/PR-598-A3-code-5b4f48a6-review.md` (outside git), 3 P2s. Fixed at `efdfb8a8`.

| Item | Fix | Regression |
|---|---|---|
| P2-1: cleaning up the trial also wiped the `check` obligation, losing the `guard_recheck` just written | The trial's reconciliation appointment gets its own code `trial_recovery` (obligation `trial`), and only that appointment is settled, by id | RV1: guard undetermined mid-trial, fix the source, the goal gets unstuck; a control where the guard really jumps still keeps the settlement |
| P2-2: Applying an expired proposal | `lesson_decide(apply)` checks `expires_at` and that the basis is still alive inside the transaction | RV2 at the store (expired, basis lost, control still within time) and through the real route (409 `expired`) |
| P2-3: the trial's store and file work ran on the event loop | Every store, file and evidence step on a worker thread, waiting to finish when cancelled; a trial turn cancelled before the engine becomes `not_run` and is refunded; the A3 routes run the store on a worker thread | RV3: storage slowed by 150 ms at three steps, the loop is not blocked; cancel and repeated cancel at reservation, at intent recording, at settling (lock released after the worker); a storage error at settling |

The reviewer's independent check script ran with `--expect-fixed` on `efdfb8a8`: the result is in `exports/reviews/A3-code-r2-review-script-output.txt`.

## After code review round 2 (`61d0d8ca`)

Report: `exports/reviews/PR-598-A3-r2-61d0d8ca-review.md` (outside git), 2 P2s. Fixed at `52cf70e4`.

| Item | Fix | Regression |
|---|---|---|
| P2-1: a mkdir failure after the reservation had committed was read as "not created", the reconciliation appointment was settled, 5 turns stuck | Separate the reservation transaction from creating the folder; a failure after commit settles the trial and refunds in full; if settling fails too, keep the trial `running` and schedule a reconciliation; a failure before commit records `storage_error` | RV4: blocking with a real file, recovery, restart, repeated reconciliation; settling also fails then settles itself later; failure before commit |
| P2-2: `_agent_intent` read SQLite on the event loop | Run through `_off_loop` | RV5: every `agent_by_key` call in the trial is off the loop, the watchdog clock does not stall |

The reviewer's two independent check scripts ran with `--expect-fixed` on `52cf70e4`: `exports/reviews/A3-code-r3-script-r1-output.txt` and `exports/reviews/A3-code-r3-script-r2-output.txt`.

Limits still stated:
- `run_once` (shared with the A2 work turn) still has a few small file-metadata operations (`resolve`, `is_dir`, `exists`) and builds the engine on the event loop.
- `_TrialCall.release`, when the engine cannot be built, still calls the store synchronously, like A2's `_ReservedCall`.
- These paths existed since A2 and are unchanged in A3.

## UI inspection on the sandbox (after `b33f3e3b`)

Sandbox server on port 7788, its own state and brain in `exports/sandbox-a3` (outside git), background tick off, a prompt-driven fake engine (`exports/sandbox-a3/seed.py`). In-app browser, desktop 1366x860 and a narrow 375x812, Vietnamese. 0 real model turns. Full record and screenshots: `exports/reviews/A3-ui-sandbox-record.md`, `exports/reviews/a3-ui/`.

Five UI bugs found and fixed, merged into four lines (I12 to I14 in design section 19):

| Bug | Fix | Regression |
|---|---|---|
| The feedback row did not show on the Partners page (GET 400 because of an empty session, then because of the previous assistant's session) | The page sends an empty session; the server looks up the receipt by report key and goal | UI1 (API): GET and POST by the empty-session triple; still strict with a wrong session, another brain, a key with no receipt. UI4 (JS) |
| The preview showed raw markdown, the method lesson showed the code `work.checklist.v1` | `plainMd`, `to_label`, `goal_label`; a pending trial has its own block with a Dismiss button | UI2 (API and JS) |
| The 409 conflict note vanished as soon as the list redrew | Keep the note across one redraw | UI3 (JS) |
| The Lessons section did not reload after feedback | The event `javis:resonance-lessons` | UI5 (JS) |

Ten new checks (4 Python, 6 JS) were all red on the code at `b33f3e3b` and green on the fixed code.

## The A3 pilot runner (not yet run for real)

`tests/python/test_resonance_a3_pilot.py`, fixing the pilot package per the review `224a109a` (three P2s). Skipped when the variable is not set.

- **Two layers of ceiling.** The store ceiling `JAVIS_RESONANCE_CALL_CEILING=8` also counts the 3 fake turns that seed the deadlock. A separate real-turn gate at the engine-call boundary: at most 5, written to the ledger on disk before every call, never reset, never refunded.
- **Stop immediately on error.** On an error turn, a timeout, a cancellation, a broken output, or a token about to expire, the gate closes; every later call is refused before the engine (the host sees the engine as not ready, no turn counted). If the process dies mid-call, the `reserved` row still counts.
- **The M5 rule is kept.** The apply branch only when `eligible` (better on the trial set, worse nowhere, no unknown). The branch label keeps the cause: `rejected/no_improvement`, `rejected/regression`, `inconclusive/unknown`, `technical_failed (...)`.

The dry run covers 13 scenarios using two processes per scenario (build and run, then reopen the store with the gate fully closed and reconcile the two turns): win, no_improvement, regression, unknown, an engine error on the first turn, on the last trial turn and on the product turn, timeout, token about to expire, the process dying mid-call, a storage error at settling, the gate ceiling mid-trial, the store ceiling too low. Results and the approval wording: `exports/reviews/A3-pilot-run-request.md` (outside git).

Runner review `ffcbc940` (outside git: `PR-598-A3-pilot-ffcbc940-review.md`), two P2s, fixed in the runner, with no change to `server/` or the scenario:

| Item | Fix | Regression (in the dry run, through real code) |
|---|---|---|
| P2-1: the technical-failure branch still came out as `pending_content_review` | A single summarizing function `finalize` for the real run: preconditions, the exit codes of the two processes, the report structure, the gate not closed, a valid ledger, phase 2 not calling the engine, the turn count matching exactly the content branch. Anything else is `technical_failed`, recorded as FAIL so it exits non-zero; the original branch is kept | `finalize` on 12 scenarios; the real `main_real` with a fake `run`/`auth` on 8 cases (no_improvement, first-turn error, token, dying mid-turn, wrong turn count, phase 2 exiting 1, missing report, broken auth gate) |
| P2-2: a broken turn ledger was treated as a new ledger | An empty ledger is only created by `RealCallGate.create` at the start of the run, together with a `.started` marker file. A read error, broken JSON, wrong structure, wrong sequence number, unknown state, changed ceiling, a file lost after the start, or a ledger with fewer turns than the receipts in the store: the gate closes, does not reserve, does not overwrite, and logs the error | 13 ledger cases, including controls for fresh creation and reopening after a `reserved` row |

## The real pilot (10/10/2026) and the changes after the pilot

- **Pilot:** run once at `fd9c034b` with the project owner's approval. 4 Sonnet turns through Claude Code (ceiling 5), result `rejected/no_improvement` (both scenarios `met/met`), the new method was not applied, the held turn was returned, phase 2 did not call the engine. The content review passed within the scope of the scenario; the `eligible` branch followed by redoing the product still has no real-model evidence. Original record and post-check report outside git: `exports/reviews/a3-pilot/real/`, `exports/reviews/A3-pilot-real-result.md`.
- **Waiting time after Revoke (`learning.v2`, I15):** Revoke blocks re-proposing the same (assistant, key, value) for 14 days, the same as Dismiss. The TV regression in `test_resonance_a3_learning.py`: within 14 days it does not propose again; a different key and a different assistant are not blocked; after 14 days it proposes again if the feedback is still within the window, and never applies by itself; old feedback outside the window is not enough. The "one day after Revoke" case was red on the old-version store.
