# Resonance A1: per-agent Resonance, switch and minimal progress (design)

- **Date:** 2026-10-08.
- **Code base:** `main` `09f254d0e4d009451dc58cb2e97788631c5acc1a` (0.86.1). Branch `claude/resonance-a1-agent-scope`.
- **Sources:** [scope and roadmap of 2026-10-08](2026-10-08-resonance-agent-scope-roadmap.md); ChatGPT's review of the A1 proposal (`exports/reviews/Resonance-A1-review-and-Claude-instructions-2026-10-08.md`, outside git).
- **Status:**
  - The design has passed review round 1. The review agreed with the direction and the five decisions in section 11; it raised 2 P1 and 1 P2, fixed in round 2 (section 12).
  - Review round 2 allowed continuing, with one P2 about the enable flow (sections 1 and 13).
  - Fully wired: registry, session link, side tables, backup, turn context, tool, gates (scheduler, handoff, publish, trial), project owner API, minimal UI.
  - Code review passed at `cc79deb2` (after the rounds in sections 12 to 14). Pilot A1-1 passed technically and on content in one scenario. Record: `docs/dev/resonance-a1-verification.md`.
  - Guide to use, upgrade, roll back and restore: `docs/dev/resonance-a1-migration.md`.
  - No model had been called at that point. Shipped in 0.87.0 on 2026-10-09 (`fdfec7c5`).

## 0. Scope

**In A1:**
- A goal can only be created inside a conversation session with an agent that has Resonance enabled.
- Each goal belongs to exactly one agent.
- Each agent has its own switch, controlled by the project owner.
- The agent page has a minimal progress screen.

**Not in A1:**
- The path for assigning work from ordinary chat to an agent: a separate item, after A1.
- Adaptive heartbeat (A2), learning from feedback (A3), multi-engine handoff (A4), maker and review team (A5).
- An OS sandbox for engines that have a shell.

**Unchanged:**
- The whole M1 to M5 foundation: goal store, revisions, receipts, evidence, guards, budget, in-turn draft handoff, cards, method trial.
- Ordinary chat, loops, reminders, Kanban and every other channel run as before.

## 1. Agent identity and registry

**Current state at `09f254d0`:**
- An agent is a file `<brain>/agents/<slug>.md`. The slug is the file name.
- A conversation session with an agent has the channel `agent:<slug>`, written by the host when the session is created (`POST /sessions/new` checks the format and that the file exists).
- There is no rename operation. `POST /agents/delete` deletes the file.
- The agent file lives in the brain, so the brain can write it with its own `Write` tool.

**Design:** the host keeps an agent registry in `resonance.sqlite3`, a new table `resonance_agents`:

| Column | Meaning |
|---|---|
| `agent_key` | Key issued by the host (`ag_` plus 16 random characters), primary key, not derived from the slug |
| `brain_id` | Brain key (`_brain_key`, the resolved path), same as `goals.brain_id` |
| `slug` | Slug at registration time |
| `status` | `active`, `missing` (the host saw the file disappear), `retired` (deleted through the host or retired by the project owner) |
| `enabled` | Resonance switch, default 0 |
| `config_version` | Incremented on every change of the switch or status |
| `created_at`, `updated_at` | Timestamps |

Every change has a row in the new event table `resonance_agent_events`: who changed it, what changed, version before and after.

**Rules:**
- **Issuing the key:** when the project owner first turns Resonance on for an agent, the host issues an `agent_key`. Each `(brain_id, slug)` has at most one `active` row.
- **Editing agent content** (prompt, model, skill) does not change the key.
- **Deleting through the host** (`POST /agents/delete`): the row becomes `retired`. Recreating the same slug is a NEW agent, which must be enabled again and gets a new key. Old goals stay with the old key and do not move to the new key by themselves.
- **File disappears outside the host** (manual delete, manual rename): when the gate sees the file missing, the row becomes `missing` and every goal of that key is blocked.
  - A file with the same slug reappearing does not unlock by itself. The project owner chooses "confirm this is the same assistant" (keep the key) or "this is a new assistant" (new key).
  - Stated limit: if the file is deleted and recreated while the host is not watching (for example while the server is off), the host cannot tell the difference.
