# Jarvis 007 Core - actual architecture and handover

Original spec: the repo owner's request of 16/10/2026 ("make Jarvis 007 Core the default system assistant, pinned in every
brain, delivering reports to the right person, supporting follow-up questions and adapting through the Second Brain").
Delivered across four releases:

| Release | Content |
|---|---|
| 0.185.0 | Jarvis 007 Core: shared definition, pinning, server-side locks, a default chat per brain |
| 0.186.0 | Report routing to Jarvis 007 Core, every guess-based delivery removed |
| 0.187.0 | System notices (read state on the server, ask Jarvis 007 Core), push notifications tied to login, memory controls |
| 0.188.0 | After review: chat turns follow the chat's brain, a slimmer Jarvis 007 Core, a hard block on memory writes for Claude Code, the server fills in the memory source itself |

## 1. Architecture found during review (before 0.185.0)

- **One account per Jarvis 007 install.** `settings.json` holds exactly one `auth` (the owner). A login session is a bare
  token, not tied to a person. Several users = several independent Jarvis 007 installs (`docker-compose.multi.yml`). Every
  Telegram chat ID in the allow list is treated as the owner.
- **The open brain is chosen by the browser** and sent with every request; the server has no per-brain member list.
- **A single reporting gate:** `_notify_owner` → inbox (`inbox.json`) + ONE outside channel. An empty `owner_chat` sends to the
  **first Telegram ID**; an unknown chat ID is also funneled to the first ID; an empty or unknown Zalo target sends to **every** ID;
  `_loop_notify` (loop stopped on its own, dead brain) sends to **every** Telegram ID. Inbox entries have a `brain` field but nobody fills it in.
- **News (releases, community announcements)** is recomputed every time, and the read state lives in each browser's localStorage.
- **Push notifications** go to every registered browser, are not tied to a login, and are still received after logging out.
- **Memory** lives in `<brain>/memory/` (MEMORY.md + facts/). There is no place to view, edit or forget, no forgotten list, and the
  self-learning switch is one flag shared by every brain. Assistant lessons (`agent_lessons`) that were revoked could still be relearned.
- **Assistants** are just `<brain>/agents/<slug>.md` files; system skills are COPIED into each brain; system plugins are read
  straight from `system/plugins/` (the pattern reused for Jarvis 007 Core).

## 2. Design decisions

- **Jarvis 007 Core is not an agent persona.** Chatting with it is a full Jarvis 007 turn (CLAUDE.md, MEMORY.md, every tool)
  plus the `# === JARVIS 007 CORE ===` block taken from `system/agents/javis-core.md`. The session channel is `agent:javis-core`, so the
  Partners page, the inbox and the history treat it like an assistant, while `workflow_chat.persona_cua_phien` returns None for this channel.
- **One definition at the platform level**, not copied into brains. The slug `javis-core` is reserved: a stray `agents/javis-core.md`
  file inside a brain is ignored (`agents_index`, `_agent_file`), pack import cannot write it, and creating an assistant with the same name is refused.
- **"The right person" = the right account of that Jarvis 007 install.** With the one-owner-per-install architecture, the recipient is the owner;
  what has to be right is the source brain and the channel. No new account system is built (see section 6).
- **The default chat per brain** is tracked by a pointer the server keeps in `STATE_DIR/javis_core.json`; if it is deleted or archived,
  the next time a new empty chat is created and the old content is not resurrected.
- **No guessing the recipient.** `_report_route` decides where to deliver from the target + the brain OF THE JOB (passed in by whatever created the job),
  and never uses the brain currently open on screen.

## 3. Spec → code mapping

| Spec | Place in the code |
|---|---|
| 3.1 shared definition | `system/agents/javis-core.md`, `server/javis_core.py` |
| 3.2, 11, 12, 14 role, start, self-learning, limits | body of the definition file (the JARVIS 007 CORE block in the prompt) |
| 3.3 permissions | Jarvis 007 Core runs with the permissions of the turn; no route grants permissions by label |
| 4 pinning, locks | `GET /agents?system=1`, `_core_refusal` (delete, edit, rename, unpin, tag, Auto, assets, pack import, team lead creation) |
| 4, 5 default chat | `POST /javis-core/session`, `javis_core.default_session` |
| 6 routing | `_report_route`, `_notify_owner`, `_owner_telegram_id` |
| 6.4 missing information | inbox entry `routing: no_target / lost_origin`, sent nowhere |
| 7.1 general news, read state | `GET/POST /notifications/read`, `inbox.news_*` |
| 7.2 scoped news | `_loop_notify` → inbox + the owner's own Telegram, no longer broadcast to every ID |
| 7.3, 15 follow-up questions | `POST /javis-core/cite` (copies the notice, with source and time, into a dedicated Jarvis 007 Core chat) |
| 8 push, Telegram | `telegram.owner_chat_id`, `webpush` tagged with `phien` (session), `/auth/logout` removes the device, `push.preview` |
| 8 duplicates on retry | `inbox.add(dedup=...)`; keys per job/run in Kanban, loops, reminders, background jobs |
| 10.2 user profile | `STATE_DIR/user_profile.md`, `GET/POST /profile`, tool `javis_memory op=profile`, loaded BEFORE the brain memory |
| 12, 13 view/edit/forget/turn off | `server/memory_control.py`, `/memory/items|edit|forget|learning`; since 0.190.0 done through chat with the `javis_memory` tool (`server/memory_chat.py`, plugin `system/plugins/javis-memory`) |
| 12.4 do not relearn what was forgotten | `memory/forgotten.json` (fingerprints), `learn._promote_sync`, `agent_lessons.add` |

