# Unified supplementary design: reactions, adaptive heartbeat, per-agent arbitration, learning inside the team (T2-T4)

Date: 2026-10-15. Base: `main` `1d1b52fa` (0.151.0). Original order: `exports/reviews/GOAL-TEAM-CHAT-T1-T4-COMPLETE.md` (review
version 2). Survey of the current state: four recon reports (T1, reaction, heartbeat, arbitration) are summarized in section 1. T1 proceeds in parallel under the approved
team chat design (`2026-10-13-team-chat-design.md`) and does not depend on this document.

**Version 2** (fixed after independent review round 1, see section 15). This document is **one** design for the whole supplementary scope, so it can be reviewed once. Every number in this document is a **versioned
initial parameter**, not a research conclusion; they are checked with fake-clock tests and may be tuned only with evidence.

## 0. Changes from the old documents (stated openly, not silently)

| Old document | Says | Now changed to | Why |
|---|---|---|---|
| Resonance spec 06/10 (`2026-10-06-javis-resonance-design.md`:251,261), roadmap 08/10 | Frequency is not tied to praise/criticism scores | The agent's PROACTIVE rhythm (layer 3) changes with a bounded usefulness estimate, confidence and return rate; the accountability schedule (goal A2, deadlines, Kanban, reminders) does **not** change with the score | GOAL 7.2, 7.3 |
| A3 (`docs/dev/resonance-a3-learning.md` "Things that never happen") | A reaction creates no wake reason and changes no schedule | A valid reaction on a Resonance-enabled agent creates **one** review reason grouped by (agent, context) and is an input to the usefulness estimate. A reaction on an agent with Resonance off is still only stored and shown | GOAL 6.2, 7.3 |
| A3 lane P | A lesson proposal is presented, and applies only after the owner approves | When Resonance is on, adjustments within the **granted self-learning scope** (speak/stay quiet, rhythm, team-scope lessons) apply on their own with before/after, observation and automatic rollback; changes to permissions, the owner's rules, or scope beyond the grant still wait for the owner | GOAL 8.2 |
| Team chat T1 (spec 13/10 :252, TC8) | An agent's message wakes no one | A teammate's or team leader's message opens a **related review turn** only through a structured event (job relation, input_refs, the `ask_peer` command), with a depth ceiling and loop protection; an `@` in text, quotes and fake tags still open nothing | GOAL 8.1 |
| Team chat T1 | A `JAVIS_LESSON` lesson is written into the agent's shared memory | A lesson inside the team is written into a lesson store with **team scope**, with a source, history and revocation; it is promoted to the general scope only through a self-review with evidence from several contexts, or owner approval | GOAL 7.5, 8.2 |
| Private chat today | A model-proposed `JAVIS_LESSON` is written to `MEMORY.md` (goes into every context) | Write the lesson with scope `dm:<agent_key>`; only the owner's rules and promoted lessons go into every context | GOAL 7.5 |
| Zalo arbitration | Two conclusions, speak/stay quiet; no turn ledger | Three conclusions, speak/wait/stay quiet (wait has a release condition); every arbitration and self-review turn goes into the shared turn ledger | GOAL 8.1, 8.3 |
| Emoji test (`tests/python/test_icons.py`) | The six emoji may live only in `teams.js` | The six emoji may live only in **one** shared table `dashboard/reactions.js`; everywhere else is still forbidden | GOAL 6.1 |

## 1. Current-state summary (evidence is in the recon files in the review package)

- **Team chat:** T0-T5 and 0.146.0 are released. R1-R9 pass on head (reviewer script, fake-engine adapted version). Missing: a per-turn permission
  checkpoint (old turns enjoy re-granted permissions), busy lease / jobs not extended during a long turn, a `running_jobs` cap > 1 has no
  effect, the limits table is incomplete. These items belong to T1 (separate PR).
- **Reaction:** the six reactions exist in team chat (stored, reason, feedback, nonce dedup, multiple tabs) but wake **no one**, only the
  owner may add them, the log lacks agent/job/previous value, and there is no status. Private chat: no reactions on an agent's replies;
  only A3's Helpful/Not quite pair on goal notices. Chat bubbles do not yet carry a message id.
- **Heartbeat:** layer 1 (lease) and layer 2 (A2 per goal) exist. Layer 3 (per agent) **does not exist**. There is no "seen" event. The turn ledger
  is scattered across five places.
- **Arbitration:** the Zalo arbiter separates "was called" from "should speak", has per-case learning, self-review with before/after and automatic
  rollback, but it is tightly bound to bot/channel, has only two conclusions, no turn ledger, and its case store pulls across every chat (a context leak if used as-is for
  an agent in many teams).
- **Learning:** an agent's lessons mix every context, with no source and no revocation; teammates have no feedback channel.

## 2. Shared concepts

- **Agent:** a durable identity `agent_key` issued by the host (`resonance_agents`). Every new table is keyed by `agent_key`, not by slug; the UI's API
  accepts a slug but the host converts it to the active `agent_key` before reading/writing (a slug can be reused).
- **Context (`context_ref`):** `team:<team_id>` or `dm:<agent_key>` (the owner's whole private chat with that agent, every session of channel
  `agent:<slug>` merged; the privacy boundary is private chat versus team, and the session id is used only in message references). The per-agent aggregate
  uses `context_ref = "*"` (for display and initialization only). Never put one context's content into another context's prompt.
- **Replies on the main Chat page** (no agent, the author is Jarvis 007): the six reactions are available for storing and display (`agent_key`
  empty); they do not enter any agent's usefulness estimate or arbitration.
- **Source event:** every effect points back to a single `source_ref` (`rx:dm:<log_id>`, `rx:team:<log_id>`, `decision:<id>`,
  `step:<id>`, `seen:<context>:<message_id>`). Each kind of effect has a unique index on `source_ref`.
- **Which store holds what (no cross-store transactions):**

| Store | New tables / new columns |
|---|---|
| `conversations.db` (private chat messages) | `dm_reactions`, `dm_reaction_log` |
| `team.sqlite3` | new columns of `team_reactions`, `team_reaction_log` (section 4.1) |
| `resonance.sqlite3` | `agent_calls`, `agent_wake_reasons`, `agent_wake_sources`, `agent_pulse`, `agent_pulse_events`, `pulse_signals`, `pulse_contrib`, `message_seen`, `pulse_opportunities` (key `(agent_key, context_ref, source_ref, version)` of consumed opportunities), `agent_lessons`, `agent_lesson_events`, `agent_peer_feedback` |
| `agent_judge.sqlite3` (new, internal data, separate from the Zalo customer arbitration store) | `profiles`, `decisions`, `offsets`, `cases`, `waits`, `changes`, `review_state` |

- **Resonance (per-agent switch) and scope:**

| Capability | Resonance off | Resonance on |
|---|---|---|
| Answer a direct call, do assigned work, team jobs | Yes | Yes |
| Speak/wait/stay-quiet arbitration when joining a team (existing policy, frozen) | Yes | Yes |
| Store and display reactions | Yes | Yes |
| Review reason from reactions, labels that teach arbitration shifting its threshold, self-review, self-applied lessons | No (labels only stored) | Yes |
| Adaptive heartbeat: proactive rhythm, sleep, finding work on its own, follow-up nudges in private chat | No | Yes |

  **Turning back on:** the host writes `resumed_at = now` into `agent_pulse` for every context of the agent. Every trigger counter (review reasons, self-review,
  label count, new signal count) counts only events **after** `resumed_at`; feedback before that point is only evidence/context, it creates no
  make-up turn and does not reset the budget. The path of turning it on through a team leader command (Full access) also writes `resumed_at` and calls `wake_agent_goals`
  the same way the owner's path does.

