# Restructuring the Jarvis 007 server

Date: 2026-07-28
Status: phase 0 DONE (0.9.235 + 0.9.236). Phases 1-4 await an execution plan.
Base version: 0.9.234

Progress:
- [x] Phase 0 - safety net. With an unplanned finding: CI had been red continuously since 0.9.231,
      so the two blocking bugs were fixed on the spot (a connector guide exceeding the character cap, and `test_graph_watch.py`
      segfaulting on exit because of watchfiles' Rust thread). CI has been fully green since 0.9.236.
- [x] Phase 1 - unblock the event loop (0.9.237 to 0.9.240). Measured results on a brain
      of 623 md / 30 skills: `build_system_prompt` **150.8 -> 37.2ms**, `import main`
      **2,263 -> ~1,400ms**, `GET /brains` 136.1ms -> now runs in a thread (48-77ms CPU,
      event loop latency measured at 18ms). Two places where the spec guessed wrong were corrected to the measurements,
      noted in section 5.
- [x] Phase 2 - move runtime data out of the source (0.9.241), but **NARROWER than planned**.
      The original item 2.1 was WRONG and was dropped: `server/brains-backup/` is the git working copy of the
      feature that backs up brains to GitHub (`main.py:1474`) and has uncommitted changes;
      `server/.staging/` holds real user uploads; `server/tmp/` is in use by
      `claude_sdk_engine.py:254`. All three are `JAVIS_STATE_DIR` content, and the default `STATE_DIR`
      is `server/` itself, so "moving them out" is really changing `STATE_DIR` - exactly
      what section 3 forbids. If a tidier `server/` is wanted, that is a per-machine configuration decision, not
      a code change.
      The real value gained lies elsewhere and is bigger than expected: `.dockerignore` was letting
      `.secret_key`, `.hub_token`, `.oauth_mcp.json`, `usage_index.db` leak into the image, and the
      build context went from **1,239 MB down to 6 MB**.
- [x] Phase 3 - split out the tests (0.9.242). `server/` went from 126 `.py` files down to **50 source files**.
      Done DIFFERENTLY from the plan, in a better way: the spec meant to keep `cwd=server` in CI, but that constraint was
      dropped entirely - 97 location-dependent spots were funneled into `tests/python/_paths.py`, and tests run
      from any directory. Plus 2 unplanned jobs: 7 JS tests that had never run once
      now run (CI listed 4 files by hand and missed 7), and JS tests are no longer served publicly via
      `/static/test_*.js`.
- [~] Phase 4 - split main.py. **Scope deliberately reduced** after re-measuring: the goal
      "under 800 lines" is DROPPED. Reason: the argument "a big file makes agents edit blind" turned out weak - throughout
      phases 1-3 `main.py` was edited about 15 times by grepping and then editing the right region, and not
      once did the file size cause an error. The benefit is LINEAR (easier to read, easier to locate), not
      threshold-shaped, so doing part of it is fine.
      Done (0.9.243): `routes/graph.py`, `routes/domain.py`, and fixing 8 places that called route handlers
      as ordinary functions. `main.py` 6,491 -> 6,159.
      NOT done: peeling off the update block (blocked: `test_update.py` patches over `main._deploy_mode`, that function
      must stay in main and be called lazily), peeling off the Telegram block, and merging the duplication between
      `_do_turn` and `_tg_answer`.

## Appendix: 10 places that drifted apart between the two engine dispatch copies (measured 2026-07-29)

`_do_turn` (dashboard, inside `@app.websocket("/ws")`) and `_tg_answer` (Telegram) are two
copies of the same 4-branch engine flow. They have really drifted apart, this is not a theoretical risk.
Recorded here so the next fix has a list and does not need to re-analyze.

Missing on TELEGRAM:
1. ~~No `usage_store` write for the Claude-CLI branch and the API branch~~ - the Usage table under-reported every
   Telegram conversation that did not go through Codex. **DONE 0.9.244.**
2. ~~No `store.append_message` / `auto_title` / `log_conversation` / `learn_feature.enqueue`~~.
   Telegram conversations were absent from `/sessions`, from `brain/Memory/conversations`, and from the self-learning loop.
   This is the biggest functional hole on the list. **DONE 0.9.244.**
3. ~~No recovery when a Codex resume fails~~ - all context lost, not rebuilt.
   **DONE 0.9.245.**
4. ~~`_codex_safe_model` forces a valid model but does NOT write it back~~, and does not tell the user the model was
   changed. **DONE 0.9.245.**
5. ~~The first `error` event kills the whole turn~~, even when the stream could still recover. The dashboard treats errors
   as non-fatal. **DONE 0.9.245.**
6. ~~`compact_mem` runs on the request path~~ - a long session had to wait for a summarization round before seeing
   the answer. **DONE 0.9.245.**
9. ~~The Codex branch passes `written=[]` to `collect_turn_files`~~ while the Claude branch collects
   Write/NotebookEdit paths. Files Codex wrote were only auto-attached if the absolute path
   happened to appear in the answer. **DONE 0.9.245.**
10. ~~No counterpart of `store.clear_codex_thread_id`~~, while `sess["codex"]` is only cleared by
    `/reset` and `/brain` - switching provider to Claude and back resumed a Codex thread that had
    never seen the turns in between. **DONE 0.9.245.**

Missing on the DASHBOARD:
7. ~~No `strip_control_blocks` before `store.append_message`/`log_conversation`~~, so raw
   `<!-- JAVIS_ASK ... -->` blocks leaked into the session store and the conversation log - that is, into the very
   corpus used for self-learning. **DONE 0.9.244.**
8. ~~The `response` frame of the Claude branch sits INSIDE the `final` handler~~, so no `final` means no
   `response`. **DONE 0.9.245.**

On how to fix: the proposal to build a shared abstraction layer (`TurnSink` / `ChatHistory` / a dependency bag)
is RIGHT in design but this is the riskiest stretch of code in the app. Recommendation: fix each
bug above directly first (one commit each, with a test), and only then consider merging - rather than merging first and
fixing afterwards.

### Fixed in 0.9.244 (bugs 1, 2, 7)

Fixed exactly per the recommendation above: the whole dispatch flow was NOT merged, only ONE shared piece was extracted,
the **turn-persistence path** - `_persist_turn(store, conv_sid, brain, user_message, final_text)`. It
strips control blocks and only then calls `append_message` + `auto_title` + `log_conversation` +
`learn_feature.enqueue`. Both `_do_turn` and Telegram call it, so bug 7 is gone for both
channels at once instead of patching only the dashboard.

On the Telegram side, shell and core were separated: `_tg_answer` (the shell - opens/matches a session in the store, saves the user turn, calls
the core, saves the assistant turn) and `_tg_answer_engine` (the 4-branch core, kept verbatim). The shell decides the
engine label and PASSES it down to the core rather than letting both sides infer it - otherwise one day a session
would be labeled `cli` while the real turn ran through OpenRouter. Return convention: **dict = a
real answer (worth saving), string = an error message (not saved)**; hence the calendar gateway branch was changed to return
a dict. `sess["sid"]` lives in RAM like `sess["cli"]/["or"]/["codex"]` and is cleared on `/reset` +
`/brain`.

Bug 1 was just two `usage_store.record` lines placed in the right spot: the CLI branch records on the `final` event (with
`cost_usd`), the API branch records on the `usage` event and tracks the REAL model from the `meta` event.

One accompanying change, deliberate: `learn_feature.enqueue` went from `asyncio.create_task` to a direct
`await`. `enqueue` only reads config + increments a counter under a lock (the real learning batch runs in `tick`), which is cheaper
than the log-file write right above it - so an orphaned task that nobody waits on, swallowing errors silently, is not worth it.

### Fixed in 0.9.245 (the remaining seven bugs: 3, 4, 5, 6, 8, 9, 10)

The list is closed. The dispatch flow is still NOT merged - each bug is fixed in place, only two more small
shared pieces were extracted (`_tg_ket` wraps up the answer, `_tg_compact_bg` pushes compaction to the background).

Three bugs eat into each other as a cluster, and could only be fixed because 0.9.244 gave Telegram a session store. **Bug 10**
clears the Codex thread link when another provider cuts into a turn, the exact counterpart of
`store.clear_codex_thread_id`. When the thread is lost there must be somewhere to rebuild the context - that is **bug 3**:
`_nuot_codex` returns a resume-broken flag; if it really is broken, it clears `session_id`, builds a bootstrap prompt from the
transcript in the store, and reruns exactly once. The same path also serves the case where a session has no
thread yet.

**Bug 5** changes the error contract in all three branches: `error` events are collected into a list instead of an immediate
`return`. If there is text, return the text with an error line at the end; only if there is no text at all is the error returned as before.
The Claude branch also accumulates what has streamed so far, so a stream that breaks before `final` still has something to return.

**Bug 8** is the same class of bug on the dashboard side: the `response` frame moves OUTSIDE the event loop,
using the streamed text as a fallback. Previously, with no `final`, the client received no
`response` at all and the chat bubble hung forever, even though the text had already appeared.

**Bug 6** pushes `compact_mem` to a background task, and only APPLIES the result if the history has not changed since compaction
started - if a turn cut in between, overwriting it would swallow the turn just spoken.

**Bug 9** was not fixed by guessing Codex's JSON shape (paths are scattered in
`changes[].path`, in `arguments`, or mixed into `command`, and the shape also changes between CLI versions).
`CodexCLI` pushes up the raw payload, and `channel_context.candidate_paths_from_tool` walks the whole
payload and collects BROADLY anything that looks like a path. Collecting broadly is safe because the downstream `collect_turn_files`
only keeps files that REALLY exist and CHANGED during the turn - surplus candidates quietly drop out. Unknown
items (e.g. a file patch) are also pushed up as an `item` event, not printed, to avoid noise.

