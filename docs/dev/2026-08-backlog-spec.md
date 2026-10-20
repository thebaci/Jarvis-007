# Spec: 10 ideas from the development notebook (08/2026)

Settles how to do the 10 ideas recorded in the "Jarvis 007 development ideas" notebook of
2026-08-04, then does them straight away. This document is a **decision record**: read it to
know why each idea was built the way you see it in the code, and why three of them turned out
far easier than the notebook assumed.

The status at the end of each section is the REAL status at the time of writing, not the hoped-for one.

## Before reading each item: three findings that changed the picture

The notebook records three ideas with the remark "don't know if it's doable". On digging, all
three already had a path:

1. **NotebookLM does not need an MCP server written.** The notebook says "write an MCP server
   wrapper". In fact `notebooklm-py` 0.8.0 already ships an MCP server: it declares a
   `console_scripts` entry named `notebooklm-mcp`, runs the stdio transport, and also has HTTP
   with a bearer token. All that is left is to add **one entry to the connector catalog** like
   the 20 other connectors, without writing a line of Python.
2. **Zalo image sending: the library can do it, the MCP just does not expose it.** `zca-js`
   accepts `sendMessage({ msg, attachments: [path] }, threadId, type)`, and `zalo-agent-cli`
   itself uses exactly that form for its `msg send-image` command. But `mcp-tools.js` only
   declares `text` for `zalo_send_message`. Version 1.6.2 is the newest on npm, so **waiting for
   upstream is waiting forever**.
3. **The editor docked into the chat frame has existed since 0.15.2**, it is just that links in
   chat do not use it and open a separate popup instead. Idea number 8 is therefore not about
   writing a new layout, only about changing what gets called.

## General rules for doing these 10 ideas

- **Do not build a second copy of something that already exists.** This is the lesson of 0.15.0
  and 0.15.1 (the Vault tree) and 0.17.0 (the Jarvis 007 CLI). Three ideas in this batch are
  directly governed by it: ideas 7 and 8 reuse the existing editor and Vault tree, and idea 10
  reuses exactly the pagination block already written for the Scheduled page.
- **A new column in SQLite needs a migration.** `CREATE TABLE IF NOT EXISTS` does not add columns
  to an old DB. `sessions.py` already has an `ALTER TABLE ... ADD COLUMN` loop for this, and new
  columns go through it (`server/sessions.py:203`).
- **Everything new must work on a DB and vault that already hold data**, without demanding a wipe
  and redo.

---

## 1. NotebookLM MCP integration

