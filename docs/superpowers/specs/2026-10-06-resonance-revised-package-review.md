# Review of Claude's revised Jarvis 007 Resonance package

Date: 06/10/2026.

**Current role:** a reference review for use when implementing the [MVP](../plans/2026-10-06-resonance-00-mvp.md), not a standalone plan. Claude confirmed the five P1 bugs and the main gaps in section 6 in the feedback the user supplied; agreeing does not mean the code has been fixed. See the [finalized index](../README-RESONANCE.md). The source ZIP and the older critiques have moved into the [historical package](../../../exports/archive/Javis-Resonance-LICH-SU-2026-10-06.zip); the source paths below record locations at the time of the review and are no longer the version in use.

> Correction after checking the remote on 06/10/2026: the checkout that was reviewed is `codex/restore-chat-colors` at `5b4a9be1`, which has 3 commits of its own and is missing 121 commits compared with `origin/main` at `7d264236` (0.83.2). `git ls-remote` confirmed the remote main has the same SHA. On this main, `_reply_policy_sandbox_engine` is at `server/main.py:1895` and `_reply_policy_ask` is at line 1955. The remarks below that the functions were not found are only true for the old checkout, and are not a gap in the current main. Before M1, pin the base commit from the latest main and re-check every integration point; the logic bugs reproduced from the code in the ZIP are not changed by this correction.

## Conclusion

Adopt the overall design and the `00-mvp` plan as the standard. The code appendix is not consistent enough to use as direct implementation guidance. There are correct fixes that were verified, but some parts only fixed the description or the tests while the old code remains.

A new architecture round is not needed. We can move to M1 when asked to implement; the appendix bugs do not block verifying the engine and receipts. Before M2/M4, the appendix passages that contradict the standard plan's contract must be fixed or removed from the implementation path.

This is the result of reviewing documents and illustrative code, not the result of software acceptance or an engine pilot.

## Package that was checked

Source: `D:\Download\Javis-Resonance-ban-chot-2026-10-06.zip`.

The ZIP has 8 files and the integrity check succeeded. SHA-256: `cd1450491e5c1837d53ae24bdf2421f0529cb0e03edccba2c5d5f1d90c9ea220`.

Six base documents have content identical to the set already in the workspace: the design, the cross-check, the MVP plan, and the three extension plans. The two additions are the code appendix and the summary in the brain. These two were compared with the earlier ZIP to check exactly what changed, and are not treated as a new design.

All line numbers below refer to `docs/superpowers/plans/2026-10-06-resonance-00-mvp-phu-luc-code.md` in the ZIP, unless another path is stated.

## Fixes that worked

| Item | Evidence | Status |
|---|---|---|
| Choose `00-mvp` as the standard, the appendix yields on conflict | Stated at the top of the appendix and in the summary | Implementation direction settled |
| Undo checks the hash after the write | Ran the proposed function with a temp file the user had edited: returned a conflict, kept the new edit | The sequential-overwrite case is fixed; not proven that the whole undo adapter is safe |
| Separate goal-fit from the result and criteria | `human_confirmation`: `fit_confirmed` for an unknown result; accepting c1 makes c1 met, c2 stays unknown | Fixed at the evaluator |
| The confirm API has `expected_revision` and checks `criterion_id` | Lines 1734-1750 | Right direction at the API; the UI and the old callback are not yet in sync |
| A deadline set by the model by itself becomes a review milestone | Lines 1355-1359 | Progress in representation; does not yet replace cross-checking the source of a deadline the user stated |

## 1. P1: The old emoji callback still confirms the wrong version

The description at line 1615 and the test at lines 1670-1671 say an emoji does not confirm a goal. But `on_feedback_goal_card()` at lines 1792-1811 still turns like/heart/wow into `fit_confirmed`, taking the current revision in place of the revision on the card. `register()` at line 1817 still registers this callback when deps exist.

**Reproduced with the appendix's own function:** the card is revision 1, the current goal is revision 2, and a like click produces a `fit_confirmed` event for revision 2. The bug raised in the previous round is still there through this callback path, even though the new button API checks the version.

**Fix:** remove the emoji-to-evidence conversion from the callback and from the registration path. Only accept evidence through an explicit action that carries a revision, is authenticated and has its scope checked. The test must go through the real registration path, not only check the new API function.

## 2. P1: A new goal still shows the old version's met result

`_goal_view()` at lines 1704-1710 calls `store.assessments(g.id, limit=1)` without filtering by revision. This passage is unchanged from the previous version.

**Reproduced:** goal revision 2 but the only assessment is revision 1/met; the view returns `last_assessment.verdict = met` under revision 2.

**Fix:** fetch the assessment of exactly the current revision and return the version information with the result. The old assessment stays in the history. Add a test that checks the view/API after a reframe; a test that only checks the assessment row in SQLite does not catch this bug.

## 3. P1: The tool classification fix passes the wrong data type

The wrapper at lines 372-399 takes `connector_id` as a string and passes it to `mcp_catalog.classify`. The real function at `server/mcp_catalog.py:426` needs a connector dictionary; line 431 calls `c.get("tool_meta")`. The real path in `server/mcp_hub.py:1069` gets the dictionary through `mcp_catalog.get(conn.get("connector_id"))` before classifying.

Because the wrapper catches the exception and falls back to `static_effect`, a multi-action tool can still keep the read label from listing time and is not recorded in the ledger when it performs a successful write.

