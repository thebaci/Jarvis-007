# Recurring jobs across brains: unified display, moving, remembering the Telegram brain

Date: 2026-07-19
Status: design approved, implemented right away at the project owner's request

## Problem (root cause, not a feeling)

Project owner: "Recurring jobs created through Telegram are saved to the default brain by default, and when I look in the brain I'm working in, they are not there. In real use it's confusing."

Tracing it to file:line confirms there are TWO separate notions of "current brain":

- **Telegram** (`main.py:4627` `_tg_brain`): each chat is tied to its own brain in `_TG_SESS` (RAM).
  Before `/brain` is typed, it falls back to the default brain (`_read_loop_config().get("brain","brain")`).
  In practice almost nobody types `/brain`, so every job created through Telegram silently lands in the Default Brain.
- **Dashboard** (`console.js:919,950`): the Scheduled page (`renderSelfImprove`) reads ONLY the brain selected in the sidebar (`fbrain()` = `currentBrainPath()`). Loops, reminders, and the
  enable/disable/delete buttons are all bound to `brain=fbrain()`.

The two are not linked. Create a job via chat (it goes to the Default Brain), then open the dashboard while on
another brain, and the Scheduled page is empty. **The job STILL runs** (the scheduler scans every registered brain,
`self_improve.py:423` `scheduler_brains`), so this is purely a problem of SEEING and CONTROLLING, not of lost jobs.

One more layer: `_TG_SESS` is wiped by `_TG_SESS.clear()` on every bot restart
(`main.py:5098`). So even after switching brains with `/brain`, one restart sends it back to the default.

## Not merging into a single store (considered and rejected)

