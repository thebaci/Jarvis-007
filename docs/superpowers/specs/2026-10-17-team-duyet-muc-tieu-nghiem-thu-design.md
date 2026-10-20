# Multi-day team work: a real approval gate, department mandate, acceptance (0.207.0 to 0.210.0)

Date: 2026-10-17. Base: main 0.206.0. Code survey before the work: summarized in section 0.
General principle: extend the mechanisms that already exist (TeamRunner, the Kanban team lane, the hub's suggest/auto/full
permission levels, pulse, ledger, outbox, evidence_store), do not build a parallel system. Fake engine in every test.

## 0. Verified current state (build 0.206.0, assuming no old bug is gone)

- The "asks for approval but still done" bug is STILL THERE: `asks_owner` (team_runner `_post`, regex `ASKS_OWNER_RE`, team leader only) is just a
  display flag and a machine notice. `_apply_step_locked` does not read it: a `plan` step that assigns no one makes `_finish` take the question itself as the job
  result; a `work` step gets `finish_step(done)` and then `_after_steps` closes the job. The server has never emitted a block kind `waiting_user`
  even though the 2026-10-13 spec and the dashboard already have a label and a button for it.
- The Work/Help turn runs at a fixed `full` level (`TEAM_WORK_MODE`), with no pre-tool checkpoint: the hub allows every tool, and Claude in
  bypassPermissions has no PreToolUse.
- `unblock("resume")` only requeues the job: with no waiting step left, `_after_steps` closes it right away with the old result. An approval must ADD a step.
- Pulse is per agent, and opportunity sources come only from team jobs and goals (`_pulse_opportunities`: blocked_new_data, stale_job,
  proposal_open, goal_waiting). There is no file, test or MCP source; no deadline, cooldown or evidence for an opportunity.
- Kanban closes done on a single model turn that reads the report (`_check_acceptance`), and if the checker fails the job is still done (`unverified`). The team lane
  has no acceptance at all. The artifacts store has only paths, no hash. Resonance already has good patterns (artifact_contract,
  human_confirmation tied to sha256, source_drift) to reuse.

## 1. A real approval gate (0.207.0)

### 1.1 Data (team.sqlite3, new tables, no change to old tables)

`team_approvals(approval_id PK, team_id, task_id, step_id, team_rev, requested_by, kind, title, action_json, scope,
impact, evidence_json, deadline_at, fingerprints_json, status, decided_by, decision, decision_note, decision_key UNIQUE,
decided_at, consumed_at, created_at, updated_at)` and `team_approval_events(id, approval_id, at, kind, by, detail_json)`.

- `kind`: `action` (one specific action blocked by the gate, with a fingerprint), `plan` (a plan the agent asks for with a structured command),
  `question` (the agent asks the owner to decide without using the command: the safety net, see 1.3).
- `status`: `pending` -> `approved` -> `consumed`; or `rejected`, `changes_requested`, `expired`, `superseded`
  (request amended / plan changed / member left), `cancelled` (job cancelled), `revoked` (permission revoked).
- Each job has at most one `pending` request (a partial unique index).

### 1.2 Lifecycle

- When a step creates a request: the step moves to `waiting_owner`, the job moves to `team_blocked` kind `waiting_user` (releasing the run slot). No
  `finish_step(done)`, no `_finish`, no added assignment step, no dependent step runs. A plan that has an assignment command together with
  an approval request: the assignment command is HELD inside the request, and the step is added only after approval.
- A decision goes only through `POST /teams/{id}/approvals/{aid}/decide` (owner signed in): `approve | reject | changes`, with
  `expected_rev` and `decision_key` (one key per click). CAS: the request is still `pending`, the job's `team_rev` still equals the request's revision,
  and the job is still blocked `waiting_user`. Resending the same key returns exactly the old result (retry after a network loss). A different key once decided
  returns `already_decided` (second tab). A wrong revision returns `stale`.
- Approve: add ONE new step for the requester (same step type), the brief says exactly what was approved; the step note is `approval:<id>`; only then unblock
  (as in `extend_job`). An approved `plan` step adds the held assignment steps. The fingerprint of an `action` request can only
  be used in exactly that step and is consumed (consume) RIGHT when the gate lets it through, in one transaction: a restart or re-running the step
  does not repeat the effect; to do it again a new approval must be requested.
