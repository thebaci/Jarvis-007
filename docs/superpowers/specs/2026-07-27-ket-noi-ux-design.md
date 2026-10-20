# Spec: thorough UX overhaul of the Connections page (blocks A, B, D)

> Approved in chat 2026-07-27. Background: the false accusation against Google Workspace (0.9.189) exposed
> a string of ailments on the Connections page: no visible health, reconnecting is hard, 4 tangled Google
> paths, wall-of-text guides. Block C (banner for a brain that lost its login) is left for a later round.

## Block A - Always-on health + one-tap reconnect (0.9.192)

### Server
- New module `server/connect_health.py`:
  - A background loop checks every `HEALTH_INTERVAL` (10 minutes): for each enabled connection,
    ping `pool.list_tools(spec)` (cheap, does not call a real tool), with a short timeout.
  - In-memory state: `{conn_id: {ok, kind, message, checked_at}}`. Not persisted;
    after a restart it rescans early (short delay after startup).
  - Errors are classified into human language on the server (`classify_error`). The user-facing messages below stay in Vietnamese:
    - 401 / invalid_grant / "OAuth session expired" -> kind `auth`, "Hết phiên đăng nhập" (login session expired)
    - timeout / connect error -> kind `net`, "Dịch vụ không phản hồi" (service not responding)
    - stdio spawn error (FileNotFoundError, early exit) -> kind `spawn`, "Không khởi động được trình kết nối trên máy" (cannot start the connector on this machine)
    - everything else -> kind `unknown`, original message truncated.
- Endpoints:
  - `GET /connect/health` -> the state map for every connection.
  - `POST /connect/health/check` (id) -> force a check of one connection right now, return the result.
- Test: `test_connect_health.py` - classify covers every branch, the check loop with a fake pool,
  endpoint shape, forced check.

### UI (console.js)
- The account chip carries a colored dot: green (ok), yellow (not checked yet / checking), red (error).
  Tooltip: the message + the time of the check.
- A card with a connection in error of kind `auth` gets a "Reconnect" button:
  - oauth -> call `/connect/oauth/start` with the existing conn id (keeping id, label, permissions).
  - apikey -> open a modal to paste the new key, submit to overwrite the secrets via `/connect/update` (extended to
    accept new secrets if it does not already).
- Poll `/connect/health` when the page opens + every 60s while on the page.

## Block B - Merge Google into one door + wizard (0.9.193)

- Catalog: the 5 Google connectors get `group: "google"`. When the UI sees a group, it gathers them into ONE
  "Google" card in the Store. Tapping the card opens a service picker screen (Calendar, Gmail, Tasks,
  Drive/Docs, Keep): each row has 1 sentence on how far the permission reaches + a difficulty badge. Mapping service -> connector is
  the UI's job; the user never sees the technical names.
- `auth.steps` (a structured array) replaces the wall-of-text guide: each step is
  `{text, link?, link_label?, copy?}`. The UI renders a stepper; the old `guide` is kept as a
  fallback for connectors not yet converted.
- The key input accepts a drag-and-drop of Google's client JSON file (extracting client_id/client_secret
  from both `web` and `installed`).
- Reuse a key: if another Google connection already has a client_id/secret -> a
  "Reuse the key from <name>" button; the server copies the secrets (a new endpoint or extending
  /connect/add to accept `reuse_from: conn_id` - secrets are NOT returned to the browser).
- Test: the steps schema in the catalog, reuse_from does not leak secrets, the group mapping.

## Block D - Polish (0.9.194)

- The two ambient sections (Claude Code, Codex) are collapsed by default.
- The word "MCP" leaves all primary text, remaining only in "Add your own (advanced)" + details.
- Store card: a human-language badge for the sign-in method ("Paste key" / "Google sign-in" /
  "Scan QR" / "One tap").
- Mobile: 1-column grid, chips do not overflow. Add icons that are still missing logos.

## General principles
- No change to the backend connection schema; everything is backward compatible.
- UI strings are in Vietnamese with diacritics, no em dash.
- Each block ships as its own release, and tests must pass before moving to the next block.
