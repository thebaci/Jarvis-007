# Jarvis 007 Resonance Runtime Implementation Plan

**Status after the second round of challenge:** reference for the extended architecture. Start with the [single-agent MVP](2026-10-06-resonance-00-mvp.md); the context, evidence and permission parts the MVP needs are built in a narrow scope. Groups, multi-worker transport and general undo are not conditions for the first milestone. Do not build two schedulers or two goal stores when extending.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking. Do not implement just because this document exists.

**Goal:** Let an agent and a group form goals from needs on their own, execute, review their understanding against evidence, adjust the beat, collaborate and continue after an interruption, within the right permissions and resources.

**Architecture:** The goal service uses the existing executor/Kanban/workflow, adding per-goal authorization and an event-based scheduler. A goal has one schedule owner. The group runtime holds a leader epoch and assigns work through child contracts.

**Tech Stack:** Python/FastAPI/SQLite, Jarvis 007's engine adapters and workflow graph, JavaScript dashboard. Use a fake clock and fake executor in tests.

**Spec:** [Overall design](../specs/2026-10-06-javis-resonance-design.md), sections 7 to 10 and 12 to 17. Depends on [Foundation](2026-10-06-resonance-01-foundation.md).

## Global Constraints

- Inherit all Global Constraints and data types of the Foundation plan.
- The beat is the schedule of the next decision, not a performance reward point.
- Self-assignment does not raise permissions/budget; revoking a permission takes effect before the next effect.
- A legacy workflow without a GoalRunContext keeps the current approval process.
- A goal attached to a loop is not started by both the loop timer and the goal scheduler.
- A worker does not drop a user pause or a guard that requires the user on its own.
- MCP/file data does not grant permissions or edit the contract.
- The agent sets and adjusts the inferred part of the goal on its own within the original constraints; no extra user gate for choosing/approving goals is needed. Clarifying intent and granting permission are two separate things.
- Changing the goal does not reset cost, guards, pause or revocation; earlier revisions are not recorded as successes on their own.
- B1 covers B1 to B3 below; after that do C1/C2 in the Evolution plan before B4/B5.

## Review Focus

1. A restart after a tool has taken effect but before the receipt is written must not blindly rerun on its own: B2.
2. A grant revoked while a task is in the queue must be blocked right before the effect: B1, B2.
3. Parent/children competing for budget must not exceed the total: B1, B4.
4. An event storm or two schedulers must not create two runs; a waiting task must not clog the old cron: B3.
5. A leader that dies and comes back cannot commit alongside a new leader; a user pause applies to the whole selected tree: B4, B5.
6. A user who does not know, or does not answer an optional question, must not create an endless question loop; a reframe must not let old actions continue for an expired goal: B2, B3, B4.
7. Context across HTTP, route caches and brains with the same slug must not be attributed to the wrong actor; a text-form tool error must not become a succeeded receipt: B2.
8. A guard must be observed when the worker slows its pace; a chat refresh must keep the right effect links: B3, B5. Undoing a file that was edited further must return a conflict: B6.

## Task B1 Delegation of authority and resource reservation

**Files:** Create server/resonance_authority.py, tests/python/test_resonance_authority.py. Modify server/resonance_store.py, server/resonance_contracts.py.

**Interfaces:**

- GoalGrant(id, brain_id, principal_id, parent_grant_id, capabilities, resource_scope, envelope, generation, expires_at); a frozen type in resonance_contracts.py.
- Authorization(allowed: bool, reason: str, grant_id: str, generation: int, reservation_id: str | None).
- AuthorityService.authorize(context: GoalRunContext, decision: Decision, principal: Principal, now: float) -> Authorization.
- AuthorityService.delegate(parent_id: str, requested: GoalGrant, principal: Principal) -> GoalGrant.
- AuthorityService.reserve(grant_id: str, action_id: str, estimate: ResourceEnvelope) -> str.
- AuthorityService.settle(reservation_id: str, actual: ResourceEnvelope) -> None.
- AuthorityService.revoke(grant_id: str, principal: Principal) -> int returns the new generation.
- AuthorityService.check_effect(context: GoalRunContext, resource: dict, effect: str, now: float) -> Authorization.

