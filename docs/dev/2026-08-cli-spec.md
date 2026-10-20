# Spec: Jarvis 007 CLI

> Dev spec, written 2026-08-03 on top of v0.16.1. Goal: bring Jarvis 007 into the terminal WITHOUT
> duplicating the runtime, by treating the CLI as a third CHANNEL next to the dashboard and Telegram.
>
> **Status: ALL 4 PHASES DEPLOYED in v0.17.0** (2026-08-04). Three places differ from this
> spec, recorded right here instead of leaving the reader to cross-check:
>
> - **The only dependency is `httpx`, `rich` was dropped.** See section 6.
> - **`render.py` is a single flat file**, the `commands/` directory is not split into six files.
>   The whole CLI fits in five files; splitting it further adds places to get lost rather than adding anything.
> - **The three questions in section 8 were settled** with the best option, recorded right in that section.

## 1. The core decision and why

**The Jarvis 007 CLI is a THIN CLIENT, not an independent agent.**

Jarvis 007 today is a 43-thousand-line Python server. Its value lies in the brain on disk, the MCP
hub, loops, Kanban work, reminders and the token-saving runtime. Nearly all of that
demands a LONG-LIVED process: loops run on a cycle, reminders wait for their time, the hub keeps
MCP connections, the capability store keeps the registry. A CLI that exits once you finish typing is no place for them.

Writing "the CLI runs by itself, no server needed" means copying all of that into a second copy.
That is exactly the trap just fallen into in 0.15.0 with the folder tree (writing a second copy of
something that already exists, then the two drifting apart), but at a hundred times the scale. **Not doing it.**

What makes the thin client option much cheaper than it first seemed: Jarvis 007 ALREADY HAS the
concept of a channel. `channel_context.build_channel_block(source, meta, ...)` builds the
per-channel context block, and `server/telegram_bot.py` is fully decoupled from the core - `main.py`
only gives it an `answer_fn` and a `command_fn`. Telegram is the second channel. **The CLI is the
third channel, going through exactly that core.**

## 2. Two benefits, and the second is bigger

**Direct benefit.** Type straight in the terminal, feed it into Unix pipelines, plug it into cron,
ask the brain on the VPS from a laptop without opening a browser.

**Strategic benefit: the installation story.** The way into Jarvis 007 today is "set up Docker on a
VPS" - a big barrier for newcomers. `pipx install javis-cli` and then typing `javis` is a much lighter
door. Given the number of people who have forked the repo, this is a more valuable lever than the convenience itself.

## 3. Current state: four things missing

Checked in the code, not guessed.

**3.1. There is no chat path over HTTP.** Chat only goes through `@app.websocket("/ws")` (main.py:6817)
and Telegram's long-polling path. No endpoint takes a question and returns an answer. Today
you cannot `curl` a question into Jarvis 007.

**3.2. Authentication only accepts cookies.** `_auth_guard` (main.py:163) checks
`cfgmod.valid_session(request.cookies.get("javis_session"))`, and `/ws` also reads `ws.cookies`.
There is no token for clients outside the browser.

There is ONE precedent in the right direction: `/hub/mcp` authenticates with `Bearer` and `hub_token()`
(mcp_hub.py:46) - a randomly generated token, stored at `STATE_DIR/.hub_token`, `chmod 600`, compared
with `secrets.compare_digest`. The CLI token design follows this precedent but must be MANY tokens,
REVOCABLE, and HASHED when stored.

One favorable detail: `_csrf_guard` runs BEFORE `_auth_guard` and deliberately skips clients that
are not browsers (they send no `Origin`). So the CLI does not run into CSRF.

**3.3. There is no packaging.** The repo has no `pyproject.toml`, no `console_scripts`. The current
ways to run are `.bat`, `.sh`, `.vbs` and Docker.

**3.4. There is no `cli` channel in the output contract yet.**
`context_compiler.ContextCompiler._channel_contract` and `_output_contract_text` only know
`telegram` and `dashboard`. Without a `cli` branch the answer comes out in the web's format:
markdown tables, embedded images `![](...)`, relative links - meaningless in a terminal.

## 4. Scope

### 4.1. Doing

