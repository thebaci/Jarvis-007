# Spec: Multilingual support for Jarvis 007

> Dev spec, written 2026-08-10 on top of v0.26.16. Goal: Jarvis 007 speaks many languages, and
> **adding language number N+1 means adding DATA, not changing code**.
>
> **Status: BATCH 1 IS DEPLOYED** (2026-08-14, on top of v0.34.1) for two languages,
> **vi** and **en**. See section 6 for exactly what was done and what was not.
>
> The survey below was written on v0.26.16, so the LINE NUMBERS have drifted. Four places where the spec was
> WRONG or OVERSTATED have been corrected in place, marked **[CORRECTION]**. Read them
> before taking this spec out to prioritize work.

## 1. Core decision and why

**"Multilingual" is not one job. It is FOUR different jobs sharing one name**, and three
of the four have nothing to do with each other technically. Lumping them together is the surest
way to finish the easiest layer and believe everything is done.

| # | Layer | The real question | Where it is hard |
|---|-------|-------------------|------------------|
| 1 | **REPLY language** | What language Jarvis 007 answers in | Almost done already, blocked only by one rule line in `CLAUDE.md` |
| 2 | **UI language** | Text on buttons, labels, error messages | 3,520 lines of Vietnamese hardcoded, no build step |
| 3 | **LOGIC language** | Gates, classifiers, the promise detector | **The most dangerous. Fails silently.** |
| 4 | **Locale** | Time zone, currency, date format, voice | UTC+7 hardcoded in 6 places |

**Layer 3 is the reason this spec exists.** When layers 1 and 2 break, users SEE it immediately and
complain. When layer 3 breaks, nobody sees anything: a Thai user will be served by Jarvis 007 just as
usual, except that the token-saving shortcut swallows questions that need live data, the catcher for "lying
about having finished" never fires, and the gate guarding calendar operations never closes. No red log,
no exception, just politely wrong answers.

So **decision number one: language must NOT be a condition of logic.** Wherever today a
`re.compile(r"...dat lich|dang bai...")` decides behavior, it has to become "look up a
per-language lexicon", plus a **safe fallback rule** for a language that has no lexicon.

**Decision number two: one single CLAUDE.md.** Do not translate 30KB of behavior rules into N copies. This repo
has already fallen once into the trap of "writing a second copy of something that exists and then the two copies drift apart" at 0.15.0 (see
[the CLI spec](2026-08-cli-spec.md) section 1). A 30KB system prompt multiplied by N languages is exactly that trap,
at a worse scale: when two copies of the safety rules differ, the English version loses a guardrail and
nobody knows. The model does not need to read the rules in English in order to ANSWER in English.

**Decision number three: split the three language variables, do not merge them.** The UI language, the reply
language, and the language of the content in the brain are three independent things. A Vietnamese person selling to Japanese customers
wants a Vietnamese UI, a Vietnamese brain, but the customer-care chatbot must answer in
Japanese. Merging the three variables into one blocks exactly the most valuable use case.

## 2. Current state: the code was inspected, not guessed

### 2.1. The REPLY layer - nearly done

This is the good news. The output contract **already** has been language-agnostic:

- `context_compiler.ContextCompiler._output_contract` (context_compiler.py:366) returns
  `{"language": "match_user", ...}`.
- `_output_contract_text` (context_compiler.py:394) spells it out in words: *"Dùng đúng ngôn ngữ người
  dùng đang dùng."* (Vietnamese for "Use exactly the language the user is using.")

That means the token-saving path already follows the user's language. The thing pulling the other way is the **legacy path**,
where the system prompt is the verbatim `CLAUDE.md`:

- `main.py:231-232` loads `CLAUDE.md` as `SYSTEM_PROMPT`.
- `main.py:354` `build_system_prompt()` appends memory, the agentic layer, the clock, and usage level.
- `CLAUDE.md`, section "Response principles", rule number 5: **"Vietnamese is the primary language"** (the original
  wording was `Tiếng Việt là ngôn ngữ chính`).

That one line overrides `match_user` on every run of the legacy path. Fixing layer 1 is mostly about making that line
conditional, plus a dynamically inserted LANGUAGE block.

A few more places force Vietnamese in secondary prompts:

- `main.py:3016` describes images "in Vietnamese".
- `main.py:5801` the lint prompt says "Vietnamese".
- `meta_tools.py:79` "Vietnamese is the primary language".
- `reminders.py:689` the reminder summary prompt says "Vietnamese".
- `context_compiler.dong_ho()` (context_compiler.py:60) generates the sentence "It is now 14:30 Monday
  10/08/2026, Vietnam time (UTC+7)" (in Vietnamese in the code).
- `channel_context.build_channel_block()` (channel_context.py:28) - the whole channel block is written in
  Vietnamese, about 60 lines of rules sent straight to the model.

The channel block and CORE_CONTRACT being written in Vietnamese **need no translation** (see decision number two),
but the clock sentence does: it contains "thứ hai" (Monday) and "giờ Việt Nam" (Vietnam time), which are data, not rules.

### 2.2. The UI layer - 3,520 lines, no build step

The dashboard is plain JS, `app.mount("/static", StaticFiles(...))` (main.py:218). No webpack,
no vite, no bundler. Vietnamese strings are scattered through template literals and HTML attributes.

| File | Lines with Vietnamese |
|------|-----------------------|
| `dashboard/console.js` | 1,464 |
| `dashboard/app.js` | 449 |
| `dashboard/chatbots.js` | 291 |
| `dashboard/index.html` | 215 |
| `dashboard/sessions-ui.js` | 135 |
| `dashboard/studio.js` | 128 |
| the other 18 files | ~838 |
| **Total** | **3,520** |

On top of that, the server side has **182 Vietnamese error strings** returned to the UI as `{"error": "..."}`
(for example `"Sai tài khoản hoặc mật khẩu"` meaning "Wrong username or password", and `"Mật khẩu tối thiểu 8 ký tự"` meaning "Password must be at least 8 characters").

**The other 9,384 lines of Vietnamese in `server/*.py` are mostly NOT product surface.** This
is often miscounted, so it was stripped out with an AST to remove any guesswork:

| Kind | Lines | Who reads it | Translate? |
|------|-------|--------------|------------|
| Comments (`#`) | 3,142 | developers | No |
| **Docstrings** | **3,313** | **developers** | **No** |
| Real strings (prompts sent to the model + errors shown to the user) | 2,482 | the model and users | Only the part shown to users |

**69% of the Vietnamese lines in the server are comments and docstrings.** This repo deliberately writes
long docstrings to explain *why* (`dong_ho()` alone has 15 lines), so the figure of 9,384 looks big while
the real product surface is only about **2,500 lines**, of which 182 are error strings shown to the user and nearly all
the rest are prompts.

In other words: **anyone who converts "9,384 lines of Vietnamese" into "9,384 lines to translate" is
overestimating by about 3.7 times.** The real scope of the whole multilingual project is 3,520 lines of
UI plus 182 error strings, not twenty thousand lines.

### 2.3. The LOGIC layer - where it bleeds

This is the complete list of places where Jarvis 007's behavior depends on the user typing Vietnamese.
Every entry was found by reading the code, with line numbers.

