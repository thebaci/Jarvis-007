> **REMOVED in 0.64.20 (2026-09-23).** The feature in this document ran from 0.64.0 to 0.64.18
> and was then removed entirely. The document is kept as a decision record, not as a guide.
>
> Reason for removal, in short: Jarvis 007 runs on a rented server, and chatgpt.com's Cloudflare blocks
> browsers coming from data-center IPs. I read two projects that do the same thing (`miuuyy/codex-chatgpt-web`,
> `XiaoDuoYa/codex-with-chatgpt`): BOTH run the browser on the user's own machine, and
> neither has a way through Cloudflare from a server. Calling `backend-api` directly is dead too
> (Sentinel's Turnstile layer no longer completes since 2026-09-08).
>
> The original goal (using an unlimited ChatGPT plan for everyday work) moved to the REVERSE
> direction: ChatGPT calls into Jarvis 007's MCP hub through an official connector, instead of Jarvis 007 driving the
> ChatGPT page.

# ChatGPT Web: a model in the ChatGPT card

**Version:** v4.1 (section 14 records what went into `main` in 0.64.0). v4.0: merged the cross-review `JAVIS_OS_WEB_ENGINE_SPEC.md` (2026-09-22) into v3.0:
added sections 18-22, and CORRECTED one place where v2.0/v3.0 overstated things (section 3).
**Status:** scope and purpose settled. **No code written yet**; the only gate is the spike in
section 13.
**Scope:** one new model id in the existing ChatGPT card, one transport module, one text-based
tool translator. No new provider.
Document for people who edit the core.

---

## Project owner's decision, 2026-09-22

v1.0 proposed ChatGPT Web as a **tool** rather than as the **brain**, on the grounds that the web quota is counted
per message, so a tool loop burns through it very fast.

The project owner heard that argument twice and **decided otherwise**: ChatGPT Web must be **selectable in the
model picker, inside the ChatGPT card**, like an ordinary model. That is the decision, and this document
follows it.

**Second decision, same day.** The first v2.0 draft set its own tool-loop cap of 6, fearing a single
turn could eat 31 messages. The project owner said **their chat plan has very large capacity, so the message count is no concern**.
The separate cap was dropped, going back to the shared cap of 30.

But dropping that cap means another constraint takes its place, and the new one is harder: **time**.
Section 5 is rewritten around that constraint.

**Third clarification, and this is where the previous two versions got the purpose WRONG.** v1.0 through v2.1 all wrote as
if `chatgpt-web` were a fallback path: when Codex runs out of quota, switch to it. The project owner said plainly that it is **not
so**:

> The web version is for doing ordinary tasks, because it has unlimited quota. Choosing web or Codex
> depends on which is more convenient, not on which one still has quota. The web version has some limitations,
> and those are accepted.

The everyday work the project owner described: Q&A, image generation, reminders, reading, understanding, planning,
implementing, programming.

Three consequences, and they change the whole roadmap:

1. **The old Gate 0 is dead.** It asked "has the Codex pool run dry yet". That question no longer matters. The only
   gate left is the spike in section 13: does the protocol work at all.
2. **The Task Handoff Packet leaves the scope of this project.** It was born for the scene "Codex dies halfway
   and web takes over". It is still worth doing for Jarvis 007, but it is not the job of this
   document.
3. **Most of the work the project owner described costs 1 to 3 tool rounds, not 15.** Section 5 is recalculated
   accordingly, and the roadmap in section 14 is reordered so the most-used thing comes first.

Kept from v1.0: the transport (section 9), the state ledger and error classification (section 10), the safety
boundary (section 11), the spike and the kill criteria.

---

## 1. The right shape: a MODEL in the ChatGPT card, not a new provider

This is the decision that makes this project cheap or expensive.

Jarvis 007 already has the provider `openai-oauth`, labeled `OpenAI OAuth (ChatGPT)`, `kind: "oauth"`,
`catalog_key: "openai-oauth"` (`main.py:1520`). That provider is **already** covered everywhere:
72 branches of `provider == "..."`, the model picker, the catalog, Telegram's `/model`, the Models page card,
the subscription label, the context budget.

So **do not add a provider**. Only add **one model id** to the catalog of the existing provider:

```
ChatGPT card
├── gpt-5.5            (via Codex CLI)
├── gpt-5-codex        (via Codex CLI)
└── chatgpt-web        (via browser, chat plan)   ← only this line is added
```

This card's `default_models` is deliberately left empty because the Codex app-server's `model/list` is the source of
truth (`main.py:1521`). So the insertion point is `_fetch_provider_models` (`main.py:4568`), after
`openai_oauth.list_models` (`openai_oauth.py:470`) returns: **append `chatgpt-web` to the end of the
list**, and append it **even when `list_models` returns `None`**.

The phrase "even when it returns None" is not a minor detail. Today the ChatGPT card reports not ready if the
machine has no Codex CLI (`main.py:4643`). After this change, **ChatGPT Web can run on a machine
WITHOUT the Codex CLI installed**, so `_provider_ready_msg` must treat the card as ready when **either one** holds:
the Codex CLI is usable, **or** the browser session is logged in.

## 2. Two traps to handle before anything else

### 2.1. Three dispatch points, and `_codex_safe_model`

Three places run a turn for `openai-oauth`, and all of them must branch when the model is `chatgpt-web`:

| Place | What it does now |
|---|---|
| `main.py:12432` | Dashboard chat, builds a `CodexCLI` |
| `main.py:16848` | Telegram, builds a `CodexCLI` |
| `main.py:2153` | Compact flow, calls `engine.openai_responses_stream` |

**The trap to handle BEFORE anything else.** Both of the first two places open with:

```python
actual_model = _codex_safe_model(api_model)
```

`_codex_safe_model` (`main.py:1737`) coerces every model that is not in the catalog and does not
end in `-codex` back to the default Codex model. Worse: when it coerces, the caller **also overwrites the setting**
with `_set_main_model`, **and overwrites the session's pinned model** (`store.set_pinned_model`), then
reports "automatically switched to ..." (the actual message in the code is Vietnamese: `đã tự đổi sang ...`).

That means if this is not handled, when the machine owner picks `chatgpt-web`, Jarvis 007 **silently flips back to Codex
and writes that choice over the settings**. Choose once and it is lost for good.

Two mandatory steps:

1. `_codex_safe_model` treats `chatgpt-web` as valid (it will be in the catalog after section 1, but
   a test must lock this in; do not rely on the catalog happening to contain it).
2. The `chatgpt-web` branch forks **before** `_codex_safe_model` is touched, because this model does not go through
   Codex at all.

`_is_codex_model` (`main.py:1749`) infers the vendor from the model name for old agents. `chatgpt-web` is in the
`openai-oauth` catalog so this function returns `True`, as intended: it still belongs to the ChatGPT vendor.

### 2.2. The API engine's file tools are LOCKED INSIDE THE BRAIN and cannot see the repo

This is a hard block, and it is bigger than everything else in this document. Found in the cross-review
of 2026-09-22; verified against three lines of code.

The Coding page switches `cwd` to the repo through `_cwd_luot_chat` (`main.py:4800`), but **only the CLI engines
benefit**, because they have native file tools that run relative to `cwd`.

API engines have no native file tools. They read and write through the hub, and the hub gets vault_root from
`main.py:2190`:

```python
vault_root = _brain_root(brain) if brain else None
```

**Unconditionally. It never asks `coding_store.cwd_cua_phien(sid)` even once.** And
`_builtin_tools._read` (`mcp_hub.py:475`) blocks every path outside the vault and returns verbatim (the string is
Vietnamese in the code, so it is kept as is; it means "the path is outside the brain currently being worked in, so this tool cannot read it"):

> `ERROR: '<path>' nằm ngoài bộ não đang làm việc nên tool này không đọc được.`

Consequence: **`chatgpt-web` sitting in a Coding session cannot read a single file of the repo.**
It can read the brain. It cannot read the repo.

That means even if the text-based tool protocol works perfectly, the model still cannot code. The fix
is in section 7.

This is a hard block **only for the programming branch**; it does not block Q&A, image generation, reminders, reading the
vault or skills. That is why the roadmap puts it in Phase 4 and not first (section 14 explains).

Note an old boundary that is there on purpose, so do not break it by mistake: the Codex branch states "The hub still points at the BRAIN even when
cwd is the repo: MCP, cron and reminders belong to the user's brain, not to the source tree
that happens to be open" (`main.py`, `openai-oauth` branch). Right for MCP, cron, reminders. Wrong for the **file**
tools. So section 7 separates those two instead of changing the vault_root of the whole hub.

## 3. Tools: this model MUST have tools, and not to please anyone

Six places in the code ask "is this a subscription brain with real tools" with exactly one expression,
`kind in ("cli", "oauth")`:

```
main.py:12101   main.py:15091   main.py:15568   main.py:16729
fast_path_runtime.py:282        adaptive_context_runtime.py:322
```

**Correction in v4.0.** v2.0 and v3.0 wrote that these six places "govern the fast-path shortcut, the context
budget and the subscription label", and that if `chatgpt-web` had no tools then "all six lie".
Reading each place again, that was **overstated**:

| Place | What it actually does |
|---|---|
| `main.py:12101`, `main.py:16729` | Only schedules `_schedule_registry_discovery_shadow`, i.e. a SHADOW run |
| `main.py:15091` | The `thue_bao` (subscription) label on the diagnostics page |
| `main.py:15568` | A branch on `kind_hien_tai` |
| `fast_path_runtime.py:282`, `adaptive_context_runtime.py:322` | Change real behavior, but the **canary allocation defaults to 0** |

So the consequence of breaking this invariant is **small**: shadow and labels, not a broken chat turn.
It still has to be done right, but do not use it as a reason to block Phase 1.

Giving it tools keeps the invariant intact, touching none of those six places. On top of that: that is
exactly what the project owner wanted from the start, "still able to use tools like the Codex version".

**Hand-off for Phase 1 (plain chat, no tools yet):** during that window `chatgpt-web` carries
`kind: "oauth"` without tools. That is acceptable because the consequence is only shadow and labels, but there must
be one line in the run log saying so plainly, otherwise the diagnostics page says the wrong thing and nobody knows why.

**But it must say exactly WHICH tools.** `CLAUDE.md` already splits two classes:

| Class | What it has |
|---|---|
| CLI (Claude Code, Codex, Grok) | Native file tools, **Bash**, **WebFetch/WebSearch**, **Task**, session resume |
| API (six engines) | Vault tools through the hub, MCP, skills, `javis_task`, `javis_schedule`, plugins. No Bash, no WebFetch, no Task |

`chatgpt-web` sits in the **API class**, not the CLI class. It has
`javis_read_file` / `javis_list_dir` / `javis_write_file` / `javis_use_skill`, every connected MCP,
every plugin, `javis_task`, `javis_schedule`.

Two things from the CLI class it still does **not** have, and the model description in the picker must say so plainly:
**WebFetch/WebSearch** and **Task** (parallel sub-agents).

As for running commands, **section 7.2 lifts that limit**, through `javis_run_command` rather than native Bash and
not a PTY. But as the cross-review pointed out: granting it that way gives it to **all six API engines too**,
so it is a decision for the project owner, not an implementation detail.

### 3.1. A real count of the tools, so nothing is promised by mouth

Counted from `mcp_hub.py` and `system/plugins/` on 2026-09-22:

| Group | Tools |
|---|---|
| Builtin vault | `javis_read_file`, `javis_list_dir`, `javis_write_file`, `javis_use_skill`, `javis_connections` |
| Orchestration | `javis_task`, `javis_schedule`, `javis_workflow`, `javis_ui` |
| Utilities | `javis_now`, `javis_date_add`, `javis_generate_image`, `javis_add_mcp`, `javis_tool_stats`, `javis_youtube_read` |
| Machine | `javis_app_list`, `javis_app_open`, `javis_app_close` |
| Meta, Zalo | `meta_ads_*` (4), `fb_pages_*` (6), `fb_monitor`, `zalo_send_image` |
| MCP | Every connected connector |

About **26 bundled plugin tools plus 5 builtins**, plus all the MCPs.

Two points that look missing but actually exist:

- **Attachments in the chat frame can be read.** The hub lets `javis_read_file` read the extra `.staging` area
  when `staging=True` (`mcp_hub.py:447`), so a file the user just dragged in still reaches the model.
- **Image generation still works.** `javis_generate_image` calls Codex Responses with OAuth
  (`system/plugins/image-chatgpt/`), independent of the browser session.

### 3.2. Six things missing ONLY from the web version, outside the class table

This is the part that is in no class table and is the easiest to overlook.

1. **No function calling.** Nothing forces the model to return the right format other than instructions in the
   prompt. The six API engines have the tool-call format guaranteed by the vendor; this model does not. This
   is the biggest technical risk of the whole project, and it is the fifth kill criterion in section 13.
2. **No system role.** Jarvis 007's whole system prompt (CLAUDE.md, MEMORY, the skill router, the
   tool list) has to be stuffed into the **first message** as plain text. Codex has its own
   `instructions` field (`engine._codex_input`); the web has nothing of the kind.
