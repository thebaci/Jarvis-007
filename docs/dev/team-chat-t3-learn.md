# T3 part L: learning in the team (0.156.0)

Design: `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` sections 3.2-3.4, 4.4, 6.4, 8, 9, 10, 12. Three-part contract:
`docs/dev/team-chat-t3-contract.md` (L owns section 3 and the lessons part of section 4). This part covers five jobs: the real reaction review turn,
the scoped lesson store, teammate feedback, self-review with self-apply and self-revert, and the per-agent budget of autonomous turns.

## 1. Modules and tables

| Module | What it does | Tables (all in `resonance.sqlite3`, created by the module, `CREATE TABLE IF NOT EXISTS`) |
|---|---|---|
| `server/agent_lessons.py` | scoped lesson store, teammate feedback, the `TeamLearning` hook for the team runner | `agent_lessons`, `agent_lesson_events`, `agent_peer_feedback` |
| `server/agent_review.py` | `ReviewHost`: reaction review turn (4.4), self-review (8.3), revert function (6.4), the "lessons" section of the pulse view, owner routes | `agent_review_state`, `agent_review_changes`, `agent_review_consumed`, `agent_review_proposals` |
| `server/agent_budget.py` | `try_spend` against the `agent_daily_calls` ceiling (section 9) | `agent_budget`, `agent_budget_waits` |
| `dashboard/agent-lessons-ui.js` | the "Lessons and budget" section in the Pulse panel (registry `window.JavisPulseParts`) | |

