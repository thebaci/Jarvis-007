# T3 contract: module boundaries between the adaptive pulse, the judge and in-team learning (0.156.0)

T3 follows `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` sections 5 to 10, split into three parts built in parallel and then joined. This file locks
the public functions between the three parts, so each part calls the others through exactly one place. If a signature changes, edit this file in the same commit. Every model turn goes
through T2's shared turn ledger (`agent_calls`, reserved before the engine, sections 3.1 and 9.1) and the per-agent busy lock (3.4).

## 0. Who does what

| Part | New modules | Tables | Notes |
|---|---|---|---|
| P (pulse) | `server/agent_pulse.py` (pure policy `pulse.v1`), `server/agent_pulse_host.py` (30-second beat, wake-ups, scans) | `agent_pulse` (exists since T2, extended), `agent_pulse_events`, `pulse_signals`, `pulse_contrib`, `message_seen`, `pulse_opportunities` in `resonance.sqlite3` | sections 5, 6, 10 (pulse part) |
| J (judge) | `server/agent_judge.py` (pure), `server/agent_judge_store.py` | new store `agent_judge.sqlite3` | sections 7, 10 (judge part), 9 (`judge_daily`, `K`) |
| L (learning) | `server/agent_lessons.py`, `server/agent_review.py` (reaction review turn 4.4, self-review 8.3), `server/agent_budget.py` | `agent_lessons`, `agent_lesson_events`, `agent_peer_feedback` in `resonance.sqlite3` | sections 4.4, 8, 6.4, 9 (`agent_daily_calls`), 10 (lessons part) |

Each module creates its own tables (`CREATE TABLE IF NOT EXISTS` on the same store path) so the three parts do not edit one schema block together.
The hooks into `main.py`, `team_runner.py` and `resonance_heartbeat.py` stay short: one call to a public function below.

## 1. Pulse (P) provides

- `agent_pulse.record_signal(store, *, source_ref, agent_key, context_ref, kind, value, w, share=1.0, reactor="", emoji="",
  reasons=(), at=None) -> bool`: writes `pulse_signals`, idempotent by `(source_ref, agent_key)`. T2's projector calls this function at the hook
  that is currently a no-op. An agent's own reaction never calls it.
- `agent_pulse.supersede_signal(store, source_ref, by_ref)` and `void_signal(store, source_ref)`.
- `agent_pulse.wake(store, agent_key, context_ref, why, at=None)`: wake again per 5.2 (`min(tier, B3)`), used for a direct call, a newly assigned
  job, a new valid reaction, a related event.
- `agent_pulse.set_state(store, agent_key, context_ref, state, by)` for `paused`/resume, `waiting_owner`, `off` (turning Resonance on/off goes
  through here and writes `resumed_at`).
- `agent_pulse.view(store, agent_key) -> dict` for `GET /agents/{slug}/pulse`.
- `agent_pulse.apply_policy_change(store, agent_key, context_ref, change)` / `revert_policy_change(...)`: the policy version and the observation
  window of 6.4 (the L learner calls it when it applies a change itself, the J judge calls it when a label shifts the threshold).
- Wake-ups (P owns): a code step, the opportunity list, a `scan` turn with the output `{"action": "none"|"propose"|"enqueue"|"say", ...}`. The
  `say` action calls `agent_judge.judge_proactive(...)` (J) before sending.

### 1b. Plug points already in part P (details: `docs/dev/team-chat-t3-pulse.md` section 7)

- `agent_pulse_host.register_view_part(name, fn(store, agent_key))`: the J/L section in `GET /agents/{slug}/pulse` (key `parts`);
  on the page side `window.JavisPulseParts.push({name, render(view, null, {slug})})` (`agent-pulse.js` calls `render(view, null, {slug})`).