- `POST /chat` one turn (synchronous) and `POST /chat/stream` (SSE) for interactive sessions.
- Personal tokens: create, list, revoke. Hashed when stored.
- A `javis-cli` package installed with `pipx`/`uvx`, command `javis`.
- A `cli` channel in `channel_context` + an output contract suited to the terminal.
- Operations commands calling EXISTING endpoints: Kanban work, conversation sessions, brain, loops, version.

### 4.2. NOT doing, even when pushed

- **No** independent agent running without a server.
- **No** duplicating the token-saving runtime, the MCP hub or the skill router into the CLI.
- **No** token enabled by default. If nobody has created a token, no token exists.
- **No** letting a token travel in the URL query string (it leaks into access logs and shell history).

## 5. Detailed design

### 5.1. Personal tokens

**Why a token rather than reusing the session:** the session was made for the browser, stored in
`.sessions.json` as `{token: created_ts}` with a 30-day TTL, and has no name and cannot be revoked
individually. A credential pasted onto another machine needs: a name to know which machine it
belongs to, individual revocation, and never sitting in readable form on disk.

**Permission level:** in v1 a token has permission EQUAL to a dashboard session. Said plainly
rather than pretending to have permission tiers: this is not a new permission level, only a new kind
of credential for exactly the permission the machine owner already has. Scope-based permissions
(`chat` versus `admin`) are left for a later version, and only done when there is real need.

**Storage.** `STATE_DIR/.api_tokens.json`, `chmod 600`, each entry:

```json
{
  "id": "tok_a1b2c3",
  "name": "home laptop",
  "hash": "<sha256 of the token>",
  "prefix": "jvs_a1b2",
  "created_at": 1754246400.0,
  "last_used_at": 0.0
}
```

The raw token has the form `jvs_<43 characters of token_urlsafe>`, **shown exactly ONCE** at
creation. After that only `prefix` remains so the user can recognize which token is which.

**Endpoints** (all sit behind `_auth_guard`, meaning you must be signed in with a session to create
a token - using a token to spawn tokens is not allowed, blocking an escalation chain):

- `POST /auth/tokens` (form `name`) → `{"token": "jvs_...", "id": ..., "prefix": ...}`
- `GET /auth/tokens` → the list, WITHOUT `hash`
- `POST /auth/tokens/revoke` (form `id`) → `{"ok": true}`

**Checking the token in `_auth_guard`.** Add a branch AFTER the cookie branch:

```
valid session  -> let through (as before)
valid Authorization: Bearer jvs_... -> let through, update last_used_at
anything else -> 401 as before
```

Compare with `secrets.compare_digest` on SHA-256, not by comparing the raw string.

**Anti-probing.** Count failures per IP in a sliding window; more than 10 in 5 minutes returns 429
for that IP for 15 minutes. Log every failure to `STATE_DIR/auth_audit.jsonl` with IP,
time, and the `prefix` tried (the raw token is not logged).

**WebSocket.** `/ws` additionally accepts the `Authorization` header. It does NOT accept it through
the query string. Browsers cannot set headers for a WS so they keep using cookies as before; the CLI can.

### 5.2. `POST /chat` - one turn, synchronous

Reuses EXACTLY the core Telegram runs every day (`_tg_answer`, main.py:8711), so it spawns no
third dispatch path. The return convention of that core is clear: **dict = a real answer (worth
saving), string = an error message (not saved)**.

Request:

```
POST /chat
  message   (required)
  brain     (default: the brain currently selected in Settings)
  session   (session id; if missing, create a new session and return the id)
```

Response:

```json
{
  "text": "...",
  "session": "sess_...",
  "engine": "ollama",
  "model": "gpt-oss:120b-cloud",
  "ctx_path": "fast",
  "ctx_in": 1288
}
```

`ctx_path` and `ctx_in` come straight from `_ctx_frame` - the CLI can print the line
"Instant · 1.3k tokens" just like the dashboard.

**About wait time.** An agentic turn can run for several minutes. This endpoint sets NO time
ceiling of its own; the client chooses. For interactive sessions, use `/chat/stream` below.

### 5.3. `POST /chat/stream` - SSE for interactive sessions

