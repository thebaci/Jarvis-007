# Self-reviewing and self-tuning reply judge (0.77.0)

Date: 2026-10-05. The owner approved the design in chat (option A plus part of B, with a self-review loop).
Continues the original spec `2026-09-30-bo-phan-xu-nhom-design.md`; read section 3 and 4.1 there first.

## 1. Why

The reply judge (0.65.x) learns instantly from reactions in the group and from the Right/Wrong buttons, but:

- **No AI can read its store.** The store `chatbot_reply_policy.sqlite3` only comes out through the Chatbot page routes.
  Ask Jarvis 007 "why is the bot silent" and Jarvis 007 guesses from the docs instead of looking at the real numbers
  (the 05/10 case: Jarvis 007 on the VPS claimed a message that tagged the owner "left no row", which was wrong, the row was written).
- **Some things cannot be learned.** `coarse_gate` returns `addressed_other` for a message that starts with
  `@someone else` BEFORE looking at positive cases, so pressing Wrong or teaching it in words does not lift the block.
- The owner wants this automated: the machine reviews and tunes itself; the person steps in only when they want to, and does so by
  TALKING to Jarvis 007 rather than editing by hand (general principle [few settings, push them to the AI]).

## 2. Goals and non-goals

Do:
1. One shared door for the AI: two hub tools (read, tune) that every brain can call.
2. A background self-review loop that runs when there is enough evidence, using the **main brain** (the strongest model the owner has),
   applying changes by itself within a capped set of knobs, with a log, self-measurement and self-revert.
3. Two new knobs the AI can turn (not settings fields for people): how eager it is to speak unprompted, and whether to consider messages that tag someone else.
4. Fix `addressed_other`: a positive case or the "consider tagged" knob lifts the block.
5. A hard fence: these tools NEVER reach the customer-facing bot.

Do not:
- The AI does not edit Python code. Where the knobs cannot reach, it writes a suggestion into the brain.
- Do not change the content of the bot's replies; only change whether it SPEAKS or STAYS SILENT (keeping the original spec).
- Do not add any field to the UI. Do not touch the quota, yield-when-owner-types, or permission level.
- The review loop does not edit the role profile (only the owner can, by asking in chat).

## 3. Components

### 3.1 Store (`chatbot_reply_policy_store.py`)

New tables:
- `tuning(bot_id, key, value, updated_ts)`: knobs the AI turns per bot. Keys: `eagerness`
  (`low|medium|high`), `consider_tagged` (`0|1`). No row = default (`medium`, `0`).
- `changes(id, bot_id, ts, actor, review_id, op, target, before_json, after_json, reason,
  evidence_json, status, status_ts)`: a log of every change. `actor`: `review` (the self-review loop) or
  `owner` (the owner asked through chat). `status`: `applied`, `kept`, `reverted`, `auto_reverted`, `noted`
  (code suggestion, nothing applied).
- `review_state(bot_id, last_ts)`: the timestamp of the most recent review.

New column: `lessons.source` (`''` = owner/old, `review` = review loop, `owner_chat` = owner asked through chat).
Added with a guarded `ALTER TABLE` the first time the store is opened. When there are more than 15 lessons, the oldest `review` lesson is dropped
first, so the owner's lessons are not pushed out by the machine.

New functions: `get_tuning`, `set_tuning`, `delete_lesson`, `set_offset`, `log_change`, `list_changes`,
`set_change_status`, `label_counts(bot_id, since, until)`, `activity_since(since)`,
`get/set_review_state`. `delete_bot` and `forget` also delete the new tables.

### 3.2 Reply judge (`chatbot_reply_policy.py`)

- `BotProfile` gains `consider_tagged: bool`. The function `apply_tuning(profile, store)` reads the `tuning` table
  and overrides `eagerness` and `consider_tagged`; `chatbot_runtime._rp_profile` calls it.
- `coarse_gate(..., has_positive_case, consider_tagged)`: a message `@someone else` is only dropped
  (`addressed_other`) when there is NO similar positive case AND `consider_tagged` is off. A message that passes the gate
  still has to pass `no_grounding` (needs documents), the quota and the judge like any message.