## 3. Shared turn ledger, reason lifecycle, per-agent lock

### 3.1 `agent_calls` (resonance.sqlite3)

`id, agent_key, brain_id, context_ref, purpose (reply|step|judge_batch|review|proactive|scan|reaction_review|goal), reason_ref,
attempt, engine, model, status (reserved|running|ok|error|refunded|interrupted), counted (0|1), obligation (0|1), tokens_in,
tokens_out, cost_usd, mirror_ref, created_at, settled_at`. A **partial** unique index: `UNIQUE(reason_ref) WHERE status IN
('reserved','running','ok')`. A reason has at most one turn running or finished successfully; a `refunded`/`interrupted`/`error` turn
holds no lock, so it can be retried (attempt + 1).

- **A single ledger for the shared ceiling** (fixed after the T1 review, see 9.1): every turn within the ceiling's scope is **reserved in this ledger BEFORE
  calling the engine**, in the same `BEGIN IMMEDIATE` transaction as the count, so the ceiling check and the reservation are atomic even when many turns (many threads,
  many processes on the same store) run at once. The `counted` column says whether the row adds to the ceiling, replacing the old rule "`mirror_ref = ''`".
- Team turns (replies, job steps): `team_turns` keeps the team's daily ceiling as today, **and** reserves a row with `counted = 1`,
  `mirror_ref = team_turn:<id>` in this ledger right after reserving `team_turns`, before the busy lock and before the engine. If the shared ceiling is full, refund the
  `team_turns` row just reserved and the turn ends with outcome `cap` with `cap = "server_ceiling"` (the engine is not called). A team turn that is refunded (error before the
  engine call, wait timeout, cancel) also has its ledger row `refunded`; settling `ok`/`error`/`interrupted` settles the ledger row to match.
- Goal A2 turns and the goal planner are already counted in `goals.calls_used` and `call_ledger` (A2 behavior unchanged): their mirror in
  this ledger carries `counted = 0`, `mirror_ref = goal_call:<id>` (only for observation and so `agent_daily_calls` knows which turns ran).
- Turns that exist only in the new ledger (batch arbitration, review, proactive, scan, reaction review) carry `counted = 1`, `mirror_ref = ''`.
### 3.2 Wake-reason lifecycle per agent (`agent_wake_reasons`)

`id, agent_key, context_ref, code (reaction_review|related_review|proactive_due|scan_due|wait_unblocked), status (pending|claimed|
served|superseded|failed), attempt, ledger_ref, created_at, updated_at`; sources are in `agent_wake_sources(reason_id, source_ref UNIQUE,
added_at, removed_at, consumed_at)`. Unique index `(agent_key, context_ref, code) WHERE status = 'pending'`: at most one **waiting** reason
per kind per context, with new sources merged into it; a new `pending` reason may coexist with one that is `claimed`. A source arriving
while a review turn is running goes into the new `pending` reason, not the running one.

`pending -> claimed` (CAS, reserve `agent_calls`; the source list is fixed at claim time) `-> served` only when the turn settles `ok`. At `served`,
any source **not** in the turn's `consumed` is moved to a `pending` reason of the same kind (created if none exists); test: a reaction arriving
while a review turn is running is reviewed exactly once in the next turn. A turn that ends `interrupted/refunded/error`: if a `pending` reason
of the same kind already exists (created while running), move the running reason's sources to that waiting reason, keep the larger `attempt`, mark the running
reason `superseded` (test "error when a newer waiting reason already exists"); if not, `-> pending`
(attempt + 1), more than 3 times -> `failed` (shown, the owner clicks retry). A removed source (reaction taken back) while the reason is still `pending`:
mark `removed_at`; a reason left with no sources -> `superseded`.

### 3.3 Standard routing when an event belongs to several layers

- A reaction on a message that has a `goal_id` (a goal notice, or a private-chat message tied to a goal): creates only a goal `feedback` reason at **A2**
  (the existing `wake_reasons`, `source_ref = rx:...`); layer 3 only records a usefulness **signal**, creating no reason of its own.
- A reaction on a message with no goal: layer 3 creates a `reaction_review` reason.
- `effective_due` (section 5.1) skips an agent that has an A2 turn or team turn running (busy lock, 3.4) and postpones 60 seconds.

### 3.4 Shared per-agent busy lock

The existing `agent_busy` lock (team_store, with the extension from T1) becomes the lock for **every** turn carrying the agent's persona: team turns, proactive,
reaction review, work scan, and goal A2 turns. An A2 turn that meets the busy lock postpones 30 seconds (not counted as an error). Batch arbitration turns do not
carry a persona, so they take no lock. Proactive/scan/review turns try the lock **without waiting before** claiming the reason (CAS) and reserving the turn ledger;
if busy they do not claim, the reason stays `pending`, and `attempt` does not increase. Proactive/scan/review turns also skip this round if the agent has queued team work or
goals; the longest a turn can take (10 minutes) fits within one lease period (15 minutes). Test: team work queued while a scan is running starts
after at most one scan turn.

### 3.5 Outbox: write the reaction, then project the effect (no cross-store transaction)

