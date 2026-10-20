# Jarvis 007 Resonance: design and goal execution roadmap

Date: 6 October 2026. A design to be implemented in phases.

**Current version:** see the [index of finalized documents](../README-RESONANCE.md). Before M1, check the latest main, pin the base commit and re-verify the code references in section 14; a survey on an old checkout does not replace integration verification.

**Priority scope after round 2 review:** implement the [single-agent MVP](../plans/2026-10-06-resonance-00-mvp.md) first. This document describes the target architecture; the extension components are not a list of things to build right away. The three Foundation/Runtime/Evolution plans are reference documents for a later phase and are not to be run in parallel with the MVP.

Jarvis 007 Resonance helps one agent, one team or the whole system take a need in natural language, form a suitable goal by itself, choose a method, gather evidence and improve both its understanding and its way of working within the scope the user has delegated. The user does not have to know how to set a goal or pick a metric. The core is shared across all domains; domain knowledge lives in replaceable tools, evidence collectors and evaluators.

**Central decision:** the user's need sets the direction; the agent forms the goal as an adjustable hypothesis; evidence determines progress; delegation determines scope. The agent is responsible for finding the right destination and finding a way to reach it. A beat is the next moment when activity is useful. Reactions do not decide an agent's performance, authority or whether it continues to exist.

## 1 Decisions kept and improved

| Topic | Final decision | Reason |
|---|---|---|
| Supreme goal | Each execution has one primary goal, tied to an intent and success conditions | Focused, yet one agent can still serve several goals in different sessions |
| Goal formation | The agent infers it from the request, the context it is allowed to read and evidence; the user can correct the understanding | Does not require the user to choose a goal or know the solution in advance |
| Ambiguous requests | Ask when the answer could change a decision significantly; if the user does not know, investigate or try something small within authority | Uncertainty becomes work to be resolved |
| Agent and team | Use the same goal contract; a team decomposes into sub-goals | Scales with the same structure |
| Autonomy | May plan, collaborate and modify itself within the delegation in force | Does not require re-approving every action that has been authorized |
| Evaluation | Based on results and evidence, with a not-enough-information state | Missing data is not turned into failure or success |
| Beat | Driven by events, ability to act and the moment new evidence appears | Does not reward by forcing the agent to run more |
| User feedback | Instructions update the intent; the That's right/Not quite buttons provide evidence about understanding; result confirmation is tied to the product; shared emoji serve communication | Separates what the user confirms, avoids using one click for every conclusion |
| Self-improvement | Create variants, test with a control, verify, then apply | A self-change must prove it is an improvement |
| A single utility score | Not used as the control for the whole system | Capability, progress, activity need and communication preference are different information |
| Attribution | Store the contribution and the confidence level; do not assume the leader receives the most | Lineage does not prove causation by itself |
| Hibernation | Stop waking on a schedule when there is no longer a reason to act, keep state and the ability to receive events | No need for a common 90-day limit for every task |
| Producing an output | Recorded as an action; counts as a success only when the criteria confirm it | Prevents mistaking activity for effectiveness |
| Expanding to new domains | Add an adapter with a common interface | No domain-specific conditions in the core |

The implementation choices below are versioned policy or contract configuration. Only the three invariants in section 2 are base law. Do not turn an experimental number into a fixed principle.

## 2 Three invariants

### 2.1 Delegation is inherited and does not expand itself

The user states the need at the level they can, together with the constraints or authority already granted. The agent infers the goal, criteria and method from that input; it does not make the user define everything before helping. A child agent receives only part of its parent's authority and resources. The total allocated in use and already spent does not exceed the original amount granted. A performance score does not generate extra authority.

Forming and adjusting an inferred goal is the agent's default responsibility when handling a request, not a permission the user must turn on separately. The agent may revise its hypothesis about the destination, the inferred criteria and the method based on evidence, with the version and reason recorded. Clear instructions and constraints the user has stated remain in force; the agent does not drop them or expand authority, scope and budget by itself. When the input contradicts itself or the requested destination is infeasible, the agent explains and looks for useful progress within the scope that is still valid; only the user can change constraints that they set themselves.

### 2.2 Success must have evidence against criteria already established

Every conclusion is tied to a contract version, an evaluator and a set of evidence. The agent does not edit source data, test results or the measure of the test itself in order to declare a win. A comment from another agent has a clear origin but does not become fact by itself.

The system accepts an unknown conclusion. Changing the criteria creates a new version and does not rewrite history. A replaced version is marked superseded together with the actual results it already had, and does not turn into success or erase failure by itself. The criteria of a running test are held fixed; finding a more suitable goal is a separate conclusion from doing better on the same goal. A completed sub-goal does not make its parent goal succeed by itself; the final result must still be evaluated against the parent contract.

### 2.3 The user's right to intervene and the history always hold

The user can stop, redirect or revoke authority. Every agent version is subject to these operations. Decisions, impacts, evidence, changes and reasons are all stored. Restoring software is not described as having undone external effects that have not been reversed.

For the mode that edits Jarvis 007's own code, the component that enforces authority, keeps evidence and stops workers must have a real access boundary. A file that sits outside the repo but belongs to an account with full write access does not create that boundary.

## 3 Product goals and success criteria

The user describes what they want, the problem they have or what they are unhappy about in natural language. The agent forms the goal by itself, shows how it currently understands it and carries out the part it can do within existing authority. There is no mandatory step to choose a goal, fill in a metric or approve a contract before each start. The system handles quantitative results, products that must be completed and quality criteria.

Resonance's success is evaluated through representative tasks with a control: whether the goal stays close to the input and constraints, the pass rate against criteria, the effort the user must spend to correct or coordinate, completion time, the level of annoyance and real cost. Goal formation quality and execution effectiveness are measured separately. The number of messages, agents, tool calls or reactions is not used as the main success measure.

Unlimited self-improvement is not promised. Each claim of improvement is only valid within the scope of the goal, data and tests that were run.