| Place | Code | How it breaks when the user speaks another language |
|-------|------|------------------------------------------------------|
| Fast shortcut gate | `fast_path_runtime.py:52-100` - `_DENY` catches `dinh kem` (attachment), `hom nay` (today), `doanh thu` (revenue), `dat lich` (book a schedule) | A question that needs live data SLIPS through the shortcut, which does not emit tools. The model makes things up. This is exactly the case recorded in the `dong_ho()` docstring. |
| One-step read-only gate | `readonly_path_runtime.py:44-49` - `_WRITE_INTENT`, `_STATE_REF` | A sentence with an INTENT to write is treated as read-only |
| Read-only orchestration | `readonly_orchestrator.py:79` | Same as above |
| Action false-claim catcher | `context_compiler.py:1093-1110` - `_FALSE_ACTION`, `_ACTION_VERBS`, `_QUANTITATIVE` | **When Jarvis 007 says "sent" without having sent, nobody stops it.** This is a safety guardrail, not a feature. |
| Empty-promise detector | `background_status.py:60-85` - `_PROMISE` | The rule "do NOT promise you will report back" in `CLAUDE.md` silently stops working |
| Calendar operation gate | `engine.py:1143-1220` - keyword lists `hom nay` (today), `nhac hen` (reminder), `dat lich tu van` (book a consultation)... | Both misses real commands and fires wrongly when a customer only makes small talk |
| Search for the customer chatbot | `chatbot_grounding.py:70-115` - strips Vietnamese diacritics, a hand-written list of colliding words | A chatbot serving foreign customers searches documents much worse |
| Memory-write priority trigger **[CORRECTION]** | `learn.py:313` - `_REMEMBER_RE` | The first draft of this spec said *"Jarvis 007 learns nothing"*. **Wrong in degree.** Reading the code again: this pattern only sets the `urgent` flag (line 341) so that `_should_fire` fires after 30 seconds instead of waiting for 3 turns. The gate that decides WHETHER TO LEARN is `_classify_turn` returning `"low"`, and that gate is language independent. The truth: English users learn **SLOWER**, not never. In exchange this turned up a hole the spec had not seen: the pattern does not strip diacritics, so `"ghi nho gium anh"` (Vietnamese WITHOUT DIACRITICS, meaning "remember this for me") also misses |
| **Stuck-bot detection** | `chatbot_runtime.py:497` - `_DAU_BI` contains `chưa có thông tin` (no information yet), `chuyển nhân viên` (hand over to staff), `em chưa rõ` (I am not sure)... | **Purely Vietnamese, not a single English word.** A bot caring for foreign customers is never counted as stuck, the "Stuck bots" tab is empty, and the owner looks at it and thinks the bot runs perfectly |
| Conversation state extraction | `conversation_state.py:26-29` - `_GOAL_RE`, `_DECISION_RE`, `_CONSTRAINT_RE`, `_DONE_RE` | Goals, decisions, constraints and finished work are not carried to the next turn |
| Memory lookup hint | `memory_index.py:28` - `_MEMORY_HINT_RE` | Does not trigger a memory lookup when one is warranted |
| Background job intent inference | `tasks.py:575` | Classifies the job into the wrong group |
| Sentence cutting for session names | `sessions.py:153` - cuts at a period because "Vietnamese uses many periods" | Ugly session names, not dangerous |

Thirteen places, not nine as in the first survey. The four found later are **worse** than the group found
earlier, because two of them hit the two things that make Jarvis 007 what it is: **whether it learns from the
user**, and **whether the owner knows their bot is stuck**.

**[CORRECTION] The danger lies in HALF a lexicon, not in the lack of a lexicon.** The first draft of the spec said that a foreign language makes the gates fail silently. Measured against the real code
that is NOT so, and the truth is more notable:

    "tóm tắt đơn hàng"    -> blocked correctly (the `don hang` pattern matches)
    "summarize my orders" -> SLIPS through the shortcut, the model invents order counts
    "สรุปยอดขายวันนี้"     -> matches nothing -> `intent_uncertain` -> full path, SAFE

(The first line is Vietnamese example input meaning "summarize the orders", kept on purpose; the third is Thai for "summarize today's sales".)

Thai is safe **because it matches nothing at all**; the classifier already defaults to refusing. English
is dangerous **because it matches half**: `summarize` matches ALLOW, while the English DENY list lacks
`orders`. In other words, the more half-served a language is, the more dangerous it gets, and the
language about to be added (English) is exactly that half-served language. The fallback rule in section 4.3 is therefore still needed,
but its real reason is **to block the half-baked case**, not to block the missing one.

**Small does NOT mean low risk.** These thirteen places
add up to under 60 lines of code out of 49,000 total, so looking at the table it is easy to conclude "contained,
nothing to worry about". Wrong. They are small **precisely because they are gates**: a three-line gate controls the whole
of what runs after it. The right measure is **blast radius**, not line count.

All of these matchers share one `_norm()` trick: strip diacritics then lowercase, with a hand-written `đ -> d` map
because NFKD cannot decompose `đ` (`fast_path_runtime.py:25`, `readonly_path_runtime.py:34`,
`background_status.py:49`). **This trick is only right for accented Latin text.** Japanese, Thai and
Arabic pass through `_norm()` unchanged, and no ASCII pattern can match them.

Worth noting: a few patterns already have English words mixed in (`send|delete|create|book|publish`). That
means English today is served **halfway**, enough to look fine and not enough to be right.

### 2.4. The LOCALE layer

- **UTC+7 time zone hardcoded in 6 places**: `usage_index.py:28`, `usage_parsers.py:19`,
  `system_sync.py:67`, `main.py:555`, `main.py:3470`, `context_compiler._bay_gio`.
- **The `datetime-vn` plugin** (`system/plugins/datetime-vn/plugin.yaml`) provides the tools `javis_now` and
  `javis_date_add` to EVERY brain, and its description says outright "in Vietnam time zone (UTC+7)" (in Vietnamese).
- **VND currency [CORRECTION]**: already DONE upstream. Commit `5c59de7` (0.32.1) removed all USD to dong conversion from the Usage page. This item falls out of scope. NUMBER FORMATTING is not done: `toLocaleString("vi-VN")` is still in `usage.js`.
- **Number/date formatting**: `toLocaleString("vi-VN")` in `usage.js`, `console.js:1245,4045`,
  `sessions-ui.js:20`, `chatbots.js:368`, `studio.js:595`; `localeCompare(..., "vi")` in
  `dataview.js:365`, `studio.js:442`.
- **Cron to text**: `cron_util.describe_cron()` (cron_util.py:185) generates "7:00 mỗi ngày" ("7:00 every day"), "thứ hai
  hằng tuần" ("every Monday"). It has a good fallback already: for an unfamiliar form it returns the raw cron expression.
- **Voice**: STT defaults to `language="vi"` (`stt.py:82-96`); TTS defaults to
  `vi-VN-HoaiMyNeural` (`main.py:6347`, `main.py:7110`, `voice.js:7,23`); the Edge voice list is
  **hard filtered** with `v["Locale"].startswith("vi")` (main.py:7148); the UI only lets you choose vi-VN or
  en-US (`index.html:288-306`).
- `<html lang="vi">` (index.html:2).

One existing asset worth using: `voice.elevenlabs_model` is already `eleven_multilingual_v2`
(`config.py` `_DEFAULT`). The ElevenLabs path almost works multilingually already.

### 2.5. There is no i18n infrastructure yet

No `gettext`, no `Babel`, no translation library in `requirements.txt`. Starting from
zero, and that is a good thing: we get to choose something that fits instead of carrying a heavy framework.

## 3. Scope

### 3.1. In scope

- **The smallest build that measures demand first (section 6)**, then the rest of this list.
- Three separate language variables + a single decision function `resolve_lang()`.
- A **lexicon** layer replacing hardcoded regexes, with a safe fallback rule.
- i18n infrastructure for the dashboard with no build step, plus regression tests.
- A LANGUAGE block inserted dynamically into the prompt; keep **one** `CLAUDE.md`.
- Error codes for the 182 server error strings, translated on the UI side.
- Separate locale (time zone, currency, format) from language.
- A per-language voice map for STT and TTS.
- A dedicated language field for each dedicated chatbot.
- A "add a new language" playbook with an acceptance test.
- The second language that ships with this build: **English**.