Write the reaction (the reaction's store) with `effect_state = 'pending'` on the log row. The projector `feedback_projector.project(log_row)` is
idempotent by `source_ref` (UNIQUE in `agent_wake_sources`, UNIQUE `(source_ref, agent_key)` in `pulse_signals`): create/merge the reason, write the signal, then set `effect_state =
'done'` and `effect_refs_json`. The projector runs right after the write (same request, skipped on error) and reruns on every pulse tick and at
startup for every row still `pending`. Order: each (message, reactor) pair is projected **in exact log-id order**; a `pending` row that already has a newer row for the same pair applies only the **net state** of the newest row and marks the older rows `superseded`. The status
shown on the old reaction is also written back by the projector after the reason changes state.

## 4. T2: six reactions in private chat and team chat

### 4.1 Data

- `dm_reactions` (conversations.db): `session_id, message_id, reactor, source_kind (owner|leader|member), agent_key,
  agent_config_version, value (like|heart|haha|wow|sad|angry|NULL), reasons_json, axis (should_speak|should_silent|''), comment,
  content_sha, seen_sha, stale, goal_id, revision, status, status_reason, updated_at, PRIMARY KEY(session_id, message_id, reactor)`;
  `dm_reaction_log(id, session_id, message_id, reactor, prev_json, next_json, nonce UNIQUE, effect_state, effect_refs_json,
  created_at)`.
- Team: `ALTER TABLE team_reactions ADD` `source_kind TEXT NOT NULL DEFAULT 'owner'`, `axis TEXT NOT NULL DEFAULT ''`, `status TEXT
  NOT NULL DEFAULT 'received'`, `status_reason TEXT NOT NULL DEFAULT ''`, `seen_sha TEXT`, `stale INTEGER NOT NULL DEFAULT 0`;
  `team_reaction_log ADD` `agent_key`, `task_id`, `prev_json`, `effect_state TEXT NOT NULL DEFAULT 'done'`, `effect_refs_json`. Old
  rows count as already projected (no backfill of effects). All new columns have defaults, so the old build still runs on an upgraded store.
- `content_sha` is computed on the stored content (after removing control blocks). `seen_sha` is sent by the client; a mismatch sets `stale = 1`, and it is still accepted.
- The source is assigned by the host: `owner` through the dashboard route; `leader`/`member` only through a structured command in the agent's turn
  (`{"op":"react","message_id":..,"value":..}`), and the host takes the identity from the turn; an agent cannot react to its own message. An agent's reaction
  does not enter the usefulness estimate (against self-rewarding), it is only collaboration feedback.
- Dedup: the client generates a `nonce` once per action and **reuses** it when retrying after a network error.

### 4.2 UI

- The six-emoji table, `nextReaction`, chips, the picker and long-press move into `dashboard/reactions.js` (the repo's only six-emoji table;
  `test_icons` moves its exception scope to this file). `teams.js`, `app.js` (reply bubbles, stream bubbles after they settle, history)
  and `mobile-chat.js` share it.
- A bubble carries `data-mid`: history takes `m.id`; a new turn gets `message_id` through the `turn_saved` packet emitted after `_persist_turn` (the function returns the message
  id). With no id there is no reaction button.
- Two separate chip groups: the six quality reasons (T2) and the axis "Should have spoken" / "Should stay quiet (interrupted)"; optional free-text feedback; nothing is
  required to add an emoji.
- Multiple tabs: the WS packets `chat_reaction` (private chat) and `team_message` (already exists); the frame filtered by a team job also receives the packet.
- Status under the chip, set by the host: Received; Waiting for review; Under review; Adjusted; No change needed; Waiting for quota (each status has a
  short reason). An agent with Resonance off (or feedback that predates turning it back on): "Received, stored only" with the reason that fits the case.
- Phone: the button is always visible, touch target 44px, text 16px.

### 4.3 Effect

- Routing follows 3.3, written through outbox 3.5, only when the agent has Resonance on and the event is after `resumed_at`.
- Change/remove: before/after log; the source in a still-waiting reason is removed; an already-written signal moves to `superseded_by` (section 6.3).
- An emoji does not close a job as accepted, change priority, grant permission, or change job/goal status (test for private chat too).
- A feedback block (like `_feedback_lines` in T2, with the note "an emoji is a feeling") goes into the agent's next turn in **exactly that context**; private
  chat adds this block to the prompt of the `agent:<slug>` turn.

### 4.4 Reaction review turn (the real processor, T3; T2 only creates the reason)

When a `reaction_review` reason is served: the host builds a prompt containing the message that got feedback, the reactions/reasons/comments in the reason's sources,
and a structured output requirement:

`{"outcome": "keep"|"ask_back"|"revise"|"lesson", "message": "...", "lesson": {"text": "...", "kind": "presentation"|"method"},
"consumed": ["rx:..."], "reason": "..."}`

- `keep`: send nothing. `ask_back`: send **one new message** asking back, replying to the message that got feedback. `revise`: send one new message that is the correction (the old
  message is not overwritten), only within the context's allowed scope (private chat; in a team it goes through arbitration like any spontaneous message). `lesson`: write a lesson
  with context scope (section 8), which may come with `keep`.
- The host checks `consumed ⊆ the reason's sources`; a wrong structure or a mismatched `consumed`: the turn is `error`, the reason goes back to `pending` (3.2).
- Status follows the **real host result**: `keep` -> "No change needed"; `lesson` -> "Adjusted"; `ask_back`/`revise` -> "Adjusted"
  only when the new message was really sent; if arbitration (in a team) chose to stay quiet, then "No change needed (arbitration chose to stay quiet)". Written on every reaction in
  `consumed`.
- Evidence of effect: the decision is written to `agent_pulse_events`; the new lesson appears in the next turn's prompt in exactly that context (the test
  checks that the next prompt contains the lesson and the source id).

## 5. T3: adaptive heartbeat (layer 3)

### 5.1 One place decides the schedule, running outside the goal tick

A pure module `server/agent_pulse.py` (policy `pulse.v1`). A **separate** 30-second rhythm coroutine in `_scheduler_loop` (its own busy flag, not inside
`_resonance_tick`), doing only fast code work: project the outbox rows still waiting, find `agent_pulse.next_due_at <= now`
and `pending` reasons, claim the schedule by CAS, then **spawn** the turn that needs a model as its own task (reserving the turn ledger first). `effective_due(agent,
context)` merges the proactive schedule and the layer 3 waiting reasons; it does not touch the goal's `wake_reasons`. The accountability schedule (goals, deadlines,
Kanban, reminders) runs by its own source and is not slowed by layer 3.

### 5.2 State (per agent x context)

Tier ladder: `B0 15 minutes, B1 1 hour, B2 4 hours, B3 1 day, B4 3 days, B5 1 week, B6 2 weeks, B7 1 month`, above B7 is hibernation (no
proactive schedule). The initial tier is B3.

| State | Meaning | Enter when | Leave when |
|---|---|---|---|
| `active` | tiers B0-B2 | moving up to B2 | dropping below B2 |
| `awake` | tiers B3-B4 | default, or waking again | tier change |
| `slowed` | tiers B5-B7 | dropping to B5 | moving up |
| `hibernating` | after B7 | staying at B7 for two periods in a row with no signal and no opportunity | a wake event |
| `waiting_owner` | waiting for the owner | arbitration/job needs the owner's decision | the owner answers/cancels; remind once after 24 hours then leave as is |
| `paused` | owner paused | the owner clicks Pause | the owner clicks Continue |
| `off` | Resonance off | turned off (and every agent that is off at upgrade time) | turned on: back to tier B3, keep the old estimate, write `resumed_at` |

`paused`, `waiting_owner`, `off`, `hibernating` stop only the **proactive** part; accepted work, deadlines, goals and direct calls still run.
**Waking again:** the new tier = `min(current tier, B3)` (if already faster than B3 keep it), keeping the estimate, memory and history as they are; triggered by
the owner messaging/calling the agent directly in the context, a new job assignment, a new valid reaction, a structured related event (7.5).

### 5.3 Rhythm adjustment (only on new evidence, with delay)

Each **evaluation period** (when the proactive schedule is due or when a reason is served), in order:

1. `new = Σ w·decay` of signals **after** `last_change_at` and after `resumed_at`. Do not change tier if it has not stayed at the current tier for the **minimum
   time** `dwell = max(2 × the tier's interval, 1 day)`.
2. Move up one tier if `u ≥ +0.25` **and** `new ≥ 1.0`, not beyond the granted `max_tier` (default B1, the owner may grant B0; Full access cannot
   raise this ceiling).
3. Move down one tier if `u ≤ -0.25` and `new ≥ 1.0` (reason `unhelpful`).
4. Move down one tier if there is no new signal and no opportunity (reason `low_demand`, not recorded as the agent being wrong) within two of the current
   intervals.
5. Otherwise hold.
6. Hysteresis: a change of direction only after at least one period of holding.

