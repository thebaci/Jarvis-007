# Resonance A5: one agent makes, another agent reviews (design)

**Status:** design **locked** (design review round 3 passed at `56f7ab50`); **code passed review round 2 at `05e9b065`; the real pilot real-2 at `33cec518` was accepted by the reviewer within the scope of one `pass_first` sample (1 maker turn, 1 review turn, 0 chats; the fix loop is not yet proven with a real model); not yet released** (guide [resonance-a5-team](../../dev/resonance-a5-team.md), record [resonance-a5-verification](../../dev/resonance-a5-verification.md)). The sections below keep the locked content unchanged; they were fixed after review round 1 (R1 to R5) and review round 2 (P2 retry counter, reconciliation schedule, two fix rounds); the project owner chose option A for hand-edited files (section 0). The A5 code passed code review round 2 at `05e9b065` (record, pilot script [resonance-a5-pilot](../../dev/resonance-a5-pilot.md)); the real pilot real-2 used 2 background-model turns within the ceiling of 4. A5 **was released as 0.109.0** (`bfb1c29f`, PR #616, 2026-10-13; CI `main` run 38369853756 and image build run 38369852881 succeeded; image `ghcr.io/blogminhquy/javis-os:0.109.0`, digest `sha256:3890f824…`; the VPS has not pulled it). Code review round 1 clarified two points that were already in the design: the review gate applies to EVERY accepted-as-passing version of a goal that has a team (both `maintain` and the discovery step, sections 4.2, 5.1), and a turn that has not reached the engine-call mark is a turn that certainly has not run (sections 5.6, 6.2). The defaults in section 16 follow the recommendation of review round 1; they are a proposed product configuration, **not a permission to run the pilot**.

- **Branch:** `claude/resonance-a5-maker-reviewer`, draft PR #616, number **0.109.0** after integrating `main` 0.108.0 (at design time it held 0.101.0; the old 0.97.0 was already below `main`).
- **Base:** at design and code review time it was `main` `a02663cb` (0.100.0); `main` `c4fb614d` (0.108.0) was integrated before the merge. A1 0.87.0, A2 0.88.0, A3 0.89.0, A4 0.96.0 (`d36ebb3e`) are released; 0.100.0 added tags for agents (section 4.5).
- **Inputs:**
  - [agent roadmap](2026-10-08-resonance-agent-scope-roadmap.md) sections 7 and 8.
  - [A4 design](2026-10-10-resonance-a4-handoff-grants-design.md): invariant 5, section 5.4 `narrow`, section 12.5 the cases left for A5.
  - [A3 design](2026-10-09-resonance-a3-feedback-learning-design.md) section 16.
  - Review round 1: `exports/reviews/PR-616-A5-design-r1-review.md`; review round 2: `exports/reviews/PR-616-A5-design-r2-review.md`.
  - The current code of `server/resonance*.py`, `server/main.py` (workflow, `_resonance_engine`), `system/plugins/javis-goal`.
- **Evidence level:** reading code and documents, plus the reviewer's probes run on the new base (section 18). Nothing has been run for A5 yet.
- **Code line numbers:** cited against `a02663cb`. `server/resonance*.py` has not changed since `dc18942e`, so the line numbers in those files stay as in round 1. `server/main.py` changed with the tag PR.

## 0. Round 2 changes (from review round 1)

| # | Review defect | Fixed in section | Acceptance cases |
|---|---|---|---|
| R1 (P1) | Attaching the team in `assign_goal` misses the main creation path (`form_goal` calls `create`) | 4.2 (attach the team inside the `create` transaction), 9.2, 16 D11 (old goals via `assign_goal` have no team) | T31 to T36 |
| R2 (P2) | The `review_due` dedup key lacks the revision and the identity of the review pass | 5.6 (review schedule identity table), 10 (code and classes), 9.1 (`reviews.bundle_ref`) | T11, T37 to T41 |
| R3 (P2) | Turning the reviewer off and on cannot resume because the version only ever increases | 4.2 (pin a durable key, not the version), 5.5, 7.3 (recovery path), 11 (actions on the card) | T18, T42 to T46 |
| R4 (P2) | The budget does not cover A3 (lane M) and does not match the 4 + 4 promise | 6 (table of every hold, refund and takeover path; lane M off when a team exists; class `FIX`; trace table) | T5, T6, T47 to T54 |
| R5 (P2) | T10 reviews a hand-edited version without a valid snapshot | 5.5 (an out-of-band edit blocks finalizing and is not reviewed), 4.3 (check the snapshot hash) | T10, T55 to T58 |

**Round 3 (from review round 2):**

| # | Point | Fixed in section | Acceptance cases |
|---|---|---|---|
| P2 | Cancelling before the engine still consumes a review retry: separate the row sequence number (`seq`) from the charged count (`charged`); one single refund function for `abort_action` and `release_call` | 5.6, 6.2, 6.4, 6.5 (V8), 9.1, 9.2 | T61 to T65 |
| Schedule | A review action only schedules `action_recovery` (code-based reconciliation, like the base code for non-`work` actions), not the AUTO-class `recovery` of the maker role; `review_retry` is added only after reconciliation | 5.6, 9.2 | T66 |
| Round | Exact inequality: the k-th valid `needs_changes` verdict produces a fix turn when k ≤ 2, the 3rd blocks; a `mismatch` or `stale` verdict does not count and produces no fix turn | 5.4, 5.1 | T4, T67 |
| Decision | The project owner chose option A (2026-10-12): a goal with a team is not finalized on a hand edit | 5.5, 16.2, D14 | T10, T55, T56 |

The "note" points from review round 1 are also recorded in the main text:
- The lease does not block maker chat: section 7.2 and T59.
- `too_large` needs a human to handle it: section 5.2 and the stop table in 5.1.

## 1. Goals and out of scope

The roadmap (section 7) sets these requirements:
- "one agent makes and one agent reviews, one goal answers for the end result";
- the review is tied to the exact hash and revision;
- the reviewer does not edit the criteria itself;
- the shared quota is split into shares;
- a change made after review must be reviewed again;
- when the owner stops, both stop;
- no spawning new agents to get past a gate.

**What the user sees:**
- On the page of an agent that has Resonance on, the project owner picks another agent as the **reviewer**. From then on, NEW goals of this agent go through review before being treated as passing.
- The goal card shows:
  - who is making and who is reviewing;
  - which version (its short code) was reviewed, and the verdict;
  - why it is waiting;
  - the turns left for each role.
- When the review asks for changes, the maker agent fixes it by itself following the feedback, with a limit on the number of rounds. When rounds or turns run out, it stops and reports, and does not loosen the limit by itself.

**Kept unchanged:**
- Normal chat stays normal chat; Resonance and review do not apply to a conversation with no goal.
- The A4 submit and publish contract is unchanged: `javis_submit_deliverable`, the four-step `host_publish`, permission by scope D1.
- The A2 heartbeat (wake with a reason, no periodic polling of the model) and the A3 feedback loop (a reaction changes no schedule and replaces no verdict) are unchanged. Only lane M of A3 is temporarily off on a goal that has a team (section 6.3).
- The `human_confirmation` criterion and the guard keep their veto.

**Out of scope:**
- Teams of more than two agents, agents that spawn agents, a general supervisor, sub-goals.
- Assigning work from normal chat is not yet locked.
- Changing the behavior of an existing target file (`target_occupied`), and taking over an arbitrary file the user edits (section 5.5).
- VPS optimization; self-editing the product code.
- A review that runs inside a chat turn (the reviewer runs only in background work).
- A quota-raising command (does not exist yet; section 16 D13).
- Choosing a reviewer or a team by tag (section 4.5).

## 2. Current state: what is reused and the gaps

| Needed for A5 | Already exists | Where | Gap |
|---|---|---|---|
| Host-issued agent identity | durable `agent_key`, `config_version`, `agent_gate` | `resonance_store.py` `agent_set_enabled` (:492), `_bump_agent` (:456); `resonance.py` `agent_gate` (:502); `_agent_block` (:680) | No second role on a goal yet |
| Goal creation path | `form_goal` calls `store.create`; `create` writes `goal_agents` in the same transaction | `resonance.py` :947-993; `resonance_store.py` :708-786. Two entry points: tool `javis_goal` (`system/plugins/javis-goal/plugin.py` :206) and `POST /goal-requests` (`resonance_api.py` :202-242) | The team is not attached yet. `assign_goal` (:2114) only works on goals NOT yet assigned (old goals) |
| Reserve a turn before the call, durably | `begin_action` inside `BEGIN IMMEDIATE`, `_ReservedCall`, `release_call`, `abort_action`, `_reconcile` | `resonance_store.py` :1439, :1856, :1148; `resonance.py` :1895, :2213 | Not split by role yet; `release_call` does not know which role's turn it is |
| Lane M turns (A3) | `begin_experiment` holds both the trial turn and one hold turn (`call_holds`); refunded via `release_trial_call`, `finish_experiment(refund)`, `_release_hold` | `resonance_store.py` :1540-1615, :1617, :1622, :2505 | Goes straight into `calls_used`, outside any role ledger |
| Shared ceiling | `call_ceiling`, `_under_ceiling` | `resonance_store.py` :32, :53 | Used as is |
| Wake with a reason | `wake_reasons` permanent dedup by (`goal_id`, `code`, `source_ref`), `CLASSES`, `HB.decide`, `auto_allowed` | `resonance_store.py` :153, :968-981, :1037; `resonance_heartbeat.py` :40, :112, :130 | No review reason code yet; `CLASSES` maps one code to one fixed class |
| Prevent overlapping runs | goal lease, CAS `claim_wake`, CAS revision | `resonance_store.py` :1424, :1341 | Used as is; both roles share one goal lease |
| Evaluate per revision | `evaluate_artifact`, `Assessment` met/not_met/unknown, `_human_verdict` tied to the current bytes sha | `resonance.py` :1578, :1074, :1548-1571 | No review condition yet |
| Out-of-band edits | `_source_drift`, `observe_source` (the observation mark is separate from the publish mark), `waiting/source_drift` | `resonance.py` :1756-1783, :2864-2880 | A2 still finalizes as passing when a hand-edited version passes the objective check; A5 must block this for a goal with a team (section 5.5) |
| Accepted version and snapshot | `published(goal_id, path, sha256, action_id)`, `submissions` (A4, has `evidence_id`), `evidence_links(action_id, evidence_id, content_hash)`, `adopt_submission` | `resonance_store.py` :111, :296, :100, :3852 | Used as is as the source of the review snapshot |
| Text-only background engine | `_resonance_engine`, `pick_text_only_link`, `SYSTEM_PROMPT` | `main.py` :2040; `resonance.py` :181, :46 | Used as is for both roles |
| Evidence | `_ResonanceEvidence`, `_put_evidence` returns None on error | `main.py` :2281; `resonance.py` :1525 | Used as is |
| Write permission by scope | root/revision grants, bindings, `authority_clock` | `resonance_store.py` A4 | The reviewer gets no write permission |
| Reviewer in a workflow | `verify_agent`, JSON `{pass, reason, fixes}`, fix loop | `main.py` :9384-9440, :9814-9880 | NOT reused as a block (see below) |

**Why the review does not run through a workflow:**
- The `verify_agent` step reads the verdict from free text with a regex.
- Missing JSON or an engine error both count as **pass** (`main.py` :9406, :9414, :9872, :9880).
- A review step that fails still completes and moves on.
- It does not count model calls and does not touch the Resonance ceiling.
- It runs the agent's own engine, with tools and a fallback provider.

A5 reuses only the **review instruction** ("treat the result as wrong by default") and the **feedback template for the fix loop** (the previous version plus the reason and how to fix it). The verdict is read in a fail-closed way, and turns go through the Resonance ledger.

**Two facts that must be stated plainly:**
- **Background work does NOT run on the agent's engine.** Both the maker turn and the review turn run on the user's shared "background work" model, text only, no tools (`resonance.py` :527-529). The two roles use the same model (D3); they differ in identity, role instruction and the data they see, not in having an independent brain.
- **The background prompt currently does not include the content of the agent file** (`_work_prompt`, `resonance.py` :1862). A5 adds a role description for the reviewer: the body of the agent file, with a length limit, marked as data. The maker side stays unchanged.

## 3. Invariants

1. **The host decides who does what.** The role and the `agent_key` of each role are pinned by the host when the goal is created. Model words cannot change the role, criteria, permission or quota.
2. **A review is tied to the exact version.** A review verdict is valid only for exactly the pin set (section 5.5):
   - `goal_id`, `revision`;
   - the accepted version and its sha;
   - the criteria hash;
   - `reviewer_agent_key` and `reviewer_config_version` at review time.

   If any component changes, the old verdict cannot be used to finalize.
3. **A review does not replace the veto.** A passing review does not remove the guard, does not replace `human_confirmation`, and does not make up for an objective criterion that has not passed.
4. **Fail closed.** An unreadable verdict, an engine error, an evidence-storage error, mismatched data, a snapshot that does not match its hash are all `unknown`, never pass.
5. **One ledger, split into shares, no detour.** Every model turn of a goal that has a team goes through the role ledger in the same transaction as `calls_used` and the shared ceiling.
   - A path that cannot carry a role (lane M of A3) is rejected by the store, and does not go outside the ledger.
   - Reserve before the call; refund only when it is certain the engine has not run; never loosen by itself.
6. **Stop wins.** Pause, cancel, permission revocation and turning an agent off take effect for both roles by scope; old turns do not benefit from a re-granted permission.
7. **Finalize only on the accepted version.** A goal that has a team can be finalized as passing only when the bytes currently at the target file match the accepted version that was reviewed. An out-of-band edit does not become an accepted version by itself.

## 4. The team model

### 4.1 Two roles

| Role | Who | May do | May not do |
|---|---|---|---|
| Maker (`maker`) | The agent that answers for the end result of the goal, exactly the agent in `goal_agents` | Form and fix the goal in chat (A1), submit a version (A4), do background work | Mark itself as passing; change the reviewer |
| Reviewer (`reviewer`) | Another Resonance agent in the same brain, chosen by the project owner | Read the snapshot of the accepted version and the criteria, return a verdict | Write files, submit a version, change criteria, permission or quota, run in chat |

The reviewer has no grants at all (no root, no revision). Every action with side effects still goes through the maker's A4 gate.

### 4.2 Choosing the two agents, attaching the team to a goal

**Choosing the pair (table `team_pairs`, project owner only):**
- The project owner turns it on from the maker's agent page. The **Reviewer** field lists the agents that have Resonance on (`resonance_agents` `active`) in the same brain, except the agent itself.
- Picking an agent turns team mode on for this agent; clearing the choice turns it off. There is no other setting: quota and number of rounds use the defaults (section 6).
- The pair is stored by the `agent_key` of both sides, not by slug or tag. Every change increments `team_pairs.config_version`.

**Attaching the team to a NEW goal (R1):** one shared store function `_attach_team(c, goal_id, brain_id, maker_key, now)`, called **inside the `create` transaction itself**, right after the `goal_agents` line (`resonance_store.py` :757).
- `create` is the only path that creates a goal with an agent. Both the `javis_goal` tool and `POST /goal-requests` go through `form_goal`, which calls `create`, so both entry points are covered without a second transaction. There is no gap in which a goal starts running before it has a team: this is why `created` is written in the same transaction.
- Pair is on: write `goal_team(status='active')` pinning `reviewer_agent_key`; write two `team_calls` rows (maker 4, reviewer 4); set `goals.budget_calls = TEAM_DEFAULT_CALLS = 8`, replacing the default 6 that `form_goal` passes in.
- **The reviewer is unusable at creation time** (off, `missing`, retired) while the pair is still on: the team is still attached. The review-role gate (section 7.3) blocks at the first wake with a specific reason. Review is never silently dropped.
- Pair off or no pair: no `goal_team`; the goal runs as in A4.
- **Idempotent:** the same `idempotency_key` makes `create` return the old goal before any write (:723-727). Creating twice from the same message does not change the reviewer, does not change the budget, does not add `team_calls`.
- Changing the pair after creation does not affect existing goals: the reviewer is already pinned in `goal_team`.

**Old goals going through `assign_goal` (D11):** `assign_goal` (:2114) only assigns goals that do NOT yet have an agent (created before A1 or by an old version), which may have already spent turns. A5 does **not** attach a team on this path.
- Such a goal runs as in A4. The card says "This goal predates the team; it has no reviewer", and the `agent_assigned` event records `team: "not_attached_legacy"`.
- Reason: attaching a team now would force re-splitting the `calls_used` already spent or raising the quota, exactly what the review forbids. This is a project-owner action, shown clearly on the card, not a path for the agent to drop review by itself.
- Calling `assign_goal` for a goal that already has an agent is still rejected as it is today (confirmed by probe).

**Detaching the team from a goal (`team_detach`, project owner only):**
- `goal_team.status` goes to `detached`, with `detached_by` and a `team_detached` event recorded. From then on the goal finalizes by the A4 rules.
- The command is stated plainly on the card: "Drop the review requirement for this goal". No tool or model path can call it.
- `team_calls` is kept as a record; turns already used are not erased.
- A5 does not support re-attaching a team or changing the reviewer midway.

### 4.3 What the reviewer sees

The host builds the review input from the host's own data, without letting the reviewer read files or use tools:
- **The understanding of the goal and the criteria** of the current revision, marked as data. The `human_confirmation` criterion (the user confirms it themselves) is left out.
- **The constraints the user stated.**
- **The snapshot of the accepted version** (section 5.5): the bytes from the evidence of the version at the publish mark (`published.action_id`).
  - That evidence is `evidence_links.content_hash`, or `submissions.evidence_id` of the A4 submission.
  - The target file is not read again.
  - Before reserving a turn, the host re-hashes the snapshot bytes. If it differs from `artifact_sha` of the pin set: `unknown/snapshot_mismatch`, no reservation, no engine call.
  - Longer than `REVIEW_INPUT_MAX_CHARS` (60,000): no truncation, no engine call, `unknown/too_large`.
- **The reviewer's role description:** the body of the reviewer's `agents/<slug>.md` file, at most 4,000 characters, marked as data.
- **Does not see:** chat history, the maker's prompt, old review verdicts (to avoid anchoring on a previous verdict), paths outside the brain, the agent's tags.

### 4.4 Who can change what

| Object | Changed by | Not changed by |
|---|---|---|
| The `team_pairs` pair | Project owner (Principal `owner`) | Agent, model, tag |
| `goal_team` of a goal | Host at `create`; the project owner detaches the team | Changing the pair afterwards, the model |
| Criteria, permission, quota | As in A1 to A4 | The reviewer |

### 4.5 Tags are not a team (0.100.0)

Since 0.100.0 an agent carries several **tags** (`docs/dev/agent-tags.md`). Tags only classify and help find agents:
- Tags do **not** choose the reviewer, do not filter the Reviewer field list, do not form pairs.
  - The list is built from Resonance status, not from tags.
  - The picker may show tags next to the name for easy recognition, but they are only labels.
- Tags do **not** grant permission, do not change the quota, do not turn Resonance on.
- Tags are **not** a chat group. Adding a tag does not add the agent to a team chat group, and an A5 team does not create a chat group.
- Renaming or deleting a tag does not touch `team_pairs` or `goal_team`, since both are stored by `agent_key`.
- Deleting an agent (A1 key retirement) leaves the pair pointing at a retired key. A goal that has a team with that key is blocked as `reviewer_retired` (section 7.3). A new agent with the same slug or the same tag does not replace the old key.

## 5. The make and review loop

### 5.1 Team state on a revision

The goal state is still the existing `run_state`/`block_reason`. A5 adds new wait reasons and block reasons, and does not add a parallel state machine.

| Observable state | Meaning | Entered when | Left when |
|---|---|---|---|
| `working` | The maker agent has a turn | An existing work reason (A2), or `review_changes` | The turn ends, a version is accepted |
| `waiting/review_pending` | The version passed the objective check, waiting for review | `_settle` sees the objective criteria pass but there is no valid review for the current pin set | The `review_due` or `review_retry` reason is served |
| `reviewing` | The reviewer has a turn | The `review` action starts | A verdict is written |
| `waiting/review_changes` | The review asks for changes, waiting for a maker turn | A `needs_changes` verdict with rounds left | A new maker turn |
| `waiting/human_confirmation` | The review passed, still waiting for the owner to confirm | There is a `human_confirmation` criterion | As A4 today |
| `waiting/source_drift` | The target file differs from the accepted version | Section 5.5 | The file is restored to the exact bytes, or a new version is validly accepted through A4 |
| `succeeded` | Passed | Objective pass, valid review `pass`, human confirmation (if any) passed, no out-of-band edit | End |
| `blocked/review_rounds` | Out of fix rounds | The `max_rounds + 1`-th (3rd) valid `needs_changes` verdict of the revision (section 5.4) | The project owner detaches the team, cancels, or edits the goal (new revision) |
| `blocked/review_unknown` | The review gave no verdict | `unknown` retries exhausted by the rules (section 6.4) | As above |
| `blocked/review_input` | The version cannot be reviewed by a model | `too_large` or `snapshot_mismatch` (permanent error, section 5.2) | A human handles it: a smaller new version, edit the goal, detach the team |
| `blocked/budget_maker`, `blocked/budget_reviewer` | A role's share of turns is used up | `begin_action` cannot reserve a turn for that role | As `review_rounds` |
| `blocked/reviewer_off`, `reviewer_missing` | The reviewer is temporarily unusable | Review-role gate (section 7.3) | The project owner turns it back on (or confirms the file) with the same key; the current version is reviewed again (section 7.3) |
| `blocked/reviewer_retired` | The reviewer key is retired | Review-role gate | Only the project owner detaches the team or cancels; a new key with the same slug does not replace it |

Transition diagram (one revision):

```
maker turn -> accepted version (A4) -> objective check
   target file differs from accepted version -> waiting/source_drift (section 5.5), no review, no model call
   objective check not_met      -> maker turn (A2 rule, maker's share of turns)
   objective check unknown      -> wait or retry as before, no review
   objective check met          -> is there a valid review for the current pin set?
        yes, pass               -> human_confirmation? -> waiting_human : succeeded
        yes, needs_changes      -> rounds left? -> review_changes -> maker turn : blocked/review_rounds
        yes, unknown (permanent) -> blocked/review_input
        yes, unknown (temporary) -> can retry? -> review_retry : blocked/review_unknown
        not yet                 -> review_due -> review turn -> write verdict -> back to the check
```

This order is deliberate: **review runs only on a version that has passed the objective check and still has its exact bytes**, so no review turn is spent on a version still missing something checkable by code or on a version being hand-edited.

### 5.2 The review turn contract

**Input** (section 4.3) plus the host's fixed instruction:
- Treat the version as not passing by default; give a `pass` verdict only when every criterion clearly passes.
- Return exactly ONE JSON object, nothing else.

**The only valid output:**

```json
{"verdict": "pass" | "needs_changes",
 "criteria": [{"index": 0, "ok": true, "reason": "..."}],
 "fixes": "..."}
```

**Reading the verdict (fail closed):**
1. Strip one ```` ```json ```` fence if present; what remains must be exactly one JSON object. No regex hunting in free text.
2. `verdict` is one of the two values above. `criteria` covers exactly every criterion index that was sent, and each entry has a boolean `ok`.
3. Contradictions become `unknown/inconsistent`: `pass` with an `ok: false` entry, or `needs_changes` where every entry is `ok: true` and `fixes` is empty.
4. Any other violation: `unknown/parse_error`. Engine error: `unknown/engine_error`. Broken evidence storage: `unknown/storage_error`. Restart while running: `unknown/interrupted`.
5. Unknown fields are ignored and recorded in the event. No field can change criteria, permission, quota or role.

**Two kinds of `unknown`:**
- **Temporary** (`parse_error`, `inconsistent`, `engine_error`, `storage_error`, `interrupted`): may be retried per section 6.4.
- **Permanent** (`too_large`, `snapshot_mismatch`): detected BEFORE reserving a turn, cost no turn, no engine call, never retried automatically. The goal goes to `blocked/review_input` and waits for a human. `HB.FIXED_ERRORS` adds these two codes.

**Pin:** the `review` action records, at start, the exact pin set (section 5.5) and `bundle_ref` (section 5.6). `criteria_hash` is the sha256 of the normalized JSON of the revision's criteria; the host keeps it, it does not come from the model.

**Writing the verdict** (one `BEGIN IMMEDIATE` transaction):
- CAS the `reviews` row from `running` to `done` by `action_id`.
- Re-check the pin set against the action. On mismatch write `review_mismatch`; the verdict is not used.
- A second write with the same `action_id` is ignored: a resent result does not double up and does not spend another turn.

### 5.3 Feedback returning to the maker agent

- A `needs_changes` verdict with rounds left adds the reason `review_changes` (class `FIX`, section 10; maker's share of turns; `source_ref = rc:<review_id>`).
- The next maker turn uses the existing `_work_prompt`, plus a block "Reviewer feedback (data)": the criteria with `ok: false` and their reasons, and `fixes` (at most 4,000 characters). The previous version goes through `prev_text` as it does today.
- In chat, the maker agent sees the feedback on the card (section 11); a chat turn does not open by itself.

### 5.4 Number of rounds and ending

- `max_rounds = 2`: the first version plus two fixes following review. Pinned in `goal_team` at creation.
- **Counting rounds.** When a VALID `needs_changes` verdict is written, the host counts `k` = the number of `reviews` rows that are `done`, `verdict='needs_changes'`, with an empty `reason_code`, for the current revision, **including the row just written**. The counter is durable, not taken from the displayed log.
  - `k ≤ max_rounds` (k = 1 or 2): add `review_changes rc:<review_id>`. The first two `needs_changes` verdicts give the first and second fix turns.
  - `k > max_rounds` (k = 3): `blocked/review_rounds`, no fix turn is added.
  - Check `k ≤ max_rounds` after counting the row just written. Do not count first and then compare `< 2`, because that loses the second fix turn.
- **Invalid verdicts do not count as a round:**
  - `review_mismatch`: the pin set of the verdict differs from the action.
  - `stale`: at write time the pin set already differs from the current state because the revision, the publish mark or the reviewer version changed.
  - These two kinds are stored with the matching `reason_code`, do not count toward `k`, and do not produce `review_changes` for the version in use.
- A new revision (the project owner edits the goal in chat) restarts the round count from 0 but does **not** refund turns already used.
- Out of rounds: `blocked/review_rounds`, notice `goal.review_exhausted` (a must-send type). No loosening the rounds by itself, no changing the reviewer by itself.

### 5.5 The pin set, old reviews and out-of-band edits (R5)

**The accepted version** of the current revision is the A4 publish mark of the product file: the `published(goal_id, path)` row with its `sha256` and `action_id`.
- Its snapshot is the evidence tied to exactly that `action_id`, or to the `sub:<id>` of the A4 submission whose `publish_action_id` matches. The evidence must have `content_hash = sha256`.
- With no matching snapshot, it cannot be reviewed: `unknown/snapshot_mismatch` (permanent).

**The pin set of a review** = (`goal_id`, `revision`, `accepted_ref` = `published.action_id`, `artifact_sha` = `published.sha256`, `criteria_hash`, `reviewer_agent_key`, `reviewer_config_version` at review start).

**A review is valid for finalizing** only when all of the following hold at the moment of finalizing:
1. A `reviews` row that is `done`, `verdict = pass`, with the same pin set as the current state:
   - the current revision;
   - the current publish mark (both `action_id` and sha);
   - the current criteria hash;
   - the `reviewer_agent_key` of `goal_team`;
   - the CURRENT `config_version` of the reviewer.
2. The sha of the bytes currently at the target file (the same `current_artifact_ref` function that `_human_verdict` uses) equals the `artifact_sha` of the pin set.

**Cases in which an old review loses its value:**
- A new version is accepted through A4 (a background-work turn or a submission from chat): the publish mark changes.
- The revision changes during a review: the verdict is written but carries the old revision.
- The criteria change: the hash changes.
- The reviewer is turned off and on, or the file is lost and then re-confirmed: `config_version` changes (section 7.3).

An old review is kept in the record, never deleted.

**Out-of-band edits** (the user or another program edits the target file, sha `H2` differs from the accepted version `H1`):
- For a goal that has a team, `_settle` treats every mismatch as `waiting/source_drift`, **even when `H2` passes the objective check**. This is where it differs from A2 (A2 finalizes as passing when the hand edit passes). Reason: the review only vouches for `H1`.
- No model call: no redo, no review, no overwrite publish. The file is protected as in A2/A4: the observation mark is recorded separately (`observe_source`), does not change the publish mark, and does not become a baseline.
- `H2` does **not** become the accepted version by itself. A5 adds no path to accept an arbitrary file.
- **Restoring exactly `H1`:** the mismatch ends. The old `pass` review of `H1` is valid again if the pin set still matches, and the goal can be finalized without a model call. If it no longer matches (for example the reviewer changed version), then `review_due` for the new set, reading the `H1` snapshot.
- **`H2` going through a valid A4 acceptance path:** the maker submits with `javis_submit_deliverable`, or a background-work turn redoes it. `host_publish` and `adopt_submission` write a new publish mark with the evidence of those bytes, so there is a new pin set and a new `review_due`.
- **A hand edit while a review is running:** the verdict is written for `H1`. At finalize time the mismatch is seen and the goal waits as above. The verdict is usable only if the file goes back to `H1`.
- **The user wants to keep `H2` without review:** detach the team (`team_detach`). The goal follows the A4/A2 rules as before. This is the project owner's choice, shown on the card.

### 5.6 Review schedule identity (R2)

The store dedups reasons permanently by (`goal_id`, `code`, `source_ref`), including reasons already served (`resonance_store.py` :153, :968-981; confirmed by probe). So each review code carries a `source_ref` that distinguishes every occasion worth running, and is narrow enough that a repeated event does not open a second turn.

| Code | Class | `source_ref` | Added when | Repeated event | Next valid occasion |
|---|---|---|---|---|---|
| `review_due` | `START` | `rb:<revision>:<accepted_ref>:<artifact_sha>:<criteria_hash>:<reviewer_key>:<reviewer_version>` (the full pin set) | `_settle` sees the objective check pass, no mismatch, and no `reviews` row yet for this `bundle_ref` | Same ref: `add_reason_event` returns False, no turn added | A new revision with the same bytes and criteria: a different ref (it includes the revision), so it runs. The reviewer turned back on (new version): a different ref, so it runs |
| `review_retry` | `AUTO` | `rr:<review_id>` (the id of the review row that just ended in a temporary `unknown`) | A temporary `unknown` verdict is written, or `_reconcile` closes a `running` row as `interrupted` | The same review row produces only one ref | The retry after the next error has a new review id, so a new ref. Bounded by section 6.4 |
| `review_changes` | `FIX` | `rc:<review_id>` (the `needs_changes` row) | A `needs_changes` verdict with rounds left is written | Same ref, nothing added | Each `needs_changes` verdict is one fix turn |

**When they are considered and the physical schedule:**
- `review_due` and `review_changes` are event reasons, due immediately (`due_at = now`).
- `review_retry` is scheduled by `ERROR_BACKOFF_S[n-1]` like `error_retry`, where `n` is the **charged count** of the pin set (defined just below).
- The three codes have their own obligation (slot) `review`, and do not replace the maker's `retry` or `check` schedule.

**Recovery after a restart:**
- Both the reasons and the `reviews` rows are durable.
- The `review` action only schedules `action_recovery` when the lock expires: that schedule **only reconciles by code**, and never opens a model turn. The base code already does this for every action that is not `work` (`resonance_store.py` :1524-1527). It does not use `recovery` (the maker's AUTO class), so a restart does not wrongly call the maker or call the review early.
- When `action_recovery` wakes, `_reconcile` meets a `review` action still `running` (the lock has expired, and it cannot be determined whether the engine ran):
  - the `reviews` row becomes `failed/interrupted`, `charged` stays 1 (the turn and the count are still charged);
  - **only after that** is `review_retry rr:<id>` added, scheduled by backoff (idempotent by ref), and only if the rule in 6.4 still allows it.
- Two processes waking at the same time: the CAS `claim_wake` and the goal lease allow only one action.

**Classification:** `CLASSES` still maps one code to one class. The first run and the retry use two separate codes; the class is not inferred from data.

**Sequence number and charged count of a pin set (round 3):** two separate concepts.
- **`reviews.seq`**: the row sequence number, increasing, unique per (`bundle_ref`, `seq`). Each `begin_action(review)` inserts a new row. Used for audit and idempotency; never reused or deleted.
- **`reviews.charged`**: 1 when the row is inserted (the turn is reserved), goes back to 0 **only** when the host confirms the engine has not run, in the refund transaction (section 6.2).
- The pin set's **charged count** `n` = the number of rows with `charged = 1` for that `bundle_ref`. This is the only counter for the retry ceiling (`n ≤ 3`) and for the backoff index.
  - A `cancelled/not_run` row that the host has confirmed is excluded.
  - A row that may have called the engine (`done`, an error after the engine, `failed/interrupted`, cancelled when the engine may have run) is never excluded.
- Refunding the budget, lowering `charged`, returning the reason to `pending` and closing the action all happen in the SAME transaction, guarded by a CAS on the action (`running` to `cancelled`). So a repeated refund or a reopened store does not subtract twice and does not grant an extra retry.

## 6. Split quota (R4)

### 6.1 One ledger, two shares

- **One ledger:** `goals.budget_calls` and `calls_used` as today, with the same ceiling `JAVIS_RESONANCE_CALL_CEILING`.
- **Split into shares:** table `team_calls(goal_id, role, cap, used)`.
  - A goal that has a team: `budget_calls = 8`, maker 4, reviewer 4. The sum of the role shares equals `budget_calls`, so no role can run on the other's "spare" turns.
  - A goal without a team keeps `GOAL_DEFAULT_CALLS = 6`.
- **The role is recorded in the action intent:** `begin_action` takes and stores `role` in `intent_json` (`work` gives `maker`, `review` gives `reviewer`). Every refund path uses the stored role, and does not guess from the state at refund time.
- No raising the ceiling by itself, no creating a replacement agent, no borrowing the other role's share.

### 6.2 Table of every path that reserves, refunds and takes over a turn

Applies to a goal with an `active` `goal_team`. "Same transaction" means the `BEGIN IMMEDIATE` transaction already open on that path.

| Path | `goals.calls_used` | `team_calls` | Note |
|---|---|---|---|
| The goal-forming step (`reserve_ledger_call` "framer") | Its own ledger, belonging to no goal | No | Runs before the goal exists, as today; not part of the 8 turns |
| `begin_action(kind='work')` not using a hold turn: first version, `retry_not_met`, `error_retry`, `recovery`, `feedback` (A3, class `NEW`), `review_changes` | +1 | maker +1, same transaction, condition `used < cap` | If any condition fails (ceiling, `calls_used < budget_calls`, role share), nothing is reserved and it returns `budget_maker` |
| `begin_action(kind='review')` | +1 | reviewer +1, same transaction | As above, returns `budget_reviewer` |
| `begin_action(kind='work')` using an A3 hold turn (`use_hold`, `require_hold`) | 0 (takeover) | 0 | Does not happen for a goal with a team: lane M is off so there is no hold turn (6.3). The store re-checks: a team plus `use_hold` raises `ConflictError` |
| `begin_experiment` (an M5 trial, hold turn `method_followup`) | Unchanged | No | The **store refuses** when an `active` team exists: returns None, the `trial_pending` lesson goes to `skipped/team_goal` |
| `begin_action(kind='trial')` | 0 (the trial was reserved earlier) | No | Does not happen: there is no trial |
| `abort_action` (cancel after the intent, before the engine) and `release_call(action_id)` (the engine could not be built or was blocked before the call, `_ReservedCall.release`) | -1 | the role in the intent -1 | **One single refund function** `_refund_not_run(c, action_id)` for a goal with a team, one transaction. CAS the action from `running` to `cancelled/not_run`; if it does not match, do nothing. If it matches: subtract from `calls_used` and from the role; the `reviews` row (if any) goes `running` to `cancelled`, `charged = 0`; the served reason goes back to `pending`; its `action_recovery` schedule is removed. A `running` row is never left behind after a refund. A goal without a team keeps the current path |
| `release_trial_call`, `finish_experiment(refund)`, `_release_hold` | Does not happen | No | Exist only for trials and hold turns, which a goal with a team does not have |
| Cancelling a goal when the engine may have run | No refund | No refund | The late result is not used |
| `_reconcile` meets a `running` action whose lock has expired | No refund | No refund | `work`: an `interrupted` error turn as in A2. `review`: `failed/interrupted`, `charged` stays 1, and only then `review_retry` is added (section 5.6) |
| `team_detach` | Unchanged | Kept as a record, not deleted | After detaching: the goal runs as in A4 on the rest of `budget_calls` (8 minus used); lane M can run again under the A3 rules |
| The maker agent's chat turn (A1, A4) | Not counted (as today) | No | Reviewing a submission from chat counts toward the reviewer's share |
| A3 reaction on the card | No model call | No | |

**Not counted twice:**
- The hold-turn takeover path does not exist on a goal with a team.
- Every refund goes through `_refund_not_run`, a CAS on exactly that action (`running` to `cancelled`), so a repeated refund, a refund after reopening the store, or an `abort_action` after a `release_call` on the same action does not subtract twice.

### 6.3 A3 lane M when a team exists

**Choice: temporarily do not automatically try a new way of working on a goal with a team**, checked at the store (`begin_experiment`), not only at the decision step.
- Reason: a trial reserves several turns at once plus one product turn. Folding that into the maker's 4 would almost always eat the fix turns that follow a review. Adding a separate share would require raising the quota, which the review forbids doing by itself.
- Display: the lane M lessons of a goal with a team move to `skipped/team_goal`. The card says "Working in maker and reviewer mode: not trying new ways of working for now".
- Lane F (lessons from feedback) does not call the model outside the normal maker turn, so it does not change.
- After `team_detach`, lane M runs again under the A3 rules.

### 6.4 Spare turn and retries

The A2 rule (`auto_allowed`): an `AUTO` turn runs only when more than `AUTO_RESERVE_CALLS = 1` turns remain. For a goal with a team, "remaining" is `min(budget_calls − calls_used, cap − used of that role)`.

| Class | Example | Can use the role's last turn? | Own limit |
|---|---|---|---|
| `START` | First version (`created`), `review_due` | Yes | Once per pin set |
| `NEW` | New message or feedback from the user (`feedback`) | Yes | As A2 |
| `FIX` (new) | `review_changes` | **Yes** | `max_rounds = 2` per revision |
| `AUTO` | `retry_not_met`, `error_retry`, `recovery` (maker); `review_retry` (reviewer) | **No**: the role must have at least 2 turns left | maker: `ERROR_MAX_FAILS = 3` errors per streak, `STALL_AFTER = 2`. reviewer: at most 3 **charged** attempts per pin set (the number of `charged = 1` rows, section 5.6); a turn cancelled before the engine does not count |

**Why `review_changes` is class `FIX`, not `AUTO`:**
- The probe confirmed: with `AUTO`, a role with exactly one turn left cannot run the fix turn, which makes "two fixes" a false promise.
- A fix turn is like a new user message: it is produced by a verdict from outside the maker role, and it already has its own ceiling (the number of rounds).
- The spare turn is still kept for automatic retries.

**The correct promise of 4 + 4** (replacing the D6 sentence of round 1):
- **Maker role:** the first version and two fixes following review, plus one spare turn.
  - The spare turn is used for one automatic retry when at least 2 turns remain, or for a new user message.
  - Each error or `not_met` that must be retried before a passing version appears eats one turn. When the spare turn is gone, the next error costs a fix round.
- **Reviewer role:** review of the first version and the two fixed versions, plus one spare turn.
  - The spare turn is used for one `unknown` retry when at least 2 turns remain, or for reviewing the version after a new user message.
  - No retry may use the role's last turn.
- `ERROR_MAX_FAILS = 3` is still the error ceiling of the maker's streak. With 4 turns, the streak hits the turn ceiling or the error ceiling, whichever comes first. The design does not promise "both fix rounds AND three retries".

### 6.5 Budget trace tables

Columns: which turn of the goal, role, reason (class), result, (maker used/4, reviewer used/4, total/8), next decision.

**V1. Success, two fix rounds, no errors**

| # | Role | Reason (class) | Result | (m, r, total) | Next |
|---|---|---|---|---|---|
| 1 | maker | `created` (START) | version H1, objective pass | (1, 0, 1) | `review_due rb:H1` |
| 2 | reviewer | `review_due` (START) | `needs_changes` (round 1/2) | (1, 1, 2) | `review_changes rc:1` |
| 3 | maker | `review_changes` (FIX) | H2, pass | (2, 1, 3) | `review_due rb:H2` |
| 4 | reviewer | `review_due` (START) | `needs_changes` (round 2/2) | (2, 2, 4) | `review_changes rc:2` |
| 5 | maker | `review_changes` (FIX) | H3, pass | (3, 2, 5) | `review_due rb:H3` |
| 6 | reviewer | `review_due` (START) | `pass` | (3, 3, 6) | `succeeded` |

1 + 1 spare turns left unused.

**V2. One maker error before the first version**

| # | Role | Reason | Result | (m, r, total) | Next |
|---|---|---|---|---|---|
| 1 | maker | `created` (START) | `engine_error` | (1, 0, 1) | `error_retry`: 3 left >= 2, allowed |
| 2 | maker | `error_retry` (AUTO) | H1, pass | (2, 0, 2) | review |
| 3 | reviewer | `review_due` | `needs_changes` 1/2 | (2, 1, 3) | |
| 4 | maker | `review_changes` (FIX) | H2, pass | (3, 1, 4) | |
| 5 | reviewer | `review_due` | `needs_changes` 2/2 | (3, 2, 5) | |
| 6 | maker | `review_changes` (FIX), exactly 1 left | H3, pass | (4, 2, 6) | `FIX` can use the last turn |
| 7 | reviewer | `review_due` | `pass` | (4, 3, 7) | `succeeded` |

Both fix rounds are covered; the maker's spare turn was used by the error. A new user message after that: `blocked/budget_maker`.

**V3. Two maker errors**

| # | Role | Reason | Result | (m, r, total) | Next |
|---|---|---|---|---|---|
| 1 | maker | `created` | error | (1, 0, 1) | `error_retry`: 3 left, allowed |
| 2 | maker | `error_retry` | error | (2, 0, 2) | `error_retry`: 2 left >= 2, fails 2 < 3, allowed |
| 3 | maker | `error_retry` | H1, pass | (3, 0, 3) | |
| 4 | reviewer | `review_due` | `needs_changes` 1/2 | (3, 1, 4) | |
| 5 | maker | `review_changes` (FIX) | H2, pass | (4, 1, 5) | |
| 6 | reviewer | `review_due` | `needs_changes` 2/2 | (4, 2, 6) | No maker turn left |
| - | | | | | `blocked/budget_maker`, notice `goal.review_blocked` |

Two errors cost one fix round. This is the behavior stated in 6.4.

**V4. Review `unknown` then retry**

| # | Role | Reason | Result | (m, r, total) | Next |
|---|---|---|---|---|---|
| 1 | maker | `created` | H1, pass | (1, 0, 1) | |
| 2 | reviewer | `review_due` (seq 1, charged count 1) | `unknown/parse_error` | (1, 1, 2) | `review_retry rr:1`: 3 left >= 2, n = 1 < 3, allowed |
| 3 | reviewer | `review_retry` (AUTO, seq 2, charged count 2) | `pass` | (1, 2, 3) | `succeeded` |

**V5. The reviewer has exactly one turn left when it meets `unknown`**

| # | Role | Reason | Result | (m, r, total) | Next |
|---|---|---|---|---|---|
| 1 to 5 | | as V1 up to and including turn 5 | | (3, 2, 5) | |
| 6 | reviewer | `review_due` H3 | `unknown/engine_error` | (3, 3, 6) | `review_retry`: reviewer has 1 left, AUTO needs >= 2, NOT allowed |
| - | | | | | `blocked/review_unknown`. The reviewer's last turn is kept for reviewing the version after a new user message |

**V6. A version that is too large**

- `review_due` of H1: the `too_large` check runs before reserving a turn.
- (m, r) unchanged; `blocked/review_input`; no engine call; no automatic retry.

**V7. Cancel, takeover, detach, restart**
- Cancel before the review engine: `_refund_not_run` refunds (total -1, reviewer -1). The review row is `cancelled/not_run`, `charged = 0`. `review_due` goes back to `pending`.
- Cancel when the engine may have run: no refund.
- Restart while a review is running: no refund, `failed/interrupted`, `review_retry` under the AUTO rule.
- Detach the team in state (3, 2, 5): `team_calls` keeps (3, 2). The goal has 3 turns left under the A4/A3 rules.

**V8. A cancel before the engine does not eat the retry ceiling (round 3)**

| Action | Result | seq | charged | n (charged count) | (m, r, total) | Next |
|---|---|---|---|---|---|---|
| maker `created` | H1, pass | | | | (1, 0, 1) | `review_due` |
| review 1 | Cancelled before the engine (`_refund_not_run`) | 1 | 0 | 0 | (1, 0, 1) | `review_due` back to `pending` |
| review 2 | The engine could not be built (`release_call(action_id)`) | 2 | 0 | 0 | (1, 0, 1) | `review_due` back to `pending` |
| review 3 | The engine ran, `unknown/engine_error` | 3 | 1 | 1 | (1, 1, 2) | `review_retry rr:3` scheduled at `ERROR_BACKOFF_S[0]`: reviewer has 3 left >= 2, n = 1 < 3, allowed |
| review 4 (after backoff) | `pass` | 4 | 1 | 2 | (1, 2, 3) | `succeeded` |

Before the retry, `team_calls.reviewer.used = 1`: only the call that really reached the engine is counted.

## 7. Permissions, engines and limits that must be stated honestly

### 7.1 What is enforced where

| Limit | Enforced by | Level of certainty |
|---|---|---|
| The reviewer calls no tools, reads and writes no files, runs no commands | The background engine is built text-only, with tools blocked and an empty working directory; `pick_text_only_link` returns None if it cannot block them | Enforced by engine configuration, like every background-work turn today |
| Reviewer words do not become a product | The `review` action has no submit path: the host only reads the verdict and does not call `submission_from_output` | Enforced by host code |
| The reviewer does not change criteria, permission, quota or role | The output has only three fields; the host ignores every other field | Enforced by host code |
| The maker writes only within the permitted scope | A4 grants and bindings | As A4: inside the host contract. A CLI engine's chat turn has native tools (Bash, Write); the hub cannot block native tools (A4 design section 6.3) |
| The review is tied to the exact version | Pin set, CAS in the store, snapshot hash check before sending | Enforced by host code |
| No turn path outside the role ledger | `begin_action` (role) and `begin_experiment` (refuses when a team exists) | Enforced by store code |

### 7.2 Not promising too much

- The two roles use the same background-work model; they are independent in role and data, not in brain.
- A review is the model's opinion and can be wrong. It does not replace the objective check, the guard or human confirmation.
- **Review is not a gate that stops bad content from appearing in the target file:** the version was already published under A4 before review (D1). The card says "not yet accepted" until the review passes.
- **The goal lease only stops two BACKGROUND turns from running at the same time.** It does not lock the maker agent's chat turn. While a background review runs, the maker can still submit a new version or edit the goal in chat. Safety comes from re-checking the pin set when the verdict is written and when finalizing (section 5.5), not from the lease.
- A5 does not give any engine a wider sandbox than today. Engines other than Claude Code are checked only with a fake engine until there is a separate pilot.

### 7.3 The review-role gate and the recovery path (R3)

**Durable identity:**
- `goal_team` pins `reviewer_agent_key`, not the version.
- `agent_key` stays the same through off, on, `missing` and re-confirming the same file (`confirmed_same`, :555).
- The key changes only when the agent is retired (deleted via the host, or confirmed as a different agent, `replaced`, :538, :556). It is then a new key, and is never treated as the old reviewer.

**Gate on every wake that has an action:** `agent_gate(reviewer_agent_key)` without a version.
- `agent_off`: `blocked/reviewer_off`.
- `agent_missing`: `blocked/reviewer_missing`.
- `agent_retired`, `agent_unknown`: `blocked/reviewer_retired`.
- Schedule `agent_recheck` as for the maker agent. Review is never silently dropped.

**The version lives only in each review:**
- The `review` action pins `reviewer_config_version` at start; the store re-checks it in `begin_action`.
- A result is valid only when that version equals the current version at finalize time (section 5.5).

**Recovery path when turned off and on again with the same key** (v1 on, v2 off, v3 on):
1. The project owner turns Resonance back on for the reviewer, on the agent page or with the button on the card (section 11). `agent_set_enabled` increments to v3.
2. `wake_agent_goals` (extended): schedules a wake for goals whose `goal_team.reviewer_agent_key` is this key, as well as the goals where this key is the maker.
3. The gate passes. The old `pass` review carrying v1 is no longer valid (different version), so `_settle` adds `review_due` with a `bundle_ref` carrying v3. The ref is new, so dedup does not block it.
4. Re-reviewing costs one reviewer turn.
   - `team_calls`, the round count and the error streak are not reset.
   - The old verdict is not used.
   - A review turn that was running at the time of turning off: its result is written with v1 and not used.
5. Reviewer turns used up: `blocked/budget_reviewer`. The project owner detaches the team, cancels or edits the goal.

**Agent file lost and then re-confirmed:**
- `confirmed_same` keeps the key and increments the version: follows the path above.
- `replaced`: the old key is retired, `blocked/reviewer_retired`; a new agent with the same slug does not replace it.

**Restart while the reviewer is off:** both the reason and the block are durable; the first wake after the restart still blocks with the right reason.

## 8. Stop, turn off, cancel, revoke

| Project owner action | Maker role | Reviewer role | Running turn |
|---|---|---|---|
| Pause a goal | No `work` wake | No `review` wake (same `paused` condition) | Runs to the end; the result is written; no finalizing as passing while paused (as today) |
| Cancel a goal | Stops for good | Stops for good | Before the engine: `abort_action`, refund the right role. May have run: no refund, the result is not used |
| Revoke write permission (A4) | As A4: an uncommitted version becomes `stale`, the binding is `dead`, the goal pauses | No permission to revoke; stops with the goal | As A4 |
| Re-grant permission | Old turns do not benefit from the new permission (A4 `authority_clock`) | The old review keeps its value if the pin set still matches; a new version needs a new review | |
| Turn off the maker agent | `blocked/agent_off` as A1 | Does not run (the goal is blocked) | As A1 |
| Turn off the reviewer agent | Cannot finalize as passing | `blocked/reviewer_off` | The verdict of a running turn is written but not used (the version changed) |
| Turn the reviewer agent back on | | Section 7.3: review the current version again, costs one turn | |
| `team_detach` | Continues under the A4 rules | The role no longer exists | A running review turn: the result is written, not used |
| Guard blocks | As today | No review while blocked | A review does not remove the guard |

## 9. Store

### 9.1 New tables

Only tables are added, no columns added to tables that predate A1.

```sql
CREATE TABLE IF NOT EXISTS team_pairs (
  maker_agent_key TEXT PRIMARY KEY, brain_id TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  config_version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL, by TEXT NOT NULL,
  CHECK (maker_agent_key <> reviewer_agent_key));

CREATE TABLE IF NOT EXISTS goal_team (
  goal_id TEXT PRIMARY KEY, maker_agent_key TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL,              -- durable identity; does NOT pin the version (section 7.3)
  reviewer_version_at_attach INTEGER NOT NULL,   -- for display and the record only, not used at the gate
  pair_config_version INTEGER NOT NULL, max_rounds INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','detached')),
  created_at REAL NOT NULL, detached_at REAL, detached_by TEXT);

CREATE TABLE IF NOT EXISTS team_calls (
  goal_id TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('maker','reviewer')),
  cap INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (goal_id, role),
  CHECK (used >= 0 AND used <= cap));

CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, revision INTEGER NOT NULL,
  bundle_ref TEXT NOT NULL,                      -- rb:<revision>:<accepted_ref>:<sha>:<criteria>:<key>:<version>
  accepted_ref TEXT NOT NULL, artifact_sha TEXT NOT NULL, snapshot_evidence_id TEXT NOT NULL,
  criteria_hash TEXT NOT NULL,
  reviewer_agent_key TEXT NOT NULL, reviewer_config_version INTEGER NOT NULL,
  action_id TEXT NOT NULL UNIQUE,
  seq INTEGER NOT NULL,                          -- row sequence number, for audit; never reused
  charged INTEGER NOT NULL DEFAULT 1 CHECK (charged IN (0,1)),  -- 0 only when the host confirms the engine did not run
  status TEXT NOT NULL CHECK (status IN ('running','done','failed','cancelled')),
  verdict TEXT CHECK (verdict IN ('pass','needs_changes','unknown')),
  reason_code TEXT, criteria_json TEXT, fixes TEXT, evidence_id TEXT,
  created_at REAL NOT NULL, finished_at REAL,
  UNIQUE (bundle_ref, seq));
CREATE INDEX IF NOT EXISTS reviews_bundle_charged ON reviews(bundle_ref, charged);
CREATE INDEX IF NOT EXISTS reviews_goal_rev ON reviews(goal_id, revision, status);
```

A review action uses the existing `actions` table with `kind = 'review'`: a new value of an existing column, no schema change. `intent_json` carries `role`, the pin set and `bundle_ref`.

### 9.2 Transactions and recovery

- **Attaching the team:** in the `create` transaction (section 4.2), function `_attach_team`. Not attached in `assign_goal`.
- **Starting a review:** `begin_action(kind='review')` does the following in one transaction:
  - the goal lease;
  - the maker-agent gate (as today) and the reviewer gate (key, status, enabled; version equal to the version pinned in the intent);
  - the ceiling, `calls_used`, `team_calls` for the reviewer role;
  - insert `reviews(status='running', seq = the largest seq of the pin set + 1, charged = 1)`;
  - serve the reason;
  - schedule `action_recovery` (reconciliation only, section 5.6), not `recovery`.

  The `too_large` and `snapshot_mismatch` checks run BEFORE this transaction, with no reservation.
- **Review finished:** store the evidence (raw output) first. Then one transaction writes the verdict (section 5.2), closes the action, and adds the next reason.
- **Cancel before the engine, or the engine could not be built:** `_refund_not_run` (section 6.2), shared by `abort_action` and `release_call(action_id)`.
- **Restart:** `_reconcile` per section 5.6.
- **Evidence storage error:** `unknown/storage_error`, the turn is charged.

## 10. Schedule (A2) and feedback (A3)

- **New reason codes:**
  - `review_due` (`START`), `review_retry` (`AUTO`), `review_changes` (`FIX`).
  - `CLASSES` adds three codes. `HB.decide` adds class `FIX`: it opens a `work` turn, is not blocked by the spare turn, and is blocked by `max_rounds` (checked when the reason is added).
  - `HB.FIXED_ERRORS` adds `too_large`, `snapshot_mismatch`.
  - No class polls the model periodically. Changing the policy increments `POLICY_VERSION` to `heartbeat.v3`.
- **Identity and physical schedule:** section 5.6.
- **Concurrency:** the CAS `claim_wake` and the goal lease guarantee one background action at a time. The maker role and the reviewer role do not run in parallel on the same goal (the lease does not block chat, section 7.2).
- **A3 feedback:** a reaction on the review card only changes how a notice is presented (like every reaction), does not change the review verdict, does not change the schedule. Lane M is off when a team exists (section 6.3).

## 11. Minimal UI

- **Agent page:** the **Reviewer** picker (section 4.2), shown only when the agent has Resonance on. Each agent's tags may appear next to its name as labels only (section 4.5).
- **Goal card:** uses the A1 to A4 card frame, adding one team line when there is a `goal_team`:
  - "Maker: <agent name> · Reviewer: <agent name>";
  - "Reviewed version: <8-character sha> · Pass / Needs changes (round 1/2) / Unclear";
  - the wait reason as a sentence a person can read: "Waiting for <reviewer> to check version <sha>", "Waiting for <maker> to apply the feedback", "The target file was edited outside Jarvis 007: waiting for an accepted version";
  - "Calls left: maker 3/4 · reviewer 2/4".
- **Project owner buttons on the card** (shown only when there is a reason):
  - `blocked/reviewer_off`: **Turn the reviewer back on**. Calls the existing Resonance enable API for the reviewer key. The card says up front "the current version will be reviewed again, using one reviewer call".
  - `blocked/reviewer_missing`: leads to the agent page to confirm the file.
  - Every `blocked/review_*`, `blocked/budget_*`, `blocked/reviewer_*`, `waiting/source_drift`: **Drop the review requirement** (`team_detach`), with a confirmation box saying plainly that from now on the goal settles by the usual rules.
- **Review feedback** appears in the expanded part of the card (reasons per criterion and `fixes`), and does not become a separate chat message.
- **New must-send notices:**
  - `goal.review_exhausted`;
  - `goal.review_blocked`: merges the `blocked/review_*`, `blocked/budget_*`, `blocked/reviewer_*` reasons.

  No separate team page is added.
- Old goals assigned through `assign_goal`: the line "This goal predates the team; it has no reviewer".
- **New text goes through i18n** (`vi.json`, `en.json`) per the repo convention; dashboard-only dictionaries (for example `de.json`) fall back to English like every untranslated key.

## 12. Expected API, tools, files

| Change | File |
|---|---|
| Table `_A5_SCHEMA`, store upgrade, snapshot `.pre-0.109.0` | `server/resonance_store.py` |
| `team_pair_set`/`team_pair_get`, `_attach_team` in `create`, `team_calls` in `begin_action`/`release_call` (by `action_id`)/`abort_action`, `begin_experiment` refusal when a team exists, `record_review`, `team_detach`, `wake_agent_goals` for the reviewer | `server/resonance_store.py` |
| `_review_prompt`, `parse_review` (a pure function), building and checking the snapshot, gate 7.3, the team branch in `_settle` (including 5.5), `_review_step`, `_reconcile` for `review`, `_ReservedCall` by `action_id` | `server/resonance.py` |
| Reason codes, class `FIX`, new permanent errors, `heartbeat.v3` | `server/resonance_heartbeat.py` |
| `GET/PUT /resonance/agents/{slug}/reviewer`, `POST .../team-detach`, field `team` in the goal view | `server/resonance_api.py` |
| The Reviewer field; the team line and buttons on the card; i18n keys | `dashboard/` (agent page, `chat-resonance.js`), `dashboard/i18n/vi.json`, `en.json` |
| Restore to 0.108.0 | `tools/resonance_restore_pre_a5.py` |
| Tests | `tests/python/test_resonance_a5_team.py`, `test_resonance_a5_budget.py`, `test_resonance_a5_rollback.py`, `tests/js/test_resonance_a5_ui.js` |

No tool is added for the model: the reviewer calls no tools; the maker agent uses `javis_submit_deliverable` as in A4.

## 13. Upgrading and downgrading

- **On upgrade:** the first time the A5 code opens a pre-existing store, `_backup_before("team_pairs", ".pre-0.109.0")` copies the store once with the SQLite backup API, then creates the A5 tables. Same pattern as A1 to A4: if the marker table exists, it does not copy again. Old goals have no `goal_team` and run as in A4.
- **Downgrading the right way:** shut down Jarvis 007, run `tools/resonance_restore_pre_a5.py`, then run 0.108.0. The script keeps the current store as `post-0.109.0-<timestamp>` and only then writes the snapshot.
- **Downgrading without restoring: not supported.** Stated plainly in the CHANGELOG. Reasons:
  - The 0.108.0 code ignores the A5 tables, so a goal with a team can be finalized as passing without a review.
  - A `kind='review'` action still `running` is treated by the old `_reconcile` as an ordinary interrupted work turn.
- **Upgrading again after the old code has run:** if the snapshot already exists it is not copied again; the A5 tables are intact. Goals finalized by the old code keep their state, with no retroactive review.

## 14. Performance

- Review adds no periodic polling loop: it runs only when `_settle` adds `review_due` or `review_retry`.
- Checking for a valid review is a query by `reviews_goal_rev` and `bundle_ref`, on the same connection as `_settle`.
- The goal card adds one query of `goal_team` and `team_calls` by `goal_id` inside the existing goal view (already running on a worker thread since 0.88.5, #602); no extra request from the page.
- The review input is taken from stored evidence, with no re-reading of a large file; the limit is 60,000 characters. One re-hash of the snapshot per review turn.
- **Checks:**
  - A test measuring goal view time with 200 goals that have teams stays within the same threshold as `test_resonance_perf.py`.
  - The event loop is not blocked while a review runs (a 10 ms timer clock as in the existing test).

## 15. Acceptance matrix (before coding)

Fake clock, fake engine, no real model. Each case has a valid control.

**Columns:**
- **Turns** is (maker, reviewer, total) used at the end.
- **Model** is the number of times the fake engine is called.
- "Usable result" is which verdict or version may be used to finalize.

**Cases through the real host path:** the cases marked (H) must run through the real host path: `form_goal` with the `javis_goal` tool or `POST /goal-requests`, the real scheduler, the real store. No `goal_team` or `reviews` is inserted into a fixture.

### 15.1 Main flow

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T1 (H) | Make, objective pass, review `pass`, no human confirmation | `succeeded` | (1, 1, 2) | 2 | The `pass` review of H1 |
| T2 (H) | As T1, with `human_confirmation` | `waiting/human_confirmation`, then `succeeded` when the owner confirms the exact sha | (1, 1, 2) | 2 | The review and the confirmation on the same H1 |
| T3 (H) | Review `needs_changes`, the maker fixes, review of the new version `pass` | `succeeded`; two review rows tied to two `bundle_ref` | (2, 2, 4) | 4 | The review of H2 |
| T4 | Review `needs_changes` three times in a row (trace V1 where turn 6 is `needs_changes`): k = 1, 2 produce fix turns; k = 3 blocks | `blocked/review_rounds`, notice `goal.review_exhausted` | (3, 3, 6) | 6 | None |
| T5 | Review output is not JSON, has a missing field, or a contradictory `pass`: three turns in a row | `review_retry` twice (charged count 2, 3), then `blocked/review_unknown` (n = 3) | (1, 3, 4) | 4 | Never treated as a pass |
| T6 | Engine error on the review turn, the next attempt passes (trace V4) | `succeeded` | (1, 2, 3) | 3 | The review with charged count 2 |
| T7 | The reviewer's share is used up while the maker's share remains | `blocked/budget_reviewer` | (k, 4, k+4) | k+4 | Does not borrow the maker's share |
| T8 | The first version and two automatic retries all fail the objective check; the fourth turn is opened only by a new user message (`NEW`) and still fails | After turn 3: wait under the A2 spare-turn rule, no automatic retry. After turn 4: `blocked/budget_maker` | (4, 0, 4) | 4 | No review of a version that fails the objective check |
| T9 | The shared ceiling is hit while the role share remains | Nothing reserved; wait as today | unchanged | 0 more | The ceiling wins over the role share |

### 15.2 Pin set, schedule and concurrency (R2)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T11 | The revision changes while a review runs | The verdict is written with the old revision, not used. A new `review_due` (the ref has the new revision) | (k, +1) | +1 | The review of the new revision |
| T12 | A verdict is written for the wrong goal, wrong reviewer, wrong sha, wrong criteria hash | `review_mismatch`, not used | the turn is charged | +1 | None |
| T13 | The review result is sent twice | One `done` row, the second is ignored | unchanged | unchanged | The first row |
| T14 | Restart after each step: reserved, engine being called, output present but verdict not written, verdict written but not yet `settle`d | Recovery exactly per sections 5.6 and 9.2; no turn lost, no verdict duplicated | the ledger is exact | the count is exact | As the last durable step |
| T37 | Revision 2 keeps the bytes and criteria of the already-reviewed revision 1 | A new `review_due` is added and served (different ref); it does not wait forever | (1, 2, 3) | 3 | The review of revision 2 |
| T38 | A `review_due` event sent twice (two `_settle` runs on the same set) | One reason, one turn | (1, 1, 2) | 2 | One review |
| T39 | `unknown` then retry, with a restart between the two | The retry runs exactly once after the restart; `seq` is continuous, `n` is correct | (1, 2, 3) | 3 | The review with charged count 2 |
| T40 | The project owner turns the reviewer back on (new version) after a `pass` | The new `review_due` with the new version can run | (1, 2, 3) | 3 | The review of the new version |
| T41 | Check the wait reasons, the physical schedule (`wake_reasons`, `wakeups`) and the turn count after each of cases 37 to 40 | No dangling reasons, no orphan schedules | | | |
| T22 | Two simultaneous wakes (a maker reason and a review reason fall due together) | One action runs; the other waits for the lease | the ledger is exact | 1 | |
| T59 | Maker chat submits a new version through A4 while a background review runs | The verdict is written for the old version, not used. `review_due` for the new version | (k, +1) | +1 | The review of the new version. The lease does not block chat (section 7.2) |

### 15.3 Attaching the team (R1)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T31 (H) | Created through the `javis_goal` tool in an agent session whose pair is on | `goal_team active`, `team_calls` 4/4, `budget_calls = 8`, in the same transaction as `goal_agents`; it still passes with `assign_goal` replaced by a function that raises | (0, 0, 0) at creation | 0 | |
| T32 (H) | Created through `POST /goal-requests` | As T31 | | 0 (with a proposal) or 1 framer (its own ledger) | |
| T33 (H) | Creating twice from the same message (same `idempotency_key`), with the pair changed to a different reviewer between the two | Returns the old goal; reviewer, budget, `team_calls` unchanged | unchanged | 0 | |
| T34 | The pair is off at creation | No `goal_team`; runs as A4 | as A4 | | |
| T35 | The reviewer is off exactly at creation (pair on) | `goal_team active`; the first wake is `blocked/reviewer_off`, review is not dropped | (1, 0, 1) if the first version was made | | |
| T36 | An old goal that has spent turns, the project owner assigns it through `assign_goal` to an agent that has a pair | No team; `calls_used` unchanged; card "no reviewer"; event `not_attached_legacy` | unchanged | | Per A4 |
| T25 | A goal created when there is no pair | No `goal_team`; as A4 | as A4 | | |

### 15.4 Reviewer off, on, missing, retired (R3)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T18 | Turn off the reviewer while waiting for a review | `blocked/reviewer_off`, a recheck is scheduled; turning it back on with the same key continues per section 7.3 | unchanged until turned on | 0 when off | |
| T42 | On v1, has a `pass`, off v2, on v3 | One review turn again; `team_calls`, the round count, the error streak are not reset | (1, 2, 3) | 3 | The v3 review |
| T43 | A review is running when it is turned off and then on | The result is written with v1, not used; the v3 review | (1, 2, 3) | 3 | The v3 review |
| T44 | Restart while the reviewer is off | Still `blocked/reviewer_off` after the restart; no model call | unchanged | 0 | |
| T45 | The reviewer file is lost, the project owner confirms `confirmed_same` | Same key, new version, review again | +1 reviewer | +1 | The new-version review |
| T46 | The reviewer is deleted (key retired), a new agent with the same slug and the same tag is created | `blocked/reviewer_retired`; the new key is not accepted; only detach or cancel | unchanged | 0 | |
| T19 | The reviewer's status changes while a review runs | The verdict is an old review, not used; block or review again per the new status | (k, +1) | +1 | |

### 15.5 Budget (R4)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T47 | Trace V1: success, two fix rounds | `succeeded` | (3, 3, 6) | 6 | The review of turn 6 |
| T48 | Trace V2: one maker error | `succeeded`, the second fix turn uses the maker's last turn (`FIX`) | (4, 3, 7) | 7 | |
| T49 | Trace V3: two maker errors | `blocked/budget_maker` after round 2 | (4, 2, 6) | 6 | None |
| T50 | Trace V5: the reviewer has exactly one turn left on `unknown` | `blocked/review_unknown`, no `review_retry` | (3, 3, 6) | 6 | None |
| T51 | A goal with a team has a lane M `trial_pending` lesson | `begin_experiment` returns None at the store; the lesson is `skipped/team_goal`; `calls_used` does not increase | unchanged | 0 | |
| T52 | Cancel before the review engine; cancel after the engine may have run | Before: refund the total and the reviewer, row `cancelled/not_run`. After: no refund | (k, 0) / (k, 1) | 0 / 1 | The late result is not used |
| T53 | `release_call` when the engine is blocked before the review turn | Refund the reviewer role by `action_id` | (k, 0) | 0 | |
| T54 | Detach the team at (3, 2, 5) and then restart | `team_calls` is still (3, 2); the goal has 3 turns left under A4; lane M can run again | kept | | Per A4 |
| T15 | Cancel before calling the review engine | `cancelled/not_run`, both counters refunded | (k, 0) | 0 | |
| T16 | Cancel after the review engine may have run | `failed/cancelled`, no refund | (k, 1) | 1 | None |

### 15.6 Out-of-band edits and the snapshot (R5)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T10 | The project owner hand-edits the file to H2 after the `pass` review of H1, and H2 still passes the objective check | `waiting/source_drift`; no review, no finalizing, no overwrite publish | unchanged | 0 | None (the H1 review does not apply to H2) |
| T55 | A hand edit while the H1 review is running | The verdict is written for H1; at finalize time the mismatch is seen, `waiting/source_drift` | (k, +1) | +1 | Only if the file goes back to H1 |
| T56 | After T10, the file is restored to the exact H1 bytes | `succeeded` using the old H1 review, no model call | unchanged | 0 | The H1 review |
| T57 | After T10, the maker submits H2 through a valid `javis_submit_deliverable` (A4) | A new publish mark; `review_due` for H2; the snapshot is read from the H2 evidence | (k, +1) | +1 | The H2 review |
| T58 | The snapshot evidence has a hash different from `artifact_sha` (corrupted or replaced) | `unknown/snapshot_mismatch`, `blocked/review_input`, no reservation | unchanged | 0 | None |
| T28 | A version over `REVIEW_INPUT_MAX_CHARS` (trace V6) | `unknown/too_large`, `blocked/review_input`; no automatic retry, no tightly spaced wakes | unchanged | 0 | None |

Every 15.6 case also checks: the hash of the bytes actually sent to the fake engine equals `artifact_sha` of the pin set.

### 15.7 Permission, stop, scope

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T17 | Revoke write permission while a review is waiting; re-grant | Paused; after the re-grant, the old review is usable if the pin set matches; old maker turns do not benefit from the new permission | unchanged | 0 | Per A4 |
| T20 | Turn off the maker agent | `blocked/agent_off` as A1; no review | unchanged | 0 | |
| T21 | The guard blocks a version that already got a `pass` review | `blocked/guard`; the review does not remove the guard; `host_publish` does not write | unchanged | 0 | |
| T23 | Evidence storage error for the review output | `unknown/storage_error`, the turn is charged, `review_retry` under the AUTO rule | (k, +1) | +1 | None |
| T24 | `team_detach` while waiting for a review | Finalizes under the A4 rules; a running review is not used | unchanged | | |
| T26 | The reviewer tries to return a field that changes criteria or quota | The field is ignored, an event is recorded; the verdict comes only from the three fields | as T1 | | |
| T27 | A submission in chat (A4) on a goal with a team | Published per A4; the review runs in background work, counted in the reviewer's share | (0, 1, 1) | 1 | |
| T29 | Normal chat with no goal, with an agent that has a team | No goal is created, no review | (0, 0, 0) | 0 | |
| T60 | Rename or delete a tag that the reviewer and the maker both carry | `team_pairs`, `goal_team` unchanged; the Reviewer field list does not change | unchanged | 0 | |
| T30 | Upgrade the store from 0.108.0; restore to 0.108.0 with the script | Exactly one snapshot; the real 0.108.0 code can open the restored store | | | The limit on downgrading without restoring is recorded |

### 15.8 Retry counter, reconciliation schedule, fix rounds (round 3)

| Case | Situation | State, final reason | Turns | Model | Usable result |
|---|---|---|---|---|---|
| T61 | Trace V8: two cancels before the engine (one `abort_action`, one `release_call` because the engine could not be built), then `unknown` on the first real call | A valid `review_retry` after exactly `ERROR_BACKOFF_S[0]`; before the retry `reviewer.used = 1`, `n = 1`; seq 1 to 4 | (1, 2, 3) | 2 | The review with seq 4 |
| T62 | Three cancels before the engine and then `pass` | Not blocked by the retry ceiling; `n = 1` | (1, 1, 2) | 1 | The review of the real call |
| T63 | Cancel after the engine may have run; restart when it cannot be determined whether it was called | `charged = 1`, counted toward the retry ceiling and the budget; `failed/cancelled` or `failed/interrupted` | (k, +1) | +1 or truly 0 | None |
| T64 | Repeated refund: `abort_action` twice, `release_call` then `abort_action` on the same action, reopen the store and refund again | Only the first has an effect; `calls_used`, `team_calls`, `charged`, the reason and the row state stay consistent, nothing subtracted twice | the ledger is exact | 0 | |
| T65 | The engine could not be built on a review turn | The row is `cancelled`, `charged = 0`, no `running` left; the reason goes back to `pending`; no orphan `action_recovery` schedule | (k, 0) | 0 | |
| T66 | Restart while a review is running, then `action_recovery` falls due | Reconciliation by code only: does not open a maker `work` turn, does not call the review before backoff; `review_retry` is added after reconciliation | (k, +1 charged) | 0 at reconciliation | |
| T67 | A `needs_changes` verdict written after the revision or publish mark has changed (`stale`), and a `review_mismatch` verdict | Not counted toward `k`, no `review_changes` produced; the version in use still needs its own review | (k, +1) | +1 | None |

## 16. Decisions

### 16.1 Proposed defaults

D1 to D5 follow the recommendation of review round 1, Q1 to Q5. This is a product configuration, **not yet a permission to run the pilot**.

| # | Decision | Reason |
|---|---|---|
| D1 (Q1) | Review runs AFTER the version is published (the A4 rule is unchanged), BEFORE finalizing as passing. The card says "not yet accepted" until the review passes | Does not change the A4 contract that was already piloted. Review is not a gate that stops bad content at the target file (section 7.2) |
| D2 (Q2) | `budget_calls = 8`, maker 4, reviewer 4, `max_rounds = 2`, no setting to adjust | Fewer settings. The honest promise is in section 6.4: errors reduce the number of fix rounds that can be carried out once the spare is gone |
| D3 (Q3) | The two roles share the background-work model; they differ in identity, instruction and data | Do not advertise two independent models |
| D4 (Q4) | An early confirmation by the project owner does not skip review. The confirmation is stored by the exact sha; if the version changes, the confirmation does not follow | Two different rights (A4 invariant 5) |
| D5 (Q5) | Out of rounds or turns: block, report, wait. There is no quota-raising command yet. `team_detach` is project owner only, and states that it drops the review requirement | Do not turn detaching into a path for the agent to skip checks by itself |
| D6 | Review runs only on a version that has passed the objective check and still has its exact bytes | Do not spend review turns on code errors that can be caught by itself or on a version being hand-edited |
| D7 | The verdict is fail closed; free text is not read. `too_large`, `snapshot_mismatch` are permanent errors | The `verify_agent` step currently defaults to pass on error |
| D8 | The reviewer sees only the hash-checked snapshot, the criteria, the constraints, the role description; it does not see chat, old reviews or tags | Reduce anchoring on the maker and on the previous verdict |
| D9 | Pin the reviewer key (durable) when the goal is created; the version is pinned per review. Turning it back on with the same key reviews the current version again, costs a turn, no reset. A new key with the same slug does not replace it | Fixes R3: a temporary off switch is usable without opening a path to swap the grader |
| D10 | The two roles share the goal lease and do not run in parallel in background work | Reuses A2; the lease does not block chat (section 7.2) |
| D11 | The team is attached in the `create` transaction. Old goals assigned through `assign_goal` have no team | Fixes R1; does not re-split turns already spent |
| D12 | A3 lane M is temporarily off on a goal with a team, checked at the store | Fixes R4; no turn path outside the role ledger |
| D13 | No review turn in chat | A chat turn uses an engine with native tools; "read only" cannot be enforced there |
| D14 | An out-of-band edit does not become the accepted version by itself; a goal with a team waits and does not finalize even if the edited version passes the objective check. **The project owner chose this (option A, 2026-10-12)** | Fixes R5; does not extend the A4 contract. To keep the hand edit, the project owner presses "Drop the review requirement" |
| D15 | Tags take no part in choosing the reviewer, forming the pair, permission or chat groups | The 0.100.0 tag contract |

### 16.2 Locked decisions

- **A hand edit that passes the objective check on a goal with a team: option A** (chosen by the project owner on 2026-10-12). A goal with a team does not finalize on a hand edit; it waits for the file to go back to the reviewed version or for a new version to come through A4. To keep the hand edit, the project owner presses "Drop the review requirement" (`team_detach`). No feature to automatically adopt a hand-edited file is added.
- Q1 to Q5 of round 1 were resolved per the recommendation (D1 to D5).

No point is left for the project owner to decide at the design level. The defaults are still not a permission to pilot.

## 17. Code plan and the boundary of evidence

**Order** (one PR #616, several commits, code review in rounds as for A4):
1. **Store:**
   - `_A5_SCHEMA`, store upgrade and snapshot.
   - `team_pairs`; `_attach_team` in `create` (T31 to T36 through the host path).
   - `team_calls` in `begin_action`; `release_call` by `action_id`; `abort_action` for `review`.
   - `begin_experiment` refusal when a team exists.
   - Store tests: T7 to T9, T14 store part, T15, T16, T30, T51 to T54, T61 to T65.
2. **Review:**
   - `_review_prompt`, `parse_review`: pure-function tests T5, T26, T28.
   - Building and checking the snapshot: T58.
   - `_review_step`, writing the verdict with CAS (T12, T13), recovery (T14, T39).
3. **Finalizing and schedule:**
   - The team branch in `_settle` including 5.5; gate 7.3; codes, class `FIX` and permanent errors in A2.
   - Cases: T1 to T4, T6, T10, T11, T17 to T25, T27, T29, T37 to T50, T55 to T57, T59, T60, T66, T67.
4. **API and UI:**
   - The Reviewer field, the team line and buttons on the card, `team_detach`.
   - JS tests and a sandbox smoke with a fake engine.
5. **Performance and regression:** performance (section 14) and full Resonance regression, including the 0.100.0 tag tests.

**Boundary of evidence:**
- **Before code review:** only the fake engine and reading code. No trial of a real engine without a key (it might fall back to an already signed-in CLI).
- **Real pilot:** a separate request after the code passes review, approved by the project owner in their own words.
  - The proposal will state the concrete number of turns: at most 1 chat turn plus the team's background work.
  - The old pilot quota is not reused.
- One pilot does not prove every engine or every channel.

## 18. Base code check (not an A5 check)

The reviewer's probe `exports/reviews/PR-616-A5-design-r1-probe.py`, run verbatim on the new base (the A5 branch after merging `main` `a02663cb`), a temporary SQLite store, no engine:
- `create` attaches the agent without calling `assign_goal`; calling `assign_goal` afterwards is rejected.
- Turn on/off/on for versions 1, 2, 3; pinning version 1 gets `agent_changed`.
- A `review_due` that was already served blocks the same `source_ref` for a new revision.
- `auto_allowed` rejects `review_changes` and `error_retry` when exactly one turn is left.

The probe exits 0. This is the semantics of the base code that the round 2 design relies on, not evidence that A5 is fixed. The design does not use the probe to claim "no longer reproduces"; the A5 behavior tests are written when the code exists.
