# Resonance A1 integration plan (after round 2 review)

- **Date:** 2026-10-08.
- **Base:** PR #590, head `241fbb5d`. Design: `docs/superpowers/specs/2026-10-08-resonance-a1-agent-scope-design.md`.
- **Round 2 review:** cleared to continue, with one P2 (a session opened before an agent's first enablement recreates the same name) and two points to settle: reusing output after an off/on cycle, and the scope of evidence that comes back.
- **Not in this round:** A2 onward, the path for handing off work from ordinary chat, a real-model pilot, merge.

## Shared policy: one agent gate function

`resonance.agent_gate(store, brain_id, agent_key, version=None)` returns `(agent | None, reason)`. Every path below calls exactly this function and does not read the switch on its own. Blocking reasons:
- `unassigned`: the goal has no agent assigned;
- `agent_missing`, `agent_retired`: the key is no longer `active`;
- `agent_off`: the switch is off;
- `agent_changed`: `config_version` differs from the version the caller is holding.

## Group 1: identity, per-agent goals, the gate (one separately checked commit)

1. **Store:**
   - `create` takes `agent_key` and `agent_version`, and writes `goal_agents` and `handoff_agents` in the same transaction;
   - `revise` writes `handoff_agents` when a handoff opens;
   - `GoalRecord` has `agent_key` (read from `goal_agents`);
   - `list_open` filters by `agent_key`;
   - `begin_action` takes an intent that has `agent_key` and `agent_config_version`.
2. **Tool `javis_goal`:**
   - Identity comes from `turn_context.current()`: it must have `agent`, `session_id`, `message_id`.
   - The user's words come from the running turn ledger by EXACTLY the key `(web:<session>, message id)` of the turn context, without guessing "the only turn". This is the text the host used for the turn (with the UI context block stripped, keeping the original sentence of a voice turn).
   - If any of the above is missing, or the agent gate blocks: reject before any store write.
   - `list` and `update` only see the goals of the exact agent.
   - `visible_fn`:
     - if there is a turn context, follow the turn's agent;
     - if not, show it when the brain has at least one agent enabled. For suggestion only.
3. **`_gate` (scheduler, posting, conclusion, trial):** replace the brain switch with `agent_gate` by the goal's key.
   - `unassigned`: block, do not set a schedule; the assignment resets the schedule.
   - The remaining reasons: block, and schedule a recheck in code.
4. **Output by agent and version:**
   - `_work_step` writes `agent_key` and the version into the intent when it takes the turn.
   - Before posting, compare against the current gate. If it differs, keep the output and schedule an immediate wake so it is reconsidered next time.
   - `_publish_latest` only uses the output of an action that carries EXACTLY the goal's `agent_key`. Output from before the assignment and from another agent must not be posted.
5. **Reusing output after an off/on cycle** (settled per the review):
   - The original intent stays as is, and its version is not edited.
   - When the gate reopens, `_publish_latest` checks everything: the action's key equals the goal's key, the agent is `active` and enabled, the revision, the guard, the baseline.
   - Then it writes a NEW `publish` action. Its intent carries the CURRENT version and a `source_action` pointing back to the old work turn. The model is not called again.
6. **Handoff within a turn:** `handoff_after_turn` replaces the brain switch with the agent gate. The version recorded in `handoff_agents` must equal the current version.
7. **Trial and apply (M5):** `_trial_gate` goes through `_gate`. `apply_method` rechecks the agent gate in the same write transaction.
8. **main.py:**
   - The hint line in the system prompt only appears when the turn belongs to an enabled agent.
   - `_resonance_after_turn` and the receipt ledger only run when the turn has an agent.
   - `/agents/delete` makes a live key retire.
9. **Tests:**
   - A shared helper enables the agent for the old M2 to M5 tests. Their checking content stays the same.
   - New tests for the matrix of 1 to 7 and 11, 12.
   - Transport: an in-process plugin, the HTTP hub with the `X-Javis-Turn` key (Codex), a fake or dead key.

## Group 2: the project owner's API

1. `GET /resonance/agents?brain=`: the brain's agent files joined with the registry, plus the number of goals waiting for assignment.
2. `POST /resonance/agents/toggle {slug, enabled, session_id?}`:
   - Enabling requires the agent file to really exist.
   - With a `session_id`, return the status of that session: `ready`, or `needs_new_session` when the session cannot use the current key (round 2 P2). It does not switch sessions on its own.
   - Enabling sets a wake schedule for the `active`, non-paused goals of that key.
3. `POST /resonance/agents/confirm {agent_key, same}`: requires the file to really exist.
4. `POST /goals/{id}/assign {agent_key, expected_revision}`: only an unassigned goal, an `active` key in the same brain, CAS.
5. **`/goal-requests`:** the message must belong to the session that the key (the same function as `run_turn`) has pinned as enabled; the goal is attached to that key.
6. **`GET /resonance/goals`:** filter by `agent_key`; `unassigned=1` for the "Waiting for assignment" section.
7. **Feedback on the card:** requires the goal's agent to be enabled. Viewing, pausing, cancelling and dropping an instruction require nothing, as before.

## Group 3: minimal UI

1. **Partners page, the agent's right column:** the Resonance block.
   - It has a switch and a status line for the session that is open.
   - When `needs_new_session`: an explanation and an "Open a new conversation" button.
   - It has a list "Assistant goals" (the understanding, criteria, product, what it is waiting on, the next wake, turns used, pause and cancel buttons).
2. **Settings page:**
   - The per-brain switch block becomes a list of agents with a switch each.
   - It has a "Waiting for assignment" section with an agent picker.
   - It has a note that the old brain switch is no longer used.
3. **Engine:** a warning line when the agent's engine cannot yet carry the turn key (Grok, Antigravity). Distinguish three capabilities: forming goals, receiving the chat version, background work.
4. Strings go through `vi.json` and `en.json`. JS tests for building the block and the `needs_new_session` flow.

## After the three groups

- The return loop has one more real A1 goal (with an agent assigned and `handoff_agents`).
- The cases of switching off within a turn, an old version, restart, the assignment CAS, and keeping output: count both the engine turns and the published versions.
- Send the A1 integration review with the base/head, tests and limits.
- A real pilot is only presented after the fake-engine path passes, with its own scope and quota.