Old evidence cannot keep pushing the tier by itself: steps 2-3 need new evidence; step 4 slows the rhythm when things stay quiet.
Added while building T3 (an accepted deviation, see section 15): step 4 also moves down a tier (`low_demand`) when the latest interaction signal and the
latest opportunity are both older than `max(4 x interval, 3 days)`, so a reaction right after a tier change does not hold a fast rhythm forever. Every tier change is written to
`agent_pulse_events` (before/after, source, `u`, `new`, reason, `policy_version`). The owner can revert a change or reset the context.

**Required fake-clock test vectors** (from B3, Resonance on, values computed per 6.3, with the numbers included in the test):

| Scenario | Expectation |
|---|---|
| The owner uses only ❤️, 1 ❤️ (`k ≈ 1.00`, `u ≈ 0.05`) or 2 ❤️ (`k ≈ 0.99`, `u ≈ 0.13`) | hold B3 |
| The owner uses only ❤️, 5 ❤️ in 3 days (average age 1.5 days, `k ≈ 0.935`, `u ≈ 0.28`) | move up exactly one tier (B2) after dwell; no further move without new signal |
| The owner uses only ❤️, 5 ❤️ spread evenly over 2 weeks (`u ≈ 0.248`) | hold B3 (right at the threshold; the test pins the exact time point) |
| The owner uses only ❤️, 10 ❤️ in 1 minute (`k ≈ 0.82`, `u ≈ 0.39`) | at most one tier in that period; no further move next period because there is no new evidence |
| Then add 10 ❤️ spread over 2 weeks | move up to B1 (= `max_tier`), never B0 |
| The owner mixes (3 👍, 1 ❤️, 1 😮 over a few days, `n = 5`) | `k(❤️) = k(😮) ≈ 0.997`, `k(👍) ≈ 0.966`; an emoji never used has `k ≈ 1.013`; every `k` is within 0.75-1.25 |
| Complete silence from B3 | around day 2 drops to B4, day 8 B5, day 22 B6, day 50 B7, day 110 hibernation; so by day 30 it is at B6, day 90 at B7, day 180 hibernating |
| 3 seen proactive messages ignored | slightly negative estimate (`u ≈ -0.02`), no drop for `unhelpful`; only `low_demand` if there is also nothing else |
| 5 reactions with the reason "wrong facts" (`u ≈ -0.24`) | hold (not enough yet); the 6th reaction (`u ≈ -0.27`) drops one tier (`unhelpful`) after dwell |
| correct silence (no signal, an opportunity exists but arbitration chose to stay quiet) | no penalty; not counted as `low_demand` when an opportunity exists |
| the owner calls directly during hibernation | back to B3 right away, keeping the estimate |

### 5.4 Durable storage and restart

`agent_pulse(agent_key, context_ref, state, tier, next_due_at, estimate, confidence, n_eff, last_eval_at, last_change_dir,
last_change_at, resumed_at, max_tier, scan_counter, policy_version, updated_at, PK(agent_key, context_ref))`. The schedule is claimed by CAS;
if the process dies midway the schedule simply comes due again. Clock skew: a negative age is clamped to 0, and a `next_due_at` far in the past runs once and is then recomputed.

### 5.5 A wake: code first, model second

