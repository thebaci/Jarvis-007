# Jarvis 007 Resonance Foundation Implementation Plan

**Status after the second round of challenge:** reference for the extended architecture. Start with the [single-agent MVP](2026-10-06-resonance-00-mvp.md); do not implement this whole plan before the demo. Paths already built in the MVP are reused, not duplicated. The interfaces/data types below are reconciled and migrated when extending.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking. Only choose an execution method after the user decides to implement; this document does not launch background work.

**Goal:** From a need expressed in natural language, the agent forms and adjusts the goal on its own; it stores a versioned contract, evidence with a source and a domain-independent assessment. The user does not have to pick goals or fill in criteria.

**Architecture:** A goal framer uses the existing engine adapter to interpret the need, raise questions or discovery steps and create the contract. SQLite holds the original input, the understanding versions, the goal status and the outbox; the existing EvidenceStore holds the encrypted payloads. The contract, permissions, evidence and assessment are version-pinned and checked per brain and principal.

**Tech Stack:** The repo's existing Python, FastAPI, SQLite, standard-library unittest, dashboard JavaScript and vi/en i18n. No added agent framework or database service.

**Spec:** [Jarvis 007 Resonance design and goal execution roadmap](../specs/2026-10-06-javis-resonance-design.md), especially sections 2 to 7 and 12 to 17.

## Global Constraints

- The core contains no industry-specific or model-provider-specific conditions.
- Goals, permissions and criteria are versioned; the agent does not raise its own permissions.
- The user hands over the need; the agent is responsible for setting the goal. An interpretation does not overwrite the original instruction; explicit permissions and constraints do not change on the model's guess.
- Ask to reduce significant uncertainty; an "I don't know" answer leads to discovery within permissions, and the user is not made to pick the goal or approve every revision.
- A completed task/workflow does not by itself confirm the goal is met.
- A reaction does not decide performance or permissions.
- New features are off by default; legacy loops/cron keep their behavior until attached to a goal.
- Time is stored as UTC epoch seconds; the UI uses the configured time zone.
- State lives in JAVIS_STATE_DIR; private data does not go into Git or the global prompt.
- No em dash (U+2014); new identifiers are in English, UI strings in vi/en. Text files are written as UTF-8 and LF. TestClient uses base_url http://127.0.0.1:8080 to go through web_security exactly as the existing tests do.
- The optional communication log may fail while chat continues; a failure of the mandatory ledger must not be faked as saved. Do not use an actor slug or closeness in time in place of a brain/run/action identity.
- Use tests/run.py to run tests; new tests use unittest and call unittest.main when run directly, following the import path tests/python/_paths.py.
- Follow docs/quy-uoc-dev.md when implementing code; do not set a release version just for this plan.

## Review Focus

1. An evaluation that uses evidence belonging to another brain or revision must be blocked, without returning sensitive metadata: A2, A3, A4.
2. A contract update in the middle of an evaluation must not use the old result to close the new revision: A1, A4.
3. Repeated/late/corrected events must not create two independent results: A2, A3.
4. An expired evidence payload, or one deleted by the user, must become unavailable/unknown: A2, A3.
5. Qualitative criteria have no fake percentages; an evaluator error is not counted as a goal failure: A3, A5.
6. An agent that sets the wrong goal, asks repeatedly or lowers the criteria to claim success must be caught in a fixture: A1, A4, A5.
7. A metric containing ids/dates/errors, late samples or a changing sampling cadence must not make the conclusion wrong. A stable metric is not equated with unreliable data: A3.

## Shared data type contract

Create frozen dataclasses in server/resonance_contracts.py; serialize through explicit functions, and do not serialize permissions from an object the model sent itself.

