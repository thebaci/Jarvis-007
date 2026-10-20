# Declutter the mobile chat frame - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On phones, make the chat input big and the screen less cluttered (drop the 2 cramped control rows), following the approved chat-first direction.

**Architecture:** Only add CSS rules inside `@media (max-width: 860px)` plus a little plain JS, and do NOT touch the desktop version. Reuse existing parts: the model picker `#mbPop` (event delegation in `model-picker.js`), the nav rail, the reset button `#resetBtn`. Three blocks: (1) the input becomes a large pill; (2) the rail becomes a left slide-in drawer plus a thin ☰/model/＋ header; (3) system buttons move into the drawer.

**Tech Stack:** Static HTML + CSS (`style.css`, `console.css`) + plain JS (`app.js`/`console.js`), Alpine (rail store). No build step. The Tabler font is not used (this is a standalone app, keep the existing SVGs).

## Global Constraints

- ONLY change the narrow-screen UI: every new rule lives inside `@media (max-width: 860px)`. The >860px (desktop) version STAYS AS IS.
- The mobile breakpoint is `max-width: 860px` (matches `isNarrow()` at `console.js:130` and the mobile rail block at `console.css:324`).
- Do not use the em dash character (U+2014). Displayed strings are in Vietnamese with diacritics.
- Reuse, do not duplicate: the model chip is the existing `#mbOpen` button itself; ＋ calls `#resetBtn` again.
- `#chatInput` keeps `font-size: 16px` (prevents iOS auto-zoom on focus).
- There is no automated UI test framework: when JS changes, run `node --check <file>`; check layout correctness with a smoke test at mobile width.
- Bump the `?v=` of the dashboard assets in the last step so browsers load the new version.

---

## File Structure

- `dashboard/style.css` - CSS for `.hud-voice`/`.voice-input`/`.mic-big`/`.send-btn` (original definitions ~486-525) + add the mobile block for the pill.
- `dashboard/console.css` - the `@media (max-width: 860px)` block (~324-354) that currently turns the rail into a bottom bar; change it into a drawer + add the mobile header rules + hide sysbar/model-bar.
- `dashboard/index.html` - add the `#navToggle` (☰) + `#newChatBtn` (＋) buttons to `.hud-top` (mobile-only) + 1 backdrop layer `#navBackdrop`.
- `dashboard/app.js` or `dashboard/console.js` - wiring for ☰ (toggle `body.nav-open` + backdrop + Esc), move `#mbOpen`/`#mbPop` into the header on mobile via `matchMedia`.
- Asset version bump: wherever index.html loads css/js with `?v=` (find it in the last step).

---

## Task 1: Large pill-shaped input (mobile)

This is the fix for the "tiny input" problem - highest value, lowest risk, so it goes first.

**Files:**
- Modify: `dashboard/style.css` (add a mobile block after the `.hud-voice` rules ~525)

**Interfaces:**
- Consumes: the existing `.hud-voice` structure (index.html:285-311): `.mic-big#voiceBtn`, `.attach-btn#attachBtn`, `.attach-btn.tts-bar-btn#ttsToggleBar`, `.voice-input#chatInput`, `.stop-btn#stopBtn`, `.send-btn#sendBtn`.
- Produces: the pill layout on mobile (no JS API change).

- [ ] **Step 1: Add the mobile CSS block for the pill**

In `dashboard/style.css`, add (after the `.send-btn` block ~525):

```css
/* ===== Mobile: large pill-shaped input (chat-first) ===== */
@media (max-width: 860px) {
  .hud-voice {
    margin: 6px 10px 8px; padding: 5px 6px 5px 8px; gap: 4px;
    border: 1px solid var(--border); border-radius: 24px; background: var(--bg2);
    border-top: 1px solid var(--border);           /* override the original border-top for consistency */
    align-items: flex-end;
  }
  #ttsToggleBar { display: none; }                 /* speaker moves into the drawer (Task 3) */
  .hud-voice .attach-btn { order: 1; width: 34px; height: 34px; border: none; background: transparent; }
  .hud-voice .voice-input {
    order: 2; border: none; background: transparent; border-radius: 0;
    min-height: 36px; max-height: 40vh; padding: 8px 4px; font-size: 16px;
  }
  .hud-voice .voice-input:focus { border: none; }
  .hud-voice .mic-big { order: 3; width: 34px; height: 34px; border: none; background: transparent; }
  .hud-voice .stop-btn, .hud-voice .send-btn { order: 4; width: 36px; height: 36px; border-radius: 50%; }
}
```

