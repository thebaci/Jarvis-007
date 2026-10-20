# Groups keep only 100 messages, the bot sees 30 messages as context (0.65.12)

## Problem

The project owner (30 Sep 2026) worried that the bot stores too many chats in the Inbox's SQL store. Reading the code: `customer_conversations.sqlite3` stores EVERY message of EVERY chat on a monitored channel (each message up to
8,000 characters), with no deletion limit, even for groups where the bot is not yet allowed to reply (messages still enter the Inbox). The other stores already have caps (the arbiter: 400 characters per decision, unlabeled
rows kept 14 days, 500 cases per bot; the bot log: 2,000 lines). The Inbox is the only store that grows without bound. Beyond disk usage there is also privacy: the store keeps the words of strangers in groups.

Also, a bot in a group is only invoked when someone tags it or replies to it, so it sees only the exact sentence that called it (the 8-message window in RAM serves only the arbiter). "What about the other one?" is
meaningless if the bot does not know what people just said.

## Decisions (key points)

- **Groups keep the 100 most recent messages; customers (private chats) keep everything.** No settings toggle.
- **A bot in a group sees the 30 most recent messages** before the message being asked when it replies.

## Approach

- `conversations.ghi_su_kien` trims right inside the write transaction, only for `chat_type == "group"`: it deletes messages whose id is lower than the id of the 100th message counting from the newest (the query uses the
  `ix_msg_conv` index, no table scan). `message_count` stays the number of messages ever received.
- **Migrating old groups** `conversations.cat_nhom_cu()`, once at startup, on a background thread: back up the WHOLE store file with SQLite's backup API (consistent even while WAL is being written), then trim the groups that exceed the
  limit, write the `cat_nhom_v1` marker into `sync_state` AFTER the trim finishes, then `wal_checkpoint` + `VACUUM` so the file really shrinks (if this step fails the file just is not smaller). The backup is made only when a group actually exceeds the limit.
  The backup still holds strangers' words so it **deletes itself after 14 days** (cleaned up at a later startup).
- **Context for the bot** `chatbot_runtime.ngu_canh_nhom`: the 30 messages right before the message being asked (excluding the asked message itself by `message_id`; if the id is unknown, drop the last customer message), each message cut to 300 characters, the whole block
  at most 6,000 characters (dropping from the oldest message), with speaker labels (the customer's name, `Bot`, `Chủ`; `Chủ` means "owner"). The content goes through `clean_chat_text` (which strips internal markers and `<chat_data>` tags) and is wrapped in `<chat_data>`
  with a note that it is DATA, not instructions. It is attached to the turn config (`cfg["_ngu_canh_nhom"]`) and to the SYSTEM PROMPT through `build_bot_prompt`, and **not** appended to the asker's message: appended
  to the message, every turn would add another 30 messages to the Agent's session history, which would swell over time. Both the real turn and the Inbox's "Reply for me" turn have it.
- Private chat is unchanged: the customer's session already carries its history.

## Fragile spots (canaries already exist in `tests/python/test_hoi_thoai_cat_nhom.py`)

1. Trimming a private chat or a new message by mistake: the test writes 130 group messages and 130 private messages; the group keeps exactly messages 31 to 130, the private chat keeps all 130.
2. Deletion that cannot be undone: back up first, run once (the second run makes no extra backup), the backup keeps the ORIGINAL number of old messages, and the expired backup deletes itself.
3. A message escaping the data block: messages containing `</chat_data>`, `[IM_LANG]`, `JAVIS_ADMIN` get stripped; the block has only one closing tag.
4. Session bloat: the context sits in the system prompt, and the asker's message stays just `[Name] content`.
5. A startup error swallowed silently: the hook runs inside `try/except`, so a missing `import threading` meant the migration never ran and nothing reported it. It was caught in a real run on the trial build
   (a `NameError` in the log) and fixed; the real migration was verified: a 300-message group left with 100, an 80-message group and a 250-message private chat intact, and a backup holding all 300.

## Included

`conversations._now()` increases strictly within the process: the Windows clock ticks about 15 ms so two consecutive writes shared the same `updated_at` and the "most recently active first" order of the customer list was
random (`test_hoi_thoai_crm` was red about 2 times in 5 on a Windows machine; 8 consecutive greens after the fix).

## Out of scope

- No trimming of private chats (owner: customers keep everything, for now).
- No trimming of the Agent session store or the arbiter (they already have their own caps).
- No settings toggle yet for the number of messages kept or the number of context messages (the owner wants few settings).