3. **The account's own custom instructions and Memory get mixed into every turn.** The API never
   has this. A custom instruction like "always answer very briefly" would squeeze every answer
   Jarvis 007 asks for, and the symptom would look like Jarvis 007 being broken. **The Models card must tell the user to turn off Memory and
   custom instructions, or use a separate account.**
4. **No token count.** `usage_store.record` would record 0, so the Usage page and the Savings page
   are **blind to this model**. The message counter in section 10 is the only substitute, and it is a different
   unit, not comparable with the other models.
5. **Reasoning effort cannot be adjusted.** There is no `reasoning effort`, and no prompt
   caching either. The web decides by itself according to the model chosen in its own interface.
6. **Images are the other way round.** Jarvis 007's API class currently does not send images to the model (there is no
   `image_url` or `input_image` anywhere in `engine.py`), while ChatGPT Web itself views images
   very well. Exploiting that means driving the file upload widget; it is outside this document, noted in section 17.

## 4. The text-based tool protocol

ChatGPT Web has no function calling. So the tool loop has to run in text, ReAct style.

Jarvis 007 **already has the loop**: `engine.openai_chat_with_mcp` (`engine.py:1740`), the loop cap
`_max_tool_rounds` (`engine.py:1680`), the anti-stuck brake `_LapGuard` (`engine.py:1697`), tool routing
through `mcp_hub`. Only the **translator** at the two ends is missing:

