# Team chat: code review before design (2026-10-13)

Base: `main` `bfb1c29f9e87e8b43a0bf1a8a43d3535581047d6` (0.109.0, A1 to A5 released). Design branch `claude/team-chat-design`.

The design uses this record: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md).

**Level of evidence.**
- Code reading only, nothing run. Six parallel review passes, one per area.
- The conclusions that the architecture depends on were re-checked by hand (section 9).
- "Real path" means traced from the UI or API down to the store and engine. "Partial" means code exists but lacks the piece team chat needs. "Name only" means only a name was seen, with no behavior yet.
- Line numbers refer to `bfb1c29f`.

## 1. Short conclusion

- **Jarvis 007 does not yet have an internal team chat.**
  - There is no team or member table. A session attaches to a single agent (`sessions.channel`, `workflow_chat.persona_cua_phien`).
  - A message has only `role`, no sender (`server/sessions.py:101-108`).
  - The dashboard has no @mention yet.
  - The agent prompt still says explicitly "there is NO mechanism for calling other agents" (`server/main.py:9638`).
- **Three things easily mistaken for team chat that are not:**
  - **Tags** (0.100.0) only classify. `docs/dev/agent-tags.md:5-7` already records that team group chat is a separate concept, not yet built.
  - **A chatbot's Zalo and Telegram groups** are outside channels: one bot talking to outside people (`chatbot_store.py`, `chatbot_reply_policy.py`).
  - **Workflows** are pipelines of sequential steps, not conversations (`main._execute_workflow_raw`).
  - **The A5 do/review pair** is attached per goal and has no chat interface (`resonance_store` `goal_team`).
- **Parts that can be reused:**
  - sessions and messages (add a sender column);
  - the send loop over WebSocket and the stream;
  - `push_to_chat` to put a result into a session;
  - the Kanban queue (durable, lease, recovery after restart, cancel, reporting results back to chat);
  - Resonance's agent identity ledger (durable code `agent_key`);
  - the agent's prompt and memory;
  - the Resonance switch and the A1 to A5 gates.

## 2. Agent identity, profile, tags

| Function | File:function | Path | Reuse | Gap |
|---|---|---|---|---|
| Agent file | `agents/<slug>.md` in the brain; `main.agents_index` (6678), `POST /agents` creates and edits (6741), `POST /agents/delete` (6803), `_agent_file` (6848) | Real | Profile, prompt, own model | No route to change a slug. Renaming only edits `name` |
| Slug | `_ascii_slug` (6479), `valid_file_slug` (`skill_router.py:169`) | Real | | **Creating an agent with the same name as an existing file silently overwrites it** (no server-side block) |
| Durable code | `resonance_agents.agent_key` (`resonance_store.py:124-129`); `_insert_agent` (490) accepts `enabled=False`; `agent_set_enabled` (538) creates the code only at the first enable | Real but lazy | Team member code | An agent that never had Resonance on has no code |
| Delete then recreate with the same slug | `delete_agent` only deletes the file, then `agent_retire` | Real | | Memory `memory/agents/<slug>/`, session `agent:<slug>`, and chatbot attachments follow the slug, so the new agent inherits them. Only Resonance separates them, thanks to the new code and the code-pinned session (`session_agent` 606) |
| Tags | `agent_tags.py`; `/capability/meta`, `/agents/tags/rename`, `/agents/tags/delete`; lock `_AGENT_META_LOCK` | Real | Filter when choosing members | Grants nothing (checked: not used in the prompt, the Resonance gates, reviewer selection or Kanban) |
| Agent prompt and memory | `_agent_sysprompt` (9566), `_agent_chat_prompt` (9658), `_ket_luot_agent` (9680): `JAVIS_RULE` goes into "Owner's rules" only when the owner just spoke in the turn; `JAVIS_LESSON` keeps 15 lines | Real | Each member's turn | No team context block |

## 3. Sessions, messages, WebSocket

