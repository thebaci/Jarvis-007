# Spec: Zalo Bot channel (official API)

> Dev spec, written 2026-08-08 on top of v0.26.3. Source: the official documentation
> <https://bot.zaloplatforms.com/docs/> (read on 2026-08-08).
>
> **Status: PHASES 1, 2, 3 (inbound), 4 and 5 ARE DONE.** The dedicated bot has run on
> Zalo since v0.26.5; the OWNER's Zalo channel and notification routing were finished in v0.26.8. Four
> deviations from this spec are recorded right here instead of leaving the reader to cross-check:
>
> - **PHASE 5 WAS DONE BEFORE PHASE 4**, at the repo owner's request (2026-08-08): the value is in the
>   dedicated bot talking to Vietnamese customers, not in the owner's channel.
> - **The shared part was split out into `server/bot_gateway.py`** instead of letting `zalo_bot.py` copy it:
>   the turn queue, the `/stop` rule, the precheck gate and the tool trace line are Jarvis 007 behavior
>   rules, not details of one provider. `TelegramBot` now uses it too.
> - **An EMPTY whitelist = NOBODY IS ALLOWED YET** (section 5 only talks about the waiting queue, not this
>   rule). On Telegram an empty field means open to everyone; keeping that habit on Zalo would turn the very
>   "enable the bot with an empty field, then message it yourself" flow the UI walks people through into a
>   bot that anyone can use to reach the brain, in the gap between enabling it and clicking Allow.
> - **Phase 0 (probing the real API) has answered only ONE question so far**, see section 7. The rest still waits
>   for a real token. The code is written to tolerate all three possible `getUpdates` response shapes, and it
>   complains on stderr when it meets an unfamiliar shape.
>
> **Remaining: Phase 3 OUTBOUND (sending images) and Phase 6 (webhook).** Both depend on the probe
> results and on where Jarvis 007 is running.

## 1. Core decision

**Zalo Bot is the FOURTH CHANNEL, not a second runtime.**

Jarvis 007 already has three channels that pass through exactly one core: dashboard, Telegram, CLI. `main.py` hands
`telegram_bot.TelegramBot` exactly a few callbacks (`answer_fn`, `command_fn`,
`callback_fn`, `precheck_fn`, `event_fn`) and that is all; the whole part that matches sessions, picks the brain,
calls the engine and saves the conversation lives in the `_tg_*` group of functions in `main.py`, which already took a
`channel` parameter before (the CLI and the dedicated bot share it).

That means **the job is to write a new transport layer, not a new gateway.**
`server/zalo_bot.py` keeps the exact contract of `TelegramBot` and plugs into the existing `_tg_answer`.
It does not touch `telegram_bot.py` in the first stage, so the most heavily used channel
takes no risk.

**Zalo Bot does NOT replace the Zalo Agent MCP.** They are different in nature and coexist:

- `zalo-agent-cli` (zca-js) logs in **your own Zalo account**: it can read real conversations,
  message anyone, and Zalo may lock the account.
- Zalo Bot is **a separate identity**, official, not subject to locking, but it only sees
  what people message to it directly.

The first lets Jarvis 007 **act on your behalf**. The second lets **other people talk to Jarvis 007**.
Anyone who merges the two into one loses half the capability.

## 2. Zalo Bot API: what the documentation says

In shape, this is almost a copy of the Telegram Bot API.

| Item | Value |
|---|---|
| Base URL | `https://bot-api.zaloplatforms.com/bot<TOKEN>/<method>` |
| Token | looks like `12345689:abc-xyz`, **does not expire** until the owner resets it |
| Where to get the token | open the Zalo app, find the OA **Zalo Bot Manager**, choose Create bot; the bot name must start with the word "Bot". The token is sent back as a Zalo message |
| Response envelope | `{ok, result, description, error_code}` |
| Receiving messages | `getUpdates` (long polling, the docs say explicitly it should **only be used when running locally**) or webhook |
| Available methods | getMe, getUpdates, setWebhook, deleteWebhook, getWebhookInfo, sendMessage, sendPhoto, sendSticker, sendVoice, sendChatAction |

`sendMessage` takes `chat_id`, `text` (1 to 2000 characters), `parse_mode` (`markdown` or
`html`), or `text_styles` as an array. It returns `{message_id, date}`.

