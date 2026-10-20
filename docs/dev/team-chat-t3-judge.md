# T3 part J: each agent's speak / wait / silent judge (0.156.0)

Design: [2026-10-15-team-adaptive-design.md](../superpowers/specs/2026-10-15-team-adaptive-design.md) sections 2, 3, 7, 9, 9.1,
10, 12, 13 (cases 1, 2, 10, 17 judge part, 19, 20, 21, 27). Contract of the three parts: [team-chat-t3-contract.md](team-chat-t3-contract.md)
section 2 and the judge part of section 4. Part P (adaptive pulse) and part L (learning) are built in parallel and meet at the contract.

## 1. Architecture

| Part | File | Job |
|---|---|---|
| Pure policy + service | `server/agent_judge.py` | The code gate (`prefilter`), building the batch prompt and the proactive-message prompt, checked JSON reading (`parse_batch`, `parse_one`), choosing K people (`select_volunteers`), threshold shift (`label_delta`, `threshold_for`). The `Judge` class takes every dependency as a parameter (store, turn ledger, wake reasons, engine, Resonance flag, context history, `try_spend`). The module-level functions per the contract call the default `Judge` that `main.py` wires (`agent_judge.wire`). |
| Store | `server/agent_judge_store.py` | New store `agent_judge.sqlite3`: `profiles`, `decisions`, `offsets`, `cases`, `waits`, `changes`, `review_state` (section 7.1) and `chains` (message chains in a team, to block depth and A->B->A). Opened lazily: with no judge turn yet there is no file. |
| Team runner | `server/team_runner.py` | `submit` records the "why didn't you answer" hint, releases `owner_message` waits, marks `judge`; `run_message` = the reply turn by @ and then `run_judge`; `_run_volunteers` (the `member_volunteer` turn); `_judge_after_accept` (message chain + related review); `_judge_team_waits` (re-judge, expiry); the `ask_peer` command; releasing waits in `_settle_reply_out` and on every job state change; `judge_tick`. |
| Turn ledger | `server/agent_ledger.py` | `member_volunteer` is a SPONTANEOUS team turn (obligation 0, uses only up to 80% of the shared ceiling). |
| Team store | `server/team_store.py` | New caps `judge_daily` (40, with Unlimited), `volunteer_k` (K, 1, at most 5, 0 turns it off), `judge_off_batch` (1 = code filter + batch, 0 = code filter only); the turn role `member_volunteer`. |
| Feedback projector | `server/feedback_projector.py` | The `axis` of the OWNER's reaction goes to `agent_judge.label` (`record_judge_label`, source `reaction`). |
| Host | `server/main.py` | `_agent_judge()` (the judge engine = the background-job model the user picked, empty folder, no tools), releasing waits when the owner messages in private chat, routes `GET /agents/{slug}/judge`, `POST /agents/{slug}/judge/label`, contributing the "judge" part to part P's pulse panel. |
| Background loop | `server/team_api.py` | Sending a message runs `run_message` in the background; the 5-second loop calls `judge_tick` (even with no team store yet, for private chat). |
| UI | `dashboard/agent-judge-ui.js`, `teams.js`, `console.css`, i18n | Decision history by context (including silent cases with no message) with a correct button; a cell in the team member row; the limits table and the owner's limit box; a hint button under a "why didn't you answer" message. |

## 2. Flow

### 2.1 Team chat (7.2)

1. The owner sends a message. `submit` routes as before (a message with @ calls the people @-ed, a normal message calls the coordinator cell). A direct call and an assigned job
   (`as_job`) record a decision `kind=direct, address=certain` (no model, no threshold). The route returns immediately.
2. In the background: `run_message` runs the reply turn by @ first (so the judge sees the answered message and avoids duplicates), then `run_judge`.
3. The code gate, for each active member who was NOT called: an open job with text matching the message, a general question to the team, role keywords, a related contribution
   within 30 minutes. No signal: `silent/no_signal`, no model. An agent with Resonance off in "code filter only" mode:
   `silent/code_only`.