| Function | File:function | Path | Reuse | Gap |
|---|---|---|---|---|
| Session | `sessions.py:73-89`, added columns 413-455; channels `web`, `agent:`, `workflow:`, `coding:`, `bot:` | Real | New channel `team:<id>` | `list_sessions` hides only four prefixes (750-753); the new prefix must be added |
| Message | `messages(id, session_id, role, content, ts, tool_calls_json)`; `append_message` (547) | Real | | **No sender, no client message id, no `reply_to`.** The chatbot group stuffs the name into the content (`chatbot_runtime.py:1616`), so identity is untrustworthy text |
| History | `get_messages_page(limit, before=(ts,id))` (677), at most 200 | Real | Chat frame pagination | `limit=0` returns everything; the engine still calls `get_messages` without pagination |
| Send over WS | `/ws` (`main.py:14376`), receive loop (16145), `get_or_create` (16271), busy check (16309), `run_turn` (16417) | Real | The send loop | The packet has no recipient or target agent |
| Busy | `chat_runtime` one job per session; a second message is refused with "This session is already replying" (16309-16317) | Real | | No server-side queue; some side effects run before the busy check |
| Stream and end of turn | `_SendProxy` (14421), `ChatRuntime.publish` (`chat_runtime.py:92`) broadcasts to every client; `turn_done` (15641) | Real | | No event sequence number, no replay after reconnecting |
| Reconnect | `hello{running}` (14402); client `_dongBoNeuLech` (`app.js:992`); ping/pong (0.85.11) | Real | | Only the streaming text; other frames are lost when the network drops |
| Duplicate-send protection | None for text messages; voice messages use `utterance_id` and `voice_receipts` | Partial | The `voice_receipts` pattern | Resending after a network drop creates another user message row |
| Getting messages from background work into a session | `push_to_chat` (10386), `_notify_owner` (10601), `report_receipts` | Real | Posting a member's result | The posted message is `assistant`, with no author |
| `turn_context` | `turn_context.make` (84): channel, `session_id`, `message_id`, `agent{key,slug,config_version}`, `authority_seq` | Real | Attach the team and job to a turn | No team or job key yet |
| `/agent-<slug>` in the main chat | `chat-slash.js:61-133`, `_bao_ve_khung_goc` | Real | A pattern for forwarding a message and reporting back | Runs in its own 1:1 session, not in a shared thread |

## 4. Engine and model

| Turn type | Engine/model source | Agent's own model | Usage logging |
|---|---|---|---|
| Ordinary chat | pinned per session, then `_effective_main` (`main.py:1772`, 2496) | n/a | Claude, Codex and API log; Grok and Antigravity do not |
| Chat with an agent | the agent's `model` + `model_provider` pinned to the session at creation (16660-16667) | **Partial:** needs both fields; the pin is a snapshot taken when the session is created; a missing API key falls back to the main model (2512) | as above |
| Workflow step, full authority | `_mk` (9515) | Claude yes; Codex conditional; other providers via `swap` may drift to the fallback chain | Claude log, `usage.json` for API |
| Workflow step under Kanban with limited tools | forces Claude (9549-9554) | Only when the agent's model is Claude | Claude log |
| Kanban, loop, reminder | aux (`aux_engine.swap`) | No | aux |
| Resonance (including A5) | `_resonance_engine`: aux, text only, no fallback chain (2041-2054) | **No** | `actions.receipt_json` in the Resonance store; `usage.json` only when aux is an API |

- The usage ledger has only the dimensions day, provider, source, activity type, model, project. **There is no session, agent or job dimension** (`usage_index.py`).
- The monthly budget brake applies only to aux when aux is an API provider (`aux_engine.read_spec` 177-185). The main chat and agent chat are not braked.

## 5. Jobs, Kanban, workflow

| Function | File:function | Path | Reuse | Gap |
|---|---|---|---|---|
| Job table | `task_store.py:84-113` (`kanban.sqlite3`): status, priority 1..3, `chat_id`, attempts, lease, `not_before`, metadata, deps, runs, events | Real | Durable storage for team jobs | No team column, assignee, or ordering; scope is per brain |
| Adding a job | `enqueue` (255-274) | Real | idempotency key | **Merges a job with the same title that is still open**: two team jobs with the same name become one |
| Picking the next job | `next_candidate` (667-680): triage first, then `priority`, then `created_at`; `_dispatch_available` (`tasks.py:355`) every 5 seconds | Real | The dispatch loop skeleton | One shared pool, `max_workers` default 2 for every brain; no "one job running per team"; `/kanban/run` and `/kanban/nudge` skip the ordering and the slot count |
| Board mode | `off`/`manual`/`auto`, a new brain is `off` (`task_store.py:78`) | Real | | A team job the user clearly assigned should not depend on this switch |
| Lease, recovery | `claim` (682-746), 90-second lease, 20-second heartbeat; `reclaim_stale` (459) | Real | Reuse | Does not refund the attempt after a crash |
| Cancel | `/kanban/task/cancel` (1561) | Real | Reuse | Can cancel only inside the process holding the worker |
| Acceptance check (0.107.0) | `_check_acceptance` (1030-1082) | Real | Could serve as a done gate | If the check cannot run, the job is still marked done (`unverified`) |
| Report back to chat | `_report` (1224-1290) through `_notify_owner` by `chat_id` | Real | Report the result back to the team | |
| Reordering | No API; the UI has no drag and drop | Only the name `priority` | | Missing ordering, a priority button, version check when two tabs edit at once |
| Workflow | `_execute_workflow_raw` (9855-10014): sequential steps, `{{prev}}`; `verify_agent` fails closed (0.107.0), `max_retries` per step | Real | The body of a job | No loop ceiling for a whole run |
| Busy per agent | None | | | The same agent can run at the same time in Kanban, private chat and Resonance |

