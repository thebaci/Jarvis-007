# Jarvis 007 Resonance: current progress and direction

Updated 2026-10-08. MVP M1-M5 shipped in 0.86.0 via PR #587; main at review time was 0.86.1 (`09f254d0`). The next direction follows the project owner's request: Resonance per agent, with its own switch, adaptive heartbeat and learning from feedback.

## Read these three documents first

| Document | Role |
|---|---|
| [Agent scope and new roadmap](specs/2026-10-08-resonance-agent-scope-roadmap.md) | Direction after the MVP, four invariants, A1-A5 and acceptance conditions |
| [Progress audit report](../dev/resonance-progress-audit-2026-10-08.md) | What already exists in code, the reusable base, and the evidence gaps |
| Tracking HTML page (`exports/javis-resonance-tien-do.html`, outside git, only on the project's host machine) | The version that is easy for the project owner to read, separating what has shipped from what has not been done |

## Current roadmap

A1: agent scope + switch + minimal progress. A2: adaptive heartbeat. A3: learning loop from feedback. A4: multi-engine product handoff. A5: team with one agent doing the work and one reviewing. After A5: multi-agent team chat group (team lead, priority queue, six reactions), see the [team chat group design](specs/2026-10-13-team-chat-design.md). Auditing one representative VPS (D0) can run in parallel with the A1 design.

Progress on 2026-10-12: A1 shipped in 0.87.0 (`fdfec7c5`, [record](../dev/resonance-a1-verification.md)); A2 shipped in 0.88.0 (`c101d108`, [record](../dev/resonance-a2-verification.md)), VPS performance not yet measured; A3 shipped in 0.89.0 (`33a3c1aa`, PR #598, [A3 design](specs/2026-10-09-resonance-a3-feedback-learning-design.md), [guide](../dev/resonance-a3-learning.md), [record](../dev/resonance-a3-verification.md)); A4 design locked (D1: no write grants from chat wording), code passed review round 5 (`5b5e3ef0`); UI smoke test with a fake engine done, one card bug fixed (`f6aeb6d1`); the pilot runner passed gate review (`5305687a`, dry 13/13); **the real pilot has run once** at `5305687a` (2 Claude Code Opus turns on a subscription plan, 0 background jobs; the raw result was `technical_failed` because the runner wrongly excluded the host's turn card, the runner was fixed and the run closed with an offline post-check; the final version passed on content, the first version added a date on its own); **shipped in 0.96.0** (`d36ebb3e`, PR #604, 2026-10-11; CI `main` run 38146898745 and image build run 38146898746 succeeded; image `ghcr.io/blogminhquy/javis-os:0.96.0`, digest `sha256:8f1751d2…`; VPS has not pulled it) ([A4 design](specs/2026-10-10-resonance-a4-handoff-grants-design.md), [guide](../dev/resonance-a4-grants.md), [record](../dev/resonance-a4-verification.md)); A5 design locked (round 3, `56f7ab50`; option A for hand-edited files), **code passed review round 2 at `05e9b065`; the real pilot real-2 at `33cec518` was accepted by the reviewer within the scope of one `pass_first` sample (1 work turn, 1 review turn, 0 chat; the fix loop with a real model is not yet proven); shipped in 0.109.0 (`bfb1c29f`, PR #616, 2026-10-13; CI `main` run 38369853756 and image build run 38369852881 succeeded; image `ghcr.io/blogminhquy/javis-os:0.109.0`, digest `sha256:3890f824…`; VPS has not pulled it)** ([A5 design](specs/2026-10-11-resonance-a5-maker-reviewer-design.md), [guide](../dev/resonance-a5-team.md), [record](../dev/resonance-a5-verification.md)). **A1 through A5 are the Resonance foundation, with the agreed scope completed.** Next item: multi-agent team chat group, [team chat group design](specs/2026-10-13-team-chat-design.md) (round 1, awaiting review); tags remain a separate classification system. Do not turn features on by yourself or reuse the quota of the old pilots. Before coding, write the design and the PR plan against the latest main; users do not have to fill in or choose business goals.

## Completed MVP, kept as history

- [Design of 06/10](specs/2026-10-06-javis-resonance-design.md).
- [M1-M5 plan](plans/2026-10-06-resonance-00-mvp.md).
- [Cross-check of the older packages](specs/2026-10-06-resonance-revised-package-review.md).
- Content review of pilot 5 (`exports/reviews/PR-579-pilot5-content-review.md`, outside git, only on the project's host machine).
- [Release PR #587](https://github.com/blogminhquy/javis-os/pull/587).

Do not rerun M1 just because the historical checklist is not ticked. One passing pilot sample does not prove that every engine/channel is supported; the final simulation sign-off and that scope are kept unchanged in the record.

## Older expansion plans

[01 Foundation](plans/2026-10-06-resonance-01-foundation.md), [02 Runtime](plans/2026-10-06-resonance-02-runtime.md), [03 Evolution](plans/2026-10-06-resonance-03-evolution.md) are reference sources. Do not execute them strictly in sequence. The mapping table to A1-A5 is in the 08/10 document; the new scope and order in that document take priority.

## Working base and history preservation

The main checkout may still be on the old branch `codex/restore-chat-colors`. The review read the code in a separate checkout at `09f254d0`; before implementing, fetch and lock the latest main, and do not rely on the 06/10 base line/commit numbers. This round's changes are local documentation edits, not yet committed/pushed.

Copy from before this edit: the history archive folder (`exports/archive/resonance-before-agent-scope-20261008-120051/manifest.json`, outside git, only on the project's host machine), with a SHA-256. Keep the old source packages for lookup; do not use them as current deployment orders.
