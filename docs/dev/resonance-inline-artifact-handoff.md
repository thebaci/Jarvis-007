# Resonance: adopting a draft the brain wrote during a chat turn

Status: **implemented to this design, awaiting code review.** No model has been run. Sources: pilot run 3 (`docs/dev/resonance-mvp-e2e-pilot-plan.md`, section "Lần chạy 3", i.e. "Run 3") and the review `PR-579-pilot3-review.md`.

## Problem

The brain writes the first draft during the chat turn (`Write`), then sets up a goal. The host has no path to adopt that draft, so:
1. The background job still spends a model turn rewriting the first draft.
2. The background draft cannot be published: the file already exists, but the goal never wrote it, so the overwrite guard leaves the file untouched. That guard is correct and must not be removed.
3. The confirmation card points to the chat's draft A, but the receipt describes the background job's draft B, and there is no published draft. The next revision would take the unpublished draft B as the "previous version" (`_work_step` reads the receipt), not the draft A the user read.

## Principles (following the review)

- A goal reuses a draft that already exists. The source can be chat or a background job. A chat source must not be disguised as a background job turn and does not count as a model turn.
- Split two permissions: **reading the file to evaluate it**, and **being allowed to replace the file in the next revision**. The second is granted only when the host has a write receipt it can verify itself. The model saying "I just wrote it", or having only a path or mtime, is not enough.
- Do not remove the overwrite guard, and do not quietly mark anything as published.

## 1. In-turn write receipt (built by the host)

**The only source is a tool event the host saw during the turn, with the FULL text of the content:**
- Claude Code engine: a `tool_call` event named `Write`, whose `input` has `file_path` and `content` (`claude_sdk_engine.map_message` already exposes `input`);
- API engines and the hub: `javis_write_file`, where the host writes the file itself and so knows the exact bytes.

**No receipt is built** for `Edit`, `MultiEdit`, shell commands, or Codex writes through the shell: the host does not have the full text. The extension is in section 6.

**Recorded in the turn ledger** (`luot_dang_chay`, keyed by the running turn):
- shape `{rel, sha256_lf, seq}`;
- `rel` is the path inside the brain, passed through the same filters as at publish time: `_brain_file`, forbidden paths, file type, size cap;
- `sha256_lf` is the hash of the content after converting CRLF to LF (see risk 1);
- a later write to the same `rel` replaces the earlier one.

**Not evidence until it is reconciled at handoff.** At handoff the host reads the file. The hash (after newline normalization) must equal the hash of the LAST `Write` to that path, and after that `Write` there must be no `Edit`, `MultiEdit` or shell call that targets the same path. If it differs, the receipt is void.

## 2. End-of-turn handoff (avoiding a race with the scheduler)

**When `javis_goal` create or update runs inside a web chat turn:**
- the work schedule is set to `now + HANDOFF_HOLD_S` (proposed 900 seconds) instead of `now`, with the reason "waiting for chat turn handoff";
- so the scheduler does not run a background job in the middle of the turn, whether the brain writes first then sets the goal, or sets the goal first then writes.

**At the end of the turn**, in `_resonance_after_turn`, in the same place that pushes the card, for the create or continue goal of this very message:

1. Check state: the feature is still on, not paused or cancelled, the revision is unchanged from the one this turn created, and there is no guard latch.
2. Look for a valid receipt for exactly the deliverable file `_deliverable_rel(goal)`. If no file is declared, nothing is adopted.
3. **With a receipt:** `store.adopt_artifact(...)` runs in ONE transaction, with the dedup lock `adopt:{goal}:{rev}:{sha}`:
   - re-check the revision and the hash of the current file;
   - save a snapshot into the evidence store (kind `chat_output`, tagged with the revision);
   - record `published(rel, sha, source="chat:<message_ref>")` as the baseline. This baseline grants the right to replace the file in the next revision, because the bytes are exactly the bytes written in that turn, as verified by the host;
   - record an `artifact_adopted` event (path, sha, message_ref, session);
   - if recording the evidence fails, do NOT announce adoption; fall back to the no-receipt branch.
   After that, set the work schedule to `now` so `advance` evaluates right away.
4. **Without a receipt:** set the work schedule to `now`, keeping current behavior. If the file already exists, the conflict message states the real cause (fixed in this version).

**Failed turn, restart, or `after_turn` not running:** no handoff happens, the schedule still comes due after `HANDOFF_HOLD_S` and runs as it does today. Safe, only slower. If the handoff runs again, the dedup lock keeps the evidence from being duplicated.

