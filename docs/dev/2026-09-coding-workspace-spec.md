# Coding Workspace (planned for 0.63.0)

**Version:** v0.3. Replaces v0.2 (split into four phases) and v0.1 (written outside the repo on 2026-09-21).
**Status:** **done** in 0.63.0, adjusted after trial feedback in 0.63.1, 0.63.2 and 0.63.4 (see section 13).
**Scope:** trimmed down to ONE editing session. The project owner decided this on 2026-09-22.
Document for people who edit the core.

## Three decisions that govern this document

1. **One editing session, no phases.** v0.2 was split into four phases; in practice, four phases
   spread over many weeks means phase 1 ships unsafe and nobody comes back to finish. This
   version cuts down to the smallest thing that is **usable and safe on its own**, and pushes
   everything else down to "For next time".
2. **No automatic model switching.** Changing the engine halfway through a coding task breaks the
   thread of the code. Switching is manual only. The quota router, the percentage quota table
   and automatic failover are dropped entirely.
3. **Borrow screens, do not rebuild them.** Every UI component is a node borrowed from another page.

---

## 1. Why

Jarvis 007 can already run Claude Code, Codex, Grok Build and Antigravity through the real CLIs, plus six
API engines through `server/engine.py`. What is missing is not coding ability but **a place to do
coding work**: today, to have Jarvis 007 edit a repo you have to say so in the shared chat box. Nothing
records which repo, which branch or how much permission it is working with, and opening two jobs in
parallel on the same repo means they step on each other.

The Code group on the rail currently holds only Terminal. `dashboard/code-term.js` was already written for this:

> "Code" is an AREA on the rail, not a page: each function is ONE ENTRY in that group. Today
> there is Terminal; adding a function later = adding one line to CHUC_NANG.

This is the second entry of that area.

## 2. Why ONE editing session is enough

Because most of the work has already been done. The three key pieces are all in place:

- **`cwd` is already an engine parameter.** `claude_engine(..., cwd=...)` (`claude_cli.py:988`),
  `CodexCLI(cwd=...)`. The chat path currently calls with `cwd=_brain_root(brain)` at `main.py:2021`.
  Making a coding session run inside a repo = passing a different cwd. No new runtime to write.
- **The session store already has a `channel` column.** `sessions.py:73`, plus `moc_cap_nhat_theo_kenh(brain,
  tien_to)` to filter by prefix. The Partners page already uses `agent:<slug>` and `workflow:<slug>`.
  A coding session is just channel `coding:<repo-id>`.
- **The chat frame can already be lent out.** `_borrowChatNodes` (`console.js:6925`) relocates the whole of
  `#chatArea #bgStrip #attachBar #modelBar #hudVoice` with every handler, WebSocket and streaming
  hookup already attached.

So the REALLY new code surface is only three things: the **repo registry**, the **context chip row**, and the
**worktree with restore points**.

## 3. The borrowing rule

This rule is not new; it has been in `console.js` since the Files tab was built:

> Do not build a second tree. The first version of this feature wrote an entire separate tree
> module, and the repo owner pointed it out right away: "why not carry over the exact same tree from Jarvis 007
> instead of rebuilding it". Correct
> [...] Building a second copy means copying all of that again and letting the two copies drift apart.

The table below is the **contract**. Do not write a second version of any line on the right.

| What the Coding page needs | Reuse |
|---|---|
| Chat frame (stream, tool calls, attachments, voice) | `_borrowChatNodes` (`console.js`) |
| Session list, pin, rename, search | `sessions-ui.js`, filtered by channel `coding:` |
| Repo folder tree | `JavisVaultPanel.borrow(host)` (`console.js:7005`) |
| View and edit files, syntax highlighting | `file-editor.js` + `code-hl.js` |
| Terminal inside the session | `code-term.js` |
| Pick engine and model | `model-picker.js` + `model-list.js` |
| Run in the background when the tab closes, notify when a turn finishes | `chat_runtime.py` + `background_status.py` + `push.js` |
| Subscription plan limit reached | `limit_resume.py` + `limit-resume.js` |
| Logs | the existing log store |
| Add an entry to the Code group | `RAIL_ITEMS` + `RAIL_GROUPS` id `code` + `CODE_PAGES` (`console.js`) + `CHUC_NANG` (`code-term.js`) |

---

## 4. Scope of one editing session

Five items. When these five are done it is really usable, not a draft waiting for a later phase.

### 4.1 The Coding entry in the Code group

Four places to declare it, one line each, exactly as the comment in `code-term.js` says:
`RAIL_ITEMS`, `RAIL_GROUPS` id `code`, `CODE_PAGES`, `CHUC_NANG`. The label comes from the
`dashboard/i18n/` dictionary, not hard-coded.

### 4.2 Repo registry

`server/coding_store.py`, one JSON file in `JAVIS_STATE_DIR`, keyed by brain:

