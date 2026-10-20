# Resonance progress review and agent scope adjustment

Review date: 2026-10-08, Asia/Saigon. Code snapshot: `09f254d0e4d009451dc58cb2e97788631c5acc1a` (main 0.86.1). Scope: Resonance, the related agent/workflow/loop/learning code, and the progress documents. This is not an audit of every Jarvis 007 feature.

## Update after A1 (2026-10-08, evening)

The rest of this document is a snapshot from the time of the review (morning of 2026-10-08), kept as history. Since then:
- A1 passed code review and pilot A1-1 (one scenario), and shipped as 0.87.0 on 2026-10-09 (`fdfec7c5`). See the [A1 record](resonance-a1-verification.md).
- A2 shipped as 0.88.0 on 2026-10-09 (`c101d108`); VPS performance not measured. See the [A2 record](resonance-a2-verification.md).
- The "0/5 milestones" figure below is from the time of the review. A1 counts as a finished milestone only once it is merged and released.

## Addendum after the local check report

According to the report Claude relayed from the project owner: the localhost 0.86.0 test server passed 13 no-model checks and one real chat (1 Opus, engine ok, turn completed). ChatGPT has not been re-run; the report/log and commit still need to be attached to the deployment record. Do not infer that the real server on port 7777 or a VPS was checked. The VPS is still unchecked because the Hostinger connection dropped.