### 3.2. NOT in scope, even when pushed

- **Do not translate `CLAUDE.md` into N copies.** The reason is in section 1.
- **Do not machine-translate the 27 user docs on every release.** An old translation that says wrong things about new software
  is worse than no translation. Translate by hand only the front door: `README.md`, `QUICKSTART.md`,
  `docs/01-bat-dau-thiet-lap.md`. For the rest, say plainly "not translated yet".
- **Do not re-translate the model's answer after it has spoken.** It costs double, breaks numbers, breaks
  markdown, and the model can answer in the right language by itself anyway.
- **Do not translate the brain's content.** Notes, wiki and memories belong to the user.
- **Do not put the language into URL paths** like `/en/chat`. The dashboard is a single page with a self-routing
  rail; a setting plus `localStorage` is enough.
- **Do not duplicate `SKILL.md` per language.** Only allow mapping `description` per language, and
  only for the 4 system skills.
- **Do not rename the `datetime-vn` plugin slug.** Renaming the slug forces every running brain to migrate, in exchange
  for zero value. Keep the slug, change the behavior.
- **Do not touch the brand text that must keep its capitalization**: "Jarvis 007", brain names, tool names.

## 4. Settled architecture

### 4.1. Three variables, one decision function

```
ui_lang       Language of the TEXT ON SCREEN. The user chooses. Stored per device.
reply_lang    Language Jarvis 007 ANSWERS in. Default "auto" (follows the user turn by turn).
content_lang  Language of the brain's CONTENT. Used only as a hint, never forced.
```

One single function, `server/lang.py`:

```python
@dataclass(frozen=True)
class LangDecision:
    lang: str          # "vi" | "en" | "ja" ... (short code, not full BCP-47)
    source: str        # turn | chatbot | brain | channel | detect | ui | default
    confidence: float  # 0..1
    has_lexicon: bool  # whether a lexicon exists for this language

def resolve_reply_lang(*, turn_text, session, brain, channel, chatbot=None) -> LangDecision
```

**Priority order, highest to lowest:**

1. The user gives a direct command in this turn ("answer in English please").
2. The pinned language of the dedicated chatbot (if this turn belongs to a bot).
3. The pinned language of the brain.
4. The channel default (Zalo defaults to `vi` because it is a Vietnamese platform).
5. Detection from the user's message.
6. `ui_lang`.
7. `vi`.

**Preventing flip-flopping.** Detecting the language every turn and switching immediately is broken: a person speaking
Vietnamese who drops in one English sentence does not mean they want to change language. The rule: the language **sticks to
the session**; it changes only when detection differs from the current language **two turns in a row** with
`confidence >= 0.8`. Write both `lang` and `lang_source` into the trace so that wrongly detected cases can be examined
in the field.

**What to detect with.** No new dependency (this repo already dropped `rich` from the CLI to keep it lean). We only need to tell
apart the REGISTERED languages, so two tiers are enough: script recognition through Unicode code ranges (this
settles ja, ko, zh, th, ar, ru, hi in a few lines), and for Latin-script languages, scoring
with a set of function words that lives right in the language profile. That means **adding a new language is also adding
data**, not changing the detector.

### 4.2. The language registry - one file, everything about a language

`server/lang_registry.py`. This is the **heart of extensibility**: adding a language = adding one entry.

```python
LANGS = {
  "vi": Lang(
    code="vi", native="Tiếng Việt", english="Vietnamese",
    script="latin", rtl=False,
    stopwords={"và","của","là","không","được","cho","với","này"},
    stt="vi",                                  # code for Whisper
    tts={"edge": "vi-VN-HoaiMyNeural", "openai": "alloy", "elevenlabs": None},
    tz_default="Asia/Ho_Chi_Minh", currency="VND", first_day=1,
    plural=False,                              # Vietnamese has no plural forms
    nudge="Trả lời bằng tiếng Việt.",          # for weak models, see 4.5 ("Answer in Vietnamese.")
  ),
  "en": Lang(code="en", native="English", english="English", script="latin",
             stopwords={"the","and","of","is","not","for","with","this"},
             stt="en", tts={"edge": "en-US-AriaNeural", "openai": "alloy",
                            "elevenlabs": None},
             tz_default="UTC", currency="USD", first_day=0, plural=True,
             nudge="Answer in English."),
}
```

The Vietnamese stopwords are the actual detection data for `vi` (and, in order: "and", "of", "is", "not", "to be given", "for", "with", "this").

The rule: **no code outside this file may write `if lang == "vi"`.** Whatever needs to be known about a language
is asked of the registry. A test guards exactly this rule (section 8).

### 4.3. The lexicon layer and the safe fallback rule

This is the hardest part and the most worthwhile.

```
server/lexicon/__init__.py    get(lang) -> Lexicon | None
server/lexicon/vi.py          carry over the existing regexes as they are, not changing one character
server/lexicon/en.py          newly written
```

Each `Lexicon` provides exactly the sets the gates need, named by MEANING rather than by the
place that calls them: `WRITE_INTENT`, `LIVE_DATA`, `ATTACHMENT`, `STATE_REF`, `PROMISE`, `FALSE_ACTION`,
`ACTION_VERBS`, `QUANTITATIVE`, `CAPABILITY_DENIAL`, `SCHEDULE_OPS`.

**Phase 2 starts by copying the Vietnamese regexes verbatim into `lexicon/vi.py`.** No edits,
no "cleaning up while we're here". Vietnamese behavior must be identical bit for bit, and the existing test suite must be green
without changing a single line of tests. Cleanup comes in a later pass.

**The fallback rule - the most important part of the whole spec.** When the detected language has no lexicon,
each gate falls back according to its **kind**, not by one common rule:

| Gate kind | Examples | With no lexicon |
|-----------|----------|-----------------|
| **Gates that EXPAND privilege** (skip a step, take a shortcut) | the fast shortcut, the one-step read-only path | **Refuse, take the full path.** It costs tokens, not correctness. |
| **Gates that CATCH ERRORS** (safety guardrails) | catching false action claims, detecting empty promises | **Must NOT quietly let it through.** Drop down to one call to a cheap auxiliary model (`aux_engine`), a binary classification, cached by the hash of the answer. If the auxiliary model fails, mark the trace `unverified` and write a log entry, rather than pretending it was checked. |
| **PRESENTATION gates** (display only) | cutting a sentence for a session name, cron to text | Crude fallback: cut by characters, print the raw cron expression. `describe_cron` already has this path. |

In other words: **a missing lexicon makes Jarvis 007 COST MORE, not become LOOSER.** That is the only
sentence to remember from this section.

### 4.4. UI i18n, no build step

```
dashboard/i18n/index.js    t(), setLang(), applyDom()
dashboard/i18n/vi.json     the canonical source, 100% of the keys by definition
dashboard/i18n/en.json     translation
```

**Loading.** `index.html` loads `i18n/index.js` before `app.js`. The dictionary sits in `localStorage`
with a version stamp (the same `?v=` mechanism that `main.py:599` already stamps on static assets), so F5
does not flash the text. If the cache is a version behind, reload once and then render.

**Key convention.** ASCII keys, dot-separated hierarchy, named by PAGE and then by idea: `chat.input.placeholder`,
`nav.viec`, `err.login.wrong`. **Never use the Vietnamese string itself as the key** - fixing a
typo in the Vietnamese version and breaking the whole English version is a pointless way to break things.

**Fallback.** `<selected> -> vi -> the key itself`. `vi.json` has 100% of the keys because it is extracted from the code that
is running. The user never sees a bare key.

**Plurals.** Vietnamese has none, English does. Do not pull in the whole of ICU MessageFormat for this one
job. The dictionary may declare `key.one` and `key.other`; `t()` chooses by `{count}` when one is
passed; a language without plurals only declares `key.other`.