- [ ] **Step 2: Smoke-test the pill layout**

Open `dashboard/index.html` through the app at ~375px width (shrunk browser or mobile devtools). Confirm: `.hud-voice` is ONE rounded pill; the order inside the pill is ＋ (attach) | wide input | mic | send; the speaker button is GONE; the input takes up almost the full width and grows taller as you type multiple lines; nothing overflows horizontally. On desktop (>860px) `.hud-voice` does NOT change (still the old button row). Tune the numbers (padding/min-height) here if they are off.

- [ ] **Step 3: Commit**

```bash
git add dashboard/style.css
git commit -m "feat(mobile): large pill chat input (attach|input|mic|send)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Thin header (☰ + model chip + ＋) and hide the cramped rows

**Files:**
- Modify: `dashboard/index.html` (add `#navToggle`, `#newChatBtn` to `.hud-top`; add `#navBackdrop`)
- Modify: `dashboard/console.css` (mobile rules: show ☰/＋, hide the old hud-top cluster + sysbar + model-bar)
- Modify: `dashboard/app.js` or `dashboard/console.js` (move `#mbOpen`/`#mbPop` into the header on mobile; ＋ calls reset)
- Test: `node --check` on the edited JS file

**Interfaces:**
- Consumes: `.hud-top`, `.hud-top-left`, `.hud-top-right` (index.html:19-71); `#mbOpen`/`#mbPop` (index.html:263,270); `#resetBtn` (index.html:64); `isNarrow()` (console.js:130).
- Produces: `#navToggle` (opens the drawer - used by Task 3), `#newChatBtn`, `#navBackdrop`; JS function `syncModelChipPlacement()`.

- [ ] **Step 1: Add the ☰ and ＋ buttons to the header + backdrop**

In `dashboard/index.html`, right after the opening `<header class="hud-top">` tag (line 19), add the ☰ button (mobile-only):

```html
      <button class="hud-icon-btn nav-toggle-btn" id="navToggle" title="Menu" aria-label="Open menu">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>
        </svg>
      </button>
```

In `.hud-top-right` (after the `#resetBtn` button, before the `</div>` closing `.hud-actions` ~68), add the mobile-only ＋ button:

```html
          <button class="hud-icon-btn new-chat-btn" id="newChatBtn" title="New conversation" aria-label="New conversation">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
```

Right BEFORE the `</div>` that closes the `.hud` tag (find the closing tag of the `.hud` frame, same level as `.hud-top`), add the backdrop layer:

```html
    <div class="nav-backdrop" id="navBackdrop" hidden></div>
```

- [ ] **Step 2: Mobile CSS - show ☰/＋, hide the old cluster + sysbar + model-bar**

In `dashboard/console.css`, add to the `@media (max-width: 860px)` block (inside the block starting ~324):

```css
  .nav-toggle-btn { display: inline-flex; }
  .new-chat-btn { display: inline-flex; }
  /* Mobile header keeps only: ☰ (left) · model chip (center) · ＋ (right). Hide the clutter. */
  .hud-top .brand, .hud-top .navbar-brain,
  .hud-top #themeToggle, .hud-top #studioOpenBtn,
  .hud-top #settingsBtn, .hud-top #ttsToggle, .hud-top #resetBtn { display: none; }
  .hud-center-title { font-size: 13px; }
  .sysbar { display: none; }                       /* the SYSTEM/MCP strip is hidden on mobile */
  .model-bar { display: none; }                    /* the original model row is hidden; the chip moves to the header (JS) */
  /* Model chip once it sits in the header */
  .hud-top #mbOpen { display: inline-flex; }
```

Outside the mobile block, add a default hide for the 2 new buttons (desktop does not see them):

```css
.nav-toggle-btn, .new-chat-btn { display: none; }
```

