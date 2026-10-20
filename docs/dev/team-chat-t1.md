# Team chat group T1: team chat core, Limited authority (0.111.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) (D1 to D7, settled on 13/10/2026). Plan: [2026-10-13-team-chat-t1.md](../superpowers/plans/2026-10-13-team-chat-t1.md), with rulings R1 to R3 there.

## First useful flow

1. The owner creates a team on the **Teams** page (sidebar, Capabilities group, next to Partners): name, description, members, leader.
2. A message with no @ is answered by the leader (D1). If an @ is picked from the suggestions, only the person called replies, in @ order; later people see the earlier person's reply.
3. Turning on **Assign job** makes the message a team job in the queue (D2). No @: the leader plans, assigns each part, then synthesizes. With @: the person called does it directly.
4. The queue has **Prioritize** / **Remove priority**, numbered in the exact run order. A blocked job leaves the running slot and shows under "Waiting for you" with a reason, and a message goes to the inbox.
5. Results come back to the right team, each message with its author, role, job label and a status in words; the final one carries the label "Job result".

## Code map

| Part | File | Job |
|---|---|---|
| Identity | `server/resonance_store.py` (`agent_register`), `server/main.py` (`save_agent`) | Durable id for members without turning on Resonance. Creating an agent with a duplicate slug returns 409, no overwrite |
| Team store | `server/team_store.py` (`team.sqlite3`) | Teams, members, events, internal steps, turn ledger, busy lock; `set_caps`, `log_event` |
| Messages with a sender | `server/sessions.py` | Columns `author_kind`, `author_ref`, `client_msg_id` (unique within a session), `reply_to`, `task_id`, `step_id`, `meta_json`; hide `team:` and `teammate:` from chat history; decision log; messages by job |
| Queue | `server/task_store.py` (the `team` lane of `kanban.sqlite3`) | `enqueue_team` (key = source message, no merging by title), `team_queue`, `team_priority` (CAS `queue_version`, 409), `claim_team_next` (one running job per team, same transaction), block, unblock, done, cancel, edit request, recover. The old Work board code ignores every `lane='team'` row |
| Runner | `server/team_runner.py` | Routing, reply turns, team jobs (`plan`, `work`, `help`, `synthesize`), the `JAVIS_TEAM` block, caps, loop guard, late output, FIFO busy lock, turn ledger, cancel mid-turn, recovery after restart |
| Routes | `server/team_api.py`, wired at the end of `server/main.py` | `/teams/*` (19 routes), 5-second dispatch loop, reminders for jobs blocked over 24 hours, text-only engine, inbox, WS packets `team_message` / `team_state` |
| UI | `dashboard/teams.js`, `console.js`, `index.html`, `console.css`, `app.js`, i18n | Three-column Teams page, a drawer under 1060px, one column under 760px |
| Upgrade, downgrade | `server/team_migration.py`, `tools/team_chat_restore_pre.py` | `.pre-0.111.0` snapshot of `kanban.sqlite3` and `conversations.db`, restore tool |

## The JAVIS_TEAM block (ruling R1)

An agent coordinates with a block the host reads at the end of its reply:

```
<!-- JAVIS_TEAM: {"op": "assign", "agent": "<id or slug>", "brief": "..."} -->
<!-- JAVIS_TEAM: {"op": "request_help", "agent": "<id or slug>", "question": "..."} -->
<!-- JAVIS_TEAM: {"op": "propose_job", "title": "...", "brief": "..."} -->
```

| Role of the turn | Ops allowed |
|---|---|
| Leader replying in chat | `propose_job` (becomes a card; the job exists only after the owner presses Create job) |
| Member replying in chat | None |
| Planning | `assign` |
| Work, Help | `request_help` (one person per turn) |
| Synthesize | None |

A bad op (broken JSON, unknown op, a person outside the team, reverse help request, too deep) is dropped and a note shows under the message; no turn goes beyond the cap.

## Caps (D7, edited in the team's Settings tab)

12 turns per job; 8 steps per job; help depth 2; no reverse help; 2 turns in a row with the same result stop it (`no_progress`); 3 @ per message; 100 turns per team per day (chat turns count too); 1 running job per team; 2 teams running at once; 1 simultaneous turn per agent (D3); 30 minutes waiting for the busy lock. Caps are checked BEFORE a turn slot is reserved, so hitting a cap does not call the model.

## Turn ledger

One row per model call. Reserving the slot and checking the caps (day, job) happen in the SAME `BEGIN IMMEDIATE` transaction (`reserve_turn` with `daily_cap`, `task_cap`), so two simultaneous turns cannot both take the last free slot. A failure before the engine-call mark refunds (`refunded`) exactly once. After the mark it counts, including on error, cancel mid-turn (`interrupted`), and restart (`interrupted`, never re-run automatically).

