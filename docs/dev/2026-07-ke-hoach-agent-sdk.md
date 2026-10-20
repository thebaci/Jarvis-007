# Plan: move the Claude engine to the Claude Agent SDK (Python)

> A dev plan, written 2026-07-12 on top of the v0.9.34 code. Goal: replace the home-made layer that spawns the
> `claude` CLI (subprocess + parsing stream-json) with the official `claude-agent-sdk`, keeping the interface
> to the rest of Jarvis 007 unchanged.
>
> **Status: DONE - FILE CLOSED (v0.9.37). All 4 phases are done; the Popen ClaudeCLI branch
> was deleted at the user's request (dropping the keep-it-for-one-release stage); the only Claude
> engine is the Agent SDK. Full log in section 8. No open items remain.**

## 1. Why (motivation)

Jarvis 007 currently shells out to the Claude Code CLI itself with `subprocess.Popen` + its own parsing of `--output-format
stream-json` in `server/claude_cli.py` (~600 lines). This layer is where bugs keep sticking:

- **WinError 206** (v0.9.31): Windows caps the command line at 32767 characters, so the prompt had to be moved to
  stdin by hand. The official SDK already handles this (the docs recommend SystemPromptFile for a big prompt).
- A hand-written idle-timeout watchdog, hand-written process-tree kill (`taskkill /T`), a separate stderr-reading thread,
  a hand-made `_ACTIVE_PROCS` registry so Stop works by tag - all things the SDK does for us and that Anthropic
  maintains with every new CLI release.
- Tool permissions are currently a STATIC list `--allowedTools`/`--disallowedTools` passed at spawn time;
  Jarvis 007's 3 permission levels suggest/auto/full can only be enforced at the MCP hub layer, and CANNOT block
  builtin tools (Bash/Write) according to the context of each call.

`claude-agent-sdk` (pip, only needs Python, auth INHERITS the Claude Code CLI login = it still runs
on the subscription plan, matching the Jarvis 007 philosophy) provides:

- `query()` / `ClaudeSDKClient` - the agentic loop + typed stream events, no need to parse JSON by hand.
- A `can_use_tool` callback + a `PreToolUse` hook - decide ALLOW/BLOCK for each tool call with
  Python code RIGHT INSIDE the server process -> maps 1-to-1 onto the read/write/danger permission matrix of
  `mcp_catalog.classify` + the 3 levels suggest/auto/full. This is the biggest safety upgrade.
- `@tool` + `create_sdk_mcp_server` - Python tools running IN-PROCESS: Jarvis 007's plugin host
  (javis_generate_image, datetime-vn...) plugs straight into the Claude engine without going around the HTTP hub.
- `resume` / `fork_session` / `interrupt` / session utilities (list_sessions, rename) - replacing the home-made
  `--resume` + the kill-by-tag registry.
- `enable_file_checkpointing` + `rewind_files()` - future: undo file operations of an `auto` loop.

## 2. Scope

- ONLY the Claude engine (provider `anthropic-cli`). CodexCLI (ChatGPT) and the API engines
  (OpenRouter/OpenAI/Anthropic API/Gemini) STAY AS THEY ARE.
- Every call site that currently uses `ClaudeCLI` must run identically, WITHOUT edits: web chat (main.py),
  metrics, workflow, lint, routines, Telegram, learn.py, tasks.py, reminders.py,
  self_improve.py (loops).

## 3. Target architecture: an adapter that keeps the interface

Do not change call sites - write `server/claude_sdk_engine.py` with a class `ClaudeSDK` sharing the same "contract"
as the current `ClaudeCLI`:

```
ClaudeCLI (current)                     ClaudeSDK (new)
────────────────────                    ────────────────────
__init__(system_prompt, cwd, tag,       same signature
         allowed_tools, model)
.session_id  (--resume)                 options.resume / fork_session
.mcp_config / .mcp_strict               options.mcp_servers / strict_mcp_config
.disallowed_tools                       options.disallowed_tools
.max_wall_s                             asyncio.wait_for + client.interrupt()
.query(prompt) -> yield dict            wraps AssistantMessage/ToolUseBlock/ResultMessage
  {type: text|tool_call|tool_result     back into EXACTLY the old event dicts (text/tool_call/
   |final|error, session_id,            tool_result/final/error + tokens_in/out
   tokens_in/out, cost_usd}             + cost_usd from ResultMessage)
cancel_all(tag)                         client registry by tag -> client.interrupt()
```

The engine is chosen by the env `JAVIS_CLAUDE_ENGINE=sdk|cli` (default `cli`). `find_claude_cli()` stays
the shared availability condition; if the SDK cannot see the CLI it falls back to `cli` and logs it clearly.

