# Chatbot (bot inbox, bot accounts, create a chatbot)

***Tiếng Việt** · [English](en/28-customer-conversations.md)*

Every message a customer sends to a **dedicated bot** (Telegram or Zalo Bot) and to a connected **personal Zalo account** is gathered into one inbox inside Jarvis 007. You read the exchange between the customer and the bot, see which chats the bot is stuck on, and **take over** a chat when a human is needed.

Since version 0.61.0 this page also holds the Chatbot section: **one item on the sidebar, two tabs** (Bot inbox and Bots; since 0.65.9, before that there were three tabs: Bot inbox, Bot accounts, Create chatbot), and you **reply to customers right inside the Bot inbox**.

## Where to open it in Jarvis 007

Left navigation bar, group **Capabilities**, item **Chatbot**. Inside the page there are two tabs:

- **Bot inbox**: every customer message, read back, take over, reply.
- **Bots**: the AI staff on duty for your channels, with a **Channels without a bot** section right below (Telegram bots, Zalo bots, personal Zalo... in the open brain, add a channel, turn recording on). A channel that already has a bot shows as a chip on the bot's card; click the chip to edit or delete that channel. See [Chatbot](25-chatbot.md).

Voice works too: "open the customer inbox", "bot inbox", "bot accounts", and "open chatbot" still land on the Bots tab. Saying just "conversation" still opens the Chat page as before.

## The model

Four concepts, read once and never guess again:

| | What it is |
|---|---|
| **Chatbot** | An AI employee: an Agent, its own brain, a permission level, and the channel accounts it is on duty for (one bot can serve several accounts). |
| **Channel** | Where customers write. Each channel has several **accounts**: a Telegram bot token, a Zalo Bot token, a personal Zalo account you scanned a QR code for. Later Zalo OA, Facebook, Web Chat. |
| **Conversation** | One exchange with one customer (or one group) on one channel. |
| **Bot inbox** | Where AI and humans run conversations together: read, take over, hand back to the AI. |

Underneath, every channel normalizes its messages into **one common event** and writes into one store: channel account, customer, conversation, message. The Bot inbox never needs to know whether a message came from Telegram or Zalo.

## The Bot inbox tab

Since 0.65.10 the top is more compact so the working area takes almost the whole screen: the **Chatbot** title, the two tabs, the search box and the filter row sit on top, and the list and the message pane fill the rest, each scrolling on its own with the reply box pinned at the bottom. The four number cards and the subtitle are gone. The **unread** count still shows as a badge on the tab, and "a human is handling it" is available in the **Status** filter.

The left column lists conversations, newest first. Each row: the customer (or group) name, the channel logo, the last message, the time, and the unread count. Above it there is a search box for names or text and **a row of filter dropdowns** (since 0.65.3, replacing the row of chips): **Bot**, **Status** (unread, needs a reply, I took over), **Type** (groups only or direct chats only), and **Channel** (shown only when there are two or more channels). The conversation count sits inside each option and is computed over the whole inbox, so it does not jump around when you filter. Filters are remembered in the browser; the line right above the list reads "N conversations · M filters" with a **Clear filters** button. When there are two or more bots, each row carries a bot name tag (each bot has its own fixed color), and notable rows carry a **Needs a reply** or **Human** tag.

**What "Needs a reply" means.** The customer wrote last, nobody has answered, no human has taken over, and either: it is a direct chat, or it is a group where the bot just **considered speaking and then stayed silent** (not sure enough, out of its self-reply allowance, or the judge failed, within the last 24 hours, and you have not pressed Right/Wrong yet). A group needs that second condition because the bot only speaks when called, so the customer having the last message in a group is normal; counting all of those would fill the filter with noise. This "bot considered" mark exists only when Auto-judge is on (see the reply judge section of [Chatbot](25-chatbot.md)).

**Groups keep only the latest 100 messages** (since 0.65.12). The inbox stores every message of direct chats with customers, but each **group** keeps just its 100 newest; older ones are deleted as new ones arrive. The reasons: the store does not grow forever, and Jarvis 007 does not keep strangers' words in a group longer than needed (a personal Zalo account in many groups records even the groups the bot is not allowed to answer in). The first time after updating, existing groups with more than 100 messages are cut down to 100; Jarvis 007 **backs up the whole store file once** before cutting (a `customer_conversations.sqlite3.bak-truoc-cat-nhom-...` file next to the store file) and **deletes that backup automatically after 14 days**. To get the cut messages back, copy the backup over the store file within those 14 days. A conversation's "messages ever received" counter does not go down.

