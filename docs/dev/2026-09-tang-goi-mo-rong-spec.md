# Plan: the Pack Layer (extension packs) for Jarvis 007

> Dev plan, written 2026-09-03 on top of code v0.55.7. Goal: make connectors and plugins
> installable PACKS at runtime (zip, URL or a separate repo, and later a public store), keeping
> the FastAPI core as it is. Includes clean connection deletion and a source-code language freeze.

## Background

Jarvis 007 already has a foundation. The problem now is not missing features but that **every new capability has to go through a release**. Measured on the repo:

- **524 VERSION bumps in 3 months** (July: 326, August: 181, September: 17).
- **60 of those were only to edit `system/mcp-catalog.json`**, that is, to add or patch one connector.

The cause is a single line: `server/mcp_catalog.py:19` points hard at exactly one file in the repo, `load()` at `:35-50` does no merge and no override, and no endpoint can write into it. On Docker the code tree is root-owned and read-only (`Dockerfile:81,112`), and only `/data` is writable. So adding a connection means shipping a new release, with no other way.

Plugins are much closer to the goal. `server/plugins_host.py` (605 lines) already scans three tiers, already does real hot reload by mtime (`_signature` :323-337), and already has a permission gate enforced by code rather than by prompt (`_make_call` :446-473). Exactly three things are missing: **no install path, no uninstall path, and the env gate is all-on or all-off**.

The goal of this plan: a **pack** that can be installed at runtime from a zip file, from a URL or a separate repo, and later from a public store. Keep the FastAPI core as it is, with no rewrite in the style of deepseek-harness's seam. Uninstalling a pack must be clean, and deleting a connection must be clean.

---

## Four broken things found during the survey

These are real bugs, re-verified by hand, not guesses. The first three are prerequisites of the plan, so they must be fixed first.

**1. Deleting a connection leaves junk behind, including a live credential.**
`POST /connect/delete` (`main.py:3212-3221`) calls `mcp_store.delete_connection` **first** and only then `mcp_hub.invalidate_cache`, but `invalidate_cache` (`mcp_hub.py:890-899`) loops over `list_connections()` to find sessions to close. The row is already deleted, so the session is never closed, and the stdio child process lives until `_IDLE_TTL = 900` seconds. And nobody ever deletes `STATE_DIR/connector-home/`: two places write to it (`mcp_store.py:428`, `zalo_login.py:161`), none deletes. On the survey machine at the time of writing there were **5 orphaned `connector-home/zalo-*` folders** while no Zalo connection remained, and one of them held a login-session credential.

**2. `safeHref` blocks too much, and three render sites bypass it.**
`dashboard/console.js:156` only accepts `^https?://`, so `guide_url: "/static/docs/substack.html"` in the catalog returns `#`: **the Substack guide link is dead today**. More seriously, three render sites (`:4227`, `:4263`, `:4491`) interpolate `esc(con.guide_url)` straight into `href=` without going through `safeHref`. `esc()` only escapes `& < > " '`, so `javascript:` slips through. It cannot be exploited today because we write the catalog ourselves; the day someone else's pack can supply `guide_url`, it becomes XSS on the dashboard's own origin.

**3. Two slugify functions disagree, and one eats the letter Đ.**
`share_bundle.py:55 slugify` uses NFKD and then `encode("ascii","ignore")`, but U+0111 (đ) has no NFKD decomposition and is **simply deleted**. Tried it: `"Đo lường doanh thu"` gives `"o-luong-doanh-thu"`. This is the agent export/import path, so one export-then-import round trip corrupts the name. `main.py:4567 _ascii_slug` does it right because it has an explicit `replace("đ","d")`.

**4. The "stuck" detector in the chatbot only knows Vietnamese.**
`chatbot_runtime.py:515 _DAU_BI` is 9 pure Vietnamese phrases. A chatbot serving English-speaking customers will **never** be recorded as stuck, so the stuck-bot tab shows empty while the bot is broken. This is a genuine bug, just dressed up as a language issue.

---

## What a pack is

One unit. One folder. One manifest. Connectors and plugins **share one format**, differing only in which `provides:` parts are filled in. The reason: `meta-ads-graph` today is already one feature split into two artifacts, glued together by the hard-coded string `CONNECTOR_ID = "meta-ads-graph"` at `system/plugins/meta-ads-graph/plugin.py:13`. Splitting the format in two would legitimize that flaw.

```
STATE_DIR/packs/<id>/
    javis-pack.yaml       manifest, kept verbatim as the author wrote it
    pack.json             normalized + checked version, written by the installer
    connectors/*.yaml     one connector per file
    plugins/<slug>/       plugin.yaml + plugin.py, LEFT IN PLACE
    assets/               icons, served at /packs/<id>/asset/<path>
    pages/                guide pages
STATE_DIR/packs.json          install ledger
STATE_DIR/packs-state/<id>.json   effects ledger (things written OUTSIDE the pack folder)
STATE_DIR/packs-staging/      files inspected but not yet installed, cleaned after 30 minutes
```

**The decision that makes uninstalling feasible:** a pack's plugins live permanently in `STATE_DIR/packs/<id>/plugins/<slug>/` and are **never copied** to `STATE_DIR/plugins/`. Uninstalling is then `rmtree` plus replaying the effects ledger, not a diff hunt.

### Manifest, spec 1

All keys are in English from day one (this is a new public contract). `name` and `description` are multi-language maps.

```yaml
format: javis-pack
spec: 1                        # SCHEMA version, not the pack version
id: acme.pos-vn                # ^[a-z0-9][a-z0-9._-]{0,63}$, immutable, = folder name
version: 1.0.0
name: {en: "Vietnam POS", vi: "POS Viet Nam"}
description: {en: "...", vi: "..."}
author: {name: "Acme", url: "https://acme.dev"}
license: MIT
icon: assets/pos.png           # relative path inside the pack ONLY
category: sales                # English slug
category_label: {en: "Sales", vi: "Bán hàng"}
compat: {app: ">=0.57.0 <2.0.0"}   # checked at install AND at startup
permissions:                   # the author's DECLARATION, shown before install. NOT enforcement.
  code: false                  # the installer computes this itself, never trusts the file
  network: ["api.pos.vn"]
  filesystem: none
provides:
  connectors: [connectors/pos.yaml]
  plugins: []
  assets: [assets/]
  pages: [{id: guide, file: pages/guide.md}]
update: {channel: manual, source: ""}
signature: {}                  # RESERVED, spec 1 only checks presence
listing:                       # RESERVED for the store, ignored by the installer
  price: {amount: 0, currency: VND, model: free}
  purchase_url: ""
  entitlement: {required: false, check_url: ""}
```

An old `plugin.yaml` with no `format:` key is mapped by a ~20-line shim in `packs.py` to `{spec: 0, id: <folder name>, provides: {plugins: ["."]}}`. **Every existing plugin, bundled and user-made, keeps running forever without changing a single byte.**