**`_codex_safe_model`** (bug 4) writes the forced model back into Settings and tells the user. On
Telegram the notice must go in the ANSWER and not in progress - progress gets replaced by the
answer so the user would never read it.

On testing: the six Telegram bugs are tested by calling the real `_tg_answer` directly with a fake engine. Bug 8
lives in a nested function inside `@app.websocket("/ws")` so it cannot be called directly - it is tested by AST,
asserting the two things that make up the bug (the `response` frame is not inside the loop, and the loop
accumulates streamed text).

Also a NINTH place that calls a route handler as an ordinary function, missed by the 0.9.243 net:
`bench_hotpath.py:103` calls `asyncio.run(main.list_brains())`. The old net only inspected `main.py` +
`routes/` and only caught bare calls, so it saw neither this file nor the `module.handler()` form.
Now `test_handler_khong_goi_truc_tiep` ("handlers are not called directly") scans all of `server/` and catches both
forms, distinguishing by module so that `skill_router.list_skills()` (an ordinary function with the same name) does not raise
a false alarm.

## 1. Why do it, and three assumptions that were refuted

The starting point was the view that "main.py is too heavy, the folder structure is not as clean as hermes-agent,
worried about hurting performance later". It was measured with numbers before designing. Three of its assumptions were wrong,
and this spec is built on the part that remained true.