**Loads gradually, no lag** (since 0.65.11). The list loads only the first 40 rows; scrolling near the bottom loads 40 more (or press **Show more**), and the counter reads "40+ conversations" until it runs out. The message pane works the same way: opening a conversation loads only the **latest** 40 messages, scrolling up near the top (or pressing **Show older messages**) loads 40 older ones and keeps your place. Every 5 seconds Jarvis 007 only asks for messages **newer than the last one** and appends them to the end of the pane; if you are reading older messages when a new one arrives the pane stays still, instead of pulling you back to the top as before.

Click a conversation and its message history opens on the right: customer messages on the left, bot replies and messages you sent yourself from your phone on the right. A failed bot turn sits there too, with its technical reason, so you can tell "the bot answered wrong" from "the bot is broken".

On a phone the page is a single column: tap a conversation to open its history, with a back button. The page refreshes itself every few seconds, with no need to reload.

## Reply, take over and hand back to the AI

**The Automatic | I reply switch** (since 0.65.4) sits at the top of every chat that has a bot, replacing the small Take over button. Flip it to **I reply** and you take over; flip it back to **Automatic** to hand the chat back to the bot. Pressing the position that is already on does nothing. On a phone the switch drops to its own row, full width. Right above the input box there is **one status line** saying who is on duty ("Mai is on duty in this chat" or "You took over, the bot is silent"), on a line of its own so it does not misalign with the input box.

**Two action buttons** sit right under the status line (since 0.65.5), the same height and splitting the width in half:

- **Reply for me**: the bot answers the customer's last message RIGHT NOW with its own Agent, even if the judge chose silence earlier. The reply is sent through the channel (a Zalo group gets a group-style message), recorded in the inbox as the bot's words, and the chat **stays on Automatic** (unlike typing by hand, which is a takeover). If that was exactly the message the judge stayed silent on, the bot also **learns one more case** (the "wrongly silent" label, the heaviest one): next time it meets a message like that, the bot will speak. It does not go through the "should I speak" gate, the judge or the self-reply allowance, because this is your own request; the Agent's permissions and limits stay intact.
- **Suggest a reply**: the bot writes a draft into the input box without sending it. You edit it and press Send (sending is a takeover). The draft **leaves no trace**: it does not enter the session store or the inbox, and the bot's temporary history is cleaned up, so if you discard the draft the bot does not "remember" having said it to the customer. It also works while you are in charge; if the input box already has text, it asks before replacing it.
- In **I reply** mode the first button becomes **Hand back to the bot**.

**A button that cannot be used yet still shows** (dashed border) and tapping it tells you why: you have taken over, the bot is off (the status line also says plainly "is off, so it will not reply on its own"), the last message is not from the customer, or the channel cannot send from Jarvis 007 yet. If the bot finishes writing but sending fails, the reply it wrote stays in the input box so you can send it by hand. If the Agent chooses silence, that is reported and nothing is sent. Each chat runs only one ask-the-bot turn at a time. Attachments the bot composes do not come along (text only).

Under the customer's last message there is a **"Bot stayed silent: reason"** line when the judge has recorded a reason (for example "Score below threshold (0.52 / 0.60)"), with a **Why** button that opens that bot's reply judge panel directly. The line only appears when the chat is on Automatic, the last message is the customer's, and the most recent decision was silence for exactly that message; when a human has taken over, the bot being silent is obvious, so it says nothing.

At the bottom of a conversation is the compose box: type and press **Enter** to send (Shift+Enter for a new line). The message goes out through the chat's own channel: a Telegram bot or Zalo Bot sends with that account's token, personal Zalo sends through the very account you scanned, **under your own name** (the compose box says so). A channel that cannot send from Jarvis 007 yet shows a line saying so instead of the box.

Sending from here in a chat that has a bot **takes the chat over**: the bot stays quiet with this customer until you flip the switch back to **Automatic**. Otherwise the customer would read two voices at once. Flipping the switch to **I reply** does the same without sending anything; after that you can also reply in the channel's own app.

