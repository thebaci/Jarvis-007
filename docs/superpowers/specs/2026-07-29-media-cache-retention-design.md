# Design: media is a cache zone, not knowledge

Date: 2026-07-29
Status: direction brainstormed and approved, awaiting implementation.

## Problem

Media flows into the vault through three paths, and none of them has any cleanup mechanism:

- Images Jarvis 007 generates itself are saved to `<vault>/attachments/` - `server/image_gen.py:202` (`save_png_b64`).
- Files/images the user sends through Telegram are downloaded to `<vault>/inbox/telegram/` - `server/main.py:6242` (`_tg_inbox_dir`).
- Source ingest copies the original image into the Attachments folder when the user asks for it - `server/main.py:1888`.

A grep over all of `server/` finds not one line of retention, prune or expire logic for media.

The expensive part is git. The brain's `.gitignore` template (`server/git_brain.py:63`) only excludes locks, `learn-staging`, `learn-log`, `loop-log`, `skill-usage.json` and `conversations/`. `attachments/` and `inbox/` are committed like anything else. That means every image is a blob that lives forever in the brain's git history: deleting the file on disk never gets the space back, and `git_brain` also keeps a mirror, so it is doubled. A 2MB image today is 4MB taking up space forever, plus the space on GitHub if backup is on.

## Comparison with hermes

Hermes keeps media in `~/.hermes/cache/images` (`.learn/hermes/agent/image_gen_provider.py:234`), in the same family as `cache/audio`, `cache/videos`, `cache/documents`, `cache/screenshots` (`.learn/hermes/gateway/platforms/base.py:950`). Media lives in the app's state directory, is named plainly as a **cache**, is fully separated from the knowledge layer, and is not tracked by git. Hermes does this part better than Jarvis 007.

But hermes only solves half of the problem. It prunes sessions at 90 days (`.learn/hermes/gateway/session.py:1429`) and checkpoints at 7 days (`.learn/hermes/gateway/run.py:2821`), while `cache/images` has no cleanup line at all. It is called a cache but nobody deletes anything, so it still grows without bound. So we take hermes's idea of "media is a cache", not its habit of leaving it alone.

## Decisions made

- Media is **material passing through**, not an asset. Once read, extracting it into a text .md is enough.
- If the user wants long-term image storage, a Drive connection will be the store later, rather than Jarvis 007 holding it. Not done for now.
- No media backup to GitHub.
- Accept that old chat history loses its images, as long as the spot clearly says "image expired" rather than showing a bare broken icon.
- Git history that already committed images is **left alone**; history is not rewritten. We only block it from now on.
- Keep 30 days, with a cap of 300MB per brain.

## Design

### Boundary

Treat each brain's `attachments/` and `inbox/` as a **cache zone**, not knowledge. Knowledge is .md files. Anything in those two folders can vanish and the brain stays intact.

### Part 1 - Block git

Add to `_GITIGNORE` at `server/git_brain.py:63`. `_ensure_gitignore_lines` is merge-only, so old brains pick up the new lines on the next commit without overwriting lines the user added.

Two traps must be handled correctly:

**The folder name trap.** Jarvis 007 detects the attachments folder with the regex `^(\d+\s*[-_.]\s*)?attachments$`, case-insensitive (`server/image_gen.py:40`, `server/main.py:1931`), so in practice it can be named `attachments`, `Attachments`, `05 - attachments`, `05-attachments`, `05_attachments` or `05.attachments`. Git is case-sensitive on Linux (the VPS runs Linux). A single `attachments/` line is not enough.

Use four lines: `attachments/`, `Attachments/`, `*attachments/`, `*Attachments/`, plus `inbox/`. The `*` covers every numeric prefix the regex accepts without listing each separator. The two lines without `*` stay for readability, even though syntactically `*` also matches the empty string.

**The already-tracked files trap.** `.gitignore` has no effect on files git already tracks. `git rm --cached -r` must be run once for those folders in every brain that is a git checkout. Consequence: the next commit records "images deleted", and pulling the brain onto another machine no longer brings the old images along. This consequence is accepted, not a bug.

Where the `git rm --cached` step runs: in the same place that already patches `.gitignore` for old brains (`server/git_brain.py:114-147`), once, idempotent (if nothing is left in the index the command does nothing).

### Part 2 - Janitor

New module `server/media_gc.py`.

The decision part is split out as a **pure** function:

```
plan_deletions(entries, now, max_age_days, max_mb) -> list[path]
```

`entries` is a list of `(path, size, mtime)`. The function does not touch the disk, so it can be tested without fixtures. Same style as `save_png_b64` in `server/image_gen.py`.

Two rules run together:

1. **Age limit**: a file whose mtime is older than 30 days goes on the deletion list.
2. **Size cap**: after removing the expired group, if the remaining total still exceeds 300MB, keep deleting from oldest to newest until it falls below the cap.

The cap is a safety valve for the case of generating a hundred images in one day, when the age rule has not had time to help.

`.md` files inside those two folders are skipped, in case a note strays in.

The janitor does **not** distinguish images Jarvis 007 generated itself from images the user actively asked to "save to source". An ingested image embedded in a Sources note expires like any other image: the .md note keeps the extracted content, while the spot where the image was embedded becomes a gray box. This consequence is accepted, consistent with the decision that "media is material passing through". If the user wants to keep images long-term, the path is Drive, not an exception in the janitor.