**Sending end:** instead of attaching `tools=[...]` as a schema, build the tool list as text and insert it into
the prompt, with a rule: to call a tool, return **exactly one block** fenced with ```` ```javis_tool ````
containing the JSON `{"name": ..., "arguments": {...}}`, and **write nothing else** in that turn.

**Receiving end:** peel that block out of the reply. If there is a block, run the tool through the hub and send the result
back as the next message. If there is no block, that is the final answer.

Three boundaries of the translator:

- **A broken block gets reported, not guessed at.** JSON with bad syntax, a missing `name`, a tool that does not exist: send
  back a message saying exactly what is wrong, counted as one round. Guessing the model's intent is a sure way to write to the wrong file
  one day.
- **`_LapGuard` is used as is.** Calling the same tool again with the same parameters is a general
  disease, not one specific to any model.
- **Enforce `min_mode` at the hub like every other engine.** When the model types out the name of a tool that the current
  permission level does not allow, the hub blocks it; the translator does not judge that itself.

### Lazy mode doubles the number of rounds, which must be known up front

The hub has a lazy layer (`mcp_hub.py:612-669`): default `auto`, switched on when the pool exceeds **40 tools** or
**6000 characters of schema**. Once on, MCP tools are hidden behind two meta-tools `javis_search_tools` and
`javis_run_tool`, so **each use of an MCP tool costs two rounds**: search, then call.

For an API engine those two rounds are two HTTP calls, and nobody notices. For `chatgpt-web` they are
**two typing turns into the chat box**, which doubles both the time and the message count. Any machine that has connected a few
connectors hits the threshold right away.

The translator **must not switch lazy off by itself** as a shortcut: switching it off pushes hundreds of schemas straight into the first
message, and the first message already has to carry the whole system prompt (section 3.2 point 2). This is a real
trade-off, written down so that section 5 counts the time correctly; it is not something this document can fix.

## 5. The cost of a turn: messages are cheap, time is expensive

With this model, **one tool round is one web message**. One chat turn costs:

```
1 message  +  number of tool rounds
```

The project owner has settled it: the chat plan is very large, **the message count is not a constraint**. So the shared cap
of 30 rounds (`JAVIS_MAX_TOOL_ROUNDS`) stays, with no separate cap. The variable `JAVIS_WEB_MAX_TOOL_ROUNDS` still
exists, defaulting to the shared cap, so anyone on a smaller plan can lower it themselves.

### The real constraint is TIME, not messages

Dropping the message cap exposes a scarier number. One web round takes **20 to 40 seconds**. This number
is an **ESTIMATE, not measured on a real machine**; the spike in section 13 gives the real figure, and every multiplication below
has to be recalculated from it. Do not take it as an architectural assumption.

```
30 rounds × 30 seconds  ≈  15 minutes for ONE chat turn
```

And there is a further factor of two from section 4: the hub's lazy mode turns each MCP tool use into **two rounds**
(search, then call). So 30 rounds in practice is only **15 MCP tool calls**, in 15 minutes.

The comparison shows the problem: Codex runs the same 30 rounds in a few tens of seconds, because each round is one
API call and not a turn typed into the chat box and then waiting for it to stream out.

So the brake changes from counting messages to **counting seconds**:

- `JAVIS_WEB_TURN_BUDGET_S`, **default 600** (10 minutes per turn). When the budget runs out it stops
  exactly as if it hit the round cap: returns what it has along with an explanation, never cutting off silently.
- **Show progress while running.** Which round, how long it has taken. After fifteen minutes of silence the
  user will think it hung and press Stop, even when it is running correctly.
- The turn counter (`so_luot_trong_ngay`, section 10) is **kept**, but with a reduced role: it is no longer a
  brake, only the one thing Jarvis 007 knows about consumption, since this model does not return token counts
  (see section 3.2).

### But most everyday work only costs 1 to 3 rounds

The 15 minutes above is the WORST case, and it only happens with multi-step programming.
Counted against the exact list of work the project owner described:

| Work | Tool rounds | Estimated time |
|---|---|---|
| Q&A, planning, reading and understanding a passage | 0 | one web turn |
| Image generation (`javis_generate_image`) | 1 | under 1 minute plus image render time |
| Reminders (`javis_schedule`) | 1 | under 1 minute |
| Reading a file in the brain, using a skill | 1-3 | 1-2 minutes |
| Multi-step programming | 10-30 | 5-15 minutes |

So **latency is not a problem for most everyday work**. It only becomes a problem in the programming branch,
and that is also the branch where Codex is more convenient. Choosing whichever is more convenient is the correct way to
use it, not a stopgap.

One precise point about image generation, so there is no confusion later: `javis_generate_image` calls
`image_gen.generate_chatgpt`, which goes through the **OAuth Responses** path, not the browser session.
That means it consumes the plan's image allowance through the API path, not web chat turns. It works; just
do not confuse it with the web quota. To have an image generated directly inside the web session you would have to pull the image from the page
and download it, noted in section 17.

## 6. Conversation thread

A conversation on chatgpt.com has its own id and can be continued, just like `codex_thread_id`.

`sessions.py:1160` already has a table mapping engine to the thread-keeping column, with a note right in the code:
"Adding a new session-keeping engine means adding one line here, do not scatter another clear command into
`main.py` - that is exactly how this table missed two engines." (The comment in the code is in Vietnamese.)

Follow that note: add a column `web_thread_id` and one line in `_MACH_NATIVE`.

The invariant of `clear_native_threads` stays and applies to this model as well: a turn run by
another engine leaves a gap in the web thread, so it is invalidated. Changing model mid-session opens a new web
thread; it does not continue the old one.

## 7. Coding Tool Context: what must be done before Phase 2

Section 2.2 pointed out the hard block: API engines read and write through the hub, and the hub is locked inside the brain. This section is
how to remove it.

### 7.1. Separate the vault_root of the FILE TOOLS from the hub's vault_root

The old boundary was half right. MCP, cron and reminders belong to the brain and stay as they are. The **file** tools
have to follow wherever the work is happening.

So `_builtin_tools` takes a second root, and `discover_all` passes it down:

```
vault_root      = brain          ← MCP, cron, reminders, skills: NO CHANGE
workspace_root  = session cwd    ← file tools: repo/worktree when on the Coding page
```

`workspace_root` comes from exactly the source the CLI engines are using, not inferred from the channel name:

```python
workspace_root = coding_store.cwd_cua_phien(sid)   # "" = not a coding session
```

When it is empty, `workspace_root = vault_root` and everything runs as it does today. This is the condition for this
change to touch no ordinary chat turn.

`_safe_read_path` lets through paths inside **either one** of the two roots, and the error message must say
clearly which root applies, because the current message ("outside the brain being worked in", Vietnamese in the code) will have the wrong meaning
the moment there is a second root.

### 7.2. `javis_run_command`, NOT the PTY of `terminal.py`

The cross-review of 2026-09-22 rejected the proposal to let the model drive the PTY of `terminal.py` directly, and
rejected it rightly. That file's own docstring says:

> The shell inherits the server's env (which includes the API keys in .env) - just like every other terminal of the
> machine owner, but you need to know it is there. (`terminal.py:29`)

A PTY is also a **long-lived** shell with state, made for a human to sit and type into. Handing it to the model
grants both an env containing keys and a stateful session that nobody can audit.

So a dedicated tool, one command at a time, stateless:

| Parameter | Meaning |
|---|---|
| `command` | The command to run |
| `cwd` | **Ignored if it lies outside `workspace_root`.** Defaults to `workspace_root` |
| `timeout` | Cap in seconds, with a default and an upper limit |

Required: an **allowlisted** env, not inheriting the server env; a cap on output size; cancellable; audit logging; and the permission level
mapped directly from the session's chip:

| `coding_store` level | `javis_run_command` |
|---|---|
| `suggest` | Does not run. Returns the proposed command as text |
| `auto` | Only commands in the allowlist, and only inside `workspace_root` |
| `full` | Runs in full |

**The `auto` level's allowlist must be written out as a list**, not guessed each time. This is the
first time Jarvis 007 needs a real command allowlist: Codex has no per-call allowlist, it only blocks at the
sandbox layer (`aux_engine.py:18-21`), and Claude Code has an allowlist but it belongs to that CLI alone. Treat this
as a design item, not a line of configuration.

This tool's `min_mode` is `full` by the hub's classification, and the session permission level tightens it further
on top. Two layers, neither replacing the other.

### 7.3. The minimal coding toolset

With `workspace_root` and `javis_run_command` in place, the rest is almost free, because they are just
wrapped git commands:

```
read file, write file, list, search in files   ← builtins, change the root and done
git status, git diff                          ← javis_run_command
run tests                                     ← javis_run_command
```

This is what makes `chatgpt-web` able to code. The text-based tool protocol is only the way of calling; without
this section, after the call it still could not touch the repo.

### 7.4. Boundary

This change **reaches all six API engines**, not just `chatgpt-web`. That is a good thing (they
cannot code right now either), but it has to be said: this widens capability for a group of engines, so it
is a decision for the project owner and not an implementation detail.

Three things **do not** change: the vault_root of MCP, of cron, of reminders.

## 8. The ChatGPT card on the Models page

The card already exists; add to it:

- A web session status line: `Signed in` / `Not signed in` / `Resting until HH:MM`.
- A **Open sign-in window** button. There is no password field, ever.
- A counter `asked N turns today` plus the most recent time the cap was hit.
- The `chatgpt-web` model description says plainly: no WebFetch/WebSearch, no Task, each tool
  round takes 20 to 40 seconds (an estimate, section 5).
- **A note to turn off Memory and Custom instructions** on the ChatGPT account itself, or to use a separate
  account. Section 3.2 point 3 is the reason: if they stay on, personal settings squeeze every question Jarvis 007 asks,
  and the symptom looks like Jarvis 007 being broken.

The card is ready when the Codex CLI is usable **or** the web session is signed in (section 1).

## 9. Transport: let the page authenticate itself, Jarvis 007 only reads the wire

Kept as is from v1.0. Three possible paths, and the third is chosen:

| Path | Why rejected / chosen |
|---|---|
| Rebuild the `backend-api/conversation` request with cookies | Has to solve the sentinel proof-of-work and get past Cloudflare by itself. Breaks every few weeks. **Rejected** |
| Scrape the DOM, read the last chat bubble | Breaks every time the UI changes. **Rejected** |
| **Tee `window.fetch` inside the already signed-in page** | The page handles auth, Cloudflare, PoW itself. Jarvis 007 only reads the stream the page was receiving anyway. **Chosen** |

Mechanism:

1. Open Chromium with `launch_persistent_context` pointing at `STATE_DIR/web-profiles/chatgpt/`.
   The machine owner signs in by hand exactly once.
2. `add_init_script` wraps the page's `window.fetch`, teeing the SSE stream out to a callback registered with
   `expose_binding`. About 30 lines of JS.
3. Type the prompt into the compose box, send it, and read from the teed stream until it ends.

Jarvis 007 never touches cookies, tokens or proof-of-work. A UI change does not break it, and a change in the auth mechanism
does not break it.

**One turn at a time.** Same profile, same account, so the module holds a lock; a second turn
queues, and past `QUEUE_TIMEOUT` it returns `DANG_BAN` and does not open a second context.

Borrow, do not rebuild:

| Need | Reuse |
|---|---|
| Chromium download, detecting an installed Chrome/Edge, `PLAYWRIGHT_BROWSERS_PATH` | `optional_tools.py` |
| Tool loop, round cap, stuck brake | `engine.py:1680`, `engine.py:1697`, `engine.py:1740` |
| Tool routing, `min_mode` enforcement | `mcp_hub.py` |
| Silent child processes on Windows | `winproc.py` |
| Reading the "limit reached" message and the reopen time | `limit_learner.parse_subscription_limit`, `subscription_span` |
| Where to store state | `config.STATE_DIR` |

**Code surface:** `server/web_chat.py` (transport plus tool translator), the three dispatch branches in section 2,
one line in `_fetch_provider_models`, one column plus one line in `sessions.py`, and the Models card part.

## 10. State and error classification

The ledger `STATE_DIR/web_chat.json`:

```
last_success     last_error     failure_count
cooldown_until   auth_state     so_luot_trong_ngay
```

This is the first implementation of the **provider state machine** that the architecture review of 2026-09-22
said was missing (`aux_engine._FallbackChain` currently tries blindly, with no memory of which link just died). Written
in a way that can be generalized, so it can later be carried over whole to another vendor.

| Code | When | What Jarvis 007 does |
|---|---|---|
| `CHUA_DANG_NHAP` | the profile has no session | Error with a line inviting the user to click "Open sign-in window" |
| `HET_LUOT` | the page reports hitting the message cap | `parse_subscription_limit` gets the reopen time, sets `cooldown_until`. During cooldown it refuses immediately, without opening the browser |
| `THU_THACH` | Cloudflare or a captcha | Short cooldown, tells the machine owner to open the window and solve it by hand |
| `QUA_HAN` | the stream does not end within `timeout` | Retry exactly ONCE then report the error |
| `KHONG_CO_TRINH_DUYET` | no Chromium/Chrome yet | Just points to `optional_tools` to download |
| `DANG_BAN` | another turn is running | Queue, and report busy once past the deadline |

`HET_LUOT` in the middle of a tool round is a special case: **keep what has been done**, say clearly which
round it stopped at, and put it into `limit_resume.REGISTRY` to re-run automatically when the plan reopens, like the other engines.

When `failure_count` reaches `NGUONG_NGAT` it enters a long cooldown. There is no infinite retry loop.

## 11. Safety boundaries and risks

**Terms of service.** OpenAI forbids automated access to the service outside the API path. This is the
machine owner's own account, on their own machine, but if it is detected, what is lost is the **paid
subscription plan**. This is exactly the same kind of warning that `CLAUDE.md` makes Jarvis 007 state plainly about running
the Claude Pro/Max plan in the background. No wrapping it up.

Therefore:

- The `chatgpt-web` model only appears in the picker when the environment gate `JAVIS_ENABLE_WEB_CHAT=true`
  is on. Turning it on is a deliberate action.
- The model description says plainly that it runs on a browser session, so whoever turns it on knows what they are turning on.
- **No background job may pick this model by itself.** Loops, reminders, Kanban tasks, `_FallbackChain`
  all exclude it. It only runs when a person sitting in front of the screen chooses it.

**VPS constraint.** It needs a browser with a real signed-in profile. On a VPS
(`docker-compose.hostinger.yml`) it needs xvfb, and a data-center IP gets challenged far more
often. In practice: **it only runs reliably on a home machine or the desktop build**. On a VPS the model hides itself from the
picker and says why, instead of appearing and then failing.

**Data.** The `javis_read_file` tool returns vault content, and that content goes straight into the chat box of
chatgpt.com. Jarvis 007 prints what was sent before each tool round.

## 12. Switching back and forth between web and Codex

The purpose stated in the opening block is "use whichever is more convenient", so switching must be as light as changing
model, not like changing configuration.

**The mechanism already exists, nothing new to build:** the session store keeps the model PINNED PER SESSION
(`sessions.set_pinned_model`, `sessions.py:740`; endpoint at `main.py:14349`). So:

```
Session "daily Q&A"          pins chatgpt-web
Session "fix repo javis-os"  pins gpt-5-codex
```

The two sessions live side by side, each remembering its own model, neither stepping on the other. Changing within one session
means picking again in the model picker like any other model.

This is also why section 2.1 matters so much: `_codex_safe_model` currently **overwrites the session's pinned
model too**. Without blocking it, the very mechanism that serves this purpose breaks.

## 13. One-day spike, with kill criteria

Set the criteria **before** running:

- 10 consecutive questions in 30 minutes, **at least 9 return the correct content**
- **No challenge at all** needing a human hand in those 10 turns
- Median latency **under 60 seconds** with a prompt of about 2,000 tokens
- The tee snippet captures the stream in **both scenes**: cold open and a tab already open
- **One tool round goes all the way through**: the model returns a correct ```` ```javis_tool ```` block, Jarvis 007 can peel it
  out, run it, send it back, and the model uses that result to answer