`Waking does not mean calling the model. Calling the model does not mean sending a message.` Every wake runs a code step: update the estimate, compute the tier,
build, in code, the **opportunity list** within the assigned scope: team jobs where the agent is a member whose update is older than the current interval, blocked jobs
with new facts, the agent's goals waiting on the owner more than 24 hours, proposals nobody has handled, pending reasons. Each opportunity has a key `(source_ref,
version)` (table `pulse_opportunities`, durable across restarts) and may be consumed only **once** (even if the scan turn returns `none`) until the source has a new version; a consumed opportunity does not
open another scan turn and is **not** counted as "an opportunity exists" in the `low_demand` rule (5.3). Nothing at all: record `no_action`, sleep.

- A `reaction_review`/`related_review`/`wait_unblocked` reason exists: run the matching turn (4.4, 7.5, 7.4).
- An opportunity exists: run a **scan** turn (purpose `scan`) with that list as input, with structured output `{"action": "none"|"propose"|
  "enqueue"|"say", ...}`. `enqueue` only when the agent's permission allows it (through the shared queue, with a source); without permission it is `propose` (a proposal
  card for the owner/team leader); `say` goes through arbitration (section 7). At most one action per scan.
- At `active`/`awake`, even when the list is empty, every 3 wakes there is one bounded scan turn (counted by `scan_counter`, at most one turn/day/
  context) so the agent has a chance to notice work from its assigned sources by itself; a scan that finds nothing creates no negative signal.
- Do not create work to keep yourself active; a proposal that is not approved is not reopened without new facts.

## 6. T3: usefulness estimate

### 6.1 Signals (`pulse_signals`, one row per source event per agent, UNIQUE `(source_ref, agent_key)`)

| Source | Initial value (hypothesis `pulse.v1`) | Source confidence `w` |
|---|---|---|
| ❤️ / 😮 / 👍 without a reason | +0.8 / +0.6 / +0.4 | 1.0 |
| 😂 without a reason | +0.2 | 0.5 (not assumed to be praise of quality) |
| 😢 / 😡 without a reason | -0.2 / -0.4 | 0.4 (may be a feeling about the situation) |
| A reaction with a quality reason | on point +0.8; too long -0.3; wrong facts, missing points, hard to understand, off topic -0.6 (the reason wins over the emoji) | 1.0 |
| Speak/stay-quiet axis | does not enter the estimate (teaches arbitration, 7.6) | |
| Accepting a proposal, closing a decision, using a result with a host event | +0.6 | 0.8 |
| Amending a request after a result, cancelling, rejecting a proposal, revoking | -0.4 | 0.8 |
| Objective check passed / failed | +0.5 / -0.5 | 0.8 |
| A seen proactive message (6.2), no interaction after 24 hours | -0.15 | 0.6 |
| A proactive message with no evidence of being seen; silence/observation; a mandatory assigned job | creates no signal | |
| An agent's reaction; an agent claiming credit itself | creates no signal | |

### 6.2 The "seen" event (`message_seen`, resonance.sqlite3)

The dashboard sends `POST /seen {context_ref, message_ids}` when an agent's message has been in the viewport for ≥ 1.5 seconds and the tab is visible (team
and private chat). The host records the first time. Only agent messages inside Jarvis 007; nothing else is tracked.

### 6.3 Formula (`pulse.v1`)

- Time decay, half-life 21 days (`decay`).
- **Personalized per reactor and per kind of context** (team or private chat), **only for reactions without a reason** (a reaction with a quality reason
  uses the reason's value, `k = 1`): for person r, context kind c, emoji e: `n` = the number of r's reactions in c, smoothed rate
  `p_s(e) = (count of e + 3)/(n + 18)`, `p̄ = 1/6`, `k = clamp(1 + 0.3 × (p̄ − p_s(e))/p̄ × n/(n + 20), 0.75, 1.25)`, `v = v0(e) × k`. `k`
  is **recomputed in each evaluation period** from the current history (not frozen at write time). With few samples `k ≈ 1`; smoothing and the 0.75-1.25 cap keep
  a consistent user from drifting negative (their habitual praise stays ≥ 0.75, a rare emoji at most 1.25); rarity alone does not
  make a conclusion.
- Prior toward 0: `estimate = Σ w·v·decay / (Σ w·decay + 2)`; `n_eff = Σ w·decay`; `confidence = n_eff / (n_eff + 4)`; `u = estimate ×
  confidence`. After a long silence `estimate` and `confidence` both go to 0.
- Each source event contributes `|w·v| ≤ 1`. `pulse_signals` has a unique index `(source_ref, agent_key)`: feedback allocated to several
  agents (6.5) writes one row per agent with a `share`; that agent uses `w·share` in both the numerator and `n_eff`. The `share` of one source sums to 1
  (test).
- Replacing/removing a reaction: the old row is `superseded_by`; deleting the source (deleting a message/agent): `void`. No accumulation.
- Per context: computed separately for each `context_ref`; the `*` version is only for display and is the initial value for a new context (times 0.5).
- Do not optimize hearts per message/turn: a message with no signal has no score.

### 6.4 Rolling back a policy change

Applies only to **policy** changes (arbitration threshold offset, eagerness, self-applied lessons, `pulse` version), not to tier steps
(tiers follow 5.3 only). After a change there is an observation window (≥ 6 labels or ≥ 5 new signals, at most 14 days); if the arbitration error rate rises by more than 0.15
(≥ 6 labels) or the context's `estimate` falls by more than 0.3 (`confidence ≥ 0.5`), it rolls back by itself and records the reason. No improvement is claimed
before the window passes.
T3 pairing: a threshold shift caused by the owner's labels is the owner teaching directly and does not open a rollback window; the window opens only for changes made by self-review
(the L part writes) and `pulse` version changes.

### 6.5 Recording contributions (`pulse_contrib`)

- A chain written by the host: work/help steps (`team_steps`) with `input_refs`; a synthesis message points to the steps it used.
- The owner's feedback on a **synthesis** (one source event, total 1.0): "used" is the **set of inputs the host gave the synthesis step**
  (that step's `input_refs`, written by the host), not citations the agent claims; the synthesizing agent cannot shrink this set. 0.8 is split among the
  steps in the set **evenly by the host's input set** (not by how many times they are cited in the synthesis text), capped at 0.6 per agent;
  the excess over the cap is split among the other contributors still under the cap, and only when everyone has hit the cap does it go to the synthesis author; the remaining 0.2
  goes to the synthesis author. An empty set (a direct
  answer that goes through no step): the author gets 1.0. An agent that both did a step and synthesized: merge the shares, do not count twice. The synthesis author does **not** get
  an extra direct signal of its own under 6.1 for the same source.
- Replacing a result version: the old allocation is `superseded`, recomputed for the new version. Multi-level quoting/forwarding/synthesis does not multiply score (one
  source is allocated once).
- An agent cannot claim credit itself; the usefulness score does not become permission (only within `max_tier`).

## 7. T3: each agent's arbiter

### 7.1 Architecture

A pure module `server/agent_judge.py` following the shape of Zalo arbitration (separating was-called / should-speak, a rough gate, per-context cases, a threshold with an
offset, self-review), without calling bot code. Store `agent_judge.sqlite3`: `profiles(agent_key, role_text, eagerness, role_hash)`, `decisions(id,
agent_key, context_ref, source_event, verdict speak|wait|silent, address certain|none, score, threshold, reason, silence_code,
wait_until_json, ledger_ref, label, label_source, created_at)`, `offsets(agent_key, context_ref, offset, updated_at)`, `cases(agent_key,
context_ref, text_sha, features_json, label, weight, created_at)`, `waits(decision_id, agent_key, context_ref, until_kinds, until_ts,
status, rejudged)`, `changes(...)`, `review_state(agent_key, last_review_at)`.

Each agent has its own profile; thresholds and cases are **per context** (rough cases come only from the same context). The result is only `{verdict, score, reason,
wait_until, ask_clarify}`; the reply is produced by the agent.

### 7.2 Team chat

1. Called directly (structured mentions, the routing box of an ordinary message, an assigned job): the existing reply path, not through arbitration; record a
   `decision` with `address=certain`.
2. Not called: filter by code for each active member (open job relation, a general question to the team, role keywords, recent relevant contributions).
   Not passing the gate: `silent`/`no_signal`, no model.
3. Candidates passing the gate: **one** batch call (spawned outside the request), the engine is the background-work model the user chose, timeout 25 seconds,
   at most 2 batches at once machine-wide; one `agent_calls` row with purpose `judge_batch` (`agent_key` empty, `context_ref` the team), and each agent
   gets one `decision` pointing its `ledger_ref` at that row. The cost is charged to the team, not split across agents.
4. Coordination: at most `K` people speak up on their own per message (default 1), highest score first, not duplicating anyone who was called; no round-robin.
   The chosen person runs a `member_volunteer` turn (no admin commands).
5. Arbitration error: candidates are `silent`/`policy_error`; direct calls are not affected.

### 7.3 Private chat

The owner's direct question goes through the normal reply flow and never through arbitration. Arbitration applies only to **proactive** messages (from layer 3 scan/review
turns): speak/wait/stay quiet before sending. An arbitration that errors/times out/has a wrong structure: nothing is sent and the reason is recorded; no question is lost, no job is closed.

### 7.4 Waiting and releasing a wait

`wait` writes `waits` with a release condition (a new owner message in the context, the person speaking finishing their turn, a related job changing status, a maximum
time limit of 30 minutes). Wait release is evaluated in `_settle_reply_out`, on job status change, and in the team's 5-second loop; it creates a `wait_unblocked` reason. Each
(agent, original message) is reconsidered **at most once**. On expiry: `silent` with a reason, or a single `ask_clarify` sentence sent to the team leader/owner.

### 7.5 Related review turn from teammates

After `_accept` posts agent X's message, the host generates `related_review` only for agents with a structured relation: the person who receives/coordinates that job, a step
whose `input_refs` points to X's message, the person asked for help, or the command `{"op":"ask_peer","agent_key":..}` (the host checks the identity). Blocked: calling
oneself, quotes (removed before evaluation), `@` in text, depth ≤ 2 from the owner's original message, one turn per (agent, original message), no A->B->A, the team's
ceiling. It goes through the receiving agent's arbitration (7.2 steps 2-5).

### 7.6 Teaching arbitration

- Labels from the owner: the chips "Should have spoken" / "Should stay quiet (interrupted)" on a message, and the **decision history** of speak/wait/stay-quiet per agent and team (including
  quiet cases with no message) with an edit button. A prompt like "why didn't you answer?" only **suggests** a link to the most recent quiet decision; the confirmation path is
  editing in the decision history.
- A label shifts the threshold offset per context (clamped ±0.25, half-life 14 days) and adds a case; it does not change the content estimate.
- Resonance off: the label is stored, the threshold does not change; turning back on does not replay (only labels after `resumed_at` count).

## 8. T3: learning inside the team

### 8.1 Scoped lesson store (`agent_lessons`, resonance.sqlite3)

`id, agent_key, scope (team:<id>|dm:<agent_key>|*), kind (speak|method|presentation|collab), text, source (owner|teammate|leader|self|
review), source_refs_json, status (active|revoked|superseded), created_at, revoked_at, revoked_by`; event log `agent_lesson_events`.

- `JAVIS_LESSON` in a team turn: scope `team:<id>`, source `self`, tied to the turn/message/revision; only when the output is still valid (R3). A team turn loads
  that team's scope and `*`.
- Private chat: `JAVIS_RULE` (a rule the owner states outright) still goes into "Luật chủ dặn" (the owner's standing rules section of the agent memory), scope `*` as today. **Changed:** a model-proposed
  `JAVIS_LESSON` in private chat now writes `agent_lessons` with scope `dm:<agent_key>` instead of `MEMORY.md`, so a private lesson does not leak into team turns;
  only the owner's rules and lessons promoted by self-review/the owner become `*`. A private chat turn (any session) loads scope `dm:<agent_key>` and
  `*`.
- Old lessons in `MEMORY.md` (already mixed across many teams): left as they are, marked "old lesson with no scope yet" in the UI; not migrated automatically,
  the owner can delete them by hand as before.
- Promotion to scope `*` from a team lesson only through self-review (evidence from ≥ 2 contexts) or the owner.
- Revocation: the owner clicks it on the agent card; `revoked`, no longer loaded, the log is kept.

### 8.2 Teammate feedback (`agent_peer_feedback`)

The command `{"op":"peer_feedback","message_id":..,"note":..}` in an agent's turn: the host assigns the source `teammate`/`leader`, tied to the message, product, revision;
it enters the receiving agent's next turn in exactly that team under the heading "Góp ý của đồng đội (không phải yêu cầu của chủ, không phải sự thật đã kiểm)" (that is: teammate feedback, not an owner request, not a verified fact; the heading is a literal constant in the code, so it stays in Vietnamese).
It does not become an owner rule; many agents agreeing is not independent evidence; a result arriving late after a cancel/amend/member removal/revocation is only
evidence.

### 8.3 Self-review and self-application (Resonance on)

- Triggered when there are ≥ 6 **new** speak/stay-quiet labels after `resumed_at`, or ≥ 5 new usefulness signals after `resumed_at`, and ≥ 24
  hours since the last one; purpose `review`. At most 3 changes from a closed list: `offset_set` (context), `eagerness_set`, `lesson_add`/`lesson_remove`
  (team or dm scope), `lesson_promote` (needs evidence from ≥ 2 contexts). Each change cites the decision/signal ids it was shown.
- Applied immediately, with before/after recorded; rolled back per 6.4; a change that was rolled back is not repeated within 14 days; it does not override a setting the owner holds.
- Outside the scope (permissions, owner rules, code/skill/workflow, agent structure): only a proposal for the owner is recorded.
- **No two learning loops for one piece of feedback:** a source that already belongs to a `reaction_review`/self-review reason is marked consumed. `learn.py`
  (rewire from conversation logs) and the curator do not read the reaction table; A3 lane P/M applies only to goal notices; Zalo self-review applies only to bots. So
  one reaction never opens two reviews.

## 9. Ceilings, cost, reserve for obligations

| Ceiling | Default | Who adjusts | Notes |
|---|---|---|---|
| Batch arbitration turns per team/day `judge_daily` | 40 | owner; Full access can adjust; has "No limit" | **separate** from `daily_turns`, it does not eat reply slots |
| `K` people speaking up on their own per message | 1 | owner; Full access | 0 = turn off speaking up on its own |
| Arbitration mode when Resonance is off | code filter + batch | owner | "code filter only" = no model turn for agents with Resonance off |
| Proactive/review/scan/self-review turns per agent/day `agent_daily_calls` | 6 | owner; has "No limit" | Full access cannot adjust (it is not a team ceiling) |
| `max_tier` (fastest rhythm) | B1 | owner (down to B0) | the team leader cannot raise it, even with Full access |
| Obligation reserve within the server's shared ceiling | 20% | server | spontaneous turns (proactive, review, scan, batch arbitration) use only up to 80% of the ceiling; goal A2, assigned work, direct calls may use the whole ceiling (9.1) |
| Shared ceiling `JAVIS_RESONANCE_CALL_CEILING` | env | server | fixed even with Full access; scope in 9.1 |

`agent_daily_calls` is spent in priority order `reaction_review` > `related_review` > `wait_unblocked` > proactive messages/scan, and always
keeps 2 turns/day for the first two kinds of review (scan/proactive do not use the reserved part). An arbitration turn for a proactive message in private chat counts toward
`agent_daily_calls`; batch arbitration in a team counts toward the team's `judge_daily`.

Ceiling reached: a wake runs only code, the reason stays `pending`, status "Waiting for quota"; after the day passes each reason gets at most one turn (no mass make-up).
The new ceilings go into T1's **limits table** (kinds: owner adjusts, Full access adjusts, server fixed, provider).

### 9.1 Scope and enforcement of the shared ceiling (`JAVIS_RESONANCE_CALL_CEILING`)

Fixed after the T1 review: the earlier version only added `goals.calls_used` and `call_ledger`, so team turns (stored in `team_turns`, a different store) were outside the ceiling.

- **Scope:** every host-level engine turn that Jarvis 007 runs by itself on the team and Resonance paths: goal A2 turns and the probe, the goal planner,
  team turns (replying to team messages, team job steps), batch arbitration, proactive turns, scan, review, reaction review, wait release. **Out of scope:**
  private chat turns the owner types themselves (the owner is sitting there, it is not a self-run turn), loops and reminders (they have their own ceiling). This is the ceiling of a pilot with a
  quota the owner approved; with the variable not set there is no shared ceiling.
- **Counting** (one shared function `_ceiling_used(c)`): `SUM(goals.calls_used) + COUNT(call_ledger WHERE status = 'used') +
  COUNT(agent_calls WHERE counted = 1 AND status <> 'refunded')`. Rows `reserved`, `running`, `ok`, `error`, `interrupted` all count
  (the turn has reached or may have reached the model); only `refunded` (certainly never called the model) is given back. A mirrored goal turn has `counted = 0`
  so it is not counted twice.
- **Atomic:** the check and reservation happen in the same `BEGIN IMMEDIATE` transaction of `resonance.sqlite3` (SQLite serializes every
  write transaction, including from another process), like the existing `reserve_ledger_call`.
- **20% obligation reserve:** a row with `obligation = 1` (goal A2, the probe, the goal planner, team job steps, replies to team messages, direct @
  calls) reserves when `used + n <= ceiling`. A row with `obligation = 0` (batch arbitration, proactive, scan, review, reaction review, wait
  release) reserves only when `used + n <= floor(ceiling * 0.8)`. The `used` count includes both kinds, so a spontaneous turn never eats into the last
  20%, while obligations can still use that part.
- **Retry, error, refund:** each attempt is a new row (`attempt + 1`) and reserves again from the start (the ceiling is checked again). An error after the engine call mark
  (`error`, `interrupted`) still counts, no refund. Refund only when it is certain the model was never called (the `engine_started` mark was not written).
- **Restart and reconciliation** (run at startup and on every pulse tick, idempotent):
  - A `team_turn:*` row is reconciled **only** by the status of the team turn itself, **never by age**: a team turn can sit
    `reserved` with no engine mark the whole time it waits for the busy lock (up to `busy_wait_s`, default 1800 seconds) and a step can run up to
    `STEP_TIMEOUT_S` (3600 seconds). A team turn that was refunded or no longer exists gets its row `refunded`; a team turn that was settled gets its row settled to match
    (`ok`/`error`/`interrupted`); a team turn still `reserved` or running is left alone. At startup (every turn of the old process is
    dead) the `reserved`/`running` row of an unsettled team turn follows exactly the refund/interrupt path that `team_store` applies to that turn.
  - There is a **grace period** of 120 seconds counted from the ledger row's `created_at`: reconciliation does not touch newer rows, so a pulse tick never catches
    a turn in between the two reservation steps of the two stores.
  - A row that exists only in the new ledger (`mirror_ref = ''`: arbitration, review, proactive, scan) has no second store, so it alone uses an age limit: `reserved`
    with no engine mark for more than 10 minutes (longer than any turn of this kind) is `refunded`, with an engine mark it is `interrupted` (counted).
  - A team turn that reached the engine mark but is **missing** its ledger row (the process died between the two stores, or the shared store failed during reservation) gets
    its `counted = 1` row rebuilt (it may briefly exceed the ceiling: a turn already counted must not be lost), **only for turns created after the T2 upgrade mark**
    (`t2_migrated_at`, written once when the table is created) or turns still open at upgrade time. A team turn settled before the upgrade is history and never
    counts toward the ceiling (the owner's decision after the T2 review: the upgrade must not immediately block a pilot machine that has set a ceiling). A team turn missing
    its ledger row that has not reached the engine mark is left alone (it may be waiting for the busy lock after a shared-store failure); when it reaches the engine mark it
    gets its row built as above. The scan uses a durable cursor `(created_at, turn_id)` with a per-pass row limit, plus a small group: turns still open,
    turns open at upgrade, turns settled recently.
- **The ceiling is lifetime, not per day:** the count adds every still-valid row from the beginning until now (like the existing `goals.calls_used`), so
  when the ceiling is hit every turn in scope is blocked (including replies to team messages and job steps) until the owner raises the environment variable. This is the
  ceiling of a pilot with a quota, not a daily quota; the daily ceilings are still the team's `daily_turns` and `agent_daily_calls`.
- **Display when the shared ceiling is hit:** a reply turn carries the reason `server_ceiling` (key `teams.reply.why.server_ceiling`: "Reached the server's shared turn ceiling"), and a job is
  blocked with kind `server_ceiling` (key `teams.block.server_ceiling`). The team's "Allow more turns" button does **not** raise this ceiling (only the server's environment variable can); the UI says so
  plainly instead of opening the team's limits box.
- **Order of the two stores:** reserve `team_turns` (the team store) first, then the shared ledger; if the shared ledger refuses, refund `team_turns` immediately. Every
  refund or settlement of a team turn goes through one function that calls both stores; a shared-store failure at settlement does not break the team turn (reconciliation fixes it later).
- **Required tests:** a ceiling right at the limit (ceiling N: the Nth turn is allowed, N+1 is blocked before the engine), many concurrent turns (a thread and two different
  connections, never exceeding the ceiling), the 20% reserve (spontaneous turns blocked at 80% while obligations run up to 100%), reconciliation of missing and extra mirrors,
  restart between reservation and settlement, retry after an error counted correctly.

## 10. UI (section 11 of the GOAL)

The assistant card and the member row in the Team pane, API `GET /agents/{slug}/pulse` (the host converts the slug to the active `agent_key`):

- Resonance on/off; state (`active/awake/slowed/hibernating/waiting_owner/paused/off`, "Waiting for quota") and tier **per context**; the latest review, the next expected one, the wake reason;
- recent reasons for rhythm changes (before/after, source); feedback already handled and its status;
- lessons in use by scope, source, a revoke button (and the label "old lesson with no scope yet");
- the arbiter: where it applies, recent speak/wait/stay-quiet decisions (including quiet cases) and an edit button;
- work in progress/waiting/blocked (the existing Jobs tab);
- the team's admin log (`team_events`: grant/revoke permission, add/remove member, team leader commands) in the Team pane, Advanced section.

Buttons: Wake, Pause/Resume, Reset pace (per context), Revert. Success is shown only after the host confirms. Two languages, narrow
screen, text ≥ 16px.

## 11. T4: long history, performance, operations

- **Long history inside the right team** (T4 0.124.0 already has cursor pagination, accent-insensitive search, a code-built summary block of the older part): add to
  the summary block the items that are **always kept** without loading the whole history: the pinned decision log, the original request and status of open jobs, the
  contribution sources of the latest result (from `pulse_contrib`), the agent's unconsumed feedback in the team; each item is an indexed query with a row
  cap. Private chat: the `agent:<slug>` turn loads scoped lessons and the feedback block the same way. Test: a team of 5,000 messages still keeps the request,
  decisions, contribution sources and feedback in the prompt; the number of store reads per turn has a ceiling.
- Measured with a fake engine: many teams, thousands of messages, many reactions, agents sleeping/waking, concurrent arbitration; measure the API, event loop latency, the number of fake
  model turns, the number of store reads/writes; the browser (list rendering, many tabs).
- Checks: many tabs, lost connection, restart, cancel, retry, leaving a team, changing the team leader, turning Resonance on/off, revoking permission.
- A blocked team or a sleeping agent does not take the slot of a team that has work. The VPS scenario is prepared, **not run**.

## 12. Migration and rollback

- Upgrade: create the new tables/stores; every `agent_pulse` is initialized at B3 with `resumed_at = upgrade time`; old reactions are **not** backfilled into tiers
  (they are only display evidence). All new columns have defaults so the old build runs on an upgraded store.
- Rolling back to the old build: the old build ignores the new tables/stores; the restore tool (R9) is extended to also copy `agent_judge.sqlite3` and the new tables in
  `resonance.sqlite3`, `conversations.db`, `team.sqlite3` into the pre-upgrade backup.
- Store error while writing an effect: the outbox stays `pending` and is projected again later; no reaction lost, no double effect.
- Rolling back to the old build when team leader/member reactions already exist in `team_reactions` (reactor `agent:...`): the old build shows
  them as ordinary reactions; this is a known effect of rolling back (no data lost), recorded in the restore guide.

## 13. Acceptance matrix (GOAL section 12) -> where it is checked

| Case | Milestone | Main test (real host, fake engine) |
|---|---|---|
| 1 two teams, tags | T1/T3 | T1's tag test; `test_agent_judge_scope.py`; `test_agent_lessons.py` |
| 2 direct call / joining on its own / staying quiet | T3 | `test_agent_judge_team.py` |
| 3 assignment, feedback, editing a version | T1/T3 | the existing team tests; `test_team_peer_feedback.py` |
| 4 six reactions in two places | T2 | `test_dm_reactions.py`, extended `test_team_reactions.py`, JS |
| 5 on/off with feedback | T2/T3 | `test_feedback_wake.py` |
| 6 long-term rhythm, low demand, quiet without penalty | T3 | `test_agent_pulse_policy.py` (vectors 5.3) |
| 7 sleep/wake again, off does not turn itself on, obligations kept | T3 | `test_agent_pulse_host.py` |
| 8, 28 contribution, no double counting, no self-rewarding | T3 | `test_pulse_contrib.py` |
| 9 replacing/removing a reaction, deleting the source | T2/T3 | `test_dm_reactions.py`, `test_agent_pulse_policy.py` |
| 10 no infinite loop, waiting for the owner | T3 | `test_agent_judge_team.py`, `test_related_review.py` |
| 11 priority A->C->B, two kicks | T1 | T1 tests |
| 12 amend/remove/change/revoke/cancel, permission per turn | T1 | T1 tests |
| 13 engine error, store error, repeated cancel, restart | T1/T3 | `test_agent_calls_ledger.py`, `test_feedback_projector.py` |
| 14 multi-store restore | T1/T3 | the existing rollback test + the new stores |
| 15 three layers, not three turns | T3 | `test_agent_calls_ledger.py` (routing 3.3, partial index) |
| 16 fake clock day/week/month | T3 | `test_agent_pulse_policy.py` |
| 17 arbitration/self-review with ledger, source, rollback | T3 | `test_agent_judge_review.py` |
| 18 UI, two languages, measurements | T3/T4 | JS, browser smoke, bench |
| 19 each agent's own profile | T3 | `test_agent_judge_team.py` |
| 20 private chat, arbitration error | T2/T3 | `test_agent_judge_dm.py` (timeout, bad JSON, engine error) |
| 21 editing a quiet / interrupting case | T3 | `test_agent_judge_labels.py` |
| 22 personalization, few samples, event emoji, not yet seen | T3 | `test_agent_pulse_policy.py` |
| 23 active in A, asleep in B | T3 | `test_agent_pulse_host.py` |
| 24 finding work on its own within permission | T3 | `test_agent_pulse_host.py` (scan, propose/enqueue) |
| 25 turning back on does not replay | T2/T3 | `test_feedback_wake.py` |
| 26 self-application, before/after, rollback | T3 | `test_agent_judge_review.py`, `test_agent_lessons.py` |
| 27 teammate signal, quotes, wait release | T3 | `test_related_review.py` |
| Store/outbox error, clock skew | T2/T3 | `test_feedback_projector.py`, `test_agent_pulse_policy.py` |

## 14. Decisions needed from you (not narrowed on our own)

1. **Arbitration when Resonance is off:** by default it still filters by code + batch per the GOAL; there is an option "code filter only" if you do not want to spend turns on
   agents with Resonance off.
2. **The "seen" event:** needs the dashboard to report that an agent's message has been in the viewport.
3. **Quality pilot on a real model** and **VPS measurement:** only the pack is prepared, awaiting your order.

## 15. Log of fixes from the design review

Independent review round 1 (FAIL, 6 blockers, 10 important, 6 minor). Each item was handled at: (1) stores and outbox: 2, 3.1, 3.5, 12; (2) partial indexes,
reason lifecycle, routing, busy lock: 3.1-3.4; (3) rhythm only on new evidence, prior toward 0, dwell, test vectors: 5.3, 6.3; (4) reaction review
turn: 4.4; (5) separate arbitration ceiling, obligation reserve, `_under_ceiling`: 3.1, 9; (6) long history: 11; (7) allocation by evidence, per-agent
ceiling, no duplicate signals: 6.5; (8) personalization per person and context, 😂 low confidence, `p̄`, one tier-down rule: 6.1,
6.3, 5.3; (9) rollback only for policy: 6.4; (10) bounded work scan: 5.5; (11) pulse rhythm outside the goal tick: 5.1; (12) ledger of batch arbitration
turns, timeout, engine: 7.2; (13) migration, rollback, clock skew: 12, 5.4; (14) new ceilings in the limits table, Full access does not raise
`max_tier`, `resumed_at` on the team leader path: 2, 9; (15) scope `dm:<agent_key>`, `MEMORY.md`, no two learning loops: 8.1, 8.3; (16) counting after
`resumed_at`: 8.3, 7.6; (17) waking again with `min`, obligations while paused, nudge when waiting on the owner: 5.2; (18) reconsidering once after a wait release: 7.4; (19) "why didn't you
answer" only a suggestion: 7.6; (20) the main Chat page, `mobile-chat.js`, reused nonce, API by `agent_key`: 2, 4.1, 4.2, 10;
(21) "Waiting for quota", waiting on the owner, admin log: 5.2, 10; (22) matrix adds case 14, store error, private chat arbitration error: 13.

Review round 2 (PASS WITH CHANGES, 2 blockers, 8 important, 4 minor), handled: (B1) `k` only for reactions without a reason, smoothing, cap
0.75-1.25, recomputed each period, vectors recomputed with `k` and adding the consistent / mixed user: 5.3, 6.3; (B2) separate `pending` index, unconsumed sources
move to the new waiting reason: 3.2; (3) projecting in log order, net state: 3.5; (4) opportunities consumed once, not
counted for `low_demand`: 5.5; (5) non-waiting lock for proactive turns: 3.4; (6) private chat lessons with `dm` scope: 8.1, 0; (7) the "used" set
written by the host: 6.5; (8) per-agent signal rows with `share`: 6.3; (9) status by the real send result: 4.4; (10) ceiling spending order and the part
reserved for review: 9; (11) wording of the quiet vector: 5.3; (12) shared ceiling counts only still-valid turns: 3.1; (13) turning back on keeps the estimate, agents that were off
at upgrade time stay `off`: 5.2; (14) effect of rolling back to the old build: 12.

Review round 3 (PASS WITH CHANGES, no blockers left; the reviewer confirmed the important items are fixed and no further round is needed), handled: (1)
vectors for the mixed user and for 5 ❤️ spread over 2 weeks right at the threshold: 5.3; (2) turn error when a newer waiting reason already exists: 3.2; (3) trying the lock before
claiming the reason, so busy costs no attempt: 3.4; (4) even split by the host's input set, the excess over the cap goes to others first: 6.5; (5) private chat scope
per agent (`dm:<agent_key>`), not per session: 2, 8.1; (minor) UNIQUE notes, table `pulse_opportunities`: 2, 3.5, 5.5, 6.1.

Fix after the T1 review (shared ceiling, 2026-10-15): the earlier version excluded `agent_calls` rows with a `mirror_ref` from the ceiling while the old count had only
`goals.calls_used` and `call_ledger`, so team turns were outside the ceiling. Now: a single ledger, the `counted` and `obligation` columns, team turns reserving
before the engine, the 20% reserve enforced with `floor(ceiling * 0.8)`, and the rules for retry, refund and reconciliation: 3.1, 9, 9.1. Review of that fix
(round 2): the ledger row of a team turn is reconciled only by the team turn's status, not by age, with a 120-second grace period; the ceiling is lifetime; how
`server_ceiling` is displayed: 9.1.

Fix while building the T3 rhythm part (2026-10-15, a deviation accepted by the coordinator): the `low_demand` rule (5.3 step 4) gains the condition "quiet for
longer than `max(4 x interval, 3 days)`" alongside the literal reading, because under the literal reading a reaction right after a tier change holds a fast
rhythm forever; the threshold of 4 intervals keeps the 5.3 vectors correct ("5 ❤️ spread over 2 weeks" holds B3, "10 ❤️ every 1.4 days" reaches B1).
Details and tests: `docs/dev/team-chat-t3-pulse.md` section 6.
