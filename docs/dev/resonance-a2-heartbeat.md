# Resonance A2: adaptive heartbeat, usage, upgrade, rollback

Applies to release 0.88.0 onward. Full design: `docs/superpowers/specs/2026-10-08-resonance-a2-heartbeat-design.md`. The A1 part (per-assistant switch) still follows `docs/dev/resonance-a1-migration.md`.

## When the assistant wakes up

An assistant with Resonance on calls the model only for one of three reasons:

- **New work:** a goal was just set, or its understanding just changed, and no draft exists yet.
- **New word from you:** feedback on the card, or a recheck you scheduled.
- **A retry still within limits:** after a turn that did not pass, or after an error.

Every other wake-up only runs code, without calling the model:
- the periodic recheck (6 hours, then stretching out to 7 days if nothing changes);
- the deadline check;
- re-checking the assistant switch or the protective conditions.

A draft the assistant writes right inside the conversation counts as the first turn. If it does not pass, the background job fixes it on the retry schedule (15 minutes later), not immediately.

## Retry limits

- **Deadlock:** after two consecutive turns that make no further progress against the criteria, the assistant stops trying and waits. The goal stays open; feedback or a clearer statement continues the work.
- **Errors:** at most 3 error turns, then it stops. A permanent error (the background-job brain cannot run) is not retried.
- **Automatic retries leave one turn spare:** they do not use the last turn of the quota. New work or your feedback can use that turn.
- **Deadline:** close to the deadline it checks more often. Past the deadline without passing, it reports once; Jarvis 007 does not extend the deadline or reach a conclusion on its own.

## A file you edit by hand

If a product file is edited outside Jarvis 007 after Jarvis 007 last wrote it:
- Jarvis 007 does not overwrite it, does not call the model to redo it, and reports once per file version;
- it rechecks itself after 1 hour, stretching out to 24 hours; with feedback it checks right away;
- if the file is put back to exactly the version Jarvis 007 wrote, Jarvis 007 carries on; if your edited version still meets the criteria, Jarvis 007 records that and does nothing more.

## Protective conditions (guard)

- **Goal paused:** still watched by code; if a guard fires, it still reports.
- **Assistant turned off:** stops watching and reports once. The card shows that the protective conditions are no longer being watched. When it is turned back on, it checks right away before any action.

## The goal card

- "Next step" with the reason (for example "periodic recheck", "new feedback").
- The "Details and history" section has "Recent wake-ups": time, reason, and whether the model was called.

There is no new settings field. The time intervals are versioned constants (`heartbeat.v1`) in `server/resonance_heartbeat.py`.

## Upgrading from 0.87.x

- **Nothing to do by hand.** The first time the store is opened, Jarvis 007 copies `resonance.sqlite3` to `resonance.sqlite3.pre-a2.bak` next to the original file, once only.
- **The store only gains four new tables:** `wake_reasons` (wake reasons), `wake_log` (wake ledger, for viewing only), `source_observations` (versions of files edited outside Jarvis 007), `heartbeat_state` (the error and progress streaks used to decide retries). No old table changes a column.
- **Open goals get their reasons rebuilt from the event history:**
  - if no turn has run yet, there is a "new work" reason;
  - feedback not yet handled is still handled once.

## Rolling back to 0.87.x

- **Release 0.87.0 runs on the upgraded store:** it ignores the four new tables. Verified with the real 0.87.0 code in `tests/python/test_resonance_a2_rollback.py`.
- **While running 0.87:** the old MVP heartbeat is active again, so a recheck may call the model as it did before A2.
- **Upgrading to A2 again:** feedback or new work that 0.87 already handled (a turn started after that message arrived) counts as handled, and the model is not called again.

## Recovering from the pre-upgrade copy

`resonance.sqlite3.pre-a2.bak` only has data up to the moment of the upgrade. The procedure is the same as for the A1 copy:

1. Stop the server.
2. Copy the current store (`resonance.sqlite3`, plus `-wal` and `-shm` if present) somewhere else separately.
3. Copy the backup over `resonance.sqlite3`, and delete the old `-wal` and `-shm`.
4. Run release 0.87.x.
