# T4 adaptive team chat: long history, operations, rollback (0.170.0)

Design: [2026-10-15-team-adaptive-design.md](../superpowers/specs/2026-10-15-team-adaptive-design.md) sections 11, 12, 13. Stacked
on T2 (0.154.0) and T3 (0.156.0: part P pulse, part J judge, part L learning in the team; last T3 branch `054975b3`). Measurements:
[team-chat-t4-bench.md](team-chat-t4-bench.md). Acceptance matrix: [team-chat-acceptance-matrix.md](team-chat-acceptance-matrix.md).
Pilot package (not run yet): [team-chat-pilot-package.md](team-chat-pilot-package.md).

## 1. Long history in the right team

When a team session is longer than the window of the latest 20 messages, the "Tóm tắt phần cũ" block (summary of the older part, T4 0.124.0) gets an extra section **Always kept despite long history**
(`server/team_long_memory.py`, called from `team_runner._older_summary`). Built by machine, no model call, at most 3,000 characters:

| Item | Source | Query (once per turn, with a row ceiling) |
|---|---|---|
| Pinned decision ledger | already in the team block (`_context`), not repeated | `idx_messages_team_decision` (a new partial index), at most 20 |
| Open jobs: the original request (the part before the first edit), number of edits, status, block reason | `task_store.team_open_brief` | `idx_tasks_team_queue`, at most 9 |
| Contribution source of the latest result: who synthesized, whose input, the credit rate | `task_store.team_last_done`, `team_store.steps`, `pulse_contrib` (part P) | `idx_tasks_team_queue`; steps by `UNIQUE(task_id, seq)`; `pulse_contrib_result` (new), at most 8 |
| The owner's feedback not yet reviewed (`pending_review`, `reviewing`, `waiting_quota`), including older than 30 days; the agent's earlier message of this turn | `team_store.unconsumed_feedback` | `team_reactions_status` (new), at most 12 |

"Newest message of agent X" (marking the new message in the window) moves to the partial index `idx_messages_team_author`.

Details of the always-kept part:
- It is only built when the history is longer than the window (same condition as the older-part summary); in a short team the request and feedback are already
  in the window and in the "Phản hồi gần đây" block (recent feedback), so the prompt does not change.
- Feedback waiting for review that already shows in this turn's recent feedback is not repeated; a heading that hits the character ceiling with no
  lines left is dropped entirely; the block ends with the note "machine-extracted data, not a new command" (in Vietnamese in the prompt).
- Every extracted text is collapsed to one line (no way to inject a fake heading or title).
- A write on the read path: `pulse_contrib_result` is created (`CREATE INDEX IF NOT EXISTS`) on the process's first read of the contribution source
  (`main._team_contrib_reader`, a once-per-process flag), because the table belongs to part P and may not exist at startup.
  That first time there is one short DDL statement; later calls only read.
- `task_store.team_last_done` sorts a team's finished jobs by `updated_at` (a temporary sort tree): the ceiling is by the team's number of jobs,
  not the number of messages. If one team's job count reaches tens of thousands, add an index `(team_id, status, updated_at)`.

Checks: `tests/python/test_team_t4_long_history.py`. A team of 5,000 messages still has the pinned decisions from the start, the original request, blocked jobs,
the contribution source (with the rate), and feedback waiting for review that is 45 days old. The number of store calls per turn is counted with a wrapper: 60 messages and 5,000 messages
are equal, under 40. EXPLAIN QUERY PLAN of the six queries all use the right indexes. If the pulse store fails, only the credit rate is lost.

Private chat `agent:<slug>`: the feedback block exists since T2 (`feedback_projector.dm_feedback_block`, a query by
`dm_reactions_agent(agent_key, updated_at)` with a ceiling), and T4 does not repeat it. Scoped lessons `dm:<agent_key>` are part
L's job (`agent_lessons.for_prompt`, checked in `test_agent_lessons.py`: a private chat loads `dm:<agent_key>` and `*`, no team
lesson); T4 does not repeat it.

## 2. Operations (checked through the real host)

`tests/python/test_team_t4_ops.py`, `main.app` through TestClient, fake engine, real engine guard (`tests/python/_t4_host.py`
shares `install_guards` with the bench):

- **Multiple tabs:** resending the same nonce adds no log row; two real tabs registered in `ChatRuntime` (the real fan-out path) both
  RECEIVE the `team_message` packet carrying the new reaction, with the same content, even when a third tab has a dead socket.
- **Lost connection:** sending a broken WS packet does not break the operation; reloading shows the saved state and the outcome of the reply turn.
- **Restart:** reactions and pulse state survive reopening the store; building a NEW runner on a running job that has not
  reached the engine (it continues to completion with the fake engine) and on a job with a turn that did reach the engine (blocked as `interrupted`, the turn counted
  once); no busy lock left hanging.
- **Cancel:** a waiting job that is cancelled does not open a model turn; cancelling twice does not give a 500.
- **Retry:** a failed turn is recorded as `error`; Retry runs exactly one new turn, `done`.
- **Leaving the team:** someone who has left is no longer judged for new messages.
- **Changing the team lead:** a message without an @ is answered by the new team lead.
- **Turning Auto off/on:** off makes feedback `stored_only`; turning it back on does not replay.
- **Revoking Full authority:** the pulse scan turn can only propose, not queue jobs.
- **Store error while projecting the effect:** the reaction is still saved, the log row stays `pending`, and the next tick finishes projecting.
- **Clock skew:** pulse evaluation with a backward clock does not fail; with the runner's clock 2 days back, the "Phản hồi gần đây" block (recent feedback)
  still has the right row for that message.