- [ ] **Step 3: JS - move the model chip into the header on mobile + ＋ calls reset**

Find the wiring file: `grep -n "resetBtn\|mbOpen" dashboard/app.js dashboard/console.js`. Add the following snippet to the right file (where the other DOM buttons are bound; if unclear, put it in `dashboard/app.js` in the DOM init section):

```javascript
  // ===== Mobile: move the model chip up to the header, put it back on desktop =====
  (function mobileHeaderSetup() {
    const mq = window.matchMedia("(max-width: 860px)");
    const mbOpen = document.getElementById("mbOpen");
    const mbPop = document.getElementById("mbPop");
    const modelBar = document.getElementById("modelBar");
    const headerCenter = document.querySelector(".hud-center-title");
    const headerRoot = document.querySelector(".hud-top");
    function place() {
      if (!mbOpen || !modelBar || !headerRoot) return;
      if (mq.matches) {                                  // mobile: chip + popover go to the middle of the header
        if (headerCenter && mbOpen.parentElement !== headerRoot) {
          headerRoot.insertBefore(mbOpen, headerCenter.nextSibling);
          if (mbPop) headerRoot.insertBefore(mbPop, mbOpen.nextSibling);
        }
      } else {                                           // desktop: return them to the model-bar
        if (mbOpen.parentElement !== modelBar) {
          modelBar.insertBefore(mbOpen, modelBar.firstChild);
          if (mbPop) modelBar.insertBefore(mbPop, mbOpen.nextSibling);
        }
      }
    }
    place();
    mq.addEventListener ? mq.addEventListener("change", place) : mq.addListener(place);
  })();

  // ===== Mobile: the ＋ button = new conversation (reuses reset) =====
  const _newChat = document.getElementById("newChatBtn");
  const _reset = document.getElementById("resetBtn");
  if (_newChat && _reset) _newChat.addEventListener("click", () => _reset.click());
```

Note: `#mbOpen` is bound by event delegation in `model-picker.js:89` (`e.target.closest("#mbOpen")`), so moving it in the DOM keeps it clickable. `#mbPop` is `position:absolute`, so it must sit inside an offset parent with `position:relative` - `.hud-top` needs `position: relative` (added in Step 4 if not already there).

- [ ] **Step 4: CSS - the model popover opens DOWNWARD below the header on mobile**

In the mobile block of `dashboard/console.css`, add (the original mb-pop opens UPWARD with `bottom: calc(100%+6px)`; in the header it has to flip down):

```css
  .hud-top { position: relative; }
  .hud-top #mbPop { bottom: auto; top: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    width: min(340px, 92vw); }
```

- [ ] **Step 5: node --check + smoke**

Run: `node --check dashboard/app.js` (and/or `dashboard/console.js` if edited there)
Expected: no syntax errors.

Smoke test at ~375px: the header has only ☰ (left) · the "Jarvis 007 · model ▾" chip (center) · ＋ (right); the model-bar row and the SYSTEM strip below are GONE; tapping the model chip opens the picker RIGHT BELOW the header (not clipped at the top); tapping ＋ resets the conversation. Desktop (>860px): header + model-bar exactly as before, the model chip stays in its old place.

- [ ] **Step 6: Commit**

```bash
git add dashboard/index.html dashboard/console.css dashboard/app.js dashboard/console.js
git commit -m "feat(mobile): thin header with ☰ + model chip + ＋; hide sysbar/model-bar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Rail becomes a left slide-in drawer + move system buttons into the drawer

**Files:**
- Modify: `dashboard/console.css` (mobile rail: from bottom bar -> left slide-in drawer + backdrop)
- Modify: `dashboard/app.js`/`dashboard/console.js` (☰ toggles `body.nav-open`; backdrop/Esc/picking an item closes it)
- Modify: `dashboard/index.html` (add a "System" section to the rail: speaker toggle, settings, theme switch, Studio, reset) - or leave the rail-nav alone and only show `rail-top/foot` again
- Test: `node --check`

**Interfaces:**
- Consumes: `#navToggle`, `#navBackdrop` (Task 2); `.rail`, `.rail-nav`, `.rail-top`, `.rail-foot` (index.html:315-351); the existing mobile rail block (console.css:324-338).
- Produces: the drawer behavior (`body.nav-open`).

