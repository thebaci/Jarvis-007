# Channel registry, channel accounts and the merged Conversations page (0.61.0)

Technical document for people who edit the core. Users read `docs/28-hoi-thoai-khach.md` and `docs/25-chatbot.md`.

## Why

Before 0.61.0, "knowledge about a channel" was scattered across eight places (`chatbot_store`, `chatbot_runtime`, `conversations`, `GET /chatbots`, the `/conversations/channels` route, `icons.js`, `chatbots.js`, `conversations.js`). Adding Zalo OA or Facebook meant editing all eight, and personal Zalo was a "special case" in each one. A bot also mixed two things of different nature into one record: the ACCOUNT (token, identity on the platform) and the ASSIGNMENT (Agent, permission level). The project owner asked (2026-09-21) to merge Chatbot and Conversations into one tab, treat every channel the same, and structure the code so that adding a channel later does not touch the core.

## Three layers

1. **Channel registry** `server/channels/`: each channel is one module that declares `SPEC: KenhSpec` (id, label, logo, kind, capabilities, how to get a token, summary) and a set of functions following the contract (see the docstring of `channels/__init__.py`). The capabilities "reply from Jarvis 007" and "can attach a bot" are DERIVED from the module (it has a `gui` function, it has a `Transport`), not taken from what the module claims. The order of `_MODULES` is the order shown in the UI; no channel is "primary".
2. **Channel accounts** `server/channel_accounts.py`: a JSON store for accounts of kind `bot` (token via `secrets_store`). Accounts of kind `account` (personal Zalo) live in `mcp_store`, and the channel module lists them itself. The id of an account migrated from an old bot equals the bot id, so the `f"{kenh}:{id}"` key of the conversation store stays unchanged.
3. **Bot** `server/chatbot_store.py`: now only the ASSIGNMENT, pointing at accounts through `accounts: [id]`. `channel`/`bot_username` are a snapshot of the first account (kept for old readers). Migration runs inside `_load()` on the first read, writes back once, and needs no script.

## Watcher

`chatbot_runtime._RUNNING[bot_id] = {"pollers": {account_id: transport}, ...}`: one poller per account. The poller callback is wrapped by `_gan_tai_khoan` so that EVERY meta carries `account_id`; `_su_kien_bot` writes to the store by that account, and `che_do` (takeover) is also looked up by that account. `status(bot_id)` returns the WORST state as the overall state, together with `accounts: [...]` for each poller.

## API

- `GET /channels`, `GET /channels/accounts` (one shape: `id`, `account_key`, `kind`, `channel`, `logo`, `label`, `state`, `watch`, `bot_id`, `so_hoi_thoai`, `chua_doc`, `nang_luc`, `xoa_duoc`).
- `POST /channels/verify-token`, `POST /channels/accounts`, `.../{id}/update`, `.../{id}/watch` (kind account only; kind bot returns 400), `.../{id}/delete` (refused while a bot is still watching).
- `POST /conversations/{id}/reply`: sends through `channels.gui`, records a `human` message, and if the conversation has a bot in `ai` mode it switches to `human` (takeover) and returns `tiep_quan: true`. If sending fails it returns 400 and does NOT record anything.
- Aliases kept: `/chatbots/verify-token`, `/conversations/channels`, `/conversations/zalo/{id}/watch`.
- `GET /chatbots` adds `tai_khoan` (free accounts) and `kenh` from the registry; `POST /chatbots` and `/update` accept `account_ids` (a comma-separated list) and still accept `token` + `channel` (creates a new account, then attaches it).

## UI

- `conversations.js` is the page shell: three tabs `TABS = ["inbox", "kenh", "chatbot"]`. The Chatbot tab delegates to `JavisChatbots.render`. The page id `chatbots` is still in `RAIL_ITEMS` (icon, label, voice alias) but is listed in `RAIL_AN` (hidden from the rail); `navigateTo("chatbots")` calls `JavisConversations.chonTab("chatbot", true)` and then goes to `conversations`.
- Rule: the UI does NOT branch on channel id. The logo comes from `kenhCua(id).logo`, the label from `nhan`, the capabilities from `nang_luc`; all of it comes from the `channels` the server returns. The tests `test_trang_chatbot.js` and `test_hoi_thoai_khach.js` have a canary for this rule.
- Adding a channel: one file in `server/channels/`, one line in `_MODULES`, one logo in `icons.js` (`KENH`). Nothing else changes.

## Tests

`tests/python/test_kenh_tai_khoan.py` (registry, migration, multiple accounts, API, reply), `test_hoi_thoai_khach.py`, `test_chatbot_store.py`, `test_zalo_bot.py`; JS: `test_hoi_thoai_khach.js`, `test_trang_chatbot.js`.