The last criterion is new in v2.0 and is the easiest to fail. If all five are not met,
**stop the project**, record the result here, and this document becomes the record of why it was not done.

## 14. Roadmap

### Done, build 0.64.0 (updated 2026-09-22)

Five layers went into `main`, each layer one commit and its own set of tests:

| Layer | File | Check |
|---|---|---|
| 1. Text-based tool protocol, state ledger | `web_tool_protocol.py`, `web_state.py` | `test_web_tool_protocol`, `test_web_state` |
| 2. Remove the hard block on file tools locked in the brain | `coding_ctx.py`, `mcp_hub._safe_path` | `test_coding_tool_context`, `test_doc_file_dinh_kem` |
| 3. `javis_run_command` (NOT a PTY) | `run_command.py` | `test_run_command_quyen` |
| 4. Fetch-tee transport | `web_transport.py` | `test_web_transport_tee` (has a layer that runs FOR REAL inside Chromium) |
| 5. Tool loop + wiring the three chat paths | `web_engine.py`, `main.py` | `test_web_engine_loop`, `test_luot_chat_web` |

That means Phase 1 through Phase 4 of the table below are done. The dashboard chat path passes the session's `workspace_root`
and `coding_ctx` to the hub, so choosing `chatgpt-web` in a Coding session means the model can read and
write the source tree and call `javis_run_command`.

