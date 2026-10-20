# Zalo: per-chat policy + chatbot replies

Date: 2026-07-20
Status: design settled, being implemented
Follows: [2026-07-20-zalo-listener-design.md](2026-07-20-zalo-listener-design.md)

> **UPDATE 2026-07-21 - the `chatbot` mode (auto-reply) has been REMOVED.** The owner decided Jarvis 007
> does NOT auto-reply to customers on Zalo: it only READS and REPORTS to Telegram. Every outgoing message is sent at
> the owner's direct request (tool `javis_zalo_send`). The remaining four modes (im-lang, bao-het,
> tu-khoa, nhac-quen) are unchanged; an old rule file with `mode: chatbot` is automatically downgraded to `im-lang` (silent)
> when read. The "chatbot" parts below are of historical value only.
> (Mode names are machine values the code matches on: `im-lang` = silent, `bao-het` = report everything,
> `tu-khoa` = keyword, `nhac-quen` = remind if forgotten.)

## Problem

The current listener is a **global notification filter**: one keyword set, one
quiet-hours window shared by every chat, and every matching message is dumped to Telegram.

What the owner really needs is a **separate policy for each chat**:

- This group: report any message at all.
- That group: only remind when the owner forgets to reply for more than 30 minutes.
- Another group: Jarvis 007 replies by itself like a chatbot, and only reports when it hits something beyond its ability.

Three places where the old structure falls short: the config is global rather than per chat;
the listener remembers nothing so it cannot do time-based rules; and there is no
path for Jarvis 007 to reply.

## Important background: Jarvis 007 has its OWN Zalo account

The owner created a separate Zalo account for Jarvis 007 (not the personal account).
This changes a few things:

- People in the group see exactly one account named Jarvis 007, so the "not knowing they are
  talking to a machine" issue is nearly gone.
- The owner accepts the risk of the bot answering wrongly.
- The bot may only reply in chats that have been enabled, not everywhere on the account.
- **The "30 minutes without a reply" rule becomes feasible**: the owner replies from their own
  personal account, so in the group the owner is a DIFFERENT member, and the owner's messages arrive in full via
  the webhook. The `--no-self` flag no longer gets in the way as in the initial analysis.

What a separate account does NOT solve: the engine is still the owner's engine. If a stranger
can steer it, what they reach is MCP, files, memory - a data-leak risk, different in
kind from the risk of a wrong reply.

## Decisions

| Point | Decision |
|---|---|
| Unit of configuration | One rule file per chat |
| Where stored | `<brain>/Javis/zalo/<slug>.md` (like loop/agent/skill) |
| How rules are set | Say it in words via chat or Telegram, Jarvis 007 writes the file |
| UI | Display ONLY, for review, no input form |
| Bot's knowledge | A per-group script, does not touch brain/POS |

## Five modes

| mode | What it does | Does an engine need to read the content? |
|---|---|---|
| `im-lang` | Only records into the ledger, no report | No |
| `bao-het` | Every message is reported to Telegram | No |
| `tu-khoa` | Reports when a message contains a keyword | No |
| `nhac-quen` | Reports when a customer writes and nobody answers for more than N minutes | No |
| `chatbot` | A sandboxed engine replies by itself, reports when stuck | **Yes** |

The first four modes keep the security barrier of the previous version (content never touches the engine).
Only `chatbot` opens the barrier, so it has its own barrier in the section below.

## Rule file

`<brain>/Javis/zalo/<slug>.md`:

```yaml
---
type: zalo-rule
thread_id: "<chat id>"
thread_name: "Nhóm Kim Khí Hà Lộc"
mode: chatbot            # im-lang | bao-het | tu-khoa | nhac-quen | chatbot
enabled: false           # chatbot is ALWAYS created in the off state
keywords: []             # only used for mode tu-khoa
escalate_after_min: 30   # only used for mode nhac-quen
owner_uid: ""            # the OWNER's Zalo uid in the group, to know whether the owner has replied
max_reply_per_hour: 20   # only used for mode chatbot
updated: 2026-07-20
---
<Script: what the bot knows, how it replies, what to push back to the owner.>
```

(`thread_name: "Nhóm Kim Khí Hà Lộc"` is a sample group name meaning "Kim Khí Hà Lộc group"; the name itself is proper-noun data and is kept as is.)

Placed in the brain for three reasons: consistency with loop/agent/skill (all `.md` produced
by chat), git history so every change can be traced, and it can be edited by hand when needed.

Read from the DEFAULT brain (the listener is a background service, with no notion of an "open brain").

## Setting rules in words

The tool `javis_zalo_rule` (a bundled plugin) is for the engine to call when the owner speaks:

- `op=list` - list the existing rules.
- `op=show` - view the details of one rule.
- `op=set` - create or edit (takes `thread`, `mode`, `script`, and optional fields).
- `op=off` - turn a rule off.

**Identifying the chat**: the `thread` parameter accepts an id or a NAME. Names are matched against the ledger of
chats seen. If more than one result matches, the tool **returns the list and does nothing** -
guessing blindly means attaching the script to the wrong group and the bot replying to another group's customers.

**Chatbot mode is always created with `enabled: false`.** The other four modes only report to Telegram,
so a mistake only bothers the owner; a chatbot sends messages outward that cannot be recalled, so turning it on must
be a separate, deliberate action. This is the only place that adds friction, and it follows the same rule as
loops in CLAUDE.md.

## nhac-quen mode

Needs per-chat state: `{since, from_name, text}` = the customer message waiting
for a reply.

- A message from someone else (not the owner) -> if there is no waiting mark yet, set the mark.
- A message from `owner_uid` -> clear the mark (the owner has replied).
- The bot replies by itself (chatbot mode) -> clear the mark too, because the code knows immediately, no need to wait for the webhook.
- The background scheduler (30s tick, already existing) scans: a mark older than `escalate_after_min` triggers one
  Telegram report and then the mark is cleared, with no repeated reminders.

If `owner_uid` is empty, the mark is never cleared by the owner's messages, so it will remind even when the
owner has replied. The tool must warn clearly when creating a `nhac-quen` rule without an `owner_uid`,
and suggest the list of senders seen in the group to choose from.

## chatbot mode: sandbox

This is the riskiest part, so the rules must be hard.

### Trap discovered: `allowed_tools=[]` does NOT lock the tools

`claude_sdk_engine.py:300` has `if self.allowed_tools:`. An **empty list is falsy**,
so `allowed_tools=[]` falls into the `else` branch: `permission_mode = "bypassPermissions"`
along with loading the machine's settings and existing MCP.

That means the most intuitive way to write a sandbox actually **throws every permission wide open**, at exactly the moment
content authored by strangers enters the engine.

You must pass a NON-EMPTY whitelist containing a tool name that does not exist
(`__zalo_bot_khong_co_tool__`). Then `allowed_tools` is truthy -> the gate is on -> every
real tool falls into `_permission_gate` -> is genuinely denied every time. A test pins this down.

### Other barriers

- `mcp_config` points to an empty MCP file + `mcp_strict = True` -> no connector is visible.
- System prompt = the group's script + an anti-injection guard. It does **not** include memory,
  the brain, or the owner's CLAUDE.md.
- Customer content is fenced between two labeled rules, just as is done for Telegram.
- **The model has no tools so it cannot choose a recipient.** It only produces TEXT; the Jarvis 007
  code decides where to send it, and always sends it to the very chat that produced the message. Even if fully
  tricked it cannot message anyone else. This is the difference between a real barrier and a
  note in the prompt.
- Output starting with `[CHUYEN CHU]` ("hand over to owner") -> not sent to the customer, pushed to the owner on Telegram.
- A `max_reply_per_hour` ceiling per group. Past it, stay silent and tell the owner once.
- `max_wall_s = 60`: this is a chat reply, anything slower is pointless.
- Every message the bot sends itself is logged so the owner can review it.

### Which path messages go out on

The `listen` sidecar cannot send messages. Sending goes through the `zalo` MCP connector (tool
`zalo_send_message`). This is where it TOUCHES the one-socket-per-account collision noted
in the previous spec. Not yet verified; if it really collides, the fallback is to pause the listener,
send, and turn it back on. No guessing in advance, let it surface and then handle it.

## Overall safety

- The bot only replies in a chat that has a rule with `mode: chatbot` **and** `enabled: true`.
  Checked in code before calling the engine, not by a note in the prompt.
- The other four modes do not call the engine.
- Messages from the Jarvis 007 account itself trigger nothing (so the bot does not talk to itself).
- The XSS guard in the UI stays: group names and sender names are still wrapped in `esc()`.

## Tests

- Reading/writing the rule file; an ambiguous group name match returns a list rather than guessing.
- Each mode: exactly which messages report and which do not.
- `nhac-quen`: set the mark, clear it when the owner replies, fire exactly once when overdue.
- Chatbot: a NON-EMPTY tool whitelist (hard-pins the `[]` trap), output `[CHUYEN CHU]`
  is not sent to the customer, the per-hour message ceiling, and the bot does not run when the rule is off.
- No engine call in the first four modes.

## Out of scope

The bot reading the Wiki or POS figures (decided no, only a per-group script). Approving
each reply via Telegram before sending (the owner chose to send directly). The official OA route.