Storing per brain is INTENTIONAL: a loop is an `.md` file in `<vault>/Javis/loops/` (editable in
Obsidian, committed with the brain's git, `self_improve.py:11`); reminders are `<vault>/Javis/reminders.json`.
The 2026-07-17 spec settled on keeping it that way. The right direction is not to cram everything into one store, but to build a
**cross-brain display layer and control layer**, and leave the storage layer unchanged.

## Design: 5 pieces

### Piece 1 - Display merged across all brains

A new endpoint `GET /viec/all` (main.py, where `loop_feature`, the `reminders` feature and
`list_brains` are all available). It iterates over `list_brains()` (NOT only registered brains - it must also show brains that have
loops/reminders but have never been opened), and for each brain returns:

```json
{"brains": [
  {"name": "Kim Khí Hà Lộc", "path": "...", "is_default": false,
   "loops": [ <loop_view + brain attached> ],
   "reminders": [ <pending reminder + brain attached> ]}
], "running": false, "running_slug": ""}
```

- A loop item reuses `loop_feature.loop_view(brain, lp, state)` exactly as it is today, adding `brain_name` +
  `brain_path`.
- A reminder item reuses the `pending` view of `reminders._load` + `_view`, adding `brain_name` +
  `brain_path`.

`renderSelfImprove` (console.js) switches from reading `/loops?brain=` + `/reminders?brain=` (one brain)
to reading `/viec/all` (all brains). Group by brain: the brain selected in the sidebar (`fbrain()`) goes
first and is highlighted; the other brains are gathered below, each group with a heading showing the brain name. Each loop/reminder card
carries a label with its own brain. The enable/disable/delete/run-now/cancel buttons switch from sending `fbrain()` to sending **the item's
own brain** (`lp.brain_path` / `r.brain_path`) - this is the easiest place to go wrong: today every button
sends `fbrain()`, and after merging, forgetting to change it means operations on an item from another brain would target the wrong brain.

### Piece 2 - Moving a job to another brain

A "Move to brain..." button on each card, listing the brains (except the item's current one).

- **Loop**: `POST /loops/move` (self_improve router): `slug`, `from_brain`, `to_brain`.
  - Read the source loop (`get_loop`); missing -> error.
  - The destination already has a file with the same slug (`_loop_path(to_brain, slug).exists()`) -> **error, do NOT overwrite**
    (identity is by file name, `self_improve.py:319`; the builtin `tu-cai-tien-javis` exists in every brain,
    so this is a real collision that will happen).
  - That exact loop is currently running (`self._running`) -> error "running, try again later".
  - `save_loop(to_brain, lp)` -> `delete_loop(from_brain, slug)` -> move the `loop-state.json` entry
    (source to destination; if it cannot be moved, let the destination start fresh) ->
    `register_brain(to_brain)`.
- **Reminder**: `POST /reminders/move` (reminders router): `id`, `from_brain`, `to_brain`.
  - Pop the record from `<from>/reminders.json`, push it into `<to>/reminders.json`, keeping the `id`
    and every field (chat_id, cron, due_at...). Save both files.

`owner_chat`/`chat_id` are kept when moving, so results are still reported to the person who set the job.

### Piece 3 - Creating on the dashboard with a chosen target brain

The "+ New loop" form (console.js `openForm`) gets a target brain dropdown (filled from
`/brains`), defaulting to the brain being viewed (`fbrain()`). `#lpSave` sends `brain` = the chosen value instead of
the hard-coded `fbrain()` (`console.js:847`). No change to the `POST /loops` backend (it already accepts `brain`).

### Piece 4 - Chat states the brain clearly when creating a job

`javis_schedule` (system/plugins/javis-schedule/plugin.py) currently reports "Created... at
Javis/loops/<slug>.md" but does NOT say which brain (`plugin.py:249`). Change it so the confirmation names the
brain: "Created the job 'Scan orders' in brain **Kim Khí Hà Lộc**, runs every 120 minutes, currently off,
go to the Work tab to turn it on."

- `brain_name = Path(vault_root).name` (vault_root is the session's brain path).
- Change `_create_loop_file` (add brain_name to the returned sentence) and `_post_reminder` (accept brain_name,
  add it to the sentence "Set... in brain X").

This plugs the confusion RIGHT at creation time: the user instantly knows which brain the job landed in, instead of
searching for it and being surprised later.

### Piece 5 - Persistently remembering the Telegram /brain choice

Problem: the session brain lives in `_TG_SESS` (RAM) and is lost on restart.

- A persistent map `chat_id -> brain name`, written to `STATE_DIR/tg_brain.json` (server state, gitignored,
  cross-brain, NOT inside any vault - the same place as `.sessions.json`, `config.py:228`).
- Store by **brain name**, not an absolute path (durable across Docker/local + brains that move). On read,
  resolve name -> path (`Path(BRAINS_DIR)/name`); a deleted brain -> fall back to the default + clean up the stale
  entry.
- `_tg_set_brain(chat_id, path)`: write both the live session (as before) and the persistent map (`name=Path(path).name`).
- `_tg_brain(chat_id)`: live session first -> persistent map -> default.
- `_TG_SESS.clear()` on restart stays as is (the conversation still resets); the brain survives because it is read from the
  separate persistent map.

Result: whichever brain `/brain` switches to sticks until another is chosen, even after a restart.

## Out of scope

- How Telegram picks the default brain when `/brain` has NEVER been used (still falls back to the Settings default brain) -
  unchanged. Pieces 4 + 5 make it transparent and durable, which is enough; no new "main working brain" concept is added (the project
  owner does not want extra configuration).
- Kanban tasks (`tasks.py`) - they have no clock and do not belong to the recurring-jobs axis. Unchanged.
- Merging into one store - rejected above.

## Risks

1. **Action buttons targeting the wrong brain after merging.** The easiest place to go wrong: every button currently sends `fbrain()`.
   After merging, they MUST switch to the item's own brain. Needs a test: enabling/deleting an item in brain B
   while the sidebar is on brain A must act on brain B.
2. **Moving a loop whose slug already exists at the destination** (builtin `tu-cai-tien-javis` exists in every brain) - must
   fail clearly, NOT overwrite. Needs a collision test.
3. **The persistent map stores the brain name** - a brain deleted/renamed midway must fail safe to the default, without
   crashing `_tg_brain`.
4. **`/viec/all` scans every brain on each load** - with many brains it may be slow. Acceptable at a scale of ~4 brains; if it
   grows, add a cache later (out of scope).

## Testing (minimum)

- `test` moving a loop: success (file moved + registered), slug collision (rejected), loop currently
  running (rejected).
- `test` moving a reminder: the record goes to the right destination file, keeping its id.
- `test` persistent tg brain: set -> read back after a "restart" (state rebuilt from the file) returns the right
  brain; deleted brain -> falls back to the default.
- `test` javis_schedule: the create reply contains the brain name.
- `test` `/viec/all`: attaches the right brain_name/brain_path to each item (if the app can be built in the test).
