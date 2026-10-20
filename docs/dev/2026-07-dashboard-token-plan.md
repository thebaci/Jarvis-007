# Dashboard Token - Implementation plan

> **For the worker:** execute using superpowers:executing-plans (inline) or subagent-driven. Each task has a checkbox and ends with an independently testable deliverable. TDD, commit per task.

**Goal:** Upgrade the "Usage" page into a real token dashboard: filter by period (today ... this year), compare with the previous period, break down by provider/source/activity/model/project, cache hit, converted cost, and actionable insights - read from the raw Claude + Codex logs (which have history) and usage_store (the API branch, forward only).

**Architecture:** One indexer (`usage_index.py`) scans `~/.claude/projects/**/*.jsonl` + `~/.codex/sessions/**/rollout-*.jsonl`, parses incrementally (skipping unchanged files), classifies activity by joining on `conversations.db.cli_session_id`, and merges into the SQLite `STATE_DIR/usage_index.db`. The API branch (openrouter/openai/anthropic) has no raw log, so it reads from the append-only `STATE_DIR/usage-events.jsonl` that `usage_store.record()` additionally writes. The endpoints `/usage/summary|insights|refresh` serve a plain-JS dashboard tab (hand-drawn SVG, no new dependency).

**Tech Stack:** Python 3 + sqlite3 (standard library), FastAPI (already there), plain JS + SVG (already there). Tests: plain python scripts run through `.venv`, isolating their own temp dir (NO pytest).

## Global Constraints

- Absolutely NO em dash character (U+2014) in any file/code/comment. Use "-".
- Timezone for computing days: Asia/Ho_Chi_Minh (UTC+7). Claude JSONL is UTC (suffix Z), so convert before bucketing by day.
- Do not break the existing `usage_store.py` / `/usage` / "Usage" page (they keep working).
- Test following the project pattern: plain python script, `os.environ["JAVIS_STATE_DIR"]=tempdir`, run `cd server && ../.venv/Scripts/python.exe test_x.py`, exit code != 0 on failure.
- Data sources must be overridable through env for testing: `JAVIS_CLAUDE_PROJECTS_DIR`, `JAVIS_CODEX_SESSIONS_DIR` (defaults `~/.claude/projects`, `~/.codex/sessions`).
- Provider raw log = authoritative for `claude` + `codex`. `usage-events.jsonl` = authoritative ONLY for API providers (openrouter/openai/anthropic-api/oauth). No double counting.
- Do not commit derived data: add `.gitignore` entries for `usage_index.db*`, `usage-events.jsonl*`.
- Default STATE_DIR = the `server/` folder (config.py: `JAVIS_STATE_DIR` falls back to `__file__.parent`).

---

## File Structure

- Create `server/usage_parsers.py` - pure parse functions (Claude line, Codex file, api-event line) -> UsageEvent dict. No I/O other than reading the file whose path is passed in.
- Create `server/usage_pricing.json` - price table in USD per 1M tokens by model.
- Create `server/usage_index.py` - SQLite schema, incremental scan, activity classification, `refresh()`, `summary()`, `insights()`, `estimate_cost()`.
- Modify `server/usage_store.py` - in `record()`, additionally append one line to `STATE_DIR/usage-events.jsonl`.
- Modify `server/main.py` - add `GET /usage/summary`, `GET /usage/insights`, `POST /usage/refresh` (keep the old `/usage`).
- Create `dashboard/usage.js` - the rich dashboard UI (period + provider filters, KPI cards, chart, insights).
- Modify `dashboard/console.js` - `renderUsage()` delegates to `usage.js` (keep the OpenRouter balance part).
- Modify `.gitignore` - add the index db + events log.
- Test: `server/test_usage_parsers.py`, `server/test_usage_index.py`.

## UsageEvent (shared key, dict)