## 6. Resonance A1 to A5

- **Per-agent switch:**
  - route `POST /resonance/agents/toggle` (`resonance_api.py:341-371`), which calls `agent_set_enabled`;
  - owner only (`_owner_only`); agents and tools cannot call it;
  - the first enable issues the code; every change bumps `config_version`;
  - an agent that is `missing` must be confirmed before it can be enabled again.
- **Turning off does not kill a running turn, but closes every later step:**
  - the work gate blocks with `agent_off`;
  - `begin_action` re-checks;
  - held write permissions all lapse;
  - review results tied to the old version are discarded.
- **The owner always wins:** pause, cancel, revoke, and dropping a review request still work when the agent is off. A version already committed to publish still completes.
- **What the model can never do by itself:**
  - enable or disable an agent; set a reviewer;
  - approve, revoke or grant write permission;
  - pause or cancel a goal; change a ceiling;
  - choose an engine; message or assign work to another agent.
- The full table of all ceilings and gates is in the design, section 13.6.

## 7. UI

- **Partners page** (`dashboard/workspace.js`):
  - The left column lists assistants (`mucHtml` 827-849): photo, name, role, tags, pin, "..." menu. **The row has no Resonance state yet**, because `/agents?prompt=0` does not return this field.
  - The right column, Settings tab, has the Resonance panel (`resonance-agent.js`): switch, Reviewer field, goals, lessons.
- **The switch currently appears in two places:** the right column of the Partners page, and the Settings page (`index.html:447-450`, `settingsHtml` 208-240).
- **Small defects seen:**
  - the Settings copy swallows errors;
  - on a 409, the Partners copy only shows text and does not reload the state;
  - the Reviewer field does not restore its old value on error.
- **Goal card** (`chat-resonance.js`): has all the buttons pause, resume, cancel, allow scope, re-enable reviewer, drop review request. It does not refresh itself periodically.
- **A3 reactions:**
  - only `up`, `down`, `none` and the three reasons `too_long`, `too_often`, `unclear` (`resonance_learning.py:36-37`);
  - only on the **host-written notice messages** of a goal;
  - the `reactions` table requires `goal_id`, `revision`, `report_key`, `notice_kind` (`resonance_store.py:171-181`).
- **i18n and narrow screens:**
  - New text must have keys in both `vi.json` and `en.json` (`tests/js/test_i18n.mjs`).
  - The Partners page turns its column into a drawer at 1060px and 900px.
  - The `[hidden]` trap overridden by `display:flex`.

## 8. Gaps to fill for team chat

1. A team table, members, the team lead role, permission mode.
2. Messages with a sender, a client message id, and a link to a job.
3. A durable code for every agent that is a member, not only agents with Resonance on.
4. A per-team job queue: one job running per team, durable ordering, a priority lane, version check when two tabs edit at once.
5. Running each member's turn with the right prompt, own model, and own resume thread.
6. Host-written coordination tools (assign, ask for help, submit a result) with a loop ceiling.
7. A system-wide busy lock per agent.
8. A turn ledger by team, job and role.
9. Six reactions on every agent reply.
10. The Resonance switch on the assistant row.

## 9. Self-check (re-read the code, not through the review passes)

| Conclusion | Checked at | Result |
|---|---|---|
| A message has only `role` | `server/sessions.py:101-108` | Correct |
| The stream broadcasts to every client | `server/chat_runtime.py:92-106` | Correct |
| Kanban merges a job with the same title that is still open | `server/task_store.py:255-274` | Correct |
| A busy session refuses new messages | `server/main.py:16309-16317` | Correct |
| The identity store can create a code without enabling | `_insert_agent(..., enabled, ...)` (`resonance_store.py:490-500`) | Correct; `agent_set_enabled` is currently called only with `True` |
| The agent prompt forbids calling other agents | `server/main.py:9638` | Correct |
| A3 reactions have only three values, tied to a goal notice | `resonance_learning.py:36`, `resonance_store.py:171-181` | Correct |

**Not checked:**
- the Codex, Claude CLI and API engine paths in `_do_turn` outside the Grok branch;
- the `_auth_guard` and `_csrf_guard` layers;
- the path of an engine turn that is already running when the agent is turned off;
- every client-side path that prevents a duplicate name when creating an agent.
