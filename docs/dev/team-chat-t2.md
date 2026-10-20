# Team chat group T2: six reactions and the feedback loop (0.120.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) section 14; cases TC28 to TC30, TC37 (reaction part). Stacked on T1 (PR #628).

## Flow

1. Hovering over an assistant's message shows a smiley button (always shown on touch devices); on a phone, pressing and holding the message for 0.5 seconds also opens the picker.
2. The picker opens right at the message: six emoji 👍 ❤️ 😂 😮 😢 😡, six quality reasons (multiple choice), a feedback box of up to 500 characters, and a reminder line "an emotion is not a score".
3. Pressing an emoji saves immediately; pressing the selected emoji again removes it; "Save feedback" saves the reasons and the feedback; "Remove feedback" clears everything.
4. The chosen emoji shows as a chip under the message (with the number of reasons, "has feedback"); pressing the chip changes or removes it.
5. The NEXT turn of that same assistant in that same team has a block "Recent feedback from the team owner" with a fixed instruction line.

## Code map

| Part | File | Job |
|---|---|---|
| Store | `server/team_store.py` | `team_reactions` (one row per reactor per message), `team_reaction_log` (append-only, `nonce` UNIQUE); `set_reaction`, `reaction_of`, `reactions_for`, `reaction_log`, `recent_feedback`; constants `REACTIONS`, `REACTION_EMOJI`, `REACTION_REASONS` |
| Runner | `server/team_runner.py` | `react` (only writes the store and pushes a WS packet), `_feedback_lines`, `FEEDBACK_NOTE`; the feedback block in `_context` |
| Route | `server/team_api.py` | `POST /teams/{id}/messages/{mid}/reaction {value, reasons, comment, nonce}`; the message page carries each message's `reaction` |
| UI | `dashboard/teams.js`, `console.css`, i18n | The `REACTIONS` table, `reactionPickerHtml`, `reactionChipHtml`, `nextReaction`; press and hold; the feedback draft survives a redraw |
| Convention | `tests/python/test_icons.py` | A reasoned exception for exactly six emoji in `teams.js`, with a check that all six remain and appear only in the `REACTIONS` table |

## Rules kept

- Exactly six values, stored as they are (`like`, `love`, `haha`, `wow`, `sad`, `angry`), plus `none` to remove the emoji. Reasons and feedback can exist without an emoji.
- Setting a reaction REPLACES that person's whole state on the message; the UI computes "press again to remove". A repeated `nonce` changes nothing.
- Stored with the reactor (`owner`), the message, the author agent, the team, the job, and the `content_sha` of the content at the time of the press.
- No model call, no turn opened, no agent woken, no change to a job, goal or queue (TC29, checked with the turn ledger and the queue version).
- The feedback block: at most 5 items, 30 days, newest first, only messages of that agent in that team; each item has an excerpt, the original emoji with its type name, the reasons, the feedback; removing the feedback takes it out of the block on the next turn (reads the current state).
- The A3 `reactions` table is not used.

## Rulings

- **Proposing lessons from feedback is left for a later milestone** (spec 14.4 item 4 allows it): T2 only puts the feedback into the context. A "Proposed lessons" mechanism needs a place to show it on the agent panel, an accept button and a remove button like A3; doing it at the same time would pull T2 onto the Partners page. Cost if wrong: if the owner wants feedback to become a durable lesson, they must say it in a 1:1 chat with the agent until this mechanism exists.
- The reactor is only `owner` (a one-account dashboard); the `reactor` column is ready.
- Reacting is allowed even in an archived team (it only records feedback, opens no turn).
- An archived team or a late-arriving message (applied=false) still receives feedback; the feedback block is read only by agent and team.

## Checks

| Command | Result |
|---|---|
| `tests/python/test_team_reactions.py` | 31 cases: TC28 (pick, change, remove, nonce, log, survives reopening the store, rejects bad input, only messages of the right agent in the right team), TC29 (no change to jobs, queue, no turn, no engine), TC30 (feedback block, instruction line, right team, right agent, removed means gone, at most 5, 30 days) |
| `tests/python/test_team_api.py` | 6 more cases for the reaction route (200, message page carries the reaction, 400, 404 for another brain, opens no turn) |
| `tests/js/test_teams_ui.js` | 22 more reaction UI cases |
| `tests/python/test_icons.py` | all six reactions remain, only in the `REACTIONS` table; no decorative emoji |