`sendPhoto` takes `chat_id`, `photo` (the docs say "image path"), and `caption` up to
2000 characters. `sendChatAction` has only `typing` so far; `upload_photo` is marked Coming soon.

Webhook: `setWebhook` needs an HTTPS `url` and a `secret_token` of 8 to 256 characters. Zalo POSTs
JSON back, with an `X-Bot-Api-Secret-Token` header that must be checked. Events are
`message.text.received`, `message.image.received`, `message.sticker.received`,
`message.voice.received`, `message.unsupported.received`. The real payload of a text event:

```json
{ "ok": true, "result": {
  "message": {
    "from": { "id": "6ede9afa66b88fe6d6a9", "display_name": "Ted", "is_bot": false },
    "chat": { "id": "6ede9afa66b88fe6d6a9", "chat_type": "PRIVATE" },
    "text": "Xin chào", "message_id": "2d758cb5e222177a4e35", "date": 1750316131602 },
  "event_name": "message.text.received" } }
```

(`"Xin chào"` is Vietnamese for "Hello", kept as the original sample payload.)

Error codes: 400 wrong path or API name, 401 wrong or expired token, 403 server error,
404 not found, 408 timeout, **429 rate limit exceeded**. The docs do not publish the limit
figures, and both the Pricing page and the FAQ were returning HTTP 500 at the time of the survey.

`getMe` returns `account_type: "BASIC"` and `can_join_groups: false`.

## 3. Seven places Zalo Bot DIFFERS from Telegram, and which of them break the current UX

This is the most important part of the spec. Copying the Telegram behavior over as is breaks things immediately.

1. **No `editMessageText`, no `deleteMessage`.** The "🤔 Jarvis 007 is processing…" message that changes
   its text with progress and then deletes itself, which has a whole section in
   `docs/11-telegram.md`, **cannot be done on Zalo**. See section 3.1 below, because this is
   something to redesign, not something to trim.
2. **No inline buttons, no callbacks.** The provider picker and the model grid of
   `/model`, and the brain picker of `/brain`, all rely on `callback_query`. On Zalo they must be reduced to
   **numbered lists**, reading the number on the next turn. Jarvis 007 already has this path for the
   `JAVIS_ASK` block; reuse it instead of writing a second one.
3. **A 2000-character cap, not 4096.** The message-splitting constant has to be per channel.
4. **No `sendDocument`.** PDF, xlsx, docx have no way out. This is the biggest functional
   gap compared with Telegram, and it must be stated plainly in the user docs rather than
   silently swallowing the file.
5. **`sendPhoto` takes an image path, most likely a public URL.** The "Using the API" page lists
   `multipart/form-data` for file upload, so pushing a file directly may be possible,
   but the `sendPhoto` docs do not confirm it. **It must be tried for real before designing**
   (see Phase 0). If it only accepts a URL, a machine running locally cannot send images out, and Jarvis 007
   must say so honestly instead of reporting success.
6. **`getUpdates` has no `offset` or `update_id`.** The only parameter is `timeout`.
   There is no acknowledgement mechanism, so **deduplication must be done by hand using `message_id`** (an LRU
   of a few thousand ids in memory). This is where the bug of answering one message twice is easy to create.
7. **`can_join_groups: false` on the BASIC plan.** The scenario of a customer-care bot in a group, which
   `chatbot_runtime` does quite carefully on Telegram, may not be usable on the free plan.
   The UI must hide the group configuration when `getMe` returns `false`, rather than showing it
   and letting it die silently.

### 3.1. Showing progress without sending a message and then deleting it

The repo owner stated clearly (2026-08-08): **sending a status message and then deleting it is wrong**; what is needed is
to see the operation states ("calling tool X"), while a message that flashes and disappears
is not. This settles the design for both channels.

First, a technical fact to keep in mind: **`sendChatAction` cannot carry arbitrary text.**
Both Telegram and Zalo accept only a fixed set of actions (typing, upload_photo...).
So to show a tool name, **it has to be a real message**, there is no
second route. The problem to solve is not "drop the message" but "do not let any message
disappear".

**Telegram: the status message is sent silently and stays as a trace line. DONE in v0.26.4.**

