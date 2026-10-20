# Resonance A5: pilot scenario and runner

**Status:** the A5 code passed code review round 2 at `05e9b065` (Codex, 2026-10-12); the runner passed gate review round 3 at `33cec518`. **The real pilot ran twice at `33cec518`, each time with its own approval from the project owner:** real-1 stopped (`stopped`) at the token gate (0 calls); real-2 ended as `pending_content_review`, branch `pass_first`, and was accepted by the reviewer within the scope of that one sample. Results, hashes and limits: [verification record, section Real pilot](resonance-a5-verification.md#real-pilot-2026-10-13). A5 **shipped in 0.109.0** (`bfb1c29f`, PR #616, 2026-10-13; `main` CI run 38369853756 and image build run 38369852881 succeeded; image `ghcr.io/blogminhquy/javis-os:0.109.0`, digest `sha256:3890f824…`; the VPS has not pulled it). Every later real run still needs its own approval from the project owner; code review does not grant that permission.

Design: [2026-10-11-resonance-a5-maker-reviewer-design.md](../superpowers/specs/2026-10-11-resonance-a5-maker-reviewer-design.md). Code verification record: [resonance-a5-verification.md](resonance-a5-verification.md).

## What the pilot proves, and what it does not

Proven with a real model, on the real host path (real server, real store, real Resonance beat, the real API of the assistants page and the card):

1. The background call of the **maker role** (the maker agent, the background-work engine) writes a version that passes the objective check. The host registers exactly those bytes into the target file under the A4 permission the owner granted.
2. The background call of the **reviewer role** (a different agent identity, review instructions, the same background-work engine by design) reads the snapshot of exactly the accepted version (hash, revision, pinned reviewer key) and produces a readable verdict.
3. The branch that actually happens is recorded exactly as it happened:
   - passes immediately; or
   - needs changes, the maker fixes it following the feedback, then it is reviewed again.

   No branch is forced, and nothing is re-run to get a nicer result.
4. Kill and rebuild the server: no further call is made, not even an attempted one.

Not proven:
- The chat brain routing by itself to `javis_goal`: the goal is created with `form_goal` and a frozen proposal, see the section "Creating the goal"; this point was already covered by the A4 pilot.
- The two roles being two independent models: by design, both roles share the background-work engine.
- The branch where the two fix rounds run to the end, retry after `unknown` or after an engine error: those branches need extra calls or a one-hour wait, beyond the proposed pilot cap. They are covered by tests with a fake engine.
- Performance or latency on the VPS: the pilot runs on a local machine.

## Scenario

**Frozen input** (`FROZEN` in `tests/python/test_resonance_a5_pilot.py`), hashed into `frozen_sha256`. Real refuses to run if the hash differs from the approved set.
- Two assistants: `nguoi-lam-tom-tat` (maker) and `nguoi-duyet-tom-tat` (reviewer), with fixed file bodies.
- The assignment (simulated data): a meeting summary at `Inbox/tom-tat-hop-a5.md`, with a Conclusions section and a Next steps section (one item per line, with an owner and a deadline), plus the meeting content. The section headings are the Vietnamese words "Kết luận" (Conclusions) and "Việc tiếp theo" (Next steps); they stay in Vietnamese because the frozen criteria match them verbatim.
- The goal proposal: two `artifact_contract` criteria on the target file, which must contain "Kết luận" and "Việc tiếp theo"; `achieve/delivery`.

**Creating the goal.** No chat call is used. The runner calls `form_goal` with the assignment and the frozen proposal, inside the maker agent's session. This is exactly the function that the `javis_goal` tool and the `/goal-requests` route use, and it does not call a model. `/goal-requests` cannot be used because it makes the goal creator call a model once and set the criteria itself, so the criteria could not be frozen. This seeds the state through the real host function; it is not a fake engine.

**Steps:**

| Step | Server | Work | Model calls |
|---|---|---|---|
| 0 | none | Source check: HEAD is the approved SHA (`JAVIS_RESONANCE_A5_APPROVED_SHA`) and the whole checkout is clean, including product code, the runner itself and no stray files (`preflight_source`). Cost gate: the pilot cap is at most the approved number and enough for the shortest branch. Create the ledger (refuse if one already exists). Engine and auth gate: the background-work engine is exactly the approved configuration; `claude auth status` is the original subscription plan; there is no apiKeyHelper, no provider-selecting env and no admin-set settings | 0 |
| A | beat paused, store ceiling 0, ledger ceiling 0 | Enable the two assistants through `/resonance/agents/toggle`. Choose the reviewer through `/resonance/agents/reviewer`. Create the goal (`form_goal`). Grant the scope through the card's `approve_scope` command. Check the team is attached (reviewer key pinned, 8 calls split 4/4, two rounds), the scope was granted, and the target file does not exist yet | 0 |
| B | beat running, store ceiling = pilot total cap, ledger ceiling per role | Preconditions (both assistants still enabled, the team still pins the right keys, no check broken), token gate (at least 30 minutes left). Observe until the goal ends, the ledger closes, or there is no work scheduled for 5 minutes, no running call, the goal is not in `running`, no wake holds the goal lock, true on two consecutive observations; time cap 30 minutes | per branch, at most 4 |
| C | beat running, store ceiling = number already used, ledger ceiling 0 | Wait about 95 seconds (more than three beats). The ledger has no new call or attempt; actions and review rows are unchanged. Pause the goal if it is still open | 0 |

**Branches that can happen** (the runner reads them from the store and records `branch`):

| Branch | What happens | Maker / reviewer calls | Verdict |
|---|---|---|---|
| `pass_first` | Work, review passes, closes as met | 1 / 1 | `pending_content_review` |
| `one_fix_then_pass` | Work, review says needs changes, fix following the feedback, review passes, closes as met | 2 / 2 | `pending_content_review` |
| `pilot_cap_after_two_reviews` | Two needs-changes verdicts; the second fix call is blocked by the pilot cap, no model call. The first layer to block is the store ceiling, blocking right at reservation (`blocked/budget`, dry sees exactly this). If the store ceiling does not block, the pilot ledger blocks before the engine is built (`blocked/engine_blocked`, the host refunds the call) | 2 / 2 | `business_incomplete` |
| `review_unknown` | The review cannot be read (the engine ran normally); the host schedules a retry in one hour, the pilot does not wait | 1 / 1 | `business_incomplete` |
| `maker_not_met` | The maker's version did not pass the objective check, no review yet; the host schedules a retry in 15 minutes, the pilot does not wait | 1 / 0 | `business_incomplete` |
| `maker_error`, `reviewer_error` | A maker or reviewer call fails in the engine or the host (every error outcome, see "Limits"); the ledger closes | 1 / 0, 1 / 1 | `technical_failed` |
| `no_review`, `other` | Matches none of the branches above; recorded as is, no inference | | `technical_failed` |

If the goal is still open, the runner pauses it after the rebuild check.

## Limits

| | Product (A5, unchanged) | Proposed pilot |
|---|---|---|
| Total background calls per goal | 8 | 4 |
| Maker role | 4 | 2 |
| Reviewer role | 4 | 2 |
| Fix rounds | 2 | 1 full round (the second fix round is blocked by the pilot cap) |
| Chat calls | not applicable | 0 |

The unit is a **host-level engine call**: one engine build for one work or review call. It is not an internal SDK request, and it is not tokens.

The blocking layers (none replaces another):
- **The pilot's per-role call ledger** (`tests/python/_a5_pilot_ledger.py`, launcher `tests/python/_a5_pilot_server.py`).
  - Reserves a slot and fsyncs BEFORE building the engine for each call.
  - Has a role cap, a total cap and a per-phase cap (A and C are 0).
  - The outcome of a call follows the host's own error rules (`GoalDeps._ask`): an `error` frame; a `final` with `is_error` or `dua_token`; a tool call inside a text-only call (before or after `final`); empty output, output that is too long, or a login-error message; an exception; cancellation while the host is still reading (timeout); a missing end frame; failure to build. A second layer wraps the host's own `_ask`: if the host concludes an error after the engine was called, the ledger row becomes `host_<code>`.
  - `ok` is only provisional: an error that arrives later downgrades it (recorded as `downgraded_from`), and an error is never upgraded to `ok`. If the host stops reading after a valid `final`, `ok` stays.
  - Every error outcome still counts the call, and the ledger closes immediately.
  - When blocked, the real engine-building function is never touched; the host refunds the call through A5's not-run path. The ledger only records one `refused` event.
  - If a ledger already exists, the run is refused; if the ledger is corrupt, no call is granted and nothing is overwritten.
- **The store ceiling** `JAVIS_RESONANCE_CALL_CEILING`, applied to every server process.
- **The product ceiling** of the team (8, 4/4, two rounds).
- **Post-check.** The pilot ledger must match the store's role ledger (`team_calls`) and `calls_used`; every counted review row (`charged=1`) corresponds to one reviewer call. A missing, corrupt or mismatched ledger is **unverified**, never 0.

No retry, no raising the cap, no switching to a paid API. The sandbox settings copy only the provider/model names (`auxiliary`, `main`, `engine`, `claude_model`), not keys or the auth mode.

## Evidence for each point

| What must be proven | Evidence (`a5-pilot-real-main.json` and the attached files) |
|---|---|
| The maker | A `work` action carrying the maker agent's `agent_key`, `role=maker`, the `engine_at` mark; a `maker` ledger row with provider/model; output `a5-maker-<n>.md` |
| The reviewer | A `review` action and `reviews` row carrying the pinned reviewer key (different from the maker agent's key), `role=reviewer`, the `engine_at` mark; a `reviewer` ledger row; raw output `a5-reviewer-<n>.txt` (read from the host's encrypted evidence); verdict, criteria and feedback in `store_B.reviews` |
| Right hash and revision | `bundle_ref` carries the right revision, registration mark, hash and reviewer key. The hash is the normalized bytes of one maker call's output. The snapshot the reviewer read hashes back to the same hash. On a met close: the target file has exactly the bytes of the version the review passed, at the same revision |
| Fix round (if it happens) | A `needs_changes` row, the maker call after it, a new review call on the new pin set |
| Rebuild makes no more calls | `restart`: no new ledger row, event, action or review row |
| No other file touched | Brain snapshots before and after phase B: only the target file changed; the old notes are intact |

## The verdict of a run

A single function, `decide_acceptance` (`tests/python/_a5_pilot_ledger.py`), decides the verdict from the FINAL evidence. Real and dry use the same rule. Any missing field counts as not passing.

| Verdict | When | Exit code |
|---|---|---|
| `stopped` | Stopped at a gate before the background-work phase (no server could have called a model) | 1 |
| `technical_failed` | Any of: a broken check; stopped after background work had started; the background-work phase ended abnormally (timeout, corrupt ledger, tripwire); the ledger at the final read cannot be verified; a call whose outcome is not `ok`; the server's engine-call ledger cannot be verified; the rebuild is unchecked or made new calls; an unknown branch; the number of calls (ledger, the store's role ledger) differs from the branch's; the goal state differs from the branch's; a missing saved output for any maker call, any review call, or the target file at close; a review snapshot that did not hash back correctly; evidence preservation failed | 1 |
| `pending_content_review` | Fully technically passed and the goal closed as met (`pass_first`, `one_fix_then_pass`): waiting for a person to read the content. There is no automatic "pass" | 0 |
| `business_incomplete` | Fully technically passed, the business branch did not pass but is defined (`pilot_cap_after_two_reviews`, `review_unknown`, `maker_not_met`); `branch` is kept as is | 2 |