**The file root is a LIST, not a single path.** 0.63.9 lets a Coding session attach
several folders. CLI engines only benefit from the MAIN folder, because their native file tools run relative to `cwd`
and one process can only stand in one place; `coding_store.khoi_prompt` says plainly that an API-only engine
cannot reach the other folders. Engines going through the hub run NO process, so
that limit does not apply to them, and `mcp_hub._safe_path` accepts a list of roots. Without this step, the Web engine would read
less than exactly the folders the Coding page just promised belong to this job,
silently, with no notice.

**Three decisions changed from the earlier draft, and why:**

1. **Do not use a callback-style `on_progress`.** A callback is only drained when the outer loop
   receives the NEXT event, and a web round takes tens of seconds, so the status line arrives just
   when it has stopped meaning anything. The engine emits a `progress` event directly in the shared event stream.
2. **The transport must go back to the RIGHT chat before typing** (`_ve_dung_luong`). One browser shared by
   every Jarvis 007 conversation, so without this step conversation B keeps typing into the chat that
   conversation A just opened: two threads merged into one, silently, with no notice.
3. **Three paths that CANNOT run the Web engine must switch back to a real Codex model** (`_model_codex_thay_the`):
   the no-tool stream, the tool loop of the dedicated bot, and background work. They call the Responses
   API directly, so `chatgpt-web` there is a model id the vendor does not know. And running the Web
   engine there would be wrong even if it could be done: ONE browser, ONE account, locking one turn at a
   time, while the dedicated bot serves many customers at once.