Same parameters, returns `text/event-stream`. Each packet is a `data: {...}` line wrapping the
SAME packets the WebSocket sends to the dashboard, so no second protocol is invented. The packet
types in `main.py`: `status`, `stream`, `tool_call`, `tool_result`, `response`, `error`,
`system`, `workflow`, `wait_user`, and the workflow `step_*` group.

The CLI only needs to understand the first four types; an unknown type is silently skipped rather
than breaking - this is a mandatory rule so that the server adding a new packet type does not kill an old CLI.

### 5.4. The `cli` channel

`channel_context.build_channel_block("cli", meta)` with `meta` containing `host` (machine name) and
`tty` (whether it is a real terminal). This block tells Jarvis 007 it is answering through a terminal.

The output contract for the `cli` channel (add branches to `_channel_contract` and `_output_contract_text`):

- No markdown tables, no HTML.
- No embedded images; if there is an image, print the absolute PATH.
- Short paragraphs, wrapping at 100 columns.
- Code blocks still use triple backticks (the CLI can colorize them).

### 5.5. The CLI package

A `cli/` directory in the repo, fully separate from `server/`:

```
cli/
  pyproject.toml         # package name javis-cli, command javis
  javis_cli/
    __init__.py
    __main__.py          # entry point, argument parsing
    config.py            # read/write ~/.javis/config.json
    client.py            # HTTP + SSE, attaches Bearer
    render.py            # packets -> terminal (color, spinner, context line)
    commands/
      chat.py  task.py  brain.py  loop.py  status.py
```

Minimal dependencies: **only `httpx`**. The original spec also counted `rich`, but when actually
writing it turned out unnecessary: the whole CLI uses exactly four ANSI color codes and one status
line, compact enough to write by hand in `render.py`. Pulling in `rich` would make the user download
a library that builds tables and directory trees for the terminal, while the CLI channel has a rule
that FORBIDS tables. Dropped.

**No** pulling in `fastapi`, `uvicorn` or anything from the server - the CLI package must install
on a machine that has never had Jarvis 007.

Configuration in `~/.javis/config.json`, `chmod 600`:

```json
{
  "profiles": {
    "vps": {"url": "https://javis.example.com", "token": "jvs_...", "brain": "My Bullet Journal"}
  },
  "default": "vps"
}
```

The environment variables `JAVIS_URL`, `JAVIS_TOKEN`, `JAVIS_PROFILE` override the file - so it
plugs into CI and Docker without mounting a file.

### 5.6. The command set

```
javis "question"             one turn, prints to stdout, pipeable
javis chat                   interactive session (SSE)
javis login <url>            paste a token, test the connection, save a profile
javis status                 version, running brain, savings level
javis task add "..."         assign Kanban work
javis tasks                  list work
javis brain ls [folder]      browse the brain
javis brain cat <file>       print a file's content
javis loops                  list loops
```

From `status` downwards all call EXISTING endpoints (`/version`, `/runtime/diagnostics`,
`/kanban/task`, `/files/list`, `/files/read`), with nothing to add on the server.

Mandatory Unix conventions: the answer goes to **stdout**, everything else (spinner, status,
context line) goes to **stderr**, and the exit code is nonzero on error. Without these three,
`javis "..." > file.md` would pick up junk and the whole CLI becomes useless for scripting.

## 6. Plan by phase

Each phase is usable on its own, and you can stop after any phase.

### Phase 0 - `POST /chat` (half a day)

Only add the endpoint, no CLI yet. Done with this step you can already `curl` and plug into cron.

Done when: `curl -X POST .../chat -d 'message=hello'` returns a real answer; that turn appears
in `/sessions` and in `brain/Memory/conversations` just like a Telegram turn; a test with mutation
proves it shares the core rather than spawning a third dispatch path.

### Phase 1 - Personal tokens (1-2 days)

The most sensitive part of the whole plan: it opens one more door into a server exposed to the Internet.

Done when: create/list/revoke work; tokens are hashed when stored and there is no path to read them
back raw; `_auth_guard` accepts Bearer; anti-probing works; mutation tests include at least
"comparing the raw string instead of compare_digest", "forgot to hash", "a revoked token still gets in",
"using a token to create a token".

