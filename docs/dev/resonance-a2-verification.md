# Resonance A2: acceptance record (09/10/2026)

Milestone A2 of the [agent scope](../superpowers/specs/2026-10-08-resonance-agent-scope-roadmap.md) roadmap: the assistant wakes for a specific reason, sleeps while waiting, and does not call the model for nothing.

**Status: released as 0.88.0 (09/10/2026). VPS performance NOT MEASURED.** PR #593 squashed into `main` as `c101d108e398121315423fb73bff412c6e178392` (tree identical to the checked head `12d349f4`). CI and the Docker build are green; image `ghcr.io/blogminhquy/javis-os:0.88.0` (`sha256:50eb0a2208d6...`). Do not conclude that the VPS is no longer slow until it has been measured on a real machine.

## Code and commits

- **PR:** #593, branch `claude/resonance-a2-heartbeat`, VERSION 0.88.0. Since 09/10/2026 it sits on `main` after A1 (#590) was squashed as `fdfec7c5` (0.87.0); before that it stacked on the A1 head `077bcf73`.
- **Design:** passed review in round 4, `cb11fc23`.
- **Code:**
  - `c2b0874f` the A2 code, `50c355f1` the i18n label fix.
  - Three fix rounds following the code review: `d1f64b46`, `f7cbab4c`, `b5975b7e`.
  - **Code review passed at `b5975b7e`.**
- **After review (integration check):** one small fix and two non-blocking review items, recorded in the "After the code review" section below.
- **Final review passed at `b80ae0ea`** (`exports/reviews/PR-593-A2-b80ae0ea-final-review.md`, outside git).
  - The reviewer independently verified 12/12 scenarios: recovery of a posting action without calling the model, the minute-15 retry schedule surviving a restart, the recheck cadence from 6 to 168 hours.
  - 25/25 Resonance test files, UI tests green; CI 4/4. No new blocking errors.
  - The review does not substitute for permission to merge.

## Acceptance table (design section 13)

| Condition | Result | Evidence |
|---|---|---|
| Only a reason can open a model turn (first step, new message, retry within the ceiling); recheck, deadline and unknown code do not call the model | Pass | `test_resonance_a2_heartbeat.py`, policy and check-only cases |
| Achieved and waiting on the user for 30 days: 0 extra turns | Pass | same file |
| Maintaining achieved for 30 days: recheck stretches 6, 12, 24, 48, 96, 168 hours; 0 extra turns | Pass | same file |
| Deadlock after 2 turns means wait, not fail; feedback reopens; with one turn left the automatic retry does not use it | Pass | same file |
| Errors: at most 3 turns in total; a permanent error is not retried; dying mid-turn counts as one error turn | Pass | same file |
| Error and progress streaks are durable, independent of the wake ledger (error written, cut off, died between receipt and ledger close, store reopened, assistant switched back on) | Pass | section "Code review round 1" |
| Deadline near, past the deadline reports once; the two obligations of retry and check do not replace each other; same moment | Pass | same file |
| A schedule the user set counts only from the set time, keeps the time across restarts, is not duplicated | Pass | same file |
| A reason is not lost when blocked (paused, assistant off, guard unreadable); an event mid-turn stays pending; a handover is not handled twice | Pass | same file |
| When shelved, only schedules a check to lift the shelving; does not wake every 30 seconds; does not take another goal's slot; a restart does not wake densely | Pass | same file, including a real store reopen |
| An out-of-band edit: 0 model turns, reports once per hash, does not change the file-replaced marker; rechecks itself from 1 hour to 24 hours; identical metadata with different bytes is still recognized | Pass | same file |
| Guard: paused still watched; assistant off reports lost watching; switching back on rebuilds even when paused; a guard settlement does not open by itself | Pass | same file |
| An error from an old revision does not shelve or delete the new revision's schedule | Pass | section "Code review round 1" |
| I/O before and after the engine call does not run on the event loop; cancelling at any phase does not release the lock early, lose a turn, or refund a turn that ran; a phase error does not hide the cancellation | Pass | sections "Code review round 2" and "round 3" |
| Performance in the test environment: does not read a target file that is not yet due, 3 schedules per beat by `due_at`, loop lag under 50 ms, the number of SQLite statements does not grow with the number of goals | Pass | section "Performance" |
| Rolling back to 0.87.0 with the real code on an upgraded store; upgrading again does not make extra calls | Pass | `test_resonance_a2_rollback.py`, also run on CI |
| Goal card: wake reason labels in two languages, recent wake ledger, watching state, out-of-band edit | Pass | `tests/js/test_resonance_a2_ui.js`; inspected on the sandbox dashboard (below) |
| Performance on a VPS | **Not checked** | Must be measured separately at deployment |

## Integration check (09/10/2026)

