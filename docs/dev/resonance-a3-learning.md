# Resonance A3: learning from feedback, usage, upgrade, rollback

Design: [2026-10-09-resonance-a3-feedback-learning-design.md](../superpowers/specs/2026-10-09-resonance-a3-feedback-learning-design.md). Verification record: [resonance-a3-verification.md](resonance-a3-verification.md).

## Two learning lanes

**The presentation lane (P):**
- Under each assistant report (a message Jarvis 007 sends into the chat box, carrying a goal card) there is a **How was this update?** row with two buttons, Helpful and Not quite.
- Clicking Not quite shows three reasons: Too long, Too frequent, Unclear. Clicking the lit button again withdraws the feedback.
- Once two different reports have the same reason, Jarvis 007 **proposes**: shorten the "done" report and the periodic update report, or do not ring the bell for the periodic update.
- The proposal sits in the **Lessons** section on the assistant page (Partners page, right column), showing the old sentence and the new sentence of the same message. You click Apply or Dismiss. If nobody decides, the proposal expires after 14 days and the old way is kept.
- This lane never calls the model.

**The method lane (M):**
- When two consecutive turns make no further progress against criteria that Jarvis 007 can score itself (the A2 deadlock), Jarvis 007 may trial the method "Check every point before returning" against the old method, on two scenarios, using exactly the M5 trial.
- It only trials when both conditions hold:
  - **a full-cycle budget**: the 4-turn trial, plus one held turn for redoing the product, plus a reserve turn;
  - **a valid control scenario**: an earlier understanding of the same goal, the same set of criteria, and real different words from the user.
- **A goal with the default 6 turns never trials**: a deadlock after 3 turns needs a quota of at least 9.
- If the new method wins, it is applied to the current understanding only, then the product is redone once using the held turn, and the result is reported. If it loses or is unclear, the old method is kept.

## Things that never happen

- Feedback does not make a goal pass, change the criteria, open a model turn, or change the wake schedule.
- Feedback does not write to the assistant file, the switch, the version or the quota.
- Mandatory messages are always complete and always ring the bell, including:
  - warnings: guard, lost supervision, past the deadline, file write conflict, error, blocked;
  - messages that need you to do something: waiting for confirmation, deadlock, exploration finished;
  - messages about a change of method.
- Ordinary chat text does not accept feedback; only a report with a Jarvis 007 receipt does.

## Revoking

- **Presentation lesson:** click Revoke in the Lessons section, and the next message returns to the default way.
- **Learned method:** click Revert method on the goal card, or Revoke in the Lessons section. The held product-making turn is returned at the same time.
- Editing the understanding (a new revision) makes the just-learned method lapse automatically, because it was only checked for the old understanding.

## Upgrading from 0.88.x

- The first time 0.89 opens a pre-existing `resonance.sqlite3` store: it copies a backup `resonance.sqlite3.pre-a3.bak`, then adds five tables `reactions`, `reaction_log`, `lessons`, `lesson_events`, `call_holds`. Old tables do not change columns.
- Each time the store opens, Jarvis 007 reconciles the held turns: it rebuilds the product-making reason if it was lost, and returns turns that are no longer valid, exactly once.

## Rolling back to 0.88.x

- The old release ignores the A3 tables. Reports return to full length and ring the bell.
- A method that was already applied stays in the M5 column that 0.88 understands, and still only applies to that exact understanding.
- A hold still in `held` still counts in `calls_used` (one turn too many, on the safe side). The old release treats the product-making reason as a check-only reason: it settles it without calling the model.
- Upgrading to 0.89 again: the reconciliation on store open rebuilds the reason (or returns the turn if, in the meantime, the old release cancelled, edited the understanding, or reverted the method). This cycle has a test that runs the real 0.88.1 code (`tests/python/test_resonance_a3_rollback.py`).

## Recovering from the pre-upgrade copy

Stop Jarvis 007, rename the current `resonance.sqlite3`, copy `resonance.sqlite3.pre-a3.bak` to `resonance.sqlite3`, then run release 0.88.x. Every piece of feedback and every lesson after the upgrade will be lost; goals and the A2 schedule stay as they were when the copy was made.