- **Rename:** there is no managed operation yet. A manual rename counts as the old file disappearing (`missing`) plus an unregistered agent. Goals and sessions of the old key do NOT move to the new agent in A1 (section 5).
- **Two brains with the same slug:** different `brain_id`, so different rows, different keys. Every query filters by both.

**Pinning a session to the agent key** (fix from review round 1, P1-1). A slug is just a file name, so looking up "the current agent of the slug" would let an old session mistakenly take an agent recreated under the same name. The host keeps a table `session_agents(session_id, brain_id, agent_key)`:
- A **session already pinned** to key A is forever A's.
  - A still `active`: the turn has identity A.
  - A `missing` or `retired`: the turn has no identity. It does not move to a new key of the same slug on its own.
  - History is still readable.
- A **session not yet pinned** is pinned at its first turn to the slug's current `active` row, if and only if it is certain to belong to that row:
  - it is the only key that `(brain, slug)` has ever had, including a session opened before the first enable; or
  - the session was created at or after the time that key was issued.
- **A session created under an old key that has no turns yet** does not take the new key.
- A1 has no operation to relink an old session to a different agent. To use the new agent, open a new session.
- **Enabling in a session that cannot use the new key** (review round 2, P2). The common case: an agent recreated under the same name, the user opens a chat and only then enables it. The session was opened before the key was issued, so the rule above blocks it.
  - The resolver stays conservative and is not loosened to "same slug is accepted".
  - The enable API takes the `session_id` of the open session and returns `needs_new_session` when that session cannot use the current key.
  - The UI says so clearly and has a button to open a new session of exactly that agent through the host (`POST /sessions/new`, channel `agent:<slug>`). Old history stays.
  - Never report "enabled and usable in this session" while the session is blocked.
- Every pin has a `session_pinned` event. The link lives in the store, so it survives restarts.

## 2. Binding a tool call to its turn and agent

The review pointed out that the ledger `luot_dang_chay.doan_luot(vault)` guesses "the only turn of the brain" and does not prove who called the tool. A1 drops that approach for Resonance and uses `turn_context` (available since 0.85.8).

**Existing infrastructure:**
- Every turn is bound to a turn context through a `ContextVar`.
- In-process engines (API engines, the plugin inside the Claude SDK) read that context directly.
- CLI engines call the hub over HTTP (Codex) carrying the key `X-Javis-Turn`; the hub maps the key back to the right context. A fake key, an old key or a missing key all yield "no turn". The key dies with the turn.

**Changes:**
- `run_turn` (dashboard) additionally attaches to the turn context:
  - `session_id` and `message_id` of the user's message;
  - an `agent = {"key", "slug", "config_version"}` block, only when the session has an `agent:<slug>` channel of the right brain, the agent file is still there, and the session's PINNED key (section 1) is still `active`. Otherwise `agent = None`.
- The host resolves these values from the stored session row and the registry; nothing is taken from the model's words.
- The tool `javis_goal` takes its identity from `turn_context.current()` at call time and accepts no `agent_id` parameter.
  - Missing context, `agent = None`, an agent no longer `active` or switched off, or a mismatched `config_version`: refuse BEFORE any store write, without calling a model.
- The user words used as the basis are read from the session store by exactly `(session_id, message_id)` and must be a user message. They are not taken from the turn ledger.
- Two concurrent turns have two separate contexts and do not borrow permissions from each other.
- `luot_dang_chay` stays as is for other tools (guessing the Kanban `chat_id`).

**Support table by engine of the agent session:**