| Type | Required fields and meaning |
|---|---|
| Principal | id: str; brain_ids: frozenset[str]; capabilities: frozenset[str]. Created by the host from the existing auth |
| CriterionSpec | id, description, evaluator_ref, evaluator_revision: str; parameters, evidence_selector, acceptance: dict |
| IntentRecord | id, brain_id, source_message_ref, author_id: str; revision: int; explicit_constraint_refs: tuple[str,...]; received_at: float; supersedes_id: str or None. The host keeps the input record with its source; the user origin must be authenticated |
| GoalFraming | stage: discovery/delivery; assumptions, unknowns, alternatives: tuple[dict,...]; evidence_refs, constraint_refs, unresolved_conflicts: tuple[str,...]; rationale, reconsider_when: str. The dicts have their own schema; a classification from the model is still an interpretation that can be wrong |
| Clarification | id, intent_ref, question, impact, fallback: str; required_for: tuple[str,...]; status: open/answered/user_unsure/superseded; answer_ref: str or None. Distinguishes clarifying a preference from a request to grant permission |
| FramingResult | intent_ref: str; framing: GoalFraming; proposed_contract: dict or None; clarification: Clarification or None; next_step: proceed/discover/clarify/blocked; reason: str |
| GoalContract | id, brain_id, owner_id, intent_ref, intent: str; revision: int; framing: GoalFraming; mode: achieve/maintain; criteria: tuple[CriterionSpec,...]; criteria_mode: all/any; guards: tuple[CriterionSpec,...]; authority_ref: str; resources, timing, communication: dict; parent_goal_id: str or None; dependencies: tuple[str,...] |
| GoalSnapshot | contract: GoalContract; status: draft/active/succeeded/failed/cancelled; run_state: ready/running/waiting/blocked/paused/dormant; state_version: int; reason: str |
| EvidenceEnvelope | id, brain_id, goal_id, source, source_event_id, resource_ref, content_hash, evidence_ref, trust_class: str; contract_revision: int; observed_at, received_at: float; action_id, resource_version, supersedes_id: str or None; freshness: dict |
| CriterionResult | criterion_id: str; verdict: met/not_met/unknown; evidence_ids: tuple[str,...]; confidence: low/medium/high; rationale: str; error_code: str or None |
| Assessment | id, goal_id, brain_id, evaluator_revision: str; contract_revision: int; criterion_results: tuple[CriterionResult,...]; verdict: met/not_met/unknown; guard_status: triggered/clear/unknown; confidence: low/medium/high; rationale: str; evaluated_at: float; next_observation_at: float or None |
| GoalEvent | id, brain_id, goal_id, source, source_event_id, kind: str; contract_revision: int; occurred_at, received_at: float; payload: dict |
| ResourceEnvelope | limits: dict[str,int or float]; units: dict[str,str]; accounting_policy: dict. Every number finite and non-negative |
| WakePlan | reason, policy_revision: str; earliest_at, observation_due_at, expires_at: float or None; wake_on: tuple[str,...] |
| Decision | id, goal_id: str; contract_revision: int; kind: act/delegate/experiment/clarify/reframe/wait/escalate/finish; rationale: str; payload: dict; resources: ResourceEnvelope; wake: WakePlan |
| GoalRunContext | goal_id, brain_id, run_id, actor_id, authority_ref: str; contract_revision, grant_generation: int; action_id, lease_id: str; turn_id: str or None. Fully confirmed by the host; the separate invocation lives in the evidence/receipt metadata |
| MessageLink | brain_id, session_id, run_id, report_key: str; message_id: int; action_ids: tuple[str,...]. Links effects to the correct turn, not inferred from time |

Later modules import exactly these types. Extension fields owned by an adapter go in parameters/metadata with their own schema; no business names are added to GoalContract.

## Task A1 Versioned contract and state transition rules

**Files:** Create server/resonance_contracts.py, tests/python/test_resonance_contracts.py.

**Interfaces:**

- validate_contract(raw: dict) -> GoalContract.
- validate_child(parent: GoalContract, child: GoalContract) -> None.
- transition(snapshot: GoalSnapshot, event: GoalEvent, assessment: Assessment | None) -> GoalSnapshot.
- Errors: ContractValidationError, RevisionConflict, AuthorityError; placed in resonance_contracts.py and reused.

