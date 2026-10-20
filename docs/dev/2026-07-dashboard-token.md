# Dashboard Token - Design (v1)

Date: 2026-07-18
Status: Spec, awaiting approval
Requested by: Minh Quy

## 1. Goal

A dashboard inside Jarvis 007 to track token consumption, able to answer 4 questions:

1. Overview: how many tokens this period, up or down against the previous period, and is it bloating abnormally.
2. Breakdown: where the tokens go the most - which provider (Claude / Codex / OpenRouter-API), which model, which project, and for Jarvis 007's own share, whether it is chat or hidden activity (loops, schedules, subagents).
3. Efficiency: is usage economical or wasteful (cache hit, tokens per session, output/input, converted cost).
4. Action: produce a few concrete suggestions to optimize (fewer loops, a cheaper model, splitting sessions, /compact...).

The main viewer is Minh Quy (human-facing). The aggregate endpoint can be reused later for a tool that lets Jarvis 007 itself read it, but v1 does not do that part.

## 2. Data sources and the historical truth

There are 3 sources, with different levels of readiness. This is the most important point of the design.

| Provider | Source | Token fields | History |
|---|---|---|---|
| Claude (Code + Jarvis 007 SDK) | `~/.claude/projects/**/*.jsonl` | input, output, cache_read, cache_creation (separate) + model, cwd, entrypoint, isSidechain, sessionId, timestamp, gitBranch | Complete, fully backfillable |
| Codex / ChatGPT | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | `total_token_usage` {input_tokens, cached_input_tokens, output_tokens, total_tokens} per session | Yes, backfillable |
| OpenRouter / OpenAI / Anthropic API (Jarvis 007 plain chat) | NOT stored today. `engine.py` extracts `usage` each turn and then throws it away; `conversations.db` has no token column | No history | Only from the moment logging is switched on (forward-only) |

Design consequence: Claude and Codex have numbers from history right away. The API branch needs a light logging sink plugged in, and the dashboard must say clearly "the API branch only has numbers from the day it was switched on".

### Claude JSONL field details (verified on the machine)

Each `type=assistant` line has:
- `timestamp` (UTC, suffix Z) - must be converted to local time (Asia/Ho_Chi_Minh) when splitting by day.
- `message.model`: `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-fable-5`, `claude-haiku-4-5-...`, `<synthetic>` (skip synthetic).
- `message.usage`: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `server_tool_use.web_search_requests/web_fetch_requests`.
- `entrypoint`: `sdk-cli`/`sdk-py`/`sdk-ts` (= Jarvis 007) vs `claude-desktop`/`claude-vscode` (= typed by hand).
- `cwd` (= project), `gitBranch`, `sessionId`, `isSidechain` (= subagent tokens).
- The project folder name is a slugified cwd; prefer reading `cwd` in the line to get the real project.

### Codex rollout details

A per-session JSONL file, with events carrying `total_token_usage` (cumulative per session) and `token_count`. Because it is cumulative, take the largest value or the last line of the session as the session total; take the timestamp from the file name / events to place it in a day.

## 3. Normalized schema (usage event)

Every source is reduced to one common record before merging:

```
UsageEvent {
  ts            : epoch (converted to local to bucket the day)
  provider      : 'claude' | 'codex' | 'api'
  engine        : original entrypoint (sdk-cli, claude-desktop, codex, openrouter...)
  model         : normalized model string
  project       : cwd, or '(codex)' / '(api)' if there is none
  session_id    : session id (to count sessions, join, dedup)
  source        : 'javis' | 'manual'      # Claude: by entrypoint; Codex/API = 'javis'
  activity      : 'chat' | 'background' | 'subagent' | 'manual'
  input         : newly loaded tokens (excluding cache)
  output        : generated tokens
  cache_read    : tokens read from cache (cheap)
  cache_create  : tokens that create the cache
  billable_in   : input + cache_read + cache_create  # total billed input
}
```

## 4. Source / activity classification (attribution)

- `source`: Claude by `entrypoint` (sdk-* = javis, desktop/vscode = manual). Codex and API are always = javis.
- `activity` for the Jarvis 007 part:
  - `subagent`: lines with `isSidechain = true` (tokens of a child agent running in the background inside any session).
  - `chat`: the `sessionId` of a Claude-SDK session is present in `conversations.db.cli_session_id` (that is, a session the user opened through the dashboard/Telegram).
  - `background`: a Claude-SDK session NOT in `conversations.db` (loops, scheduled reminders, self-improvement, cron). This is the "hidden activity".
  - `manual`: a hand-typed entrypoint.
