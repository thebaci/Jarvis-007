# Jarvis 007 Resonance Evolution Implementation Plan

**Status after the second round of challenge:** reference for the extended architecture. The small method trial is done early in the [single-agent MVP](2026-10-06-resonance-00-mvp.md); the full ExperimentService, variant store or supervisor is not needed yet. C3 to C5 only open after the small loop has run and there is evidence that expansion is needed; there is no self-modifying code in the MVP.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking. This is a plan, not an instruction to start updating a running Jarvis 007 on its own.

**Goal:** Let the agent improve its ability to understand needs, form goals and do work through experiments with evidence; then extend to editing Jarvis 007 code with real recoverability.

**Architecture:** The experiment service manages the baseline/candidate, the verification data and the conditions for applying. A candidate only has worker permissions; an independent supervisor holds the scoring, the right to apply, the recovery copy and the log. Changing a method and changing the application are two separate apply targets.

**Tech Stack:** Python, SQLite, the existing runner, a Git checkout for candidate code, a host supervisor and a container worker in live self-update mode. V1 does not support live self-update if the environment has no verified worker/supervisor boundary.

**Spec:** [Overall design](../specs/2026-10-06-javis-resonance-design.md), sections 10 to 17. Depends on [Foundation](2026-10-06-resonance-01-foundation.md) and B1 to B3 of [Runtime](2026-10-06-resonance-02-runtime.md).

## Global Constraints

- Inherit the Global Constraints and data types of the two previous plans.
- A candidate does not write to permissions, protected evaluators, receipts or the answer set kept private for the current trial.
- The user does not need to approve a change again if the grant already allows applying within the exact scope and the verification passes.
- Changing the evaluation criteria creates its own revision; do not compare scores on different metrics to claim an improvement.
- Adjusting the inferred goal is normal operation; the execution result of each revision is kept separate. The goal framer is improved by a control comparison on the same input/constraints, not by choosing an easier target.
- Discovery sits inside the total original resources; variants are stored within a limit, and no unbounded store is created.
- Self-modifying code is a separate opt-in; do not replace a loop's default full with the self_modify/deploy permission.
- Do not advertise live protection by a flag file or a process running under the same fully privileged account.
- A health check does not replace a behavior check; a Git rollback does not replace restoring data and outside effects.
- C1 and C2 are done right after B3; C3 after B4/B5; C4/C5 only open live when the environment boundaries are sufficient.

## Review Focus

1. A candidate that edits the questions/answers or creates a fake test log must not be accepted: C1, C4.
2. A baseline/candidate with different budget, data or metric must not be compared as equivalent: C1.
3. A result without enough data must not be applied on its own; a worse version must keep the baseline: C2.
4. A new lesson that is wrong or withdrawn must not continue to be inserted into the prompt: C3.
5. A crash during deploy, an app that is healthy but behaves wrongly, or an incompatible migration must be recovered or kept in a clearly blocked state: C5.
6. A goal that is easy to reach but off the need must not be scored well; the agent must not learn to dodge necessary questions or ask repeatedly to reduce its responsibility: C1, C3, C6.

## Task C1 Experiments and the method trial set

**Files:** Create server/resonance_experiments.py, server/resonance_trials.py, tests/python/test_resonance_experiments.py, tests/fixtures/resonance/README.md, tests/fixtures/resonance/document_cases.json, tests/fixtures/resonance/index_cases.json, tests/fixtures/resonance/intent_cases.json. Modify server/resonance_contracts.py, server/resonance_store.py.

**Interfaces:**

- ExperimentSpec(id, brain_id, goal_id, contract_revision, hypothesis, baseline_ref, candidate_ref, evaluator_ref, evaluator_revision, development_set_ref, holdout_set_ref, resource_envelope, acceptance, target, status); target is method/app_code; status is draft/running/inconclusive/rejected/eligible/applied/reverted. Defined in resonance_contracts.py.
- TrialResult(id, experiment_id, variant_ref, case_id, receipt_ids, assessment_ids, resources, completed_at); every ref must be traceable.
- ExperimentService.create(spec: ExperimentSpec, principal: Principal) -> ExperimentSpec.
- TrialRunner.run(experiment: ExperimentSpec, variant_ref: str, case_id: str) -> TrialResult.
- ExperimentService.compare(experiment_id: str, principal: Principal) -> dict; verdict inconclusive/rejected/eligible, with reasons and evidence_ids.

