# Jarvis 007

Jarvis 007 is a personal, English-first fork of [Javis OS](https://github.com/blogminhquy/javis-os) by blogminhquy, used under the MIT License (see `LICENSE`, which keeps the original copyright notice).

"Jarvis 007" is a working name for a private build. Rename before any public launch (the JARVIS and 007 names belong to other trademark owners).

## How this fork differs from upstream

Changes are kept small and marked with `Jarvis 007` comments so upstream merges stay easy.

| Area | Upstream default | Jarvis 007 default |
| - | - | - |
| Reminders, webhooks, loops | `full` (acts outside for real) | `auto` (drafts and file writes only; `full` is opt-in per job) |
| Login | Off when bound to localhost | Required everywhere (`JAVIS_REQUIRE_LOGIN=0` restores upstream) |
| Interface language | Guessed from browser, `vi` for old installs | `en` |
| Timezone / currency | Asia/Ho_Chi_Minh, VND | Asia/Bangkok, USD (same UTC+7 offset) |
| System prompt (`CLAUDE.md`) | Background work acts on its own | Background work writes drafts unless the user opts a job into `full` |

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
2. Rename the visible product name through one setting instead of editing hundreds of strings.
3. Hide the Vietnam-only channels (Zalo, Pancake, Webcake) by default.
4. Rebuild the 3D brain graph and strict model routing that were added locally.
5. Guided English setup for the Google connectors (Gmail drafts, Calendar, Drive).