- [ ] Write tests for met/not met/unknown, finite numeric values, all/any, parent in the same brain, dependency cycle, achieve/maintain, and pause being kept before ordinary events.
- [ ] Write the regression test_task_done_is_not_goal_success: a task.completed event without a met Assessment keeps the status active; test_maintain_met_stays_active keeps the status active when the condition is met.
- [ ] Write tests that a passing discovery only requires reviewing the target or completing the discovery sub-goal, and does not close the original need on its own; unresolved_conflicts prevent claiming the need is resolved. An agent changing the framing does not edit the IntentRecord and does not erase the history of results or pause.
- [ ] Run python tests/run.py resonance_contracts -v; confirm the new tests fail because there is no implementation yet.
- [ ] Implement pure validate and transition, with no I/O. A transition may only close a goal when the assessment is for the same goal/brain/revision, guards are clear, no unresolved_conflicts remain, and a discovery result is not used to close the original need; the planner's finish is not enough. Distinguish research that is the product the user asked for from an intermediate survey to find the target.
- [ ] Rerun the tests. PASS when every case is accepted/rejected correctly and does not depend on the model or the network.
- [ ] Review the diff, then commit the task on its own after the tests are green.

## Task A2 Goal store and evidence links

**Files:** Create server/resonance_store.py, server/resonance_evidence.py, tests/python/test_resonance_store.py, tests/python/test_resonance_evidence.py. Modify server/evidence_store.py, server/context_runtime.py to support retaining evidence that is being referenced.

**Interfaces:**

- GoalStore(path: Path); create(contract: GoalContract, principal: Principal, key: str) -> GoalSnapshot.
- GoalStore.get(goal_id: str, principal: Principal) -> GoalSnapshot.
- GoalStore.record_intent(record: IntentRecord, principal: Principal, key: str) -> IntentRecord; get_intent(intent_id: str, principal: Principal) -> IntentRecord. A user revision is tied to an authenticated source; it does not accept a user author that the model declares itself.
- GoalStore.revise(goal_id: str, expected_revision: int, contract: GoalContract, principal: Principal) -> GoalSnapshot.
- GoalStore.append_event(event: GoalEvent, principal: Principal) -> bool, false if source_event_id was already processed.
- GoalStore.record_assessment(assessment: Assessment, expected_state_version: int) -> GoalSnapshot.
- GoalStore.pending_outbox(limit: int) -> list[dict]; acknowledge_outbox(event_id: str) -> None.
- EvidenceBridge.capture(context: GoalRunContext, source: str, source_event_id: str, value: object, metadata: dict) -> EvidenceEnvelope.
- EvidenceBridge.resolve(envelope: EvidenceEnvelope, principal: Principal, now: float) -> object.
- EvidenceStore.pin(evidence_id: str, owner_ref: str, until: float) -> None; unpin(evidence_id: str, owner_ref: str) -> None. Permissions are checked at the bridge; existence and storage quota are checked at the store.

- [ ] Write a test that with two SQLite connections doing revise at the same time only one wins; repeated create and append_event do not create new rows; a crash before acknowledge makes the event be received again without multiplying the effect.
- [ ] Write tests that cross-brain is rejected; supersedes does not delete the old record; pinned evidence is not cleaned up; when the pin ends it returns to the old retention; deletion by the user makes resolve report unavailable.
- [ ] Write tests that IntentRecord keeps its source and the goal revisions reference the right version; editing the understanding does not edit the original input. Questions and answers have linked ids, and being received again does not multiply the question; the input payload follows the same redaction/retention and read permissions as evidence.
- [ ] Write tests that a SQLite error/full disk does not turn create/revise/append_event into a success; two brains with the same slug do not share records. History that is still referenced is not lost to log rotation; a snapshot is restored if the existing EvidenceStore and quota are used.
- [ ] Run python tests/run.py resonance_store resonance_evidence -v; confirm red on the missing behavior.
- [ ] Implement SQLite WAL, BEGIN IMMEDIATE transactions, a unique key by brain/source/source_event_id, optimistic concurrency and an outbox in the same transaction. Store payloads through the existing EvidenceStore.put; create/resume the trace through the real runtime, and do not fake a TurnTrace to skip a check.
- [ ] Add a pin registry in context_runtime and adjust snapshot retention so cleanup respects pins. A pin does not extend indefinitely by default; the duration comes from the contract/experiment. A crash between saving the payload and the link is cleaned up by orphan reconciliation, and a loose payload is not treated as evidence already attached to a goal.
- [ ] Rerun the new tests and python tests/run.py adaptive_runtime_hardening context_runtime_phase01 -v. PASS when the old encryption/redaction/retention is not lost.
- [ ] Review and commit the task.