- Reject: the request is `rejected`, the step `cancelled`, the job stays blocked with kind `rejected` and the owner's reason. The owner chooses: cancel the job, amend
  the request (new revision) or hand it back to the team leader to find another way (adds a plan step with the rejection note).
- Request changes: the request is `changes_requested`; add a step for the requester with the feedback and unblock. The revised plan is a NEW request.
- Invalidation: `team_amend` (request amended) -> every unconsumed request of the job becomes `superseded`; job cancelled -> `cancelled`; a team
  permission change (revoking `work_mode=full`, revoking Full access) -> approved unconsumed requests become `revoked`; a member asking to leave the
  team -> `superseded`. Past `deadline_at` -> `expired`, and the job blocks with kind `approval_expired`.
- An agent's message, a quote inside a message, or text the owner types in chat is NOT an approval: no JAVIS_TEAM command decides anything,
  and the parser does not read words to approve. The approval card appears in the chat with the buttons Approve, Reject, Ask for changes.

### 1.3 Who may create a request, and the safety net

- Structured command (the main protocol): `<!-- JAVIS_TEAM: {"op": "ask_approval", "title", "action", "scope", "impact",
  "evidence": [...], "deadline"} -->` in a `plan`, `work` or `help` step. Any member may use it in a step of the job.
- The tool gate (1.4) blocks an action: the host itself creates an `action` request from the blocked call (tool name, argument summary,
  fingerprint). This is data the host observed, not the model's words.
- Safety net: a step result that calls on the team owner (`ASKS_OWNER_RE`, any member, not only the leader) or asks for a decision without
  the command: the host creates a `question` request with the excerpt, stating clearly "the agent asked in words and did not give a structured plan". The step
  does not become done. The regex is only a net, not the protocol.

### 1.4 The pre-tool gate (done, team_gate.py)

The team's work permission, new column `teams.work_mode`:
- `gated` (default, including old teams): work inside the scope (read, search, write files in the brain and the team folder, read connections,
  read-only shell commands) runs without asking; outside actions (hub tools of class `danger`: send, post, delete, pay, order;
  plugin tools that need level `full`; shell commands outside the read-only list; Claude account connectors that are not read commands; file writes
  outside the allowed folders) need an approved request for exactly that call.
- `full`: the owner turns on "The team acts without asking" (the same permission as the 0.194.0 private chat, no gate).

New hub level `gated`: lists tools like `full` (so a blocked action can become a request and run after approval), with the ceiling
of `auto` (`mcp_catalog._MODE_CAP`), so anywhere that does not know the gate fails closed and never runs at `full`. When the hub's `_guard`
or `plugins_host._make_call` sees a call blocked by the `gated` ceiling while the connection allows it at `full`, it asks the turn's gate
(`turn_context` key `team_gate`, arriving through `X-Javis-Turn` or a ContextVar). If there is an approved fingerprint for this step it is consumed right away
in one transaction and the call is let through; otherwise it is refused BEFORE the call and the call is recorded (name, arguments, fingerprint). With no live
gate (missing or forged turn key) it is refused.

