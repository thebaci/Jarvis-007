# Resonance for agents: scope and roadmap after the MVP

Direction settled on: 2026-10-08. Reference code: main `09f254d0e4d009451dc58cb2e97788631c5acc1a` (0.86.1). The Resonance MVP shipped in 0.86.0, commit `438f8309`, PR #587.

**Document status:** product direction following the project owner's new requirements, with a roadmap and acceptance conditions. Progress as of 2026-10-12: A1 shipped in 0.87.0 (section 12), A2 shipped in 0.88.0 (section 13); A3 shipped in 0.89.0 (`33a3c1aa`, PR #598, [A3 design](2026-10-09-resonance-a3-feedback-learning-design.md), record [resonance-a3-verification](../../dev/resonance-a3-verification.md)); A4 design settled, code passed review round 5 (`5b5e3ef0`); UI smoke test with a fake engine done, one card bug fixed (`f6aeb6d1`); one real pilot (2 Claude Code Opus turns, 0 background jobs; the raw result was `technical_failed` because of the runner, closed by a post-hoc check; the final version met the content bar, the first version added a date on its own); **shipped in 0.96.0** (`d36ebb3e`, PR #604, 2026-10-11; `main` CI run 38146898745 and image build run 38146898746 succeeded; image `ghcr.io/blogminhquy/javis-os:0.96.0`, digest `sha256:8f1751d2…`; the VPS has not pulled it) ([A4 design](2026-10-10-resonance-a4-handoff-grants-design.md), record [resonance-a4-verification](../../dev/resonance-a4-verification.md)); A5 design settled (round 3, `56f7ab50`), **code passed review round 2 at `05e9b065`; the real pilot real-2 at `33cec518` was accepted by the reviewer within the scope of a single `pass_first` sample (1 maker turn, 1 review turn, 0 chats; the fix loop is not yet proven with a real model); shipped in 0.109.0 (`bfb1c29f`, PR #616, 2026-10-13; `main` CI run 38369853756 and image build run 38369852881 succeeded; image `ghcr.io/blogminhquy/javis-os:0.109.0`, digest `sha256:3890f824…`; the VPS has not pulled it)** ([A5 design](2026-10-11-resonance-a5-maker-reviewer-design.md), record [resonance-a5-verification](../../dev/resonance-a5-verification.md)). A1 to A5 are the Resonance foundation, with the agreed scope completed; the next item is the team chat group ([team chat group design](2026-10-13-team-chat-design.md), awaiting review); tags continue as a separate system. This is not an order to run a model, enable a feature or change a live system. The detailed code plan for each PR is written from this document and the latest code when work starts.

## 1. What the owner wants and what stays

- Resonance equips **each agent**; it does not automatically equip ordinary conversations.
- Each agent has a clear Resonance switch. The agent forms its goal from the assignment on its own; users are not asked to pick or fill in a goal.
- The agent knows when to work and when to wait; the adaptive heartbeat and the learning loop from feedback must come in the post-MVP phase, before the AI team.
- The base rules are few and fixed; methods, schedules, lessons and presentation can change within that range.
- M1 to M5 are not redone: keep the goal store, revisions, receipts, evidence, guards, budgets, product handoff, cards and the method trial.

The scope of "all progress" in this review is the Resonance program plus the related agent/workflow/loop/learning systems in Jarvis 007. It is not an audit of every other Jarvis 007 feature or a re-verification of the whole test suite.

## 2. Four invariants as the common frame

1. **Owner and authority:** every goal has a responsible agent determined by the host, in the right brain, with the right permissions and budget. Chat or the model cannot declare its own identity to obtain permissions.
2. **Grounded results:** success rests on criteria and evidence for the right revision/product; not on the model's word alone, a reaction or the number of work attempts.
3. **The right to stop always wins:** switching off, pausing, cancelling, revoking permissions and guards are checked before the next action; learning must not reopen these stops by itself.
4. **Changes must be traceable:** record the source of the request, the decision, the product, the feedback and the method; an applied change has a scope and a suitable way back. Do not promise to undo effects that cannot be undone.

Do not add one "master beat score" that decides authority, grades success and drives frequency all at once. Signals with different meanings must stay separate.

## 3. The new product boundary