**Refuted 1: hermes-agent is not tidier.** The clone at `.learn/hermes` is a real repo
(remote NousResearch/hermes-agent, HEAD 972b1620). `gateway/run.py` is 18,911 lines, `cli.py` 15,695,
`hermes_cli/web_server.py` 14,142, `hermes_cli/config.py` 7,731. 12 hermes source files are larger
than `server/main.py` (6,442). The average is 712 lines/file against Jarvis 007's 558. On route registration hermes
is even worse: 200 routes hang off `@app.*` in one 14k-line file, `APIRouter` is used in only 4 minor places,
whereas Jarvis 007 already has 5 feature modules using `APIRouter` + `register(app, Deps)`.
Conclusion: do not take hermes as a structural template. The only four things worth learning are `pyproject.toml`,
`tools/registry.py` (self-registration + lazy discovery via AST), `PluginContext` with 18 typed extension points,
and `tests/` mirroring the source tree.

**Refuted 2: file length costs no runtime.** Compiling 6,442 lines takes 155ms exactly once,
after which loading `__pycache__/main.cpython-312.pyc` takes 1.7ms. The only size-related cost is
Starlette's linear scan of `app.routes`: 0.13ms for the first route, 0.64ms for the last route, 0.52ms for a 404 scanning
all 192 routes. That figure depends on the NUMBER OF ROUTES, not the number of lines, and `include_router` merges child routers
back into `app.routes`, so splitting the file leaves the route table exactly the same.
Conclusion: phase 4 of this spec is so that people and agents can read/edit the code, and it must ABSOLUTELY not be advertised as a performance fix.

**Refuted 3: the folder structure is not what hangs the app.** The cause is blocking the event loop on
a single uvicorn process with no `--workers` (`Dockerfile:96`, `main.py:6441`), which makes the 4-second
healthcheck fail, Traefik drops the route, and a 404 results.

**What is true, and the real reasons to do it:**

- `main.py` is 6,442 lines / 311 KB, roughly 80,000 tokens. It was edited in 50 of the last 200 commits,
  i.e. a quarter of the project's commits. An agent either burns 80k tokens to view one file, or greps and edits blind.
- `build_system_prompt()` (`main.py:261`) blocks the event loop for 95-110ms on every chat turn, called from 6 places.
- `server/` weighs 1.5 GB, of which `brains-backup/` is 1.4 GB and `.staging/` 114 MB, sitting right inside the source folder.
- 67 test files are mixed with 55 source modules in one flat folder, with no pytest configuration.

## 2. Goals

1. Remove the cheapest event loop blocks, bringing each chat turn from ~100ms down to ~30ms and `/brains`
   from 110ms to near 0.
2. Bring `main.py` down to a level an agent can hold entirely in context (target 400-600 lines, hard cap 800).
3. Separate runtime data from the source folder, and separate tests from the source.
4. Change no behavior observable from the outside. The 182-endpoint table must diff to empty.