## 3. Evaluate first, then choose the next step (fixes at the read points)

- `advance` and `_human_only`: `refs` include both `action_output` and `chat_output` of the current revision.
  - If only user confirmation is left: wait, do **not** call a background job.
  - If an objective criterion is not met: the background job revises from exactly the adopted draft, within budget.
  - "Has a first draft" does not by default mean "ready to wait for approval".
- `_artifact_file`: an adoption in the current revision counts as a successful work turn when choosing the file for the card.
- `_work_step`, previous version: take the **version in effect**, meaning the target file when its hash equals the `published` baseline (from a background job or from chat). With no baseline, take the background job's receipt as before. This way a revision builds on the draft the user read.
- An old confirmation does not apply to a new hash or revision. This already exists (`artifact_ref` per click, `guard_seq`); the tests in section 5 will check it again.
- Feedback that creates a new revision: the old draft is only an input to revise, and does not by itself become the passing deliverable of the new revision. If the feedback turn has a valid receipt (the brain revises it itself with `Write`), that draft is adopted for the new revision and then re-evaluated.

## 4. Two small fixes (ALREADY done in this commit)

1. **The conflict message states the real cause.** The payload has `had_baseline`. When there was never a baseline: "File ... already exists and has not been adopted by this goal, so Jarvis 007 left that file untouched. The draft Jarvis 007 just made was not published...". The sentence "was changed after Jarvis 007's previous write" is used only when there is a real baseline. Test in `test_resonance_mvp_run.py`.
2. **The runner keeps every background output**, including drafts that could not be published, next to the report, together with the receipt, hash, publish status and publish event. If saving fails, the sandbox is not cleaned up and this is reported clearly.

## 5. Tests with a fake engine (written together with the core)

Following the eight review cases:
1. Chat `Write`s a valid draft then sets up a goal: the right draft is adopted, 0 background turns, waits on the user's criterion.
2. Set up the goal first, then `Write`: the scheduler does not run before handoff; adoption is correct.
3. Replace permission is not granted by itself when:
   - the file existed beforehand;
   - the file was written by another turn or session;
   - the file was `Edit`ed after the `Write`;
   - the file was changed after the snapshot.
4. The chat draft does not meet the criteria, or the guard does not clear: not reported as done. The background job revises from draft A, keeping the guard rules, cost and permissions.
5. Feedback then a background revision: the prompt contains draft A. Feedback where chat itself `Write`s a revised draft: adopted for the new revision, 0 background turns.
6. No duplicated evidence or calls, no wrong-state side effects when:
   - restart, repeated handoff;
   - the revision changes midway;
   - pause, cancel, feature turned off.
7. Hash or revision changes after confirmation: the old confirmation does not make the new draft pass. Adoption does not create a fake background receipt.
8. A publish conflict reports the correct cause (already done).

**The pilot contract changes accordingly:** S2 and S5 accept "adopted or published", and do not demand exactly one background turn. The cap of 2 Opus and at most 2 Sonnet is still a cap, not a quota that must be spent. Acceptance checks the adoption or publish receipt, hash, revision, evidence and the notification; the quality criteria are not loosened.

## 6. Out of scope for this version (proposed for later)

- **Receipt for `Edit` and `MultiEdit`:** the host has `old_string` and `new_string`, so it could rebuild the content if it had a snapshot from the start of the turn. But the `tool_call` event reaches the host almost at the same moment the CLI executes the tool, so taking a "before edit" snapshot can miss. Needs its own design.
- **Engines without the full text** (Codex writes via shell): no automatic adoption. The right path is to let the user allow it, for example a "Use this draft" button on the card; that is UI work.
- **A reminder in the result of `javis_goal`:** "goal created; to edit the deliverable file, write the whole file with Write or let the background job do it". It only reduces frequency and does not replace the handoff path. Can be added later if the review wants it.

## Risks and questions for review

1. **Newlines.** Claude Code on Windows may write `content` with CRLF. Comparing hashes after converting CRLF to LF keeps "exactly the content that turn wrote" without breaking on newlines. The evidence still stores the real bytes and the hash of the real bytes. Does the review accept this normalization?
2. **`HANDOFF_HOLD_S` = 900 seconds.** If a chat turn is cut off, the background job is delayed by at most 15 minutes. A shorter value risks cutting into a long chat turn.
3. **Scope of change** is within:
   - `luot_dang_chay`: the receipt ledger;
   - five engine branches in `main.py`: call one helper that records a receipt;
   - `resonance_store`: `adopt_artifact`, baseline with `source`;
   - `resonance`: `advance`, `_human_only`, `_artifact_file`, previous-version source;
   - `javis-goal`: place-holding schedule;
   - the pilot runner: S2 and S5 contract.
   The feature is still off by default. A brain that has not turned Resonance on does not go through any path above.

