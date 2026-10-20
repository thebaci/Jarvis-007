# Adding a language to Jarvis 007

***Tiếng Việt** · [English](adding-a-language.md)* (the language switcher keeps the native name "Tiếng Việt", meaning "Vietnamese")

This document is the **acceptance test** for the whole multilingual layer. If adding a language
forces you to edit a file that is not on the list below, the architecture is broken somewhere:
**fix the architecture first, do not quietly patch one spot and move on**.

The full design lives in `docs/dev/2026-08-da-ngon-ngu-spec.md`. This is the to-do list.

Running example throughout: adding **Thai (`th`)**.

---

## READ FIRST: Jarvis 007 already answers in Thai

Without registering anything, a user who types in Thai still gets an answer in Thai. Since 0.35.0,
the REPLY language is handled by the **model**: the prompt tells it to follow the language the
user just wrote in, and it can do that for every language.

So what does registering get you? Exactly four things, all in places where **there is no model
in the loop**:

| What you get | Without registering |
|--------------|---------------------|
| Translatable on-screen text | the interface shows English (since 0.66.0; Vietnamese before that) |
| A TTS voice in the right language | read aloud with the Vietnamese voice, sounds like a broken machine |
| Default time zone, currency and number format | the Vietnamese ones, until the user changes them |
| The token-saving shortcut can switch on | still works, only costs more |

In other words this is work you **should** do, not work you **must** do before Jarvis 007 can speak
that language. Do not make anyone wait for all four steps below before inviting Thai users in.

---

## Four required steps

### 1. Declare the language in the registry

In `server/lang_registry.py`, add an entry to `LANGS`:

```python
"th": Lang(
    code="th", native="ไทย", english="Thai", script="thai", rtl=False,
    stopwords=("และ", "ที่", "เป็น", "ของ", "ไม่", ...),   # function words, used for DETECTION
    request_words=("ช่วย", "อยาก", ...),                    # words that open a request sentence
    stt="th", tts={"edge": "th-TH-PremwadeeNeural", ...},
    tz_default="Asia/Bangkok", currency="THB", first_day=0,
    number_locale="th-TH", plural=True,
    nudge="...", weekdays=(...), clock_template="...",
    lang_directive="Reply in Thai.",
),
```

Two fields that people tend to get wrong:

- **`stopwords`** are the evidence `lang.detect()` scores against, and the detector now only
  serves the SAFETY GATES and the VOICE; it no longer decides the reply language. Pick function
  words that are **common and distinctive** for that language, and **only function words, never
  nouns**: nouns cross languages (a trial once added "week" and "report" to English, and Dutch
  sentences turned into English). Also avoid words that collide with Vietnamese typed without
  diacritics; see `lang._TU_NGOAI` for the list of words already excluded and why.
- **`weekdays`** follow `datetime.weekday()`, so **0 = Monday**. Cron uses 0 = Sunday.
  `cron_util._ten_thu()` already corrects for this offset; do not correct it a second time.

For a non-Latin script, also add its Unicode range to `lang._KHOANG_CHU` (Thai is already
there). That table is checked in **priority order**, not first match wins: Japanese must come
before Chinese because Japanese text mixes kanji with kana.

### 2. Copy and translate the interface dictionary

```
cp dashboard/i18n/vi.json dashboard/i18n/th.json
```

Then translate the values. **You do not need to translate everything at once.** Since 0.66.0 a
missing key falls back to `en`, then `vi`, and only then to the key name itself - the interface
never breaks, it is just mixed-language until the translation fills in.

Two technical keys must be edited: `_meta.name` (the name shown in the picker) and
`_meta.number_locale`.

### 3. Write the lexicon for the safety gates (**optional, but read this part carefully**)

`server/lexicon/th.py`, with all 12 sets named in `lexicon.BAT_BUOC`.

**Not writing it is fine. Writing HALF of it is more dangerous than not writing it.**

This is the easiest place to go wrong in the whole multilingual layer, so here is why:

- **No `th.py`**: `lexicon.get("th")` returns `None`, the gates know they are blind, the
  token-saving shortcut switches itself off, and the safeguard drops down to the auxiliary
  model layer. Jarvis 007 runs **correctly**, it just costs more.
- **A `th.py` that is missing the DENY set**: the gate believes it can read Thai. A sentence that
  matches ALLOW goes straight through, and nothing stops it. **A leak, and a silent one.**