**Engine-call mark (review round 1, R4):** the real engine (`fn.marks_engine`) finishes building the engine, checks `is_available`, and only then calls `req["engine_started"]`; the runner records the mark there. If building fails (`_resonance_engine` returns None, the engine reports not ready, the config throws) or the turn is cancelled while building, the turn is refunded and the blocked job is `failed` with the reason "Could not build the engine" so it can be re-run. A fake engine that declares nothing gets the mark right before the call, as before.

**Engine outcome (R1):** the adapter reads events through `team_runner.TextOnlyOutcome`, with the same rules as `_engine_outcome_pop` of the chat turn: a final with `is_error`, the flag `auth_refresh_race`, an `error` event (even after the final), tool calls (`tool_call`, `tool_use`, `tool_result`), a missing final, or an empty final all make the turn `error` (counted), the step failed, and the blocked job `failed`. A lost-thread error the engine already primed again within the turn (`resume_failed`) does not count as an error.

**Durable lessons (R3):** the adapter only EXTRACTS `JAVIS_LESSON` / `JAVIS_RULE` (a rule is downgraded to a lesson because in a team the owner does not talk to the agent directly) and returns `commit`. The accept phase (`_accept`) checks the output is still valid and then calls `commit` inside the same `accept_lock` (chat turn); for a team job step, `commit` runs in the apply phase (`_apply_step`) after the final check (round 2, R7). Operations that make the output invalid (removing a member, changing the leader, cancel, editing the request, archiving, deleting an agent in `delete_agent`) hold the same lock. `commit` re-checks identity (the durable id still points at the right slug) right before writing, and `claim_commit(turn_id)` allows writing exactly once per turn. Invalid output is only evidence: the message has `applied=false` and `held_lessons`, and the agent's memory does not change.

## Known limits of T1

- **Team turns are text only** (R3): no file read or write, no MCP, no `javis_goal`. Opening tools with a per-team permission gate is left for T3.
  - **Changed in 0.142.0** ([team-chat-0142.md](team-chat-0142.md)): team turns no longer build the engine through the Resonance contract (`_resonance_engine`, the background-job model, only Claude and API engines). A dedicated contract `server/team_engine.py` uses the assistant's model, and the main model when missing; Codex runs text only (no profile, empty MCP, native tools off, always `--sandbox read-only`). The R3 limit stays: still text only, no tools, no MCP, no hub; Grok and Antigravity run on the main model with a note.
  - **Changed in 0.194.0** (owner, 17/10/2026: "a team needs full permissions to be able to work"): the **Work** and **Help** steps of a team job (`team_runner.TOOL_ROLES`) run WITH tools like a private chat with the assistant: cwd is the team's pinned working folder (the brain if none), the MCP hub is attached at `full` level (`main.TEAM_WORK_MODE`), brain files go through `javis_vault`, built with `team_engine.build_tools` (providers other than Claude go through the background-job builders `aux_engine._build_*`, so Grok Build and Antigravity can also run Work turns). The outcome is read through `team_runner.ToolTurnOutcome` (tool calls are normal, the other error rules stay). Tool turns on the same brain run one after another (an in-process lock per brain). Chat, planning, synthesize, scan and learn turns stay text only. Test: `tests/python/test_team_work_tools.py`.
- **No resuming a member's thread:** each turn is a fresh call carrying the team block: a window of the 20 MOST RECENT messages of the team's own session (including the owner's old messages and every member's earlier replies, the agent's own included; messages after the agent's previous turn are labeled "new"), at most 8,000 characters; the decision log; the step input. Before review round 1 this block had only messages AFTER the agent's previous turn, so a follow-up question lost its facts (R2). Messages older than the window survive only through the decision log.
- **I/O on a side thread (R5):** every SQLite and file read and write of the runner and of the `/teams/*` routes goes through `run_io` (a side thread). If it is cancelled, even repeatedly, while the side thread is writing, it waits for the write to finish, runs the undo step (refund the turn just reserved, release the lock row just taken, return the job just claimed to the queue), and only then raises the cancel; the busy lock row is released only after the turn has settled. WS packets, the inbox, and cancelling asyncio tasks from the side thread are scheduled back onto the event loop.
- **No word-by-word streaming** (R2): the reply arrives when it is done.
- **No reactions yet** (T2), **no Full authority yet** (T3).
- **A private 1:1 chat with an agent does not take the busy lock:** an agent can run a team turn and a private chat turn at the same time.
- **Dismissing a proposal card** only hides it in the open tab.
- Real performance on the VPS is not measured; the 100 ms threshold in the test is a local indicator with a fake store slowed by 250 ms, not an SLA. To be measured in T4.