**Reproduced:** with a fake tool that has a write action, the classifier using the connector dictionary returns write; the proposed wrapper passes a string, falls back to read and records 0 rows instead of 1. No real connector or tool was called in this check.

**Fix:** resolve the connector correctly per the repo's interface and classify by the call's args. If it cannot be classified, record an explicit undetermined state instead of silently dropping the log based on the old read label. The authority check still belongs to the existing guard path; this observation bug does not by itself prove the authority guard was bypassed.

## 4. P1: The four routing branches are not yet wired into correct behavior

`route()` at lines 1376-1386 has four labels but does not check the relation of the new sentence to the current goal. As soon as an open goal exists, almost every sentence that is not a create-new command becomes `continue_goal`.

**Reproduced:** with an open goal, both "cảm ơn em" (thank you) and "giải thích SMART là gì" (explain what SMART is) are sent to continue_goal. The sentence "giúp anh làm việc đỡ rối" (help me get less tangled up at work) with no goal yet is decided as task_now only because it has M and lacks T. These results show the regex cannot tell apart a need to understand something, work to do right away and work that needs to be pursued.

The real call path at lines 1418-1421 does not pass `open_goals`; `maybe_frame_turn()` returns immediately for every decision other than create_goal at lines 1391-1393. A comment says the caller will handle task_now/continue_goal, but the integration passage has no such step.

**Fix:** use the context and the orchestration result that already exist to choose the branch, and do not infer the relation just from an open goal. Wire the follow-up branch fully to the related goal. T and M are clarified by the agent when needed; do not require the user to speak in keyword templates, and do not create a background task just because of a word that refers to a document/result. The MVP plan already states these conditions correctly, and no separate classification service needs to be added.

## 5. P1: The confirm buttons and card data do not fully match the new API

The new API requires `expected_revision`, and for an outcome also requires `criterion_id`. The card added `data-goal-rev`, but `goal_block()` still sends the list of criteria as a description string. `goalCardHtml()` at lines 1828-1843 has one general Meets the bar button that carries no criterion ID; the handler guidance at line 1847 only says to send the kind.

If implemented exactly as the described handler says, the request will lack a revision; even if a revision is added, the outcome button still does not know which criterion is being confirmed. This is a gap in the UI contract, not the result of an actual browser run.

**Fix:** send the revision together with the identifier of the output/criterion the user sees. One action can confirm a clearly displayed set of criteria, and the user need not click each criterion if that is not needed. Test from the card through the request to the assessment, not only the API by pre-filling the fields that the UI does not supply.

## 6. Conditions raised in the previous round that must still hold when taking the appendix code

- **Goal correction keeps context:** line 1775 only passes the new sentence to the framer; line 1779 creates a new intent but `revise()` at lines 1055-1068 does not update `intent_id`. There is no expected_revision for a reframe or lock to prevent creating a duplicate goal from the same message.
- **Traceable evidence:** the final evaluator still reduces evidence to a hash/resource in the assessment, and does not link to a durable record/snapshot in the EvidenceStore. This part must follow M3 of the standard plan.
- **Do not require approval of every goal:** creating a draft and only switching to active after fit_confirmed is still in the sample code; it must be replaced with the MVP's self-forming/executing loop. Do not use the confirm callback as a general unlock condition.
- **Data source and audit errors:** the appendix still has a rotating JSONL with the same principle of swallowing every error. The MVP requires SQLite as the canonical source, and when the mandatory log fails, no new effect is sent. A secondary log may be kept for diagnostics, and must not replace the canonical source.
- **Feature off and scope:** the global ledger hooks still need to be checked against the feature-off commitment. The sample store/API does not yet accept a principal and check scope as the M2/M4 contract requires.
- **Engine hook point:** the names `_reply_policy_ask` and `_reply_policy_sandbox_engine` were still not found in `server`/`tests` of the checkout that was reviewed. M1 must fix the adapter from the actual code.
- **Test quality:** line 1249 still has `... or True`, so that assertion proves nothing. The evaluator test adds one assessment write but line 1495 still demands exactly two assessments of revision 1; update it to the number of evaluations that really occur. Do not use a test name or a statement "fixed" as evidence that it ran green.

These items are not new expansion requirements. They are the differences between the appendix and the standard plan that both sides have agreed on.

## How to close this version

1. Keep the design and the MVP plan as the canonical source. The three extension plans do not need editing in this review round.
2. Define the appendix as a reference sample that has not been accepted. Fix or remove the old callback, handler and integration points; do not let the A1-A9 checklists form a roadmap competing with M1-M5.
3. When asked to implement, do M1 first. Then take each part of the appendix through the behavior tests of M2/M4 instead of copying whole modules.
4. Only finalize code when the real paths through the UI, API and data store meet the contract. No new principle is needed; what is needed is to carry out the principles already settled.

## Scope of verification

Ran, under control, the functions that had been read beforehand: route/tier1, the feedback callback, the goal view, undo with a temp file, human_confirmation and the tool wrapper with a fake tool and the existing classification function. The two fixes, sequential undo and the evaluator with the right criterion, gave the expected results. The callback, view, classification and routing bugs were reproduced as described.

The whole test suite in the appendix was not run; main, the HTTP server, the engine, connectors and real project operations were not run. The ZIP was not extracted over the standard documents, no application code was changed, and none of the implementation instructions inside the ZIP were carried out.
