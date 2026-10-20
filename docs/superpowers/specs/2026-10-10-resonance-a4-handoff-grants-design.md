# Resonance A4: multi-engine deliverable submission through one host contract, with scoped permissions

**Status:** design **final** (round 5, fallback option D1), reviewer approved for coding. **The A4 code passed round 5 code review** (`5b5e3ef0`; section 17: I1, I2 accepted; I10 to I16). UI smoke test, pilot runner and one real pilot (11/10, closed by a post-check): [record](../../dev/resonance-a4-verification.md). **Released as 0.96.0** (`d36ebb3e`, PR #604, 11/10/2026; CI `main` run 38146898745 and image build run 38146898746 succeeded; image `ghcr.io/blogminhquy/javis-os:0.96.0`, digest `sha256:8f1751d2…`; VPS has not pulled it yet). A change to the permission mechanism beyond this version must send a design diff for review first.

- **Branch:** `claude/resonance-a4-handoff-grants`, draft PR #604, version **0.96.0** (reserved as 0.90.0; `main` went through 0.91.0, 0.92.1, 0.94.0 and then 0.95.1, so the number was reassigned four times).
- **Round 1** (`5edfc9b6`) not passed: 3 P1, 2 P2 (`exports/reviews/PR-604-A4-design-r1-review.md`, outside git).
- **Round 2** (`99c88447`) not passed: 1 P1, 3 P2, 6 minor notes (`exports/reviews/PR-604-A4-design-r2-review.md`, outside git).
- **Round 3** (`efa1fce3`) not passed: 1 P1, 1 P2, 3 minor notes (`exports/reviews/PR-604-A4-design-r3-review.md`, outside git). The draft, approval, `sealed`, adoption, per-revision locking and legacy parts passed at design level.
- **Round 4** (`bd6ad1d1`): the permission order and three notes passed; the directive receiver still accepted wrong input (`exports/reviews/PR-604-A4-design-r4-review.md`, outside git). Fallback option D1 chosen: **A4 does not grant permission from chat text**.
- The table mapping each review point is in section 16. The architecture and scope stayed unchanged through both rounds.

**Base and inputs:**

- **Base:** the design was written on `main` `33a3c1aa` (0.89.0); the code has merged `main` `1d0b515c` (0.91.0: 0.89.1, 0.89.2, DeepSeek), then `709e3db9` (0.92.1: sign-in, first-run setup screen), `b7e09dbf` (0.92.2: local Ollama with tools), `55bc8e86` (0.94.0: bot views customer images) and `adb103ed` (0.95.1: local Ollama thinking off by default). A1 0.87.0, A2 0.88.0, A3 0.89.0 and the performance release 0.88.5 (#602) are already in `main`.
- **Roadmap:** [agent scope roadmap](2026-10-08-resonance-agent-scope-roadmap.md), section 7 (A4, A5).
- **Delegation inputs** (outside git):
  - Paperclip report of 08/10: `exports/reviews/paperclip-javis-assessment-2026-10-08.md`;
  - supplement of 10/10: `exports/reviews/2026-10-10-resonance-delegation-paperclip-review-supplement.md`.

**Level of evidence:**

- The real code was surveyed at `9716cecf`, which matches `33a3c1aa` in `server/`.
- No model was called. No A4 code or tests existed yet.
- Section 2 is code that was actually read. Everything else is a proposal.

## 1. Goals and out of scope

**A4 goal:** every engine submits the deliverable of a goal under **one host contract**.

> The host determines who is working and pins the permission for that turn. The engine submits content through a path the host checks. The host reads and hashes the bytes itself, stores them as a submission with a receipt, then publishes to the destination itself through the real permission, guard and baseline.

Alongside it come **scoped permissions** learned from Paperclip, at the minimum A4 needs:

- The root scope is set by the project owner, independent of the criteria the model edits.
- The permission of each revision can only narrow from the root scope.
- The permission is pinned to each turn.
- Revocation goes through `generation`.
- It is checked at every point of effect.

A5 reuses exactly this contract for the maker/reviewer pair.

**What the user sees:**

- You hand over a result once.
- **New destination or changed scope:** you click Allow on the card, with the exact file path. Even when the assignment already names the destination, Jarvis 007 still asks once; A4 does not infer write permission from chat text.
- **Scope already granted:** the assistant keeps working on its own, without asking again at each step or each edit.
- **Drafts are kept:** a version the assistant wrote before you allowed it is kept as a draft. When you click Allow, Jarvis 007 publishes exactly that version, and this step does not call the model. A goal with no draft yet: after you allow it, the background job runs on the usual per-turn budget.
- The goal card shows: what it may do, on which file, at most how many turns, whether it may contact others, and a Revoke button.

**Kept unchanged:**

- **A1 to A3 quota rules:** reserving within a transaction, the shared cap, "refund if not yet called, keep if already called", `call_holds`.
- **Publish rules:**
  - valid destination: a path inside the brain, extension `.md`/`.txt`, at most 1MB, not in a forbidden folder;
  - the guard checks the candidate version;
  - CAS on `published`;
  - the existing `_gate` checks: goal active, not paused, guard, assistant, baseline.
- **One deliverable per goal.** The destination is `_deliverable_rel`, i.e. the **first** `artifact_contract` path of the revision. A second path in the criteria (if any) may only be read by the host's evaluator for grading; it does not go into the prompt and may not be written.
- **Background turns** still only produce text.
- **Store:** existing tables get no column changes. A4 only adds new tables.

**Out of scope for A4:**

- **Two-role teams, sub-jobs, truly granted child permissions:** these belong to A5. A4 has a parent/child mechanism because the revision permission is itself a child of the root scope (section 5), but there is no path for delegating work to a second assistant.
- **Sandbox for engines with native tools:** A4 does not promise to block native Bash/Write (section 6.3).
- **Opening background jobs to Codex, Grok, Antigravity.**
- **Paperclip's company model, roles, trust rules and policy engine.**
- **Several deliverables per goal.**
- **Granting permission from chat text.** A4 has no directive receiver and no `owner_message` permission source (section 5.2.1, D1).
- **Permission expiry (`expires_at`).** Not in A4 (D10).
- **Continuing a goal that has A4 permissions with 0.95.1 code after a downgrade.** Not supported (section 7.4).

## 2. Current state: what is reused and the gaps (code at `9716cecf`)

| Already exists | Where in the code | Gap A4 fills |
|---|---|---|
| Turn identity attached by the host: `kenh`, `session_id`, `message_id`, `agent{key, slug, config_version}`. Passed through `X-Javis-Turn` (Claude, Codex) or in-process (API engines). The turn key lives only in the process and is destroyed when the turn ends (`turn_context.reset`) | `turn_context.make/current/issue_key/resolve_key`, `main.run_turn`, `mcp_hub` | A turn carries no goal, revision, permission, `generation` or start time. Grok and Antigravity do not pass the turn key |
| Two-layer assistant gate, version pinning | `resonance.agent_gate`, `resonance_store._agent_block`, `begin_action`, `finish_handoff` | No scope by path or by operation |
| `CapabilityGrant` (workflow replan) | `agent_runtime.py` | In memory only, not stored, not revocable. A4 does not extend this class |
| SQLite quota, turn refund, `call_holds`, reconciliation | `resonance_store.begin_action/finish_action/reconcile_holds` | Sufficient. Permission adds no counter |
| Text-only background work: the host writes `output_root/<action_id>.md` and hashes by reading it back | `resonance.run_once`, `_work_post_core` | `_work_post_core` writes the receipt, publishes and grades in one pass. There is no submission before the publish step (section 4.4) |
| Publish: path check, guard, CAS | `resonance._publish`, `_gate` | **The branch where the target file already has the same hash calls `set_published` and returns `same` before `begin_action`.** There is no permission gate. Reading then writing has no ordering point against revocation |
| Claude chat handoff: Write receipt by id, compare bytes | `note_turn_event`, `handoff_after_turn`, `finish_handoff` | **`finish_handoff` assumes the file is already at the destination and writes `published` immediately**; it copies no draft. The adoption event key is `adopt:<revision>` |
| Opening a handoff when creating or editing a goal in a chat turn | `resonance_store._open_handoff` (key `(goal, revision)`, `INSERT OR REPLACE`, `message_ref`) | The store allows **two goals in the same session, with the same destination, both `pending`**. One message that creates and then edits the same goal makes two handoff rows by revision |
| Handoff expiry after restart | `handoff_gate` (owner is per process) | Does not yet distinguish "the turn no longer accepts calls" from "a submission the host has accepted can still be completed" |
| Reconciling interrupted background turns | `resonance._reconcile` (only settles the receipt), `_publish_latest` (publishes bare output) | No submission, no link yet |
| The model may edit criteria and the destination path when a quote appears in the message | `resonance.validate_proposal`, `revise_goal` | **A quote is not an approval to open permission on a new path** |
| `resume` clears the pause | `resonance.apply_command(..., "resume")` | 0.95.1 code does not know permissions: downgrade, then press Resume, and it runs again |
| Path helper: blocks absolute paths, paths that resolve outside the brain, symlinks pointing outside | `resonance._brain_file` | **It accepts `a/../a/x.md` and `./a/x.md`** because they still resolve inside the brain (tested). It does not yet compare case-insensitively on Windows |
| Snapshot when upgrading the store: SQLite backup API, includes the WAL part, once, no overwrite | `GoalStore._backup_before(marker_table, suffix)` | Reused for 0.96.0 (section 7.4) |

- **There is no "submit deliverable" tool.**
- **Old ideas not yet in code:** the 06/10 document has `GoalGrant`, `AuthorityService`, `X-Javis-Run`, but not a single line of code exists.

## 3. Five invariants

Taken from the 10/10 supplement, section 5. A4 implements invariants 1 to 4; invariant 5 belongs to A5.

1. **The host holds identity and grants permission.**
   - The model only proposes.
   - A quote, the "That's right" button, a revision edited by the model, or **a file path that merely appears in the message** are **not** approval to open permission.
   - Ordinary chat has no Resonance permission.
2. **Delegation only narrows.**
   - Revision permission = the intersection of the root scope and what the revision needs.
   - A missing scope, an unknown scope or a corrupted configuration means no permission to act.
3. **Only the turn that holds the exact permission may act.**
   - The permission is pinned to the turn when the host opens the link.
   - At the point of effect, check that the pinned permission is still alive with its own `generation` **and** that of the root scope.
   - Re-granting or approving mid-turn does not give the old turn the new permission.
4. **Cost and effect have one source of record.**
   - The same key and the same operation fingerprint produce only one effect.
   - An effect that has passed its commit point is completed or reported as a conflict; it is never undone and rerun automatically.
   - Running out of authority to accept new calls does **not** remove the authority to complete a submission the host already accepted, as long as the pinned permission is still alive.
5. **Making, reviewing and settling as done are three different permissions.** This is A5's part.

## 4. The submission contract

### 4.1 Four sources, one submissions table

| Source | Engine | Where the content comes from | Where the bytes are when it becomes a submission |
|---|---|---|---|
| `background_text` (exists) | Claude, API engines | The model returns text | The host already wrote `output_root/<action_id>.md` |
| `submit_tool` (new) | Engines that carry the turn key to the hub: Claude, Codex, API engines | The model calls `javis_submit_deliverable` | The host writes `output_root/submissions/<id>.md` (draft area) |
| `observed_write` (exists, kept as a side path) | Claude in chat | The model Writes straight to the destination | The engine already wrote it at the destination |
| `approved_draft` (new) | No engine | The project owner clicks Allow on a kept draft (section 5.3) | The old draft file itself, not copied again |

Each submission is one `submissions` row (section 7.1), attached to one **binding** (section 4.2).

**Two rules common to every submission:**

- **A submission is not a published version.** Only the host publishes, per section 4.5. `observed_write` has one exception (section 4.4).
- **An unpublished version is never treated as one the user has seen or approved** (section 4.6). A draft awaiting approval only shows its size and a preview button on the card; clicking Allow approves the scope together with exactly that version, not "Meets the bar".

### 4.2 Binding: pinning permission to each turn

The `bindings` table (section 7.1). Each row is pinned hard and is never edited to point at a different permission:

- **Goal:** `goal_id`, `revision`.
- **Authority type** `authority`:
  - `grant`: pins `grant_id`, `grant_generation`, `root_id`, `root_generation`;
  - `draft`: pins the `scope_request_id` that is waiting for the project owner; no revision permission, no root scope.
- **Assistant:** `agent_key`, `agent_config_version`.
- **Origin:** `origin_kind` plus `origin_ref`.
- **State:** `status`.

The `origin_kind` field takes five values:

| `origin_kind` | `origin_ref` | Who creates it, when |
|---|---|---|
| `handoff` | `<session_id>:<message_id>` | The host, in the **same transaction** as `_open_handoff`, each time a goal is created or edited in the middle of a chat turn. It does not require knowing the goal from the start of the turn |
| `action` | `<action_id>` | The host, in the same transaction as `begin_action(work)` |
| `experiment` | `<experiment_id>` | The host, in the same transaction as `begin_experiment` (an A3 trial) |
| `followup` | `<action_id>` | The host, when the A3 deliverable turn uses a hold (`begin_action` with `use_hold`) |
| `approval` | `<scope_request_id>` | The host, in the `approve_scope` transaction when the project owner chooses a draft (section 5.3) |
| `republish` | a new code each time | The host, when the destination file is deleted but the current revision has a PUBLISHED version (I2): it copies exactly the published version (same goal, revision, destination, sha) under a new binding that pins the revision permission currently IN EFFECT. It never legitimizes a `candidate` or `stale` version that was never published |

**Key and reopening.** `UNIQUE(goal_id, revision, origin_kind, origin_ref)`:

- A message that creates a goal (revision 1) and then edits it (revision 2) has **two** bindings, one row per revision.
- Reopening exactly `(goal, revision, origin)` (replaying an edit call that changes nothing): `INSERT ... ON CONFLICT DO NOTHING`, then read the existing row. If the row is still `live`, return its code; if it is no longer `live`, there is no binding for this turn. **Never `INSERT OR REPLACE`**, because submissions and actions reference the old row.
- Opening the binding for a new revision does the following in the same transaction: `candidate` and `awaiting_scope` submissions of the old revision become `superseded`; the old revision's binding becomes `closed`. A submission that is `publishing` is left so that step 3 of section 4.5 cancels itself, since the revision no longer matches.

**Pinning the root scope per chat turn** (only `origin_kind=handoff`). A new `grant` binding for a message may be opened only when both of these hold:

1. Every earlier binding for the same `(goal_id, origin_ref)` pins the **same** `root_id` and `root_generation` as the currently `active` root scope. If one binding is already `dead`, or the current root differs from the pinned root, refuse (`turn_authority_changed`).
2. For the first binding of the message for that goal (the turn has never touched the goal): the root must satisfy `root.seq <= turn.authority_seq`. No exceptions: A4 has no root created by the chat turn itself.

**Permission ordering is managed by the store, not by the machine clock.**

- A one-row table `authority_clock(seq)`. Every transaction that creates a root, revokes, approves or re-grants (all `BEGIN IMMEDIATE`) increments `seq` by one inside that same transaction. A new root carries `grants.seq` equal to the value just incremented.
- A turn with an assistant: `main.run_turn` reads `authority_clock.seq` (a single primary-key read) **before the engine runs** and writes it to `turn.authority_seq`. The host sets this field; the model cannot see or edit it.
- Because SQLite serializes write transactions, the read at the start of the turn sees the store **either before or after** a re-grant. A root re-granted after the read always has a larger `seq`, so that turn cannot accept it, even on its first touch of the goal. A clock moving backward or two identical timestamps have no effect.
- `seq` is stored in the store, so a restart does not move it backward. Turns of the old process die with the process.
- If `seq` cannot be read when building the turn: `authority_seq = -1`. The turn still chats normally, but cannot open a `grant` binding under an existing root (fail closed); background work continues as usual.
- A root's `created_at` is only for display and audit, not a basis for permission.

Consequence: revoking then re-granting, or the project owner clicking Allow while the old turn is still running, never lets that turn take a binding under the new root, whether the turn already had a binding or is touching the goal for the first time, whether through an edit or a late call. The goal edit is still recorded; that turn simply has no permission to submit, and background work continues under its own binding.

**Binding lifecycle:**

| `status` | Accepts new submissions | Completes a submission the host already accepted | Enters this state when |
|---|---|---|---|
| `live` | Yes | Yes | The host opens the binding |
| `sealed` | **No** | Yes | The chat turn ends or expires (including after a restart); a background turn finishes writing its output or is interrupted; a trial ends. An `approval` binding is born `sealed` |
| `closed` | No | No | Every submission of the binding is in a final state; or a new revision replaces it |
| `dead` | No | No | Revoked |

**Two checks**, both read-only inside a transaction:

- `binding_accepts(c, b)`: the gate for a new submission.
  1. `b.status = live`.
  2. The authority is still in effect:
     - `grant`: the row `b.grant_id` is `active` with `generation = b.grant_generation`, **and** the root `b.root_id` is `active` with `generation = b.root_generation`;
     - `draft`: the request `b.scope_request_id` is still `pending`, with the right revision and the binding's assistant.
  3. `_agent_block(b.agent_key, b.agent_config_version)` reports nothing.
  4. The goal's current revision equals `b.revision`.
- `binding_may_finish(c, b)`: the gate for completing an accepted submission (publish, adopt, reconcile).
  - Same as above, but item 1 is `b.status IN (live, sealed)`.
  - The authority must be `grant`. A `draft` binding can **never** publish or adopt.

These two checks are permission checks only. The publish step still runs the full existing `_gate` (section 4.5).

**Consequences:**

- **Re-granting does not rescue an old turn.** Revoking increments the root's `generation` and turns the binding `dead`. Re-granting creates a **new** root (new `id`). The old turn still pins the old root.
- **Calls from a dead turn are blocked in two layers:**
  - the turn key of the old process no longer exists (`no_turn`);
  - within the same process, the binding is `sealed`, so the submission is refused (`turn_closed`).
- **A restart does not lose an accepted submission.** Handoff expiry only moves the binding to `sealed`. Reconciliation can still publish the accepted `candidate` submission, under exactly the pinned permission, if that permission is still in effect (section 4.7).

### 4.3 The `javis_submit_deliverable` tool

**Input:**

- `path`: the destination path.
- `content`: the full text.
- `submission_key`: optional.
- `handoff`: optional. This is the binding code the host returned in the result of the tool that created or edited the goal.

The model cannot pass a goal, assistant or permission. `handoff` is only used to choose among the bindings of **the calling turn itself**.

**Steps.** If steps 1 to 5 fail, no submission is accepted and nothing affects the destination. A draft file or orphan evidence may remain at step 6; section 4.7 describes how it is reconciled.

1. **Turn identity** (`turn_context` by turn key).
   - No turn: `no_turn`.
   - A turn that carries no assistant (ordinary chat, external channel, workflow): `not_agent_turn`.
2. **Path key** (`resonance_grants.path_key`).
   - Refuse before resolving if there is a `.` or `..` segment, an absolute path, or a control character. No alias is opened.
   - Then pass through `_brain_file`: real resolve, check it is still inside the brain, block symlinks pointing outside. Add checks on extension, size and forbidden folders.
   - The matching key is the POSIX relative path, passed through `os.path.normcase` on Windows. No string-prefix comparison.
3. **Find the turn's binding.**
   - Take every binding with `origin_kind=handoff`, `origin_ref = <session_id>:<message_id>` **of the calling turn itself**, with the turn's own `agent_key` and `config_version`, **in every state**.
   - If `handoff` is given, it must be one of them.
   - Filter by the path key of the destination the binding points to (the revision permission for `grant`, the scope request for `draft`).
   - More than 1 row after filtering: `ambiguous_handoff`, no guessing. Example: the same message edits a goal twice with the same destination, so there are two bindings (one `closed`, one `live`); a submission without `handoff` gives `ambiguous_handoff`. The tools that create and edit goals always return the **new** `handoff` of the revision just created, and the submit tool's description tells the model to send that code along. A4 does not pick the first or the last row itself.
4. **Content.**
   - Replace long dashes with "-", counting the number of replacements.
   - Compute sha256 over the bytes that will be written.
5. **Key, fingerprint, replay.** Fixed order: identity (step 1) and the turn's own binding (step 3) **first**, then look up an old receipt.
   - Fingerprint `fp` = sha256 of `(binding_id, path key, content sha, source)`.
   - Key: `<binding_id>:<path key>`, or `<binding_id>:<submission_key>` if the model gives a key.
   - Same key, same `fp`: return the existing receipt, with its **current** state (it may already be `stale`). No new effect. Holds even when the binding is already `sealed` or `dead`.
   - Same key, different `fp`: `submission_conflict`.
   - A different destination with the same optional key also has a different `fp`, so it yields a conflict.
   - No old receipt: exactly one binding must pass `binding_accepts`. If not, return a specific reason: `turn_closed`, `grant_revoked`, `scope_decided`, `revision_changed`, `agent_changed`, `no_open_handoff`, `path_not_in_scope`.
6. **Write.**
   - Write the draft file `output_root/submissions/<submission_id>.md` (temp file then `os.replace`), read it back to hash, store the evidence.
   - Then **one transaction** re-checks `binding_accepts` and the permission:
     - `grant` binding: the revision permission has `submit` and the right destination; insert `submissions` with state `candidate`;
     - `draft` binding: the path equals the request's path; insert state `awaiting_scope`.
   - The evidence store and the file system are not inside the SQLite transaction. A failure midway leaves an orphan file or evidence, with no row.
7. **Return the receipt:** submission id, sha, size, state. No content.

### 4.4 State transition table by source

**States of `submissions`:**

| State | Meaning | Final? |
|---|---|---|
| `awaiting_scope` | A draft kept under a `draft` binding, waiting for the project owner to decide the scope | No |
| `candidate` | A valid submission under a `grant` binding, not yet published | No |
| `publishing` | Publish intent recorded, waiting for the commit point | No |
| `published` | Published, bytes at the destination checked and matching. An empty `adopted_at` means adoption is not finished yet | No, until `adopted_at` is set |
| `adopted_in_place` | `observed_write` only | Yes |
| `promoted` | The draft was chosen by the project owner; a new `approved_draft` row carries it forward | Yes |
| `conflict` | The destination holds bytes that do not match the baseline | Yes |
| `stale` | The pinned permission lapsed before the commit point | Yes |
| `superseded` | A newer submission exists under the same binding, or a new revision took its place | Yes |
| `rejected` | Refused, including the project owner clicking No | Yes |

**`submit_tool`, `grant` binding:**

1. `candidate`: section 4.3.
2. At the end of the chat turn, `handoff_after_turn` moves the binding to `sealed`, picks the newest `candidate` of this binding (older ones become `superseded`) and calls the **host publish** (section 4.5), reading bytes from the draft file.
3. After publishing: `published`, then `adopt_submission` (the new split-out part of `finish_handoff`):
   - attach the `chat_output` evidence stored at submission time (`INSERT OR IGNORE`);
   - an `artifact_adopted` event with key `adopt:<submission_id>` (replacing the old `adopt:<revision>`, because one revision can have several submissions over several attempts);
   - close the handoff; release the schedule if the existing gate allows;
   - write `adopted_at`. All in one transaction. **Do not write `published` again**, since the publish already wrote it.
4. If publishing hits a conflict: `conflict`, reported truthfully. The handoff adopts nothing and keeps the draft.

**`submit_tool`, `draft` binding:** the submission is at `awaiting_scope`. At the end of the turn the binding becomes `sealed`; nothing is published and no background turn is held. It proceeds per section 5.3 (Allow or No).

**`approved_draft`:** a new row created by `approve_scope`, with an `approval` binding (`sealed`), state `candidate`, and `derived_from` pointing back to the old draft (already `promoted`). Publishing and adoption follow steps 2 to 4 of `submit_tool`. The adoption event records the source `owner_approval`.

**`background_text`:** reorder `_work_post_core`:

1. Receipt, then evidence. The `action` binding moves to `sealed`.
2. **Insert a `candidate` submission** with the turn's `action` binding, through `binding_may_finish`. If it does not pass, `stale`.
3. Grade on the candidate version, as today.
4. Publish **from the submission** (section 4.5).
5. `_publish_latest` (republish when the previous attempt was blocked) only takes the `candidate` submission of the current revision that has `binding_may_finish`. It no longer takes bare action output as before.

**`observed_write`:**

- The engine already wrote the bytes at the destination, so this is an **exception**: the host adopts in place and does not publish again.
- Conditions for adoption:
  - a valid Write receipt, under the old rules;
  - bytes at the destination match the receipt's sha;
  - `binding_may_finish` of the `handoff` binding, authority `grant`;
  - the permission has `publish` for exactly this destination;
  - the existing `_gate`.
- If met, write `adopted_in_place` and the `published` marker, with source `observed_write`. The record states clearly that this is a file the engine wrote, not a file the host just published.
- A `draft` binding never adopts an in-place Write. A file the assistant Writes on its own before a scope exists becomes foreign bytes at the destination, handled as in A2.

**Same turn has Write A at the destination and submission B (D3):**

1. If A has a valid receipt and can be adopted, the host adopts A in place first, and A becomes the baseline. Then the host publishes B over A through CAS and the guard, because the baseline is now A.
2. If A has no valid receipt, the destination carries foreign bytes with no baseline. The host reports `conflict` for B.
3. **Never write B's baseline onto file A** to force the publish.

### 4.5 Host publish: ordering against revocation

Every path that changes the deliverable marker goes through exactly one function, `host_publish(submission)`:
- normal publish;
- the same-content branch (`same`);
- republish;
- reconciliation;
- the A3 deliverable turn;
- a draft chosen by the project owner.

Four steps, holding no lock while calling the model or writing files:

1. **Intent.** A transaction checks:
   - `binding_may_finish` of the submission;
   - the permission has `publish` and the right destination;
   - **the full existing `_gate`:** goal active, not paused, guard on the submission's bytes, assistant;
   - it reads the baseline (`published`) and the current hash of the destination.

   If met, it writes `actions(kind=publish)` carrying `binding_id` and `submission_id`, and moves the submission to `publishing`.
   - Destination already has the same hash as the submission (the `same` branch): go straight to step 4, **inside this very transaction**, after the permission check. The existing detour path is removed.
2. **Temporary write.** Write a temp file next to the destination, outside the transaction.
3. **Commit point.** A `BEGIN IMMEDIATE` transaction:
   - re-check `binding_may_finish` and the `_gate` checks;
   - re-read the destination hash and compare it with the baseline read in step 1.

   If met, write `commit_at` into the publish action. A revoke operation also uses `BEGIN IMMEDIATE` on the same store, so the two are **serialized**:
   - **Revoke commits first:** step 3 sees the binding dead, deletes the temp file, the action becomes `aborted`, and the submission goes back to `stale`.
   - **Step 3 commits first:** the effect has been allowed. A later revoke blocks subsequent effects but does not cancel this one.
4. **Replace the file and write the marker.**
   - `os.replace`, then re-read the destination hash.
   - Match: `set_published` transaction, submission `published`.
   - No match: `conflict`.

**Rule for a committed effect.** From the moment `commit_at` exists, completing step 4 (including during reconciliation) does **not** re-check the binding, permission or pause; it only checks the baseline and hash. This is a rule specific to committed effects and does not apply to a `candidate` submission with no intent.

**Messages when a revoke lands in between:**

- `commit_at` exists, no evidence at the destination yet: "The publish was committed before the revoke; Jarvis 007 is finishing it." It does not yet say the file was published.
- Step 4 hash matches: "Finished the publish that was committed before the revoke", with the sha. It does not say "published before the revoke", because the file may have been replaced after the revoke.
- Step 4 does not match: report a conflict as with any other publish.

The goal card and the guide state this rule explicitly.

**Limit (stating exactly what is detectable):** there is no atomicity between SQLite and the file system.

- The user edits the file **before** step 3: step 3 sees a hash different from the baseline, cancels the publish and keeps the draft.
- The user edits the file **after** `os.replace` but before the re-read: step 4 sees a different hash and writes `conflict`.
- The user edits the file **between step 3 and `os.replace`**: `os.replace` overwrites that edit, and the re-read hash still equals the submission, so it is **not detected**. That edit is lost. This is the published TOCTOU gap, kept as short as possible by keeping step 3 and `os.replace` adjacent in the same thread.

### 4.6 Who reads what in each state

| Reader | Reads |
|---|---|
| `artifact_contract` evaluator, `_artifact_file`, `artifact_ref` | The published bytes at the destination (as today). Grading a candidate before publish uses the submission's bytes, like the existing guard rule on candidates |
| "Current version" in the background job prompt | **Only published bytes** at the destination that belongs to `read_paths`. Never an unpublished submission or a draft awaiting approval |
| The user's "Meets the bar" confirmation | Attached to the published sha; not attached to a draft |
| Goal card | The published version; the number of versions waiting to publish or in conflict; the draft awaiting approval (size, short sha, preview button) |
| `_publish_latest` | A `candidate` submission with `binding_may_finish`; does not take bare output |

### 4.7 Failure points and reconciliation (no model call)

Reconciliation runs at the next wake, in the same place as the existing `_reconcile`. Every step uses only bytes, hashes and rows the host has accepted, under the binding's **pinned permission**; it takes no new root and does no re-pinning. Running it twice does not duplicate evidence, events or schedule releases.

| Failure point | State left behind | Reconciliation |
|---|---|---|
| Draft file written, row not inserted | Orphan file in `submissions/` | Ignored. A file with no row is never adopted. Cleaned after 7 days |
| Chat turn: `candidate` inserted, process died before `handoff_after_turn` | `candidate`, binding `live`, handoff `pending` | On restart: the handoff expires, the binding is `sealed`. If `binding_may_finish` passes, publish (section 4.5) then adopt. If not, `stale` (revoked), `superseded` (revision changed), `stale` with an assistant reason (assistant changed) |
| Chat turn: `awaiting_scope` inserted, process died | `awaiting_scope`, binding `live` | The binding becomes `sealed`. The draft still waits for the project owner; nothing is published |
| Background turn: output written, died before the submission was inserted | Interrupted action, output file exists | `_reconcile` settles the receipt as today, the binding becomes `sealed`, then inserts a submission from the **host's** output if `binding_may_finish`, otherwise `stale`. Publishing goes through `_publish_latest` and section 4.5 |
| Background turn: `candidate` inserted, died before publishing | `candidate`, binding `sealed` | `_publish_latest` publishes if `binding_may_finish` |
| Intent recorded, commit point not reached | `publishing`, action has no `commit_at` | Delete the temp file, action `aborted`. The submission goes back to `candidate` if `binding_may_finish`, otherwise `stale` |
| Commit point passed, no `os.replace` yet | Action has `commit_at` | Rule for a committed effect: if the destination still equals the baseline, replace the file and write the marker. If the destination already differs: `conflict` |
| File replaced, marker not written | Action has `commit_at` | Destination equals the submission's sha: write the marker, `published`. Different: `conflict` |
| **Published and marker written, not yet adopted** | `published`, `adopted_at` empty | Call `adopt_submission` again: attach evidence with `INSERT OR IGNORE`, event with key `adopt:<submission_id>` (the events table already has `UNIQUE(goal_id, idempotency_key)`), close the handoff if still open, write `adopted_at`. Release the schedule only when `adopted_at` is empty and the existing gate allows, in the same transaction, so exactly once. Evidence and event are still written when revoked after the commit, because the effect is real; in that case the schedule is not released |
| Draft chosen, died before publishing | `approved_draft` at `candidate`, `approval` binding `sealed` | Same as the row for a background turn that inserted `candidate` |
| Chat turn died, Claude Write has no receipt left | Handoff expired | As today: foreign bytes at the destination with no baseline become drift or `conflict` (A2). Not accepted as the deliverable |
| Committed, TEMPORARY read or write error when replacing the file or reconciling (file open) | Action has `commit_at`, `running` | This is not evidence that the destination changed: keep `running`, extend the deadline with spacing (60 seconds doubling, at most 1 hour), schedule a `settle` wake. Settle `conflict` only when the destination can be read and it differs from both the baseline and the submission (I11) |
| Committed, then the goal is revoked, paused, cancelled or finished | Action has `commit_at` | Its own `settle` schedule still comes due: it only completes or verifies the conflict of exactly that action, opens no work turn, grants no permission again, and publishes no other version (I10) |
| Destination file deleted after being published | `published` submission | Republish that version through source `republish` when the current permission is still in effect, 0 model turns (I2) |
| DRAFT file temporarily unreadable (during publish or reconciliation) | `candidate` or committed action | Not a destination conflict: keep the obligation, retry with spacing. Draft file lost or wrong hash: the submission is `rejected` with reason `draft_missing`/`draft_hash_mismatch`, the action `failed`, wrong bytes are never published (I13) |
| Published, adoption step fails (SQLite lock, died midway), even after a later revoke, pause or cancel | `published`, `adopted_at` empty | The `settle` schedule remains until adoption finishes; the `settle` wake adopts exactly once in every goal state (I14) |
| A settled publish still waiting for the file replace or for adoption while the work schedule comes due | Committed action or unadopted version | The work schedule holds `publish_settling`, keeps every reason, opens no work turn or trial; when done, it lifts the hold and considers the goal again (I15) |
| I/O error arising RIGHT IN a work wake that is publishing a kept `candidate` itself (file replace after the commit point, reading the draft file before the commit point, adoption) | Committed action, kept submission, or unadopted version | Re-evaluate the obligation right after publishing, hold `publish_settling` before the work decision. Draft file not yet readable before the commit point: the submission stays `candidate` with `hold_until`, the `settle` schedule rereads with 60-second spacing, doubling, capped at 1 hour; once readable, release the hold so the work schedule publishes exactly that version and only then evaluates (I16) |

A `sealed` binding moves to `closed` in the same transaction that takes its last submission to a final state.

## 5. Scoped permissions

### 5.1 Two tiers: root scope and revision permission

Both tiers live in the `grants` table (section 7.1):

- **Root scope** (`kind=root`, empty `parent_id`). Set by the project owner. **Independent of the criteria the model edits.**
  - Carries the allowed destination (one path, since A4 has one deliverable per goal).
  - Carries the set of operations: `read_deliverable`, `submit`, `publish`; `communicate` is always off.
  - Carries the source evidence (`source_ref_json`, section 5.2).
  - Has `generation` and `status`.
- **Revision permission** (`kind=revision`, parent is the root scope).
  - Equals `narrow(root, what the revision needs)`.
  - What the revision needs is taken from `_deliverable_rel(revision)`, not from every criteria path.
  - Records `parent_generation` = the root's `generation` at grant time.

**A revision permission is in effect** when it is itself `active` **and** the root is `active` with exactly `parent_generation`. The binding pins both (section 4.2).

### 5.2 Where the root scope comes from

| `source` | When | Destination | Evidence recorded with it |
|---|---|---|---|
| `owner_approved` | The project owner clicks "Allow" on the card for **one specific request** the host issued (section 5.3) | The request's path | `scope_request_id`, who clicked |
| `legacy_frozen` | The store-upgrade transaction to 0.96.0, for goals created earlier | `_deliverable_rel` of the revision **at upgrade time** | The revision and frame sha at upgrade time. **Legacy compatibility**; it does not claim the project owner approved |

**A goal newly created in a chat turn never has a root scope yet**, whether or not the assignment names a destination. The goal is in the state **waiting for scope approval**:

- The host writes `scope_requests` (kind `create` or `expand`) carrying the path, revision, assistant, version and source message.
- The card shows "The assistant wants to write to `Inbox/x.md`. Allow / No".
- **No background turn is held yet.** The prompt does not read the destination.
- The running chat turn gets a `draft` binding (section 4.2): it can submit a draft into the draft area, but it **cannot** read and **cannot** publish.

**Legacy freeze at upgrade time.** The store-upgrade transaction (after the snapshot in section 7.4, before any A4 code accepts a call) creates a `legacy_frozen` root for every goal that has an assistant and a `_deliverable_rel`, read from the stored revision. There is no more lazy granting at the "first wake", so there is no gap for the model to edit the destination before the freeze. A goal with no assigned assistant or no deliverable path gets no root.

#### 5.2.1 No permission from chat text (D1)

Rounds 2 to 4 tried a pure-write directive receiver (an imperative template and a blocklist of words). Every review round still found ordinary sentences that were mistaken for write permission, such as "This is an illustrative example. Write to `Inbox/x.md`." or "Write to `Inbox/x.md` is the sentence to translate." The cause is that a finite list cannot tell **mentioning** a command from **requesting** that the command be carried out.

A4 decides:

- **There is no `owner_message` source.** The model still understands the assignment and proposes a destination in the goal frame; understanding the goal is not granting write permission.
- A destination gets permission only through the card (`owner_approved`) or the legacy freeze (`legacy_frozen`).
- There is no module that parses text to grant permission. If a path suggestion on the card is needed later, the suggestion is only a proposal; it creates no root and raises no permission.
- "Hand over once" holds in this sense: once a destination has been allowed, later revisions with the same destination get permission automatically (section 5.3), without asking again.

### 5.3 Editing a goal, approval, revocation, re-granting

**A new revision with the same destination** (feedback, rephrasing, the model editing criteria while `_deliverable_rel` does not change):
- The host grants the new revision permission as `narrow(current root, destination)`.
- The old revision permission becomes `superseded`; the old revision's submissions and bindings follow section 4.2.

**A new revision with a different destination:**
- `narrow` yields an empty intersection on the write operations, even if the edit names the new destination. The host writes an `expand` request, the goal waits, and the card asks once with the specific path. No turn is held. The running chat turn gets a `draft` binding for the new revision.

**A quote and the "That's right" button** only confirm the understanding; they do **not** open scope.

**Allow (`approve_scope`).** One `BEGIN IMMEDIATE` transaction that checks everything before writing:

1. The request `request_id` exists and is still `pending`.
2. `request.revision` equals the current revision; the submitted `path` equals `request.path` by path key.
3. The goal's assistant equals `request.agent_key`, and `_agent_block` with `request.agent_config_version` reports nothing. The goal is not archived or done.
4. If the card sends `submission_id` and `sha256` (the draft you saw): that draft is still `awaiting_scope`, belongs to the `draft` binding of exactly this request, has the right sha, and is the newest draft of the request. If the card sends no draft while the request has one: refuse, because the card is out of date.

If any check fails: `scope_request_stale`, **no root is created**. If all pass, in the same transaction:

- create the `owner_approved` root (the old root, if this is `expand`, becomes `superseded`) and the revision permission;
- the request becomes `approved`;
- the `draft` binding becomes `closed`; its other drafts become `superseded`;
- if a draft was chosen: that draft becomes `promoted`; create an `approval` binding (`sealed`, pinning the new root and permission); create an `approved_draft` submission at `candidate` pointing to the same draft file and sha.

After the transaction, the host calls `host_publish` and then `adopt_submission` for the `approved_draft` submission. **No model call.** With no draft, the goal continues as usual: the next wake holds a background work turn under the new root.

The old chat turn gains nothing: its `draft` binding is already `closed`, so a later submission is refused (`scope_decided`); editing the goal again also cannot open a binding under the new root (the per-turn root pinning rule, section 4.2).

**No (`deny_scope`).** The same checks 1 to 3. The request is `denied`, the draft is `rejected`, the `draft` binding is `closed`. The goal keeps waiting. The project owner can speak again so the assistant edits back to the old destination.

**Old card.** A new revision replaces the old request with `superseded`; revocation does not touch a request that is already decided. Clicking Allow on the card of a request that is `superseded`, `denied` or `approved` always gives `scope_request_stale`. Clicking an old card is never a re-grant.

**Revoke** (the Revoke permission button on the card). Turning off Auto (Resonance) for the assistant is NOT a revocation (I1): the root stays as it is, but every in-progress binding dies immediately because it pins the assistant version (§4.2 item 3) and never comes back to life; turning it back on lets a NEW turn continue under the old root. A publish that passed the commit point before the switch-off still completes under the committed-effect rule. Revoking is one `BEGIN IMMEDIATE` transaction:
- the root becomes `revoked` and `generation += 1`;
- the goal's `candidate`, `awaiting_scope`, and `publishing` submissions that have **no** `commit_at` become `stale`. A submission with `commit_at` proceeds under the committed-effect rule;
- the goal is paused with the existing `pause` command;
- `live` and `sealed` bindings become `dead`;
- a `pending` scope request (if any) becomes `withdrawn`.

**Re-granting** is a separate owner action (Resume while revoked), not a consequence of any card:
- create a **new** root scope (`owner_approved`, destination as in the old root) and a new revision permission;
- do not flip old rows, do not change old bindings;
- a `stale` submission is not published. To reuse the content, the assistant submits again under the new binding.

### 5.4 `narrow` (used for revision permission in A4, child permission in A5)

`narrow(parent, request) -> grant | reason`:
- Operations, write paths, read paths and recipients are all the **intersection**.
- `goal_id` and `brain_id` must match.
- `communicate` exists only when the parent has it.
- A request with a missing field or an unknown value: empty intersection.
- Compare paths by the path key from section 4.3 step 2.

### 5.5 Every check point

| Point | Check (inside a transaction) |
|---|---|
| Opening a `handoff` binding | Root is `active`, the per-turn root pinning rule (section 4.2). With no root, a `draft` binding by the pending request |
| `javis_submit_deliverable` | The binding of exactly this turn; replay first, then `binding_accepts`; permission `submit` + destination, or exactly the request's path |
| `begin_action(work)` | Revision permission in effect. Writes an `action` binding. If absent, no turn is held (`grant_missing`, `scope_pending`, `grant_revoked`) |
| `begin_experiment` (A3 trial) | As above, `experiment` binding. Each trial turn checks `binding_accepts` at the existing turn gate (`_TrialCall`). On failure the trial stops `inconclusive` with a permission reason, through the existing stop path |
| A3 deliverable turn (`use_hold`) | A new `followup` binding, checking the current permission, not inheriting the trial's binding |
| Building the background-job prompt | Only published bytes at the pinned permission's `read_paths` |
| `host_publish` steps 1 and 3 | `binding_may_finish` + `_gate` (section 4.5), including the `same` branch |
| `host_publish` step 4 | Committed-effect rule: baseline and hash only |
| Adopting an in-place Write | `binding_may_finish` (`grant`) + `publish` + destination + `_gate` |
| `approve_scope`, `deny_scope` | CAS on request, revision, path, assistant, draft (section 5.3) |
| Reconciliation, republish | Use the submission's binding. No re-pinning to a new permission |
| UI | Display only, not a basis for permission |

## 6. Engines: real capabilities and limits

### 6.1 The capability table declared by the host (`ENGINE_CAPS`)

| Provider | Turn key reaches hub | Submit via tool | Observe Write with receipt | Block native writes | Text-only background work |
|---|---|---|---|---|---|
| `anthropic-cli` | Yes (header) | Yes | Yes | Per call (`can_use_tool`) when there is `allowed_tools` | Yes |
| `openai-oauth` (Codex) | Yes (`-c`) | **Yes (new)** | No | Sandbox only; can be turned off with `JAVIS_CODEX_SANDBOX=off` | No |
| `grok-cli` | **No** | No | No | `--deny` by level | No |
| `antigravity-cli` | **No** | No | No | Sandbox only | No |
| API engines | Yes (in-process) | **Yes (new)** | No | No native tools | Yes |

When coding, check the **real transport path** of Claude, Codex and the API engines: the turn key reaching the hub through a header, the `-c` parameter, and in-process. Do not check only with a fake turn context (review D4/D5).

### 6.2 Background work keeps the same list

Codex and Grok still have native tools. For Antigravity, `strip_tools` makes the fallback chain go back to Claude. Opening background work to these engines needs evidence of a tool-free run; A4 has none.

### 6.3 Limits that must be stated honestly

- **The hub cannot block native tools.** A check at the hub does not block Bash or Write native to an engine with full OS access. If the assistant Writes directly before a scope exists, that file is foreign bytes and does not become the deliverable.
- **A receipt only proves what was submitted.** A4 guarantees that the host only adopts and publishes versions that pass through the contract.
- **`communicate` is off only within the Resonance contract.** It does not claim that every workflow, task or native tool outside the contract is blocked (D8).
- **`read_paths` is only the prompt scope of A4 background work.** It is not a restriction on all reading by chat or native engines (D9).

## 7. Store

### 7.1 New tables

```sql
CREATE TABLE IF NOT EXISTS grants(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, parent_id TEXT NOT NULL DEFAULT '',
  parent_generation INTEGER NOT NULL DEFAULT 0,
  brain_id TEXT NOT NULL, goal_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
  agent_key TEXT NOT NULL, agent_config_version INTEGER NOT NULL,
  granted_by TEXT NOT NULL, source TEXT NOT NULL, source_ref_json TEXT NOT NULL DEFAULT '{}',
  actions_json TEXT NOT NULL, write_paths_json TEXT NOT NULL, read_paths_json TEXT NOT NULL,
  recipients_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL, generation INTEGER NOT NULL, seq INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS authority_clock(id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL);
INSERT OR IGNORE INTO authority_clock(id, seq) VALUES(1, 0);
CREATE UNIQUE INDEX IF NOT EXISTS grants_root_active ON grants(goal_id) WHERE kind='root' AND status='active';
CREATE UNIQUE INDEX IF NOT EXISTS grants_rev_active ON grants(goal_id, revision, parent_id)
  WHERE kind='revision' AND status='active';
CREATE INDEX IF NOT EXISTS grants_goal ON grants(goal_id, kind, status);
CREATE TABLE IF NOT EXISTS grant_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id TEXT NOT NULL, kind TEXT NOT NULL, by TEXT NOT NULL,
  generation INTEGER NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS scope_requests(
  id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
  path TEXT NOT NULL, agent_key TEXT NOT NULL, agent_config_version INTEGER NOT NULL,
  origin_ref TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
  decided_by TEXT NOT NULL DEFAULT '', decided_submission_id TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL, decided_at REAL);
CREATE UNIQUE INDEX IF NOT EXISTS scope_requests_pending ON scope_requests(goal_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS bindings(
  id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, revision INTEGER NOT NULL, authority TEXT NOT NULL,
  grant_id TEXT NOT NULL DEFAULT '', grant_generation INTEGER NOT NULL DEFAULT 0,
  root_id TEXT NOT NULL DEFAULT '', root_generation INTEGER NOT NULL DEFAULT 0,
  scope_request_id TEXT NOT NULL DEFAULT '',
  agent_key TEXT NOT NULL, agent_config_version INTEGER NOT NULL,
  origin_kind TEXT NOT NULL, origin_ref TEXT NOT NULL, status TEXT NOT NULL,
  created_at REAL NOT NULL, closed_at REAL,
  UNIQUE(goal_id, revision, origin_kind, origin_ref));
CREATE INDEX IF NOT EXISTS bindings_origin ON bindings(origin_kind, origin_ref, status);
CREATE TABLE IF NOT EXISTS submissions(
  id TEXT PRIMARY KEY, brain_id TEXT NOT NULL, goal_id TEXT NOT NULL, revision INTEGER NOT NULL,
  binding_id TEXT NOT NULL, source TEXT NOT NULL, engine_json TEXT NOT NULL,
  path TEXT NOT NULL, draft_ref TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
  normalized_em_dash INTEGER NOT NULL DEFAULT 0, evidence_id TEXT NOT NULL DEFAULT '',
  idem_key TEXT NOT NULL, fingerprint TEXT NOT NULL, derived_from TEXT NOT NULL DEFAULT '',
  publish_action_id TEXT NOT NULL DEFAULT '', adopted_at REAL,
  status TEXT NOT NULL, status_reason TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(goal_id, idem_key));
CREATE INDEX IF NOT EXISTS submissions_goal ON submissions(goal_id, revision, status);
CREATE INDEX IF NOT EXISTS submissions_binding ON submissions(binding_id, status);
```

- The publish action carries `binding_id`, `submission_id` and `commit_at` in the `intent_json` / `receipt_json` of the existing `actions` table; no columns are added.
- The `idem_key` of `approved_draft` is `approval:<scope_request_id>`, so clicking Allow twice does not create two versions.
- `CHECK` constraints on state and `authority` are left to the code layer (same style as the A1 to A3 tables), with their own tests.

### 7.2 Source of truth

- **Scope:** the goal's `active` root row. No row means no permission.
- **Turn permission:** only the pinned binding. It is not inferred from the permission currently in effect at call time.
- **Deliverable:** `published` and `evidence_links`, as in A1 to A3. `submissions` is the input ledger.
- **Quota:** `goals.calls_used` and the A1 to A3 ledger.

### 7.3 Publishing

Per section 4.5. No atomicity is promised with the file system.

### 7.4 Upgrade, downgrade, upgrade again (choosing a limited policy)

Round 1 review pointed out that the 0.95.1 `apply_command(..., "resume")` clears the pause without knowing about permissions. So a pause does **not** preserve a revocation when running with old code. A4 chooses a limited policy:

**Downgrading to 0.95.1 only supports restoring a snapshot or reading the records.** Continuing to run a goal that has A4 permissions with old code is not supported.

- **On upgrade:**
  1. `GoalStore._backup_before("grants", ".pre-0.96.0")`: reuse the existing helper, the SQLite backup API (includes the WAL part), only when the store has no `grants` table yet, never overwriting an existing copy.
  2. Create the new tables.
  3. Legacy freeze (section 5.2) in the same transaction that creates the tables, before the server accepts calls.
- **A proper downgrade,** with the bundled script `tools/resonance_restore_pre_a4.py`, run while Jarvis 007 is off:
  1. Copy the **current** store to `resonance.sqlite3.post-0.96.0-<time>` with the SQLite backup API, to keep the post-upgrade records.
  2. Restore the snapshot into the store path with the backup API, then clean up old `-wal`/`-shm` files.
  3. Run 0.95.1.
  - Every goal change after the upgrade is lost from the running store: turns already run, published versions recorded in the store, feedback. The copy from step 1 can still be read.
  - Files already published in the brain remain, and 0.95.1 may see them as drift against the old marker (A2).
  - The release notes state this consequence clearly.
- **Downgrading without restoring the snapshot (not supported):**
  - old code does not read `grants`, so clicking Resume reruns a revoked goal;
  - A4 promises nothing for this case.
- **Upgrading again after old code has run** (the `grants` table already exists, so no re-freeze):
  - a revision with no matching revision-permission row is a revision created by old code. A4 **does not grant** permission to it by itself: with the same destination as the `active` root it still waits for the project owner like an `expand` request (section 5.3);
  - a goal created by old code after the downgrade has no root, so it waits for approval;
  - a root that is already `revoked` stays `revoked`; there is no path to revive it automatically.

## 8. UI

- **Goal card**, permission line: "Allowed: submit and publish `Inbox/x.md` · read `Inbox/x.md` · up to 6 calls · no contact with other assistants", with the **Revoke permission** button (confirmed once).
- **Waiting for approval:** "The assistant wants to write to `Private/y.md`. Allow / No".
  - With a draft: add "The assistant already drafted a version (3.2 KB). Allowing publishes exactly this version" and a Preview button.
  - The card sends the displayed `request_id`, `path`, `submission_id`, `sha256`. An old card gets the message "This card is out of date, reload to see the current request".
- **Drafts:** "1 draft waiting to publish", or "A draft conflicts with the existing file; see the history".
- **Revoke landing in the middle of a publish:** "The publish was committed before the revoke; Jarvis 007 is finishing it", then "Finished the publish that was committed before the revoke" once there is evidence at the destination.
- **Collaborators page:** the engine capability table (section 6.1).
- Text goes through `vi.json` and `en.json`. There is no technical permission configuration field.

## 9. Stop points and errors

| Situation | Behavior |
|---|---|
| Revoke while the chat turn is still alive | A later submission fails `binding_accepts` (binding `dead`). An earlier submission becomes `stale` right in the revoke transaction. Turns already run still count |
| Revoke then re-grant while the same chat turn is still alive | The turn still pins the old root, every submission is refused; editing the goal again also cannot open a new binding (`turn_authority_changed`). The assistant needs a new turn |
| Project owner clicks Allow while the chat turn has a live draft | The chosen draft is published through the `approval` binding. The chat turn cannot submit more (`scope_decided`) |
| Revoke while a background turn is calling the engine | Output is recorded as today. A submission inserted afterwards has a `dead` binding so it is `stale`. Not published. Turns already used stay as they are |
| Revoke after the publish intent, before the file replace | Ordering follows the commit point (section 4.5) |
| Same content after a revoke | The `same` branch checks permission first, so no baseline is created |
| Assistant or version changes mid-turn | As in A1: `agent_changed`, fails item 3 of both checks |
| Restart while an accepted submission exists | Binding `sealed`; reconciliation completes it if the pinned permission is still in effect (section 4.7) |
| A3 trial meets a revoked permission | Stops `inconclusive` (permission reason), refunds a turn that has no recorded intent under the A3 rule |

## 10. API and tools

- **`javis_submit_deliverable(path, content, submission_key?, handoff?)`:** a hub tool.
  - The tools that create and edit goals also return `handoff` (the binding code) when the host opens a binding, and `scope: "granted" | "pending"`.
- **`GET /goals/{id}`:** adds these fields:
  - `scope`: root, destination, source, state;
  - `grant`: the revision permission;
  - `scope_request`: if present, with the newest draft (code, sha, size);
  - the most recent `submissions`.
- **`POST /goals/{id}/commands`:**
  - `revoke_grant`: owner, CAS `expected_revision`;
  - `approve_scope`: owner, carries `request_id`, `path`, and `submission_id` + `sha256` when the card has a draft; CAS per section 5.3;
  - `deny_scope`: owner, carries `request_id`;
  - `resume`: when the root is `revoked`, re-grants per section 5.3.
- No route lets the model create, expand, approve or re-grant permission.

## 11. Performance

- Permission, binding and submission reads go by index; one query per check point. No scanning of files or assistants on every tick.
- The I/O of the submit tool and of publishing runs on a side thread. A `BEGIN IMMEDIATE` transaction only wraps store reads and writes, never a model call.
- Each turn with an assistant reads one extra `authority_clock` row by primary key when building the turn. An ordinary chat turn does not read it.
- The legacy freeze runs once at upgrade time, over the goals that exist.
- The card's permission reads in `goal_view` are already bounded (0.88.5).

## 12. Acceptance matrix (fake clock, fake engine, no real model)

Each case has a valid control that passes. Race cases insert the change right before the transaction being protected. Negative cases check all three things: no permission to read the destination into the prompt, no publish, no background turn held.

### 12.1 Round 1 cases (kept, adjusted to the new design)

| Case | Expectation |
|---|---|
| G1 | `narrow` with a recipient that has no permission: empty intersection |
| G2 | A child permission asking for a wider destination or a different goal: refused |
| G3 | No `communicate`: no path within the contract creates work for a third assistant |
| G4 | The model declares its own goal, assistant, project owner; an MCP named like the submit tool: no permission raise |
| G5 | Revoke right before the submit transaction: `grant_revoked`, no submission |
| G6 | Re-grant, a submission from the old binding arrives late: refused. The old submission is `stale`, not published |
| G7 | Revoke while a background turn is calling the engine: `stale`, not published, the turn still counts |
| G8 | Restart after a revoke: does not revive itself, does not complete twice |
| G9 | Error before or after the engine could run: keep the A1 to A3 rule |
| G10 | Same key, same fingerprint: return the old receipt. Same key, different fingerprint: `submission_conflict` |
| G11 | Editing the assistant file to add permission itself: host permission unchanged; `agent_changed` |
| G12 | The background-job prompt contains no file outside `read_paths`, and no unpublished draft or draft awaiting approval |
| G13 | Destination outside the scope, `..`, `.`, symlink pointing outside, unusual extension, over 1MB: refused before writing |
| G14 | The engine writes natively to the destination without submitting: does not become the deliverable; publishing hits `conflict` |
| G15 | No permission, corrupted permission, unknown operation: no turn held |
| G17 | A valid task within the scope: submitted, published, adopted exactly once, no extra model call |
| G18 | Many goals not yet due: no file reads, no model wake-ups; the event loop is not blocked by parallel submissions |
| G20 | Ordinary chat, external channel, workflow calling the submit tool: `not_agent_turn` |
| G22 | Engine capability table. **Check the real transport path**: Claude's header, Codex's `-c`, the API engine's in-process. Grok and Antigravity are refused |

### 12.2 Cases from the round 1 review

| Case | Situation | Expectation | Review point |
|---|---|---|---|
| G23 | Feedback that does not mention a path, the model changes or adds a destination (with a valid quote) | No permission into the new destination; write `scope_requests`; no turn held; the new destination is not read into the prompt | r1 P1-1 |
| G24 | New revision with the same destination | The new revision permission is granted automatically within the scope, without asking | r1 P1-1 |
| G25 | The project owner clicks Allow with exactly the request's path; sends a path different from the request | Match: new `owner_approved` root, continues. Mismatch: `scope_request_stale`, no root | r1 P1-1 |
| G26 | A goal with two criteria paths | Permission and destination are only the first path (`_deliverable_rel`); the second path is only read by the evaluator | r1 P1-1 |
| G27 | Creating a goal: the project owner's message names the destination as a direct command; a destination the assistant chose itself | Both wait for approval, no turn held yet, the destination is not read into the prompt. After Allow, runs normally | r1 P1-1, r2 P1-1, r4 D1 |
| G28 | An old goal from before 0.96.0 | `legacy_frozen` root with exactly the `_deliverable_rel` at upgrade time. A goal waiting for assignment has no permission | r1 P1-1 |
| G29 | Revoke then re-grant while the same chat turn is still alive | That turn can no longer submit | r1 P1-2 |
| G30 | A submission in the same session but the turn key belongs to another message (two interleaved messages) | Sees only its own message's binding | r1 P1-2, P2-1 |
| G31 | Revoke after step 1 (intent), before step 3 (commit point) | The publish is cancelled, the destination file is unchanged, the submission is `stale` | r1 P1-2 |
| G32 | The commit point commits first, revoke right after, before `os.replace` | The effect completes. Before the file is replaced it says "was committed before the revoke"; only after the hash matches does it say "finished the publish that was committed before the revoke". Later publishes are blocked | r1 P1-2, r2 note 2 |
| G33 | The `same` branch after a revoke | Creates no baseline | r1 P1-2 |
| G34 | An A3 trial when the permission is revoked in the middle of a trial turn | Stops `inconclusive`, permission reason; the deliverable turn does not run | r1 P1-2 |
| G35 | Reconciling an action that carries a binding with an old `generation` | Not published, no re-pinning | r1 P1-2 |
| G36 | Submit when the destination does not exist yet | The host publishes: the file is created, the marker has the right sha | r1 P1-3 |
| G37 | Submit when the destination has a user version with no baseline | `conflict`, the user's file is intact, the draft is kept | r1 P1-3 |
| G38 | Same turn: valid Write A, then submit B | Adopt A in place, then publish B through CAS; the final marker is B | r1 P1-3 |
| G39 | Write A with no receipt, submit B | `conflict`; B's baseline is not written onto A | r1 P1-3 |
| G40 | Failure at each point of section 4.7 (inject an error right before and after each step) | Reconciliation follows the table exactly; 0 model turns; no orphan file is adopted | r1 P1-3 |
| G41 | A valid submission completes without the model rewriting | Both the background turn and the chat turn publish from the submission | r1 P1-3 |
| G42 | The old `finish_handoff` is no longer called with a draft that is not at the destination | Only `adopt_submission` after publishing, or in-place adoption when there is a Write receipt | r1 P1-3 |
| G43 | Two goals in the same session, same destination, same message | `ambiguous_handoff`. With a valid `handoff`, the right one is chosen | r1 P2-1 |
| G44 | Same optional key, same bytes, different destination | `submission_conflict` | r1 P2-1 |
| G45 | Alias paths: letter case on Windows; `./a/x.md`, `a/../a/x.md` | Letter case maps to the same key. `.` and `..` are refused at the path key even though `_brain_file` accepts them; symlinks pointing outside are blocked | r1 P2-1, r2 note 4 |
| G46 | Replay after a revoke and re-grant, within the same live turn | Return the old receipt with state `stale` (receipt lookup before the `binding_accepts` gate); no new effect. A different turn or a new process: `no_turn` or no binding found | r1 P2-1, r2 note 5 |
| G47 | Upgrade to A4 | Exactly one `resonance.sqlite3.pre-0.96.0` copy, made with the backup API, including data still in the WAL | r1 P2-2, r2 note 3 |
| G48 | A4 revokes, then run `resume` of the 0.95.1 code (taken through `git archive`) | Records correctly that this is not supported: old code reruns. The test proves the limit written in the documentation is true; it does not prove it is blocked | r1 P2-2 |
| G49 | Upgrade again after old code created a new revision and a new goal | No permission is granted automatically for that revision or goal; a `revoked` root stays `revoked` | r1 P2-2 |
| G50 | Run the restore script, then run 0.95.1 | A `post-0.96.0-*` copy equal to the pre-restore store exists; the store opens, goals are in their state at upgrade time | r1 P2-2, r2 note 3 |

### 12.3 Cases from the round 2 review

| Case | Situation | Expectation | Review point |
|---|---|---|---|
| G51 | "Draft a new note, do not write to `Private/giu-nguyen.md`", and the model picks exactly that path as the destination | Waits for approval; three-sided negative case (no root, the destination is not read into the prompt, no publish, no background turn held) | r2 P1-1, r4 D1 |
| G52 | "Read `Private/giu-nguyen.md` for reference, write the new version to `Inbox/ban-moi.md`" | Either path waits for approval, three-sided negative case | r2 P1-1, r4 D1 |
| G53 | A message pasting someone else's text that contains "write to `Private/giu-nguyen.md`" | Waits for approval, three-sided negative case | r2 P1-1, r4 D1 |
| G54 | Direct command "Write the summary to `Inbox/x.md`" | Still waits for approval. Allowing exactly that path gives an `owner_approved` root and runs normally | r2 P1-1, r4 D1 |
| G55 | "can you write to `x.md`?"; two paths in one message | Waits for approval | r2 P1-1, r4 D1 |
| G56 | A legacy goal that 0.95.1 code had the model edit to a new destination right before the upgrade, then edited again after the upgrade | The root is frozen from the revision stored at upgrade time. An edit after the upgrade to a different destination waits for `expand`; the new destination is not read into the prompt | r2 P1-1 |
| G57 | Create a goal with a destination the model chose, submit, end the chat, the project owner clicks Allow | 1 model turn (the chat's), 0 turns after approval. The draft is `promoted`, the `approved_draft` submission is `published`, root `owner_approved`, binding `approval`, adopted exactly once | r2 P2-1 |
| G58 | Like G57 but the project owner clicks No | The draft is `rejected`, no root, no publish, no turn held | r2 P2-1 |
| G59 | Clicking Allow on an old card: after a new revision; after No; after a newer draft exists; after a revoke and re-grant | `scope_request_stale`, no root is created | r2 P2-1 |
| G60 | A live chat turn keeps submitting after the project owner has clicked Allow | `scope_decided`; that turn editing the goal again also gets no binding under the new root | r2 P2-1, P2-3 |
| G61 | A `draft` binding tries to publish or adopt an in-place Write | Blocked by `binding_may_finish` | r2 P2-1 |
| G62 | Restart after the chat turn's `candidate` was inserted | Binding `sealed`; reconciliation publishes and adopts, 0 model turns | r2 P2-2 |
| G63 | Restart after the background receipt, before the submission is inserted; and after it is inserted, before publishing | Completes from the host's output, 0 model turns | r2 P2-2 |
| G64 | Restart after `published`, before adoption | Adopts once: one evidence, one event, schedule released once. Running reconciliation twice does not duplicate | r2 P2-2 |
| G65 | Like G62 but revoke, revision change or assistant change before reconciliation | Not published; `stale` or `superseded`; no pinning to the new permission | r2 P2-2 |
| G66 | A late submission from a finished turn (same process, key destroyed; and a simulation where the key still exists but the binding is `sealed`) | `no_turn`; `turn_closed` | r2 P2-2 |
| G67 | Same message: create a goal (r1) then edit (r2), submit at each revision | Two bindings; the r1 submission is `superseded`; only the r2 submission is published | r2 P2-3 |
| G68 | Two edits with changes in one message; and replaying an edit that changes nothing | Three bindings by revision; the replay returns the existing binding, no new row, no `REPLACE` | r2 P2-3 |
| G69 | The r1 submission tries to publish after the goal moved to r2 | Blocked at item 4 of `binding_may_finish` | r2 P2-3 |
| G70 | Revoke then re-grant, the old turn edits the goal to obtain a new binding | `turn_authority_changed`, from the per-turn root pinning gate, not from a `UNIQUE` error | r2 P2-3 |
| G71 | The user edits the file between step 3 and `os.replace` | A case recording the limit: the edit is lost, no conflict reported. Two control cases (edit before step 3, edit after `os.replace`) are both detected | r2 note 1 |
| G72 | `host_publish` when the goal is paused, the guard blocks, or the baseline differs, even though the binding is valid | Not published; the `_gate` still runs | r2 note 6 |

### 12.4 Cases from the round 3 review

| Case | Situation | Expectation | Review point |
|---|---|---|---|
| G73 | "If you approve later, write to Inbox/x.md." (Vietnamese original: "Nếu anh duyệt sau, ghi vào Inbox/x.md.") | Waits for approval, three-sided negative case (does not depend on any receiver) | r3 P1-1, r4 D1 |
| G74 | "Should we write to Inbox/x.md?" (Vietnamese original: "Có nên ghi vào Inbox/x.md?") | Waits for approval, three-sided negative case (does not depend on any receiver) | r3 P1-1, r4 D1 |
| G75 | "You plan to write to Inbox/x.md." (Vietnamese original: "Anh định ghi vào Inbox/x.md.") | Waits for approval, three-sided negative case (does not depend on any receiver) | r3 P1-1, r4 D1 |
| G76 | "If I approve later, write to Inbox/x.md" | Waits for approval, three-sided negative case (does not depend on any receiver) | r3 P1-1, r4 D1 |
| G77 | A condition or negation in another sentence, not repeating the path: "Not sure yet, do not rush. Write to Inbox/x.md." (Vietnamese original: "Chưa chắc lắm, đừng vội. Ghi vào Inbox/x.md.") | Waits for approval, three-sided negative case (does not depend on any receiver) | r3 P1-1, r4 D1 |
| G78 | A direct command with a trailing period, a path with a dot in its name (`Notes/a.b.md`) | Waits for approval; the card shows the full intact path; on Allow the root carries the exact path key | r3 P1-1, r4 D1 |
| G79 | The three counter-example sentences of round 4 (a translation request, an illustrative example, a tail "is the sentence to translate") | Waits for approval; no code reads chat text to grant permission | r4 P1 |
| G80 | Turn T has not touched goal G; during the turn, G is revoked then re-granted; the clock is moved backward before the re-grant; T calls an edit on G for the first time | No `grant` binding (`turn_authority_changed`), because `root.seq > turn.authority_seq` | r3 P2-1 |
| G81 | Like G80 with a normal clock, and with the new root's `created_at` equal to exactly the turn's start time | Same result as G80; the machine time takes no part in the decision | r3 P2-1 |
| G82 | Control: a root that really exists before the turn (`owner_approved` or `legacy_frozen`) | A `grant` binding can be opened | r3 P2-1, r4 D1 |
| G83 | A goal edit or a submission from an old turn **arriving late** after a re-grant (including when the turn never had a binding) | The edit is still recorded; no binding, no submission; G60, G70 unchanged | r3 P2-1 |
| G84 | `authority_clock` cannot be read when building the turn | `authority_seq = -1`; chat runs, no `grant` binding is opened under an existing root; background work unchanged | r3 P2-1 |
| G85 | Same message edits twice with the same destination, submits without `handoff`; then submits with the new `handoff` | `ambiguous_handoff`; with the code, the right `live` binding. G67, G68 use the code returned by the tool | r3 note 2 |
| G86 | Reconciliation completes a committed publish under a revoked permission | Only completes exactly the committed action; opens no new publish action, inserts no new submission, publishes no other `candidate` submission under the old permission | r3 note 3 |

The sentence table of `test_resonance_a4_directive.py` records the real results of the verb list, including the sentences it missed (for example the Vietnamese "viết bản mới ở `x.md`" ("write the new version at `x.md`") has no verb in the list so it goes through the card). Missing a sentence is accepted; mistaking one for permission is not.

### 12.5 Moved to A5

| Case | Reason |
|---|---|
| Two sub-jobs racing for the last turn | A4 has no sub-jobs |
| Changing the recipient before the callback completes | A5 |
| A worker submitting a review under the reviewer's identity | A5 |
| Hash, revision, criteria changing after a review | A5 |
| Tool approval, sending to another channel | A4 has no channel-sending permission |

## 13. Default decisions that need review

| # | Decision | Status |
|---|---|---|
| D1 | The root scope is independent of the criteria and is **not granted from chat text**. A new destination or a scope change goes through the card; an already granted scope continues automatically; a draft is kept, and after approval it is published without a model call | **Final** per r4 (fallback option) |
| D2 | Publishing only through `host_publish`, keeping the full `_gate` | Kept, plus r2 note 6 |
| D3 | Keep Write observation; the Write A + submit B rule in section 4.4 | Fixed per r1 P1-3 |
| D4 | Grok and Antigravity do not accept chat handoff | Kept; check the real transport path when coding |
| D5 | No more background work is opened | Kept |
| D6 | Revoke = root `revoked` + `stale` (except committed effects) + pause, in one transaction | Kept; committed effects clarified |
| D7 | Expansion through a request with a specific path, the project owner clicks Allow with CAS | Fixed per r2 P2-1 |
| D8 | `communicate` is off within the Resonance contract | Kept, scope stated accurately in section 6.3 |
| D9 | `read_paths` is the background-job prompt scope | Kept, scope stated accurately in section 6.3 |
| D10 | No permission expiry in A4 | Kept |
| D11 | A downgrade only supports restoring a snapshot, with a script that keeps a copy of the current store | Fixed per r2 note 3 |
| D12 | **Keep the draft before approval** (`draft` binding, no read, no publish); on Allow, publish exactly that version through the `approval` binding, 0 model turns. Not chosen: refusing submission before approval, because under D1 every new goal goes through the card and that approach costs one extra model turn each time | New, r2 P2-1 |
| D13 | A binding has `sealed`: it stops accepting submissions but can still complete an accepted version under the pinned permission | New, r2 P2-2 |
| D14 | Binding key by revision; per-turn root pinning by the store-issued `authority_clock.seq` order, captured when the turn is built. Machine time is not used | New at r2 P2-3; fixed per r3 P2-1 |
| D15 | The path key refuses `.` and `..`, no alias is opened | New, r2 note 4 |

## 14. Code plan (after the design passes review)

1. **Store:**
   - the tables in section 7.1, including `authority_clock`; snapshot through `_backup_before`; legacy freeze inside the upgrade transaction (the legacy root gets `seq` in the same transaction);
   - `scope_*` (root, request, approve, deny, revoke, re-grant), `grant_rev_*`;
   - `binding_open/seal/close`, `binding_accepts`, `binding_may_finish`, attached to `_open_handoff`, `begin_action`, `begin_experiment`;
   - `submission_*`, `adopt_submission` (key `adopt:<submission_id>`);
   - `BEGIN IMMEDIATE` transactions for the commit point, revoke, approve.
2. **Pure policy** (`resonance_grants.py`): `path_key`, `narrow`, `allows`, fingerprint, `ENGINE_CAPS`. No text parser.
3. **Turn identity:** `turn_context.make` adds `authority_seq`; `main.run_turn` reads `authority_clock` for a turn with an assistant before the engine runs.
4. **Contract** (`resonance.py`):
   - the four-step `host_publish`, replacing every call site of `set_published` and `_publish`;
   - reorder `_work_post_core`;
   - `_publish_latest` by submission;
   - `handoff_after_turn` by submission, the A/B rule, sealing bindings;
   - the gate in A3 trials;
   - reconciliation per section 4.7.
5. **Hub tool** `javis_submit_deliverable` (plugin `javis-goal`). The tools that create and edit goals return `handoff` and `scope`.
6. **API** per section 10.
7. **UI** per section 8.
8. **Script** `tools/resonance_restore_pre_a4.py` (the repo has no `scripts/` folder).
9. **Tests:**
   - `test_resonance_a4_grants.py`: the matrix 12.1 to 12.3;
   - `test_resonance_a4_rollback.py`: G47 to G50 with `33a3c1aa`;
   - `test_resonance_a4_ui.js`;
   - one real turn-key transport test for Claude, Codex and the API engine.
10. **Documentation:** guide, record, roadmap, release notes about downgrading and the committed-effect rule.

## 15. Evidence boundary

- **The 17 Paperclip cases** are evidence about Paperclip.
- **The reviewer's 10 checks in round 1**, **13 checks in round 2** and **16 checks in round 3** prove assumptions about the base code and contradictions in the design text. They are not A4 tests.
- **Section 2:** code read at `9716cecf`. The row stating that `_brain_file` accepts `a/../a/x.md` was tested on that code; the round 3 reviewer rechecked it and corrected the round 2 remark. D15 is a new rule of `path_key`, and does not change the shared helper.
- **The rest** is proposal.

## 16. Changes after review

### 16.1 After the round 1 review (`5edfc9b6`)

| Point | Fix | Section |
|---|---|---|
| P1-1: a revision edited by the model grants itself permission to a new destination | The root scope is independent of the criteria. Revision permission = `narrow(root, _deliverable_rel)`. Changing the destination becomes an expansion request waiting for the project owner with a specific path. Legacy is frozen, stated as compatibility. One deliverable per goal | 1, 5.1 to 5.3, 12.2 (G23 to G28) |
| P1-2: permission not pinned to the turn; the `same` branch detours; no ordering against revocation | The `bindings` table pins revision permission, root, `generation`, assistant, turn source. The four-step `host_publish` has a `BEGIN IMMEDIATE` commit point serialized with revocation. Every path that changes the marker goes through it | 4.2, 4.5, 5.5, 9, 12.2 (G29 to G35) |
| P1-3: using `finish_handoff` as if the draft were at the destination; the background submission inserted after the publish step | State transition table by source. Publish bytes from the draft through `host_publish`. `adopt_submission` split from writing the marker. Reorder `_work_post_core`. The Write A + submit B rule. Who-reads-what table. Reconciliation table | 4.4, 4.6, 4.7, 12.2 (G36 to G42) |
| P2-1: choosing the goal by session + path; dedupe by sha only | Choose by the binding of exactly the calling message; with several results, `ambiguous_handoff`. Whole-operation fingerprint. Normalized path key | 4.3, 12.2 (G43 to G46) |
| P2-2: a pause does not preserve revocation when running 0.95.1 code | A downgrade only restores a snapshot. Upgrading again does not grant permission to revisions old code created. `expires_at` removed | 7.4, D10, D11, 12.2 (G47 to G50) |

### 16.2 After the round 2 review (`99c88447`)

| Point | Fix | Section |
|---|---|---|
| P1-1: a path present in the project owner's message does not prove write permission; legacy took the current revision at wake time | `owner_message` only when a pure directive receiver finds exactly one clear write directive, excluding quoted and pasted parts, blocking negation and read verbs; records proposition evidence. When unsure, waits for approval. Legacy frozen in the upgrade transaction, reading the revision stored at upgrade time | 1, 3, 5.2, 5.2.1, 5.3, 12.3 (G51 to G56), D1 |
| P2-1: waiting for approval has no root but submit demands a root; no path to use the draft after approval; old cards | Chose to keep the draft: the `draft` binding pins the pending request, may only submit into the draft area (`awaiting_scope`), no read, no publish. `approve_scope` CAS on request, revision, path, assistant, draft in one transaction, creates a new root, an `approval` binding and an `approved_draft` version; 0 model turns. The old chat turn does not benefit from the new permission. An old card never grants a root | 4.1, 4.2, 4.4, 5.2, 5.3, 8, 10, 12.3 (G57 to G61), D7, D12 |
| P2-2: closing the binding on restart loses accepted versions; missing the row for published but not yet adopted | Split `live` (accepts submissions) from `sealed` (only completes accepted versions under the pinned permission). Two checks `binding_accepts` and `binding_may_finish`. A separate committed-effect rule. Added the row for published but not adopted, key `adopt:<submission_id>`, `adopted_at` holds the schedule release to exactly once | 3, 4.2, 4.4, 4.5, 4.7, 9, 12.3 (G62 to G66), D13 |
| P2-3: `UNIQUE(goal_id, origin_kind, origin_ref)` blocks two revisions in one message | Key `UNIQUE(goal_id, revision, origin_kind, origin_ref)`; reopening the same key returns the existing row, no `REPLACE`; a new revision makes the old version `superseded`. Per-turn root pinning (round 3 used `turn.started_at`; round 4 replaced it with `authority_clock.seq`, section 16.3) so an old turn cannot take the new root by editing again | 4.2, 7.1, 12.3 (G67 to G70), D14 |
| Note 1: re-reading the hash after `os.replace` does not detect an overwritten edit | Rewrote the limit section around three time gaps; states clearly which gap is undetectable | 4.5, G71 |
| Note 2: "published" when only committed | Two messages: "was committed before the revoke" and "published before the revoke" once there is evidence at the destination | 4.5, 8, G32 |
| Note 3: raw snapshot copy with WAL; keep the current store before restoring | Use `_backup_before`; the restore script copies the current store with the backup API first | 7.4, G47, G50, D11 |
| Note 4: the `..` rule is not uniform | Tested: `_brain_file` actually accepts `a/../a/x.md`. Decided the path key refuses `.` and `..` | 2, 4.3, G13, G45, D15 |
| Note 5: order of receipt lookup and live-binding filtering | Identity and the turn's binding first, then the old receipt lookup, then the `binding_accepts` gate for a new submission | 4.3, G46 |
| Note 6: `binding_valid` does not replace `_gate` | `host_publish` steps 1 and 3 run the full `_gate`; stated in sections 1, 4.2, 5.5 | 1, 4.2, 4.5, 5.5, G72 |

### 16.3 After the round 3 review (`efa1fce3`)

| Point | Fix | Section |
|---|---|---|
| P1-1: the directive receiver granted permission from conditional sentences, questions, statements of intent; splitting on periods broke paths | Recognize the path token before any splitting step. A whole-message context gate runs before sentence splitting: `?`, condition, question, intent, negation anywhere means wait. No splitting on commas. A sentence must match a command template **in full**, the opening part only from a closed list. A table of positive and negative examples. Recorded the fallback of dropping automatic granting in D1 | 5.2.1, 12.4 (G73 to G79), D1 |
| P2-1: comparing `created_at` with `started_at` granted wrongly when the clock moved backward or two instants coincided, especially on a turn's first touch of a goal | Store-issued order: `authority_clock.seq` increments in every transaction that creates a root, revokes, approves, re-grants; a turn with an assistant captures `seq` before the engine runs; the first binding only accepts a root whose `seq` does not exceed the snapshot, except a root created by the message itself. Fail closed on read error. `created_at` is for display only | 4.2, 7.1, 11, 14, 12.4 (G80 to G84), D14 |
| Note 1: "Published before the revoke" has the wrong timing | Changed to "Finished the publish that was committed before the revoke" | 4.5, 8, G32 |
| Note 2: without `handoff`, two revisions in the same message give `ambiguous_handoff` | Keep that behavior, state it clearly; the tools that create and edit return a new code, the submit tool's description tells the model to send it along; G67, G68 use the code | 4.3, G85 |
| Note 3: completing a committed effect differs from opening a new effect | A case checking that the old permission only completes exactly the committed action | G86 |
| Reviewer's correction about `_brain_file` | Recorded in section 15; D15 stays as the new rule of `path_key` | 15, D15 |

### 16.4 After the round 4 review (`bd6ad1d1`): D1 finalized

| Point | Fix | Section |
|---|---|---|
| P1: the directive receiver still mistook sentences that mention a command (translation, example, free tail) for write permission | Dropped the `owner_message` source and the receiver from A4. Every new destination or scope change goes through the card; an already granted scope and legacy stay unchanged; an approved draft is published with 0 model turns | 1, 4.2, 5.2, 5.2.1, 5.3, 6.3, 11, 12, 13 (D1, D12), 14 |
| Order exception for a root created by the message itself | Removed, since that source no longer exists | 4.2 |
| Old case expectations based on `owner_message` | G27, G51 to G55, G73 to G79, G82 changed to wait for the card or a root that exists before the turn | 12 |

## 17. Implementation notes

The points below are where the code had to choose something the design did not fully say, or where old behavior changed because of the design. The first two touch the permission mechanism, so they **need reviewer confirmation** before the code is finalized; the code currently chooses the option written down.

| # | Point | What the code chose | Why |
|---|---|---|---|
| I1 | §5.3 says "Revoke (the Revoke permission button, or turning off Resonance for the assistant)" | **Turning off Resonance does NOT revoke the root.** Bindings still die immediately because they pin the assistant version (§4.2 item 3); turning it back on lets a new turn continue under the old root | Keeps the A1 behavior "turn it back on and it keeps going". **The reviewer accepted this at code review round 1**; §5.3 was fixed accordingly |
| I2 | §4.5 lists "republish" but §4.2 has no source for it | When the destination file is deleted, `_publish_latest` creates a `republish` submission that copies the published version, under a **new** `republish` binding that pins the revision permission IN EFFECT now (the old binding is not reused). With no permission in effect, it does not republish | Keeps the A2 behavior "if the file is deleted, republish the effective version, 0 model turns". **The reviewer accepted this at code review round 1**; recorded in §4.2 and §4.7 |
| I3 | A goal with no deliverable path (only user-confirmed criteria) | `scope_state=none`: no scope needed, background work runs like 0.95.1, there is nothing to publish | There is no destination to allow; blocking them would leave the goal stuck forever |
| I4 | Consequence of D1 for Claude | A Write in the turn that CREATES the goal is not adopted (foreign bytes at the destination). Only a submission through `javis_submit_deliverable` is kept as a draft. The hint in the prompt and in the `javis_goal` result tells the brain to submit through the tool, not Write directly | Matches §4.4 ("a draft binding never adopts an in-place Write"). Open question for A5: whether a Write with a receipt should be turned into a draft; the code does not do this yet |
| I5 | A1 decision 4 (republish held output after switching off and on, new intent by the current version) | Replaced by §4.2 item 3: the submission is `stale`, the next wake redoes one turn | "The host never edits an in-progress binding to a new permission". The A1 test's expectation was fixed, with an annotation |
| I6 | A revision created by old code, or a goal just assigned, needs a scope but has no request yet | `_gate` calls `ensure_scope_request`: it only writes a waiting request, grants nothing | So the card has an Allow button; §7.4 |
| I7 | `origin_ref` of a `handoff` binding | Uses `message_ref` (`msg:<session>:<message>`), the same key as the `handoffs` table | Equivalent to the `<session_id>:<message_id>` of §4.2 |
| I8 | Notifying that permission is awaited | No separate outbox message; the card pushed after the chat turn already shows the question, and the card and the Collaborators page also show it | Avoids two messages for the same thing |
| I9 | End-of-turn handoff | `main` hands over EVERY goal that message created or edited (before, only the first goal), the Write receipt is taken once | Each goal with its own binding must be sealed |
| I10 | The path to reconciliation of a committed effect (code review round 1, P2-2) | A separate physical schedule `kind=settle`, set in the commit-point transaction (lock deadline + 1), not parked by pause, revoke, cancel, finish; `due_wakeups` takes it in every state; the `settle` wake only runs `_reconcile_publish` for the committed action, then cleans up the schedule when none remain | A revoke pauses the goal and `_recompute_wake` parks every work schedule, so before this a committed effect lost its path to completion |
| I11 | Temporary I/O error after the commit point (code review round 1, P2-1) | `publish_retry`: keep `running`, extend the deadline with spacing, schedule `settle`; `conflict` only when the destination can be read and differs from both the baseline and the submission | Being unable to read or write is not evidence of a conflict |
| I12 | "Not quite" feedback before the commit point (code review round 1, P1-1) | `_publish_held` reads the newest understanding feedback of exactly this revision INSIDE the intent transaction (including the `same` branch) and the commit-point transaction; if blocked, the submission goes back to `candidate`, and if changed back to "That's right" it publishes next time | A user intervention recorded before the commit point must win, like a revoke |
| I13 | DRAFT FILE read error (code review round 2, P2-1) | `_sub_read` separates `draft_unreadable` (temporary I/O: keep the obligation, `publish_retry` or keep `candidate`) from `draft_missing` and `draft_hash_mismatch` (`reject_submission`: its own reason, not `target_changed`, wrong bytes are not published) | Being unable to read the draft is not evidence the destination file changed |
| I14 | Adoption obligation after publishing (code review round 2, P2-2) | The `settle` schedule is dropped only when no committed action is running AND no published but unadopted `submit_tool`/`approved_draft` version remains; the `same` branch sets the schedule immediately; an error in the adoption step does not escape; the `settle` wake adopts these versions | Publishing and adoption are two transactions; the gap between them must have a recovery path even when the work schedule is parked |
| I15 | Work schedule while a completion obligation remains (code review round 2, P2-3) | `_wake_work` parks `waiting/publish_settling` (part of `_parked`) before considering republish or opening a turn; `_settle_done` lifts the park and recomputes the schedule when the obligation reaches 0 | A valid version already exists, it just has not reached the destination; calling the model now would burn quota for nothing |
| I16 | Publish error arising in the work wake itself (code review round 3) | `_wake_work` calls `settle_pending` again AFTER `_publish_latest`; when `host_publish` meets `draft_unreadable` it does `hold_submission` (column `hold_attempts`, `hold_until`; `_settle_left` counts held versions); the `settle` wake rereads the draft file, releases the hold with `release_hold` if readable, `reject_submission` if lost or wrong hash, and drops the hold if the version is no longer the one to publish; `settle_cleanup` sets the schedule at the earliest obligation's time | The gate at the start of the wake only sees obligations that existed BEFORE; an obligation just born in the tick must also block a model turn, and the uncommitted branch needs a retry path with its own code |