- Loop vs schedule refinement (after v1): for now they are merged as `background`. To split out "how much does loop X cost", Jarvis 007 would have to label the session when it spawns it (for example by writing a map `sessionId -> {kind: loop, slug}` into a sidecar). Recorded as a v1.1 item, it does not block v1.

Join key: `conversations.db.sessions.cli_session_id` = `sessionId` in the Claude JSONL. Verified: 31 of 43 sessions have this key.

## 5. The set of metrics

### 5.1 KPI cards (top of the page, changing with the selected period + comparison with the previous period)

- Total tokens in the period (+ % delta against the previous period).
- Average tokens/day (run-rate) and the projection to the end of the period (if the period is not closed).
- Cache hit rate = cache_read / billable_in. The main efficiency metric.
- Number of sessions and average tokens per session (to spot bloated sessions).
- Output / input ratio.
- Estimated converted cost (see section 7).

### 5.2 Breakdown (charts)

- By provider: Claude / Codex / API (this is the main filter; choose a provider and the whole page filters by it).
- By source: Jarvis 007 vs typed by hand (applies to the Claude part only).
- By Jarvis 007 activity: chat / background / subagent.
- By model: a ranking of token-hungry models (with a converted-cost column).
- By project (cwd): top projects.
- Over time: tokens per day in the period (stacked by provider or by activity); plus a 24-hour heatmap to see which hours the most background work runs.

### 5.3 Automatic insights (a list of suggestions)

Generated from rules, each rule producing 0..n warning lines:

- The average cache hit of a project/session is below a threshold (for example < 50%) when the session is long -> suggest /compact or splitting the session.
- A `background` group (loops/schedules) takes a large share of tokens (for example > 25% of the period) with small output -> "hidden activity is eating a lot, review the frequency".
- An expensive model (opus) takes most of the tokens for short sessions/small jobs -> suggest a cheaper model.
- A session exceeds an absolute token threshold (for example > 1M billable_in) -> suggest splitting.
- Tokens/day this period exceed the previous period's run-rate by more than X% -> spike warning, pointing out the main source of the increase.

Thresholds live in config and can be adjusted.

## 6. Time periods and comparison

Period filter: today, yesterday, this week, last week, this month, last month, last 3 months, this year. Letting the user choose an arbitrary range (from/to) is a bonus.

Each period is automatically compared with the equivalent period right before it (today vs yesterday, this week vs last week, this month vs last month, 3 months vs the 3 months before, this year vs last year). The delta shows on the KPI cards.

Timezone: Asia/Ho_Chi_Minh. The Claude JSONL is UTC so it must be converted before bucketing by day, otherwise the "today" boundary shifts.

## 7. Converted cost (pricing)

A `pricing.json` file (unit price in USD per 1 million tokens) for each model: input price, output price, cache_read, cache_write. Estimated cost = input*price_in + output*price_out + cache_read*price_cacheread + cache_create*price_cachewrite.

Meaning: Claude/ChatGPT are subscription plans, so this is NOT real money, it is "if billed by API it would cost this much" - showing how much the plan is saving. For OpenRouter/API it is real money. The dashboard labels it clearly as "converted estimate" to avoid misunderstanding.

The price table needs a manual update when a new model appears; keep it in config, not hard-coded in scattered places.

## 8. Technical architecture

Matches the existing stack: FastAPI (`server/main.py`) + plain JS (`dashboard/`), no build tool.

### 8.1 `server/usage_index.py` (indexer)

- Scans the 3 sources. For each file, remembers the `(path, size, mtime)` already processed; reads only new or changed files (incremental parse). With 594MB / 1581 files, incremental is mandatory.
- Parse -> normalize to `UsageEvent` -> write into the SQLite `server/usage_index.db` (gitignored, it is derived data).
- Two tables: `files_seen(path, size, mtime, provider)` to know how far indexing has gone; `usage_events(...)` or a pre-aggregated table `usage_daily(day, provider, source, activity, model, project, input, output, cache_read, cache_create, sessions)` for fast queries. It may also keep the raw events for session drill-down; weigh the disk size.
- Query functions: `summary(period, compare, provider=None)` returns KPIs + breakdowns + timeseries; `insights(period)` runs the section 5.3 rules.
- Reads `conversations.db` (read-only) to get the set of `cli_session_id` used to classify chat vs background.

