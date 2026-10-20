# Team chat group: locking the T1 foundation to the unified GOAL (0.152.0)

GOAL: `exports/reviews/GOAL-TEAM-CHAT-T1-T4-COMPLETE.md` sections 4.1, 4.2, 4.3, 5, 9, 12 (cases 1, 3, 11, 12, 13, 14). Foundation: [team-chat-t1.md](team-chat-t1.md) (0.111.0) and later versions. Every check here runs with a FAKE engine, with no model calls and no VPS access.

## 1. R1 to R9 verified on the actual head

| Code | Requirement | Evidence |
|---|---|---|
| R1 | Classify engine failures: failed final, empty final, tool calls that never become a product | Reviewer script (adapter version) `PASS fixed R1_engine_outcome`; `test_team_t1_review.py` |
| R2 | Correct team history in the prompt | `PASS fixed R2_context` |
| R3 | Check late output before writing a lesson | `PASS fixed R3_late_learning` |
| R4 | Refund a turn that never reached the engine | `PASS fixed R4_before_engine` (turn is `refunded`, no engine mark) |
| R5 | I/O off the event loop, keep the turn atomic | `PASS fixed R5_event_loop`, largest gap 40.8 ms (threshold 100 ms, local machine) |
| R6 | Consistent store recovery | `PASS fixed R6_rollback`; `test_team_rollback.py` |
| R7 | An old revision does not settle a new one | `PR-628-T1-r2-race-checks.py --expect-fixed`: `PASS fixed R7_stale_revision`; plus a permission-revocation case at the apply gate (G1 below) |
| R8 | Several kicks never exceed the pool, no duplicate pickup, no leaked slot | `PASS fixed R8_parallel_cap`; G2 (second kick while A is running), G4 |
| R9 | Recovery broken after a write | `PASS fixed R9_restore_failed_destination` |

Full output with commands and exit codes: `exports/reviews/team-adaptive/t1-evidence.txt`.

**The reviewer script must be the adapter version.** Since 0.142.0, `main._team_engine_for` builds the engine through `team_engine.build` and no longer through `main._resonance_engine`, so the original `PR-628-T1-review-checks.py` can no longer swap the engine and called the REAL engine. The version `team-adaptive/PR-628-T1-review-checks.adapted.py` changes only the point where the engine is swapped (diff: `PR-628-T1-review-checks.adapter.diff`), keeps every scenario and expectation, and adds a guard: if it builds a real engine or runs an engine CLI (claude, codex, grok, agy, gemini, ollama), it stops with a clear message and exit code 2. After the scenarios it checks that the fake engine was called exactly once per scenario. The guard has been self-checked: with the engine swap removed, the script stops at `REAL ENGINE BLOCKED`.

## 2. Changes

