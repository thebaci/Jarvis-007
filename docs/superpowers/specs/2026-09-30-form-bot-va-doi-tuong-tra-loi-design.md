# A leaner bot form and choosing "who the bot answers"

Date: 2026-09-30
Status: design settled (the owner approved the sketch in chat), being implemented in 0.64.85
Continues: [2026-08-bot-chuyen-trach-spec.md](../../dev/2026-08-bot-chuyen-trach-spec.md), 0.64.82 (bot in Zalo groups, Auto-judge)

## Problem

The project owner commented that the Edit bot form is "complicated, with a lot of surplus", and that it is missing exactly the most important
thing: **choosing who the bot answers**. Specifically:

- The form is longer than two screens, and every field comes with an explanation longer than its label.
- A private chat always answers everyone. For groups there is only one box for pasting ids, hidden in "More settings". There is no
  way to pick individual people, and no way to say "answer everything on the channel".
- The terminology is confusing ("What the bot answers from", "Agent", "brain"); the risk warning takes up a whole screen.
- 0.64.83 removed the on-duty person field but the bot card still shows the label "no recipient set".

## Decisions

### 1. The "who the bot answers" model (`audience`)

Three values, and a list of people (`people`) parallel to the existing list of groups (`groups`):

| `audience` | Private chat | Groups |
|---|---|---|
| `all` "Every chat on the channel" | everyone | every group the bot is in |
| `nhom` "Anyone in private, groups I choose" (**default**) | everyone | only groups in `groups` |
| `chon` "Only people and groups I choose" | only people in `people` | only groups in `groups` |

- `nhom` is exactly the behavior up to now, so **an old record without an `audience` field is read
  as `nhom`** and nothing changes.
- The remaining cases are all fail-closed: setting an unknown value **keeps the old value** (same rule as
  `muc_quyen`); a record that HAS an `audience` field but with a corrupt value is read as `chon` (the narrowest);
  people and groups not in the list stay silent. Erring toward silence means the owner sees the bot silent and fixes it;
  erring toward open means the bot talks to strangers under a real person's name.
- In allowed groups (every group with `all`), the bot still follows `reply_when` (mentioned / Auto-judge /
  every message). `audience` answers "where it may speak", `reply_when` answers "when it speaks up".
- A chat that is NOT yet chosen gets absolute silence from the bot (no canned sentence: a personal Zalo account is a real
  person), but it shows up in a **pending-approval list** right inside the form and on the card, with an Allow button.
  The pending list now contains both groups and people (previously only groups).
- Choosing `all` must go through a confirmation: on a personal account it would answer friends and family too.

### 2. Picking people and groups from the Inbox

No pasting ids. `GET /chatbots/chats?account_ids=..&q=..` returns the known chats of the channel
account (taken from the `conversations` store), each row: id, display name, kind (group / person), last message
time, and a "pending approval" flag if the bot has seen it but it is not yet allowed. The form draws two tabs Groups / People, a search
box, and ticks to choose. A chat not yet in the Inbox (a newly joined group, nobody has messaged) can still be declared
by id in the "Add by id" box folded under the list.

### 3. The form: one scroll, four sections

1. **Who the bot is**: bot name, Agent (+ New Agent). The channel shows as a "Answers on ..." chip with Change.
2. **Who the bot answers**: three selection cards (radio cards) + a pick list + a "In groups, the bot speaks when" field
   (Mentioned / Auto-judge / Every message). The speaks-when field shows only when groups are in play.
3. **What the bot answers from**: a two-choice button (Agent and documents / Documents only), one line.
4. **What the bot can do**: a three-level button, one description line. The warning shows only when raising the level, kept to two lines
   with "Show all risks"; the risk confirmation box stays as it is.

"Advanced" (folded): reply language. The separate step 1/2 is dropped once an account exists (kept when creating a new bot with no
channel chosen). Every long explanation is cut to one line; the long explanations move to the docs.

### 4. The bot card

One line "Answers: <audience summary>", chips for channel/Agent/permission level; a warning shows only when there is a real
problem; On/Off and Edit stay outside, Log / Conversations / Delete go into the "..." menu. The label "no recipient set"
is dropped (nowhere left to set it), and so is the model line.

## Architecture

- `chatbot_store`: the `audience` field (`AUDIENCE = ("all", "nhom", "chon")`, default `nhom`) and
  `people` (a list of ids like `groups`, same `_clean_groups`). Added to `_PATCHABLE`.
- `chatbot_runtime._ly_do_im`: private chat follows `audience`; groups follow `audience` then `reply_when`.
  Adds the silence code `nguoi_chua_chon`. `_NHOM_CHO` additionally keeps `chat_type`; the precheck also records people not yet chosen.
- `main.py`: `POST /chatbots/{id}/people` (allow/remove one person, like `/groups`),
  `GET /chatbots/chats`. `nhom_cho` returns `chat_type` too.
- `dashboard/chatbots.js` + `style.css` + i18n: rebuild `moForm`, `the`.

## Testing

Python: `_ly_do_im` for all 9 cells of the table above, an old record is still `nhom`, an unknown value, the pending list including
people, the chats/people API, an end-to-end try with personal Zalo (a person outside the list stays silent, a person in the
list gets an answer). JS: a structural canary for the form (four sections, three cards, no old fields), complete vi/en i18n.
Run the real server on a separate port to inspect it by eye.

## The fourth card: Automate everything (0.65.2)

The project owner wanted an "automate everything" choice in the Who the bot answers section. It is **a single pick that bundles two settings**, not a new
stored value: `audience = all` plus `reply_when = auto` (Auto-judge decided by the arbiter). Design consequences:

- No server change, no record change. The selected card is derived from the record (`all` + `auto` shows this card), so a bot set up like this
  earlier shows the right card again when reopened.
- Choosing this card HIDES the "In groups, the bot speaks when" button (already decided, so two places do not say two things). The "Every chat" card drops
  the Auto-judge option from that button, because Auto-judge for every chat is exactly the new card. The groups/people cards keep all three choices.
- The same risk-confirmation gate as `all` (`can_xac_nhan_doi_tuong` in the store still blocks a second time). If `all` is already saved, switching to this card
  does not ask again. The confirmation text also mentions that chat text is recorded for learning, matching the arbiter's explanation line.
- A channel with no groups (Zalo Bot): the card is hidden like the "Every chat" card, because the arbiter only makes sense in groups.
- The bot card says "automate everything" in place of "every chat · auto-judge group messages".
- The default stays "Anyone in private, groups I choose".

## Not doing (deliberately)

- No change to the `reply_when` mechanism, limits, or Auto-judge.
- The on-duty-person switching code behind the scenes is not removed (bots already set keep running), only removed from the UI.
- Choosing by people labels/tags (a VIP customer group...) comes later.