A negative case in dry meeting its expectation means the runner produced exactly `technical_failed` or `stopped`. That is a passing test of the runner, not a technically passed pilot.

**Writing the final record is part of the verdict** (`finalize_record`, gate review round 2):
- When the sandbox is kept, `a5-pilot-recovery.txt` is written FIRST; the JSON report is written LAST. So there is never a report that says pass while a required file written after it is broken.
- If any required write fails: the verdict becomes `technical_failed` (exit code 1, even if it was `pending_content_review` or `business_incomplete` before), a specific cause is added, the branch is kept, and the sandbox is kept (`sandbox_kept = true`).
- If the report fails, the recovery path is rewritten with the new verdict and the report is tried exactly once more. If it still cannot be written, it prints "KHÔNG GHI ĐƯỢC HỒ SƠ CUỐI" (Vietnamese for "could not write the final record") with the sandbox path to stdout and stderr; the string stays in Vietnamese because the tests match it.
- The `A5_PILOT` line is printed after the verdict is final, with `report_saved`. This line, the report (if any), the exit code and the sandbox-kept state always carry the same verdict.

## Evidence preservation

On EVERY branch, after every server has stopped, the runner copies the evidence into a NEW `sandbox/` folder inside the record folder (nothing existing is overwritten):
- the goal store and the conversation store, copied with SQLite backup (consistent, WAL included);
- the usage ledger and settings (only provider/model names);
- the log of every server, with keys and tokens masked;
- the whole temporary brain (assistants, the target file, the outputs of the maker calls) and the dry scenario.