## 3. Non-goals

- Do **not** switch to a `pyproject.toml` / `src/javis/` package. The reason is the trap in section 8.1.
- Do **not** cache the system prompt by file signature in this round. If one input is missed, the stale prompt
  is used silently and the model misbehaves with no error reported. Wait to re-measure after phase 1.
- Do **not** touch the 3 import cycles currently broken by in-function imports (`config`<->`secrets_store`,
  `oauth_mcp`<->`mcp_store`, `claude_cli`<->`claude_sdk_engine`).
- Do **not** change the default `JAVIS_STATE_DIR`. It points at `server/`, where every existing install keeps
  `settings.json`, `.secret_key`, `.hub_token`, `kanban.sqlite3`, `conversations.db`. Changing the default
  means users start up and find their accounts and all connectors gone.
- Do **not** merge the 4-branch engine dispatch that is written twice in `_do_turn` (5459-5599) and
  `_tg_answer` (5838-5966). A separate job, done later.
- Do **not** rewrite the 60 script-style test files into real pytest in this round. Only move them.

## 4. Phase 0: safety net (about 1 hour, done before anything else)

Without this step every later step is hope rather than proof.

1. `tests/test_route_table.py`: dump `[(route.path, sorted(route.methods or []), route.name) for route in app.routes]`
   to `tests/fixtures/route_table.json`, commit that file, and match against it in the test. 182 endpoints.
   This is the insurance wire for all of phase 4.
2. Add `python -c "import main"` to `.github/workflows/ci.yml`. Currently CI only byte-compiles
   (`ci.yml:22-23`), so a broken import cycle still passes CI, still gets pushed, still auto-deploys, and only then dies at runtime.
3. `server/bench_hotpath.py`: measure and print `build_system_prompt`, `skill_router.list_skills`,
   `plugins_host.describe`, `usage_index.summary`, `GET /brains`. Run before and after phase 1.

Acceptance: CI goes red if a route path is deliberately changed.

### 4.1 Baseline measured (2026-07-28, VERSION 0.9.234)

Route table snapshot: **192 entries** (185 APIRoute, 2 WebSocket, 4 default FastAPI routes, 1 StaticFiles Mount),
i.e. 187 endpoints of the app. The figure 182 quoted in the research draft was a hand-summed estimate and lower than reality;
from now on `server/route_table.json` is the source of truth.

The guard was verified to catch errors: deliberately deleting `/brains`, shifting the order of `/health`, renaming
`/version` made the test print all three kinds of mismatch and return exit 1.

Measurements on the large brain `brains/My Bullet Journal` (623 .md files, 30 skills), Windows machine, warm cache:

- `build_system_prompt()` **150.8ms** (median of 5 runs). Broken down: `list_skills` 53.4ms,
  `plugins_host.describe` 34.7ms, `_gather_capabilities` 76.9ms, `_javis_capability_summary` 69.8ms,
  `_skill_router_block` 26.9ms.
- `GET /brains` **136.1ms**.
- `usage_index.summary()` 46.7ms, `usage_index.insights()` 46.6ms.
- `import main` **2,263ms** (after subtracting 63ms of bare interpreter startup).

On the small default brain (101 .md files, 7 skills) `build_system_prompt` is only 39.6ms. A nearly 4x difference,
so **every acceptance threshold must state which brain it was measured on**, otherwise we are fooling ourselves.

Note this baseline is higher than the 95-110ms figure in the research draft. Do not hunt for the reason for the gap, just take the re-measured
number as the standard because only the same machine and same script allow a before/after comparison.

## 5. Phase 1: unblock the event loop (about 1 day)

All of it is behavior-preserving change, one independently revertable commit per item.

**1.1 `server/fastyaml.py`.** The function `safe_load` picks `yaml.CSafeLoader`, falling back to `yaml.SafeLoader`
when libyaml is missing, exporting a `HAS_C` flag to log at boot. Replace all 9 `yaml.safe_load` call sites outside tests:
`main.py:2465` (in `_read_md`), `main.py:3065` (in `_scan_note_md`), `plugins_host.py:151`,
`self_improve.py:311`, `share_bundle.py:47`, `skill_router.py:117`, `system_sync.py:91`,
`system_sync.py:271`, `system_sync.py:279`. The hottest are `skill_router.py:117` and `plugins_host.py:151`.
Measured: 0.446ms down to 0.072ms on a 130-byte SKILL.md frontmatter, 6.2 times faster. YAML accounts for
64% of the cost of `build_system_prompt`. Along with a test comparing that both loaders give the same result on
every frontmatter in the repo.