Two things to know:

- A bot turn that is still being written at the moment you take over still sends that reply. Cutting off a message mid-send would confuse the customer more.
- Takeover is **per chat**, not a bot switch. Other customers keep getting bot replies.

## Channels without a bot (Bots tab)

Every account customers write to appears as **the same kind of card**, whatever the channel: channel logo and name, account name, state (running, off, error with the reason), the bot on duty, conversation and unread counts, and that channel's capabilities (join groups, send files, reply from Jarvis 007). No channel gets its own section, Zalo included. A channel added later simply shows up as one more card.

There are two kinds of account, differing in how you get them, not in how they look:

**Bot accounts** (Telegram, Zalo Bot) are a token. Press **Add a channel**, pick the channel type, paste the token, press **Check** so Jarvis 007 asks the platform that issued the token which bot it is, give it a display name and Save. A bot account records into the inbox while the bot on duty for it is enabled; with no bot on duty the card says so plainly and offers a **Create a bot for this channel** button that opens the New bot form with that channel already ticked. The **Channels without a bot** section lists only channels with no bot; it opens by itself when a channel needs attention and folds away when none does.

### Bot accounts belong to a brain (0.62.4)

Before 0.62.4 this section showed the accounts of **every** brain, because a Telegram token is a real account outside Jarvis 007 and so belongs to no brain. That was technically correct but hard to use: standing in your own brain and looking at a mixed list, you could not tell which ones were yours.

Since 0.62.4 each account has an **owner brain**:

- **An account belongs to the brain where you added it.** The section only shows accounts of the open brain.
- **The create-bot form also only offers accounts of that brain**, so cross-brain links can no longer be created.
- **The "Show all brains" switch** at the top of the section is for finding an account you added in the wrong place. Each card then names its brain, and the section also lists channels served by another brain's bot (that bot does not appear on this page, so this is the only place to edit or delete that channel). Personal Zalo is a connection on the Connections page, so it belongs to no brain and every brain sees it.
- **Changing the owner:** press **Edit**, then pick again under **Channel's brain**. Conversation history stays, because it is keyed by account id, not by brain.
- **Old accounts whose owner cannot be guessed** (no bot was serving them at upgrade time) are left **unassigned** and show in **every** brain with a note. This is deliberate: better to see one card too many than to have a token that exists with no screen showing it, that nobody can delete or reattach. Attach it to a bot and it takes that bot's brain.

Personal Zalo (`kind: account`) is not filtered: it is a connection on the **Connections** page, belongs to no brain, so it always shows.

This is the first step of a longer direction: splitting account management by brain, then agents, skills, workflows and chatbots, so that a multi-user edition becomes possible later.

**Deleting an account:** press **Delete**. If a bot is on duty for it, Jarvis 007 says plainly which bot, in which brain, then asks a single question: take it off that bot and delete it too? Agree and it is done in one go, with no need to switch brains and hunt for the bot to detach it by hand. The bot stays and keeps serving its other accounts. If it is the bot's **only** account, Jarvis 007 says so up front, and after deleting turns that bot off (the bot record stays; attaching another account turns it back on). Conversations already recorded stay in the inbox.

**Your own account** (personal Zalo) comes from the **Connections** page (QR scan in Zalo Agent MCP) and appears here with a **Record conversations** switch. Turn it on and Jarvis 007 reads new messages every 20 seconds through the MCP and writes them into the inbox. Three plain facts about this channel:

- **Off by default.** Turning it on keeps your Zalo session alive continuously through an unofficial API, meaning the account is signed in 24/7 on the machine running Jarvis 007. That is your choice, not Jarvis 007's. Use a secondary account.
- **Stored from the moment you turn it on.** No old history is pulled. Messages you send yourself from your phone (or that staff sharing the same account send) show as "You". For personal Zalo this needs Jarvis 007 0.108.0 or newer: earlier versions used javis-zalo 1.2.0, which dropped every message from the account itself out of the new-message stream, so messages you typed by hand never reached the inbox.
- **No bot on duty.** Replying from the Bot inbox sends under your own name. If you want this account to answer customers by itself, create a dedicated Bot and choose the personal Zalo channel (direct chats since 0.64.80, groups and Auto-judge mode since 0.64.82), see [Chatbot](25-chatbot.md).

