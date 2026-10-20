# The Chatbot page has two tabs: Inbox and Bots (0.65.9)

## Problem

The project owner (30 Sep 2026): the "Bot channels" section and the "Create chatbot" section should be merged into one, "so people do not have to choose which channel a chatbot goes into, it is
hard to understand". The page had three tabs (Bot inbox, Bot channels, Create chatbot). To get a bot answering on Zalo you had to: go to the Channels tab and Add a channel; go to the
Create chatbot tab and click New bot; then tick the channel you just added. The two tabs also pointed at each other ("Create a bot" on the channel side, "Connect a new channel" on the form side).

## Decisions (approved through two rounds of mockups)

- **Two tabs**: Bot inbox and Bots. The old tab ids `kenh` and `chatbot` still lead to Bots (`TAB_CU`), because `console.js`, notifications and bookmarks still call them.
- **The Bots tab = the bot list (chatbots.js) + a "Channels without a bot" section (conversations.js)** right below.
  - Channels that ALREADY have a bot show as chips on the bot card. Telegram/Zalo Bot chips are clickable: they open the channel edit panel (label, token, brain), which now also has a **Delete channel** button
    (previously on the channel card, but a channel card that already has a bot no longer exists). A personal Zalo chip is read-only (it is a connection on the Connections page).
  - The "Add a channel" chip on a bot card opens the Edit form directly at the channel-picking step.
  - The channels section: channels without a bot, the "Show all brains" switch, and the Add a channel button. It opens by itself when there is a channel to handle and folds by itself when there are none; if the user clicks, their choice wins.
- **New bot form**: a channel already staffed by another bot is DIMMED with a lock, showing the name of the bot holding it (and the brain if it differs from the open brain). Previously the form hid it entirely.
  The server additionally supplies `tai_khoan_ban` in `GET /chatbots`. A locked row has no tick box and does not carry the `cb-tk-o` class, otherwise it would be counted as a selected channel.
- **Icons**: the robot was criticized as ugly. The tab uses `headset` (the "Create chatbot" icon already used it), the Agent chip uses `user-round`, the "Automatic" button in the Inbox uses `sparkles`,
  and the empty screen uses `headset`. Studio and Partners stay unchanged.
- **Keep the brain model** (the key point): a bot belongs to exactly one brain; Telegram/Zalo Bot have an owner brain; personal Zalo is a global connection so every brain sees it;
  each channel has only one bot on duty no matter which brain the bot is in.

## Spots where functionality is easily lost (canaries already exist in `tests/js/test_chatbot_hai_tab.js`)

1. Editing/deleting a channel that already has a bot must keep a way in (a clickable chip), otherwise the token can no longer be changed.
2. While "Show all brains" is on, the channels section also lists channels staffed by a bot of ANOTHER brain: that bot does not show on this page, so there is nowhere else left to edit or delete it.
3. After deleting a channel the tab must be rebuilt so the chip of the just-deleted channel disappears.
4. `ht-bot` is the old class name of the bot picker in the Inbox (a test guards against it coming back), so the element wrapping the Bots tab is named `ht-tab-bot`.

## Out of scope

- No change to the channel/bot API, no change to the brain model, no merging of data stores.
- The channel card (`theTK`) keeps its old mold inside the "Channels without a bot" section.

## Testing

`test_chatbot_hai_tab.js` (source canary), `test_chatbot_tai_khoan_ban.py` (server), the old JS tests updated for the new tab names; a real run on the
sandbox build with sample bots and channels: two tabs, the channel edit chip, the Add a channel chip opening the form at the channel step with the locked row, "Create a bot for this channel", fold/open, auto-fold when channels run out,
"Show all brains", the old tab ids, an empty inbox going to the Bots tab, and the 375px phone layout with no horizontal overflow.