A `connectors/pos.yaml` file is **exactly** one element of the `connectors[]` array in `system/mcp-catalog.json` today, plus `category_key` and relative icon/guide paths.

### Two choke points

All three review rounds confirmed that only two places need touching:

- `mcp_catalog.load()` (`:35-50`): a single mtime-cached read that returns `{id: connector}`. **Every** function downstream (`get`, `public_catalog`, `build_headers`, `build_url`, `build_env`, `classify`, `allowed`, and `mcp_store.resolved()` :373-501) already receives the connector as a **dict parameter**. So turning `load()` into a merge function is a self-contained change.
- `plugins_host._iter_plugin_dirs` (`:170-182`): a tuple of three sources deduplicated by folder name. Adding a fourth source means inserting one element, and `_signature()` already stats every `plugin.yaml`/`plugin.py` it returns, so **hot reload for pack plugins comes for free**.

**Anti-deadlock rule:** `server/packs.py` imports only `config`, `secrets_store`, `fastyaml` and the stdlib. It never imports `plugins_host`, `mcp_store`, `mcp_hub` or `main`. Spec 1 **has no** `ctx.register_connector`, so pack code cannot call back into the catalog merge layer while `plugins_host._lock` (:57) is held through `reg(ctx)` (:403).

---

## Trust boundary: the "execution surface", not "no .py files"

This is the most important adjustment, and the reason a public store can be safe.

`transport: stdio` copies `command`/`args` from the connector into the connection (`mcp_store.py:225-229`), then `mcp_client.py:216-220` spawns it with `env = dict(os.environ)`, and `POST /connect/add` (`main.py:3112`) dials immediately. **A pack containing not one line of Python can still run `npx -y goi-doc-hai` with the server's entire environment from a single click.** The `javis-connect` plugin already knows this and forces every stdio connection added by the model to `enabled: False` (`plugin.py:224-228`).

So there are **three tiers, computed by the installer itself from the unpacked file tree, never trusting the author's claims**:

**DATA tier** - installable without agreeing to run code:
transport `http`/`sse`; `url`/`url_template` **https on port 443 only**, with the domain shown on the confirmation screen; `auth.type` is `apikey`/`none`/`oauth` with a `provider` from the existing dialects (`meta`, `google`, `generic`); `tool_meta`, `validate`, `arg_rules`, `rate_limit`, `risk`; icons and guide pages **as in-pack paths only** (an `http://` icon is rejected because it is a beacon that fires every time the Connections page is drawn); and `default_perm` is **forced to `readonly`** for every connector coming from a pack, and the user raises each connection themselves through the old UI where the risk warning already exists.

**CODE tier** - requires separate consent per pack, tied to a content hash:
any `.py` file; `transport: stdio` or any `command`/`args`; a static `env` block; `cred_dir`, `isolate_home`, `oauth_file`, `needs_local_browser`; `auth.exchange`.

**A pack containing Python is NORMAL, not an exception that must be asked for twice.** The project owner settled this on 2026-09-03: packs are open to Python code, because the owner is the one who looks at the pack before installing it. So **the `JAVIS_ENABLE_USER_PLUGINS` env gate does NOT apply to packs installed through the installer.** This is consistent rather than a loosening, and the reason is worth writing down:

The env gate was created to plug exactly one hole: `STATE_DIR/plugins/` and `<brain>/plugins/` are **writable** folders, so anything that can write there gets code running inside the server process **with nobody clicking anything** - including a model working on files in the brain. The installer removes exactly that condition: a person clicks, there is a screen listing every `.py` file before the click, and a digest is recorded so later loads can check against it. Those three things are the same kind of guarantee the env gate provides, only more precise because it works PER pack instead of all-on or all-off.

So we split by route, not by trust level:

| Entry route | Condition for running code |
|---|---|
| Installed through the installer (zip, URL, separate repo, store) | Consent per pack, tied to a digest. **No env needed.** |
| Folder dropped by hand into `STATE_DIR/plugins/` or `<brain>/plugins/` | Still needs `JAVIS_ENABLE_USER_PLUGINS=true` as today |

The env gate is therefore **not removed**, it just stops blocking a path that already has a guard. It remains the rescue route when you need to switch off every user-installed plugin without being able to reach the dashboard, and `JAVIS_DISABLE_PACKS` is the matching switch for packs.

**REFUSED outright in spec 1**, naming the offending field:
`transport: internal` and the `internal:` key (because `mcp_client.py:37 _INTERNAL` is a **protective allowlist** for `importlib.import_module`, not a lookup table); `auth.type: qr` (Zalo is its own path); an unknown OAuth `provider`; and **a connector id that collides with the base catalog or with another pack**. There is no `override: true` in spec 1. This one rule also kills the nastiest attack: a pack shipping `id: pancake-pos` with `url_template: https://evil.host/mcp` would **silently redirect a connection that is really logged in**, because `mcp_store.py:383-388, 489-495` rebuilds the url and headers **from the connector** on every resolve.

**Who trusts which source is the installer's choice, and Jarvis 007 has to show them enough to choose.** The owner reviewing their own pack is enough; but once there is a public store, someone who forks Jarvis 007 installs a third party's pack, and there "the author reviewed it" is no longer a guarantee for them. So a pack carries a **source label** (first-party / public store / self-downloaded zip / separate repo) shown next to its name everywhere, and the consent screen for an unreviewed pack says more than one line. Jarvis 007 does not decide for users whom to trust; it just must not let them click without knowing what they are clicking.

**Say it plainly on the confirmation screen, without softening:** `min_mode` only limits what the **model** may call, it does not limit what `register()` may do. `permissions.network` and `permissions.filesystem` are declarations, with no enforcement layer. There is no sandbox. Required wording: **"This pack runs real Python inside the Jarvis 007 server. It can read every API key, token and file that Jarvis 007 can read. Only install packs from a source you trust."** No padlock icon.

---

## Three hard truths

Said up front so nobody expects the wrong thing.

**One: only 13 of the 29 existing connectors can be expressed as a DATA pack today**, not 24 as the first design claimed. After the pack-code phase it is about 25. Three (`zalo` qr, `botcake` and `substack` internal) will permanently need the core. This number will be computed by `tests/python/test_pack_coverage.py` from the catalog, which prints the reason for each refusal, rather than copied by hand, because the first design got this number wrong by 11.

**Two: this does NOT shorten the dev team's own loop by much.** Of the 60 recent commits touching `system/mcp-catalog.json`, **41 also touched `server/*.py`**, 18 touched `tests/`, 17 touched `console.js`. The pack layer only removes the release for connectors that never needed a server change, which is exactly the cheapest part. **What this program really buys is third-party packs and the publisher's own private packs**, not a reduction of that 60.

