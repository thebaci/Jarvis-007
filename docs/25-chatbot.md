# Chatbot (a dedicated bot)

***Tiếng Việt** · [English](en/25-chatbots.md)*

Put an **Agent** you created in front of other people: they message a dedicated bot on **Telegram** or **Zalo**, that Agent answers by the rules you wrote for it, and hands anything beyond its reach to a real person.

It suits anything you answer over and over for other people: questions about a product or a service, explaining internal rules to colleagues, fielding students' questions, guiding members of a community, filtering questions before they reach you.

It differs from [the Telegram channel](11-telegram.md) in one decisive way: the Telegram bot on the **Admin channels** page is **your own Jarvis 007** (full power, reading the main brain, able to call every data source, and only you can message it). The bot on the **Chatbot** page is **an Agent on duty** (read-only by default, seeing only its own brain, and strangers can message it). Do not use one in place of the other.

A dedicated bot **can do real work** if you raise its permission level: writing files, calling data sources, even acting outside. But whoever drives it is the person messaging it, not you, so read [The four permission levels](#the-four-permission-levels-what-the-bot-may-do) carefully before raising it.

## What this feature is

- Each bot = one **Agent** in one brain + a **dedicated token** on Telegram or Zalo. The bot reads that brain's documents.
- **The channel is a choice**: Telegram or Zalo. For Vietnamese customers Zalo is almost always the right one, because they already have the app. See [Choosing Telegram or Zalo](#choosing-telegram-or-zalo).
- The Chatbot page **belongs to the open brain**: switching brains at the top of the page shows that brain's bots, just like the Agents and Skills pages.
- People message the bot directly, or you drop the bot into a group.
- **The bot follows your Agent file exactly.** Jarvis 007 inserts no rules of its own.
- **Four permission levels**, chosen at creation and changeable later: Read only (the default), Reads documents, Can write, Full power. The first two write nothing and call no source; for the last two you must tick a consent box after reading the risks.
- Two rails **do not change with the level**, and they are locked in code rather than in wording: **the bot only sees its own brain**, and **it cannot run machine commands**.
- Questions the bot cannot answer are logged in the **Bot stumped** tab so you can add documents, and you click **Take over** on the Conversations page when a real person needs to step in.
- The Chatbot page is built for **many bots** from the start: a card grid, a search field, add/edit/delete, and enable/disable in place. Running one bot or ten uses the same interface.
- Every chat a customer has with a bot is kept in the **conversation inbox** (the **Conversations** page): read it back, see which chats the bot got stuck on, and click Take over to answer yourself when needed. See [Customer conversations](28-hoi-thoai-khach.md).

## Where to open it in Jarvis 007

The left navigation rail, the **Capabilities** group, the **Chatbot** item, the **Bots** tab. The page has only two tabs, **Bot inbox** and **Bots** (since 0.65.9; before that there were three tabs, Bot inbox, Bot channels and Create chatbot, and people had to jump between "add a channel" and "create a bot"). Saying "open chatbots" lands on the Bots tab.

## Preparing before creating a bot

Three things, and doing them in this order saves going back to fix things.

### 1. Stand in the right brain

A bot belongs to **the brain you have open**. Its Agent and the documents it reads both come from that brain, so switch to the brain you intend to give it before creating the bot.

**The bot only knows what is in that brain.** This is the point worth weighing most: if the bot will answer strangers, do not create it in your main brain, which holds internal notes, private figures and unannounced plans, and the bot cannot tell what may be said aloud and what may not.

The clean approach: create a brain dedicated to answering outsiders (the **Second Brain** page), put in exactly the documents outsiders may see, then switch to that brain and create the bot.

The rule for choosing what goes in: **if one sentence from this file leaking out would bother you, that file does not belong in the bot's brain.**

### 2. An Agent in that same brain

Go to the **Agents** page and create an Agent for the job the bot will do. Write the role and the instructions as if briefing someone on their first day: how to speak, what to prioritise, and in which cases to hand over to a human.

If you are on the Chatbot page and the brain has no Agent yet, click **New Agent** to jump to the Agents page, then come back when it is created.

The bot **reads the Agent at run time** rather than copying it. Editing the Agent later on the Agents page changes the bot immediately, with nothing to fix in two places. How to write an Agent: [Agents and Workflows](07-agents-va-workflows.md).

### 3. A channel account: a dedicated token, taken from the right place for the channel

Since 0.61.0 a token is a **channel** (a bot account), and a bot only **points** to it. Add a channel with the **Add a channel** button in the **Channels without a bot** section right under the bot list and tick it when creating the bot, or click **Connect a new channel** inside the New bot form (the newly connected channel is ticked for you); both lead to the same result. One bot on duty can serve **several** accounts (one role answering on Telegram and Zalo Bot alike), while each account has only **one** bot on duty.

If the bot runs on **Telegram**: go to **@BotFather**, type `/newbot`, set a name and username, and take the token string shaped `123456789:ABCdef...`.

If the bot runs on **Zalo**: open the Zalo app, find the Official Account **Zalo Bot Manager** and choose **Create bot**. The bot name must start with the word "Bot" (for example "Bot Hardware Store"). The token arrives as a Zalo message, shaped `123456789:abc-xyz`, and it **does not expire** until you reset it yourself.

**Each bot needs its own token, and do not use your main Jarvis 007 bot's token.** One token can only run one process; sharing kills both and the server returns a 409 error. Jarvis 007 blocks this when you click Check, but knowing in advance is better.

Pasting one channel's token into the other makes Jarvis 007 say so outright rather than leaving you guessing: the **Check** button asks the platform you actually selected.

## Choosing Telegram or Zalo

The first field in the create form is the channel, and it comes first because it decides everything below: where the token comes from, whether the bot can join groups, whether it can send files.

| | Telegram | Zalo |
|---|---|---|
| Vietnamese customers already have the app | Rarely | Almost always |
| Can join groups | Yes | **No** on the basic bot tier |
| The bot can send images to customers | Yes | Experimental |
| The bot can send documents (PDF, spreadsheets) | Yes | **Not yet** (Zalo has not opened the API) |
| Customers can send images for the bot to read | Yes | Yes |
| Customers can send documents for the bot to read | Yes | Not yet |
| Message size ceiling | 4096 characters | 2000 characters |
| The bot shows a `/` command menu | Yes | No, commands must be typed |

In short: **a bot talking to Vietnamese customers should use Zalo**, accepting that it is direct chat only and cannot send documents yet. **A bot for internal groups, or one that needs files going both ways, should use Telegram.**

**The channel cannot be changed after the bot is created.** Changing the channel means an entirely different bot: a different token, a different identity, different customers, and every stored group id instantly meaningless. If you need another channel, create a new bot; the Edit form shows the channel locked with exactly this explanation.

On the card grid, each bot carries a **channel marker** in two places: a small badge overlapping the icon corner (to recognise at a glance), and a chip with the logo in the information section (to read while scanning). Once you have bots on both channels, an **All / Telegram / Zalo** filter row appears at the top of the page.

### How the Zalo Bot differs from Zalo Agent MCP

Jarvis 007 has two ways into Zalo, and they do not replace each other:

- **The Zalo Bot** (this page) is a **separate identity** using the official API. No risk of the account being locked, but it only sees what people send directly to it.
- **[Zalo Agent MCP](12-zalo.md)** signs into **your own Zalo account** through the unofficial API. It reads real conversations and can message anyone, at the cost of the account possibly being restricted or locked.

The first is for **other people talking to Jarvis 007**. The second is for **Jarvis 007 acting on your behalf**. Using both is fine.

## How to use it (step by step)

### Step 1: Create the bot

Click **New bot**. Since 0.64.85 the form has **four parts**, each one a single decision, and the fields you rarely touch sit in an **Advanced** section that is collapsed by default:

| Part | What to enter |
|---|---|
| **Who the bot is** | Tick one or more channel accounts (only accounts of this brain that no bot is on duty for are shown), name the bot, and pick the Agent that serves as its brain or click **New Agent**. A channel already served by another bot appears **greyed out with a lock**, saying which bot (and which brain, if it differs from the open one) holds it. No channel yet? Click **Connect a new channel**: choose the channel type, paste the token, Check. See [Choosing Telegram or Zalo](#choosing-telegram-or-zalo) |
| **Who the bot answers** | Four cards, pick one; see [Who the bot answers](#who-the-bot-answers) just below. To choose groups or people you tick them in a list rather than typing ids. Alongside it is a selector for **when the bot speaks in a group**: Mentioned (the default), Auto-judge, or Every message (the Automate everything card has already decided this, so it hides the selector) |
| **What the bot answers from** | Agent and documents, or Documents only. See the two modes below |
| **What the bot may do** | The permission level. Leave it at **Read-only** the first time; read [The four permission levels](#the-four-permission-levels-what-the-bot-may-do) before raising it |
| Advanced | Reply language |

With only a Zalo Bot account, the group-selection part **disappears** rather than appearing and doing nothing: Zalo's basic bot tier does not let a bot join groups, so choosing groups there would be an empty promise sitting in the data.

#### Who the bot answers

This is the most important decision in the form, so it is four cards side by side for comparison:

| Card | What the bot does |
|---|---|
| **Automate everything** (since 0.65.2) | Like the card just below, but in a group the bot **decides by itself whether to speak or stay silent** (the Auto-judge mode of the [reply judge](#the-reply-judge-the-bot-decides-whether-to-speak-and-learns-from-the-group)) and gradually learns. One choice replaces two settings. What is saved is still "every chat" plus "Auto-judge", so a bot configured that way earlier automatically shows this card. It shares the confirmation box with the card below, plus a line saying the bot records the group's chat text in order to learn |
| **Every chat on the channel** | Answers direct messages and every group the bot is in; in a group you can choose Mentioned or Every message. You must tick the confirmation box, because if this is a personal Zalo account, friends and family get answered too |
| **Anyone in private, groups I choose** | **The default.** Anyone may message privately, and any group you have not ticked gets silence from the bot |
| **Only people and groups I choose** | The bot stays silent in every other chat. People and groups you have not ticked wait in a queue on the bot card; click **Allow** and it is done |

With only direct-message channels (Zalo Bot), the first two cards are hidden (there are no groups for the bot to decide about), and the remaining two are relabelled "Anyone may message" and "Only people I choose". Clicking the last card reveals the **people and groups picker**: two tabs, Groups and People, each with a count, a search box by name, the list of chats that have messaged the account, and an **Add by id** field for a chat that has never messaged. A chat waiting for your approval is sorted to the top and labelled.

The cards do not change the rule that the bot must be named in a group: a chosen group still follows the "when the bot speaks" selector. A card only decides **whether the bot is allowed to stand in that chat at all**.

**There is no brain selector**, and that is deliberate: the bot belongs to the brain you have open. To put a bot in another brain, switch brains at the top of the page and create it again; one place to look, with no two layers that have to match.

When you paste a new token, click **Check** before saving: Jarvis 007 asks the platform you selected whether the token is real, returns the actual bot name, and reports at once if that token is already an account in Jarvis 007 (if it is free, you just tick that account; if a bot is on duty, it names the bot). For Zalo Bot, if your tier does not let bots join groups, it says so right here.

**A newly created bot is always OFF.** That is deliberate: turning it on makes the bot talk to real people immediately, so turning it on has to be a conscious click rather than a side effect of creating it.

### Step 2: Test by messaging before going live

Turn the bot on with the **Turn on** button on the card, then open Telegram and message that bot directly with a few questions as a real outsider would. Ask a few questions within its scope, then one you know is not in the documents. See whether it answers in the right voice, whether it invents things, and whether it is willing to say it does not have that information.

If it is not right, turn it off, edit the Agent or add documents to the brain, then try again. Turning off takes effect immediately, with no Jarvis 007 restart.

### Step 3: When the bot is stuck, a real person steps in

Since 0.64.83 the form **no longer has an on-duty Chat ID field** (that was a Telegram number, unusable for a Zalo bot). A new bot does not message anyone by itself when stuck.

When stuck, the bot still answers by its Agent, or says it has no information if you chose the **Documents only** mode. The questions it cannot answer are logged in the **Bot stumped** tab so you can add documents. To answer a chat yourself, click **Take over** on the **Conversations** page and the bot goes silent in that chat. Anyone who types `/nhanvien` (Vietnamese for "staff member") is honestly told that no human line is connected and is invited to keep asking.

A bot that had an on-duty person set before 0.64.83 is **left as it was** (the bot card says "has human handover") and works as described in [When the person on duty is called](#when-the-person-on-duty-is-called).

### Step 4: Dropping the bot into a group

1. Invite the bot into the group like any member.
2. In the group, type **`/id`**. The bot returns the group id **and states the situation**: whether this group is enabled, whether Telegram's privacy mode is on or off, and what to do next.
3. That group **appears on the bot's card** on the Chatbot page. Click **Allow this group**. Done.

Use `/id` rather than naming the bot, and that is deliberate: **a `/...` command always reaches the bot** even with Telegram's privacy mode on, while a message naming it may not (see the section below). If the bot **says nothing at all** at step 2, the problem is not the group: either the bot is off or the token is broken; check the status dot on the card.

Declaring it by hand also works: take the id from step 2 (a **negative** number, shaped `-1001234567890`) and paste it into the **Add by id** field in the **Who the bot answers** part of the create or edit form.

**Until a group is allowed, the bot does not answer in it** (unless you chose the "Every chat on the channel" card in the Who the bot answers part). That default is deliberate: a bot dropped into an unfamiliar group that takes work on itself is butting into other people's conversation. But refusing does not mean vanishing: the bot says one sentence telling whoever called it what to do, and that group waits on the card for you to decide.

For a group you do not want, click **Skip** and it leaves the waiting list. If someone calls the bot there again it comes back; this page does not hide a place where people are trying to use the bot.

In an allowed group, by default the bot only answers when someone **names it** (typing `@bot_name`, or picking its name from the member list) or **replies to one of its messages**. In a group with several bots it can tell them apart: naming another bot or replying to another bot does not make it answer.

To make it answer **every message in the group**, change the "In a group, the bot speaks when" selector to **Every message**. Weigh it carefully: in a busy group it is very noisy and burns model quota fast. And it only works once privacy mode is off, so read the section just below.

### A bot on a personal Zalo account: groups and Auto-judge mode

Since 0.64.82 a bot attached to a **personal Zalo account** (connected on the Connections page, see [Zalo Agent MCP](12-zalo.md)) can stand in Zalo groups, not just chat privately. That account is a real person, so everything below leans toward silence.

**You must allow the group.** A message from an unfamiliar group puts that group in the waiting list right on the bot card, with the group name and an **Allow this group** button. Unlike Telegram, on Zalo the bot says **not one word** in a group that has not been allowed: a line such as "I have not been switched on yet" in front of the whole group is declaring itself a machine.

**If it is tagged, replied to or called by name, it answers at once.** Since 0.65.0 a bare name (such as "nhi mai ơi", Vietnamese for "hey Nhi Mai") also counts as calling it, see [The reply judge](#the-reply-judge-the-bot-decides-whether-to-speak-and-learns-from-the-group). The bot recognises a tag by "@name" in the text (the name is the connection label or the account's display name), by `mentions` if Zalo returns it, and recognises a reply to one of its messages. Tagging someone else does not make the bot answer. If it is tagged and stays silent, see the troubleshooting section below.

**Auto-judge.** In the "In a group, the bot speaks when" selector, choose **Auto-judge**. The bot still answers when tagged, and takes on one more job: for a message nobody addressed by name, it decides for itself whether to speak up. It goes from cheap to expensive, and a layer that rejects the message stops the process without spending a model turn:

1. Does the message look like a **question or a request for help** (a question mark, or words such as "làm sao" (how), "lỗi" (error), "cách" (way to), "hướng dẫn" (guide); this keyword list is Vietnamese on purpose)? Chatter, thanks, a bare link, or a message addressed to someone else is dropped.
2. Does any part of **the documents in the bot's brain** match the question? This is how the bot understands "a topic I can answer": there is grounding in the documents you supplied, not the model's general knowledge. If there is none, it stays silent.
3. Finally one model turn, in which the Agent is still free to choose silence if it feels it should not butt in.

The bot **waits about 20 seconds** before answering by itself, and if someone types manually from this account in the meantime it yields. Since 0.85.5 there is **no cap on the number of self-initiated replies** (before that, at most 8 per group and 3 per person per hour, with a pause between two replies): speaking or staying silent is the job of the reply judge and the model, following the Agent's role and the documents.

A message skipped because it could have been answered but the documents lack the answer always gets **one reason line in the bot log** (the bot card, the log section). The line "no part of the documents matches" is precisely a real question from someone in the group that the bot's brain is missing, so it is your list of documents to add. Skipped lines are **not** counted in the bot's turn count or stuck rate.

This mode also works with Telegram groups if you have turned privacy mode off (the section just below), but the yielding wait and recognising a tag by name exist only on a personal Zalo account.

**A tag inside an image caption counts too** (since 0.65.13). Send an image with a caption "@Bot name ..." and the caption is treated as the message content: the bot recognises the tag and answers as with a text message, and knows the message carried an image. **The bot sees that image with its own brain** (since 0.81.0): Jarvis 007 saves the image into the bot's brain, then sends the image straight into the chat turn for the model running the bot (Claude, GPT, Gemini, OpenRouter, Groq, Ollama, the ChatGPT plan, the Claude Code plan). A ChatGPT connection is no longer needed. If the brain cannot view images (Antigravity, Grok Build, a pure text model) or the image fails to download, the bot reads only the caption and says honestly that it could not see the image. Telegram works the same way: an image tagged with the bot, a reply to an image that tags the bot, or sending an image then tagging the bot right after (within 3 minutes, same person; privacy mode must be off) all work. An image with no caption is still ignored.

**A bot on a personal Zalo account differs from a Telegram bot** in one important respect: the sentences it sends carry the account's name, and many other people may also be messaging that account. So the bot only handles text messages, **images with captions** and **file** messages (bare images and voice are skipped), drops messages older than 3 minutes, and yields for 10 minutes when someone has just typed manually in that chat. A sentence the bot has just sent (images included) coming back round the reading loop is recognised as an echo and not counted as a person typing manually.

**In a private chat, the bot waits for the customer to finish, then answers once** (since 0.128.0). Customers often split one idea over several consecutive messages ("Teacher", "may I ask", "is there still room in grade 9"). The bot gathers those messages and answers only after the customer has been quiet for **5 seconds**, with one reply covering every point, in the right order. Sending an image then writing "please take a look" also becomes one question with an image, and sending a file does too (since 0.133.0): a bot with the Can write level or higher downloads the file into `inbox/khach` in the bot's brain (up to 20MB, reading text files' content directly), while a Read-only bot does not download it but still knows the customer sent a file. If you type manually into that chat during the wait, or turn the bot off, the bot sends nothing. So customers do not wait long, an account that just received a private message is read every 2 seconds instead of every 20, for one minute; that reading only reads the cache on the machine running Jarvis 007, with no extra calls up to Zalo. Groups are unchanged: each message is still judged separately as before.

**Images sent in a private chat** (personal Zalo). When a customer sends an image with no text (an exercise, their work), the bot still gets to see the image and answer; before, a bare image in a private chat was dropped entirely. The most recent image is attached again to text messages for the next 10 minutes (for example sending an image then writing "check whether this is right", or the bot asks for identity before looking at the work), so the bot no longer says "I could not read the image in the earlier message".

**If you typed manually and have not answered the customer after 10 minutes, the bot answers in your place** (since 0.136.0, private chats). The bot still yields for 10 minutes when you have just typed into the chat yourself, but customer messages arriving in that window are no longer dropped. Jarvis 007 holds them; once you answer (typing on your phone or sending from the Bot inbox), that is the end of it. When a full 10 minutes have passed since **your last manual message** and you have written nothing more, the bot answers once for all of them (since 0.172.0; at 0.136.0 the starting point was the customer's first message). The bot is told the customer has been waiting and what the customer attached (file name, image), so a message with only a file or a bare image still gets a fitting reply, for example confirming receipt and saying it will respond. The bot cannot open the file's content. Before 0.136.0 these messages were never answered, because after 10 minutes the message was already more than 3 minutes old. A bot with no yield minutes set (the field left empty) does not apply this to groups: during the yield window the bot stays completely silent in a group, as before 0.172.0, because in a group answering a message from ten minutes ago can feel out of place; see the paragraph below for a bot that has set a number of minutes. If Jarvis 007 restarts midway, held messages are forgotten: the worst case is one message not answered on your behalf, and it never answers twice.

**The yield minutes can be adjusted, or switched off** (since 0.172.0). The **Step aside after you type (minutes)** field in the Active hours section of the bot form. **Left empty** (the default, and every bot created before 0.172.0) keeps the old behaviour: yield for 10 minutes, private chats are answered on your behalf once 10 minutes pass, and groups stay silent for that whole window, even when tagged. **Writing a number** (even 10) means you choose the new rule for groups: a message that **tags the account directly** or replies to the account's message is answered at once, even within the yield window; a message that addresses nobody is held and answered when the window ends (see the paragraph below). A number other than 10 (say 5) makes the bot yield for exactly that many minutes, and in a private chat it also waits exactly that long before answering a customer message you have not answered. **Setting 0** means that when you type manually into any chat the bot does not go silent in that chat, even in a group; that is, while you are talking the bot may still butt in and answer. Even so, a customer message in a private chat that you have already answered manually is not answered again by the bot.

**In summary, the manual-typing rules** (since 0.172.0): if you do not type manually, the bot answers continuously as usual. When you have just typed manually into a chat, timing starts from **that manual message**: once the yield minutes pass and you write nothing more, the bot proactively goes on to answer the customer messages that are waiting. A private chat is merged into one turn; a group (only when the bot has a yield-minutes number set) gets one turn per person (the last 5 people to write at most) and still follows the bot's group rule, so a group set to "always answer" can receive up to 5 replies in a row when the window ends. If you type manually again, the starting point is recalculated from the newest message.

**Automatically accepting friend requests and reading the introduction** (since 0.172.0, personal Zalo only, off by default). Turn on the **Accept friend requests and read their introduction** box in the Active hours section of the bot form. Once an hour Jarvis 007 asks Zalo for the account's pending friend requests (each account is limited to 24 Zalo calls a day, so a sender may wait up to about an hour to be accepted), accepts each request (at most 10 per round, a few seconds apart), saves the message that came with the request into the Bot inbox as that person's first message and hands it to the bot as though they had just written it. If the introduction is complete (parent's name, child's name, grade), the bot does not ask again; if it is incomplete or there is no message, the bot asks for the missing part. Why it needs turning on: the message attached to a request exists only while the request is pending, and once it is accepted (even on the phone) Zalo discards it. Outside on-duty hours, or when the bot only answers chosen people, Jarvis 007 accepts no requests: the requests simply wait, and are accepted during on-duty hours. If Zalo refuses to accept a request, that round stops, that person is left alone for a while (for longer each time), and after 3 failures they are skipped until Jarvis 007 restarts, so they do not block newer requests. This runs separately, so a slow Zalo does not slow down message reading. It needs javis-zalo 1.0.0 or later (Jarvis 007 currently pins 1.4.0).

Engine notices such as "You've hit your session limit", "API Error" or "Credit balance is too low" are never sent to customers, even when the engine returns one as an ordinary answer (since 0.108.0). That turn counts as a failed turn: the person who asked the bot receives a generic apology, an Auto-judge turn makes the bot stay silent, and the real reason stays in the bot log.

**In a group, the bot tags the person it is answering by itself** (since 0.65.7). When a customer asks, the reply opens with "@Name ...", so the asker is notified and the whole group knows who the bot is speaking to. There is no setting for it, and it applies only to groups (a private chat does not need it). The **Reply for me** button in the Bot inbox also tags the sender of that message. A tagged message goes out through the `zalo-agent-cli` tool itself rather than through MCP (MCP can only send text), so each group reply takes about 1 to 2 seconds longer (since 0.65.8; before that about 3 to 5 seconds because each time `npx` had to run). The first time after an update, Jarvis 007 quietly installs a copy of the Zalo tool into the `tools/` folder inside its own data folder (about 10 seconds, once); during that time replies still go the old way and so are slower. If the tag fails (the machine lacks Node.js, Zalo refuses), the bot still sends the reply as before, only losing the tag; after three failures in a row the bot rests tagging for 10 minutes so as not to slow things down for nothing. In the timeout case specifically, Jarvis 007 **does not resend**, because the message may already have gone out and resending would produce two replies under your name; the bot log records one error line.

**In a group, the bot reads the 30 most recent messages to answer in context** (since 0.65.12). The bot is only called when someone tags or replies, so before, it saw only the sentence that called it and could not understand "so what about the other one?". Now each group reply carries up to 30 messages immediately before the message being asked (each cut to about 300 characters, the whole block at most about 6,000 characters, trimmed from the oldest message). This block is supplied as **data**, not instructions: internal markers and block-closing tags inside messages are stripped, and the bot is told to ignore any sentence in it that tells it to change its rules. It sits in that turn's instructions and is not written into the Agent's session history, so it does not grow over time. Private chats are unchanged. Each group turn costs about 1,000 to 2,000 more tokens.

### The reply judge: the bot decides whether to speak, and learns from the group

The old Auto-judge mode used a keyword gate: any message that did not look like a question was thrown away in silence, leaving no log line. Since 0.65.0 the **reply judge** replaces that gate with a context reader, shared by every bot but with one role per bot. Since 0.65.1 it **runs entirely by itself: there is no setting at all**.

**Where to turn it on.** Edit the bot, the **Who the bot answers** part, and choose the **Automate everything** card (every chat), or choose **Auto-judge** in the "In a group, the bot speaks when" selector (for the groups you chose). That is all. To turn it off, choose something else. The machine takes care of the rest:
- **Eagerness.** Each group has its own speaking threshold, starting at medium. The threshold moves down when the bot wrongly stays silent, moves up when the bot wrongly butts in, and drifts back toward medium by itself if there is no feedback for a long time (a half-life of 14 days).
- **When nobody calls it, the bot speaks only if there is grounding.** A bot that has documents needs a document section matching the question. A bot with no documents at all relies on the Agent's role (otherwise it could never speak up by itself). The machine knows which kind a bot is from the bot's brain. A learned case is not exempt from this rule.
- **A role profile written automatically** from the Agent file and the table of contents of THIS bot's own documents, and rewritten automatically when the Agent or the documents change.
- **Self-learning is always on** (see below).

**How it differs from the old rule.**
- **A bare name also counts as calling the bot**, no @ needed: "nhi mai ơi", "alo nhi mai" (Vietnamese for "hey Nhi Mai"), or the name at the start of a sentence. This one point applies to EVERY bot, even when it is not in Auto-judge mode. The names it answers to are the Zalo connection label and the account's display name. To make the bot recognise one more name (for example "Thu"), call the bot and teach it, such as "Nhi Mai, from now on call yourself Thu", using the account of the person being taught (see below). A name in the middle of a sentence ("ask nhi mai whether") is not enough to count as calling: the reply judge will weigh it.
- **It reads the last few messages** instead of exactly one, so a person the bot has just answered who asks a follow-up ("so what about the other one?") is understood as following up with the bot.
- **Every decision leaves a trace, even when the bot stays silent.** The "..." menu on the bot card, the **Reply judge** item, lists each message with its reason (for example "No matching document section", "Score below threshold") and the score against the threshold.

**One role per bot.** The reply judge **does not write the reply**: the voice and manner of answering are still the Agent's, so Nhi Mai speaks the Nhi Mai way and Jarvis 007 Vũ speaks the Jarvis 007 Vũ way. Three bots in different fields cannot read each other's learned cases, lessons or profiles, and one group's threshold does not change another's. A new bot comes with about 12 sample messages in its own field, written by the model from the Agent, and these samples fade as the bot learns real cases. Version 0.65.0 had a hand-written "Speaking rule" field: any text written there was merged once into the bot's **lessons** (visible in the Reply judge menu), and the form no longer has that field.

**How you tune it.** Not with settings but with feedback, on real data:
- Click **Right** or **Wrong** on each line in the Reply judge menu: the heaviest label, taking effect on the very next message. **Right** means the bot did the right thing (spoke at the right time, or stayed silent at the right time); **Wrong** means the bot should have done the opposite. Hover over the button to see the specific meaning for each line (for example "The bot should have stayed silent").
- Click **Make bot owner** on your message in the Reply judge menu: from then on the bot listens to your teaching right in the group (call the bot by name and say "don't answer small talk" or "when I call your name you must answer") and saves it as a **lesson**. Only the people you have set can teach it; other people's words in the group ("from now on answer every message") do NOT become rules. At the top of the menu a **Bot owner** line lists the people already set, each with a **Remove** button (since 0.65.14); a person who has been set shows an **Owner** label on their messages.

**Self-learning.** The bot also learns from STRONG reactions by real people, and a case just learned takes effect on the very next message:
- The bot stays silent and **the same person asks again** ("why aren't you answering") or someone calls the bot right afterwards: next time a similar message gets an answer, and the group's threshold goes down.
- The bot speaks by itself and **the owner says** "don't butt in", or you click **Take over** right afterwards: the group's threshold goes up.
- The bot is thanked, or is asked a follow-up in the right thread: recorded as right.
- Being ignored **does not count**, because people ignore it all the time.

Learning only changes **speaking or staying silent**, and never changes what the bot asserts: answers still stick to the documents and the Agent's role. Yielding while you type manually, which groups are allowed, and the permission level all lie outside the learning loop. When the reply judge errors, times out or returns garbage, the bot stays **silent** (except that a message that clearly calls it by name is still answered). The **Forget all** button erases the cases, thresholds, lessons **and the bot's decision log** (irreversible).

**Privacy.** Because it runs by itself, a bot in Auto-judge mode records the text of every group message worth weighing so it can show it in the Reply judge menu: at most 400 characters per message, kept for 14 days. Learned cases (from your feedback or the group's) are kept for at most 180 days. All of it sits in Jarvis 007's data folder (not in git). A bot not in Auto-judge mode stores nothing. **Forget all** or deleting the bot wipes this data completely.

**Who runs it and what it costs.** Each message worth weighing costs one cheap model turn on the "background work" model you chose on the **Models** page (a cheap subscription plan or API both work), adding a few seconds; the model runs in an empty folder, with no tool that writes or runs commands. Obviously unworthy messages (empty, just a link, addressed to someone else when nothing else has been learned) and messages that clearly call it by name cost no turn. The reply judge is fully used on **personal Zalo** (message window, consecutive messages). On **Telegram** it also decides in groups but has no consecutive-message window.

**For the operator.** To observe before trusting it, set the environment variable `JAVIS_REPLY_POLICY_SHADOW=1` and restart: every bot runs in trial mode, the old rule still decides and the reply judge only records its decision for comparison. This is an operator switch, not in the interface.

### The reply judge reviews itself, and you can ask Jarvis 007 to tune it (since 0.77.0)

The instant learning above fixes one message at a time. Since 0.77.0 there is also a **self-review loop** that looks at the whole picture: when a bot has gathered enough new evidence (about 8 Right/Wrong labels, or 40 messages it stayed silent on) and 24 hours have passed since the last review, Jarvis 007 sends that bot's report to the **main brain** (the model you chose on the **Models** page, usually stronger than the cheap model scoring each message). The model looks for repeating patterns, for example "customers tag Quý and ask about the class schedule and the bot stayed silent all seven times", then adjusts at most 3 things itself. With no clear pattern, nothing changes.

**What it can adjust.** Only speaking or staying silent, from a closed list:
- add or remove **lessons** (the review loop can only remove lessons it wrote itself, and never pushes out one you taught);
- turn a message the bot stayed silent on into a "should answer" **sample case** (or the reverse);
- the **threshold** of each group, and the bot's overall **eagerness to speak**;
- **also weigh messages that tag someone else**: by default a message opening with "@someone" is skipped. Turn this on and a message such as "@Quý what is the schedule" is still weighed, though the bot still speaks only when the documents have a matching section and the reply judge agrees. Clicking **Wrong** on such a tagged message now has an effect too: a similar message will be weighed next time.

Every change must cite the bot's own messages as evidence, so text a customer types into a group cannot turn into a command. Rate limits, yielding while you type manually, permissions and the content of the replies remain out of reach.

**Self-measuring, self-reverting.** After each review, the machine compares the rate at which the bot is marked wrong before and after. If it is clearly higher, that whole review reverts itself and you receive a notice. Where something is hard-coded (something the review loop cannot adjust), it writes a suggestion into `Javis/gop-y-bo-phan-xu.md` in the bot's brain.

**How you find out.** Every review that changed something or left a suggestion sends exactly one message to your **inbox** (the bell) and your Telegram, listing each change and the review id.

**To intervene, tell Jarvis 007**, with no settings to open:
- "Give me the reply judge stats for Jarvis 007 Vũ this week, why is the bot silent so often?"
- "Let Jarvis 007 Vũ answer in my place when a customer tags me about the class schedule."
- "Revert self-review a1b2c3 for Jarvis 007 Vũ."

Jarvis 007 reads the reply judge's actual figures (the same report the review loop reads), proposes a change, and applies it once you agree. Every change, whether from the review loop or at your request, is logged and reversible. For deeper analysis, switch the main brain to a stronger model on the **Models** page before asking.

**A customer-service bot never sees these two tools.** The reply judge's store holds the chat text of every customer, so only your own session can read and adjust it. A bot at the Can write or Full power level does not see them either.

**Note on subscription plans.** The self-review loop is background work on the main brain. If that is a Claude Pro/Max plan, this is a kind of use Anthropic does not count as ordinary personal use. The frequency is very low (at most once a day per bot, and only when there is evidence), but the safest course is to run the main brain on a ChatGPT plan, Grok or an API key. The operator can switch the review loop off entirely with the environment variable `JAVIS_REPLY_POLICY_REVIEW=0`.

### Telegram's privacy mode (read this if the bot is silent in a group)

Every new bot has privacy mode **on by default**. While it is on, Telegram **does not forward** most group messages to the bot, and blocks them on Telegram's side: Jarvis 007 never sees those messages, whatever you set in the dashboard.

What is **guaranteed** to reach the bot while this mode is on:

- **Commands** `/...` (which is why `/id` always works).
- **Messages that reply directly to a bot message** (clicking Reply on something the bot said).
- Service messages (members added or removed).

A message that only **names** the bot depends on the version and the type of group, and is **not guaranteed**. If you tag the bot's name and it stays completely silent while direct messages work fine, this is almost always the reason.

Fix it in **one of two ways**:

1. Open **@BotFather**, type `/setprivacy`, choose this bot, choose **Disable**.
2. Or make the bot an **administrator** of that group. A bot that is an admin receives every message, regardless of privacy mode.

Afterwards, **turn the bot off and on again** on the Chatbot page so it re-reads the new state. The bot card shows this state for every bot that uses groups, and `/id` in the group says it too.

There is a third cause for exactly that symptom, rarer: **the bot cannot ask Telegram for its own identity** (the network dropped at the very second of startup). In that case it does not know its own `@username`, so it cannot recognise anyone calling its name, even though direct messages work perfectly. The bot card flags it with a red line, and Jarvis 007 asks again every minute; turning the bot off and on fixes it immediately.

**When an ordinary group is upgraded to a supergroup, Telegram changes its id** (adding the `-100` prefix). Jarvis 007 hears about it at that moment and updates the list by itself, so you do not have to declare it again; this used to be a way for the bot to go silent without leaving any clue.

## Reading a bot card

Each card has a coloured dot and a status line. There are **four** statuses, not two:

| Dot | Meaning |
|---|---|
| Green - Running | The bot is listening and answering normally |
| Yellow - Starting | Just turned on, shaking hands with Telegram |
| Red - Error | The bot is dead. The token was revoked, the network dropped, or the token duplicates one elsewhere. The reason shows right under the card |
| Grey - Turned off | You turned it off |

The **Error** status has to be visible, because a bot dying silently is something you only discover when someone complains.

The card **refreshes itself every few seconds** while you have the page open. This is needed because the status changes without anyone clicking anything: right after you click Turn on, the card says "Starting" (the bot is shaking hands with Telegram), then a few seconds later it becomes "Running". Without the refresh, the card would sit at "Starting" until you leave the page and come back, while the bot has been answering for a long time.

The card also warns when **the bot's Agent no longer exists** (you deleted it or changed its slug on the Agents page). The bot keeps running but answers without role instructions, so fix it at once.

**The permission level shows right on the card**, for all three levels and not only the two that can act: grey is Read-only, yellow is Can write, red is Full power. You do not have to open the Edit form to know which one is at which level, and a card with no label no longer reads as two opposite things.

## How many tokens a bot costs

A bot **does not go through** the Optimised and Ultra-saving levels on the Usage page. That is deliberate, not an omission: those two levels exist to trim CLAUDE.md, MEMORY.md and the tool specification table, **three things a bot has never had**.


Measured on a sample brain, the fixed portion per turn:

| Path | Fixed tokens |
|---|---|
| Dashboard chat, Full level | ~8,900 |
| Dashboard chat, Ultra-saving level | ~460 |
| **Dedicated bot** | **~20** |

The rest of a bot turn is searchable documents, and those are the answer itself, not surplus. In other words the bot is already lighter than the deepest saving level, so pushing it through those two tiers would only make it **heavier**.

On the line under the answer and in the measurement table, a bot turn shows as **"Dedicated bot"**. Before 0.23.1 it was lumped into "Full", exactly the opposite of the truth, since this is the cheapest path in the system.

A bot is still counted in **Usage** like any other turn, by the actual provider and model running.

Do not confuse a bot with **your own Telegram channel**: that channel *does* go through the two saving levels (since 0.24.0), because your own Jarvis 007 really does have a CLAUDE.md and a MEMORY.md to trim. A bot has nothing to trim.

## What the bot answers from

Every time someone asks, Jarvis 007 **searches the documents in the bot's brain first**, takes the few best-matching passages, and puts them straight into the head of that turn's prompt.

This is different from "the bot has permission to read the brain". Having permission to read does not mean it will read: the model can perfectly well answer straight from its general knowledge, with a sentence just as fluent and confident, and you **cannot tell the difference from the outside**. So Jarvis 007 searches first, rather than leaving that decision to the model.

### Google Docs and Google Sheets linked from the Agent (since 0.84.10)

A price list or guide that lives on Google does not need copying into the brain. Attach the link to the Agent (the **Assistant documents** section when you open the Agent) or paste the link straight into the Agent's content, and the bot will search it just as it searches the brain's files:

- Google Sheets are read across **every tab**, each row carrying its column names, so when a customer asks "how much is the Stanley cutting pliers" it finds exactly that row. A link pointing at one specific tab (with `#gid=` at the end) reads only that tab.
- The file must be shared as **Anyone with the link, Viewer permission**, with downloading not disabled. A file that is not shared still lets the bot answer normally, but without that part, and the bot card shows a warning saying exactly which link needs sharing.
- Edit the file on Google and a few minutes later the bot uses the new version. If Google has a temporary problem, the bot uses the last version it could read.
- Only links **you** attach in the Agent are read. If a customer pastes a link into a message, Jarvis 007 does not open it. Two bots in the same brain but with different Agents do not see each other's links.

At the **Reads documents** level, the bot's three self-search tools still only open files in the brain. The content of Google links reaches the bot through the pre-searched part before each turn.

### Two modes, chosen when creating the bot

The difference lies only in **what happens when no matching document is found**. When one is found, both modes behave identically.

| Mode | If no document is found, the bot does this | Suited to |
|---|---|---|
| **Agent expertise** (the default) | Jarvis 007 adds nothing; the Agent handles it by the rules you wrote | Advisory, coaching, training and professional Q&A bots |
| **Documents only** | Adds one rule: say there is no information, do not use general knowledge | Bots that read figures and regulations, where one wrong sentence does real damage |

A wrong choice shows immediately: a coaching Agent running in "documents only" mode will answer "I have no information" to exactly the questions that fall within its expertise, however carefully you wrote the role instructions. Change the mode with the **Edit** button; it takes effect at once.

### Jarvis 007 does NOT write rules for the bot

This is the most important thing to know about this page.

The bot runs on **exactly the contents of your Agent file**, nothing more. Jarvis 007 puts no extra rules on top: it does not tell it how to address people, does not forbid it any topic, does not force it to answer briefly. The rules you wrote in the Agent are the only rules the bot has.

The only exception is the "documents only" mode above, and that is a rule **you actively switch on**, not a Jarvis 007 default.

So **the Agent file decides the bot's quality almost entirely**. Write it as you would brief someone new on the job: how to speak, how far its scope goes, what it must not promise, and in which cases to hand over to a real person. If the bot behaves wrongly, fix the Agent; do not look for another button.

### Two rails Jarvis 007 locks at the first three levels

The two things below hold at Read-only, Reads documents and Can write. The **Full power** level is different (since 0.85.3 it runs exactly like the admin channel, see the Full power level below). They live in the source code rather than in instructions, so wording cannot talk its way around them:

- The bot **cannot see other brains**, including your main brain. Every file read and write path is clamped inside the bot's own brain folder; climbing out with `../` or an absolute path is refused at once.
- The bot **cannot run machine commands**, cannot open an arbitrary web page by itself, and cannot spawn sub-agents. The bot also has **no admin commands**: `/brain`, `/model` and `/status` do nothing.

How Jarvis 007 guarantees it: **the bot never touches the engine's native tools.** At Read-only it has no tools at all; at Reads documents it has only the three document-reading tools; at Can write, every tool goes through Jarvis 007's connection hub, where file paths are clamped and the permission level is enforced right at the point of the call. The bot does not open a CLI, so Claude Code's `Bash` and absolute-path `Read` are not present here.

As for documents, they are still pre-searched in Python before the model runs and then placed in the head of the prompt, at every level. The bot reads its brain without needing any tool.

## The four permission levels: what the bot may do

Chosen in the **What the bot may do** field when creating or editing a bot. The default is **Read-only**.

| Level | What the bot can do | Suited to |
|---|---|---|
| **Read-only** (default) | Only reads documents then answers. No tools at all. | Duty desks and Q&A, almost every job |
| **Reads documents** | Like Read-only, plus three read-only tools to **search and open** documents in its brain by itself. No writing, no calling any source | A bot that stays silent unfairly because customers type differently from the document's wording |
| **Can write** | Adds: writing files in its own brain, calling data sources you connected at read/write level | Recording requests, updating notes, looking up real figures |
| **Full power** | **Exactly like the admin channel**: machine commands, every file, every one of your connections (including Gmail, Drive, calendar through your Claude/ChatGPT account), skills, background work, every outside action | A bot that only you or someone you trust absolutely can message |

### The Reads documents level (since 0.80.0)

At Read-only, Jarvis 007 searches documents **by wording** before each turn and hands the bot the few best-matching passages. That keeps the bot from inventing, but it misses when a customer uses different words from the document: the document says "hoàn trả" (refund) and the customer types "đổi trả" (return/exchange), so nothing is found and the bot stays silent or says it has no information. (This example is Vietnamese on purpose, since it shows how Vietnamese wording differs.)

The **Reads documents** level keeps that pre-search, then gives the bot three extra tools to read its brain **by itself**, the way Jarvis 007 itself reads a notebook:

- **Search** the documents, retrying with other words when the first attempt finds nothing.
- **List** the documents with their section names, to pick the right document for the topic.
- **Open and read in full** a document.

The bot is told: a question that needs specific information the pre-search lacks must be searched for first, and only when a thorough search still finds nothing may it say there is no information.

**The reply judge looks at the table of contents too.** At other levels, a message nobody addressed to the bot whose wording misses is dismissed by the reply judge at once. At this level it gets to see the bot's document table of contents and judge for itself whether that message belongs to any topic, so a customer typing different words is no longer unfairly ignored.

**Why this level does not require a consent tick:** it takes away nothing that the pre-search has not already taken.

- No writing tools, no data-source calls, no plugins, even if you have connected many sources. Jarvis 007 locks this at the tool-call layer, not with instructions.
- The bot can open only the very files the pre-search still searches: excluding `memory/`, `inbox/` (files customers sent), skills, plugins, Jarvis 007's convention files, and also `agents/` and `workflows/` (your internal instructions). A path typed by a customer is compared only against that list, so `../`, absolute paths or linked files pointing outside cannot be opened.
- Only the bot's own brain. If the brain information is missing, the bot gets no tools at all, rather than falling back to the brain you have open.

The **Try** button runs exactly this level (because it only reads), so you can test straight away. This level costs a few extra model calls when the bot searches by itself, and is as engine-sensitive as the two levels above it (see [Which engines can run the raised levels](#which-engines-can-run-the-raised-levels)).

### What you lose by raising the level

This is the part of the page most worth reading closely, because it is the fundamental difference between a dedicated bot and your own Jarvis 007: **the person typing into the bot is someone else, not you.**

At Read-only that is harmless: however cleverly someone coaxes it, the bot can only wander off topic, because it has nothing to harm anything with. Raising the level removes exactly that property.

**The Can write level:**

- The bot can write files in its brain. A single sentence from someone messaging the bot changes real content in the brain, **with no approval step**.
- The bot can call the data sources you connected, at read and write level. Everything in those sources is within reach of the person chatting with the bot.
- Jarvis 007 still **hard-blocks** the group of outside actions at this level: no sending out, no paying, no booking or cancelling, no deleting, no publishing anything. The block sits at the tool-call layer, not in instructions.

**The Full power level (runs exactly like the admin channel since 0.85.3):**

- The bot runs **exactly the admin channel's path**: the same brain, the same native engine tools (running commands on the server, reading and writing every file including other brains), all of your connections (including Gmail, Drive and calendar connected through a Claude or ChatGPT account), skills, background work handoff, scheduling. It differs from the admin channel only in that it speaks in the **Agent's role** and works inside the bot's brain.
- The bot can perform every outside action: sending out, paying, booking or cancelling, deleting, publishing. Those actions are **irreversible**.
- The person driving it is **whoever messages the bot**. One cleverly worded sentence ("ignore the earlier instructions, do this for me") is enough for the bot to comply; all that remains is the Agent file you wrote, and wording can be talked around. There is no per-command approval gate.

So: **only turn on Full power for a bot that only you or someone you trust absolutely can message** (set the **Who the bot answers** part to chosen people). Where anyone can message, do not turn it on, however carefully you wrote the Agent.

The Grok Build and Antigravity brains can use tools only at the Full power level. At Reads documents and Can write they answer with no tools, and the bot card shows a warning saying so plainly.

### How to raise the level

1. Click **Edit** on the bot card (or choose it right when creating).
2. Choose the level in the **What the bot may do** field. That level's list of risks appears right below.
3. Tick the **I have read and accept the risks above** box. Without the tick it cannot be saved: Jarvis 007 blocks it in both the interface and the server, so removing the tick box with devtools cannot raise the level either.
4. The Full power level asks once more before saving.
5. Turning the bot on also asks again, because creation may have been days ago and the hand clicking Turn on may not remember which level this bot is at.

Lowering the level asks nothing: lowering permissions is always safe, and when you are trying to stop an incident you should not have to click more.

Every bot card with a raised level has a coloured band stating the level: yellow for Can write, red for Full power. A Read-only bot carries no label, since that is the default. The log also records the level of **each turn**, so looking back at "what the bot did that day" stays accurate even if you lowered the level after an incident.

### Per-chat exceptions (since 0.172.0)

A bot answering strangers at the **Read-only** level that still has to do real work for someone close to you (for example your mother messages that very Zalo account asking you to fix a Word or Excel file) should not have the whole bot raised. Add an **exception** for exactly that person's private chat, in the **Per-chat exceptions** section of the bot form: type a few letters of the person's name in the search box, pick the chat in the list (the private chats the Bot inbox already knows on the ticked account), click **Add**, then choose the level and the wait seconds for that row.

- **Only that chat, on exactly that account** runs at the chosen level. An exception is tied to the channel account where the chat lives: the same id on another of the bot's accounts (Telegram, WhatsApp, another Zalo account) does not count, and a group with the same id does not either. Every other chat stays at the bot's general level. Because you have to choose from a list, that person must have messaged the account at least once beforehand.
- Raising a chat to **Can write** or **Full power** requires confirming the risks **separately for the exception**, apart from the confirmation for raising the whole bot: agreeing to raise the bot does not mean agreeing to raise one chat. Saving again with the same list, or lowering a level, does not ask again.
- When a level is raised, that person is always answered by the bot, even when the bot only answers chosen people, and on a personal Zalo account the bot is told not to stay silent just because it is a family matter. **Lowering a level** (for example a Full power bot but you do not trust one customer) only lowers: that chat does not become a chosen person and the bot is not told anything extra.
- The exception's level applies both to the bot's own automatic replies and when you click **Reply for me** or **Suggest a reply** in the Bot inbox.
- **Wait seconds** (0 to 60, empty means the same as everyone) is how long the bot waits for that person to finish writing, and **exists only on personal Zalo**, the only channel that gathers messages before answering. Other channels ignore this value. Note that messages gathered over 180 seconds (`TUOI_TOI_DA`, the maximum age) are dropped from the turn, so for someone who often writes in scattered bursts over a long time, a short wait is safer than waiting 60 seconds.
- Raise the level only for people you trust absolutely: at Full power, that person can drive the bot like you yourself. The bot card shows the number of exceptions it has.

### Which engines can run the raised levels

The **Read-only** level runs identically on all nine brains, with no exceptions.

The other three levels (Reads documents, Can write, Full power) need an engine that can call tools. The six API engines (OpenRouter, OpenAI, Anthropic, Gemini, Groq, Ollama) and the Claude Code plan use the path that has been running for a long time. The **ChatGPT plan** specifically goes through a Codex backend route that the provider has not published as stable, so it may be unable to call tools.

In that case **the bot does not die**: it answers that turn at the Read-only level, and the bot card shows a yellow band saying plainly that it is running with less permission than the level you set. Raising the level is never allowed to take away capability the bot already had.

If you see that yellow band, pick one of two: change the engine on the **Models** page if you really need the bot to do work, or lower the bot to **Read-only** so it is not mistaken for doing it.

### Changing the brain does not change the experience

The bot runs identically on **every brain**: Claude Code, ChatGPT, Grok Build, Antigravity, OpenRouter, OpenAI API, Anthropic API, Gemini, Groq, Ollama. Change the model and the bot follows, but how it works does not change. When tools can be called, every engine holds **exactly one set of tools**; see the note above about the ChatGPT plan.

This works because the bot's turn takes its own path, shared by every engine: the same prompt head from the Agent, the same pre-searched documents, the same conversation history, and tools (if any) come from the same place. What remains different is exactly the difference between models, not between pipelines.

This path also does not open a CLI, so the bot answers faster than your own chat path.

### Making documents match well

- **Put clear headings in the file.** Jarvis 007 splits documents by markdown headings (`##`), and each passage is taken separately. One long file with no headings can let the bot read half a condition and answer as if that were the whole condition. Splitting into "Retail price", "Wholesale price", "Returns", "Delivery"... matches best.
- **Files outsiders upload are NOT counted as documents.** They sit in `inbox/khach/` and are excluded entirely from the search. Otherwise anyone could upload a file that overrides your rules and then ask again, and the bot would quote it as an official document.
- **Jarvis 007's internal convention files are excluded too.** `CLAUDE.md`, `AGENTS.md`, `wiki/index.md`, `wiki/log.md` and a few other navigation files exist in every brain but are the system's internals, not content for answering outsiders. Your real Wiki notes are used as normal.
- **Typing with or without Vietnamese diacritics are both searchable**, but typing with diacritics is more exact: "bán" (sell) does not match "bản" (version), "cà" (as in "cà phê", coffee) does not match "cả" (all). Documents should use correct spelling and correct diacritics. (These examples are Vietnamese on purpose.)

## The log and where documents are missing

Click **Log** on the bot card. There are two tabs, and the one that opens first is the more important.

**Where the bot's conversations with customers live.** Since 0.65.0 each customer chat is a conversation in the **history of the Agent** attached to the bot, on the **Partners** page (open that Agent, the History tab), with a **Bot** label to tell it apart from the chats you have with the Agent yourself. A conversation in a group carries the **group name** (since 0.65.1), not the first message of whoever wrote first; a private chat is still named after its first message. They no longer appear in the history of the **Chat** page. Bots sharing one Agent have both conversations in that Agent's history.

**Bot stumped** lists the questions the bot could not answer, merged for duplicates and ranked by **how many times they were asked**. This is the most valuable tab: each line points to exactly one place where your documents are missing, in the asker's own words. Write the addition into the brain and next time the bot can answer.

Duplicates are merged ignoring diacritics, so "Giá bao nhiêu?" and "gia bao nhieu" (both Vietnamese for "How much is it?") count as one question. Otherwise one question would be split into several separate lines and you could not see that it is in fact asked a lot.

"Stumped" is measured by **the bot's own sentence**: it says it has no information, or it has to hand over to a real person. For a bot running in "documents only" mode, finding no document counts too.

The most notable kind is the stumped case where the bot **still found a document**: the document exists but lacks exactly what the person needed. That kind points to where the writing is insufficient, and is subtler than the kind with no file at all.

**Recent conversations** lets you review each turn, with **the exact file the bot used** to answer. That source line is what makes the question "did the bot answer correctly" verifiable instead of a guess.

### When the person on duty is called

A bot that had an on-duty Chat ID set before 0.64.83 calls the person in two cases: the person asking types `/nhanvien`, or the bot is **stumped on two consecutive questions** from the same person. Answering one question resets the count to 0.

A single stumped question does not call. Reporting every stray question means the person on duty mutes notifications within a few tries, and when a real person needs help nobody reads them any more. Two in a row is the sign that someone is truly stuck.

The third case is the bot **breaking** (it cannot call the model). This is reported from the very first time, without waiting for two questions, because every silent minute is a person who is messaging and thinking they have been abandoned. But it is reported only **once** until a turn runs successfully, otherwise the on-duty inbox becomes an error log.

Before counting it as broken, Jarvis 007 has already retried up to three times if the error was **transient** (the provider returning 429 for too many calls, a 5xx overload, a network blip). A momentary 429 no longer wakes the person on duty. A break notice carrying *(retried 3 times)* means everything was tried, so go and look at the **Models** page or the account's quota. Details in [Troubleshooting](17-khac-phuc-su-co.md#the-provider-reports-a-rate-limit).

The log keeps the 2000 most recent turns per bot, and older ones are trimmed automatically. Deleting the bot deletes its log with it.

## What a bot can and CANNOT do

**At every level, the bot can:** read the documents in its brain, answer by the rules in the Agent file, remember the conversation thread with each person, and hand over to the person on duty.

**At every level, the bot CANNOT:** read or write another brain, run machine commands, open an arbitrary web page by itself, spawn sub-agents, or use admin commands (`/brain`, `/model`, `/status`... all do nothing, and the bot just answers generically).

**The rest depends on the permission level** you set: writing files, calling data sources, acting outside. See the table in [The four permission levels](#the-four-permission-levels-what-the-bot-may-do). The default is Read-only, which means it can do none of those.

The bot's Telegram command menu has only three entries (`/help`, `/nhanvien`, `/id`), not the admin menu of your main Jarvis 007 bot. Listing commands there that the bot refuses to run would teach people to go looking for a different set of commands.

As for **how it speaks, the scope it takes on, and what it refuses**, your Agent file decides, not Jarvis 007. To make the bot avoid a topic, not promise things on your behalf, or not change roles when coaxed, write those things into the Agent.

Note the correct understanding: the limits above live in the **permission level in the source code**, not in an instruction in the prompt. An instruction can be talked around by clever wording; a permission level cannot, because the tool is simply not granted to that turn. The flip side of the same fact: when you **grant** a tool to that turn, the instruction in the Agent can no longer hold it back either.

## The bot sends images to customers (since 0.84.3)

The bot can send images on Telegram, personal Zalo, Slack, WhatsApp and Lark, at **every permission level**. How to use it: say in the Agent file when to send which image, for example "when a customer asks about the shirt model, send `![Shirt model](attachments/shirt-model.jpg)`". The Agent inserts that image syntax into the reply, Jarvis 007 strips it from the text and sends the real image right after the text message. In a Zalo group, the text message still tags the person asking.

Jarvis 007 sends only when all of these conditions hold:

- The image **lives in the bot's own brain** (path counted from that brain's root). An image in another brain or elsewhere on the machine does not qualify.
- It really is an image (`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`), it exists, and it is no larger than 10 MB. Document files such as PDFs or `.md` notes are not sent.
- At most 4 images per reply.

If an image does not pass the conditions, the image syntax stays in the text as it was, so you can see in the Bot inbox what the bot meant to send. Jarvis 007 does **not** automatically attach any file the bot has just produced: the person driving the bot is a stranger, so only an image the Agent deliberately names goes out.

## The bot speaks like a person, exposing no machine state

A dedicated bot **shows no Jarvis 007 status line at all** to the person messaging it. This is entirely unlike your own main Jarvis 007 bot (that one still shows everything, see [Telegram](11-telegram.md); the machine's owner needs to see how far Jarvis 007 has got).

Specifically, a person messaging a dedicated bot will NEVER see:

- the "🤔 Jarvis 007 is processing…" message and its "⏳ ⚙ Calling tool…" updates
- the line "⏳ Still processing the previous message. Send /stop to stop, then ask again."
- technical error lines like "⚠ Error: TimeoutError: ..."
- the text "(no content)" when a turn returns empty

Instead, while the bot is thinking, Telegram shows the **"typing…"** dots at the top of the conversation, exactly what a real person leaves when they are typing. When a turn breaks, the bot apologises in an ordinary sentence and invites the person to write again; the technical reason is still fully recorded in the bot log and is still reported to the person on duty if you set one.

**Writing more while the bot is answering is not blocked.** The bot gathers those messages, and once it has answered the earlier one it answers the next straight away, exactly like a person who finishes reading the messages before replying. It gathers at most 5 messages per conversation so a stranger cannot spam it into bloating memory.

One place still deliberately speaks plainly: when someone calls the bot in a **group you have not allowed**, the bot says exactly one sentence, once, saying it has not been switched on for this group. If it stayed completely silent there, the bot would look broken and you would have no way to know to go and click **Allow**.

## Rate limiting

Since 0.85.4 there is **no limit on how many replies the bot gives each person**. Anyone who messages privately or calls the bot by name is answered, however many messages. (Before that, each person had at most 20 replies an hour, beyond which the bot asked them to try again later.)

Since 0.85.5 there is also **no cap when the bot speaks up by itself** in a group when nobody calls it (the Auto-judge mode, see the section above). How many times the bot answers by itself is decided by the reply judge and the model, following the Agent's role and the documents; you tune it by clicking Right/Wrong in the Reply judge.

No limit means that a person who messages continuously, or a large group that asks a lot, will keep spending your model usage. If you see something unusual, click **Take over** on that chat on the Conversations page, narrow the **Who the bot answers** part, or switch that group back to **Mentioned**.

## Deleting a bot

Click **Delete** on the card. The bot stops answering at once.

**The bot's reply judge data IS deleted** (decision log, learned cases, lessons, role profile): it is customers' chat text, so it is not left orphaned.

**Its brain and Agent are NOT deleted.** The brain may hold a month of documents you wrote yourself, and the Agent may be in use by another bot or a workflow. To delete them, do it on their own pages.

## Frequently asked questions

**Which model does the bot use?** The model in the **Model** field of the very Agent the bot points to (Partners, then Agent settings). If that field is left at **Default**, the bot runs the main model from the Models page. The bot card on the Chatbot page shows the model it is running, so a glance tells you. Change the model and the bot follows, and how it works does not change; every brain goes down the same path.

Why it follows the Agent rather than the main model: the bot already borrows the Agent's prompt head wholesale, so the model has to be the Agent's too; otherwise you could pick a cheap model for a public-facing assistant and the bot would still burn the expensive model, with no sign of it. If the chosen provider has its key removed, the bot falls back to the main model rather than dying silently in front of customers.

**Can the bot call the data sources I have connected?** By default no: the Read-only level has only the documents in its brain. Raise it to **Can write** and yes, and **Full power** does exactly as the admin channel does, including the connections of your Claude/ChatGPT account and the group of outside actions. Bear in mind that the person driving it is whoever messages the bot; for things only you need, asking Jarvis 007 in the dashboard or on your own Telegram channel is still safer.

**Is a bot at Full power dangerous?** Yes, and that is why Jarvis 007 makes you tick a consent box and then asks once more. This level gives the bot exactly the admin channel's powers. The danger is not the model misbehaving but that **other people can message the bot**: one cleverly worded sentence and the bot runs a machine command or calls a real tool, irreversibly and without asking you. Use it only for a bot that only you or someone you trust absolutely can message.

**It is running at Full power and something feels wrong. What do I do right now?** Click **Turn off** on the card; it takes effect within seconds, with no Jarvis 007 restart. Then click Edit and lower the level to Read-only; lowering asks nothing. See what the bot did in the **Log**, the Recent conversations tab.

**Can I run several bots at once?** Yes. Each bot has its own token and its own process. The Chatbot page is built for it.

**Can two bots share one Agent?** Yes, and sometimes it makes sense: the same role but two different brains for two different groups of askers. On the other hand, two bots sharing one token is not allowed; Jarvis 007 blocks it.

**What if people send the bot an image?** Files sent in land in `inbox/khach/` in that bot's brain ("khach" is Vietnamese for "customer"), kept separate from your files, and are not counted as documents to answer from.

**The bot answered one question wrongly. Where do I look?** Click Log, the Recent conversations tab. The source line under each turn says which file it took the answer from, so you can fix exactly the right place.

**The bot says "I have no information" although the documents clearly cover it?** Usually the cause is a long file with no headings, or a document using words quite different from what people ask (the document says "hoàn trả" (refund), the asker types "đổi trả" (return/exchange)). Add headings to the file, or write the names people often use into that very passage.

**Does the bot remember the people who messaged?** Yes, each person has their own conversation thread in the bot's brain.

**I dropped the bot into a group and tagged its name and it does not answer, but direct messages work?** Type **`/id`** in that very group: the bot will answer and state the cause. Three causes produce exactly this one symptom: the group has not been enabled (click **Allow this group** on the bot card), Telegram's privacy mode is still on (see [Telegram's privacy mode](#telegrams-privacy-mode-read-this-if-the-bot-is-silent-in-a-group)), or the bot has not been able to ask for its own identity (turn the bot off and on). If even `/id` gets no response, the bot is not running; look at the status dot on the card.

**The bot is set to "answer every message" but still only answers when named?** Telegram's privacy mode is still on, it blocks on Telegram's side so Jarvis 007 never sees those messages. Turn it off at @BotFather (`/setprivacy`, then Disable) or make the bot a group administrator, then turn the bot off and on. The bot card reminds you when it is in this situation.

**Tagged the bot in a Zalo group and it is silent?** Check in this order:

1. The bot is on, the status dot is green, and the Zalo connection is still signed in on the Connections page.
2. **Whether the group has been allowed.** Look at the waiting list on the bot card; if you see the group, click **Allow this group**. If no group shows up, the reading loop has not received messages from the group: open the Bot inbox and see whether group messages arrive.
3. **The bot recognises a tag by name.** The text after "@" must match the Zalo connection's label (the Connections page) or the account's display name. If they differ, change the connection label to match the display name. If you choose **Auto-judge**, the bot still catches questions covered by the documents even when it does not recognise the tag.
4. If someone has just typed manually from that account in the group within 10 minutes (or the bot's yield minutes), the bot yields. A bot that has a yield-minutes number set still answers a message that tags it directly at once.

**If I shut down Jarvis 007, does the bot still run?** No. The bot runs inside the Jarvis 007 process, so the machine/VPS must be on. When Jarvis 007 comes back, every bot that was on runs again by itself.

## See also

- [Agents and Workflows](07-agents-va-workflows.md) - writing an Agent to be the bot's brain.
- [The Telegram channel](11-telegram.md) - your personal Telegram bot, entirely different from the bot here.
- [Second Brain](13-second-brain-bo-nho-wiki.md) - creating a brain and loading documents for the bot to read.
- [Security and accounts](14-bao-mat-tai-khoan.md) - how tokens are encrypted.