## Final review (a fresh reviewer, strongest model)

Verdict "ready after fixes": 0 critical bugs, 5 important bugs, all fixed, each with a test that was red first and then green.
- A leader assigning by display name ("Minh") was dropped and the job reported done before anyone worked: now it matches the name too, case-insensitively; if every assign command is broken, the job is blocked.
- Editing the request of a job with several @ redid only one person's part: now everyone assigned who is missing a result for the new version redoes it.
- Pause then immediately resume jammed the team; an unexpected error left a job hanging at `team_running`; the background loop ran recovery wrongly on a fresh install: all fixed.
- Extra fixes (raised by impact): a reply turn does not run when the team is paused, archiving cancels a hanging job, a step with no progress becomes a failed step so it can be re-run, the busy lock does not get stuck on cancel, the team session does not show in the main chat's search box.
- Left as is (recorded in the rulings log): lessons from a late turn are still written to the agent's memory; the daily cap can be exceeded by a few turns when many turns run at once; the busy lock is not renewed after 15 minutes; reason text from the server exists only in Vietnamese; building member names costs a file read each turn (to be measured in T4).

## Code review round 1 (14/10/2026, head `c729f464`)

The reviewer reproduced 2 P1 and 4 P2 with `exports/reviews/PR-628-T1-review-checks.py` (outside the repo, fake engine). On `c729f464` all 6 reproductions fire (default mode exit 0, `--expect-fixed` exit 1). Fixed, each with its own regression in the repo:

| Bug | Fix | Regression |
|---|---|---|
| R1 [P1] a failed or empty engine became Done | `TextOnlyOutcome` in the adapter; the turn is `error` and counted, the blocked job is `failed` | `test_team_t1_review.py` section R1: 9 bad outcomes through the real factory, a valid-final control, `resume_failed`, Re-run, chat turn |
| R2 [P2] the second turn lost context | Window of the 20 most recent messages of the team's own session | section R2: SOURCE and the earlier reply are in turn two, labels (you) and new, no mixing with other teams, 20-message cap, 8,000-character cap |
| R3 [P1] late output written to durable memory | The adapter only extracts, `commit` after the check inside `accept_lock`, identity pinning, `claim_commit` | section R3: correct-write control, rule downgraded to a lesson, leaving the team, cancel, editing the request, changing the leader, delete then recreate with the same slug, lock contention, repeated handling |
| R4 [P2] an engine not yet built still counted | The `engine_started` mark after building finishes | section R4: `_resonance_engine` returns None, engine not ready, build throws, cancel while building, restart |
| R5 [P2] blocking the event loop | `run_io` for the runner and every `/teams/*` route; reserve plus cap check in one transaction | section R5: slow store (reply turn, job, real route), two simultaneous turns with cap 1, eight threads with cap 3, repeated cancel while reserving, cancel when settling the turn, cancel when taking the lock, store error |
| R6 [P2] a live team pointing at a lost session | Restore all three stores, reconcile orphan teams at startup | `test_team_rollback.py` section R6: full round trip with a real team and real 0.109.0 code, orphan team, missing snapshot, failure midway |

Decisions changed from the earlier version: the context block carries history, not only new messages (R2); `JAVIS_RULE` in a team turn is still downgraded to a lesson but written only when the output is accepted (R3); `team.sqlite3` is no longer "left alone" on restore (R6). Out of scope: Full authority, tools, streaming, reactions (T2, T3).

## Code review round 2 (14/10/2026, head `280959a7`)

The six round 1 cases still pass. The reviewer reproduced 1 more P1 and 2 P2 with `exports/reviews/PR-628-T1-r2-race-checks.py` (fake engine, barrier with a deadline). Fixed:

| Bug | Fix | Regression (`test_team_t1_review.py`) |
|---|---|---|
| R7 [P1] a stale version's result settled Done for an edited request | `_apply_step` and `_job_tick` run inside `accept_lock` and re-check validity right before applying effects; once invalid, the message becomes evidence (`superseded`, applied=false) and takes the late-arrival branch. `team_finish(expected_rev=...)` is a CAS in the store. A job step's lesson is written in the apply phase, not the accept phase | section R7: plan with a direct answer, work step, synthesize (each case edits the request at the apply gate and then redoes on the new version), completion winning first so the edit is refused, cancel, removing a member, changing the leader at the apply gate, store CAS, no-edit control |
| R8 [P2] two wake-ups exceeded the pool cap | Computing slots, claiming the job and reserving (`_pool`) is one critical section in `_claim_batch` (`_pool_lock`, side thread); the slot is returned when the task finishes; the model runs outside the lock; a mid-way failure returns even the job that was creating its first step to the queue | section R8: four teams, cap 2, two dispatches through a barrier; sequential control; the lock is not held while the model runs; failure in the middle of claiming; repeated cancel while claiming |
| R9 [P2] a broken restore after a write left stores mixed | A store counts as "possibly touched" BEFORE writing; restore from the copy then re-check (row counts per table); a destination that did not exist is removed; if it cannot be restored, report `unrecoverable` with the copy | section R9: failure before and after writing each store, failure when removing the team store, a destination that did not exist, cannot restore, control |