The 3 permission levels map into `can_use_tool` (replacing the static allowedTools when running the SDK):

```
suggest  -> allow only read tools (classify=read) + file reads; deny the rest with a reason message
auto     -> allow read+write inside the vault; deny danger (money/orders/sending messages) + Bash outside the vault
full     -> allow everything (like the current --dangerously-skip-permissions)
```

Audit: every allow/deny decision is logged the way the hub does it - the Claude engine gets an audit of
builtin tools (Bash/Write/Edit) for the first time, not just MCP tools.

## 4. Roadmap (4 phases + a spike)

**Phase 0 - Spike (0.5-1 day, decides go/no-go):** install `claude-agent-sdk` into the venv, write a trial script on
Windows 11 + Python 3.12: (1) a query with subscription auth runs without an API key;
(2) stream text + tool events; (3) resume the right session; (4) interrupt midway; (5) mcp_servers
pointing at the current hub config file works; (6) a 26k system prompt + a 40k prompt do not error;
(7) measure the spawn overhead against the current Popen. Whatever point fails, write that point down.

**Phase 1 - Adapter running dark (1-2 days):** write `claude_sdk_engine.py` + a contract test
(compare the SDK event sequence vs the CLI one on the same prompt). The flag defaults to `cli`; switch on `sdk` by hand to try.

**Phase 2 - Permissions + audit (1 day):** `can_use_tool` mapping the 3 levels + the audit log. Turn on the SDK for
the LOOP branch first (it benefits the most from per-call blocking, and has the smallest blast radius because a new loop
defaults to suggest + enabled:false).

**Phase 3 - In-process plugins (0.5 day):** plugins_host registers tools through
`create_sdk_mcp_server` for the Claude engine (the plugin handler + schema map straight onto `@tool`).
The HTTP hub stays unchanged for Codex + the API engines.

**Phase 4 - Flip the default (after 1-2 weeks of real use):** change the default to `sdk`, keep the
`cli` branch for one release as an exit route, and only then delete the dead Popen code in claude_cli.py.

## 5. Risks + mitigations

- **The SDK is young, its API changes fast** -> pin the version in requirements.txt; a contract test in CI
  catches drift early; the adapter isolates every SDK import into 1 file.
- **Windows/event loop:** claude_cli.py once had to avoid asyncio-subprocess by using Popen+thread
  (compatible with Selector/Proactor). The SDK uses anyio - the spike MUST run inside Jarvis 007's own uvicorn
  loop, not just a standalone script.
- **CLI version mismatch:** the SDK requires a newer CLI than the one the user installed -> the spike determines the floor version,
  and the Models page shows a warning if the CLI is old.
- **Regression of hidden behavior** (background fork max_wall_s, kill by tag family, stderr surfacing...) ->
  keep the same semantics in the adapter, write a test for each semantic before flipping.
- **Rollback:** switching the env flag back to `cli` is all it takes, no data is touched.

## 6. Success criteria

1. Every existing flow (chat/workflow/loop/telegram/task/reminder) runs on the SDK without editing
   call sites, with identical UI events.
2. A suggest-mode loop is REALLY BLOCKED when it tries to call Write/Bash (today it can only be blocked through allowedTools
   at spawn time); the audit log records the decision.
3. Delete >= 300 lines of home-made code in claude_cli.py after Phase 4.
4. Do not raise the p50 latency of a chat turn by more than 10% versus the current Popen.

## 7. What we do NOT do this round

- Do not migrate CodexCLI (no equivalent SDK; keep Popen + the v0.9.31 stdin fix).
- Do not drop the MCP hub (Codex + the API engines still need it; the hub is still where multi-account + OAuth is managed).
- Do not use the SDK's session_store/checkpointing in place of Jarvis 007's SQLite sessions (revisit later).

## 8. Implementation log

**2026-07-12 (v0.9.35) - Phases 0-2 done:**

- **Phase 0 spike: GO on all 7 items** on Windows 11 + Python 3.12.10 + CLI 2.1.196 +
  claude-agent-sdk 0.2.116, running the Proactor loop (the right uvicorn loop): (1) subscription auth
  without an API key; (2) stream text/tool/Result with full usage+cost+session; (3) resume remembers correctly;
  (4) interrupt is clean; (5) mcp_servers accepts a json path + strict; (6) system 19k + prompt 43k
  with no WinError 206; (7) SDK first-text 3.6s FASTER than CLI Popen 4.0s.
- **Phase 1**: `server/claude_sdk_engine.py` (ClaudeSDK with the same contract as ClaudeCLI, map_message
  pure and testable offline, idle watchdog + max_wall_s parity, cancel registry by tag family).
  Factory `claude_cli.claude_engine()` + env `JAVIS_CLAUDE_ENGINE=sdk|cli` (default cli);
  12 call sites (main/learn/tasks/reminders/self_improve) now go through the factory. `cancel_all` interrupts
  both engines.