## Done (awaiting code review)

The two questions above were settled as proposed; the review may change them:
- compare after converting CRLF to LF;
- `HANDOFF_HOLD_S` = 900 seconds.

**Code:**
- `resonance.py`:
  - `note_turn_write`, `drop_turn_writes`, `handoff_after_turn`;
  - `_output_refs`: `advance` also counts `chat_output`;
  - `_effective_text`: the previous version for `_work_step` is the version in effect;
  - `_artifact_file` accepts the adopted draft;
  - `form_goal` and `revise_goal` accept `hold_until`.
- `resonance_store.py`: `adopt_artifact` (one transaction); `create` and `revise` accept `work_due_at`.
- `javis-goal/plugin.py`: creating and updating inside a chat turn holds the schedule.
- `main.py`:
  - `_resonance_note_write` in the Claude engine branch (`_consume_claude`) and the API engine branch;
  - `_resonance_after_turn` calls the handoff and records the `resonance.handoff` trace.
- Achieve pilot runner:
  - S2 and S5 accept "adopted or published";
  - the wait condition is tied to the notification of the exact revision, not reading the previous revision's `run_state`.

**Tests:**
- `test_resonance_inline_handoff.py` (40 checks, fake engine, real store), following the eight review cases:
  - Write then set up, set up then Write;
  - pre-existing file, receipt from another turn, Edit after Write, outside the brain, tool without full text;
  - evidence failure;
  - a chat draft that does not pass, so the background job revises from that draft;
  - pause, feature off;
  - feedback on both paths;
  - revision changes midway, restart, old confirmation.
- `test_resonance_mvp_main.py`: the real wiring in main.
  - Handoff releases the schedule.
  - A Write in a turn, through the exact helper the engine branches call, is adopted.
  - A goal passes without a background turn.

**Remaining limits:**
- The runner's `dry` mode sets up goals directly with `form_goal`, so it does not go through the handoff. The handoff is only checked by the two tests above.
- The Grok, Antigravity and Codex engines do not record receipts yet (no full text in the event), so they run as before.


## Fixes from the handoff code review (`67007b7d`, 2 P1, 2 P2)

The review answered three questions:
- **CRLF/LF:** accepted for COMPARING the content of a Write that already succeeded. The evidence hash, the replace baseline and `artifact_ref` remain the hash of the real bytes.
- **900 seconds:** only a reconciliation point, handoff state is needed. Done, see P1-2.
- **Before pilot 4:** fix the four points below, without spending more model turns yet.

**P1-1, a failed Write was still adopted.** The SDK mapper (`claude_sdk_engine.map_message`) now keeps the call `id`, and the result's `tool_use_id` and `is_error`. `note_turn_event` treats a `Write` call only as a **candidate**. Only a successful result tied to the same id confirms it.
- Error result, missing result, or the result of a different call: no receipt.
- Any tool not on the list of tools known to be read-only (Edit, Bash, unknown MCP...), if called AFTER a Write, invalidates that Write, even if the final content matches again.
- A background shell or Task invalidates the whole turn.
- Bash called BEFORE the Write (e.g. `ls`) has no effect.
- The API engine's `javis_write_file` has no host-confirmed write result tied to the exact call yet, so it was removed from the list that builds receipts. The API engine runs as before.

**P1-2, a background job ran before the handoff, and old output overwrote the adopted draft.** The handoff is now **state in the store** (the `handoffs` table), not a scheduled time.
- One row per revision created or revised in a chat turn, recording the message and the owning process (`BOOT_ID`). The row is opened in the same transaction as `create` / `revise`.
- `advance` calls `handoff_gate` before publishing or doing work:
  - this process's own chat turn is still running (`luot_dang_chay.dang_chay`): wait, wake again after `HANDOFF_POLL_S` = 30 seconds;
  - the turn is no longer running, or `BOOT_ID` differs (the server restarted): hand control to the background job (`expired`) right inside the transaction.
