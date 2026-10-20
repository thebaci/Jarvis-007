# Plan: Connection Store (MCP Hub) + engine-independent agents

> Dev plan, written 2026-07-04 on top of the v0.8.13 code. Goal: upgrade the whole MCP experience of Jarvis 007 and decouple Jarvis 007 from the Claude Code structure.

## 1. Goals (3 items)

1. **A catalog of ready-made MCPs**: the user opens the page and sees Pancake POS, Zalo, Botcake, Webcake Landing... already there, and clicks "Connect" and is done. No more typing the URL, transport and headers by hand as today.
2. **One connector linking MANY accounts** (multi-account): the same Pancake POS but 3 shops, the same Zalo but 2 accounts. Each account signs in as easily as with Claude: paste a key, scan a QR or click OAuth, with a "Connected: <shop name>" confirmation.
3. **Every engine can use everything**: MCP, skills, loops and file read/write work the same whether the Main Model is Claude Code, Codex, OpenRouter, OpenAI API or Anthropic API. Jarvis 007 is a real agent; Claude Code is just ONE of the brains.

## 2. Current state (code read on 2026-07-04)

What already exists and can be kept:

- `server/mcp_store.py`: a flat server registry (name/transport/url/headers/env). It generates `.mcp_config.json` for `claude --mcp-config` and a toml profile for Codex, and has deny_tools plus strict mode. Multi-shop is handled by duplicating rows with the same URL and different headers.
- `server/mcp_client.py`: a hand-written MCP client (Streamable HTTP, JSON-RPC) that lets API engines (OpenRouter/OpenAI) run a tool-calling loop. Namespacing `server-name__tool-name` already exists.
- The MCP page UI in `dashboard/console.js` (renderMcp, around line 1399): a technical form plus an ambient area (Claude Code's own MCPs, view only).

Gaps against the goals:

- No catalog: everything is typed by hand, which ordinary people cannot do.
- Multi-account is a "trick" (duplicating rows), not an official model: no grouping by connector, no account labels, no default account.
- The hand-written client is HTTP only: NO stdio (so the local Zalo CLI only works through Claude Code), NO OAuth, and every tool call opens a new session (slow, so the docs have to apologize with "the first message is a bit slow").
- OAuth MCP is pushed to `claude mcp add` plus making the user open a terminal and type `/mcp`: it only works on a machine with a screen and only for the Claude Code engine. This is the heaviest "tied to Claude Code" spot.
- The engine matrix is uneven (docs/10): Anthropic API is plain chat with no MCP; ChatGPT OAuth (responses) has no MCP; skills and loops only work on Claude Code; API engines have no file tools.
- Secrets sit in plaintext in `mcp_servers.json` (gitignored, but still plaintext).

## 3. Target architecture: JARVIS 007 MCP HUB

The central idea: every engine plugs into ONE single point owned by Jarvis 007. The hub handles connections, accounts, permissions and logs. The engine only sees "one MCP server called javis".

```
Claude Code  --mcp-config 1 entry --\
Codex        profile toml 1 entry ---+--> [ JARVIS 007 MCP HUB ] --> Pancake POS (shop A) (shop B)
API engine   in-process calls ------/          |               --> Zalo (acct 1) (acct 2)
                                               |               --> Botcake, Webcake, ...
                              catalog + permission + audit + cache + OAuth token store
```

Benefits of funneling everything into one point:

- Multi-account routing, tool naming, permissions and tool-call logs are done ONCE and every engine benefits.
- OAuth: the hub holds the token and refreshes it itself, so any engine can use it (Claude Code included, since the hub is just one HTTP MCP to it). The "open a terminal and type /mcp" scene is gone for good.
- The 3 loop permission levels (suggest/auto/full) are ENFORCED at the hub (write tools are truly blocked) instead of only relying on the prompt as today.

### 3.1 Data model: Connector (template) separate from Connection (account)

**Connector** = a template in the catalog, shipped with the app, versioned:

```json
// system/mcp-catalog.json (array of connectors)
{
  "id": "pancake-pos",
  "name": "Pancake POS",
  "icon": "pos.png",
  "category": "Sales",
  "description": "Orders, revenue, customers and inventory from Pancake POS.",
  "transport": "http",
  "url": "https://mcp-pos.pancake.biz/mcp",
  "auth": {
    "type": "apikey",
    "fields": [{ "key": "api_key", "label": "The shop's API key", "header": "Authorization: Bearer {api_key}" }],
    "guide": "In Pancake POS go to Settings > Apps & API > create an API key.",
    "guide_url": "https://docs.pancake.biz/pos/st-f13/st-p2?lang=vi"
  },
  "validate": { "tool": "pos_shop", "label_from": "$.name" },
  "tool_meta": {
    "write": ["pos_order", "pos_purchase", "pos_transaction", "pos_debt", "pos_voucher", "pos_promotion"],
    "danger": ["pos_transaction"]
  },
  "default_perm": "readonly"
}
```

- `auth.type`: `apikey` | `oauth` | `qr` | `none`. The fields are declared up front so the UI builds the form itself and the user never sees the word "header".
- `validate`: after the key is entered, the hub immediately calls one read tool to (a) confirm the key is correct and (b) set the account label automatically (the shop name). This is the "easy as Claude" feeling: paste the key and see "Connected: Kim Khí Hà Lộc".
- `tool_meta`: classifies read/write/dangerous per connector (more accurate than the current WRITE_HINTS heuristic; the heuristic stays as a fallback for custom connectors).
- The catalog loads from the app and can also refresh from a remote (GitHub raw), so new connectors can be added WITHOUT an app release.

**Connection** = one specific account of the user, stored in `server/mcp_servers.json` (schema upgraded, automatic migration):

```json
{
  "id": "abc123",
  "connector_id": "pancake-pos",
  "label": "Kim Khí Hà Lộc",
  "secrets": { "api_key": "<encrypted>" },
  "config": {},
  "enabled": true,
  "perm": "readonly",
  "is_default": true
}
```

- Migration: any old server row whose URL matches a catalog entry gets the matching `connector_id`; the rest get `custom` (a custom connector is one the user declares themselves, via an advanced form like Claude's "Add custom connector", keeping every capability that exists today).
- Secrets are encrypted at rest (Fernet, with a per-machine key stored outside the registry file). Secrets are masked in logs and API responses (`_public` already does this, keep it).

### 3.2 Hub runtime (upgrading mcp_client.py)

- **Session pool**: keep MCP sessions alive between messages (hold the `Mcp-Session-Id`, share one `httpx.AsyncClient`), cache tools/list with a TTL, and run a background health check. This ends the "every message reconnects, so it is slow" problem.
- **stdio support**: spawn a child process and speak JSON-RPC over stdin/stdout. This is the precondition for the Zalo CLI (and every local MCP) to run for API engines and not only for Claude Code.
- Recommendation: move the client to the **official `mcp` SDK (Python)** instead of maintaining the protocol ourselves. The SDK already has Streamable HTTP, stdio and the auth flow; for the server side (the aggregator) use FastMCP directly or write something thin on FastAPI. Less technical debt when the protocol versions up.

### 3.3 Aggregator: the hub appears as ONE MCP server

- Endpoint `POST /hub/mcp` (Streamable HTTP) on the FastAPI app that is already running, bound to localhost.
- Claude Code's `.mcp_config.json` and Codex's toml profile keep only ONE entry pointing at the hub (with an internal token so stray processes on the machine cannot call in).
- Tool naming: a connector with 1 connection keeps the short name `pos__pos_order`; with several connections it becomes `pos_kim-khi-ha-loc__pos_order`. A meta-tool `javis_connections` (lists connectors + accounts + permissions) lets the model know which sources exist.
- Optional protection against context bloat when the user connects many connectors: a "lazy tools" mode (expose only the meta-tools `search_tools` + `run_tool`, Composio style). DONE (v0.9.146): `mcp_hub._apply_lazy` hides the tool pool (MCP tools that have a route entry `conn`) behind `javis_search_tools`/`javis_run_tool`, while builtins and plugins stay visible; it turns on automatically when the number of MCP tools exceeds `settings.mcp.lazy_threshold` (default 40), and can be forced on or off with `settings.mcp.lazy_tools`. It is applied inside `discover_all`, so every engine (Claude Code, Codex, API) benefits equally; permissions and audit stay intact because `run` goes through the full routing in `call_route`.

### 3.4 Centralized permissions at the hub

- Each connection has a `perm`: `readonly` (read tools only) | `safe` (adds draft writes, blocks danger) | `full`. Derived from `tool_meta`, one toggle in the UI instead of making the user type the names of tools to block as today. Manual `deny_tools` stays for power users.
- Loop mode maps straight onto the hub: a `suggest` loop calls the hub with a read-only context (the hub rejects every write tool regardless of the connection's perm), `auto` blocks the danger group, `full` follows the connection's perm. Safety becomes a hard layer and no longer depends on the prompt.
- Audit log: every tools/call is recorded (connection, tool, shortened args, ok/error result, duration) in SQLite/JSONL and can be viewed from the UI.

### 3.5 Jarvis 007 handles OAuth itself (dropping the dependency on claude mcp add)

- Implement the standard MCP Authorization (OAuth 2.1 + PKCE + Dynamic Client Registration): clicking "Connect" opens the browser, the callback returns to `http(s)://<dashboard>/connect/oauth/callback`, and the hub stores and refreshes the token itself and attaches it to the header when calling the server.
- It works on a VPS too, because the callback goes through the very dashboard URL the user has open (no terminal and no screen on the server needed).
- From then on OAuth servers work for EVERY engine (today: Claude Code only). The native `claude mcp add` path stays as a fallback for a while and is then removed.

## 4. UX of the "Connections" page (replacing the current MCP page)

Rename the menu entry: MCP -> **Connections** (subtitle "Data sources & tools"). The word MCP only remains in the advanced section.

Layout of 2 areas plus the ambient area:

1. **Connected**: one card per connector, and inside the card are account chips: `● Kim Khí Hà Lộc (default) | ● Shop B | + Add an account`. Each chip opens a menu: rename, set as default, re-test, read only (toggle), disable/enable, view log, delete.
2. **Connection store**: a grid of cards from the catalog (icon, name, one-line description, badge "API key" / "OAuth" / "Zalo QR"), a search box and a filter by group. At the end of the grid: an "Add your own (advanced)" card = custom connector, keeping the old form.
3. **MCPs from Claude Code** (ambient): unchanged, view only.

Flow for adding an account by auth type:

- **apikey**: a modal with one box to paste the key plus a line saying where to get the key (text + the vendor's docs link) -> click Connect -> the hub validates right away (calls the verification tool) -> shows "✓ Connected: <shop name>" and fills in the label itself -> choose the permission (default comes from the catalog; POS defaults to read only). A wrong key is reported on the spot, with a hint.
- **oauth**: click Connect -> a tab opens with the vendor's login -> come back and see the account already in the list.
- **qr** (Zalo): a modal shows the QR code (Jarvis 007 spawns the CLI login, captures the QR and puts it in the UI) and polls the status until "✓ Signed in: <Zalo name>". It comes with a mandatory-read risk warning (see section 6).
- After the user's FIRST connection: run one demo question right in the page ("How much did we sell today?") to prove the value immediately.

Principle: an ordinary person never sees the URL/transport/header. The technical details only show in "Add your own (advanced)" and when opening a connection's details.

## 5. Engine parity: a real agent on every brain

Target matrix (current -> target):

| Capability | Claude Code | Codex | OpenRouter/OpenAI API | Anthropic API |
|---|---|---|---|---|
| MCP | ✓ (kept, via the hub) | ✓ http -> ✓ hub (stdio too) | ✓ (faster thanks to the pool) | ✗ -> ✓ (new tool loop) |
| Skills | ✓ native | ✗ -> ✓ (skill router) | ✗ -> ✓ (skill router) | ✗ -> ✓ |
| Vault files | ✓ | ✓ | ✗ -> ✓ (built-in tools) | ✗ -> ✓ |
| Loop/agent/workflow | ✓ | partial | ✗ -> ✓ | ✗ -> ✓ |

Concrete work:

1. **Anthropic API tool loop**: write `anthropic_chat_with_mcp` in `engine.py` (the Anthropic Messages API has tool use, same pattern as `openai_chat_with_mcp`). Small job with immediate value: remove the "Anthropic API = plain chat" line from the docs.
2. **Built-in tools for API engines**: a set of sandboxed file tools inside the vault (read/list/write/append by perm), put into the same tool-calling loop as the MCP tools. From then on loops/tasks/workflows can run on API engines.
3. **Skill router for every engine**: inject the skill list (name + description from `.claude/skills/*/SKILL.md`) into the system prompt, plus a meta-tool `use_skill(name)` that returns the SKILL.md content when the model activates it (progressive disclosure, the way Claude Code does it, but done by Jarvis 007 itself so every engine works).
4. **Loop/agent/workflow accept an API provider**: the agent's `model` field is extended to accept API providers too; the runner maps through a common Engine interface.
5. Standardize the `Engine` interface (capabilities: native_mcp, native_skills, file_tools...) so call sites no longer have if/else on engine names scattered around as they are today; the engine badge in the UI reads from the real capabilities.

ChatGPT OAuth (responses API) does not accept function tools: keep the strategy of going through the Codex CLI and do not try to force it.

## 6. Four connectors preinstalled in the first wave

1. **Pancake POS** (the surest): endpoint `https://mcp-pos.pancake.biz/mcp` + API key, already running in practice. Remaining work: write the catalog entry + validate via `pos_shop` + `tool_meta` read/write classification + make multi-shop an official multi-connection. Docs: https://docs.pancake.biz/pos/st-f13/st-p2?lang=vi
2. **Webcake Landing**: the vendor already has an MCP ("Let AI design and edit landing pages by voice"). We need to open the full docs page to get the exact endpoint and how keys are issued (the page is an SPA and an automatic fetch only returns the title). Docs: https://docs.pancake.biz/landing/st-f7/st-p3?lang=vi
3. **Botcake**: the docs page describes the direction "Botcake AI consumes MCP servers". We need to verify whether Botcake EXPOSES MCP to outside parties; if it only has a JSON API (Developer section), write a thin MCP wrapper in the repo (`server/connectors/botcake_mcp.py`, mounted into the hub as an internal connector). This wrapper pattern is reusable for every service that only has a REST API. Docs: https://docs.pancake.biz/botcake/st-f2/st-p10/st-s2?lang=vi
4. **Zalo** (zalo-agent-cli, npm): an unofficial CLI built on zca-js, QR login, ALREADY supports multiple accounts + a separate proxy per account (matches the connection model), has an MCP mode since v1.2.0 (4 tools: read messages, send message, list threads, mark as read) and 15+ CLI command groups. Catalog entry: transport stdio, command `zalo-agent-cli` (verify the syntax for running MCP + the account-selection flag when building), auth type `qr`.
   - MUST show a warning: the API is unofficial and the account may be locked by Zalo. Default `readonly` (read messages); sending messages requires the user to deliberately raise the permission and confirm the risk. Add a rate limit at the hub for this connector.

## 6b. Wave 2 - three ad connectors (research 2026-07-04, ship 0.9.2)

1. **Meta Ads (official)**: remote MCP `https://mcp.facebook.com/ads`, standard MCP OAuth (exactly the hub's oauth_mcp flow - no dev app or token needed). Open beta since 2026-04-29, rolled out gradually per ad account, and requires the account to belong to a Business Manager. 29 tools: reads (`ads_get_*`, `ads_insights_*`, `ads_catalog_get_*`), catalog writes (`ads_catalog_create`), real-money danger (`ads_create_campaign/_ad_set/_ad`, `ads_update_entity`, `ads_activate_entity`). Guardrail on Meta's side: entities created through MCP are always PAUSED. 3 scope tiers chosen at sign-in (read-only / read-write / financial). Could not be tested live because it needs a real Facebook login - validate + automatic label will run on the user's first connection.
2. **Google Ads (official)**: local stdio, repo `googleads/google-ads-mcp` (there is NO usable PyPI release - the PyPI package of the same name is a 0.0.1 placeholder). Run `uvx --from git+https://github.com/googleads/google-ads-mcp.git google-ads-mcp` - ACTUALLY TESTED on Windows: server "Google Ads Server" v3.4.2, initialize + tools/list OK in under 90s (matches mcp_client's init timeout). The REAL tool names carry a namespace prefix: `customers_list_accessible_customers`, `search_search`, `metadata_get_resource_metadata` (the docs list the names without the prefix). Read-only by design. Auth: developer token (the MCC's API Center, Explorer level is enough) + a GCP project with the Google Ads API enabled + ADC (gcloud auth application-default login --scopes=adwords,cloud-platform --client-id-file=oauth-client.json) - the user pastes the ADC file content, mcp_store writes it out to a file and sets the env GOOGLE_APPLICATION_CREDENTIALS. Through an agency/MCC, also add GOOGLE_ADS_LOGIN_CUSTOMER_ID.
3. **TikTok Ads (community, waiting for official)**: TikTok announced an official MCP at TikTok World on 2026-05-13 but as of 07/2026 it is NOT GA (no public endpoint yet; the docs portal v1.3 is an SPA whose content could not be read). Chosen: the PyPI package `tiktok-ads-mcp` (ysntony, v0.1.4): stdio `uvx tiktok-ads-mcp` - ACTUALLY TESTED: all 6 tools are read-only, and the real names have a `_tool` suffix (`get_authorized_ad_accounts_tool`, `get_campaigns_tool`, `get_reports_tool`...). Stateless auth by pasting env vars TIKTOK_APP_ID / TIKTOK_SECRET / TIKTOK_ACCESS_TOKEN directly (a long-term Marketing API token does not expire on its own) - fits the multi-account connection model. We CONSIDERED and REJECTED the repo `AdsMCP/tiktok-ads-mcp-server` (sent by the user as a link): it is not on PyPI (must be cloned), auth is interactive OAuth through a tool in chat, and token persistence inside the process is unclear - it does not fit the hub. When TikTok opens the official version: switch the `tiktok-ads` entry to the official endpoint (keep the id so old connections can migrate).

Also in 0.9.2: after a successful token exchange, the `/connect/oauth/callback` callback now calls validate by itself to set the label (the ads account name) if the label is still the default name, and writes the codex profile immediately (it was missed before).

## 6c. Wave 3 - official Google Calendar + Gmail (research 2026-07-04, ship 0.9.3)

Google has released official REMOTE MCPs for Workspace, one endpoint per service (actually probed):
- Calendar `https://calendarmcp.googleapis.com/mcp/v1` - 8 tools: read (list_events, get_event, list_calendars, suggest_time), write (create_event, update_event, respond_to_event), danger (delete_event).
- Gmail `https://gmailmcp.googleapis.com/mcp/v1` - 12 tools: read (list_drafts, get_thread, search_threads, list_labels), write (create_draft, create_label, *label*). NOTABLE: there is NO tool for sending mail - only creating drafts and applying labels. Naturally safe.
- Drive `https://drivemcp.googleapis.com/mcp/v1` exists too (not added in this wave).

Auth characteristics (different from Meta): initialize + tools/list return 200 WITHOUT a token; only tools/call returns 401 with `WWW-Authenticate: Bearer resource_metadata=".../.well-known/oauth-protected-resource/<tool>"`. The resource metadata at `/.well-known/oauth-protected-resource/mcp/v1` -> `authorization_servers: ["https://accounts.google.com/"]` + scopes_supported. accounts.google.com has NO registration_endpoint -> **no DCR** -> the old oauth_mcp flow (DCR only) cannot be used.

Solution (0.9.3): add an EXPLICIT branch in `oauth_mcp.start_auth`. The connector declares `auth.authorize_url` + `token_url` + `scopes` + `authorize_params` + client_id/client_secret fields (BYO). When authorize_url + token_url are present -> skip discover/DCR, read the BYO client from `mcp_store.connection_secrets(conn_id)`, build the URL with the declared scopes + `access_type=offline&prompt=consent` (REQUIRED for Google to issue a refresh_token; without it the connection dies after 1h). handle_callback + _refresh also send client_secret (a Google Web app is a confidential client). The account name is set automatically to the email extracted from the id_token (scope openid+email). The DISCOVERY branch (Meta) is unchanged.

Why choose the official remote instead of the existing local `google-workspace` connector (workspace-mcp): the remote needs no uv/node, runs on a headless VPS, and OAuth goes through the dashboard redirect (no browser opens at tool-call time - the local workspace-mcp opens a browser on first use, so it fails on headless). workspace-mcp exposes 45 tools (heavy context bloat); the 2 focused connectors have only 8 + 12 tools. Keep google-workspace for anyone who needs Drive/Docs/Sheets in one connection.

The end-to-end OAuth round trip is NOT yet tested (it needs an OAuth client + the user's real Google login). Tested: probing the endpoints + the real tool list, building the authorize URL (unit test: offline/consent/scope/PKCE/no resource param), extracting the email from the id_token, permission classification over 17 cases. The user must: create an OAuth client of type "Web application" in GCP, add the redirect `http://localhost:7777/connect/oauth/callback` (+ the domain on a VPS), enable the Calendar API / Gmail API, and add themselves to Test users.

## 7. Roadmap (each phase ships and is usable right away)

**P0 - Hub foundation (backend)**
- Connector/connection schema + migration from the old registry (do not break running servers).
- `system/mcp-catalog.json` + loader (`server/mcp_catalog.py`), first entries: pancake-pos, zalo, custom.
- Upgrade `mcp_client.py`: session pool + stdio (consider moving to the `mcp` SDK).
- Secret encryption. New endpoints: `/connect/catalog`, `/connect/add`, `/connect/validate`, with the old `/mcp/*` kept running in parallel.
- Done when: a Pancake POS connection is added through the new API, validate returns the shop name, and a chat asking for numbers still works on both Claude Code and OpenRouter.

**P1 - Connection store UI**
- `console.js`: renderMcp -> renderConnect (2 areas + ambient), guided apikey flow + validate + auto label, one-tap read-only toggle, test/health, multi-account chips, a demo question after the first connection.
- Update docs/09.
- Done when: a non-technical person connects 2 Pancake POS shops by themselves in under 2 minutes without seeing the words URL/header.

**P2 - Aggregator + centralized permissions**
- `/hub/mcp` streamable HTTP + internal token; the Claude Code and Codex configs keep only 1 entry pointing at the hub; API engines call the hub in-process.
- Enforce the 3 perm levels + loop mode at the hub; audit log + a log viewing screen.
- Done when: the old per-server registry is turned off, every engine runs through the hub, and a suggest loop is truly blocked from write tools by the hub (test by deliberately calling pos_order).

**P3 - OAuth + QR**
- OAuth 2.1 PKCE + DCR + refresh, callback through the dashboard; gradually remove the `claude mcp add` path.
- Zalo QR flow end to end (spawn the CLI, capture the QR into the modal, poll, map the CLI account -> connection).
- Done when: any OAuth connector can be signed in from the dashboard on a headless VPS; Zalo is scanned and then sends one test message (perm full, with confirmation).

**P4 - Engine parity**
- Anthropic API tool loop; built-in file tools; `use_skill` skill router; loops/agents/workflows accept an API provider; Engine interface + capability flags; update docs/10.
- Done when: switching the Main Model to Anthropic API or OpenRouter still lets us call POS for numbers, activate a skill and run one background loop.

**P5 - Store expansion**
- Webcake Landing + Botcake (after verifying the endpoints), Facebook Ads and the connectors users often need; catalog refresh from a remote; lazy tools when there are many connectors; consider a community store.

Ordering note: P4 (item 1: the Anthropic tool loop) is independent and can be slotted in at any time. P1 depends on P0. P2 should come before P3 so the OAuth token only has to be plugged into one place (the hub).

## 8. Risks and open questions

- **Zalo account bans**: a real risk of zca-js. Mitigation: mandatory warning, default readonly, rate limit, recommend using a secondary account. Never let an auto/suggest loop mode send Zalo messages.
- **Webcake Landing + Botcake endpoints unverified**: the docs pages are SPAs, so they must be opened in a browser (or the user supplies the details) to get the MCP URL + how keys are issued before writing the catalog entries.
- **OAuth with services that do NOT follow the MCP standard** (e.g. raw Google APIs): the DCR standard does not apply, so a separately registered app is needed. Direction: prefer standard remote MCPs; for special cases guide the user to bring their own client id, or go through a third-party aggregator (Composio) as an optional connector.
- **Context bloat with many connectors**: perm + deny already trim some; at a large threshold turn on lazy tools (P5).
- **Backward compatibility**: the old registry must migrate smoothly, the old `/mcp/*` stays until the new UI is stable; the codex profile + empty-mcp fork keep their behavior.
- **Hub endpoint security**: `/hub/mcp` binds to localhost + an internal token generated on every run, so other processes on the machine cannot sneak in (the hub holds all of the user's keys).