## 4. Test results by acceptance group

Each line is a real check in the tests (run `python tests/python/<file>`).

- **Default assistant** (`test_javis_core.py`, 34 checks): old and new brains both have Jarvis 007 Core at the top; delete, rename, unpin,
  tag, turn off Auto, edit through the form, attach assets, import a pack, and a team lead creating a duplicate slug are all refused by the server;
  12 concurrent calls create only one chat; deleting or archiving the default chat yields a new empty chat while Jarvis 007 Core stays.
  UI: `tests/js/test_javis_core_ui.js`, with real screenshots on desktop and iPhone 13.
- **Routing** (`test_javis_core_routing.py`): with an origin chat the report goes to that chat; without one it goes to the Jarvis 007 Core of the job's own
  brain (two brains, two places); if the origin chat was deleted it goes to Jarvis 007 Core when the brain is known and stays only in the inbox when it is not;
  no target and no brain means nothing is sent; Telegram/Zalo/Slack... no longer funnel to the first ID or broadcast to every ID.
- **System news, push** (`test_javis_core_notices.py`): read state on the server, marked once and seen on every device; asking
  Jarvis 007 Core copies the exact notice into the right brain's chat, asking again does not copy a duplicate, the general notice is unchanged; devices
  are tied to a login, logging out removes them, an expired login receives nothing; with content hidden, the push carries no text.
- **Self-learning and personalization** (`test_javis_core_memory.py`, `test_memory_chat.py`): view, edit, forget; once forgotten
  the learning loop does not write it back (same slug or same text); forgetting does not delete chats; with self-learning off, the learning loop, assistant
  lessons and the model's file-writing tool all refrain from writing to `memory/`, and the model is told; the model cannot change the switch or the forgotten
  list; revoked lessons are not relearned; the profile is shared across all brains and sits ahead of the brain memory.

## 5. Data migration and rollback

- No destructive migration. New files: `STATE_DIR/javis_core.json`, `news_read.json`, `user_profile.md`,
  `<brain>/memory/forgotten.json`, `<brain>/memory/learning.json`. New fields: `inbox` (`dedup`, `routing`),
  `push_subs` (`phien`), `settings.telegram.owner_chat_id`, `settings.push.preview`.
- Old notices in the inbox are kept as they are, old push notifications are not re-sent, deleted chats are not resurrected. Old entries have no
  `brain`, so they cannot be moved to Jarvis 007 Core: they still open as before (the origin chat, if it still exists).
- News: the first time the bell is opened after the update, the read list in that browser's localStorage is pushed to the
  server; a browser that has not been opened has nothing to push.
- **Rollback:** reinstall the previous release. The new files are ignored; Jarvis 007 Core chats remain in the store with channel
  `agent:javis-core` (the old release says "assistant no longer exists" when you open one, and the content can still be read through the history). Reports with no target
  fall back to the first Telegram ID again, as in the old behavior.

## 6. Limits and what is not done

- **Multiple users on ONE Jarvis 007 install is not supported.** The current architecture is one owner per install; the criteria "two people
  in the same brain keep private chats", "per-person read state", "revoke access per brain" only hold in the form of one Jarvis 007 install
  per person. Doing it for real needs: a users table, sessions tied to a person, an owner column on `sessions`, a per-brain ACL enforced
  at `_brain_root`, and a Telegram ID → person mapping. That is a separate project and needs a decision from the repo owner.
- **Every ID in the allowed Telegram list is still the "owner"** when chatting (as before). 0.186.0 only stopped SENDING
  reports with no target to them.
