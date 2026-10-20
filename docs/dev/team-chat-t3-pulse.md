# T3 part P: adaptive pulse, layer 3 (0.156.0)

Original design: `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` sections 2, 3, 5, 6, 9, 9.1, 10, 12, 13. Contract with parts
J (judge) and L (learning): `docs/dev/team-chat-t3-contract.md`. This part never calls a model itself in tests; every path through
`main.py` blocks the real engine at build time.

## 1. Code map

| Part | File | What it does |
|---|---|---|
| Pure policy + store | `server/agent_pulse.py` | `pulse.v1`: tiers, states, `decide`, `score`, `compute_k`, `attribute`, `effective_due`; tables and store operations (`record_signal`, `wake`, `set_state`, `evaluate`, `view`, `record_contrib`, opportunities, seen, policy changes) |
| Host | `server/agent_pulse_host.py` | the 30 second tick (`PulseHost.tick`), wake-ups, the scan turn, adapters to `agent_judge` and `agent_budget`, the registry of view sections and reasons, routes |
| Projector | `server/feedback_projector.py` | `record_pulse_signal` (the T2 hook, now wired), `record_task_event`, `pulse_wake`, `void_task_event`, replacing a signal when a reaction changes |
| Team | `server/team_runner.py`, `server/team_api.py` | signals for accepting a proposal, settling a decision, editing after a result, cancelling; wake when the owner @-mentions or assigns a job; the `max_tier` row and the 20% reserve in the limits table |
| Resonance store | `server/resonance_store.py` | opening the store creates the pulse tables and upgrades once; re-enabling from `off` goes back to B3 |
| Server | `server/main.py` | `_pulse_tick` inside `_scheduler_loop` (its own busy flag), real dependencies, wake when the owner messages a private chat, deleting an agent `void`s its signals, route registration |
| UI | `dashboard/agent-pulse.js`, `dashboard/pulse-seen.js`, `workspace.js`, `teams.js`, `console.css`, i18n | the Pulse panel on the assistant card and the member row, the `window.JavisPulseParts` registry, the seen event |

## 2. Policy `pulse.v1`

Tiers: B0 15 minutes, B1 1 hour, B2 4 hours, B3 1 day, B4 3 days, B5 1 week, B6 2 weeks, B7 1 month, tier 8 is hibernation (no schedule).
Initial tier is B3. State by tier: `active` B0-B2, `awake` B3-B4, `slowed` B5-B7, `hibernating` tier 8; in addition `waiting_owner`,
`paused`, `off` are set by the owner or the host and only stop the proactive part.

Each evaluation period (`decide`):

1. `dwell = max(2 x interval, 1 day)` counted from the previous tier change (or the re-enable mark): if not enough time has passed, hold.
2. Up one tier when `u >= +0.25` and `new >= 1.0`, no faster than `max_tier` (default B1; only the owner sets it, down to B0).
3. Down one tier (`unhelpful`) when `u <= -0.25` and `new >= 1.0`; from B7 this rule does not enter hibernation.
4. Down one tier (`low_demand`, not recorded as the agent being wrong) when there is no unconsumed opportunity right now and one of:
   (A) no new interaction signal since the previous change and no opportunity within two intervals; (B) the most recent interaction signal and opportunity
   are both older than `max(4 x interval, 3 days)`.
5. Otherwise hold. Hysteresis: a change of direction only after at least one holding period.

`new = sum of w*share*decay` over signals after `max(last_change_at, resumed_at)` (context-init signals are not counted). "Interaction"
does not include `seen_ignored`.

Formulas (6.3): `decay = 0.5^(age in days / 21)` (negative age clamped to 0); `estimate = sum of w*share*v*decay / (sum of w*share*decay + 2)`;
`n_eff = sum of w*share*decay`; `confidence = n_eff / (n_eff + 4)`; `u = estimate x confidence`. Personalization only applies to reactions
without a reason: `p_s(e) = (count of e + 3)/(n + 18)`, `k = clamp(1 + 0.3 x (1/6 - p_s)/(1/6) x n/(n + 20), 0.75, 1.25)`, `n` is the number of that person's
reactions without a reason in the context kind (team or private chat), counting each source once, recomputed every period.

