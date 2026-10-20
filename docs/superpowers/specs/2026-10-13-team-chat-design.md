# Multi-agent team chat (design)

**Status:** round 1 design. **The project owner settled D1 through D7 as proposed and approved implementation (13/10/2026)**, starting with T0 and then T1 ([plan](../plans/2026-10-13-team-chat-t0-t1.md)). No model has been called, no pilot has run, nothing is merged, and the VPS is untouched.

- **Base:** `main` `bfb1c29f9e87e8b43a0bf1a8a43d3535581047d6` (0.109.0). Resonance A1 0.87.0, A2 0.88.0, A3 0.89.0, A4 0.96.0 and A5 0.109.0 have shipped; the agent tag shipped in 0.100.0.
- **Branch:** `claude/team-chat-design`. No version number reserved yet: the number is reserved when T1 coding starts (section 19), per `docs/quy-uoc-dev.md`.
- **Inputs:**
  - The project owner's GOAL of 13/10/2026, in three parts: the team chat group; the team leader and Full access mode; six reactions.
  - [Code audit report](../../dev/team-chat-audit-2026-10-13.md).
  - [Agent roadmap](2026-10-08-resonance-agent-scope-roadmap.md), [A4 design](2026-10-10-resonance-a4-handoff-grants-design.md), [A5 design](2026-10-11-resonance-a5-maker-reviewer-design.md), [agent tags](../../dev/agent-tags.md).
- **Wireframes and diagrams:** [team-chat-wireframes.md](../../dev/team-chat-wireframes.md).
- **Evidence level:** code and docs reading only. Every "already exists" claim cites a file and function in the code audit report. A documentation test is not evidence that the product runs.

## 1. Goals and out of scope

### 1.1 Experience

You work with many agents in team chats, familiar from Zalo groups but living inside Jarvis 007:
- **Team list**: you can create many teams by job or topic. Each team has a name, description, members, history and its own jobs.
- **Members:** add an existing agent, or create a new agent and put it in the team. One agent can be in many teams.
- **Team leader:** each team has one team leader, an agent you choose.
  - When you send a general request, the team leader coordinates, assigns and summarizes.
  - You can still @ an agent to hand out work or talk to it directly.
- **Coordination:** agents exchange inputs and post results into the right team.
- **Team settings:** current job, queue and a **Prioritize** button.
- **Partners screen:** each assistant shows its status and a Resonance switch.
- **Feedback:** every agent reply has the full set of six reactions: 👍 Like, ❤️ Love, 😂 Haha, 😮 Wow, 😢 Sad, 😡 Angry.
- **Two team leader modes:** Limited access and Full access.

### 1.2 Distinctions, not merges

| Concept | What it is | Relation to the team chat |
|---|---|---|
| Tag (0.100.0) | A label that classifies agents | Only used for filtering when picking members. Not a team, adds no members, does not choose the team leader, grants no permission |
| Chatbot Zalo/Telegram group | A bot talking to outside people on an outside channel | Unrelated. The team chat is not connected to Zalo in this version |
| Workflow | A pipeline of sequential steps | A team job can use a workflow as its body; it does not replace the team |
| A5 maker/reviewer pair | One agent makes, one agent reviews, for each **Resonance goal** | An agent in a team can still have a Resonance goal with an A5 pair. The A5 pair is not a team structure; a team is not limited to two agents |
| Resonance goal | A long-term job an agent pursues on its own | A message in the team does not create a goal by itself. A goal created during a team turn reports back to that same team (section 10.3) |

### 1.3 Out of scope for the first version

- multiple accounts, organization-level permissions;
- voice or video calls;
- integration with real Zalo groups;
- a separate engine per agent for every kind of turn (section 12.1);
- surfacing background-job usage on the shared usage screen (a separate item, recorded after A5);
- a request source pinned by the host for the A5 reviewer (a separate item).

## 2. Current state in brief

Details and code references are in the [code audit report](../../dev/team-chat-audit-2026-10-13.md).

**Does not exist yet:**
- teams and members;
- a sender on messages;
- @mention;
- a per-team job queue;
- a per-agent busy lock;
- a per-job turn ledger;
- the six reactions;
- a Resonance switch on the assistant row.

**Already exists and is reused:**

| Need | Reuse | What changes |
|---|---|---|
| Team conversation | A session (`sessions`) with a new channel `team:<team_id>`; pagination `get_messages_page` | Add a sender column to `messages` |
| Send, stream, reconnect | `/ws`, `ChatRuntime`, `push_to_chat` | The packet carries `team_id`, recipient, `client_msg_id` |
| Agent prompt | `_agent_sysprompt`, agent memory, `_ket_luot_agent` | Add a team context block |
| Durable jobs, lease, recovery, cancel, report back to chat | The Kanban `tasks` table, `claim`, `heartbeat`, `reclaim_stale`, `_report` | A separate `team` lane (section 5.4) |
| Durable identity | `resonance_agents.agent_key` | Register a key for every member, with no need to enable Resonance |
| Resonance switch | `POST /resonance/agents/toggle` and the A1 contract | Moved onto the assistant row; the Settings page keeps only a summary |
| A4, A5 gates | Unchanged | No change |

## 3. Three architecture options

| | A. Team on a session + `team` lane in Kanban (**chosen**) | B. Build teams on Resonance | C. A standalone team system |
|---|---|---|---|
| Conversation | `team:` channel session | `team:` channel session | Its own message store |
| Team jobs | Rows in the Kanban `tasks` table, `team` lane, own statuses | Each job is a goal | Its own jobs table |
| Who runs jobs | Team runner, the agent's chat turn (with tools) | Resonance's text-only turn | Its own runner |
| Pros | Reuses lease, recovery, cancel, report back to chat, the Work page. One place for all background work. Does not touch the A1 to A5 contracts | Already has the turn ledger, quota, review | Free design |
| Cons | The lane must be separate so old Kanban code does not pick jobs up by mistake; adds a few columns | A goal is a long-term text-only job with a fixed ceiling and a wake schedule; turning every message into a goal contradicts "ordinary messages do not create goals"; changes a shipped contract | Adds a second work-assignment system competing with Kanban: exactly what the GOAL forbids |

**Choose A**, for three reasons:
- A team job is a job the user hands out, run once, needing order and visibility. A Kanban row already has durable storage, locking and recovery.
- Resonance keeps its role for long-term goals.
- It does not create a third system.

## 4. Invariants

1. **The host manages identity.** Team ids, members, agents, turns, messages and jobs are issued by the host. Never trust an id the model declares itself.
2. **Ordinary messages do not create jobs or goals.** Only an authorized action creates a job (sections 7.1, 7.3). An agent's message does not wake another agent by itself.
3. **A model call is counted exactly once.**
   - Reserve a slot in the turn ledger before building the engine.
   - An error before the engine-call mark refunds the turn.
   - Resending a request, reconnecting or restarting does not call again.
4. **A result is applied only while it is still correct** for the job, revision, assignee and membership. If any one is wrong, the result is saved as "arrived late, not applied".
5. **The team owner's command always wins:** stop, cancel, revoke, remove a member. Full access cannot override the owner's command.
6. **Each team belongs to exactly one brain.** No cross-brain access is opened. One team's context does not enter another team's turn or a private chat.
7. **The A1 to A5 contracts stay unchanged.** Moving the place in the UI does not change the policy. No message widens permissions, bypasses the A4 gate or skips the A5 review requirement.
8. **"Unlimited" is an explicit state**, not faked with a big number. Any ceiling that still applies (technical, provider, server) must be shown.

## 5. Data model

### 5.1 Agent identity: one shared ledger

An agent's durable key reuses `resonance_agents` (same `resonance.sqlite3` file).
- Add a function `agent_register(p, slug)`: creates a key with `enabled=0` if there is no live row yet. The owner calls it, or the host calls it when adding a member.
- The meaning of the `enabled` column does not change: it is still only the Resonance switch.
- The table name stays so that no migration is needed. Docs call it the "agent identity ledger".