**Three: the 29 base connectors STAY IN PLACE in `system/mcp-catalog.json`, but must be removable.** This is where the project owner corrected the first draft (2026-09-03): delete nothing now, and migrate no data, but **the code must have the right structure to be removable**, because the destination is that once the store exists we delete some, leaving exactly the default core and letting users install more themselves.

These are two different jobs, and separating them is the whole point: **data migration** (splitting the catalog file into 29 separate packs) is expensive, breaks 18 test files that read that file by literal path, and buys exactly nothing for users today. **The removable layer** is cheap, touches not one byte of the catalog, and immediately buys what is needed: users switch off connectors they do not use, and the day we really delete, the road is ready.

So build the removable layer, do not migrate. See the section "Core set and add-ons" right below.

---

## Core set and add-ons

The destination the project owner set: **once the store exists, delete some things and leave exactly the default structure of Jarvis 007, and users choose for themselves to install more plugins, skills or connections.** Nothing is deleted now, but the structure must be ready.

That structure needs only one idea: **every default capability is removable, and the "removed" state is recorded in `STATE_DIR`, not by editing the code tree.** The code tree is read-only on Docker and overwritten by `git pull` on native installs, so `STATE_DIR` is the only place state survives an update.

Three kinds of default capability, three places to record, one way of understanding:

| Kind | Lives in | Ledger recording "removed" | Exists yet |
|---|---|---|---|
| Core connectors (29) | `system/mcp-catalog.json` | `STATE_DIR/core-off.json` key `connectors[]` | Not yet, done in Phase 1 |
| Bundled plugins (11) | `system/plugins/<slug>/` | `STATE_DIR/plugins.json` key `removed[]` | `enabled`/`disabled` exist, add `removed` in Phase 2 |
| System skills (6) | `.claude/skills/`, synced into the brain by `system_sync` | `<brain>/skills/.disabled/` | **Already working** (`system_sync` respects it) |

Three accompanying rules, all aimed at avoiding the same kind of false promise:

1. **"Remove" is not "delete the file".** For something shipped with the app, removing means disappearing from the main list, from every engine, from the prompt; the file stays inside the image. Deleting the file for real would hit `EACCES` on Docker, and on native installs it would grow back after the next `git pull` - a thing that is "deleted" and comes back by itself is worse than a thing that is switched off.
2. **Removable means reinstallable, with one click.** This is the condition that makes "remove" not scary, and it is what makes it different from delete.
3. **Removing a core connector does NOT delete the connections already set up on it.** A connection is the user's data; the connector is only the mold. If you remove the mold while connections remain, those connections become **orphans**, and the orphan guard in Phase 1 is what makes that state safe instead of silently losing permissions. The UI asks directly: remove the mold only, or delete the connections too.

The day we really delete, the remaining work is just to split `system/mcp-catalog.json` into separate packs and fix the 18 test files that read it by literal path. By then it is a deliberate one-time job, with a store so users can reinstall right away, not a rushed patch halfway through.

---

## Roadmap

Each phase can be merged on its own, with green CI, and is useful by itself.

### Phase 0 - Clean connection deletion (4 days)

The other half of the original request, and also a live credential leak, and also a prerequisite for uninstalling packs. Do it first and do it separately.

- New file `server/purge.py`, the **sole owner** of the question "what can a connection leave behind". API: `plan_connection(cid)`, `async purge_connection(cid, mode="trash", purge_audit=False)`, `gc_trash(days=30)`. Every path deletion goes through a guard `_inside(path, base)` that uses `resolve()`, because `config.home_dir` is user-editable through `POST /connect/update`, and without the guard "delete connection" becomes an arbitrary `rmtree`.
- New `SessionPool.close_now(key)` in `mcp_client.py` next to `invalidate` (:451-455): pop, then **await** `obj.close()` so it reaches `_kill_tree` (:308-338). `invalidate` is fire-and-forget through `_close_later`, right for a config change, wrong right before an `rmtree`.
- Fixed order: **quiesce** (`await close_now`) → **snapshot** (move into `STATE_DIR/purge-trash/conn-<cid>__<ts>/` with a `manifest.json`) → **remove** (`oauth_mcp.forget`, `connect_health.forget`, new `mcp_hub.forget_rate`, new `capability_registry.drop_source` hard delete, new `purge_home_dir`, then `mcp_store.delete_connection`) → **invalidate** → **report**.
- `purge_home_dir`: read `config.home_dir` first, and if missing glob by the prefix `connector-home/<connector_id>-<slug>*`, and refuse anything that fails `_inside`. The two writers use two different name forms, so deriving from id and slug would miss every folder created by QR, which is exactly the 5 folders on the survey machine.
- Audit lines are **kept by default**, only the label field is cleared. A log that the pack can delete itself is no longer a log. There is a separate checkbox to delete it entirely.
- If `pool.dang_goi_tool(spec)` is true, return `{"ok": false, "busy": true}` and let the UI say so, because closing a stdio session is a SIGKILL of the whole process tree, which may be placing an order.
- Split `_kill_tree` out into `server/winproc.py` and call it from `zalo_login.cancel` (:191-203), which today only kills `cmd.exe /c npx` and misses the real node process holding the home folder.
- **Fix `safeHref`** (`console.js:156`) to also accept same-origin paths with a single leading slash (never `//`), and **all six** places that render `guide_url` go through it.
- New endpoint `GET /connect/purge-plan?id=`. The confirmation box is **drawn from the plan itself** so the warning cannot drift from what is actually done. Add a `purge_warning` field **in the catalog** (not in JS); the zalo entry says: "Deleting this connection loses the QR login session. To use it again you must open the Zalo app on your phone and scan the code again." For a connector with that field, the main button is "Move to trash for 30 days", and "Delete permanently now" requires typing the connection's exact label, following the same `confirm == name` rule as `/brains/delete` (`main.py:4517-4518`). Put "Pause" and "Sign in again" **above** Delete in the menu.

**Done when:** deleting a live stdio connection makes `ps` show the child process gone within a second instead of 900. `server/connector-home/` no longer holds its folder, including folders created by QR with a custom `home_dir`. A test snapshots `STATE_DIR`, adds a connection, uses it, deletes it, then asserts the diff is empty except for `mcp_audit.jsonl` and `logs/`. `purge_connection` on a connection whose `home_dir` is `C:\` refuses and the target folder is left intact. `javascript:...` becomes `#` at all six render sites.

### Phase 1 - Pack ledger, catalog overlay, and the removable layer (4 days) - DONE

> Shipped in 0.55.20 (`server/core_off.py`: the removable layer, the orphan guard) and 0.55.21
> (`server/packs.py`: loading packs from `STATE_DIR/packs/`, the catalog overlay, the
> `/packs` and `/packs/<id>/asset/<path>` endpoints). The pack guide-page part is not done yet:
> it must be markdown rendered server-side into filtered HTML, moved to Phase 3.