| Context | Target behavior |
|---|---|
| Ordinary chat | Answer or do one-off work through the existing mechanism; do not create a Resonance goal or a pursuit schedule on its own |
| Chat that clearly assigns work to an agent | Extension direction after A1: the host hands off to an equipped agent with a trace. A1 does not implement this path |
| Chat with an agent that has Resonance | Still tells apart Q&A, one-off work, continuing a goal and creating a goal; no goal for every message |
| Workflow, loop, chatbot, external channel | Use Resonance only when an adapter identifies the agent and delegation is explicit; where not wired, do not infer authority implicitly |
| AI team later | One agent is responsible for the goal; maker/reviewer roles are granted scopes, with no overlapping ownership |

Brain is where shared data and configuration live; engine is the machine that runs; agent is the subject that performs the work. Do not use these three concepts interchangeably. Source data from an `agent:<slug>` session can be used by the host to resolve the agent, but a slug in a prompt is not a basis for granting authority.

## 4. A1: agent scope, switch and minimal progress

**This is the first functional PR to build.** The A1 scope has been narrowed: it only creates goals from an equipped agent's session; the path for assigning work from ordinary chat is split into an item after A1 and is not merged implicitly into A2. Combine the minimal screen with the switch so users see the state of the agent they just enabled right away.

### Identity and permission gate

- Add the agent link to goals and events. Use a persistent identity within the brain; renaming the display name must not move authority or lose goals. Review how agents are currently stored before choosing a concrete schema.
- The host resolves the agent from the authenticated session/dispatch path. Apply the same gate at the tool, the HTTP API, the scheduler, the intake/publish-product step and the method trial. Do not just hide `javis_goal` from the tool list.
- The current `Principal("agent", "javis", brain)` is not enough as a separate identity for multiple agents. `/goal-requests` must also go through the agent gate and must not become a side door from ordinary chat.
- Goal lists, feedback, revisions and products must be filtered by the right agent/brain, including two brains with the same slug. The owner user has a goal management path under existing permissions.

### Switch

One **Resonance** switch in the agent configuration, off by default until equipped. Turning Resonance off does not turn off the agent's ability to chat or do one-off work, and does not affect independent loops/reminders.

| Action | Semantics |
|---|---|
| On | Allows the agent to accept and continue valid goals within its permissions/budget; does not reopen guards, pauses or cancelled goals by itself |
| Off | Blocks taking new turns and new actions; requests running work to stop as far as the engine allows; keeps data for review |
| A model turn in progress | A turn that has already started still counts; do not advertise "instant stop" or refunded cost. Block publishing/submitting once permission is revoked; save the result for reconciliation if there is one |
| On again | Reconcile unfinished parts, reuse valid output when eligible; do not duplicate actions or start a goal that has ended |

Proposal: store the effective flag and a configuration version number in a host-managed source, so that budget-holding and application decisions can be checked for consistency. Do not let the agent write the configuration file itself to turn its own permission back on. Persistence details and synchronization with agent metadata must be settled in the A1 PR design.

### Migrating old data

- The old `Javis/resonance.json` is a per-brain flag; it must not be automatically multiplied into "every agent is on". It may be kept as an overall admin switch during the transition, but the UI must say clearly when it blocks an agent.
- Old goals without a trustworthy agent identity: keep the history intact and put them in a waiting-to-assign list. Do not assign by similar name or latest session. The owner assigns once through a permission-checked path; only then are they eligible to continue running.
- New goals belong only to an agent; ordinary chat may display delegated progress but must not itself become the executing subject.
- Do not delete SQLite, evidence or accepted goals to "clean up" the migration. Test with a copy of the old data and a recovery path before release.

### Minimal screen on the agent page

Show: on/off, goal/revision, criteria met/not met/unknown with their basis, the product currently in effect, who it is waiting on or what blocks it, the next wake time and why, budget used/remaining, a stop button. Ordinary chat only shows a card linking to the agent's goal when work has been assigned.

Do not use a percentage guessed by the model. A ratio of verified criteria, if shown, must be named accurately and not treated as a percentage of workload.

**A1 acceptance:** ordinary chat creates no goal even when the API/tool is called directly; enabling agent A does not grant permission to agent B; switching off during a turn blocks the next step; rename/delete/restart do not move the owner by mistake; old data is neither lost nor run on its own; cards and controls work for the right agent.