- [ ] **Step 1: CSS - rail becomes a left slide-in drawer (replacing the bottom bar)**

In `dashboard/console.css`, REPLACE the rail rules inside the `@media (max-width: 860px)` block (which currently puts the rail at the bottom, ~326-338) with:

```css
  .rail {
    top: 0; left: 0; bottom: 0; right: auto; width: min(280px, 82vw); height: 100vh;
    flex-direction: column; padding: 10px 8px; gap: 4px;
    border-top: 0; border-right: 1px solid var(--glass-brd);
    transform: translateX(-100%); transition: transform .22s ease; z-index: 60;
    overflow-y: auto;
  }
  body.nav-open .rail { transform: translateX(0); box-shadow: 8px 0 40px rgba(0,0,0,.5); }
  .rail-top, .rail-foot { display: flex; }          /* show the brand + version again inside the drawer */
  .rail-nav { flex-direction: column; overflow-x: hidden; overflow-y: auto; gap: 2px; }
  .rail-group, .rail-grp-items { display: block; }  /* restore the vertical groups */
  .rail-grp-lbl { display: flex; }
  .rail-item { flex: none; flex-direction: row; gap: 10px; padding: 9px 10px; }
  .rail-item .rail-lbl { font-size: 13px; }
  /* backdrop */
  .nav-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 55; }
  .nav-backdrop[hidden] { display: none; }
  body.nav-open .nav-backdrop { display: block; }
  /* the body no longer reserves 56px at the bottom for the rail */
  body.has-rail .hud { margin-left: 0; width: 100%; height: 100vh; }
  .cview { left: 0; bottom: 0; }
  .hud { grid-template-rows: 46px 1fr auto; }        /* the voice row sizes itself to the pill, drop the hard 62px */
```

- [ ] **Step 2: JS - ☰ toggles the drawer, closes via backdrop/Esc/picking an item**

Add to the wiring file (next to the Task 2 snippet):

```javascript
  // ===== Mobile: navigation drawer =====
  (function navDrawerSetup() {
    const toggle = document.getElementById("navToggle");
    const backdrop = document.getElementById("navBackdrop");
    const rail = document.querySelector(".rail");
    const open = () => { document.body.classList.add("nav-open"); if (backdrop) backdrop.hidden = false; };
    const close = () => { document.body.classList.remove("nav-open"); if (backdrop) backdrop.hidden = true; };
    if (toggle) toggle.addEventListener("click", () =>
      document.body.classList.contains("nav-open") ? close() : open());
    if (backdrop) backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
    if (rail) rail.addEventListener("click", (e) => {           // picking a nav item -> close
      if (e.target.closest(".rail-item") && window.matchMedia("(max-width: 860px)").matches) close();
    });
  })();
```

- [ ] **Step 3: (optional) Move the system buttons into the drawer**

If you want the old header buttons (speaker toggle `#ttsToggle`, Settings `#settingsBtn`, theme switch `#themeToggle`, Studio `#studioOpenBtn`, brain picker) reachable on mobile: add a "System" block at the end of `.rail` in index.html (shown on mobile only). The leanest way that does NOT duplicate handlers: add mobile-only buttons in the rail whose click delegates to the original button, for example:

```html
      <div class="rail-sys only-mobile">
        <button class="rail-item" onclick="document.getElementById('themeToggle').click()"><span class="rail-lbl">Switch theme</span></button>
        <button class="rail-item" onclick="document.getElementById('settingsBtn').click()"><span class="rail-lbl">Settings</span></button>
        <button class="rail-item" onclick="document.getElementById('studioOpenBtn').click()"><span class="rail-lbl">Studio</span></button>
        <button class="rail-item" onclick="document.getElementById('ttsToggle').click()"><span class="rail-lbl">Toggle speaker</span></button>
      </div>
```

CSS: `.only-mobile { display: none; } @media (max-width:860px){ .only-mobile { display: block; } }`. (If you find this is not needed on mobile yet, skip this step - YAGNI.)

- [ ] **Step 4: node --check + smoke**

