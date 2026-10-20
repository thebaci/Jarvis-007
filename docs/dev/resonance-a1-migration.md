# Resonance A1: usage, upgrade, rollback and recovery

Applies to release 0.87.0 onward (per-assistant Resonance, shown as "Auto" in the UI). Full design: `docs/superpowers/specs/2026-10-08-resonance-a1-agent-scope-design.md`.

## How to use

1. Go to the **Partners** page, pick an assistant, and open the **Settings** tab in the right column. The **Auto** block (Resonance) is at the top.
2. Turn the switch on. The first time, Jarvis 007 issues the assistant its own key (not written into the assistant file).
3. Chat with that assistant. When you hand it work that must be pursued until done, the assistant sets a goal. The **Assistant goals** panel in the same place shows its understanding, criteria, product, what it is waiting on, the next run, the number of turns used, and the Pause and Cancel buttons.
4. The **Settings** page has a list of all assistants with their switches, and a **Waiting for assignment** section.

Things to know:
- A normal chat (the Chat page) does not set goals, even if the model tries to call the tool.
- With the switch off, the assistant still chats and does one-off work as usual. Open goals stand still; viewing, pausing and cancelling still work.
- Turning it back on does not reopen a goal that was paused, cancelled or finished. A valid output finished before the switch went off is posted without calling the model again.
- If you see **"this conversation was opened before the assistant got its key"**: click **Open a new conversation**. The common case is an assistant that was deleted and then recreated with the same name.
- Assistant engine:
  - Claude Code: sets goals and receives the draft right inside the conversation.
  - Codex and the API engines: can set goals; a draft written in the conversation is not yet accepted as the product (left for A4), and the background job produces the passing version itself.
  - Grok and Antigravity: cannot set goals yet, and the UI shows a warning.
- If an assistant loses its file or is renamed by hand: its Resonance is blocked. Once the file is back, choose **Same assistant** (keeps the key and goals) or **This is a new assistant** (new key, must be turned on again).

## Upgrading from 0.86.x

- Nothing to do by hand. The first time the store is opened, Jarvis 007 copies `resonance.sqlite3` to `resonance.sqlite3.pre-a1.bak` next to the original file (in the `JAVIS_STATE_DIR` folder), once only.
- The store only gains new tables (`resonance_agents`, `resonance_agent_events`, `session_agents`, `goal_agents`, `handoff_agents`). No old table changes a column.
- The old per-brain switch (`<brain>/Javis/resonance.json`) no longer grants anything. The file is not deleted.
- Goals that existed before (not yet belonging to any assistant) move to a waiting-for-assignment state:
  - they do not run on their own and are not assigned automatically by name;
  - go to **Settings → Waiting for assignment**, pick an assistant, click **Assign**;
  - assignment is one-time and cannot be moved to another assistant in A1;
  - output produced before assignment is not posted; the assistant redoes it under its own permissions.

## Rolling back to 0.86.x (keeping the upgraded store)

Release 0.86.1 runs on the upgraded store: it ignores the new tables. This was verified with the real 0.86.1 code in `tests/python/test_resonance_a1_rollback.py`. Before rolling back:

1. **Turn off the old brain switch** (`Javis/resonance.json` of every brain, or leave it off). Releases 0.86.x do not know the per-assistant switch and go back to using the brain switch; if it is not off, goals may run on their own during the transition.
2. Roll back the image or release to 0.86.x as usual.
3. Turn the brain switch back on only when the project owner decides to.

Upgrading to A1 again afterwards:
- the assistant ledger, conversation links and assigned goals are intact;
- goals created while running 0.86.x do not belong to any assistant yet, so they sit in **Waiting for assignment**.

## Recovering from the pre-upgrade copy

`resonance.sqlite3.pre-a1.bak` only has data up to the moment of the upgrade. Goals, events, evidence and assistant-ledger entries created afterwards are **not** in the copy.

1. Stop the server.
2. Copy the current store (`resonance.sqlite3`, plus `-wal` and `-shm` if present) somewhere else separately, to keep the new state.
3. Copy `resonance.sqlite3.pre-a1.bak` over `resonance.sqlite3`, and delete the old `-wal` and `-shm`.
4. Run release 0.86.x (per the section above, turning off the brain switch first).

Do not run the recovery on the real store without the copy from step 2.