- [ ] Write a test that two variants on the same case have good/bad/unknown results; the same evaluator revision and envelope; a case missing a receipt must not be scored passed.
- [ ] Write tests that changing the criteria midway, a mismatched dataset, or a different baseline budget must not conclude a win; an unmeasured cost must stay unknown.
- [ ] Write a test of a valid reframe during a trial: keep the trial and the verdict of the old revision, and a trial that no longer applies returns inconclusive/goal_reframed. Do not apply to the new revision before comparing again on the same metric and checking applicability.
- [ ] Write tests that development cases do not overlap the holdout; a candidate does not receive the holdout path/answers; a payload that says PASS but whose checker fails is still rejected.
- [ ] Run python tests/run.py resonance_experiments -v; confirm red.
- [ ] Implement trials on a copy of simulated resources, and do not rerun an irreversible action on a real service to get a control comparison. Pin the revision and the seed/order if there is a random element; record every trial, including failures.
- [ ] In C1/C2 before C4, a variant is only a declared method configuration run through host tools whose scope has been checked; the model does not receive the answers/checker path. Do not yet run Python/shell generated by a candidate with host permissions. Arbitrary candidate code needs the C4 backend.
- [ ] For the first fixture: the baseline omits a required section in a document and the candidate adds it; in another fixture the baseline misses a file change in an index. The artifact/state checker from A3 confirms the result, not the worker's self-grading.
- [ ] Add intent_cases: a vague request, information already available that needs no question, an "I don't know" answer, contradictory constraints, a hard goal and an opportunity to lower the criteria to win. The fixture records the need/constraints and the acceptable behavior, and does not force a single goal sentence. C1 checks structure, permissions and history with a deterministic checker; C6 adds a semantic evaluation independent of the executing model.
- [ ] When trying Goal framer variants, the baseline/candidate receive the same input and budget and create their own goals; the outside scoring stays fixed by the original need/constraints. Report goal fit and output effectiveness separately, and do not compare the pass rate of criteria each candidate chose for itself as the same metric.
- [ ] Fixture acceptance: the candidate passes all held-out cases, does not turn a case the baseline already passed into a failure, and does not exceed the granted envelope. This is a condition of this specific trial, not a rule for every future experiment.
- [ ] Rerun the tests; review and commit.

## Task C2 Applying a method and keeping variants

**Files:** Create server/resonance_variants.py, tests/python/test_resonance_variants.py. Modify server/resonance_store.py, server/resonance_experiments.py, server/resonance_executor.py, server/resonance_api.py, dashboard/resonance.js, dashboard/i18n/vi.json, dashboard/i18n/en.json.

**Interfaces:**

- VariantStore.register(brain_id: str, owner_id: str, parent_ref: str, artifact_ref: str, evidence_ids: tuple[str,...]) -> str.
- VariantStore.activate(owner_id: str, expected_active_ref: str, candidate_ref: str, experiment_id: str, principal: Principal) -> str.
- VariantStore.revert(owner_id: str, expected_active_ref: str, restore_ref: str, principal: Principal) -> str.
- API: GET /goals/{id}/experiments; POST /goals/{id}/experiments; POST /experiments/{id}/apply; POST /experiments/{id}/revert. The apply permission comes from the grant; the application calls the service itself once the conditions are met if authorized.