## 5. A2: adaptive heartbeat

The MVP schedule already has claim/lease, next_wake, backoff and restart. Reuse that foundation; do not build another independent scheduler that calls the model in parallel.

A heartbeat is a host step that checks whether there is a valid reason to execute. With no reason, no engine is built and no model is called.

- Prioritize useful events: new feedback, a changed data source, a sub-task result, or a review milestone that is genuinely due.
- When waiting for user feedback, sleep; silence is not penalized and does not become authority to act.
- When there is a useful next step, keep the turn within budget; on error or missing information, slow the rhythm or wait for the exact condition. No unlimited automatic retries.
- Merge duplicate events; one event, one logical action. Notifications emitted by the agent itself must not trigger a self-calling loop.
- Separate the guard observation schedule from the work schedule. Slowing the worker must not drop monitoring of a committed guard; revoking observation permission must report loss of monitoring capability, not pretend it is clear.
- A job already attached to a goal has only one schedule owner. Other old loops and fixed-time reminders keep their current semantics.
- Frequency is the outcome of a versioned policy, based on state, new information, urgency and remaining cost. Minimum/maximum intervals are configuration; do not add fixed rules by industry.

**A2 acceptance:** a fake clock tests sleep/wake, duplicate events, two schedulers, restart, a recovering source, guards while the worker sleeps, budget exhaustion and switching the agent off; every wake has a traceable reason; with no event to handle there are 0 model turns.

## 6. A3: feedback loop and learning from reactions

M4 already has feedback on interpretation/output; M5 already has compare_methods and application within a revision. What is new is turning sourced feedback into learning proposals, trials and records, without attaching emoji scores directly to the scheduler.

| Signal | Used for | Must not be inferred as |
|---|---|---|
| Reaction on the agent's words | Hypotheses about presentation, length, timing of updates, level of interruption | Work done, added permissions, higher budget, more turns on its own |
| Right on point / Misunderstood | Correct or confirm the interpretation of the exact revision | The product has passed |
| Meets the bar / Needs changes | The human_confirmation criterion of the exact artifact hash/revision | Overriding a guard or replacing an objective check result |
| Measured results, evidence, cost | Compare methods on the same yardstick | Attributing every fluctuation to the agent's actions without grounds |

Target loop: **record sourced feedback → propose a small change → trial within budget → compare with the old way → apply within the verified scope or keep as is → keep observing**.

- A changed/revoked reaction must replace the old contribution and not add a point each time it is clicked; attach it to the message, agent, goal/revision/artifact where relevant, and the person reacting must have permission.
- Ordinary chat is not collected into a global Resonance learning loop. Feedback on an agent's card can reach that agent even when the card is viewed in ordinary chat.
- Do not penalize users for not clicking. A reaction does not spawn a model turn by itself; batch feedback to process in the same valid turn or within the granted exploration budget.
- An initial lesson is a hypothesis with scope and evidence. It does not become a system-wide preference just because one person liked one reply.
- Feedback like "say less" may reduce the number of notifications; it must not slow guard checks or hide a mandatory warning. Feedback must not turn a hard task into an easy criterion to score higher.
- A good method is applied through the M5 trial mechanism; it stays limited to the revision until there is evidence of transfer. Presentation style can be stored per agent/user but still has provenance and can be withdrawn.

**A3 acceptance:** a thumbs up does not make a goal succeed; a thumbs down does not record an objective failure by itself; no feedback is unknown; late/wrong-revision feedback is not applied by mistake; clicking again does not raise the score; a losing/unknown candidate keeps the old way; revoking a lesson stops its application.

## 7. A4 and A5

**A4: multi-engine product handoff.** One host contract checks path/permissions, execution result, bytes/hash and revision. Claude Code currently has a successful Write adapter; add adapters for Codex/Grok/Antigravity one by one, or submit content for the host to write within the right permissions. A model's self-declaration is not a receipt. The same test set is used to compare equivalence; do not claim every engine is supported just because the API name is the same.