- [ ] Write tests that a child asking for extra capability/scope is rejected; expired and wrong-brain are rejected; a legacy full grant does not automatically have self_modify/deploy.
- [ ] Write a test of two concurrent reserve transactions: total spent + reserved does not exceed the original limit; a repeated settle is not counted twice; creating children does not multiply the budget.
- [ ] Write tests that forming a goal needs no new capability; survey/small-trial actions still go through the corresponding grant. A reframe of the same goal or creating a child does not reset spent/reserved, does not open extra resources or drop user constraints on its own.
- [ ] Write tests that an unknown price is not recorded as 0 and is still blocked by the granted token/turn ceiling; an actual that exceeds the estimate blocks the next grants and records the real overrun, without editing usage to fit the ceiling.
- [ ] Run python tests/run.py resonance_authority -v; confirm red.
- [ ] Implement the capability subset and the budget transaction. Grants come from the host, not from a prompt. Check the generation at every effect; policy and budget are versioned configuration.
- [ ] Rerun the tests; PASS when real concurrency is checked with two SQLite connections.
- [ ] Review and commit.

## Task B2 Single-agent execution and effect evidence

**Files:** Create server/resonance_executor.py, server/resonance_run_context.py, tests/python/test_resonance_executor.py, tests/python/test_resonance_run_context.py. Modify server/agent_runtime.py, server/workflow_runtime.py, server/main.py, server/mcp_hub.py, server/mcp_client.py, server/tasks.py, server/task_store.py, server/resonance_store.py, server/resonance_contracts.py.

**Interfaces:**

- ActionReceipt(action_id, status, started_at, finished_at, evidence_ids, external_ref, error_code, invocation_ids); status is succeeded/failed/uncertain/cancelled; defined in resonance_contracts.py. The invocation id is attached to each call and each retry, not inferred from the tool name.
- RunContextRegistry.issue(context: GoalRunContext, ttl: float) -> str; resolve(credential: str, now: float) -> GoalRunContext; revoke(run_id: str) -> None. A short-lived credential tied to the run/grant, issued by the host and generation-checked again before the effect; do not log the credential or put it in chat content.
- The X-Javis-Run header carries the credential to the Hub; X-Javis-Actor, if present, is only for diagnostics, and does not grant permissions or serve as the authoritative source for attribution. An in-process engine uses the resolved context and resets the ContextVar with a token in finally. A legacy request without a goal context keeps the old behavior and must not be attached to another goal on its own.
- GoalExecutor.execute(context: GoalRunContext, decision: Decision) -> ActionReceipt.
- GoalExecutor.reconcile(context: GoalRunContext, action_id: str) -> ActionReceipt.
- Add goal_context: GoalRunContext | None = None and an optional effect_authorizer callback at the end of the AgentRunner.run, WorkflowCanary.run/resume signatures; keep the old positional compatibility.
- EffectAuthorizer: async (context: GoalRunContext, node: WorkflowNode) -> Authorization.
- TaskStore.enqueue gains metadata: dict | None = None at the end of the signature, using the existing metadata_json; goal metadata consists of id/revision/action_id, and does not contain a self-declared grant.

