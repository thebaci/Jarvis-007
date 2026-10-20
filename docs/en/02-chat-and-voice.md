# Chat & voice

*[Tiếng Việt](../02-tro-chuyen-va-giong-noi.md) · **English***

This is where you spend most of your time with Jarvis 007: type and Jarvis 007 answers in text, or click the mic to call Jarvis 007 and it speaks out loud. This page covers the whole chat frame, from keyboard shortcuts, slash commands and the buttons under each message to picking a voice and asking Jarvis 007 to generate images.

If you have not finished the first-run setup, read [Getting started & first-run setup](01-getting-started.md) first.

## What this feature is

One place to work with Jarvis 007:

- Type messages like any chat app.
- Click the mic to call Jarvis 007 and talk like on a phone call; Jarvis 007 sends automatically when you stop talking.
- Jarvis 007 answers in text; during a call it also speaks out loud.
- Attach files or images to a message for Jarvis 007 to read.
- Jarvis 007 embeds images, files, diagrams and HTML pages back into its answers so you can view them in place.
- Watch the knowledge globe react to sound (it lights up while listening and while speaking).

Answers are produced by **the engine you selected**, not Claude by default: Claude Code, ChatGPT (Codex), OpenRouter, OpenAI API, Anthropic API or Google Gemini API. The small badge next to the CONVERSATION label shows the engine and model that ACTUALLY ran that turn. Every engine can call Jarvis 007 tools and data sources through the MCP Hub, not just Claude. Details in [Models & engines](10-models-and-engines.md).

While Jarvis 007 thinks, an activity chip appears at the bottom of the chat with three bouncing dots, a status line ("Jarvis 007 is thinking...", "✓ Data received, analysing...", "✍ Writing the answer...") and a seconds counter (the number only appears from the third second onward).

## Where to find it in Jarvis 007

There are **two** chat surfaces sharing one conversation, so switching between them loses nothing.

### The main "Jarvis 007" screen

Left navigation rail, group **Assistant** → item **Jarvis 007**. This is also the default screen when you open the dashboard (port 7777 by default), so it is already open when the page loads.

| Area | Position | Contents |
|---|---|---|
| VAULT | Left column | The folder tree of the selected brain, a **Find note...** box, two filter modes **Name** / **Content**, and three buttons **＋** (new file), **📁** (new folder), **⟳** (refresh the tree) |
| Knowledge graph + status | Centre | The note network, the status line (READY, LISTENING...), and the **AGENTS** / **SKILLS** / **WORKFLOWS** counters at the bottom |
| CONVERSATION | Right column | Chat history, the engine badge, and the **⛶** button that opens the Chat page |
| Composer | Bottom | One rounded card: attachments, the text box, then a row with **＋**, the model chip, the Effort chip, the Fast mode bolt, the pinned folder chip (when there is one), the mic and the send button (which becomes a stop button while a turn runs) |

The left column **no longer** holds a grid of business metric cards; it is the vault explorer, and clicking a note opens it for editing right there (see [File manager](05-file-manager.md)). Clicking the AGENTS / SKILLS / WORKFLOWS numbers jumps straight to the matching page in the **Capabilities** group.

### The dedicated "Chat" page

Rail, group **Assistant** → item **Chat**. This is a full-screen chat page with no globe and no vault tree:

- The left column is the **conversation history** (reopen, search, rename, delete old sessions).
- The top bar reads **Chat with Jarvis 007**, with the engine badge on the right.
- The chat area, attachment chips, model bar and input are **the same** elements borrowed from the Jarvis 007 screen, so messages, pending attachments and the running turn all stay intact.

Use this page when you want the full width just for chatting. To see the globe and the folder tree again, go back to **Jarvis 007**.

## How to use it (step by step)

### Step 1 - Type a question

1. Click the input box at the bottom (the one that reads "Talk to Jarvis 007, type here, or drag and drop a file...").
2. Type your question.
3. Press **Enter** to send. To add a line break inside the same message, press **Shift + Enter**.
4. Or click the send button (the arrow) at the right end of the input bar.

Jarvis 007's answer streams into the CONVERSATION column on the right, character by character.

### Step 2 - Call Jarvis 007 by voice: click the mic button

The mic button (the large microphone on the left of the input bar) **calls Jarvis 007**, like a phone call:

1. Click the mic button once. It turns red and becomes **Hang up**, and a **call bar** appears right above the chat: the call path (for example **ChatGPT Live**), the status (Listening, Jarvis 007 is speaking, Working, Waiting), a call timer, a **Mute** button and a **Hang up** button.
2. Talk naturally. Both sides appear as normal chat bubbles, so tables, files and task results still show in full.
3. To interrupt while Jarvis 007 is speaking, just talk; Jarvis 007 stops reading to listen. The answer it was writing is still finished in the chat. Talking while Jarvis 007 is answering does not stop it either: what you said is kept and Jarvis 007 answers it right after the current answer. The call only stops when you hang up.
4. To end the call: click **Hang up** (on the call bar or the mic button itself), or press **Esc**.

Jarvis 007 picks the call path itself: **ChatGPT Live** when your ChatGPT plan is connected, then Live with an API key if you have one, otherwise the **Basic** path (browser listening, Edge voice). If ChatGPT Live cannot start, the call switches to Basic and says so in one line. The Space bar no longer opens the mic.

The first time you use the mic, the browser asks for microphone permission. Allow it. If you deny it, Jarvis 007 cannot hear you and reports that the page needs microphone permission.

During a call, when you start talking Jarvis 007 **pauses** what it is saying to listen. If you really speak a sentence within 2 seconds, Jarvis 007 stops for good and your next message carries the sentence it was cut off in, so it continues from there instead of starting over. If it was only a cough or a noise, Jarvis 007 resumes where it paused. The mechanism measures loudness on the echo-cancelled mic stream (about 0.5 seconds of continuous speech, clearly louder than the room), so Jarvis 007's own speaker output does not interrupt it. This is always on.

Interrupting only works while the **mic is open**. With the mic off, a noise in the room will not reopen it even while Jarvis 007 is speaking.

### Step 3 - Hear Jarvis 007 answer out loud

During a call, Jarvis 007 **speaks every answer** out loud. The graph pulses along with the voice.