**Variable substitution.** Only `{ten}` (`{name}`). **No HTML in the dictionary** - the dictionary is data, and putting HTML in it is
opening an XSS door that nobody will remember to close later. To bold part of a sentence, split the string.

**Static HTML.** `index.html` uses `data-i18n`, `data-i18n-title`, `data-i18n-aria`; `applyDom()`
sweeps once after loading.

**How to migrate 3,520 lines without freezing.** Not all at once. Follow usage traffic: the chat
frame -> the navigation rail -> the Settings page -> the rest. Each pass adds the file name to an
`I18N_MIGRATED` list, and a test **goes red if a migrated file shows Vietnamese text outside
comments again**. Without that latch, every cleanup gets dirtied again by the next feature change.

**The server's 182 error strings: use error codes, do not translate on the server.** The server returns an extra `code` field
next to the Vietnamese string it already has:

```python
{"error": "Sai tài khoản hoặc mật khẩu", "code": "auth.bad_credentials"}
```

The UI prefers `t("err." + code)` and shows `error` as is if there is none. Fully
backward compatible, can be done endpoint by endpoint, and the server does not have to know what language the user is viewing in.

### 4.5. System prompt: one copy, plus a LANGUAGE block

`build_system_prompt()` (main.py:354) inserts, next to the `# === BÂY GIỜ ===` block (the "NOW" block):

```
# === NGÔN NGỮ ===
Ngôn ngữ trả lời: English (en). Người dùng đang viết bằng: en.
Viết TOÀN BỘ câu trả lời bằng ngôn ngữ này, kể cả tiêu đề, nhãn, đơn vị, câu cảnh báo.
Giữ nguyên không dịch: tên riêng, đường dẫn file, tên tool, khối mã, trích dẫn từ brain.
Nội dung brain viết bằng ngôn ngữ khác thì cứ đọc bình thường, chỉ TRẢ LỜI bằng ngôn ngữ trên.
```