Ordered by **the order of what the project owner uses most**, not by technical order. Each phase
must be usable on its own.

| Step | Content | Unlocks what | Estimate |
|---|---|---|---|
| Spike | Fetch tee plus one tool round all the way through, scored by section 13 | (the only gate) | 1-2 days |
| Phase 1 | `web_chat.py`: transport, state ledger, Models card, sign-in button, model in the picker, block the section 2.1 trap. Plain chat | Q&A, planning, reading and understanding | 2-3 days |
| Phase 2 | Text-based tool translator, time budget, counter | **Image generation, reminders, reading the vault, skills, MCP.** Most of the value is here | 3-4 days |
| Phase 3 | `web_thread_id`, thread continuation, rotating the thread when it bloats (borrow `compaction.nen_mach_thue_bao`) | Daily use without rebuilding context every turn | 1-2 days |
| Phase 4 | Coding Tool Context (section 7): `workspace_root`, `javis_run_command`, `auto`-level allowlist | Programming | 3-4 days |

**Why Coding Tool Context goes last, even though v2.1 put it first:** v2.1 thought the goal was "web replaces
Codex when Codex dies", so coding was mandatory. The real goal is everyday work, in which
programming is one branch, and exactly the branch where Codex is more convenient. It is still a hard block **for the programming
branch**, but it does not block the other four groups of work.

