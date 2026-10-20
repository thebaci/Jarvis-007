# Design: Google Keep connector

Date: 2026-07-20
Status: awaiting approval

## Goal

Let Jarvis 007 read and operate on notes in Google Keep, wired through the community MCP server
[feuerdev/keep-mcp](https://github.com/feuerdev/keep-mcp) (PyPI `keep-mcp` 0.3.1, Python >=3.10).

## Background: why a master token is needed

Google Keep has NO public API for personal gmail accounts. The official API (Keep API) is only open
to Google Workspace Enterprise with a service account + domain-wide delegation. The account used here
is a regular gmail, so the only route is the unofficial library `gkeepapi`, which requires a
**Google Master Token**.

A master token is NOT a scope-limited OAuth token. It is an Android device-level token, shaped like
`aas_et/...`, [with full access to the account, equivalent to the password](https://gkeepapi.readthedocs.io/en/latest/):
whoever holds it can mint tokens for nearly every other Google service (Gmail, Drive, Photos, Contacts).

Jarvis 007 encrypts secrets at rest with Fernet via `secrets_store.encrypt_map` (see `mcp_store.save`),
so the token is not plaintext on disk. But encryption at rest does not change the nature of
"token = full account access", and the token will also sit on the Hostinger VPS.

This risk was spelled out to the user, who accepted it and chose to use their main account.

## Decisions made

1. **Scope of operations**: turn on `UNSAFE_MODE` so Jarvis 007 can edit ANY note, including notes handwritten
   in the Keep app (the server's default only allows editing notes it created itself, tagged with the `keep-mcp` label).
2. **Account**: use the main account, no secondary account.
3. **Runner**: `uvx` rather than `pipx` as the README suggests, to match the existing stdio connectors
   (`google-sheets`, `tiktok-ads`). `uv` is already available via `requirements.txt`, nothing to add (see below).
4. **`UNSAFE_MODE` is an optional input field**, NOT hard-coded in the catalog.

On decision 4, the reason: hard-coding `UNSAFE_MODE=true` would pre-enable edit-any-note mode for everyone
who forks Jarvis 007, against the settled principle that capabilities touching personal data must be opt-in, default OFF.
Making it an input field still gives this user exactly what they chose (type `true`), keeps forks clean, and
the dangerous switch is plainly visible on the Connections page so it can be removed later. It also needs NO core change,
because `mcp_catalog.build_env` currently builds env only from `auth.fields` that declare an `env`, and does not yet support
static env at the connector level.

## Change 1: catalog entry

Add to `system/mcp-catalog.json`, the `connectors` array. Do not change `mcp_hub`, `mcp_store`,
`mcp_catalog`, or the dashboard: all the infrastructure is already there (the sign-in form is generated from `auth.fields`,
secrets are encrypted automatically, the three permission levels apply automatically through `tool_meta`).

The icon is an emoji instead of a logo file, following the precedent of `google-search-console` (`🔍`) and
`google-workspace` (`📧`). This avoids pulling trademarked assets into the repo.

Note: `requires` is PURELY DOCUMENTATION metadata, nothing in the code reads it (grepped
`server/*.py` and `dashboard/console.js`). `lark` declares `requires: {node: ">=18"}` also just for reading.
Keep it to match precedent and so later readers know what the connector needs, but do NOT expect it to stop a
missing `uv`. What actually guarantees `uv` is present is the `uv>=0.5` line in `requirements.txt`.

The catalog strings below are the Vietnamese text as it appears in the catalog data (the catalog itself is user-facing data and is not part of this
document). `"category": "Văn phòng"` is a machine value the code matches on; it means "Office".

```json
{
  "id": "google-keep",
  "name": "Google Keep",
  "icon": "📒",
  "category": "Văn phòng",
  "description": "Đọc và sửa ghi chú Google Keep: tìm note, tạo note/danh sách việc, gắn nhãn, ghim, lưu trữ. Chạy local qua thư viện không chính thức - cần Google master token.",
  "status": "beta",
  "transport": "stdio",
  "command": "uvx",
  "args": ["--from", "keep-mcp", "python", "-m", "server"],
  "requires": { "uv": true },
  "auth": {
    "type": "apikey",
    "fields": [
      {
        "key": "google_email",
        "label": "Email Google",
        "placeholder": "ten@gmail.com",
        "env": "GOOGLE_EMAIL"
      },
      {
        "key": "master_token",
        "label": "Google master token (aas_et/...)",
        "placeholder": "aas_et/...",
        "env": "GOOGLE_MASTER_TOKEN"
      },
      {
        "key": "unsafe_mode",
        "label": "Cho sửa MỌI note - gõ true nếu muốn (để trống = chỉ sửa note do Jarvis 007 tạo)",
        "placeholder": "để trống cho an toàn",
        "optional": true,
        "env": "UNSAFE_MODE"
      }
    ],
    "guide": "Google Keep KHÔNG có API chính chủ cho gmail thường nên phải dùng master token. CẢNH BÁO: token này có TOÀN QUYỀN tài khoản Google của bạn (Gmail, Drive, Photos...), tương đương mật khẩu - đừng chia sẻ cho ai. Lấy 1 lần: (1) Bật xác minh 2 bước cho tài khoản. (2) Vào myaccount.google.com/apppasswords tạo App Password 16 ký tự. (3) Chạy lệnh này trong terminal (cần cài uv: winget install astral-sh.uv): uv run --no-project --with gpsoauth python -c \"import gpsoauth; print(gpsoauth.perform_master_login('EMAIL_CUA_BAN','APP_PASSWORD_16_KY_TU','0123456789abcdef')['Token'])\" (4) Dán chuỗi bắt đầu bằng aas_et/ vào ô Master token. Ô cuối để trống thì Jarvis 007 chỉ sửa được note do chính nó tạo; gõ true thì Jarvis 007 sửa được mọi note kể cả note bạn viết tay.",
    "guide_url": "https://github.com/feuerdev/keep-mcp"
  },
  "validate": { "tool": "list_labels", "args": {} },
  "tool_meta": {
    "read": ["find", "get_note", "list_labels", "list_note_collaborators", "list_note_media"],
    "write": [
      "create_note", "create_list", "update_note",
      "add_list_item", "update_list_item", "delete_list_item",
      "set_note_color", "pin_note", "archive_note", "restore_note",
      "create_label", "add_label_to_note", "remove_label_from_note"
    ],
    "danger": [
      "trash_note", "delete_note", "delete_label",
      "add_note_collaborator", "remove_note_collaborator"
    ]
  },
  "default_perm": "readonly",
  "risk": "Kết nối này dùng Google MASTER TOKEN - token có TOÀN QUYỀN tài khoản Google (Gmail, Drive, Photos), không phải OAuth giới hạn phạm vi. Mức Ghi nháp cho Jarvis 007 tạo/sửa note, ghim, lưu trữ, gắn nhãn thật trong Keep. Mức Toàn quyền thêm quyền VỨT/XOÁ note và CHIA SẺ note cho người khác. Nếu đã gõ true vào ô UNSAFE_MODE thì Jarvis 007 đụng được cả note bạn viết tay, không chỉ note nó tạo."
}
```

For readers, the main user-facing strings mean: the `description` says "Read and edit Google Keep notes: find notes, create notes/to-do lists, label, pin,
archive. Runs locally through an unofficial library - needs a Google master token." The `guide` explains that Keep has no official API for regular gmail, warns that the
token has FULL access to the Google account, and walks through: enable 2-step verification, create a 16-character App Password at
myaccount.google.com/apppasswords, run the `gpsoauth` command in a terminal, and paste the `aas_et/` string into the Master token field; leaving the last field empty
limits edits to notes Jarvis 007 created, typing `true` allows editing every note. The `risk` text warns that Draft level lets Jarvis 007 create/edit/pin/archive/label real notes, and Full level adds
TRASH/DELETE and SHARE with other people.

### How it is invoked: why NOT `uvx keep-mcp`

The first version of the design declared `args: ["keep-mcp"]` following the README. Real-world verification showed it is BROKEN,
and broken in a silent way, so it is worth recording.

The package `keep-mcp` 0.3.1 declares a console script named `mcp` (`server.cli:main`). But its own dependency,
the MCP Python SDK (`mcp` 1.28.1), also declares a console script named `mcp` (`mcp.cli:app`). The two
have the same name, so after install the SDK wins.

Consequences for each way of invoking it:

- `uvx keep-mcp` -> uv errors out directly: "An executable named `keep-mcp` is not provided by package
  `keep-mcp`". Loud failure, easy to spot.
- `uvx --from keep-mcp mcp` -> RUNS, but runs the wrong thing: the MCP SDK's CLI ("MCP development tools",
  commands version/dev/run). It fails SILENTLY, which is the real trap: it reports no error at all.
- `uvx --from keep-mcp python -m server` -> the correct keep-mcp server, via `server/__main__.py`.

Verified with a real MCP stdio handshake (initialize + tools/list, no credentials needed):
the server returns EXACTLY 23 tools, matching the README list exactly, with no hidden tools beyond `tool_meta`.
This matters for security, because a tool not declared in `tool_meta` falls through to the `WRITE_HINTS`
heuristic and could slip past the blocking layer.

A `_args_doc` note sits right in the catalog entry so that later readers do not "tidy it up" back to `uvx keep-mcp`.

### Tool classification and reasons

`mcp_catalog.allowed()` blocks based on `tool_meta`, which is a hard layer independent of the prompt, so
the classification must be declared explicitly rather than relying on the `WRITE_HINTS` heuristic.

Two notable choices:

- `restore_note` is classed **write** while `trash_note` is classed **danger**. This means that at the Draft level, Jarvis 007
  can always restore a note that was trashed by mistake but cannot trash one itself. The asymmetry is deliberate.
- `add_note_collaborator` and `remove_note_collaborator` are classed **danger** because they share notes with
  other people, i.e. leak data outward, which is different in kind from editing content in-house.

`archive_note` is classed write because it is non-destructive (the note remains, merely hidden from the main list).
`delete_list_item` is classed write because deleting a line in a checklist is a normal editing operation.

### About the `validate` block

It uses `list_labels` (no parameters, purely read) so the Test button truly reaches the Keep API, proving the
master token is still alive rather than merely proving the server starts.

It does NOT declare `label_paths` because the response shape of `list_labels` is not known for sure. Per
`mcp_hub.validate_connection`, a missing `label_paths` only leaves the display label empty and does not break the
connection. Guessing `label_paths` wrong would not make Test fail either, but declaring it at random is pointless.

Note: this `validate` block has NOT been verified in practice because it needs a real master token to run.
If `list_labels` returns an error when the account has no labels yet, the Test button will report a false failure and the
`validate` block must be dropped. This must be confirmed at acceptance.

## Change 2: NOTHING needed (this section was once WRONG, kept as a lesson)

The first version of the design had a section "add uv to the Docker image", arguing: the `Dockerfile` only has `node`, `npx`,
`pip`, with neither `uv` nor `pipx`, so `uvx` would die on the VPS, and the 4 existing `uvx` connectors
(`google-sheets`, `google-search-console`, `google-ads`, `tiktok-ads`) were probably broken too.

**That argument was WRONG.** `uv>=0.5` has been in `requirements.txt` since v0.9.0 (commit 856cb19), and
the `Dockerfile` still runs `pip install --no-cache-dir -r requirements.txt`. So the image ALWAYS has `uv`,
and those 4 connectors were never broken for this reason. The extra `pip install uv` line was redundant and was removed
in 0.9.112.

Where it went wrong: it only ran `grep` over the Dockerfile for the word `uv`, found nothing and concluded it was missing, while the
`pip install -r requirements.txt` line was right there and `requirements.txt` was never opened. A guess
from a narrow search, presented as a verified fact.

Lesson: when concluding "X is not in the image", trace EVERY installation path (requirements.txt,
apt, npm, COPY from another stage), not just grep for the name X in the Dockerfile.

The knowledge that `uv` serves the `uvx` connectors now lives in a comment in `requirements.txt`,
where it belongs.

## Acceptance testing

1. `python -c "import json; json.load(open('system/mcp-catalog.json', encoding='utf-8'))"` must be clean.
2. `mcp_catalog.load()` picks up `google-keep`; `public_catalog()` returns all 3 fields.
3. Check the permission classification with `mcp_catalog.allowed()`:
   - `readonly` + `find` passes; `readonly` + `create_note` is blocked.
   - `safe` + `create_note` passes; `safe` + `delete_note` is blocked.
   - `safe` + `restore_note` passes but `safe` + `trash_note` is blocked (checks the deliberate asymmetry).
   - `full` + `add_note_collaborator` passes.
   - `mode: suggest` forces everything to readonly even when the perm is full.
4. Docker: `docker run --rm <image> uvx --version` must run (uv comes from requirements.txt).
5. Manual: connect for real on the Connections page, press Test, confirm `validate` does not report a false failure.
   Then try `find` through chat.

### What has been verified (2026-07-20)

Points 1 to 3 became `server/test_google_keep.py`, 40 checks, run with
`cd server && ../.venv/Scripts/python.exe test_google_keep.py`. There is a canary proving that
`mcp_catalog.allowed` really blocks rather than returning True unconditionally. Re-ran
`test_fb_monitor`, `test_fb_personal`, `test_meta_graph`, `test_meta_pages`, `test_security`,
`test_plugins_host`, `test_skill_caps`, all green.

Also verified by hand outside the test suite:

- `pip install uv` on a clean venv does produce a working `uvx`, so the `uv>=0.5` line in requirements.txt is enough.
- `uvx --from keep-mcp python -m server` starts the right keep-mcp server and speaks the MCP protocol.
- The `initialize` + `tools/list` handshake returns exactly 23 tools, matching `tool_meta`.

### NOT yet verified, to be done at acceptance

- **`uvx` has not been run in a real Docker.** The dev machine has no Docker installed. That `pip install uv`
  yields `uvx` has only been shown on a Windows venv, not on `python:3.12-slim`.
  Low risk because uv has manylinux wheels and the `uv>=0.5` line has been in requirements.txt since v0.9.0
  (so the other uvx connectors have run this path for a long time), but it is still not a verified fact.
- **The `validate` block has not been run for real** because it needs a master token. If the account has no labels and
  `list_labels` returns an error, the Test button will report a false failure and the `validate` block must be dropped.
- **No tool that touches real Keep has been called.** All the verification above needs no credentials, so it has not
  proven that the master token works end to end or that `UNSAFE_MODE` behaves as documented.

## Out of scope

- No dedicated skill or agent for Keep. The MCP tools are enough for Jarvis 007 to use through chat; only if there is a real
  repeated need will it be considered later.
- No two-way sync of Keep with the Second Brain. That is a large, separate job.
- No automating the step of getting the master token. That step must be done by the user because it involves the App Password.
- No touching the 4 `uvx` connectors that were thought broken beyond adding `uv` to the image. Re-verifying them is
  a separate job.

## Sources

- [feuerdev/keep-mcp](https://github.com/feuerdev/keep-mcp)
- [gkeepapi: obtaining a master token](https://gkeepapi.readthedocs.io/en/latest/)
- [simon-weber/gpsoauth](https://github.com/simon-weber/gpsoauth)
