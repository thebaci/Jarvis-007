# Team chat T4: long history, in-team search, performance measurement (0.124.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) sections 12.5, 17, 19 (row T4); case TC38. Stacked on T3 (PR #640).

Version 0.170.0 (adaptive team chat T4) adds the "Always kept despite long history" part, operations checks, measurements with a fake engine and the rollback
chain: [team-chat-t4-ops.md](team-chat-t4-ops.md), [team-chat-t4-bench.md](team-chat-t4-bench.md).

## Flow

1. **Code-built summary of the older part.** When a team session is longer than the history window (20 messages, 8,000 characters), a member's turn gets an extra block "Tóm tắt phần cũ của nhóm (máy tự tóm, không phải model)" (Summary of the team's older part, summarized by machine, not by a model; kept in Vietnamese as the code emits this prompt heading):
   - the number of messages older than the window;
   - a reminder that pinned decisions are still in the decision ledger;
   - at most 8 recently finished jobs (newest first), each with a 160 character excerpt of the result.

   The block only takes the team's own data, at most 2,000 characters, no model call, no turn opened.
2. **Search in the team.** The magnifier button at the top of the chat frame opens a search box. How it searches:
   - matches every word, ignoring case and Vietnamese diacritics ("mat dien" matches "mất điện", "deu" matches "ĐỀU"; these are Vietnamese examples that show the diacritic-insensitive behavior);
   - newest first, at most 50 results;
   - each result has the sender and an excerpt around the match;
   - never mixes in another team.
3. **Jump to an old message.** Clicking a result loads the chunk of messages ending at exactly that message and highlights it. The banner "Viewing an old message" has a **Back to latest** button. While viewing an old message, new incoming messages are not inserted into the middle of the old chunk.

## Code map

| Part | File | What it does |
|---|---|---|
| Session store | `server/sessions.py` | `team_message_count`, `fold_text` (strips diacritics, including đ, casefold), `team_search` (reads by session index, filters in Python because SQLite's LIKE only ignores case for ASCII; scans at most the 50,000 newest messages) |
| Runner | `server/team_runner.py` | `_older_summary` (placed before the recent history block in `_context`), `search` (excerpt around the match); constants `SUMMARY_JOBS`, `SUMMARY_RESULT_CHARS`, `SUMMARY_CHARS` |
| Route | `server/team_api.py` | `GET /teams/{id}/search?q=&limit=` (a query under 2 characters gives 400, another brain gives 404); jumping to a message reuses `GET /teams/{id}/messages?before_ts=&before_id=` |
| UI | `dashboard/teams.js`, `console.css`, i18n | `searchResultsHtml`, `drawSearch`, `runSearch`, `jumpTo`; a separate search area under the chat header (not redrawn when new messages arrive) |
| Measurement | `tools/team_perf_bench.py` | Builds a temporary state, calls the real routes through TestClient, prints the median and p95 along with the measuring machine |

## Measurements (local machine, NOT a VPS)

Machine: Windows 11 (10.0.26200), Intel64 Family 6 Model 165, 8 threads, Python 3.12.10. Two kinds of measurements are recorded separately (spec 17). Raw files: `exports/reviews/team-t4-perf/`.

**Server-side API** (`tools/team_perf_bench.py`, in-process TestClient, 20 calls per route):

| Route | 50 teams, 5,000 messages: median / p95 (ms) | 1 team, 5,000 messages: median / p95 (ms) |
|---|---|---|
| `GET /teams` | 14.2 / 19.6 | 7.9 / 8.5 |
| `GET /teams/{id}` | 25.4 / 32.3 | 28.1 / 42.8 |
| `GET /teams/{id}/queue` | 14.1 / 16.7 | 16.9 / 26.9 |
| `GET /teams/{id}/messages` (first page of 30) | 11.6 / 17.1 | 11.9 / 12.9 |
| `GET /teams/{id}/messages` (200) | 17.0 / 25.4 | 15.7 / 19.2 |
| `GET /teams/{id}/search` | 15.0 / 17.3 | 32.2 / 53.0 |
| `GET /teams/{id}/turns` | 10.3 / 12.4 | 10.0 / 11.5 |

Opening a team only loads the first page: 30 messages, `has_more=true`.

**Browser:** drawing 200 team messages into the chat frame (building the HTML, assigning `innerHTML`, one layout read), 10 times, on the real Teams page of the sandbox, Chromium in the Claude desktop app, a 1280x860 viewport. Median 87.7 ms, slowest 112.3 ms.

**VPS: not measured.** Spec 17 and the GOAL need separate approval from the project owner before running on a VPS; the numbers above must not be used to conclude anything about the VPS.

## Verdicts

- The code-built summary of the older part only uses finished jobs and the message count, and does not summarize the conversation content (summarizing content needs a model). Cost if wrong: old exchanges that did not become jobs only survive through the decision ledger and the owner's search box.
- Search filters in Python (reading by session index) instead of FTS5: fast enough at 5,000 messages per team (median 32 ms), and it adds no virtual table to the shared session store. Cost if wrong: a team with tens of thousands of messages will be slower, and then FTS5 should be added.
- Jumping to a message reuses the existing message page cursor (a chunk ending at that message); there is no "load newer messages" from an old chunk yet, replaced by the Back to latest button.

## Final review (fresh reviewer, strongest model)

Verdict "Ready with fixes": 0 Critical, 1 Important, 7 Minor. All eight fixed:
- **Important:** after jumping to an old message and then sending a message or filtering jobs, the "Viewing an old message" banner stayed and the new message (the assistant's reply) was not appended. Now every load of the latest chunk leaves the old-message view.
- The excerpt was offset when a message was typed with combining characters (NFD) or had characters that change length under casefold: normalize to NFC, then fold character by character with a position map.
- Search read up to 50,000 full rows inside the session store's shared lock: now it reads in batches of 2,000 rows containing only id and content, stops once there are enough results, at most 20,000 messages; the full message is only read for matching messages.
- The summary sentence said "above" while the history is below; there is a separate sentence for when the latest message is so long that no history shows.
- A leftover search box on the create-team form; the "Back to latest" banner was scrolled out of view (now it sticks to the top of the frame); the search button was narrower than 44px on phones; search results and jump-to responses that came back late after switching teams (now dropped).

Cases #2 to #4 in `test_team_history.py`, #1, #5 to #8 in `test_teams_ui.js` were red first, then green (the UI cases are source checks, not yet re-inspected in a browser).

## Checks

| Command | Result |
|---|---|
| `tests/python/test_team_history.py` | summary (only when over the window, the count of old messages, finished jobs newest first, no mixing with other teams, character ceiling, no turn opened), search (no diacritics, every word, đ becomes d, the right team, excerpt around the match, too short a query, limit, newest first), first page of 30 messages |
| `tests/python/test_team_api.py` | the search route: 200, no mixing teams, 400, 404 |
| `tests/python/test_team_perf_bench.py` | the measuring script runs, records the machine and the kind of measurement |
| `tests/js/test_teams_ui.js` | search results are escaped, the jump button, highlighting, the old-message banner, CSS `[hidden]`, 44px |

**UI smoke** (sandbox port 7788, team paused, daily cap 0): searching "mat dien" finds the message "mất điện"; clicking jumps to it and highlights it; Back to latest returns to the latest chunk.