- **Base at the time of the check:** A1 (#590) was not merged yet, `main` was at `71f9c5b9`. Afterwards A1 went into `main` (`fdfec7c5`), A2 changed its base and pinned the rollback test to `fdfec7c5` (section "Integration path").
- **Dry smoke on the integrated build:**
  - ran `JAVIS_RESONANCE_E2E_ACHIEVE=dry tests/python/test_resonance_mvp_e2e_achieve.py`;
  - stood up a real server and went through all of S0 to S6 in an assistant session;
  - result `dry_ok`, **0 host-level engine turns**, 255 seconds.
- **UI inspection** on a sandbox server (port 7788, temporary state and brain, fake engine, paused heartbeat):
  - three goals: not met and waiting to retry, maintaining achieved with a guard, file edited by hand;
  - the Partners page, the assistant's Settings tab, shows exactly the items in the table below;
  - no horizontal scrolling. The sandbox was stopped and deleted.

| Goal | What the card shows |
|---|---|
| Not met, waiting to retry | "Next step: ... (redo the unmet part)", 15 minutes after the first turn |
| Maintaining achieved, with a guard | "(periodic review)" and "Watching the protective conditions, next check: ..." |
| File edited by hand | the status "The file was edited outside Jarvis 007, waiting", a warning line with the time of the self-recheck |
| All three | The "Recent wake-ups" section records the reason and "ran one step" or "no model call" |

## After the code review (during the integration check)

1. **A small fix, the reviewer needs to look at the diff again:** the action of POSTING a product created a recovery appointment with code `recovery`, the same obligation as an automatic retry.
   - This bug showed up when inspecting the sandbox's card data.
   - When no retry appointment replaced it, after about 2 minutes it was treated as an automatic retry. For an achieved goal that is harmless; on the branch where a version could not be posted, it could open a turn earlier than the marker.
   - Now an action that is not a work turn uses the code `action_recovery` (check only, never opens a model turn).
   - The work turn's ledger line also records an evaluation trace keyed by the hash of the version just posted, so the first recheck after a work turn stretches out to exactly 6 and then 12 hours.
   - New test: after posting, no automatic retry reason is left waiting. This case failed on the code at `b5975b7e`.
2. **Non-blocking note 1:** the guide lists all four new tables, including `heartbeat_state`.
3. **Non-blocking note 2:** `_cleanup` and the final lock-release step of `advance` log the error that a cancellation carries (`_CancelledWith.error`). The cancellation still proceeds as before.

## Tests run

- `test_resonance_a2_heartbeat.py`: **148 checks passed**.
- `test_resonance_a2_rollback.py`: 11 checks passed. `test_resonance_a2_ui.js`: 10 checks passed.
- The regression group `tests/run.py resonance turn_ route_table plugin hub chat_disconnect workflow agent settings i18n`: **70/70 green** on the integrated code; all JS tests green.
- All 621 files were run once at `c2b0874f`: 605/621. The 16 red files are all due to the machine environment, none belong to Resonance. The full run was not repeated after the fix rounds.
- CI: see the PR for the final head.

## Integration path

1. Merge A1 (#590) first, when the project owner allows it.
2. After A1 is squashed: move the A2 commits (`077bcf73..`) separately onto the new `main`, without pulling in A1's history again. Change the base of PR #593 to `main`, change the rollback pin SHA in the test and in `ci.yml` to the real 0.87.0 commit, and check VERSION and CHANGELOG against `main` at that time.
3. Rerun the regression group, the rollback test and the dry smoke, and wait for CI at the new head. Conflicts in running code (if any) go to an additional review.

**Rehearsal (09/10/2026, temporary worktree, not pushed):**
- Squash A1 onto the current `main` (`71f9c5b9`) to get exactly A1's tree.
- Apply the 10 A2 commits on top: no conflicts, and the resulting tree is identical to `b80ae0ea`.
- Because `main` had not changed since the branch point, after the real A1 squash only the pin SHA needs changing. If `main` gains more commits before that, it must be rechecked.

**Base change done (09/10/2026):**
- The project owner allowed it; PR #590 was squashed into `main` as `fdfec7c5`, locking head `077bcf73`. The squash commit's tree is identical to the A1 head.
- The A2 branch was rebased `--onto main` from `077bcf73`: 11 commits, no conflicts, and the tree is unchanged compared with `72075ead`.
- The pin SHA of the rollback test and the fetch step in `ci.yml` changed to `fdfec7c5`. The base of PR #593 changed to `main`.
- VERSION 0.88.0 on top of `main`'s 0.87.0, CHANGELOG in both languages in the right order.

## Remaining limits

- **VPS performance is not measured.** The event-loop numbers come from a local test environment and do not imply that the tab on the VPS is no longer slow. Measuring tab speed on the VPS is separate deployment evidence (together with the Cloudflare issue and PR #592).
- **There is no real-model pilot for A2.** Design sections 12 and 13 were accepted with a fake clock. If a real pilot is needed, submit a separate scenario and quota.
- **A chat draft that did not pass** is fixed by the background job after 15 minutes (the policy as settled); the card now shows the next step.
- **`user_schedule`** exists in the core but has no button or tool yet for users to set a schedule.
- **Linking `javis_schedule` to goals** is left for later (design section 9).

## User documentation

- [Usage, upgrade, rollback, recovery](resonance-a2-heartbeat.md).
- [A2 design](../superpowers/specs/2026-10-08-resonance-a2-heartbeat-design.md).