- `agent_pulse_host.register_reason_handler(code, fn(host, reason))`: serves `reaction_review` (L), `related_review` and
  `wait_unblocked` (J); the function itself calls `WakeReasons.claim(..., try_busy, release_busy)` with `host.busy_pair(agent_key)`.
- `judge_proactive(..., origin="pulse", payload={"judge_daily", "source_ref"})`: the host does NOT pass `engine` (the judge uses its own
  model-asking path; fix from T3 review J P1: before, the host passed a zero-argument lambda, the wrong signature, and every `say` became silent).
  `judge_daily` is taken through `runner._judge_caps` (Full authority overrides correctly). The host calls `agent_budget.try_spend(agent_key, "scan", at)` before
  reserving the scan turn.
- Projector: `FeedbackProjector.record_task_event(event, context_ref=, agents={key: share}, source_ref_=)`, `pulse_wake`,
  `void_task_event`.

## 2. Judge (J) provides

Details and reasons: [team-chat-t3-judge.md](team-chat-t3-judge.md). The three functions that call the model are coroutines (`async`).

- `await agent_judge.judge_team_message(ctx) -> list[Decision]`: filter with code, then one batch (purpose `judge_batch`), `K` people volunteer. `team_runner` calls it after the reply turns
  for the team owner's message (`run_message`) and after `_accept` (the related review turn 7.5).
- `await agent_judge.judge_proactive(*, agent_key, context_ref, draft, source_event, engine=None, origin="", payload=None) ->
  Decision`: speak/wait/silent for a proactive message in private chat and in a team. Error, timeout, wrong structure: `silent` with a reason, nothing sent. In a
  team pass `payload={"judge_daily": <cap>}`. `engine`: `async (prompt, purpose, started) -> str`, the background-job model by default.
  Under the test guard `JAVIS_NO_REAL_JUDGE_ENGINE=1`, every asking function (including `engine=` and `ctx["ask"]`) is refused except one marked with
  `agent_judge.mark_test_fake`. An error before `started()` refunds the ledger row (`engine_unavailable`). In private chat, `origin =
  "reaction_review"` spends quota at the `reaction_review` priority.
- `Decision = {"decision_id", "verdict": "speak"|"wait"|"silent", "score", "threshold", "reason", "wait_until", "ask_clarify",
  "silence_code", "kind", "volunteer", ...}`.
- `agent_judge.record_direct(agent_key, context_ref, source_event, *, root_ref="", excerpt="", message_ref="")`: records a decision
  `address=certain` for a direct call (no model).
- `agent_judge.label(decision_id or "msg:<id>", label, by, *, at=None, source="history")` where `label` is `should_speak`/
  `should_silent` (empty removes it): shifts the offset by context (±0.25, half-life 14 days), adds a case; only when Resonance is on and the label is after
  `resumed_at` does it change the threshold. The `axis` of T2's reaction calls this function through the projector (`source="reaction"`).
- `agent_judge.set_offset(agent_key, context_ref, value, source)`, `set_eagerness(agent_key, value, source)`, `get_profile(agent_key)`:
  the L learner calls them when self-review applies `offset_set`/`eagerness_set`.
- `agent_judge.release_waits(context_ref, event) -> list`: releases waits and creates a `wait_unblocked` reason; called from `_settle_reply_out`, a job
  state change, the team's 5-second loop (`event.kind` = `owner_message`|`speaker_done`|`job_change`|`tick`).
- `agent_judge.decisions(agent_key, context_ref=None, limit=50)` for the decision history and the correct button; `agent_judge.view(agent_key,
  contexts)` for the "judge" part of the pulse panel.
