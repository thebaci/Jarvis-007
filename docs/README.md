# 📚 Jarvis 007 documentation

***Tiếng Việt** · [English](en/README.md)*

Detailed guides for every feature of Jarvis 007. Each page is a standalone how-to: where to open it, what to click, how to use it.

> Just starting? Read [Installation in the README](i18n/vi/README.md#-cài-đặt) first (the Vietnamese README; its installation section is headed "Cài đặt"), then go to [01 - Getting started and first setup](01-bat-dau-thiet-lap.md).

The dashboard's navigation bar groups **19 pages** into **7 groups**: Assistant · Brain · Code · Capabilities · Work · Connections · System. The table of contents below follows the same logic.

## Table of contents

### Getting started
- [01 - Getting started and first setup](01-bat-dau-thiet-lap.md) - creating the admin, signing the brain in, choosing an engine and model, the Settings page.

### Everyday use (the Assistant and Brain groups)
- [02 - Chat and voice](02-tro-chuyen-va-giong-noi.md) - chatting, hands-free speech, slash commands, quick-reply buttons, sending files, generating images.
- [03 - Knowledge graph](03-do-thi-tri-thuc.md) - wikilinks, category colors, the timelapse and the graph switches.
- [04 - Sessions](04-phien-hoi-thoai.md) - saving, reopening, renaming, deleting, full-text search, compacting a long session.
- [05 - File manager](05-quan-ly-tep-tin.md) - browsing the brain, finding files by name or content, editing .md/.txt directly, uploading and downloading.

### Code (the Code group)
- [27 - The Code group: Terminal](27-tab-code-terminal.md) - a real command line on the machine running Jarvis 007, opened right in the dashboard, no SSH needed.

### Extending capabilities (the Capabilities group)
- [06 - Skills](06-skills.md) - grouping, searching, turning on and off, adding, editing and deleting, importing and exporting skills.
- [07 - Agents & Workflows](07-agents-va-workflows.md) - creating specialist assistants plus automated multi-step chains.
- [20 - Plugins](20-plugins.md) - adding native tools and hooks for every engine with one Python folder.
- [25 - Chatbot (a dedicated bot)](25-chatbot.md) - putting an Agent in front of customers through a dedicated Telegram or Zalo bot, with its own brain and a handover to a human when it is stuck.
- [28 - Customer conversations (Inbox)](28-hoi-thoai-khach.md) - every chat customers have with your bots and personal Zalo in one place, with takeover when a human is needed.
- [29 - Slack and WhatsApp](29-slack-whatsapp.md) - chat with Jarvis 007 and run customer bots on Slack (no domain needed) and WhatsApp (Meta's official API).
- [30 - Discord and Lark/Feishu](30-discord-lark.md) - chat with Jarvis 007 from Discord and Lark/Feishu on the Admin channels page, no domain needed.
- [31 - Messenger](31-messenger.md) - a customer bot that answers your Facebook Page inbox (Meta's official API, needs an HTTPS domain).

### Background work (the Work and Brain groups)
- [08 - Recurring jobs and reminders](08-viec-dinh-ky.md) - several background loops plus reminders on a clock or a cron schedule.
- [21 - Work (Kanban)](21-viec-kanban.md) - handing over a goal in words, with the AI specifying and running the background task.
- [22 - Self-learning](22-tu-hoc.md) - Jarvis 007 extracting memories, distilling Wiki pages and skills after each conversation, undoably.

### Connections and channels (the Connections group)
- [09 - Connections and business data](09-mcp-va-so-lieu.md) - the multi-account store of external services, permissions, reporting real figures.
- [10 - Models and engines](10-models-va-engine.md) - switching the brain between Claude Code, ChatGPT/Codex, Antigravity CLI, OpenRouter, OpenAI, Gemini, Anthropic, Groq and Ollama without losing capability; thinking levels, the background work model.
- [11 - The Telegram channel](11-telegram.md) - asking Jarvis 007 from a phone, sending and receiving files.
- [26 - The Zalo Bot channel](26-kenh-zalo-bot.md) - asking Jarvis 007 on Zalo through the official API, paired with one click.
- [12 - Zalo Agent MCP](12-zalo.md) - signing in by QR, reading and searching history, sending messages through the standard MCP.
- [24 - The Jarvis 007 CLI (terminal)](24-cli-terminal.md) - typing `javis "..."` from a terminal, API tokens, composing in scripts.

### The brain and data
- [13 - Second Brain: memory, Wiki, INGEST](13-second-brain-bo-nho-wiki.md) - multiple brains, living memory, digesting knowledge.
- [18 - Backing the brain up to GitHub](18-sao-luu-github.md) - two-way sync to a private repo, recovering after losing a machine or VPS.
- [19 - Tasks and Dataview in notes](19-task-va-dataview.md) - Obsidian-style self-saving checkboxes, ```dataview blocks that really run.

### Accounts, branding, configuration (the System group)
- [14 - Security and accounts](14-bao-mat-tai-khoan.md) - forced login, passwords, rate limiting, secret-key encryption.
- [15 - Branding and custom domains](15-thuong-hieu-ten-mien.md) - changing the logo and avatar, pointing a domain and turning on HTTPS.
- [16 - .env configuration](16-cau-hinh-env.md) - a reference for every environment variable.
- [23 - Usage: tokens and cost](23-muc-dung-token.md) - Jarvis 007 measuring input and output tokens by day, by provider and by source.

### When something goes wrong
- [17 - Troubleshooting and FAQ](17-khac-phuc-su-co.md) - common errors and how to handle them.

---

## English edition

**All the documentation is available in English.** Every page has a language switch line right under the title;
click it to go to the matching page. The English table of contents is at [docs/en/](en/README.md); in addition, the repo
root has [README.md](../README.md), [QUICKSTART.en.md](../QUICKSTART.en.md),
[DEPLOY.en.md](../DEPLOY.en.md) and [CONTRIBUTING.md](../CONTRIBUTING.md) (Vietnamese edition: [i18n/vi/CONTRIBUTING.md](i18n/vi/CONTRIBUTING.md)).

The Vietnamese edition is the original of the documentation: to change content, change the Vietnamese side first and then update
the matching English page, so the two never say different things. README is the exception, the other way round: since 0.66.0
the `README.md` at the repo root is the English edition, and the Vietnamese edition lives at
[i18n/vi/README.md](i18n/vi/README.md). To add a language to Jarvis 007 itself (not the
documentation), follow the [language playbook](dev/them-mot-ngon-ngu.md).

---

> Documentation conventions: practical and concise (the Vietnamese pages are written in Vietnamese). Never use the em dash character (U+2014), always replace it with the hyphen "-". See [CLAUDE.md](../CLAUDE.md) for the system conventions aimed at AI agents.