- [ ] Write tests that a Decision act goes through the grant and creates a receipt; a Decision finish only calls evaluate_goal; a run that is COMPLETED but whose assessment is unknown keeps the goal active.
- [ ] Write tests that a legacy workflow write still goes to WAITING_USER; a goal write with a valid grant proceeds; an explicit wait_user always keeps its waiting behavior; a grant revoked after enqueue blocks the effect.
- [ ] Write a test that a CLI backend with a native shell outside the permission gate but with no isolation must not receive an action that needs scope protection. Only switch backends when another backend meets the same grant; otherwise blocked with a reason, and never lower protection silently.
- [ ] Write a test of a crash after an external commit with the receipt not yet written: with an idempotency key, reconcile/retry with the same key; without confirming evidence it is uncertain, and no second effect is created.
- [ ] Write a test of a reframe between enqueue and effect: the old revision emits no more effects; an effect already sent is reconciled and saved under the original revision. A new plan only runs from a valid checkpoint, does not multiply actions or count old results for new criteria on its own.
- [ ] Write test_context_cross_process_and_brain: two runs with the same actor and two brains with the same slug sending in parallel do not mix context; a failed/cancelled request resets the ContextVar; a fake X-Javis-Actor does not receive another's permissions or credit; an expired credential is rejected. A reused discovery cache does not keep an old run context or wrap the ledger repeatedly.
- [ ] Write test_tool_error_content_not_success and test_multiplexed_effect_at_call: ERROR:/isError keeps the error, and the effect is judged by the actual arguments even if the metadata at list time says read. Reads that create evaluation evidence have a receipt/provenance; do not log the whole sensitive payload.
- [ ] Write test_call_route_receives_mapping with a fake route: call mcp_client.call_route(route, fn, arguments), not passing route[fn]; the fake tool must be called exactly once. When the adapter changes how it keeps structured results, run a regression check that the old client still receives text.
- [ ] Write test_required_audit_failure: if the intent/reservation is not saved there is no effect; losing the receipt after an effect leads to uncertain and reconciliation; a failure of secondary telemetry does not fail the chat. Check real crash/timeout, not just chmod, because a permission test may not cause an error on Windows.
- [ ] Run python tests/run.py resonance_executor resonance_run_context -v; confirm red.
- [ ] Implement the adapter to the existing engine/workflow, without creating a second model loop. Record the intent and reservation before the effect; the event/receipt after the effect. The task outbox enqueue uses a stable idempotency key.
- [ ] Clarify and reframe go through the A4 GoalService; changing the revision in the same transaction cancels unsent schedules/actions and the outbox. Release exactly the reservation not yet used; keep the part with an undetermined effect. Old evidence is only reused if the new evaluator checks its fit and freshness, and the old verdict is not reused.
- [ ] Do not drop the existing lease/capability revision checks. The current read-only executor is only used for reads; writes go through the effect_authorizer and the authorized write path. Do not set approved_nodes in bulk just because of full mode.
- [ ] B1 before C4 only allows actions through tools whose scope is enforced by the host. An arbitrary Python plugin in the same process as the host is not a permission boundary; actions that need a shell/candidate code wait for a verified isolation backend.
- [ ] A snapshot after a native tool has written only proves the later state if it is observed enough, and does not create undo ability or certain attribution. Do not claim the Hub wrapper sees every CLI action; a backend whose writes cannot be controlled must keep the limits in section 5 of the spec.
- [ ] Run the new tests and python tests/run.py agent_replan_phase11 workflow_graph_phase10 workflow_runs kanban_snapshot -v; confirm the legacy paths are unchanged.
- [ ] Review and commit.

## Task B3 Event-based beat and continuing after an interruption

**Files:** Create server/resonance_scheduler.py, tests/python/test_resonance_scheduler.py. Modify server/self_improve.py, server/main.py, server/resonance_store.py, server/resonance_service.py.

**Interfaces:**

- BeatScheduler.on_event(event: GoalEvent) -> None.
- BeatScheduler.schedule(goal_id: str, revision: int, plan: WakePlan) -> str.
- BeatScheduler.schedule_observation(goal_id: str, revision: int, due_at: float, source_ref: str) -> str; the observation wakeup type uses the same store/lease, only collects data within the grant, and does not call a worker/model by default.
- BeatScheduler.tick(now: float) -> list[str] returns the run ids that were dispatched.
- BeatScheduler.cancel_tree(goal_id: str, principal: Principal, reason: str) -> None.
- decide_next_wake(snapshot: GoalSnapshot, assessment: Assessment | None, decision: Decision | None, now: float) -> WakePlan.