Signals (6.1): ❤️ +0.8 w1, 😮 +0.6 w1, 👍 +0.4 w1, 😂 +0.2 w0.5, 😢 -0.2 w0.4, 😡 -0.4 w0.4; when there is a reason, the reason wins over the emoji
("On point" +0.8, "Too long" -0.3, "Wrong facts"/"Missing points"/"Unclear"/"Off topic" -0.6, w1, several reasons are averaged); the speak/silent axis and written feedback
create no signal; accepting a proposal/settling a decision +0.6 w0.8; editing after a result, cancelling, rejecting a proposal -0.4 w0.8; an
objective check +/-0.5 w0.8 (section 2a); a proactive message that was seen and got no interaction after 24 hours -0.15 w0.6; an agent's reaction never counts. `pulse_signals` is UNIQUE on `(source_ref, agent_key)`; replacing a reaction sets `superseded_by` on the old row, and deleting a message/agent `void`s it.

## 2a. Objective check and proposals: which host events count

- **Objective check (+/-0.5 w 0.8), the FINAL conclusion only**, one signal per (goal, revision), source `obj:<goal_id>:<revision>`:
  - achieved: `GoalStore.finish(..., "succeeded")`, meaning A2 just judged `met`, every guard is `clear`, not in an exploration step, and (if the goal
    has a team) a valid A5 review `pass`; this is the only place that closes a goal as achieved;
  - not achieved: `GoalStore.finish(..., "failed")` (the API exists, no path calls it yet), or a revision parked as `blocked/budget` in
    `_settle` when the final check is `not_met` (all turns used up, no attempt left); an `unknown` conclusion does not count;
  - does NOT count: any `add_assessment` inside a working round (an intermediate `not_met`), a passed deadline (informational only), the owner cancelling.
  - If the same revision later gets a different final conclusion (the owner raised the limit and then it succeeded): the value of that same signal is corrected, still one row.
  - Recipient: the goal's agent (`goal_agents`), context `dm:<agent_key>`, only when Resonance is on. An A2 goal has a single
    output author and no synthesis step, so rule 6.5 attributes to the author.
  - Team jobs: the host has NO objective check when a job is settled (`team_finish` only records the result), so there is no check signal.
- **Proposals** (`pulse_proposals`): a `propose` scan turn writes a ledger row (source, version). A proposal with the same source and the same version that already exists (waiting,
  accepted, rejected) is not proposed again (5.5). The owner decides:
  - team: a card in the chat window (the Create job button is accept, +0.6, and queues the job in the team's shared queue as before; the Skip button is now reject,
    `POST /teams/{id}/messages/{mid}/reject`, -0.4); the status is written onto the message so every tab sees it, and the card loses its buttons;
  - the Pulse panel: `POST /agents/{slug}/pulse/proposals/{id}/accept|reject`. Private chat: accepting turns it into a job assigned to the assistant like the
    Assign job button (Kanban, reports back to the private chat, dedupe key `pp<id>`), +0.6; rejecting -0.4. A team proposal from the Pulse panel goes through the
    team card path. Already decided: 409.
  - A team lead with Full authority can queue jobs itself (enqueue of the scan turn), so it does not need approval for its own proposals.

## 3. Fake clock vectors (`tests/python/test_agent_pulse_policy.py`, all green)

| Scenario | Measured in the test | Result |
|---|---|---|
| 1 ❤️ | k 0.9962, u 0.0531 | hold B3 |
| 2 ❤️ | k 0.9864, u 0.1315 | hold B3 |
| 5 ❤️ on days 0.5..2.5 | day 2: u 0.2494 (hold); day 3: k 0.935, u 0.2861 | up to B2 exactly once, not up to B1 |
| 5 ❤️ spaced 3.5 days apart | u 0.2481 at day 14 + 8 hours, maximum over the whole range < 0.25 | hold B3 throughout |
| 10 ❤️ in 1 minute | k 0.8214, u 0.3912 | B2 at the period after dwell, no further rise the period after |
| then 10 ❤️ every 1.4 days | | reaches B1, never B0, and slows down when quiet for long |
| 3 👍 1 ❤️ 1 😮 | k 0.997 / 0.966 / not yet used 1.013 | k always within 0.75-1.25 |
| Silence from B3 | | day 2 B4, 8 B5, 22 B6, 50 B7, 110 hibernation (day 30 B6, 90 B7, 180 hibernation) |
| 3 proactive messages seen and ignored | u -0.0221 | not `unhelpful`; `low_demand` when nothing else, hold when there is an opportunity |
| 5 / 6 "Wrong facts" | u -0.2378 / -0.2697 | hold / down to B4 (`unhelpful`) |
| Correct silence (there was an opportunity, the judge stayed silent) | estimate 0 | no penalty, no `low_demand` within two intervals |
| Direct call during hibernation | | straight back to B3, estimate kept |