- **Turning self-learning off is hard-blocked on two paths:** the hub's file-writing tool (API engines) and the deny rule for `Write/Edit/MultiEdit/
  NotebookEdit(memory/**)` on Claude Code (0.188.0, which stays in force even under bypassPermissions). Not blocked: Claude Code's Bash
  commands that write files by themselves, and the own file tools of Codex, Grok and Antigravity; these paths only get the
  "NEW MEMORY IS OFF" reminder in the prompt (the prompt text itself is Vietnamese: "GHI NHỚ MỚI ĐANG TẮT").
- **Forgetting has limits:** a brain stored with git (self-learning uses git commits) still has the old version in its git history; a backup
  made earlier does too. The tool's reply says so after forgetting.
- **The user profile is written by the user.** Jarvis 007 does not infer personality or write into this profile on its own.
- Since 0.188.0, a memory the model writes during a chat turn without a `source` gets "chat <date> (<chat id>)" attached by the server
  (the Vietnamese text is "chat <ngày> (<mã chat>)").
  `status` (confirmed or inferred) and `scope` are still only present when the writing path fills them in.

## 7. Additions in 0.188.0 (after review)

- **Chat turns follow the chat's brain** (spec 9): opening a chat of brain B while brain A is selected runs the turn on B (the server
  switches brain per session and reports `brain_follow`); the chat shows a "belongs to brain B" line with a switch button; clicking a notice from another
  brain makes the dashboard switch brain FIRST and then open it. Incoming reports do not switch anything on their own.
- **Slimmer Jarvis 007 Core:** a loop run that finished fine (`quiet`) shows only in the bell (the "Ask Jarvis 007 Core" button still gets it in); a report
  sent to Telegram is copied into Jarvis 007 Core only when it is the owner's own Telegram.
- **The "Your Telegram" field** is a picker over the list of allowed IDs.

## 8. Minimal settings, memory through chat (0.190.0)

Repo owner, 16/10/2026, after seeing the Jarvis 007 Core card and the assistants column: Core's self-learning shows too many things while Jarvis 007 already has
context in the brain; the old assistant lessons are convoluted, and the Revoke and Use Everywhere buttons are something users do not know how to use. "It is better to
just message to delete, edit or revoke and let the AI do it for me." Settings keep only what the market is used to (change avatar,
name, description, instructions, documents, skills, model).

- **The Jarvis 007 Core card:** only the avatar, name, System label, role and one sentence "to remember, edit or forget, just message in chat".
  `dashboard/core-memory.js` is removed.
- **Single assistant column:** the settings form comes first. The Auto block (goal, rhythm, auto-run limit) sits below and only shows when the assistant's
  Auto is on (`veAuto` in `workspace.js`). The A3 Lessons section (`resonance-agent.js`) and the lessons list by scope, old lessons, self-review
  changes and proposals (`agent-lessons-ui.js`) leave the screen; the remaining section is "Auto limit".
- **The `javis_memory` tool** (owner sessions only, `safe` level, every engine): `list`, `edit`, `forget`, `learning`, `profile`,
  `lessons`, `lesson_add`, `lesson_revoke`. The rules stay the same: forgetting leaves only a fingerprint and is never relearned, revoked lessons are not
  relearned, and the model's file-writing tool still cannot write the switch.
- **Not put into the tool:** the A3 presentation lessons (short or full reports) were applied earlier; new proposals of this kind no longer
  have an Apply button, so none are generated. The routes `/memory/*`, `/profile`, `/agents/{slug}/lessons/*` remain for
  external tools.
- **The "Remembered · Undo" line** (`server/memory_receipt.py`, `dashboard/chat-nho.js`): at the start of a dashboard chat turn it snapshots
  `memory/` (excluding `conversations/`, `runs/`), and at the end compares again; new, edited and forgotten memories become one line pushed into the
  chat (hidden block `JAVIS_NHO`, which survives F5). Undo calls `/memory/forget`, so it is not relearned. If the answer claims "remembered,
  forgotten, revoked" (the `MEMORY_CLAIM` set in `server/lexicon`) while no file changed and no memory tool wrote anything
  (`memory_control.note_change`), a correction line is added. Dashboard path only; Telegram does not have this line yet.
- **Assistant card:** the chat time (12px) and the Auto switch share the `.ws-item-end` cluster at the bottom right, and the switch is on every
  assistant (the hide-when-off rule from 0.175.0 is dropped). The Auto block in the Settings column uses the compact rhythm table (`compact`): one
  plain-language limit line and the pending proposals; the full table stays in the Group pane.
- **News does not go into Jarvis 007 Core:** the News tab card drops the "Ask Jarvis 007 Core" button; notices about the owner's own jobs still have it.
