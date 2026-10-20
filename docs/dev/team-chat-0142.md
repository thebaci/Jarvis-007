# Team chat 0.142.0: no more silence, Zalo-style team creation, Jobs tab, Auto

14 Oct 2026. Branch `claude/compassionate-wozniak-z5umfl`, PR [#651](https://github.com/blogminhquy/javis-os/pull/651).
Base: `main` `063750a` (0.141.0). The version number was reserved right at the head of the branch (first commit, draft PR carrying 0.142.0).

**Renumbered at release:** while the work was in progress, `main` rose to 0.145.0 (#652 and #653, still open, hold 0.143.0 and 0.144.0), so this
change ships as **0.146.0**. The record's file name, the test names and the "0.142.0" notes in the code stay as they are, as the feature's milestone marker
(the backup suffix `.pre-0.142.0` also stays, to match the migration marker that already ran on test machines).

The original goal sits on the repo owner's machine (`exports/reviews/team-chat-zalo-ux-2026-10-14/goal-claude-v2.txt`, `audit.md`, images
01 to 08). This session ran in a cloud container and could not read that folder; the work followed the goal text pasted into
the `/goal` command, together with the five attached screenshots. PR #645 (closed) was not touched.

## 1. Silent team chat: verified root cause

Two overlapping bugs:

1. **Team turns went through Resonance's contract.** `main._team_engine_for` built the engine with `_resonance_engine`: the BACKGROUND-WORK
   model, and `resonance.pick_text_only_link` accepts only two text-only mechanisms (Claude with the `can_use_tool` gate, API engines with
   `no_tools`). On a machine whose background-work model is Codex, every turn was blocked before the model call milestone.
   Reproduced on the old `origin/main` code (temp worktree, settings: main Claude, background work Codex):
   `EngineUnavailable: model việc nền chưa chạy được lượt chỉ chữ: {... 'blocked': 'engine openai-oauth còn công cụ
   native, chưa có cơ chế chỉ chữ được kiểm; Resonance M1 chỉ nhận Claude (cổng can_use_tool) và engine API (no_tools)'}`
   (Vietnamese error text, kept verbatim; in English: the background-work model cannot yet run a text-only turn, because the openai-oauth engine
   still has native tools and no verified text-only mechanism, and Resonance M1 accepts only Claude (the `can_use_tool` gate) and API engines (`no_tools`)),
   and `engine_started` was never called.
2. **The failure outcome was thrown away.** `team_api.teams_send` ran `runner.run_replies(sub)` in the background and nobody read the result; a failed turn
   survived only in the turn ledger, with no row in the chat frame.

## 2. What was done

| Item | Change | Main files |
|---|---|---|
| Engine contract | `team_engine.py`: the assistant's own model, or the main model if it is missing or cannot be configured (a note on the message says why). No background-work model, no fallback chain, no privilege raise | `server/team_engine.py`, `main._team_engine_for` |
| Codex text-only | No `-p` profile, `mcp_servers={}`, `web_search="disabled"`, native tools turned off with `features.*=false`, ALWAYS `--sandbox read-only` (even with `JAVIS_CODEX_SANDBOX=off`) | `team_engine.codex_text_only` |
| Grok, Antigravity | No verified text-only mechanism yet: report the reason, do not run on another provider instead | `team_engine.build` |
| Reply turn outcome | Table `team_replies` (queued, running/answering, done, error + reason), WS packet `team_replies`, message page with `replies`, Retry by CAS `error -> queued`, a restart turns a half-done turn into `error/restart` | `team_store.py`, `team_runner.py`, `team_api.py`, `teams.js` |
| Blocked background work | Add a system message right in the chat frame (outside the inbox) | `team_runner._block` |
| @ by agent_key | With duplicate names the user must pick from the suggestions (the code is written in order of picking); hand-typing a duplicate name calls nobody and says so | `teams.js mentionScan` |
| Create, add to a team | Zalo-style picker box, overlay attached to `<body>` | `team-picker.js`, `teams.js`, `console.css` |
| Jobs tab | `GET/POST /agents/{slug}/jobs`; grouped by agent_key, reading the source records; Assign a job creates a Kanban job carrying the key `agent:<code>:<slug>:<nonce>` | `agent_jobs.py`, `main.py`, `tasks.py`, `task_store.py`, `agent-jobs.js`, `workspace.js` |
| Drop the fixed reviewer | A new goal is not attached to a team; a one-time migration for old goals | `resonance_store.py`, `resonance_api.py`, `resonance-agent.js`, `chat-resonance.js` |
| Auto | Display rename; the switch in the card and the entry in the three-dot menu share `doiAuto` | i18n, `resonance-agent.js`, `workspace.js`, `console.css` |

### Evidence for Codex text-only (Codex CLI 0.153.4, the pinned Docker version)

Ran a real `codex exec` pointed at a fake Responses server on the local machine (no call to OpenAI), recording the request body:

- Default: the tools sent to the model are `exec_command, write_stdin, request_user_input, apply_patch, view_image, get_goal,
  create_goal, update_goal, tool_search, web_search`.
- With the `codex_text_only` flags: only `request_user_input` (usable only in Plan mode) and `apply_patch` remain.
- The fake server returned an `apply_patch` writing a file OUTSIDE the working directory: Codex refused at the policy layer (`patch rejected:
  writing is blocked by read-only sandbox; rejected by user approval settings`), and the file was not created.
- A `features.*` name unknown to a given Codex version is ignored (tried), so the extra list does not break another version.

### Jobs tab: sources and states

- **Team:** directly assigned jobs (`assignee_key`), coordination jobs (`coordinator_key`, the plan and synthesize steps), and jobs that
  only do a sub-step or give help (the `work` and `help` steps in `team_steps`). Progress is the real number of steps, the real position in the
  team's queue, and Cancel goes through the team's cancel route.
- **Private chat:** a Kanban job with a `chat_id` that is an `agent:<slug>` session pinned to the right code (an older code-pinned session with the same slug is excluded),
  and jobs assigned with the Assign a job button. A Kanban job's metadata is overwritten when the job finishes running, so ownership lives in the
  idempotency key (durable for the whole life of the job). The title carries the assistant's name so Kanban does not merge two jobs with the same text from two assistants.
- **Auto:** the assistant's goals (`goal_agents`) and old goals where the assistant is the reviewer. The reason codes `review_removed` and
  `paused` appear in plain words.
- **Honest queue:** if the brain has "AI self-driving" turned off, a directly assigned job says clearly that it only sits waiting; the tab footer states the
  ceiling on background work running at the same time (`JAVIS_KANBAN_MAX_WORKERS`).
- A Kanban job assigned to an assistant runs in the assistant's role (the prompt as in a workflow, appended to the system prompt). The Kanban engine,
  permissions and ceiling are unchanged. Reading the tab creates nothing; ordinary chat does not create jobs by itself.

### Migration that drops the fixed reviewer

Runs once when the store is opened (a row in `review_migrations`), after first copying `resonance.sqlite3.pre-0.142.0`:

- Every `team_pairs` pair is turned off (`enabled=0`, `config_version` bumped), and the row is kept.
- For every goal that still has an `active` team: the team is `detached` by `host:review_removed`, the `team_detached` event records the running state and the
  previous blocking reason, and the wake reason of the review role is closed as `superseded`. A goal that is open is **paused**, and a block belonging to the detached team
  goes back to `ready`.
- The owner's `team_detach` is not reused: that command schedules an immediate wake, and that wake closes under rule A4, and can end
  `succeeded` with nobody reviewing (A5 tests T24 and T46 assert exactly this).
- Nothing is deleted: `reviews`, `team_calls`, `goal_events`, submissions and the target files are kept. The owner sees the goal in the Needs you drawer
  and on the card: Resume, edit, cancel, or assign a verification job.

## 3. Checks

**New tests:**
- `tests/python/test_team_chat_0142.py`: model selection, building the engine for each provider, Codex `read-only` when the sandbox is off, reply turn
  outcome (waiting, answering, done, error), one failed turn does not lose the next turn, Retry does not double the message, turn or
  result, resending the same `client_msg_id`, paused team, restart, blocked work has a message in the chat.
- `tests/python/test_agent_jobs_0142.py`: real routes, roles in team jobs (assigned, coordinating, helping), cancelling one job does not
  touch another, Assign a job duplicate protection, no merging by title between two assistants, private chat session, role at run time, no
  source fails silently.
- `tests/python/test_review_removed_0142.py`: an A5-era store with a goal waiting for review, simulating a pre-0.142.0 store, opened
  with the new code; it does not pass itself even when woken again, history is kept, there is a copy, and running again changes nothing.
- `tests/js/test_team_chat_0142.js`: duplicate-name @, the turn status line, the picker box, the Jobs tab, Auto.

**Old tests updated to the new design** (the reason is stated in each file): `test_team_t1_review.py` (the engine swap point),
`test_teams_ui.js`, `test_workspace.js`, `test_tab_thu_muc.js`, `test_team_t0_toggle.js`, `test_resonance_a5_ui.js`,
`test_resonance_a5_api.py` (the set-reviewer route returns 410), `test_resonance_a5_team.py` (T31: the real `javis_goal` path does not
attach a team), `test_resonance_a5_rollback.py` and the helper `_resonance_team.py` (re-enable attaching a team to build an A5-era store).

**Results on the container:** `tests/run.py --js` 187/187. `tests/run.py --py` 503/512 the first time; 9 red files, none caused by
this change (`pytest` missing from `.venv` for 7 files, `test_khoi_dong_nhe` measuring time while the machine was under heavy load, and
`test_icons` catching two fallback characters in `team-picker.js`, since fixed). After installing `pytest` and rerunning all 9: green.

**Real browser smoke test** (Chromium via Playwright, sandbox on port 7788, temp state and brain, real main model Claude `haiku`,
background-work model set to Codex to reproduce the original failure case, no Telegram, Zalo or any outside channel):

- 1366x860: created a team through the picker box (searching "muc tieu" finds Coach, filtering by tag and then changing the tag keeps the people already picked, the Coordinator defaults
  to the first person), went into the chat immediately. Ordinary message: the team lead replied with the real model. @One when there are two assistants named One: picked
  copy B, and exactly copy B replied. An assistant with a nonexistent model: the "Could not answer" row with the real error sentence and a Retry button;
  clicking Retry ran exactly one turn. Assigning a short job: the result came back to the chat frame with the label "Job result", and appeared in the Jobs tab
  in the Done drawer. Reloading the page: the turn status stayed intact. Assigning a job from the Jobs tab with AI self-driving off: said clearly that it only
  sits waiting. The Auto switch on the card and the Auto entry in the three-dot menu.
- 768x1024: the team chat frame, the picker box in the middle of the screen.
- 375x812: the picker box fills the screen, a fixed footer at the bottom (737 to 806 of 812), no horizontal overflow; the Auto switch tap target
  is 87x44; the Jobs tab in the right drawer.
- Bugs found by the smoke test and fixed: the picker overlay was covered by the app's top bar on a phone (now attached to `<body>`),
  the error detail showed "(success)" instead of the real error sentence, the label of a finished job showed only the code after reloading, a stray
  period in a note, and "Team Team ..." in a job's source.

## 4. Independent review of the whole change

A fresh review agent read all of `origin/main..HEAD` (not only the last fix) and ran the team, 0142, A5 and i18n tests itself.
Verdict: 1 Blocking, 2 Important, 6 Minor. All fixed, each with a test:

| Level | Finding | Fix | Test |
|---|---|---|---|
| Blocking | Re-attaching the Jobs tab on the same frame stacks listeners: one click on Assign creates several jobs, and Cancel asks several times | The listener is attached once per frame, handing over to the live attachment | `test_team_chat_0142.js` (attach three times, one POST) |
| Important | The old "Unlimited" permission (`anthropic-cli`) now also covers runs of the main model that the owner never agreed to | The permission carries `providers_v=2`; an old permission grants Unlimited to no provider, and the ceiling falls back to the team level until the owner grants it again | `test_team_chat_0142.py` |
| Important | A late old turn overwrites the outcome of a Retry; recovery marks even a just-sent turn as "restart" | `settle_reply` by `attempt` and only while the turn is still open; recovery touches only turns written before the process started | `test_team_chat_0142.py` |
| Minor | Cancelled midway, later turns sit "waiting" forever; so do background jobs that could not be created | Cancel closes unstarted turns as error `interrupted`; waiting more than 10 minutes gives a Retry | `test_team_chat_0142.py`, `.js` |
| Minor | The reasons `leader_changed` and `superseded` have no labels | Added vi/en labels | `.js` |
| Minor | Enter in the team name field does not move to the search field (the picker box moved out to `<body>`) | Search inside the overlay | |
| Minor | Assigning a job reports into the session of an older assistant with the same slug | Choose the session pinned to the right code, open a new one if none | `test_agent_jobs_0142.py` |
| Minor | A nonce made entirely of odd characters becomes empty, so every assignment shares one key | Check after filtering, 400 | `test_agent_jobs_0142.py` |
| Minor | A superfluous `metadata` parameter | Removed | |

Checked and found no defect: a team turn never has tools (Claude, Codex, API; Grok and Antigravity are refused), no data mixing
between brains, all new HTML is escaped, the migration does not pass itself and does not delete history, ordinary chat does not create jobs,
turning off Auto does not touch team work or Kanban.

## 5. Remaining limits

- The smoke test with a real provider covers only Claude (the container has no ChatGPT login). The Codex path was checked with the real Codex CLI
  against a fake Responses server, not a real ChatGPT turn.
- Grok Build and Antigravity cannot yet run a team turn: Grok still has native read tools, and `agy` uses an MCP shared through a machine file. An assistant set to these two models uses the main model, with a note on the message.
- Codex's `apply_patch` cannot be turned off with a flag; the blocking layers are `--sandbox read-only` plus the tool-event check in
  `TextOnlyOutcome`.
- A job assigned with the Assign a job button runs on Kanban's background-work engine (permissions and ceiling unchanged), in the assistant's role; it
  does not use the assistant's own model the way a team chat turn does.
- The old "Unlimited turns" permission that recorded `aux` no longer matches any turn (a team turn now records the real provider): the ceiling falls back to the team's level,
  which is stricter.
- Not merged, not deployed to a VPS.

## 6. Cross-check against goal-claude-v2 and the audit

Second session (14 Oct 2026, the repo owner's Windows machine, able to read `exports/reviews/team-chat-zalo-ux-2026-10-14/`): each
requirement of `goal-claude-v2.txt`, each finding of `audit.md` and images 01 to 08 were checked against the code on the branch (HEAD `f225ba1`).
Three agents read code in parallel by item group (1-3 and 7, 4-5, 6 and 8-9), each item recorded as Pass, Missing or Wrong with `file:line`; the
missing and wrong parts were fixed on the same branch, keeping the number 0.142.0. Items that already Passed from the earlier session are the ones in section 2 above.

### Cross-check table (items that were Missing or Wrong at the time)

| Goal / audit item | At cross-check | Fixed | Evidence |
|---|---|---|---|
| 1. Internal team context in the prompt (not a customer Zalo group, no silence by chatbot rule, no sending out to Zalo) | Missing | `INTERNAL_GROUP_NOTE` appended after the assistant's prompt in every team turn | `team_runner._prepare`, `test_team_chat_0142_review.py` item 1 |
| 1. An AI's message is not a new command from the owner | Missing | Same paragraph as above: only the "Chủ nhóm" (Team owner) message is a request | same as above |
| 1. State the T1/R3 contract change explicitly | Missing in the design doc | Note under R3 | `docs/dev/team-chat-t1.md` |
| 1. Grok/Antigravity | Wrong against the record (reported an error instead of using the main model) | Run on the main model, with a note on the message | `team_engine.text_only_supported`, test item 5 |
| 2. Timeout | Missing: a hung turn sat "answering" forever | `JAVIS_TEAM_TURN_TIMEOUT` ceiling (600 seconds), error `timeout` with Retry; kills exactly the engine process of the turn before releasing the busy lock | `team_runner._turn`, `main._team_engine_for.run` (tag per turn) |
| 2. Login error, model | Wrong: one shared label, only Retry | Reason `auth`; buttons Open the Models page, Change the assistant's model | `replyActions` (`teams.js`) |
| 2. Missing coordinator | Wrong: the message had no outcome row | A `__leader__` row with reason `no_leader`, a Choose coordinator button; Retry hands exactly one turn to the current coordinator | `team_runner.retry_reply`, test item 3 |
| 2. Out of turns, paused, coordinator left | Wrong: only Retry | Open the team limits, Resume the team, Choose coordinator; a paused team with no coordinator still gets a row | same as above |
| 2. Busy with other work | Weak: only "Waiting" | "Waiting: the assistant is working in the team X" | `_acquire(on_wait)`, test item 4 |
| 2. WebSocket lost | Wrong: a missed packet was not reloaded | The second `hello` emits `team_resync`, and the Teams page reloads messages, the job queue and teams | `app.js`, `onTeamEvent` |
| 3. Picking from a suggestion is not re-inferred by name | Wrong | The choice is stored as `{agent_key, label}`; if the token is intact, call exactly that code; editing or deleting the token drops it; the newest choice wins | `mentionScan`, `pickMention` |
| 3. A separate token in the composer, deleting the token drops the call | Missing | A "Calling:" row, one card per person with an x button (deletes exactly that token, without breaking another person's longer token) | `callsHtml`, `removeMention` |
| 3. Accent-insensitive search; up/down, Enter, Escape; photo, name, role, slug | Wrong, Missing | Accent-insensitive search by the start of any word (name, slug, role); the listbox has `aria-activedescendant`; keys are handled before the drawer's Escape; skipped while typing in an IME | `mentionMatches`, `sugKey`, `member_views.title` |
| 3. An email does not open suggestions | Partly wrong | `emailBefore` | `test_team_chat_0142_review.js` |
| 4. "No tag" chip, composite photo preview, collapsed description | Missing, Wrong | Done | `team-picker.js` |
| 4. Coordinator chosen right on the picked list; removing the coordinator is shown clearly | Wrong (a separate select, switching silently) | A Coordinator button on the chip; removing it leaves it empty, says so, and locks the Create button until chosen again | `normalize`, `canSubmit` |
| 4. Server-side duplicate-creation protection, at least one assistant, one transaction | Missing | `client_req_id` (unique index per brain), 400 when there is no assistant, team + members + coordinator in one transaction, an orphan session is deleted | `team_store.create_team`, `team_api.teams_create`, test item 6 |
| 4. After creating, focus the composer; loading, load error | Wrong, Missing | Done | `drawComposer`, `loadRoster` |
| 4. Adding members: "Already in the team", count only new people | Wrong (hid people already in) | Show them, lock the picker box, "N new" | `team-picker.js` |
| 5. The creator comes from the server's authenticated session; old teams get a migration | Missing | Column `created_by` (old teams get `owner`), `team.creator` is filled by the server, a client-supplied value is ignored | `team_store`, `team_api.creator` |
| 5. "You + N assistants" at the head of the team and the member list | Wrong | `headLine`, the title of the Members section | `teams.js` |
| 5. Not covered by the keyboard (picker box) | Wrong on iOS | The picker box shrinks by `--vv-h` when `kb-open` | `console.css` |
| 6. Source filter, pagination | Missing | Done (no more hidden ceiling on jobs) | `agent_jobs.collect`, `agent-jobs.js` |
| 6. Card: latest update, next step | Missing | `updated_at`, `next` (queue position, waiting on another team, needs you, turn on AI self-driving) | same as above |
| 6. Roles Coordinating, Doing, Helping, Checking | Wrong labels | Renamed | i18n `ajobs.role.*` |
| 6. Assign a job: completion criteria, where the result goes, confirmation | Missing | Done; assigning into a team goes through the team's own `runner.submit`; a team job's title takes the opening passage | `main.agent_jobs_assign`, `_enqueue_for` |
| 6. Resume, priority; Cancel goal with revision | Missing | Resume (`resume` + `expected_revision`), Prioritize team jobs through the existing route | `agent-jobs.js` |
| 6. Editing in one place syncs the others | Missing | Listens to team, goal, session and job events; does not redraw while a form is being typed in or an IME is active | `agent-jobs.js` |
| 7. Do not open many model turns just because there are many jobs | Missing for jobs assigned from the Partners page | Kanban: one `agent:` job running per assistant, other jobs still run (FIFO) | `task_store.next_candidate`, `claim` |
| 7. Role by identity | Wrong: looked up by slug | `_agent_persona(root, slug, agent_key)` checks the code | `tasks._persona` |
| 8. Verification is a separate job, clearly linked | Missing | A "Check" kind in Assign a job, criteria required, a link to the item being checked, self-checking one's own job is blocked; an "Assign a check" button on the card | `agent_jobs.resolve_link`, `/agents/{slug}/jobs/verify-targets` |
| 8. Migration test for every state | Missing | `review_changes`, running, blocked for another reason, not started, failed | `test_review_removed_0142.py` |
| 9. Still the words "Cộng hưởng" (Resonance) and "trưởng nhóm" (team lead) in the UI | Wrong | "Auto" in settings and system messages; "team lead" became "coordinator" in the team UI (vi/en) | i18n, `team_runner.py`, `index.html` |
| 9. Auto synced with the Teams page; the job badge separated from Auto | Missing | The Teams page listens to `javis:resonance-agents-changed`; a job badge (working, needs you) separate on the card | `teams.js`, `workspace.js`, `/agents/jobs/counts` |
| Image 01 (silent chat frame) | Pass after the fix | Real smoke test below | `smoke-0142/1366-error-row.png` |
| Images 02, 04, 07 (flat form; Zalo flow) | Pass after the fix | | `smoke-0142/1366-picker.png`, `375-picker.png`, `1366-add-members.png` |
| Images 03, 05, 06 (Zalo group info) | Pass within scope | The panel has the creator, coordinator, members, Add, pin, status, permissions; invite link, polls, deleting history are outside the goal's scope | `smoke-0142/1366-team-panel.png` |
| Image 08 (the "Resonance: On" row outside the card) | Pass | The Auto switch inside the card, orange when on | `smoke-0142/375-auto-on.png`, `375-menu.png` |

### Independent review round 2 (the new changes, `f225ba1..81eb61c8`)

No blocking defects. Fixed, each with a test:

| Level | Finding | Fix |
|---|---|---|
| Important | An old @ choice grabs the token of a new choice ("Lan" then "Lan Anh") | Consider the newest choice first; drop a choice that lost its token when a new person is picked |
| Important | Going over the time ceiling only cancelled the read side, the Codex process was still alive, and the busy lock was released | Tag per turn, `cancel_all(tag)` and `aclose()` before releasing the lock |
| Important | The Jobs tab redraws the whole frame while a form is being typed in | Defer the reload while a form is open, an input is focused or an IME is active |
| Minor | Dropping the call of one person breaks another person's longer token | Skip places where a longer name of another person also matches |
| Minor | A paused team with no coordinator: the message has no row | A `__leader__` row with reason `team_paused` |
| Minor | The job count for the badge runs even while viewing Workflows or a hidden tab | Only when the assistant list is showing |
| Minor | Reading the store on the event loop in `waiting` | Moved to `_io` |
| Minor | An orphan session when creating a team fails | Delete the session |
| Minor | A team could be created with no coordinator | Lock the Create button until one is chosen |
| Minor | Kanban from private chat (without an `agent:` key) and team turns can still run at the same time as an assigned job | Recorded under limits, not fixed |

### Smoke test with a real provider (sandbox on port 7788, temp state and brain, no Zalo, Telegram or customers)

Configured like the real machine in the audit: the main model and the background-work model are both OpenAI OAuth (Codex CLI 0.160.0 on the machine),
`gpt-6.1-sol`. "Jarvis 007 Vũ Zalo" is set to its own Codex `gpt-6.1-sol`, and its prompt carries the Zalo chatbot rule "stay silent when not called";
Coach has no model set (follows the main model); the two assistants with the same name One are set to Claude `haiku`.

Five model calls, and it stopped there:

1. Ordinary message: Jarvis 007 Vũ Zalo (the coordinator) replied after 10 seconds with `openai-oauth gpt-6.1-sol`, without going silent by the chatbot rule.
2. @One, copy A picked with the arrow keys: exactly copy A replied (`anthropic-cli haiku`).
3. A short job assigned to Coach: ran on the main model Codex, the result came back to the team, and appeared in the Jobs tab in the Done drawer after reloading;
   Open took the user back to the right team.
4. One copy B set to a nonexistent model: the row "Could not answer: the model reported an error..." with the real error sentence, the Change model and Retry
   buttons; it was still there after reloading the page. (Correction: the original record said "restarted the server and it was still there after reloading". Wrong: the stop command
   killed only the shell process of the `.venv`, the child Python process kept port 7788, so the later "restarts" could not
   bind and the browser kept talking to the first server that started (code `81eb61c8`). The server part fixed after that, along with a half-done turn
   becoming `restart` after a restart, was checked only by automated tests, not by the smoke test.)
5. Fixed the model and double-clicked Retry: exactly one new turn, and copy B replied.

No model call: double-click Create team (one team), removing the coordinator with a warning, Add members ("Already in the team", "0 new"),
Assign a job in private chat with criteria and a review step (double-click Confirm still gave one job; AI self-driving was off, so it said clearly that it only sits
waiting), an email does not open suggestions, the Calling token can be removed, Auto on in the card and off in the three-dot menu.

Measurements: 1366, 768, 375 had no horizontal overflow (`scrollWidth` equals the width); the picker box at 375 fills the screen, footer 743 to 812;
the smallest text in the picker box is 16px; the Auto switch is 87x44. The smoke test caught two more bugs, fixed: the @ suggestion list in the dark theme
had a nearly transparent background (`--surface-1`, a pre-existing bug); the filter bar for finished jobs showed the job code instead of the name. Screenshots:
`exports/reviews/team-chat-zalo-ux-2026-10-14/smoke-0142/`.

### Remaining limits

- Kanban from private chat and team turns do not yet share the busy lock with jobs assigned from the Jobs tab; the shared ceiling is still
  `JAVIS_KANBAN_MAX_WORKERS` and the team's busy lock.
- Kanban jobs have no priority route yet, so the Jobs tab has Prioritize only for team jobs. A workflow run (`wf:`) has no
  assistant identity yet, so it does not appear in the tab.
- The team photo cannot yet be changed (it is composed from the assistants' photos), so there is no change-photo button. Invite links, polls, multiple accounts are outside the scope.
- Not merged, not deployed to a VPS.

### After the report: the Auto switch moves to the tag row

The repo owner looked at the 375 screenshot and asked (14 Oct 2026): the Auto switch on its own row at the bottom of the card makes it hard to tell which assistant it belongs to. Now the
switch sits inside the card, on the SAME ROW as the tags, on the right; the three-dot button moved up level with the name so the tags have enough room in the narrow column; an assistant with no
tags keeps the switch on its own bottom row. Measured in the browser: the switch's center is off the tag's center by at most 1px, tags are not clipped at
1366 and 375, they do not overlap the three-dot button, and the tap target is 44px on touch screens. The card is also one row shorter.

### After the report: Partners page layout

The repo owner asked (14 Oct 2026, with a screenshot of a chat list that shows times):

- **Latest message time** on the assistant card, on the same row as the name (today hour:minute, yesterday "Yesterday", older day/month). The data is the
  existing `last_chat_at` from `/agents` (also the list order); it now counts only sessions that have messages, because clicking an assistant makes the page
  create an empty session in advance. When a chat turn finishes, the time on the card changes immediately.
- **The right column is hidden by default** on wide screens; a button in the right corner shows it again and the choice is remembered (`javis_ws_right`). Opening Settings to confirm
  an assistant still shows the column by itself without overwriting the choice. Narrow screens keep the drawer as before.
- **A wider list column** (default `clamp(240px, 24vw, 320px)` instead of 210-260px) that is **draggable** at the edge, as is the right column;
  with a keyboard handle (left/right arrows 16px), double-click to return to the default, clamped to 220-560px (left) and 280-640px (right), never more than
  45%/50% of the page width; remembered through `javis_ws_left_w`, `javis_ws_right_w`.
- **With the right column hidden the text gets wider:** the reply bubble stretches to `min(120ch, 100%)` instead of 72 characters.

Measured in the browser: at 1366 the left column is 320px, dragging 80px more gives 400px and it persists after reloading; with the right column showing, dragging 350 to 430px;
the bubble is 846/850px of the middle area when the right column is hidden (1366), 1298px at 1920 (the 120-character ceiling); at 375 there is no drag handle, no horizontal
overflow, and the time is on the same row as the name. The time text is 14px to match the assistant name in the narrow column (a deliberate exception to the 16px floor for new parts).
Tests: `tests/js/test_cong_su_bo_cuc_0142.js`, plus one check in `test_sessions_kenh_cong_su.py`.

### Review before release

The repo owner asked for a full review before merging. Two agents independently read `origin/main...HEAD` (server and UI), running
the code and tests themselves; no blocking defects. Real checks: upgrading a `team.sqlite3` built with `origin/main` code (opened twice, the old code could still open the
upgraded store), the Resonance migration, recovery at startup, Kanban's one-job-per-assistant lock, and per-turn tags killing the process. Restarted the
real sandbox server (stopped by port): the server came back, and the reply turn status row stayed intact.

Fixed, each with a test (`test_prerelease_0142.py`, `test_team_chat_0142_review.js`, `test_cong_su_bo_cuc_0142.js`):

| Level | Finding | Fix |
|---|---|---|
| Important | The job badge and the verification list opened one Resonance store connection for EACH session: 15 seconds with 20 assistants x 150 sessions on Windows, and overlapping requests clogged the side thread | `session_pins` is read once; the page runs only one count pass at a time |
| Important | Shrinking the window to half the screen made the right column pop out over the chat frame (the `right-open` class changed meaning with the screen size) | Listen for screen-size changes and reset to the new meaning |
| Important | The "File location" button on the Partners page did nothing when clicked (the Folder tab was removed) | Open the Files page and highlight the file in the tree |
| Important | The status row of a person who left the team showed the code instead of the name | Look up the author ledger |
| Minor | @ a person who left the team: nobody answered the message and the notice was filtered out (it contained a code with `_`) | The notice uses the name; the composer filters only codes |
| Minor | The 10-minute ceiling applied to team job steps too (there was no ceiling before) | Chat replies 10 minutes, team job steps 60 minutes (`JAVIS_TEAM_STEP_TIMEOUT`) |
| Minor | An assigned job reported into an archived or empty session | Prefer an unarchived session that has messages |
| Minor | Manually running a Kanban job while the assistant is busy returned `ok:false` with no reason | A reason sentence in vi/en |
| Minor | The picker box lost focus after picking, Escape did not close it; the Jobs tab still asked the server after leaving the tab; Retry could get stuck; saving Settings collapsed the right column even though the owner chose to show it; on a 1061-1240px laptop the right column lost its old width; dragging both columns could squeeze the chat frame down to ~100px | Fixed one by one; the chat frame always keeps at least 360px |
| Minor | A `nonce` error returned a raw code | A sentence in vi/en |