4. The remaining candidates go into ONE batch (at most 8): reserve ONE `agent_calls` row with purpose `judge_batch`, empty `agent_key`, the team's `context_ref`,
   obligation 0, counted 1, BEFORE the engine; the `judge_daily` cap is counted and reserved in the SAME BEGIN IMMEDIATE transaction. At most 2
   batches at once in the process, deadline 25 seconds. Each decision points to `ledger_ref = call:<id>`.
5. A score >= the agent's own threshold (eagerness low 0.75 / medium 0.60 / high 0.45 plus the offset for the context, clamped to 0.30-0.90) means it wants to speak. Choose at most
   K people with the highest scores (ties go by member order: stable, not round-robin), minus the number already volunteered for the same root message. Others:
   `not_selected`; K = 0: `k_zero`.
6. A chosen person runs a `member_volunteer` turn through exactly the team turn path (`team_turns` + shared ledger, busy lock, daily cap, the outcome row
   `team_replies` with Retry). No admin commands. If the message cannot be posted, the decision records `turn_blocked`.

### 2.2 Private chat and proactive messages (7.3)

The owner's direct question takes the normal reply path, not the judge; the host only releases the `owner_message` waits of `dm:<agent_key>`.
`judge_proactive(...)` is for proactive messages (P's `say` scan turn, L's `ask_back`/`revise`). In private chat the judge turn asks
`agent_daily_calls` first (the `try_spend` switch, section 5), then reserves a `judge_batch` row with `agent_key`. In a team the turn counts
toward `judge_daily` (the caller passes `payload.judge_daily`). Error, timeout, wrong JSON, engine not ready: `silent` with a code, nothing sent.

### 2.3 Waiting and releasing (7.4)