## Task A3 Evaluation interface and the first two evaluators

**Files:** Create server/resonance_evaluators.py, server/resonance_eval_artifact.py, server/resonance_eval_predicate.py, tests/python/test_resonance_evaluators.py.

**Interfaces:**

- Evaluator Protocol: async evaluate(contract: GoalContract, evidence: tuple[EvidenceEnvelope,...], now: float) -> Assessment.
- EvaluatorRegistry.register(evaluator_id: str, revision: str, evaluator: Evaluator) -> None; resolve(evaluator_id: str, revision: str) -> Evaluator.
- evaluate_goal(contract: GoalContract, evidence: tuple[EvidenceEnvelope,...], registry: EvaluatorRegistry, now: float) -> Assessment.
- artifact_contract/v1 parameters: required_resources and required_sections; file data is only read from captured evidence, not from an arbitrary path the model enters.
- state_predicate/v1 parameters: path as a list of keys/indexes; op in exists/eq/ne/lt/lte/gt/gte; expected as a JSON type. No eval of Python/JavaScript/string expressions.

- [ ] Write a test that the same goal service evaluates an artifact and a state; there is no industry-specific logic in the evaluator registry.
- [ ] Write tests for stale evidence, wrong evaluator revision, missing source, NaN, reading beyond the brain, prompt injection in an artifact, and evaluator timeout. Cases with missing data return unknown with a reason; a timeout has an error_code.
- [ ] Write tests that a correction reverses the new assessment but keeps the old one; a duplicate source does not raise confidence; all criteria met but a guard triggered does not close the goal.
- [ ] Write tests that data with an id/date field before the value still selects the right path; a result of ERROR:/isError must not be entered as a number or as success evidence. The data-collecting adapter must keep the error state, not just catch the exception.
- [ ] Run python tests/run.py resonance_evaluators -v; confirm red.
- [ ] Implement the registry and aggregation per section 6 of the spec. Time/evidence limits are passed in by the evaluation policy; adapter errors are isolated and do not stop the whole scheduler.
- [ ] Rerun the tests. PASS when no LLM is needed and a new evaluator type can be registered through the interface without editing the goal state machine.
- [ ] Review and commit the task.

When a contract needs a time-series comparison, add a metric_series/v1 adapter in server/resonance_eval_metric.py with tests/python/test_resonance_metric.py, using the same Evaluator Protocol. Do not put percentage formulas in the goal service. The parameters schema includes selector, unit, value_kind (gauge/period_total/counter), window/timezone, aggregation (last/sum/delta/time_weighted_mean), baseline, direction and missing_data_policy; validate that the combination is appropriate. Sample metadata has source_sample_id, observed_at, received_at, unit and quality. The baseline and quality limits are pinned by the contract; there is no default 30% reduction for every domain.

- [ ] Write test_metric_source_selection, test_metric_error_is_unknown, test_metric_constant_is_readable, test_metric_duplicate_samples and test_metric_sampling_cadence_does_not_reweight: if the source data is unchanged, changing the read schedule does not change the aggregation; stable data still has enough quality.
- [ ] Write test_metric_late_sample, test_metric_zero_baseline, test_metric_nonfinite, test_metric_unit_change and test_metric_window_policy: if the conditions are not met it is unknown; the same calendar period differs from rolling when the policy says otherwise; a timestamp after the read start time is still considered at the next evaluation after it is received.
- [ ] Run python tests/run.py resonance_metric -v to confirm red; implement the adapter per section 6.5 of the spec, not a regex on the first number; rerun the same resonance_evaluators and commit when green. It can be done after the first artifact demo milestone; do not use metric_series in a contract before the adapter has been verified.

