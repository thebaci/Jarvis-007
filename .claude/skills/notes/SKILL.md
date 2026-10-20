---
name: Notes
description: Save the current message verbatim into sources/ (images included), then distil it up to the wiki if it earns a place.
description_en: "Save the current message verbatim into sources/ (images included), then distil it up to the wiki if it earns a place."
group: AI
---

# NOTES - quickly save 1 note into the Second Brain (kept verbatim), wiki if worthy

## When to use

Activate when the user types the `/notes` command (web or Telegram), or says "save this note",
"jot this into the brain". This is the QUICK-CAPTURE version: save verbatim first, distil later
if worthy. Different from `ingest-source` (for a source already sitting in `sources/`, which always distils).

Read the vault schema (`CLAUDE.md`/`AGENTS.md` at the brain root) before writing.

## Where the note content comes from

- The "request" part the user types AFTER `/notes` = the note body. Keep it EXACTLY VERBATIM, do not edit,
  do not summarize, do not add or remove a single word.
- Files/images attached in the SAME message (paths are provided) = the note's documents.
- ONLY the current message. Do not pull in the previous answer or earlier turns.

## Steps

1. Identify the current brain folder: `sources/`, `attachments/`, `wiki/`.
2. Name the file: `sources/note-YYYY-MM-DD-HHmm-<first-few-words-without-diacritics>.md` (use the real date and time,
   taken via the datetime tool if available; the slug comes from the first ~4-6 words of the note, diacritics removed, joined with hyphens).
3. Write the source file with frontmatter:
   - `type: source`
   - `source_kind: own-note`
   - `status: unprocessed`
   - `created: <YYYY-MM-DD HH:mm>`
   - `tags: [note]`
   Body = the original text VERBATIM. For attached images: move/ensure the file is in
   `attachments/`, embed `![[image-name]]` in the body. If the file is already in `sources/`/
   `attachments/` because of a web upload, use that one, do NOT duplicate it.
4. Judge wiki-worthiness (same criteria as ingest-source): a reusable concept / framework / principle /
   procedure / insight -> WORTHY. Confessions, small chores, passing reminders, shopping
   lists -> NOT worthy.
5. If WORTHY: apply the INGEST operation - write/update `wiki/` pages with all 3 disciplines (every specific claim with
   `[[Source]]`; distinguish "(target)"/"(actual as of ...)"; a contradiction with an old page means
   adding `## Mâu thuẫn` ("Contradiction") + appending to `wiki/_open-questions.md`, do NOT overwrite). Every page self-contained in
   context (1-2 positioning sentences at the top) + `aliases:` if there are other names. Update `wiki/index.md`
   (add a link line + a 1-line description). Append to `wiki/log.md`:
   `## [YYYY-MM-DD] notes | <note name>` + source/created/updated/insight. Set the source
   `status: processed`, `processed_at: <...>`, `wiki_links: [...]`.
6. If NOT worthy: keep the source (`status: unprocessed`), do NOT touch the wiki.
7. Report BRIEFLY in spoken prose (no tables, no long dashes, no em dash): the note was saved to
   `[[source-name]]`; whether it went up to the wiki, and if so which page. If there is an image, embed it again with `![...](...)`
   so the user can see it.

## Scope

Writing `sources/` + `wiki/` is `safe` level, allowed to run because the user deliberately typed the command. This skill only
writes files in the vault; it does not need to call any outside tool.