- [ ] Write tests that eligible + a valid apply grant changes the active_ref; rejected/inconclusive or an expired grant keeps the old version.
- [ ] Write tests that two experiments applying at the same time have only one winning the CAS; a running run keeps the old revision; the next run uses the new version.
- [ ] Write a test that a goal that has been reframed does not automatically apply an experiment belonging to an old revision; check the scope of applicability, the criteria and the evidence before creating a new trial. A framer variant that has been confirmed still has no right to rewrite the original instruction or raise a grant.
- [ ] Write tests that exceeding the storage quota cleans up by policy but does not delete the active, pinned or still-needed restore_ref; a different version that has not won may be kept within quota.
- [ ] Run python tests/run.py resonance_variants -v; confirm red.
- [ ] Implement the version pointer in a transaction, recording applied/reverted events. V1 applies a method through a configuration ref, and does not overwrite agents/skills in the brain in bulk.
- [ ] Complete the demo A -> B1 -> C1: the agent runs a goal, tries an improved method, the checker confirms, it applies it itself within permissions, the next run uses the new method and can go back.
- [ ] Rerun the tests, check that the UI shows the winning evidence and the limits of the trial; review and commit. After this milestone continue with groups at B4/B5.

## Task C3 Lessons and qualitative evaluation with a source

**Files:** Create server/resonance_learning.py, server/resonance_eval_rubric.py, server/resonance_eval_human.py, tests/python/test_resonance_learning.py, tests/python/test_resonance_rubric.py. Modify server/main.py at the JAVIS_LESSON path, server/resonance_evaluators.py, server/resonance_store.py.

**Interfaces:**

- LearningService.propose(context: GoalRunContext, text: str, evidence_ids: tuple[str,...], scope: dict) -> str.
- LearningService.validate(lesson_id: str, assessment_id: str, principal: Principal) -> None.
- LearningService.supersede(lesson_id: str, replacement_id: str | None, evidence_ids: tuple[str,...]) -> None.
- LearningService.active_lessons(brain_id: str, owner_id: str, scope: dict) -> list[dict].
- RubricEvaluator and HumanConfirmationEvaluator implement the A3 Evaluator Protocol. The prompt/rubric revision and the identity of the confirming source are recorded in the assessment.

- [ ] Write tests that a reaction does not create a validated lesson; a worker's comment is only proposed; a clear instruction from a principal with the right permission can confirm.
- [ ] Write tests that a user editing the understanding creates a new IntentRecord, stating clearly the scope of this need; it is not inferred as a preference for every domain. An assumption about a need that is still uncertain must not be promoted to a validated lesson just because the agent completed the goal it set itself; a refuted lesson must be withdrawn from both the framer and the planner.
- [ ] Write tests that a lesson only applies within its scope, a superseded one is no longer put in the prompt, it does not edit the memory area the user wrote by hand, and no lesson leaks across brains.
- [ ] Write tests that a rubric with missing evidence returns unknown; model confidence is not presented as a probability; without permission to see the data the evaluator must not read it to score.
- [ ] Run python tests/run.py resonance_learning resonance_rubric -v; confirm red.
- [ ] Implement separate provenance for Resonance lessons; bridge to the existing memory mechanism by id/hash to withdraw an auto-generated lesson at the right line. Keep the legacy JAVIS_LESSON behavior that is not part of Resonance.
- [ ] Add the new evaluators through the registry, without editing the state machine. Human confirmation requires an authenticated identity, and does not accept a model's self-reported sentence as the user's signature.
- [ ] Run the new tests and python tests/run.py learn_agent_workflow agent_tu_boi_dap memory_hoa_thuong -v; review and commit.

## Task C4 Supervisor and worker with separated permissions

**Files:** Create server/resonance_supervisor.py, server/resonance_worker.py, server/resonance_isolation.py, tests/python/test_resonance_supervisor.py, tests/python/test_resonance_isolation.py, docs/dev/resonance-supervisor.md.

**Interfaces:**

- IsolationProbe(supported: bool, reason: str, verified_boundaries: tuple[str,...]); a type in resonance_isolation.py.
- IsolationBackend.probe() -> IsolationProbe; launch(workspace: Path, manifest: dict) -> str; stop(worker_id: str) -> None; inspect(worker_id: str) -> dict.
- Supervisor.issue_job(experiment_id: str, grant_id: str, workspace_ref: str) -> str.
- Supervisor.revoke_tree(goal_id: str, principal: Principal) -> None.
- Supervisor.collect_receipt(worker_id: str) -> dict.