No install UI yet, no network touched. Drop a folder in and the connector appears, no new release needed. And core connectors can be **switched off**, so the removable structure exists from here on instead of waiting for the store.

- New `server/packs.py`: `load_manifest`, `installed()`, `catalog_signature()`, `connector_layers()`, `plugin_dirs()` (returns empty for now), `asset_path()`, `page_path()`, the spec 0 shim.
- Edit `mcp_catalog.py`: key the cache on `(base file signature, packs.catalog_signature())`; build `by_id` from the base file, then overlay `connector_layers()` on top, tagging `_pack: "<id>"`. The `packs` import is lazy and wrapped in `try/except` so a broken `packs.py` falls back to exactly today's behavior, matching the existing broken-file branch at `:46-48`.
- **A duplicate connector id is a refusal, never a merge.** Check the id against `_SLUG_RE` **before** building any path from it: `mcp_catalog.py:44` checks nothing today, yet `mcp_store.py:301, 421, 428` interpolate that id into paths, one of which leads to `shutil.rmtree`.
- `public_catalog()` rewrites relative icon and guide paths to `/packs/<id>/asset/...` **on the server side**, so `iconInner` (`console.js:4062-4075`, which already routes a `/` to `<img>`) needs no change.
- `classify()` for an entry with `_pack`: the `WRITE_HINTS` heuristic becomes a **floor** rather than a fallback, meaning a pack may only make classification **stricter**, never looser.
- **Orphan guard** (mandatory before anything can be removed): `mcp_store.resolved()` :386-408 today tolerates `con = None` and silently drops the headers, env and cred_dir; worse, `mcp_hub._guard` then calls `allowed(None, perm, ...)` with `perm` defaulting to `"full"`, and the function returns True unconditionally (`mcp_catalog.py:327-328`). Fix: a connection whose `connector_id` nobody supplies is marked orphaned, `resolved()` refuses to build a spec, and a startup scan shows a red banner offering "Reinstall pack" or "Delete connection".
- `mcp_hub._store_mtime()` returns `max(mtime of mcp_servers.json, mtime of packs.json)`. One extra `stat` call, closing the hand-drop case within the existing 60-second TTL. **Do not** scan every manifest on the hot path.
- `.gitignore` **and** `.dockerignore` gain six new paths, update `test_ignore_files.py`. Remember `STATE_DIR` defaults to `server/` (`config.py:15`), so on native installs packs land **inside the git tree**. Also add `server/connector-cred/`, which currently appears in neither file.
- Refuse a pack id equal to a top-level module name in `server/` (because `server/` is on `sys.path` and `__init__.py` is a valid entry file).
- **THE REMOVABLE LAYER for core connectors.** `STATE_DIR/core-off.json` shaped like `{"connectors": ["tiktok-ads", "lark"]}`, read in `packs.py` (same place, same cache keyed on `(mtime_ns, size)`), and `mcp_catalog.load()` filters them out **after** the pack overlay. Three points must be right:
  - Filter in `load()`, not in `public_catalog()`: filtering at display time still lets the tool reach the engine, so "removed" would be a false promise. `load()` is the one place every path goes through.
  - `catalog_signature()` folds in the mtime of `core-off.json`, so switching a connector off takes effect on the next load without a restart.
  - Endpoint `POST /connect/core-toggle {id, off}`. Removing the mold does **not** delete connections already set up on it: they become orphans and the orphan guard in the bullet above handles safety. The API returns the number of connections that will become orphans so the UI can ask one more question.
  - The removed list shows in a collapsed section on the Connections page, each card with a Reinstall button. No file under `system/` is deleted, see the section "Core set and add-ons".

**Done when:** a sample pack folder in a temporary `STATE_DIR` makes `mcp_catalog.get("acme.pos-vn")` return the connector, `public_catalog()` includes it with an absolute icon URL, `POST /connect/add` creates a real connection, and deleting the folder makes it vanish on the next load. Removing `tiktok-ads` makes `mcp_catalog.get("tiktok-ads")` return `None`, its card leaves the store, its tools vanish from `mcp_hub.discover_all`, and clicking Reinstall brings it all back - **not one byte of `system/mcp-catalog.json` is modified in that whole round trip**. **All 18 test files that read the catalog stay green without editing a line.** `server/bench_hotpath.py` does not regress past the 150.8ms mark.

### Phase 2 - Install from zip, consent screen, clean uninstall, Packs page (9 days) - DONE

> Shipped in 0.55.22. `server/pack_install.py` (zip rules, install ledger, two-step install
> pinned by a fingerprint, clean uninstall), `server/routes/packs.py` (7 endpoints, require a real
> session), `dashboard/packs.js` (Packs page + confirmation screen), and bundled plugins made
> removable through `plugins_host.set_removed`. NOT done yet: install from URL and separate repo
> (Phase 5), the pack guide page (Phase 3), the effects ledger for pack plugins (Phase 4).

This phase delivers exactly the part that is needed most: private packs by zip, and clean removal.

