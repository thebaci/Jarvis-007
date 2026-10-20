# Resonance A5: code verification record (2026-10-12)

A team of one maker agent and one reviewer agent. Final design: [2026-10-11-resonance-a5-maker-reviewer-design.md](../superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md) (`56f7ab50`; option A for hand-edited files). Guide: [resonance-a5-team.md](resonance-a5-team.md).

**Status: the code passed code review round 2 at `05e9b065` (Codex, 2026-10-12); the pilot gate passed review round 3 at `33cec518`; the real pilot real-2 at `33cec518` was accepted by the reviewer within the scope of one `pass_first` sample (1 maker call, 1 reviewer call, 0 chat; the fix round has not been proven with a real model). Integrated with `main` 0.108.0 under number 0.109.0 (final integration review passed at `bd5663da`).** A5 **shipped in 0.109.0** (`bfb1c29f`, PR #616, 2026-10-13; `main` CI run 38369853756 and image build run 38369852881 succeeded; image `ghcr.io/blogminhquy/javis-os:0.109.0`, digest `sha256:3890f824…`; the VPS has not pulled it). Pilot scenario and runner: [resonance-a5-pilot.md](resonance-a5-pilot.md). The code-verification sections use a FAKE engine; real model calls appear only in the section [Real pilot](#real-pilot-2026-10-13).

## New tests

| File | Content | Cases |
|---|---|---|
| `tests/python/test_resonance_a5_team.py` | Main flow, team attachment through the real host path (the `javis_goal` plugin, the `/goal-requests` route), pin set and schedule, concurrency, restart, reviewer off/on/lost/retired, hand-edited file and snapshot, permission and stop, tag | T1 to T4, T10 to T14, T17 to T29, T31 to T46, T55 to T60; parse fails closed (T5, T26) |
| `tests/python/test_resonance_a5_budget.py` | Role ledger, trace table V1, V2, V3, V5, V8, call refund, retry counter, reconciliation schedule, fix round | T5 to T9, T15, T16, T47 to T54, T61 to T67 |
| `tests/python/test_resonance_a5_rollback.py` | REAL 0.108.0 code (`c4fb614d`, through `git show`; before integrating `main` it was 0.100.0 `a02663cb`): upgrade, downgrade without restoring (the limit is recorded), the restore script, upgrade again | T30 |
| `tests/python/test_resonance_a5_api.py` | Real routes: choose and clear the reviewer, reject an assistant that is not enabled or the agent itself, the `team` block of the goal view, the `team_detach` command | 4.2, 11, 12 |
| `tests/python/test_resonance_a5_perf.py` | 200 goals with a team versus 200 without; a 10 ms timer while the review saves evidence slowly | 14 |
| `tests/js/test_resonance_a5_ui.js` | The Reviewer field (only enabled assistants, not by tag), the team row, feedback, the two buttons and their requests, i18n | 11 |

Cases that go through the real host path use a real SQLite store, the real `form_goal` (tool and API), the `_gate`, and the real `R.advance` and `R.tick`; only the engine is fake (roles are split by the call's system instructions). `goal_team` or `reviews` are not pre-inserted into fixtures. Deliberate exceptions, stated in the tests: T12 edits the running review row directly to create a mismatched verdict (which can only happen if the data was tampered with); T14, T15, T61, T62, T64, T66 call the host's own `_advance_prepare` and `_review_pre` phases and then stop midway to simulate a process dying or being cancelled at exactly that point.

## Requirements and tests

| Requirement (GOAL, design) | Test |
|---|---|
| Attach the team in the create transaction, for both the tool and goal-requests; idempotent; not through `assign_goal` | T31, T32, T33; T36 (an old goal has no team) |
| Durable identity for both roles, the team is not chosen by tag | T46, T60; API (choose by slug, store the key); UI (the field does not go by tag) |
| Permission gate, snapshot, bundle, parser that fails closed; re-check the bundle when saving the result and when closing | parse (T5, T26); T11, T12, T19, T43, T58, T59; `finish` refuses without a valid review (a guard in the store) |
| Total 8, maker 4, reviewer 4, at most 2 rounds; no self-upgrade | T1, T4, T7, T8, T47 to T50 |
| `seq` is only for tracing; the cap of 3 and the backoff count `charged` of the exact bundle | T5, T14, T39, T61, T62, T63 |
| Refund only when sure the model was not called; cancel and engine-cannot-be-built share the refund path, idempotent, never left `running` | T15, T53, T61, T64, T65 |
| The model may have run, so the call is counted | T6, T14, T16, T23, T63 |
| After a restart, reconcile by code, never becoming a maker call; retry with the right backoff and enough calls left | T14, T39, T44, T66; T50 (the last call is not retried) |
| needs_changes number 1 and 2 allow a fix, number 3 stops; a stale or wrong-version verdict does not increase the round | T3, T4, T47, T67, T12 |
| A hand-edited file waits, no model call, no closing; a review is reused only when bytes and bundle match; Drop the review requirement is a project owner action | T10, T55, T56, T57; T24, T46 |
| The reviewer has no write permission; an unknown field changes neither permission nor limit | T1 (the target file is the maker's version), T26 |
| A3's lane M is blocked by the store on a goal with a team | T51, T8 (no experiment is proposed) |
| I/O does not block the event loop; cancel waits for the write phase to finish | perf (10 ms timer); T16 (cancel during the engine call) |
| Downgrade to 0.108.0 through the snapshot | T30 |

## Results (local machine, the root checkout's `.venv`, code at `0ae4cc2b`)

| Command | Result |
|---|---|
| `python tests/python/test_resonance_a5_team.py` | 86 ok, exit 0 |
| `python tests/python/test_resonance_a5_budget.py` | 31 ok, exit 0 |
| `python tests/python/test_resonance_a5_rollback.py` | 11 ok, exit 0 (real 0.100.0 code) |
| `python tests/python/test_resonance_a5_api.py` | 10 ok, exit 0 |
| `python tests/python/test_resonance_a5_perf.py` | 5 ok, exit 0 (200 cards with a team are about 7 ms slower per card than without; the 10 ms timer is on time when the review saves evidence slowly at 0.2 seconds) |
| `node tests/js/test_resonance_a5_ui.js` | 32 ok, exit 0 |
| `tests/run.py resonance route_table i18n version_khop_changelog nhat_ky_song_ngu tai_lieu_song_ngu ignore_files phien_ban_moi_nhat prompt_budget prefix_slim agent_tags workspace` | 63/63 files green, exit 0 |
| Whole repo `tests/run.py` (code at `5048fc4d`, before the last commits that only changed messages, tests and docs) | 639/654. The 14 red files match exactly when the same 14 files are run on an export of clean `main` `a02663cb` (machine-dependent tests: agy_prompt_dai, antigravity_cli, ba_loi_mac_va_telegram, cai_windows, grok_cli, install_admin, khoi_dong_nhe, link_file_uri, machine_translations, memory_hoa_thuong, model_theo_phien, ollama_local, terminal, windows_no_console). The 15th red file is `test_resonance_a2_ui.js`: it counted 24 wake-reason labels and A5 added exactly 6; it was updated to 30 and runs green in the group above |

## Bugs found while writing the code, fixed, and controls

The final test was run on the exact code tree before each fix (a `git archive` export, with the current tests copied in):

| Bug | Fixed in | Red on the code before the fix |
|---|---|---|
| A `stale` or `review_mismatch` verdict scheduled no wake, so the goal stood still | `2b264122` (`record_review`, `review_interrupted` schedule a check-only `review_done`) | T12, T19, T43 on `3c290b5c` |
| Comparing a hand edit with `current_artifact_ref`, but that function returns empty at a new revision that has no work call yet, so a new revision was treated as hand-edited | `2b264122` (`_disk_sha`) | T11, T37 on `3c290b5c` |
| A check-only `action_recovery` schedule stayed after the review call finished, pulling the physical schedule earlier than the backoff | `2b264122` (`_drop_idle_action_recovery`) | T39 on `3c290b5c` |
| A new user message on a goal with a team hit the `use_hold` flag (take over the held call if there is one), and the work call was refused | `2b3ab099` (ignore `use_hold` when there is a team, only refuse `require_hold`) | T8, T51 on `2b264122` |
| The review call's engine could not be built: the row recorded a generic reason, and the re-check compared the store's time (real time) with the wake's time, so the review call tried to build again immediately | `2b3ab099` (reason `engine_not_ready`; wait by the `review_recheck` appointment on the same clock as the wake) | T53, T65 on `2b264122` |

Output: `a5-control-team-on-3c290b5c.txt`, `a5-control-budget-on-2b264122.txt` (evidence folder, outside git).

## Old tests that had to change because behavior changed by design

- `test_resonance_a3_learning.py`: the heartbeat policy version `heartbeat.v2` became `heartbeat.v3` (design section 10); the two A3 class checks are unchanged.
- `test_resonance_a2_ui.js`: the number of wake-reason labels on the card went from 24 to 30 (six A5 codes).
- `tests/python/route_table.json`: added exactly one route at the end (`POST /resonance/agents/reviewer`); the order of the old routes is unchanged.

## UI smoke test on a sandbox (fake engine)

Sandbox server on port 7788 running the worktree's code; temporary state and brain (in `.playwright-mcp/sbx`, gitignored, a short path to avoid Windows' 260-character limit), the Resonance beat running for real, `main._resonance_engine` replaced by a two-role fake engine that reads a script from a control file. Chromium through Playwright, Vietnamese UI, desktop 1366x860 and narrow 375x812. Turning on Resonance and choosing the reviewer were done in the UI; goals were seeded with the real `form_goal` (simulating the chat call that creates a goal, with no real chat call).

Passed, cross-checked against the store:
- The Reviewer field lists only assistants that have Resonance on (no "assistant off"); once chosen, the host stores the pair by key.
- Goal 1: click Allow on the card; the maker call published the first version, the review said "needs changes"; the card shows "Maker: nguoi-lam · Reviewer: nguoi-duyet", "Reviewed version: 7cdeda8d · Needs changes (round 1/2)", "Waiting for nguoi-lam to apply the feedback", "Calls left: maker 3/4 · reviewer 3/4" and the feedback. The fix call published a new version, the review passed, the goal was met; calls (2, 2, 4); the target file is the fixed version.
- Goal 2: turned the reviewer off before the first beat: `blocked/reviewer_off`, 0 model calls; the card has two buttons. Click "Turn the reviewer back on", the real confirm box clearly says "counts one review call", agree: the goal woke again, maker, review, met; calls (1, 1, 2).
- Goal 3: reviewer off, click "Drop the review requirement": Cancel in the confirm box sends nothing (the store is unchanged); Agree: the card shows "Review requirement dropped", and the goal settles by the usual rules with 1 maker call, 0 review calls.
- Width 375 px: the card shows the full team row, no horizontal scroll (`scrollWidth = innerWidth = 375`).

Screenshots: `a5-s01-reviewer-picker.png`, `a5-s02-needs-changes.png`, `a5-s03-reviewer-off.png`, `a5-s04-narrow-375.png`.

Not observed in the UI (behavior tests exist): a hand-edited file on the card (T10, T55 to T57), running out of rounds (T4), running out of calls (T7, T8), an unreadable review (T5, T50). The console errors in the smoke test belong to pre-existing pages (`/tools/optional` 401, an old session code in the sandbox that 404'd earlier), unrelated to A5.

## Limits of the evidence and remaining limits

- Every check uses a fake engine; the number of real engine calls is 0. No pilot yet, no VPS measurement.
- (Round 1 recorded here the limit "a `maintain` goal is not blocked by review"; code review round 1 identified that as bug R3, fixed in round 2 below.)
- After `team_detach`, a new call counts toward the goal's total but not toward `team_calls` (the role ledger is kept as a record), as in design section 6.2.
- A WORK call of a goal with a team, when the engine cannot be built, keeps A2 behavior (closes with the permanent error `engine_blocked`) plus a refund of the maker share; only the REVIEW call goes through the full `_refund_not_run`. Both paths refund exactly once.

## Round 2: fixing the three P2s of code review round 1 (base reviewed: `d22b6c66`)

Review: `exports/reviews/PR-616-A5-code-r1-review.md`. Regression: `tests/python/test_resonance_a5_code_r1.py` (real host path, fake engine; the button's request is built with the real `teamHtml`/`requestFor` through node and then sent to the real FastAPI route).

| Bug | Fix | Test |
|---|---|---|
| R1: an error in the prepare phase after `begin_action` lost the reviewer call and ate into the attempt cap | The `mark_engine` mark (writes `engine_at` and `running` in one transaction) is the last step before the engine; an error before the mark goes to `_prepare_failed`: `abort_action(code='prepare_error', recheck_at)` refunds the total, the role, `charged` and the pending reason AND parks the goal with a recheck appointment in the same transaction. If the refund also fails, reconciliation after the lock expires refunds thanks to the missing `engine_at`. Applies to work calls too (`blocked/prepare_error`, appointment `prepare_recheck`) | R1a ordinary error, R1b error at another point, R1c error plus repeated cancel (the lease is released after the refund), R1d the refund also fails, R1w/R1w2 work call, R1wn a new message still opens a call; controls R1e (past the mark it is `interrupted`, counted), R1f (an old action without the flag keeps the old rule), existing T16/T63 (cancel while the engine runs is still counted) |
| R2: the "Turn the reviewer back on" button on an old card could enable a new agent with the same slug | The button pins `agent_key`; route `POST /goals/{id}/reviewer/enable`; `team_reviewer_enable` checks in one transaction that the team is still in effect, still pins exactly that key and the key is still `active`, and only then enables; otherwise 409 with a fresh goal view. The enable button on the assistants page is unchanged | R2 old card 409 (the new agent is not enabled, the pin holds, the ledger is unchanged), R2 through the route with the same key 200 without changing the ledger, clicking again does not raise the version, team dropped, wrong key, owner only, the ordinary toggle keeps its behavior; UI test `test_resonance_a5_ui.js` |
| R3: maintain goals and the discovery step had a team but no review call | `_settle` calls `_team_settle` for every version that passes the check of a goal with a team BEFORE the discovery, maintain, finish or wait-for-human-confirmation branch; `goal.maintained` is only emitted after `pass`; if the same pin set already has `pass`, it goes straight through | R3 maintain pass then healthy, many periodic check beats do not review again, a hand edit waits at `source_drift`, three needs-changes verdicts give `review_rounds`, an unreadable review gives `review_unknown`, reviewer off; discovery pass then `discovery_done`, needs changes then pass; control achieve |

Non-blocking notes done in the same batch (separate from the three P2s): the review call's receipt keeps the engine diagnostics (`engine`, `usage`, `tool_calls_observed`, `engine_error_code`, `engine_error_detail`), taking no part in the decision; the sentence "No A5 code yet" (Vietnamese: "Chưa có mã A5") at the top of the design was fixed.

**Changed to follow the new behavior (expectations were not loosened):**
- Three fixtures that simulate "dies in the middle of an engine call" (`test_resonance_a2_heartbeat.py`, `test_resonance_a3_learning.py` R5d, `test_resonance_mvp_run.py` restart) create the action with `begin_action` directly; they now add `mark_engine` as the real host does before the call. The `interrupted` expectation is unchanged.
- `test_resonance_a2_ui.js`: the number of wake-reason labels went from 30 to 31 (`prepare_recheck`).
- `test_resonance_a5_ui.js`: the button carries `agent_key`, and the request goes to the card's route.
- `route_table.json`: added exactly one route at the end.

**The reviewer's independent script.** The original `PR-616-A5-code-r1-probe.py --expect-fixed` on the new head: C1, R3 (2 cases), R1 reopen store, R2 PASS; the first R1 case FAILs because the injection point `set_run_state(..., 'running')` is no longer called after `begin_action` (`injected: false`, the review call ran for real so the ledger (1, 1, 2) is correct). The adjusted version only moves the injection point to `store.mark_engine` (the same position: after the reservation, before the engine), with no change to the scenario or the expectation: 6/6 PASS, exit 0.

**Control on `d22b6c66`** (a `git archive` export, the new tests copied in, run CASE BY CASE): real behavior bugs at R1b (a `running` row, `charged=1`, (1, 1, 2)), R2 old card (the request goes to `/resonance/agents/toggle` by slug, HTTP 200, the new agent gets enabled), R3 (8 checks: maintain and discovery had no review call). The remaining R1 cases and two R2 cases throw `AttributeError` because the new API is missing (`mark_engine`, `team_reviewer_enable`); the behavior of those R1 scenarios on `d22b6c66` was already reproduced by the reviewer's script. Controls green as expected on the old code: R1e, R1f, the ordinary toggle, reviewer off, achieve.

**UI smoke test (sandbox port 7788, fake engine, Chromium 1366x860).** Simulated actions done with a seeding script (stated): create the goal through `form_goal`, grant the scope, turn the reviewer off, and "delete the reviewer and create a new assistant with the same slug" (`agent_retire` then enable, turn the new key off). Clicks done in the UI:
- The card has a "Turn the reviewer back on" button carrying the durable key (`data-key="ag_…"`). Click, agree in the confirm box: `POST /goals/{id}/reviewer/enable` 200, exactly the old key was enabled, the goal worked, the review passed, closed with (1, 1, 2).
- An old card (after replacing the reviewer with one of the same slug): click, agree: 409; the new agent is still off; the goal still pins the old key; 0 model calls; the card is redrawn with the sentence "The goal changed since you looked. The card is updated; review it and click again if needed." (Vietnamese: "Mục tiêu vừa đổi so với lúc bạn xem"). Screenshot `a5r2-s01-stale-card-409.png`. Console errors: the 409 of that very request and the pre-existing `/tools/optional` 401.
- The old card still shows the `reviewer_off` state until the gate's next wake (appointment `agent_recheck`), when it becomes `reviewer_retired`; clicking again in the meantime keeps getting 409.
- R3 has no UI change of its own (the card shares the team row); the behavior is checked by tests.

**Remaining limits.**
- Fake engine; the number of real engine calls is 0; no pilot, no VPS measurement.
- The permanent errors of `run_once` before the call (`output_scope`, `action_exists`, `invalid_action_id`) still close as `cancelled` under A2 and do not refund the call (unchanged in this round; they are permanent errors, not exceptions).
- When the prepare phase fails, the goal parks until the recheck appointment `ERROR_BACKOFF_S[0]` (one hour); a new user message still opens a work call immediately.

**Round 2 results** (local machine, the root checkout's `.venv`, code at `b10abf4b`):

| Command | Result |
|---|---|
| `test_resonance_a5_team.py` / `_budget` / `_rollback` / `_api` / `_perf` | 86 / 31 / 11 / 10 / 5 ok, all exit 0 |
| `test_resonance_a5_code_r1.py` (new) | 45 ok, exit 0 |
| `node tests/js/test_resonance_a5_ui.js` / `test_resonance_a2_ui.js` | 36 / 10 ok, exit 0 |
| Reviewer script, adjusted version `--expect-fixed` | 6/6 PASS, exit 0 |
| Reviewer script, original version `--expect-fixed` | 5/6, exit 1 (the first R1 case could not inject the error, see above) |
| Group: resonance, route_table, i18n, version/changelog, bilingual docs, ignore_files, version, prompt_budget, prefix_slim, agent_tags, workspace | 63/64; the only red is `test_ignore_files.py` because the new test file had not been `git add`ed at that moment; green in the whole-repo run after the commit |
| Whole repo `tests/run.py` | 641/655; the 14 red files match exactly the red list on clean `main` `a02663cb` (machine-dependent tests), no new red |

## Code review round 2 and the pilot gate

**Code review round 2 (Codex, 2026-10-12) passed at `05e9b065`.** No new P1 or P2. The three P2s of round 1 were handled. The reviewer ran by themselves:
- the independent script, adjusted injection point: 6/6;
- five extra checks on a goal without a team: 5/5;
- `tests/run.py resonance_a5`: 7/7 files;
- the A2, A3, MVP, A2 UI and route table group: 5/5 files.

The reviewer did not re-run the whole repo and did not repeat the browser smoke test.

Limits the reviewer recorded (not blocking the pilot preparation gate):
- when the prepare step fails, the goal waits one hour;
- an old card updates slowly;
- three permanent errors before the engine (`output_scope`, `action_exists`, `invalid_action_id`) keep the old path;
- the two roles share the background-work engine.

**A5 is not finally accepted and not yet released.**

**The pilot gate (no product code change).** Scenario, limits and evidence: [resonance-a5-pilot.md](resonance-a5-pilot.md). New files, same commit `18b2ab60`:

| File | Role |
|---|---|
| `tests/python/_a5_pilot_ledger.py` | Per-role call ledger: reserve before building the engine; has a role cap, a total cap and a phase cap; an outcome other than `ok` closes the ledger; a corrupt ledger grants no call; a blocked attempt records `refused`; branch classification |
| `tests/python/_a5_pilot_server.py` | Runs the checkout's `main.app`, only wrapping `main._resonance_engine` with the ledger; dry swaps in a fake engine, and the "real" path is a tripwire |
| `tests/python/test_resonance_a5_pilot.py` | The real and dry runner (it only runs when `JAVIS_RESONANCE_A5_PILOT` is set) |
| `tests/python/test_resonance_a5_pilot_gate.py` | The ledger logic, needing no server or model |

**Results** (local machine, code at `18b2ab60`, product code equal to `05e9b065`):

| Command | Result |
|---|---|
| `JAVIS_RESONANCE_A5_PILOT=dry python tests/python/test_resonance_a5_pilot.py` | 12/12 cases, exit 0. Every case: `commit 18b2ab60`, clean tree, 0 real calls, the sandbox server's engine-call ledger verified as 0 |
| `python tests/python/test_resonance_a5_pilot_gate.py` | 35 ok, exit 0 |
| `tests/run.py resonance_a5 ignore_files tai_lieu_song_ngu version_khop_changelog nhat_ky_song_ngu route_table phien_ban_moi_nhat` | 15/15 files, exit 0 |

Details of the dry cases:

| Dry case | Branch | Ledger (maker, reviewer) | Verdict |
|---|---|---|---|
| `main_pass` | `pass_first` | (1, 1) | dry_ok |
| `main_fix` | `one_fix_then_pass` | (2, 2) | dry_ok |
| `fix_cap` | `pilot_cap_after_two_reviews`; the store ceiling blocks the third fix call at reservation | (2, 2) | dry_ok |
| `ledger_cap` | as above; the store ceiling raised to 8 (dry only), the ledger blocks before the engine is built, the host refunds the call | (2, 2) | dry_ok |
| `review_unknown` | `review_unknown`; no retry | (1, 1) | dry_ok |
| `maker_error` | `maker_error`; the ledger closes | (1, 0) | dry_ok |
| `cost`, `auth`, `ledger_exists`, `precondition` | stopped before background work | 0 | stopped |
| `ledger_corrupt` | corrupt ledger, no call granted; ledger unverified | unverified | stopped |
| `tripwire` | the tripwire records an event; one `not_built` row because the ledger reserves before building (conservative) | (1, 0) | stopped |

Found by the runner, which had never run for real:
- The branch classification at first did not recognize the store ceiling as a blocking layer. The `fix_cap` case showed that the store ceiling blocks before the ledger, so the goal became `blocked/budget` with the ledger seeing nothing. The classification function was fixed and the `ledger_cap` case was added so the ledger layer can still be proven.
- The initial hash check had the wrong target (`accepted_ref` is the registration mark, not the work call). It was changed to two checks: the hash is the normalized bytes of one work call's output, and the snapshot the reviewer read hashes back to the same hash.

**Not yet proven** (only a real pilot can answer):
- a real model in both roles;
- the review content being useful;
- real latency;
- the behavior of the `anthropic-cli` background-work engine in the sandbox.

Local performance is not VPS evidence.

### Pilot gate review round 1 (head `3378832d`): three P2s in the runner, fixed

Review: `exports/reviews/PR-616-A5-pilot-gate-r1-review.md`. Product code unchanged; code review round 2 still stands. Fixed in commit `2468919c`, touching only the runner, tests and docs.

| Bug | Fix | Test |
|---|---|---|
| R1: the ledger recorded `ok` for a result the host treats as an error (a `final` with `is_error` or `dua_token`, an error after `final`, a tool call inside a text-only call) | `Counted` applies `_ask`'s error rules to each frame. `ok` is only provisional: an error that arrives later downgrades it and is never upgraded back. Added a wrapper around `GoalDeps._ask` to cross-check the host's final conclusion (`host_<code>`). If the host stops reading after a valid `final`, `ok` stays | Gate test: cases that run through the real `_ask`; `final` then cancel, exception or stop reading; no error upgrade; the second cross-check layer. Dry: `final_is_error`, `maker_error`, `reviewer_error` |
| R2: the real verdict did not rule out an engine error, a timeout or a ledger lost at the final read | The `decide_acceptance` function has an explicit contract: `stopped`, `technical_failed`, `pending_content_review`, `business_incomplete`; exit codes 1, 1, 0, 2; it demands the full evidence of the exact branch. Added two branches, `maker_not_met` and `reviewer_error`. Real also demands a verifiable usage ledger | Gate test: 15 `technical_failed` cases, 3 business branches, controls. Dry: the negative cases go through the real orchestration path and verdict function |
| R3: cleaning up the sandbox lost the logs and the store on error | `preserve_sandbox` copies the store (SQLite backup), the key-masked logs, the usage ledger and the temporary brain into a new folder on EVERY branch, after the servers have stopped; handles Windows long paths. Real always keeps the sandbox; otherwise it only cleans up when the technical result is fully passing and preservation is complete. There is an `a5-pilot-recovery.txt` | Gate test: preservation, no overwrite, key masking, an error while saving, a missing required item, a corrupt file, paths over 260 characters, cleanup rights. Dry: `save_error`, `early_crash`, `ledger_corrupt`, `ledger_lost_end`, `timeout` |
| Note 1: the run request merged the checkout's base with `main` | The request separates the lines: the pilot checkout's base is 0.100.0 (`a02663cb`), current `main` is 0.102.0 (`57c40348`); the pilot is not an acceptance of the integrated build | request |
| Note 2: the SHA and clean tree were only recorded, not a gate | `preflight_source` at step 0, before any server: HEAD must be exactly `JAVIS_RESONANCE_A5_APPROVED_SHA` and the whole checkout must be clean (including the runner itself). Mandatory for real | Gate test: a temporary git repo. Dry: `sha_mismatch` |

**The reviewer's script.** The original run on the new head: the five R1 checks (calling the ledger API directly) PASS, then it stops at `StopIteration`, because the assignment `rep["acceptance"] = <expression>` and the condition around `rmtree` became calls to `decide_acceptance` and `may_delete_sandbox`. The adjusted version only changes the adapter to call exactly those two calls, taken from the runner's AST, with a fallback to the old structure:
- A successful control sample was added so there is full evidence of one `pass_first` run.
- Each R2 sample applies its own scenario on top of that fully evidenced run.
- The cleanup condition is tried with the easiest input to clean up (preservation passes, record outside the sandbox).

No change to scenarios or expectations. Results of the adjusted version:
- on `3378832d`: 9 reproduced bugs, 2 controls pass, exit 0, the same as the reviewer's original output;
- on the new head with `--expect-fixed`: 11/11, exit 0.

**Control on `3378832d`** (a `git archive` export, the new gate test copied in, run block by block): the R1, R2, R3 and source-check blocks throw errors because the new API is missing (`host_text_verdict`, `decide_acceptance`, `preserve_sandbox`, `preflight_source`, the `reviewer_failed` parameter). The buggy behavior of those scenarios on the old code was already reproduced by the script, as above.

**Results of this round** (local machine, runner at `f4b79b58`, product code equal to `05e9b065`):

| Command | Result |
|---|---|
| `JAVIS_RESONANCE_A5_PILOT=dry python tests/python/test_resonance_a5_pilot.py` | 21/21 cases, exit 0. Every report: `commit f4b79b58`, 0 real calls, the server's engine-call ledger verified as 0 |
| `python tests/python/test_resonance_a5_pilot_gate.py` | 90 ok, exit 0 |
| Reviewer script, adjusted version `--expect-fixed` | 11/11, exit 0 |
| `tests/run.py resonance_a5 ignore_files tai_lieu_song_ngu version_khop_changelog nhat_ky_song_ngu route_table phien_ban_moi_nhat` (at `2468919c`) | 15/15 files, exit 0 |

Verdicts of the dry cases:
- 2 `pending_content_review` cases: (1, 1) and (2, 2);
- 4 `business_incomplete` cases: `fix_cap`, `ledger_cap`, `review_unknown`, `maker_not_met`;
- 10 `technical_failed` cases, the branch kept as is;
- 5 `stopped` cases.

The `save_error` case keeps the original sandbox (the store with its WAL remains) and has `a5-pilot-recovery.txt`. All the other incident cases have copies of the store, logs and brain in the record.

Runner bugs that dry found in this round, fixed before the final version:
- preservation failed when the record folder was deep (Windows' 260-character limit);
- the pin-set check demanded a review row even on a branch with no review (`f4b79b58`).

### Pilot gate review round 2 (head `4bcf3615`): one P2 in the final-record phase, fixed

Review: `exports/reviews/PR-616-A5-pilot-gate-r2-review.md`. The three round 1 bugs and two notes were re-checked and closed. Product code unchanged.

**Bug.** The verdict and the sandbox cleanup rights were computed before writing the JSON report and `a5-pilot-recovery.txt`. If either write failed, the result was still `pending_content_review`, exit 0. If the recovery file was corrupt, the JSON written earlier still said pass. In dry, `sandbox_kept` was also recorded as false while the real sandbox was kept.

**Fix** (`2eb79253`, runner, tests and docs only): `finalize_record`.
- Write order: the recovery file first, the JSON report last.
- If any required write fails, the verdict becomes `technical_failed`, exit code 1, with a specific cause; the branch is kept; the sandbox is kept with `sandbox_kept = true`.
- If the report fails, the recovery file is rewritten with the new verdict and the report is tried exactly once more. If that still fails, it reports to stdout and stderr with the sandbox path.
- The `A5_PILOT` line is printed after the verdict is final, with `report_saved`.
- The dry orchestrator also demands: the exit code matches the contract; the required JSON report exists and matches the `A5_PILOT` line; the KEPT line matches `sandbox_kept`.

**Tests.**
- The gate test (100 checks) calls the real `finalize_record` on finish-phase fixtures, real and dry, with no engine. Cases:
  - a control where saving succeeds, keeping the verdict and exit 0;
  - a report write error after a passing result;
  - a recovery file write error;
  - a business-incomplete result plus a write error, no longer exit 2;
  - an inherent technical error plus a write error;
  - a transient error then a successful write: the second report still says `technical_failed`;
  - a save location that does not exist.
- Dry through `run_case` with a fake engine: `report_fault`, `recovery_fault`, `report_fault_technical`.

**Control on `4bcf3615`:**
- The reviewer's finalization script in reproduce mode: 3 behavior bugs, 2 controls, exit 0.
- The new gate test run block by block: only the finish-phase block lacks the `finalize_record` API; the other blocks are green.

**The reviewer's scripts on the new head:**
- The round 2 finalization script needed no adjustment: the anchor `delete = PL.may_delete_sandbox(...)` still holds. Result `--expect-fixed` 5/5, exit 0.
- The round 1 script (adapter adjusted in the previous round, no further change): `--expect-fixed` 11/11, exit 0.

**Another runner bug that the full set of dry cases found in this round, fixed (`7211d4b7`).** The "quiet" condition for ending the background-work phase was evaluated exactly at the state-transition gap: the maker call had just closed, but the host still held the goal lock to publish the version and schedule the review, so the wake schedule was briefly empty. Four cases stopped early and ended in the wrong `maker_not_met` branch. Now the runner only counts it as quiet when:
- no call is running;
- the goal is not in `running`;
- no wake holds the goal lock;
- that holds on two consecutive observations.

A real run could also hit this gap.

**Results of this round** (local machine, runner at `7211d4b7`, product code equal to `05e9b065`):

| Command | Result |
|---|---|
| `JAVIS_RESONANCE_A5_PILOT=dry python tests/python/test_resonance_a5_pilot.py` | 24/24 cases, exit 0. Every case: the exit code matches the contract, the report matches the `A5_PILOT` line, 0 real calls, the server's engine-call ledger verified as 0 |
| `python tests/python/test_resonance_a5_pilot_gate.py` | 100 ok, exit 0 |
| Round 1 script (adjusted adapter) `--expect-fixed` | 11/11, exit 0 |
| Round 2 finalization script `--expect-fixed` | 5/5, exit 0 |
| The reviewer's dry wrapper (blocks the `main_pass` report write, real server, fake engine) | `technical_failed`, exit 1, sandbox kept, no report |
| `tests/run.py resonance_a5 ignore_files tai_lieu_song_ngu version_khop_changelog nhat_ky_song_ngu route_table phien_ban_moi_nhat` | 15/15 files, exit 0 |

## Real pilot (2026-10-13)

Commit run: `33cec5184c7d825dfc08ba84a3ddf07f3b1d1424`, on a separate checkout, clean before and after every run; base 0.100.0 (`a02663cb`), `main` not yet integrated. Run request: the gate round 3 build (gate review round 3 passed). Each run had its own approval from the project owner.

| | |
|---|---|
| Frozen input | `d15720546f4d53d611735e9cf3bf0096f02b711f15bf246086a441f50e5f609e` |
| Engine | background work `anthropic-cli/sonnet`, Claude subscription plan (`claude.ai`, `firstParty`, `max`); no paid API |
| Cap | maker 2, reviewer 2, total 4; 0 chat calls |
| Evidence | `exports/reviews/a5-pilot-real-1/` and `exports/reviews/a5-pilot-real-2/` (outside the repo): JSON report, ledger, the output of each call, the recovery path, `sandbox/` (store copy, key-masked logs, temporary brain) |

### real-1: `stopped` at the token gate

Passed the source, cost and auth gates and phase A (0 calls). The token gate before background work failed: the subscription plan token had expired 163 seconds earlier, and the gate demands at least 30 minutes left. Verdict `stopped`, exit code 1, **0 model calls**; the background-work phase did not start. Offline post-check 19/19 checks. This run's approval was used up; real-2 had its own approval after the project owner refreshed the login.

| File | sha256 |
|---|---|
| `a5-pilot-real-1/a5-pilot-real-main.json` | `bb5a4b50184b20d8740b0536695e3d5fa3023587628dca523c7bdc97c661deb4` |
| `a5-pilot-real-1/a5-pilot-ledger.json` (empty) | `f588a20b079ca1d16a25d2c57d6ee07aa74ae07c1f1139fc9f63d0ad917e26dc` |
| `a5-pilot-real-1-console.txt` | `58426d373afb028e21c5de14fa0a3f9fa1d74b03c406d504d61fed891fc04009` |

### real-2: `pending_content_review`, branch `pass_first`

The token had 28698 seconds left at the gate. The maker role wrote the summary; the reviewer role (pinned key, different from the maker agent) read the snapshot with the right hash and revision and gave `pass`; the host published exactly those bytes into the target file, and the goal was `succeeded`. The background-work phase took 95.7 seconds. Rebuilding the server (ledger ceiling 0): no new ledger row, action or review row. Runner: 26 checks all passed, exit code 0. Offline post-check 33/33; the reviewer re-ran it independently, 33/33.

| Call | Role | Outcome | Tokens in / out |
|---|---|---|---|
| 1 | maker (`nguoi-lam-tom-tat`) | ok | 18447 / 291 |
| 2 | reviewer (`nguoi-duyet-tom-tat`) | ok | 18651 / 258 |

Pilot ledger = the store's role ledger (maker 1/4, reviewer 1/4) = `calls_used` 2; one review row counted a call.

| File | sha256 |
|---|---|
| `a5-maker-1.md` (the maker call's output) | `a37808c46962a97075cc63b51b5be11fde0dff78c18ee2f0f3e96c42fce3e253` |
| `a5-deliverable-final.md` (the final version, same bytes as the maker's version) | `a37808c46962a97075cc63b51b5be11fde0dff78c18ee2f0f3e96c42fce3e253` |
| `a5-reviewer-1.txt` (the raw output of the review call) | `5c5a7b19d3b332e6b924545defbb5e1b7965fafa0a2dc9d80b4047c55d93da20` |
| `a5-pilot-real-main.json` | `3b935c3b23bc5f8f12b89c2c941214ea37219e0bce31262a91b4b037800e2b7b` |
| `a5-pilot-ledger.json` | `f8d406063b917899ceb04cf45b8672839bda36c4ca24daaff082f387ae29dc65` |
| `a5-pilot-real-2-console.txt` | `fe462dc6db1371ad9559a3f04d4b95d87c0556f690cb13910efcc6d7fe0e8c79` |

The JSON report, ledger, outputs and final version of both runs are kept exactly as the runner recorded them; the post-check is a separate record and does not edit them.

### Content review

The reviewer accepted real-2 **within the scope of one `pass_first` sample**: the four facts of the meeting (launch on 20 Nov; Lan sends the communications plan before Friday; Minh sends the ad budget sheet before Thursday; the whole team meets again next Monday) were kept with the right person, task and deadline.

Two wording notes, not blocking (the quoted sentences are translated from the Vietnamese pilot output):
1. "The communications plan and the ad budget will be finalized before the next meeting" is an inference: the assignment only states the deadline for sending them.
2. "to review progress" is a meeting purpose that the maker added, and the source does not state it.

"The whole team" as the owner of the task of meeting again is acceptable (the assignment says "the whole team meets again"), but it does not mean an organizer has been determined. The pilot version is kept as evidence; it is not edited and then used to claim a pass.

**Limit of the reviewer role in the current A5.** `_review_prompt` only supplies the role description, the interpretation of the goal, the criteria, the constraints and the version to review; it does not supply the original assignment (as designed, section 4.3 and D8: no chat history). In the pilot, the interpretation of the goal only described the structure of the summary, so the facts the reviewer saw came from the very version to be checked. A `pass` result does **not** mean the reviewer faithfully cross-checked against the source or caught added information.

**Usage.** The server's shared usage ledger (`usage.json`) recorded 0 because it only counts chat calls; Resonance's background calls are in the store's actions and receipts, and in the pilot ledger (2 real calls). A shared usage ledger reporting 0 does not mean the run cost no model usage.

### Remaining limits

- One sample, the pass-immediately branch. The branches for requested fixes, hitting the cap, an unreadable review and engine errors only have evidence from a fake engine.
- The two roles share the background-work model: independent in role and context, not two different models.
- 0 chat calls: the chat brain routing by itself to `javis_goal` is not checked.
- Local machine, base 0.100.0; VPS performance not measured. Integrating `main` is a separate diff with its own review.

### Two separate improvements (not implemented, outside this PR)

1. A minimal source of requirements, pinned by the host to the exact goal and revision, given to the reviewer role to cross-check for added or dropped facts. Not the whole chat history, and still not showing the maker's reasoning.
2. Put Resonance's background calls and tokens into the shared usage screen, without double counting against the chat ledger.

## Integrating `main` up to 0.108.0, numbered 0.109.0 (2026-10-13)

`main` moved on four times during the integration (0.103.0, 0.105.0, 0.107.0, 0.108.0). Every round followed the same rules:
- merge `main` into the branch, no rebase;
- conflicts resolved only in `VERSION` and the two changelogs: the A5 block on top, the `main` blocks kept as is;
- renumbering and moving the rollback marker in a separate commit, following the last real release before A5.

Historical markers (the results of earlier rounds, the pilot checkout's base, line numbers cited against `a02663cb`) keep the old number.

| Commit | Round | Content |
|---|---|---|
| `0840dc6e` | | Pilot real-1 and real-2 record (docs only) |
| `ba591f4f`, `371ff0ab`, `1db1d570` | 1 | Merge `main` 0.103.0 (`eb733834`, #622); A5 0.104.0; record |
| `d7276bc5`, `4b20001e` | 2 | `main` 0.105.0 (`1dd593ba`, #624) overtook 0.104.0, #623 also held 0.104.0; A5 0.106.0. **Integration reviewed at `4b20001e`** |
| `ef18c9f5`, `fecbb63d` | last | `main` 0.107.0 (`49c795ab`, #623) overtook 0.106.0, #625 held 0.108.0; A5 took **0.109.0**; suffix `.pre-0.109.0` |
| `79724208` | last | New test `test_resonance_a5_engine_session_gate.py` (test only) |
| `6c4f0b5a`, `20d7c063` | last | `main` 0.108.0 (`c4fb614d`, #625); 0.109.0 was still free and greater than `main`, so it kept the number; the rollback marker moved to the real 0.108.0 (CI and GHCR image build of `main`) |

All five merge commits (`ba591f4f`, `d7276bc5`, `ef18c9f5`, `6c4f0b5a`): `--remerge-diff` shows only `VERSION`, `CHANGELOG.md`, `CHANGELOG.en.md`.

### Running code

- **The A5 code is unchanged.** The A5 part added on `main` matches, file by file, the A5 part reviewed on the old base (`a02663cb` to `33cec518`): 9 files, the same added and removed lines.
  - Checked in round 1 (`eb733834` to `ba591f4f`), round 2 (`1dd593ba` to `d7276bc5`) and the last round (`49c795ab` to `ef18c9f5`, compared with `1dd593ba` to `4b20001e` which was reviewed).
  - #625 (0.108.0) touches none of those 9 files.
- **Auto-merged files** keep the changes of both sides in full: `server/main.py` in every round that changed it (last round: A5 adds 2 lines, #623 adds 137 and removes 38 lines), the two i18n files in round 1.
- **The only running-code line changed by integration:** `A5_BACKUP_SUFFIX = ".pre-0.109.0"`, with its comment. 0.104.0 and 0.106.0 were never released, so changing the suffix affects no machine.

### Indirect impact of `main` 0.107.0 and 0.108.0

- **`claude_sdk_engine` (#623):** a session with `allowed_tools` now loads the plugin tools when the list names `mcp__javis-plugins__<name>` explicitly. A5's work and review calls are built with `main._resonance_engine`, with a sentinel name that matches no tool. The new test `tests/python/test_resonance_a5_engine_session_gate.py` builds EXACTLY that path (swap, `strip_tools`, `pick_text_only_link`) for the system prompts of the two roles, replacing `ClaudeSDKClient` with a fake client to capture the real `options` handed to the SDK. Result, 26 checks:
  - empty and strict MCP: no hub, no plugin server;
  - `allowed_tools` holds only the sentinel name, the `can_use_tool` gate is on; the user's machine settings are not loaded; native tools are denied up front;
  - the gate rejects 14 tool names (native, hub, plugin with and without the prefix);
  - no fallback chain; if the chosen provider is not ready, it does not run on another provider instead;
  - control: a session that names a real plugin tool explicitly does get a plugin server, so the test would notice if A5 leaked. On `4b20001e` (SDK 0.105.0), the test stops at the second check because `plugins_host.granted_plugin_tools` does not exist yet.
- **`sessions` (#623):** added the `cli_session_history` table and writes history in `set_cli_session_id`. Same test file: an old-style session store (with exactly the new table dropped, because CI only shallow-fetches one base commit) opens and creates the table; the session row is kept; an agent session still produces the right identity (`agent:<slug>`, A5's identity source); attaching a new CLI session writes history.
- **#625 (0.108.0):** only the Zalo path, chatbot, customer conversations and the MCP catalog; it touches no Resonance file, `server/main.py`, engine or `sessions`.

### Results

| Command | Head | Result |
|---|---|---|
| `python tests/python/test_resonance_a5_rollback.py` | `20d7c063` | 11 ok, exit 0, real 0.108.0 code through `git show c4fb614d` |
| `python tests/python/test_resonance_a5_engine_session_gate.py` | `20d7c063` | 26 ok, exit 0 |
| `tests/run.py` by impact: every `resonance_*`, `sdk_engine`, `aux`, `session`, `strip`, `kanban`, `workflow`, `agent_rules`, `learn`, `usage`, `plugin`, `reminder`, `task`, the new tests of #623, version, changelog, route, i18n, `ignore_files` | `fecbb63d` + new test | 101/102; the only red file is `test_ignore_files` because the new test was not yet committed; green after commit `79724208` |
| By impact after the 0.108.0 merge: engine and session store tests, version, changelog, route, bilingual docs, the two new tests of #625, `ignore_files` | `20d7c063` | 9/9 and 1/1, exit 0 |
| `JAVIS_RESONANCE_A5_PILOT=dry JAVIS_RESONANCE_A5_DRY_ONLY=main_pass,main_fix python tests/python/test_resonance_a5_pilot.py` | `79724208` | 2/2 cases, exit 0; right branch, ledger (1, 1) and (2, 2), server engine ledger 0, 0 real model calls |

**Not re-run:** all 24 dry cases or the whole repo in the last round, because:
- the pilot runner has not changed since `33cec518`;
- the A5 code did not change apart from the suffix;
- the paths `main` touched already have their own checks above;
- the by-impact checks found no new bugs.

CI on the final head runs the repo's full test suite.

Round 2 (`4b20001e`, reviewed) has: rollback back to 11 ok on 0.105.0 code; dry 24/24; whole repo 647/661 with 14 machine-dependent red files matching clean `main` `1dd593ba`; CI `push` 38342887031 and `pull_request` 38342891054 succeeded. Round 1 (`371ff0ab`) was equivalent on 0.103.0. The 14 red files: agy_prompt_dai, antigravity_cli, ba_loi_mac_va_telegram, cai_windows, grok_cli, install_admin, khoi_dong_nhe, link_file_uri, machine_translations, memory_hoa_thuong, model_theo_phien, ollama_local, terminal, windows_no_console.

No real model was called, the pilot was not re-run, nothing was merged, nothing was released, the VPS was not touched. The limits of pilot real-2 stay as in the section "Real pilot".