## Task A4 Self-forming goals, goal service and a permission-checked API

**Files:** Create server/resonance_intent.py, server/resonance_service.py, server/resonance_api.py, tests/python/test_resonance_intent.py, tests/python/test_resonance_api.py. Modify server/main.py only for dependency injection/router/lifecycle. Use the existing engine adapter through dependency injection; do not create a separate model client.

**Interfaces:**

- GoalFramer.form(intent: IntentRecord, context_refs: tuple[str,...], current: GoalSnapshot | None, evidence: tuple[EvidenceEnvelope,...], policy: dict) -> FramingResult; async, the context input is already permission-checked, and the policy is issued by the host and versioned.
- GoalFramer.check_revision(current: GoalSnapshot, proposed: FramingResult, principal: Principal) -> dict returning permitted, conflicts, reasons. Permissions and protected fields are checked by code; the judgment of semantic fit is stored in a grounded form and is not faked as proven by schema validation.
- GoalService(store: GoalStore, evidence: EvidenceBridge, evaluators: EvaluatorRegistry, framer: GoalFramer).
- GoalService.accept_request(source_message_ref: str, principal: Principal, key: str) -> FramingResult; authenticates the stored input and automatically creates/activates an eligible contract within the scope of phase A.
- GoalService.clarify(clarification_id: str, answer_ref: str, expected_revision: int, principal: Principal) -> FramingResult.
- GoalService.reframe(goal_id: str, reason: str, evidence_ids: tuple[str,...], expected_revision: int, principal: Principal) -> GoalSnapshot; the new revision keeps the spent resources, guards and intervention state.
- GoalService.create(raw: dict, principal: Principal, key: str) -> GoalSnapshot.
- GoalService.evaluate(goal_id: str, principal: Principal, now: float) -> Assessment.
- GoalService.command(goal_id: str, command: str, expected_revision: int, principal: Principal) -> GoalSnapshot; command is one of activate/pause/resume/cancel.
- GoalDeps consists of the service and get_principal(request) -> Principal taken from Jarvis 007's auth; register(app, deps: GoalDeps) -> None.
- Conversation API: POST /goal-requests; POST /goal-clarifications/{id}/answers; POST /goals/{id}/reframe. The main input is a reference to a user message; the client is not made to fill in a GoalContract. A need with missing information is still stored and returns next_step/clarification, with no 422 error just because the wording is vague.
- Management/detail API: POST /goals; GET /goals; GET /goals/{id}; POST /goals/{id}/revisions; POST /goals/{id}/commands; POST /goals/{id}/evaluate; GET /goals/{id}/events; GET /goals/{id}/assessments. The structured create is for adapters/tests or advanced users, and is not a mandatory step of the UI.
- Mutations take an idempotency key; revise/commands take expected_revision; 409 if stale, 422 if the contract is invalid, 404 for an id outside the scope, 403 for missing permission within a valid brain.

Phase A only supports observation-only contracts with an authority_ref created by the host from the principal's existing read permission. Active allows collecting/evaluating evidence within this scope, and does not yet grant autonomous execution permission. Execution grants and the full budget are added in B1; do not create a circular dependency from A into B.