### Phase 2 - The real CLI (2-3 days)

`javis "..."`, `javis chat`, `javis login`, the `cli` channel, packaging, `POST /chat/stream`.

Done when: install with `pipx` on a clean machine and then ask the brain on the VPS; `javis "..." | wc -l`
gives the right number (no junk on stdout); an unknown packet does not break the CLI.

### Phase 3 - Operations commands (2-3 days)

Work, brain, loops, status. No new endpoints.

### Phase 4 - `javis up`, optional (not estimated)

The CLI starts a localhost server itself if one is not running and then attaches to it. Still ONE
server, ONE brain; the CLI is only the thing that starts it. This is what could change the product's
entry point, but it is also the phase most prone to bloat, so it is split off entirely and only done
once the three phases above stand firm.

## 7. Risks and how to block them

**Opening one more door into a public server.** This is the biggest risk. Blocked with: tokens
hashed when stored, revocable, per-IP anti-probing, logging, no token spawning tokens, and no token
existing until the machine owner creates one.

**The CLI and the dashboard drifting apart.** Blocked with the principle that the CLI may only call
existing endpoints, and the SSE packets wrap the WebSocket packets themselves. Every new feature
added to the server is seen by the CLI at once, with no need to edit two places.

**The CLI package bloating along with the server.** Blocked with the fully separate `cli/` directory
and the dependency rule: only `httpx`. There is a test that checks EXACTLY the `dependencies` line
in `pyproject.toml` (not scanning the whole file - the comments there mention the names of the
banned packages, and scanning the whole file makes the test catch its own comment; this exact trap
was hit once in 0.14.3).

**Users thinking the CLI works without a server.** Blocked with documentation saying so plainly on
the very first line, and `javis`, when it cannot connect, reports the real cause with a way to fix
it, not a generic network error.

## 8. Three open questions - settled in v0.17.0

The repo owner said "build all the phases, and for whatever needs approval of a proposal, pick the
best proposals yourself". The three questions below were settled as follows, with reasons so that
when changing them later you know what is being changed.

1. **Package name: `javis-cli`, the typed command is `javis`.** Users never type the package name -
   they type `javis`, and that is still as short as hoped. In return, the package name says plainly
   that this is the CLIENT and not the whole Jarvis 007, the very thing most easily misunderstood
   about this feature. Someone who does `pip install javis` and thinks they just installed the whole
   system is a misunderstanding caused by the name itself.

2. **Phase 4 is done, but in a narrow sense: `javis up` STARTS the Jarvis 007 already installed on
   the machine, and the CLI package does not contain the server.** Stuffing the server into the CLI
   package pulls in `fastapi`, `uvicorn` and all the heavy dependencies for someone who just wants
   to ask one question from a terminal - and worse, it means two ways of installing Jarvis 007 that
   must be kept in sync forever. `javis up` goes looking for the real `server/main.py` (through
   `JAVIS_HOME`, the current directory, or `~/javis-os`), and if it cannot find it, it SAYS PLAINLY
   that it does not contain the server and points to three ways to deal with it, rather than
   reporting a vague error.

3. **Tokens have two levels from v1: `full` and `chat`.** Giving them permission equal to a session
   means every machine that wants to ask a question has to hold a credential that opens both
   `/settings` and the MCP store. The `chat` level follows a WHITE list
   `("/chat", "/version", "/health", "/sessions")` - the white direction chosen rather than the
   black one, because a black list means every new endpoint added to the server is automatically
   exposed to the narrow token.

Three accompanying safety barriers, not in the original spec:

- **No default token.** If nobody has clicked create, no token exists, and no door in other than
  the browser.
- **A token cannot spawn a token.** `POST /auth/tokens` demands a browser session. Without this
  barrier a leaked token lets whoever holds it issue itself more tokens permanently, and revoking
  the leaked one is meaningless. In contrast, REVOKING is allowed with the token being held: losing
  the machine means you must be able to take down the credential at once, even when you cannot
  open a browser.
- **Hashed when stored, compared with `compare_digest`, counting and blocking probing IPs.** The
  `auth_audit.jsonl` log only records the first 12 characters, because logs are what often get sent along with bug reports.