```json
{
  "repos": [
    {"id": "javis-os", "ten": "javis-os", "duong_dan": "/home/user/javis-os", "nhanh_goc": "main"}
  ],
  "phien": {
    "<session id>": {"repo": "javis-os", "nhanh": "main", "worktree": "/var/javis/wt/ab12",
                     "muc_quyen": "full", "diem_hoi": "javis/ab12/3"}
  }
}
```

Adding a repo = entering an absolute path. Check that `.git` exists; if it is not a git repo, refuse with
a reason rather than silently accepting it.

### 4.3 Context chip row

It sits right ABOVE the input box, not in the header. This is a place to control things, not to display them:

```text
[ javis-os ▾ ]  [ main ▾ ]  [ ☑ worktree ]  [ Bypass ▾ ]  [ Claude Code · Opus ▾ ]
```

The Engine chip opens the existing `model-picker.js` directly. The Permission chip reuses Jarvis 007's three levels
(`suggest` / `auto` / `full`) and introduces no new names. It can be changed mid-session and applies from the next turn.

### 4.4 Running the engine inside the repo

At `main.py:2021` and the matching spot for Codex, when the session has a `coding:` channel the `cwd` comes from the repo
registry (the worktree if there is one, otherwise the repo path) instead of `_brain_root(brain)`. The permission level
is passed exactly as the chat path passes it.

One rule must be kept: a coding session **still uses the MCP Hub and skills like every other session**. Do not build
a separate engine path for coding, because that is how two paths drift apart.

### 4.5 Worktree and restore points

This is the part that makes Bypass mode usable without relying on luck, so it is in scope
and not pushed to later.

- **Worktree**: in `full` mode it is on by default, in the other two levels it is off by default. `git worktree add` puts it
  outside the main repo tree, named after the session. When the session closes and the worktree is clean it is removed; if it still has
  unfinished edits it is kept, and the chat says where it was kept.
- **Restore point**: before each turn in `full` mode, create a tag `javis/<session>/<n>` on the current
  HEAD. Rollback is `git reset --hard <tag>`, shown as a button on that turn.
- **Never** force push, and never touch a branch that does not belong to the session.

---

## 5. Changing engine: manual only

### 5.1 Why automatic switching is dropped

Changing the engine midway means Claude is halfway through editing three files in one direction, Codex steps in with a
different style, and may overwrite the earlier edits. A half-and-half of two styles is usually worse than one mediocre
style. The convenience gained is only one saved click, which is not worth it.

So there is **no** router that picks the engine automatically, **no** failover when a provider errors,
**no** quota threshold that triggers an engine switch, and **no** percentage quota table.

### 5.2 What remains

Click the Engine chip, choose, done. The confirmation panel states three things: the old engine, the new engine, and the state of
the working tree. If the tree is dirty it offers to create a restore point first; declining still lets the switch go through, but the
panel says plainly that the new engine will see a pile of unfinished edits with no description.

Within the scope of this one editing session, the new engine **re-reads the repo itself** to understand the state, per section 6.
There is no model-generated handover. See "For next time".

### 5.3 Subscription plan limit reached

Keep `limit_resume.py` as it is, untouched: it re-runs that exact turn with the **same old engine** when the
limit reopens. That is a re-run, not a model switch, so it does not violate the decision above.

Add exactly one button to the limit card in `limit-resume.js`: "Switch engine and continue", going through
the same confirmation gate as 5.2. The person making the decision is still the user.

---

## 6. The repo is the source of truth

The real state lives in `git status`, `git diff` and the test results. A new engine entering a session must always
re-read them itself; when the context in the chat disagrees with the repo, trust the repo.

This is also why a model-generated handover is not needed in the first version: repo plus diff plus test
results is already most of the context, and the only missing part is the **intent in progress**, and that intent still sits
intact in the chat history of the session itself.

---

## 7. UI

Two areas, not three:

```text
┌──────────────┬────────────────────────────────────────────┐
│ CODING       │                   CHAT                     │
│ SESSIONS     │                                            │
│ status       │  ── context chip row ──                    │
│ repo/branch  │  ── input box ──                           │
└──────────────┴────────────────────────────────────────────┘
```

There is no fixed Work Tree column. The folder tree, the file editor and the terminal are **tabs opened on demand**
in the right area of the chat frame, using exactly the mechanism of the Files tab on the Chat page. Claude Code
on the web, a pure coding tool, also has no file tree column; keeping an always-visible column brings
an IDE mindset into a product that calls itself chat-first.

**Phone:** one chat column, the chips go onto one horizontally scrolling row, and the session list is a pull-up sheet.
The two-area layout only applies from desktop width.

**Session status:** four levels, `running`, `done`, `error`, `limit reached`, derived from the existing
`background_status.py` and `limit_resume.py`. When a turn finishes while the tab is closed, the notification goes
along the current background path; do not write a new notification path.

A fifth level, `needs reply` (the agent stopped to ask a question), is the most valuable thing when running many sessions, because
an agent that runs in the background and then stops to ask while nobody knows is how work dies silently. But detecting
it requires guessing the intent at the end of a turn, and a wrong guess gives false alarms or misses. For next time, to be done properly.