(In English: "Reply language: English (en). The user is writing in: en. Write the ENTIRE answer in this language, including
headings, labels, units, warning sentences. Keep untranslated: proper nouns, file paths, tool names, code blocks, quotes from the brain.
If brain content is written in another language, read it normally and only ANSWER in the language above." The block header and body stay Vietnamese because the machine-matched header is `# === NGÔN NGỮ ===` ("LANGUAGE") and the body is a behavior rule for the model.)

`CLAUDE.md` rule number 5 changes from "**Vietnamese** is the primary language" to "**Answer in the language
named in the LANGUAGE block** (the `# === NGÔN NGỮ ===` block); if there is no such block, follow the language the user is using". The same
fix applies to `meta_tools.py:79`, `main.py:3016`, `main.py:5801`, `reminders.py:689`.

`context_compiler.dong_ho()` generates the sentence according to the configured language and time zone. Weekday names
come from the registry, not from the hardcoded `_THU_VN`.

**One point that must be said honestly, not hidden.** A strong model answers in the requested language even when
the rules are written in Vietnamese. A weak model **drifts into the prompt's language** - this is real
with the small models run through Groq or Ollama Cloud, the two routes Jarvis 007 is competing on. The fix: the language
profile already has a `nudge` field, one sentence written in the TARGET language itself; for an engine marked weak,
stick that sentence onto the front of the last message. One line, in the right place, and still data rather than code.

**Token cost.** The LANGUAGE block is about 60 tokens per turn. Negligible next to the 30KB `CLAUDE.md`,
and it spoils no additional prompt-cache hit: Jarvis 007's system prompt already changes every turn because the
`MỨC DÙNG HÔM NAY` ("TODAY'S USAGE") block counts in real time (the argument is recorded in the docstring of `dong_ho()`,
context_compiler.py:56).

### 4.6. Locale separated from language

Add to `config._DEFAULT`:

```python
"locale": {
    "ui_lang": "vi",          # UI language
    "reply_lang": "auto",     # auto | vi | en | ...
    "tz": "Asia/Ho_Chi_Minh",
    "currency": "VND",
    "first_day": 1,
},
```

**A naming trap to avoid: do NOT name the file `server/locale.py`.** Modules in `server/` load
flat (`import config`, `import system_sync`), so a file named `locale.py` would shadow the standard library's
`locale`. Name it **`server/localefmt.py`**, providing `now()`, `today()`, `fmt_money()`,
`fmt_dt()`. `zoneinfo` ships in the standard library, so no added dependency.

Replace the 6 hardcoded UTC+7 places with `localefmt.now()`.

**One place needs care: `usage_index._TZ` decides the DAY boundary of the usage statistics.** Changing the
time zone changes the meaning of old data. The rule: new data follows the configured time zone, old data is left
as is, and the time zone is stamped into the record. Do not rewrite history.

The `datetime-vn` plugin keeps its slug and keeps the tool names `javis_now` / `javis_date_add` (these two
names are already in the prompt and in usage habits). The only changes: read the time zone from config, and the plugin
description stops hardcoding "Vietnam".

`toLocaleString("vi-VN")` in 6 places on the dashboard side becomes a `LOCALE` constant supplied by `i18n/index.js`. The VND
conversion at `usage.js:181-199` follows `currency`; for a currency other than VND, drop the conversion line
instead of inventing an exchange rate.

### 4.7. Voice

- **STT** (`stt.py:82-96`): the `language` parameter comes from `resolve_reply_lang()`. When `reply_lang`
  is `auto` and there is no firm basis yet, pass **empty** so Whisper detects by itself. The hardcoded default `"vi"`
  today actively breaks non-Vietnamese speech.
- **TTS**: remove `startswith("vi")` at `main.py:7148`; filter by the selected language. The voice comes from
  `LANGS[lang].tts[provider]`. If there is no voice for that language-provider pair, fall back to
  ElevenLabs `eleven_multilingual_v2` (already configured), and only then to the default Edge voice.
- UI: the two hardcoded radio buttons at `index.html:288-306` become a list generated from the registry.

### 4.8. Channels and dedicated chatbots

- **Dedicated chatbot** (`chatbot_store.py`) gets a `ngon_ngu` ("language") field, default `auto`. This is
  the most valuable use case of the whole spec: the bot serves STRANGERS, not the owner, so its language
  has no reason to follow the owner's UI language.
- **Telegram**: language per chat, detected from messages, sticking to the chat.
- **Zalo**: default `vi`, with override allowed.
- **CLI**: follows the global `reply_lang`, plus a `--lang` flag.
- The channel block (`channel_context.py`) **stays in Vietnamese**. It is a rule for the model, not
  text for the user.

### 4.9. Skills

`skill_router.SKILL_DESC_MAX` stays at 150 characters, applied **per language**. Frontmatter is
allowed to declare a map:

```yaml
description:
  vi: "Tiêu hoá một source thô vào Second Brain..."
  en: "Digest a raw source into the Second Brain..."
```

The flat string form remains valid and remains the recommended form for skills users write themselves. The router reads
`description[lang]`, falls back to `description[vi]`, then to the flat string. **Only the 4 system skills**
(`javis-builder`, `ingest-source`, `query-wiki`, `lint-wiki`) declare a map; user skills
are not touched.

## 5. Adding a new language: the playbook

This is the **acceptance test of the whole spec**. Adding Thai must be this much work and no more:

1. `server/lang_registry.py`: add one `th` entry (native name, script, function words for detection, STT code, TTS
   voice, default time zone and currency, whether it has plurals, the `nudge` sentence).
2. `dashboard/i18n/th.json`: copy `vi.json` and translate. Missing keys fall back to Vietnamese on their own, without breaking the
   UI.
3. `server/lexicon/th.py`: **optional**. Without it the token-saving shortcut turns itself off for Thai
   users, and the safety guardrails drop down to the auxiliary model tier. Jarvis 007 still runs CORRECTLY, just costs
   more. It can be written after real users show up.
4. Run `python tests/run.py`. The key cross-check test and the registry invariant tests must be green.

**Change no other file. Having to change anything else means this spec is broken - fix the spec first, do not
patch around it quietly.**

Two OPTIONAL steps, which can be done any time later because both have a fall-back path:

5. `description_<code>` in the skill's frontmatter (if missing it falls back to the original description).
6. User docs, translated by hand (`README.en.md`, `docs/en/*`).

The full to-do list, including a section on "what you do NOT have to do":
**[docs/dev/them-mot-ngon-ngu.md](them-mot-ngon-ngu.md)**.

## 6. The smallest build that measures demand

Before spending two weeks, there is a reasonable question: **is there real demand, or is this a self-
suggested feature?** That question deserves to be answered with real money rather than guesses. But the test has to
be designed carefully, because the intuitive version of it **returns dirty numbers**.

### 6.1. The trap: a cheap test with a wrong result

The intuitive version sounds very reasonable: *insert "Reply in English" into the prompt, translate a few dozen main labels,
ship it, and only when 50 foreign users really use it, invest deeply.* One to two days of work.

The problem: that plan **turns English on without touching the 13 gates in section 2.3**. That means those 50
trial users get a Jarvis 007 where:

- the token-saving shortcut swallows questions that need live data and then the model makes things up,
- the false-claim catcher does not fire when Jarvis 007 says "sent" without having sent,
- **the memory-write trigger does not fire, so Jarvis 007 learns nothing from them** - exactly the thing that makes Jarvis 007 different
  from an ordinary chat window,
- the customer-care bot is never counted as stuck.

Then you measure "no demand". **But what you just measured is a broken product, not the
market.** A cheap test that returns a false negative is worse than no test, because you will act on
it and close off a direction for the wrong reason.

### 6.2. The fix, and it is cheaper than it looks

**The whole of Phase 2 is not needed.** Only the fallback rule from section 4.3, cut down to exactly one condition:

> If the session is not Vietnamese, **turn off every optimization path and take the full path.**

Turn off the fast shortcut and the one-step read-only path. It costs extra tokens for a few dozen beta users and costs almost
nothing to write. Add an honest label in the UI: *"beta, not yet optimized for this
language"*.

The smallest build therefore consists of:

1. A trimmed Phase 0: `lang.py` + a registry with two entries, `vi` and `en`, writing `lang` into the trace.
2. The LANGUAGE block in the prompt + the `CLAUDE.md` rule 5 fix.
3. **The one-line rule above: a non-Vietnamese session does not take the optimized path.**
4. The `ngon_ngu` field for the dedicated chatbot.
5. STT and TTS following the selected language.

**Two to three days instead of one to two.** In exchange the measured data can be trusted. This trade is a bargain:
one working day so that a strategic decision does not rest on garbage data.

Three things are **NOT** in the smallest build: UI translation (not needed, see 6.3), the full lexicon
layer, and locale.

### 6.3. Where to aim the test

This is where it is easy to choose wrong, and a wrong choice is only discovered two weeks later.

The intuitive version aims at **foreign shop owners**: translate the UI, wait for Americans to arrive. That test is
expensive (the UI has to be translated before anything can be tried), slow (it needs a distribution channel in the new market), and
it **hits where Jarvis 007 is weakest** - leaving Zalo, leaving the Vietnamese POS, entering a market with hundreds of
AI dashboards fighting each other.

The right aim is **Vietnamese shop owners serving foreign customers**:

> A Vietnamese shop owner has a chatbot caring for Japanese, Korean or Chinese customers, or sells for export. The owner's
> UI stays Vietnamese, the brain stays Vietnamese, Zalo stays Zalo. **Only one field, `ngon_ngu`, changes on the
> customer-facing bot.**

Three benefits, the third being the biggest:

- **Not one UI label has to be translated**, because the shop owner never leaves Vietnamese. The smallest
  build drops its single most expensive item.
- **Measure on the customer base you already have**, instead of first finding a new market and only then being able to measure.
- **Deepen the moat instead of switching moats.** This is a feature the international dashboards cannot match,
  because they have no Zalo and no Vietnamese business context. Whereas "translate the UI into English and go
  international" gives up the only advantage in order to step into a place where there is no advantage at all.

To be clear, because this is often conflated: **multilingual does NOT mean going international.** There are at least
three ways to use it, and the second is the one to try first:

| Direction | Who pays | Does the UI have to be translated? | Relation to the Zalo/POS moat |
|-----------|----------|------------------------------------|-------------------------------|
| Foreign owners use Jarvis 007 | completely new customers | Yes, all of it | Abandons the moat |
| **Vietnamese owner, foreign customers** | **existing customers** | **No** | **Deepens the moat** |
| Vietnamese owner prefers an English UI | existing customers | Yes, partly | Neutral |

### 6.4. Fix the threshold BEFORE running

The test only means something if the deciding number is written down **before** looking at the result; otherwise
any number looks reasonable. The concrete threshold is the repo owner's decision, but it must have
a shape like: *"within N weeks, at least X shop owners turn `ngon_ngu` to something other than `vi` on their bot and
still have it on after two weeks"*. The "still on after two weeks" metric matters more than the number of times it was turned on, because
trying it once is curiosity, not yet demand.

If the threshold is reached, go on to Phases 2 and 3. If not, stop here, and what was done is still not wasted:
the fallback rule in step 3 is a safety guardrail with value in its own right, even if Jarvis 007 only ever speaks
Vietnamese.

### 6.5. DEPLOYED (2026-08-14, on v0.34.1)

Batch 1 has code written and 226/226 tests green. Recording exactly what exists and what does not, so that nobody reads the
spec and assumes the unfinished parts are done.

**Exists:**

| Item | Where |
|------|-------|
| Language registry (vi, en) | `server/lang_registry.py` |
| Language detection + settling the part the human PINS | `server/lang.py` (**[CORRECTION 6.10]** the first version said "8 priority levels + session inertia"; the session layer was dropped, the reply language is handled by the model) |
| Per-language lexicon | `server/lexicon/{__init__,vi,en}.py` |
| LANGUAGE block (`# === NGÔN NGỮ ===`), **three** insertion points | `main.build_system_prompt`, `context_compiler._output_contract_text`, `chatbot_runtime.build_bot_prompt` |
| The shortcut gate + two read-only gates look up the lexicon | `fast_path_runtime`, `readonly_path_runtime`, `readonly_orchestrator` |
| Language-aware clock | `context_compiler.dong_ho(lang=)` |
| `ngon_ngu` field for the chatbot + picker | `chatbot_store`, `chatbots.js` |
| "Reply language" box in Settings | `console.js`, `POST /settings` `locale` branch |
| Three-state STT, TTS filtering voices by language | `stt.py`, `GET /tts/voices?lang=` |
| Behavior tests + invariant tests against regression | `test_da_ngon_ngu.py`, `test_lang_bat_bien.py` |

**Three insertion points, not one.** This is where the first draft of the spec fell short. The TOKEN-SAVING path does not
go through `build_system_prompt`, and the dedicated chatbot's prompt goes through neither of the other two paths.
Fixing only `build_system_prompt` makes the other two areas lose the LANGUAGE block silently - and the third
area is exactly the most valuable use case in section 6.3.

### 6.6. BATCH 2 AND THE FOUNDATION OF BATCH 3 (2026-08-14)

**Batch 2 closes: the two ERROR-CATCHING gates are wired into the lexicon.**

| Gate | Where | Fallback when the lexicon is missing |
|------|-------|--------------------------------------|
| Catching false action claims | `context_compiler.DeterministicQualityGate.evaluate` | run the UNION of the patterns of every lexicon, then mark `lang_unverified` in the trace |
| Detecting empty promises | `background_status.detect_promise` | same as above |

One detail worth recording because it saved an entire round of threading parameters: these two gates **detect the
language from the answer text itself** instead of receiving a parameter from the caller. They check what the model ACTUALLY
wrote, so the language of that text is a better basis than the language we ASKED for - the model can
still answer in the wrong language, and at exactly that moment we want to check with the lexicon that matches what it wrote.
That way the five call sites of `evaluate()` did not need a single line changed.

And `lang_unverified` does NOT change `status`: failing every Japanese answer just because there is no
Japanese lexicon yet would punish the user for a shortcoming of ours.

**The foundation of Batch 3 is built, the UI is not fully translated.**

- `dashboard/i18n/index.js` - `t()`, the `<selected> -> vi -> key` fallback, DOM sweeping via
  `data-i18n*`, plurals with `.one`/`.other`, loads itself at startup and then emits `javis:i18n`.
- `dashboard/i18n/{vi,en}.json` - the navigation layer (rail, page titles) and the language settings box.
- `console.js` - `RAIL_ITEMS`, `RAIL_GROUPS`, `VIEW_META` take their labels from the dictionary through getters, plus
  an `i18nTick` counter so Alpine re-renders when the dictionary arrives or when the user changes language.
- The **Interface language** box on the Settings page, takes effect immediately without F5.
- `tests/js/test_i18n.mjs` - two-way key matching, no HTML in the dictionary, no em dash, catches
  the case of "copying the Vietnamese verbatim into en.json", and **`I18N_MIGRATED`** is the latch against
  regression: a cleaned file that gets Vietnamese text back in running code turns the test red immediately.

A trap worth recording because it wasted time in a silly way: writing `dashboard/i18n/*.json` inside
a `//` comment made the test's comment-stripping function read `/*` as the start of a block comment, and it swallowed
20 lines of code after it. Three tests went red because of one asterisk in a sentence.

**Not done, on purpose:** most of the 3,520 UI strings (only the navigation layer is translated so far), error codes for the
182 server error strings, locale (time zone, number formatting), and per-language skill `description`.

### 6.7. BATCH 4 - LOCALE (2026-08-14)

**Locale fully separated from language.** That is the point of this whole batch: a person reading an English UI,
telling Jarvis 007 to answer in English, who still sits in Vietnam and so still uses UTC+7 and VND. Merging the two forces
them to choose between "understanding the text" and "seeing the right time".

`server/localefmt.py` is the single source: `now()`, `tz()`, `today_str()`, `fmt_tien()` (money formatter),
`cho_giao_dien()` (UI locale).

**The file name must NOT be `server/locale.py`.** Modules in `server/` load flat, so a file with that
name shadows the standard library's `locale` for everything that imports it, and it breaks in a way that is very hard to trace.
This trap was recorded in the spec at section 4.6 and was avoided this time.

**16 places with UTC+7 pinned in have been cleaned up**, in three groups by consequence:

| Group | Where | Consequence of changing the time zone |
|-------|-------|---------------------------------------|
| Only needs "what time is it now" | main, system_sync, self_improve, share_bundle, usage_store, learn, context_compiler | change directly, no consequence |
| **Cutting the DAY boundary** | usage_index, usage_parsers, usage_saving | data already written KEEPS its date string; only new data follows the new time zone |
| **Reminder times** | reminders, plugin javis-schedule | "7am" becomes 7am where the user is sitting |

The `reminders` spot is where the effect is clearest: before this, a user in another time zone was woken
a few hours off every day, and nothing on screen told them why.

**Do not rewrite history.** A record dated "2026-08-14" created under UTC+7 is still that date after
switching to UTC+9. At the moment of the switch there will be a bump in the date series; that is an unavoidable
consequence of changing time zones, and rewriting history to flatten it is much worse.

**Currency: format, do NOT convert.** `fmt_tien()` only puts the symbol in the right place for the currency
(VND after the number, USD before). Conversion needs a REAL exchange rate updated daily, and the old
conversion with a hardcoded rate was removed upstream (`5c59de7`) precisely because the number it showed did not match
what the user actually paid. A test guards against this coming back.

**Cron read out in words per language**, with weekday names taken from the registry. A trap worth recording: cron uses
`0 = Sunday` while the registry's `weekdays` follows `datetime.weekday()`, i.e. `0 = Monday`. Off
by one, and if the conversion is forgotten every "every Monday" schedule shows as "Sunday" - a silent error,
which the user only discovers when the job runs on the wrong day. Two tests guard both ends.

**The dashboard** stops hardcoding `toLocaleString("vi-VN")` in 10 places; the locale comes from `JavisI18n.locale()`.

**The `datetime-vn` plugin** reads the time zone and weekday names from config. The slug and tool names stay: renaming the
slug forces every running brain to migrate, in exchange for just a prettier name.

**The latch:** `test_locale.py` scans the code and goes red if anyone pins `timezone(timedelta(hours=7))` again
outside the three exempted places (where the default is declared and two plugins that may run outside the server process).

### 6.8. BATCH 5 - SKILLS AND DOCS (2026-08-14). Closes the vi+en roadmap.

**Per-language skill descriptions.** Frontmatter gains `description_<code>` and `name_<code>`; six
system skills already have an `_en` version. This is not cosmetic: a skill description is the **matching
surface** between the sentence the user just typed and the list of skills the router injects into the system prompt of every
engine, so in the same language the selection is sharper.

The most important rule is the **fall-back** rule: with no translation take the original, NOT empty. A Vietnamese
description can still route for someone asking in English (the model reads both), while an empty description
makes the skill vanish from the router. Thanks to this rule, translating skill descriptions is an **optional** step when adding a
language, and the playbook says exactly that.

Three accompanying fixes were needed, all of them silent breakages if skipped:

- `system_sync._cap_desc` now truncates **every** description key, not only the original key. The translation goes to
  the same place the original goes (the fixed head of every chat turn) so it has to obey the same 150-character cap;
  exempting it would reopen exactly the 61% token hole this cap plugs. In exchange, the multi-key scan must be
  confined to the frontmatter - the old single-key version avoided editing the skill body by mistake only because it took the first match.
- `POST /skills` reads the old frontmatter before overwriting. The form on the Skills page only sends
  `{name, description, group}`, so a blind overwrite means every Save click wipes the translations without
  anyone noticing.
- The cache key of `mcp_hub.discover_all` now includes the language. The tool list is shared across every
  turn so it reads the language from CONFIG rather than taking it from the chat turn; without the language in the key,
  after switching language you would still receive the skill list in the old language until the cache expires.

**Where language changes BEHAVIOR, not just text: `LazySkillSource._score` of Phase 8.** The router
in the system prompt hands the whole list to the model to read, so a description in the wrong language still picks the right skill.
The Phase 8 scorer has no model at all - it counts SHARED WORDS between the question and the description. Measured
on a skill that has both versions: the sentence `save a note fast` scores **0.65** against the English description and
**0.17** against the Vietnamese one, while the selection threshold is 0.24. That means before this batch, English
users were NEVER given a skill by Phase 8; it silently fell back to the full router - the right result,
but losing all of the tokens Phase 8 exists to save.

`refresh()` and `resolve()` take `lang`, and `lang` is IN the cache key. The language here comes from
config and NOT from the language detected per turn, on purpose: config is a single value
for the whole process, whereas a per-turn language would make the manifest and the capability registry rebuild
on every sentence. Picking the wrong language only leaves a skill short of the score and falling back to the router - lost
tokens, no wrong result.

**The marker labels in the prompt stay Vietnamese, on purpose.** `# === SKILL KHẢ DỤNG` ("AVAILABLE SKILLS"),
`# === BÂY GIỜ ===` ("NOW") and labels of the same kind are **measurement markers**: `context_runtime` counts tokens by exactly
that string, and `tests/fixtures/context_compiler_contract.json` pins them. Translating the labels by
language makes the measurement silently stop working for exactly the group of users just added. Only the **content**
follows the language, not the frame.

**Docs.** `README.en.md`, `QUICKSTART.en.md`, `docs/en/01-getting-started.md`,
`docs/en/README.md`. Translated by hand, not through the dictionary - docs have no fall-back mechanism so a
drifting translation drifts silently. `docs/en/README.md` says outright which pages are translated and which are not,
instead of leaving the reader to find out.

`docs/dev/them-mot-ngon-ngu.md` is the to-do list distilled from section 5: four required steps, two
optional ones, and a section on "what you do NOT have to do" - written out because that is where people tend to overdo it.

**Stale figures in the docs, fixed on the spot instead of duplicated.** The Vietnamese version still said 7 brains
(actually 10), 6 rail groups (actually 7), 23-24 docs pages (actually 27). Translating it as is would mint
one more wrong copy, so both sides were corrected. `test_tai_lieu_song_ngu.py` reads the numbers straight from
`PROVIDER_DEFS` and `RAIL_GROUPS` and checks them against both versions - copying the numbers into the test would create
a third place to drift.

**The latch:** `test_skill_da_ngon_ngu.py` (26 items, including a canary for a truncated translation and a canary that the skill
body is untouched) and `test_tai_lieu_song_ngu.py` (internal links, the language switch line, figures
matching the source code, no em dash in the English version).

### 6.9. PRE-MERGE REVIEW (2026-08-14). Three bugs that 231 tests did not catch.

Before putting this on `main`, a pass of FUNCTIONAL checking was run, independent of the test suite: throw real business
questions at each layer and see whether anything behaves absurdly. Three bugs came out, **none of them
turned a test red**, and the first one broke the headline feature of this very spec.

**Bug 1: English users were still answered in Vietnamese.** The English function-word list had
only 20 words and lacked exactly the group most common in short commands (`my`, `from`, `we`, `will`,
`show`, `give`). Measured on 18 common English business questions: **5 detected**. `show me my
revenue`, `list my pending tasks`, `check my inbox` all came back empty, meaning the session stayed in
Vietnamese. After the additions: **16/18**.

Why the whole test suite did not see it: every sample case in `test_da_ngon_ngu.py` was a fully
written sentence (`Can you show me the revenue breakdown by channel?`) - the kind that always contains a few function
words. Users type clipped sentences. The tests pin the right BEHAVIOR, but nobody measured COVERAGE.

**Bug 2: French/Spanish sentences typed without diacritics were recognized as Vietnamese.** `_CHU_NGOAI` only
catches foreign characters, but a European sentence missing its accents no longer has any foreign characters; the Vietnamese
function words without diacritics are full of two-letter words that coincide with European ones, so `les ventes du mois de juin sont bonnes` was scored as
Vietnamese on the strength of a single word `de`. This is a SERIOUS kind of breakage, not a politeness matter: misrecognizing it
as Vietnamese means taking the Vietnamese lexicon to judge a French sentence at the safety
gates - exactly what section 1 calls "half a lexicon is more dangerous than none".

Fixed with a THIRD layer of counter-evidence: `lang._TU_NGOAI`, the function words of the other Latin languages.
One word is enough to knock Vietnamese out of the scoring.

**Bug 3: an English concept question could not take the shortcut, while the equivalent Vietnamese one could.** The
`explanation` pattern of `lexicon/en.py` demanded an article (`what is a/an/the`), so `what is entropy in
information theory` fell into `intent_uncertain`. A difference by LANGUAGE rather than by
content: the same question asked in Vietnamese is cheap, asked in English it is expensive.

**Three traps hit while fixing, all self-inflicted and then caught by re-measuring:**

| What was added | What broke | Why |
|----------------|------------|-----|
| `het` into `_TU_NGOAI` | `xoa het don hang cua toi` lost its result | `het` is Vietnamese "hết" without diacritics (the input means "delete all my orders") |
| `week`, `report` into EN function words | a Dutch sentence became English | nouns travel across languages, only function words can tell them apart |
| `nào` into VI function words | a Portuguese sentence became Vietnamese | `nao` is "não" typed without its accent |
| loosening `what is` to drop the article | `what are my pending orders` SLIPPED through the gate | `my orders` is blocked, `my pending orders` is not - one adjective squeezed in and it escapes |

The fourth is the most dangerous because it slipped in the wrong direction: a sentence needing live data was allowed to
take the shortcut. Patched by allowing EXACTLY ONE word between the possessive and the noun in the `live_data` pattern.
Not loosened to two: `the difference between revenue and profit` is a purely conceptual question, and loosening further
would wrongly block exactly that.

**Bug 4, found last and the most serious: the FALSE-CLAIM catching gate missed the most natural English
phrasing.** The `FALSE_ACTION` pattern allowed EXACTLY ONE auxiliary slot (`have` OR `just` OR `already`),
so `I have created the order` was caught while `I have **already** sent the report` slipped through. This is the
gate that stops Jarvis 007 from claiming it did something the read-only path does not allow, so a miss here means the guardrail
silently stops working.

The Vietnamese version is not affected because Vietnamese rarely stacks auxiliaries ("đã vừa gửi" - "already just sent" - nobody says it).
So the bug exists in only ONE language - exactly the kind of drift the multilingual layer has to go looking for actively,
because it never reveals itself in the original language.

**Remaining, known and accepted:** a very short Vietnamese sentence without diacritics that contains no function word
(`so sanh doanh thu 3 kenh`, meaning "compare revenue of 3 channels") still comes back empty. It errs in the SAFE direction -
the session keeps the language already in use, and the default is Vietnamese, so the user sees nothing different.

**The latch:** `test_do_chinh_xac_ngon_ngu.py`. It differs from `test_da_ngon_ngu.py` in that it measures COVERAGE
on a basket of real sentences instead of pinning behavior on a few sample cases, and that basket **keeps even the sentences
that are currently failing** - dropping the hard sentences to reach the score is measuring yourself with a bent ruler.

### 6.10. SLIMMING DOWN (2026-08-14). Handing the reply language back to the model.

The repo owner asked the right question right after the review: if the user types in some language, the answer goes in that language,
so why detect it ourselves? The model already does that. Measuring again shows the repo owner was right, and the evidence is
right in the numbers of section 6.9 itself:

| | Our detector | The model |
|---|---|---|
| English, real questions | 16/18 | follows correctly |
| Thai, Japanese, French, Spanish | **always answers in Vietnamese** | follows correctly |
| Adding a language | edit the registry + re-measure | nothing to do |

The second row is the deciding one. The detector RECOGNIZES Thai (0.97) and still answers in Vietnamese,
because `th` is not in the registry so `chuan_hoa` (normalize) returns empty and the whole chain falls back to the default. In other
words we built a worse version of something that already exists for free.

**The new design, and it is much smaller.** `resolve()` now only handles the part the human PINS:

- if pinned (a command in the turn, the chatbot, Settings, the brain, the channel default) -> name that language;
- if not pinned but the user HAS text -> `theo_nguoi_dung=True` ("follow the user"), and the prompt tells the model to follow by itself;
- if not pinned and there is NO text at all (loops, reminders, Kanban, self-learning) -> there is nothing to follow, so it must
  name one, taken from `ui_lang` and then from the default.

**What was removed:** the entire session-stickiness layer - the in-RAM session store, the lock, the 2000-session cap,
the count of consecutive turns, `streak_best`, `NGUONG_DOI`, `SO_LUOT_DE_DOI`, and the `session` rung
in the priority chain. All of it existed only to make the detector stable enough to steer the reply language.
With the model steering there is nothing to flip-flop, so the whole mechanism became redundant.

**What was NOT removed, and why.** The detector is still needed exactly where **there is no model in the loop**:
the blocking gate reads the QUESTION (it runs before the model and must pick a lexicon itself), the false-claim catching gate reads
the ANSWER (it runs after the model), and the TTS voice (chosen by a language code in code). The four bugs in section
6.9 are therefore still worth fixing - the only difference is that they dropped from "breaks the headline feature" to "costs extra
tokens" and "picks the wrong voice".

`lang_cau_hoi` ("language of the question") is slimmer as well: it now only accepts what is detected from THIS turn itself, and stops borrowing the session
language when the sentence is too short. Borrowing means guessing, and a blocking gate that guesses wrong takes the wrong lexicon
to judge with - better to return empty and then fall back safely.

**One confirmation worth recording:** the chatbot's prompt island (`chatbot_runtime.build_bot_prompt`) had
already done this design from the start - pinned means name it, not pinned means "answer in EXACTLY the language
the customer is writing in". It was small so nobody thought of building a detection layer for it, and precisely because of that it
avoided that whole layer. The main path now follows it.

## 7. Six phases

This section is the FULL plan, to run after the smallest build in section 6 has reached its threshold. The smallest build
is itself a thin slice of Phases 0 and 1 plus a piece of Phase 2, so doing it is not
wasted work.

**Phase 0 - Measure and lock (half a day).** Add `server/lang.py`, `lang_registry.py` with exactly one `vi`
entry, add the `locale` group to config, write `lang` and `lang_source` into the trace. **Change no
behavior.** The lock is that every old test stays green.

**Phase 1 - Reply language (2 days).** The LANGUAGE block, fix `CLAUDE.md` rule 5 together with the 4 prompt places
that force Vietnamese, `dong_ho()` by language, `resolve_reply_lang()` with all 7 priority levels, sticking to the
session, STT and TTS by language, the `ngon_ngu` field for chatbots. Add English to the registry.
**The UI stays completely Vietnamese.** This is the phase most users call "it has multilingual
support", and it is the cheapest phase.

**Phase 2 - Lexicon and safety gates (2 to 3 days).** Extract the regexes into `lexicon/vi.py` verbatim,
write `lexicon/en.py`, implement the fallback rule by gate kind, and the auxiliary model infrastructure for error-catching gates.
**Do this BEFORE the UI part**, because this is the layer that breaks silently, whereas the UI breaks visibly.

**Phase 3 - UI i18n (4 to 5 days, can be spread out).** The `i18n/index.js` infrastructure, extract `vi.json`,
translate `en.json`, migrate by traffic: chat -> rail -> Settings -> the rest. Error codes for server
errors, endpoint by endpoint. The language picker on the Settings page.

**Phase 4 - Locale (1 day).** `localefmt.py`, replace the 6 UTC+7 places, currency, `describe_cron` by
language, `toLocaleString` by locale, the `datetime-vn` plugin reading the configured time zone.

**Phase 5 - Skills and docs (1 day).** The `description` map for the 4 system skills. Translate by hand
`README.md`, `QUICKSTART.md`, `docs/01`. Write the `docs/dev/` section "add a language" pointing back to section 5
of this spec.

**Suggested order to ship something usable**: Phases 0 to 2 as one complete build (Jarvis 007 answers in the right
language, the safety gates are not disabled), then Phase 3 at a sustainable pace, then Phases 4 and 5. A total of
about two weeks of focused work.

## 8. Testing

The existing test suite lives in `tests/python`, `tests/js`, run through `tests/run.py`. Add:

- `test_lang_resolve.py` - all 7 priority levels, preventing flip-flopping, sticking to the session.
  **[CORRECTION 6.10]** In practice merged into `test_da_ngon_ngu.py`, and the "preventing flip-flopping
  / sticking to the session" part is gone: with the model following the user there is nothing to flip-flop.
  Instead the test pins two things - pinned means name it, not pinned means tell the model to follow by itself.
- `test_lang_registry_invariant.py` - **scan the code for a hardcoded `lang == "vi"` or `"vi-VN"` outside the
  registry, and go red when found.** This is the latch that keeps extensibility from eroding.
- `test_lexicon_parity.py` - every set name in `lexicon/vi.py` must be present in every other lexicon.
- `test_lexicon_degrade.py` - a language with no lexicon: gates that expand privilege must REFUSE, gates that
  catch errors must call the auxiliary model or mark `unverified`, and must not quietly let it through.
- `test_vi_behavior_frozen.py` - re-run exactly the existing Vietnamese case set after extracting the regexes, and the
  results must match bit for bit.
- `tests/js/test_i18n.mjs` - extra keys, missing keys, no HTML in the dictionary, and **no Vietnamese text
  in a migrated file**.
- `test_prompt_lang_block.py` - exactly one LANGUAGE block, the right language, with a `nudge` when the engine is weak.

## 9. Risks and traps

- **Safety gates turning off silently.** The biggest risk of the whole spec. The only reliable defense
  is `test_lexicon_degrade.py`, plus writing `unverified` to the trace so it can be seen in the field.
- **Language detection flip-flopping.** Vietnamese people typing Vietnamese without diacritics mixed with English is an everyday
  occurrence. The two-turns-in-a-row rule plus the confidence threshold is meant to handle this case; there must be a test with
  real mixed sentences.
- **Weak models drifting into the prompt language.** The `nudge` exists, but it must be tried by hand on Groq and Ollama
  Cloud before declaring Phase 1 done.
- **UI translation regressing.** The next feature change will embed Vietnamese strings into a cleaned file if there is no
  test blocking it. The `I18N_MIGRATED` list must go in on the first day of Phase 3, not
  at the end.
- **Changing the time zone skews old statistics.** Stamp the time zone, do not rewrite history.
- **A brain mixing languages.** A user taking notes in Vietnamese and then asking in English is a normal case,
  not an error. The LANGUAGE block already says it: reading any language is fine, only ANSWER in
  one language.
- **Missing voice.** If there is no voice, say so plainly in the UI, do not read a Japanese sentence in a Vietnamese
  voice.

## 10. Three questions already settled

**Vietnamese or English as the source dictionary?** Settled: **Vietnamese**. `vi.json` is extracted from the code
that is running so it has 100% of the keys by definition, and every other language falling back to it never
has an empty text box. Taking English as the source would mean translating 3,520 strings BEFORE anything runs -
paying the entire cost up front in exchange for tidiness on paper.

**Should the UI language switch automatically by the browser's `Accept-Language`?** Settled: **suggest only
the first time**, never switch automatically. Jarvis 007 runs on a VPS and users open it from many machines and browsers; a UI that
jumps to another language because today they opened it on a different machine is the kind of "smart" that annoys people.
The first time, with nothing chosen yet, show a one-line suggestion; once chosen, remember it per device.

**Is the default reply language `auto` or `vi`?** Settled: **`auto`**. The output contract is already
`match_user` today (context_compiler.py:366) and it works well; making the default `vi` is
regressing a behavior that is already right with our own hands. Whoever wants to pin it can pin by brain or by bot.

## 11. Sources in the repo

- [Architecture overview](01-kien-truc.md) - where a chat turn runs through
- [Jarvis 007 CLI spec](2026-08-cli-spec.md) - the "third channel" precedent and the lesson of not duplicating a runtime
- [Dedicated bot spec](2026-08-bot-chuyen-trach-spec.md) - why a bot serving strangers needs its own
  assumptions
- [Adaptive Context Runtime spec](2026-08-adaptive-context-runtime-spec.md) - the Context Compiler,
  where the `match_user` output contract lives
- `CLAUDE.md` - the behavior rules; rule number 5 of the "Response principles" section is the first place to change