Consequences:
- **Rename** only changes `name` in the file; the key and slug stay, so membership stays.
- **Deleting an agent** calls `agent_retire` as today: the key becomes `retired`, the member row shows "deleted", and the agent's jobs go into a blocked state (section 6.4).
- **Recreating the same slug** produces a new key that is not a member and inherits no jobs or permissions.
- **Old hole:** creating an agent with a duplicate name silently overwrites the old file (audit report section 2). T1 fixes it: creating a new agent whose slug already exists makes the server return 409, with a suggestion for another slug. No overwrite.

### 5.2 New team store: `team.sqlite3`

A new file in `JAVIS_STATE_DIR`, a new module `server/team_store.py`. Old code ignores this file, so downgrading is safe (section 18).

| Table | Main columns | Notes |
|---|---|---|
| `teams` | `team_id` (`tm_`+hex), `brain_id`, `name`, `description`, `session_id` (the `team:` session), `leader_key` (nullable), `leader_mode` (`limited`/`full`), `status` (`active`/`paused`/`archived`), `queue_version`, `caps_json`, `created_at`, `updated_at` | `queue_version` increases on every queue change, used for CAS |
| `team_members` | `team_id`, `agent_key`, `slug_at_join`, `role` (`member`/`leader`), `status` (`active`/`removed`/`agent_gone`), `managed_by_team` (0/1), `joined_at`, `left_at` | PK (`team_id`, `agent_key`). One agent in many teams |
| `team_events` | `id`, `team_id`, `kind`, `by` (`owner`/`leader:<key>`), `before_json`, `after_json`, `created_at` | Log: members, team leader, permission mode, ceilings, priority, cancel |
| `team_steps` | `step_id`, `task_id`, `team_id`, `seq`, `kind` (`plan`/`work`/`help`/`synthesize`/`reply`), `agent_key`, `job_revision`, `brief`, `input_refs_json`, `status`, `parent_step`, `result_msg_id`, `applied` (0/1), `created_at`, `updated_at` | Internal steps of one team job. **Not team-level jobs** |
| `team_turns` | `turn_id`, `team_id`, `task_id` (nullable for chat turns), `step_id`, `agent_key`, `role` (`leader_reply`/`member_reply`/`plan`/`work`/`help`/`synthesize`), `engine`, `model`, `status` (`reserved`/`running`/`ok`/`error`/`refunded`/`interrupted`), `engine_at`, `tokens_in`, `tokens_out`, `cost_usd`, `created_at`, `settled_at` | Turn ledger. One row per model call |
| `agent_busy` | `agent_key` PK, `team_id`, `turn_id`, `lease_until` | A system-wide per-agent busy lock (section 8.7) |
| `team_reactions` | `id`, `team_id`, `session_id`, `message_id`, `responder`, `agent_key`, `task_id`, `content_sha`, `value`, `reason`, `comment`, `seq`, `created_at`, `updated_at` | UNIQUE (`session_id`, `message_id`, `responder`) |
| `team_reaction_log` | `id`, `reaction_id`, `value`, `reason`, `comment`, `nonce`, `created_at` | Append-only. UNIQUE (`reaction_id`, `nonce`) |
| `team_authority` | `team_id`, `seq`, `mode`, `grant_json`, `by`, `created_at`, `revoked_at` | History of Full access grants and revocations (section 13) |

### 5.3 New columns on `messages` in `sessions.db`

All added columns allow null, and old code ignores them:

| Column | Meaning |
|---|---|
| `author_kind` | `owner` / `agent` / `system` |
| `author_ref` | `agent_key` when `author_kind=agent`, empty otherwise |
| `client_msg_id` | Message id generated by the client; UNIQUE (`session_id`, `client_msg_id`) when not null |
| `reply_to` | Id of the message being replied to |
| `task_id` | The related team job, nullable |
| `step_id` | The related step, nullable |
| `meta_json` | Validated mentions, the "arrived late" flag, result status |

- Old messages with no author display as they do today.
- In T1 only `team:` channel sessions write these columns. Ordinary chat is unchanged.

### 5.4 New columns on Kanban `tasks` (the `team` lane)

| Column | Meaning |
|---|---|
| `lane` | `''` (old Kanban) or `team` |
| `team_id` | The team that owns the job |
| `team_seq` | Sequence number added to the team queue, increasing |
| `team_prio` | null = normal; a number = position in the priority lane |
| `team_rev` | Revision of the request, increases when the team owner edits the request |
| `assignee_key` | The agent assigned directly (null if assigned generally to the team leader) |
| `coordinator_key` | The team leader coordinating, pinned at start, changed together with an event |
| `source_ref` | `msg:<session_id>:<message_id>` of the message that assigned the job |

- **Statuses of the `team` lane** use their own values: `team_queued`, `team_running`, `team_blocked`, then `done` / `cancelled` when finished.
- `next_candidate`, `reclaim_stale`, `/kanban/run` and `/kanban/nudge` only work with `triage`/`ready`/`running`. So Kanban code (including the old version after a downgrade) never picks up a team job.
- **Idempotency key** = `source_ref`.
- **Title-based merging is disabled for the `team` lane:** two different jobs with the same name are still two jobs.

## 6. Roles and permissions

### 6.1 Three roles

| Role | Who | Allowed to |
|---|---|---|
| Team owner | The user (the dashboard owner) | Everything: create, edit, archive teams; create agents; add and remove members; choose and change the team leader; change the permission mode; prioritize, cancel, stop; set ceilings |
| Team leader | A member agent chosen by the owner | Limited access: coordinate within the assigned job. Full access: additionally as in section 13 |
| Member | An agent in the team | Reply when called; do an assigned step; ask for help within the ceiling; submit results |

- The first version has no multiple accounts: "team owner" is the owner logged in to the dashboard.
- Every team management route goes through the auth and CSRF layer like the existing owner routes.
- An agent acts only through the `javis_team` tool (section 15.2), with identity taken from `turn_context`, not from a model parameter.

### 6.2 Permission matrix

| Action | Team owner | Team leader (limited) | Team leader (Full access) | Member |
|---|---|---|---|---|
| Create a team, edit its name and description | Yes | No | No | No |
| Create a new agent | Yes (through the existing `POST /agents`) | No | Yes, the agent becomes "managed by the team" | No |
| Add and remove members | Yes | Suggests (owner taps) | Yes | No |
| Choose or change the team leader; change the permission mode | Yes | No | No (cannot raise itself) | No |
| Open a team job | Yes | Suggests (owner taps) | Yes, within the assigned scope | No |
| Assign a step in a running job | n/a | Yes | Yes | No |
| Ask another member for help | n/a | Yes | Yes | Yes, within the ceiling |
| Prioritize, un-prioritize a waiting job | Yes | No | Yes | No |
| Interrupt a running job | Yes | No | Only when the owner turns on the separate permission "Can interrupt jobs" | No |
| Cancel a job | Yes | No | Yes, for waiting jobs; for running jobs it needs the "Can interrupt jobs" permission | No |
| Turn Resonance on and off | Yes (any agent) | No | Only agents managed by the team (section 13.3) | No |
| Change ceilings | Yes | No | Within the level the owner allows (section 13.2) | No |
| Approve an A4 write scope | Yes (on the card) | No | Only inside the team folder if the owner chooses so (D4) | No |

### 6.3 Changing or removing the team leader mid-run

- **Pinning:** the job's `coordinator_key` is pinned at the start.
- **When the owner changes the team leader:**
  - The old team leader's running turn is allowed to finish; its result is saved but **not applied** as coordination (`applied=0`, labeled "team leader changed").
  - At the next coordination point, the job moves to the new team leader, with a `coordinator_changed` event.
- **When the owner removes the team leader without choosing a replacement:**
  - A running job that needs coordination goes to `team_blocked` with reason `no_leader`.
  - The team shows a banner "The team has no team leader".
  - Jobs @-addressed directly still run.
  - New general jobs still enter the queue but do not start.
  - Coordination is never lost silently.
- **When the team leader is deleted from Jarvis 007:** handled like removing the team leader.

### 6.4 Removing a member who has work

- **A step that has not reached the engine-call mark:** cancel and refund the turn.
- **A step that already called the engine:** runs to the end, the result is saved with `applied=0` and the label "member left the team".
- The job goes back to the coordination point so the team leader can reassign.
- If the job was assigned directly to that person, the job goes to `team_blocked` with reason `assignee_removed`; the owner chooses to reassign or cancel.
- Removing from a team does not delete the agent from Jarvis 007 or from other teams. The agent's memory stays.

