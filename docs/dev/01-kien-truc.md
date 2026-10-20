# 01 - Architecture overview

## The core idea (read this first)

Jarvis 007 **does not call a model API directly**. Jarvis 007 borrows the vendor's **agent-style CLI** (Claude Code, Codex) as its brain, so it can use the very **subscription plan** the user is already paying for instead of making them buy a separate API. That brain already knows how to read and write files, call MCPs, run commands and use skills. Jarvis 007 wraps a dashboard, a Second Brain, and a permission-control layer around it.

An important architectural consequence: **Jarvis 007 is an orchestration layer, not an inference layer.** When you debug "why did Jarvis 007 answer wrong", ask first: what prompt was injected, which tools are allowed, which brain does the cwd point to. Do not fix the model.

There is still a pure API path (OpenRouter/OpenAI/Anthropic/Gemini) for people without a CLI subscription, but that path is **plain chat, without the CLI's native MCP**, compensated by the in-process hub (see [page 04](04-engine-hub-plugin-skill.md)).

## Four layers

```
┌─────────────────────────────────────────────────────────┐
│ 1. DASHBOARD  (dashboard/*.js, plain JS + Alpine)       │
│  Knowledge graph + navigation rail + voice (Web Speech) │
└───────────────┬─────────────────────────────────────────┘
                │ WebSocket /ws  (chat streaming)
                │ REST  /settings /skills /files /kanban ...
┌───────────────▼─────────────────────────────────────────┐
│ 2. SERVER  (server/main.py - FastAPI, ~120 endpoints)   │
│    + feature modules: learn, tasks, reminders,          │
│      self_improve  (each carries its own APIRouter)     │
└───────────────┬─────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
┌───────▼──────┐  ┌──────▼──────────────────────────────┐
│ 3. ENGINE    │  │ 4. MCP HUB  (mcp_hub.py)            │
│  the brain   │◄─┤  the ONLY tool gateway for engines  │
│  claude_sdk  │  │  - Claude/Codex see the hub as one  │
│  codex CLI   │  │    http MCP server named "javis"    │
│  engine.py   │  │  - API engines call it in-process   │
│  (plain API) │  │  Hub enforces 3 permission levels   │
└──────────────┘  │  plus audit                         │
                  └──────┬──────────────────────────────┘
                         │
              ┌──────────┴───────────┬──────────────┐
              ▼                      ▼              ▼
        External MCPs (POS,     Python plugins   Skill router
        Ads, Calendar...)       (system/plugins) (SKILL.md)
```

And running across all of them: the **BRAIN (vault)** - a folder of `.md` files that is the whole memory plus capability of Jarvis 007. See [page 05](05-brain-vault.md).

## Where a chat turn goes

This is the path to memorize for debugging anything:

1. **Browser** - the user speaks or types. `dashboard/voice.js` (Web Speech API) or `#chatInput`. `dashboard/app.js` opens the WebSocket `/ws` and pushes the message up.
2. **`main.py` `/ws`** (around line 4155) - receives the message and builds the **system prompt**: the contents of `CLAUDE.md` + the brain's `MEMORY.md` + the skill index + channel context (`channel_context.py`) + usage figures.
3. **Pick the brain** - `_effective_main(cfg)` (`main.py:488`) reads `settings.json → model.main = {provider, model}` and returns the provider that is currently MAIN.
   - `anthropic-cli` → `claude_sdk_engine.py` (through the factory `claude_cli.claude_engine`)
   - `openai-oauth` → `CodexCLI` in `claude_cli.py`
   - `openrouter` / `openai` / `anthropic-api` / `gemini` → `engine.py` (plain chat, streams tokens)
4. **The engine runs** and streams out `{type: text | tool_call | tool_result | final | error}` events. This is the **shared contract** every engine must follow, see the docstring at `claude_sdk_engine.py:1`.
5. **A tool call** (if any) goes through the **MCP Hub**: the hub merges the tools of every connection, checks permission, runs it, writes the audit.
6. **Streams back to the browser** over the WebSocket. `chat-render.js` renders markdown, `voice.js` reads it aloud.
7. **After the turn** - `learn.py` rewires memory (debounced, read-only, undoable); `sessions.py` saves the conversation into SQLite + FTS5.

## Where state lives (easy to get wrong)

There are **three** different state stores, do not mix them up:

| Store | Path | Holds | Owner |
|-----|-----------|---------|-----------|
| **STATE_DIR** | `server/` (default), or `$JAVIS_STATE_DIR` = `/data/state` on Docker | `settings.json` (has secrets, encrypted), branding, hub token, plugin enable-state, `conversations.db` | Jarvis 007, gitignored |
| **BRAIN (vault)** | `brains/<name>/` | Notes, Wiki, Memory, skills, agents, workflows, loops | The user, can be pushed to GitHub |
| **Code tree** | `server/`, `dashboard/`, `system/` | Source code plus bundled plugins/loops/catalog | The repo. **Read-only on Docker** |

The trap: inside the container, the code tree is read-only. Anything Jarvis 007 writes by itself **must** go through `STATE_DIR`. That is why a custom logo lives in `STATE_DIR/branding` and not in `dashboard/`, and why the enable-state of bundled plugins lives in `STATE_DIR/plugins.json` instead of editing the app's `plugin.yaml`.

## Where to enter the code

| To understand | Open this file |
|-----------|---------|
| The whole API plus the app lifecycle | `server/main.py` (read the `# =====` banner bands, see [page 02](02-backend.md)) |
| Configuration, paths, auth | `server/config.py` |
| The Claude brain | `server/claude_sdk_engine.py` |
| The plain-API brain | `server/engine.py` |
| Where tools go, where permission blocks them | `server/mcp_hub.py` + `server/mcp_catalog.py` |
| The UI, the rail, the pages | `dashboard/console.js` |
| Chat, WebSocket, voice | `dashboard/app.js` + `dashboard/voice.js` |
