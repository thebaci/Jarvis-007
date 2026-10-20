# Design: a `/` command panel for the dashboard + the `/notes` skill

Date: 2026-07-18
Status: approved, preparing to implement

## Goals

Equip Jarvis 007's web chat panel with `/` commands (like Claude/Telegram), and make the first
command `/notes`: typing the command saves the message content verbatim into `sources/`
(including images/files), then automatically distills it into the wiki if that note is worth it.

## Background (findings from the code)

- Telegram ALREADY has a full `/` command system in `server/telegram_bot.py` + the handler
  `_tg_command` in `server/main.py:4981`. Any unknown `/<slug>` is interpreted by Telegram as
  "call the skill with that name" (`server/main.py:5076-5081`). So `/notes` on Telegram is almost
  free once the `notes` skill exists.
- The dashboard (web) does NOT yet have a `/` command mechanism. `sendMessage()` at
  `dashboard/app.js:196` sends the string verbatim over the WebSocket, even when it starts with `/`.
- System skills live at `<project>/.claude/skills/<slug>/SKILL.md`
  (`system_sync.SYSTEM_SKILLS_DIR`), which `system_sync.py` spreads into every brain
  (`<brain>/skills/<slug>/SKILL.md` canonical + a `.claude/skills` mirror). The manifest hash
  protects a user-edited copy from being overwritten by an update.
- The endpoint `GET /skills?brain=...` (`server/main.py:2193`) returns the brain's skill list
  with `slug`, `name`, `description`, `group`, `system`... used as the source for the `/` menu.
- The `ingest-source` skill (`.claude/skills/ingest-source/SKILL.md`) already has a procedure for
  saving a source + distilling the wiki per the vault's 3 disciplines. `/notes` reuses this
  judgment and discipline for the distill step.
- File attachments on the web: `sendMessage()` already adds a context block listing the file
  paths in `Sources`/`Attachments` (`dashboard/app.js:210-221`). `/notes` hooks into this to
  keep images/files.

## Decisions made

1. Scope: build BOTH the `/` command panel for the web AND the `/notes` skill.
2. `/notes` captures: only the current message (the text after `/notes` + files attached in the
   same message), verbatim.
3. Where the skill lives: a bundled SYSTEM skill (`.claude/skills/notes/SKILL.md`), present in
   every brain automatically.
4. The first web `/` menu: the brain's skill list + a few session commands (`/reset`, `/stop`,
   `/new`).
5. A note not worth the wiki: STILL saved into `sources/`, with only a light notice, wiki
   untouched (no asking back).

## Architecture

Unifying principle: on Jarvis 007, `/<slug>` = call the skill `<slug>` (exactly the semantics
Telegram uses). The web will apply the same rule, plus a handful of session commands handled in
place.

### Part A - The `/` command panel for the dashboard

Frontend, no backend change needed.

- New module `dashboard/chat-slash.js`: manages a floating command menu above the chat box.
  - When `chatInput` starts with `/` and the cursor is in the first command token, show the menu.
  - Item sources:
    - Static session commands: `/new` (new conversation), `/reset` (reset the session), `/stop`
      (stop the running turn).
    - Dynamic skills: fetch `GET /skills?brain=<current brain>`, take `slug` + `name` +
      `description`. Cache per brain; reload when the brain changes.
  - Filter by the text after `/`. Keyboard navigation: up/down arrows, Enter/Tab to pick, Esc to
    close. Picking a skill = fill `/slug ` into the box so the user can keep typing the content;
    picking a session command = run immediately.