- Hanging up (the **Hang up** button, the mic button or **Esc**) silences it at once.
- Typed chat outside a call is answered in text only.
- There is no separate speaker button or voice switch any more: the call decides whether Jarvis 007 speaks.

To change the voice, go to **Settings → Voice**, see **Voice settings** below.

### Step 4 - Stop Jarvis 007 mid-answer

While Jarvis 007 is thinking or speaking, the send button turns into a **stop button** (a square). Clicking it aborts the running turn and stops the speech immediately, and the status returns to READY. Typing **`/stop`** and pressing Enter does exactly the same.

**Esc hangs up; it does not stop the answer.** Esc turns off the mic and silences the voice, while the answer keeps being written and appears as text. Esc also closes any open popup. The "(Esc)" hint on the stop button is leftover text from an older build.

The stop button only stops **the session you are looking at**; other sessions running in the background continue. See [Sessions](04-sessions.md).

### Sending more while Jarvis 007 is working

From 0.206.0 you can keep typing and sending while Jarvis 007 works, like in Claude Code or Codex. As soon as there is text in the box, the send button comes back next to the stop button (tooltip "Send to the work in progress"); Enter works too on a computer. The running work is **not stopped**:

- With Claude Code and the API-key brains, Jarvis 007 reads the new message at its **next step** (after the tool call in progress) and acts on it. A correction is applied at once; a new task is taken on as well, in parallel where possible, and both are answered.
- From 0.213.0 Codex (ChatGPT plan) also reads the new message within the turn, like Enter in the Codex app itself: a message sent while Codex runs a command joins the next step, and one sent while Codex writes its final answer makes Codex do one more round in the same turn to cover it. To go back to the old way (the message waits for the next turn), set the environment variable `JAVIS_CODEX_STEER=0` and restart Jarvis 007.
- With Grok Build and Antigravity CLI (which run in one go and take no input mid-way), or when Jarvis 007 is already writing its final answer, your message **runs as the next turn** as soon as the current work ends. Nothing is lost.

A small line under the message you sent says where it is: "Jarvis 007 will read this at its next step", "Jarvis 007 has read this", "Jarvis 007 will do this right after the current task" or "Jarvis 007 is working on this now". You can send several in a row; Jarvis 007 reads them in order. To drop the current work altogether, press stop as before.

From 0.213.0 the same goes for Telegram, Discord, Slack, Lark, Messenger and Zalo. Before, the bot replied "Still on the previous message, send /stop" and dropped yours. Now it answers with one short line, "↪ Got it, Jarvis 007 reads this at the next step of the current work" or "📥 Got it, Jarvis 007 handles this right after the current answer", and then works in the two ways above. /stop ends the current work and drops what was waiting. Customer-facing bots (human mode) keep their old way: no reply line, and follow-up messages are merged into the next turn.

## Slash "/" commands in the chat box

Typing **`/`** opens a command menu just above the input box, and it works **at the start of the box or mid-sentence**.

Three session commands lead the list:

| Command | Name in the menu | What it does |
|---|---|---|
| `/new` | New conversation | Start a new conversation |
| `/reset` | Reset session | Clear the context and start over |
| `/stop` | Stop | Stop the running answer |

On the web build, `/new` and `/reset` both open a new conversation.

Right below are **twelve system commands** (see the next section), followed by **all skills of the selected brain**, each row showing `/slug`, the skill name and a one-line description.

Controlling the menu:

- Keep typing to narrow the list. Slug matches rank ahead of name matches.
- **Arrow up / down** to move, **Enter** or **Tab** to confirm, **Esc** to close. Clicking a row works too.
- Picking a **session command**, or a **system command that needs no extra text**, runs it immediately, no Enter needed. `/plan` and `/goal` need you to type more, so picking them only fills in `/plan ` or `/goal `.
- Picking a **skill** inserts `/slug ` **exactly at the cursor**, keeping the text on both sides; keep typing, then press Enter to send.

When you send a skill command, Jarvis 007 turns it into a prompt: "Use the skill `<slug>` for this request: ... If no skill by that name exists, just handle my request normally."

### Calling a skill mid-sentence

You do not always think of the skill before you write. Write the request first and type `/` where it fits: *"test using a skill mid-chat `/notes`"* runs the `notes` skill with the **remaining text** as the request. Text before and after the command is merged into the request, so *"write me `/notes` about the meeting"* becomes the request "write me about the meeting".

A few rules so nothing is misread as a command:

- The `/` must sit **at the start of the message or right after a space**. That is why `https://example.com/notes` and `3/4 of a cake` are never read as commands.
- Mid-sentence, the command name must be a **real skill** in the selected brain. `/home/user/notes` or `/does-not-exist` go through as plain text.
- With several commands in one message, the **last one** wins (your latest intent). A command at the very start of the box always takes absolute priority.
- **The three session commands (`/new`, `/reset`, `/stop`) and the twelve system commands only run at the start of the box**, and the menu does not suggest them mid-sentence: writing half a message and accidentally hitting `/reset`, losing all the context, hurts more than it helps. If a skill happens to share a name with a system command, the command wins at the start of the box, while mid-sentence the skill can still be called as before.

Skill details are in [Skills](06-skills.md).

### System commands

These are handled by **Jarvis 007 itself**, not borrowed from Claude Code, so they behave the same whichever brain you use (Claude Code, ChatGPT, Grok, Antigravity or an API engine). The result shows up as a tinted bubble right in the chat; that bubble lives only on your screen, is not sent to the model and is not saved into the conversation.

| Command | What it does |
|---|---|
| `/help` | Lists the session and system commands |
| `/status` | The engine and model running for this conversation (pinned to it or following the main model), the brain, message count, latest context size, whether it is answering, the version |
| `/model` | Opens the model picker. Type `/model model-name` to switch directly: an exact match switches at once, several matches are listed for you to choose from instead of guessing |
| `/brain` | Lists the brains. Type `/brain name` to switch (if the name matches several brains, Jarvis 007 asks again) |
| `/retry` | Sends your last message again |
| `/usage` | Tokens and cost Jarvis 007 has measured today and all time, plus the OpenRouter balance when a key is set |
| `/tasks` | Background tasks that are running, waiting for review, blocked or queued. Warns you when "Auto-run" is off (tasks then just sit and wait) |
| `/compact` | Compacts a long conversation right now, see below |
| `/plan the-task` | One read-only turn that proposes a plan and does nothing outside |
| `/memory` | Index of the selected brain's long-term memory, with clickable entries |
| `/export` | Downloads this conversation as a markdown file |
| `/goal the-target` | Jarvis 007 keeps working on its own until the target is met, see below |