## 7. Chat and coordination flows

### 7.1 Two kinds of owner message

The composer has an **"Assign work"** switch, off by default.

| | Chat (default) | Assign work |
|---|---|---|
| Creates a team job | No | Yes, one job |
| Enters the queue | No | Yes |
| Model turn | A short reply turn (section 7.2) | Per job |

The team leader can **suggest** turning a discussion into a job, with `javis_team op=propose_job`:
- Limited access: the suggestion appears as a card "The team leader suggests a job: ..." with two buttons, Create job and Skip. Until tapped, no job exists.
- Full access: the team leader opens the job directly, within the assigned scope. The card still shows so the owner can see it and cancel.

### 7.2 Routing chat messages

An @mention is a structured list produced by the composer when picking from suggestions: `mentions=[agent_key...]`. The server checks each key against the list of active members. Text "@name" typed by hand without picking from suggestions is just text.

| Message | Who replies | Number of turns |
|---|---|---|
| No @ | The team leader (D1). A team with no team leader: no turn, shows "The team has no team leader; @ a member to ask directly" | 1 |
| One @X | Only X; the team leader is not called | 1 |
| Several @ (at most 3, adjustable) | Each person in @ order; later ones see earlier answers within the same question | Equal to the number of valid @ |
| More @ than allowed | Sending is refused, stating the ceiling | 0 |
| An @ that is no longer valid (left, deleted, `missing`) | That person is skipped, shows "X is no longer in the team"; valid people still reply | Equal to the number of valid @ |

- **An agent's message wakes nobody.** The text "@Y" in an agent's reply is just text. An agent that wants help from another must call `javis_team op=request_help` inside a running job (section 7.4).
- A chat reply turn runs as soon as the agent is free. It does not go through the team job queue, but it must wait for the agent's busy lock (section 8.7).
- A chat reply turn cannot open a job or ask others for help. It only replies, or suggests a job (section 7.1).

### 7.3 Assigning work

| "Assign work" message | The job created |
|---|---|
| No @ | General assignment: `assignee_key` null, `coordinator_key` = team leader. Starts with the team leader's `plan` step |
| @X | Direct assignment: `assignee_key` = X, `coordinator_key` = team leader (follow-up only). Starts with X's `work` step; the team leader does not redo X's part |
| Several @ | One job, the list of workers is stored in `metadata.assignees`; the team leader summarizes if there is more than one person |

- **No duplicate jobs:** key = `source_ref`. Resending the same `client_msg_id` returns the old message and the old job.
- **Example of flow B (general assignment):**
  1. The owner sends "Assign work: draft the launch plan".
  2. The job goes into the queue as `team_queued`.
  3. When its turn comes, the team leader's `plan` step calls `javis_team op=assign` for members 1 and 2, each with a brief and inputs.
  4. The host writes two `work` steps.
  5. Each step runs (sequentially by default); results are posted into the team with the member as author and a job label.
  6. The team leader's `synthesize` step posts the summary; the job is `done`.

### 7.4 Asking for help (flow D)

1. During a `work` step, agent A calls `javis_team op=request_help(B, question, inputs)`.
2. The host writes a `help` step for B, with `parent_step` being A's step. A's step ends in a waiting state.
3. B's step runs and the answer is saved.
4. The host creates A's next turn with B's answer as input. A continues.

**Loop-prevention ceilings (defaults, adjustable in section 12.3):**
- help depth: 2 (A asks B, B asks C; C does not ask further);
- **A asks B and then B asks A back in the same job: blocked**, with the note "no asking back";
- steps per job: 8;
- model turns per job: 12;
- **no progress:** two consecutive turns of the same step with no new result (same `content_sha`) stop that step. The job goes to `team_blocked` with reason `no_progress`.

### 7.5 The same agent in two teams (flow E)

Each (team, agent) pair has its own **member thread**: a hidden session on channel `teammate:<team_id>:<agent_key>`, keeping `cli_session_id` and `codex_thread_id` for resume.

- The `team:` session shows the shared history, only on the Teams page. The member thread only holds the engine thread.
- `list_sessions` hides both the `team:` and `teammate:` prefixes, as it already hides `agent:`, `workflow:`, `coding:`, `bot:`. These two kinds of session do not appear in the main chat's history list.
- A turn in team X receives only team X's context (section 11.2).
- Results carry that turn's `team_id` and `task_id`, so they always post back to the right team.

### 7.6 The owner interrupts, edits or cancels (flow F)

While the team is running a job, the composer shows "Working: <job summary>" with two buttons.

**"Edit request":**
- The owner enters the edit; the job's `team_rev` increases.
- Steps that have not started use the new revision.
- A running step runs to the end, its result carries the old revision: it is saved and shown but `applied=0`, labeled "per the old request".
- At the next coordination point, the team leader (or the directly assigned person) re-plans per the new revision.

