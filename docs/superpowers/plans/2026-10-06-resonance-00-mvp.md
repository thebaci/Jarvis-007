# Jarvis 007 Resonance MVP Implementation Plan

**Current implementation plan.** Read it together with the [final catalog](../README-RESONANCE.md) and the [latest review](../specs/2026-10-06-resonance-revised-package-review.md). Claude's code appendix is an unaccepted sample, kept in the historical package; it is not a parallel implementation roadmap.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans when the user requests implementation. Steps use checkbox (- [ ]) syntax. This is the priority plan after the second round of challenge; do not launch agents or background work just because this document exists.

**Goal:** When a need calls for pursuit, the agent turns it into a goal on its own, carries it out, verifies the result and improves its method within the budget, with minimal coordination work from the user.

**Architecture:** A thin layer connecting the existing conversation/engine to the existing SQLite and EvidenceStore. Three new core modules: resonance.py holds the data types, routing, goal formation, the two evaluators and the small execution loop; resonance_store.py holds revision/events/actions/outbox; resonance_api.py connects the API/UI and the existing scheduler. Roles are functions in the same small layer, not yet split into a long list of services.

**Tech Stack:** Python, FastAPI, SQLite, the existing engine adapter, dashboard JavaScript and vi/en i18n. Test with tests/run.py. No agent team, message broker, container, new service or new model account is needed.

**Spec:** [Overall design](../specs/2026-10-06-javis-resonance-design.md), prioritizing sections 2, 4.0, 4.6, 4.7, 6, 8, 10 and 12. Plans 01/02/03 are extension documents, not three concurrent implementation tracks.

## Global Constraints

- Keep the three invariants: permissions never expand on their own; results carry evidence; the user can intervene and history is binding.
- Start one agent and one goal per run. No goal tree, team, self-spawned agents or self-modifying code. The number of threads later is configuration, not a base rule.
- Questions, advice and work that finishes immediately do not create a durable goal or Kanban item; feedback attaches to the open goal when appropriate. Do not add a model call to classify every message.
- SMART is an internal check by the agent; there is no SMART form and no step that makes the user approve the goal. Quick feedback is optional and never blocks starting.
- Artifact contract and human confirmation are the first two evaluators; there is no model rubric that scores a win by itself yet. A passing artifact does not by itself prove the need was understood correctly.
- Use the chosen engine and quota, record real usage, do not treat a subscription plan as unlimited or silently switch to a paid API.
- The feature is off by default, enabled once per brain within the trial scope; legacy tasks/loops not attached to a goal keep their old behavior. Do not require reconfiguration per goal.
- Data lives in JAVIS_STATE_DIR; payloads go through the EvidenceStore with retention/quota checks. The current permissions and scope must be checked before an effect; if a mandatory log fails, no new effect is sent.
- No em dash; UTF-8 and LF; UI strings in vi/en. TestClient uses http://127.0.0.1:8080. Follow docs/quy-uoc-dev.md when code implementation begins.
- Before M1, check the latest main from the remote, record the base commit and work on a separate branch. Survey 5b4a9be1 is an old checkout; main as checked on 2026-10-06 is 7d264236 (0.83.2) and already has _reply_policy_sandbox_engine/_reply_policy_ask. Re-probe the signatures and call paths on the actual base commit; do not use old line numbers as a contract.
- The implementer self-tests before handing over for review. Independent review after M1, per PR in M2-M4, then an overall review after M5; fix defects that affect dependent steps before building further. Writer and reviewer must check against the same commit/PR.

## Review Focus

1. Ordinary chat or a plan proposed by the agent turns into background work on its own: M2.
2. The user confirms the understanding but the system reports the output as met; an old card confirms a new revision: M4.
3. The runtime has files but no real matching execution path, or a native tool exceeds its scope: M1, M3.
4. Restart, repeated callback, revision change or exhausted quota creates a repeated effect/model call: M3.
5. A candidate changes the goal or the criteria in order to win: M5.

## Minimal data and shared interfaces

GoalRecord holds an id/brain/owner created by the host, the original request source, revision, understanding/assumptions, criteria, constraints/permissions, remaining budget, schedule and status. This is internal data; the UI only shows the understanding, progress and next step. The first version does not need every field of the extended contract.

An Event has id, goal_id, revision, kind, source, payload_ref and timestamp. Evidence is tied to its source and the resource version. An Action has id, goal/revision/run, intent, status, resources and receipt; the uncertain status is distinct from failed. A unique key and expected_revision/state_version protect redelivered operations. A rotating JSONL is not used as the source of truth.

The types live in resonance.py: RouteDecision (answer_now/task_now/continue_goal/create_goal), GoalRecord, Assessment (met/not_met/unknown), ActionReceipt and GoalDeps. Later extensions use schema migration; do not implement GoalRecord and plan 01's GoalContract set in parallel for the same goal.