- Intercept commands in `sendMessage()` (`dashboard/app.js`):
  - If `msg` starts with `/`, split into `cmd` (the first token, minus the `/`) and `arg` (the rest).
  - `cmd` is a session command (`new|reset|stop`) → call the app's existing matching function, do
    NOT send to the engine. (Reuse the existing logic for minting a new session / stopping a turn.)
  - Otherwise → treat it as a skill: build `outMsg` = a skill invocation like Telegram's
    (`Hãy dùng skill \`<cmd>\`` + (` với yêu cầu: <arg>` if present) + a safety sentence "nếu không
    có skill tên này thì cứ xử lý bình thường"). These are Vietnamese literals sent to the model,
    mirroring the Telegram handler; in English they read "Please use skill `<cmd>`", " with the
    request: <arg>", and "if there is no skill with this name, just handle it normally". If there
    is an attached file, KEEP the existing path context block and splice it in. Send over the
    WebSocket like a normal chat.
  - Still `appendUserMessage` showing exactly what the user typed (`/notes ...`), without
    exposing the expanded string.
- Menu CSS in `dashboard/style.css`; hook the `<script>` in `dashboard/index.html`.

Boundary: `chat-slash.js` only handles display + picking an item and tells `app.js` what was
picked; `app.js` keeps full authority over sending/not sending. No engine logic goes into the
menu module.

### Part B - The `notes` system skill

File `.claude/skills/notes/SKILL.md`. Frontmatter: `name`, `description` (<=150 characters,
stating the capability directly), `group` (pick the closest group among existing skills,
expected to be "Năng suất" (Productivity) or "AI"). The skill body tells the engine, on each run:

1. Identify the working vault (the current brain) and the `sources/`, `attachments/`, `wiki/`
   folders. Read the brain-root `CLAUDE.md`/`AGENTS.md` first (the vault schema).
2. Take the note content = the text the user typed after `/notes` (verbatim) + the attached
   file/image if any. Only the current message. ABSOLUTELY do not re-edit the wording.
3. Create `sources/note-YYYY-MM-DD-HHmm-<first-few-words-without-diacritics>.md`:
   - Frontmatter: `type: source`, `source_kind: own-note`, `status: unprocessed`,
     `created: <date time>`, `tags: [note]`.
   - Body: the original text verbatim. Image: move the file into `attachments/`, embed `![[image-name]]`.
   - If the attached file is already sitting in `Sources` (web upload), use it/move it, do not
     duplicate.
4. Assess wiki-worthiness: a reusable concept/framework/principle/procedure → worth it; venting,
   chores, transient reminders → not worth it. (Same criteria as ingest-source.)
5. If worth it: apply the INGEST operation of `ingest-source` to this note - write/update a wiki
   page following the full 3 disciplines (citation `[[Source]]`, goal vs reality, contradictions
   kept explicit), update `wiki/index.md`, append `wiki/log.md`, set the source
   `status: processed` + `processed_at` + `wiki_links: [...]`.
6. If not worth it: keep the source `status: unprocessed` (or `skipped` + a `note` with the
   reason), do NOT touch the wiki.
7. Report briefly in spoken prose (no tables, no long dashes): the note was saved to `[[...]]`,
   whether it went to the wiki, and which page. If an image is embedded, show it again to the user.

Safety: writing `sources/`+`wiki/` is level `safe`, and since the person typing the command is
the one asking, it runs on its own. No money, no orders, no posting, no sending messages.

## Testing

- Web: type `/` and see the menu; type `/no` and it filters to `notes`; picking fills `/notes `;
  type content + send → a file appears in `sources/`, content verbatim; a note with a concept
  gets a new wiki page + `wiki/index.md` updated; a trivial note only gets a source, with a
  light notice.
- Web attach an image + `/notes` → the image goes into `attachments/`, the source embeds `![[...]]`.
- Session commands: `/new` opens a new conversation, `/stop` stops the turn, neither is sent to
  the engine.
- Telegram: send `/notes <content>` → runs the `notes` skill, saves a source (this channel
  already routes this, just verify it still works after adding the skill).
- `system_sync`: other brains also see the `notes` skill after sync (not only the default brain).

## Out of scope (later round)

- A full web `/` menu like Telegram's (`/model`, `/brain`, `/status`, `/agents`, `/workflows`)
  needs its own command handlers for the web session - later.
- `/notes` capturing Jarvis 007's most recent reply when typed bare - later.
- Capturing a multi-turn stretch of conversation - later.

## Files touched

- Add: `.claude/skills/notes/SKILL.md` (system_sync spreads it into every brain automatically).
- Add: `dashboard/chat-slash.js`.
- Edit: `dashboard/app.js` (intercept `/` in `sendMessage`, expose a few session functions to the
  menu module).
- Edit: `dashboard/style.css` (menu CSS), `dashboard/index.html` (hook the script).
- Possibly touched: update `LEGACY_HASHES`/the manifest in `server/system_sync.py` if the seed
  procedure requires stamping the new skill's hash (check while doing the work).