**"Cancel job":**
- Cancels running turns (`cancel_all` by the turn's tag). A step that has not reached the engine-call mark refunds its turn.
- The job becomes `cancelled`. A result arriving later is saved with the label "arrived after cancel, not applied".

A chat message interjected during a run follows section 7.2. If the @-addressed person is busy in a job, the reply waits for the busy lock and shows "X is working on '<summary>', will reply later".

### 7.7 Linking messages, jobs and products

- Each job has a `source_ref` pointing back to the assigning message.
- Each step has `input_refs` (message ids and earlier step result ids) and `result_msg_id`.
- Each agent message within a job carries `task_id`, `step_id` and `reply_to`.
- Product files (if any, through A4 or a write tool) record the path and `sha256` in the `meta_json` of the result message.

UI:
- filter the chat by one job;
- tap the job label on a message to open the job details;
- the job details list the source message, the steps, the exchanges and the products.

Many jobs in the same team do not get mixed up because every link goes by id, not by position in the chat.

## 8. Queue and the Prioritize button

### 8.1 Unit and statuses

- **The queueing unit is the team-level job** (one `tasks` row in the `team` lane). Internal steps (`team_steps`) are not team-level jobs and do not appear in the queue.
- **Each team runs at most one job at a time.** Full access can change the level to parallel (section 13.2).

| Status | Meaning | Holds the team's run slot? |
|---|---|---|
| `team_queued` | Waiting | No |
| `team_running` | Working | Yes |
| `team_blocked` | Blocked, reasons: `waiting_user`, `failed`, `no_leader`, `assignee_removed`, `interrupted`, `no_progress`, `cap_reached`, `agent_busy_long` | **No:** the queue moves on |
| `done` / `cancelled` | History | No |

### 8.2 Order

The run order of waiting jobs in a team:

```
ORDER BY (team_prio IS NULL), team_prio, team_seq
```

- `team_seq` increases with the time of joining the queue.
- `team_prio` = null for normal jobs. Tapping Prioritize sets `team_prio = (max team_prio of the team) + 1`, so prioritized jobs run in the **order they were prioritized**, and the whole priority group stands before every normal job.
- **Tapping Prioritize again** on an already prioritized job: nothing changes, it returns the current position. There is no "push to the front of the priority group" in the first version.
- **Un-prioritize:** sets `team_prio = null`. The job returns to its position by its original `team_seq`.
- **Prioritizing does not interrupt a running job,** does not duplicate a job, does not raise a ceiling, does not call a model.

**Mandatory example.** A is running; B and C are waiting (B's `team_seq` is smaller than C's). The owner taps Prioritize on C:
- C gets `team_prio = 1`; the waiting order becomes C, B.
- A keeps running, not interrupted.
- When A finishes, C runs, then B.
- A does not run again; C does not cut in on A.

### 8.3 Who runs next

The new team dispatcher, `team_runner.dispatch`, runs in the Kanban 5-second loop and is also called on events. For each `active` team with no `team_running` job (or with a free parallel slot):
- take the job at the head of the queue;
- claim the job in one `BEGIN IMMEDIATE` transaction: check that no other job is running in the team, check that `queue_version` has not changed, set `team_running`, write `task_runs`.

A team job **does not depend on the "AI self-driving" switch** of the Kanban board: a team job is a job the owner explicitly handed out. The team's own switch is Pause team (`teams.status=paused`).

**Run pool:**
- team jobs use their own pool `team_max_parallel` (default 2 teams at once on the whole machine), and do not take Kanban's slots;
- chat turns do not enter this pool, they only wait for the agent's busy lock.

### 8.4 Blocked, errors, waiting for the user

- **A blocked job leaves the run slot**, and the queue moves on. A team is never stuck because of one job waiting forever.
- **A blocked job shows in the "Blocked/waiting for you" section**, with a reason in words and fitting buttons: Reply, Rerun step, Reassign, Cancel.
- **A badge with the number of jobs waiting for you** shows on the team row in the team list. Each time a job is blocked, one message goes to the inbox (the bell).
- **When unblocked** (the owner replies, reruns), the job returns to `team_queued` with its old `team_seq` and `team_prio`. It still stands in its old place, usually the head of the queue because it joined early.
- **Reminder:** a job waiting on the owner for more than 24 hours gets one reminder message (no model call). It is not cancelled automatically.

### 8.5 Two tabs change at once, the dispatcher just claimed a job

- Every queue operation (prioritize, un-prioritize, cancel a waiting job) sends `expected_queue_version`.
- The server uses CAS in the same transaction as the claim step. A wrong version returns 409 with the new queue; the UI redraws from the real state and says "The queue just changed".
- If the dispatcher claimed B right before the Prioritize C command was written, B is the running job and C is at the head of the waiting queue. The UI shows exactly that. There is no state in which two jobs run in the same team at once.

### 8.6 Restart

| At restart | After starting again |
|---|---|
| A `team_running` job whose step has not reached the engine-call mark | The step goes back to waiting, the turn is refunded; the job continues at that step |
| A step that called the engine but did not finish | The step becomes `interrupted`, the turn is counted once; the job goes to `team_blocked` with reason `interrupted`, button "Rerun step". **It does not rerun by itself**, to avoid paying twice |
| Waiting jobs | Keep their order |

- The queue and the order are stored in `kanban.sqlite3`, so they survive F5, reconnects and restarts.
- Kanban's 90-second lease is used for `team_running` jobs. A separate reclaim function `team_reclaim` handles things as in the table above.

### 8.7 The same agent busy in many teams

- **Per-agent busy lock** (`agent_busy`, default one turn per agent at a time on the whole machine, D3).
  - Reason: avoid two turns writing the agent's `MEMORY.md` at once, and avoid mixing threads.
  - The lock has a lease, with a renewal heartbeat like Kanban.
- When a job in team X needs an agent that is busy in team Y:
  - the step in X waits for the lock, without losing its place in the job;
  - team X's UI shows "<Name> is working in team Y";
  - the lock is released in request order (FIFO by request time), so no team is forgotten.
- After waiting more than 30 minutes the job goes to `team_blocked` with reason `agent_busy_long`, so the owner sees it and decides.
- A private 1:1 chat with the agent and the agent's Resonance goals **do not** take this lock in T1, because they have their own mechanisms. The docs state this is a limitation: an agent can still run a team turn and a private chat turn at the same time.

## 9. A member's turn

### 9.1 Run path

1. **Reserve:**
   - write `team_turns` (`reserved`);
   - take the `agent_busy` lock;
   - check the ceilings of the job and of the team;
   - check that the member is still `active` and the job is still at the right revision.
2. **Build the engine:** use the agent's chat path as today (`_chat_provider_for_session` with the member thread). Model per section 12.1.
3. **Prompt:**
   - the agent's system prompt (`_agent_sysprompt`: role, memory, the owner's standing rules, lessons);
   - the team block (section 11.2);
   - the feedback block (section 14.4).
4. **Engine-call mark:** write `engine_at` right before the call. An error before the mark refunds the turn (`refunded`).
5. **Tools:**
   - the agent's toolset as in private chat, plus `javis_team`;
   - `javis_task` is hidden in team turns, because assigning background work inside a team goes through `javis_team`, in one place;
   - `javis_goal` exists only when the agent has Resonance on.
6. **Finish:**
   - re-check the member, the revision, that the job is not cancelled, that the team leader has not changed (for a coordination turn);
   - if all conditions hold, post the message into the `team:` session with the agent as author, `applied=1`;
   - if not, post it with the late label, `applied=0`;
   - record tokens and cost; release the lock;
   - `_ket_luot_agent` handles `JAVIS_LESSON` / `JAVIS_RULE` as today: a rule is only written when the owner themselves said it in that turn.

### 9.2 Readable results

Each agent message within a job shows:
- the agent's name and picture;
- the job label (tappable);
- the role in the job (Planning, Working, Helping, Summary);
- the status (Working, Done, Error, Late, Per old request).

The final summary carries the label "Job result".

## 10. The Resonance switch on each assistant

### 10.1 Location

- **Each assistant row in the left column of the Partners page** (`workspace.js` `mucHtml`):
  - the text "Resonance: On" or "Resonance: Off", and a switch with a label for screen readers (not relying on color alone);
  - a `missing` agent shows "Needs confirmation" and a link that opens the right column, where the two confirm buttons are as today.
