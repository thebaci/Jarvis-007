# The "Partners" page: chat with agents and workflows, with saved run history

Date: 2026-09-15. Status: approved (the project owner decided in chat).

## 1. Problem

- The Agents page is currently just a list of cards (Edit, Export, Delete). You cannot chat with an agent.
- On the Workflows page, clicking Run shows the browser's `prompt()` box, and the result streams into a
  temporary drawer (`#runDrawer`). Closing the drawer loses it; it is not saved anywhere.
- There is no store of run history. Ask Jarvis 007 "how did the latest workflow run go?" and Jarvis 007 has
  nothing to look up, so it answers with nothing.

## 2. Decisions made

1. Merge the Agents and Workflows pages into ONE "Partners" page (machine id: `workspace`), replacing
   the two old sidebar entries. The page has an Agents | Workflows switch.
2. You can chat with both agents and workflows, in the same chat box.
3. In a workflow's chat box, each message is ONE new run; the result of the previous run
   in the same conversation is appended to the input as context, so feedback messages ("make
   paragraph 2 shorter") are still understood.
4. The workflow list is sorted with the most recent run first. The agent list is sorted with the most recent
   chat first. Anything never run/chatted goes after, by name.
5. Technical approach A: everything is a chat session. Chatting with an agent and running a workflow are both a
   WebSocket turn on a session with its own channel. The new page borrows the app's existing chat box.

## 3. Interface

Three-column layout, following the concept file `javis-workspace-concept.html`:

- Left column: the Agents | Workflows switch, a search box, a filter by `group`, the list, a Create
  new button, a Jarvis 007 Store button (opens the existing store through `JavisPacks.moKho`, filtered to the right type). Each row: an
  icon (agents use the `bot` icon, workflows use the `workflow` icon), name, group and role/step count.
- Middle column: the chat box BORROWED from the app via `_borrowChatNodes` (exactly how the Chat page
  does it). The header bar has the partner's name, a sub-line (group and status for an agent; "Workflow, N
  steps" for a workflow), a New conversation button, and a button to open the right column on narrow screens.
- Right column, when an AGENT is selected: an inline settings form with exactly the fields of the current editor (name,
  group, role, model, skills, instructions = the file body), a Save button, an Export button, a Delete button,
  and a "Recent conversations" section (the `agent:<slug>` channel sessions, click to open).
- Right column, when a WORKFLOW is selected: a title, a progress strip, a list of steps with the responsible agent and
  status (waiting, in progress, done, error), a "Run history" section (the latest runs, click to open
  that run's conversation), an Edit steps button (opens the existing workflow edit modal), Export, Delete.
- Narrow screens (under 900px): the left and right columns become drawers and the chat box takes the full screen.
- Display text comes from the dictionaries `dashboard/i18n/vi.json` and `en.json`, with proper Vietnamese diacritics.

Register the page in exactly three places: `RAIL_ITEMS` (console.js), `PAGES` (ui-actions.js), `PAGES`
(server/ui_targets.py), plus `VIEW_ICON`, `RAIL_GROUPS` (group `nang_luc`), `VIEW_META`, and a branch
in `renderPage`. Remove `agents` and `workflows` from all three lists; the voice aliases
("tro ly", "quy trinh", "agent", "workflow"...) point to `workspace`. The places that currently navigate
to `agents`/`workflows` (chatbots.js, packs.js) switch to `workspace`. The `skills` page stays
unchanged.

## 4. Chat sessions per partner

- The `conversations.db` session store already has a `channel` column. Use the values `agent:<slug>` and
  `workflow:<slug>`.
- Add `POST /sessions/new`, which takes `brain` and `channel` and returns `{id}`. The Partners page calls it when you
  click New conversation or when you pick a partner that has no session yet, then calls `openStoredSession(id)`.
  An agent session pins the agent's model (`model`, `model_provider` in the frontmatter) if it has one.
- `GET /sessions` gets a `channel` parameter: a specific value filters to exactly that channel; left empty it does
  NOT return channels with an `agent:` or `workflow:` prefix (so the Chat page's history bar
  does not mix in partner sessions). `list_sessions` in sessions.py takes the matching parameter.
- The title is set automatically like a normal session.

## 5. Chat with an agent

- In the turn dispatcher (`_do_turn` in main.py), split out a small function
  `_persona_cua_phien(row, brain)` that returns `(kind, slug)` from the session's `channel` column. This function is
  testable on its own.
- If kind is `agent`: the turn's system prompt is that agent's own prompt, built with
  `_agent_sysprompt` from `_workflow_agent_helpers` (which already includes the private memory
  `memory/agents/<slug>/MEMORY.md` and the `JAVIS_LESSON` rule). Drop the Jarvis 007 prompt layer (CLAUDE.md,
  the owner's memory, the channel block) and drop the context compactor (`_subscription_system_prompt` returns the
  agent prompt). Tools still go through the hub as in a normal turn.
- At the end of the turn: strip `JAVIS_LESSON` from the answer and write it into the agent's memory (using `_learn`),
  write the run log `memory/agents/<slug>/runs/` (using `_log_agent_run`), then save the session through
  `_persist_turn` as in a normal turn.
- If the agent file is gone: the turn returns an `error` frame "Agent <slug> is no longer in this brain",
  and does not fall back to Jarvis 007.

## 6. Running a workflow as a chat turn

- If kind is `workflow`: the dispatcher does not call `run_turn` but `run_workflow_turn`
  (a new function, same signature, registered in `_CHAT_RUNTIME` like a normal turn, so the Stop button and an F5
  mid-run both work).
- `run_workflow_turn`:
  1. Input = the user's message. If the session has an earlier finished run, append the block
     `\n\n# Kết quả lần trước\n<final result, cut to 8000 characters>` to the input. (The heading
     `# Kết quả lần trước` means "# Previous result"; it is kept verbatim because the code emits exactly this string.)
  2. Loop over `execute_workflow(brain, slug, input, tools=None, session_id=conv_sid)`.
  3. For each event: `start`, `step_start`, `step_done`, `step_error`, `step_verify*`,
     `step_retry`, `step_model`, `wait_user`, `escalation`, `replan`, `resume` are pushed as-is
     through a new WebSocket frame `{"type":"wf_event", ...}` (the right column draws progress). At the same time
     `step_start` pushes a `status` frame "Step i/N: <agent name> is working..." so the chat box shows
     an activity chip. `step_text` of the LAST step is pushed as a `stream` frame so the bubble fills in gradually;
     earlier steps do not stream into the bubble (they are already in the right column).
  4. `done`: the answer saved to the session = a first line "Run #N · K steps · T seconds" (N is the
     sequence number of the run within the session) + a blank line + the last step's result. Send `turn_done`.
  5. `error`: the answer = "Workflow stopped at step i (<agent name>): <error>". It is still saved to the
     session, and `turn_done` is still sent. It never ends without a message.
  6. `wait_user`: the answer saved to the session = "Workflow is waiting for approval of step <node>:
     <prompt>. Click Approve in the right column to continue." (no control block inside the message).
     The `wf_event` frame carries `task_id`, `node`, `code`; the right column draws the Approve button. Clicking Approve sends a
     WebSocket message `{"type":"wf_resume", session_id, task_id, node, code}`; the server runs
     `execute_workflow_resume` through the same `run_workflow_turn` (the resume branch), so the following
     result is also a message in the same session and is also written to the history store (updating the
     `waiting` record to `done`/`error`).
- Kanban still calls `execute_workflow` as before; the history saving lives inside `execute_workflow`,
  so Kanban, reminders and loops are all recorded.

## 7. Run history store

New module `server/workflow_runs.py`, SQLite at `<JAVIS_STATE_DIR>/workflow_runs.sqlite3`
(like `task_store.py`). One table `workflow_runs`:

| column | meaning |
|---|---|
| id | uuid hex |
| brain | brain key |
| slug, name | the workflow |
| session_id | the chat session if run from the Partners page, empty if from Kanban |
| source | `web`, `kanban`, `reminder`, `loop`, `other` |
| input | the input, cut to 4000 characters |
| status | `running`, `done`, `error`, `waiting` |
| started_at, finished_at | epoch |
| steps_json | list of steps: i, agent, task (cut to 2000), output (cut to 4000), verified, error |
| output | the final result, cut to 20000 characters |
| error | the error message |

API:
- `bat_dau(brain, slug, name, input, source, session_id) -> run_id`
- `ghi_buoc(run_id, i, **fields)`, `ket_thuc(run_id, status, output, error)`
- `gan_nhat(brain, slug=None, limit=20)`, `lay(run_id)`
- `lan_chay_moi_nhat_theo_slug(brain) -> {slug: started_at}` for sorting the list.

`execute_workflow` is wrapped with a tee generator: it opens a record at the start, updates on each event,
and closes on `done`/`error`/`wait_user` (waiting). The `start` event carries an extra `run_id`. `source`
is derived from a new parameter `source=""` of `execute_workflow` (Kanban passes `kanban`, the Partners
page passes `web`, default `other`).

HTTP:
- `GET /workflows/runs?slug=&brain=&limit=` returns the list (without the full `output`, only the first
  200 characters).
- `GET /workflows/runs/{id}` returns one full record.
- `GET /workflows` additionally returns `last_run_at` for each workflow; `GET /agents` additionally returns
  `last_chat_at` (the updated_at of the latest `agent:<slug>` session). The Partners page sorts by
  these two fields, descending, with empty ones after, by name.

## 8. Jarvis 007 knows about the latest run

- A new system plugin `system/plugins/javis-workflow/` (plugin.yaml + plugin.py) with tool
  `javis_workflow`, `min_mode: readonly`. Op `runs` (optional `slug` parameter, `limit` defaults to
  10) returns a compact list; op `show` (`id`) returns the full record including the steps and the result.
- `_javis_capability_summary` adds one line after the `Workflows:` line:
  "Latest workflow run: <name> at <time date> (<status>). See details or other runs with the
  javis_workflow tool (op=runs, op=show)." If there are no runs, the line is omitted.

## 9. Testing

- Python: `tests/test_workflow_runs.py` (the store: start, record a step, finish, latest, length
  truncation); tests for the two `/workflows/runs` endpoints; a test for the `javis_workflow` plugin; a test for
  `_persona_cua_phien`; a test for `list_sessions` channel filtering; a test for `run_workflow_turn` with a fake
  (mock) `execute_workflow` checking that the right messages are saved to the session in the three cases done/error/wait_user, and
  that the input has the "Previous result" block appended (`# Kết quả lần trước`).
- JS: `tests/test_ui_actions.js` updates the page list; the alias test in
  `tests/test_ui_targets.py` (if present) points to `workspace`.
- By hand: run the server locally, open the Partners page, chat with an agent, run a workflow, press F5 mid-run,
  view the run history, and ask in the main chat box "how did the latest workflow run go".

## 10. Out of scope

- A new marketplace: use the existing Jarvis 007 Store.
- Colored avatars and shapes per the concept: use the Lucide icons already in place.
- Inline editing of workflow steps in the right column: keep the existing modal.
- Running a workflow from the main chat box through a tool: still goes the Kanban `wf:<slug>` route as before.

## 11. Docs and version

- Update `docs/07-agents-va-workflows.md` for the new page.
- CHANGELOG for people reading on a phone: 3 to 4 bullets saying what users see differently.
- Bump VERSION to the next number on origin/main (fetch first).