GoalDeps provides the configured engine, current permissions, call limits, EvidenceStore, clock, reporting channel and an execution operation with a receipt. The model only proposes; the host confirms the context and changes state. Tool/file data does not become a user command.

## Task M1 Verify the small execution path before building further

**Files:** Create tests/python/test_resonance_mvp_integration.py. Inspect server/main.py, server/aux_engine.py, server/agent_runtime.py, server/evidence_store.py, server/self_improve.py and server/mcp_hub.py. Record the implementation evidence in docs/dev/resonance-mvp-verification.md.

- [ ] Check the latest main and the base commit, re-probe the integration points and function signatures from the real code. Record the SHA and environment in the verification report; do not carry assumptions over unchanged from the old checkout to the implementation branch.
- [ ] Write a harness that takes one simulated input, runs it once through the chosen engine, and gets the output and one receipt the host can observe. A fake engine checks the flow; a real pilot checks integration capability; report the two results separately.
- [ ] Check the existing connection points _workflow_agent_helpers/_run_workflow_step in main.py and the aux_swap/engine adapter path. Do not assume the AgentRunner canary is the live path; do not turn on the canary globally to get past a test.
- [ ] Run python tests/run.py resonance_mvp_integration -v. For the real pilot, use simulated data and the granted quota, and record host/engine, invocation, output, time and the observable permissions. If the engine has no path that fits the scope, record a specific blocked status before building the later layers; do not switch providers on your own.
- [ ] Fix GoalDeps.run_once(goal: GoalRecord, prompt: str, action_id: str) -> ActionReceipt as an adapter to the existing, verified path. There is no new agent runtime; the MVP can let the model generate content and let the host write the output into the granted area instead of granting a shell or arbitrary plugin.

Output: know exactly which path works in the target environment and its limits. A green harness with a fake engine does not replace real pilot evidence.

## Task M2 Routing and self-forming goals

**Files:** Create server/resonance.py, server/resonance_store.py, tests/python/test_resonance_mvp_core.py. Modify server/main.py at the conversation dispatch point verified in M1.

**Interfaces:** route_request(message_ref: str, turn_context: dict) -> RouteDecision; form_goal(message_ref: str, context: dict, deps: GoalDeps) -> GoalRecord; GoalStore.create/revise/get/append_event with a principal, an idempotency key and expected_revision. Functions that use the engine are async; route_request only consumes the routing result and context that already exist.

- [ ] Write test_chat_does_not_create_goal, test_inline_job_stays_inline, test_followup_reuses_goal, test_persistent_request_creates_once and test_proposed_plan_does_not_schedule. Do not use the single phrase "làm cho xong" ("get it done") alone to create background work.
- [ ] Write test_ambiguous_goal_smart, test_user_unsure_discovers and test_no_invented_target_or_deadline. SMART is filled with evidence of recognizing success and a reasonable review point; do not invent targets. The original intent and the assumptions have separate sources.
- [ ] Run python tests/run.py resonance_mvp_core -v, confirm red, then implement. SQLite uses transactions, versions and an outbox; revising the understanding keeps permissions/budget/guard/pause and old results. Do not create a service or a table that serves teams in the MVP.
- [ ] Rerun the tests, check cross-brain and that sending the same message twice does not create a duplicate goal; review and commit.

## Task M3 Execution, evidence and a small schedule

**Files:** Modify server/resonance.py, server/resonance_store.py, server/main.py and the existing scheduler connection point. Create tests/python/test_resonance_mvp_run.py.

**Interfaces:** advance(goal_id: str, event: dict, deps: GoalDeps) -> Assessment; evaluate_artifact(goal: GoalRecord, evidence_refs: tuple[str,...], deps: GoalDeps) -> Assessment; next_wake(goal: GoalRecord, event: dict, now: float) -> dict. The model is called through M1's GoalDeps.run_once, with no client/provider of its own.

- [ ] Write test_done_is_not_success, test_missing_evidence_unknown, test_restart_does_not_repeat_effect, test_old_revision_cannot_finish, test_pause_and_revoke and test_audit_failure_before_effect.
- [ ] Write test_budget_reserved_before_call, test_limit_keeps_checkpoint and test_no_paid_provider_fallback: count every form/run/verify/experiment call; when tokens or the subscription quota cannot be measured, still enforce the real limits on turns and time. Missing data is not recorded as zero cost.
- [ ] Write test_idle_does_not_call_model, test_guard_wakes_without_worker and test_no_source_uses_bounded_review. Instructions about a review only change the schedule; a reaction does not change the frequency. A guard that needs to read only works when a matching adapter and permission exist; state clearly which sources are not yet supported.
- [ ] Run python tests/run.py resonance_mvp_run -v, confirm red, then implement one loop that can resume after a restart: check permissions/reserve resources/save the intent, execute, save the receipt, check the artifact, report and wait. The action path has a lock/lease and idempotency; an uncertain effect must be reconciled.
- [ ] Connect one wakeup type to the existing scheduler, keeping the schedule needed for observation separate from the schedule that calls the worker in the same queue. Reuse the outbox instead of creating a second scheduler. Rerun the tests and pilot one goal with a continuation event, review and commit.