- [ ] Write tests that a worker does not create a grant itself, change the revocation epoch, edit a receipt or report a fake test as a host receipt.
- [ ] Write tests that when the probe lacks enough boundaries, supported=false and app_code stays in prepare mode only, with no automatic fallback to a full host shell.
- [ ] Write an integration test with a trial worker writing to the grant/evaluator/receipt/supervisor control path: it is rejected; revoke blocks new jobs and stops the worker; no secret is printed in the test log.
- [ ] Run python tests/run.py resonance_supervisor resonance_isolation -v. A test in an environment without isolation must confirm unavailable correctly, and must not record PASS for a boundary that has not actually run.
- [ ] Implement the supervisor outside the candidate checkout. V1 live uses an unprivileged container worker, with no Docker socket, no host PID, no mount of the grant store/host secrets; only the workspace and the necessary input data. Network/tool access goes through a gate with a scoped grant, and no host admin credential is handed over.
- [ ] Support Linux/Docker Desktop when the probe actually proves the conditions. The module does not install or configure a production environment on its own; the document records the host conditions and how to verify.
- [ ] Protect the evaluator/receipt and the contract content on the supervisor side. The same process/same host permissions can only be marked trusted-development, not a protected live self-update mode.
- [ ] Rerun the unit tests and the boundary integration on the target host; record the environment and the result. Review and then commit.

## Task C5 Candidate code and applying a Jarvis 007 version

**Files:** Create server/resonance_deployment.py, tests/python/test_resonance_deployment.py. Modify server/resonance_supervisor.py, server/resonance_experiments.py. Reuse server/updater.py and server/update_state.py through an adapter, only editing the interface if testing proves it is needed. Create docs/dev/resonance-recovery.md.

**Interfaces:**

- DeploymentPlan(id, experiment_id, candidate_sha, baseline_sha, manifest_hash, data_compatibility, recovery_ref, smoke_suite_ref, rollout_scope); a type in resonance_deployment.py.
- DeploymentService.prepare(experiment_id: str, principal: Principal) -> DeploymentPlan.
- DeploymentService.validate(plan_id: str) -> dict.
- DeploymentService.apply(plan_id: str, principal: Principal) -> dict.
- DeploymentService.recover(plan_id: str, reason: str) -> dict.
- The deployment result has phase, code_revision, data_state, checks, unresolved_effects; there is no boolean rollback_ok unless code and data have both been checked.

- [ ] Write tests that a candidate_sha that does not match the verified version, an edit to a protected path, a grant missing deploy, or a failed probe all block apply.
- [ ] Write a test that changing the goal revision after validate but before apply makes the applicability be rechecked; a reframe does not skip a pause, guard or revocation. The old deploy receipts and cost are kept even if the goal is adjusted.
- [ ] Write tests of the app health green but the smoke behavior red; a crash before/after changing the active version; a failed recovery reports clearly and keeps the supervisor running.
- [ ] Write tests that a backward-compatible migration can be recovered; a migration that does not prove compatibility, or has no recovery_ref, blocks live. Do not wipe the user's changes in the original checkout to deploy a candidate.
- [ ] Run python tests/run.py resonance_deployment -v; confirm red.
- [ ] Implement a separate candidate checkout, CI/test checks per the repo, an artifact manifest with a SHA, and a smoke suite held by the supervisor. A candidate may not edit the updater/guard in the same experiment; it may create a separate proposal for the owner to consider.
- [ ] Apply within the limited trial scope that was granted; expand only when the checks pass. Drain/checkpoint runs before a restart, resume from state; do not lose schedules and do not rerun an uncertain effect.
- [ ] Recovery restores the app and data per the plan that was tried, keeping the ledger of outside effects as is. Do not send a compensating action on its own if the grant lacks that permission.
- [ ] Run the new tests and python tests/run.py update update_lui_hong update_diagnose workflow_graph_phase10 -v. Run a real smoke/recovery on a copy of the deployment, not on user data during the planning turn.
- [ ] Write a recovery guide with specific conditions; review and commit.