---

## 8. Data and API

Settled up front so nothing has to be decided again midway:

- `GET /coding/repos` - list the repos of the brain.
- `POST /coding/repos` - add one, body `duong_dan`. Checks `.git`.
- `POST /coding/repos/{id}/delete` - only removes it from the registry, does NOT touch the disk.
- `GET /coding/session/{sid}` - the current bindings of the session.
- `POST /coding/session/{sid}` - set repo, branch, worktree, permission level.
- `POST /coding/session/{sid}/checkpoint` - create a restore point, returns the tag name.
- `POST /coding/session/{sid}/rollback` - body `tag`.

New routes go in `server/routes/` in the style of `channels.py` and `conversations.py`, not added
to `main.py`.

## 9. Tests

Following the repo convention, CI runs `python tests/run.py`:

- `tests/python/test_coding_store.py` - adding a non-git repo is refused; deleting a repo does not
  touch the disk; the registry migrates when fields are missing.
- `tests/js/test_trang_coding.js` - the chip row draws the bindings correctly; changing the permission level does not lose the session.

Add one canary for the borrowing rule: the Coding page must not build a second chat frame or
folder tree of its own.

---

## 10. For next time

Cut from the first version on purpose, with reasons:

- **Handover when changing engine.** `conversation_state.py` already has `StructuredState` (goals,
  decisions, open_questions, constraints, artifacts, last_completed_step); all that is needed is to
  add a coding block (repo, branch, restore point, files_changed, test_status). But per section 6,
  the new engine reading the repo is enough for the first version. To correct one figure from v0.1: working state is
  not "about 0 tokens"; writing it costs 0 because code writes it, but reading it has to sit in the prompt EVERY turn.
- **The `needs reply` status** and pushing it out to the inbox plus Telegram. See section 7.
- **Preflight before deploy** (tests pass and build passes and a restore point exists and the branch is allowed), plus
  **a secret scan before commit**. Not needed yet because the first version is not wired to deploy; when it is wired,
  these two come in together, not later.
- **Git and PRs in the UI**, Cloudflare / Supabase / VPS deploy adapters, deployment
  rollback.
- **API-only models running in a coding session.** The path exists (`engine.py`, the tool loop through the MCP Hub,
  at most 30 rounds), so this is an extension and not a new build, just not needed in the first version.

## 11. Decisions NOT to do

Kept because the reason for a rejection outlasts the thing rejected:

- **Automatic model switching.** See 5.1. Decided 2026-09-22.
- **Percentage quota table.** The subscription CLIs do not expose a trustworthy number to read in advance; you only
  know after you hit the limit. Drawing that table would promise something the infrastructure does not provide.
- **A fixed Work Tree column.** See section 7.
- **A separate Handoff Layer.** `conversation_state.py` is already the Working State. The word "handoff"
  also keeps its old meaning (a bot handing over to a human, `chatbot_store` / `chatbot_runtime`); switching
  engines is called a session handover.
- **Forcing API-only models through the Codex CLI.** v0.1 made this the preferred path with the Jarvis 007 runtime as the
  fallback. Reversed: the Jarvis 007 runtime is running for real, Codex-as-harness is an unverified assumption,
  downgraded to a one-day experiment.
- **An IDE, a complex editor, a heavy terminal UI.** `file-editor.js` and Terminal already exist.
- **Copying the whole transcript as the handover.**
- **Self-improve / ASA in this document.** Jarvis 007 already has its own `selfimprove` page. If it is built, the hard
  constraints are: run only in a separate worktree, only open a PR, never self-merge, never self-deploy
  `javis-os`.

---

## 12. North Star

> One Jarvis 007. Many engines. The user picks the engine, Jarvis 007 handles the rest.

---

## 13. Three rounds of fixes after trial use

Version 0.63.0 matched this document but got the experience wrong in a few places that only showed up with real users.
Recorded because all three rounds were the SAME kind of mistake, and that kind is easy to repeat:

- **0.63.1** removed the "No repo yet" blocking screen (a setup step had been put in front of a CHAT page),
  and changed REPO to FOLDER (git is something you read off the folder, not a condition for entry).
- **0.63.2** replaced the hand-drawn session list with the conversation column of the Chat page itself
  (`JavisChatSide.mount`), and added Plan mode.
- **0.63.4** replaced the path text box with the `JavisFolderPicker` folder browser, reusing the existing
  `.folder-modal/.fm-*` class set and the `GET /browse` endpoint; `/browse` gained `md=0` (skip counting .md files) and
  a `git` flag for each subfolder. The entry icon changed to `code-xml`.

The common mistake: **building a second copy of something the app already has** (the conversation list, the folder
picker), or **making the user declare data to fit the internal model** (must have `.git`, must type an
absolute path). Decision 3 at the top of this document already says "borrow screens, do not rebuild"; these three rounds
of fixes are the price of applying it only to the chat frame and forgetting everything smaller.