Phase 3 coming before Phase 4 is for the same reason: for daily use, rebuilding context from scratch every turn
is both slow and costly, and that touches every turn, not just coding turns.

## 15. Not doing

- Adding a new provider. Section 1 is the reason.
- DeepSeek Web. The DeepSeek API is cheaper than the effort of building and patching a bridge; for DeepSeek, add an
  OpenAI-compatible API provider, one afternoon, not part of this document.
- Solving proof-of-work yourself, building `backend-api` requests yourself, touching cookies or tokens.
- A ChatGPT password field in Jarvis 007.
- Running on a VPS.
- Background work picking `chatgpt-web` by itself.
- Letting the model drive the PTY of `terminal.py` directly. Section 7.2 is the reason: the PTY inherits a server env containing
  keys, and is a long-lived shell with state.

## 16. Tests

The repo runs tests by calling each file as a script, so each file must have a direct-run branch.

- `test_web_chat_model_khong_bi_coerce.py`: **the most important.** `_codex_safe_model("chatgpt-web")`
  returns exactly `chatgpt-web`; and the chat branch does not call `_set_main_model` or `set_pinned_model`
  when the model is `chatgpt-web`. This is the trap in section 2; lose it and the machine owner's choice is overwritten
  silently.
- `test_web_chat_catalog.py`: `chatgpt-web` is in the ChatGPT card's model list **even when**
  `openai_oauth.list_models` returns `None`; and the card reports ready when only the web session exists, with no
  Codex CLI.