The store and log of every server that was started are required items. The secrets store and the encryption key are not copied.

**The original sandbox is kept** on real runs (always kept), when the verdict is not `pending_content_review`, when preservation fails, or when the record folder is inside the sandbox. In that case the runner prints `A5_PILOT_KEPT <path>` and writes `a5-pilot-recovery.txt` (sandbox path, copy, verdict, reason). The source is never modified or deleted; a corrupt file is copied byte for byte; a corrupt ledger is never overwritten. The person running it does not need to set any extra variable.

## Dry

`JAVIS_RESONANCE_A5_PILOT=dry python tests/python/test_resonance_a5_pilot.py` runs 24 cases, each in a child process with a real server, going through exactly the same orchestration path, verdict function and record-writing phase as real. A case passes only when its exit code matches the verdict's contract and the required JSON report (except in the case that blocks the report write) carries the same verdict, branch and sandbox-kept state as the `A5_PILOT` line. Dry blocks the path to the real engine right from the configuration and the call path, not just by counting after the run:
- the settings use a provider that does not exist (`pilot-dry`);
- the launcher replaces the background-work engine builder with a fake engine that reads a script; the "real" builder is a tripwire;
- there is no chat call at all.

Each case also verifies that the sandbox server's own engine-call ledger (`usage.json` and `usage-events.jsonl`) is 0.