**1.2 Remove the duplicated skill scan.** `_gather_capabilities` calls `skill_router.list_skills(root)`
(`main.py:4061`), then `_skill_router_block` calls `skill_router.list_enabled_meta(root)`
(`main.py:4222`), while `list_enabled_meta` is just `[s for s in list_skills(root) if s.get("enabled")]`
(`skill_router.py:186`). The whole skill tree is walked and YAML-parsed twice per turn, 46.3ms each time.
Fix: call `list_skills` once and pass the result down to both places.

**1.3 Cache `plugins_host.describe()`.** It re-reads and re-parses every `plugin.yaml` with no cache,
21.9ms each time, called from `_gather_capabilities` so it runs on every chat turn, every Kanban task,
every time a reminder fires, every loop tick. Attach a cache keyed on `(mtime_ns, size)` of the `plugin.yaml` files,
following the pattern that already exists at `config.py:136-169`.

**1.4 Offload the usage queries.** `main.py:3435/3449/3462` already wrap `usage_index.refresh` in
`asyncio.to_thread` correctly, but the very next line calls `usage_index.summary()` directly
(`main.py:3437`, measured at 68ms) and `usage_index.insights()` (`main.py:3451`) on the loop. Wrap those too.

**Two places where this spec guessed wrong, corrected to real measurements (recorded so they are not repeated):**

- Item 1.5 below assumed that the repeated DDL at `_connect` was a significant cost. Measured, `_connect`
  costs only 1.14ms out of the 65ms of `summary()`, i.e. under 1.5%. The real culprit is
  `usage_parsers.estimate_cost`, which linearly scans the whole price table for EVERY row: 321,009
  `startswith` calls over 3 passes, while there are only 11 distinct models and 6 price keys. It is now memoized.
  But to state the gain plainly: only 9% of the total, because the function is still called 53,496 times as `_group` reruns
  over the same set of rows for 15 dimensions. A thorough fix is restructuring `_group` - NOT done yet,
  because this is a dashboard endpoint and item 1.4 already removed the dangerous part, which is blocking the loop.
  What 1.5 REALLY needs is WAL, and not to be fast but to be CORRECT: after 1.4,
  summary/insights read in parallel with `refresh()` writing.
- Item 1.7 set the `/brains` target under 15ms based on using `_MDINDEX_CACHE`. In reality it uses
  `_count_md` (a capped scandir) at 48-77ms CPU. That figure was not reached, but the important
  property was: it runs in a thread, with event loop latency measured at 18ms while scanning a 3000-note
  brain. The 15ms target was in the wrong place - what needs to be bounded is the time the LOOP IS LOCKED, not the function's time.

**1.5 sqlite hygiene for usage_index.** `usage_index._connect()` (`usage_index.py:60-69`) opens a
new connection on every call and reruns 2 `CREATE TABLE IF NOT EXISTS` + 2 `CREATE INDEX IF NOT EXISTS`
at every connect, with no `journal_mode=WAL` and no `busy_timeout`. This is the only sqlite store in the
codebase that gets all three wrong, while `sessions.py:100-118` and `task_store.py:61-65` both do it right.
Fix it following the mold of those two files.

**1.6 Lazy import of `edge_tts`.** `main.py:22` imports it at module level unconditionally, even though TTS is an
optional feature. It accounts for 944ms of the 2,280ms total `import main`, and drags in the whole `aiohttp` chain at 212ms.
Move it inside the TTS function.

**1.7 `GET /brains` stops using rglob.** `main.py:2360` calls `p.rglob("*.md")` on each brain just to count
notes, with no offload and no cache, measured at 108-115ms per request, and the dashboard calls it at boot from two places
(`dashboard/brains-ui.js:75`, `dashboard/console.js:1191`). This exact bug was already diagnosed and commented
(in Vietnamese) for `/viec/all` at `main.py:3946`, but `/brains` was left alone.
Fix: take the count from the prewarmed `_MDINDEX_CACHE`, falling back to `_count_md` (`main.py:4404`, already a scandir
with early exit and a cap) when there is no cache. An approximate count is accepted, just as it was accepted for `/viec/all`.

**1.8 Batch the Kanban `_snapshot()`.** `tasks.py:114` calls `list_tasks(limit=5000)` then loops over each task
calling `list_events(task_id, 20)`, i.e. N+1 queries, then serializes and rewrites a JSON file, with no offload,
called from `_claim_and_spawn` (`tasks.py:313`) and `_worker_done` (`tasks.py:324`). It is free right now because the table
is empty, but grows linearly up to the 5000 cap. Merge into one batched events query, and offload.

Acceptance (measured with `bench_hotpath.py` on the `My Bullet Journal` brain, against the baseline in section 4.1):