#### `/compact` - compacting a conversation

The longer a conversation grows, the more each turn costs and the more it blurs. Jarvis 007 already compacts by itself past a large threshold; `/compact` lets you do it **now**. How it works depends on the conversation's brain, and Jarvis 007 always says what it actually did:

- **API engines** (OpenRouter, OpenAI, Claude API, Gemini, Groq): older messages are folded into a summary, and only the last two question-and-answer turns are kept as they are. From the next turn Jarvis 007 sends the summary instead of the whole history.
- **Engines on a subscription plan** (Claude Code, ChatGPT/Codex, Grok): the bulk sits in the thread the engine keeps itself (tool results, its inner loop), not in the history Jarvis 007 stores. `/compact` drops that thread; on the next turn Jarvis 007 opens a fresh one and reloads the saved history. There is no summary step because a subscription has no API key to make a separate summary request.
- Under 4 messages, or when the brain keeps no thread of its own (Antigravity rebuilds from history every turn), Jarvis 007 says plainly that there is nothing to compact.
- It is refused while the conversation is answering: compacting mid-turn would change the history under a turn that is reading it.

#### `/plan` - plan only

Type `/plan tidy the warehouse at month end`: Jarvis 007 reads the data it needs, then gives a short plan (goal, steps, what needs your approval, main risks) and asks whether you want to go ahead. That turn is **not allowed** to write files, send messages, post, create orders, change ads, queue background tasks or set reminders. Only when you agree in the next message does Jarvis 007 do it for real.

The strength of the block differs by brain, so to be exact: with **Claude Code, Grok and Antigravity**, the `/plan` turn runs at the `suggest` permission level, so the tool gate really blocks any outside action. With **ChatGPT (Codex) and the API engines**, there is currently only the instruction inside the message, not a per-turn gate.

#### `/goal` - work until it is met

Type `/goal every order from today is reconciled`. Jarvis 007 does one round, checks with real data whether the target now holds, and if not it **sends the next round itself** without you nudging it. Each round leaves a short note saying what is still missing.

Jarvis 007 proposes "done or not", but **whether to keep going is decided by code**, so a target that can never be met does not become an endless token-burning loop. The automatic rounds stop when:

- the target is met;
- **8 rounds** have run without meeting it;
- two rounds in a row report exactly the same thing missing (no progress);
- Jarvis 007 asks you a question that needs your decision;
- a round fails, or Jarvis 007 does not say whether the target was met;
- **you type a new message, press Stop, open another conversation or type `/goal clear`** - your words always come first.

It runs inside the **chat tab that is open**: closing the tab or reloading the page stops it. Unlike `/plan`, `/goal` does real work (within the permissions you gave Jarvis 007), so write a concrete target that can be checked.

#### On Telegram

Telegram already had `/status`, `/model`, `/brain`, `/retry`, `/skills`, `/agents`, `/workflows`, `/reset` and `/stop`. It now also has `/usage`, `/tasks`, `/memory` and `/plan the-task`, working the same way with plain-text replies. On Telegram `/plan` is only an instruction (no gate at the hub); `/compact`, `/goal` and `/export` are web-only.

## When Jarvis 007 asks back with buttons

When Jarvis 007 has to guess a parameter and guessing wrong would hurt (which period, which shop, which channel), it asks back and attaches a row of buttons under the answer bubble:

- One question line, optionally with a short topic label in front.
- At most **4 option buttons**, plus an **"Something else…"** button.
- Clicking a button sends **exactly the text on that button** as your message. "Something else…" sends nothing and just puts the cursor in the box for you to write.
- Labels longer than 40 characters are trimmed with an ellipsis; whatever text the button shows is exactly what gets sent, never something different.

Only the **newest** button row is clickable. Once you answer (by clicking or typing), every older row freezes, and scrolling back to click does nothing. Jarvis 007 always writes the question in words too, so you can type an answer without touching the buttons.

## Attaching files in chat

You can put files or images into a message for Jarvis 007 to read. Three ways:

1. Click the **paperclip** button (next to the mic) and pick files. Multiple files are allowed.
2. **Drag and drop** files from your computer onto the Jarvis 007 window (an overlay shows the drop zone).
3. **Paste** directly with Ctrl + V.

Pasting has one trick of its own: pasting an **image** attaches it as a file as usual, while pasting **very long text** (over 1500 characters or over 25 lines) into the chat box makes Jarvis 007 package it as an attached `.txt` file instead of stuffing the whole thing into the input. Jarvis 007 still reads all of it, and the screen only shows a tidy chip. This applies to the chat box only; other inputs still take plain text.

Files appear as small chips above the input bar. Wait for the chip to report the upload finished, then type or speak your request and send as usual. Click the ✕ on a chip to drop that file from the message.

Important, in terms of how Jarvis 007 handles files:

- **Default: read only.** Jarvis 007 reads the file (looks at images and describes them) and answers, and saves **nothing** anywhere. The drag-and-drop overlay label that says files are saved into Sources is old text; the real behaviour is read-only.
- **It only saves when you ask clearly.** To have Jarvis 007 store a file in the Second Brain, say so in the message, for example "save this to sources", "ingest this" or "write this into the second brain". Only then does Jarvis 007 convert the file into a note and save it in the vault's Sources folder. See [Second Brain: memory, Wiki, INGEST](13-second-brain.md) and [File manager](05-file-manager.md).

## The "open file" chip: what you are editing becomes an input to the conversation

Besides attachments there is a second kind of chip: when you open a text file in the editor (see [File manager](05-file-manager.md)), Jarvis 007 pins that file to the chat as an orange chip reading "open, click to keep editing".

It differs from an attachment chip in two ways: there is only **one** pinned chip (opening another file replaces it), and it **does not disappear after you send**, because that file is an input to the whole conversation rather than a one-off payload. That is why you can say "clean up the overdue section" or "write me a closing paragraph" without naming the file, and Jarvis 007 still knows which file you mean and writes straight into it.

