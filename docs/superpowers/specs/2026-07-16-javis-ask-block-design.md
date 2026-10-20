# Ask-back block with choices in the Jarvis 007 chat window

Date: 2026-07-16
Status: design settled, waiting for an implementation plan

## Goal

When Jarvis 007 needs to ask the user a follow-up question, the chat window shows clickable
choices right under the answer, instead of making the user read the question and type the
answer themselves. The aim is to make the chat window feel familiar to people who already use
Claude Code.

This round covers ONLY the ask-back block. No tool timeline, no task list, no permission
requests. It works on every engine (Claude Agent SDK, Codex CLI, and the chat API engines).
The dashboard gets real buttons; Telegram gets a text version.

## Technical background

The chat window runs over WebSocket. The server pushes back `status` / `tool_call` /
`tool_result` / `stream` / `response` / `error` / `turn_done`; in the other direction the
client can only send one kind of text message (`{message, brain, session_id}`).

The project already has exactly one precedent for this: the `JAVIS_METRICS` block. Jarvis 007
embeds an HTML comment at the end of the response, `app.js:1126` strips it out with a regex
and pushes it into the left panel. This design follows the same trail.

Two existing details make this path cheap:
- `chat-render.js:246` already swallows every HTML comment, including a comment that is still
  unclosed while streaming. So the control block never flickers onto the screen midway.
- `app.js:160` already has the hook: `const { clean, cards } = extractMetrics(data.content)`
  right in the `response` handling branch.

## Chosen approach and rejected approach

Chosen: **a marker convention at the end of the answer**.

Rejected: **a real `javis_ask_user` tool through the MCP hub** (the model calls the tool, the
server holds the turn waiting for the user to click, and returns the result as the tool
result). This is how Claude Code really does it, and it allows asking mid-way while work is
in progress. Rejected because the price is too high for the usable part: the hub is HTTP, so
the session would have to be stuffed into the MCP config header for every turn (the config
file is currently cached per mode, not per session), timeouts have to be handled, the user
pressing F5 while the turn is waiting has to be handled, and it has to be built three times
for the three engine paths. Meanwhile, in the Jarvis 007 chat window almost every follow-up
question lands at the end of a turn anyway.

If mid-turn asking is really needed later, the tool approach can be layered on top: the chip
UI is reused as is, only the source that emits the question changes.

## Data contract

Jarvis 007 ends the answer with:

```
<!-- JAVIS_ASK: {"question":"Which period do you want to see revenue for?","header":"Period","options":[{"label":"This week","desc":"Last 7 days"},{"label":"This month","desc":"From the 1st"},{"label":"Vs last month","desc":"With comparison"}]} -->
```

- `question`: the full question, required.
- `header`: a short label for the topic, optional.
- `options`: at most 4 elements. `label` is the text on the button, `desc` is a one-line
  explanation.

One block is one question. Multi-select is not supported: in a chat window it is almost always
single choice, and adding multi-select means adding a confirm button for something rarely used.

This block and the `JAVIS_METRICS` block can live together in one response.

## UI behavior

The chips appear as one row under the answer bubble, inside the same message card. `desc` goes
in the tooltip so the chip row does not bloat. The last chip is always "Something else...":
clicking it sends nothing, it only moves the cursor down to the input box.

Clicking a chip sends exactly that `label` as a normal user message, in the same session. The
conversation history still reads naturally, there are no ghost messages, and Jarvis 007 does
not need to know whether the user clicked or typed.

**Only the last message has live chips.** Once the user replies (by clicking a chip or typing
a different answer by hand), the chip row freezes: the chosen one keeps a mark, the others
fade and can no longer be clicked. Reason: if you scroll back through history and can click
the questions from ten turns ago, it muddles the flow of the conversation. Session restore
after F5 follows the same rule: chips come back to life only if they belong to the last
message and have not been answered yet.

Chips only appear when the turn ends (the `response` event), not while streaming.