- New `server/routes/packs.py` following the factory pattern of `server/routes/__init__.py` (never imports `main`, everything through the `Deps` dataclass). **Register all 14 endpoints in one go**; the ones for later phases return 501 but **keep their final function names**, because `test_route_table.py:95-99` checks both order and names. The whole program regenerates `route_table.json` only **twice**.
- **Every `/packs/*` requires a real session, unconditionally**, independent of `gate_active()` (`config.py:811-813` returns False on the default local build, making `main.py:190-207` skip the guard). Installing requires a session and does not accept an API token. **No tool, skill or agent can reach `/packs/install`**: the endpoint is not in the hub's route table, and this goes in the docs, because `javis_add_mcp` is exactly the precedent of a model reaching an install-style surface.
- **Two-step install.** `POST /packs/inspect` streams the file to `packs-staging/<sha256>.zip` (read in 1MB blocks, abort past 25MB, **do not** copy how `/import` does it at `main.py:5952`, because it does `await file.read()` and loads everything into RAM before checking), opens the archive read-only, reads the manifest, runs every rule, and returns `{manifest, permissions, provides, tier, conflicts, sha256, staging_id}`. **Nothing is extracted yet.** `POST /packs/install {staging_id, consent_sha256, ...}` refuses if the hash does not match, which **forces what was shown to be exactly what gets installed**.
- **Zip rules.** Copy the constants and the anti-traversal predicate from `share_bundle.py:36-38, 250-255` (copy the logic, **do not call it**, because `_bad` is a closure inside `import_bundle` and that function has its own bundle shape). Add what `share_bundle` does not need yet: reject members that are not regular files via `(info.external_attr >> 16) & 0o170000` (a symlink named `plugin.py` pointing at `.secret_key` would be served right back by any file endpoint); extract with fixed 0o644/0o755, ignoring modes in the archive; block compression ratios over 100:1; reject `.env`, `*.pem`, `id_rsa*`, `*.p12` outright; **zip only, no tar** (Python 3.12 `extractall` still defaults to `filter=None`); cap the manifest size before `safe_load` because SafeLoader still expands anchors.
- **Atomic install with rollback.** Extract into `packs/.tmp-<id>-<pid>-<ts>/`, check on the extracted tree, `os.replace` the old version to `.trash-<id>-<ts>` **first**, then `os.replace(tmp, packs/<id>)`. A failure at any step rmtrees tmp and restores the old version. Then write the ledger and call the same trio that `/plugins/toggle` uses (`main.py:8091-8095`).
- **Install ledger** `packs.json` records `{version, enabled, tier, installed_at, source, sha256, code_consent, connectors[], plugins[], assets[], pages[]}`; the last four fields are the inventory used for uninstalling. Written with tmp + `os.replace` like `plugins_host._write_state` (:142-150), with `.bak` rotation and `POST /packs/repair` rebuilding from a directory scan (the consent record is lost, so it asks again, which is the safe direction).
- **Uninstall.** `GET /packs/uninstall-plan` returns exactly what will die with counts and sizes, and the dialog is drawn from it. Then: refuse if a connection is busy; **mandatory** purge of every connection belonging to the pack's connectors (no path leaves orphans, because an orphaned row can still spawn its stdio command with the permission gate gone); replay the effects ledger in reverse LIFO, each in its own `try/except`; `rmtree plugin-data/<slug>` only if the user ticks the box (default **unticked**: pack code is disposable, pack data is not); `os.replace` to `.trash-` then rmtree; remove the row in `packs.json` and every `plugins.json` entry of the pack; invalidate three caches. Return a receipt so the UI prints one honest line.
- **A bundled plugin in `system/plugins/` can never be deleted.** The code tree is read-only so even trying would hit EACCES, and a thing that is "deleted" and grows back on every image pull is worse than leaving it switched off.

- **But default plugins must still be REMOVABLE, in the sense users understand** (the project owner asked
  directly on 2026-09-03: "there will be default plugins preloaded that the customer's machine can remove"). The way to get
  there without fighting the read-only code tree: add a **removed** state, recorded in
  `STATE_DIR/plugins.json` next to the existing `enabled`/`disabled` (`plugins_host._read_state`
  :127, `_effective_enabled` :213-223). The card disappears from the main list and drops into a
  collapsed section "Removed, can be reinstalled"; `_load_all` skips it so the tool vanishes from every engine exactly like a
  real delete. It differs from deleting in exactly two points, and both are pluses: an app update does not make it
  grow back, and a mis-click is undone with one click instead of a re-download. The cost is about half
  a day, versus several days if the 11 bundled plugins were converted into preinstalled packs. This is the second row of the
  table in "Core set and add-ons"; the first row (core connectors) is done in Phase 1, and the third row (system skills) is
  already handled by `system_sync`, it only needs to be surfaced in the same place.
  Do not convert bundled plugins into packs in spec 1: they ship with the app so changing them still needs a release,
  meaning converting buys nothing and adds a migration path that has to be maintained.
- **System skills need only one button, the hard part already exists.** `system_sync` already respects
  `<brain>/skills/.disabled/`: removing a skill means moving its folder in there, and the next sync does not
  grow it back. So the work here is a Remove button on the Skills page that goes through exactly that path, plus a collapsed
  "Removed" section with a Reinstall button - not a new mechanism. Called out separately because the first draft of the plan
  put skills outside spec 1, while the project owner stated clearly on 2026-09-03 that plugins, skills and connections
  should all be installable and removable.
- New `dashboard/packs.js` exposes `window.JavisPacks = {render}`, called from the dispatch spot in console.js the way `studio.js` is. **Do not keep growing console.js** (already 6,951 lines). Register the page in five places: `VIEW_ICON`, `RAIL_ITEMS`, `RAIL_GROUPS`, keys `page.packs.label`/`sub` in **both** i18n dictionaries (currently balanced at 715/715, the JS test goes red if they drift), and a `<script src>` tag near `index.html:803`. Before writing i18n in the pack code, **rename the 11 local variables named `t` in console.js**, notably `const [t, c] = SRC[s]` (:1431) and `const chip = (t, iconName)` (:1436), both right inside `renderPlugins()`.
- **Consent screen**, drawn entirely from `/packs/inspect`: name and version; origin verbatim (file name with the head of the sha256, or repo @ ref @ commit); trust tier; for the CODE tier, a red block that cannot be collapsed with the wording above, listing every `.py` file and its size, and requiring the exact pack id to be typed; lists tools and hooks with a note that **a hook sees every tool call and its result** (`wrap_with_hooks` :533-542 wraps every tool in the route, MCP and builtin included); one line saying `permissions` is a declaration, not enforcement; the Cancel button is focused by default, no Enter-to-submit; the "Enable after install" checkbox **defaults to OFF**, per the rule in CLAUDE.md that capabilities created from chat never switch themselves on.
- On the Plugins page, a plugin that comes from a pack gets a `pack` badge and a "Manage on the Packs page" link instead of a delete button, so there is only **one** place to uninstall. `plugins_host.describe()` (:226-253) must learn the `"pack"` source, otherwise a running pack plugin would wrongly show as "enabled (not loaded)".

**Done when:** drag a sample data-only zip onto the Packs page, read the consent screen naming the domain it will talk to, install it, see the card with its own icon on the Connections page, create a connection, and **call that tool from an API engine** (OpenRouter or Gemini, not a CLI engine) to prove it goes through `mcp_hub.discover_all` and not only the SDK path. Then uninstall with purge: a recursive hash snapshot of the whole `STATE_DIR` before install is **byte-for-byte identical** to the snapshot after uninstall, except `mcp_audit.jsonl` and `logs/`. A zip containing `../../x`, an absolute member, a symlink member, a 500:1 ratio, or 600 files is rejected without writing anything to disk.

### Phase 3 - Presentation for packs (4 days)

Serve a pack's icon and guide page, with a resolve-then-check-prefix guard and a **narrow** content-type allowlist: `png`, `webp`, `jpg`. **No SVG** (SVG served from the same origin is inert inside `<img>` but runs script when opened directly in a tab). Send `X-Content-Type-Options: nosniff` and a tight `Content-Security-Policy` on exactly these two routes; the app **has no CSP anywhere yet**.

A pack's guide page is **Markdown rendered server-side into filtered HTML**, not the author's HTML: a foreign HTML page on the dashboard's origin is exactly one XSS hole away from `POST /packs/install`.