- `GET /agents?prompt=0` also returns `resonance: {enabled, status, registered}`, joined with the identity ledger in one read. No extra request per row.
- **The right column** (the agent's Resonance panel): keeps the Reviewer field, goals, lessons and the confirm buttons. The switch in this panel is **removed**, so there are not two switches for the same agent on the same screen.
- **Settings page:**
  - remove the per-agent switch list;
  - replace it with one summary line "N assistants have Resonance on · Manage on the Partners page", with a link;
  - keep the existing shared tools: orphan goals, assigning ownerless goals, the note about the old brain switch.
- **Member list in the team settings:** shows the same status. Changing it here uses **exactly the same route** `POST /resonance/agents/toggle`, with the same owner permission.

### 10.2 Behavior

- **Send and wait:** send `{slug, enabled}`; the switch stays in a "saving" state until the server answers.
  - Show success only when the server confirms.
  - On an error or 409, reload `GET /resonance/agents` and redraw from the real state (fixes the current bug: a 409 only shows text).
- **Two-tab sync:**
  - after every change, fire the event `javis:resonance-agents-changed` within the tab;
  - the server broadcasts a packet `{"type":"resonance_agents"}` over WebSocket so other tabs reload.
- **Turning off an agent that has work:** the confirmation box states the real impact:
  - the number of open Resonance goals that will stop at their next step (A1 contract);
  - the teams the agent takes part in;
  - "team jobs are not stopped by this switch; to stop team jobs, cancel them in the team settings".
- **Keep the A1 `missing` flow, identity confirmation and "needs a new session".** The switch on the row does not send `session_id`. When the server returns a state that needs a new session, the right column shows the button as today.
- **An agent never turns on Resonance by itself.** Only under Full access, the team leader can turn a team-managed agent on or off, through the same store function with `by=leader:<key>` and logging an event (section 13.3). Other agents can still only be changed by the owner.

### 10.3 What an agent without Resonance can do

| Activity | Off | On |
|---|---|---|
| Chat in the team, reply when @-mentioned | Yes | Yes |
| Do a step in a team job (the agent's chat turn with tools) | Yes | Yes |
| Be the team leader | Yes | Yes |
| Create and pursue Resonance goals (`javis_goal`), hand over products per A4 | No | Yes; the report of a goal created in a team turn goes back to that same `team:` session |
| Be an A5 reviewer | No | Yes |

Membership does **not** grant Resonance permission by itself.

## 11. Identity, permissions and context

### 11.1 Team and brain

- Each team belongs to exactly one brain (`teams.brain_id`). Members must be agents of that brain.
- Changing the brain on the dashboard changes the team list with it.
- The agent's file read and write permissions in a team turn are **exactly the same** as in private chat: membership adds no file permission.

### 11.2 The team context block

The team block is built by code, with no model call:
- the team's name and description;
- the member list (name, role, whether it is the team leader);
- the agent's own role in this turn;
- the current job: summary, revision, step, brief, inputs (per `input_refs`);
- **new messages in the team since this agent's own previous turn in this team**, at most 20 messages and 8,000 characters. The agent's resume thread keeps anything older.
- **The team's "decision log":** messages the owner pinned as decisions (the "Pin as decision" button), at most 20 lines. A long history still keeps the request and the decisions without resending everything.

The team block does **not** include:
- the owner's private conversations;
- data of other teams;
- `CLAUDE.md` and the owner's memory (same as today's agent chat);
- configuration secrets.

**Shared memory and private memory:**
- **Shared:** `memory/agents/<slug>/MEMORY.md` belongs to the agent and is used in every team. A lesson self-learned in team X may affect team Y; the design accepts this and says so.
- **Private:** each team's context lives in the `team:` session and the member thread.

### 11.3 Who is responsible, where results go

| Question | Answer |
|---|---|
| Who is ultimately responsible for a team job | The coordinating team leader (`coordinator_key`) for general jobs; the assignee for jobs addressed directly with @. The team owner decides acceptance |
| Who is ultimately responsible for a goal | As in A1: the agent that owns the goal. A goal created in a team turn has its `origin` set to that `team:` session, so its report goes back to the right team |
| Where results and notifications go | The team's `team:` session; a blocked job also sends a message to the inbox |

### 11.4 Stop, cancel, turn off, revoke

| Owner command | Effect |
|---|---|
| Pause team | No new jobs or new chat turns start. Running turns run to the end, and their results are applied if still correct. A running job keeps `team_running` and stops at the next coordination point |
| Cancel job | Section 7.6 |
| Remove a member, change the team leader | Sections 6.3, 6.4 |
| Turn off an agent's Resonance | Only affects goals (A1 contract). Team jobs do not change |
| Revoke Full access | Section 13.5 |
| Delete an agent | The key becomes `retired`; the member becomes `agent_gone`; handled like removing a member |
| Archive the team | Like pause, plus cancel every waiting job; history is kept and readable |

**Parts already committed to write or post** follow the A4 contract: a version already committed to post still completes; a version not yet committed expires.

## 12. Model, quota and recovery

### 12.1 Model for each kind of turn

| Turn | Model |
|---|---|
| Chat, planning, working, helping and summary turns in a team | The agent's chat path: use the agent's `model` + `model_provider` when both are present; otherwise the main model |
| Resonance goals (including the A5 pair) | The shared background-work model, text-only, as in A1 to A5. Unchanged |
| Ordinary Kanban jobs | As today (aux) |

In a team turn, the agent's model is read from the agent file **on every turn**, not pinned per session. Reason: the member thread is a hidden session, and a snapshot taken when the session was created would go stale.

**Do not promise too much:**
- If the agent's provider is missing a key, the turn uses the main model and says so in the turn ledger.
- Grok and Antigravity do not record usage today (audit report section 4); the team turn ledger still counts turns, but leaves tokens empty.

### 12.2 Counting turns

- **One `team_turns` row per model call**, with role (`role`), job, step, agent, engine, model, tokens, cost.
- **Before the `engine_at` mark:** an error means `refunded`, not counted.
- **After the mark:** counted, including errors, timeouts or cancels.
- **Restart midway:** `interrupted`, counted once, not rerun automatically.
- **Team settings, Turns tab:** turns and tokens by job, by agent, by day.
- The shared usage screen does not yet receive these turns (a separate item is recorded).

### 12.3 Default ceilings (Limited access)

| Ceiling | Default | Unit |
|---|---|---|
| Model turns per job | 12 | job |
| Steps per job | 8 | job |
| Help depth | 2 | job |
| Asking back within a job | 0 (blocked) | job |
| Consecutive no-progress turns | 2 | step |
| @ per message | 3 | message |
| Model turns per team per day | 100 | team |
| Running jobs per team | 1 | team |
| Teams running jobs at once on the whole machine | 2 | machine |
| Simultaneous turns of one agent | 1 | agent |
| Wait for the busy lock before reporting blocked | 30 minutes | job |

- **The per-team daily turn ceiling** counts every turn of the team, including chat turns. When the ceiling is hit, chat messages are still saved but get no reply turn; the team shows "The team has used all N turns today".
- **Hitting a job's ceiling:** the job goes to `team_blocked` with reason `cap_reached`, naming which ceiling. The owner chooses Allow more turns (only the owner in limited mode) or Cancel.
- **A ceiling cannot be bypassed by creating more jobs:**
  - the turns of every job add up to the team's daily ceiling;
  - a team leader in limited mode does not open jobs by itself;
  - asking for help is a step within the same job, and adds to that job's ceiling.
- **An agent does not raise a ceiling or change provider by itself.**

### 12.4 Duplicate prevention and stale output

| Situation | How it is blocked |
|---|---|
| Resending a message after a network drop | `client_msg_id` is UNIQUE in the session; a duplicate returns the old message and creates no turn |
| Duplicate job assignment | The job key is `source_ref` |
| A step running twice | `team_steps` CAS `queued` to `running`; at most one `running` turn per step |
| WebSocket reconnect | A turn is a server job; reconnecting creates no turn |
| Late output | Section 9.1 step 6: check member, revision, cancel, team leader before applying |

### 12.5 Performance

- The team list is paginated (50 rows per page), with the number of jobs waiting for you. Counted by index, without loading the jobs of every team.
- The chat uses the existing cursor pagination (30 messages, at most 200).
- Opening a team loads only: the 30 newest messages, the running job, the first 20 waiting jobs, 20 blocked jobs, the members. Job history loads when the History tab opens.
- All SQLite I/O runs in a worker thread like the existing stores, without blocking the event loop.
- **Measure:**
  - API: time of `GET /teams`, `GET /teams/{id}`, `GET /teams/{id}/queue` with 50 teams and 5,000 messages;
  - browser: time to draw a 200-message chat;
  - state which machine measured. A number from a local or sandbox machine is not evidence for the VPS.

## 13. Full access team leader

### 13.1 Turning on and off, scope

- The owner turns on "Full access for the team leader" in the team settings. After turning it on, one `team_authority` row is saved.
- **The team leader does not raise itself to Full access.** No tool can change `leader_mode`.
- **The grant box states clearly:**
  - scope: within this team;
  - the agents the team manages;
  - the providers and models that may be used (chosen from already configured providers; no account or credentials are added);
  - the payment source: a subscription plan or a paid API;
  - the ceilings (section 13.2);
  - whether "Can interrupt running jobs" is allowed (default no);
  - whether approving write scopes inside the team folder is allowed (D4).
- **When the team leader changes, Full access does not carry over.** The team goes back to Limited access until the owner turns it on again for the new team leader.

### 13.2 Ceilings under Full access

- Each ceiling in section 12.3 has three states: a **number**, **Unlimited**, or **Use default**.
- "Unlimited" is stored as `null` with the flag `unlimited=true`. The ceiling-check code treats it as no ceiling and **does not replace it with a big number**.
- **The owner sets a maximum (a ceiling on the ceiling) for each item.** A Full access team leader can change the team's ceilings within that maximum. If the maximum is "Unlimited", the team leader can set any value.
- **Ceilings that cannot be removed, always shown in the grant box:**
  - `JAVIS_RESONANCE_CALL_CEILING` set by the server (only affects goals);
  - the quota of the subscription plan or of the provider;
  - account permissions;
  - technical limits (section 13.6, group c).
- **Resonance goals created by an agent in a Full access team** take the goal ceilings (turns per goal, A5 role split, number of revision rounds) from the team settings instead of constants. This needs a code change (section 13.6). The A5 review gate stays.

### 13.3 An agent's shared configuration

An agent can be in many teams, so changing the shared configuration (prompt, model, Resonance) affects every team.

- **Team-managed agent:** an agent created by a Full access team leader, or an agent the owner marks "assign to this team to manage". Each agent has at most one managing team.
  - A Full access team leader can edit this agent's prompt, model (within the granted provider list) and Resonance.
  - Every change is logged with `by=leader:<key>`, `team_id`.
- **An agent not managed by the team:** the team leader cannot change the shared configuration (D5).
- **Changing the configuration of an agent that is also in other teams:** a confirmation box (for the owner) or a notice (for the team leader) lists the other teams affected. Permissions are never silently widened from one team to every team.

### 13.4 Full access and the queue

- A Full access team leader can change the order of **waiting jobs** (prioritize, un-prioritize), with the same CAS as the owner.
- **The rule "the running job finishes before the next one is taken" stays.** Interrupting or cancelling a running job is allowed only when the owner turns on the separate permission "Can interrupt running jobs"; in that case the reason for interrupting is written into an event and shown in the team.

### 13.5 Revoking

The owner can revoke at any time: turn off Full access, change the team leader, or stop the team.
- Write `revoked_at`. Every `javis_team` call after that mark re-checks the mode inside the transaction and is refused.
- The team leader's running turn runs to the end. Admin actions it requests after the revoke mark are refused. Content results are still applied if valid under Limited access.
- Ceilings go back to the Limited access level. A running job that exceeds the new ceiling goes to `team_blocked` with reason `cap_reached`, waiting for the owner.
- Team-managed agents still exist; the team leader loses the right to edit them.

### 13.6 Existing limits and how they are handled under Full access

Groups: (a) product ceiling, (b) integrity guarantee, (c) technical or external limit.

| Limit | Value | Where | Group | Under Full access | Code change needed? |
|---|---|---|---|---|---|
| Turns per goal | 6 | `resonance.py:451`, `begin_action` CAS | a | Taken from the team settings | Yes: pass `budget_calls` when creating a goal |
| Turns of a goal with a team, role split | 8, 4/4 | `resonance_store.py:311-312` | a | Per the team settings | Yes: constants become parameters when attaching a team |
| Number of A5 revision rounds | 2 | `resonance_store.py:313` | a | Per the team settings | Yes |
| Review turns counted per pinned version | 3 | `resonance_heartbeat.py:57` | a | Per the team settings | Yes |
| Retry, backoff, check cadence (15 minutes, 1 h/4 h/24 h, 6 h to 7 days) | | `resonance_heartbeat.py:28-38` | a | Kept in the first version | Yes if we want to open it |
| No command to raise an exhausted goal budget | | | a | Add an "Allow more turns" command for the owner, and for the Full access team leader within the maximum | Yes |
| Machine-wide ceiling `JAVIS_RESONANCE_CALL_CEILING` | env | `resonance_store.py:32-59` | a (server level) | Cannot be removed; shown in the grant box | No |
| Text-only engine for goals | | `main._resonance_engine` | b | Kept | No |
| Folders forbidden for posting (`javis`, `plugins`, `skills`, `agents`, `workflows`, `memory`, dotfiles) | | `resonance.py:2268-2280` | b | Kept | No |
| Product file type `.md`/`.txt`, 1 MB | | `resonance.py:1025-1026` | b/a | Kept in the first version | Yes if we want to open it |
| Approving the A4 write scope on the card | owner only | `approve_scope` | b | Only the team folder if the owner chooses so (D4) | Yes: a new grant source `team_full` for exactly that folder |
| A5 review gate | | `resonance_store.py:2425-2430` | b | Kept; the team leader cannot waive the review requirement | No |
| One run per goal (lease), CAS, pinned hash, idempotency key | | | b | Kept | No |
| Resonance switch is owner-only | | `_owner_only` | b | The team leader can change team-managed agents | Yes: `by=leader` and a management check in the store |
| Kanban `max_workers` | 2 | `tasks.py:138` | a/c | Does not apply to team jobs (own pool) | Yes |
| Kanban merging of jobs with the same title | | `task_store.enqueue` | a | Disabled for the `team` lane | Yes |
| Kanban `priority` 1..3 fixed at creation | | `task_store.py:288` | a | The `team` lane uses `team_prio` | Yes |
| Kanban lease 90 seconds, heartbeat 20 seconds | | `tasks.py:41-42` | c | Kept | No |
| Workflow `max_retries` per step | 1 | `main.py:9906` | a | Per the team settings when the job runs a workflow | Yes |
| Team ceilings (section 12.3) | | new | a | Number, Unlimited, Use default | New |
| One turn per agent at a time | 1 | new | a | The owner can change it; the team leader cannot | New |
| No-progress loop detection | 2 turns | new | b (always on) | Still detects. At "Unlimited", the policy is to **pause the job and report**, and it runs again only after the owner taps Continue; it never runs silently | New |
| The owner's stop, cancel, revoke commands | | | b | Always win | No |
| Quota of the subscription plan, of the provider | | | c | Cannot be exceeded | No |

## 14. Six reactions and the feedback loop

### 14.1 Values

Exactly six values are stored as they are, not merged:

| Value | Emoji | Label |
|---|---|---|
| `like` | 👍 | Like |
| `love` | ❤️ | Love |
| `haha` | 😂 | Haha |
| `wow` | 😮 | Wow |
| `sad` | 😢 | Sad |
| `angry` | 😡 | Angry |

- Plus `none` to remove a reaction.
- Each responder has one reaction per message: picking a different one changes it, picking the one already selected removes it.

### 14.2 Storage

- **Table `team_reactions`:** responder, message (`session_id`, `message_id`), agent (the message's `author_ref`), team, job, and the `content_sha` of the message content at the time of the tap.
- **`team_reaction_log`** appends every change, with a `nonce` to prevent duplicate sends.
- Kept across F5 and restarts.
- **Does not use A3's `reactions` table:** that table requires a goal and a report message written by the host (audit report section 7).

### 14.3 UI

- **Desktop:** hovering over an agent's message shows a smiley button; tapping it opens the six-emoji picker right at the message.
- **Phone:** a long press on a message opens the same picker as a large horizontal row; minimum touch target 44px.
- The chosen emoji shows under the message; tap it to change or remove it.
- **Additions, which do not replace the six emoji:**
  - **Quality reasons** (multiple choice): "On point", "Wrong facts", "Missing points", "Too long", "Unclear", "Off topic";
  - **a written comment** (at most 500 characters).
- Every string has an i18n key in both `vi.json` and `en.json`.

### 14.4 The feedback loop

No separate model call for each tap. Everything is handled by code.

**1. Separate two kinds of signal:**

| Signal | Meaning in the design |
|---|---|
| Emoji (six kinds) | An **emotional** signal. It can be aimed at the content being told (Sad about a sad story; Angry about an event), at the way of answering, or be a joke or sarcasm. It is never a quality rating by itself |
| Quality reasons and written comment | An **evaluation** signal, which can lead to adjustment |

**2. What must not be inferred:** from an emoji, the system does not infer "the agent did it wrong", "must fix now", "the job passed" or "the goal is met". Specifically:
- a reaction does not change the status of a job, goal or queue;
- it does not wake an agent;
- it does not open a turn.

**3. Feeding it into the next turn:** in the next turn of **that same agent in that same team**, a block "Recent feedback from the team owner" (at most 5 entries, 30 days, only entries not removed) lists for each message:
- a short excerpt;
- the original emoji, not renamed;
- the quality reasons;
- the written comment.

Together with a fixed note:

> The emoji is the team owner's feeling, possibly about the event being told; do not treat it as a score. Adjust only according to the quality reasons and the written comment. If unclear, keep your way of working.

**4. No firm lesson is created from an emoji.**
- A durable lesson comes only from quality reasons or a written comment, through a sourced suggestion mechanism: a "Suggested lesson" appears in the agent panel, and it becomes a lesson only when the owner taps accept.
- The suggestion mechanism is built in T2 if simple enough; otherwise it is left to a later milestone, and T2 only feeds the feedback into the context.

**5. Revoking:** when the owner removes a reaction, or edits or deletes a comment, that entry leaves the feedback block on the next turn. An accepted lesson has a remove button as in A3.

**6. Scope of learning:** feedback in team X only goes into turns in team X. An accepted lesson belongs to the agent so it is used everywhere; this is shown clearly in the "Accept lesson" box.

## 15. Planned API and tools

### 15.1 Owner routes (dashboard, auth and CSRF as today)

| Route | Purpose |
|---|---|
| `GET /teams?brain=&cursor=` | Team list, paginated |
| `POST /teams` | Create a team `{name, description, members:[slug], leader_slug}` (registers keys for members) |
| `GET /teams/{id}` | The team, members, team leader, mode, ceilings, running job, number of waiting and blocked jobs |
| `PATCH /teams/{id}` | Name, description, status (`active`/`paused`/`archived`) |
| `POST /teams/{id}/members` | Add `{slug}` or create a new agent and then add it (calls the existing `POST /agents` first) |
| `DELETE /teams/{id}/members/{agent_key}` | Remove a member |
| `POST /teams/{id}/leader` | Choose, change, remove the team leader `{agent_key or null}` |
| `POST /teams/{id}/authority` | Turn on, edit, revoke Full access `{mode, grant}` |
| `GET /teams/{id}/queue` | Running, waiting (in the right order), blocked jobs; `queue_version` |
| `POST /teams/{id}/queue/{task_id}/priority` | `{on: true/false, expected_queue_version}` |
| `POST /teams/{id}/tasks/{task_id}/cancel` | Cancel a job |
| `POST /teams/{id}/tasks/{task_id}/amend` | Edit the request, increases `team_rev` |
| `POST /teams/{id}/tasks/{task_id}/unblock` | Reply, rerun step, reassign `{action, ...}` |
| `POST /teams/{id}/messages/{mid}/reaction` | `{value, reasons, comment, nonce}` |
| `POST /teams/{id}/messages/{mid}/decision` | Pin or unpin as a decision |
| `GET /teams/{id}/turns` | Turn ledger by job, agent, day |

Sending a message goes through `/ws` as in today's chat. The packet adds these fields:
- `team_id`;
- `client_msg_id` (required for `team:` sessions);
- `mentions:[agent_key]`;
- `as_job: bool`.

### 15.2 The `javis_team` tool (only in team turns)

| `op` | Who | Purpose |
|---|---|---|
| `assign` | Team leader, in the `plan` step | Create a `work` step for a member, with a brief and inputs |
| `request_help` | A member in a `work` step | Create a `help` step (section 7.4) |
| `submit` | The person doing the step | Submit the step's result; the host posts the message |
| `propose_job` | Team leader | Suggest a job (section 7.1) |
| `open_job`, `reprioritize`, `add_member`, `remove_member`, `create_agent`, `set_cap`, `set_resonance` | Full access team leader | As in section 13, each call checks the mode inside the transaction |

Identity, team, job and step come from `turn_context` (adding the keys `team_id`, `task_id`, `step_id`). Model parameters carry content only (brief, question, result).

## 16. User interface

Full wireframes (desktop, narrow screen, the states) are in [team-chat-wireframes.md](../../dev/team-chat-wireframes.md).

- **Sidebar:** add a "Teams" item next to "Partners". The Teams page has three parts:
  - the team list (left);
  - the chat (middle);
  - the team settings (right, a drawer on narrow screens) with the tabs Members, Jobs, Turns, Settings.
- **Chat:**
  - messages show the sender's name and picture;
  - a job label on messages;
  - @ with suggestions from the member list;
  - an "Assign work" switch in the composer;
  - a "Working: ..." bar with two buttons, Edit request and Cancel.
- **Narrow screen:** the team list is the first page; tapping a team opens a full-screen chat; the team settings are a page that slides up.
- **Following the existing conventions:**
  - settings pages are a single column, with the Save button at the bottom;
  - no two-cell tables;
  - a class with `display:flex` must come with its own `[hidden]{display:none}` rule.

## 17. Performance measurement

See section 12.5. Measure before and after T1 on the same machine:
- API time (server side) for the team routes;
- browser time (drawing the chat, opening the team settings).

The two kinds of measurement are recorded separately. A conclusion about the VPS exists only when measured on the VPS after the project owner approves it separately.

## 18. Upgrading and downgrading

- **New store** `team.sqlite3`: old code does not read it.
- **Columns added to `messages` and `tasks`** all allow null, and old code ignores them.
- **The `team_*` statuses** are not in the set of statuses that old Kanban code picks up, so after a downgrade, team jobs are not run by old code with aux.
- **Snapshot on first upgrade:** copy `kanban.sqlite3` and `sessions.db` to `.pre-<T1 version number>`, using SQLite backup as in A5.
- **Restore tool** `tools/team_chat_restore_pre.py`, modeled on `tools/resonance_restore_pre_a5.py`.
- **Rollback test** runs the real release code from before T1 via `git show`, like `test_resonance_a5_rollback.py`.
- **Downgrade without restoring:** old code shows the `team_*` rows on the Jobs page with an unfamiliar status but does not run them. A `team:` session shows as an ordinary session. State this clearly in the guide.

## 19. Implementation milestones

| Milestone | Content | Useful flow |
|---|---|---|
| **T0** (small, can be done first) | Resonance switch on the assistant row; `/agents` returns the status; the Settings page keeps only a summary; reload on 409; two-tab sync | Turn on and off right on the Assistants screen |
| **T1** (the team chat core) | Sections 5 to 12 in Limited access mode, fixed default ceilings, the screens in section 16 | **Create a team, add agents, choose a team leader, assign generally or by @, a queue with Prioritize, coordination and asking for help, results back to the right team** |
| **T2** | Six reactions, reasons, comments; the feedback block in the next turn; (a lesson suggestion if simple enough) | Feedback with all six feelings |
| **T3** | Full access: the grant box, adjustable ceilings and "Unlimited", team-managed agents, admin tools for the team leader, per-team goal ceilings (section 13.6), the "Can interrupt jobs" permission, loop detection with a policy | The team leader runs itself within the scope the owner grants |
| **T4** | Long history: code-based summaries, search within a team, measurement on the VPS (needs separate approval) | Many teams, long history |

- Each milestone is one PR, reserving the version number when coding starts.
- **T1 is the largest. Do not split it smaller**, because the GOAL demands the first milestone have the full flow from creating a team to a result in the right team.
- **A real-model pilot** for each milestone is a separate package, with its own inputs, engine, ceilings and approval. This design does not authorize a pilot.

## 20. Acceptance matrix

Every case runs on a **fake engine** unless stated otherwise. Case code: TC. "Milestone" is the first milestone that must pass.

| Code | Case | Milestone | Planned code path | Evidence |
|---|---|---|---|---|
| TC1 | Create three teams; the same agent in two teams, team leader in one team, member in the other | T1 | `team_store.create`, `add_member`, `agent_register` | Store and route tests; screenshot of the team list |
| TC2 | Add an existing agent; create a new agent in the team settings (through `POST /agents`) and then add it; remove a member; the agent remains in Jarvis 007 and in other teams | T1 | `members` route | Test |
| TC3 | Creating an agent with a duplicate slug returns 409, without overwriting the old file | T1 | `POST /agents` | Test comparing the old file's bytes |
| TC4 | Change a member's tag: membership, team leader and permissions do not change | T1 | `/capability/meta` | Test |
| TC5 | Rename an agent: still a member; delete then recreate with the same slug: new key, not a member, does not receive old jobs | T1 | `agent_retire`, `team_members.status` | Test |
| TC6 | A message with no @: only the team leader replies, one turn; a team with no team leader: 0 turns, with a banner | T1 | routing in section 7.2 | Fake engine's turn ledger |
| TC7 | One @, several @ (in the right order, later people see earlier ones), over the @ ceiling, @ of a member who left | T1 | as above | Turn ledger, displayed messages |
| TC8 | The text "@Y" in an agent's reply does not wake Y | T1 | | Turn ledger = 0 for Y |
| TC9 | An ordinary message creates no job or goal; the "Assign work" switch creates exactly one job; resending the same `client_msg_id` creates no extra message, job or turn | T1 | `client_msg_id`, `source_ref` | Count the rows of `tasks`, `messages`, `team_turns` |
| TC10 | General assignment: `plan` step, two `work` steps, `synthesize`; results have an author, job label, status | T1 | `team_runner` | Flow test with the fake engine |
| TC11 | Direct @ assignment: starts with the @-mentioned person's `work`; the team leader does not redo it; the job still enters the shared queue | T1 | | Test |
| TC12 | Asking for help from A to B and A continues; B asking A back is blocked; depth 3 is blocked; no progress in two turns blocks | T1 | `request_help` | Test |
| TC13 | Ceilings for turns per job, steps per job, turns per team per day: hitting a ceiling gives `cap_reached`, no further calls | T1 | ceiling check at reservation | Turn ledger |
| TC14 | **A is running, B and C wait, prioritize C: order A, C, B; A does not run again; C does not cut in** | T1 | `team_prio`, `dispatch` | Test with a fake clock |
| TC15 | Repeated prioritize (changes nothing); un-prioritize (back to the old position); two prioritized jobs in tap order | T1 | | Test |
| TC16 | Two tabs change the order at once: one side gets 409 and receives the new queue; never two jobs running at once in one team | T1 | CAS `queue_version` | Concurrency test |
| TC17 | Restart in the middle of claiming a job, in the middle of a step before the engine mark, after the engine mark | T1 | `team_reclaim` | Test with the real store, server rebuilt |
| TC18 | A job waiting on the owner, a failed job: leaves the run slot, the queue moves on, shows in "Blocked", has an inbox message, has a reminder after 24 hours | T1 | | Test |
| TC19 | Remove a working member (before and after the engine mark); change the team leader mid-job; removing the team leader gives `no_leader` | T1 | sections 6.3, 6.4 | Test |
| TC20 | Edit the request and cancel a job midway; a late result has a label, `applied=0` | T1 | section 7.6 | Test |
| TC21 | The same agent in two teams, both with jobs: busy lock, FIFO wait, each result goes to the right team, contexts do not mix | T1 | `agent_busy`, member thread | Test inspecting the prompt sent to the fake engine |
| TC22 | No data mixing: a team turn's prompt contains no messages of other teams, private chat or the owner's memory | T1 | team block in section 11.2 | Test comparing prompts |
| TC23 | An agent without Resonance can do team steps but has no `javis_goal`; a goal created in a team turn reports back to the right `team:` session | T1 | | Test |
| TC24 | The A4 and A5 gates stay unchanged: a message grants no write permission; a goal with a team still needs a passing reviewer | T1 | existing A4, A5 tests rerun | Regression test |
| TC25 | Resonance switch on the assistant row: shows success only when the server confirms; reloads on 409; two tabs sync; the team member list shows the same status | T0/T1 | `workspace.js`, toggle route | JS test, UI smoke |
| TC26 | Turn off an agent that has work: the confirmation box names goals and teams; team jobs do not stop | T0/T1 | | UI smoke |
| TC27 | The Settings page no longer has a per-agent switch; has a summary and a link | T0 | | i18n test, smoke |
| TC28 | Six reactions: choose, change, remove; desktop and phone; kept across F5 and restart; correct person, message, agent, team, `content_sha` | T2 | `team_reactions` | Store test, UI smoke |
| TC29 | A reaction does not change the status of a job, goal or queue, opens no turn, calls no model | T2 | | Turn ledger = 0 |
| TC30 | The feedback block in the next turn keeps the original emoji, reasons, comment; has the fixed note; only within the right team; removing a reaction removes it from the block | T2 | | Test comparing prompts |
| TC31 | Full access: the team leader cannot turn it on itself; when the owner turns it on, `team_authority` is written; the team leader adds members, creates agents, changes the order of waiting jobs; every action has an event | T3 | `javis_team` admin op | Test |
| TC32 | "Unlimited" is `null` + a flag, not a number; the server ceiling and the provider quota are still shown and still apply | T3 | | Test |
| TC33 | A Full access team leader cannot edit the configuration of an agent not managed by the team; editing a team-managed agent reports the other teams affected | T3 | | Test |
| TC34 | Revoke Full access mid-turn: admin tools after the mark are refused; ceilings go back to the limited level; a job over the ceiling is blocked | T3 | | Test |
| TC35 | Without the "Can interrupt jobs" permission, a Full access team leader cannot interrupt a running job | T3 | | Test |
| TC36 | A no-progress loop at "Unlimited": pause and report, does not keep running silently | T3 | | Test |
| TC37 | Narrow 375px screen and desktop: team list, chat, team settings, reaction picker, no horizontal scrolling | T1/T2 | | Sandbox screenshots |
| TC38 | 50 teams, 5,000 messages: opening a team loads only the first page; API and browser measurements recorded separately | T1/T4 | | Measurements with the measuring machine |
| TC39 | Rollback to the version before T1 via snapshot; a downgrade without restore does not run team jobs | T1 | restore tool | Rollback test with the real release code |

## 21. Decision table

### 21.1 Requirements already settled (per the GOAL, not asked again)

- Many teams; a team has a name, description, members, history, its own jobs.
- An agent in many teams; each team has one team leader chosen by the owner.
- A tag only classifies; an A5 pair is not a team structure.
- Queue: the running job continues; Prioritize is considered before normal jobs after the running job finishes; durable storage; a direct @ assignment still enters the shared queue; the example A, C, B.
- The Resonance switch on the Assistants screen, showing success only when the server confirms.
- Two team leader modes. "Unlimited" is an explicit state. The owner can always revoke.
- Six reactions, keeping the original emoji kind, no firm inference, no model call for each tap.

### 21.2 Proposed defaults (my picks, with reasons; changeable at review)

| # | Default | Reason |
|---|---|---|
| M1 | Architecture A (section 3) | Reuses Kanban's durable storage and recovery, adds no work-assignment system |
| M2 | One job runs per team; two teams run at once on the whole machine | Matches the queue requirement; keeps cost and load in range |
| M3 | Priority in tap order; repeated taps change nothing; un-prioritize returns to the old position | Easy to understand, deterministic |
| M4 | A blocked job leaves the run slot | A team is never stuck invisibly |
| M5 | A step that already called the engine and was interrupted by a restart: does not rerun by itself | Avoids paying twice |
| M6 | Default ceilings in section 12.3 | Enough for a medium job (planning, three people working, help, summary) |
| M7 | The agent's model is read on every turn from the agent file | The member thread is a hidden session, a snapshot would go stale |
| M8 | `javis_task` is hidden in team turns | One place to assign work inside a team |
| M9 | Remove the duplicate switch in the right column and the Settings page | Not two switches for one agent |
| M10 | A separate reaction table for teams, not A3's table | A3's table is tied to goals and report messages |
| M11 | Full access does not carry over when the team leader changes | Permission is tied to a person, not a title |

### 21.3 Settled points (the project owner agreed to all seven proposals, 13/10/2026)

| # | Question | Settled | Impact |
|---|---|---|---|
| D1 | A message with no @ in chat mode: does the team leader reply (one turn per message), or does nobody reply unless @-mentioned? | The team leader replies | Cost per message, the feeling that "the team has someone there" |
| D2 | Assigning work: only when you turn on "Assign work", or may the team leader recognize a request itself and suggest it (you tap once)? | Both: an explicit switch, plus the team leader's suggestion that needs your tap | Number of taps and cost |
| D3 | An agent runs only one team turn at a time on the whole machine (memory safety, slower when an agent is in many teams)? | Yes | Speed and preventing mix-ups |
| D4 | May Full access approve A4 file write permission? | Only inside one team folder you choose; outside that folder it still waits for your tap on the card | Opens part of the A4 gate |
| D5 | Which agents' shared configuration (prompt, model, Resonance) can a Full access team leader edit? | Only team-managed agents | Cross-team impact |
| D6 | May "Unlimited" model turns apply to a paid API provider? | Only to providers you tick in the grant box; the amount used is always shown | Cost |
| D7 | Default ceilings in section 12.3 (12 turns per job, 8 steps, 3 @, 100 turns per team per day) | As in the table | Cost and depth of coordination |

## 22. Self-check for contradictions

| Pair that might disagree | Conclusion |
|---|---|
| Prioritize and "a direct @ does not skip the queue" | No conflict: an @ assignment enters the shared queue; only the owner's Prioritize, or a Full access team leader's, changes the order |
| Chat turns not going through the queue and "one job runs per team" | No conflict: a chat turn is not a team job; it only waits for the agent's busy lock. Stated in section 7.2 |
| Full access and "the owner's command always wins" | No conflict: every Full access action checks the mode inside the transaction; revoking has the `revoked_at` mark |
| Full access and "the running job finishes" | No conflict: interrupting needs a separate permission that is off by default (section 13.4) |
| Turning off Resonance and team jobs | Settled: the switch only affects goals; the confirmation box says so clearly (section 10.2) |
| Restart and duplicate-call prevention | A step that already called the engine does not rerun by itself; a step that has not called is refunded (section 8.6) |
| Cancelling a job and an A4 version already committed to post | Per A4: a version already committed still completes; one not yet committed expires (section 11.4) |
| Reactions and the learning loop | An emoji does not change status or create a firm lesson; only reasons and written comments lead to a suggestion (section 14.4) |
| Per-agent busy lock and private chat, goals | The recorded limitation: T1 does not lock private chat and goals (section 8.7) |
| An agent's own model and Resonance | Goals still use the background-work model as in A1 to A5; stated in section 12.1 |