Run: `node --check dashboard/app.js` (and console.js if edited)
Expected: no errors.

Smoke test at ~375px: the bottom nav bar is GONE; tapping ☰ -> the drawer slides in from the left + a dimmed backdrop; tapping the backdrop / Esc / picking an item -> it closes; the tool list shows vertically and is easy to tap; the bottom of the screen now holds only the input pill. Desktop (>860px): the rail is still the old left column, ☰ is not shown, no backdrop.

- [ ] **Step 5: Commit**

```bash
git add dashboard/console.css dashboard/app.js dashboard/console.js dashboard/index.html
git commit -m "feat(mobile): rail becomes left slide-in drawer + ☰ open/close, drop bottom nav bar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Bump assets + overall smoke + push

**Files:**
- Modify: `dashboard/index.html` (bump the `?v=` of the dashboard assets)
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: all the tasks above.

- [ ] **Step 1: Bump the ?v= of the dashboard css/js**

`grep -n "?v=" dashboard/index.html` -> raise the version number of the edited assets (style.css, console.css, app.js/console.js) so browsers load the new version. If there is no `?v=`, skip it (index.html changed, so the browser reloads it anyway).

- [ ] **Step 2: Overall smoke test on mobile + desktop**

At ~375px: compact 3-button header, big pill input, working drawer, no cramped rows. At >900px: everything exactly as before the change (no desktop regression).

- [ ] **Step 3: Bump VERSION + CHANGELOG**

Get the next VERSION (read `cat VERSION`, bump the patch). Add a CHANGELOG entry:

```markdown
## [x.y.z] - 2026-07-19
The chat UI on phones is much tidier: a large rounded pill input, a header with just the ☰ menu + model chip + new-conversation button, and the tool row turned into a slide-in drawer. Only the phone (narrow screen) version changed, the desktop version stays as it was. Reload the page to see it (?v is bumped).
### Improvements
- **Phone chat frame**: the input grows large (pill: attach | input | mic | send), the 2 cramped control rows (the SYSTEM strip and the bottom nav bar) are gone, tools + system buttons are gathered in the ☰ menu; the model chip moved up to the header and opens the same old picker.
```

- [ ] **Step 4: Commit + push**

```bash
git add dashboard/index.html VERSION CHANGELOG.md
git commit -m "chore(release): x.y.z - tidy phone chat frame

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git fetch origin && git rebase origin/main
git push origin main
```

- [ ] **Step 5: Verify after the push**

Wait for CI to build the image, then on the phone (the Hostinger build) tap the "Update now" button (Watchtower is on) or wait, and reopen the page to check the real mobile UI.

---

## Self-Review (done)

**Spec coverage:**
- Block 1 pill input -> Task 1. ✓
- Block 2 thin header (☰/model chip/＋) + hide sysbar/model-bar + model chip moved to header (JS, popover flips down) -> Task 2. ✓
- Block 2 left slide-in drawer replacing the bottom bar -> Task 3. ✓
- Block 2 system buttons into the drawer -> Task 3 Step 3 (optional). ✓
- Block 3 speaker hidden in the bar -> Task 1 (`#ttsToggleBar` display:none). ✓
- Mobile-only, desktop unchanged -> every rule is in @media 860px; new buttons default to display:none. ✓
- Bump ?v= + release -> Task 4. ✓

**Placeholder scan:** no TBD/TODO; every step has real code/commands. Task 3 Step 3 is clearly labeled optional (YAGNI), not a placeholder.

**Type/name consistency:** ids are consistent across tasks - `#navToggle`, `#newChatBtn`, `#navBackdrop`, `body.nav-open`, `#mbOpen`/`#mbPop`, `.hud-voice`/`.voice-input`/`.mic-big`/`.send-btn`/`.attach-btn#ttsToggleBar`. The `860px` breakpoint is used uniformly.

**Execution note:** this is visual CSS work - the pixel numbers are a starting point, and each task's smoke step is where you tune them. Since there are no automated tests, the smoke test at mobile width is the main gate; if run by a subagent, the subagent should take screenshots through the Browser tool at a mobile viewport to self-check, or let the user check on a phone.