Add `category_key` to all 29 base entries in one mechanical commit, **keeping the old `category`**; `public_catalog()` emits both; the console reads `category_key` through `t("catalog.cat." + key)` with a fallback so nothing is blank. A pack that supplies an unknown `category` with a `category_label` shows its own label, with no repo change needed. A badge "from pack `<name>`" on the connector card and on the connection detail, so a connector supplied by a pack is never confused with a first-party row.

### Phase 4 - Packs with code (7 days) - DONE

> Shipped in 0.55.23. `plugins_host` learned the fourth source 'pack'; the code signature is checked at LOAD
> (`_pack_duoc_nap`), not only at install; `ctx.on_unload` + `unload(slug)` also pop
> `sys.modules`; `sys.path.insert` removed in favor of `submodule_search_locations`; the installer
> refuses a pack that hijacks a bundled plugin's name; compatibility scan at startup. NOT done:
> `ctx.record_effect` and the effects ledger, `permissions.max_effect`.

`_iter_plugin_dirs` gains the source `("pack", d)`, in the order **bundled → pack → user → vault**. **A pack with a plugin folder whose slug equals a bundled slug is rejected at install time** (the deny list is the 11 bundled slugs). This keeps today's behavior of user/vault overriding bundled exactly bit-for-bit, while blocking a pack from silently replacing `javis_task`/`javis_schedule`/`javis_add_mcp` under a consent screen that only says "this runs code".

**The env gate does NOT apply to packs.** A pack's plugin loads when the pack has a valid `code_consent`, and that is enough; `_env_user_enabled()` stays bit-for-bit unchanged for the `user` and `vault` sources as today. The full reason is in "Trust boundary": the env gate plugs the "writable folder with nobody clicking" hole, while the installer has a person clicking, a screen listing every `.py` file, and a digest recorded - the same kind of guarantee, only per pack instead of all-on or all-off. `JAVIS_DISABLE_PACKS` is the matching switch that turns packs off completely.

**Consent is checked at LOAD, not at install.** `code_consent` records the digest of every `.py` file in the pack; `_load_all` recomputes the digest from disk and refuses to load on a mismatch, and the digest sits inside `_signature()` so changing content forces a reload instead of riding on the mtime cache. Anyone who can write `plugin.py` can also write `packs.json`.

`ctx.on_unload(fn)` and `ctx.record_effect(kind, ref)`. Tools and hooks are **already** reversible (register only appends to lists on the `LoadedPlugin` in the cache, there is no global registry, and the hub rebuilds the route table on every cache miss). What is **not** yet reversible: `sys.modules[mod_name]` set at :340-341 and never popped, plus every thread/socket/atexit that `register()` opens. So `plugins_host.unload(slug)` runs `on_unload` in reverse LIFO, drops the cache, then pops every `javis_plugin_*_<slug>` key. `set_enabled(..., False)` goes through `unload` so the "Off" button really stops it. Add a manifest key `unload: clean | restart-required` so the UI says "restart needed" instead of lying.

**Fix `sys.path.insert(0, plugin_dir)`** in `_import_entry` :348-350: a pack containing `config.py` or `mcp_hub.py` currently **shadows the server's own modules** throughout its module body. Use `submodule_search_locations` instead of poking `sys.path`.

**Startup compatibility scan:** checking `compat.app` at install is not enough, because `update.sh` (`git pull`) and `updater.py:326` never rerun the installer. Add a pass at boot that **switches off** (never deletes) any pack whose range no longer matches `VERSION`, with the reason on its card.

Do not convert `meta-ads-graph`, `meta-pages-graph`, `fb-monitor-apify` into packs in spec 1. They are evidence that one format is right, not a migration target: the `CONNECTOR_ID` coupling can only be removed once there is a `ctx.connector_id`, and that is later work.

### Phase 5 - Install from URL and separate repo (4 days) - HALF DONE

> Shipped in 0.55.24: `server/packs_fetch.py` (SSRF guard by resolved address, rechecked
> at every redirect hop, cap by real bytes) and the `/packs/install-url` endpoint.
> NOT done: token for a private repo, pinning by commit, periodic new-version check. A private pack
> still ships as a .zip file, which is already enough to use.

New `server/packs_fetch.py`. **Zip over HTTPS only.** No `git clone` even though the image has git, for three reasons: the token ends up in argv and is readable from `/proc/<pid>/cmdline` (exactly the shape of `_auth_url` at `git_brain.py:489-503`, the reason `_redact` exists); a clone pulls the whole history so size cannot be capped before the bytes land; and `httpx` is already pinned so the HTTPS path adds neither a dependency nor a subprocess. The token travels in a **header**.

- `owner/repo@ref` → `api.github.com/repos/<o>/<r>/zipball/<ref>` with `Authorization: Bearer`.
- GitLab → `repository/archive.zip?sha=<ref>` with `PRIVATE-TOKEN`.
- `git+https://` is **not in** spec 1: no subprocess, no argument-injection surface.

**SSRF guard**, which the server **has nowhere today**: `https` only, port 443 only, and every resolved address must fail `is_private / is_loopback / is_link_local / is_reserved / is_multicast`; at most 3 redirects, **rechecked against the resolved socket address after every hop**, not against the hostname. This is very concrete: `mcp_hub.py:82` puts the hub at `http://127.0.0.1:7777/hub/mcp`, and the hub holds all of the user's keys. To be complete: `/hub/mcp` skips the cookie guard (it is in `_AUTH_PUBLIC_EXACT`, main.py:158-162) but is NOT open - `handle_http` requires a `Bearer hub_token` compared in constant time. What the SSRF guard blocks is a different layer: a URL supplied by someone else that points at loopback makes the request go OUT from the server process itself, so it is already inside the network perimeter, and any internal service that trusts localhost becomes a target. The guard must exist before opening the download-from-URL path, not after.

**Tokens are stored per host, Fernet-encrypted in settings.** `config.py:452 _SECRET_PATHS` gains `"packs.tokens.*"`, which needs ~6 lines changed in `_transform_secret_fields` to understand a trailing `*` as "every key of this dict", and the same character must be added to `secret_paths_hong()` otherwise the broken-secret reporting silently stops covering them.

**Version pinning:** record the requested `ref`, the resolved `commit`, and the `sha256` of the archive. Pinning by branch shows an amber chip "tracking main". **Never auto-update a pack with code.** On update, recompute `permissions` and the code digest; if broader, install in the **off** state and ask again. Keep one rollback generation in `packs/.prev/<id>/`.

### Phase 6 - Public store (4 days) - DONE

> Shipped in 0.55.24. `server/packs_store.py`, `system/pack-index.json`,
> `docs/dev/pack-store-index.md`, and the store grid in `dashboard/packs.js`. The project owner settled
> 2026-09-04: the store holds first-party packs only, DROP download counts (a static JSON file cannot count them,
> and counting ourselves would mean clients calling back to the server, which becomes a privacy matter that must be stated clearly).