- [ ] Write fake clock tests: with no event/deadline due, the model is not called; waiting wakes on exactly the right event; dormant receives a matching event; paused does not wake on its own.
- [ ] Write tests that two schedulers claiming the same wakeup dispatch only once; a repeated event creates only one logical action; an old revision is dropped; an event from the report itself does not create a self-triggering loop.
- [ ] Write a test that a loop attached to a goal drops the legacy schedule for exactly that loop, while other loops and reminders still run; one long task does not block the tick.
- [ ] Write tests that user_unsure moves to a discover step still within permissions; an open optional question does not block an independent step. No response is not treated as granting permission; a question missing essential data only blocks the dependent part. Do not ask again about the same unknown without new evidence.
- [ ] Write a test that once there is enough new data, reframe happens once with a reason; a timer or a notice generated by the agent itself does not cause a chain of goal changes. When the discovery budget is used up or no useful step remains, return the current result and waiting/dormant with clear wake conditions, and do not call the model continuously.
- [ ] Write test_guard_without_agent_action_stops and test_guard_observed_while_worker_dormant: when the stop condition is true, block the declared scope even if the cause is not determined; the observation cadence does not depend on points, the number of actions or the worker's sleep interval.
- [ ] Write test_guard_unknown_policy, test_guard_latched_resume and test_observation_revoked: a missing source does not become clear; a good sample does not drop a latch that needs the owner; withdrawing observation permission stops reading and reports lost monitoring. Alert dedupe and the anti-oscillation policy do not lower a stop condition that was already set.
- [ ] Run python tests/run.py resonance_scheduler -v; confirm red.
- [ ] Implement leases, coalescing and the outbox. earliest_at must not exceed the contract deadline when the deadline needs to be checked; an invalid timestamp returns an error with a reason. Versioned technical limit configuration, not tied to reaction points.
- [ ] Handle blocked by reason: source_reconnected/budget_replenished only reopen on their own when the contract allows it; user_pause/guard_requires_owner do not reopen on their own. Guard and completion notices are deduped by goal/revision/event.
- [ ] Store the clarification id, required_for, fallback, the answer and the assumptions tried. A versioned policy decides the time spent on questions/discovery by context and the remaining share of resources, and the number of questions is not set as a fixed system-wide rule. Waiting for an optional answer still lets independent work run; when time runs out, permissions do not change on their own.
- [ ] Separate the observation wakeup from the worker wakeup in the same queue; keep the monitoring resources per grant. Only take the evaluation time after the await that collects the new sample, and do not drop a new sample because it used a timestamp taken before the tool call. A source's existing schedule keeps its data semantics even if the worker changes pace.
- [ ] Run the new tests and python tests/run.py loop_goal_default loop_ambient kanban_het_luot -v.
- [ ] Review and commit. At this point move on to Tasks C1 and C2 to verify one small self-improvement loop.

## Task B4 Groups and child goals

**Files:** Create server/resonance_groups.py, tests/python/test_resonance_groups.py. Modify server/resonance_store.py, server/resonance_contracts.py, server/resonance_executor.py.

**Interfaces:**

- GroupState(id, brain_id, goal_id, leader_id, epoch, members, status); defined in resonance_contracts.py.
- GroupService.create(goal_id: str, leader_id: str, members: tuple[str,...], principal: Principal) -> GroupState.
- GroupService.delegate(group_id: str, child: GoalContract, principal: Principal) -> GoalSnapshot.
- GroupService.contribute(group_id: str, actor_id: str, kind: str, evidence_ids: tuple[str,...], content: str) -> str.
- GroupService.commit_decision(group_id: str, epoch: int, decision: Decision, principal: Principal) -> None.
- GroupService.replace_leader(group_id: str, expected_epoch: int, new_leader_id: str, principal: Principal) -> GroupState.
- Contribution kinds: proposal/objection/evidence/decision/ack; the kind only describes the conversation and is not a reward.