## 4 Goal contract

### 4.0 When a goal needs to be stored and pursued

First reuse the existing conversation router to choose answer_now, task_now, continue_goal or create_goal. Questions, advice, planning and work that can be finished in the current turn use the answer/do-now path, and do not create a durable goal, schedule or Kanban item just because many steps of thinking are needed. An answer to an open goal attaches to that goal and does not create a duplicate.

Create a durable goal only when the request truly needs to continue after the chat turn, track results later, wait for an event or hold state to carry out work that was assigned. "Get it done" is a signal of intent to complete, not a keyword that always creates a background job. A simple timed job keeps using the existing reminder. If it is unclear whether background running is needed, do the part that can be completed right away; do not infer long-running authority from an ambiguous question.

This decision uses the context and routing result of the current turn, and does not call one more model for every message. Call the Goal framer only when a goal really needs to be created or adjusted. This gate is a routing policy, not a step that asks the user to choose a goal.

### 4.1 Common fields

| Field | Content |
|---|---|
| identity | goal_id, brain_id, revision, owner_id, readable name |
| intent_ref | The original record of the need and instructions, with source and version; kept apart from what the agent inferred |
| intent | How the agent currently interprets the result to be produced, and why |
| framing | Stage discovery/delivery, goal hypothesis, assumptions, grounds, unknowns, unresolved contradictions, reason for the choice and conditions for revisiting |
| owner | The agent or team responsible, independent of the person with authority |
| mode | achieve to complete a goal, maintain to keep a condition true |
| success | A list of CriterionSpec, how they combine (all or any), end conditions |
| evidence | Sources used, required freshness, how resources and versions are identified |
| evaluation | Evaluator and version; check schedule/window; policy when data is missing |
| authority | A grant reference to the authority to act, resources, authority to assign work and to modify itself |
| resources | Limits, units of measure, how to reserve before running, how to reconcile cost |
| stop | Stop conditions, scope of impact, who is notified, how to resume |
| timing | Deadline or the reason for having none, events to listen for, time policy |
| relations | parent_goal_id, dependencies, role of the contribution to the parent goal |
| communication | Reporting channel, events to report, periodic report requirement if any |

A CriterionSpec has id, description, evaluator_ref, evaluator_revision, parameters, evidence_selector and acceptance. Parameters belong to the evaluator; the core does not need to know whether they are a number, text, a state or a document structure.

Stop conditions use the same evaluation interface but are checked independently of success conditions. A stop can apply to one action, a goal and its descendants, a team, or the whole autonomy layer. A global scope needs the corresponding authority.

### 4.2 Creating and changing a contract

1. Store the original request, its source and the stated constraints in an IntentRecord. When the user adds to or corrects an instruction, a new record is created that links to the previous one; the agent does not rewrite the user's words.
2. The Goal framer reads the allowed context and distinguishes the need, the solution the user suggested, the mandatory conditions and the assumptions. When there is only one sufficiently clear interpretation, use it right away; create several hypotheses only when there is a significant difference, and do not open an endless search tree.
3. Choose the working goal that best fits the current evidence: stay close to the need and constraints, create an observable benefit, be feasible within the resources, and avoid a large commitment while things are still vague. The model's confidence is not used as evidence that it understood correctly.
4. Propose the criteria and the verification sources by itself. If there are not enough grounds to determine the final destination, choose a useful discovery step such as looking at the current state, making a sample or a small trial, and state clearly that the result the user wants is still undetermined/not reached. Completing a survey is not turned into having solved the original need.
5. Ask briefly when the answer could change a decision significantly and cannot be inferred from context. If the user says they do not know, the agent continues with a survey or a small reversible trial within authority; it does not make them invent a goal. No answer is not read as granting extra authority.
6. Activate the valid part of the work from the assigned request by itself, and briefly say how it is understood when helpful. Setting a goal has no separate approval gate; an optional clarifying question does not block independent steps. Wait on a dependency only when irreplaceable information is missing or authority is truly required.
7. Revisit the hypothesis when data contradicts an assumption, the user corrects the intent, a result does not help resolve the need, or a discovery step produces new understanding. Do not change it just to make it easier to achieve or because a timer tick arrived. Each change stores the revision, diff, grounds and the IntentRecord link; runs, evidence and assessments in progress still carry the pinned revision.
8. Stop issuing actions under the old revision; reconcile the effects already sent and move over at a suitable checkpoint. An old run does not close the new version by itself. Budget already spent, active guards, pauses and revoked authority remain in force after a goal change.

V1 supports one owning parent per goal, and dependencies form an acyclic graph. Cross-goal collaboration uses contribution links and does not create two budget owners for the same run. The root goal plays the organization-level role; a separate company object type is not needed.

### 4.3 Achieve goals and maintain goals

Achieve moves to succeeded when the criteria are confirmed and there is no unresolved contradiction with the known need/constraints. If the root goal is still at the discovery stage to find the final destination, meeting the discovery criteria moves it to a goal review and does not close the original need. A discovery sub-goal can complete on its own. A request that is only for research or a survey can belong to delivery because the research result itself is what the user asked for. To keep tracking after completion, create an authorized maintain goal, or carry out the follow-on policy recorded in the contract. Do not raise the target by itself after a win.

Maintain stays active, records healthy/degraded/unknown through assessments and keeps observing until it is ended. It is not closed permanently the first time the condition is met.

### 4.4 Bounded clarification and discovery

The agent is responsible for choosing the next step; the user does not have to choose from a list of goals. When it needs to ask, prefer something close to their experience, for example what is causing difficulty or which result would be useful, rather than asking them to set a KPI. The agent may give examples to help understanding, but does not turn choosing an example into a default condition for working.

If the user is unclear, record a testable assumption and take a step that is cheap, easy to correct and able to tell the interpretations apart. Discovery resources share the request's limit; limits on questions, time and trials are policy configured by context. Do not ask again about something already answered as unknown when there is no new information.

