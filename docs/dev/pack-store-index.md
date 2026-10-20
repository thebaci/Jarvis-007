# Pack store: catalog format and how to publish

The Jarvis 007 pack store is **exactly one public JSON file**. There is no server to run, no
database, no accounts. Edit that file and the store changes.

It can be this simple because the store does only ONE job: helping users **find** a pack. The hard work (opening the
pack, checking, asking, installing, uninstalling cleanly) lives in `server/pack_install.py`, which does not care where a pack comes from.
Installing from the store goes through **exactly** the same confirmation screen as dragging in a `.zip` file.

The store lives in a **SEPARATE REPO**: [blogminhquy/javis-store](https://github.com/blogminhquy/javis-store),
and Jarvis 007 reads `index.json` there through `raw.githubusercontent.com`. Users can switch to another store with the
`packs.store_url` key in `settings.json`.

Splitting the repo is the key point of this whole layer, not tidiness. It opens up two things:

- **Adding a pack no longer depends on shipping a new app release.** Push one commit to the store repo and every
  running machine sees it on its next catalog refresh.
- **Strangers can contribute.** They send a Pull Request to the store repo, the store owner reads the code and only then merges - and
  nobody needs write access to the Jarvis 007 source code.

`system/pack-index.json` in this repo is now **frozen**, kept only so releases 0.55.24-0.55.29 (which point
straight at it) can still browse and install. Do not add anything to it any more.

---

## Format

The `"vi"` values below are the Vietnamese-locale strings of the example pack, kept as they are (the keys select the display language).

```json
{
  "format": "javis-pack-index",
  "format_version": 1,
  "updated": "2026-09-04",
  "store": {"name": "Kho gói Jarvis 007", "url": "https://github.com/..."},
  "packs": [
    {
      "id": "javis.tinh-gia",
      "name": {"vi": "Tính giá bán", "en": "Pricing helper"},
      "description": {"vi": "Tính giá bán từ giá vốn và biên lợi nhuận."},
      "version": "1.0.0",
      "author": {"name": "Jarvis 007"},
      "kind": "tool",
      "category": "sales",
      "category_label": {"vi": "Bán hàng", "en": "Sales"},
      "tier": "code",
      "verified": true,
      "updated": "2026-09-04",
      "homepage": "https://github.com/...",
      "icon": "packs/javis.tinh-gia/assets/tinh-gia.png",
      "download": {
        "url": "https://github.com/.../releases/download/v1.0.0/javis-tinh-gia.zip",
        "sha256": "abc123...",
        "size": 3052
      },
      "listing": {"price": {"amount": 0, "currency": "VND", "model": "free"},
                  "purchase_url": ""}
    }
  ]
}
```

Required: `id` and `download.url`. An entry missing either one is **skipped** rather than shown, because
a card that cannot be installed when clicked is worse than no card.

`download.url` may also be relative; Jarvis 007 joins it with the address of the index file itself.

`icon` is the logo on the card in the Store: a path **relative** to the index file, pointing at
a `.png` / `.webp` / `.jpg` / `.gif` image. Jarvis 007 joins it like `download.url` and keeps it only when the
result is on the **same host** as the index; an absolute URL, `data:` or `.svg` is dropped and the card falls back to the
letter tile. The same-host rule exists so that a store entry cannot become a beacon calling a third party's server every
time a user opens the grid. The main store puts the logo inside the pack (`packs/<id>/assets/`), so the card in the
store and the Connections page after install use exactly one file.

---

## Five easy misunderstandings

**`kind` is what splits the grid into tabs.** One of `agent`, `skill`, `workflow`, `tool`,
`connector`, `bundle`. It decides which chip an entry appears under and what label it carries, and it is the path
users take to get there: clicking the Store tab on the Skills page opens the store already filtered to `skill`. An
unknown or missing value falls back to `bundle` and is NOT dropped - a card that a filter misses is still better than a card
that vanishes with nobody knowing why. Use `bundle` for a pack that really contains several things.

**`tier` is a claim, not the truth.** It is only for filtering and showing a label on the grid. The REAL tier
is computed by the installer from the downloaded file (`pack_install.soi` scans for `.py`, `transport: stdio`, an `env`
block...). Claim `data` while packaging `code` and the confirmation screen still tells the truth, and still shows the red warning
block.

**`sha256` is a TAMPER-PROOF lock, not a check of who published it.** It and the download address
sit in the same file, so whoever can edit that file can edit both. What it really catches is the case where the downloaded file is
**different** from what the store announced, that is, the download path was intercepted. With a `sha256`,
Jarvis 007 stops right at the download step, before it has asked anything.

**Every field is trimmed and type-coerced on read.** `packs_store._lam_sach` is the only place that
decides which fields pass through; unknown keys are dropped. The reason: `name` and `description` go straight into the UI,
and a pack's tool descriptions go straight into the tool list of engines that hold Bash.

**An unreachable store does NOT break anything.** With a cache, the grid is still drawn with a line saying the data
is stale; without a cache, the empty state with a reminder still lets you install from a file. Installed packs do not depend
on the store at all.

---

## Publishing a pack

Do this in the store repo, not this one.

1. Put the source in `packs/<id>/`, then package it and get the fingerprint in the same step:
   ```bash
   python tools/dong-goi.py javis.tinh-gia
   ```
   The command prints the file path and the `sha256`. Packing with `zip -r` also works, but remember to exclude
   `__pycache__`: it leaks into the code's content signature so two machines would produce two different `sha256` values.
   The manifest `javis-pack.yaml` must be at the root of the archive, or inside exactly one wrapper folder like a GitHub
   zipball, which Jarvis 007 unwraps by itself.
   The command puts the file into `dist/` automatically with a name that includes the version and prints the JSON block ready to paste.

2. Add an entry to `packs[]` in `index.json`, declaring `download.url` as **relative**
   (`dist/javis-tinh-gia-1.0.0.zip`). Jarvis 007 joins it with the address of the index file itself.

   The file and the catalog entry go in the SAME commit, so there is never a moment when the index already points to
   the new version while the file is not uploaded yet. For large packs use a Release and declare an absolute address.

3. Push to the `main` branch of the store repo, or open a Pull Request if you are not the store owner.

Keeping the source next to the release file is deliberate: a `code`-tier pack runs real Python inside the installer's Jarvis 007 server,
so they must be able to read it without downloading anything first. `packs/javis.tinh-gia/` is a
working pack to copy as a template.

Jarvis 007 caches the catalog for 6 hours, so after pushing, click **Refresh** on the Store page to see it right away.

---

## Releasing a new version of a published pack

Raise `version` in BOTH places: the manifest inside the pack, and the entry in the index. Repackage (the file
name carries the new version number by itself), KEEP the old file in `dist/` - users need to download the previous version when the new one is
broken - then change `download.url` and `sha256`.

People who installed the old version will see the button change to **Update to vX**. Clicking it goes through exactly the reinstall
flow: download, open and inspect, confirm. **Jarvis 007 never auto-updates a pack that contains code** - a new version can
change the code, and if the code changes without anyone looking, the whole content-signature lock in
`plugins_host._pack_duoc_nap` becomes meaningless.

**Third-party MCPs are different** (the repo owner decided on 2026-10-05): when that party has an official release,
the connector follows that release. A connector that runs through `npx`/`uvx` fetches the MCP from npm/PyPI and writes the package name with
`@latest`; leaving the version empty is not enough, because `npx`/`uvx` reuses the version downloaded the first time. When the third party ships a
new version, the machine runs it on the next start, with no pack release or Jarvis 007 release needed. An exception is
declared with `ngoai_le_ban_chinh_thuc` plus a reason. The only exception today is Zalo: it no longer follows the
upstream release, Jarvis 007 moved to its own CLI build and only keeps the `zca-js` library following the official release.
`tests/python/test_mcp_official_release.py` guards the app's catalog, `tools/kiem-tra.py` guards the store, and
the `soi-ban-moi` job in the store's CI really runs the latest release every day to catch new tools that are not yet
classified.

---

## Packs that carry agents, workflows, skills

Files go in `agents/`, `workflows/`, `skills/<slug>/` inside the pack; Jarvis 007 finds them **by
folder**. Only `provides.connectors` must be declared in the manifest, because each connector is a file
that must point at the right name; declaring `provides.plugins` or `provides.skills` as well is so that someone reading the manifest
can see what the pack has without opening every folder, and the installer does not read it.

They are written into the **brain that is open when you click Install**, not every brain.

Three rules, and they are the reason this part has its own module (`server/pack_vault.py`):

1. Installing **does not overwrite** an existing entry that the pack did not put there. If the user picked the same name,
   their file wins, and the confirmation screen says so in advance.
2. A pack update overwrites only when the entry is **still exactly as** the pack placed it. If it was edited, the user's
   version is kept, exactly how `system_sync` treats system skills.
3. Uninstalling **deletes only what is still unchanged**. Edited items are kept and the dialog says clearly what it kept.

The hash comparison reuses `system_sync`, so line endings are normalized: opening a file in a Windows editor
and saving it is **not** mistaken for an edit.

## Private stores that need an access token

Stored in Settings, **one token per hostname** (one GitHub token works for every repo it has access to).
The token is encrypted when written to disk, travels in a header rather than in the address, and is **dropped when
redirected to a different hostname** - forwarding the old host's token to the new host is the most common
way tokens leak.

## Where the store shows up in the app

The store is **one** store, on the **Store** page in the sidebar. Four capability pages (Agents, Skills,
Workflows, Plugins) each have a tab that leads there, already filtered to that page's kind.

The tab only NAVIGATES, it does not embed a copy of the grid. Four copies are four things that drift apart after
a few months, and users would have to learn the same interface twice.

## Deliberate limits of this version

Not yet there: a dedicated guide page per pack; pinning a pack to a commit; periodic checks for new versions; and download
counts.

Ceilings: 500 packs per index, 4MB for the index file, 25MB for one pack.
