# Dev conventions (for Claude Code sessions working on this repo)

This file was split out of `CLAUDE.md` on 2026-09-22. Reason: `CLAUDE.md` is the system prompt that goes into
EVERY Jarvis 007 chat turn and has a budget ceiling (`tests/python/test_prompt_budget.py`), while dev
conventions are something Jarvis 007 users never need. Kept here, it can be as long as it needs to be without
taxing any chat turn.

## Branches, PRs and merging

- Keep developing on a dedicated branch and open a PR as usual.
- Once CI is green, **merge straight into `main`** (rebase/squash, keep history linear; this repo does not
  use merge commits). The repo owner allowed this from 2026-07-30 so changes can be tried on the VPS right away,
  with no need to ask each time. The only difference from the usual flow is that the merge does not wait for
  anyone to review it by hand.
- **Red CI means DO NOT merge.** Make it green first.
- The repo owner repeated on 2026-09-26: **every merge into `main` must ship a new version number**,
  bump `VERSION` and update `CHANGELOG.md` in the same PR so other machines can tell an update is
  available. Before merging, check that this number is greater than the current version on
  `origin/main`; after merging, confirm the build/release flow for the update succeeded.
  Do not count a code merge as released if the new version has not been published.

## Reserve the version number BEFORE coding

Requested by the repo owner on 2026-09-22, after three collisions in a row: 0.63.3, 0.63.8 and 0.63.10 were all
taken by another PR that merged first. The last one happened when the PR had already passed all of CI, and had
to be rebased and renumbered from scratch.

Root cause: this repo often has several Claude Code sessions running in parallel. A number picked at the end
of the work is a number picked from stale information.

Procedure:

1. `git fetch origin main`, read `VERSION` on `origin/main`.
2. List the **open** PRs and read the version number in their titles. Every number there counts as **already
   taken**, even if `main` does not carry it yet.
3. Take the next free number after all of them.
4. Push the commit that bumps `VERSION` + `CHANGELOG.md` **at the very start of the branch**, with a draft PR
   carrying that number in the title. This is the actual reservation: the next session can read it in step 2.
   The body of the changelog can be written later.
5. Only then write code.

Two situations come up often:

- **`main` still moves past the reserved number.** Rebase and renumber. Only `VERSION` and `CHANGELOG.md`
  conflict, so it costs exactly one beat, not a redo of the change.
- **An open PR carries a stale number** (for example 2026-09-22: PR #417 still held 0.64.1 while #416 had
  already released that exact number). A number like that says "someone is aiming for it", not "it is still
  valid". The session that owns that PR must renumber before merging.

This convention reduces collisions but does not eliminate them: two sessions that start a few seconds apart
can still read `main` at the same time and pick the same number. What it avoids is the last-minute collision,
when the PR is already green and everything is done.

## Text shown on screen (from 0.67.0)

The UI runs in English for users with an English browser, so NEW text written for the screen must not be
bare Vietnamese:

- **Dashboard (JS, HTML):** add the key to BOTH `dashboard/i18n/vi.json` and `en.json`, and call `t("...")`
  (or the file's own guard function `tw()`). `tests/js/test_i18n.mjs` goes red when a JS file has Vietnamese text in
  running code that is not on the data-exception list.
- **Server:** text returned to the screen (errors, messages, labels) is written as `localefmt.chu("Vietnamese text",
  "English")`. With no request (Telegram, background jobs) it follows the machine's `ui_lang`.
- **Do NOT translate:** prompts and tool descriptions sent to the model, regexes that match what the user types or
  says, logs, and content written into the user's brain. The reason is in `docs/dev/them-mot-ngon-ngu.md`.

## Explanatory text folded into the (i) button (from 0.214.0)

The repo owner decided on 2026-10-18: "there are too many lines of explanation, I want those explanatory lines
tucked into an (i) rather than spilled out in the open". A hard rule for EVERY dashboard screen:

- **Only what needs to be seen and clicked stays on the surface:** titles, labels, statuses, numbers, input
  fields, buttons. A short secondary line (up to about 100 characters, one sentence) may stay out in the open if
  people would not know what to click without it.
- **Any explanation longer than that** (why, caveats, step-by-step instructions, risks, the difference between two
  options) **goes inside the (i) button**: `JavisInfo.btn(t("info.more"))` next to the title or label,
  `JavisInfo.body(...)` right after it, or `JavisInfo.pair(html, label)` when there is no title to sit beside
  (`dashboard/info-tip.js`). Static HTML uses the same two classes `info-i` / `info-body`, with a template at the
  top of that file. It opens only on click, with text in a 16px block.
- **Not folded:** errors and confirmations that appear after the user clicks (they are waiting for exactly that
  sentence), placeholders, and content the user opens to read (update log, chat content, notes). For warnings
  about money or data loss: leave one short sentence stating the risk outside, and the explanation still goes in
  the (i).
- **Descriptions sent by the server** (plugins, channels): the card shows at most two lines, with the full text in
  the (i).
- `tests/python/test_info_tip_rule.py` goes red when a string over 100 characters is rendered outside an (i)
  block. A legitimately long string (error, confirmation...) goes into `tests/python/info_tip_allow.json` with a
  reason; do not put an explanation in there just to get past the test.

## Writing CHANGELOG.md

The repo owner reads the update log on a portrait screen (2026-08-12), so write FOR SOMEONE READING ON A
PHONE, not for a developer reading the diff:

- At most 3 to 4 bullets per version, each 1 to 2 sentences.
- Say WHAT THE USER SEES DIFFERENTLY, not function names and file paths. Technical detail belongs in the commit
  body and the PR description.
- Use `**` and backticks sparingly. The page renders markdown, but a line dense with symbols is tiring to read on
  a narrow screen.
- **From 0.68.0 write TWO versions:** a Vietnamese block in `CHANGELOG.md` (the original) and an English block
  with the same version number in `CHANGELOG.en.md`, with the same number of `###` groups. The Updates page shows
  the English version to English-reading devices. `tests/python/test_nhat_ky_song_ngu.py` goes red when a version
  from 0.66.0 onward lacks an English version, so the version-number reservation block must also exist in both
  files.

## Language of commits, PRs and code (from 0.68.0)

The repo is open to international contributors, so everything OUTSIDERS READ is written in English:

- **Commit messages, PR titles and descriptions:** English.
- **All newly written code is in English** (decided by the repo owner on 2026-10-15): module, function and
  variable names, data fields, comments, docstrings, test names and the strings printed in `check(...)`, even when
  added to an old file that is written in Vietnamese. Do not retranslate old code you are not touching. Text shown
  to users goes through i18n (`vi.json` with diacritics, `en.json`). The old glossary of Vietnamese identifiers for
  foreign readers is at `docs/dev/GLOSSARY.md`, and the architecture is in `ARCHITECTURE.md`.
- **Keep Vietnamese:** `CHANGELOG.md` (the original, which the repo owner reads), this conventions file, the
  specs in `docs/dev/`, and prompts sent to the model (the reason is in `docs/dev/them-mot-ngon-ngu.md`).
- PRs from outside contributors do not need to touch `VERSION`/CHANGELOG: whoever merges bumps the number and
  writes the log.

## README translations and the quick-install guide (from 0.69.0)

- `README.md` and `QUICKSTART.en.md` (English) are the originals. The Vietnamese versions at `docs/i18n/vi/` and
  `QUICKSTART.md` are still edited by hand at the same time as before.
- The other versions at `docs/i18n/<code>/` (Chinese, Spanish, Japanese, Hindi, Portuguese, Korean, Russian,
  German, French, Indonesian) are MACHINE translations. The language picker bar is generated from the `LANGS`
  list in `tools/check_translations.py` with the `--bars` command; do not edit it by hand file by file. The first
  line of each file records the source file and its hash at the time of translation. Editing the English README
  does NOT require retranslating right away: the **Translations** workflow will warn which versions have gone
  stale. When retranslating, run `python tools/check_translations.py --stamp <file>` to update the hash.
- The animated figures in the README live in `docs/assets/diagrams/*.svg`: the text in the figures is English and
  shared by all translations. The figure captions (alt text) are translated per version.
- `tests/python/test_machine_translations.py` guards against dead links, broken anchors and long dashes in the
  translations, so run this test after retranslating.
- The server, the voice and the full guide documentation stay in English and Vietnamese only. The repo owner
  decided on 2026-10-03: add a FULL language (lang_registry) when a real user needs it. From 0.99.0
  (decided by the owner on 2026-10-12, accepting the German from @sirschnake) a DASHBOARD-ONLY translation
  (`dashboard/i18n/xx.json`) is accepted separately: it shows for browsers in that language and appears in the
  language picker, while the server stores `ui_lang` as English (`uiLangForServer` in console.js) so that Telegram,
  background jobs and the voice come out in English instead of falling back to Vietnamese.