| Case | Verdict | Branch, ledger (maker, reviewer) | Extra check |
|---|---|---|---|
| `main_pass` | `pending_content_review` | `pass_first` (1, 1) | every evidence check |
| `main_fix` | `pending_content_review` | `one_fix_then_pass` (2, 2) | a separate fix call after the needs-changes row |
| `fix_cap` | `business_incomplete` | `pilot_cap_after_two_reviews` (2, 2) | the store ceiling blocks the third fix call at reservation |
| `ledger_cap` | `business_incomplete` | same as above (2, 2) | the store ceiling raised to 8 (dry only); the ledger blocks before the engine is built, the host refunds the call |
| `review_unknown` | `business_incomplete` | `review_unknown` (1, 1) | no retry |
| `maker_not_met` | `business_incomplete` | `maker_not_met` (1, 0) | no retry |
| `maker_error`, `final_is_error` | `technical_failed` | `maker_error` (1, 0) | an `error` frame error, or a `final` with `is_error`; the ledger closes; sandbox kept |
| `reviewer_error` | `technical_failed` | `reviewer_error` (1, 1) | a reviewer engine error is not merged with an unreadable review |
| `timeout` | `technical_failed` | `maker_error` (1, 0) | the engine hangs past the time cap (60 seconds in this case); a call that still holds its reservation is unverified |
| `missing_output` | `technical_failed` | `pass_first` (1, 1) | the maker call's output is gone before the save step |
| `ledger_lost_end` | `technical_failed` | `pass_first`, ledger unverified | the ledger is lost right before the final read (renamed, the `.lost` file remains) |
| `save_error` | `technical_failed` | `pass_first` (1, 1) | an error while copying the store; preservation failure; sandbox kept, original store remains, a recovery path exists |
| `early_crash` | `technical_failed` | (0, 0) | the runner fails before the normal save step; logs and stores are still copied |
| `ledger_corrupt` | `technical_failed` | ledger unverified | a corrupt ledger before B: no call is granted; the corrupt file keeps its bytes |
| `tripwire` | `technical_failed` | (1, 0) | the "real" engine-building path was called in dry: the tripwire records an event |
| `report_fault` | `technical_failed` | `pass_first` (1, 1) | writing the final report fails after a passing result: exit code 1, no report, sandbox kept, a recovery path exists |
| `recovery_fault` | `technical_failed` | `review_unknown` (1, 1) | writing the recovery path fails on a business-incomplete result: exit code 1 (not 2); the report says technical_failed |
| `report_fault_technical` | `technical_failed` | `maker_error` (1, 0) | an inherent technical error plus a report write error: still a failure, sandbox kept |
| `cost`, `auth`, `ledger_exists`, `precondition`, `sha_mismatch` | `stopped` | | stopped at a gate before background work |

The ledger logic, call outcomes through the real `_ask`, the verdict, preservation, cleanup rights and the source check have their own tests that need no server: `tests/python/test_resonance_a5_pilot_gate.py`.

## Real run (only after approval)

```bash
JAVIS_RESONANCE_A5_PILOT=real JAVIS_RESONANCE_PILOT_SETTINGS=<real settings.json> JAVIS_RESONANCE_A5_OUT=<new folder, outside the checkout> JAVIS_RESONANCE_A5_APPROVED='{"aux": {"provider": "anthropic-cli", "model": "sonnet"}}' JAVIS_RESONANCE_A5_MAX_CALLS=4 JAVIS_RESONANCE_A5_INPUTS_SHA=<frozen_sha256> JAVIS_RESONANCE_A5_APPROVED_SHA=<approved SHA> python tests/python/test_resonance_a5_pilot.py
```

Exactly once, on a clean checkout at the approved SHA. The runner checks for itself (step 0, before any server) that HEAD is exactly `JAVIS_RESONANCE_A5_APPROVED_SHA` and the whole checkout is clean; if it is wrong or unreadable, it stops, with no calls. The record folder must be outside the checkout.
