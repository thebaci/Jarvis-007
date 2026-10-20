# Resonance A1: acceptance record (08/10/2026)

Milestone A1 of the [agent scope](../superpowers/specs/2026-10-08-resonance-agent-scope-roadmap.md) roadmap: Resonance switched on per assistant, goals attached to the right assistant, minimal progress on the Partners page.

**Status: released as 0.87.0 (09/10/2026).** PR #590 squashed into `main` as `fdfec7c5c84c2663276d088194844e058d9a22aa` (tree identical to the reviewed head `077bcf73`). CI and the Docker build are green; image `ghcr.io/blogminhquy/javis-os:0.87.0` (`sha256:bb437e0d0bfb...`).

## Code and commits

- **PR:** #590, branch `claude/resonance-a1-agent-scope`, VERSION 0.87.0.
- **Base:** `origin/main` `71f9c5b9` (0.86.2). The branch already contained this base, no further merge needed.
- **Code review passed:** `cc79deb2`.
- **After the code review:** `e01eb3c2` only added regression tests, `e0a60352` only added the pilot record. The last commit on the branch only changed documentation.

## Acceptance table

| Condition (A1 design) | Result | Evidence |
|---|---|---|
| Per-assistant switch, no more per-brain switch | Pass | `test_resonance_a1_registry.py`, `test_resonance_a1_transport.py` |
| A normal chat cannot set a goal | Pass | `test_resonance_a1_turn_agent.py`; pilot S0b: 403 |
| A goal attaches to the session's own assistant, a session opened before the key was issued is blocked | Pass | `test_resonance_a1_turn_agent.py`; pilot S1 |
| Turning off, deleting, losing the file, or changing the assistant's version all block at every gate (scheduler, handoff, posting, trial) | Pass | `test_resonance_a1_gates.py`, M2 to M5 updated |
| Old output is posted again after switching back on, without calling the model | Pass | `test_resonance_a1_gates.py` |
| A trial that breaks the store before calling the model refunds the turn, after calling the model it keeps the turn | Pass | `test_resonance_mvp_trial.py` (entries 7d08, cc79) |
| Old goals go to Waiting for assignment, assigned once | Pass | `test_resonance_a1_registry.py`, `POST /goals/{id}/assign` |
| Rolling back to 0.86.1 on an upgraded store | Pass | `test_resonance_a1_rollback.py` runs the real 0.86.1 code |
| Minimal UI (switch, goals panel, Waiting for assignment, engine warning) | Pass | `tests/js/test_resonance_a1_ui.js` |
| Real pilot in an assistant session | Pass technically and in content, one scenario | [pilot record](resonance-mvp-e2e-pilot-plan.md), section A1-1 and the post-check |

## Tests run

- **Locally, on the current tree:** `tests/run.py resonance turn_ route_table plugin hub chat_disconnect workflow agent settings`. **64/64 green** (57 Python, 7 JS), 228 seconds.
- **CI:** green on `e0a60352`. The last commit only changed documentation; see the PR for CI on the final head.
- The full Python test suite was not run on this machine. About 14 files here are falsely red, red even on a clean main. CI is where the full run happens.
- Green tests do not replace an independent review. The code review was done separately by the reviewer, at `cc79deb2`.

## Pilot A1-1

- Run once, with exactly the approved package, at `e01eb3c2`.
- 2 Opus chat turns, 0 Sonnet background-job turns, against a cap of 4. Used the Claude Code subscription plan, not the paid API.
- The final confirmation in S6 was simulated through the API.
- Content passed: first draft 4/4, revised draft 3/3.
- Two wording suggestions that did not block, recorded in the post-check section. The evidence files are kept byte for byte.

## Remaining limits

- One successful scenario is not a stable rate. Not measured on Codex, the API engines, Grok or Antigravity.
- The path where a background job fixes the draft with a real model was not used in the A1 pilot.
- Codex and the API engines: can set goals, but a draft written in chat is not yet accepted as the product (left for A4).
- Grok and Antigravity: cannot set goals yet.
- Not checked on a VPS (D0). The slowness through Cloudflare is a network path issue, handled separately in PR #592 and on the infrastructure side.

## User documentation

- [Usage, upgrade, rollback, recovery](resonance-a1-migration.md).
- [A1 design](../superpowers/specs/2026-10-08-resonance-a1-agent-scope-design.md).
- [Integration plan](../superpowers/plans/2026-10-08-resonance-a1-integration-plan.md).