## Task C6 System-wide control comparison and limited release

**Files:** Create tests/python/test_resonance_acceptance.py, tests/fixtures/resonance/evaluation_protocol.json, docs/dev/resonance-evaluation.md. Modify the vi/en user guides and the feature flag configuration where it is integrated in server/main.py.

**Interfaces:** run_acceptance_suite(profile: dict) -> dict in the test harness; the report contains the intent/contract/evaluator/model/variant revisions, case results, goal_fit, execution_outcome, actual resources, intervention count and unavailable measurements.

- [ ] Write the end-to-end scenarios of section 16 of the spec with fixtures that use no real services. Compare the same runner with learning on/off and the same resources.
- [ ] Create an unseen input set for the Goal framer: vague, clear enough, user_unsure, no answer, conflict and a change of need. Score fit against the source and constraints kept private; the semantic evaluator does not receive the identity of baseline/candidate when feasible. Allow multiple reasonable goals; a case without enough basis has an unknown conclusion, and the model's confidence is not used as the answer.
- [ ] Measure the number of questions actually needed, the number of repeated questions, the effort of fixing the understanding, the level of useful progress and the discovery cost. Do not optimize for fewer questions alone, because it may create wrong actions; dropping a necessary question is also an error. Check that finishing discovery does not report the need as resolved on its own.
- [ ] Add regression cases from the Claude comparison: a numeric string with an id/date/error code; a stable source with enough quality; changing cadence does not change the result for the same source; a guard exceeding its threshold when the agent has not acted; two brains with the same slug; losing the audit before/after an effect; a chat refresh keeping the right action. Only run the undo suite when the B6 adapter is released; otherwise confirm the UI does not advertise that capability.
- [ ] Run the suite with a fake clock/executor to check determinism, then run a pilot with the engine the user chose on simulated resources. Do not record pilot results before they have been run.
- [ ] Report goal fit, work results, measurement quality, cost and intervention effort separately. If the criteria change, record a table by revision with the reason; do not aggregate into a win rate that hides lowering the goal. Do not use tokens per heartbeat or the number of chats as the main metric.
- [ ] Test adding a new adapter type only through plugin/evaluator registration and fixtures; the goal service adds no business branch.
- [ ] Measure one small milestone first: the same request, one agent, an artifact adapter and two method configurations on a fixture. Record clearly what was checked and what is not yet open; there is no need to wait for weeks of reactions or to finish building groups/undo before checking the value of the self-improvement loop.
- [ ] Run python tests/run.py resonance -v, then all the repo's mandatory checks before release. New errors are handled before expanding; do not repeat the whole suite if there is no new change or problem.
- [ ] Enable per brain/goal chosen, with a switch back to the old behavior; live self-update remains a separate opt-in permission. Record the conditions for expansion with pilot numbers, and do not set in advance an assumed win rate.
- [ ] Finish the PR per docs/quy-uoc-dev.md; CI green and check against the phase criteria before integration.

## Conditions for completing the whole program

- [ ] A natural need is turned by the agent into a goal, executed, verified and reported, without making the user pick a goal, without depending on reactions or a specific industry.
- [ ] When the user is unclear, the agent clarifies selectively or discovers on its own within permissions; it fixes its understanding according to evidence, keeps the history and does not score itself a win by changing the criteria.
- [ ] The agent and the group use the same contract, with contribution evidence and inherited permissions.
- [ ] At least one method change is tried, confirmed, applied and recoverable on its own.
- [ ] The live self-update claim is only enabled on an environment that has passed supervisor testing, effect recovery and data compatibility.
- [ ] It is possible to point clearly at what improvement was measured, what is still uncertain and the numbers that serve as the basis.
