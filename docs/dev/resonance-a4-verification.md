# Resonance A4: code verification record (2026-10-10)

**Status:** the A4 code on branch `claude/resonance-a4-handoff-grants` (PR #604, number 0.96.0; renumbered four times because `main` went through 0.91.0, 0.92.1, 0.94.0 and then 0.95.1) was fixed after **code review round 1** (`a3356165`: 1 P1, 3 P2), **round 2** (`7b47e246`: 3 P2) and **round 3** (`d26c0f09`: 1 P2); **code review round 5 passed at `5b5e3ef0`** (no P1 or blocking P2 left). After that: a UI smoke test on a sandbox with a fake engine (one card bug fixed at `f6aeb6d1`) and the pilot runner (pilot gate review passed at `5305687a`, dry 13/13). **The real pilot ran ONCE** at `5305687a` (project owner approved on 2026-10-11): 2 Claude Code chat calls on `claude-opus-5-5` through the subscription plan, 0 background calls; the original result was `technical_failed` because of the runner, and was closed by an offline post-check (section "Real pilot real-1"). The design was finalized in round 5 at `6d774bd5` (D1: no write permission is granted from chat wording), and the reviewer approved coding. Integration review and final review passed at `3606362c`; **shipped as 0.96.0** (`d36ebb3e`, PR #604, 2026-10-11; `main` CI run 38146898745 and image build run 38146898746 succeeded; image `ghcr.io/blogminhquy/javis-os:0.96.0`, digest `sha256:8f1751d2…`; the VPS has not pulled it). Pilot real-1 ran on `5305687a`, not on the integrated build.

Design: [2026-10-10-resonance-a4-handoff-grants-design.md](../superpowers/specs/2026-10-10-resonance-a4-handoff-grants-design.md) (section 12 is the matrix; section 17 holds the implementation notes the reviewer must confirm). Guide: [resonance-a4-grants.md](resonance-a4-grants.md).

## Tests run (local machine, the root checkout's `.venv`, no real model)

| File | Result |
|---|---|
| `tests/python/test_resonance_a4_grants.py` (real store, fake engine, fake clock) | 124 checks passed |
| `tests/python/test_resonance_a4_transport.py` (real plugin, real HTTP hub with `X-Javis-Turn`, real Claude SDK plugin MCP server, `main.app`) | 14 checks passed |
| `tests/python/test_resonance_a4_rollback.py` (real 0.95.1 code, `adb103ed`, the last build before A4, via `git show`) | 11 checks passed |
| `tests/js/test_resonance_a4_ui.js` (including the real `send()` behavior with a fake server response) | 27 checks passed |
| `tests/python/test_resonance_a4_pilot.py` (`JAVIS_RESONANCE_A4_PILOT=dry`, real server, simulated chat call) | 13/13 cases, 0 real calls, every case verifies 0 engine calls; skipped when the variable is not set |
| `tests/python/test_resonance_a4_pilot_gate.py` (the runner's real code loaded via AST, no server, no model) | 133 checks passed |
| 31 older Resonance test files (M1 to M5, A1 to A3) and 5 older Resonance UI tests | all passed (14 files had expectations fixed or `RA.preapprove()` added, see below) |
| Whole repo `tests/run.py` (639 files, last run at `f6aeb6d1`) | 625 green; 14 red, all environmental, sorted out in the section "Whole repo" |

Command to re-run:

```bash
python tests/run.py resonance -v
python tests/run.py resonance_a4 -v
```

## Matrix cross-check (design section 12)

| Case group | Where | Notes |
|---|---|---|
| G1, G2 (`narrow`) | a4_grants | the part that was granted; other goals rejected; an unknown operation is empty |
| G13, G45 (path key, D15) | a4_grants | `a/../a` is accepted by `_brain_file` but the path key rejects it; `.`, `..`, absolute paths, control characters, unknown extensions, forbidden folders; letter case on Windows. Symlink to the outside: reuses the `_brain_file` check (old test), no symlink is built on Windows |
| G15, G27, G51 to G55, G73 to G79 (D1) | a4_grants | six sentences (direct command, negation, condition, question, illustrative example, a sentence to translate): wait for permission, no root, no model call, no file write; `begin_action` throws `GrantError(scope_pending)` |
| G57 to G61 (draft, Allow, No, old card) | a4_grants, a4_transport | the right draft is published, 0 model calls; an old card gets 409; an old turn gets `scope_decided` |
| G23, G24 (change target, same target) | a4_grants | |
| G17, G36, G37, G41 | a4_grants | |
| G38, G39 (Write A + submit B) | a4_grants | |
| G10, G44, G46, G5, G20 | a4_grants, a4_transport | replay after revocation returns a `stale` receipt |
| G30, G43, G85 (choosing a link) | a4_grants | |
| G29, G70, G80 to G84 (permission order) | a4_grants | including `created_at` set back to 0: a re-granted root after the snapshot is still not accepted |
| G31, G32, G33 (commit mark vs revocation) | a4_grants | |
| G62, G64, G65, G66 (restart, reconciliation) | a4_grants | accepted exactly once when reconciliation runs twice |
| G67, G68, G69 (several revisions in one message) | a4_grants | |
| G7 (revocation while a background call is running) | a4_grants | |
| G34 (revocation in the middle of an experiment) | a4_grants | the trial gate stops; a new experiment cannot be opened (`GrantError(grant_revoked)`) |
| G40 (partial: dying between intent and commit mark) | a4_grants | reconciliation cancels, the submission goes back to `candidate`, the next wake publishes, 0 model calls |
| G72 (the `_gate` still runs) | a4_grants | paused |
| G86 (an effect committed under a revoked permission) | a4_grants | |
| G47, G28, G49, G48, G50 (upgrade, legacy, downgrade) | a4_grants, a4_rollback | G48 proves that the published limit is true; it does NOT prove it was blocked |
| G22 (engine capability, real transport) | a4_grants, a4_transport, a1_gates | Grok, Antigravity: no turn key, so the hub returns an error and no submission is recorded |
| G18 | a4_grants | |
| G3, G4, G6, G8, G9, G11, G12, G14, G35, G42 | old tests and part of a4_grants | G3: A4 has no communication path at all (no tool); G4, G11: identity comes only from the turn context (A1); G12: the prompt does not contain the draft; G14: a native Write does not turn a receipt into unknown bytes (G39) |

**No dedicated case yet (stated honestly):** the full G40 (fault injection at EVERY point of section 4.7; so far only dying between intent and commit mark, G62 to G66 and G86), G71 (the gap between the commit mark and `os.replace`, a published limit).

## UI smoke test on a sandbox (after review round 5)

Sandbox server on port 7788, its own state and brain (`exports/sandbox-a4`, outside git), beat off, fake engine with a counter, REAL file locks on Windows (one process holding the file: blocking `os.replace`, or blocking even reads). Chromium through Playwright, desktop 1366x860 and narrow 375x812, Vietnamese UI; the native confirm box answered for real, a real second tab. Record and 16 screenshots: `exports/reviews/A4-ui-sandbox-record.md`, `exports/reviews/a4-ui/` (outside git).

Passed, cross-checked against the store and the file hash:
- ask permission for a new target, preview exactly the draft, Allow publishes exactly those bytes, 0 engine calls;
- No (deny); an old card gets 409 after another tab already clicked; pause keeps version 2; revoke (Cancel sends nothing, Agree makes version 2 `stale`); re-granting does not revive version 2;
- the target file already exists: reports not published, keeps the file; the draft file locked: keeps the version, retries at growing intervals, unlocking publishes the right version; the target file locked: parks at `publish_settling`, restart and F5 show the card "Finishing a publish that was already committed" (the Vietnamese UI label is "Đang hoàn tất lần đăng đã chốt"), unlocking publishes exactly version 2; a published file edited by hand: `source_drift`, not overwritten;
- the narrow layout does not scroll horizontally.

**Bug found and fixed (`f6aeb6d1`):** on the Partners page, the chat card was collapsed and the message "Allowed and published…" landed in the assistant-drawer card that was hidden (the last card in the DOM). It has been there since 0.87.0; now the assistant-drawer card is always full and the "newest card" rule only considers chat cards. Two new checks in `test_resonance_a4_ui.js`, red on the old code.

**Design question, not changed:** when Allow meets a target file that already exists and belongs to the project owner (no baseline), the schedule still runs a background work call (sandbox: 3 out of a limit of 4, every version conflicting) and then stops with `stalled`. This is the reviewed MVP behavior (check "3a"); trying to change it turned 5 old test files red, so it was put back. The project owner needs to decide.

## A4 pilot runner (ran for real once, see "Real pilot real-1")

`tests/python/test_resonance_a4_pilot.py`. Real runs Claude Code (subscription plan) in the assistant's chat call, at most 2 calls (a reservation ledger fsynced before each send, closed on error, never reset), store ceiling 0 for every server process. Dry has 10 cases: main, cost gate, auth gate, old card 409, a publish receipt that failed, engine error, no submission, the target file written by itself, missing evidence, a ledger still holding a reservation. Run request: `exports/reviews/A4-pilot-run-request.md` (outside git). Engines other than Claude Code are only checked with fake engines.

**Pilot gate review (`1719303d`): 3 P2 in the runner, fixed.**

| Point | Fix |
|---|---|
| P2-1: having `turn_done` counted as a successful write | Only `engine_status == ok` and `turn_status == completed` is success; `ws_chat` keeps the `turn_done` metadata as is. Engine error, unknown, cancelled, failed, missing status, no `turn_done`: the call still counts, the ledger closes, a technical error (not a routing one) |
| P2-2: a broken check still called call 2 | The gate sits inside the ledger's `reserve` (a required check already broken, or a token that fails before that call: no reservation, no send); the precondition of the step that has an effect is a hard check (stop immediately); an explicit gate before Allow and before call 2; login and token expiry checked before EACH call |
| P2-3: an empty session still passed | `audit_notices`: every sendable outbox message has exactly one message in the session, on the right goal, with a receipt; no unknown or repeated keys, no pending messages; empty does not pass; there must be a message at the last revision; the second rebuild (D) does not change the set of messages |

Durable regression: `tests/python/test_resonance_a4_pilot_gate.py` loads the runner's real code (the ledger, `chat`, `ws_chat`, `audit_notices`, the orchestration segment before call 2) and runs it against a fake frame source, no server, no network, no model. Dry gained the cases `contract`, `token`, `notice`.

An incident while fixing: one dry case tried to go through `/ws` with a keyless API brain and settings missing `engine`, so the runtime fell back to Claude Code and ran 1 real call on the subscription plan. That path was removed: dry never sends a message through `/ws`, and every dry case checks that the sandbox server's engine-call counter equals 0. Record outside git: `exports/reviews/a4-pilot-incident-2026-10-11/`.

**Pilot gate review round 2 (`da2b8c0b`): 1 P2 in the dry post-check, fixed.**

- A count that is NOT readable never becomes 0. The two call ledgers of the sandbox server (`usage.json`, `usage-events.jsonl`) are created in advance, empty and valid, before the server is built. It only reports 0 when they are readable, correctly structured and the two ledgers agree. Otherwise it is `None` with the reason `unverified: ...`, and the dry check fails.
- Any case that reports a verified non-zero (a call exists, cannot be verified, a real call, no report): the dry orchestrator STOPS THE WHOLE BATCH and does not open the next case. That case keeps its folder (state, the usage ledger as found, server log) and the orchestrator copies it into the record. A negative case that meets its expectation and has verified 0 calls keeps going.
- This is a POST-CHECK, not a blocker: `usage_store` skips calls with no tokens and records on a best-effort basis. Dry's real blocker is still `ws_chat` refusing to send a message when not real.
- Regression in `test_resonance_a4_pilot_gate.py`, running the runner's exact AST node.
- **Round 3 (`dd2b1d58`):** the per-call ledger was created in advance, so it is REQUIRED to still exist and be readable (a lost ledger means unverifiable, the comparison is not skipped); every `total` entry must have `turns` as a non-negative integer (no default of 0). `total = {}` with an empty per-call ledger is still a valid 0. Two counterexamples go through the whole chain: cannot verify, check fails, keep the evidence, stop the whole batch. Tests: 84 checks.

The assignment: two input sets with pinned hashes. v1 is the original wording, which may be done right inside the call, exactly as the call that slipped through showed. v2 is a proposal that hands over responsibility after the call. Real must choose the approved set.

### Real pilot real-1 (2026-10-11)

**Scope.** Ran exactly ONCE, following the project owner's approval, on a separate checkout at the reviewed commit `5305687a` (0.93.0 at the time; clean tree). One sample, one engine: Claude Code `claude-opus-5-5` through the subscription plan (`authMethod: claude.ai`, `firstParty`), input set v2. It does not prove Codex, Grok, Antigravity or the seven API engines; it did not check background calls with a real model. This is NOT evidence that the integrated 0.96.0 build was trial-run.

**Limits.** Chat call ledger 2/2, both `ok` and `completed`; store ceiling 0 held across four servers, 0 store-level engine calls; the sandbox server's engine-call counter was 2, verified. Tokens: 534,079 in, 5,152 out; the app estimates USD 1.23, inside the subscription plan. No retry, no paid API.

**The original result is kept as is:** `acceptance: technical_failed`, only the two checks that cross-check the notice messages broke. The report, the ledger and the two products are unedited. Hashes: report `3ab7aaf9…4b4a3`, version 1 `80e28006…3b6a1` (662 bytes), version 2 `135ac274…90c6e` (827 bytes).

**Cause: a runner bug, not a message-delivery bug.** The host places a `turn:<message_ref>` card after every chat call that creates or edits a goal (`_resonance_push_card`); the old `audit_notices` demanded the session key set equal exactly the `outbox:<id>` set, so it wrongly rejected those two cards. Dry simulates the chat call so it has no turn card; the pilot gate review did not see it either. The required notice `outbox:3` (`goal.waiting_human`, revision 2) has exactly one message, in the right session, with a receipt that matches the message itself, not repeated after two rebuilds.

**Runner fix (`8582bdd6`), no product code change.** `read_notice_evidence` reads read-only (SQLite `mode=ro`), shared by the runner and the offline post-check. A receipt only counts when the single receipt row of (key, goal) points at the right session and at THAT very message. A turn card is only allowed as an extra when its message_ref belongs to the session itself and the goal store has a `created`, `reframe` or `continued` event for the same goal, same message_ref, same revision; a turn card never replaces the required outbox message. Unknown keys and repeated keys still do not pass. The gate test added the three real cards as fixtures and negative cases (only a turn card, missing or wrong receipt, wrong goal or session, no linked event, repeated, unknown key, outbox from an old revision). Control: the new test on the `5305687a` runner is red on exactly the three-real-cards case.

**Offline post-check** on a copy of the saved data, read-only, no server built, no auth, no engine call: the new cross-check gives `matched_ok` and `required_ok` correct; the old function on the same data reproduces the wrong result; the 85-file evidence tree did not change by a single byte. The reviewer's independent post-check script: 16 checks passed. Record outside git: `exports/reviews/A4-real-1-postcheck.md`.

**The four things to prove, according to the post-check:** call 1 created exactly one goal for the assistant and submitted through `javis_submit_deliverable`, the host held the draft waiting for permission, no target file; Allow published exactly the bytes that were held, with no model call; call 2 edited the goal, version 2 was published by the host itself without asking for permission again; rebuilding twice made no further calls, the notices were correct and not repeated. A side note: the first `javis_goal` call in call 1 was rejected by the host (missing a readable `at_iso`), and the brain corrected itself within the same call.

**Content (reviewer).** The final version (revision 2) PASSES: it covers the points, the Next steps section has the right owners and deadlines, and it keeps the "next Monday" ("thứ Hai tuần sau") commitment unchanged. Version 1 does NOT fully pass: it added a date "(19/10/2026)" that was not in the assignment (2026-10-11 is a Sunday; by the usual reckoning "next Monday" is 2026-10-12). This flaw stays in the record as is; the final version dropped that date. No claim is made that the model's quality is stable from one sample.

## Code review round 3 (`d26c0f09`) and the fix

| Point | Fix | Regression (a leftover `candidate` submission after the process is interrupted, reopen the store, real `tick`) |
|---|---|---|
| P2: a publish error that arises right inside the work wake still opens a model call (file replaced after the commit mark; draft file read before the commit mark) | Re-evaluate the obligation after `_publish_latest`, then park at `publish_settling`; when the draft file cannot be read yet, keep the submission, and the `settle` schedule retries by code at growing intervals (I16) | V3, for both error positions: the first wake makes 0 engine calls, `calls_used` 0, no work action, the work reason is still pending; an error lasting 20 beats of 30 seconds with a store reopen: wakes at growing intervals, no model opened; when the error ends: publishes the held version exactly once, accepts once, clears the park, no `settle` schedule left; control with no immediate publish error |

**A held submission when the goal changes state** (added when closing round 3): pause, revoke, cancel, or a revision change while held, then after the lock expires the old version is still not published on its own, the holding obligation is dropped, no `settle` schedule remains; on a revision change the newer version is published. Within the same revision, a version with different content is rejected as `submission_conflict`, and the held version is published exactly once when the lock expires. Revoke and revision change wrote state with their own SQL statement, so a `hold_until` used to be left on a row that was no longer `candidate` (no effect on scheduling because only `candidate` rows are counted); it is now cleared at the same time.

**The reviewer's scripts:** `PR-604-A4-code-r2-checks.py --expect-fixed` 14/14 and `PR-604-A4-code-r3-checks.py --expect-fixed` 4/4, both exit 0. Output: `exports/reviews/A4-code-r5-reviewer-checks.txt`.

**Control on the old head:** the new test run on `d26c0f09`: all 7 V3 checks red (1 engine call, a work action, the submission not published correctly), the no-error control case still green. Output: `exports/reviews/A4-code-r4-control-on-d26c0f09.txt`.

## Code review round 2 (`7b47e246`) and the fix

| Point | Fix | Regression (through `handoff_after_turn`, the real `tick` with both the normal schedule and `settle`, store reopened) |
|---|---|---|
| P2-1: a draft file that is temporarily unreadable was closed as `conflict/target_changed` | `_sub_read` separates a temporary I/O error (keep the obligation, back off) from a lost file or a wrong hash (`reject_submission`, its own reason) (I13) | V2-P2-1: lock the draft file once and several times, reopen the store, when the lock ends publish exactly the original version, 0 engine calls; a draft with the wrong hash does not reach the target, `draft_hash_mismatch`, no conflict event; control where the target was really edited is still `conflict` |
| P2-2: the recovery schedule was deleted before acceptance | The `settle` schedule lives until acceptance is done; the `settle` wake accepts the published version; an acceptance error does not escape (I14) | V2-P2-2: one SQLite lock error at the acceptance step, then active, revoke, cancel, pause, store reopen, three ticks: accepted exactly once, one publish action, no extra schedule, 0 engine calls |
| P2-3: the work schedule called the model while a committed publish was still waiting on I/O | `_wake_work` parks at `publish_settling` while a completion obligation remains; `_settle_done` clears the park (I15) | V2-P2-3: replacing the file with repeated errors across several ticks including the normal schedule, store reopened: 0 engine calls, 0 work actions, parked state; unlocked: the original version is published exactly once, accepted, park cleared |

**The reviewer's script** (`PR-604-A4-code-r2-checks.py`): `--expect-fixed` 14/14, exit 0. The default reproduce mode now reports 4 broken, meaning the four cases N1, N2 revoke, N2 cancel, N3 no longer reproduce. Output of both modes: `exports/reviews/A4-code-r3-reviewer-checks.txt`.

**Control on the old head:** the new test run on `37a86fe9` (equal to `7b47e246` plus the merge of `main` 0.91.0):
- the three V2-P2-1 cases red;
- the V2-P2-2 case throws `sqlite3.OperationalError` out, so the acceptance step's own error breaks the flow.

Output: `exports/reviews/A4-code-r3-control-on-37a86fe9.txt`.

## Code review round 1 (`a3356165`) and the fix

| Point | Fix | Regression |
|---|---|---|
| P1-1: "Not quite" (the Vietnamese UI label is "Chưa đúng ý") recorded before the commit mark still published | `_publish_held` checks the latest interpretation feedback of that exact revision inside the intent transaction (including the `same` branch) and the commit mark | V1-P1: rejection before commit (through `handoff_after_turn`), before the `same` branch, control "That's right" ("Đúng ý"), switching back to "That's right" then publishing, 0 model calls |
| P2-1: a temporary I/O error in reconciliation closed a permanent `conflict` | `_reconcile_publish` distinguishes being unable to read or write from evidence that the target changed; `publish_retry` keeps `running`, backs off, schedules `settle` | V1-P2-1: an error on the first publish and three reconciliations, store reopened in between, then completes exactly once; control where the real file was edited stays as is and `conflict` |
| P2-2: revocation lost the scheduler's path to a committed effect | A physical `settle` schedule (I10) | V1-P2-2: the real `tick` after revocation and a store reopen, for "file not yet replaced" and "file replaced but the mark not yet written", the second beat does nothing; the goal is cancelled; control where revocation before commit still blocks |
| P2-3: the card said "draft published" when the server reported a conflict | `noteFor` chooses the sentence by `publish`; two new sentences (conflict, not published) | the real `send()` with `conflict` and `succeeded` responses |
| I1, I2 | Accepted; section 5.3, 4.2, 4.7 synchronized | |

**Control on the old head:** copy the two new test files into a temporary worktree at `a3356165`. Result:
- 7 server-side regression cases red;
- the card test breaks because `RS.noteFor` does not exist yet;
- the control cases are still green.

Output at `exports/reviews/A4-code-r2-control-on-a3356165.txt` (outside git).

**The reviewer's independent check script:** `--expect-fixed` all 9 cases green (5 controls, 4 bugs). The script's R4 case extracts the `send()` body separately, so the note sentence it sees is the generic error sentence, because `noteFor` is outside the extracted scope. The correct sentence is checked by the real `send()` behavior test above.

## Internal review before the external review

An independent pass (a read-only agent that also ran trials on a temporary store) found six bugs; all six were fixed, each with a regression case R1 to R5 in `test_resonance_a4_grants.py` (bug 6 is covered by G38):

1. **Permission bypass:** a product path with `.` or an empty segment (`./Inbox/x.md`) made the path key empty, the scope fell to `none`, and a Write in an accepted chat call went through without permission. Fix: a raw path with no key makes the scope `invalid` (blocked, `path_rejected`); `_artifact_params` rejects `.` and `//` right at creation.
2. `ensure_scope_request` broke the unique key when a pending request of the previous revision existed (the re-upgrade path, section 7.4). Fix: replace the old request first.
3. `os.replace` failing after the commit mark was closed as `conflict`. Fix: let the action run, and reconciliation completes under the committed-effect rule.
4. The guard-closing state could be overwritten by the gate at two new call sites. Fix: `_gate` returns immediately while a guard is being closed.
5. During revocation, the model's edit rebuilt the Allow card (turning it into a re-grant through the card). Fix: `_scope_sync` does not create a request when the last root is `revoked`.
6. Handing over Write A and then submitting B released the schedule before B was published. Fix: accepting A does not release the schedule (`release=False`), and only the B publish step closes the handoff.

## Old tests that had to change because behavior changed by design

- 13 files added `RA.preapprove()`: it plays the project owner clicking Allow right after each create, edit and goal assignment, so the old check content stays as is. The chat call that creates a goal still gets no new permission (the permission-order rule is correct).
- `test_resonance_a1_gates.py` case 7 (toggling the assistant off and on mid-call): the old call's submission is `stale`, and the next time it redoes one call instead of re-publishing the held output (note I5). Case 11: a Write in the creating call is not accepted (D1). Case 12: Codex and API engines can submit through the tool.
- `test_resonance_mvp_main.py` call 302 and `test_resonance_e2e_achieve_harness.py` P2-2, `test_resonance_inline_handoff.py`: handing over a chat version moves to the UPDATE call after permission was granted (the creating call has no permission).
- `test_resonance_a1_turn_agent.py`: the assistant's call now also carries `authority_seq` and `provider`.
- `test_resonance_a2_ui.js`: added the wake-reason label `scope_granted`.
- `tests/python/route_table.json`: added exactly one route at the end of the table (`GET /goals/{goal_id}/drafts/{submission_id}`, registered through `register_a4` after every old route).

## Limits of the evidence

- Fake engine and fake clock; no real model call, no real server other than `TestClient`.
- The rollback test runs real 0.91.0 code fetched with `git show 1d0b515c` (before merging the new `main`, it was 0.89.0 `33a3c1aa`).
- The UI was not checked in a real browser (only the card's pure functions).
- Points I1 and I2 in section 17 of the design touch the permission mechanism; the reviewer accepted them in code review round 1.

## Whole repo

**Last run (2026-10-11, `f6aeb6d1`, product code equal to the pilot package's head):** 639 files, 625 green, 14 red. Re-running each red file on a clean `main` worktree `1d0b515c`: 13 files are red in exactly the same way (this machine's environment); `test_ignore_files` is green on `main` and red on the PR worktree only because of the `exports/` folder (review records, untracked). No new red file is due to A4. Log and triage: `exports/reviews/A4-full-suite-f6aeb6d1.*` (outside git).

**First run (before code review round 1):**

`tests/run.py` ran all 637 files on this Windows machine: 619 green. 18 red files, sorted out:

- 14 files already red on this machine's clean `main` (environmental, recorded earlier): `test_agy_prompt_dai`, `test_antigravity_cli`, `test_ba_loi_mac_va_telegram`, `test_cai_windows`, `test_grok_cli`, `test_install_admin`, `test_link_file_uri`, `test_machine_translations`, `test_memory_hoa_thuong`, `test_model_theo_phien`, `test_ollama_local`, `test_terminal`, `test_windows_no_console`, and `test_ignore_files` (the `exports/` folder is untracked).
- `test_khoi_dong_nhe` (the load-time ratio against `main`): red even on the clean worktree `6d774bd5` while the machine was running the large test suite (6.29 and 6.50 times, the A4 build 5.16 and 5.17 times); not due to A4.
- `test_hoi_thoai_nhom`: green when re-run on its own.
- `test_route_table`: due to the new route; the route was moved to the end of the table and the table re-snapshotted (exactly 1 entry added).
- `test_update`: a false alarm; the crc32 cache key of the new `style.css` became `72de33ed`, which contains the string `?v=72` that the test forbids by substring. Fix: the test compares the whole key.

After the fixes above, re-running `resonance`, `test_update` and `route_table` on the final code: 45/45 green. Full log at `exports/reviews/A4-code-full-suite.log` (outside git).