## Where data lives and what is kept

The store sits in the Jarvis 007 state folder (`customer_conversations.sqlite3`), separate from the chat session store. **Text** is kept long term; images, files and voice messages keep only the message type and a description, and the original files follow Jarvis 007's cleanup schedule. A message read twice (after a restart, say) never creates a second row.

Deleting a bot does **not** delete its conversations, nor the channel accounts it served: customer history is your asset, a token is reusable. Bots created before 0.61.0 (token stored inside the bot) move to the account model automatically when you update; token, conversations and allowed groups are all kept.

## For anyone adding a channel

Since 0.61.0 everything the core knows about a channel lives in the **channel registry** (`server/channels/`, one file per channel). A channel file declares: id, name, logo key, kind (`bot` uses a token, `account` uses an existing signed-in session, `webhook` for platforms that call back), capabilities (groups, send text, send files), how to get a token; and a set of functions: token check and the long-poll transport (bot kind), listing accounts and turning recording on (account kind), `gui` to reply from Jarvis 007. Incoming messages are normalized into the common event (`channel`, `account_id`, `external_chat_id`, `sender_type`, `text`, `external_message_id`, `created_at`) and then the store is called.

Adding a channel = one file in the registry, one registration line, one logo in `icons.js`. The bot store, the supervisor, the API and both tabs pick it up; nothing else needs editing. Details in `docs/dev/2026-09-kenh-hoi-thoai-spec.md`. API routes:

- `GET /channels` channel types and capabilities; `GET /channels/accounts` every account, one shape.
- `POST /channels/verify-token`, `POST /channels/accounts`, `POST /channels/accounts/{id}/update`, `.../watch` (account kind), `.../delete`.
- `POST /conversations/{id}/ai-reply` (since 0.65.5): `mode=send` or `draft`; on error it returns a `code` (`human`, `bot_off`, `no_bot`, `already_answered`, `busy`, `no_message`, `send_failed`, `engine`).
- `GET /conversations` list with stats, filtered by `channel`, `bot_id` (`-` = chats with no bot), `account_id`, `q`, and since 0.65.3 `status` (`unread`, `need_reply`, `human`) and `chat_type` (`group`, `private`; an unknown value makes that filter ignored). It also returns `bot_name` and `need_reply` for each row, `facets` (counts for the dropdowns, over the whole inbox) and `bots` (bots that have conversations, with names).
- `GET /conversations/{id}/messages` message history; `POST /conversations/{id}/reply` reply through the channel.
- `POST /conversations/{id}/read`, `POST /conversations/{id}/mode` (`ai` or `human`).
- `GET /conversations/channels` and `POST /conversations/zalo/{conn_id}/watch` are old aliases, still served.

## Troubleshooting

- **Bot enabled but no conversations show**: the store only records from the moment the channel was connected; send the bot a test message. If it is still empty, press Log on the bot's card in the Bots tab.
- **Bot card says "No channel account yet"**: the bot is not on duty for any token. Press Edit, tick an existing account or paste a new token.
- **Sending from the Bot inbox fails**: the error text comes from the platform itself (token revoked, customer blocked the bot, Zalo session expired). A message that did not go out is not written to the store.
- **Personal Zalo shows a red error under Channels without a bot**: usually an expired QR session or a machine without Node.js 20. Go to the Connections page, check the Zalo connection, and rescan the QR if needed. The reader retries by itself after 90 seconds.
- **Flipped to I reply but the bot still answered once**: that turn was already running before the click. From the next message on, the bot stays quiet.

## Want more: the Customer management (CRM) pack

The Store has a **Customer management (CRM)** pack (`javis.khach-hang-crm`, needs version 0.60.1 or newer) that sits on this very inbox. Once installed, just ask Jarvis 007: "which customers have waited more than 2 hours without a reply", "what did Lan ask", "tag Lan as VIP", "how many new customers this week", "export the customers who asked for a price to Excel". It ships a customer-care assistant and a daily review workflow. The pack only reads the inbox and writes tags and notes on customers; it never messages anyone.

## See also

- [Chatbot (a dedicated bot)](25-chatbot.md)
- [The Zalo Bot channel](26-kenh-zalo-bot.md)
- [Zalo Agent MCP](12-zalo.md)