## Upgrading, downgrading

- On the first run of 0.111.0 over an existing `kanban.sqlite3` and `conversations.db`, each store is snapshotted to `<name>.pre-0.111.0` with the SQLite backup before columns are added. A brand-new store is not snapshotted.
- **Downgrade to 0.109.0:** stop Jarvis 007, run `python tools/team_chat_restore_pre.py --yes`. The restore tool restores the WHOLE SET of three stores (review round 1, R6):
  1. Check the whole set first, writing nothing: every upgraded store must have a valid snapshot. A missing or broken snapshot stops it, touching no store.
  2. Copy every existing store (`team.sqlite3` included) to `<name>.post-0.111.0-<timestamp>`.
  3. Remove `team.sqlite3` from the running location: before 0.111.0 this store did not exist.
  4. Write the snapshots into the other two stores. If it fails midway, return every store already touched to the copy from step 2 and report the error, never success.
- **Lost from the running store / kept:** Kanban jobs, chat messages and teams created after the upgrade leave the running store; all three have a `.post-0.111.0-*` copy to read back. On upgrading again, no team points at a lost session, and the `.pre-0.111.0` snapshot is reused, not overwritten.
- **Orphan teams:** if the session store is rolled back to an old copy while `team.sqlite3` remains (the tool before the review, or a manual copy), on the next start the background loop archives the team, logs a `session_missing` event, and cancels open jobs; team data is kept for comparison. Sending a message to such a team returns a business error (TeamError), not a foreign key error.
- **Downgrade without restore:** old code never picks up team jobs, but the Work page shows the `team_*` rows with an unfamiliar status and `team:` sessions show like ordinary sessions.

## Checks

| Command | Result |
|---|---|
| `tests/python/test_team_identity.py` | A durable id does not turn on Resonance; a duplicate slug returns 409, the old file is unchanged |
| `tests/python/test_team_store.py` | 24 cases: team, members, leader, step CAS, turn ledger, busy lock |
| `tests/python/test_team_messages.py` | Sender, duplicate-send guard, paging, hidden from chat history |
| `tests/python/test_team_queue.py` | 33 cases: TC9, TC14 to TC18 (the A, C, B example), isolation from the Work board |
| `tests/python/test_team_runner.py` | 65 cases, fake engine: TC6 to TC13, TC17 to TC23, malformed JAVIS_TEAM block, cancel mid-turn |
| `tests/python/test_team_api.py` | 40 cases on the real app with a fake engine: routes, 409, proposals, decision log, delete an agent then recreate (TC5), archive |
| `tests/js/test_teams_ui.js` | 53 cases: list, messages, queue, composer, settings, wiring, CSS, i18n |
| `tests/python/test_team_rollback.py` | 31 cases with the real 0.109.0 code (`bfb1c29f`): snapshot, downgrade with and without restore, upgrade again; R6 with a real team, orphan team, missing snapshot, failure midway |
| `tests/python/test_team_t1_review.py` | 101 cases: review round 1 (R1 to R5, through the real factory `main._team_engine_for` with a fake engine) and round 2 (R7 to R9), with valid controls |
| `python tests/run.py --js` | 186/186 |

**UI smoke test** (sandbox on port 7788, state inside the worktree). The team's daily turn cap was set to 0 before sending anything, so no turn reached a real engine; the turn ledger had 0 rows at the end of the session. Screenshots are in `exports/reviews/team-t1-smoke/`, outside the repo.
- Create a team through the form; the leader and member count show at the top of the chat panel.
- A normal message: saved, shows "The team has used up its turns today", nobody replies.
- Typing "mi" for @ shows the suggestion Minh; picking it makes a card; turning on Assign job shows the suggestion "Create 1 job · assign to Minh · at the end of the queue (position 1)".
- A job hit the cap and went into "Waiting for you" with a reason and a Continue button.
- Pause the team, add B then C, press Prioritize on C: C moves to position 1 with a "Priority" label with a star icon and a Remove priority button.
- 375px: the list is the first page; the chat panel is full screen, the panel header has two rows; settings slide up with a solid background; no horizontal scroll; 44px buttons.
- The smoke test found and fixed: a hidden button still showing (`.ws-btn` overriding `hidden`), an empty settings column when no team is open, the chat header squeezed on phones, a transparent drawer, a back button narrower than 44px.