### 8.2 API branch logging (forward)

- `engine.py` already has 3 places with `yield {"type":"usage", ...}` (around lines 316, 492, 588). Add a function `usage_log.record(provider='api', engine, model, session_id, input, output, ...)` called at those points, appending to `server/logs/usage-api.jsonl` (append-only, crash-safe). The indexer reads this file as the 3rd source.
- Minimal engine change: one function-call line at each yield point. The main flow does not change.

### 8.3 Endpoints (FastAPI)

- `GET /usage/summary?period=&compare=&provider=&project=` -> JSON KPIs + breakdowns + timeseries.
- `GET /usage/insights?period=` -> the list of suggestions.
- `POST /usage/refresh` -> runs the incremental index, returns the number of newly processed files.
- (optional) `GET /usage/session/{id}` -> details of one session for drill-down.
- Protect with the same auth mechanism as the other dashboard routes.

### 8.4 Dashboard tab (UI)

- Add a "Token" tab to `dashboard/index.html` + the file `dashboard/usage.js` + styles in `style.css`.
- Components: a row of period filter chips; a provider filter dropdown/segmented control; a row of KPI cards; the breakdown charts; the timeseries chart + heatmap; the insights block.
- Charts: use a lightweight library that is already embedded (consider the one-file Chart.js, or hand-draw SVG to avoid adding a dependency). Decide at the planning step.
- A "Refresh" button calls `/usage/refresh` and then reloads the numbers.

## 9. v1 scope and what comes later

v1 (do now):
- Indexer for Claude + Codex (with complete history).
- Plug in forward logging for the API branch (numbers accumulate from the moment it is switched on).
- The full set of KPIs, breakdowns (provider/source/activity/model/project/time), basic insights, converted pricing.
- A dashboard tab with the full period filter + provider filter.

Later (v1.1+):
- Split `background` into loop vs schedule vs self-improvement (needs Jarvis 007 to label the sessionId when it spawns).
- Drill-down to each session.
- A tool for Jarvis 007 itself to read the token report through chat.
- Proactive alerts (push to Telegram on a spike).

## 10. Edge cases / risks

- Timezone UTC->local: getting it wrong shifts the day boundary. Must be tested.
- Codex `total_token_usage` is cumulative: do not add up every line, take only the session total.
- The `<synthetic>` model and lines missing usage: skip, do not count.
- A file that is being written (a running session): read the readable part, the next refresh makes up the rest. Do not lock the file.
- Index size: if raw events are kept, `usage_index.db` can get large. Consider keeping only `usage_daily` + per-session totals, and dropping old raw events.
- Dedup: the same requestId/uuid must not be counted twice on a re-parse. Use a natural key (the line uuid) or parse only unchanged files.
- Clean fork: `usage_index.db`, `usage-api.jsonl` are machine data, must go into `.gitignore`, never to git.

## 11. Testing

- Unit: the Claude parser (one sample line -> a correct UsageEvent), the Codex parser (takes the session total correctly), activity classification (chat vs background by presence/absence in conversations.db), period grouping + comparison, timezone conversion at the day boundary.
- Integration: run the indexer on a small fixture folder, call `/usage/summary` and check that the total matches the hand count.
- Run tests through the project's `.venv` (per the note: the system python lacks libs).

## 12. Task list (carried into the planning step)

1. `usage_index.py`: the SQLite skeleton + files_seen + incremental scan.
2. Claude JSONL parser -> UsageEvent (including entrypoint, isSidechain, cwd, cache).
3. Codex rollout parser -> UsageEvent (session total).
4. Activity classification through a join on `conversations.db`.
5. `pricing.json` + the converted cost function.
6. The `summary()` + `insights()` functions + period grouping/comparison + timezone.
7. `usage_log.record()` + plug in the 3 points in `engine.py` + a parser reading `usage-api.jsonl`.
8. Endpoints `/usage/summary`, `/usage/insights`, `/usage/refresh`.
9. The "Token" tab in the dashboard + `usage.js` + styles + choosing a chart library.
10. Unit + integration tests; update `.gitignore`.
```
