---
name: Ingest Source
description: Digest one raw source into the Second Brain and distil it into wiki knowledge that compounds.
description_en: "Digest one raw source into the Second Brain and distil it into wiki knowledge that compounds."
group: AI
---

# INGEST - digest 1 source into the wiki (compounding)

## When to use

Activate when the user says things like: "digest this source", "process this article into the
wiki", "read this file and write down the knowledge", or when a new file is dropped into `sources/`.

The skill follows the vault's 3 disciplines exactly.

Read the vault schema (`CLAUDE.md`/`AGENTS.md` at the brain root) first; this is the operational version of the INGEST operation.

## Before you start
- Check the source frontmatter: `status: processed` -> STOP, say it was already processed, ask whether to re-ingest. `unprocessed`/missing -> go ahead.
- Classify the length. A long source (>= ~10,000 lines / a book / a transcript) -> a 3-pass approach is MANDATORY:
  1. Skim and build a table of contents by line numbers (e.g. "1-1300: introduction"). Ask the user to confirm the focus.
  2. Read each section in depth, ~1,000-1,500 lines at a time, and write the wiki IMMEDIATELY for each section (do not compress the whole file in one go - it loses 25-40% of the detail).
  3. Ask yourself 5 questions about different areas; if the wiki cannot answer one, do an extra scan of that area.

## Steps
1. Read the source (with images if any).
2. Summarize 3-5 key points; extract insights/frameworks; connect them to existing concepts.
3. Decide the wiki pages: which are new and need creating / need updating / need merging (read `wiki/index.md` to dedupe).
4. Write/update the wiki (1 page = 1 idea, with `[[...]]` links back to related pages) - FOLLOW THE 3 DISCIPLINES:
   - Hard citation: end every specific sentence with `[[Source]]`.
   - Target vs actual: label with "(target)" / "(actual as of ...)" / "(needs verification)".
   - Contradiction with an old page: add `## Mâu thuẫn` ("Contradiction"; keep both views + sources) + append to `wiki/_open-questions.md`, do NOT overwrite.
   Beyond the 3 disciplines, every page must be SELF-CONTAINED in context (contextual retrieval - a page detached from its source must still be understandable and findable):
   - Open the page with 1-2 positioning sentences: what this concept is, which topic/source it belongs to, when to use it. Especially when ingesting a long source section by section - a page from the middle of a book without a positioning sentence is unreadable on its own later.
   - Add `aliases: [other names, abbreviations, English terms]` to the frontmatter - so that later a question using different words is still caught by grep/search.
5. Update `wiki/index.md` (add a link line + a 1-line description).
6. Set the source to `status: processed`, `processed_at`, `wiki_links: [...]`. If it is not worth putting in the wiki -> `status: skipped` + `note`.
7. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <source name>` + source/created/updated/insight.
8. Propose a task if the source opens up an action (propose only). Short report: summary + pages touched + insight + task.