**UI smoke test** (sandbox on port 7788, state inside the worktree, team paused, daily turn cap 0; the assistant's message was inserted straight into the session store, no model call). Screenshots are in `exports/reviews/team-t2-smoke/`:
- desktop: picking 😢 shows a chip; it is still there after F5; adding the reason "Too long" and feedback; pressing 😢 again removes the emoji while the reason and feedback stay; switching to 😂;
- 375px: the smiley button is shown by default at 44x44; press and hold opens the picker; six buttons at 44x48; no horizontal scroll;
- the smoke test found and fixed: at 375px the row of six buttons overflowed the edge (😡 was cut off) because of a 6px gap and 10px padding; the text "1 reasons" was ungrammatical (changed to "Reasons: 1");
- the team's turn ledger after the smoke test: 0 turns.

## Final review (a fresh reviewer, strongest model)

Verdict "Ready with fixes": 1 Important, 6 Minor. Reordered by impact, all seven fixed:
- **Important:** the job detail (the job filter view) returned messages without feedback, so pressing an emoji there wiped the saved reasons and feedback. The route `GET /teams/{id}/tasks/{task}` now carries each message's `reaction`.
- Multi-line feedback broke the one-line-per-item format (a new item header could be faked): whitespace is collapsed.
- Feedback on a message that no longer exists still entered the block with an empty excerpt: now skipped.
- While composing feedback, a new incoming message lost the cursor and scrolled to the bottom: the cursor and scroll position are kept.
- Opening the picker did not move focus into the panel (Escape could not close it with the keyboard): focus goes to the first emoji, and on close it returns to the smiley button.
- A mouse press-and-hold also opened the picker and fought the touch long-press menu: now only touch and pen; the context menu of that hold is blocked; `-webkit-touch-callout: none` on touch devices.
- A nonce already used for another message returned 200 "saved": now refused (0.120.0 returned 400; from 0.154.0 it returns 409 to match the T2 contract); a nonce longer than 100 characters is refused.

The four server-side bugs have tests that were red first and then green (`test_team_reactions.py`, `test_team_api.py`). The three UI bugs are checked with source tests in `test_teams_ui.js` written after the fix (DOM behavior cannot run under node yet; not re-checked in a browser).

What the reviewer did not conclude: press and hold on real iOS Safari and Android Chrome; a screen reader reading the chip; `de.json` has no `teams.*` keys yet (falls back to English, present before T2).

---

## Team chat T2 (0.154.0), server side: reactions in two places, shared turn ledger, wake reasons, feedback projector

Original design: `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` sections 2, 3.1-3.5, 4.1-4.4, 9, 9.1, 12, 13. The contract
with the UI: `docs/dev/team-chat-t2-contract.md`. The UI part (reactions.js, app.js, teams.js, mobile-chat.js)
is done separately by the UI branch; this document covers only the server side.

### 1. What it does

- **Shared turn ledger and server ceiling (3.1, 9.1).** The `agent_calls` table in `resonance.sqlite3`. A single count
  `_ceiling_used(c)` = `SUM(goals.calls_used)` + `COUNT(call_ledger used)` + `COUNT(agent_calls counted = 1, not refunded)`.
  Obligation turns (goal A2, probe, goal planner, team turn) use the whole ceiling; spontaneous turns (`obligation = 0`) reach only
  `floor(ceiling * 0.8)`. The ceiling counts over the whole life of the store, not per day. A partial unique index
  `UNIQUE(reason_ref) WHERE status IN ('reserved','running','ok')`.
- **A team turn reserves before the engine.** `TeamRunner` has a `ceiling` dependency (`agent_ledger.TeamCeiling`). Right after reserving
  the `team_turns` slot, the turn holds one `counted = 1` row, `mirror_ref = team_turn:<id>`. Ceiling full: refund `team_turns`, outcome
  `{"status": "cap", "cap": "server_ceiling"}`, no engine call. A reply turn fails with the reason `server_ceiling`; a job step
  is blocked with `block_kind = server_ceiling` (the "Allow more turns" button cannot lift it). Every refund/mark/settle path (`busy_long`,
  failure before the engine, cancel, timeout, T1's pre-engine `lease_lost`, recovery) goes through `_refund_if_unmarked`,
  `_mark_engine`, `_settle_turn`, so the ledger row settles with it. A shared store error at mark/settle time does not break the team turn.
- **Reconciliation** (`TeamCeiling.reconcile`): at startup (the end of `TeamRunner.recover`) and every 60 seconds (the loop of
  `TeamApi.tick`). A `team_turn:*` row follows only the state of the team turn itself (refunded or gone means refund, settled means
  settle with it, still `reserved`/`running` means leave it), never by age. Rows and turns newer than 120 seconds are skipped.
  A team turn that reached the engine mark but lacks a ledger row gets a counted row rebuilt. The 10-minute rule applies only to rows with `mirror_ref = ''`.
- **Wake reasons per agent (3.2-3.4).** `agent_wake_reasons` and `agent_wake_sources` with a full lifecycle (pending, claimed,
  served, superseded, failed). The API is in `agent_ledger.WakeReasons`: `add_source`, `remove_source`, `remove_group`, `claim`
  (tries the busy lock first, and being busy costs no attempt; CAS and the turn ledger reservation in one transaction), `settle`, `retry_failed`.
  Only T3 serves reasons; T2 creates them and has lifecycle tests.
- **Feedback projector (3.5)** `server/feedback_projector.py`: idempotent by `source_ref`, projects in log order,
  net state, old rows `superseded`. It runs right after a write (errors swallowed and logged), on every scheduler beat and at
  startup (`_feedback_pulse_tick` in main.py). Routing: a message tied to a goal goes only to the A2 `feedback` reason; other messages go to the
  `reaction_review` reason at `team:<id>` or `dm:<agent_key>`; only when the agent has Resonance on and the event is after `resumed_at`.
  Resonance off: `stored_only`. Main Chat page: `received`. The reaction status is written back by reason.
  The hook left empty for T3: `FeedbackProjector.record_pulse_signal`.
- **`resumed_at`.** The `agent_pulse` table (all columns of section 5.4). The mark is written in `GoalStore.agent_set_enabled` in the same transaction
  as the switch, so both the owner's route and the leader's `set_resonance` command get the mark. Upgrade: an agent already on gets
  `resumed_at = upgrade time`.
- **Private chat reactions (4.1, contract section 4).** `dm_reactions`, `dm_reaction_log` in `conversations.db`. Route
  `POST /sessions/{session_id}/messages/{message_id}/reaction`. `GET /sessions/{id}/messages` and `GET /sessions/{id}` have
  `content_sha` on every message and `reaction` on `assistant` messages. WS packet `chat_reaction` after every write and every time the host changes
  the status. `_persist_turn` returns the message id and pushes `turn_saved` right after saving (every calling path: dashboard, Telegram, voice,
  workflow).
- **Extended team reactions (4.1, contract section 5).** New columns for `team_reactions`/`team_reaction_log` (idempotent ALTER, with
  defaults). Resending the same nonce returns the current state; a nonce of another message: 409. The agent `react` command in a team turn
  (every role, at most 5 per turn, nonce `<turn_id>#rx<i>`): the host assigns `leader`/`member` and does not allow reacting to the agent's own message.
  Messages carry `agent_reactions` and `content_sha`.
- **Effect (4.3).** An emoji does not settle a result, does not change priority, grants nothing, does not change job or goal state (tested for private
  chat too). The feedback block goes into the next turn in the right context: team (`_feedback_lines`, with the speak/stay-quiet axis added) and private chat
  (`_agent_turn_system_prompt` adds `feedback_projector.dm_feedback_block`, only for that agent).

### 2. Where

| File | Content |
|---|---|
| `server/agent_ledger.py` (new) | `CallLedger`, `TeamCeiling`, `WakeReasons` |
| `server/feedback_projector.py` (new) | feedback projector, the private chat feedback block |
| `server/reaction_values.py` (new) | the six values, reasons, axis, input checks, the R shape |
| `server/resonance_store.py` | `_ceiling_used`, `ceiling_limit`, T2 tables, `resumed_at`, `agent_any`, A2 supersede |
| `server/team_store.py` | new reaction columns, `set_reaction_ex`, outbox, `NonceConflict`, `turns_since` |
| `server/team_runner.py` | `ceiling`/`projector` dependencies, the `react` command, `server_ceiling`, teammate feedback |
| `server/team_api.py` | wiring the dependencies, the reconcile beat, the reaction route (axis, seen_sha, 409) |
| `server/sessions.py` | `dm_reactions`, `dm_reaction_log`, `content_sha` on messages |
| `server/main.py` | the private chat reaction route, `turn_saved`, the feedback block, the projector beat, wiring the ceiling |
| `dashboard/i18n/{vi,en}.json` | `teams.reply.why.server_ceiling`, `teams.block.server_ceiling` |

### 3. Migration

- `resonance.sqlite3`: snapshot `resonance.sqlite3.pre-0.154.0` the first time (no `agent_calls` yet), then create the new tables. Old
  tables are unchanged.
- `team.sqlite3`: snapshot `team.sqlite3.pre-0.154.0` the first time (no `axis` column yet), then ALTER to add columns with defaults. Old log
  rows get `effect_state = 'done'` (no effect backfill).
- `conversations.db`: snapshot `conversations.db.pre-0.154.0` the first time (no `dm_reactions` yet), then create the two new tables.

### 4. Rolling back

Version 0.153.x ignores the new tables and columns, so a downgrade runs without a restore. The leader's/members' reactions
(reactor `agent:...`) will show as ordinary reactions in the old version (a known effect, no data lost). To restore fully:
use the tool in the section below, do not copy by hand (a raw copy of the `.sqlite3` file misses what is still in the WAL and has no way back).

#### Restore to before 0.154.0

**Usually no restore is needed.** Every 0.154.0 migration only ADDS (new tables, new columns with defaults), so running 0.152.0
or 0.153.0 again over an upgraded store still works: the old version ignores the new tables, does not see the new reaction status, and an agent's reactions
(`reactor` of the form `agent:...`) show as ordinary reactions. Use the tool below only when you want the stores back in EXACTLY the state before
the upgrade (every message and change after that point is lost).

The internal tool `tools/team_adaptive_restore_pre.py` (not in the CHANGELOG). Run it when Jarvis 007 is FULLY OFF:

```
python tools/team_adaptive_restore_pre.py --to 0.154.0 --state-dir /path/to/state          # only prints the plan
python tools/team_adaptive_restore_pre.py --to 0.154.0 --state-dir /path/to/state --yes    # real restore
```

Without `--state-dir` it uses `JAVIS_STATE_DIR`. On a VPS, stop the container first, run the tool on the state folder, then
run the old version.

- Back to the `.pre-0.154.0` snapshots: `team.sqlite3`, `conversations.db`, `resonance.sqlite3`. If it already went up to 0.156.0, then
  `agent_judge.sqlite3` (T3, did not exist before) is copied aside and removed, and `resonance.sqlite3.pre-0.156.0` is renamed to
  `.superseded-<timestamp>` (kept; the next upgrade takes a new snapshot on the right timeline).
- Lost from the running store: every change to the three stores after the upgrade: chat messages and sessions (private chat and team), reactions in both places
  (agent reactions included), teams and the team turn ledger, Resonance goals, the shared turn ledger, wake reasons, agent pulse.
- Kept: a copy `<store>.post-0.154.0-<timestamp>` next to each store file touched (read it back with sqlite3 when you need to compare), and
  the `.pre-0.154.0` snapshot (upgrading again reuses exactly this copy and does not overwrite it).
- `kanban.sqlite3` is NOT changed (this milestone does not snapshot it): team jobs created after the upgrade remain in Kanban even though the team or its messages
  went back to the earlier version.
- Safety: the whole set is checked before writing (a missing snapshot for an upgraded store, a broken snapshot, or one already carrying the T2 marker stops it, with nothing
  written); it re-checks after writing; if a step fails it returns EVERY store already touched to its `.post-*` copy and reports an error, and never reports success
  for a half restore. A file that is held open (Jarvis 007 not off) is reported clearly with a hint to turn it fully off.
- The "already upgraded" markers the tool uses: the column `team_reactions.source_kind`, the table `dm_reactions`, the table `agent_calls`
  (`test_team_adaptive_restore.py` checks they match the code). A store created fresh from 0.154.0 (no snapshot) has no earlier version to go
  back to: the tool stops and says so.
- `--to 0.156.0` (T3) is already in the tool's `MILESTONES` table: it removes `agent_judge.sqlite3` and goes back to
  `resonance.sqlite3.pre-0.156.0` if present. T3 fills in that snapshot's marker table when it settles.

### 5. Decisions made along the way

1. **The emoji code is `love`, not `heart`.** Design 4.1 says `heart`; the contract keeps `love` so old data stays readable. Following the contract.
2. **A nonce of another message in a team returns 409** (0.120.0 chose 400, see the section above) to match T2 contract section 4 and private chat; `test_team_api.py` was updated accordingly.
3. **No mirror row `goal_call:<id>` (`counted = 0`) yet for A2 turns.** They are only for observation; A2 behavior does not change.
   T3 adds them when `agent_daily_calls` needs them.
4. **Reconciliation per the coordinator's design fix (d408d89a):** team rows follow only the team turn's state, a 120-second grace,
   the 10-minute rule only for `mirror_ref = ''`. The first version of this branch had an age-based refund at startup; removed.
5. **Shared store failing at reserve time:** if a ceiling is set, refund the team turn and report an `internal` error (does not run when the ceiling cannot be checked);
   if no ceiling is set, carry on, and reconciliation rebuilds the counted row when the turn reaches the engine mark.
6. **Private chat author:** the route issues a durable id for the assistant (`agent_register`, Resonance stays off) and pins the session
   (`session_agent`), as team chat issues ids to members. If it cannot be looked up, `agent_key` is empty.
7. **A message tied to a finished goal:** creates no reason, status `no_change` "Goal already finished".
8. **A served A2 reason:** status `no_change` with "The goal read the feedback in its next job turn" (A2 does not report a
   result per piece of feedback). A served and consumed layer-3 reason: `no_change` by default; T3 writes a real `adjusted`/`no_change` and
   the projector does not overwrite it.
9. **`revision`** of R is the number of log rows of the pair (message, reactor).
10. **An agent's reaction in the author's next turn** becomes its own block "Teammate feedback"; the block "Recent feedback
    from the team owner" now takes only the owner's reactions.
11. **`agent_wake_sources.group_ref`** (a column added beyond the design) to remove sources by the pair (message, reactor).
12. **A reason's `attempt` increases at claim time;** a refunded turn costs no attempt; at 3 failures it becomes `failed`.
13. **`waiting_quota`** is not written in T2 yet (it belongs to T3's review turn).
14. **`content_sha`** is added to every message dict of the session store (`_tin`, `_team_msg`).
15. The sentence `FIXED_LIMITS["server_call_ceiling"]` changed to "Auto goals and team turns".
16. **Upgrading does not count team history toward the ceiling** (review T2 P1, owner's decision): the mark `ceiling_state.t2_migrated_at` is written once when the tables are created; reconciliation
    builds rows only for turns created after the mark (minus 120 seconds) or still open at upgrade time. It scans by a durable cursor
    `ceiling_cursor` `(created_at, turn_id)`, at most 2000 rows per pass, plus a small group of still-open and just-settled turns.
17. **Changing/removing a reaction while the reason is running** (P2-1): the source of a `claimed` reason also gets `removed_at`, so it is not
    carried into the next pending reason.
18. **Every path that turns on Resonance writes `resumed_at`**, including A5's reviewer-enable path (P2-3).
19. **The private chat route** checks the body, the message and a resent nonce BEFORE looking up the author; if the resonance store fails during lookup the reaction is still saved
    (`effect_state = 'pending_author'`, status Received with a reason) and the feedback beat looks it up again and then projects. The projector locks per pair
    (message, reactor) in-process so a request and the beat do not project interleaved.
20. **Goal report messages keep only the six emoji** (owner's decision 2026-10-15): A3's Helpful / Not good row is no longer drawn (flag
    `A3_REACT_ROW = false` in `chat-resonance.js`); an emotion on a goal report message wakes the goal through A2's `feedback` reason. A3's API and
    store are unchanged, and old data is still readable. The private chat reaction route does not check `brain` (like `GET /sessions/{id}`): the session is the key.

### 6. Still open

- `tools/team_adaptive_restore_pre.py --to 0.154.0` exists (section 4). `team_chat_restore_pre.py` still handles only `.pre-0.140.0`.
- When merging T1 `d408d89a`: both sides added keys to `_REPLY_REASON` (`lease_lost`, `server_ceiling`); merge both. T1's pre-engine
  `lease_lost` path calls `_refund_if_unmarked`, so the ledger row refunds itself (this branch's test checks exactly that function).

### Evidence

Full version: `exports/reviews/team-adaptive/t2-be-evidence.txt` (outside the repo). Summary, fake engine, no real model:

- `test_agent_calls_ledger.py` 67 checks, `test_feedback_projector.py` 23, `test_feedback_wake.py` 22, `test_dm_reactions.py`
  49, `test_team_reactions.py` 55 (extended), `test_team_api.py` 83: all green.
- The filter `team route_table i18n resonance dm_reactions feedback agent_calls sessions`: 85/86, the only red one (a source canary
  of `test_resonance_a1_transport`) was fixed and is green in the full run.
- The whole suite (Python and JS): 698/712. All 14 reds are identically red on `origin/claude/team-adaptive-t2` (46ae9471) in a clean
  worktree (same exit code, same FAIL count): antigravity, grok, Windows install, home-machine ollama, terminal, light startup, machine translation...
  `test_link_file_uri` differs in FAIL count only because of the drive (temp folder on C:, worktree on D:); with TEMP on the same drive it is identical to the original.