```
{ ts:int(epoch), day:'YYYY-MM-DD'(local), provider:'claude'|'codex'|'api',
  engine:str, model:str, project:str, session_id:str,
  source:'javis'|'manual', activity:'chat'|'background'|'subagent'|'manual',
  input:int, output:int, cache_read:int, cache_create:int }
```
`billable_in = input + cache_read + cache_create`.

---

### Task 1: UsageEvent + Claude line parser

**Files:** Create `server/usage_parsers.py`; Test `server/test_usage_parsers.py`

**Produces:** `parse_claude_line(obj: dict, chat_sessions: set[str]) -> dict | None`
- obj = one JSONL line already passed through json.loads. Returns None if: type != 'assistant', model == '<synthetic>', there is no message.usage, or the token total is 0.
- source: 'javis' if entrypoint starts with 'sdk', else 'manual'.
- activity: 'subagent' if isSidechain; else 'manual' if source is manual; else 'chat' if session_id is in chat_sessions, else 'background'.
- day: convert the UTC timestamp to UTC+7 -> 'YYYY-MM-DD'.
- project: basename of cwd (keep the full path in a separate field if needed); provider 'claude'.

- [ ] Step 1: write the test `test_parse_claude_line` with one real sample line (sdk-cli, with cache) -> assert provider claude, source javis, activity background (session not in the chat set), billable includes cache, day correct in UTC+7 (use a timestamp close to UTC midnight to catch tz bugs).
- [ ] Step 2: run the test, see it FAIL (function does not exist yet).
- [ ] Step 3: write `parse_claude_line`.
- [ ] Step 4: run the test, PASS.
- [ ] Step 5: add tests: synthetic line -> None; manual line (claude-desktop) -> activity 'manual', source 'manual'; isSidechain line -> 'subagent'; session_id in chat_sessions -> 'chat'. PASS.
- [ ] Step 6: commit.

### Task 2: Codex rollout parser

**Files:** Modify `server/usage_parsers.py`; Test `server/test_usage_parsers.py`

**Produces:** `parse_codex_file(path: str) -> dict | None`
- Read the rollout JSONL file. Take `total_token_usage` (cumulative) - use the LAST line that has total_token_usage as the session total (input_tokens, cached_input_tokens, output_tokens). If there is none -> None.
- ts: from the first/last event timestamp or by parsing the file name `rollout-YYYY-MM-DDTHH-...`. model: from an event if present, else 'codex'. provider 'codex', source 'javis', activity 'background' (Codex runs in the background by default; adjust if it can later be mapped to chat). session_id = file name.
- Map: input = input_tokens - cached_input_tokens (new tokens), cache_read = cached_input_tokens, output = output_tokens, cache_create = 0.

- [ ] Step 1: write a small fixture (2-3 jsonl lines with increasing total_token_usage) + a test asserting it takes the correct session total (does not add up every line), day correct.
- [ ] Step 2: run, FAIL.
- [ ] Step 3: write `parse_codex_file`.
- [ ] Step 4: run, PASS.
- [ ] Step 5: commit.

### Task 3: Price table + converted cost

**Files:** Create `server/usage_pricing.json`; Modify `server/usage_parsers.py` (function `estimate_cost`); Test `server/test_usage_parsers.py`

**Produces:** `estimate_cost(ev: dict, prices: dict) -> float`
- prices: { model_prefix: {in, out, cache_read, cache_write} } USD/1M. Match by longest prefix; fallback {0,0,0,0}.
- cost = (input*in + output*out + cache_read*cache_read + cache_create*cache_write)/1e6.
- pricing.json seed: opus-4-8, opus-4-7, sonnet, haiku, fable, gpt-4o..., with approximate prices (state clearly that they are updated by hand). OpenRouter API models are very diverse, so a fallback of 0 is acceptable.

- [ ] Step 1: test `estimate_cost` with one opus event + a sample price table -> assert the number is right per the formula.
- [ ] Step 2: FAIL.
- [ ] Step 3: create pricing.json + the function.
- [ ] Step 4: PASS.
- [ ] Step 5: commit.