So either write all 12 sets, or do not create the file. `lexicon/__init__.py` checks the number
of sets at load time, and the test `test_lang_bat_bien.py` guards the same thing at both ends.

Writing it after real users have arrived is fine - that is the right order, not laziness.

### 4. Run the tests

```
python tests/run.py
```

`test_da_ngon_ngu.py`, `test_lang_bat_bien.py` and `test_locale.py` compare keys across the
dictionaries, check the registry invariants, and guard the spots that tend to grow back
(hard-pinned UTC+7, hard-coded `lang == "vi"`).

---

## Optional steps, fine to do later

### 5. Skill descriptions per language

In `SKILL.md`, add a `description_th` key (and `name_th` if the name also needs translating)
next to the original:

```yaml
---
name: Notes
description: Lưu tin nhắn hiện tại nguyên văn vào sources/ ...   # original, in Vietnamese: "Save the current message verbatim into sources/ ..."
description_en: Save the current message verbatim into sources/ ...
description_th: ...
group: AI
---
```

If it is missing, it falls back to the original `description`. A skill description is the
**matching surface** between what the user just typed and the skill list, so the same language
routes more sharply - but a different language still works.

A translation is subject to the same `SKILL_DESC_MAX` cap (150 characters) as the original,
because it goes into the same place in the prompt. `system_sync._cap_desc` trims every
description key, not only the original one.

### 6. Server-side text, the Connections catalog, the sample brain

Since 0.67.0, server-side text follows the interface language of the DEVICE making the call
(the `javis_lang` cookie, set by `dashboard/i18n/index.js`). Anything with no Thai version shows
in English, so none of the steps below is required to invite Thai users in.

- **Server messages** are written in two versions right where they are used:
  `localefmt.chu("Đã lưu", "Saved")` (the first is the Vietnamese text "Đã lưu", meaning "Saved"). There is no room for a third version yet, so Thai shows English. When it is really needed,
  extend `chu()` with a SEPARATE parameter that takes a `{code: text}` map (not `**kwargs`:
  `**bien` is already the variables filled into the text), and do not branch with
  `if lang == ...` at the call site.
- **Connections catalog:** copy `system/mcp-catalog.en.json` to `system/mcp-catalog.th.json`, then
  translate the text. Wizard steps and install links are matched by POSITION, so keep the exact count.
- **Seed files of a new brain:** add a `"th"` version for each entry in `HAT_GIONG` in
  `server/brain_seed_i18n.py`.

### 7. Documentation

User docs are translated by hand, not through the dictionary. Since 0.66.0 the root README
(`README.md`) is the **English** one; README translations live in `docs/i18n/<code>/README.md`
(Vietnamese: `docs/i18n/vi/`), and the language bar at the top of README.md must list the new
language. The other docs still follow the old convention: `QUICKSTART.en.md`, `docs/en/*.md`.
Each version carries a link to the other at the top of the file.

---

## What you do **not** need to do

Listed here because this is where people tend to do extra work:

- **Do not** translate the system prompt or `CLAUDE.md`. The prompt stays in Vietnamese; the block
  `# === NGÔN NGỮ ===` (the "LANGUAGE" block) at the end is what decides which language Jarvis 007
  answers in. The model can read the Vietnamese instructions and answer in Thai - that is
  normal, and one prompt set per language is one more set to drift apart.
- **Do not** translate the marker labels in the prompt (`# === SKILL KHẢ DỤNG` meaning "available skills",
  `# === BÂY GIỜ ===` meaning "now", ...). They are **measurement markers**: `context_runtime`
  counts tokens by exactly those strings. Translating them makes the measurement silently stop
  working for exactly the group of users you just added.
- **Do not** derive locale from language. Reading the interface in English while sitting in
  Vietnam is perfectly normal; time zone and currency live in `server/localefmt.py` and are
  chosen separately.
- **Do not** write `if lang == "th"` anywhere except `lang_registry.py`. A test guards this.

---

## REGISTERED languages

A reminder: this is NOT the list of languages Jarvis 007 speaks. Jarvis 007 can answer in any language.
This is the list of languages that already have their own interface, voice and gates.

| Code | Name | Interface dictionary | Gate lexicon | Skill descriptions |
|------|------|----------------------|--------------|--------------------|
| `vi` | Tiếng Việt (Vietnamese) | complete | complete | original |
| `en` | English | complete | complete | complete |