The part that touches the disk is a separate function: scan the folders, call `plan_deletions`, delete, and return the number of files and bytes cleaned up.

**The disk scan must use `os.scandir` and must not run inside the event loop.** An old lesson in this project: `glob(...)[:N]` walks the whole tree and only then slices, so it is not a real cap, and a synchronous disk scan blocked the event loop to the point that Traefik removed the route because the container was unhealthy.

### Part 3 - Hook into the scheduler

Add one entry to `_scheduler_loop` (`server/main.py:4220`), but **do not** run it on that loop's 30-second beat. Keep a `last_run` marker in process memory, run one pass only every 6 hours, and wrap it in `asyncio.to_thread`. Wrap it in its own `try/except` that prints to stderr in the same pattern as the existing entries, so a broken janitor cannot take down the loop, kanban or reminders tick.

Scan the brain list from `loop_feature.scheduler_brains()`, like the Jarvis 007 index entry at `server/main.py:4263`.

### Part 4 - Configuration

A `media` key in `settings.json`, read through `cfgmod.read_settings()`:

- `enabled`: default `true`.
- `max_age_days`: default `30`.
- `max_mb`: default `300`.

With `enabled: false` the janitor deletes nothing, for users who want to manage it themselves.

### Part 5 - The expired-image box

`/files/raw` returns 404 when the file does not exist (`server/main.py:2864`), so the `<img>` fires an `error` event.

Change `imgHtml` in `dashboard/chat-render.js:172`: attach an `onerror` that replaces the `<img>` tag with a gray box reading **"Image expired"** (in the Vietnamese UI: "Ảnh đã hết hạn"). Doing it at the `onerror` layer also covers the case where the user deletes or renames a file by hand, not just the janitor.

The Vietnamese display string must keep its diacritics (project rule, a mistake already made twice before).

The gray-box CSS goes into `dashboard/style.css`; remember to bump `?v` (static assets are cached by VERSION, automatic since v0.9.139).

## Addendum after implementation: the fourth path

The original survey counted three media paths and missed the fourth, because at the time it only scanned `brains/`.

`STATE_DIR/.staging` (`server/main.py:1779`) is where files the user pastes or uploads into the chat box land before the engine reads them. The code has only two operations on it: create the folder and write files into it (`server/main.py:1848`). Nothing cleans it. Measured on the development machine on 2026-07-29: **114MB, 62 files, oldest file 27 days old**, which is bigger than the brain's `attachments`.

It is not inside the vault so git does not touch it (already blocked at `.gitignore:11`), but it still eats VPS disk like everything else.

Handling: `media_gc.sweep_staging`, limit **3 days**, configured through `media.staging_days`. It differs from the brain cache zone's rules in two ways, both because staging is a pure transit spot:

- **`.md` is not spared.** The chat never embeds a staging path, so nobody scrolls back to open it; a `.md` file here is something the user just pasted into the chat, not a note. This requires `plan_deletions` to take a `keep_md` parameter, defaulting to `True` so the brain's rules do not change.
- **Age rule only, no size cap.** A 3-day limit is already tight enough.

Staging is a shared folder, not per brain, so the scheduler scans it exactly once outside the brain loop.

## Scope and boundaries

- **No** Drive-upload code in this scope. The janitor is one small function; if Drive upload is wanted later, insert a step right before the delete call. No empty hook scaffolding is built in advance.
- **No** rewriting of the brain's git history. It is settled that what was already committed stays.
- **No** moving media outside the vault the hermes way. The path `![](attachments/x.png)` stays as is, so `/files/raw`, `chat-render.js`, `console.js` and `file-editor.js` need no path changes.
- Zalo listener media is out of scope: `server/zalo_listener.py` does not download files into the vault.

## Files touched

- `server/media_gc.py` - new. Pure `plan_deletions` plus the scan/delete function.
- `server/git_brain.py` - add lines to `_GITIGNORE`; add a one-time `git rm --cached` step for old brains.
- `server/main.py` - add the janitor entry to `_scheduler_loop`, 6-hour cadence, run in `to_thread`.
- `dashboard/chat-render.js` - `onerror` for `imgHtml`.
- `dashboard/style.css` - the gray "Image expired" box; bump `?v`.
- `tests/python/test_media_gc.py` - new.

## Testing

`plan_deletions` (pure, no disk needed):

- Files newer than the age limit and a total under the cap: nothing is deleted.
- Files past the age limit go on the list, files within the limit do not.
- Total over the cap even though every file is within the age limit: delete from oldest to newest, stop as soon as it falls below the cap, no extra deletions.
- Both past the age limit and over the cap: the two rules add up, and no file is counted twice.
- `.md` files never go on the deletion list.
- `max_age_days` or `max_mb` equal to 0 or negative: treat that rule as off, do not wipe everything by mistake.

The disk-touching part: build a temp folder with a few files with fake mtimes, run the scan function, and check that exactly the right files disappear and the returned byte count matches.

Gitignore: a newly created brain has all the variant lines; an old brain that already has its own `.gitignore` gets the lines merged in without losing the old ones.

Manual on the dashboard: delete one image in `attachments/` by hand, then reload an old chat; that spot must show the gray box "Image expired" and not a broken icon.
