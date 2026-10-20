# Bot Inbox improvements: filter by bot, reply right inside the inbox (design)

30 Sep 2026. Requested by: the project owner ("propose improvements for the inbox, need to filter conversations of multiple bots, add a reply
button right inside the chatbot to quickly choose auto-reply if it is in the right mode; want a dropdown, not a row of buttons").
Delivered as three slices, one small PR each. Slice 1 shipped in 0.65.3.

## 1. Problem

- Running three bots in different fields (Jarvis 007 Vũ, Nhi Mai, Ngọc Thu) makes the inbox blend together: each row has only the channel logo, no bot name.
- The old filter had only channel chips (shown only when there are two or more channels) and a bot picker hidden when fewer than two bots have accounts.
  No filtering by unread, needs a reply, taken over, group or private chat. And the row of chips costs space.
- Replying: sending by hand is an implicit takeover (the bot goes silent), with a small Takeover button in the corner. There was no way to ask the bot to answer a message it stayed silent on, and no
  way to ask the bot to draft something for the owner to approve.

## 2. Decisions (key points from the design session)

- **Dropdowns, not chips.** One row shared with the search box: Bot, Status, Type; Channel only when there are two or more channels. Use the browser's native select (on phones it opens the device's
  picker). Counts sit inside the options, computed over the WHOLE inbox so they do not jump when filtering.
  One value per select. The trade-off accepted: no colored dot inside the dropdown (each list row still has a bot name tag in the same color).
- **"Needs a reply" must mean something real.** The customer messaged last, nobody has answered, nobody has taken over, AND (a private chat, or a group where the bot just
  considered speaking and then stayed silent). Counting every group where a customer messaged last fills the filter with junk, because the bot speaking only when called is normal.
  "The bot considered it and stayed silent" comes from the arbiter store: decision `silent`, a candidate, code `judge_silent` / `below_threshold` /
  `rate_limited` / `rate_limited_user` / `policy_error`, unlabeled, within 24 hours. `agent_silent` (the Agent chose silence deliberately) does not count.
- Defaults for the rest (the owner was not asked again, following the recommendation): both "Reply for me" and a per-chat auto switch exist for
  each chat; and "Suggest a reply" exists.

## 3. Slice 1 (0.65.3, shipped): filters and the bot name tag

- `conversations.danh_sach(status, chat_type, hesitant)`, `dem_bo_loc(hesitant)`; `bot_id="-"` = a chat with no bot.
  An unknown value of `status` / `chat_type` makes that filter be IGNORED (an old value still stored in the browser must not make the inbox empty).
- `GET /conversations` additionally returns `bot_name` and `need_reply` per row, `facets`, and `bots` (bots that have conversations, with names; a deleted bot
  shows "Deleted bot", with no raw id leaking). If the arbiter store does not exist yet the groups part is empty, and no file is created.
- UI: `conversations-filters.js` (the pure part: state, browser persistence, building `<option>`s, bot colors) and drawing in `conversations.js`.
  An open dropdown is not rebuilt in the middle of the 5-second auto-refresh beat (that would close it mid-use). Phone: the search box and Bot each get a row,
  Status and Type split one row in half. The bot name tag appears only when there are two or more bots.

## 4. Slice 2 (0.65.4, shipped): the Automatic / I reply switch and the status bar

- Top of the conversation pane: a two-position switch **Automatic | I reply** replacing the small Takeover button (it calls `POST /conversations/{id}/mode`, no new API).
- Bottom of the pane: ONE status line ("Nhi Mai is on duty for this chat" / "You have taken over, the bot is silent") then a row of two buttons of equal height, splitting the width in half,
  never wrapping (the first mockup was misaligned because the status tag was smaller than the buttons and the second button dropped down); the input box and the send button share one row.
- A "Bot stayed silent: <reason>" line right in the message pane, taken from the arbiter log, with no need to open a menu. `GET /conversations/{id}/messages` additionally returns
  `bot_silence` (code, score, threshold) and `bot_name`. The conditions for showing it are deliberately strict because showing it wrongly is worse than not showing it: the chat is in AI mode, the last message is the
  customer's, the latest decision is `silent`, and its time differs from the last message by no more than 60 seconds. A real person has taken over, the bot has answered, the decision is `reply`,
  or the arbiter store does not exist yet (no file is created): it does not show. The "Why" button opens the bot's Reply judge panel.
- Phone: the switch moves to its own row spanning the full width, two positions splitting it in half, instead of squeezing into a title that has only a few dozen pixels left.

## 5. Slice 3 (0.65.5, shipped): Reply for me and Suggest a reply

- `POST /conversations/{id}/ai-reply` with `mode=send|draft`. It uses the existing reply path of THAT bot itself (its Agent), skips the
  "should it speak" gate but keeps the permission guard and the safety limits. `send`: sends through the channel in the bot's name, the chat stays Automatic, the Inbox records it as a bot message,
  and if that message was once chosen silent by the arbiter, it counts as the heaviest "wrongly silent" label so the bot learns. `draft`: only returns text to fill into the input box, does NOT write to the
  Agent session (uses `phien_kho` / `ghi_kho=False` of `_tg_answer`) and does not write the Inbox.
- Enabled only in the right mode: the bot is running, the chat is Automatic, the channel can send. Otherwise the button still shows, and touching it says why (not hidden, not silently grayed out).
- Risks watched (all have tests): the customer's message is not recorded twice in the Inbox; two runs cannot overlap on one chat (`busy`); a Zalo group message is sent in the group way;
  a draft always cleans up its traces even when the engine throws; if sending fails, the composed text is returned; the turn's channel is taken from the conversation ITSELF (`meta._kenh`) so the sentence the bot
  writes back lands in the right conversation (the first test caught a bug where it fell onto the default channel).
- **Echo on personal Zalo**: the channel's send path does not remember the sentence just sent (only `Transport._gui` does that), so a sentence the bot sends from the Inbox must call
  `ghi_da_gui` before sending, otherwise the read loop sees it come back as the owner's own message (the bot thinks the owner messaged by hand and stays silent for a stretch) or as a customer message
  (the bot answers itself). The owner's manual send path keeps its old behavior.
- The status line tells the truth when the bot is off ("it is off so it does not reply on its own"), and does not say "on duty".

## 6. Not doing (deliberately)

- No filtering by several bots at once, no grouping by bot, no custom-drawn dropdown (not needed yet).
- No merging the Inbox with the Chat page.