`_send_status` adds `disable_notification: true`, so the status message appears without
buzzing the phone. It is still edited in place as before to follow progress. When the work is done it is **not deleted**:
the last edit turns it into a compact trace line (`⚙ pos_statistics · Read · 8s`, or
`✓ Direct answer · 3s` when the turn called no tool), then the answer goes out as a NEW
message with a notification sound. `/stop` edits that line into `⏹ Stopped.`. `_del_msg` was removed from the code.

Result: exactly one notification sound per turn, and the phone notification shows exactly the content of the
answer.

**Considered and rejected: letting the status message turn into the answer itself** (a single
bubble for the whole turn). The chat is tidier, true, but `editMessageText` **does not trigger a notification**, so
the user would not be alerted when the answer is done. For a handheld assistant that is a
bigger loss than the tidier chat. Rejected.

(The Vietnamese status strings `Trả lời trực tiếp` = "Direct answer" and `Đã dừng.` = "Stopped." are code
output; they are rendered here in English for the reader.)

**Zalo: a "typing" dot plus a tool trace line attached to the answer.**

Zalo can neither edit nor delete messages, so **there is no dynamic status at all**. All that is left is
`sendChatAction typing` kept alive through the turn (Phase 0 has to measure how long until the dot goes out
to know the refresh interval). Never send a separate status message on Zalo: once sent it stays
there permanently.

To compensate, attach **one compact trace line** to the answer, like `⚙ pos_statistics · Read · 8s`.
It stays permanently but is not junk, and it is proof the tool really ran, exactly the
role the "⚙ Calling..." line plays on Telegram. This line should be shared by both
channels, because on Telegram once the bubble turns into the answer the progress history
is lost with it.

**Considered and rejected:** reacting to the very message the user just sent (`setMessageReaction`,
Bot API 7.0) is a real state and creates no message. But it can only pick from a fixed emoji set,
so it cannot say the tool name. Using it alongside is fine; using it instead loses information.
Zalo has no equivalent API.

## 4. Why it is worth doing

In short: **Vietnamese customers do not use Telegram.**

The Telegram channel is currently the only door for asking Jarvis 007 from a phone, and it is where every
background notification (loops, Kanban jobs, reminders) lands. For a hardware shop owner in Vietnam,
Telegram is a strange app they would have to install. Zalo is already on the phone.

Two products open up from exactly one transport layer:

- **The owner's channel.** Ask Jarvis 007 through Zalo, receive loop reports and reminders through Zalo.
- **A dedicated bot on Zalo.** `chatbot_store` has had the field `"channel":
  "telegram"` since it was designed. Letting it accept `"zalo"` as well means the shop's consulting bot can
  talk to real customers, on the real app they already have open. This is the part with
  business value, and it is almost free architecturally once Phase 1 is done.

## 5. User pairing: do not copy Telegram's way

Telegram makes the owner look up the Chat ID with @userinfobot and paste it into the whitelist field. Zalo
**has no** equivalent tool, and the id is a hex string like `6ede9afa66b88fe6d6a9`, from which
nobody can tell who it is.

The approach: a **pairing code**. When a stranger messages the bot, the bot replies "You have not been granted
access to Jarvis 007. Your pairing code: 4821". The Channels page on the dashboard shows a small card
listing the waiting chats, with the real `display_name` and the code, plus an **Allow** button. One
click puts the id into the whitelist.

Details to settle up front: the waiting queue holds at most 20 entries, each entry lives 30 minutes and then drops off, and an unknown
chat_id receives only one rejection message per 10 minutes (to stop strangers pumping messages
to flood the queue). The pairing code lets the owner match the right person when two people share a name.

This fits the habit (`feedback_khong-bat-user-chay-lenh`, i.e. "do not make the user run commands": do not make users
do the plumbing work), and is also something that should be brought back to Telegram later.

## 6. Architecture and the files to touch

**New files**

- `server/zalo_bot.py`: class `ZaloBot`, keeping the exact contract of `TelegramBot`
  (`answer_fn`, `command_fn`, `precheck_fn`, `event_fn`, `download_dir`, `commands`,
  `giau_trang_thai`). It drops `callback_fn` because Zalo has no buttons. Inside: the long poll loop,
  deduplication by `message_id`, a per-chat queue like the Telegram version, message splitting at 2000,
  and keeping the "typing" dot alive with `sendChatAction`.
- `tests/python/test_zalo_bot.py`: whitelist, splitting at 2000, deduplication, the pairing
  waiting queue, webhook secret comparison.