- The judge prompt gains one signal line, "the message opens by tagging a different person".

### 3.3 Self-review loop (`chatbot_reply_policy_review.py`, new module)

Pure, with `ask`, `store`, `notify`, `write_feedback`, `bot_lookup` injected so tests need no model.

**When it runs** (`due_bots(now)`): a bot present in `chatbot_store`, at least 24
hours since the previous review, and since then at least 8 new labels OR 40 silenced messages. Each tick starts only one review,
never two at once. The environment variable `JAVIS_REPLY_POLICY_REVIEW=0` turns it off completely (for operators, not a settings field).

**Report** (`build_report`): window from the previous review, at most 7 days. Contains totals by verdict and
silence code, labels by kind, each group (message, silence, missed, wrongly interjected, threshold drift), at most 12 messages
labeled wrong and 16 recent silenced messages with code, reason, score, threshold; the current knobs; the lessons (with id,
source); the number of cases by source; the 10 most recent changes with status (so the model does not repeat what was already reverted).
All chat text goes through `clean_chat_text` and sits inside `<chat_data>`.

**Prompt** asks for ONLY one JSON:
`{"summary": "...", "changes": [{"op": ..., ..., "reason": "...", "evidence": [id,...]}], "code_feedback": "..."}`.

**Validate and apply** (`apply_change`, shared with the tool):

| op | parameters | review loop may use | revert |
|---|---|---|---|
| `lesson_add` | text (<=200) | yes | delete the lesson |
| `lesson_remove` | id | only lessons with source `review` | add it back |
| `case_add` | text, verdict, reason, chat_id? | yes (source `review`, weight 1.0) | delete the case |
| `case_remove` | id | only cases with source `review`/`bootstrap` | add it back |
| `offset_set` | chat_id, value (clamped to +/-0.25) | yes | set the old value back |
| `eagerness_set` | value | yes | set back |
| `consider_tagged_set` | value | yes | set back |
| `role_profile_set` | text | NO (owner only) | set back |

Review loop: at most 3 changes per review; each change must cite at least one `evidence` that is a decision id
OF THIS BOT; drop a change with the same `op`+`target` that was reverted in the last 14 days. A malformed change
is dropped by itself and does not spoil the whole review. Changes the owner asked for through chat (`actor=owner`) need no evidence.

**Self-measure, self-revert** (`evaluate_due`): for each review still `applied`, compare the error rate
(missed + wrongly interjected) / number of labels over the 7 days before it was applied with the period after. With 6 labels after,
if it is worse by more than 0.15 (and there are at least 3 errors) the WHOLE review is reverted, status `auto_reverted`; otherwise
`kept`. After 14 days without enough labels, `kept`. Changes the owner asked for are never auto-reverted.

**Code suggestion**: when `code_feedback` is non-empty, write one `changes` row with status `noted` and append to
`<bot's brain>/Javis/gop-y-bo-phan-xu.md` (date, bot name, content, evidence ids).