- `await agent_judge.serve_reason(reason_id)`: P hands a `related_review`/`wait_unblocked` reason to J (it does not run a turn itself).
- `agent_judge.register_sender(fn)`: P/L register the way to send a proactive message when a wait is released and re-judged as `speak`,
  `fn(decision, payload, mode)` with `mode` = "send"|"ask_clarify". For "ask_clarify" the sender does NOT post `payload["ask_clarify"]` verbatim
  (the judge model's wording); the host sends its own fixed sentence (`main._judge_clarify_template`).

## 3. Learning (L) provides

Details and reasons: [team-chat-t3-learn.md](team-chat-t3-learn.md).

- `agent_lessons.add(store, *, agent_key, scope, kind, text, source, source_refs=(), at=None) -> id`,
  `revoke(store, lesson_id, *, by, reason="", agent_key=None) -> dict|None`, `promote(store, lesson_id, *, by ("owner"|"review"),
  evidence_contexts=(), source_refs=()) -> new_id`, `restore(...)`, `for_prompt(store, agent_key, scopes) -> list`,
  `scopes_for(context_ref, agent_key)`, `prompt_block(store, agent_key, context_ref) -> str`: a team turn loads `team:<id>` and `*`, private
  chat loads `dm:<agent_key>` and `*`. `agent_lessons.TeamLearning(store_fn, task_state=...)` is the `learning` dependency of `TeamRunner`.
- `agent_review.ReviewHost(ReviewDeps(...))`, wired once with `agent_review.wire(host)` and then `agent_review.register_with_pulse()`
  (the `reaction_review` handler, the "lessons" section, the revert function for `offset_set|eagerness_set|lesson_add|lesson_remove|lesson_promote`).
  `ReviewHost.tick(agents)` runs before `PulseHost.tick`. `ReviewHost.on_judge_send(decision, payload, mode)` is the sender registered with J
  (accepts only `payload.origin == "reaction_review"`).
- A private chat `JAVIS_LESSON` writes `agent_lessons` with scope `dm:<agent_key>` (no longer into `MEMORY.md`); a team turn's goes to scope
  `team:<id>`; `JAVIS_RULE` is unchanged.
- `agent_review.serve_reaction_review(reason)`: serves the `reaction_review` reason per 4.4 (a structured turn, `consumed ⊆ sources`, state
  from the real host result, writes `agent_pulse_events`).
- `agent_review.maybe_self_review(agent_key)`: 8.3, at most 3 changes from a closed list, applied itself, records before/after, reverts per 6.4.
- `agent_budget.try_spend(agent_key, purpose, at=None, *, store=None, reason_ref=None) -> (ok, reason)` (check only, counted from
  `agent_calls`; `main.py` wires the store with `agent_budget.wire(store_fn)`): the `agent_daily_calls` cap (default 6, the owner has "Unlimited"),
  priority order `reaction_review` > `related_review` > `wait_unblocked` > proactive/scan, keeping 2 turns for the first two kinds. Every turn of P, J
  (except the team judge batch, which counts toward `judge_daily`) and L asks this function before reserving a ledger slot. Cap reached: the reason stays `pending`, status
  "Waiting for quota" (`waiting_quota`).
- The command `{"op": "peer_feedback", "message_id": .., "note": ..}` in an agent turn (the host assigns the source), and the "Teammate feedback" block in the
  next turn in the right team.

## 4. UI

- `GET /agents/{slug}/pulse` (P builds the frame, J and L add their parts through each module's `view`): state and tier per context, the latest
  review, the expected next one, wake reasons, recent pulse changes, handled feedback, lessons by scope with a revoke button (and the label "old lessons
  with no scope yet"), recent speak/wait/silent decisions with a correct button.
- Action routes: `POST /agents/{slug}/pulse/wake|pause|resume|reset`, `POST /agents/{slug}/pulse/revert` (P);
  `POST /agents/{slug}/judge/label` (J); `POST /agents/{slug}/lessons/{id}/revoke` (L). Success is shown only after the host returns 200.
- `POST /seen {context_ref, message_ids}` (P) and the page side: an agent's message counts as seen when it is in view for at least 1.5 seconds while the tab is visible.
- T1's limits table adds `judge_daily`, `K`, `agent_daily_calls`, `max_tier`, the 20% reserve.
