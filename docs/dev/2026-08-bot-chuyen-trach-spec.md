# Proposal: Dedicated bots - turning an Agent into a chatbot that answers customers

The repo owner raised this on 2026-08-04, replacing the "Let an Agent attach an AI chatbot" idea
left open in `2026-08-backlog-spec.md` section 2. The intent is now fully clear, and it does not
match any of the three interpretations I guessed at the time.

Status: **all four phases are done**. Phase 1 shipped in 0.19.0; phases 2, 3 and 4 shipped in
0.20.0 (along with one hole in 0.19.0 that had to be patched, recorded in section 7). User guide:
`docs/25-chatbot.md`.

## 0. Settled (2026-08-04)

The repo owner settled three things, and all three made the design tighter rather than bigger:

1. **One dedicated brain per bot.** Physical isolation, not a barrier made of code.
2. **One dedicated token per bot.** Each one has its own name and avatar in the customer group.
3. **A Chatbot page in the dashboard** to manage every running bot. Creating a bot means
   **choosing an existing Agent, or creating a new Agent right there**.

Point 3 changes the order of the roadmap: the management page is no longer the last job but the
**entry point**. Without it, bots would have to be created by hand-editing a `.md` file, and then
once the page was built that path would be thrown away. See section 7, reordered.

The first two turned out to be almost free, because Jarvis 007 already has:

- **Multiple brains have existed for a long time**: `GET /brains`, `POST /brains/new` (seeds the
  standard structure by itself), `POST /brains/delete` (`server/main.py:3270`). Creating a brain
  for a bot means calling exactly that API, not writing a second store.
- **Adding a page to the rail** means adding an entry to `RAIL_ITEMS` and placing it in a group of
  `RAIL_GROUPS` (`dashboard/console.js:78`). Proposed placement is the **Capabilities** group,
  right next to Agents, because the bot creation flow starts from an Agent. The existing
  **Admin channels** page is the OWNER's channel, a different kind, so it is not merged.

## 1. The wish, restated to be sure

> Jarvis 007 has many Agents, each with its own Skills and Workflows attached. Make use of them to
> create chatbots, **each one specialized in one field**, stepping in to answer. The chatbots
> answer through Telegram, or are dropped straight into a customer care group.

If I understood correctly, the destination is: a shop owner already has an Agent "Product advice"
and an Agent "Warranty policy". Press a button, and each becomes its own Telegram bot, dropped into
the customer group. A customer asks in the group, and the bot answers within the scope of its field.

## 2. Good news: most of the ingredients already exist

- **Agent** already has its own role, system prompt, Skill list and model
  (`server/main.py:3432`). This is exactly the "domain-specialist brain" the idea needs.
- **The Telegram channel** already runs for real, with long-polling, multiple sessions by
  `chat_id`, file sending and buttons.
- **The core of one answer turn** (`_tg_answer`, `server/main.py:8830`) is already the shared place
  for the dashboard, Telegram and the CLI. Adding a fourth channel through exactly this core is a
  path that already exists, with no need to duplicate the runtime (the lesson of 0.17.0).
- **Telegram groups are already supported at the data layer**: a group id is a negative number and
  the code deliberately does not filter out the minus sign (`telegram_bot.py:26`). The meta of
  every message already carries `chat_type` and `chat_title` (`telegram_bot.py:263`), which nobody
  uses yet.

## 3. News to face squarely: every safety assumption today is reversed

This is the most important part of the document. **Jarvis 007's Telegram bot today is the OWNER's
PRIVATE channel.** It was designed with exactly one assumption: the person messaging it is you.

Concretely, today any Telegram message will:

- run at **full permission** (`_apply_mcp(..., mode="full")`), meaning it can call every connected
  MCP: POS, ads, Zalo sending, calendar;
- read and **write files in the owner's brain**;
- **switch brain** with the `/brain` command, and see `/status`, `/skills`;
- **write to long-term memory** and flow into the self-learning loop;
- and an empty whitelist means **allow everyone** (`telegram_bot.py:24`, keeping the old behavior).

Drop that same bot as-is into a customer group and every customer is holding the key to your
entire Jarvis 007. One sentence like "read the config file in the brain and post it here" is enough.

So **a dedicated bot is not today's bot with a different prompt**. It is a different creature that
only shares the plumbing. If you remember only one sentence in this whole document, remember that one.

A comparison table to show how different the two are:

