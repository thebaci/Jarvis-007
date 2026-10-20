# Team chat T5: the Teams page as compact as a chat app (0.129.0)

Stacked on T4 (PR #643). Source: the UI inspection session of 2026-10-14 (screenshots in `exports/reviews/team-ux-audit/`), the project owner approved the direction and asked for all three steps in one go. The T1 to T4 team flow is unchanged; only the presentation, the wording, and one new "Allow more turns" button change.

## Problems found (phone, 375px)

- The message frame was only 284px (35% of the screen). It was squeezed by:
  - the shared page header;
  - a two-row chat header;
  - the job filter box;
  - the paused banner;
  - a 5-row composer (209 to 249px).
- Member names broke one word per line.
- The Settings tab was 2,003px long with 31 input fields.
- The composer had two bugs:
  - the Assign job toggle and the send button both read "Assign job";
  - a person who was @-mentioned showed up twice (chip and text).
- A job blocked for running out of turns had a "Continue" button, but after clicking it the job was blocked again at once, because the cap had not been raised.
- Internal wording leaked to the user: cap, model turns, full authority, limited authority, queue position.
- The mascot covered the composer; the "Team" title appeared twice.
- Desktop: the chat frame was only 564px wide because the settings column was always open.

## New layout

1. **The page takes the full height.**
   - `console.js` adds `.cview-flush` and `body.on-teams`; `_pageLeave` removes both.
   - On phones, the shared page header and the mascot are hidden.
   - The composer is always at the bottom, leaving the bottom safe area.
2. **Team list in the style of a chat app.**
   - Each row has an initial-letter avatar (a fixed color per name), the name, the time, a preview line "Lan: ..." or "You: ...", and a badge: Needs you / Working / Paused / Archive.
   - When there are no teams yet, a three-step guide card appears with a New team button.
3. **One-row chat header:** back, the team name and "Lan leads the team · 3 people", the jobs chip, search, three dots.
   - The jobs chip reads "Needs you N" (warning color) or "Jobs N"; on phones only an icon with the number remains.
   - The message filter select is gone. Filtering by job is now a banner "Showing messages of job X" with a Show all button.
4. **Compact banners with buttons:** if paused, Resume; if there is no team lead yet, Pick.
5. **A job strip at the top of the chat frame.**
   - A running job shows one line, with Edit request and Cancel.
   - Jobs waiting for you show at most two cards, each with one button that resolves it according to the reason (table below); if there are more, they collapse into one button.
6. **Bubble-style messages.**
   - The owner's messages are on the right, without a name.
   - The assistant's messages are on the left, with an avatar and name.
   - The role label only shows for job steps.
   - The "Done" status is hidden; a reply that was not used shows a one-line warning.
   - A system message is a gray line in the middle.
   - The emotion button (assistant messages) or three dots (owner messages) sits next to the bubble, adding no row.
   - Long-press opens the sheet for every message. Pinning is inside the sheet; a pinned message has a Decision label, and clicking the label unpins it.
7. **One-row composer:** the Assign job toggle (`aria-pressed`), a text box that grows up to about five lines, a round send button.
   - The people being called are the "@Name" strings still in the text at send time: deleting the text removes the call, and there are no duplicate chips.
   - Only when Assign job is on is there a line "Will create a job for ...".
8. **The "Jobs | Team" drawer is closed by default**, opened from the jobs chip or the three dots.
   - It shows as a right column on desktop, a drawer with a dimmed backdrop below 1060px, and a page that slides up below 760px.
   - Escape or tapping the backdrop closes it, and focus returns to the exact button that opened it.
   - **Jobs tab:** Working on, Waiting for you, Up next (in order) (numbered, Prioritize, Cancel).
   - **Team tab:**
     - members one per row, tap to open the actions;
     - "How much can the coordinator decide alone?" with three levels;
     - "Used today: X of Y replies";
     - name, description, status;
     - "Advanced" (closed by default) holding the limit numbers, T3's detailed permissions box and the reply log.

9. **The avatar is the assistant's real avatar, and team pinning** (the owner asked for this the same day, reference: Zalo, "Offsite crew").
   - Every place that draws an assistant (messages, member list, @ suggestions) uses the `JavisAvatar` set from the Partners page, by slug and the `avatar` in the assistant's file. `_resonance_agents_meta` includes `avatar`; `member_views` returns `avatar` for each member.
   - The team picture is composed from the active members' pictures (team lead first): 1 person one picture, 2 people diagonal, 3 people a triangle, 4 people a 2x2 grid. With more than 4 people, three pictures and a "+N" cell (over 99 shows "99+"). `GET /teams` includes `faces` (at most 4) and `member_count`; the chat header derives it from the members.
   - Pinning: column `pinned_at` in `teams` (added automatically to old stores), `TeamStore.set_pinned` (events `pinned` / `unpinned`), route `POST /teams/{id}/pin {on}`. The first page of the list opens with the pinned teams (the most recently pinned first), and later pages only contain unpinned teams so nothing repeats. A team row has a pin mark; the "Pin this team to the top" toggle is in the Team tab.

10. **Pin right on the list** (the owner approved after asking "do we need pinning by long-press").
    - The toggle in the Team tab is still the visible path; this is the shortcut that Zalo and Messenger users are used to.
    - Desktop: hovering a team row shows a pin button in the corner of the row. This button is a sibling of the open-team button, not nested inside it.
    - Right-click on a row opens a menu "Pin team" or "Unpin".
    - Phone: long-pressing a team row for 0.5 seconds opens the same menu. The click generated on release is blocked (`swallowClick`, cleared on the next touch) so the wrong team is not opened. Touch devices have no floating pin button.
    - The menu closes with Escape (focus goes back to the team row), a click outside, or after choosing.
    - Pinning from the list shares `savePin`: an error is reported, nothing gets stuck.
    - Sandbox smoke: hover then click the pin button; right-click then Unpin; Escape; long-press with simulated touch events (the menu opens, the team is not opened by mistake); a short tap still opens the team.

## Buttons that resolve a blocked job

| Block reason | Button |
|---|---|
| `cap_reached` | Allow more turns (new route `extend`) |
| `failed`, `no_progress` | Try again (reruns the step) |
| `interrupted` | Continue (reruns the step) |
| `no_leader` | Pick a coordinator (opens the Team tab) |
| `agent_busy_long`, `waiting_user` | Continue |
| `assignee_removed` | Cancel only |

## Three levels of self-decision (built on T3's Full authority)

| Level | Sent to `POST /teams/{id}/authority` |
|---|---|
| 1 Ask me first | `mode: limited` (revoke) |
| 2 Act, then tell me | `ceilings {task_turns 24, task_steps 12, help_depth 3, daily_turns 200}`, no interrupting jobs, no Unlimited provider, subscription plan |
| 3 Run the whole team | every maximum cap Unlimited, may interrupt jobs, no Unlimited provider (asks again before turning on) |

- `levelOf` reads the grant box back and only compares the maximum caps, the interrupt permission, and the providers. If the team lead adjusts the numbers within the allowed range, the level stays.
- A grant box that matches none of the three levels shows as "Custom"; edit the details in Advanced.

## Code map

| Part | File | What it does |
|---|---|---|
| Runner | `server/team_runner.py` | `_block_cap` (records a `cap_blocked` event with the cap that was hit and the rejected steps, then blocks), `_put_steps`, `extend_job`, `usage`; block reasons and system messages in plain words (`CAP_PLAIN`, `EXTEND_TEXT`) |
| Team store | `server/team_store.py` | `update_authority_caps(..., ceilings=)` so the owner can raise the maximum caps too |
| Routes | `server/team_api.py` | `GET /teams` includes `last`; `GET /teams/{id}` includes `usage`; `POST /teams/{id}/tasks/{task}/extend` (404 for a job of another team, 409 for a job not blocked for running out of turns) |
| UI | `dashboard/teams.js`, `console.css` (the `tm-*` block at the end of the file), `console.js`, i18n vi and en | as above |

## Allow more turns (`extend_job`)

All of it runs inside `accept_lock`, so when two clicks arrive at the same time only one has an effect.

1. Read the job's newest `cap_blocked` record. The record is written BEFORE blocking, so it belongs to the current block.
2. If that cap still blocks (by the real number used), raise it to `max(cap, used) + step`. Steps: replies per day +20, replies per job +6, steps +4.
   - If the grant box sets a number for that cap, raise it in the grant box (and raise the maximum cap if it is lower).
   - Otherwise raise the team's own cap.
3. If that cap no longer blocks (a new day, or the owner already raised it), raise nothing.
4. Add back the rejected steps. A step that follows after asking for help is reconnected exactly as in a normal add.
5. The job goes back to the waiting queue.
6. A `caps_extended` event and a system message in plain words are recorded.

A job blocked from before the record existed is guessed from the real numbers. The step cap is only guessed when no step is waiting, because a block caused by turns always sends the steps back to the queue.

## Verdicts

- **Raise from the number used, not from the cap.**
  - Why: if the cap was lowered below the number used, raising from the cap would block again at once.
  - Cost if wrong: one click can give more than one step over the old cap.
- **Allow more turns when the daily cap is 0 (the owner turned it off on purpose) still raises it to 20.**
  - Why: this is a clear click by the owner, with a system message recording it.
  - Cost if wrong: this button can get past the "off switch" of a cap of 0.
- **A paused team can still be given more turns.**
  - The job goes back to the queue and the message says clearly that the team must be resumed.
- **Level 3 is "maximum caps Unlimited", not "model turns Unlimited".**
  - No provider is Unlimited (D6), so the team lead has to set the numbers itself.
  - The description says exactly that.
- **The mascot is only hidden on phones.**
  - On desktop it sits at the right edge like on every other page, and sometimes overlaps the edge of the Team drawer.

## Final review (fresh reviewer, strongest model)

Verdict "Not ready": 1 Critical, 5 Important, plus Minors. I fixed all the Critical and Important ones, plus two Minors raised in priority because users bear real consequences, and a few cheap Minors.

- **C1. A block from the step cap lost the rejected steps.** After Allow more turns, the job became `failed` ("No steps left to run").
  - Now the rejected steps are recorded in the `cap_blocked` event and added back on Allow more turns.
- **I1. A cap that was hit but no longer blocks raised the wrong step cap.**
  - Now it reads the cap from the record made at block time, and raises nothing if that cap no longer blocks.
- **I2. A cap lowered below the number used still blocked again right after allowing more.** Now it raises from the number used.
- **I3. The drawer at 761 to 1060px sat under the global top bar**, so the tab row and the close button were covered.
  - Now it starts from `--topbar-h`; the page slides up to the real viewport height.
- **I4. The level 3 description promised to remove limits while the server still applies the team's cap.** Rewritten.
- **I5. A pinned owner message opened an empty sheet**, and from then on new messages no longer scrolled down on their own.
  - Now the three-dots button is gone and no sheet opens for that message.
  - `drawMsgs` also drops the open state when the sheet is not drawn.
- **Raised to Important:**
  - the email address "ho@lan.vn" was treated as calling Lan (costing a model turn); now the "@" must be at the start of the text or after a non-letter character, and matching uses NFC text;
  - while typing in the Team tab, a team event made the drawer redraw and lose the text; now it does not redraw while typing in a text field.
- **Minors fixed:**
  - a failing Allow more turns no longer leaves the button stuck disabled;
  - when changing the level fails, the selection returns to the real level;
  - a reply log that comes back late after switching teams is dropped;
  - the three levels are a named choice group (fieldset + legend);
  - the drawer button has `aria-expanded`, and the drawer body is a `tabpanel`;
  - member toggles and the status choice buttons are a full 44px;
  - long job labels are cut with an ellipsis;
  - 9 unused text keys were removed.

Cases red first, then green:
- `test_team_ux.py`: C1, I1, I2.
- `test_teams_ui.js`: the "review T5" cases.

I fixed the two CSS cases (I3, 44px) before writing tests, so they were never seen red.

## Review of head `b93c46bd` (report `exports/reviews/PR-645-b93c46bd-review.md`)

Three P2 bugs, all fixed. Each has a reproducing test that ran red first, then green.

1. **The pin toggle got stuck when saving failed.** A non-200 HTTP response or a network error left the toggle in the unsaved state and disabled, and the network error was even missed.
   - Now `savePin` locks the toggle while saving. On an error it returns to the saved state, re-enables it to try again, and reports the error (a network error has its own sentence).
   - Behavior test with a fake toggle: HTTP 500, a rejected fetch (no unhandled rejection), a successful save.
2. **Old messages lost their avatar and name when an assistant left the team.** The message avatar was looked up among the active members.
   - Now `GET /teams/{id}` also returns `authors` {agent_key: {slug, name, avatar}} for every assistant that was ever in the team (`members(include_removed=True)`, identity looked up by agent_key).
   - A message looks up its author among the members and then in this table; search results do too.
   - The team picture and the @ suggestions still only use active members.
   - Test: the route after removing, and after deleting then recreating an assistant; a message by an author no longer in the team.
3. **Allow more turns lost the rejected steps when the block record fell out of the team's last 500 events.**
   - Now `TeamStore.cap_record(team_id, task_id)` looks up the newest `cap_blocked` record of exactly that job directly in SQLite (`json_extract`), with no limit on the number of events.
   - Test: blocked by the step cap, then add a record for another job, then 600 pin / unpin events. After that, Allow more turns adds back both steps, and the job runs to completion.

Checks:
- `tests/run.py --js` 186/186.
- `test_teams_ui.js` 184 items.
- `tests/run.py team agent_avatar agents_danh_sach_nhe resonance_mvp_main route_table icons` 24/24.

Temporary SQLite, fake engine, no model calls.

Correction of numbers: the report and earlier write-up said the UI test had "190 items". It was actually 178 items at that time.

## Review of head `4f6268bd` (report `exports/reviews/PR-645-4f6268bd-review.md`)

Two P2 bugs, all fixed. Each has a reproducing test that ran red first, then green.

1. **Old messages took the name and avatar of a new assistant that reused the slug.**
   - **Bug:** the author table took the name and avatar by the slug of the current file. Deleting Minh and then creating a new Minh with the same slug made the old key also become "new Minh".
   - **Identity snapshot:** identity is now kept by agent_key (`TeamApi._identity`). The current file is only used when the identity row of exactly that key is still `active`; a key that has retired or is `missing` does not use it. When it can be confirmed, the identity is captured into a new column `team_members.identity_json` (added automatically to old stores; written only on change).
   - **Cannot be confirmed:** use that key's own latest snapshot.
   - **Never captured (an old record):** fall back to the key itself, meaning the name by the slug at the time of joining the team and the avatar derived from the key (`avatar_seed`, the dashboard draws by key, not by slug). It never takes the name or avatar of the new assistant.
   - **Test:** old Minh (default avatar) is deleted; new Minh with the same slug has a different picture and color. The old key keeps exactly "Minh" and the old avatar, the new key is "new Minh" with the new avatar. Added a case where deleting the snapshot makes the old key fall back to its own fallback.
2. **A pin error from the list was invisible on phones.** The notice area was inside the chat frame, and the chat frame is hidden while on the list.
   - **Shared toast:** the `.tm-note` notice area moves out of the chat frame into a layer floating over the whole page (`role="status"`, solid background). It has a Try again button when the action can be rerun, and a close button; it hides itself after 8 seconds, or 15 seconds if it has Try again.
   - **Pin from the list:** goes through `pinTeamWith(id, on, btn, deps)`. An HTTP error or lost network is reported with a Try again that reruns exactly that action. Lost network has its own sentence `teams.err_network` in place of the word "network", also used when sending a message.
   - **Test:** HTTP 500, a rejected fetch (no unhandled rejection), Try again and then a successful save. Also checks that the notice sits outside the chat frame and that CSS does not hide it on the list.
   - **Browser smoke** at 375px, on the list: simulating POST /pin returning 500 and then lost network, the notice is visible with Try again; Try again with a healthy network pins. Screenshot `exports/reviews/team-t5-smoke/m08-ghim-loi-mang-danh-sach-375.jpg`.

Checks:
- `tests/run.py --js` 186/186.
- `test_teams_ui.js` 200 items.
- `tests/run.py team agent_avatar agents_danh_sach_nhe resonance_mvp_main route_table icons i18n changelog em_dash docs` 29/29.

Temporary SQLite, fake engine, no model calls.

## Left over (Minor, not done)

- Two members with the same display name: an @ always points to the first.
- The drawer does not trap focus yet and the tabs do not move with the arrow keys.
- Allow more turns raising the maximum caps of level 2 makes the level show as "Custom".
- Every team event reloads the team list along with each team's last message (at most 50); it works, but should be watched.

## Checks

| Command | Result |
|---|---|
| `tests/python/test_team_ux.py` | allow more turns by the daily cap, the per-job cap, the step cap (add back rejected steps, run to completion), Full authority with numbers (raise in the grant box and the maximum cap), a cap that no longer blocks, a cap below the number used, a job that is not blocked does nothing; the number used today; block reasons and system messages in plain words |
| `tests/python/test_team_api.py` | `last` in the list, `usage` in the details, the extend route: 200, 409, 404 |
| `tests/js/test_teams_ui.js` | 163 items: list, bubbles, job strip, resolve buttons, jobs chip, @ by text (email, NFD, the long name wins), three levels, the Team tab and Advanced, drawer, one-row composer, CSS `[hidden]` and 44px, vi/en text |
| `tests/run.py --js` | 186/186 |
| Affected Python | 12/12 (`team_runner`, `team_t1_review`, `team_authority`, `team_reactions`, `team_history`, `team_ux`, `team_perf_bench`, `route_table`, `team_store`, `team_api`, `icons`) |

**UI smoke** (sandbox port 7788, team paused, daily cap 0, no model calls). Screenshots in `exports/reviews/team-t5-smoke/`; compare with the earlier screenshots in `exports/reviews/team-ux-audit/`.

| Measurement | Before | After |
|---|---|---|
| Message frame on a 375px phone | 284px | 461px |
| Composer row | 209 to 249px | 44px |
| Team tab (settings) | 2,003px | 908px, numbers set in Advanced |
| Member names | one word per line | one line |
| Chat frame on a 1366px desktop | 564px | 926px, drawer closed |

Tried on the sandbox:
- the three levels (switching back and forth, level 3 asks again);
- Allow more turns (daily cap 0 became 20, the job went back to the queue; then reset to 0 right away);
- @ inserting a name and the Assign job hint line;
- the drawer with a dimmed backdrop at 900px;
- a new system message.

Not tried on a real iOS/Android device or with a screen reader.