| Engine | Turn context reaching the tool | A1 |
|---|---|---|
| Claude Code (SDK, in-process plugin) | `ContextVar` | Supported |
| API engines (OpenRouter, OpenAI, Anthropic API, Gemini, Groq, Ollama) | `ContextVar` (in-process hub) | Supports creating and updating goals. In-turn draft handoff not yet available (A4) |
| Codex | `X-Javis-Turn` key via `-c` | Supports creating and updating goals. In-turn draft handoff not yet available (A4) |
| Grok, Antigravity | do not carry the turn key yet | Not supported: the tool refuses, the UI says so clearly |

## 3. The switch and project owner authority

**Where it is stored:** the columns `enabled` and `config_version` in `resonance_agents`, changed only through the host API.
- **No tool lets an agent change the switch.**
- The switch is not put in the agent file, because the brain can write files in the brain.

**New API:**
- `GET /resonance/agents?brain=` lists the brain's agents with their registry status.
- `POST /resonance/agents/toggle` with `{slug, enabled}` turns it on or off; the first enable issues the key.
- `POST /resonance/agents/confirm` with `{agent_key, same: true|false}` handles a `missing` agent.

Every API goes through the existing web protection layer: Origin and CSRF checks, and the login session when `JAVIS_REQUIRE_LOGIN` is on.

**The old per-brain switch** (`<brain>/Javis/resonance.json`): after A1 it grants NO permission.
- It is not inferred as "every agent is on".
- The file is not deleted.
- The settings page turns the old brain switch block into a list of agents with switches, with the note "the old per-brain switch is no longer used".
- Reason: fewer settings (one switch, in the right place), as the project owner wants.

**Stated limits:**
- An engine with a shell (Claude Code running with Bash) runs with the same OS permissions as the server, so in theory it can edit `resonance.sqlite3` directly, or call the localhost API when login is off.
- A1 protects the normal tool path: no tool changes the switch, and the store sits in the state folder outside the brain. A1 does not promise that SQLite protects itself against a shell; an engine sandbox is out of scope.

## 4. The gates

The gate is a host function, `agent_gate(goal or turn context)`, called on every path below:

| Path | Today | A1 |
|---|---|---|
| Tool `javis_goal` create, update, list | brain switch + `doan_luot` | turn context has an `active`, `enabled` agent with a matching version; list returns only the goals of exactly that agent |
| `POST /goal-requests` | project owner, brain enabled | project owner; the message must belong to a session whose PINNED key (section 1, same function as `run_turn`) is an enabled agent; the goal belongs to that key. An old message is not resolved by the current slug |
| Scheduler (`tick` → `advance` → `_gate`) | brain switch | the key in the goal's `goal_agents`: if there is none then `blocked/unassigned`; if the agent is not `active` or is off then `blocked/agent_off`. Re-checked by code, no model call. No live chat turn needed |
| In-turn draft handoff (`finish_handoff`) | brain switch, pause, guard | adds: the goal's agent is still enabled and its version equals the version recorded when the goal was created or edited in the turn |
| Publishing the product (`_publish`), concluding success | `_gate` | `_gate` includes the agent gate; if the action's intent (`begin_action` records `agent_key` and version) differs from the goal's current key or version, the output is kept in the work area and not published |
| Method trial and application (M5) | `_trial_gate` calls `_gate` | as above; `apply_method` re-checks the agent gate in the same transaction |
| View, pause, cancel, drop an instruction, confirm | no switch required | unchanged: the project owner can always view, stop and cancel, even when the agent is off or `missing` |
| Hint line in the system prompt | brain enabled | only in the session of an enabled agent |
| Showing the tool `javis_goal` | `visible_fn` per brain | within a turn (plugin built per turn): shown only to an enabled agent; with no turn (the shared hub list): shown if the brain has at least one enabled agent. Only a hint; the real gate is in the handler |