`server/packs_store.py` fetches `packs.store_url` **server-side** (keeping the token and the SSRF guard on the server, and avoiding CORS entirely), with `If-None-Match`, cache TTL 6 hours. The index schema is published in `docs/dev/pack-store-index.md`, each entry mirrors the manifest plus `download: {url, sha256, size}`, `verified`, `updated`, and the reserved `listing` block. **The price fields are present from v1** so a paid pack later is just a "Buy" button opening `purchase_url`, not a format break.

The `sha256` is **pinned from the first install**, in the ledger. Checking a download against a hash supplied by that same index proves nothing about the publisher; refusing an artifact that **has changed** under the **same version** does.

**The public store may list CODE-tier packs**, but a tap from the store must still go through the same consent screen as zip and URL - there is no "install now" shortcut for a pack containing Python. With two things so the installer sees what they are choosing: a **source label** (first-party / community / unreviewed) and one line saying plainly that this pack runs code. First-party packs get the `verified` label in the index; community packs do not, and their consent screen says more. Jarvis 007 does not decide for users whom to trust.

Three degraded states, none of them a stack trace: with a cache, show an amber line and still draw the grid; with no cache, an empty state with "you can still install from zip or URL"; an unknown `format_version` says outright "this store needs a newer Jarvis 007", never parsing halfway.

Add the environment variable `JAVIS_DISABLE_PACKS`, read live, deny wins, switching off every non-bundled pack without opening the dashboard.

Treat the index as **untrusted data**: a pack's `name`, `description` and tool descriptions go straight into the tool list of engines that are holding Bash.

### Phase L - Language freeze (10 days, runs in parallel)

Can run at any time; the only ordering constraint is that `category_key` must be done before Phase 6.

- **Blocking gate.** New `tests/python/test_ngon_ngu_ma_nguon.py`, scanning the AST with a **CLEAN list by path in ratchet style**, exactly the pattern the repo has used twice (`MIEN_TRU` in `test_lang_bat_bien.py`, `I18N_MIGRATED` at `tests/js/test_i18n.mjs:178`). Seed CLEAN with `server/routes/**` (measured 0 real flags), `server/packs*.py`, `server/purge.py`, `dashboard/packs.js`. Rule in CONTRIBUTING.md: every new module goes into CLEAN in the very commit that creates it. Plus a whole-tree check with no allowlist that no identifier contains a non-ASCII character (measured at **exactly 0** today, so it is a free ratchet). The escape hatch `# lang-ok: <reason>` prints how many times it is used.
  Do not use ruff (the repo has no ruff, and no rule can express "is this a Vietnamese word"), do not scan by git diff (`actions/checkout@v4` has no `with:` so fetch-depth is 1, no merge base), do not use an 853-entry baseline (false positives cannot be reduced on `cap`, `do`, `con`, `day`, `ban`, `tin`, `set`, which are Vietnamese words without diacritics that are also English words).
- **Merge the slugify functions**, this is a bug fix, not tidying up. Promote a single `ascii_slug()` based on the correct version at `main.py:4567`, route both `share_bundle` and the pack loader through it, and move `main.py:4709, 5887, 7138` off `_slugify` (which uses `\w` with `re.UNICODE` and so **keeps diacritics**, meaning every new brain is being seeded with an agent file whose slug carries diacritics).
- **Rename the public contract**, each with a read-both-write-the-new strategy with a stated deadline: 7 Vietnamese URL routes (not 5, missing `/usage/tong-quan` and `/usage/bao-cao`), the aliases joined into **one block at the end** of the route list so `route_table.json` only grows by 7 lines without renumbering; ~13 returned JSON fields renamed together with their consumers in the dashboard in one commit (no alias needed, every consumer is first-party JS in this repo); 5 settings keys plus `nguon_tra_loi` get a `_migrate_key_names` step added to the normalization chain of `read_settings` (`config.py:698`) and that step must **pop** the old key, because `_deep_merge` lets both live; and `muc_quyen` → `permission` (140 places, 15 files, the biggest item, and the same concept as `min_mode` in `plugin.yaml` and `discover_all(mode)`, so the pack format must absolutely not spawn a fourth name).
- **Error codes instead of building an i18n framework for the server.** Return `{"ok": false, "error_code": "tts_no_audio", "error": "<Vietnamese text>"}` and let the dashboard render `t("err." + error_code)` with a fallback to the Vietnamese sentence itself. This turns an unbounded server-side project into a finite dictionary-key project, at exactly the layer that already has 715/715 English.
- Move `chatbot_runtime.py:515 _DAU_BI` and `conversation_state.py:26 _GOAL_RE` into `server/lexicon/` (bug number 4 above).

**Done when:** adding `def _kiem_tra_moi(): pass` to `server/routes/domain.py` turns `python tests/run.py lang` red and names the right file, line and word; adding `# lang-ok:` turns it green with a usage count of 1. `ascii_slug("Đo lường doanh thu") == "do-luong-doanh-thu"` and an agent with the letter Đ in its name survives one export/import round trip byte for byte. Both spellings of all 7 URLs return byte-identical responses.

---

## How far it is done (updated 2026-09-04)

| Phase | Status | Version |
|---|---|---|
| 0 - Clean connection deletion | Done | 0.55.19 |
| 1 - Pack ledger, catalog overlay, removable layer | Done | 0.55.20 and 0.55.21 |
| 2 - Install from zip, consent screen, clean uninstall | Done | 0.55.22 |
| 3 - Pack guide page | **Not yet** | |
| 4 - Packs with code | Done | 0.55.23 |
| 5 - Install from URL and separate repo | Done | 0.55.24 and 0.55.25 |
| 6 - Public store | Done | 0.55.24 |
| L - Language freeze | **Not yet** | |

Beyond the original plan, 0.55.25 also did the part the first draft left outside spec 1: **packs can carry
agents, workflows and skills**. The mechanism is in `server/pack_vault.py`, reusing exactly the normalized hash pattern of
`system_sync` rather than writing a second one. Three rules: installing does not overwrite anything the pack did not put there;
updating only overwrites an entry that is still unchanged; uninstalling only deletes what has not been edited.

What notably remains: the pack guide page (Phase 3), pinning packs by commit and the periodic new-version check
(second half of Phase 5), and all of Phase L.

---

## After everything is done, what still needs a new release

Said plainly, because the painful number is 524 releases in 3 months and this program does **not** cut it in half.

One point to restate versus the first draft: **the 29 core connectors are now REMOVABLE from Phase 1**, so the list below is only still true for FIXING or ADDING a core connector, no longer for taking one off a user's machine.