`wait` writes `waits` with `until_kinds` (`owner_message`, `speaker_done`, `job_change`), `until_ts = decision time + 30 minutes`, `job_refs`
(the agent's open jobs). Released at: `submit` (a new owner message), `_settle_reply_out` (the person speaking settles the turn), `_block`, `_finish`,
`_cancel_records`, `unblock`, when a job is claimed (a job state change), the 5-second loop (expiry), the owner's private chat turn. Releasing is a CAS
`waiting -> released` with a `wait_unblocked` reason (source `wait:<id>`). Re-judged exactly once per (agent, root message): if the re-judge
still chooses to wait, it is `rejudge_limit`. On expiry: if there is an `ask_clarify`, one turn of the agent ITSELF asks the leader/owner exactly one question
(`kind=clarify`), otherwise `silent/wait_expired`. A released wait that has not been re-judged after 120 seconds (a lost background job) is re-judged by the tick loop.

### 2.4 Related review (7.5)

Replaces the T1 clause "an agent's message wakes no one" with a controlled contract: after `_accept` posts agent X's message (still
valid), the host records the message chain (the owner's root message, depth, who woke X), then works out recipients ONLY from structured relations: the recipient
and coordinator of the job of the message, a step whose `input_refs` point to the message, the person who asked for help (the parent step of a `help` step), the command
`{"op": "ask_peer", "agent_key": ..}` (the host checks the asker is the turn's agent and the one asked is another member). Blocked: calling
oneself, the `@` character in text (never a relation), quotes (removed before judging), depth > 2, more than one turn per (agent, root
message), A->B->A, the `judge_daily` cap. Those who pass get a `related_review` reason and go through steps 3-6 of 2.1 (one batch for all recipients
of message X, K counted per message X).

### 2.5 Teaching the judge (7.6)

`label(decision or msg:<id>, should_speak|should_silent|empty, by, at, source)`: a label against the decision shifts the offset of EXACTLY that context (`should_speak` on a silence: -0.05 x 1.5; `should_silent` on a speak: +0.08 x 1.5), clamped to ±0.25, half-life 14 days; a label that agrees only adds
a case. The effect is recorded in `label_effect`: `applied` only when Resonance is on and the label is after `resumed_at`; `stored_only`,
`stored_before_resume`, `stored_direct` (a direct call never teaches the judge). Changing a label first reverses the old part. Removing the axis on a
reaction does not erase a label the owner edited in the history. It does not change content estimates. A message "why didn't you answer?" only adds a hint
`judge_hint` (the latest silent decision within 24 hours) to the owner's message; confirming is editing in the decision history.

## 3. Prompts (sent to the model, kept in Vietnamese)

- Team batch (`build_batch_prompt`): the judge's role (it does not write the answer), each person to judge with their role, eagerness, code signals
  and at most 3 cases of the SAME context, the people already called, the 12 most recent messages OF THIS TEAM in `<chat_data>`, the message to judge, the principles (speak
  only with your own contribution, nobody has to speak to fill a turn), the JSON shape
  `{"decisions":[{"agent_key","verdict","score","reason","wait_for","ask_clarify"}]}`. An id not in the batch is dropped.
- Proactive message (`build_proactive_prompt`): the role, cases of the same context, the history of exactly that context, the draft, the source, the one-item JSON shape.
- The volunteer turn: "Không ai gọi bạn trong tin này; bạn tự lên tiếng vì có đóng góp riêng (...). Chỉ nói phần đóng góp đó" (in English: "No one called you in this message; you are speaking up because you have your own contribution (...). Say only that contribution"). The prompt is Vietnamese on purpose and stays verbatim. The answer is always produced by the agent; the judge's explanation is only the reason in the decision.

## 4. Errors and how they are handled

| Error | Result | Turn ledger |
|---|---|---|
| Engine not ready (thrown before the model call) | `silent/engine_unavailable` | `refunded` |
| Engine error after the call | `silent/policy_error` | `error` (counted) |
| Over 25 seconds | `silent/timeout` | `error` (counted) |
| JSON in the wrong shape, missing people | `silent/bad_json` / `policy_error` | `ok` (the model did answer) |
| Waiting for a slot (2 batches) over 25 seconds | `silent/judge_busy` | `refunded` |
| `judge_daily` / shared ceiling reached (80% for spontaneous turns) | `silent/judge_cap` / `server_ceiling` | no reservation |
| `agent_daily_calls` reached (private chat) | `silent/waiting_quota` | no reservation |
| Calling the batch again for the same message | returns the old decision | `ReasonBusy`, no second turn |
| Background job lost while releasing a wait | the tick loop re-judges after 120 seconds | |
| Judge store error in `_accept`/`submit` | logged; the team turn and the owner's message are not broken | |

A direct call never depends on the judge: the reply turn runs first, and a judge failure only makes candidates silent.

## 5. Join points with parts P and L

- P calls `agent_judge.judge_proactive(...)` before sending the `say` message of a scan turn (passing `payload={"judge_daily": ...}` if the context
  is a team). If the result is `wait`, P does NOT send; when the wait is released, the judge re-judges and calls the sender P registered with
  `agent_judge.register_sender(fn)` with `fn(decision, payload, mode)`, `mode` = "send" | "ask_clarify".
- P serves the `related_review` and `wait_unblocked` reasons with `agent_judge.serve_reason(reason_id)` (the judge re-judges itself; a team's
  reason has already been closed `served` by the judge batch itself, so usually nothing is left). P does not run its own turn for these two kinds.
- P registers the view: `main._register_judge_view_part()` calls `agent_pulse_host.register_view_part("judge", fn)` when the module exists
  (lazy load, skipped if absent); `fn(agent_key)` returns `Judge.view(...)`. Page side: `window.JavisPulseParts` has the part
  `{name: "judge", render(part, el, {slug})}`.
- P and J share `agent_pulse.apply_policy_change(store, agent_key, context_ref, change)` (lazy load, `agent_pulse.default_store()`
  if present): J calls it when a label shifts the threshold, on `set_offset`, `set_eagerness`.
- L calls `agent_judge.set_offset`, `set_eagerness`, `get_profile`, `decisions`; reads/writes `review_state` through
  `default().store().last_review_at / set_review_at`.
- L provides `agent_budget.try_spend(agent_key, purpose)`; J calls it through `_default_try_spend` (lazy load). With no module yet: allowed, and the
  turn is still recorded in the shared turn ledger (where L counts); tests inject a fake `try_spend`. The purposes J uses: `proactive_judge`, `wait_unblocked`.
- L writes `ask_back`/`revise` in a team: it calls `judge_proactive` with `context_ref = team:<id>` like P.

## 6. Migration and rollback

- New store `agent_judge.sqlite3`, created on first use. No `.pre-0.156.0` (there was no store before). Old stores do not change schema:
  `team.sqlite3` only gains keys in `caps_json` (an old version carries the unknown keys in `caps` but does not read them) and the role
  `member_volunteer` in `team_turns` (an old version only reads the role string for display).
- Rollback: `tools/team_adaptive_restore_pre.py --to 0.156.0` (or `--to 0.154.0`) sets `agent_judge.sqlite3` aside as
  `.post-*` and then removes it from the running location (the `absent` row in `MILESTONES`). J adds no table to `resonance.sqlite3`; the
  `judge_batch` rows and the `related_review`/`wait_unblocked` reasons sit in T2's existing tables.
- A downgrade without restore still runs: the old version does not know the judge store; old decisions stay where they are.

## 7. Tests

`tests/python/test_agent_judge_team.py`, `test_agent_judge_dm.py`, `test_agent_judge_labels.py` (with routes through `main.py`, real-engine
guard), `test_related_review.py`, `test_agent_judge_scope.py`, `test_agent_judge_waits.py`; `tests/js/test_agent_judge_ui.js`.
The shared world is `tests/python/_judge_world.py` (real stores, fake engine). Fixes made along the way: `test_team_t1_goal.py` (judge_daily has Unlimited),
`tests/js/test_teams_ui.js` (the permission box has 6 cap rows).

## 8. Decisions made along the way

- **Module-level functions are coroutines**: `judge_team_message`, `judge_proactive`, `serve_reason` are `async` (model calls). The contract
  was fixed in the same commit.
- **The judge engine receives `started`**: `ask(prompt, purpose, started)`; `started()` records the engine mark right before the model call so a refund happens
  exactly when the engine could not be built.
- **A team's reasons are closed by the batch**: a team's `related_review`/`wait_unblocked` is marked `served` by the judge batch itself (even when the batch fails
  or hits the cap), because a team judge failure must end in silence and not retry against the owner's will. Private chat uses the full `WakeReasons.claim/settle`
  (retry per the T2 lifecycle).
- **A volunteer turn is spontaneous** within the shared ceiling (obligation 0); it still counts toward the team's `daily_turns` like any team turn.
- **The mode when Resonance is off** is set per team (`judge_off_batch` in the team's caps, only the owner edits), because `judge_daily` is also per team.
- **K** at most 5, no Unlimited; Full authority edits within the owner's maximum cap. `judge_daily` follows rule D6 like the model turn cap
  (the batch runs the "aux" background-job model).
- **Threshold when Resonance is off**: the learned offset still applies (the policy is frozen, and still fades with the half-life), new labels are only stored.
- **Extra tables**: `decisions` has `kind`, `root_ref`, `volunteer`, `message_ref`, `features_json`, `excerpt`, `ask_clarify`,
  `label_effect`, `label_delta`; `waits` has `root_ref`, `source_event`, `job_refs_json`, `payload_json`, `reason_id`,
  `release_event`; the table `chains`. No column of section 7.1 was narrowed.
- **A case stores a short excerpt** (<= 200 characters, in `features_json`) to serve as an example in the prompt; read only within the same context.
- **`GET /agents/{slug}/judge` was added** so the team member row loads exactly one context, independent of part P; P's pulse panel
  uses the same `Judge.view`.
- **Decision cleanup**: every hour, drop silent decisions older than 90 days with no label, no message, and not waiting.

### 8.1 Fixes after the T3 review (branch `claude/team-adaptive-t3-fix`)

- **The test guard has no detour (P2-2)**: `Judge._run_engine`/`_run_engine_claimed` refuse every asking function when
  `JAVIS_NO_REAL_JUDGE_ENGINE == "1"`, except one marked `mark_test_fake`; the variable is set in `tests/run.py`, `_paths.py`,
  `test_adaptive_context_phase8.py` and the A5 dry pilot.
- **The pulse `say` turn (P1)**: does not pass `engine`, has `payload` (the team's `judge_daily`). An error thrown before `started()` refunds the ledger row
  and comes out as `engine_unavailable` (does not count toward the cap).
- **Clarifying question in private chat (P2-3)**: the host sends a fixed sentence; the model's `ask_clarify` text lives only in the decision history. In a
  team, the hint goes into the agent's own `member_volunteer` turn in the `<chat_data>` block.
- **Retrying a volunteer turn (P2-4)**: `demote` keeps `features.volunteer_origin`; Retry reruns exactly that decision (keeping `clarify`),
  and on success `restore_volunteer` (back to `speak`, attaching the message).
- **P3**: a label stores the shift actually applied after clamping; a private chat re-judge takes the reason first and only then asks for quota (if not enough, refund); a released
  wait older than 30 minutes expires at `tick`; a reason is closed on the duplicate-call path, a paused team, a cancelled wait; learned cases are in
  `<chat_data>`, the volunteer turn does not carry the judge's `reason`; "one turn per (agent, root message)" is also kept by an in-process
  locked ledger.
- **A wait of a proactive message in a TEAM** (round 2 P2-1): a wait that has a draft and no `message_id` is re-judged exactly once as in
  private chat (`_proactive_wait`): CAS `released -> rejudged`, close the reason, `judge_proactive(rejudge_of=...)` with the team's `judge_daily` cap
  (does not ask the agent's daily quota), on `speak` it sends through `_judge_send` -> `_pulse_post` (scope already checked). A team batch wait whose team or root message no longer exists:
  a visible `silent/wait_cancelled` decision.

## 9. Evidence (branch `claude/team-adaptive-t3-judge`, checked head `1049027e`)

- `tests/run.py judge related team feedback agent_calls i18n icons route_table`: 43/43 green (439 seconds).
- `tests/run.py --js`: 193/193 green (76 seconds).
- **Incident fixed:** before `1049027e`, a harness through `main.py` (`test_team_t1_goal_host.py`, run right after wiring the new host)
  built a real judge engine and called the Claude CLI ONCE (claude-opus-5-5, 122 output tokens, 15/10/2026 11:16 +07). Cause: the old
  harness only replaced the team turn engine, while the judge batch used the background-job model. Fix: `tests/python/_paths.py` sets
  `JAVIS_NO_REAL_JUDGE_ENGINE=1` for every Python test, `main._agent_judge_ask` throws `EngineUnavailable` before building the engine (the turn
  is refunded, the candidates stay silent); regression check in `test_agent_judge_labels.py`. Two full runs after that created no new
  `agent_judge_cwd` folder.
- Fixed at the same time: `team_runner.run_io` spun forever when the side-thread task itself was cancelled as the event loop closed (hanging `test_team_api`);
  `TeamRunner.wait_jobs` also waits for the judge's background jobs.


## 10. Performance

The judge batch no longer reads/writes the store on the event loop (the preparation and the settle part run through `run_io`, only the model call waits on the
loop; a cancel right after reserving refunds the ledger row). Details, before/after numbers and tests: [team-chat-t3-pulse.md](team-chat-t3-pulse.md)
section 9.