### Task 4: SQLite indexer + incremental scan (Claude + Codex)

**Files:** Create `server/usage_index.py`; Test `server/test_usage_index.py`

**Consumes:** parse_claude_line, parse_codex_file (Tasks 1-2).
**Produces:**
- `db_path() -> Path` = STATE_DIR/usage_index.db.
- `_chat_sessions() -> set[str]` reads `conversations.db` read-only (non-empty cli_session_id). Error/missing file -> set() (does not block).
- `refresh() -> dict{claude_files, codex_files, events}`: scans the 2 sources (paths from the env override), skips files whose (path,size,mtime) were already seen in the table `files_seen`, parses, and adds into the table `usage_daily(day, provider, source, activity, model, project, input, output, cache_read, cache_create, sessions)` (cumulative UPSERT; count distinct sessions through a helper table or an in-RAM set while building). Writes files_seen. Idempotent.
- Schema `files_seen(path PK, size, mtime, provider)`; `usage_daily` aggregate key (day,provider,source,activity,model,project).

- [ ] Step 1: build a temp test: create `JAVIS_CLAUDE_PROJECTS_DIR` with 1 jsonl file of 2 assistant lines (1 background, 1 subagent) + `JAVIS_CODEX_SESSIONS_DIR` with 1 rollout. Run `refresh()`; assert the token total matches the hand count + the classification is right. Run `refresh()` a second time; assert NO increase (idempotent, files_seen blocks it).
- [ ] Step 2: FAIL.
- [ ] Step 3: write usage_index (schema + refresh + classify).
- [ ] Step 4: PASS (including idempotence).
- [ ] Step 5: test a changed file (append a line + change mtime/size) -> a third refresh adds only the new part. PASS.
- [ ] Step 6: commit.

### Task 5: usage_store writes forward events + the indexer loads the API branch

**Files:** Modify `server/usage_store.py`; Modify `server/usage_index.py`; Test `server/test_usage_index.py`

**Produces:**
- `usage_store.record(...)`: additionally append one JSON line `{ts, provider, model, in, out, cost}` to `STATE_DIR/usage-events.jsonl` (append-only, best-effort try/except, never breaks the chat flow). usage.json keeps its behavior (30 days) for the old panel.
- `usage_index`: in refresh, read `usage-events.jsonl`, take ONLY lines whose provider is in {openrouter, openai, anthropic, anthropic-api, oauth} (map to provider 'api'), and add them into usage_daily (source javis, activity chat, project '(api)'). Track the offset already read in files_seen (using size as the offset) so nothing is read twice.

- [ ] Step 1: test: call `usage_store.record('openrouter','x/y',100,50)`; assert `usage-events.jsonl` has 1 correct line. Then `usage_index.refresh()`; assert provider 'api' appears with 150 tokens. Record one more line -> refresh -> only the new part is added.
- [ ] Step 2: FAIL.
- [ ] Step 3: edit usage_store + usage_index.
- [ ] Step 4: PASS.
- [ ] Step 5: commit.

### Task 6: summary() - period + comparison + breakdowns

**Files:** Modify `server/usage_index.py`; Test `server/test_usage_index.py`

**Produces:** `summary(period: str, provider: str|None=None, project: str|None=None) -> dict`
- period in {today, yesterday, this_week, last_week, this_month, last_month, last_3_months, this_year}. Resolves to (start_day, end_day) local + the equivalent previous period.
- Returns: `kpi` {tokens, tokens_prev, delta_pct, per_day_avg, sessions, avg_per_session, cache_hit, out_in_ratio, cost_est}; `by_provider`, `by_source`, `by_activity`, `by_model` (top + cost), `by_project` (top); `timeseries` [{day, providers...}]. Filters by provider/project if passed.
- cache_hit = sum(cache_read)/sum(billable_in).