The pinned chip is also a **way back**: click it and the file reopens in the editor exactly where you left off (if it is already open, the view simply scrolls to it without reloading, so unsaved text survives). Click **✕** on the chip to unpin it.

## Jarvis 007 shows images, files and artifacts inside answers

The reverse direction works too: Jarvis 007 can put images and files from the brain straight into an answer.

- **Images**: Jarvis 007 writes `![description](attachments/image-name.png)` and the dashboard renders the real image in the chat bubble. Click the image to open that exact file in the **Files** page.
- **Other files** (pdf, docx, xlsx...): Jarvis 007 writes a markdown link that opens the file in the Files page.
- **Paths in backticks** such as `Javis/loops/morning-report.md` also become links that open the file.
- **Wikilinks** `[[Note name]]` become Wikipedia-style navigation links: clicking one makes Jarvis 007 find that note in the vault and open it.
- Images that **can no longer be loaded** (expired from the cache area, deleted by hand or renamed) render as a grey box reading **"Image expired"** instead of a broken icon. The brain's `attachments/` and `inbox/` folders are cache areas: they are cleaned after 30 days or when they hit the 300MB ceiling.

### Artifact blocks

Long or visual content does not flood the chat frame; it collapses into a tidy **artifact card**:

| Type | Card label | When it becomes an artifact |
|---|---|---|
| HTML page | HTML page | A ```` ```html ```` block, or content starting with `<!doctype html>` / `<html>` |
| SVG image | SVG image | A ```` ```svg ```` block, or content starting with `<svg` |
| Mermaid diagram | Diagram | A ```` ```mermaid ```` block |
| Long source code | Code + language name | A code block of 24 lines or 800 characters or more |

The card also shows the line count and a "click to view" hint, with an **Open ▸** button on the right. Clicking the card opens a panel on the right of the screen with:

- Two tabs, **Preview** and **Source** (long code only has the source tab).
- A **⧉** button to copy the source, a **⇩** button to download it as a file, and a **✕** button to close the panel.
- Pressing **Esc** also closes the panel.

Mermaid diagrams need a rendering library fetched from the internet; offline, the panel says the library could not load and shows the source instead. ```` ```dataview ```` and ```` ```tasks ```` blocks do not become artifacts; they run and render as result tables, see [Tasks & Dataview in notes](19-tasks-and-dataview.md).

## Asking Jarvis 007 to generate images

Jarvis 007 generates images right inside the chat using **the ChatGPT plan you signed into** (OAuth), with no extra OpenAI API key. Just ask in words, for example "make me a photo of a fish sauce bottle on a wooden table, dark background, landscape".

Under the hood, Jarvis 007 calls the `javis_generate_image` tool (from the bundled `image-chatgpt` plugin) with three parameters:

| Parameter | Values | Default |
|---|---|---|
| `prompt` | The image description, the clearer the better (required) | none |
| `aspect_ratio` | `square` (1024x1024), `landscape` (1536x1024), `portrait` (1024x1536) | `square` |
| `quality` | `low`, `medium`, `high` | `medium` |

Generated images are saved into the selected brain's `attachments/` folder, then Jarvis 007 embeds `![...](attachments/...)` in the answer so you see it in place. Because `attachments/` is a cache area that expires after 30 days, copy anything you want to keep into another folder in the brain.

A few things to know:

- **You must connect ChatGPT first.** Without it, the tool answers plainly that ChatGPT (OAuth) is not connected and points you at the **Models** page to sign in. See [Models & engines](10-models-and-engines.md).
- Image generation is a `safe`-level action (it writes a file and spends quota), so background work running in read-only mode will not generate images on its own.
- AI-generated images carry provenance marks (Content Credentials). **Settings → Interface & Brain → AI image provenance** has **Keep marks** / **Strip marks**; the default is to keep them.
- Outside chat you can call it directly through `POST /image/generate` with the fields `prompt`, `aspect_ratio`, `quality`, `brain`.

## Summarising YouTube videos

Paste a video link into the chat and say what you want, for example "summarise this video for me" or "does this video mention the price". Jarvis 007 reads the video's **captions** and answers from the actual dialogue, with timestamps for each main point.

It accepts every link shape: `youtube.com/watch?v=...`, `youtu.be/...`, Shorts, live links, links carrying a playlist or a timestamp, and links buried in the middle of your sentence.

Under the hood, Jarvis 007 calls the `javis_youtube_read` tool (bundled `youtube-read` plugin). This is a **read-only** action, so background work in read-only mode can summarise videos too, and it runs on **every engine**, including the six API engines that cannot open web pages themselves.

A few things to know:

- **A video with no captions cannot be summarised.** Jarvis 007 says so plainly rather than guessing the content from the title. Most Vietnamese and English videos have machine captions, but a video posted minutes ago may not have them yet.
- **Private, age-restricted or region-blocked videos** cannot be read either, and Jarvis 007 names which of those it hit.
- **"YouTube suspects this server is a robot" is not a problem with your video.** The root cause is **IP reputation**: YouTube flags hosting-provider IP ranges, so the same video opens fine at home but gets challenged on a VPS. Jarvis 007 rotates through eight player types before falling back to yt-dlp, so most such cases pass on their own. Seeing that message means all nine routes were refused.
  - Trying again a few minutes later usually works, because YouTube throttles in waves.
  - If it repeats, the server IP is heavily flagged. The definitive fix is to set the environment variable `JAVIS_YOUTUBE_PROXY` to a residential proxy and restart, see [.env configuration](16-env-configuration.md). Only YouTube traffic goes through it.
- **To see exactly which route failed**, run this on the server:
  ```
  python server/youtube_read.py <video link>
  ```
  It tries each route in turn and prints a table: which lived, which died, what reason YouTube gave, and whether yt-dlp is installed. One run tells you the diagnosis without guessing.
- **Long videos get truncated.** One read takes at most about 40,000 characters of dialogue (enough for a 60 to 90 minute video). Beyond that, Jarvis 007 says which minute it reached; say "keep reading" and it continues.
- **For captions in another language**, say so, for example "read the English track". By default Jarvis 007 prefers captions matching the interface language, then English, and always prefers human-made captions over machine ones because human captions carry punctuation and summarise better.
- Machine transcripts often get proper nouns and figures wrong. For numbers that matter, open the video at the timestamp Jarvis 007 cites and check.

## The button row under each message

Hovering over a message (yours or Jarvis 007's) reveals a small button row underneath. On phones, **tap** the message to show it.

| Button | Tooltip | What it does |
|---|---|---|
| Timestamp | The full date, for example "Wednesday, 29/07/2026 14:05" | Display only |
| ↻ | "Send this again" (your message) or "Answer the question above again" (Jarvis 007's message) | Resends the original text as a NEW turn at the end of the conversation, deleting nothing from the old turn |
| ✎ | "Edit and send" | Only on your messages. Loads the original text into the input for editing; it does **not** send by itself |
| ⧉ | "Copy content" | Copies the whole message; the button briefly reads "✓ Copied" |

Common points:

- While a turn is running, ↻ dims and cannot be clicked, which prevents overlapping turns.
- Messages with only an image and no text have no ↻ or ✎ buttons (there is nothing to resend).
- Messages saved before timestamps existed simply hide the time rather than showing a made-up current time.
- **Long** messages of yours (over 10 lines or over 900 characters) collapse, with **Show more** / **Show less** buttons.
- Every code block has its own **⧉ Copy** button in the corner.
- If you have scrolled up to reread something while Jarvis 007 answers, the chat does NOT jump down; a **↓ New messages** button appears at the bottom to jump when you are ready.

## Choosing a model, Effort and the engine badge

The row under the text box holds three controls side by side:

- **Model chip**: shows the short name of the provider and model in use. Clicking it opens a picker with a **Find model...** box and a provider list, each expanding into its models. Providers that are not configured show a 🔒 with the line "+ Add an API key on the Models page to unlock".
- **Effort chip** (thinking depth): separate from the model chip because you change it more often. Clicking it opens a six-stop slider **Off / Light / Medium / High / Extra / Ultra**, with "Faster" on the left, "Smarter" on the right and "Recommended" under Medium. Drag it or use the arrow keys, Home and End. Antigravity models that carry the level in their name (e.g. `-high`) lock the slider.
- **Fast mode bolt**: click to turn it on and the bolt starts an orange wave; click again to turn it off. There is no on/off label; hover to see "Fast mode" and a cost note for the selected brain. Brains or models that do not support it show a dimmed bolt.

  | Brain | What Fast mode does | Notes |
  |---|---|---|
  | Claude Code | Turns on Claude Code's fast mode | Opus 5.5, Opus 5, Opus 4.8 only; billed to usage credits at twice the price |
  | Anthropic API | Sends `speed: "fast"` | Opus 5.5, Opus 5, Opus 4.8 only |
  | ChatGPT (Codex) | Runs the Fast tier (`priority`) | With the bolt off Jarvis 007 forces the normal tier, even when the model or the Codex config defaults to Fast |
  | OpenAI API | `service_tier: "fast"` | |
  | OpenRouter, Gemini | `service_tier: "priority"` | Gemini: Tier 2/3 accounts only |
  | Grok, Antigravity, Groq, DeepSeek, Ollama | None | Dimmed bolt |

  When a provider refuses Fast mode (account not eligible, limit reached), Jarvis 007 resends at normal speed and the turn does not fail; hover the bolt to see why. Background runs (loops, reminders, Kanban, teams) always run at normal speed.

The badge next to **CONVERSATION** (and in the top right of the Chat page) shows the **real** engine and model of the last turn, taken from the server rather than from what the model claims about itself. If the badge disagrees with what you expected, trust the badge.

On phones, the model chip moves into the header and the picker opens in the middle of the screen.

### Pin a working folder

**Pin working folder** in the **＋** menu lets a conversation work right inside a folder, for example a code project. The list shows the folders in the brain with a search box; the last row, **Browse another folder...**, picks a folder outside the brain.

- Once pinned, a 📁 chip with the folder name appears next to the bolt. Hover for the full path; click to change it or **Unpin**.
- The pin is **per conversation**: a new conversation starts in the brain as usual. Pinning on an empty chat carries the folder into the conversation from its first message.
- CLI brains (Claude Code, ChatGPT via Codex, Grok Build, Antigravity) run commands right inside that folder. API brains read and write files through the brain's tools, so they work with folders **inside** the brain; a folder outside the brain only works with CLI brains.
- The Coding page uses the same chip instead of its own folder button. The branch, worktree, restore point and permission chips stay on the Coding page.

## How Jarvis 007 formats answers

Since version 0.26.9, answers in the web chat are written for **eyes**, not for ears:

- Short paragraphs of 2 to 4 sentences, then a line break, instead of unbroken prose.
- Lists of 3 or more items use bullets.
- **Bold** on figures, proper nouns and conclusions, the things you scan for.
- Long answers with several distinct parts get a heading per part.
- Tables when comparing the same set of fields across several items, for example revenue for three channels by week.

Before that, Jarvis 007 was told to write flowing prose because it was often used by **voice**. That trade-off is gone: the voice **strips markdown** (headings, bold, bullets, links, code blocks) before reading aloud, so formatting that looks good on screen does not trip up the voice.

Short questions still get a one-sentence answer. Formatting exists for readability, not to make every answer look like a report.

Plain-text channels are stricter because they cannot render: **Telegram** and **Zalo** have no markdown tables, and the **terminal** has no tables, inline images or markdown links. All three still use ordinary bullets. See [Telegram](11-telegram.md) and [CLI in the terminal](24-cli.md).

> If Jarvis 007 still answers in long prose: most likely the brain's long-term memory still holds an old fact such as "dislikes markdown tables, prefers short spoken prose" from when you used voice, and that memory is loaded into **every** turn. Open `memory/MEMORY.md` in the **Files** page, find the line about answer style, and delete it along with the matching file in `memory/facts/`. See [Second Brain, memory & wiki](13-second-brain.md).

## Voice settings

Everything about the voice lives in **Settings → Voice**. The page is a single card, and every field saves itself as soon as you change it; there is no Save button.

The card holds two things:

- **The "Using: ..." line**: the call path in use, **ChatGPT Live**, **Live (provider name)** with an API key, or **Basic**. On Basic it also says which brain gives quick replies, for example Antigravity CLI on your Google plan.
- **Jarvis 007's voice**: the list depends on the call path, see below.

When Jarvis 007 had to fall back to a lower path, the "Using" line says why and what to do, for example connect ChatGPT on the **Models** page, install Codex CLI, or update Codex CLI to 0.153 or later.

### Jarvis 007's voice

The voice list depends on the call path:

- **ChatGPT Live**: 9 voices, juniper (default), maple, spruce, ember, vale, breeze, arbor, sol, cove. **▶ Preview** plays a recorded sample.
- **Live with an API key**: that provider's voices, with no preview button.
- **Basic**: 7 free Edge voices, Emma (default), Hoài My, Nam Minh, Ava, Andrew, Brian, William. With an OpenAI API key on the **Models** page you also get the 11 OpenAI voices (alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse). Last in the list is **Your ElevenLabs voice**. **▶ Preview** reads a sample sentence.

Picking a voice also picks the provider (Edge, OpenAI or ElevenLabs). The Edge voice and the speaking rate are stored on this device; updates do not overwrite the voice you picked.

If a paid voice fails (quota used up, wrong key, no network), Jarvis 007 reports the error so you can retry or pick another voice. It does not switch voices on its own.

### Advanced

- **Call path**: **Automatic (recommended)**, **ChatGPT Live**, **Live with an API key** or **Basic**. Automatic tries ChatGPT Live, then Live with an API key, then Basic. If you pick a path that is not ready, Jarvis 007 uses the next one and says why on the "Using" line.
- **Quick-reply brain**: **Automatic** (default, shows the brain in use), **Main brain (same as typing)**, or a specific brain; one that is not installed or has no key is marked "(not ready)". This box (with its **Model** box) only appears while calls run on the Basic path, including when Automatic falls back to Basic; see **The Basic path and quick replies**. On ChatGPT Live or Live with an API key the Live model listens and replies itself, so the box is hidden.
- **Model**: the model of the brain in use, for example `gemini-3.8-flash-low` for Antigravity or `haiku` for Claude Code. The default is the provider's model. Each brain remembers its own model, so switching between brains never mixes up model names. Hidden when Main brain is picked.
- **Speaking rate**: 0.85× to 1.45×, default 1.10×. Shown only on the Basic path.
- **ElevenLabs API key** and **Voice ID** (from ElevenLabs → Voices): shown only when the ElevenLabs voice is picked. Leaving the key box empty keeps the saved key.

OpenAI voices need an OpenAI API key on the **Models** page; the voice page no longer has an OpenAI key field.

### ChatGPT Live: call Jarvis 007 on your ChatGPT plan

**ChatGPT Live** uses the ChatGPT plan you connected on the **Models** page, no API key needed. Jarvis 007 picks this path itself when the ChatGPT plan is connected and the machine has Codex CLI 0.153 or later; there is nothing to select.

- Press the mic to start talking: Jarvis 007 listens continuously, answers in under a second, and you can interrupt at any time.
- Small talk gets an instant answer. Anything that needs real data or an action (revenue, calendar, email, files, opening a page) is handed to the main brain you chose (Claude or another), which works with all your MCPs and tools; Jarvis 007 reads back a summary and the full result (with tables) appears as a chat bubble. The spoken summary does not show up as a second bubble.
- If you add something like "ok, tell me when it's done" while Jarvis 007 is working, it does not start over. A remark with something new (for example "add the cancelled orders too") is handled right after the current task.
- Change the voice in **Jarvis 007's voice** (9 voices, see above).
- Audio goes straight from the browser to OpenAI, so it works even when Jarvis 007 runs on a VPS.
- Calls count against your ChatGPT plan's usage.
- Mid-call, Jarvis 007 does not switch to another path (and another voice) on its own. If reconnecting fails, it tries once more; if that fails too it shows one line and waits, and speaking again makes it retry.

### Live with an API key

Without ChatGPT Live, Jarvis 007 uses **Gemini Live**, **OpenAI Realtime** or **OpenAI GPT-Live**, with the Gemini or OpenAI API key you pasted on the **Models** page. Expressive voices, natural interruptions, and a two-way transcript in the chat. When real data is needed, the model hands the work to the main brain in the background and keeps talking, then relays the result (the Gemini 3.1 line still waits silently because Google does not support background work yet).

### The Basic path and quick replies

The Basic path listens through the browser and speaks with the voice you picked. Ordinary spoken turns get a quick reply in 1 to 2 seconds from a voice brain (the "fast lane"). Jarvis 007 takes the first voice brain available on a plan you are already signed in to, in this order:

1. Antigravity CLI
2. ChatGPT (via Codex)
3. Claude Code
4. Grok Build

If none is available, spoken turns go to the main brain. Questions that need data, files or tasks are still handed to the main brain, all in the same conversation. To choose yourself, change **Quick-reply brain** under **Advanced**; a brain you chose in an older version is kept.

### Listening ear: Vietnamese mixed with English

On the Basic path the browser only hears one language, so a Vietnamese sentence like "Mở dashboard Facebook ads" (open the Facebook ads dashboard) often comes out as "Mở double Facebook add". The **listening ear** is a multilingual model that listens to the audio of what you just said again before settling the text in the bubble. The browser's interim text still shows instantly while you talk.

- Jarvis 007 always picks the ear itself: **Groq Whisper** when a Groq key is on the **Models** page, otherwise the browser's text as before.
- Measured on 20 Vietnamese-English mixed commands: the browser got 41% of words wrong, the Groq ear 14%. Each sentence takes about 1 second longer.
- If the ear fails, takes over 8 seconds, or returns a sentence far from the draft (Whisper sometimes invents sentences from noise), Jarvis 007 keeps the browser's text and the turn is not lost.
- The message sent is the ear's text when there is an ear, otherwise the browser's text when you finished the sentence. Once sent, the AI does not rewrite the message in history.

### Handled by the machine

- **Long silence pauses the line, speaking resumes it**: on a ChatGPT Live call, after 30 quiet seconds Jarvis 007 pauses the connection to save plan usage and the call bar says "Waiting, just speak to continue". Just keep talking, no need to say its name: Jarvis 007 starts reconnecting as soon as it hears your first few words, so it usually answers about 2 seconds after you stop talking. A TV or someone nearby speaking clearly also resumes it. Since 0.65.22 there is no "Focused conversation" switch.
- **The screen stays on during a call**: phones cut the microphone when the screen locks, so during a call Jarvis 007 keeps the screen from turning off; hanging up lets it sleep as usual. Pressing the power button still ends the call.
These fields were removed from the page because the machine decides them:

- **Read answers aloud**: removed because it duplicated the mic. During a call Jarvis 007 speaks every answer; hanging up (the **Hang up** button, the mic button or **Esc**) mutes it. Typed chat outside a call is answered in text only.
- **Listening language**: follows the interface language (an English interface listens in `en-US`, otherwise `vi-VN`). Mixed Vietnamese and English is handled by the listening ear.
- **Send after silence**: fixed at 1.2 seconds. A level you picked earlier on that device is still used. Jarvis 007 still waits longer after "và", "nhưng", "thì" (and, but, then) or a comma, and saying "khoan" or "đợi chút" (wait, hold on) still makes it wait.
- **Interrupt Jarvis 007 by voice**: always on.
- **Conversation timing (experimental)**: removed entirely.
- **Listening ear**: always picked automatically, see above.
- **Conversation mode** (Standard, Fast lane, Live): replaced by the call path. The voice brain is now **Quick-reply brain** under **Advanced**.
- **Often-misheard words**: Jarvis 007 builds the list itself from the assistant name and the names of connected MCPs. Words you saved earlier are still used.

## Enlarging the chat

When you work in chat for a while on the **Jarvis 007** screen, click the **⛶** button in the corner of the CONVERSATION panel to jump to the **Chat** page: a full-screen chat, with the **conversation history** on the left (reopen, search, rename, delete old sessions, see [Sessions](04-sessions.md)) and the chat centred on the right for easier reading, with a taller input for longer writing.

To go back to the Jarvis 007 screen: click **‹ Shrink** in the Chat page title bar.

It is still **one single conversation**: chatting on the Jarvis 007 screen or on the Chat page is the same thread, the same model bar, the same attachment area. Since version 0.12.4, the enlarge button no longer opens a separate overlay; before that there were two nearly identical chat frames that behaved differently, which was easy to confuse.

## Asking for business numbers

The fixed grid of metric cards in the left column was removed in version 0.9.166. Previously, every time you opened the dashboard Jarvis 007 ran a scan of the connected sources to fill that grid, spending quota that mostly nobody looked at.

Now, when you want numbers, just ask in chat ("how is revenue today", "compare with last week"). Jarvis 007 calls the right connected source (POS, sales channels, ads...) and answers in words, so it only runs when you actually need it. Details about data sources are in [Connections & business data](09-connections-and-business-data.md).

## Charts, number tiles and buttons in an answer

When an answer is built on real numbers (revenue, orders, ad spend), Jarvis 007 can draw them right in the chat:

- **Charts**, bars or a line, for a trend over days or weeks (up to 24 points and 3 series).
- **Number tiles**: a few key figures with their change, drawn red when they fall.
- **Buttons** (up to 4) when it needs a quick choice from you, for example "Approve draft A" or "Redo it". A press sends that text as if you typed it; a button grants nothing.

Cards are drawn from data inside the answer, so reopening the chat shows them again. Telegram, Zalo and the terminal get a text version: a chart becomes one line of numbers per label, buttons become a numbered list you answer with a number. Text in a card that looks like an API key is masked before drawing.

## Jarvis 007 recalls earlier conversations

Start a new chat that refers to an old one ("carry on with the fish sauce landing page from last time") and Jarvis 007 searches your other chats in this brain and adds up to 3 short excerpts to the question for context. Only the owner's chats are searched (the main chat, chats with partners, Jarvis 007 Core); team chats, chatbots and customer conversations never feed it. The excerpts are not saved in the chat history. To turn it off, set `recall.enabled` to `false` in the settings.

## Voice notes

Ask Jarvis 007 to "read it to me", "send a voice note", or say you would rather hear a report than read it, and Jarvis 007 calls the `javis_voice_note` tool: a short spoken message (up to 1000 characters) is saved as an mp3 in the brain's `attachments/voice/`. The chat shows a player next to the link, Telegram receives it as audio, and Jarvis 007 still writes the words as text below. The voice is a free Edge voice picked by the language of the text.

Reminders also have a **Read it aloud** box: at the set time, the reminder or the report arrives with a voice note. If Jarvis 007 is open on a computer or phone, the voice note plays at once like a call (press play when the browser blocks autoplay).

To have Jarvis 007 **call you at a set time**, tick **Call me** (or say in chat "call me at 7am and read the sales report"). At that time an open Jarvis 007 tab rings and shows an incoming-call card with **Answer** and **Decline**. Answer starts the voice call just like the mic button (ChatGPT Live when it is set up, the basic voice otherwise): Jarvis 007 reads the reminder or report briefly, asks if you need anything else, and the call goes on as usual. Unanswered for 45 seconds, it counts as missed and the content stays in the chat. With no Jarvis 007 tab open nothing rings: Telegram gets the message like any other reminder. This is a call inside the Jarvis 007 app, not a call to a phone number.

## Keep the prompt cache warm (Claude Code, Pro/Max plan)

A Pro/Max plan keeps Claude Code's prompt cache for one hour. After a longer break, the next message reloads the whole conversation, which costs a lot of allowance on a long chat. On the **Token usage** page, the budget section has a **Keep the prompt cache warm** box: with it on, about 50 minutes after the last message Jarvis 007 sends one tiny request (no tools, nothing written to the conversation) that keeps the cache for another hour. It only runs within 2 hours of the last message, never while the chat is answering, and stops at once when the plan reports a usage limit or the cache has gone cold. It is still background use of the plan, so it is off by default.

## Using it on a phone

Below 860px wide, the interface changes to fit the screen:

- Navigation collapses into a drawer: tap **☰** to open it, then tap the dimmed background, pick an item or press Esc to close.
- The **model chip** and the **+** button (new conversation) move into the header.
- The **System** group (brain picker, light/dark toggle, the SYSTEM and MCP strips) moves to the bottom of the navigation drawer.
- The input shortens its placeholder to "Speak or type to Jarvis 007…".
- The **🕘 History** button in the header is hidden (the **Chat** page has the history built in).
- There is no speaker button anywhere: the call (the mic button) decides whether Jarvis 007 speaks out loud.
- There is no mouse to hover with, so **tap a message** to reveal its button row; tapping elsewhere hides it again.
- On the **Chat** page, the **🕘** button in the title bar opens and closes the history drawer sliding in from the left.

## What the status line in the middle means

The line under the globe says what Jarvis 007 is doing:

| Text shown | Meaning |
|---|---|
| READY | Idle, waiting for you |
| LISTENING | Listening to you |
| LISTENING • ALWAYS | On a call, the mic stays open |
| THINKING | The brain is processing the question |
| SPEAKING | Jarvis 007 is reading the answer aloud |

## Quick reference: buttons and shortcuts

Buttons around the chat frame:

| Button | Where | What it does |
|---|---|---|
| ＋ | Start of the button row | Open the menu: attach a file or photo, **pin a working folder**, pick a file from the brain, commands and skills "/", **Connections** (with health), **Assistants and workflows** |
| Mic | Next to send | Call Jarvis 007; during a call it becomes **Hang up** |
| Arrow | End of the button row | Send the message |
| Square | Replaces send while running | Stop the running turn and stop speaking |
| ⛶ | Corner of the CONVERSATION panel | Enlarge the chat |
| 🕘 History | Top right | Open the wide chat with conversation history |
| Engine badge | Next to CONVERSATION | The real engine and model of the last turn |
| Model chip | Button row under the text box | Change provider and model |
| Effort chip | Next to the model chip | Thinking depth slider |
| Bolt | Next to the Effort chip | Turn Fast mode on or off |
| 📁 Folder chip | Next to the bolt, only when pinned | The folder this conversation works inside. Click to change it or unpin |

Keyboard shortcuts:

| Action | Result |
|---|---|
| **Enter** | Send the message you typed |
| **Shift + Enter** | Line break inside a message |
| **Ctrl + V** | Paste an image, or paste long text as an attached .txt file |
| **Ctrl + U** | Pick files to attach |
| **/** (start of the input) | Open the command menu; ↑ ↓ to move, Enter or Tab to confirm |
| **Esc** | Hang up the voice call; close the command menu; close the artifact panel. Does **not** stop the answer |

## Tips

- To speak several sentences without Jarvis 007 sending early, call Jarvis 007 (the mic button) and talk continuously; only pause fully when you are actually done.
- To read in silence: hang up and type; Jarvis 007 answers in text only.
- Send several screenshots at once by dragging them all into the window; Jarvis 007 processes each one.
- If you normally speak English, switch the interface language to English (**Settings → General**): Jarvis 007 listens in the interface language.
- Feel free to paste a whole long article into the chat box: Jarvis 007 turns it into an attached `.txt` file and the chat stays tidy.
- To reask a question with a few words changed: click **✎** on the old message, edit it in the input and send, instead of retyping.
- The **⛶** button on the CONVERSATION panel and the **Chat** item in the Assistant group lead to the same place; use whichever is closer.

## Common problems

- **A sentence you never typed appears in the chat.** Almost certainly the mic picked up room noise (music, TV, someone talking), transcribed it and sent it, because Jarvis 007 sends as soon as a sentence ends rather than asking first. Look at the status line: **LISTENING** or **LISTENING • ALWAYS** means the mic is still open, so click the mic button or press **Esc** to close it. Jarvis 007 speaking does not reopen the mic after you hang up. To clear that stray message, start a new conversation; Jarvis 007 has no way to type into your chat box, and every background result appears as a bubble on the left.
- **The browser cannot hear.** Jarvis 007 reports that the browser does not support speech and suggests Chrome or Edge. Open the dashboard in Chrome or Edge.
- **The microphone does not work.** The browser is blocking microphone permission. Open the site permissions in your browser, allow the microphone, then reload the page.
- **Pressing Esc but the answer keeps appearing.** That is by design: Esc hangs up, turning off the mic and the voice, while the answer keeps being written as text. To stop the turn for good, click the stop button (the square) on the input bar or type `/stop`.
- **You cannot hear Jarvis 007.** Jarvis 007 only speaks during a call, so click the mic to call. If it is still silent during a call, check the system volume, then click "▶ Preview" in **Settings → Voice** to test speech on its own. If you use an OpenAI or ElevenLabs voice, check whether Jarvis 007 reported a voice error (quota used up, wrong key, no network); Jarvis 007 does not switch to another voice on its own.
- **Typing "/" shows no menu.** The menu only opens when "/" starts the input with no space after it. If there are still no skill rows, the selected brain has no enabled skills.
- **Clicking one of Jarvis 007's option buttons does nothing.** That row belongs to an older turn and froze when you sent a new message. Just type the answer instead.
- **An image in the conversation became a grey "Image expired" box.** The file lived in the `attachments/` cache area and passed 30 days, or was cleaned when the 300MB ceiling was hit. Ask Jarvis 007 to regenerate it, or next time copy important images into another folder in the brain.
- **A diagram does not render, only the code shows.** The diagram library is fetched from the internet; the machine is offline or blocked. The content is still intact on the source tab.
- **Asking for an image reports that ChatGPT is not connected.** Go to the **Models** page and sign into ChatGPT (OAuth), no API key needed, then try again.
- **An empty answer.** If the answer area shows a hint to retry or change model, the selected model may be having trouble. See [Models & engines](10-models-and-engines.md) to switch model or engine.
- **A file never finishes uploading.** Large file or slow network; the file chip reports the specific error (upload timeout, server error). Try a smaller file or check the connection.

## Related

- [Sessions](04-sessions.md) - save, reopen, rename and delete old conversations.
- [Skills](06-skills.md) - write and call skills with `/slug`.
- [Models & engines](10-models-and-engines.md) - the providers and how to switch engines.
- [Connections & business data](09-connections-and-business-data.md) - connect data sources to ask for real numbers.
- [File manager](05-file-manager.md) - the VAULT column and the Files page.
- [Tasks & Dataview in notes](19-tasks-and-dataview.md) - `dataview` and `tasks` blocks in answers.
- [Telegram channel](11-telegram.md) and [Zalo](12-zalo-agent-mcp.md) - chat with Jarvis 007 outside the dashboard.

Still stuck? See [Troubleshooting & FAQ](17-troubleshooting.md).
