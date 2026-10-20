---
name: Lint Wiki
description: Audit the health of the Second Brain wiki and hand back a list of problems. Never mass-edits on its own.
description_en: "Audit the health of the Second Brain wiki and hand back a list of problems. Never mass-edits on its own."
group: AI
---

# LINT - wiki health check (CHECKLIST only)

## When to use

Activate when the user says things like: "health check the wiki", "lint wiki", "is anything wrong with the
wiki", "audit the brain".

Scan `wiki/` for 8 kinds of problems:
1. Contradictions between pages (including a `## Mâu thuẫn` ("Contradiction") section recorded earlier and not yet resolved).
2. Stale claims (an old page not updated to match a newer source).
3. Orphans (no inbound `[[link]]`).
4. Missing pages (a concept mentioned in many places but with no page of its own).
5. Broken `[[wikilink]]` (pointing to a file that does not exist).
6. Duplicates (2 near-identical pages -> propose a merge).
7. Gaps (thin areas of knowledge that need more sources / a web search).
8. Open questions that have sat for a long time in `wiki/_open-questions.md`.

GOLDEN RULE: only RETURN A NUMBERED LIST. ABSOLUTELY DO NOT fix 50 places at once on your own. The user prioritizes, then orders fixes one by one (to avoid losing control of the audit).