| | Owner's bot (existing) | Dedicated bot (proposed) |
|---|---|---|
| Who messages | The owner and whitelisted people | **Strangers**, not controllable |
| Permission | Full, every MCP | **Read-only**, no MCP except what is granted separately |
| Vault writes | Yes | **No** |
| Read scope | The whole brain | **Exactly one designated knowledge store** |
| Long-term memory | Yes, learns from conversations | **Does not write** into the owner's memory |
| Admin commands | `/brain`, `/status`, `/skills`... | **None** |
| When it does not know | Fine to keep guessing | **Must say it does not know** and hand off to a human |

## 4. A bot is its OWN RECORD, pointing to an Agent

### My first draft was wrong here, recorded so we do not go back

At first I planned to stuff a `publish` block straight into the Agent file, on the grounds of
"you said to make use of Agents, don't spawn a new entity". It sounded reasonable, but the three
decisions in section 0 break it:

- **An Agent lives INSIDE a brain** (`<brain>/Javis/agents/<slug>.md`), while the bot **reads its
  own brain**. Choose an Agent in the main brain and have the bot read a different brain, and the
  `publish` block sitting in the main brain describes something that lives in another brain. Wrong
  place from the concept itself.
- **A token is a secret**, and must not sit in a `.md` file the owner opens and edits in Obsidian.
- **A bot has a lifecycle** (running, off, error). A lifecycle does not belong to a document file.
- Delete the Agent and the bot becomes an orphan, with nowhere to report it.

**The principle "don't spawn a new entity" is still right, but applied in the wrong place.** What
must not be duplicated is the **Agent** concept (role, prompt, skills, model) - and it is not
duplicated: the bot only **points to** an Agent rather than copying it. The bot itself really is
something new: it has a token, a brain, a lifecycle, and groups.

### Where to store it

Follow exactly the mould `mcp_store` uses for MCP connections - same problem, same solution:

```
<JAVIS_STATE_DIR>/chatbots.json      ← the list of bots (NO tokens)
<JAVIS_STATE_DIR>/secrets            ← tokens, encrypted, via secrets_store
```

One bot record:

```json
{
  "id": "bot_a1b2c3",
  "name": "Product advice",
  "icon": "message-circle",
  "enabled": false,

  "agent": { "brain": "brain", "slug": "tu-van-san-pham" },
  "brain": "bot-tu-van-san-pham",

  "channel": "telegram",
  "token_ref": "bot_a1b2c3.token",
  "bot_username": "TuVanSanPham_bot",

  "groups": ["-1001234567890"],
  "reply_when": "mention",
  "handoff_to": "123456789",
  "rate_limit": 20
}
```

Three things worth noting in this shape:

1. **`agent` is a two-part pointer** (brain + slug), not a copy. Edit the Agent on the Agents page
   and the bot changes with it right away, with no editing in two places.
2. **`brain` is the brain the bot READS**, different from the brain holding the Agent. This is
   exactly where the first draft broke.
3. **No token**, only `token_ref`. The same way the MCP store keeps the keys of its connections.

Deleting an Agent while a bot still points to it **warns and blocks**, just as deleting a Project
must not delete conversations: if the user cannot guess the consequence, do not make them carry it.

### The five pieces of a bot

1. **Brain** = the Agent pointed to (role + prompt + skills). Already exists.
2. **Knowledge store** = the bot's own brain. The API to create and seed it already exists.
3. **Channel** = a dedicated Telegram bot. Needs support for running several pollers at once.
4. **Permission level** = hard-locked to read-only. The mechanism exists (`min_mode`,
   `effective_perm`), just wired to the right place.
5. **Escape hatch** = hand off to a human when stuck. Does not exist yet, has to be written.

## 5. Three big decisions, with recommendations

### 5.1 One dedicated token per bot (SETTLED)