**Semantics when the agent is switched off:**
- **On:** accepts and continues valid goals. Does not reopen a pause, a guard, or a cancelled or ended goal. The host sets a wake schedule for the agent's `active`, non-paused goals; the first wake is a code check.
- **Off:** `config_version` is incremented.
  - No new turns are held; every further action is blocked.
  - A running model turn runs to the end and still counts toward the budget. No promise of instant stop or cost refund. Its result is kept in the work area for reconciliation when it is turned on again.
  - Data is kept as is.
- **On again:** reconciles unfinished parts through the existing M3 mechanism.
- **Reusing output after an off/on cycle** (settled after review round 2):
  - The intent of the original work turn stays as history; the version is NOT edited to make it look pre-approved.
  - When the gate reopens, `_publish_latest` checks everything: the key of the work turn equals the goal's currently attached key; the agent is `active` and on; revision; guard; baseline of the target file.
  - If it all passes, the host records a NEW `publish` action. Its intent carries the `agent_key` and the CURRENT version, and a `source_action` pointing back to the old work turn, and only then writes the file. Permission is checked one last time at the effect, as with every publish.
  - The model is not called again: the number of engine turns does not increase.
  - Output from a different key (from before assignment, or from another agent) is never reused through this path.

## 5. Store and migration

**Schema changes** (fix from review round 1, P1-2). A1 does NOT add, delete or change columns of any table that exists since 0.86.x. Reason: the 0.86.1 code writes some tables by column position (`INSERT INTO handoffs VALUES(?,...)`), so adding a column would stop the old version from writing after a rollback. All A1 data lives in separate tables:
- `resonance_agents`, `resonance_agent_events`: the registry and the trail.
- `session_agents(session_id, brain_id, agent_key)`: a session pinned to a key (section 1).
- `goal_agents(goal_id, brain_id, agent_key)`: which key a goal belongs to. No row means unassigned.
- `handoff_agents(goal_id, revision, agent_key, agent_config_version)`: the agent and version when the in-turn handoff was opened.
- `actions.intent_json` is existing JSON, with `agent_key` and `agent_config_version` added. No column change.

A test locks the column list and order of the 13 tables of 0.86.1, so if anyone later adds a column to an old table the test goes red.

**Old goals** (no `goal_agents` row):
- History, evidence and revisions stay intact.
- The running state becomes `blocked/unassigned` at the next gate. They do not run by themselves and are not assigned by similar name or most recent session.
- The project owner assigns once with `POST /goals/{id}/assign {agent_key, expected_revision}`.
  - Only assigns a goal that is NOT yet assigned, to an `active` agent of the same brain. CAS on `expected_revision` and on "no `goal_agents` row yet" in the same transaction.
  - Records an `agent_assigned` event (who assigned, to which key).
  - After assignment, the first wake is a code check; the gate opens according to that agent's switch.
  - **Old output and lease are invalidated:** an action written before assignment has no `agent_key` (or carries another key) in its intent. The publish gate requires an intent carrying the goal's exact current key and version, so old output stays in the work area and is not published. The old lease expires under the M3 rule; a later turn keeps it with a new intent.

**Moving a goal between two agents: not supported in A1.** Goals of a `retired` or `missing` key stay put, blocked. The project owner can still view, pause and cancel. The move operation (managed rename, reassigning from one key to another) is left until after A1, when there is a design that covers running turns and permission over old output.

**Reconciliation before effects** (decision 4, detail per the review): before every publish, intake of a chat draft or application of a method, the host checks in the same transaction:
- the `agent_key` in the action's intent equals the key currently attached to the goal;
- the `config_version` in the intent equals the current version of that key;
- the key is still `active` and on;
- revision, guard and baseline as in M3 to M5.

Comparing only the version number is not enough, because two different agents can have the same number.