## Task M4 Goal card and feedback with a clear meaning

**Files:** Create server/resonance_api.py, tests/python/test_resonance_mvp_feedback.py, tests/js/test_resonance_mvp_ui.js. Modify dashboard/app.js, dashboard/chat-acts.js, dashboard/console.js, dashboard/i18n/vi.json, dashboard/i18n/en.json, server/main.py and server/sessions.py when needed to link durable messages.

**Interfaces:** POST /goal-requests takes a message_ref; GET /goals/{id}; POST /goals/{id}/feedback takes expected_revision, kind, artifact_ref/criterion_id if confirming an output, and an idempotency key; POST /goals/{id}/commands takes pause/resume/cancel and a revision. The host takes the principal from auth. Kinds: goal_fit_confirmed/goal_fit_rejected/outcome_accepted/outcome_rejected; each kind validates its own payload.

- [ ] Write test_goal_fit_not_outcome, test_feedback_old_revision, test_feedback_cross_brain and test_silence_is_unknown. Clicking "That's right" (Vietnamese: Đúng ý) confirms the understanding; "Meets the bar" (Vietnamese: Đạt yêu cầu) confirms the right product criterion with a revision. It does not drop a guard or create a grant on its own.
- [ ] Write test_reload_keeps_goal_action_links and test_report_replay_same_mid. The message is stored before it is sent, the report key has idempotency at the message store; a crash between the two stores has reconciliation. Do not change the push_to_chat signature while skipping the old caller checks.
- [ ] Run python tests/run.py resonance_mvp_feedback -v and python tests/run.py --js resonance_mvp_ui -v, confirm red, then implement the "What Jarvis 007 is working toward" card (Vietnamese: Em đang hướng tới) and a short action/evidence timeline. Feedback in words is still allowed; no app-wide six-emoji bar is needed.
- [ ] Implement human_confirmation in resonance.py: a verified confirmation only closes the specified criterion that the contract allows, and does not negate objective errors. A missing required confirmation stays unknown/waiting, and does not ask the user to click again on a schedule.
- [ ] Rerun the tests and check the real UI after F5, reconnect, editing the understanding, mouse/keyboard. General undo is not in the MVP; only show "view changes" when there is no verified undo adapter. Review and commit.

## Task M5 One small improvement trial and the release milestone

**Files:** Create tests/python/test_resonance_mvp_trial.py, tests/fixtures/resonance/mvp_cases.json. Modify server/resonance.py, server/resonance_store.py and the M1 verification document. Do not yet create an ExperimentService or a general variant store.

**Interfaces:** compare_methods(goal_id: str, baseline_ref: str, candidate_ref: str, cases: dict, deps: GoalDeps) -> dict; verdict inconclusive/rejected/eligible, with the revision, evidence_refs, usage and scope of applicability. The two method refs are declared configuration, not arbitrarily generated code.

- [ ] Write test_same_goal_and_rubric, test_holdout_not_visible, test_unknown_not_win and test_failed_candidate_not_applied. The host keeps the criteria and the test cases separate; it recreates a simulated snapshot for each run and does not repeat outside effects in order to compare.
- [ ] Write test_one_change_within_budget: baseline/candidate use the same input and resources, with a deterministic artifact checker; a losing result is also saved. Do not create an experiment on your own if the share of resources for exploration is used up, or merely because a timer fired.
- [ ] Run python tests/run.py resonance_mvp_trial -v, confirm red, then implement the narrow comparison. Only change the method ref within existing permissions after verification, keep the old ref to roll back; if the goal has changed revision, re-evaluate applicability.
- [ ] Run python tests/run.py resonance_mvp -v and then the repo's mandatory checks when actually implementing. Pilot with the chosen engine on simulated data; do not record success just because the fake engine is green. Record one passing case, one unknown case and one losing-candidate case.
- [ ] Trial release within the granted scope after there is end-to-end evidence and the ability to turn the feature off. Teams, self-modifying code, supervisor, time-series metrics and general undo only open when there is real need and a separate plan is chosen.

## MVP completion criteria

- [ ] One request that calls for pursuit has gone through the whole loop on a real host: forming its own goal, an action with a receipt, verification, continuing after an interruption and returning the result to the right session.
- [ ] Ordinary chat does not create background work; the user does not need to fill in SMART or confirm every goal.
- [ ] Goal-fit and outcome are separated; it knows how to say there is not enough evidence; human confirmation is neither wasted nor used outside its scope.
- [ ] One method change is tried on the same metric and applied only when there is enough basis within permissions; usage/quota is recorded and can be stopped.
- [ ] Reports only claim the scope that actually ran. Do not call the MVP proven safe for every native tool or for live self-updates.