**Still needs a new release:** a new OAuth dialect (`meta`, `google`, `generic` are selectable by a pack, a fourth is a PR into the core, and splitting the Meta branches apart is the most regression-prone change in this repo, and if it breaks it shows up 60 days later as silently expired tokens rather than a red test); a Zalo-style QR login flow; `transport: internal`; **a new field in the connector description** (the schema is still growing: `inject_args` was added 08/19, `url_template` 07/31, static `env`, `cred_dir`, `isolate_home` are all only a few months old, and 8 of the 60 recent catalog commits also edit `mcp_catalog.py` itself; the policy is that an unknown key is **ignored, never refused**); fixing or adding one of the 29 core connectors; any dashboard UI beyond one icon and one guide page (there is no build step, 34 hand-versioned script tags, and adding a JS loader for packs would spawn a second extension system); and `notifications/tools/list_changed` for an already-open CLI session.

**No longer needs a new release:** a new apikey/http connector with its icon, guide page, group label, `tool_meta`, `validate`, `arg_rules`, `rate_limit`; a new plugin with a tool and a hook; and **those same two things shipped privately to one customer by zip or a private repo**, exactly the goal set.

**Parallel pairs that will exist permanently, listed so nobody is surprised:** `system/mcp-catalog.json` next to a pack's connector YAML; `plugin.yaml` (spec 0) next to `javis-pack.yaml`; `system/plugins/` next to `STATE_DIR/packs/`; `plugins.json` next to `packs.json`; `/plugins` next to `/packs`; `connector_id="custom"` next to packs. Each pair has its own reason. No pair dies out.

---

## Effort

| Phase | Content | Days |
|---|---|---|
| 0 | Clean connection deletion, `purge.py`, `close_now`, `safeHref` | 4 |
| 1 | `packs.py`, catalog overlay, orphan guard, removable layer | 4 |
| 2 | Zip install, consent screen, clean uninstall, routes, Packs page | 9 |
| 3 | Assets, guide page, CSP, `category_key`, badge | 4 |
| 4 | Packs with code, consent by hash, `unload`, `sys.path` | 7 |
| 5 | Install from URL and separate repo, SSRF guard, token storage | 4 |
| 6 | Public store, kill switch, new-version check | 4 |
| L | Language gate, slugify, contract renaming, error codes | 10 |

About **46 person-days** in total, of which **phases 0 to 2 (17 days) are fully delivered**: clean deletion, a working pack layer, and private packs by zip. Phases 0, 1, 2, 3, 5, 6 merge independently. Phase L runs in parallel.

---

## Acceptance

```
.venv\Scripts\python tests\run.py              # all 234 files; system python lacks libs
.venv\Scripts\python tests\run.py packs
.venv\Scripts\python tests\run.py purge
.venv\Scripts\python tests\run.py cred_dir     # must be green: guards that delete_connection still calls forget_cred_dir
.venv\Scripts\python tests\run.py catalog      # no em dash, guide wrap, line length, now also scans packs
.venv\Scripts\python tests\run.py i18n         # dictionary balance, placeholder balance, I18N_MIGRATED ratchet
.venv\Scripts\python tests\run.py lang         # identifier gate
.venv\Scripts\python server\bench_hotpath.py   # build_system_prompt does not regress past 150.8ms
```

The most notable new test is **`test_packs_purge.py`**: a recursive hash snapshot of `STATE_DIR`, install a sample pack, create a connection on its connector, call a tool, uninstall with purge, then assert the snapshot is identical byte for byte. Plus a regression form: assert that the `cid` string appears in **no** file name and **no** file content under `STATE_DIR`. That second half is what catches the **next** kind of artifact that someone adds and forgets to tell `purge.py` about.

Accompanying: `test_pack_coverage.py` (computes the 13/29 number itself and prints the refusal reasons), `test_packs_zip_safety.py` (traversal, absolute member, symlink, executable bit, 500:1 ratio, 600 files, YAML alias bomb), `test_purge_giet_tien_trinh.py` (spawns a real process, purges, asserts `poll() is not None` immediately and not 900 seconds later), `test_packs_fetch_ssrf.py` (a 302 from a public host to `169.254.169.254` must be blocked, proving the guard reruns at every hop), `test_packs_secret.py` (the token on disk must start with `enc:`).

**Manual run, end to end:** build a sample zip → drag it onto the Packs page → read the consent screen → install with the "Enable after install" box **unticked** → enable → create a connection → call that tool **on all three kinds of engine** (Claude Code, Codex, and an API engine such as OpenRouter; the third is what proves it goes through `mcp_hub.discover_all` and not only the SDK path) → run one more background loop tick → uninstall with purge → `tools/list` is clean → the snapshot diff is empty. **Then repeat the whole thing in Docker** with the read-only code tree under a non-root user, asserting every byte lands in `/data/state/packs/` and **nothing** is written to `/app`, and that `docker compose restart` leaves the pack intact.

One thing that must be done by hand, not automatically: **do not delete the 5 orphaned `connector-home/zalo-*` folders on the running machine yourself.** Report them and offer a single cleanup pass, because one of them may still hold a session the user still needs.

---

## Answering the question "is it too late to fix Vietnamese now"

It is not too late, and it is much cheaper than it first feels. Real measurements:

- **0 identifiers with diacritics** in all of `server/**/*.py`. Not one function or variable.
- Vietnamese identifiers without diacritics: **181 functions (7.2%), 0 classes, 81 variables**. Almost all are private helpers with a leading underscore.
- Public contract touched by Vietnamese: **about 22 places**, all listed in Phase L.
- **Agent/workflow/loop frontmatter and all 35 SQLite tables already use English keys**, with a rule written straight into `server/meta_tools.py:79` requiring it.
- `dashboard/i18n/en.json` **already has all 715/715 keys**.

That means the **most expensive** part of internationalization, changing the data schema stored on users' disks, **barely exists**. Nobody has to migrate a brain.

What is really still owed, ordered by how much it blocks an English-speaking user **today**:

1. **`CLAUDE.md`, 33.7KB of Vietnamese, read verbatim into every system prompt.** It does not block, because the model reads Vietnamese instructions and answers in English just fine, and the project's own docs have already rejected translating it into N copies (N copies means N things drifting apart). It does cost tokens.
2. **~2,081 Vietnamese strings still hard-pinned in JS**, only ~25% extracted into the dictionary so far (`console.js` 328 `t()` calls, `studio.js` 96, `app.js` exactly 4, the other 30 files at 0). **This one really blocks.** It is work to peel off gradually through the `I18N_MIGRATED` ratchet, not to do in one pass.
3. **~2,244 strings in Python, 0% covered**, and there is no `t()` function on the server side. It blocks, but the cheap way is the **error codes** in Phase L rather than building a whole framework.
4. Docs, commit messages, CHANGELOG in Vietnamese. Does not block, just not tidy.

In short: starting in Vietnamese was not a mistake. The project accidentally got the most expensive part right (English data keys), and what remains is display strings, which can be peeled off gradually without breaking anything.
