# Jarvis 007

Jarvis 007 is a personal, English-first fork of [Javis OS](https://github.com/blogminhquy/javis-os) by blogminhquy, used under the MIT License (see `LICENSE`, which keeps the original copyright notice).

"Jarvis 007" is a working name for a private build. Rename before any public launch (the JARVIS and 007 names belong to other trademark owners).

## How this fork differs from upstream

To rename it, set `"branding": {"name": "Your Name"}` in `server/settings.json` and restart. Text written straight into the code instead of the dictionary still says Javis.

Changes are kept small and marked with `Jarvis 007` comments so upstream merges stay easy.

| Area | Upstream default | Jarvis 007 default |
| - | - | - |
| Reminders, webhooks, loops | `full` (acts outside for real) | `auto` (drafts and file writes only; `full` is opt-in per job) |
| Login | Off when bound to localhost | Required everywhere (`JAVIS_REQUIRE_LOGIN=0` restores upstream) |
| Interface language | Guessed from browser, `vi` for old installs | `en` |
| Timezone / currency | Asia/Ho_Chi_Minh, VND | Asia/Bangkok, USD (same UTC+7 offset) |
| System prompt (`CLAUDE.md`) | Background work acts on its own | Background work writes drafts unless the user opts a job into `full` |
| Product name | Javis OS | Jarvis 007 (settings `branding.name`; empty = build default) |
| Zalo, Botcake connectors and the Zalo admin channel | Shown | Hidden unless settings `regional.vn_channels` is `true` (an existing connection always stays visible) |
| Reminder endpoints behind a same-machine tunnel | Exempt from login for any 127.0.0.1 caller | Exempt only for direct local calls (no proxy headers) |

Existing jobs that already store an explicit level keep it. A job saved without a level now runs at `auto`.

## Keeping up with upstream

```bash
git remote add upstream https://github.com/blogminhquy/javis-os   # once
git fetch upstream
git merge upstream/main
python tests/run.py --py
```

Resolve any conflict in favour of the upstream change, then re-apply the small `Jarvis 007` edit on top.

## Roadmap

1. Safe defaults and English locale (this pass).
2. Done: product name through one setting (`branding.name`), applied to dictionary text, page title, sidebar and home-screen name.
3. Done: Vietnam-only connectors and the Zalo admin channel hidden by default. The Zalo section of `CLAUDE.md` stays, because upstream tests depend on it.
4. Brain visualization: local perspective renderer with slow rotation, drag, pinch/wheel/button zoom, real selectable memory nodes, category filters and timelapse. Respects reduced motion and pauses when hidden.
5. Rebuild strict model routing separately.
6. Guided English setup for the Google connectors (Gmail drafts, Calendar, Drive).
