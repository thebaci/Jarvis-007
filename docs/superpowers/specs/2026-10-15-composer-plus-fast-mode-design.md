# New composer: a "+" button, an effort chip with a slider, and a Fast mode lightning bolt

October 15, 2026. Request from the repo owner, with screenshots of the Claude and ChatGPT composers. The code map and
the Fast mode research were done by 9 agents reading in parallel (workflow `composer-map-fastmode`); the constraints
below come from that work.

## Goals

- A composer as compact as Claude's: **one rounded box**, a **"+"** button that gathers everything that can be "added
  to the message", and a menu that can be extended later without touching the composer.
- **Effort is separate from the model choice**: changing effort is a frequent action, and it must not force the user
  to open the model list and scroll to the bottom.
- **Fast mode** is toggled with one lightning-bolt button, like ChatGPT: on means orange with a shimmer running across
  it, off means static.
- The effects use the Jarvis 007 orange (`--accent`, #ff7a3c) and work in both the light and dark themes.

Success means: every existing action still works (typing, Enter to send, paste and drag-and-drop files, voice, model
selection, per-session model pin, the Chat/Coding/Workspace pages borrowing the composer, phones), and there is only
one control row left.

## Split into two PRs

1. **PR 1, UI**: the box, the "+" menu, the effort chip and slider, and a lightning-bolt button whose state is saved.
2. **PR 2, wire Fast mode into each brain** and read back the real state the brain reports.

PR 2 merges right after PR 1. Between the two releases the bolt saves its state but does not change speed, and the
tooltip says so.

## PR 1: layout

```
#bgStrip (background-job pill, unchanged, outside the box)
#modelBar (empty on the home page; the Coding page still inserts its context chip row here)
┌ #hudVoice.hud-voice ─────────────────────────────────────────────┐
│ #voiceFocusResume (kept, floats above the box)                    │
│ #attachBar (images, attached files: moved INTO the box)           │
│ <textarea id="chatInput" ... rows="1">                            │
│ .cp-row: [+] [#cpChips: model chip | effort chip | bolt] ··· [mic] [stop/send] │
│ #mbPop  #effPop  #plusMenu (popovers, open upward, inside the box)│
└───────────────────────────────────────────────────────────────────┘
```

- The root of the box is still `#hudVoice.hud-voice`. The `.hud-voice {` block in style.css keeps `align-items: flex-end`
  and keeps `border-radius` ahead of `background: var(--bg2)` (a test pins the order); add `flex-direction: column` and
  give children `align-self: stretch`. The corner radius grows from 18px to **24px** at the repo owner's request
  (sketch approved on 15/10): deliberately change the two tests that pin 18px (test_theme_tokens,
  test_o_chat_no_theo_chu) and the cp-css `.chatpage-slot .hud-voice` rule to match. The box is `position: relative`
  and has no `overflow: hidden` (popovers and #voiceFocusResume float outside).
- `#attachBar` moves into the box. Remove `"attachBar"` from `CHAT_NODE_IDS` (console.js), otherwise the Chat, Coding
  and Workspace pages pull it out of the box. `CHAT_NODE_IDS` keeps the order `callBar, chatArea, bgStrip, ...` and
  keeps `modelBar`.
- `#modelBar` stays as a sibling of the box (a test pins the id and its place in `CHAT_NODE_IDS`, and coding.js inserts
  chips into it). Write it inline as `<div class="model-bar" id="modelBar"></div>` with no whitespace, and add
  `.model-bar:empty { display: none; }`. The `.model-bar {` block keeps its text unchanged (a test pins it).
- The `#chatInput` textarea keeps its attributes (`id` first, `rows="1"`) and keeps the auto-grow code, IME handling and
  Enter-to-send.
- `#attachBtn` is removed. The app.js line that binds `getElementById("attachBtn")` needs a null check, and opening the
  file picker moves to a "+" menu item. `#fileInput` stays inside the box.
- `#voiceBtn` moves to the right and becomes a small 34px round button; it keeps its id, its 4 state classes
  `recording`, `handsfree`, `in-call`, `focus-waiting`, and its synchronous `click` listener (iOS audio unlock, screen
  lock). Shrink the pulsing glow to fit the new size; `.mic-big.in-call` stays red.
- `#stopBtn`/`#sendBtn` keep the show/hide behavior driven by `style.display` in `updateStopBtn()`.
- The box's thin border turns light orange when the input has focus (replacing the textarea's own border).

### Phones (<= 860px)

- `#mbOpen`/`#mbPop` still go to the top of the page as they do today (mobile-chat.js). The branch of `placeHeader`
  that returns to desktop changes where it puts them back: re-insert at the start of `#cpChips` (anchored before
  `#effBtn`), no longer `modelBar.firstChild`.
- The effort chip and the bolt stay inside the box (the page header has no room at ~375px).
- Drop the old `order` rules for `.hud-voice` on phones and rewrite them for the new layout: input on top, button row
  below.
- Keep `.cview .hud-voice { margin-bottom: 0; }` and `body.kb-open .hud-voice { margin-bottom: 6px; }` (tests pin them).

### Pages that borrow the box (Chat, Coding, Workspace)

- The cp-css rule `.chatpage-slot .hud-voice{ background:var(--bg2); ... border-radius:18px; }` keeps its text, adjusted
  to match the new box; no hard-coded colors (test_theme_tokens).
- The `edit-on` grid rules for `.attach-bar` and `.model-bar` keep their text (tests pin them); an empty row collapses
  on its own.
- workspace.js currently locks only `#chatInput` while the session is not ready: also lock "+", mic and send.

## PR 1: the "+" menu

New file `dashboard/composer-plus.js` (no Vietnamese in running code; text goes through i18n). One registry list:

```js
window.JavisComposerMenu.register({ id, order, icon, label: "i18n.key", hint, run(ctx) | submenu(ctx) })
```

Adding a feature later only takes a `register` call. Default items:

1. **Attach a file or photo** (Ctrl+U): `fileInput.click()`. The Ctrl+U shortcut (Cmd+U on Mac) is bound on the
   document with `preventDefault`, because the browser uses it for view-source; it does not run while another input
   besides `#chatInput` or the note editor has focus.
2. **Attach a folder**: a hidden `<input type="file" webkitdirectory>`. It skips `.git`, `node_modules` and hidden
   files, with a cap of **50 files** and a notice when exceeded. Files go through the existing upload path, at most 4 at
   a time. The folder structure is not kept (the `/upload` path stores files flat), and the notice says so.
3. **Pick a file from the brain**: a popover that searches by name (GET `/files/search?mode=name`); choosing a file
   attaches it to the message like any attachment but without uploading it again. This needs a small endpoint
   `GET /files/resolve?path=` that returns the absolute path after checking it is inside the brain root (blocks `..` and
   symlinks pointing outside). app.js exposes `window.JavisAttach = { upload, addBrainFile }`, and `addBrainFile` pushes
   into `pendingAttachments` with the existing `[File đính kèm ...]` block (Vietnamese for "attached file", a machine token kept verbatim).
4. **Commands and skills** (/): focus the input, insert "/" at the cursor, and fire an `input` event so chat-slash.js
   opens its menu.
5. **Connections ›**: a submenu built from GET `/connect/health` (plus names from the catalog), one status dot per
   connection; the parent row says "N need reconnecting" when there are any. Clicking a connection or "Open the
   Connections page" goes to the Connections page.
6. **Call an assistant or workflow ›**: a submenu that takes agents and workflows (GET `/agents`, `/workflows`);
   choosing one inserts the same token the "/" menu inserts for agents and workflows.

The menu opens upward from the "+" button, with arrow-key navigation, Enter and Esc; clicking outside closes it. The
"/" menu in chat-slash.js anchors to the box instead of the textarea so it does not cover attached images.

## PR 1: effort chip and slider

- An `#effBtn` chip next to the model chip, with the English label: **Off · Light · Medium · High · Extra · Ultra**
  (the stored values stay `off/low/medium/high/xhigh/ultra`; tests pin these words in model-picker.js). The labels live
  in i18n (`eff.*`), with the same English words in vi and en at the repo owner's request. The Ultra tooltip adds "max
  effort".
- The `#effPop` popover: an "Effort <label>" line, "Faster" and "Smarter" at the two ends, a 6-step bar, and a
  "Recommended" line under the Medium step. `role="slider"` with `aria-valuemin/max/now/text`, arrow keys, Home and End;
  both dragging and clicking work.
- Effect (new file `dashboard/effort-slider.js`, canvas): an orange streak fills up to the selected step, and sparkles
  drift inside the streak, denser and larger toward Smarter. It only draws while the popover is open;
  `prefers-reduced-motion` draws a static version.
- Saved with `saveModel({reasoning})` as before (effort is a global setting, not per session).
- The model picker drops the effort row at its bottom; the model chip drops the "Effort: ..." text.
- A model that already has effort built in (Antigravity, names ending in `-low/-medium/-high/-xhigh/-max`): the popover
  shows an explanatory sentence instead of the slider.
- Clicking outside or pressing Esc closes the popover; opening this popover closes the other one.

## PR 1: Fast mode lightning bolt

- A round `#fastBtn` button next to the effort chip, with `aria-pressed`. **No on/off text beside it**; on hover or
  focus a "Fast mode" tooltip appears with one note that depends on the brain:
  - Claude Code: "Billed to usage credits at twice the price, not to your plan limits."
  - ChatGPT/Codex: "Uses your plan limits 2.5 times faster."
  - API (Claude API, OpenAI, OpenRouter, Gemini): "Higher token price, about twice the standard rate."
  - A brain without Fast mode (Grok, Antigravity, Groq, DeepSeek, Ollama): the button is dimmed (`aria-disabled`, not
    `disabled`) and the tooltip says "This brain has no Fast mode."
- On: an orange background with a bright band running across continuously and a gently pulsing bolt. Off: gray border,
  static. With reduced motion, on is just a static orange background.
- Saved with `saveModel({fast: true|false})` into `settings.model.fast` (default `false`). The server needs its own
  branch in POST /settings because that path swallows unknown keys (main.py, next to the `reasoning` branch).

## PR 2: wire Fast mode into the brains

Each wiring goes next to where effort is already passed. Never send a model parameter that is not declared as accepted.

| Brain | How to turn it on | Notes |
|---|---|---|
| Claude Code (SDK) | `ClaudeAgentOptions(settings='{"fastMode": true}')`, merged with the settings already passed | only Opus 5.5, Opus 5, Opus 4.8; when off, pass nothing |
| Claude API | header `anthropic-beta: fast-mode-2026-02-01` + body `"speed": "fast"` | on 429/529, or a 400 saying "does not support the `speed` parameter", resend without `speed` |
| ChatGPT/Codex | `-c service_tier="fast"` in `_codex_do_sau` when the model declares tier `priority` | when off, force normal speed (the machine has `service_tier = "priority"` preset in `~/.codex/config.toml`); check with one real turn whether the value `"default"` is accepted |
| ChatGPT OAuth direct call (engine.py) | `payload["service_tier"] = "priority"` | |
| OpenAI API | `service_tier: "fast"` | on a 400 error mentioning `service_tier`, resend without it |
| OpenRouter | `service_tier: "priority"` | |
| Gemini | `service_tier: "priority"` | Tier 2/3 accounts only; on error, resend without it |
| Grok, Antigravity, Groq, DeepSeek, Ollama | none | dimmed button |

- `codex_models._chuan_hoa` keeps the `serviceTiers` field so it knows which models accept Fast mode.
- Reading back the real state: Claude Code reports `fast_mode_state` (`off|cooldown|on`) and
  `fast_mode_disabled_reason`; the APIs report `usage.speed` or `service_tier` in the response. Jarvis 007 remembers the
  last state per brain, and the bolt's tooltip reads it: "running at normal speed for now because the rate limit was
  exceeded", "turn on usage credits"...

## Testing

- Keep the tests that pin the composer green (the list from the code map: test_bo_badge_engine, test_call_bar,
  test_viec_nen_hien_ra, test_o_chat_no_theo_chu, test_lui_tien_note, test_theme_tokens, test_sua_md_giu_khung_chat,
  test_trinh_sua_de_len_cot_hoi_thoai, test_mobile_layout, test_do_sau_suy_nghi, test_model_theo_phien,
  test_linh_vat, test_voice_*, test_i18n...). Change a test only when the pinned text changes on purpose, and say why.
- New tests: "+" menu registry (order, run, submenu), folder filter (skips `.git`, cap of 50), `/files/resolve` blocking
  escapes from the root, the slider (value, keys, locked step), the bolt (saved, per-brain tooltip, dimmed button),
  POST /settings keeping `fast`; PR 2: each brain adds exactly the right parameter when on and none when off, and the
  resend path when rejected.
- Look at it in a browser: desktop light and dark, phone at 375px, the Chat, Coding and Workspace pages.
- Before pushing: run the whole JS test suite and the Python files that inspect strings of the changed files (lessons
  #648, #655).

## Out of scope

- Esc to stop the answer (the stop button says "(Esc)" but it does not exist yet), to be done separately.
- Keeping the folder structure when attaching a folder (needs a change to the `/upload` path).
- Per-session Fast mode (effort is also a global setting for now).