## 4. Host (`tests/python/test_agent_pulse_host.py`)

- `_scheduler_loop` creates `_pulse_tick` every 30 seconds when its busy flag is free. The tick: projects the feedback outbox (T2), creates the context rows
  per scope (every 5 minutes), scans `seen_ignored`, nudges the waiting owner once after 24 hours, closes policy change windows, finds due
  schedules and claims them with CAS (`claim_token`, `claim_until` 10 minutes), and dispatches reasons to the registered handlers.
- Agent busy (busy lock, a team job running/queued, an A2 goal running): postponed by exactly 60 seconds, not claimed.
- Wake-up: builds opportunities (the agent's team job older than the current interval, a blocked job with a new message, a team lead proposal nobody
  has handled, the agent's goal waiting for the owner for more than 24 hours), filters by `pulse_opportunities` (consumed once until a new version), evaluates
  the tier, and only calls the model when there is a new opportunity (or it is the limited scan's turn: every 3 wake-ups in active/awake, at most once a day per
  context).
- Scan turn: try the busy lock WITHOUT waiting first (busy: postpone 60 seconds, no attempt spent), ask `agent_budget.try_spend` (if the module does not exist
  yet, let it through), reserve an `agent_calls` slot with purpose `scan`, `obligation = 0`, `reason_ref = pulse:<agent>:<context>:<mark>` BEFORE the engine.
  A schedule that already had a turn reach the model (a restart) does not run a second time. Output `{"action": none|propose|enqueue|say}`; enqueue
  only for a team lead with Full authority, otherwise it becomes a proposal; a limited scan with no source creates nothing; `say` always goes through
  `agent_judge.judge_proactive`, and if the module is missing it is `silent` with reason `judge_unavailable`.
- Obligations do not go through layer 3: the test runs the real team runner with a paused, hibernating and pulse-off agent and checks that direct calls
  and team jobs still run.

## 5. Migration and rollback

- Opening `resonance.sqlite3` with this code creates `agent_pulse_events`, `pulse_signals`, `pulse_contrib`, `message_seen`,
  `pulse_opportunities`, `pulse_proactive`, `pulse_policy_changes`, `pulse_proposals`, `pulse_meta`, and adds columns with defaults to
  `agent_pulse`. The first
  time (mark `pulse_v1_upgraded_at`): every pulse row goes back to B3, `resumed_at = upgrade time`, agents with Resonance off stay at `off`; old reactions
  do not become signals.
- Rollback to 0.154.x: the old version ignores the new tables and columns (all columns have defaults). A full restore uses the `.pre-0.154.0` snapshot as in T2.

## 6. Decisions made along the way

1. **Rule `low_demand` (B):** read literally, rule 4 (no new signal since the change, no opportunity within two intervals) means one
   reaction right after a change keeps the fast tier forever, against the line "slows down when quiet for long". Added (B) "quiet for more than `max(4 x interval, 3
   days)`". The threshold of 4 intervals is so the vector "5 ❤️ spread over 2 weeks" (3.5 days apart) still holds B3 and the vector "10 ❤️ every 1.4 days" still reaches B1.
2. **At B1-B2 the agent oscillates by one tier** when interaction is sparser than dwell (rule A). Hysteresis and dwell keep each change at least
   a day apart; a test pins that.
3. **The initial value for a new context, "0.5 x aggregate"**, is an initialization signal (`context_init`) carrying the aggregate estimate with
   `w = min(1, 0.5 x aggregate n_eff)`, decaying like other signals, not new evidence, and not part of `k`.
4. **Several quality reasons** on one reaction: the value is averaged.
5. **`k` only counts reactions without a reason** (a reaction with a reason uses the reason's value, `k = 1`).
6. **The objective check only counts the final conclusion** (section 2a), never an intermediate assessment.
7. **Skip on a team proposal card is now reject** (recorded on the server, -0.4); before, it only hid the card on the page.
8. **Un-settling then settling again** the same message does not count again (a `void`ed source keeps the UNIQUE slot), preventing toggling back and forth to raise the score.
9. **Layer 3 reasons while paused:** the host does not dispatch reasons for a `paused`/`off` context; hibernating and waiting for the owner are still served.
10. **`POST /seen`** also accepts `context_ref = "session:<session id>"` (the page does not know `agent_key`); the server converts it to
    `dm:<agent_key>` and returns `agent: false` for a session that is not an assistant's so the page stops sending.
11. **A proposal in a private chat** is a proposal message with a source (no dedicated card yet); in a team it is a message carrying `proposal` (the existing Create job button).
12. **Without `agent_budget`** (part L did not exist yet) the scan turn has no daily cap; the server-wide ceiling and the 20% reserve still apply.
13. **Resetting a context's pulse** keeps the history and estimate, only returns it to B3 and treats evidence before the mark as old.
14. **Busy lock when there is no team store yet:** an in-process lock (there is no team turn yet to contend for the lock).

### 6.1 Fixes after the T3 review (branch `claude/team-adaptive-t3-fix`)

15. **Delegated scope (P2-1):** `_code_pass` reads `deps.contexts(key)` every tick: a row outside the scope loses its schedule (event
    `out_of_scope`) and its layer 3 reasons are not served; when it comes back into scope it gets a schedule again. If reading the scope fails, that pass is skipped and nothing
    is removed. `main._pulse_team_live` (active team, member currently participating) blocks every autonomous post/propose/enqueue path.
16. **The "cancel" signal (P2-2):** only the owner's cancel-job route (`owner_cancel=True`); a team lead interrupt, archiving the team, or cancelling a hanging job writes nothing.
17. **Event loop (P2-3):** the private chat reaction route, `_pulse_wake_dm` at the end of a chat turn, and `deps.store()` of the pulse route run in a worker thread.
18. **P3:** wake-up, new row, reset, re-enable are clamped by `max_tier`; 15 minute lease, scan turn at most 9 minutes; `ledger_busy` releases
    the schedule; the "Waiting for quota" label is lifted when the quota is enough; an invented source makes it `none` (`bad_source`); cancelling/editing a request after a synthesis is attributed per
    6.5; a scan turn's enqueue writes `team_events` and a system message; `record_contrib` does not revive a `void` row; routes only accept a team the
    agent participates in (or already has a row for); layer 3 reasons by `sort_by_priority`; the Pulse panel has B0..B7 cells and a revert button for policy changes.

## 7. Where parts J and L plug in

- `agent_pulse_host.register_view_part(name, fn(store, agent_key) -> dict)`: a section in `GET /agents/{slug}/pulse` (`parts`).
- `window.JavisPulseParts.push({name, render(view) -> html})`: a section on the Pulse panel (escapes itself).
- `agent_pulse_host.register_reason_handler(code, fn(host, reason))`: serves `reaction_review` (L), `related_review`,
  `wait_unblocked` (J). The function claims the reason itself with `WakeReasons.claim(reason_id, try_busy=..., release_busy=...)` using
  `host.busy_pair(agent_key)`.
- `agent_judge.judge_proactive(*, agent_key, context_ref, draft, source_event, engine)`: `engine` is a no-argument function returning the host's
  `(engine, model, run)` (built lazily). Returns a `Decision`; only `speak` sends.
- `agent_budget.try_spend(agent_key, purpose, at=None) -> (ok, reason)`: the host calls it with purpose `scan` before reserving a slot.
- `agent_pulse.register_policy_reverter(kind, fn(change))`, `apply_policy_change`, `record_policy_labels`,
  `revert_policy_change`, `observe_policy_changes` (6.4).
- `agent_pulse.wake(store, agent_key, context_ref, why)` for the related review turn and lifting waits; `agent_pulse.record_event(...)`
  writes a decision into `agent_pulse_events`.

## 8. Checks

Fake engines everywhere; no real model calls. (The working session could not write to `exports/reviews/`, so the evidence lives here.)

- `test_agent_pulse_policy.py` 100 checks, `test_agent_pulse_host.py` 66 checks (including blocking the real engine through `main.py`, routes,
  `POST /seen`, accepting/rejecting proposals), `test_pulse_contrib.py` 49 checks (including the objective check and rejecting proposals),
  `tests/js/test_agent_pulse_ui.js` 45 checks: all green.
- `tests/run.py pulse team resonance feedback agent_calls i18n icons route_table`: 88/89, the red one is `test_resonance_perf.py`
  (event loop lag 0.114 seconds > 0.1). Compared with `origin/claude/team-adaptive-t3` in a clean worktree: the base was 4/4 green, the branch 3/4 red,
  so it is a real bug of the branch: `GoalStore` was built inside the event loop on the first GET and `agent_pulse.ensure` wrote many times. Fixed in
  `865758bf` (a store that already has all its tables writes nothing; the first time it creates the tables in one transaction): 4/4 green. Rerun of `pulse feedback
  agent_calls team_adaptive rollback resonance_a1`: 20/20 green.
- `tests/run.py --js`: 193/193 green.
- UI inspection (a static frame using the real `console.css`, `style.css`, `agent-pulse.js`, i18n; served locally; 375x812): dark and
  light, vi and en, no horizontal scroll (scrollWidth 375), smallest text 16px, buttons and selects 44px tall. Not yet inspected on the real dashboard
  (sandbox port 7788) and not yet on a real phone.

## 9. Performance (fix after the T4 bench)

GOAL section 10: learning, saving schedules, searching or self-review must not make tabs lag. T1 convention R5: every SQLite and
file read/write in an async path runs in a worker thread (`run_io` / `asyncio.to_thread`). The T4 bench found two violations: the judge batch wrote to the store
right on the event loop, and the pulse tick took 0.5 to 3.4 seconds per tick, with loop lag up to 217 ms from the tick alone.

### 9.1 Moved off the event loop

- `io_offload.py` (new): `run_io` (moved from `team_runner`, the name `team_runner.run_io` is kept), `run_io_quiet` for the cleanup step in the
  cancel branch, `call_hook` (a plain hook function runs in a worker thread, a coroutine function runs on the loop), `LoopMarker` (an engine milestone that the
  engine calls synchronously is written in a worker thread, and the ledger row is settled only after it finishes).
- The judge: `judge_team_message`, `judge_proactive`, the private chat re-judge (`serve_reason`, `_rejudge_dm`,
  `_rejudge_with_call`), and wait expiry (`_expire_dm`) are split into SYNCHRONOUS `_..._prepare` / `_..._finish` parts that run through `run_io`;
  the coroutine only keeps the wait for the model. The judge store, `resonance_on` (`agent_any`), reserve/milestone/settle/refund of the turn ledger, wake reasons,
  history, quota, waits, and the plain sender (`_judge_send`) are all in a worker thread. Semantics unchanged: reserve BEFORE the engine, refund
  when the engine cannot be built or the wait for a slot timed out, `interrupted` when cancelled after the engine milestone. New: if cancelled right after reserving
  (during the prepare step, or while waiting for a slot in 2 batches) the ledger row is refunded (`_undo_reserve`, like the `undo` pattern of `run_io`);
  if cancelled right after claiming a reason, the reason is returned (`_undo_claim`).
- The pulse tick: `tick` checks the store in a worker thread and runs the plain `project_pending` function in a worker thread; `wake_step` gathers all the code parts
  (opportunities, estimate, counting reasons, releasing the schedule) into ONE thread hop (`_wake_code`); quota, `engine_for`, `persona`,
  `can_enqueue` and the last write of the scan turn run in a worker thread. `_learn_tick` reads the agent list in a worker thread; the reaction review turn
  and self-review (`agent_review`) read the store, quota, sources, events and release the busy lock in a worker thread. Lifting the wait when the owner messages a
  private chat (`_judge_dm_owner_message`) runs in the background in a worker thread, so the chat turn does not wait. `_reply_turn` reads the team through `_io`.
- `_pulse_busy`: before, every due agent rescanned ALL team jobs twice. Now `busy_snapshot` (a new dep of `PulseHostDeps`,
  `main._pulse_busy_snapshot`) reads the busy lock (`team_store.busy_keys`), running/queued team jobs and running goals ONCE
  per tick.

### 9.2 The projector: does it redo work

Checked: `project_pending` ONLY projects rows with `effect_state = 'pending'` (a private chat `pending_author` row goes through
`_dm_resolve_pending_authors` first and only then becomes `pending`); a `done` row is never projected again; writing the status back
only writes when the computed status differs from the current one. What repeated was READING: every 30 second tick, with up to 200 reactions in "Waiting for
review"/"Under review", it re-read each row (log row, reason source, current reaction: three SQLite connections per row). Now it reconciles
in batches (`_refresh_open`): one query reads the reactions (`open_reaction_rows`), one reads the log (`reaction_log_rows`), one reads the
sources (`WakeReasons.sources_by_ref`), and then it only writes reactions whose reason status changed. A store without a batch read function (the fake store of
old tests) takes the row by row path as before. The 200 rows per tick limit stays (it has existed since T2: beyond 200 open reactions the later rows are not
reconciled; batch reading makes raising this limit cheap later).

### 9.3 Measurements (T4 bench, fake engine)

Conditions: `tools/team_adaptive_bench.py` of branch `claude/team-adaptive-t4-work` (not committed to this branch), run outside the
repo through a wrapper that points `ROOT` at the code under test; default parameters (12 teams x 1,500 messages, 1,500 seeded reactions, 8 assistants, 30 calls per
API, 8 threads, 24 messages opening a judge batch, 5 ticks, 5 ms fake engine), `--no-ui`. Local Windows 11 machine, Python 3.12.10, 8 CPUs; NOT
VPS numbers. Base = the `server/` code of `origin/claude/team-adaptive-t3` (`92202224`), branch = `46b49f1f`. Two rounds ran base/branch interleaved
back to back on the same machine (the machine had background load from other sessions, so compare within the same round):

| Metric | Base v1 | Branch v1 | Base v2 | Branch v2 |
|---|---|---|---|---|
| One steady outbox projection (ms) | 788-837 | 13-16 | 1,408-2,069 | 12-13 |
| Pulse tick alone: time per tick (ms) | 3,198-6,093 | 237-3,197 | 6,011-8,230 | 321-2,718 |
| Pulse tick alone: max loop lag (ms) | 172 | 68 | 715 | 51 |
| Concurrent phase: max loop lag (ms) | 477 | 103 | 331 | 139 |
| Concurrent phase: request p95 (ms) | 1,572 | 822 | 1,454 | 966 |
| Judge batch wave alone: max loop lag (ms) | 36 | 116 | 40 | 53 |
| Requests only: max loop lag (ms) | 31 | 46 | 62 | 29 |

The first tick of each run is longer (it refreshes the `CONTEXT_REFRESH_S` scope for every agent). The `--stall-watch` diagnostic (captures the loop thread's
stack every time it is held more than 50 ms, one run per side): the base has 40 hits in the judge and turn ledger code (`add_decision`,
`get_decision`, `agent_any`, `_reserve`, `mark_engine`, `settle`, `cases`, `get_offset`); the branch has none left in the judge
or tick code. What remains is out of scope: `team_runner._reply_turn` and the lock release in `agent_review` (moved after the measurement, in the next
commit) and the route `POST /sessions/{id}/messages/{mid}/reaction` (writes the store on the loop, not fixed here). The remaining loop lag in the
concurrent phase (about 100 to 140 ms, one or two samples) has no stack in Jarvis 007 code: it is GIL contention between several worker threads running at once.
The judge batch wave alone fluctuates (once 116 ms) for the same reason. The number of fake judge batches in the concurrent phase is sometimes below 24 because the bench only
waits for the judge's background work, not for the `run_message` task the route spawns (a measurement window, not a lost turn).

Regression test: `tests/python/test_t3_event_loop.py` (the judge store and the resonance store slow at EVERY connection open by 110 ms and at the
main store function by 250 ms: a team batch with a self-initiated turn, a proactive message + wait + lift wait + re-judge + send in a private chat, the pulse tick with every
slow host function: loop gap < 100 ms and no store function runs on the loop thread; cancelling right after reserving refunds; the projector over two
ticks does not project again, does not write again, reads in batches). On the base code this test is red (4.1 seconds lag in the team batch, 2.8 seconds in the private chat).