**Backup, rollback and restore:**
- The first time the A1 code opens a pre-existing store, the host copies `resonance.sqlite3` to `resonance.sqlite3.pre-a1.bak` with the SQLite backup API. Only once, never overwriting an existing copy.
- **Rolling back to 0.86.x while keeping the upgraded store:** the 0.86.1 code ignores the new tables and writes as before.
  - Verified with the real 0.86.1 code: create a goal with handoff, edit, action ledger, publish, cancel (`test_resonance_a1_rollback.py`).
  - Consequence: 0.86.x does not know the per-agent switch, and the old brain switch takes effect again. So BEFORE rolling back, the project owner turns off `Javis/resonance.json` of every brain (or keeps it off), so that no goal runs on its own during the switch. Turn it on again only by the project owner's decision.
  - Upgrading to A1 again afterwards: the registry and session links are intact. Goals created while running 0.86.x have no `goal_agents` row, so they wait for assignment and do not run by themselves.
- **Restoring from `.pre-a1.bak`:** this copy only has data up to the time of the upgrade. Every goal, event and evidence item created afterwards is NOT in the copy. Before restoring, stop the server and copy the current store separately to keep the new state.
- Test the migration with a copy of a store holding real data before release, not on the real store.

## 6. Minimal UI

**The Partners page, top of a conversation with an agent:**
- A switch labeled "Auto" (the UI name of Resonance). When off, a short note: the assistant still chats and does one-off work as usual.
- If the agent's engine is not yet supported (Grok, Antigravity), the switch can still be turned on but a warning line says "this engine cannot set goals yet". An engine without in-turn draft handoff gets a corresponding note line.

**The "Assistant goals" panel** (reads `GET /resonance/goals?agent_key=`), each goal shows:
- the understanding and revision;
- criteria: met, not met, unknown, with a short basis;
- the product currently in effect (path, shortened hash);
- who it is waiting on or what blocks it;
- the next wake and why;
- turns used against the budget;
- pause and cancel buttons.

No percentage guessed by the model. A ratio of verified criteria, if shown, is named accurately.

**Ordinary chat:** still shows the goal card when there is one (the card reads `/goals/{id}` under project owner permissions). The buttons on the card act on the goal of the owning agent.

**Settings page:**
- The per-brain Resonance block becomes a list of agents with switches.
- A "Waiting for assignment" section for old goals, with a picker to assign an agent.

Every UI string goes through i18n `vi.json` and `en.json`.

## 7. Unchanged outside Resonance

- Ordinary chat does not see the goal hint line. Calling `javis_goal` (if the model still sees it through the hub) is refused with the instruction "answer normally".
- `javis_task`, `javis_schedule`, loops, reminders, external channels, chatbots: unchanged.
- The turn context gains the keys `agent`, `session_id`, `message_id`. Existing plugin hooks read `turn` by the old keys, so they are not affected.

## 8. Behavior matrix and tests

Tested with a fake engine, real SQLite, the real SDK mapper when needed, running the real body of `run_turn` like the M2 tests and pilot 4.