If there is no valid action that reduces uncertainty, return the result already produced, state exactly what is missing and wait for a useful event. Do not call a model or change goals continuously just to look proactive. For a request with contradictory constraints, keep the constraints and do the compatible part; uncertainty about what is wanted is different from lacking authority to act.

Example: the user says "help me get less tangled up at work" (in Vietnamese: "giúp anh làm việc đỡ rối"). The agent looks at the work context it has been authorized to see, picks a hypothesis about what is causing the tangle and creates a trial arrangement that can be corrected. If the user also does not know what they need, the sample creates a basis for observing and adjusting. The agent does not treat this need as authority to delete tasks, send messages on the user's behalf or optimize the number of finished tasks regardless of quality.

### 4.5 Separating goal quality from execution results

Evaluate two separate questions: "does the goal fit the known need and constraints?" and "does the result meet that goal's criteria?". The second passing does not prove the first is right. When information is insufficient, fit remains a hypothesis and is not labeled as having fully understood the user.

There is no general utility function that determines what is best for everyone. The default policy prefers evidence from the input, clear constraints and useful progress within the resources. The user's corrective instruction has directional value; a single reaction is not enough to change the goal or a performance conclusion. These principles implement the three invariants and add no separate domain-specific rulebook.

### 4.6 SMART helps the agent clarify a goal