- `build_system_prompt` from 150.8ms down to **under 60ms**. By hand: removing the duplicate scan saves ~53ms,
  caching `describe` saves ~35ms, and what remains is mostly `list_skills`, where YAML is 64%, so `CSafeLoader`
  takes 53ms down to ~24ms. Added up that is about 34ms, so 60ms is a comfortable threshold and 40ms is a stretch goal.
- `GET /brains` from 136.1ms down to **under 15ms**.
- `import main` from 2,263ms down to **under 1,400ms** (dropping `edge_tts` saves 944ms).
- `usage_index.summary/insights` need not be faster, they just must no longer sit on the event loop.

All old tests stay green, and `test_route_table.py` still matches 192 entries.

## 6. Phase 2: move runtime data out of the source (1-2 hours)

**2.1 Move the two heavy folders out of the repo:** `server/brains-backup/` (1.4 GB) and `server/.staging/`
(114 MB). Both are gitignored but physically sit inside the source tree, so every `find`, `grep`, IDE index,
and docker context has to walk through them. Also delete the two pointless empty folders `server/utf-8/` (0 bytes, produced
by a broken redirect command) and `server/tmp/`.

**2.2 Patch `.gitignore` for 6 artifacts that are currently neither tracked nor ignored:** `server/_selfupdate.bat`
(hardcodes `D:\Project\Javis-OS`), `server/brain-trash/`, `server/kanban.sqlite3`, `server/logs/`,
`server/tg_brain.json`, `server/update_state.json`. A single `git add -A` would commit all of them.
Verified that nothing sensitive is currently TRACKED.

**2.3 Sync `.dockerignore` with `.gitignore`.** `Dockerfile:64` is `COPY . .` so `.dockerignore`
is the only fence, and it is an old, much weaker copy. It does NOT exclude: `server/.secret_key`,
`server/.hub_token`, `server/.oauth_mcp.json`, `server/.mcp_hub_*.json`, `server/plugins/`,
`server/connector-home/`, `server/usage_index.db`, `server/session_brain.db`, `server/kanban.sqlite3`,
`server/brain-trash/`, `server/brains-backup/`, `server/logs/`, `.gitnexus/` (106 MB), `.superpowers/`,
`.pytest_cache/`, `videos/` (754 MB), `cap.txt`, `scratch_url.txt`.
The GHCR build runs from a clean checkout so it is unaffected, but anyone running `docker build` locally bakes
their own `.secret_key` and `.hub_token` into the image.

**2.4 Clean up junk at the repo root:** delete the empty `memory/` folder, delete the two extensionless files `agents` and `workflows`
at the root (their content is a log fragment `  - Move: Jarvis\agents  -`), then remove the two lines `/agents` `/workflows`
at `.gitignore:83-84` because they permanently block creating real `agents/` `workflows/` folders at the root.

Acceptance: `du -sh server/` under 50 MB. `git status --porcelain -uall server/` is clean.
A local `docker build` no longer swallows secrets.

## 7. Phase 3: split out the tests (2-3 hours)

Move the 67 `server/test_*.py` files (11,340 lines) to `tests/python/`, adding a `conftest.py`.
Keep the current loop runner at `ci.yml:34-42` as is, because 55 files call `sys.exit()` and 52 call it right at
module level, 11 files call `asyncio.run()` at module level, and only 1 file has `if __name__ == "__main__"`.
Under pytest, the collect step imports each module, which runs the asserts straight away and then `sys.exit(1)`, killing the whole run.
Gradually moving to real pytest is background work, not on the critical path of this spec.

Breakage points to handle: 56 files rely on the `sys.path` idiom keyed on the script's folder, 12 files rely purely on cwd,
and 2 files open source files directly by relative path (`test_zalo_listener.py:222-878`,
`test_zalo_rules.py:146`). Keep `cwd=server` in CI and point the glob at `../tests/python/`.

Also: 7 of the 11 dashboard JS tests have never run in CI (`test_brains_ui.mjs`,
`test_dataview`, `test_task_suggest`, `test_zalo_panel`, `test_chat_acts`, `test_graph_timelapse`,
`test_graph_tooltip_cleanup`). Add them at `ci.yml:28-33`. And the JS test files sit under the StaticFiles
mount so `/static/test_chat_render.js` is being served publicly; they need to move out of `dashboard/`.

Acceptance: CI is green with all 67 Python tests and 11 JS tests, and `server/` no longer has `test_*.py` files.

## 8. Phase 4: split main.py (3-4 days, one commit per module)

### 8.1 Traps to know in advance

