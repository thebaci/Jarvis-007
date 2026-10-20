# Decluttering the chat screen on mobile - Design

Date: 2026-07-19
Status: design approved (mockup), about to be planned.

## Goal

On a phone, the Jarvis 007 chat screen is cluttered and the input box is tiny. Rework it along the lines of "chat first, as compact as possible" (agreed with the project owner): the input grows large, and everything secondary is gathered into one thin header and one drawer.

Scope: phone UI ONLY (narrow screens, 860px breakpoint - exactly where the app already counts as mobile). The desktop version (>860px) STAYS AS IS, untouched.

## Current state (why it is cluttered)

On narrow screens (`console.css` @media max-width:860px), the bottom of the screen stacks three control rows plus the phone's browser bar:
1. `.model-bar` (index.html:262): the model chip (`#mbOpen`) + the `.sysbar` strip (SYSTEM: Claude/TTS status + MCP). One row.
2. `.hud-voice` (index.html:285): the input `#chatInput` (textarea rows=1, flex:1) SQUEEZED into the same row as 5 buttons - big mic `.mic-big` (46px), attach `#attachBtn`, speaker `#ttsToggleBar`, stop `#stopBtn`, send `#sendBtn`. The buttons take almost the whole width, leaving the typing area a sliver -> this is the main culprit behind the "tiny input box".
3. `.rail` (nav, index.html:315): on mobile it becomes a 56px BOTTOM bar (`console.css:324-338`), scrolling horizontally through the `.rail-item`s (Workflows, Plugins, Tasks, Scheduled, Connections, Channels, Mode...).

The top header (`.hud-top`, 46px on mobile) is also crowded (brand + brain picker + metrics + tone switch + Studio + settings + speaker + reset).

## Design (approved via mockup)

Three blocks, all mobile-only changes (extra rules inside the @media plus a little JS). Reuse existing parts (the model picker `#mbPop`, the Alpine rail nav `$store.nav`) rather than writing new ones.

### Block 1 - Thin header (replaces the model row and the bottom bar)

On mobile, `.hud-top` is cut down to three things, evenly aligned in one row:
- Left: the **☰** button (`#navToggle`, mobile-only) that opens/closes the navigation drawer (Block 2).
- Middle: the **model chip** "Jarvis 007 · <model> ▾" - tapping it opens the existing `#mbPop` (change model + effort + engine). Decided approach: JS MOVES the existing `#mbOpen` button (and `#mbPop`) into the header on mobile, and puts them back into `.model-bar` on desktop (tracked with matchMedia). Because the original button is reused, the model text (`#mbModelTxt`) updated by `model-picker.js` stays correct, with no copy to keep in sync.
- Right: the **＋** button (new conversation) - reuses the handler of `#resetBtn` (reset = new conversation).

The old `.hud-top` buttons (brand, brain picker, metrics, tone switch, Studio, settings, speaker, reset) are hidden from the header on mobile and moved into the drawer (Block 2, "System" section). The old `.model-bar` (the whole row) is hidden on mobile; `.sysbar` on its own (SYSTEM/MCP - just status information) is hidden entirely on mobile.

### Block 2 - Navigation drawer (replaces the bottom rail bar)

On mobile, `.rail` is NO LONGER a bottom bar. It is replaced by a drawer sliding in from the LEFT:
- Hidden by default (slid out of view to the left). Tapping ☰ -> it slides in, with a dimmed backdrop over the chat.
- Tapping the backdrop / Esc / choosing an item -> it closes.
- Drawer contents: keep `.rail-nav` as is (Workflows, Plugins, Tasks...) + ADD a "System" section gathering the old header buttons (brain picker, Settings, tone switch, Studio, Reset, speaker on/off). Bring `.rail-top`/`.rail-foot` (brand + version) back into the drawer so it looks like a proper menu.
- Mechanism: an open-state flag (body class `nav-open` or `$store.nav.drawer`) toggled by ☰; the mobile CSS translates `.rail` based on the flag. Desktop behavior is not touched (desktop remains the left column with the old collapse button).

### Block 3 - Input box as a large rounded pill

On mobile, `.hud-voice` is wrapped into a rounded pill:
- Layout inside the pill: **＋ (attach, `#attachBtn`)** on the left | **`#chatInput`** taking almost the whole width | **mic (`.mic-big` shrunk to ~34px)** | **round send button (`#sendBtn`)** on the right. The stop button `#stopBtn` shows only while a run is in progress (taking the send button's place), as it does now.
- `#chatInput`: min-height ~40px, grows taller as you type a long message (higher max-height than now, e.g. 40vh), 16px font (prevents iOS zoom).
- The speaker button in the bar (`#ttsToggleBar`) is hidden on mobile (speaker on/off is already in the drawer's System section).
- Mic + send are ALWAYS visible (Jarvis 007 uses voice a lot); no mic/send swapping, to keep things simple.

## Out of scope

- No change to the desktop UI (>860px).
- No mic/send button swap based on content.
- No change to chat/engine/model logic - only moving buttons and restyling.
- No new settings screen - reuse the existing buttons/menus.

## Error handling / edge cases

- Drawer open: lock the background scroll (so the chat does not scroll behind it); the backdrop captures taps to close.
- The header model chip shares `#mbPop`: make sure the popover is positioned correctly below the header (not clipped) and closes on an outside tap.
- Landscape / tablet up to 860px: the layout is still one column, and the pill and header stretch with the width.
- A tall `#chatInput` must not cover the chat (the chat area shrinks accordingly).
- When the on-screen keyboard appears: the pill sticks to the bottom of the visible area and is not hidden by the keyboard (use a safe layout, avoid fixed positioning that causes jumping).

## Testing

- `node --check` on the JS files touched (the repo has no automated UI test framework).
- Manual smoke test at mobile width: resize the browser to ~375px (or use devtools mobile mode) and check: the header shows only ☰/model chip/＋; ☰ opens/closes the drawer + backdrop; the model chip opens the picker; the input is large and grows; no bottom rail bar; no SYSTEM strip. The desktop version (>860px) is unchanged.
- The project owner does a real smoke test on a phone (the Hostinger build) after it ships.

## Files expected to be touched

- `dashboard/index.html` - add the `#navToggle` (☰) + `#newChatBtn` (＋) buttons for the mobile header; possibly add the drawer backdrop; wrap `.hud-voice` if a pill layer is needed.
- `dashboard/console.css` (+ `dashboard/style.css` for `.hud-voice`/`.voice-input`) - all the new mobile rules: 3-button header, rail as a sliding drawer + backdrop, model-bar hidden/sysbar hidden, input pill.
- `dashboard/app.js` (or `console.js`) - wiring: ☰ toggles the drawer flag + backdrop + Esc; ＋ calls the conversation reset; make sure the mobile model chip opens `#mbPop`; move the System buttons into the drawer.
- Bump the `?v=` of the dashboard assets so the new version loads (as in earlier UI changes).