1. **Pin the authority per turn** (GOAL 9 "an old turn does not benefit from a re-grant"). `team_turns.authority_id` records the Full authority row in force in the SAME transaction that reserves the turn (`team_store.reserve_turn`), and only for a turn of the team leader that was granted it. `team_runner._apply_admin` compares the row in force with the pinned row inside `accept_lock`; if they differ (revoked then re-granted, newly granted, permission box edited, granted when the turn started under Limited authority) the command is dropped with a note. The prompt also shows the Full authority block only while the pinned row is still in force. The leader changing a cap inside the row (`set_cap`) does not change the row, so it has no effect on this.
2. **Priority through the host path**: the behavior was already correct; a regression-guard test was added (A is running in the engine, priority C, order A, C, B; A runs once and is not interrupted; a second kick does not open work beyond the pool).
3. **Renew the busy lock and the job hold deadline during a long turn.** `TeamRunner._keep_leases` runs for the whole turn and renews `agent_busy` (`team_store.renew_busy`, which UPDATEs only that turn and never takes the lock back) and the job hold deadline (`task_store.team_heartbeat`) every `min(30 seconds, deadline/3)`. It stops when the turn finishes or is cancelled, before the lock is released. The deadlines are adjustable on the runner (`busy_lease_s`, `job_lease_s`, `lease_renew_s`).
4. **`running_jobs` becomes a server limit.** The shared pool skips a team that already has a running job (T1 review R8), so a number greater than 1 used to be accepted without ever taking effect. The small, safe change: remove it from the owner-editable caps (`team_store.OWNER_CAPS`) and fix it at 1 (`FIXED_CAPS`); old rows that stored another number still show 1. Opening parallel jobs inside one team would collide with the per-agent busy lock, the queue order and the shared context, so that is left for a later milestone if needed. `no_progress` is handled the same way: the runner stops at two identical results in a row, and the number was never read.
5. **Limits table** (`TeamRunner.limits_table`, returned in `authority.limits` of the team view) and a "Limits table" section under Advanced (`teams.js` `limitsHtml`, i18n vi/en, 16px text). The owner's cap has its own **Unlimited** box right in the team's Limits section (it stores `null`, not a large number).
6. **The leader's `set_resonance`** calls `wake_agent_goals` after turning it on, like the owner's enable route (`_TeamAdmin.set_resonance`). Rule written in `_apply_admin`: only assistants managed by THIS team, and only under the Full authority row pinned for the turn (Full authority includes managing team-managed assistants, spec 13.3). If the owner already turned an assistant off and the team only has it as a member, or another team manages it, the leader cannot turn it back on. Logs: `team_events` `agent_set_resonance` and `resonance_agent_events` by `leader:<id>`.
7. **Changing a tag does not change the team** (GOAL 12.1): a test through the real route was added; the behavior was already correct.

## 3. Limits table

| Limit | Default | Who can change it | Unlimited |
|---|---|---|---|
| Max replies per job (`task_turns`) | 12 | Owner; leader under Full authority, within the maximum cap | Yes (Full authority: only for plans the owner ticked, D6) |
| Max steps per job (`task_steps`) | 8 | Owner; leader under Full authority | Yes |
| Nested ask-for-help depth (`help_depth`) | 2 | Owner; leader under Full authority | Yes |
| Max replies per day (`daily_turns`) | 100 | Owner; leader under Full authority | Yes (Full authority: only for plans the owner ticked, D6) |
| Max people called (@) per message (`mentions`) | 3 | Owner | No |
| Max wait for a busy assistant (`busy_wait_s`) | 1800 seconds | Owner | No |
| Jobs running at the same time in one team (`running_jobs`) | 1 | Fixed by the server | No |
| Teams running jobs at the same time on the whole machine (`max_parallel_teams`) | 2 | Fixed by the server | No |
| Simultaneous turns of one assistant, all teams | 1 | Fixed by the server | No |
| Busy lock deadline (`BUSY_LEASE_S`), renewed automatically while the turn runs | 900 seconds | Fixed by the server | No |
| Stop after identical results in a row (`no_progress`) | 2 | Fixed by the server | No |
| Time for one reply (`JAVIS_TEAM_TURN_TIMEOUT`) | 600 seconds | Server (environment variable) | No |
| Time for one step (`JAVIS_TEAM_STEP_TIMEOUT`) | 3600 seconds | Server (environment variable) | No |
| Admin commands per leader reply | 10 | Fixed by the server | No |
| Recent messages an assistant reads per turn | 20 messages, 8000 characters | Fixed by the server | No |
| Team turns are text only, no tools | rule | Fixed by the server | No |
| Machine-wide turn ceiling (`JAVIS_RESONANCE_CALL_CEILING`, read with `resonance_store.call_ceiling()`; a broken or negative value is 0, which blocks everything) | not set | Server (environment variable) | No |
| Quota of the subscription plan or provider | rule | Provider | No |
| Permissions of the model account | rule | Provider | No |

No mode is described as "removes every limit": the server and provider groups always apply, even at Full authority level 3.

## 4. Tests