- [ ] Write tests that a valid owner creates/reads/edits, others cannot read across brains, and a planner payload does not grant itself a Principal or an authority_ref with extra permissions.
- [ ] Write a test that a contract edited while an evaluator is running: the old assessment is saved in history but does not update the active revision.
- [ ] Write a test that a fake engine receiving a vague request and context: picks the goal and criteria on its own, does not make the user choose; missing information that is not significant uses an assumption with a recorded source. When there is a question worth asking, only the dependent part waits; an "I don't know" answer switches to discover, and the old question is not replayed.
- [ ] Write tests for no basis or no access source: stay unknown, choose a permitted discovery step or return blocked with a reason. Contradictory constraints are stated clearly; do not drop a direct instruction on your own or take document content as a user instruction.
- [ ] Write a test that a reframe with new evidence keeps a valid intent_ref and constraint_refs, supersedes the old revision, and does not change permissions or reset the budget on its own. Merely lowering the target to report a win does not pass check_revision; a reasonable change of goal is also not recorded as a method improvement when there is no control comparison.
- [ ] Write tests that resume does not cross a guard that requires user permission on its own, and activate is blocked when a needed evaluator/source/grant is missing. When the feature is off, no background run is created.
- [ ] Run python tests/run.py resonance_intent resonance_api -v; confirm red.
- [ ] Implement the framer and service per section 4 of the spec: keep the origin of the input, the hypotheses, the questions already asked, the grounds for edits and the discovery limits by policy. Reuse the existing engine adapter; model output goes through schema validation and host authorization. Do not let the model call an internal endpoint that writes an assessment as a trusted evaluator. Do not attach the execution scheduler in phase A.
- [ ] Verification limit: a unit test with a fake engine only checks the flow and constraints. Evaluate the quality of inferring goals with a real engine, with an independent rubric/fixture, at C6; do not call a green unit test evidence that the agent understood every need correctly.
- [ ] Rerun the resonance test group; PASS if the API works with fixtures and does not call a real engine.
- [ ] Review and commit the task.

## Task A5 UI for receiving a need and showing the current understanding

**Files:** Create dashboard/resonance.js, tests/js/test_resonance_ui.js. Modify dashboard/workspace.js, dashboard/console.js, dashboard/index.html, dashboard/i18n/vi.json, dashboard/i18n/en.json. Create docs/22-muc-tieu-va-resonance.md, docs/en/22-goals-and-resonance.md.

**Interfaces:** window.JavisResonance.render(container, {ownerType, ownerId, brain}); destroy(container). The module calls the A4 API; it does not read SQLite/files directly.

- [ ] Write tests that render the states no goal yet, active, waiting, unknown, paused, succeeded; do not derive a percentage from the number of criteria arbitrarily.
- [ ] Write tests that switching brain clears the previous screen's data and cancels old requests; name/intent/evidence HTML is escaped; a revise request with 409 does not overwrite a newer change.
- [ ] Write a test that handing over a need in words creates a goal automatically, without opening a goal-picking/KPI-filling/contract-confirming screen; an "I don't know" answer is received and shows a discovery step. Editing the understanding through conversation updates the revision, and does not delete the original words.
- [ ] Run python tests/run.py --js resonance_ui -v; confirm red.
- [ ] Implement the entry point through conversation and the "What Jarvis 007 is working toward" card (Vietnamese: Em đang hướng tới): the understanding, important assumptions, what is being done, evidence and history. Allow editing the understanding in words; contract details only open when needed. Attach it to Partners/Tasks; do not yet turn the existing classification field group into a runtime group. Phase A states clearly that it is only observing/preparing and does not yet execute the effects of phase B on its own.
- [ ] Rerun the JS tests and open the dashboard with a fixture to check wide/narrow screens, keyboard operation, vi/en wording and API error states. Do not record that the UI is verified if only strings were tested.
- [ ] Update the guide and commit the task when it passes.

## Phase A acceptance

- [ ] The same API receives a natural-language need, infers and evaluates a structured document and a simulated data state; the user is not made to provide a standardized goal.
- [ ] A vague request and an "I don't know" answer create a valid discovery step; missing permission still blocks the part that needs permission. The history separates the original input, assumptions, revisions and actual results.
- [ ] Evidence can be reopened; unknown, errors and stale revisions display correctly.
- [ ] No reaction, message count or model call count is in the success logic.
- [ ] All resonance tests and related regressions are green; record the actual results in the PR.
- [ ] Continue to B1; after that, run C1 before expanding to teams.