**Problem.** Wanting to ask Jarvis 007 about content sitting in NotebookLM (sources, notes, the
notebook's chat) without opening a browser and copying it over.

**Decision.** Add the `notebooklm` connector to `system/mcp-catalog.json`, running the existing
MCP server of `notebooklm-py` via `uvx`. No wrapper is written.

**Design.**

- `transport: stdio`, `command: uvx`, args `["--from", "notebooklm-py[mcp]", "notebooklm-mcp"]`.
  `--from` is used because the package name (`notebooklm-py`) differs from the command name
  (`notebooklm-mcp`), and the `[mcp]` extra is required because `fastmcp` sits outside the core
  dependencies. This is exactly the trap already recorded on the `google-keep` connector in the
  same catalog.
- **Sign-in**: NotebookLM has no official API, the library reads the Google session cookie. The
  most stable route on a VPS is to paste a cookie already taken from the browser, so the connector
  takes two fields: `NOTEBOOKLM_COOKIES` (the cookie string) and `NOTEBOOKLM_PROFILE` (the profile
  name used to cache the session). `isolate_home: true` like the Zalo connector, so each
  connection gets its own profile and removing the connection takes the session with it.
- **Tool classification** by `tool_meta`: reading notebooks/sources/notes/chat is `read`; creating
  and editing notebooks, adding sources, writing notes is `write`; deleting notebooks, deleting
  sources, sharing outside is `danger`. `default_perm: readonly` - this is a personal knowledge
  store, so opening write access has to be a deliberate act.
- **State the risk plainly** in the `risk` field: the Google session cookie is not OAuth with a
  limited scope; the library is unofficial, so Google changing the protocol can break it at any time.

**Where it touches.** `system/mcp-catalog.json` (add 1 connector), `docs/09-mcp-va-so-lieu.md`.

**Not doing.** Not adding `notebooklm-py` to Jarvis 007's `requirements.txt`: it runs in a child
process built by `uvx`, and pulling it into the core adds `fastmcp` + `playwright` for something
most users will not connect.

**Status.** Done. Real sign-in could not be tested because the build machine has no Google
account, which fits the "beta" level of the 20 connectors of the same kind in the catalog.

---

## 2. Letting an Agent attach an AI chatbot

**Status: THE INTENT IS NOW CLEAR, split into a separate document.** The repo owner stated it
clearly at the end of 2026-08-04: make use of the existing Agents to create many chatbots, each
specialized in one field, answering customers through Telegram and droppable into customer care
groups.

That is interpretation number 3 below, but far more specific, so it is discussed further in
**[Dedicated bots](2026-08-bot-chuyen-trach-spec.md)**.

The three original guesses are kept to show how far off the guessing was - the first two are
things I thought up myself, not what the repo owner needed:

1. **A separate chat frame for each Agent.** Clicking an agent in Studio opens a conversation
   that asks it directly, the agent running with its own role + skills + model. This reuses almost
   the whole chat core: the session stored in `sessions.py` (adding an `agent_slug` column), the
   engine going through exactly the `_tg_answer` path that the dashboard/Telegram/CLI already use.
   This is the direction that adds the clearest value.
2. **An Agent picking its own engine.** An agent already has a `model` field
   (`server/main.py:3432`) but cannot yet choose an ENGINE. Adding `engine` to the frontmatter
   finishes the data side; the hard part is that `workflow_runtime` must route by it.
3. **An Agent acting as a bot for an outside channel** (Zalo OA, a separate Telegram bot,
   Messenger). The heaviest, and it hits the "never send messages outside on its own" safety
   barrier head-on, so permissions must be designed first.

The three directions are not mutually exclusive: 1 and 2 can be combined, and 3 should be split
out as a separate piece of work.

---

## 3. Sending Zalo messages with images

**Problem.** `zalo_send_message` of `zalo-agent-cli` only accepts `text`. To send an image (for
example an image Jarvis 007 just created, or a report image) you have to open Zalo by hand.

**Decision.** Write a bundled plugin `zalo-image` that exposes the tool `zalo_send_image`, calling
the CLI `zalo-agent-cli msg send-image` with **exactly the isolated home of the currently
signed-in Zalo connection**.

**Why this route and not another.**

- *Wait for upstream to add a parameter*: 1.6.2 is already the newest, there is nothing to wait for.
- *Fork zalo-agent-cli*: carries a whole Node package just to add one parameter, and every new
  release has to be merged by hand.
- *Call zca-js directly from Python*: not possible, zca-js is a Node library.
- *Call the existing CLI*: `zalo-agent-cli` itself already has the command
  `msg send-image <threadId> <paths...>`, which works exactly the way Jarvis 007 needs. The login
  session lives in the HOME directory (`STATE_DIR/connector-home/zalo-*`, see
  `server/zalo_login.py:157`), and `mcp_store` already sets `HOME` from `config.home_dir` when
  running the MCP (`server/mcp_store.py:424`). So all that is needed is to set that same variable
  for the child process to share the session, with no new sign-in and no new QR scan.

**Design.**

- Tool `zalo_send_image(thread_id, paths[], caption?, thread_type?, connection_id?)`.
- `paths` accepts paths **relative to the vault root** (exactly the convention the AI already uses
  in chat, e.g. `attachments/anh.jpg`) or absolute. A relative path is joined with `ctx.vault_root`.
  If the file does not exist, report the error IMMEDIATELY, do not push it to the CLI to get a
  hard-to-read Node error.
- **Block escaping the vault**: after resolving, the path must lie inside `vault_root`; an
  absolute path outside the vault is rejected. Without this barrier, one clever chat message would
  send `/etc/passwd` out through Zalo.
- `min_mode: full`. Sending a message outside is a real action that cannot be undone, in the same
  class as `zalo_send_message`, which is `danger` in `tool_meta`.
- With several Zalo connections, `connection_id` picks the account; left empty with exactly one
  connection, use it directly, and with several **refuse and list them** rather than guess
  (sending from the wrong account is sending under the wrong identity).
- Limit of 10 files per call, timeout 120 seconds.

**Where it touches.** `system/plugins/zalo-image/{plugin.yaml,plugin.py}`, `docs/12-zalo.md`,
`CLAUDE.md` (the Zalo section).

**Status.** Done. Tests cover command building, connection selection and the path barrier; the
real send needs a Zalo account that has scanned the QR, so it cannot run on CI.

---

## 4, 5, 6. Pinning conversations, grouping into Projects, attaching icons

These three ideas share one place in the data, so they are done in one pass. Splitting them into
three passes is three migrations for the same table.

**Problem.** The conversation list is ordered purely by time: important conversations that get
used again and again sink to the bottom, and it is all text, so after a while you cannot tell
which is which.

**Decision.**

- Pin: a `pinned` column on `sessions`, pinned items gathered into a **Pinned** group at the top
  of the list.
- Project: a new `projects` table + a `project_id` column on `sessions`.
- Icon: an `icon` column **on `projects` only**, storing a **Lucide icon name** (e.g. `star`), in
  the pattern `^[a-z0-9][a-z0-9-]{0,39}$`. Conversations do NOT get their own icon - see the
  addendum at the end.

**Design.**

*Store (`server/sessions.py`).*

```
projects(id TEXT PK, name TEXT, icon TEXT, brain TEXT, created_at REAL, updated_at REAL)
sessions  + pinned INTEGER NOT NULL DEFAULT 0
          + icon TEXT
          + project_id TEXT            -- NULL = not in any project yet
```

- `project_id` does **not** declare `REFERENCES projects(id)`: a column added with `ALTER TABLE`
  cannot declare a foreign key in SQLite, and even if it could, `PRAGMA foreign_keys=ON` would
  block deleting a project that still has conversations. Instead, deleting a project **removes the
  label** from its conversations back to `NULL` in the same transaction. Deleting a project NEVER
  deletes conversations - that is something a user would not expect and could not undo.
- `list_sessions` orders by `pinned DESC, updated_at DESC` and takes an extra `project`: empty
  means all, `<id>` means exactly that project, `none` means the ungrouped ones.

*API (`server/main.py`).*

```
GET    /projects?brain=            -> [{id,name,icon,session_count}]
POST   /projects                   name, icon, brain            -> create
POST   /projects/{id}/update       name?, icon?                 -> rename / change icon
POST   /projects/{id}/delete                                    -> delete, conversations go to NULL
POST   /sessions/{id}/pin          pinned=1|0
POST   /sessions/{id}/project      project_id=<id|empty>, brain?
GET    /sessions?...&project=      filter by project
```

- `/sessions/{id}/project` **creates the row if it does not exist** when `brain` is given. Reason:
  the dashboard generates the conversation id on the client side the moment send is clicked
  (`dashboard/app.js:253`), while the row in the DB only exists once the server handles the turn.
  To get "whichever project is open, a new chat automatically falls into that project", the label
  has to be attachable right at the moment of clicking send. `create_session` already uses
  `ON CONFLICT DO NOTHING`, so two creation paths at the same time do not step on each other, and
  the chat turn after that only updates `engine`/`model` and does not touch `brain`.

*UI (`dashboard/sessions-ui.js`).*

- A Project bar at the top of the left column: a button to pick the open project, a button to
  create a project, rename, change icon, delete.
- While a project is open, the list filters by it, and **a newly created chat is automatically
  attached to that project** through `window.JavisProjects.claim(sid)`, which `app.js` calls right
  after minting the id.
- Each conversation item: icon (if any) + name; on hover a row of buttons appears for pin / icon /
  rename / delete.
- The icon picker is a popover showing **every Lucide icon the app has vendored**, with a name
  filter box and a Clear icon button. **No emoji** - the repo owner settled this on 2026-08-04.
  The right reason, worth recording: Lucide icons are drawn with `stroke="currentColor"` so they
  change color automatically with the light/dark tone and with the text color where they sit, and
  look identical on every machine; emoji are drawn differently by each operating system and have
  fixed color. The whole dashboard dropped emoji for exactly that reason and has `test_icons.py`
  guarding it, so letting this one place use emoji would both stand out from the rest and require
  loosening the very test that holds that rule.
- The stored value is the icon **NAME**, not a character. The list of names comes through
  `Icons.names()` (newly added in this batch) rather than reading `window.LucideIcons` directly:
  the whole point of `icons.js` is to be the single layer between the dashboard and the vendored
  icon set.
- An unknown name (the icon set changed between two versions, or someone hand-edited the DB) is
  skipped on the display side, rather than letting `ic()` draw a question mark with a console
  warning on every render. On the store side, garbage forms are blocked at write time.
- **The open project state is kept in `localStorage`** per brain, not on the server. It is where
  the user is standing on ONE machine, not shared data.

**Risks considered.** Pin then switch brain: pinned conversations belonging to another brain do
not show up mixed in, because `list_sessions` still filters by brain first. Projects are also tied
to a brain, so switching brain switches the project list too.

**Status.** All three done.

---

## 7. Links in .md files must be clickable and the tree must expand to the target

**Problem.** Open a .md file to read, it has a link to another file, and clicking does nothing.
Wikilinks `[[..]]` navigate, markdown links `[text](path)` do not, yet the two look identical.

**Real cause.** `chat-render.js` handles clicks in two layers: wikilinks are handled BEFORE the
"currently editing in the editor, so open nothing" barrier, while ordinary file links
(`a.jv-floc`) sit AFTER that barrier (`dashboard/chat-render.js:818`). And the editor's rendered
view is `contenteditable`, so every markdown link in a .md file falls right into the zone the
barrier blocks. The same goes for http links: inside `contenteditable` the browser does not open a
tab by itself, it only places the caret.

**Decision.** In the editor's rendered view, links are for **going**, not for editing text - the
same rule already applied to wikilinks. To edit a link's text, switch to Source mode.

**Design.**

- Move the `a.jv-floc` branch up BEFORE the contenteditable barrier, alongside wikilinks.
- Add a branch for external links (`http/https/mailto`) in the rendered view: open a new tab.
- **Images are still left alone**: images in the rendered view must be draggable and deletable like
  a character, so they keep the old path.
- CSS `cursor: pointer` for links in `.ne-wys` and `.jvfe-prev`, so hovering shows they are clickable.
- **Auto-expanding tree**: `_vtRevealInTree(path)` has existed since 0.15.0 (the Location button
  of the search frame, `dashboard/console.js:5016`). Expose it as `window.JavisRevealInTree` and
  call it every time navigation to a file happens through a link. No second tree-expanding
  mechanism is written.

**Status.** Done.

---

## 8. Opening files in chat: drop the popup, use the docked frame

**Problem.** Clicking a file link in chat raises `.jvfe-modal` covering the middle of the screen.
Meanwhile opening a file from the Files tab right next to it gives a very different experience:
the editor takes the place of the chat frame. Two entrances to the same file, two faces.

**Decision.** File links in chat go into **exactly the docked editor** that has existed since 0.15.2.

**Design.**

- `chat-render.js` calls `window.JavisOpenNote(rel)` instead of `window.JavisEditFile(rel)`.
  `openNote` already knows: on the Chat page it borrows `#chatPageEdit` (taking the place of the
  chat frame), on the main screen it floats above the brain visual - that spot is empty, so
  covering it is reasonable.
- **Fallback in exactly this order**: a narrow screen (under 860px) or `JavisOpenNote` not loaded
  yet keeps the old popup. A narrow screen has no room for a docked frame, and the popup already
  has its own `@media` for it.
- **File types that cannot be edited** (pdf, docx, zip...) already have a `_neRenderDownload`
  branch in `openNote`: it shows a file card with an Open in new tab button and a Download button.
  That meets the requirement "the fallback shows a loading state, or lets it be viewed like a
  normal file in the browser", and nothing extra has to be written.
- `JavisOpenNote` currently refuses to run on a narrow screen with the toast "editing notes on
  phone is turned off" (Vietnamese: "sửa note trên điện thoại đã tắt"). The original reason was
  accidentally tapping a graph node, which does not apply to deliberately clicking a link. But
  since chat-render already blocks narrow screens before calling, that rule does not need touching.

**Status.** Done.

---

## 9. A skill picker in the Agent edit screen

**Problem.** The skill list in the Agent edit form is a flat heap of checkboxes. The brain
currently has 55+ skills, so finding the one to tick means scanning the whole list by eye.

**Decision.** Add a search box + grouping by the skill's existing `group` field, each group being
a collapsible block.

**Design.**

- Groups come from `group` in the skill frontmatter (`/skills` already returns it). Empty goes
  into "General" - the same convention used on the Skills page (`dashboard/studio.js:541`).
- The search box filters by **name + slug + description**, ignoring Vietnamese diacritics (typing
  "viet email" finds "Viết email"). While searching, every matching group expands itself, and when
  the search ends they collapse back.
- A group that has a ticked skill is open by default when entering the form - whoever edits an
  agent cares about what is on first.
- At the top of the frame is a count line "selected N/M" and a **Clear selection** button.
- **Ticks must still be kept while filtering.** This is the easiest place to break: if you redraw
  the list per the filter and read the state from the DOM, skills filtered off the screen lose
  their tick at save time. So the selection state is kept in an in-memory `Set`, the DOM is only a
  projection, and saving reads from the `Set`.

**Status.** Done.

---

## 10. Pagination for the self-learning log and the log table under the Savings page

**Problem.** The Self-learning page shows only the 10 most recent log lines and 12 commits, then
nothing. The Savings page pours the whole "Recent turns" table out in one go.

**Decision.** Reuse **exactly the pagination block already written for the Scheduled page**
(`dashboard/console.js:2211`): load once then flip pages on the client side.

**Design.**

- Extract that block into a shared helper `_pager(box, items, perPage, renderRow)` instead of
  copying it a third time. Copying a third time is the start of three drifting versions.
- Self-learning page: `/learn/log` raises `limit` from 10 to 200, showing 10 per page;
  `/learn/review` raises 12 to 60, showing 6 per page.
- Savings page: the "Recent turns" table shows 20 rows per page.
- No infinite scroll: these frames sit in the middle of a page with other content below, and
  infinite scroll would swallow the way down to that part.

**Status.** Done.

---

## What is NOT done in this batch

- Idea number 2 (chatbots for Agents) - waiting for brainstorming, see section 2.
- No touching the chat protocol, the engines, or the token-saving runtime. All 9 doable ideas sit
  at the conversation data store layer, the dashboard UI, the connector catalog and plugins.
- No change to the default behavior of what is running: old conversations have no project, no pin,
  no icon, and look exactly as before.

---

## Addendum 0.18.1: where the icon belongs

Version 0.18.0 misread idea number 6 in the notebook ("add icons for conversations and folders").
It built an **icon picker for each individual conversation**. The repo owner pointed it out the
moment he saw the real screen: the idea was to add **a fitting icon at the HEAD of the two tabs**
"Conversations" and "Files", while the place to change icons belongs to **Project**, where many
different icons are really needed to tell groups apart.

Correct, and correct in a way that could have been deduced beforehand if we had bothered to ask
"what does this icon classify":

- **The conversation list**: every row is a conversation. An icon there cannot separate any group
  from any other, so it is only decoration that has to be set by hand one by one, plus one more
  button in a row of buttons that already has four and only appears on hover.
- **The two tabs**: they are two DIFFERENT kinds of thing standing side by side, told apart only
  by text, so a glance is not enough, you have to read to know where you are. This is exactly where
  a fixed icon helps.
- **Project**: each group really is a different thing (Customers, Content, Engineering...). This is
  where an icon has work to do.

Changed in 0.18.1:

- Removed the per-conversation icon entirely: the `sessions.icon` column, `SessionStore.set_icon`,
  the endpoint `POST /sessions/{id}/icon`, the button and the rendering. No dead UI left behind.
- Added a fixed icon at the head of the two tabs, taking exactly the rail icons already used for
  those two things (`message-circle` for Chat, `folder-tree` for Files) so the whole app speaks one
  visual language, instead of placing a new icon only here.
- A project with no icon set borrows `folder` as the default, and the first two lines of the menu
  ("All conversations", "Ungrouped") also have icons. When every row has an icon, the eye can scan
  down the icon column, and the user knows at a glance that icons can be changed here.

**Lesson recorded.** Both misreadings came from jumping straight to "build an icon picker" without
first asking **what that icon is used to tell apart from what**. Answering that question shows at
once that it belongs to Project and the two tabs, not to each conversation row.