Per provider (`team_gate.provider_support`, `main._team_gate_support` reads the machine's real flags):
- Claude: the SDK's PreToolUse hook (bypassPermissions does not skip hooks). Read/Glob/Grep/WebSearch/WebFetch/Task pass;
  Write/Edit only inside the team folder and the brain; Bash only read-only commands (ls, cat, grep, git status... no shell characters, `find`
  without `-exec`/`-delete`); `mcp__javis__*` is left for the hub to block; account connectors only read commands. If the SDK has no hook, refuse.
- Codex: built at `auto` (sandbox `workspace-write`, no network), the hub overrides it to `gated` and turns on the turn key. With no sandbox
  (`JAVIS_CODEX_SANDBOX=off`) refuse.
- API: every tool goes through the in-process hub at level `gated`.
- Grok Build: built at `auto` (Bash banned, hub `auto`). Grok cannot carry the turn key to the hub (the MCP config file is shared by the whole
  brain), so it can only do the in-scope part; an approved action cannot run on Grok. A build without `--deny` is refused.
- Antigravity: cannot block its own tools before they run. When `gated`: refuse the step and say clearly "switch the assistant to Claude,
  Codex or an API model, or turn on full permission for the team".

An approved call can only be used in exactly the step that was opened (`granted_step`), once per fingerprint. If an approved step is interrupted
(restart, error), "Re-run step" moves the UNUSED part of the approval to the re-run step; the used part never runs a second time.

### 1.5 UI

The approval card in the team chat (meta `kind: approval_request`): what is being asked, scope, impact, evidence, deadline; three buttons. The card
state is read from the server (not guessed): pending, approved by..., rejected, no longer valid because... The list of pending requests is on the
Jobs tab. Team settings have the `work_mode` switch.

## 2. Department mandate and opportunities (0.208.0)

### 2.1 Mandate (team.sqlite3, new table `team_mandates` with a version, `team_mandate_events`)

Fields: outcome, metrics[], sources[] (type + reference: `folder:<rel>`, `kanban`, `mcp:<conn_id>`, `test:<safe command>`),
scope, budget (observations/day, self-created jobs/day), cadence_min, autonomy (`act` the job types it may do on its own,
`propose`, `approve` needs approval), stop_conditions[], status `off|active|paused|revoked`, version. Old teams have no mandate
(off). Turning on, editing (new version), pausing and revoking are done only by the owner through the API; revoking blocks every new action from the mandate.

### 2.2 Observations and opportunities

- Observers are code first, model second, run on the mandate's cadence and budget, only on granted sources:
  `folder` (fingerprint of mtime/size/sha of the files in the granted folder, with a file-count limit), `kanban` (new failed/blocked jobs of the
  brain, `sentinel`), `mcp` (connection state `connect_health`, if missing record "missing source"), `test` (a safe command through
  `run_command`, exit code).
- Every observation is stored durably (`mandate_observations`: source, ref, version/hash, observed_at, summary). A change compared with the last time
  produces an opportunity (`mandate_opportunities`: source, ref, version, reason tied to the goal, expected benefit, status, expires_at,
  cooldown_until, decision, trace). Dedup key `(team, source, ref, version)`. A rejected one is not reopened until the source
  version changes. It expires after N hours unhandled.
- Classification (code plus one model turn limited to text): `none | watch | propose | ask | enqueue`. `enqueue` only when the job
  type is in `autonomy.act` AND budget remains AND no outside action is needed (if one is needed it becomes `ask` through the approval gate).
  No opportunity means nothing is created. A source with no connection shows a missing-source state, no invented problems.
- A self-created job carries the trace `mandate:<id>@v` -> `opp:<id>` -> decision -> (approval) -> job -> product -> acceptance.

## 3. Acceptance (0.209.0)

- Acceptance criteria are tied to the job and revision (`team_acceptance`: criteria_json, policy, revision, accepted_by_owner_at). Criteria
  kinds: `file_exists`, `file_contains` (min_chars, must_contain), `json_schema` (required keys), `command_ok` (a safe command
  through `run_command`, exit code 0), `owner_confirm` (the owner confirms exactly the product's hash). A model review is only evidence.
- Product: path, sha256, size, mtime at check time (evidence). Result per criterion: `pass | fail | unknown`. A job is done only
  when every criterion is `pass` under the policy the owner accepted; `unknown` or a missing `owner_confirm` waits for the owner. `fail` opens a
  bounded fix round (`fix_rounds`, default 2), beyond that it blocks `acceptance_failed`.
- Editing the product file after it passed invalidates the old evidence (compare sha). History is stored durably. Useful signals (`result_used`,
  `objective_pass`) are recorded exactly once per (job, revision) when acceptance passes or the owner confirms, never from an agent's words.

## 4. Testing, review, pilot (0.210.0)

Real-host tests with a fake engine (listed in the GOAL), a fake clock over many days, many teams. Independent review at each milestone. The pilot pack
in `pilot/team-multiday/`: its own state and brain, 3 sample teams, a 7-day scenario, budget, how to stop, rollback, metrics, report
template, requirements matrix. The pilot has not been run.

## 5. Migration and rollback

New tables, new columns with defaults (an old build can ignore them). One-time snapshot before adding columns (`team_migration.snapshot_once`).
Rolling back to the old build: the new tables are ignored; jobs blocked `waiting_user` show the old build's "Continue" button.