The agent uses SMART to review a goal after routing: Specific, Measurable, Achievable, Relevant, Time-bound, in the commonly used interpretation in the [CDC SMART guide](https://www.cdc.gov/youth-advisory-councils/action-plans/smart-framework.html). The mapping into Jarvis 007 below is a design proposal, not a form the user must fill in.

| Component | How the agent applies it |
|---|---|
| Specific | State the concrete result and the person/audience being served |
| Measurable | Choose the evidence that recognizes success; it can be a product or a specific confirmation, not forced into a percentage |
| Achievable | Check authority, tools and resources; if grounds are missing, investigate, and do not quietly lower the requirement |
| Relevant | Explain how the goal serves the original need |
| Time-bound | Use the deadline the user stated; if there is none, set an internal review milestone with a reason, not yet treated as a user deadline |

A discovery goal may be SMART only at the next step of finding out. Do not invent baseline numbers, targets or deadlines to fill all five boxes. SMART supports goal quality; it does not prove the wish was understood correctly and does not decide which chat messages need a durable goal.

### 4.7 Quick feedback with clear meaning

The What Jarvis 007 is working toward card has That's right and Not quite, optionally with an icon. The buttons send the explicit meanings goal_fit_confirmed/goal_fit_rejected, tied to the confirming person, goal_id and revision. Clicking on an old card does not confirm a new version; silence keeps unknown. Rejecting an interpretation triggers a review of the related part before the next impact, and does not turn by itself into a stop command for the whole system or an increase in authority. Clicking is never required in order to start.

On a product output, Meets the bar/Needs changes is a different kind of evidence, tied to the artifact revision and criterion. Confirming the goal does not mean the output passes; confirming a writing taste can be enough for a preference criterion if the contract allows it, but it does not override an objective check that failed, or a guard. An emoji under a shared message is not to be interpreted by itself as any of these confirmations.

This way human feedback is still used where it has meaning. The system does not depend on feedback to maintain capability, raise its tempo or prove every kind of effectiveness.

## 5 Overall architecture

| Component | Responsibility | Changeable by the agent |
|---|---|---|
| Goal framer | Form a goal from the need, choose what to clarify or explore, revisit the hypothesis based on evidence | Yes, through revisions; does not rewrite original instructions or authority |
| Goal service | Store the contract, revisions, relations and state | Through the API and the correct grant |
| Authority service | Check authority, revoke, reserve resources | Does not expand the caller's authority by itself |
| Planner | Choose actions, methods, assignments and the next time | Yes, per the authority to modify itself |
| Executor | Execute through the existing engine, workflow, MCP and tools | Granted methods/tools; does not bypass the authority gate |
| Evidence bridge | Collect receipts, store sources and link evidence | Workers may submit observations, but do not overwrite host confirmation |
| Evaluator registry | Run versioned evaluators | May propose variants; does not replace the measure of the current test by itself |
| Beat scheduler | Receive events, schedule, prevent duplicate runs and wake | Policy within the granted limits |
| Experiment service | Compare variants and manage apply/restore | May improve the trial method under the same proof rules |
| Supervisor | Stop workers, enforce authority and restore the software build | Outside the scope of the self-modification being tested |

V1 keeps Python, FastAPI, SQLite and the existing JavaScript dashboard. Do not build a message broker, a graph database, an agent marketplace or a new model framework. Use transactions and an outbox in SQLite for reliable coordination.

In the first phase, execute by itself only through a backend that can enforce a scope that has been verified. The CLI's native tools may go outside the MCP Hub; do not treat an allowlist in a prompt as a sandbox. A shell and arbitrary plugins running with host authority must not carry an isolated label. Authority to modify live code opens only after the supervisor phase.

The run context must cross processes: the host issues short-lived credentials tied to brain/goal/revision/run/actor and the grant for the worker to call the Hub over HTTP; an in-process engine uses the same context confirmed by the host. A header carrying an actor name is only a label unless it is matched against that context. A ContextVar is set/reset with a token in try/finally and must not leak into another request. The tool list cache does not keep the previous run's context. Each invocation has its own id linking action, run and evidence source; a slug or closeness in time is not enough for attribution.

## 6 Evidence and evaluation

### 6.1 Evidence format

An EvidenceEnvelope holds evidence_id, brain_id, goal_id, contract_revision, action_id if known, source, source_event_id, resource_ref, resource_version, observed_at, received_at, content_hash, evidence_ref, trust_class, freshness and supersedes_id if it is a correction.

Distinguish the confirming sources: a tool receipt written by the host, data from an adapter, a model evaluation, a user confirmation and a worker's self-report. A content hash confirms the content was kept intact, but does not prove the content is correct. Many copies from the same source do not create more independent evidence.

Record new evidence to correct, and do not delete the old one. Every read/write must check brain_id and the person with authority; a path or id supplied by a model is not enough to serve as access authority.

### 6.2 Evaluation results

An Assessment has goal/revision, evaluator/revision, criterion_results, evidence_ids, verdict, confidence, rationale, evaluated_at and next_observation_at.

A criterion's verdict is met, not_met or unknown. An evaluator run failure is recorded separately as error; it is not forced into not_met. A guard reports triggered, clear or unknown. V1 uses confidence low/medium/high with an explanation, and does not display a fake probability derived from the model's confidence.

An all condition is met when every criterion is met. An any condition is met when some criterion is met, but every guard and mandatory constraint must still be satisfied. A missing evaluator, stale data, a wrong revision or unreadable evidence each prevent success from being confirmed.

### 6.3 Extensible evaluators

The common interface Evaluator.evaluate(contract, evidence, now) returns an Assessment. An adapter describes its id, version, input schema, evidence types, read/write capability, timeout and failure conditions. By default an evaluator has no authority to create impact beyond writing an assessment.

The first adapters:

- artifact_contract: checks that a resource exists and meets the declared structure/criteria.
- state_predicate: evaluates a declarative data expression, and does not run arbitrary code or eval a string from a model.
- rubric: evaluates quality against version-pinned criteria, and may only confirm success if the contract accepts this method.
- human_confirmation: used for the part of a result that only the user can confirm.

In the MVP, prioritize artifact_contract and human_confirmation; the model rubric is deferred until needed. Later, a rubric only scores products that have source evidence, using a pinned version and criteria, and does not accept a worker's self-report as a completed product. Not every qualitative task must wait for the user: the contract may accept an independent model evaluation for a suitable criterion, together with checks of the objective conditions. A conclusion must state its method and limits, and must not pretend to be a certain measurement.

Returned documents and MCP output are data; they have no authority to change the contract or grant extra authority. MCP annotations are only hints about a tool and do not by themselves determine result quality or the intent to undo.

The catalog's read/write/danger labels are used to support authorization and do not prove the ability to undo. A multi-action tool must be classified by its actual arguments, and the effect at listing time must not be taken as the conclusion for every invocation. A result of ERROR:, isError or a structural error must be kept as an error by the adapter; a function returning normally does not mean the tool succeeded. Reads used for evaluation must also store their source and time, even though the full content read need not go into the activity log.

### 6.4 Leading indicators and attribution

The agent may propose actions that can have an impact, and a hypothesis for why they help reach the goal. This is a hypothesis to test, not a way to award itself credit through the volume of activity. Periodically reconcile actions with results, and change the method when the hypothesis is no longer supported.

Lineage stores contributions, critiques, evidence and decisions. V1 records effectiveness at the method and team level when there are not enough grounds to separate individuals. Do not multiply one result into several independent rewards; do not assume the synthesizer receives the most.

### 6.5 Numeric measurement and data quality

When metrics need to be compared over time, use the metric_series adapter with the schema: source, selector, unit, observed_at, window, aggregation, baseline, direction, acceptance and missing_data_policy. Take the specified field from structured data; do not take the first number in a piece of text. Text may be turned into a number only through a parser tested for that source; if it does not match the schema, it is unknown. The agent proposes the configuration itself; the user does not have to write frontmatter or choose a metric.

Distinguish whether a metric is a state at a point in time, an amount arising in a period or a cumulative counter, so as to choose the appropriate last/sum/delta/time_weighted_mean. The window, time zone and baseline are versioned. A sample uses the source's observed_at; received_at serves delay tracking. Calling a source several times does not create extra independent samples or change how the same event series is computed. An evaluation after receiving a sample must use the time that covers the new sample; late-arriving data is handled according to the declared window and policy.

Track readability, freshness, coverage, compatibility and the level of confidence in attribution separately. Stable data can still be very trustworthy; an action happening does not prove the action caused the change. Do not mix these quantities into a weight that shifts to reaction when the result does not move. Three samples alone are not enough to serve as a general rule confirming reliability; the number of samples and the coverage conditions belong to the adapter and the contract.

A guard protects the desired state independently of assigning responsibility: once a stop condition is confirmed, stop the specified scope even if it is not known who caused it. An unknown guard is different from clear; the missing-data policy determines which part may still be done. A zero baseline, a non-finite number, a change of unit or a missing source must not be treated by itself as 0% change or as everything being normal.

## 7 State and operating loop

Separate GoalStatus from RunState:

- GoalStatus: draft, active, succeeded, failed, cancelled.
- RunState: ready, running, waiting, blocked, paused, dormant.

Framing stores a level of confidence with an explanation and the unverified assumptions, independent of GoalStatus. An active goal may still rest on a provisional hypothesis. Superseded describes a revision that has been replaced, and does not add a success result to the goal's history. A discovery step has its own criteria; completing it does not complete the original need by itself.

Failed only when there is a not-met conclusion under the contract's end conditions. When a deadline arrives with no data yet, record it clearly as unknown and apply the agreed deadline policy; do not wrongly call it proven failure. Paused means the user paused it. Blocked means a condition is in the way; keep the reason code and the condition to reopen.

The control loop:

1. Receive an event or a due schedule, and check that the contract is still active.
2. Check current authority, guards, resources and version.
3. Collect the needed data and evaluate the existing evidence.
4. If there is evidence that the understanding no longer fits, hand it to the Goal framer to revisit before concluding. If the criteria are met and there is no unresolved contradiction with the known need/constraints, confirm it and end or maintain according to the mode.
5. If a new step is needed, the planner returns a Decision: act, delegate, experiment, clarify, reframe, wait, escalate or finish. Clarify opens a question; reframe requests a grounded revisit of the contract. Both go through the goal service, and are not authority to modify state or a grant by itself.
6. The Authority service checks the Decision, reserves resources and records the action intent before execution.
7. The Executor runs; the receipt and result are stored; re-evaluate when suitable evidence arrives.
8. Record lessons that have enough grounds, report meaningful events and set the next observation.

Finish is a request to verify completion, and has no authority to set succeeded by itself. A task or workflow with status done/COMPLETED does not complete the goal by itself.

## 8 Beat and communication

A beat is a WakePlan consisting of a reason, earliest_at, wake_on, observation_due_at, expires_at and policy_revision. Do not tie activity frequency directly to praise/criticism scores.

Prefer events from tasks, resources, deadlines, data sources and the user. A timer is the fallback when there is no suitable event. A scheduler tick only does cheap checks in code; call a model only when there is new information or a decision that needs reasoning.

Waiting has a clear condition to reopen. Dormant does not call a model on a schedule, but keeps the subscriptions it needs and receives user commands. A suitable event can wake a hibernating agent; an event must not by itself drop a user pause or reopen a guard that requires the user.

The guard observation schedule is separate from the agent invocation schedule but shares the same scheduler: a stretched-out loop or a busy worker must not lengthen the blind interval of a stop condition. It reads only for monitoring within authority and resources still in force; if the user revokes even observation, stop reading and report the loss of monitoring ability. A guard that has fired does not reopen by itself on one good sample; the recovery conditions, anti-oscillation and repeat notices belong to the versioned policy. If the policy allows automatic recovery, the host carries it out, and a user pause always stays in force.

The agent proposes the next time based on when evidence is available and the ability to have an impact. The host normalizes timestamps, merges duplicate events, and limits by budget and serving capacity. It does not rerun continuously by receiving a notification that it created itself.

A goal with no event source uses a useful review or polling of an authorized source with resource limits. An instruction like "ask me again on Friday" adjusts the WakePlan directly. Feedback about frequency only edits the communication/schedule policy within the scope of the request; a satisfied emoji does not make a worker wake more often. With no new data or useful action, sleep; do not call a model periodically just to ask whether the user is satisfied.

Default notifications for a new goal: reaching a meaningful milestone, completion, hitting a guard, an error that needs intervention, or needing a decision. The detail of each action is in the log. A request for periodic reports is recorded separately. An old loop/cron keeps its existing reporting behavior until it is moved to a goal.

When the user messages again, the agent continues or sets up a new goal from the current state and intent, and does not restore authority that has expired. Capability is not deleted because no reaction has been received for a long time.

## 9 Teams with a decider

Each group is tied to a goal_id, leader_id, membership and a coordination epoch. Only the leader holding the epoch has the authority to finalize the execution plan; the leader has no authority to drop a guard or edit the root authority. If the leader is interrupted, the host transfers coordination authority with a record and prevents the old leader from also finalizing.

Members choose for themselves to speak, critique, work or stay silent within the scope of the task. No forced round-robin; nor is every member woken for every message. Subscriptions by role and by relevant change help reduce useless invocations. Free discussion is still supported within a run that has been granted resources.

A conclusion must keep its reasons, evidence and unresolved critiques. A disagreement about method can create two small experiments if resources remain. The leader decides which result to use according to the contract, and does not equate majority agreement with correct evidence.

The leader may reassign work and raise/lower the tempo within the grant when the user is away. When a decision outside authority is needed, the team waits and sends one consolidated request. Independent steps may still run if the scope of the wait allows; if the contract requires stopping the whole tree, all descendants stop.

The leader is responsible for unifying the understanding of the need and for adjusting the inferred goal by itself within the root constraints. Members may challenge how the goal is set, using evidence; there is no need to wait for the user to choose a goal for each agent. Changing a parent goal makes the related children re-check before their next impact; one consolidated question replaces many agents asking repeatedly.

V1 does not build a social chat between agents. Exchanges must belong to a goal or to a test that has been granted resources. Exploring new ideas is a valid sub-goal when it is within the delegation to explore.

## 10 Authority and resources

Keep the existing names and meanings suggest, auto, full. Autonomy and authority to modify itself are separate axes, and are not folded into a fourth level that implicitly has every authority:

- proactivity: whether it may choose work by itself within the goal or only run when assigned;
- method modification: memory proposals, prompt, skill, workflow;
- assignment: calling an existing agent or creating a child agent;
- code modification: the workspace/code scope that is allowed;
- version application: whether it may put a verified build into operation by itself or only prepare a proposed build.

These are capabilities in the grant, and the UI may provide easy-to-understand presets. Full does not automatically carry authority to modify Jarvis 007's code. The user can turn that authority on once for exactly one agent/team/scope and is not asked again for every valid change.

Each grant has a principal, brain_id, scope, capability revisions, expires_at if any, parent_grant_id and a revocation generation. Check at decision time and again right before the impact. Write authority through a shell/API other than MCP must sit within the same execution boundary, not only through MCP.

A ResourceEnvelope uses a map of resource names and units, and does not require money. V1 measures calls, tokens and worker time; monetary cost is recorded only when the provider supplies reliable data. Reserve before a run, reconcile after a run. When price/usage is unclear, show unknown and use the agreed substitute resource cap, and do not treat it as free.

Tasks and experiments inherit the configured shared engine, model and limits; no need to declare them again per goal. Record the number of calls, the time and the usage the provider actually returns; a subscription plan quota that cannot be read is unknown. On hitting a limit, store a checkpoint and wait for the right condition, and do not loop with infinite retries, switch to a paid API by itself or use another account. Check the background-running capability and the service terms of the chosen engine at deployment time; do not pretend every subscription plan supports automation in the same way.

Revocation blocks issuing new runs and cancels running runs through the supervisor. An impact that has already gone out may not be revocable; record the uncertain result and reconcile before retrying. An action that does not support idempotency must not be blindly rerun after a crash.

## 11 Self-improvement through experiments

### 11.1 The experiment loop

Each Experiment stores the related goal, hypothesis, baseline_revision, candidate_revision, evaluation_revision, the set of scenarios, the budget, the scope of modification, the conditions to apply and the restore build.

The steps: find a concrete weakness; create a variant; run the baseline and the candidate on equivalent scenarios; collect independent receipts; compare success, errors, user effort and cost; apply if there is enough evidence. Unknown keeps the candidate in an inconclusive state.

There is a held-out set of scenarios to check generalization, and the candidate may not read the answers or edit the scoring results. The agent may propose extra tests but does not replace, by itself, the verification set being used to apply itself.

Not every goal is forced to have a cumulative score function. Acceptance may require reaching a minimum quality and reducing cost, or doing better on the main criterion without violating other conditions. The criteria are pinned before the comparison.

Distinguish the goal-adjustment loop from the method-comparison loop. If the contract changes while an experiment is running, the old results keep their scope; an experiment that no longer fits is recorded as inconclusive with the reason goal_reframed. To apply it to a new goal, re-check applicability and create a comparison on the same new revision. Do not reward changing the question in order to win. Improvement of the Goal framer is tested on the same inputs and held-out constraints, evaluating both fit and work results.

### 11.2 Exploration authority

The user may set aside part of the resources for exploration in the grant. The agent chooses worthwhile tests itself; a positive reaction is not required before trying. The exploration allocation sits within the total limit and does not create a separate unlimited resource wallet.

Keep the number of variants within the storage budget granted. A distinct variant may be kept even though it has not won, with a reason, to continue searching later. Do not try to keep every version or create unlimited agents.

### 11.3 Memory and lessons

New observations go into the evidence ledger first. A lesson has a status proposed/validated/superseded, a scope of application and evidence_ids. Only validated lessons are put into the self-learned part of memory; an explicit user instruction may confirm directly.

Reuse the existing JAVIS_LESSON path but add confirmation for sources from Resonance. Do not turn every emoji into a lesson. A lesson refuted by new evidence is removed from the context in use, keeping the history to explain.

### 11.4 Modifying Jarvis 007 itself

A code candidate runs in its own checkout and worker. A supervisor outside the candidate holds the authority to issue runs, verify, apply and restore. A trial build cannot write the protected evaluator, the original evidence, the grant or the supervisor's credentials.

Self-application is allowed when the grant has deploy authority and verification passes: functional checks, data compatibility, build/CI per the repo, a startup check, a limited trial run and then expansion. A health endpoint only proves part of liveness; a representative behavior check is required before confirming a good build.

Deploying code and restoring data are two different things. The first migration must be backward compatible or have a snapshot and a tested recovery path. Do not just reset Git and declare a complete rollback.

If the environment cannot yet create a real authority boundary, only support trials in an isolated workspace and preparing a candidate; the UI states clearly that controlled live self-update is not yet supported. Do not claim that a flag file under the same account is an unmodifiable kill switch.

## 12 Data and recoverability

Store the contract and runtime in JAVIS_STATE_DIR/resonance.sqlite3, partitioned by brain_id. The planned tables: intent_records, goals, goal_revisions, goal_events, goal_evidence_links, assessments, actions, wakeups, reservations, grants, group_memberships, experiments, variants and outbox. An IntentRecord stores references to the input, the constraints and the source; framing lives in goal_revisions; questions and answers live in goal_events with a linking id. Evidence payloads use the existing EvidenceStore, and do not copy secrets into JSONL or a prompt.

SQLite is the canonical source for revisions/authority/state. A Markdown contract can be exported for the user to read and take away; editing the export only creates a draft when imported again, and does not grant authority by itself. Do not add a goals folder to the global prompt.

Events with a source_event_id are deduplicated, with the time of occurrence and the time of receipt kept apart. A transaction writes the state and the outbox at the same time. A consumer may receive an event again but must be idempotent. A unique key prevents accepting two runs for the same logical action; a worker lease is time-limited and checks the revocation generation.

The existing EvidenceStore has finite retention. Evidence used for a goal or an experiment that is not yet closed must be pinned or have a suitable snapshot kept; after it ends, keep it according to the retention policy granted. The user still has the right to delete data; if data is deleted, the historical assessment records unavailable and must not pretend it can be re-verified.

A hash chain/append log does not replace an operating system boundary. A record that cannot be edited is only guaranteed within the access scope that has been verified.

Distinguish the optional communication log from the mandatory ledger needed for self-directed action: losing a secondary log does not break chat; if the action intent/authority/reservation cannot be stored before an impact, block that impact. If an impact has gone out but the receipt could not be stored, reconcile before issuing anything further or retrying. Do not create an id and then report a successful write when the save operation failed. A JSONL export serves re-reading, but a rotating file that can lose history is not used as the canonical source for undo or authority.

Each EvidenceEnvelope is linked to an assessment and an observation time, not only to the moment a tool returned data. A pin that keeps the record does not make old data into new data; freshness is always checked by the contract and the evaluator.

Message links are stored durably with brain_id, session_id, message_id, run_id and the action_ids that truly belong to that turn; the message_links table connects to the actions ledger. Store the message before emitting on WebSocket and return the same identifiers on the history-reading API. Reloading the page restores the result links and the undo state; a successful store/emit does not by itself prove the user read or used the result. Do not attach the same actor's files from the last ten minutes to an arbitrary message.

### 12.1 Conditional undo

Undo is a separate utility so the user can control impacts, not a default performance-penalty signal. It is shown only when the adapter has the capability and the preconditions still hold. For files, the host keeps an encrypted previous copy, the hash/version after the write, the allowed path scope and the action id. When undoing, check the current authority and compare the file's current state with the state after the write; if the user or another task has edited it, return a conflict, and do not overwrite or delete the newer copy.

An undo creates a new action pointing to the original action, with idempotency, a reservation and a receipt; a crash or two simultaneous requests do not create two compensating impacts. Check the path after resolve, symlinks/junctions, and locks/CAS as far as the backend allows. If detecting a change between the check and the write cannot be guaranteed, only create a separate recovery copy to view and compare. A snapshot that has expired or does not exist is not advertised as undoable. Do not infer the undoability of an external service from a write label; restoring code also does not replace undoing an external impact.

## 13 User interface

The entry point is the conversation "How can I help?" (in Vietnamese: "Anh muốn em giúp điều gì?") in Partners or a team. The user describes the need; the agent creates the goal by itself and starts the valid part of the work. Remove the screen that forces choosing a goal, the metric form and the default goal confirmation step. The Tasks page shows the goal the agent is pursuing and links to the execution tasks. Do not create a second Kanban system.

The "What Jarvis 007 is working toward" card shows: the current understanding, the status, the important unclear assumptions, the latest evidence, what is being done, what is being waited on and the reason for the next activity. It only explains a change of direction when it is meaningful; it does not ask for re-approval on every revision. Do not show a progress percentage if the criteria have no meaningful way to compute it.

The actions: add a description or correct the understanding in words, pause, resume, view evidence, view history, adjust authority, stop the goal tree. The goal and criteria details can be opened for inspection, and are not a form that must be filled in. The answer "I don't know yet" (in Vietnamese: "anh chưa biết") is accepted and moves to discovery within existing authority. A stop action states the scope and the impacts that have already happened. Results and requests for intervention are sent to the person/channel that assigned the work.

The file undo button is only added after the adapter in section 12.1 passes verification; it is not a condition for launching the first goal loop. Do not map an emoji to an implicit stop command. Stop and intent-correction commands have a clear action or wording, separate from communication reactions.

The UI uses easy-to-understand labels in the user's language; new strings have vi/en following the existing i18n structure. Evaluator parameters, tokens and revisions appear only in the detail section when useful. Reactions may stay as an independent communication feature, not a dependency for turning on Resonance.

## 14 Components that can be reused

The initial source snapshot used for planning: HEAD 5b4a9be1, branch codex/restore-chat-colors. A remote comparison on 6 October 2026 confirmed origin/main at 7d264236 (0.83.2), with 121 commits the old checkout lacks; the old checkout has 3 commits of its own. On this main there are _reply_policy_sandbox_engine and _reply_policy_ask. Before M1, check the latest main, record the base commit and re-verify the entire table below along with the integration points in the plan on that commit. The descriptions that follow are a historical survey, not a confirmation of the live execution path or of an integration contract that has been accepted on main.

AgentPolicy in server/agent_runtime.py defaults to off/allocation 0 when configuration is missing. Main has both a wired path and the old path continuing to work; the existence of a file does not prove the canary has run live. The MVP must have an end-to-end test with the chosen engine and simulated data on the host before depending on this runtime. Do not turn on the whole canary just for a demo; reuse the existing execution path that has been verified for a narrow scope.

| Existing component | Reuse | What needs to be added |
|---|---|---|
| server/self_improve.py | LoopFeature.tick, run_cycle, scheduler, mode, result reporting | An adapter that attaches goal_id, a single schedule owner, no use of the utility EMA to close a goal |
| server/agent_runtime.py | AgentRunner, CapabilityGrant, replan within authority | Receive GoalRunContext and a host-confirmed grant; flexible assignment authority with checks |
| server/workflow_runtime.py | Checkpoint, revision, resume, node history | Receive an authorization already granted; legacy workflows keep asking at write as they do now |
| server/workflow_runs.py | History of runs | Link a run to goal/revision; a run's done does not replace the goal verdict |
| server/task_store.py and server/tasks.py | Kanban, transaction, claim, dependency | Goal metadata and prevention of duplicate enqueue through the outbox |
| server/evidence_store.py | Evidence with hash, encryption, redaction and retention | Pin by goal/experiment; link provenance and observation time |
| server/capability_executor.py | Lease, invocation, idempotency/resource lock helpers | A goal authority adapter; do not assume this read-only executor already supports every write |
| server/context_runtime.py | Trace, checkpoint, audit and runtime event | Connect the goal ids, without depending on canary state to record mandatory evidence |
| server/updater.py and server/update_state.py | Startup, health check, source rollback | Wrap in a protected supervisor, behavior verification and data compatibility |
| dashboard/workspace.js and dashboard/console.js | Partners, visible team, Tasks, loop | Goal panel and scoreboard; the current visible group is not by itself a runtime group |

Do not use a readiness percentage to estimate the work. The paths that write through workflows, shell protection, evidence retention and self-update are items that must be tested separately.

## 15 Implementation roadmap

**Current priority:** the [MVP plan](../plans/2026-10-06-resonance-00-mvp.md), one agent/one goal, three new core modules and two small evaluators. Defer teams, the general self-learning module, time-series metrics, the supervisor and self-update. The table below is the direction of expansion after one real run exists, and is not an entry requirement of the MVP.

| Phase | Usable output | Condition to pass the phase |
|---|---|---|
| A Goal and evidence core | Infer a contract from a need, clarify, ingest evidence, evaluate, view the scoreboard | An ambiguous input does not make the user choose a goal; two kinds of goals use the same core; authority/revision/unknown are correct |
| B1 One executing agent | Carry out a goal through the existing runner, continue after an interruption | No duplicate runs, revocation takes effect, task done does not become success by itself |
| C1 Small improvement experiment | Compare two methods on a fixture, apply configuration within authority | The improvement is confirmed by independent receipts, the candidate cannot edit the scoring |
| B2 Teams and adaptive beat | Assign, finalize, wait for events, hibernate, resume | Leader failover does not finalize twice; a child does not exceed its parent's authority/budget |
| C2 Method self-modification | Lessons, skill/workflow, a bounded variant library | A worse build is not applied; a wrong lesson can be withdrawn |
| C3 Self-modification and updating Jarvis 007 | Code candidate, supervisor, limited trial, restore | The real boundary test and recovery through crash/migration pass |

The order is A -> B1 -> C1 -> B2 -> C2 -> C3. Do not wait to finish emotion handling or weeks of use before testing self-improvement. Do not fix calendar time before phase A is complete and the integration bottlenecks have been measured.

Detailed implementation plans:

1. [Goal and evidence core](../plans/2026-10-06-resonance-01-foundation.md).
2. [Goal execution and collaboration](../plans/2026-10-06-resonance-02-runtime.md).
3. [Self-improvement and version application](../plans/2026-10-06-resonance-03-evolution.md).

The first demo milestone needs only one natural-language request, one agent, one output adapter and one improvement experiment on simulated resources. Choose the needed parts in turn from A, B1 through B3 and C1/C2 to prove the closed loop; do not yet call the whole phase complete if the remaining criteria are not met. Teams, reactions and the undo button are not on the required path of this milestone. The chosen guard observation and the evidence links must still work from the start.

## 16 System-wide testing and acceptance

Three fixture groups that do not depend on the business domain: create a document with the correct structure and cited sources; maintain an index that matches a set of changing files; improve how a set of requests is handled on simulated resources. Adding a third fixture set must not add a domain-specific if branch to the core.

The controls are the same runner without learning, the Resonance runner with learning, and a team when collaboration effectiveness needs comparing. Use equivalent goals and the same budget, separate development data from held-out data, and reverse the test order to reduce time effects. Record unsuccessful runs and criteria that could not be measured. Do not infer long-term effectiveness from a few winning examples.

| Required scenario | Expected result |
|---|---|
| A worker says it is done but there is no evidence | The goal is not confirmed as met |
| An ambiguous request, the user does not know how to set a goal | The agent forms a hypothesis by itself and chooses a useful discovery step within authority |
| An optional question is not answered or is answered "don't know" | No pointless repeat asking; continue the independent part; silence is not treated as granting authority |
| An inferred goal is met but evidence deviates from the need | Revisit the goal; do not claim the need is solved just because a metric was met |
| The agent changes the goal or criteria in the middle of a test | The old revision keeps its result; changing the question is not counted as improvement; re-verify before applying |
| A goal changes when the budget is exhausted, paused or a guard has fired | Do not reset cost or reopen blocked activity by itself |
| A request with contradictory constraints or an infeasible destination | Explain the limit, do the compatible useful part; do not drop the user's constraints by itself |
| Data arriving late, corrected or duplicated | Update the correct revision, do not multiply scores or actions |
| The user corrects the goal while a worker is running | Do not apply an old result to close the new goal |
| Two workers claim the same item or allocate the same budget | One valid action, the total resources do not exceed the limit |
| A tool times out after it may have written externally | State uncertain, reconcile before retrying |
| The user stops the whole tree | No new run is issued to descendants, cancel runs within the host's ability |
| Evaluation data lost or evidence expired | Unknown, do not use a summary to pretend to prove |
| Maintain is met once and then the condition changes | Keep monitoring and record degraded/unknown correctly |
| A child agent wins but the parent does not progress | The parent is still not met; revisit the decomposition |
| A candidate edits the evaluator or fakes the test log | Not recognized or applied |
| An update starts but behaves wrongly | Do not expand the rollout, restore the previous build per the plan |
| A reaction changes, the result stays the same | No change to the performance evaluation |
| Two brains have a loop with the same slug or two runs by the same actor | Do not mix samples, authority, evidence or message links |
| A tool returns an error as content or contains many numbers | Do not treat an error code/date/id as the goal result |
| A multi-action tool is listed as read but the invocation writes | Check authority and record the receipt by the actual arguments |
| A guard crosses its threshold when there has been no agent action or the worker is asleep | Stop per the contract; do not wait for attribution or for the worker to wake |
| The audit store is lost before or after an impact | Before: block the impact; after: uncertain and reconcile, no blind retry |
| A file was edited by the user after the action that needs undoing | Conflict or a separate recovery copy, no loss of the new change |
| Chat refresh or WebSocket redelivers an event | Keep the correct message/run/action links, do not duplicate messages or undo |

## 17 Implementation and transition rules

A new feature is off by default for new installs and forks. Turn it on per chosen goal/brain; do not move a running loop to a goal by itself. Do not change the default full value of legacy loops just because Resonance was added.

Each phase has a compatible migration, regression tests and a feature kill switch. Per docs/quy-uoc-dev.md when starting to code: a separate branch, a version reservation and a draft PR before writing code, and integrate only on green CI. Writing this document set does not yet create a runtime, grant autonomous authority or launch a goal.

Deferred choices: a reward market between agents; a single metric that ranks all agents; learning emoji weights; a model retraining engine; a graph database; self-modification of the supervisor within the same experiment. Add them only when a real problem exists and a test proves them necessary.

Cross-check the reference code against the [latest review](2026-10-06-resonance-revised-package-review.md), including the bugs that were reproduced and the corrections about the code branch. The older critiques are archived in the [historical package](../../../exports/archive/Javis-Resonance-LICH-SU-2026-10-06.zip). The index and the current order of use are in the [Resonance README](../README-RESONANCE.md).

## 18 References

- [FranklinCovey on the four disciplines of execution](https://www.franklincovey.com/courses/the-4-disciplines/): focus on the goal, leading indicators, a scoreboard and a cadence of accountability. The mapping onto agents in this document is Jarvis 007's design.
- [FranklinCovey on goals with a starting point and a deadline](https://www.franklincovey.com/blog/strategic-execution-in-uncertainty-and-complexity/).
- [FranklinCovey on leading and lagging indicators](https://www.franklincovey.com/courses/the-4-disciplines/discipline-2-act/).
- [FranklinCovey on the cadence of accountability](https://www.franklincovey.com/courses/the-4-disciplines/discipline-4-accountability/).
- [Sakana AI on the Darwin Gödel Machine](https://sakana.ai/dgm/): research on self-modifying code, evaluating and keeping variants; not a guarantee that Resonance improves itself without limit.
- [MCP on the limits of tool annotations](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/).