- **A blocked team or sleeping agent does not take a slot:** a one-slot pool; the job of team A and then team B is blocked RIGHT INSIDE the runner's turn (the fake engine fails) and
  gives the slot back immediately; then team C is accepted and finishes even though C's agent is hibernating in team C;
  the pool is empty after the turn; the hibernation tick does not hold the busy lock.

## 3. Findings while measuring

Items 1, 2, 3 were fixed by the T3 branch (from `7e8b96f5`, last branch `054975b3`); before/after numbers are in [team-chat-t4-bench.md](team-chat-t4-bench.md). Kept for reference.

1. **The team judge batch (part J) reads and writes SQLite right on the event loop thread.** The bench's `--stall-watch` caught the loop thread
   held more than 50 ms at `agent_judge.judge_team_message` -> `agent_judge_store` (`get_decision`, `profile`, `get_offset`,
   `cases`, `add_decision`) and `agent_ledger.reserve/mark_engine`. In the judge-batch-only phase, the max event loop lag is about
   15 ms on this machine, but it grows with the number of members and disk slowness (VPS). Fix direction: run the batch's store work in a worker thread
   (`asyncio.to_thread`) as `team_runner` does (R5). This belongs to part J. **Fixed** in T3 (`server/io_offload.py`); after the fix,
   the judge-batch-only phase still sometimes holds the loop for about 70 ms on this machine.
2. **The pulse tick is heavy when many feedback items are waiting.** One tick costs 0.5 to 3.4 s (worker thread), and the max event loop lag in the
   tick-only phase is about 0.2 s, most likely from the projector's reconciliation thread contending for the GIL (about 4.7 ms per "Waiting for review" reaction,
   ceiling 200 rows per tick). While part L was not merged, those reactions were never served so the cost repeated every 30 seconds. It needs
   re-measuring with L merged and on the VPS. **Fixed** in T3 (batch projector, tick off the loop): the max lag in the tick-only phase went from
   217 ms to 39 ms; one projection with 1,125 waiting reactions is about 20 ms. VPS not measured.
3. **Part P's test assumed part J did not exist yet:** the case in `test_agent_pulse_host.py` "no agent_judge: say becomes silent
   (judge_unavailable)" went red once J was merged (it received `judge_error`). This is a T3 merge bug, not T4. **Gone** after the full T3 merge.
4. **Every `team_message` packet redraws the whole message frame of each tab** (`teams.js onTeamEvent -> drawMsgs`) and schedules a re-read of the
   list, queue and team after 300 ms. 20 reaction packets x 2 tabs x 200 messages: about 80 ms of string building under node. Acceptable at this
   size; if it needs to be faster, redraw only the changed message.

## 4. Rolling back (the whole chain)

T4 creates **no** store, table or column. It only adds four indexes (`CREATE INDEX IF NOT EXISTS`), which the old version ignores:
`team_reactions_status` (team.sqlite3), `idx_messages_team_author` and `idx_messages_team_decision` (conversations.db),
`pulse_contrib_result` (resonance.sqlite3, created the first time the contribution source is read). `tools/team_adaptive_restore_pre.py --to
0.170.0` says clearly there is nothing to restore and writes nothing (checked in `test_team_adaptive_restore.py`).

Run the tool while Jarvis 007 is OFF. Without `--yes` it only prints the plan. Every step keeps a copy `.post-<mark>-<time>`.

The chain was renumbered when merging with main: T1 shipped as 0.167.0, T2 0.168.0, T3 0.169.0, T4 0.170.0. The milestone names
of the restore tool and the snapshot suffixes keep the old internal names (`--to 0.154.0` is T2, `--to 0.156.0` is T3, files
`.pre-0.154.0`, `.pre-0.156.0`), because the code already wrote exactly those names to disk.

| Downgrade from | To | What to do | What is lost |
|---|---|---|---|
| 0.170.0 (T4) | 0.169.x (T3) | Just run the old version. | Nothing (the extra indexes are harmless). |
| 0.169.x (T3) | 0.168.x (T2) | Not required (the migration only adds; the old version ignores `agent_judge.sqlite3` and the new pulse tables). To go back exactly to before the upgrade: `python tools/team_adaptive_restore_pre.py --to 0.156.0 --state-dir <state> --yes` (removes `agent_judge.sqlite3`, restores `resonance.sqlite3` from `.pre-0.156.0` if present). | With the tool: judge history, pulse, signals, every resonance change after the upgrade. |
| 0.168.x (T2) | 0.167.x (T1) | Not required (as above). To go back exactly: `--to 0.154.0` (team.sqlite3, conversations.db, resonance.sqlite3 restored from `.pre-0.154.0`; removes the judge store if it was already at 0.156.0). | With the tool: every message, session, reaction, team, turn ledger, goal after the 0.154.0 upgrade. Kanban is unchanged. |
| 0.167.x (T1) | before team chat (0.140.0) | `tools/team_chat_restore_pre.py` (T1, see team-chat-t1.md). | Team chat. |

Known effects of a downgrade without restore: reactions by the team lead/members (`reactor = agent:...`) show as ordinary reactions
in versions before 0.154.0; judge decisions and the pulse do not show in versions before 0.156.0. No data is lost.

Check after downgrading: open the Teams page, a team with a long history loads its first page, sending a message with an @ gets an answer; `GET /health` returns 200.