- `docs/26-zalo-bot.md`: the user doc, kept entirely separate from `docs/12-zalo.md` so that
  nobody confuses the two.

**Files to edit**

- `server/main.py`: the `_ZALO_BOT` variable, start and stop following settings, the endpoints
  `/zalo-bot/status`, `/zalo-bot/restart`, `/zalo-bot/test`, `/zalo-bot/pending`,
  `/zalo-bot/allow`. It calls `_tg_answer(..., channel="zalo")` with the session key
  `zalo:<chat_id>` (Zalo ids are hex and Telegram ids are numbers, but the prefix is still needed so that
  accidental collisions cannot mix the two conversation threads together).
- `server/config.py`: add the default block `"zalo_bot": {"enabled": False, "token": "",
  "chat_id": "", "mode": "poll", "webhook_secret": ""}`, and add `zalo_bot.token` and
  `zalo_bot.webhook_secret` to the list of encrypted keys (around line 381).
- `server/channel_context.py`: `build_channel_block` accepts `source="zalo"`, and adds "Zalo
  Bot" to the platform list. Add a tone reminder like the Telegram one (no markdown tables,
  short message-style writing).
- `server/main.py`, notification part: `_notify_owner` and `_tg_send_to` currently only know the `web:`
  prefix and otherwise fall back to Telegram. Add a `zalo:<chat_id>` branch. Work assigned from Zalo
  must report its result back to Zalo, per the default reporting rule in `CLAUDE.md`.
- `server/reminders.py`: the `can_force` gate currently treats "Telegram not connected" as having no reporting
  channel. An enabled Zalo Bot must also count as a channel, or it will block wrongly.
- `server/chatbot_store.py`: `channel` becomes a real field, accepting `"telegram"` or
  `"zalo"`. `token_owner` (which blocks two pollers on the same token) must be checked per channel.
- `server/chatbot_runtime.py`: `start_bot` picks the transport class by `channel`.
- `dashboard/console.js`: a Zalo Bot card on the Channels page, next to the Telegram card, plus the pairing
  waiting queue card.
- `server/web_security.py`: exempt `POST /hook/zalo-bot` from CSRF (Phase 6) but still rate
  limit it.

## 7. Phases

### Phase 0: Probe the real API

**One question has been answered without a token** (2026-08-08): calling `getMe` with a junk token
makes Zalo return `{"ok":false,"description":"Unauthorized","error_code":401}` with **HTTP 200**,
not HTTP 401 like Telegram. That means **you must read the `ok` field and never look at the HTTP
code**. The current code already does this.

The other five questions still need a real bot token:

1. Does `getUpdates` return old messages again after they have been received? How much duplication?
2. Does `sendPhoto` accept `multipart/form-data`, or does it require a public URL?
3. What fields does the real payload of `message.image.received` and `message.voice.received` have,
   and how long does the image URL stay alive?
4. What is the real rate limit before getting a 429?
5. Can the bot message a `chat_id` that has never messaged it?
6. How does `parse_mode: markdown` look on a real phone?

Question 2 decides whether Phase 3 exists at all, and question 5 decides whether reminders over Zalo are
usable. Do not guess, because guessing wrong here means redesigning from scratch.

### Phase 1: Transport layer and the owner's channel

`server/zalo_bot.py` plus configuration, endpoints, a dashboard card, and pairing by code.
At the end of this phase the owner messages the Zalo bot and Jarvis 007 answers with the right brain, the right
engine and the right MCPs as on Telegram.

### Phase 2: Quick commands and the downgraded interactions

The command set for Zalo: `/help`, `/status`, `/stop`, `/reset`, `/retry`, `/model`, `/brain`,
`/notes`, `/skills`. `/model` and `/brain` draw a numbered list in place of the button grid, reading
the number on the next turn. The `JAVIS_ASK` block reuses the existing downgrade path.

The Telegram part of this **was done first, in v0.26.4** because it is independent of Zalo: the status
message is sent silently, not deleted, and settled into a tool trace line. The function that builds the trace line
(`TelegramBot._dong_vet`) and the expression that extracts the tool name (`RE_TEN_TOOL`) should therefore be **pulled out and
shared** when writing `zalo_bot.py`; do not copy them. Details in section 3.1.

### Phase 3: Two-way media (depends on Phase 0)