- `tests/python/test_team_t1_goal.py` (real runner and store, fake engine, Events with a wait deadline): G1 authority pinning (four cases, including the plan step), G2 priority, G3 renewing the busy lock and job hold deadline (finished and cancelled), G4 `running_jobs`, G5 limits table and Unlimited, G6 the `set_resonance` rule. On the old head `75e17400`: 24 red cases (G1, G3, G4, G5); G2 and G6 are green because the behavior was already correct (regression guard).
- `tests/python/test_team_t1_goal_host.py` (main.py, TestClient, fake engine, real-engine guard): H5 limits table and Unlimited through the route, H6 `set_resonance` wakes goals and the management rule, H7 tag change. On the old head: 4 red cases (H5, the wake part of H6); H7 is green.
- `tests/js/test_teams_ui.js`: the Unlimited box of the owner cap, the limits table, i18n, 16px CSS.
- `tests/python/test_team_t1_review_fixes.py` (independent T1 review, after `af85ad71`): F1 lost hold (lock moved to another turn, job changed holder, store failing past the deadline; control: a store failing transiently for one beat), F2 renewing the job hold deadline while waiting for the busy lock, F3 the server ceiling in the table equals `call_ceiling()`, F4 Auto can be turned on even when the wake fails, F5 `set_caps` blocks NaN and infinity. Host: H8 (wake failure through `main._TeamAdmin`), H9 (caps route returns 4xx for NaN, Infinity, 1e400). JS: `capsPayload` sends nothing when Unlimited is unticked and no number was entered.

## 5. Fixes from the independent T1 review

- **Losing the hold in the middle of a turn** (`team_runner._keep_leases`, `_accept`): a renewal returning False is a real loss (`busy_taken`, `job_lost`); a store error becomes a loss (`store_error`) only when a whole deadline passes without a single successful renewal. Before releasing the lock there is one last check of `TeamStore.busy_turn`. A turn that lost its hold has the result `lease_lost`: the message is still posted as evidence, but no lesson is written and no admin command or step result is applied. If the job moved to another process, the step is not touched and the loop stops; if only the agent lock was lost, the step runs again.
- **Waiting for the busy lock** (`_keep_job_lease`): the job hold deadline is renewed during the wait, without touching the agent lock of another turn.
- **Limits table** reads the server ceiling with exactly `resonance_store.call_ceiling()`.
- **Auto turned on but the wake fails** (`main._TeamAdmin.set_resonance` returns `wake_error`): Auto stays on, the team log has `agent_set_resonance` and `agent_wake_failed`, and the note says plainly that Auto is on.
- **`set_caps`** rejects NaN, infinity and wrong types before writing (both `busy_wait_s` and the cap in the permission box), and returns 4xx.
- **Wording:** the `effective_caps` docstring and the coordinator's cap note now state correctly the case where the owner sets a cap to Unlimited.
- **Round 2 of the fix review:** the final lock check sits in a `try/finally`, so a second cancel still releases the lock (F6); a job that loses its holder right while waiting for the lock does not call the engine and refunds the turn (F7); a lost job still keeps the agent lock until the turn ends; `job_lost` beats any late label; repeated lock loss is limited to `LEASE_REQUEUE_MAX = 2` reruns per step and then blocks the job (F8), even when the cap is Unlimited; a reply turn that lost its hold before the engine has the reason `lease_lost`; the Save limits button is split into `saveCapsFlow` so the real behavior can be tested (no POST, focus on the right box).

## 6. Measured fluctuation (not a regression)

- The CI of `af85ad71` failed one latency check in `test_resonance_perf.py` (0.102 s, threshold 0.1 s). That commit changed only `teams.js` and i18n. Re-running the same SHA on CI: green (second run, run 38629547827). Locally 5/5 passed. A real regression (blocking the event loop) gives about 0.2 s, not 0.102 s. The threshold is unchanged.
- `test_team_t1_review.py` R5 (event loop with a store slowed by 250 ms): on the fixed version it was red 1 of 5 times (114.6 ms), on the original code `3240168f` it was red 1 of 6 times (237.8 ms), while two other agents were running tests on the machine. An AST scan of every async function in `team_runner.py` found no synchronous store call on the event loop. Conclusion: fluctuation caused by machine load, present before; the threshold is unchanged.