## Code architecture

**New: `dashboard/chat-ask.js`** (about 100 lines). It does exactly three things: strip the
JSON block out of the text, draw the chip row, catch the click event. It exposes
`window.JavisAsk`:

- `extract(text) -> { clean, ask }` pure, does not touch the DOM.
- `render(msgEl, ask, live)` draws the chips into the message card; with `live=false` it
  draws the frozen form.
- `freezeAll()` freezes every live chip row (called when a new message arrives).

It does not go into `app.js` because that file is already 1900 lines. This split follows the
trail the project is already taking with `chat-render.js`, `chat-zoom.js`, `voice.js`, and
lets the ask-back part be edited or tested without opening `app.js`.

**Edit `dashboard/app.js`**, exactly three places:
- the `response` branch: strip `ask` at the same time as `cards`, call
  `JavisAsk.render(..., live=true)`.
- `sendMessage()`: call `JavisAsk.freezeAll()` before adding the user bubble.
- `restoreSession()`: redraw the chips, keeping them live only on the last unanswered
  message. The ask is stored along with the turn record in `convo`.

**New: a server-side function that strips control blocks**, placed in `channel_context.py`
because that module is exactly where per-channel text handling lives and it already has pure
functions of the same kind (`extract_paths`, `collect_turn_files`); `main.py` already
imports it. The function strips every `JAVIS_*` block out of the text before returning to a
non-web channel, and is called at the end of `_tg_answer`. For `JAVIS_ASK` it substitutes a
numbered list:

```
Which period do you want to see revenue for?
1. This week
2. This month
3. Vs last month
```

The user just replies "1" and that is it. Jarvis 007 reads "1" in the context of the question
it just asked and understands, with no state to store. The Telegram bot already has inline
button infrastructure (`reply_markup`, `_handle_callback`) but it is not used this time.

**Edit `CLAUDE.md`**: teach Jarvis 007 when to embed the block, attached to the existing
"Clarify before answering" section rather than opening a new rule. That section already says
to ask back only when truly stuck, at most 1-3 questions. This block is the presentation
for that "ask back only when truly stuck" step. The typical use: having to guess a parameter
where a wrong guess does harm, for example the time period or which shop.

## Existing bug fixed along the way

The `JAVIS_METRICS` block **is leaking verbatim into Telegram** today. `_tg_answer`
(`main.py:4614`) returns the raw `out`, and `telegram_bot._send` calls `md_to_mdv2`, which
only escapes and does not strip comments. Verified by running `md_to_mdv2` directly: the
output contains the literal `<\!\-\- JAVIS\_METRICS: ...`.

This is an existing bug, but it sits exactly on the path of this design: the `JAVIS_ASK`
block would leak in exactly the same way if it were not handled. The control-block stripping
function above fixes both at once.

## Error paths

- Broken JSON: skip the block silently, still show the answer. A block with a syntax error
  must never swallow Jarvis 007's answer.
- Too many options: cut to 4.
- Label too long: truncate when drawing.
- Block in the middle of the text instead of the end: still stripped, because it is matched
  by regex, not by position.
- Labels are generated by the model so they cannot be trusted: escape everything when drawing.
- No `options` or an empty `options`: treat as no block.

## Tests

Pure, no browser needed:
- `extract()` with valid JSON, broken JSON, no block, too many options, empty options, a block
  in the middle of the text, and both `JAVIS_ASK` and `JAVIS_METRICS` present.
- The server-side stripping function: `JAVIS_ASK` becomes the right numbered list;
  `JAVIS_METRICS` disappears completely (a regression test for the leak above).

Manual click-through to confirm (DOM behavior):
- Chips appear after the turn finishes, with no flicker while streaming.
- Clicking a chip produces a user message with exactly that label, and Jarvis 007 carries on.
- Chips freeze after a reply; scrolling up through history, they cannot be clicked.
- After F5 and restore, chips come back to life only on the last unanswered message.