- [ ] Write tests that a child goal is in the same brain, with a subset of permissions, budget from the parent, no cycle; all children done but the parent criterion not met means the parent stays active.
- [ ] Write tests that an old leader committing after a failover is rejected; a duplicate contribution does not multiply evidence; the leader does not edit the scoring of a running experiment or raise a grant on its own.
- [ ] Write tests that a silent member is not docked capability; an event only calls the relevant subscription; the whole group can stop to wait for the user within the right scope.
- [ ] Write tests that a leader sets child goals itself from the parent need; a rebuttal with evidence leads to a reframe through GoalService. When the parent changes revision, related children recheck before an effect; a child does not change its goal to hide that it does not contribute to the parent. The group sends only one combined question and continues the independent part when the user does not know.
- [ ] Run python tests/run.py resonance_groups -v; confirm red.
- [ ] Implement durable membership with a leader epoch. Do not use the classification field group in workspace.js as the group runtime id. Do not force every member to run each round.
- [ ] Connect delegation through GoalService and AuthorityService; group discussion uses the shared run budget, and may choose its own number of rounds within the granted share.
- [ ] Pin the parent revision and the related IntentRecord in the assignment metadata; store contributions to goal formation along with the evidence. The leader epoch protects the reframe decision as well, not only the execution decision. Child goals and discovery use the same original resources.
- [ ] Rerun the tests and the regressions nhom_agent_workflow, agent_replan_phase11; review and commit.

## Task B5 Activity UI and group controls

**Files:** Modify dashboard/resonance.js, dashboard/workspace.js, dashboard/console.js, dashboard/app.js, dashboard/chat-acts.js, server/main.py, server/sessions.py, server/resonance_store.py, server/resonance_api.py, dashboard/i18n/vi.json, dashboard/i18n/en.json, docs/22-muc-tieu-va-resonance.md, docs/en/22-goals-and-resonance.md. Create tests/js/test_resonance_runtime_ui.js, tests/python/test_resonance_runtime_api.py, tests/python/test_resonance_message_links.py.

**Interfaces:** Added API POST /goals/{id}/run-now, GET /goals/{id}/actions, GET /goals/{id}/wake-plan, POST /goals/{id}/stop-tree, POST /goal-groups, GET /goal-groups/{id}, POST /goal-groups/{id}/contributions. Principal and expected_revision/epoch follow the same rules as A4.

- GoalStore.link_message(link: MessageLink, principal: Principal) -> None; message_links(brain_id: str, session_id: str, message_ids: tuple[int,...], principal: Principal) -> list[MessageLink]. Idempotent by report_key/run, checking that the session and message belong to the permitted brain.
- The response/push frame and the history-reading API return the mid along with the run/action link; the dashboard keeps it across the live stream, restored data and F5. Do not change the push_to_chat bool into an int without checking every caller; add a report-sending path with a receipt in the adapter or an explicit compatible result type.
- A report has a durable report_key, stores the message before sending and records the link with reconciliation. The sessions store and the resonance store are two separate stores: an idempotency key in the message store and reconciliation after a crash are needed, and it is not faked as one shared transaction with just two consecutive writes. A failed publish is replayed with the same mid and does not create a new message.