- `test_web_chat_tool_protocol.py`: peels the `` ```javis_tool `` block correctly; broken JSON returns a
  speakable error message and does not throw an exception or guess; a nonexistent tool name is reported clearly;
  `_LapGuard` still cuts in on an exact repeat.
- `test_web_chat_ngan_sach_gio.py`: when `JAVIS_WEB_TURN_BUDGET_S` runs out it stops and returns what it has
  with an explanation, not cutting off silently; and the default round cap equals `JAVIS_MAX_TOOL_ROUNDS`
  rather than a separate number.
- `test_web_chat_state.py`: `HET_LUOT` sets `cooldown_until` correctly; during cooldown it refuses
  **without** opening the browser; hitting the limit mid tool round keeps what was done and goes into `limit_resume`.
- `test_web_chat_tee.js`: runs the tee JS snippet on a static page emitting fake SSE, reassembling the
  exact original text; a stream cut mid-way gives `QUA_HAN` and not a truncated string.
- `test_web_chat_viec_nen.py`: `_FallbackChain` and the background work queue never pick
  `chatgpt-web`.
- `test_coding_tool_context.py`: in a coding session `javis_read_file` can read a file in the repo;
  in an ordinary session `workspace_root` equals `vault_root` and behavior **does not change at all**;
  a path outside both roots is still blocked, and the error message names the right root.
- `test_run_command_quyen.py`: `suggest` runs no command; `auto` only runs commands in the
  allowlist and refuses a `cwd` outside `workspace_root`; the env passed down does **not** contain the server's
  variables; exceeding `timeout` gets it killed and reported clearly.

## 18. Compress tool results before sending them back

A web round is expensive in time, and the first message already carries the whole system prompt. So tool results
**must not be dumped in raw** into the next turn.

| Tool | What it returns |
|---|---|
| Read file | The relevant range, or cut at the cap. Never a whole large file |
| Run tests | Exit code, list of failing tests, the relevant tail of stderr/stdout |
| Search in files | A ranked list of matches, not every line |
| `git diff` | Cut at the cap, and past it a summary of the number of files and lines |

If the model is missing something it calls again to ask for more. A round asking for more is cheaper than a turn with a full context.

## 19. A shared event contract between engines

Jarvis 007 already has an implicit contract: every engine produces dicts `{"type": ...}` that `CodexCLI.query` and
`claude_sdk_engine` both follow (`type` takes `session`, `text`, `tool_call`, `item`,
`final`, `error`, `usage`).

The Web Engine **maps into exactly that contract**, and does not spawn a second one. Concretely:

```
transport receives a text chunk  → {"type": "text"}
opens a new web thread           → {"type": "session"}
peels a javis_tool block         → {"type": "tool_call"}
turn finished                    → {"type": "final"}
transport error / limit reached  → {"type": "error"}
```

There is no `usage` because the web does not return token counts (section 3.2). The dashboard needs no changes.

## 20. Engine capability flags

So that the UI and the tool picker do not have to guess, each engine declares its real capabilities. `chatgpt-web` by
phase:

| Flag | Phase 1 | Phase 2 | Phase 4 |
|---|---|---|---|
| `chat` | yes | yes | yes |
| `tools` | **no** | yes | yes |
| `files` | no | yes | yes |
| `mcp` | no | yes | yes |
| `coding` | no | no | yes |
| `shell` | no | no | yes |
| `vision` | no | no | no |
| `web_image_generation` | no | no | no |
| `native_thread` | yes (Phase 3) | yes | yes |
| `reasoning_control` | no | no | no |
| `usage_tokens` | no | no | no |
| `background` | no | no | no |

**Do not declare a flag that does not work yet.** Over-declaring is promising to Jarvis 007's own tool picker, which then
sends down a tool the engine cannot use.

## 21. Image generation: two paths, and say clearly which one

Section 5 already noted: `javis_generate_image` goes through OAuth Responses, **not** through the browser. So when
`chatgpt-web` is selected and you ask for an image, the image still comes out, but it consumes the image allowance through the API and does not
consume web chat turns.

Rules:

- When the engine is `chatgpt-web`, the default path **should** be generating the image inside the web session itself, when
  that capability exists (flag `web_image_generation`).
- When it does not exist yet, it is **allowed** to use `javis_generate_image`, but it **must say so**: "this image was created
  through the plan's API path, not through the web session".
- **Never** silently spend the allowance of another pocket. Whichever engine the machine owner chooses, they are choosing that engine's whole
  quota pocket.

The web path (for next time, section 23): call the page's image generation flow, wait for it to finish, peel the image out, download it to
`attachments/`, then embed it like any other image.

## 22. Measurement and transport versioning

**Measure what can be measured, do not invent what cannot.** The web does not return tokens, so drop the token column
for this model entirely and measure other things:

```
web_turns          tool_rounds        tool_batch_size
wall_time          repair_rounds      transport_errors
challenge_count    session_expiry     task_completed
```

The two most worthwhile figures: **the median time per turn** and **the share of turns finishing without a
format-repair round**. The second is exactly the health measure of the text-based tool protocol.

**Versioning.** The web transport is fragile by nature, so record the version of three things and let tests
catch it when the page changes:

```
transport_version        the fetch tee snippet
selector_version         DOM selectors (compose box, send button, file upload button)
tool_protocol_version    the shape of the javis_tool block
```

Every DOM selector lives in **one single place** in the transport. Scattering selectors everywhere means that the
next time OpenAI changes the UI you have to go hunting.

## 23. For next time

- A session command `/web` and a chip "ask Web for the next turn" in a Coding session, to ask one question while staying
  on Codex. Specified in v1.0 section 7 (the old version); cheap, but only do it after the model selection path runs well.
- Send IMAGES to `chatgpt-web` by driving the page's file upload widget. Section 3.2 point 6: Jarvis 007's API class
  currently does not send images, while ChatGPT Web itself views images very well.
- **Chrome Extension Relay** instead of the Jarvis 007 server holding a Chrome profile forever:
  `Jarvis 007 server ↕ authenticated relay ↕ extension ↕ signed-in ChatGPT tab`. Fits a VPS far better
  than Playwright, and the project owner had already planned to build an extension. A fixed Playwright profile is still
  the right path for the spike. To check first: the MV3 service worker gets killed when idle, so long
  connections may have to go through an offscreen document.
- **Image generation DIRECTLY in the web session** (section 21): call the page's image generation flow, wait for it to finish, peel the image out,
  download it to `attachments/`. This is the condition for the `web_image_generation` flag to be switchable on.
- **Receiving images and attachments through the page's upload widget**, to switch on the `vision` flag.
- **Engine Registry**: gather engine construction into one place in place of the 72 `provider ==` branches scattered
  across `main.py`. A gradual refactor, and it must NOT block Phase 1: the cross-review made it step 1, which
  would mean many weeks before anything runs.
- A provider state machine shared by every vendor, lifted out of the section 10 ledger.
- Task Handoff Packet (the 2026-09-22 review). Worth doing for Jarvis 007, but NOT part of this
  project: it was born for the scene of switching engines midway, while the purpose here is choosing by hand for convenience.
- Image generation DIRECTLY in the web session (peeling the image from the page and downloading it) to consume web quota instead of the API
  image allowance. See section 5.
- A version guard for the Codex CLI: `install.sh:143` and `update.sh:50` currently install
  `@openai/codex@latest` unconditionally, with no supported range and no smoke test.