Inbound: download images and voice to `inbox/zalo/` of the brain selected for the session, following the
30-day cache cleanup rule and the 300MB cap of `media_gc.py`.

Outbound: if multipart works, do it like Telegram's `send_file`. If it only accepts a URL
there must be a public, signed, short-lived media endpoint, and it is **only available when Jarvis 007
runs on a machine with a public domain name**. The local build must say plainly "cannot send
images over Zalo from this machine yet" and must not report a false success. With no `sendDocument`,
PDFs and spreadsheets cannot be sent; state this in the docs.

### Phase 4: Background notification routing

The `zalo:` prefix for `owner_chat`. Loops, Kanban jobs and reminders created from Zalo report their
result back to Zalo. Fix the `can_force` gate in `reminders.py`. If Phase 0 shows the bot cannot
message first, then a reminder that fires for a recipient who never messaged the bot will fail; that
error must be caught and surfaced, not swallowed.

### Phase 5: Dedicated bot on Zalo

`channel` becomes a real field and `chatbot_runtime` picks the transport class by it. Hide the group
configuration when `getMe` reports `can_join_groups: false`. This is the part that delivers real business
value, and after Phase 1 it is almost only wiring.

### Phase 6: Webhook mode (VPS only)

`POST /hook/zalo-bot`, check `X-Bot-Api-Secret-Token` with a constant-time comparison,
exempt from CSRF but rate limited. The two modes are mutually exclusive, so when switching
`deleteWebhook` must be called first.

One thing to be careful about: the old Zalo version **once had** `/hook/zalo` and it was removed entirely along with the
listener (see the section "Different from the old Zalo integration" in `docs/12-zalo.md`). The new path must differ
in name and in nature, so that a later reader of the code does not think the listener is back.

### Phase 7: Docs and testing

`docs/26-zalo-bot.md` for users, stating clearly when to use Zalo Bot and when to use Zalo
Agent MCP. Update `docs/12-zalo.md` to point to it. The test suite as listed in section 6.

## 8. Risks and open questions

- **The rate limit is not published.** The Pricing and FAQ pages are returning 500. Back off
  over time on a 429 and **expose the rate limit error in the status line**, do not swallow it. A paid plan
  appearing later may change the rules.
- **The bot most likely cannot message first.** If so, every background notification only
  reaches people who have messaged the bot before. This must be said in the UI.
- **The BASIC plan cannot join groups**, which blocks part of the dedicated bot scenario.
- **Sent messages cannot be edited or deleted.** The status UX is very different from Telegram; write it into the
  docs so it is not read as a bug.
- **The platform is young.** `event_name` and field names may change. Keep the payload extraction compact
  in one function so only one place needs fixing.
- **Deduplication is where it bleeds most easily**, because there is no `update_id`. Tests must cover it.

## 9. Estimate and suggested order

Phase 0 half a day. Phases 1 and 2 about two to three days. Phase 3 one day. Phase 4 half a
day. Phase 5 one to two days. Phase 6 half a day. Phase 7 half a day. Total about one week
of focused work.

Suggested order: ship **Phases 0 to 2 first** as a usable build (the owner asks Jarvis 007 through
Zalo), then **Phase 4** (background notifications to the right Zalo), then **Phase 5** (the dedicated bot,
the part that unlocks business value). Phases 3 and 6 depend on the probe results and on where
Jarvis 007 is running, so they come later.

## 10. Sources

- [Zalo Bot documentation](https://bot.zaloplatforms.com/docs/), read 2026-08-08
- [Create a bot](https://bot.zaloplatforms.com/docs/create-bot/),
  [Authorization](https://bot.zaloplatforms.com/docs/authorize/),
  [Calling the API](https://bot.zaloplatforms.com/docs/call-api/),
  [Webhook](https://bot.zaloplatforms.com/docs/webhook/),
  [Error code table](https://bot.zaloplatforms.com/docs/error-code/)
- [OpenClaw's Zalo channel](https://docs.openclaw.ai/channels/zalo) - a real implementation to compare
  against; they default to long polling, split messages at 2000, with a 5MB media cap
- In the repo: [Telegram channel](../11-telegram.md), [Zalo Agent MCP](../12-zalo.md),
  [Jarvis 007 CLI spec](2026-08-cli-spec.md), [Dedicated bot spec](2026-08-bot-chuyen-trach-spec.md)