**A5: AI team that makes and reviews.** Reuse the workflow graph, verify_agent and the runtime with grants; start with one maker agent and one reviewer agent, with one goal ultimately responsible. The review is tied to the exact hash/revision, the reviewer does not edit the criteria itself, and both use a shared budget with allocated shares. A version edited after review must be reviewed again. When the owner stops, both stop within the scope of the work, and no new agent is spawned to get around the stop.

The AI team comes after A1 to A3. On the default roadmap A4 comes before A5 to unify handoff; if only one verified engine is used, A4 is not a mandatory technical dependency of the two-role model.

## 8. Order, outputs and completion gates

| Milestone | Visible result | Status as of 2026-10-11 |
|---|---|---|
| D0 | Operational check on the deployment machine | Localhost trial pinned to `438f8309` (0.86.0) passed 13 no-model checks and 1 real chat; commit, how it was run and results are in the [D0 record](../../dev/resonance-d0-local-check-2026-10-08.md). VPS not checked, does not block the A1 design |
| A1 | Agent page has a Resonance switch, goals under the right owner and minimal progress | Passed code review (`cc79deb2`), pilot A1-1 passed technically and on content in one scenario. Shipped in 0.87.0 (`fdfec7c5`, PR #590). Record: [resonance-a1-verification](../../dev/resonance-a1-verification.md) |
| A2 | The agent wakes for a specific reason, sleeps when waiting, makes no useless model calls | Design passed (`cb11fc23`), code passed review (`b5975b7e`), final review passed (`b80ae0ea`). Shipped in 0.88.0 (`c101d108`, PR #593); VPS performance not measured. Record: [resonance-a2-verification](../../dev/resonance-a2-verification.md) |
| A3 | Feedback leads to verified adjustments; does not chase emoji | Shipped in 0.89.0 (`33a3c1aa`, PR #598). One pilot on the M lane (4 Sonnet turns, a tie, not applied). Record: [resonance-a3-verification](../../dev/resonance-a3-verification.md) |
| A4 | Engines submit products under the same host contract | Shipped in 0.96.0 (`d36ebb3e`, PR #604). One real pilot sample on Claude Code (2 chat turns, 0 background jobs), closed by a post-hoc check; other engines checked only with a fake engine. The `javis_submit_deliverable` tool for Claude, Codex and API engines; the scope is allowed by the project owner on the card (not granted from chat words). [A4 design](2026-10-10-resonance-a4-handoff-grants-design.md), [record](../../dev/resonance-a4-verification.md) |
| A5 | One agent makes, one agent reviews; clearly says who is waiting on whom | Shipped in 0.109.0 (`bfb1c29f`, PR #616). Real pilot real-2 accepted within the scope of a single `pass_first` sample; the fix loop is not yet proven with a real model: [A5 design](2026-10-11-resonance-a5-maker-reviewer-design.md), [guide](../../dev/resonance-a5-team.md). Record: [resonance-a5-verification](../../dev/resonance-a5-verification.md) |
| Team chat group | Multiple groups; a lead coordinates; @ assigns work; a queue with a Prioritize button; a Resonance switch on the assistant row; six reactions; the lead is Limited permissions or Full permissions | Round 1 design awaiting review ([team chat group design](2026-10-13-team-chat-design.md)); no code yet |

A1 to A5 are a development order, not five features that already exist. Each milestone produces a PR or small PRs with their own verification value; there is no need to reserve all the version numbers right now. Do not give completion dates or % effort before an estimate exists.

Call a real model only when the pilot conditions/goal and the budget for that run are clear; the budgets of old pilots do not become permission to call more. Reviewing this document does not by itself open a feature release.

## 9. Mapping to the old 01/02/03 plan set

| Old plan | How it continues |
|---|---|
| A1 to A4 Foundation: contract/store/evaluator/framer | The MVP built the core. Review the gaps and agent scope; do not rebuild in parallel |
| A5 Foundation and B5 Runtime: UI | The single-agent part moves early into the new A1; the group UI is left to the new A5 |
| B1/B2: grants/execution | Reuse M1/M3 and add the per-agent gate in A1 |
| B3: beat | Becomes the new A2, using the existing schedule, without waiting for the whole Runtime |
| C1/C2: method trial/application | Use M5 as the base of A3; keep the existing evidence limits |
| C3: sourced lessons | Move the feedback part into the new A3 |
| B4: groups/sub-goals | Narrowed at first to the A5 maker/review pair |
| B6, C4/C5: general undo, supervisor, self-fixing code | Deferred; not on the required path of the next phase |

The three old plans are reference documents; they are not executed sequentially in full after the MVP. When they conflict on the **new scope and the post-MVP order**, this 2026-10-08 document takes priority. Do not rewrite the acceptance history of M1 to M5.

## 10. Points to settle when writing the A1 PR design

Persistent agent identity and rename/delete; the host-controlled store for the switch; schema/migration for old goals; delegation from chat/external channels; permission limits for an agent connected to customers; the lifecycle of running work when switched off. These are technical decisions that need the latest code read, not questions that make the user set their own goal.

Audit source and evidence gaps: [Progress report of 2026-10-08](../../dev/resonance-progress-audit-2026-10-08.md). Tracking page: HTML (`exports/javis-resonance-tien-do.html`, outside git, only on the project's server).

## 11. Update after the A1 proposal review (2026-10-08)

- **A1 scope narrowed:** only create goals in the session of an agent with Resonance enabled. The path of assigning work from ordinary chat to an agent is a separate item after A1, not merged into A2. Ordinary chat can still view valid cards under the project owner's permissions; the stop and cancel commands do not lose effect.
- **D0:** record [resonance-d0-local-check-2026-10-08.md](../../dev/resonance-d0-local-check-2026-10-08.md). Local operational evidence, not the VPS or the port 7777 server.
- **A1 design:** [2026-10-08-resonance-a1-agent-scope-design.md](2026-10-08-resonance-a1-agent-scope-design.md). It has passed the review rounds; see section 12 below.

## 12. A1 progress (2026-10-08)

- **Code:** PR #590. Code review passed at `cc79deb2`; `e01eb3c2` added a recovery regression test, `e0a60352` added the pilot record.
- **Pilot A1-1** (assistant session, 2 Opus chat turns, 0 Sonnet background jobs, simulated final confirmation): passed technically and on content, in one scenario.
- **Acceptance record:** [resonance-a1-verification](../../dev/resonance-a1-verification.md).
- **Release:** 0.87.0, PR #590 squashed into `fdfec7c5` (2026-10-09). VPS performance is handled separately (#592 not merged).

## 13. A2 progress (2026-10-09)

- **PR #593** (0.88.0), stacked on A1. Design passed review in round 4 (`cb11fc23`); code passed review at `b5975b7e` after three rounds of fixes.
- **Integration check:** a dry smoke test on the real server (0 engine turns), a look at the heartbeat UI on a sandbox.
- **Record:** [resonance-a2-verification](../../dev/resonance-a2-verification.md).
- **Release:** 0.88.0, PR #593 squashed into `c101d108` (2026-10-09), GHCR image 0.88.0.
- **Not done:** VPS performance not measured. A3 shipped in 0.89.0; A4 shipped in 0.96.0 (`d36ebb3e`); A5 shipped in 0.109.0 (`bfb1c29f`). Next item: the team chat group (design awaiting review).

## 14. After A1 to A5: the team chat group (2026-10-13)

- **A1 to A5 are the Resonance foundation with the agreed scope completed** (A5 shipped in 0.109.0, `bfb1c29f`). The limits of the A5 pilot stay as they are: a single `pass_first` sample, the reviewer has not received the original assignment, the fix loop is not yet proven with a real model.
- **Next item: the multi-agent team chat group** ([team chat group design](2026-10-13-team-chat-design.md), [code review](../../dev/team-chat-audit-2026-10-13.md), [wireframes](../../dev/team-chat-wireframes.md)).
  - Includes: multiple groups, a lead who coordinates, @ to assign work, a queue with a Prioritize button, a Resonance switch on the assistant row, six reactions, two lead modes (Limited permissions, Full permissions).
  - Status: round 1 design awaiting review; no code yet.
- **Tags remain a separate classification system**, not chat groups.
- **The A5 maker/review pair is not a structure of the group:** an agent in a group can still have a Resonance goal with an A5 pair.
- **Separate items noted, not yet implemented:**
  - request source pinned by the host for the A5 reviewer;
  - background-job usage on the shared usage screen;
  - pull the new build onto the VPS and re-measure (needs separate approval).