`updater.py:143` hardcodes `pip install -r requirements.txt` (no `-e .`) and `updater.py:131`
hardcodes `uvicorn main:app`. `javis.service` is a template with `__APP_DIR__` that `install.sh` substitutes,
so the running systemd unit is not in git and `git pull` never updates `ExecStart`.
Consequence: any change that makes `main:app` no longer importable from `server/` would make the next self-update
on the VPS pull code that the old updater does not install and cannot start, health fails, automatic rollback,
and the machine is stuck permanently below that commit.

**Hard constraint of phase 4: after every commit, `uvicorn main:app --app-dir server` must still run exactly as before.**
This is why the spec keeps `server/` flat, keeps imports by bare name, and does not change the `Dockerfile`,
`javis.service`, `start-javis.vbs`, `updater.py`.

### 8.2 Foundation modules, done first

- `server/paths.py` (~250 lines, lifted verbatim): `atomic_write_text` (149), `brain_memory_dir` (179),
  `default_brain_dir` (1960), `brain_root` (1972), `brain_sub` (1979), `resolve_subfolder` (1991),
  `slugify`/`ascii_slug` (2439-2452), `read_md`/`write_md` (2456/2471), `today` (2477),
  `agents_dir`/`workflows_dir` (2479/2481), `skills_dir` (2531), `TEXT_EXTS` (2721),
  `files_ceiling` (2726), `files_root` (2754), `safe_path` (2759), `safe_serve_path`, `files_rel`.
  No FastAPI dependency. `_brain_root` has 60 call sites spread across every domain, this is the hardest thing to pull out
  so it must be done first.
- `server/prompt.py`: `build_system_prompt` (261-317) + the capability block (4034-4248). This is also where
  fixes 1.2 and 1.3 of phase 1 landed, so move it after phase 1 is done.
- `server/logging_redact.py`: secret-masking regex + `_mask_secret`, `_redact_secrets`, `_clip_for_log`,
  `log_conversation` (319-408).
- `server/lifecycle.py`: 4 `@app.on_event` hooks (`_prewarm_mdindex` 3199, `_start_scheduler` 4296-4397,
  `_warm_mcp_hub` 6402, `_shutdown_mcp_pool` 6416) along with the nested `_scheduler_loop`.

### 8.3 Leaf wave (9 routers, 45-90 minutes each)

Groups that only use their own helpers, pulled out without touching anyone:
`routes/graph.py` (1727-1937), `routes/backup.py` (1449-1552), `routes/usage.py` (3402-3464),
`routes/browse.py` (4400-4509), `routes/ops_update.py` (4512-5021), `routes/branding.py` (5024-5110),
`routes/domain.py` (5113-5282), `routes/tts.py` (5285-5382), `routes/sessions_api.py` (5674-5707).

### 8.4 Core wave (the part that creates the real value)

`routes/auth.py` (468-575), `routes/settings_api.py` (1320-1446), `routes/upload.py` (1939-2095),
`routes/vault.py` (2097-2437, containing `/vault/*` `/brain/migrate` `/brains*`),
`routes/studio.py` (2439-2712 + 3305-3345 + 3615-3658, containing agents/skills/workflows/studio),
`routes/files.py` (2715-3009 + 3012-3196 + 3222-3302), `routes/connectors.py` (966-1317, 26 routes),
`routes/models.py` (884-960 + 1555-1676, 14 routes), `routes/chat_ws.py` (5385-5671),
`channels/telegram.py` (5710-6399), `routes/misc.py` (`/`, `/stop`, `/health`, `/memory/stats`,
`/reflect`, `/viec/all`, `/lint`, `/javis/index`, `/image/generate`, `/plugins`).

**Mandatory order:** `vault.py` and `files.py` must go AFTER `lifecycle.py`, because `_prewarm_mdindex` and
`_ensure_default_brain`/`_sync_system_all_brains` are startup hooks that touch them.

**The hardest spot is Telegram.** `_tg_command` (6264/6271/6282), `_tg_callback` (6147) and
`_tg_skills_text` (5991) call route handlers (`list_agents`, `list_workflows`,
`list_brains`, `list_skills`, `provider_models`) directly as ordinary Python functions. When splitting, `channels/telegram.py`
must import from the corresponding routers. This is a real dependency edge but creates no cycle, as long as no
router imports `telegram` back. If a cycle arises, move the shared function down to `paths.py`
or a new `services/` module, do NOT use in-function imports to hide a cycle.

### 8.5 Delete dead code (alongside, about 20 minutes)

Re-verified with `grep -nw` over every non-test .py file in `server/`:
`SOURCES_PATH` (425), `_update_outcome` (37), `_trim_history` (719), `_LOOP_LOCK` (3781),
`_write_loop_config` (3788), `run_loop_cycle` (3792). The last four have one more hit each, but those are in
docstrings or comments (`compaction.py:4`, `self_improve.py:44`, `self_improve.py:550`),
not calls. When deleting the code, also fix those comments so they do not point at nothing.