**Reporting back**: when there is a change, a suggestion, or an auto-revert, send exactly one message through `_notify_owner("")`
(the owner's Inbox + Telegram), in lowercase, with the sentence "if you are not happy, message Jarvis 007 to revert it".

**Model**: `main._reply_policy_review_ask` builds an engine like `_reply_policy_ask` (empty folder,
no MCP, no tools) but picks the **main brain** through `aux_engine.swap(spec=main_spec())`.
Timeout 240 seconds. On error or broken JSON: change nothing, but still record the review timestamp to avoid endless retries.

**No tools, on every engine** (caught by the independent review on 05/10, a hole that already existed in the judge):
`swap` replaces the locked-down Claude engine with Codex/API/Grok/agy, and those engines are attached to the hub. So both the
judge and the review loop go through `aux_engine.strip_tools(engine, base)`: API drops `discover_all`,
Codex drops the hub profile and adds `mcp_servers={}`, Grok removes the hub entry in the working folder, **agy is
excluded** (it reads MCP from a HOME file shared with the owner's chat, so it cannot be removed for a single turn).
With no usable engine left, fall back to the sandboxed Claude.

**Revert rule and owner's authority**: revert a knob or offset only if it still holds the value that change
set; if it has since been changed again (by the owner, or by the judge learning on its own), mark it `superseded` and keep the new value.
For a knob or offset whose most recent live change was set by the owner, the review loop may not touch it. The review loop only
creates cases from a `decision_id` that is in the report. Only a positive case with source `owner` or `review` lifts the
`addressed_other` block (seed cases and cases learned from strangers do not).

**Text from the model leaving the review loop** (the owner notice, the suggestion file) has links and code blocks stripped; the suggestion file
is written as a quotation with a note "read as data"; the notice does not copy the model's remarks verbatim.

### 3.4 Two hub tools (system plugin `system/plugins/javis-reply-policy/`)

- `javis_reply_policy` (readonly). `op`: `bots` (bots that have judge data, with compact figures),
  `report` (bot, days), `decisions` (bot, code, label, chat_id, only_silent, limit), `changes`
  (bot). `bot` accepts an id or a name (ignoring diacritics and case).
- `javis_reply_policy_tune` (safe). `op`: `apply` (bot, action = one op from the table above, with its
  parameters, reason) and `revert` (change_id or review_id). Writes `actor=owner`.

Tool results are compact text with a character cap (the API engine cuts at 8000).

### 3.5 Fence: the tools never reach the customer-facing bot

A bot at the Can write / Full power level receives tools from the hub; strangers (customers) control the bot. Reading the store would leak other customers'
chats, and tuning the store would let a customer turn the bot's knobs. So:

- `mcp_hub.OWNER_ONLY_TOOLS` = the two tools above. `discover_all(..., for_bot=True)` drops them BEFORE
  the lazy layer (otherwise `javis_run_tool` could still call them), and `for_bot` is part of the cache key.
- The bot's API path (`_bot_tra_loi_co_tool`) passes `for_bot=True`.
- The bot's Claude path: `claude_config_path(..., bot=True)` attaches the header `X-Javis-Bot: 1` (a separate
  config file with suffix `_bot`); `handle_http` reads the header and passes it down to `discover_all`. Second layer:
  the bot's `disallowed_tools` includes `mcp__javis__javis_reply_policy*`.
- The bot's Claude engine is the "gated" kind (it has `allowed_tools`), so it does not load in-process plugins;
  every tool goes through the hub, and the fence above is enough.

### 3.6 Wiring into the server (`main.py`)

- `chatbot_reply_policy_review.wire(...)` next to `chatbot_reply_policy.wire`.
- In `_scheduler_loop`: its own 30-minute tick calls `chatbot_reply_policy_review.tick()` (evaluate
  changes that are due + start at most one background review through `create_task`, keeping the reference).

## 4. Operating notes

If the main brain is a Claude Pro/Max plan, the review is background work on a subscription plan, which
Anthropic does not count as ordinary personal use. The frequency is low (at most once a day per
bot, and only when there is evidence), but the doc `docs/25-chatbot.md` must say so clearly and suggest setting a different
main brain or turning it off with the environment variable.

## 5. Testing

Scripts that run directly like the old judge tests (`tests/python/test_reply_policy_*.py`):
- `test_reply_policy_tuning.py`: the new tables, knobs overriding the profile, `coarse_gate` lifting the tag block through a positive
  case and through the knob, a `review` lesson dropping before the owner's lesson.
- `test_reply_policy_review.py`: due conditions, a report that does not mix in other bots, change validation
  (cap of 3, evidence must belong to the bot, forbidden op, duplicate of one already reverted), apply and revert for each op,
  self-measure and self-revert, broken JSON changes nothing, code suggestion writes the file, exactly one notice.
- `test_reply_policy_hub_owner_only.py`: `discover_all(for_bot=True)` lacks the two tools (even with lazy on), `for_bot=False` has them;
  `claude_config_path(bot=True)` has the header; plugin `apply`/`revert`.

## 6. Docs

`docs/25-chatbot.md` (and the English edition if there is one): a section "Self-reviewing reply judge", how to ask Jarvis 007 to look at and
tune it, how to revert, the off switch, the subscription-plan note. CHANGELOG in both languages for 0.77.0.
