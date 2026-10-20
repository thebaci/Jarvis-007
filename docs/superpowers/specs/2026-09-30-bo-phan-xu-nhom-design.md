# Group conversation arbiter (0.65.0)

Date 2026-09-30. Status: a spec to build in ONE go, one PR (#502), several commits by milestone.

## 1. Problem

A dedicated bot standing in a chat group (personal Zalo, Telegram) has to decide three things by itself: is anyone
talking to me, should I chime in, and if I speak, what do I say. Version 0.64.82 solved this with a chain of hard
rules written for a single case:

- `zalo_personal_channel.nhan_dien_goi` only catches "@name". A plain name call ("javis vũ ơi", Vietnamese for "hey javis Vũ") is not counted
  as calling the bot.
- `chatbot_tu_dong.nhin_nhu_cau_hoi` is a keyword gate (question mark, "sao" (why/how), "giúp" (help)...). Messages that do not match are
  dropped, and deliberately NOT logged, so errors leave no trace.
- It looks at exactly ONE message. When people follow up with "vậy còn cái kia?" ("what about the other one, then?") right after the bot answers, the bot
  treats it as a stranger's message.

The project owner (2026-09-30): wants a context-based mechanism, not tied to one bot, so that several different bots
gradually learn by themselves how to answer in groups; learn LIVE rather than weekly; drop the approval step because the bot uses
a personal account so speaking wrongly is cheap.

And the most important point, which the owner made clear after the first version of this spec: the owner runs MANY bots in unrelated fields and groups
(for example Jarvis 007 Vũ supports Jarvis 007, while Nhi Mai and Ngọc Thu each have a different industry). Each bot's way of
answering must come from its own Agent. The design must not borrow the voice, cases or examples
of one bot for another, and must not lean toward Jarvis 007 Vũ's case.

## 2. Goals and non-goals

Goals:
1. Recognize being called by a plain name, understand follow-up messages after the bot's turn.
2. Every decision, silence included, leaves a readable trace.
3. One engine shared by every bot and every channel; what is specific to each bot lives in data
   (profile, rule cards, learned cases), not in code.
4. Learn instantly from real people's reactions; a case just labeled affects the very next decision.
5. A new bot has reasonable behavior from day one FOR ITS OWN FIELD (inferred from the bot's own Agent and documents),
   without borrowing another bot's voice or cases.

Non-goals: changing the CONTENT of what the bot says (it still sticks to the documents and the Agent's role); training or fine-tuning
a model; cross-user learning; changing how the bot handles private chat; sharing cases, voice or rules between bots.

## 3. Principles

1. **Separate "being called" from "should chime in".** The first is recognition, a hard and generous rule. The second is
   judgment, which is where learning happens. Mixing the two lets the bot wrongly learn that "staying silent when called by name is fine".
2. **Learning only changes SPEAK or STAY SILENT.** It never changes what the bot asserts. That way dropping approval still
   does not make the bot invent more.
3. **Hard guards sit outside the learning loop** and are the limit on everything that can be learned.
4. **Err toward silence.** Errors, timeouts, broken JSON, ambiguous signals: silent. The only exception is a message that surely
   calls the bot by name, which always gets answered like a private chat.
5. **A single case is light, the owner's teaching is heavy.** Only the owner can create rules. Other people in the group are an untrusted
   source: their words are only a weak signal.
6. **Three layers, learning writes only to its own layer.** The shared layer holds only the group-conversation MECHANISM, no topic,
   voice or form of address. The bot layer comes from the bot's own Agent. The chat layer is each group's own culture. What is learned is written
   only to the bot layer or the chat layer, never upward into the shared layer,
   and one bot cannot read anything of another bot (see 4.1).
7. **The arbiter does not write the answer.** It only decides speak or stay silent. The sentence spoken is still run by the bot's engine
   with the bot's Agent prompt, so the voice and way of answering are always the Agent's.
8. **Extend by data and plug-ins, not by if branches.** Adding a signal, a channel or a language
   is adding one function or one line of data.
9. **Customer chat data is sensitive data.** Learning is switched on per bot, DEFAULT OFF; data
   is kept out of git, has a retention limit, is deleted per bot, and has a forget button.

## 4. Architecture

```
group message -> [normalized Event] -> R hard guards -> G recognize being called -> T signals
                                                        |                  |
                                            certain --->|                  v
                                       (reply at once)  |          C coarse gate (junk/no signal -> silent + trace)
                                                        |                  |
                                                        +----------> J arbiter (background-job model)
                                                                     ^   |   receives: guidelines + similar cases + last 8 messages
                                                       similar cases +   v   returns: reply|silent + score + reason
                                                       K case store      D compare score with threshold(bot, chat)
                                                                     ^   |
                                                    label, lesson ---+   v
                                                       O outcome tracker  <- every later message in the chat
```

Three separate data blocks, changing one does not touch the others:

- **Event:** a normalized mold, independent of the channel. The Zalo and Telegram adapters
  build it themselves.
- **Profile:** per bot. Aliases, rule cards, eagerness, the people who teach the bot.
- **Store:** learned cases, the decision log, per-chat thresholds.

### 4.1 Three layers: what comes from where

| Layer | Contains | From where | Who can change it |
|---|---|---|---|
| Shared | mechanism: recognizing name calls, follow-up messages, scoring method, base threshold, reaction keywords, mechanism templates | code and data in the repo, NO topic at all | only an update |
| Bot | the scope it does and does not handle, voice, form of address, language, when to speak up | compiled from the Agent file and the brain's document index of the bot ITSELF (5.10) | the owner by hand; re-composed automatically when the Agent changes |
| Chat | offset threshold, learned cases, lessons | reactions inside that very group | learned automatically; the owner can delete |

An example with three bots: Jarvis 007 Vũ takes questions about Jarvis 007, Nhi Mai and Ngọc Thu each take their own field. All three use the SAME engine, but the
role profile, bootstrap cases, learned cases, threshold and lessons are all separated
by `bot_id` (and by chat). Nhi Mai's arbiter never sees the cases, examples or
voice of Jarvis 007 Vũ. Whatever is learned in a group stays in that group.

New code lives in `server/chatbot_reply_policy.py` (the engine, pure and testable) and
`server/chatbot_reply_policy_store.py` (SQLite). No more stuffing into `chatbot_runtime.py`.

### 4.2 The normalized Event

```
Event: channel, bot_id, chat_id, chat_type, msg_id, ts, text, sender_id, sender_name,
       sender_role ("owner" | "known" | "new"), mentioned (bool), reply_to_bot (bool),
       window (at most the last 8 messages: ts, sender_id, name, is_bot, text),
       bot_last_spoke_ts (ts or None), owner_typing (bool)
```

`window` comes from the Inbox (`conversations.tin_nhan`) of that very chat; if none yet it is empty and the engine
still runs. Each message's content is cut to 400 characters, with internal markers stripped (`[IM_LANG]`, `JAVIS_`).

### 4.3 Naming convention

New identifiers (module names, functions, variables, data fields, SQL columns, API routes, enum values, data file
names) are written in ENGLISH, at the owner's request on 2026-09-30. Strings displayed to users, comments and
docs remain Vietnamese with diacritics. Old names that this PR only calls (such as `chatbot_tu_dong`, `_ly_do_im`,
`zalo_personal_channel.nhan_dien_goi`) stay as they are: renaming in bulk drags in stored data, API routes
that the UI calls, and hundreds of tests, so it is a separate PR, not mixed in here.

| Concept | Identifier |
|---|---|
| arbiter, role profile, case store | `judge`, `role_profile`, `cases` |
| threshold, threshold offset | `threshold`, `offset` |
| calling level: certain, possible, none | `certain`, `possible`, `none` |
| decision: speak, silent | `reply`, `silent` |
| label: correct, wrongly silent, wrongly intruded, taught | `correct`, `missed`, `intruded`, `taught` |
| mode: off, trial run, on | `off`, `shadow`, `on` |
| eagerness: low, medium, high | `low`, `medium`, `high` |
| speaker: owner, known, new | `owner`, `known`, `new` |
| case source: automatic, owner, bootstrap | `auto`, `owner`, `bootstrap` |
| people who teach the bot, aliases, lessons | `trainer_ids`, `aliases`, `lessons` |

## 5. The layers

### 5.1 R: hard guards (kept as is, not learnable)

> Discovered while building: the 20-second pause between two bot self-speaks also blocks the FOLLOW-UP message of the person the bot just answered,
> breaking exactly the "understand follow-up messages" feature. So follow-up messages get a relaxed pause and per-person cap; the per-group
> hourly cap still applies (`chatbot_tu_dong.duoc_tra_loi(..., follow_up=True)`).

A group that is not yet allowed stays silent (`_nhom_duoc_phep`); a person not yet chosen stays silent; a chat already Taken
over; the owner just typed by hand (`chu_vua_nhan_tay`); a message older than `TUOI_TOI_DA`; a message sent by the account itself;
the cap on self-speaking count (`chatbot_tu_dong.duoc_tra_loi`); no outside actions performed by the arbiter.
The guards run BEFORE anything that costs a model call and stay where they are now in `chatbot_runtime`.

### 5.2 G: recognizing being called

Returns `address_level` ∈ `certain` | `possible` | `none` together with the evidence. Normalization: strip diacritics, lowercase, collapse
whitespace (using `chatbot_grounding._bo_dau`), match on word boundaries. The Vietnamese words below are kept as is because the matching is done on Vietnamese text.

| Level | Condition |
|---|---|
| `certain` | `@name`; `mentions` contains the account id; a reply to a bot message; the alias at the START of the sentence (after opening words such as "ê", "này", "alo", "hi", "chào", i.e. "hey", "listen", "hello", "hi", "greetings"); the alias directly followed by a calling particle ("ơi", "à", "ạ", "này", "nè", "nha", "ê", Vietnamese vocative particles roughly meaning "hey"/"please") |
| `possible` | the alias in the middle or at the end of the sentence with no particle ("hỏi javis vũ xem", "go ask javis Vũ and see"); a follow-up message (5.3) |
| `none` | everything else |

Aliases (`aliases`) consist of: the connection label, the account's learned display name, and the list of names the owner
adds by hand. It does NOT automatically take the Agent name or bot name ("@Lan" in a group is usually a member named Lan). A
self-inferred name must be at least 4 characters long after normalization; names the owner adds are exempt from this rule.

Examples that must come out right (also run in the no-diacritics form): "javis vũ ơi" certain; "Jarvis 007 Vũ giúp anh cái này" ("Jarvis 007 Vũ, help me with this") certain;
"alo javis vu" certain; "hỏi javis vũ xem" possible; "mai họp mấy giờ" ("what time is the meeting tomorrow") none; "@Lan xem giúp" ("@Lan please take a look") none.

`certain` gets answered at once like a private chat, does NOT go through the arbiter, does NOT need documents, and does not count against the
self-speak cap.

Recognizing a plain name call is a BUG FIX so it applies to EVERY bot, even when the arbiter has `mode = off`, but it only uses self-inferred
names (the connection label, the account's display name) and names the owner declared. The `mentioned` flag is set at the transport layer (personal Zalo)
and at each point of use (the gate, `_answer`), because `_gan_tai_khoan` wraps `meta` into a separate copy per callback so
marking in one place does not carry over to another.

### 5.3 T: signals (a registry, pluggable)

Each signal is a pure function `(Event, BotProfile) -> {value, evidence}` registered with a decorator.
Adding a signal = adding one function and one test; the frame is not touched.

- `question_score`: a 0..1 score from the question mark, keywords (a data table, replacing `_HOI`), the "có ... không" ("is there ... or not") structure.
  From now on it is a SIGNAL, no longer a blocking gate.
- `follow_up`: the bot spoke in the group within the last 180 seconds and this message is from exactly the person the bot just answered, or
  a reply into that thread.
- `doc_match`: a matching part of the documents exists (`chatbot_grounding.thu_thap`), with a score. Computed only for
  candidates, no disk scan for every message.
- `sender_role`: owner / known (already has a conversation with the bot) / new.
- `chat_pace`: message density over the last 2 minutes (when the group is lively the bot chimes in less).
- `alias_mid_sentence`: the alias appears but is not enough for `certain`.

### 5.4 C: coarse gate

It only throws away what obviously is not a candidate: empty, not text, only a link, one or two words that are not a call,
a message that opens by tagging someone else when `address_level = none`. The remaining messages are **candidates** when at least one
of these holds: `address_level = possible`, `follow_up`, `question_score >= 0.5`, or the store has a similar positive case (5.7). A non-candidate
stays silent AND leaves a `no_signal` trace.

The full set of silence codes (each code has a readable label in the UI): `junk`, `addressed_other`, `no_signal`, `no_grounding`,
`rate_limited`, `rate_limited_user`, `just_spoke`, `owner_typing`, `policy_error`, `judge_silent`, `below_threshold`, and
two codes that a LATER step decides to retract: `taken_over` (the owner has Taken over) and `agent_silent` (the Agent chose silence).

Keep the existing rule for self-speech: when `address_level = none` and not `follow_up`, the bot only opens its mouth if it has
grounds. The `grounding` config: `docs` (default, must have `doc_match`) or `role` (the bot takes its expertise
from the Agent's role, for advisory bots that do not rely on documents). Learned cases are NOT exempt from this
rule.

### 5.5 J: the arbiter

One cheap model call, run by the "background job" engine (`aux_engine`, which the owner chose on the Models page), mode
`suggest`, no tools. The input is text consisting of:

1. The role profile of the bot ITSELF (5.10): the scope it does and does not handle, the voice to understand the role, when
   it should speak up, plus the lessons.
2. Up to 5 most similar cases OF THIS BOT with the "correct decision" (5.7). Never take cases from another bot.
3. The window of the 8 latest messages, the speakers, what the bot said.
4. The computed signals and the matching document excerpt (shortened).
5. The message to decide.

The prompt contains no name, example or voice of any other bot. All chat content is wrapped in a `<chat_data>` block and the prompt states clearly that it is data, not
instructions. The output must be one JSON: `{"verdict":"reply"|"silent","score":0..1,"reason":"<= 120 characters"}`.
At most 3 arbiter calls run concurrently (a semaphore per event loop). A wrong format, a 25-second timeout (a subscription-plan engine takes a few seconds just to start, 8 seconds is too tight), or an engine error: treated as
`silent` with reason `policy_error`. The engine runs in an EMPTY directory, with no MCP, no write or run-command tools
(chat content is untrusted data).

Modes: `off` (run the old rules), `shadow` (the arbiter runs in parallel, only records, the old rules decide), `on`
(the arbiter decides). Existing bots stay `off` until the owner turns it on.

### 5.6 D: threshold

`threshold = base_threshold(eagerness) + offset(bot, chat)`. `base_threshold`: `low` (few words) 0.75, `medium` 0.60, `high` (many words) 0.45.
The bot speaks when `verdict = reply` and `score >= threshold`. `offset` ∈ [-0.25, +0.25], `threshold` is clamped to [0.30, 0.90].
Update: wrongly silent subtracts 0.05, wrongly intruded adds 0.08 (intruding costs more than silence), multiplied by the label weight. With no
labels `offset` decays toward 0 with a half-life of 14 days. The threshold is PER chat: a customer group
likes the bot to speak a lot, an internal group does not.

### 5.7 K: the case store

Every candidate decision writes a row; when it gets a label it becomes a **case**. Lookup needs no embedding
library: only among the cases of THIS bot itself, similarity = 0.6 × Jaccard(normalized tokens) + 0.25 × feature match (`address_level`, `follow_up`,
`sender_role`) + 0.15 if the same chat, multiplied by age fading (30-day half-life) and the case weight.
Take at most 5 cases with score ≥ 0.25. A case's "correct decision": `correct` keeps the decision made,
`missed` gives `reply`, `intruded` gives `silent`, `taught` follows the teaching. The interface `tim_ca(event,
k)` lets an embedding replace it later without changing the frame.

**Bootstrap for a new bot, two layers and neither carries another bot's topic:**

1. *Mechanism templates* (shared): `system/reply_policy/mechanics_vi.json`, about 20 ABSTRACT cases describing only the group-conversation
   mechanism, written with the placeholders `{bot_name}` and `{topic}` instead of a specific name or industry. Examples:
   "{ten_bot} ơi" ("hey {ten_bot}") then answer; two people talking to each other then stay silent; a message tagging someone else then stay silent;
   "vậy còn cái kia?" ("what about the other one, then?") right after the bot answered then answer; a thank-you not aimed at the bot then stay silent;
   a question outside {chu_de} ("{topic}") then stay silent. When used, `{bot_name}` is replaced by the bot's own alias and `{topic}`
   by the scope in the bot's role profile. A test forbids industry names or product names in this file.
2. *Role-based bootstrap cases* (per bot): at first switch-on and every time the role profile changes, one model call
   reads the Agent and the document index of the bot itself and writes about 12 sample messages for EXACTLY THAT FIELD: 5 messages it should
   answer, 5 it should stay silent on, 2 borderline, each with a reason. They are stored as cases with `source = bootstrap`, low weight. The owner can view
   and delete them. Every real case of the same kind lowers the weight of the bootstrap case similar to it, so once the bot has learned enough from
   real groups the fake cases fade and disappear.

This way the second and third bots start out smart for THEIR OWN industry without copying behavior from any bot.

Cap: 500 cases per bot, 200 per chat; beyond that, drop the case with the lowest weight × recency, and a case already merged
into a rule card is deleted from the store.

### 5.8 O: tracking consequences and labeling

Every candidate decision opens a tracking window of 10 minutes or 8 messages, whichever comes first. Each new message
of the chat runs through `assign_label(watch, new_message)`, a pure function. Only STRONG signals assign a label;
**no reaction means no label** (being ignored is normal, and silence by nature has no reaction to measure;
using it as a label would teach the bot to speak more).

| Decision | Signal | Label | Weight |
|---|---|---|---|
| silent | the same asker asks again ("sao không trả lời" = why no answer, "bot ơi" = hey bot, "ai biết không" = does anyone know) or resends something ≥ 0.6 similar | `missed` | 1.0 |
| silent | someone surely calls the bot by name right after, same topic | `missed` | 0.8 |
| silent | the owner gives a substantive answer to that very asker | `missed` | 0.5 (the owner may just have done it in passing) |
| reply (not called) | the owner says "đừng chen vào" (don't butt in), "ai hỏi bot" (nobody asked the bot), "im đi" (shut up) | `intruded` | 1.0 |
| reply (not called) | someone else says something similar | `intruded` | 0.5 |
| reply (not called) | the owner clicks Take over on the chat within 10 minutes | `intruded` | 0.7 |
| reply | thanks, "ok", "được rồi" (alright) | `correct` | 0.6 |
| reply | a follow-up question on the same thread (`follow_up`, reply to the bot) | `correct` | 0.8 |
| any | the owner clicks 👍 or 👎 in the Log | per the button | 1.5 |

The signal keyword table lives in `system/reply_policy/keywords_vi.json` (diacritics stripped); adding a language is adding a file.
Label spam protection: each person at most 3 labels per hour per bot, each bot at most 50 new cases per day.

### 5.8b Independent review (2026-09-30): fixes applied

An independent review pass found nine real bugs, all fixed and covered by tests: (1) the arbiter engine must run with `allowed_tools` set to a
value (leaving it empty means `bypassPermissions` and loads the machine's settings), plus a list of forbidden tools; (2) a teaching does not label
the teaching message itself; (3) a name call right afterward only counts as "wrongly silent" when it is on the same topic; (4) the text of learned cases sits in `<chat_data>`
and the tag filter catches variants; (5) the owner's label overwrites instead of accumulating (`cases.decision_id`); (6) a `reply` decision
blocked at a later step is retracted (`amend_decision`), and Take over is checked BEFORE the model call; (7) opening words "này/ê" are only considered
on the diacritics-KEPT version so "hôm nay Nhi Mai..." ("today Nhi Mai...") is no longer a call; (8) Forget everything also deletes the decision log, and the UI tells the truth
that Trial run/On mode records chat text for 14 days even when auto-learning is not on; (9) concurrency limits, and no disk scanning on the
event loop.

### 5.9 The owner's teaching

A message from someone in `trainer_ids` that calls the bot (`address_level >= possible`) runs one more cheap classification call: "does this
message the owner teaching the bot how to behave?" → `{"is_teaching":bool,"rule":"...","kind":"should_speak"|"should_stay_silent"|"alias"}`.
If yes: create a `taught` case with weight 2.0 (effective right at the next decision), add a line to the
Lessons section of the rule card, and if `kind = alias` add that phrase to `aliases`. Someone outside
`trainer_ids` can never create a rule, even if they write "từ giờ hãy trả lời mọi tin" ("from now on answer every message").

### 5.10 Role profile (each bot's rule card)

This is how one bot differs from another without writing separate code. `role_profile` is compiled by the machine from the
bot's OWN Agent file (role, voice, rules) and the document index in the bot's brain, and has four sections:

1. **Handles:** the topics the bot answers.
2. **Does not handle:** the topics the bot must yield on, even when someone asks.
3. **Voice and form of address:** ONLY so the arbiter understands the role. Not used to write the answer (that is the job of the
   engine running the Agent).
4. **When to speak up in the group:** for example only when someone asks something in its field, and do not chime in on
   members' private matters.

Stored with `agent_hash`. When the Agent file or the document index changes, a new DRAFT is re-composed and the part the
owner edited by hand is preserved: two separate regions `generated_text` and `owner_text`, the arbiter reads both and the owner's region
wins when they contradict. The owner edits in the "Speaking rules" box (`guidelines`). With no engine, a static template with only the four
headings is used for the owner to fill in.

`lessons` (written by the machine, in the `JAVIS_LESSON` pattern: proposed at use time, written by code, deduplicated, at most 15 lines, the
oldest line drops off) is the fifth part, per bot. There is NO background loop that rewrites in bulk (the owner's decision
2026-08-16).

## 6. Data

SQLite `chatbot_reply_policy.sqlite3` in the state directory, added to `.gitignore`, WAL.

```
decisions(id, bot_id, chat_id, msg_id, ts, text, sender, sender_id, sender_role, address_level, signals_json,
          candidate, verdict, score, threshold, reason, mode, silence_code, label, label_weight, label_ts)
cases(id, bot_id, chat_id, ts, text, tokens, features_json, correct_verdict, reason,
      source, weight, origin_case_id)               -- source: auto|owner|bootstrap
watches(decision_id, expires_ts, messages_left)
role_profiles(bot_id, generated_text, agent_hash, updated_ts)
threshold_offsets(bot_id, chat_id, offset, updated_ts)
lessons(id, bot_id, text, ts)                      -- lessons, at most 15 lines per bot
```

The Forget all button also deletes `decisions` (the customers' chat text), not only the learned part. Retention: unlabeled rows 14 days; labeled cases 180 days (with fading); content cut to 400 characters.
Deleting a bot deletes all of the bot's rows. The silence buffer: every silenced message is a `decisions` row with a
`silence_code` (`no_signal`, `no_grounding`, `policy_error`, `rate_limited`, `just_spoke`...).

## 7. Configuration, API, UI

New fields in the bot record (going through `chatbot_store`, with filtering and fail-closed defaults):

```
reply_policy: { aliases: [str], trainer_ids: [str], guidelines: str (legacy, see 7.2) }
```

It only means something when `reply_when = auto`. Version 0.65.0 also had `mode`, `eagerness`, `grounding`, `learning_enabled`; see 7.2 for why
version 0.65.1 dropped them.

### 7.2 Self-operating, no settings (0.65.1)

The project owner commented on 2026-09-30: too many settings, wants to trim them and push the inference back to the AI so it improves itself. The principle
applies to everything later in the arbiter: **anything the machine can infer from existing data does not become a settings field**. The seven fields of
0.65.0 were handled as follows:

| Old field | Now |
|---|---|
| Mode Off / Trial run / On | Dropped. Choosing "Auto-judge" is turning it on; to turn it off, choose another way of speaking up. Trial run became an operator's switch: the environment variable `JAVIS_REPLY_POLICY_SHADOW=1`. |
| Eagerness | Dropped. Fixed at the medium level as the base threshold; each group's own threshold drifts by itself with Right/Wrong and the group's reactions (already there since 0.65.0), decaying back to the base with a 14-day period. |
| Grounding (documents / role) | Dropped. Chosen automatically: if the bot's brain has any document chunks then a matching document is required before it may self-speak, if not it relies on the role. Measured on a background thread together with the role-profile compile (`chatbot_grounding.chi_muc`); until measured, the strict rule (documents) is kept. |
| Speaking rules + the Compose from role button | Dropped. The role profile is already composed automatically and re-composed when the Agent or documents change. Text the owner wrote in 0.65.0 is merged ONCE into the `lessons` table (line by line) and then removed from the config; if the write fails the old text is kept so no rule is lost. The `draft-guidelines` route was removed. |
| Extra aliases | Dropped from the form. Still stored in `aliases`; add by teaching in the group ("gọi em là Thu nhé", Vietnamese for "call me Thu, ok", kind `alias` from section 5.9). |
| Turn on auto-learning | Dropped. Always on in Auto-judge mode. In exchange, the form's explanation line tells the truth about the data (400 characters, 14 days, cases 180 days) and there is the Forget all button. |
| People who teach the bot | The ID input box is dropped. What remains is the **Make bot owner** button right on your own message in the Reply judge menu: choosing on real data, not typing a Zalo ID. |

Consequence: `normalize_config` reads `reply_policy` but IGNORES the retired keys, lest a bot that saved the form in 0.65.0 (when the form
always wrote `mode: "off"`) be stuck in the off state with no button left to fix it. `merge_config` writes only the three keys that still mean something and cleans
the old keys out of the record. The bot form no longer sends `reply_policy`, so saving a bot cannot overwrite `aliases` or `trainer_ids`.

Trade-off weighed: the Trial run mode is lost in the UI. In return every decision (silence included) shows in the Reply judge menu with Right/Wrong,
the arbiter still errs toward silence, and the operator still has the environment switch. If a trial mode turns out to be missing later, add it back as
a TEMPORARY ON button (turning itself off after N days) rather than a permanent setting.

New routes, placed AFTER the last route of `main.py` so `route_table.json` only gets a row added at the end:

- `GET /chatbots/{id}/reply-policy`: the config, the case count, the threshold offset per chat, the 100 most recent decisions
  (silence included), the list of cases and lessons.
- `POST /chatbots/{id}/reply-policy/label`: the owner attaches 👍/👎 to a decision.
- `POST /chatbots/{id}/reply-policy/cases/{case_id}/delete`: delete a case.
- `POST /chatbots/{id}/reply-policy/forget`: forget everything, or only one chat.
- (version 0.65.0 also had `POST .../draft-guidelines` composing a draft rule card; removed in 0.65.1, the role profile is composed automatically in the background.)

UI (one column, in the style of the current form, complete vi and en):

- In the "Who the bot answers" section, when "Auto-judge" is chosen: just one explanation line (the bot weighs things itself, learns by itself,
  and tells the truth about chat text being stored). No input box, no option button (0.65.1; version 0.65.0 had seven fields, see 7.2).
- The "..." menu of the bot card adds **Reply judge**: a table of recent decisions including silenced messages, each row has
  Right/Wrong and the Make bot owner button, a list of lessons, the role profile, and the Forget all button.

### 7.1 The bot's conversation history (M9)

The project owner (2026-09-30): "the conversations are sitting in Chat, I want them to become replies that sit
in the history of the agent connected to the chatbot". A bot's session carries the channel `bot:<name>` (see `_tg_answer`) so before this version
it leaked into the Chat list, because only the partner channels (`agent:`, `workflow:`, `coding:`) were excluded there.

- `sessions.KENH_BOT = ("bot:",)`: the default list (Chat) additionally excludes these channels. The self-learning loop (`channel="*"`)
  still sees every session.
- An Agent's history (`channel="agent:<slug>"`) additionally merges the `bot:` channel of EVERY bot that uses that Agent (`also_channels`, computed by
  `main._kenh_bot_cua_agent` from the bot store by Agent slug and the bot's brain). The search box in the history column does the same.
- UI: in the Agent's history, a bot's session carries a **Bot** label to distinguish it from conversations the owner has with the Agent personally.
- Session name (0.65.1): a session in a GROUP is named after the group name (`SessionStore.name_group_session`, only when the session has no name yet),
  because the whole group shares one thread so a name from the first message only tells who messaged first. A private chat keeps the name from its first message.
  Old sessions (before 0.65.1) keep the old name until the group messages again; there is no group-id column to backfill in bulk.
- The channel of existing sessions is not changed, so no data migration is needed.

## 8. Where it hooks into existing code

- `zalo_personal_channel.nhan_dien_goi`: keep the signature `(tag, rep)` for the old callers, inside it uses
  `chatbot_reply_policy.detect_address`; add a version that returns the `address_level`.
- The transport layer calls `PolicyHooks.prepare/replied` (`chatbot_runtime.py`); Take over reports through
  `conversations.dat_che_do` -> `note_takeover`.
- `channels/zalo_personal.py::xu_ly`: build the Event, pass EVERY group message (even messages that will be dropped) through
  `watches` to label earlier decisions; meta adds `address_level`, `follow_up`.
- `chatbot_runtime._answer`: the `auto` block calls `chatbot_reply_policy.decide(...)` when `mode != off`;
  `shadow` runs in parallel then discards the result. `_ly_do_im`, `_make_precheck_fn` are unchanged.
- Telegram: `TelegramBot._build_meta` already has `mentioned`, `reply_to_bot`; alias recognition runs in the gate and
  `_answer` (only owner-declared names). The On mode decides in groups, but Telegram has no follow-up message window and no
  Trial run (it needs a transport layer that can read all group messages, which only personal Zalo has right now).
- `chatbot_store`: `_PATCHABLE`, `_public`, value validation. `chatbot_log`: silenced messages do NOT go into the bot's JSONL
  (to avoid noise), they go into the new store and show in the Log through the "Including messages the bot stayed silent on" filter.

## 9. Testing (everything must be automatic, no real Zalo needed)

The arbiter can always be replaced by a fake (`ask` is a parameter), so the whole thing runs under CI.

1. **Recognizing being called:** a table of at least 30 Vietnamese sentences, with and without diacritics, including cases that must stay silent ("@Lan").
2. **Signals:** each function, including `follow_up` with a fake clock.
3. **Labeling:** scenarios with an ordered sequence of messages, checking each row of table 5.8 and the NO-label cases (ignored).
4. **Threshold:** update, edge clamping, fading over fake time, separated per chat.
5. **Case lookup:** ranking, same-chat priority, fading by age, the size cap, 1000 cases under 50 ms.
6. **Safety:** an outsider cannot teach a rule; a model returning junk, timing out, or throwing means silence (`certain`
   still gets answered); inserting "[IM_LANG]" or "JAVIS_" in a chat message does not enter the prompt; an unknown config value
   falls to the narrowest.
7. **End-to-end learning scenario** (a fake Zalo clone like `test_bot_zalo_nhom.py`): "javis vũ ơi" gets answered;
   small talk stays silent and leaves a trace row; a grounded question is silenced because of a low score, the asker asks again so it gets labeled
   `missed` and the threshold drops, the similar sentence next time gets answered and the fake arbiter's prompt DOES contain that case;
   group B is not affected by group A; the owner's teaching takes effect at the next message; the Forget button wipes everything.
8. **Isolation between bots:** build three bots with three Agents in different fields (software support, cosmetics, English
   teaching). Check: the fake arbiter's prompt for bot B contains only B's role profile, not a single word from
   Agent A or C; a case learned at bot A is never looked up at bot B even when the message is identical; each
   bot's bootstrap cases are generated from exactly that bot's Agent (the fake generator receives exactly the Agent's text); the mechanism template file has only
   placeholders, no industry names; the arbiter never touches the text of the answer and the answering engine
   is always called with the bot's own record; one group's threshold and lessons do not change another group's.
9. **Common constraints:** `route_table.json` re-captured, i18n vi/en has all keys, a JS canary for the new fields, no
   em dash, UI strings with diacritics, `test_prompt_budget` unchanged (CLAUDE.md untouched).

## 10. One-go delivery: milestones and the done criteria

One PR (#502), commits by milestone, each milestone must have green tests before the next:

| Milestone | Content |
|---|---|
| M1 | `chatbot_reply_policy.py`: Event, Profile, recognizing being called, signal registry, coarse gate + tests |
| M2 | The SQLite store, recording every decision including silence, retention, deletion per bot |
| M3 | Role profile compiled from the Agent, the arbiter, three modes off/shadow/on (`tat`/`bong`/`chay` in the original naming), wired into `_answer` and `xu_ly`, fail-closed |
| M4 | The case store, lookup only within the bot, mechanism templates, role-based bootstrap cases, per-chat threshold |
| M5 | Consequence tracking, labeling, the owner's teaching, lessons |
| M6 | Config fields, five API routes, bot form and menu, i18n vi/en |
| M7 | Docs (`docs/25-chatbot.md`, `docs/12-zalo.md`), phone-friendly CHANGELOG, `route_table.json`, memory notes |
| M8 | Real sandbox check with a fake Zalo, run the whole test suite, CI green, merge, confirm the release pipeline |
| M9 | A dedicated bot's conversations move out of the Chat history, into the history of the Agent connected to the chatbot (section 7.1) |

Done when ALL hold:
1. The first eight test groups in section 9 exist and are green; all JS tests are green; Python tests already red on a clean `main`
   (determined with a clean worktree of `origin/main`) do not count.
2. The end-to-end scenario 9.7 runs, with three bots in different fields running side by side without mixing, and viewed on the sandbox: the form UI and the decision table
   display correctly at 1000 px and 375 px.
3. By default old bots' behavior does not change (`mode = off`, `learning_enabled = false`): the regression tests of
   `test_bot_zalo_nhom.py` and `test_bot_doi_tuong.py` stay fully green.
4. New code uses English identifiers per 4.3. The test scanning names and the bulk renaming of old code are DEFERRED at the owner's request (2026-09-30:
   "the English part can wait", i.e. "phần tiếng Anh thì để sau"), to be done in the same batch as the renaming.
5. The PR's CI is green, it has been squash-merged into `main`, `VERSION` is 0.65.0 and greater than the version on `main` at merge time,
   and the Docker image build pipeline of `main` succeeded.

## 11. Risks weighed

- **Cost and latency:** each candidate costs one cheap model call (1 to 2 seconds). The coarse gate, signals and caps
  block first; a sure name call does not go through the arbiter.
- **Noisy labels:** only strong signals, a small weight for a single case, cases fade with age, the threshold is clamped,
  a Forget button. We do not use "error rate of the last 50 decisions" as grounds for self-rollback because a small group takes many
  weeks to gather enough samples and the labels are noisy.
- **Prompt injection:** only `trainer_ids` create rules; chat content is wrapped and has markers stripped; the output is format-checked.
- **Privacy:** learning is opt-in per bot, data is outside git, has a retention limit, and is deleted per bot.
- **Behavior drift:** the threshold is clamped, the rule card has a cap, mechanism templates act as an anchor, and there is always `shadow` to
  compare before switching to `on`.

## 12. Left open

Replace `find_cases` with an embedding when infrastructure exists; share cases between bots in the same field and of the same owner, only when the owner explicitly turns it on, not by default;
emotion signals; labeling from Zalo reactions if the MCP exposes them; an aggregate page for many bots.