Plus three branches that can never run: `_check_structure` branch `"exact"` (2136-2139) and
`"file_any"` (2140-2144), and `_ensure_brain_scaffold` branch `"file_any"` (2193-2194).
Reason: recounted, all 12 entries of `STANDARD_STRUCTURE` (2099-2119) are `"kind": "dir"`, and those three
branches reference keys `it["path"]`/`it["files"]` that no entry has, i.e. they would raise KeyError if reached.
That drags the constant `SCHEMA_SEED` (2170) into being dead, since its only write is line 2194, inside a dead branch.
Note the branch `it["kind"] in ("dir", "exact")` at 2191 is NOT dead, leave it as is.

### 8.6 What remains in main.py

Creating `app`, 3 middlewares (`_csrf_guard` 94, `_auth_guard` 105, `_static_cache_headers` 128),
the StaticFiles mount, the auth path allowlist, the `include_router` table, the 5 `register(app, Deps)` calls
of the feature modules (3672/3802/3824/3870/3893), and the `__main__` block.
Target 400-600 lines, hard cap 800.

A note on authorization: the auth allowlist is a path string match in middleware attached to `app`
(76-91, 105-119), NOT per router scope, so splitting the file cannot change who gets in where.
This includes the entries `/reminders`, `/reminders/cancel`, `/hook/zalo` that `main.py` holds on behalf of other modules.

Acceptance per commit: `tests/test_route_table.py` green (route table diff empty),
`python -c "import main"` runs, the 67 old tests green, the app starts and `GET /health` returns 200.

## 9. Risks and how to block them

**Missing imports when moving a block.** Caught immediately by `python -c "import main"` in CI, and every
moved handler must still work on the first request. This is why phase 0 goes first.

**Changing the route registration order.** `include_router` placed at the exact position of the old lines in `main.py` recreates the exact
registration order. The route table snapshot proves it across all 182 endpoints.

**Merge conflicts.** Cloud agent PRs often merge on GitHub before local. One small commit per router,
and always `git fetch` before bumping the version.

**Moving files on the VPS in phase 2.** Stop the server before moving, list the target folder before starting
again, and keep the old copy in `server/` for a week before deleting it for good.

**The approximate note-count cache in 1.7.** For a brain the prewarm has not reached, the count is capped.
This is a tradeoff already accepted earlier for `/viec/all`, stated clearly in a comment.

## 10. Items identified but left out of scope

- `dashboard/console.js` is 4,767 lines, with the same edit frequency as `main.py` (50/200 commits), and has a ready cut line
  at `renderPage()` in `console.js:221`. Same recipe, done after the server is finished.
- 4 libraries are still loaded from a CDN at runtime despite the self-hosting policy: `three@0.159.0` and
  `3d-force-graph@1.73.4` (`app.js:644-645`), `turndown` (`console.js:4495-4496`), `mermaid@10`
  (`chat-render.js:480`). In an offline deploy the 3D graph, markdown round-trip and mermaid die silently.
- The hand-written `?v=NN` in `index.html` is dead code, because `main.py:443` already overwrites every
  `/static/*.js|css?v=` with VERSION when serving. It should be deleted so later readers do not think it still has an effect.
  Only `/brand-logo?v=5` at `index.html:8-9` does not match that regex so it still has to be edited by hand.
- `GET /browse` and `/path/exists` allow listing the file system, and the `_safe_path` guard is copy-pasted in 12 places.
  Needs a separate review, more important for people who fork than file size.
- There is no structured logging or error aggregation yet, so every restructuring can currently be accepted only by feel
  beyond the tests.
- `mcp_store._load()` (`mcp_store.py:57`) re-reads and re-decrypts `mcp_servers.json` on every call, uncached,
  35 call sites. `mcp_hub` already shields the tool-call path so it only bites dashboard endpoints. Low priority.

## 11. Overall acceptance criteria

1. `bench_hotpath.py` on the `My Bullet Journal` brain: `build_system_prompt` under 60ms
   (baseline 150.8ms), `GET /brains` under 15ms (baseline 136.1ms), `import main` under 1,400ms
   (baseline 2,263ms).
2. `server/main.py` under 800 lines.
3. `du -sh server/` under 50 MB, `git status --porcelain -uall server/` clean.
4. `test_route_table.py` green, i.e. the 192 entries of the route table keep their path, method, name and order.
5. 68 Python tests and 11 JS tests run in CI, all green.
6. `uvicorn main:app --app-dir server` is still the start command, `updater.py` needs no change.