Small edits to existing places: `feedback_projector.FeedbackProjector.review_source/set_review_status` (reads `rx:*` sources, writes status from
the real host result), `team_runner` (team-scope lesson block, feedback block, the `peer_feedback` command, attaching messages to lessons, the
`agent_daily_calls` row of the limits table), `team_api.TeamApiDeps.learning`, `main.py` (the `JAVIS_LESSON` write path, the private chat prompt note,
wiring the learning host, the learning tick before P's tick, routes).

### `agent_lessons`

`id, agent_key, scope (team:<id>|dm:<agent_key>|*), kind (speak|method|presentation|collab), text, text_norm, source (owner|teammate|
leader|self|review), source_refs_json, status (active|revoked|superseded), promoted_from, created_at, revoked_at, revoked_by,
revoke_reason`. Partial unique index `(agent_key, scope, text_norm) WHERE status = 'active'`: adding the same text again only appends a source. Ceiling:
40 active lessons per scope (the oldest self-learned lesson that is not the owner's moves to `superseded`). The `agent_lesson_events` log
(`add`, `dup`, `revoke`, `restore`, `promote`, `supersede`, `link`): no row is ever deleted.

### `agent_peer_feedback`

`id, team_id, receiver_key, author_key, author_role (teammate|leader), message_id, task_id, revision, turn_ref, note, status
(active|evidence), evidence_reason, nonce UNIQUE, delivered_turn, created_at, delivered_at`.

### `agent_review_changes`

Every change self-review proposes (applied or not): `kind`, `signature` (`kind|context|target`: up/down direction for offset, the value for
eagerness, the normalized text for adding a lesson, the lesson id for remove/promote), `before_json`, `after_json`, `evidence_json`, `why`, `status
(applying|applied|kept|reverted|rejected)`, `reject_reason`, `policy_change_id` (a row of P's `pulse_policy_changes`), `reverted_at`,
`revert_reason`.

## 2. Flows

### 2.1 Reaction review turn (4.4)

1. The T2 projector groups valid reactions (Resonance on, after `resumed_at`, message not attached to a goal) into ONE `reaction_review` reason per (agent,
   context). P's pulse host (`PulseHost.tick`) spawns the registered handler for `pending` reasons (skipping agents that are busy, paused or off).
2. `ReviewHost.serve_reaction_review(reason)`: try the busy lock WITHOUT waiting (busy: `busy`, the reason stays `pending`, attempt unchanged), ask
   `agent_budget.try_spend(key, "reaction_review", reason_ref="wr:<id>", units=2 in a private chat)` (a private chat needs room for both the review turn
   and the judging turn for a new message; if exhausted: every reaction of the source moves to `waiting_quota` ("Waiting for quota"), a `quota` event, no turn ledger entry;
   the state write, the event and the WS packet happen at most once per 10 minutes per reason), then `WakeReasons.claim` (CAS, fixes the source list, reserves an `agent_calls` slot with purpose
   `reaction_review`, `obligation = 0`; if the shared ceiling is full: "Waiting for quota" with reason `server_ceiling`).
3. The source's reactions move to `reviewing`. The prompt: the review rules (`REVIEW_RULES`) appended after the persona; the body is each source `[rx:..]` with the message
   excerpt, emoji, reason, speak/silent axis, feedback, and the flag "the owner changed this response afterwards"; plus the lessons block for the context's own scope.
4. Engine: `deps.engine_for(key, ctx, "reaction_review")`, which in `main.py` is `_pulse_engine_for` (the same text-only contract as team turns and
   scans). The engine milestone is written to the ledger; 10 minute timeout.
5. `parse_review`: one JSON block with only the keys `outcome, message, lesson, consumed, reason`; `outcome` is one of four values; `consumed`
   is a NON-EMPTY list and a subset of the sources; `message` is non-empty for `ask_back`/`revise`; `lesson {text, kind presentation|method}` is required
   for `lesson`. On failure: `W.settle(error)` (the reason goes back to `pending` with attempt + 1, more than 3 tries means `failed`), the reactions go back to "Waiting for review" with a reason,
   and a `reaction_review_error` event.
6. On success: `W.settle(ok, consumed)` BEFORE any effect (sources not yet consumed move to a `pending` reason of the same kind, their reactions go back to
   "Waiting for review"); then the effect:
   - `keep`: nothing is sent; "No change needed" with the model's reason.
   - `lesson`: `agent_lessons.add(scope = context, source = review, sources = consumed + wr:<id> + call:<id>)`; "Adjusted".
   - `ask_back`/`revise`: `judge.proactive(agent_key, context_ref, draft, source_event = "wr:<id>", origin = "reaction_review",
     payload = {judge_daily (team), draft, review{..., session_id}})`. `speak`: `deps.send` sends a NEW message replying to the message that got the reaction
     (it does not overwrite); in a private chat the message goes into the EXACT session that holds the reacted message, with `reply_to` and a `review` mark (if that session is not
     the assistant's private chat, it goes to the report session). If it is sent, "Adjusted"; if not, "No change needed" ("could not send the new message").
     If the judge stops because of quota or a ceiling (`waiting_quota`, `judge_cap`, `server_ceiling`): "Waiting for quota", the sources go back to the waiting reason
     (`WakeReasons.requeue`), backed off by 10 minutes; this is not "the judge chose silence". `silent`: "No change needed" ("the judge chose silence"). `wait`:
     "No change needed" ("the judge chose to wait"); when J lifts the wait and re-judges to `speak` (private chat and team), the sender `on_judge_send` (it only
     accepts `origin = reaction_review`) sends the message and changes the status to "Adjusted".
7. The status is written onto EVERY reaction in `consumed` (private chat store and team store, only if the reaction is still at exactly that revision), WS packets
   `chat_reaction`/`team_message`. The decision writes `agent_pulse_events` kind `reaction_review` (reason = outcome, payload: reason_id,
   call_id, consumed, moved_to, status, lesson_id/decision_id/message_id).

### 2.2 Scoped lessons (8.1)

- Team turn: `_team_engine_for` only STRIPS `JAVIS_LESSON`/`JAVIS_RULE` (downgraded to lessons); `commit` (the runner calls it only when the output is still valid,
  R3, once per turn) writes `team:<team_id>`, source `self`, source refs `turn:<id>`, `task:<id>`, `step:<id>`; after posting the message the runner
  also attaches `msg:<id>`. The fake team of a scan/review turn (no `session_id`) never writes.
- Private chat: `_ket_luot_agent(..., conv_sid)` writes `JAVIS_RULE` into the "Luật chủ dặn" section (the owner's rules) as before; `JAVIS_LESSON` (and a `JAVIS_RULE` without a
  sentence from the owner) goes to `dm:<agent_key>` (code: the session's pin, the live row of the slug, otherwise it issues a code without enabling Auto). It no longer goes into MEMORY.md.
- Prompt: a team turn loads `team:<id>` + `*` (`TeamRunner._learning_lines`), a private chat loads `dm:<agent_key>` + `*`
  (`_dm_lessons_prompt`). `for_prompt` filters to exactly the given scope and never returns another scope.
- Old lessons in MEMORY.md are left as they are (still in the prompt as before), and the UI labels them "Old lessons without a scope" (read with
  `legacy_lessons`, not migrated).
- Promotion to `*`: the owner (route `promote`) or self-review with evidence from at least 2 different contexts; the original lesson becomes `superseded`.
- Revoke: `revoked`, the log is kept; restore is only used when reverting a self-review change.

### 2.3 Teammate feedback (8.2)

The command `<!-- JAVIS_TEAM: {"op": "peer_feedback", "message_id": .., "note": ..} -->` in any role, at most 3 per turn, handled in
`accept_lock` in the same place as the `react` command. The host assigns `author_role` (the team's team lead or a teammate), the receiver is the message author
(it must be another assistant's message in the same team), attaches the message's `task_id` and `revision`, `turn_ref`, and nonce `<turn>#pf<i>`. If the output is no longer
valid (a member left, cancel, a request edit, a team lead change, lost the hold) or the receiver has left: `status = evidence`, and it is never
shown. When the receiver's next turn in the same team is built: feedback pointing at a cancelled task or a changed revision is downgraded to evidence; the rest is shown
under "Góp ý của đồng đội (không phải yêu cầu của chủ, không phải sự thật đã kiểm)" (a Vietnamese prompt heading, kept verbatim as code matches it: "Teammate feedback (not an owner request, not a verified fact)") with the sentence "nhiều trợ lý cùng ý cũng không phải
bằng chứng độc lập" (kept verbatim, same reason: "several assistants agreeing is also not independent evidence"); once the turn is accepted it is marked delivered (once). Feedback creates no lesson, rule or useful signal.

### 2.4 Self-review and revert (8.3, 6.4)

- `ReviewHost.tick(agents)` runs in `main._learn_tick` RIGHT BEFORE `PulseHost.tick` every 30 seconds: it updates the label/error counts for its own open
  observation window (`agent_pulse.record_policy_labels`), syncs `kept`/`reverted` from P, checks each agent at most once per 10
  minutes and spawns `maybe_self_review` when due.
- Due (`due`): Resonance on; at least 24 hours since the last successful review; at least 1 hour since the last failed attempt; new evidence after
  `max(resumed_at, last time)`: at least 6 speak/silent labels (J, excluding direct calls) or at least 5 useful signals (P, excluding `context_init`), minus sources
  already consumed by a reaction review turn, sources that are STILL in an unfinished `reaction_review` reason (waiting, running), labels born from the reaction's
  speak/silent axis (`label_source = reaction`), and sources the previous review already used.
- The turn: busy lock, `try_spend(key, "review")`, reserve an `agent_calls` slot with purpose `review` (`selfreview:<key>:<ms>`, obligation 0), prompt
  `SELF_RULES` with evidence codes `[decision:<id>]`, `[<source_ref>]` and lessons `[L<id>]`.
- Each change (at most 3, the excess is `over_limit`): kinds outside the closed list become proposals; evidence must be a code that was shown; `offset_set`
  (the agent's context, clamped to +/-0.25, dropped if unchanged), `eagerness_set` (low|medium|high), `lesson_add` (team/dm, needs at least one piece of evidence from the target context ITSELF, otherwise `evidence_context`), `lesson_remove`
  (not an owner lesson, not `*`), `lesson_promote` (evidence from at least 2 contexts). It does not override a setting the owner holds (`owner_held`).
  It does not repeat a signature that was reverted within 14 days.
- Applied immediately through J (`set_offset`/`set_eagerness` with source `self_review:<code>`) or the lesson store; before/after is recorded; it is linked to P's window: it uses the
  `pulse_policy_changes` row J already wrote through the `policy_change` hook (same source), or writes one itself if there is none; it sets `base_error` (the rate of labels contradicting the conclusion in the
  context over 30 days) so the rule "+0.15 at 6 or more labels" has a baseline.
- Revert: P closes the window (at least 6 labels, or at least 5 new signals, or 14 days) and calls the revert function registered for that kind
  (`agent_pulse.register_policy_reverter`). L's function only handles sources `self_review:*`: for an offset it removes EXACTLY the shift this change made (already
  decayed like the offset), so what the owner taught through labels during the window is kept; eagerness goes back (if the owner reset it, the owner's value is kept and `owner_held` is recorded);
  a lesson that was added is revoked, a lesson that was removed is restored, a promotion is reverted. When the owner clicks Revert on a card, it uses P's route
  `POST /agents/{slug}/pulse/revert {change_id}`; the reason is recorded as `owner`.
- A process that dies between `applying` and `applied`: after 10 minutes the change becomes `interrupted` and shows in the Lessons section with before/after
  (there is no 6.4 window, the owner checks and fixes it by hand).
- Proposals outside the scope (permissions, owner rules, code, skills, workflows, structure) go to `agent_review_proposals`, shown in the "Proposals for you to decide" section.

### 2.5 Budget (section 9)

`try_spend(agent_key, purpose, at=None, *, store=None, reason_ref=None) -> (ok, reason)` only CHECKS; a turn is counted when the caller reserves the ledger slot right after. Counting: the agent's `agent_calls` rows since 00:00 (machine time), minus `refunded`, purpose `proactive|scan|review|reaction_review`
plus `judge_batch` in a `dm:` context (judging proactive messages in a private chat). The first two kinds (`reaction_review`, and `related_review` received through the reason
`related_review`) can use up to the ceiling; the others only up to `ceiling - max(0, 2 - number of turns of the first two kinds today)`. When exhausted: the reason stays `pending`,
`agent_budget_waits` records which reasons waited; the next day each such reason gets only one turn (`backlog_once`). The ceiling is set by `set_cap` (only `by =
"owner"`; a number 0..200 or "unlimited"/null; an empty string is a 400 error). `units` (default 1) is the number of turns that must still be free. The pulse host serves tier 3 reasons
by `sort_by_priority`. The `agent_daily_calls` row goes into the T1 limits table (owner group, default 6, with Unlimited).

## 3. Routes (owner only, after auth + CSRF middleware; success only after the store has been written)

- `POST /agents/{slug}/lessons/{lesson_id}/revoke`, `POST /agents/{slug}/lessons/{lesson_id}/promote` -> `{ok, result, view}` (`view`
  is the new "lessons" section); 409 when there is nothing left to change (already revoked, another assistant's lesson).
- `POST /agents/{slug}/budget {daily_calls: number | "unlimited"}`; 400 for a bad value; 409 when the assistant has no code yet.
- The "lessons" section in `GET /agents/{slug}/pulse` (`parts.lessons`): `scopes`, `legacy`, `changes` (with `can_revert`, `policy_change_id`),
  `proposals`, `budget`, `reviews`, `slug`.

## 4. Errors and recovery

| Situation | Result |
|---|---|
| Agent busy (team turn, A2, scan) | the reason stays `pending`, attempt does not go up; the next tick retries |
| Judging a new message stops for lack of quota | "Waiting for quota"; the sources go back to the waiting reason (not consumed), backed off by 10 minutes |
| Engine cannot be built several times | each time the turn is completed; the reason is backed off 5 minutes before the next attempt |
| Daily quota exhausted / shared ceiling | "Waiting for quota"; no ledger entry, no engine; the next day one turn per reason |
| Engine cannot be built (before the milestone) | the turn is `refunded`, the reason is `pending` (the attempt does not count) |
| Engine fails after the milestone, timeout | the turn is `error`, the reason is `pending` with attempt + 1 (more than 3: `failed`, the owner clicks retry) |
| Output in the wrong shape | as above, a `reaction_review_error` event with the error code |
| Failure while applying the effect (after `ok` was settled) | status "No change needed" with "could not apply the review result"; no retry (to avoid duplicate messages) |
| Process dies mid-turn | the reason is stuck in `claimed`: `recover_stale_claims` (every learning tick) settles it as `interrupted` after 11 minutes, the sources go back to `pending` (attempt kept, more than 3 means `failed`), the reactions go back to "Waiting for review"; a ledger row that passed the engine milestone still counts |
| Lesson store fails while building the prompt | the turn continues without the lessons block (logged) |
| P has no module | `register_with_pulse` returns False; `pending_reviews()` and `serve_reaction_review` can still be called by hand |
| J not wired | judging returns `silent` (`judge_unavailable`): `ask_back`/`revise` are never sent without being judged; self-review skips `offset_set`/`eagerness_set` (error `apply_error`) |

## 5. Migration and rollback

- Upgrade: only creates new tables. No backfill: old lessons in MEMORY.md stay where they were; old reactions do not become reasons.
- Rollback: the old version ignores the new tables; `JAVIS_LESSON` writes MEMORY.md again as before. Scoped lessons written while 0.156.0 was running stay in
  `agent_lessons` (not lost, just not loaded) until the next upgrade. The T2 restore tool (`tools/team_adaptive_restore_pre.py`) copies
  `resonance.sqlite3` whole, so the new tables are inside the backup.

## 6. Join points with P and J

- **P (merged into this branch):** `agent_pulse_host.register_reason_handler("reaction_review", ...)`, `register_view_part("lessons",
  ...)`, `agent_pulse.register_policy_reverter(kind, ...)` for the five kinds of change; `apply_policy_change`, `record_policy_labels`,
  `policy_changes`, `record_event`, `events`, `signals`; `main._learn_tick()` runs before `_pulse_host().tick()`. P's budget calls
  `agent_budget.try_spend(key, "scan", at)` through the `_budget_try_spend` adapter (the module exists now, so there is no more "let it through").
- **J (merged through `origin/claude/team-adaptive-t3` d8d1b2b1, called through `JudgeAdapter`):** `judge_proactive(..., origin, payload)`
  (async), `get_profile` (reads `eagerness_source`), `set_offset`, `set_eagerness`, `default().store(False).decisions/changes` (labels with
  `label_at`, the owner holds the offset).
  1. `main._learn_register_sender()` registers `ReviewHost.on_judge_send` with `agent_judge.register_sender` once the judge is wired (retried
     every tick). The shared sender `main._judge_send` SKIPS payloads with `origin = "reaction_review"` (so nothing is sent twice); test
     `test_t3_integration.py` checks both.
  2. Closed (92202224): `_agent_judge()` passes `policy_change=_judge_policy_change_noop`; the owner's labels do not open a 6.4 window in P,
     and L writes the window row itself for its own changes.
  3. Closed together with item 2: the owner's changes do not open a window, so P does not revert them.
  4. Closed: `agent-pulse.js` calls `render(view, null, {slug})`; the "judge" and "lessons" sections follow the same signature.
- **Team runner:** `TeamRunner(learning=agent_lessons.TeamLearning(...))` through `TeamApiDeps.learning`.

## 7. Decisions made along the way

- An empty `consumed` is the wrong shape: a turn that consumes nothing would push every source into a new reason and loop forever within the quota.
- Settle `ok` before any effect: better to lose one effect (it shows "could not apply") than to send a duplicate message on a rerun.
- `message` of `keep`/`lesson` and `lesson` of other outcomes are ignored (no error); an unknown key is an error.
- The budget counts straight from `agent_calls` (no second ledger): a refunded turn gives itself back, no "spent" record needed.
- `wait_unblocked` does not use the 2-turn reserve (the design only reserves for "the first two review kinds").
- The budget is stored in its own `agent_budget` table (there is no per-agent settings store; P's `max_tier` lives in `agent_pulse`, and P's table is not extended);
  the route `POST /agents/{slug}/budget` follows the same pattern as `POST /agents/{slug}/pulse/max_tier`.
- Self-review counts evidence after `max(resumed_at, previous review)` and marks the evidence it used; a signal already consumed by a reaction review
  turn is not counted (no two learning loops for one piece of feedback).
- A workflow step (`_learn` of a workflow) still writes MEMORY.md as before: the design only changes private chat and team turns.
- Teammate feedback is delivered exactly once, for the receiver's first ACCEPTED turn in that team.
- `learn.py` (rewire, curator) and `resonance_learning.py` (A3) do not read the reaction table, `pulse_signals` or `agent_lessons` (a code-scanning test).
- Fixes after the T3 review (branch `claude/team-adaptive-t3-fix`): the judging turn for a new message in a private chat spends quota at the `reaction_review` level
  and needs 2 free turns before accepting a reason; running out of quota at the judging step no longer loses the feedback (`requeue`); self-review does not relearn
  feedback that is waiting for a reaction review turn; `offset_set` reverts by the shift; `lesson_add` needs evidence from the target context.
  A new message's wait in a team is re-judged once, as in a private chat (round 2 P2-1).