- [ ] Step 1: test: seed usage_daily by hand-inserting days known in advance (today + yesterday + last month). Call summary('today') and assert tokens + delta vs 'yesterday' are right; summary('this_month') includes exactly the right days; cache_hit right; by_provider adds up right.
- [ ] Step 2: FAIL.
- [ ] Step 3: write the period resolver (UTC+7) + summary.
- [ ] Step 4: PASS.
- [ ] Step 5: tz boundary test: an event at 23:30 UTC must belong to the NEXT local day. PASS.
- [ ] Step 6: commit.

### Task 7: insights()

**Files:** Modify `server/usage_index.py`; Test `server/test_usage_index.py`

**Produces:** `insights(period: str) -> list[dict{level, title, detail}]` following the rules in section 5.3 of the spec (low cache, background eating a lot, expensive model on small jobs, bloated sessions, spike vs run-rate). Thresholds are constants at the top of the file.

- [ ] Step 1: test: seed data that triggers each rule (e.g. background taking 40% + a spike) -> assert the matching insights are present; seed "clean" data -> an empty/short list.
- [ ] Step 2: FAIL.
- [ ] Step 3: write insights.
- [ ] Step 4: PASS.
- [ ] Step 5: commit.

### Task 8: FastAPI endpoints

**Files:** Modify `server/main.py` (near the old `/usage`, ~line 2753); uses `import usage_index`.

**Produces:**
- `GET /usage/summary?period=&provider=&project=` -> `usage_index.summary(...)` (call a light refresh() first if fresh numbers are wanted; or let the client press refresh). Default: incremental refresh, then summary.
- `GET /usage/insights?period=` -> insights.
- `POST /usage/refresh` -> refresh(), returns the stats.
- Follow the existing route style (no special auth; the old `/usage` has none).

- [ ] Step 1: add the 3 routes.
- [ ] Step 2: smoke test with a script: start by importing the app? Instead, test indirectly by calling `usage_index.summary` directly, already covered in Task 6; the endpoint is just a shell. Verify by hand with curl when running the app in Task 9.
- [ ] Step 3: commit.

### Task 9: Dashboard tab (UI)

**Files:** Create `dashboard/usage.js`; Modify `dashboard/console.js` (renderUsage delegates); Modify `.gitignore`.

**Produces:** UI: a row of period chips (8 choices), a segmented provider filter (All/Claude/Codex/API), a row of KPI cards (total + delta, tokens/day, cache hit, sessions, avg/session, converted cost), a bar chart of tokens by day (hand-drawn SVG, stacked by provider), model/project breakdown tables, an insights list. A "Refresh" button -> POST /usage/refresh then reload. Keep the old OpenRouter balance block.

- [ ] Step 1: write usage.js to render from `/usage/summary` + `/usage/insights`; console.js calls into it.
- [ ] Step 2: add to `.gitignore`: `server/usage_index.db*`, `server/usage-events.jsonl*`.
- [ ] Step 3: run the app (skill run / preview), open the Usage page, change the period + provider, confirm the numbers change + the chart draws + insights show. Screenshot.
- [ ] Step 4: commit.

### Task 10: Overall verification + cleanup

- [ ] Step 1: run both `test_usage_parsers.py` + `test_usage_index.py` through `.venv`, all PASS.
- [ ] Step 2: run `refresh()` for real on the machine's data, check that a month's token total matches intuition (compare with the old panel).
- [ ] Step 3: confirm `git status` shows no derived db/jsonl.
- [ ] Step 4: bump VERSION + CHANGELOG, commit, push (following the habit of auto-pushing after tests pass).

## Self-review (checked)

- Spec coverage: sources (T1,2,5), schema (T1), classification (T1,4), pricing (T3), KPI/breakdown (T6), insights (T7), endpoints (T8), UI + period + provider (T9), tests (every task). Forward API (T5). Timezone (T1,6). No double counting (Global + T5). OK.
- No placeholders: each task has a real signature + a concrete test. The chart library is settled (hand-drawn SVG, no dependency).
- Naming consistency: parse_claude_line/parse_codex_file/estimate_cost/refresh/summary/insights are used consistently across tasks.