| # | Case | Expectation |
|---|---|---|
| 1 | Ordinary chat calls `javis_goal` create, or `POST /goal-requests` on an ordinary chat message | Refused before any store write, no model call; Q&A, one-off work and Kanban still run |
| 2 | Agent A on, B off, same brain | A can create; B is refused; A's list does not see B's goals and vice versa |
| 3 | Two agents run turns concurrently | Each tool call gets exactly its own turn's agent; no borrowed permissions |
| 4 | Two brains with the same slug | Different keys; goals, products and message sources do not mix |
| 5 | A tool passes another agent's `agent_id` or `goal_id`; a call outside a turn; a fake or dead `X-Javis-Turn` key | Refused; no permission taken from the only running turn |
| 6 | Agent switched off after holding a turn, before publish, before intake of a chat draft, before applying a method | No effect; the turn already used is still recorded correctly; output kept for reconciliation |
| 7 | Turned on again | Does not reopen a pause, guard or cancel; valid output is published without calling the model again; the worker needs no chat turn |
| 8 | Delete through the host then recreate the same slug; manual rename; file disappears then reappears; restart | No automatic transfer of permission or goals; history readable; `missing` needs project owner confirmation |
| 9 | Migration on a copy of a store with old goals | No goal or evidence lost; unassigned goals do not run by themselves; after assignment they run per the switch; a `.pre-a1.bak` copy exists |
| 10 | UI and API | State matches the store; the project owner can still view, stop and cancel when the agent is off; an old confirmation does not apply to a new draft or revision |
| 11 | The agent path runs the full loop with a fake engine: prompt has the hint line, the tool is in the list, turn context reaches the tool, draft handoff | Goal created for the right agent, draft taken in, waiting for the user |
| 12 | Unsupported engine (Grok, Antigravity, a turn without context) | The tool refuses clearly; the UI reports not supported |
| 13 | Old session of a deleted agent, new agent with the same slug; restart; manual rename then rename back | The old session does not take the new key; a new session takes the new key; a manual rename loses the identity until the project owner confirms. Goes through the context-binding part of `run_turn` with the real session store |
| 14 | Roll back to 0.86.1 on an upgraded store, then upgrade again | The real 0.86.1 code can write on every main path; upgrading again keeps the A1 data; goals created during the rollback wait for assignment; the `.pre-a1.bak` copy is not overwritten |
| 15 | Enabling a `missing` agent while the flag is still on | Refused, no success reported, version not incremented |

**Old M1 to M5 tests:** tests that currently enable Resonance through `resonance.json` will switch to enabling the agent through the registry with one shared helper. What they check stays the same.

## 9. Planned changes to files, API and schema

- `server/resonance_store.py`:
  - tables `resonance_agents`, `resonance_agent_events`, `session_agents`, `goal_agents`, `handoff_agents`; no column change to old tables;
  - functions to register, enable, disable, confirm, pin a session, assign;
  - filtering by agent; `.pre-a1.bak` backup.
- `server/resonance.py`:
  - `agent_gate`;
  - `_gate` checks the agent;
  - `form_goal` and `revise_goal` take `agent_key` and version;
  - `handoff_after_turn` and `finish_handoff` check the agent;
  - `enabled_for` (brain) is now only used for the old UI label.
- `server/main.py`:
  - `run_turn` attaches the agent to the turn context;
  - the hint line only in the session of an enabled agent;
  - `/agents/delete` retires the agent;
  - `_resonance_after_turn` uses the turn's agent.
- `server/resonance_api.py`: `/resonance/agents`, `/resonance/agents/toggle`, `/resonance/agents/confirm`, `/goals/{id}/assign`; the `/goal-requests` gate; `?agent_key=` for the list.
- `server/turn_context.py`: allow adding keys to the turn context, keeping the old contract.
- `system/plugins/javis-goal/plugin.py`: identity from the turn context; `visible_fn` per turn.
- `dashboard/`:
  - switch and progress panel in the Partners page (`workspace.js`, or a new file `resonance-agent.js`);
  - the settings block;
  - `i18n/vi.json`, `i18n/en.json`.
- `tests/python/`: `test_resonance_a1_agent_scope.py` (new) following section 8; update the M1 to M5 tests to the agent-enabling helper; `route_table.json`.
- `docs/`: migration and restore guide; CHANGELOG in both languages.

## 10. After A1: pilot

- **The achieve pilot runner moves to the agent session:** create a temporary agent in a temporary brain, enable it through the project owner API, create an `agent:<slug>` session.
- **Re-check the parts that may differ from pilot 5:** the agent persona's prompt, the agent's provider and model, the tool list, the turn context, the file-write receipt.
- **Order:** prove it with a fake engine first, then propose one real pilot with its own configuration and budget. Do not reuse the old pilot budget.

## 11. Decisions settled by ourselves, for the reviewer to look at