- [ ] Write tests of the running/waiting/blocked/paused/dormant states and reasons; do not show queued as running; stop-tree displays the right scope.
- [ ] Write tests that resources not yet measured display as unknown, not 0; the current classification group does not automatically have autonomy.
- [ ] Write tests of editing the understanding through conversation, an "I don't know" reply and a change-of-direction notice with a reason. The UI does not switch to making the user pick a goal when the planner meets uncertainty; it does not report the need as resolved just because a discovery step finished.
- [ ] Write test_reload_restores_action_links, test_report_retry_same_mid, test_message_link_cross_brain and test_two_runs_same_actor: live/F5/reconnect keep the right message and effects; do not attach by the actor in the last 10 minutes. A link lost to a crash is reconciled; a session_id received from the client is not accepted as proof of owning a message.
- [ ] Run python tests/run.py resonance_runtime_api -v and python tests/run.py --js resonance_runtime_ui -v; confirm red.
- [ ] Implement the decision/evidence timeline and understanding changes, group conversation attached to the goal, stop/resume buttons, and the reason for the next wake. The "What Jarvis 007 is working toward" card (Vietnamese: Em đang hướng tới) distinguishes assumptions from user instructions and allows editing in words. Report important events to the right owner_chat through the existing report path; do not require approving each revision.
- [ ] Run the tests, check the dashboard with a real fixture on wide/narrow screens, and check that refresh/reconnect does not lose state or send duplicates.
- [ ] Update the guide, review and commit.

## Task B6 Conditional file undo, optional after the demo milestone

This task is only needed when releasing an undo button; it does not block the first goal loop. Undo creates no default performance penalty.

**Files:** Create server/resonance_undo.py, tests/python/test_resonance_undo.py. Modify server/resonance_executor.py, server/resonance_store.py, server/resonance_api.py, dashboard/resonance.js, dashboard/chat-acts.js, dashboard/i18n/vi.json, dashboard/i18n/en.json.

**Interfaces:**

- FileUndoAdapter.capture_before(context: GoalRunContext, resource_ref: str) -> str returns an encrypted evidence ref; record_after(action_id: str, before_ref: str, after_version: str) -> None.
- FileUndoAdapter.preview(action_id: str, principal: Principal) -> dict returns available/conflict/expired/unsupported, a reason and a diff_ref within the permitted read scope.
- FileUndoAdapter.undo(action_id: str, expected_after_version: str, principal: Principal, key: str) -> ActionReceipt; returns a new effect/action linked to the original action. The API GET /actions/{id}/undo-preview and POST /actions/{id}/undo use permission checks, expected version and idempotency.

- [ ] Write test_undo_changed_file_conflicts, test_undo_created_then_edited_not_deleted, test_undo_cross_brain_denied and test_undo_symlink_escape: no change made after the action is lost, and nothing leaves the scope.
- [ ] Write test_undo_concurrent_requests_once, test_undo_crash_reconciles and test_undo_missing_backup: no compensation twice, and an expired snapshot is not shown as undoable.
- [ ] Run python tests/run.py resonance_undo -v; confirm red.
- [ ] Implement snapshots through EvidenceStore, content/version preconditions, a lock/CAS per backend and a durable receipt. If protection against an outside editor changing the file between the check and the write cannot be proven, create a separate recovery copy for comparison and do not overwrite the original file. Only an adapter that already has undo ability provides the button; a read/write/danger classification is not enough.
- [ ] Rerun the tests and check the UI after F5, two concurrent requests, and a file the user edited further. Only open the button when it passes, update the guide and commit.

## Phase B acceptance

- [ ] One agent completes a goal on its own through real events, with confirming evidence independent of the message.
- [ ] A restart between steps does not repeat a confirmed effect; an unclear effect is reconciled.
- [ ] A group can assign and commit; a leader change does not run two commit threads.
- [ ] A user being away does not make the system lower its own capability; pause/revocation take proper effect.
- [ ] The agent/group finds goals itself from vague input, adjusts with grounds and moves revisions without repeating effects. A user who does not know does not cause repeated questions or exceed permissions; a discovery goal is not reported as the final result.
- [ ] The schedulers/permissions of legacy tasks that have not joined are not replaced.