- `finish_handoff` adopts only when the row is still `pending`. A handoff arriving late, after the background job has taken control, returns `handoff_expired`, adopts nothing and sets no baseline.
- Extra defense: `_publish_latest` does not publish a background output OLDER than the adopted draft of the same revision (`superseded`).
- `HANDOFF_HOLD_S` is now only the time of the first schedule.

**P2-1, outputs without a receipt were missed.** `_e2e_achieve_harness.preserve_work_outputs` looks by both the receipt and the host-defined path (`output_root/<action id>.md`, exactly where `_reconcile` reconciles), and every stray .md file in the work area.
- A draft without a successful receipt is saved with the label `unverified`, and is not promoted to succeeded.
- Save failure, missing storage, or an action that succeeded but no file found: the sandbox is not cleaned up.

**P2-2, the runner wrongly rejected a valid revision path.** `adoption_contract` reads the reason of **each** background turn (`intent.last_verdict`, written by the host before calling the model).
- 0 turns: pass.
- With turns: every turn must be for `not_met`, have a succeeded receipt, and not exceed the remaining cap.
- A turn that runs when the draft already passes is pointless rework: reject.
- The first evaluation is not used, because a failed evaluation right before a work turn is not saved as its own row.

**Tests:**
- `test_resonance_inline_handoff.py` rewritten against the real SDK mapper, with the review cases reproduced:
  - Write error, missing result, result of a different call;
  - Bash after Write, Edit then revert, background shell;
  - Bash before Write, Write then ToolSearch and javis_goal (the pilot run 3 path);
  - past 900 seconds while chat is still running;
  - a turn that ends without handoff, a late handoff, restart;
  - old output does not overwrite.
- Mutations re-checked:
  - treat the call as already confirmed: 2 checks red;
  - remove the handoff gate: 5 checks red.
- `test_resonance_e2e_achieve_harness.py` adds the P2-1 and P2-2 cases, and the exact product path: a BAD chat draft is adopted, the background job revises in one turn, the contract accepts.
- `test_sdk_engine.py` and `test_resonance_mvp_main.py` updated for the new event shape.

## Fixes from handoff code review round 2 (`15cbf200`, 1 P1, 2 P2)

**P1-1, an MCP tool ending in `Write` was treated as the original Write.** Tool identity is now the FULL NAME, with no suffix stripping.
- Only Claude Code's exact `Write` creates a candidate. `mcp__remote__Write` is an MCP that reports success, not a local write.
- The read-only list consists of Claude Code's own tools and exactly the Jarvis 007 tools through the two servers Jarvis 007 knows well (`mcp__javis__...`, `mcp__javis-plugins__...`).
- Other MCPs, including `mcp__untrusted__Read`, take the conservative branch: they invalidate the Writes before them.

**P2-1, a living turn lost its authority after three hours.** `luot_dang_chay` gets an additional LIVE ledger `_SONG`.
- Only `ket_thuc` (called in the turn's `finally`) removes entries; it is not cleaned by age.
- `dang_chay` reads only this ledger.
- `_DANG` is still cleaned by age, because it is used only to guess who assigned the work.
- A turn that really ends, or a server restart, still releases authority.
- Assumption: one server process owns the store.

**P2-2, the adopt-then-revise branch lost the receipt check.** `_e2e_achieve_harness.work_receipt_ok` is the shared receipt contract for every background turn, on both the S2 and S5 branches:
- status succeeded;
- real provider = requested provider = approved provider;
- real model = requested model = approved model;
- `tool_calls_observed` is the number 0;
- a missing field means it does not pass.

`adoption_contract` adds the adoption path's own conditions (reason `not_met`, within the cap) on top of the shared contract.

**Tests:**
- `test_resonance_inline_handoff.py`: added an MCP ending in Write, an unknown MCP ending in Read, a control with a known Jarvis 007 tool, a turn alive past three hours, and a turn that really ends being removed from the ledger.
- `test_resonance_e2e_achieve_harness.py`: added cases for wrong provider, providers that match each other but differ from the approved one, wrong model, tool calls present, missing fields; the product path with a wrongly edited receipt is rejected; runner source audit.
- Mutations re-checked:
  - strip the name suffix again: 4 checks red;
  - `dang_chay` reads the age-cleaned ledger: 2 checks red.
- The script `PR-579-handoff-round2-checks.py --expect-fixed` stops at line 101, because `adoption_contract` now needs the approved engine parameter (an intentional change from P2-2). The call in the script needs updating.