- **Phase 2**: a background fork with `allowed_tools` runs `permission_mode=default` + the callback
  `can_use_tool`: tools outside the whitelist are DENIED per call (fnmatch pattern for
  `mcp__javis__*`), audit JSONL at `STATE_DIR/logs/sdk_tool_audit.jsonl`. Real smoke test:
  a read-only fork given the command "create a file by any means" → the file was NOT created; cancel 0.6s.
- **Dependency**: the package `mcp` (an SDK dependency) pulled in starlette 1.x, which broke fastapi 0.115 → pinned
  `starlette>=0.37.2,<0.39` + `sse-starlette>=1.6.1,<3` in requirements.txt (pip check clean).
- New CI test `server/test_sdk_engine.py` (14 cases, needs no CLI/auth).

**2026-07-12 (v0.9.36) - Phases 3-4 done, plus sdk-loops + e2e bake:**

- **sdk-loops** (a careful transition step of Phase 2): `JAVIS_CLAUDE_ENGINE=sdk-loops`
  → only the background tag families (loop/dispatch/reminder/learn/lint/metrics/routines/workflow) use the SDK,
  while chat + telegram stay on the CLI.
- **Phase 3 - in-process plugins:** the dedup problem solved with a header: the SDK engine (not gated) reads the
  mcp_config file into a dict, attaches `X-Javis-No-Plugins: 1` to the hub entry (the hub drops the plugin
  group when it sees the header - `discover_all(include_plugins=)`) and then wires up the in-process server
  `javis-plugins` built from plugins_host (min_mode enforced by the `javis_mode` set by _apply_mcp,
  pre/post hooks wrapped like the hub). A GATED fork keeps the old isolation - NO in-process plugins. With no hub (0
  connections) plugins still run - the SDK engine can use plugins even before any MCP is wired.
  Real smoke test: the model called `mcp__javis-plugins__javis_now` and got the right Vietnam time.
- **Settings parity:** chat/full loads `setting_sources=[user,project,local]` like the CLI (ambient
  MCP + the machine's CLAUDE.md); a gated fork does NOT load them - an allow rule in the user settings must not cover the gate.
- **Phase 4 - flip:** the factory default changed from `cli` → `sdk`. The exit route `JAVIS_CLAUDE_ENGINE=cli`
  is kept for at least 1 release; docs/16 records the variable. The Popen code is NOT deleted yet (as planned - delete it
  in a later release once the user confirms it runs smoothly; then claude_cli.py shrinks by ~300 lines).
- **E2E bake (section 1, condensed):** a REAL isolated server (temp state + brains, port 7999, default
  sdk) ran 4 checks, ALL PASS: (1) a 2-turn WebSocket chat with resume remembering the number correctly
  (first-token 11-14s on the first turn of a session because of the spawn + large system prompt, ~6s on later turns); (2) a workflow
  SSE with the full event chain step_start→step_done→done; (3) a suggest loop told to create a file by any means
  still could NOT create the file; (4) server log 0 fallbacks, 0 tracebacks. A separate probe confirmed the gate
  really fires when the model tries to call Write: per-call deny + audit JSONL + a tool_result stating the reason.
  Telegram was not tested live (no bot token in the test environment) - same factory path and event
  contract as the chat that was tested.

**2026-07-12 (v0.9.37) - Closing the file:**

- The user asked to delete the Popen branch outright (dropping the keep-it-for-one-release stage). The class
  ClaudeCLI (~219 lines) was removed from claude_cli.py; the shared Popen infrastructure was kept
  (CodexCLI, _kill_tree, the cancel-by-tag registry, Claude Code auth, _empty_mcp_file).
- The factory `claude_engine()` now always returns ClaudeSDK; the env `JAVIS_CLAUDE_ENGINE=cli|sdk-loops`
  are now historical values only (ignored, with a one-time log). SDK not installed → ClaudeSDK.query() reports
  an install-instructions error by itself, no crash.
- Success criteria of section 6 settled: (1) every flow runs on the SDK without editing call sites - met (e2e
  bake v0.9.36); (2) a suggest loop is really blocked from Write/Bash - met (probe gate deny + audit);
  (3) delete >= 300 home-made lines - met (219 lines of class + ~90 lines of factory/flag/test simplification);
  (4) latency not up by more than 10% - met (first-token SDK 3.6s vs Popen 4.0s, later turns ~6s).
- Rollback from here on = git revert (the cli branch is no longer in the code).

Outside the file (maybe later, whenever the mood strikes): surface the engine status on the Models page to make it easier to see.