A1 is narrowed to the agent session; handing off from ordinary chat is split out after A1. See the review and the Claude instructions (`exports/reviews/Resonance-A1-review-and-Claude-instructions-2026-10-08.md`, outside git, only on the project owner's machine).

## Progress conclusion

- **MVP M1-M5: 5/5 milestones finished and released in 0.86.0.** Squash `438f83097db4ee64e96b7b4880deb581521f217a`, PR #587. The stacked PRs are closed; do not restart from M1.
- Main is now at **0.86.1**; PR #589 improves how Codex's running step is shown, and is not a new Resonance milestone.
- Pilot 5 passed on content and technically in one scenario: 2 Opus turns, 0 Sonnet, simulated final confirmation. Do not generalize this to every engine or channel, or to routing always being right.
- **New direction A1-A5: 0/5 new milestones accepted.** There is a substantial reusable base; this figure counts milestones, it is not 0% of the code or 0% of the effort.
- There is no evidence that any specific VPS was updated and runs stably. There is no evidence that goal execution granted per agent exists in the current product.
- At the time of the review, the open PR list returned by GitHub was empty. No open PR is used as evidence that A1-A5 have started.

## What did M1-M5 deliver?

| Milestone | Result so far | Limit to keep in mind |
|---|---|---|
| M1 | Execution engine with receipts, quota, errors and usage | Do not infer that every engine has the same capability |
| M2 | Goals formed/updated automatically, stored handoffs and revisions | Scope is currently per brain, with the shared agent javis; not a dedicated agent |
| M3 | Do/check/wait/stop, guard, evidence, next_wake, restart | Not yet an adaptive scheduler that learns by value for each agent |
| M4 | Cards, feedback on understanding/output, controls, duplicate-report prevention | Switch is per brain; no separate per-agent progress screen yet |
| M5 | Compare methods, trial limits, conditional apply | Does not yet propose trials by itself; no reaction learning loop yet; the real pilot has not applied the winning candidate |

The handoff after pilot 3 added acceptance of a successful Write from Claude Code; pilot 5 proved the path chat → acceptance → feedback → acceptance of the revised version. Not calling Sonnet that time was the correct rewrite-avoiding case, not a missing make-up turn.

## Code evidence and reusable parts

| Where read at the snapshot | Observation | Effect on the plan |
|---|---|---|
| `server/resonance.py: enabled_for` | Reads `<brain>/Javis/resonance.json`; off if missing or broken | The switch is not yet per agent |
| `system/plugins/javis-goal/plugin.py: javis_goal` | Uses Principal agent/javis, gated per brain; `_turn` relies on the web turn | Identity and tool gate must change in A1 |
| `server/resonance_api.py: goal_request` | The goal form goes through agent/javis in the brain | The HTTP bypass must be blocked, not just the UI changed |
| `server/resonance_store.py: _SCHEMA` | A goal has brain/owner/session; no separate executing-agent key | Needs a migration with a subject; do not treat owner as agent_id |
| `server/workflow_chat.py: persona_cua_phien` | Resolves session agent:<slug>/workflow:<slug> | An identity integration point exists, but it is not itself a permission policy |
| `server/resonance.py: next_wake, advance, tick` | Already has cheap scheduling, backoff, waiting, lease; reaction is skipped when the schedule changes | A2 reuses it; A3 does not wire emoji points straight into the rhythm |
| `server/resonance_store.py: record_feedback, fit_status` and `dashboard/chat-resonance.js` | Feedback tied to the right revision and hash | A base to reuse for the learning loop, not yet a complete learning loop |
| `server/resonance.py: compare_methods`, `server/resonance_store.py: apply_method` | Tries on the same measure and applies with limited scope | Use for A3; do not build a large ExperimentService first |
| `server/self_improve.py: LoopFeature` | Loops have config/schedule/mode and a result-reporting mechanism | Avoid a goal and a loop both running the same job; do not replace every loop with Resonance |
| `server/learn.py` | Has a self-learning system, fork/promote, quotas and a curator schedule | Cannot say Jarvis 007 has no learning; needs an adapter/scope so two systems do not both edit one agent |
| `server/agent_runtime.py`, `workflow_graph.py` | Agents have replan with a grant; workflows have verify_agent | The Resonance team does not exist yet, but there is a do/review base to connect to |
| `dashboard/chatbots-reply-policy.js` | Has a thumb attached to the chatbot's reply decision | Do not treat it as a general reaction loop for Resonance |

Do not confuse the heartbeat that keeps a connection alive, or the voice-call heartbeat, with the goal-execution rhythm.

## Discrepancies in the records fixed in this pass

1. The old HTML stopped at 80% and at the review before pilot 2; replaced with the 0.86.0 release milestone, the main 0.86.1 snapshot and the new roadmap.
2. The old README said the document set had not proven deployment and told readers to start M1; changed to the current index, agent guidance and released records.
3. The old M1-M5 implementation command file still carried pilot quotas and run commands; labeled as history, and the old quota is not granted again for new work.
4. The old specs and plans 00/01/02/03 are kept for reference, with pointers to the new documents added. No evidence deleted and no past result rewritten.

The version before the edit is stored with a SHA-256 manifest at `exports/archive/resonance-before-agent-scope-20261008-120051/`.

## Current roadmap

**A1 agent + switch + minimal progress → A2 adaptive heartbeat → A3 learning from feedback → A4 multi-engine handoff → A5 do/review team.**

Checking one VPS (D0) can run in parallel with A1 design work; a trial with a model needs the scope and quota of that trial. Do not use a completion date or an arbitrary overall percentage for the parts not yet estimated.

See the [detailed scope and acceptance conditions](../superpowers/specs/2026-10-08-resonance-agent-scope-roadmap.md).

## Output status of this review

Documents and the tracking HTML page were updated. **No runtime, schema, API, live switch or brain/agent configuration was changed.** No model was called, the main checkout branch was not changed, and nothing was committed, pushed or deployed to a user machine. The A1-A5 behavior changes need the follow-up PRs.

The document files in the main checkout are currently a local working copy (the main checkout is still on the old branch); the source code was read from a separate review checkout at the main snapshot named at the top of this document. When handing over for implementation, bring the new documents onto a branch based on the latest main; do not code on the old checkout and do not treat historical line numbers as a contract.

## Release and acceptance sources

- [PR #587](https://github.com/blogminhquy/javis-os/pull/587)
- [CI after merge](https://github.com/blogminhquy/javis-os/actions/runs/37726542811)
- [Build/push 0.86.0](https://github.com/blogminhquy/javis-os/actions/runs/37726542815)
- [Pilot 5 record at the evidence commit](https://github.com/blogminhquy/javis-os/blob/450dd095/docs/dev/resonance-mvp-e2e-pilot-5.json)
- Independent content review (`exports/reviews/PR-579-pilot5-content-review.md`, outside git, only on the project owner's machine)
- Post-release review (`exports/reviews/Resonance-0860-post-release-review.md`, outside git, only on the project owner's machine)
- New tracking page (`exports/javis-resonance-tien-do.html`, outside git, only on the project owner's machine)