1. The old per-brain switch no longer grants permission. Only the per-agent switch remains.
2. The agent key is issued by the host at the first enable. The key is not written into the agent file.
3. A file that disappears and reappears needs project owner confirmation. Permission is not regained automatically.
4. A `config_version` mismatch between holding the turn and the effect means the output is kept, not published. The next wake re-evaluates under current permissions.
5. Grok and Antigravity are not supported in A1 because they do not carry the turn key yet.

Review round 1 agreed with all five decisions. Additions per the review:
- Decision 2 gains the durable session link (section 1).
- Decision 4 reconciles key, version, revision, guard and baseline in full (section 5).
- Decision 5: the UI distinguishes three capabilities (creating goals, taking in a chat draft, background-work engine). The engine support table is only accepted when there is evidence through a real transport with a fake service, not just reading the turn context in a fake `_do_turn`.

## 12. Fixes after review round 1 (PR #590, previous head `5ed5a9e3`)

1. **P1-1 old session takes the wrong new agent.** A session is pinned to the agent key in the `session_agents` table (section 1). `run_turn` resolves through that link, not by slug.
2. **P1-2 rolling back to 0.86.x breaks the write path.** All columns added to old tables were removed; A1 data moved to separate tables (section 5).
   - Verified with the real 0.86.1 code obtained through `git show 09f254d0`.
   - CI fetches that commit separately so the test is not skipped.
   - The rollback and restore guide states the exact limits of the copy.
3. **P2-1 enabling a `missing` agent reports success.** Check the status before the "value unchanged" branch.
4. **Assignment scope settled:** A1 only assigns goals that are not yet assigned. Moving between two agents is left until after A1 (section 5).

## 13. After review round 2 (head `241fbb5d`)

- The three round 1 bugs were confirmed fixed.
- The new P2 (a session opened before the first enable of an agent recreated under the same name) is handled in the API and UI with `needs_new_session` (section 1). The resolver is not loosened.
- Settled how output is reused after an off/on cycle (section 4).
- Plan to wire the rest: `docs/superpowers/plans/2026-10-08-resonance-a1-integration-plan.md`.

## 14. Fixes after the integration review (previous head `52d841d1`)

1. **P1-1 real prompt of the assistant session.** The hint line (`_RESONANCE_GOAL_HINT`, one copy) is appended to `_agent_chat_prompt`, the prompt-building path that EVERY engine of the assistant session uses.
   - When the assistant is on, the "only two ways" sentence in the assistant's tools block becomes three ways.
   - A switched-off assistant and ordinary chat stay unchanged.
2. **P1-2 assistant file lost.** `agent_gate` reconciles the file right at the gate (same folder lookup rule as `_agents_dir`).
   - If the file is gone it settles `missing` even with no chat turn. Applies to the scheduler, `/goal-requests`, handoff, publish and trial.
   - `GET /resonance/agents` also settles `missing` for a key whose file is gone.
   - A returned file still needs project owner confirmation.
3. **P1-3 trial.** A trial pins the key and version in the new table `experiment_agents`; the store checks inside the transaction that holds the budget, each trial turn and the apply step.
   - Switching off or changing the version stops the trial, refunds the unrun part of the budget, and does not apply.
   - A goal that already belongs to an assistant requires every `begin_action` and `begin_experiment` to carry the key; if missing, it refuses and does not silently skip the check.
   - There is no path to re-grant permission to a trial result after turning on again: a new trial must run.
4. **P2 session state after reload.** `GET /resonance/agents?slug=&session_id=` returns the session state by exactly the rule of `run_turn`, read-only, without writing the link. The UI block asks the host again on every open, reload or session change.
5. **Pilot** runs in the assistant session; there is a three-door check that calls no model (`docs/dev/resonance-mvp-e2e-pilot-plan.md`, section A1).

**Remaining limits:**
- The hub's tool list is cached per brain, so `javis_search_tools` may still return `javis_goal` in the turn of a switched-off assistant.
- The call is then refused by the handler (`agent_off`) and writes nothing. The tool list is only a hint (section 4).