- **One dedicated token per bot** (the proposal's pick): each has its own name, avatar and
  `@handle` created by you at BotFather. Dropped into a customer group it is "Product Assistant"
  rather than "Mr. Quy's Jarvis 007". This is a difference in brand image, not a technical matter.
  The price to pay: several pollers must run at once, and currently `_TG_BOT` is a single global
  variable (`server/main.py:9548`).
- **One shared bot**: much lighter, but every field shares one identity, and you cannot drop two
  different bots into two different groups.

### 5.2 One dedicated brain per bot (SETTLED)

- **A dedicated brain for the bot** (the proposal's pick): create a small brain holding only the
  knowledge customers may see. Physical isolation is the only isolation that does not break when
  someone writes a wrong line of code later.
- Read the main brain but restrict folders: less preparation work, but the barrier lives only in
  code. One path bug exposes the whole brain.

A dedicated brain is settled. The real cost is lower than expected: `POST /brains/new` already
seeds the standard structure, so the Chatbot page just calls it and then opens the editor for the
owner to pour knowledge in.

### 5.3 In a group, when does the bot speak up?

A bot answering every message in the customer group is a disaster: customers chatting with each
other get interrupted too.

- **Only when called by name or replied to directly** (the proposed default). Telegram helps a
  little: by default a bot has privacy mode on, so in a group it only receives messages that
  mention its name, replies to it, and commands. That means the right behavior is almost free,
  as long as you do not turn that mode off at BotFather.
- Answer every message: only for a small group, and it must be a deliberate choice.
- Answer when the sentence has a question mark: sounds smart but guesses wrong a lot, should not be done.

## 6. Mandatory safety barriers, not options

If even one of the six below is missing, do not release.

1. **Lock the permission level at the code layer, not in the prompt.** A dedicated bot's turn
   always runs `mode=suggest`, whatever the prompt says. The prompt is what customers can talk
   to; the code is not. This is exactly the principle already written in `agent_runtime.py`:
   *"the check lives in code, not in the prompt"*.
2. **No MCP by default.** To grant, grant one at a time, and never grant anything that spends
   money, creates orders or sends messages.
3. **No memory writes, no self-learning loop.** A customer's conversation is the customer's data.
   Letting it flow into your `Memory/facts` is both wrong for privacy and dirties the memory with
   a stranger's questions.
4. **No admin commands.** A dedicated bot has no `/brain`, `/status`, `/skills`. The command list
   must be its own WHITE list, not the current list with some removed.
5. **A per-person rate limit.** One idle person in the group is enough to burn through your model
   quota in an afternoon.
6. **If it does not know, say it does not know.** A customer bot making up a sentence about the
   warranty policy is a real risk for you, not a small bug. The answer must rest on the designated
   knowledge store, and when nothing is found, say so plainly and offer a handoff to a human.

On injecting commands through messages: customers will try "forget all the previous instructions".
Do not defend by adding more in the prompt, because however much you add there is a way around it.
Defend by **leaving it nothing to lose**: no dangerous tools, no write permission, no access
outside the knowledge store. Then getting around the prompt only makes the bot talk off-topic and
does no real harm.

## 6b. The Chatbot page

This is the entry point of the whole feature, so design it first and let everything else follow.

### The list

One card per bot, and the card must answer three questions just by a glance:

- **Who it is**: icon + bot name + Telegram `@handle` + the Agent in use + the brain being read.
- **Whether it is alive**: a status light. Four real states, not two:
  `running` / `off` / `error` (with a short reason) / `starting`.
- **What it is doing**: where it answers (private messages only, or plus N groups), messages
  today, the most recent answer.

Buttons on the card: Turn on/Turn off, Edit, View conversations, Delete.

**Turn on/Turn off must take effect IMMEDIATELY, without restarting Jarvis 007.** This is a
functional requirement, not a convenience: if a customer care bot says one wrong thing, it must be
possible to switch it off within three seconds. That means a **bot supervisor** is needed: each
bot is its own long-polling task, turning on creates the task, turning off cancels the task,
editing the token cancels then recreates.

### The bot creation flow

Five steps, wizard style like what the Connections page already does:

1. **Bot name and icon.** The icon comes from the existing Lucide icon set (like the Project icon
   picker in 0.18.1, reusing `Icons.names()`).
2. **Brain** - choose one of two:
   - **Choose an existing Agent**: the list of Agents in the current brain, with their role and
     assigned skills.
   - **Create a new Agent right here**: a shortened form (name, role, prompt, pick skills, model),
     written to `Javis/agents/<slug>.md` through the existing `POST /agents`. **Do not write a
     second agent creation path** - this form is just a shortcut to the same endpoint.
3. **Dedicated brain.** By default it proposes creating a new brain named `bot-<slug>` via
   `POST /brains/new` (which already seeds the standard structure). It allows choosing an existing
   brain if the owner wants two bots to share one. After creation, open the editor straight away to
   pour knowledge in, with a reminder: **the bot only knows what sits in this brain**.
4. **Telegram token.** Paste the token from BotFather, with a **Check** button: it calls `getMe`
   and shows the bot name and `@handle` so the owner knows which bot was just pasted. The token is
   stored in the encrypted secret store (`secrets_store`), **never written to a `.md` file** and
   never returned back to the UI.
5. **Review, then create.** The bot is always created in the **OFF** state. The owner turns it on
   after trying a private message to it.

Adding groups comes later, on the Edit screen, because getting a group id means inviting the bot
into the group first. With a tip right on the screen: invite the bot into the group, then type
`/id`, and the bot returns the group id to paste here.

### Three traps to handle from the very start

1. **A duplicate token = Telegram returns 409 and both bots die together.** One token may have only
   one long-polling process. So block it at the storage layer: do not let two bots share a token,
   and do not allow reusing the owner's main bot token. Check by comparing `getMe` rather than
   comparing token strings (the same bot can still be pasted twice with different whitespace).
2. **Editing the token while the bot is running.** The old task must be cancelled BEFORE the new
   one is created, otherwise at some moment two pollers are alive and you fall into trap 1.
3. **A bot dying silently.** The token revoked at BotFather, the network dropping, Telegram
   changing an error. The poller must record the last error and push it up to the card, because
   "the bot is not answering customers" is something the owner only discovers when a customer
   complains. This is exactly the kind of silent failure this repo has patched twice in a month.

### Viewing customer conversations

Reuse exactly the existing conversation store: the `channel` column already exists in `sessions`,
set `channel = "bot:<slug>"`. That means customer conversations automatically get full-text
search, pagination and pinning - no second store written. And because `list_sessions` filters by
brain, a bot's conversations sit in its own brain so **they do not mix into the owner's History**.

## 7. Four-phase roadmap

Reordered after settling the Chatbot page as the entry point. The principle stays: when each phase
is done there is **something really usable**, not that you see nothing until everything is done.

**Phase 1 - Create and run one bot, private messages only.** DONE, 0.19.0.
Bot store + a supervisor for multiple pollers (removing `_TG_BOT` from its single global variable
form) + a Chatbot page good enough to use: the list, the five-step creator, on/off without a
restart. The bot's turn goes through `_tg_answer` with a hard-locked read-only level, no MCP, no
admin commands.
*Done means*: create a bot on the dashboard, message it privately, it answers in the Agent's role
and cannot touch anything outside its own brain.

**Phase 2 - Grounded answers.** DONE, 0.20.0 (`server/chatbot_grounding.py`).
Limit the read scope inside the bot's brain. Require answers to rest on documents, and when
nothing is found say it does not know instead of guessing.
*Done means*: the bot answers from your documents rather than from the model's general memory.

Three things learned while really building it, worth recording because they cannot be guessed on paper:

- **Limiting the read scope alone is not enough.** The bot already has a read tool pointing at its
  own brain from phase 1, but having a read tool is not the same as reading: if the model answers
  straight from general memory, the sentence is just as fluent and the owner cannot tell from the
  outside. So the documents must be looked up BEFORE and stuffed into the prompt in advance, not
  left for the model to decide.
- **The threshold for "counts as found" must be measured by how much of the question is COVERED,
  not by an absolute score.** "Does the shop hire Rust programmers" hits exactly the word "hàng"
  (Vietnamese for "goods", the second half of the word for delivery) in the Giao hàng ("Delivery")
  section, and since "hàng" is rare its IDF is high, so the score passed the threshold. Added a
  rule: a sentence of three or more meaningful words must hit at least two of them.
- **Stop words must be written specifically for Vietnamese WITHOUT diacritics.** "bán" (sell) and
  "bạn" (you) both come out as "ban"; dropping "ban" out of habit loses the most meaningful word
  for a sales bot.

**Phase 3 - Into groups.** DONE, 0.20.0.
Use the existing `chat_type`. Answer only when called by name or replied to. The `/id` command
gets the group id. Hand off to a human. Per-person rate limit.
*Done means*: it can be dropped into a customer group and used for real.

**A hole in 0.19.0 found when reviewing this phase, recorded so it is not repeated:** the speaking
rule reads two flags `mentioned`/`reply_to_bot`, but `TelegramBot._build_meta` never attached
them. The condition was always false, so the bot stayed SILENT in EVERY group. Version 0.19.0 even
had a test asserting exactly that behavior, and the test stayed green - because it checked the
CONTRACT of the function `_nen_tra_loi` (given these flags, what comes out) rather than checking
who attaches the flags. The lesson: a rule that reads data attached by SOMEWHERE ELSE must have at
least one test going from raw input (here, Telegram's update JSON) to the final decision, because
piece-by-piece tests all being green still leave a gap exactly at the joint.

**Phase 4 - Measurement.** DONE, 0.20.0 (`server/chatbot_log.py`).
A log of customer conversations on the bot card, and statistics on **questions the bot could not
answer**. The latter has real business value: it points exactly at where your documents are missing something.

Only after building it did we see that "stumped" comes in two kinds, and the second is the one
worth watching. Finding no document at all is the easy-to-see kind. Finding a document and still
having to say there is no information is the subtle kind - the document EXISTS but LACKS what the
customer needs, and that is usually the place most worth fixing.

## 8. What I advise NOT doing

- **Do not let a dedicated bot run Workflows in the first phase.** A Workflow runs many steps and
  costs time and tokens; a customer asking in a group needs an answer within seconds. Skills yes,
  Workflows after it has run stably.
- **Do not reuse the `chat_id` whitelist as the permission mechanism.** The whitelist is a list of
  people allowed to talk, not a list of people allowed to do things. They are two different
  things, and merging them leads to a mix-up one day.
- **Do not let the bot proactively message customers on its own.** Answering when asked is fine,
  messaging first on its own touches both Jarvis 007's safety barrier and Telegram's anti-spam rules.
- **Do not do Zalo before Telegram.** A personal Zalo goes through an unofficial library and the
  account can be locked; putting a Zalo account to work as a customer care bot is betting on
  something uncontrollable. Telegram has an official bot API, so once it is stable, then consider Zalo OA.

### Update 2026-08-05: the "hard-locked to read-only" item is no longer right

Section 4 (piece number 4), section 6 (barriers number 1 and 2) and the table in section 3 were
all written on the assumption that **the bot is always read-only**. The repo owner dropped that
assumption: *"I still want to be able to do many tasks, but you add a notice so I understand the
risk of using it."* See section 10.

The text of those other sections is kept as it was instead of being rewritten, because the
reasoning in them is still right for the default level - and reading why the default must be
read-only is how you understand the cost of raising the level.

## 9. Still needs you to settle

The first two questions are already answered (own brain, own token, with a management page). Two remain:

1. **How many bots for the first run?** I advise **one, one narrow field, one group**. Running for
   real for a week will reveal more than continuing to discuss on paper, and phase 1 is already
   enough to try.
2. **What does the bot do when a customer asks outside its scope?** Stay silent, or say "I'll
   hand you over to a staff member"? The latter needs a real person on duty, so it depends on
   whether you have people. If not yet, the default should be to say plainly "I don't have
   information on this yet" and stop, rather than guess.

## 10. Opening the scope (2026-08-05): three permission levels

The repo owner: *"in the bot creation feature it is read-only now, I want to add the ability to
write and full power. Because basically I still want to be able to do many tasks, but you add a
notice so I understand the risk of using it."* Shipped in 0.24.0.

### Where the real problem lies

It is not "how to grant tools to the bot" - granting tools is easy. The problem is **granting
tools without losing the two barriers that already exist**, because those two barriers are exactly
why 0.21.0 exists:

1. **Brain isolation.** The bot only sees its own brain.
2. **No machine commands.** No Bash, no web, no sub-agents.

The easiest path - opening the CLI to the bot and then limiting it with `allowed_tools` as loops
do - **loses both at once**. Claude Code's `Read` accepts an ABSOLUTE path, so an allowlist with
`Read` lets the bot read every brain and even `/etc/passwd`. Exactly the hole 0.21.0 had to patch,
and it patched it by dropping the tool altogether.

### The solution: tools come ONLY from the hub, on all eight brains

The bot never opens the CLI. At the raised levels it takes the detour of calling API-style tools
(`*_chat_with_mcp`) with tools taken from
`mcp_hub.discover_all(muc_quyen, vault_root=<the bot's brain>)`. Three consequences, and all three
are consequences of the ARCHITECTURE rather than a barrier that must be watched:

- File tools go through `_safe_path(vault_root)` → brain isolation stays intact **even at the full level**.
- The hub has no Bash/WebFetch/WebSearch/Task → barrier number 2 stays intact.
- `muc_quyen` becomes the hub's `mode` → `mcp_catalog.allowed()` blocks the dangerous group at the
  `auto` level right at the call site, independent of the prompt.

The two subscription plans are not left behind (the promise "switching brains does not change
capability"): ChatGPT goes through `responses_with_mcp`, Claude Code goes through
`anthropic_chat_with_mcp` with `oauth_token` - a parameter newly added in this release, mirroring
exactly the header pair that `anthropic_stream` already uses.

### Why the two paths are fully separate

`_bot_tra_loi` (no tools) and `_bot_tra_loi_co_tool` (with tools) are two separate functions,
sharing a few small pieces (history, stream reading, pinning the measuring path). This is on purpose:

- The no-tool path must be **visibly verifiable by eye** as having no tools, and there is a test
  that cuts exactly that function body out to check it (`test_chatbot_cach_ly.py` section B2).
  Stuffing both into one function with one `if` means that canary can no longer be written.
- The Read-only level is the default, meaning the path of almost every bot. It must not be touched
  when adding features for the other two levels.

### The easiest places to break, recorded so they are not repeated

- **Branching must fail closed.** `if _muc in MUC_NANG` and not `if _muc != "suggest"`. With the
  latter, a typo in `chatbots.json`, or an old record missing a key, is enough to hand tools to a
  bot chatting with strangers.
- **An unfamiliar value on EDIT keeps the old level**, it does not fall to the default. Falling to
  the default is a silent downgrade of permission: the owner thinks the bot still works, while it
  refuses every tool and nobody knows.
- **The confirmation barrier must sit in the STORE, not only in the route.** The route is one of
  many entrances (the UI, a chat that creates a bot by itself, the owner's script). Put it in the
  store and every path goes through it.
- **Only block when RAISING.** Demanding confirmation when lowering the level puts up a barrier
  exactly when the owner is putting out an incident.
- **The warning is issued by the server, the UI does not copy it.** Once copied, one day the server
  tightens a barrier while the warning box still promises the old thing, and the owner clicks agree
  based on a sentence that is already wrong.

### What code CANNOT solve, and must be said plainly to the owner

At the `full` level, the person controlling the tools is **the person messaging the bot**. The
remaining barrier is only the Agent file the owner wrote, and words can be bypassed - this is
exactly what section 6 warned about ("do not defend against command injection by adding more in
the prompt"), the only difference being that now the bot HAS something to lose.

So the "risk notice" the repo owner asked for is not a side feature, it is **the other half of the
solution**: code blocks what can be blocked, and the owner must know the rest before clicking. That
is why the warning lists what can be LOST (the kinds of operation, not undoable, who controls it)
rather than a "be careful" sentence - and it appears three times: when choosing the level, when
saving the `full` level, and when turning the bot on.

One more point to hold, because the first version was wrong exactly here: the warning describes
**KINDS OF OPERATION** (sending out, paying, booking/cancelling, deleting, publishing), it does NOT
name the work of one industry. The first version wrote "creating orders, spending ad money,
posting" - familiar to a seller, meaningless to a Jarvis 007 user who manages projects, looks after
health or teaches. Worse: that person reads it and thinks the warning does not apply to them, then
turns on Full power because they think they have nothing to lose. The repo owner rejected it
(2026-08-05): "it's too personalized to me". There is a canary in both the Python test and the JS test.

### A trap that really collapsed (0.24.0 → 0.24.2)

Recorded because it is a named kind of sloppiness, and the "easiest places to break" section above
does **not** name it.

**Wiring a real path into a function nobody ever called.** To keep the promise "all eight brains
the same", 0.24.0 sent the ChatGPT plan through `engine.responses_with_mcp`. That function already
existed in the repo, with the right name and the right signature, and reading it looked
reasonable. But `git log -S responses_with_mcp` returns exactly ONE result - the 0.24.0 commit
itself - meaning that before it **nowhere called it**, and its docstring itself says EXPERIMENTAL.
Run for real, it returned empty.

Two separate lessons:

1. **"Already in the repo" does not mean "works".** Before wiring a real path into an unfamiliar
   function, run `git log -S <function name>` to see whether anyone has called it. If nobody has,
   or the docstring says EXPERIMENTAL, treat the code as unverified - there must be a fallback.

2. **Raising permission must not TAKE AWAY a capability that already exists.** This is the painful
   part. The bot was answering well at the Read-only level; the owner raised it to Can write so it
   could do MORE; the result was that it stopped answering entirely. A "add permission" feature
   that breaks the basic path is far worse than not having the feature. Now when the tool loop
   comes back empty, that turn is rerun without tools, and a test guards it.

The fallback must NOT be silent. An owner who sets Can write while the bot quietly runs as
Read-only is a worse kind of failure than breaking outright - a break is at least visible. So a
turn that ran without its permission carries `canh_bao` ("warning") up to the bot card, through its
OWN path rather than borrowing the `loi` ("error") field: `loi` drags in the stumped counter, which
drags in calling the person on duty, and dirties the "Bot stumped" tab, while this is a normal
answer turn.
