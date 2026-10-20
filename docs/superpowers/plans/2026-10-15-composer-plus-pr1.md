# New Composer (PR 1: UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the composer into a single rounded box with a "+" button (an expandable menu), a separate model chip and thinking-level chip (an orange sparkling slider), a Fast mode lightning button that persists its state, and a small mic on the right.

**Architecture:** Keep the ids that app.js, pet.js, console.js and the tests rely on (`hudVoice`, `chatInput`, `voiceBtn`, `sendBtn`, `stopBtn`, `fileInput`, `attachBar`, `modelBar`, `mbOpen`, `mbPop`), and only change where they sit plus the CSS. The new logic lives in two new files whose pure parts do not depend on the DOM (tested with node): `composer-plus.js` (the registry for the "+" menu) and `effort-slider.js` (the slider plus the canvas effect). model-picker.js handles the thinking-level chip and the lightning button because it already holds `state.reasoning` and `saveModel`. The server adds the `settings.model.fast` key and the `GET /files/resolve` endpoint.

**Tech Stack:** HTML/CSS/vanilla JS (dashboard, no build step), FastAPI (server/main.py), node tests `tests/js/*.js` and Python tests `tests/python/*.py` run with `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py`.

**Spec:** `docs/superpowers/specs/2026-10-15-composer-plus-fast-mode-design.md`

## Global Constraints

- Effect color: Jarvis 007 orange `var(--accent)` (#ff7a3c); no hard-coded colors in the cp-css of console.js (test_theme_tokens).
- Box corner radius: **24px** (changed from 18px, with a deliberate edit to test_theme_tokens lines 51-58 and to cp-css).
- Thinking-level labels are in English in both vi and en: Off, Light, Medium, High, Extra, Ultra. The stored values stay `off/low/medium/high/xhigh/ultra` and those quoted strings must remain in model-picker.js.
- Lightning button: no on/off text next to it; only a tooltip (`title`) "Fast mode" plus one note line.
- No em dash (U+2014) anywhere. NEW .js files have no Vietnamese text in running code (text goes through `window.t`). app.js keeps exactly 12 lines of running code containing Vietnamese text (test_i18n), so every line newly added to app.js contains no Vietnamese text.
- Every new label in index.html has `data-i18n`/`data-i18n-title`/`data-i18n-aria`, and the key exists in both `dashboard/i18n/vi.json` and `en.json`; en contains no Vietnamese text.
- `<textarea id="chatInput" ...>`: `id` is the first attribute, keep `rows="1"`.
- Do not put a `disabled` attribute on `#voiceBtn` (pet.js calls `.click()`).
- Do not add a script tag between `call-bar.js` and `app.js`; `model-list.js` comes before `model-picker.js`.
- The `?v=` cache-busters of style.css, console.css, app.js, model-picker.js, mobile-chat.js and console.js only go up.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- Coding page on desktop: coding.js inserts `#cdChips` into `#modelBar`; the context chip row must still show above the box (`#modelBar` is no longer `:empty`). Tested in Task 2.
- Resizing the window from phone to desktop: the model chip must return to `#cpChips` (before `#effBtn`), not stay stuck at the top of the page. Tested in Task 2.
- Attaching a folder whose files are all hidden or empty: send nothing, say so clearly, do not hang. Tested in Task 5.
- `/files/resolve` with `../`, an absolute path, or a symlink pointing outside the brain: reject with 400. Tested in Task 1.
- A model that already carries a thinking level (Antigravity `gemini-3.8-flash-high`): the slider cannot be dragged and shows an explanation; the chip is still readable. Tested in Task 3.

---

### Task 1: Server: the `fast` key and the `/files/resolve` endpoint

**Files:**
- Modify: `server/main.py` (the `model` section branch of POST /settings, next to `if "reasoning" in patch:` ~line 5129; add the route after `files_search` ~line 7367)
- Modify: `server/config.py` (the `model` defaults, ~line 112 where `"reasoning": "off"` is)
- Test: `tests/python/test_khung_go_server.py` (new)

**Interfaces:**
- Produces: `settings.model.fast: bool` (default `False`, returned by GET /settings). `GET /files/resolve?brain=<b>&path=<rel>` -> `{"ok": true, "path": "<abs>", "name": "<basename>", "size": <int>, "kind": "image"|"file"}`; on error -> HTTP 400 `{"ok": false, "error": "..."}`.

- [ ] **Step 1: Write the failing test**

```python
"""New composer (0.148.0): the Fast mode key in settings and the path for attaching files already in the brain.

    python tests/run.py khung_go_server
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-khunggo-")
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import config as cfgmod  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        fails.append(name)


client = TestClient(main.app, base_url="http://localhost")   # brand-new STATE_DIR: no account yet so no login is needed (like test_messenger)

# 1. fast can be saved and only accepts a boolean
s = cfgmod.read_settings()
check("fast is off by default", (s.get("model") or {}).get("fast") is False, s.get("model"))
r = client.post("/settings", data={"section": "model", "data": json.dumps({"fast": True})})
check("POST /settings saves fast=true", r.status_code == 200 and cfgmod.read_settings()["model"]["fast"] is True, r.text)
client.post("/settings", data={"section": "model", "data": json.dumps({"fast": "yes"})})
check("a non-boolean value is read as false", cfgmod.read_settings()["model"]["fast"] is False)

# 2. /files/resolve
brain = Path(main._brain_root("brain"))
(brain / "ghi-chu").mkdir(parents=True, exist_ok=True)
f = brain / "ghi-chu" / "bao-cao.md"
f.write_text("doanh thu", encoding="utf-8")
root = Path(main._files_root("brain")).resolve()
rel = f.resolve().relative_to(root).as_posix()
r = client.get("/files/resolve", params={"brain": "brain", "path": rel})
d = r.json()
check("resolve returns an absolute path inside the brain", r.status_code == 200 and d.get("ok")
      and Path(d["path"]) == f.resolve() and d["name"] == "bao-cao.md" and d["kind"] == "file", d)
for bad in ("../../etc/passwd", str(f.resolve()), "", "ghi-chu/khong-co.md"):
    r = client.get("/files/resolve", params={"brain": "brain", "path": bad})
    check(f"resolve rejects {bad!r}", r.status_code == 400 and r.json().get("ok") is False, r.text)
outside = Path(tempfile.mkdtemp(prefix="ngoai-")) / "x.txt"
outside.write_text("x", encoding="utf-8")
try:
    (brain / "link-ra-ngoai.txt").symlink_to(outside)
    r = client.get("/files/resolve", params={"brain": "brain", "path": (brain / "link-ra-ngoai.txt").relative_to(root).as_posix()})
    check("resolve rejects a symlink pointing outside the brain", r.status_code == 400, r.text)
except OSError:
    print("skip symlink (this machine cannot create symlinks)")

if fails:
    print("\nFAIL - test_khung_go_server: " + ", ".join(fails))
    sys.exit(1)
print("\nOK - test_khung_go_server: all pass")
```

- [ ] **Step 2: Run it and watch it fail**

Run: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/python/test_khung_go_server.py`
Expected: FAIL at "fast is off by default" (the key does not exist yet) and at the resolve checks (the route does not exist yet).

- [ ] **Step 3: Write the code**

`server/config.py`, in the default `model` dict next to `"reasoning": "off",` add:

```python
        "fast": False,   # Fast mode (lightning button in the composer, 0.148.0): runs faster, costs more
```

`server/main.py`, right after the `if "reasoning" in patch:` block:

```python
        # Fast mode (lightning button in the composer, 0.148.0). This POST path swallows unknown keys so it needs its own branch.
        if "fast" in patch:
            m["fast"] = patch["fast"] is True
```

`server/main.py`, after the `files_search` function:

```python
@app.get("/files/resolve")
async def files_resolve(brain: str = Query("brain"), path: str = Query("")):
    """ABSOLUTE path of a file that already exists in the brain, for the "Pick a file in the brain" item of the
    composer's "+" menu (0.148.0). `path` is relative to the root, as /files/search returns it. Only accepts a
    real file inside the brain root (blocks `..`, absolute paths, and symlinks pointing outside)."""
    rel = (path or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return JSONResponse({"ok": False, "error": "path"}, status_code=400)
    root = Path(_files_root(brain)).resolve()
    broot = Path(_brain_root(brain)).resolve()
    try:
        p = (root / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=400)
    if not p.is_file() or (p != broot and broot not in p.parents):
        return JSONResponse({"ok": False, "error": "outside"}, status_code=400)
    kind = "image" if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "file"
    return {"ok": True, "path": str(p), "name": p.name, "size": p.stat().st_size, "kind": kind}
```

(`re`, `Path`, `JSONResponse` and `Query` are already imported at the top of main.py; check with `grep -n "^import re\|^from pathlib\|JSONResponse,\|Query" server/main.py | head`.)

- [ ] **Step 4: Run it and watch it pass**

Run: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/python/test_khung_go_server.py` -> `OK - test_khung_go_server`
Run: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/python/test_route_table.py --update` (new route), then run again without `--update` -> `route table matches`.
Run: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py settings` -> green.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/config.py tests/python/test_khung_go_server.py tests/python/route_table.json
git commit -m "Composer: settings.model.fast and GET /files/resolve for brain file attachments"
```

---

### Task 2: Single-block composer: HTML, CSS, borrowed box, phone

**Files:**
- Modify: `dashboard/index.html:490-528` (the `#attachBar`, `#modelBar`, `#hudVoice` block)
- Modify: `dashboard/style.css:1346-1433` (box, mic, input, send/stop buttons, mobile)
- Modify: `dashboard/console.js:7489` (`CHAT_NODE_IDS`), `:7599` (cp-css 24px)
- Modify: `dashboard/mobile-chat.js:12-41` (where the model chip is returned on desktop)
- Modify: `dashboard/app.js:3547` (remove `#attachBtn`), `:1604` (the Sources folder comes from the first file that HAS `sources`)
- Modify: `dashboard/workspace.js:38-46` (`chatReady` also locks "+" and send)
- Modify: `tests/python/test_theme_tokens.py:51-58` (18px -> 24px, deliberate)
- Test: `tests/js/test_khung_go.js` (new)

**Interfaces:**
- Produces (DOM, later tasks depend on it): `#hudVoice` contains, in order, `#voiceFocusResume`, `#attachBar`, `#fileInput`, `#folderInput`, `#chatInput`, `.cp-row#cpRow` (holding `#plusBtn`, `.cp-chips#cpChips` [`#mbOpen`, `#effBtn` > `#effTxt`, `#fastBtn`], `.cp-gap`, `#voiceBtn`, `#stopBtn`, `#sendBtn`), then the popovers `#mbPop`, `#effPop`, `#plusMenu` (all `hidden`). `#modelBar` is empty and sits right before `#hudVoice`.

- [ ] **Step 1: Write the failing test** `tests/js/test_khung_go.js`

```js
/* Single-block composer (0.148.0): everything sits inside #hudVoice, the old ids are intact.

       node tests/js/test_khung_go.js
*/
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "../..");
const html = fs.readFileSync(path.join(ROOT, "dashboard/index.html"), "utf8");
const css = fs.readFileSync(path.join(ROOT, "dashboard/style.css"), "utf8");
const consoleJs = fs.readFileSync(path.join(ROOT, "dashboard/console.js"), "utf8");
const mobile = fs.readFileSync(path.join(ROOT, "dashboard/mobile-chat.js"), "utf8");
const app = fs.readFileSync(path.join(ROOT, "dashboard/app.js"), "utf8");
const ws = fs.readFileSync(path.join(ROOT, "dashboard/workspace.js"), "utf8");
let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

const card = (html.match(/<div class="hud-voice" id="hudVoice">[\s\S]*?<!-- \/hudVoice -->/) || [""])[0];
check("found the #hudVoice box (ending with the <!-- /hudVoice --> marker)", !!card);
["voiceFocusResume", "attachBar", "fileInput", "folderInput", "chatInput", "cpRow", "plusBtn", "cpChips",
 "mbOpen", "effBtn", "effTxt", "fastBtn", "voiceBtn", "stopBtn", "sendBtn", "mbPop", "effPop", "plusMenu"].forEach(id => {
  check("the box contains #" + id, card.indexOf('id="' + id + '"') !== -1);
});
const order = ["attachBar", "chatInput", "cpRow"].map(id => card.indexOf('id="' + id + '"'));
check("attachments on top, input in the middle, button row at the bottom", order[0] < order[1] && order[1] < order[2]);
const row = card.slice(card.indexOf('id="cpRow"'));
check("button row: + before the chips, mic and send at the end",
  row.indexOf('id="plusBtn"') < row.indexOf('id="cpChips"') && row.indexOf('id="cpChips"') < row.indexOf('id="voiceBtn"')
  && row.indexOf('id="voiceBtn"') < row.indexOf('id="sendBtn"'));
check("#attachBtn is gone from the page", html.indexOf('id="attachBtn"') === -1);
check("#modelBar remains, empty, right before the box", /<div class="model-bar" id="modelBar"><\/div>\s*(<!--[\s\S]*?-->\s*)*<div class="hud-voice" id="hudVoice">/.test(html));
check("#folderInput picks a folder", /id="folderInput"[^>]*webkitdirectory/.test(card));
check("textarea keeps id first and rows=1", /<textarea id="chatInput"[^>]*rows="1"/.test(card));
check("no disabled on #voiceBtn", !/id="voiceBtn"[^>]*disabled/.test(card));

check("CSS: the box stacks vertically, 24px radius before the --bg2 background",
  /\.hud-voice \{[^}]*flex-direction: column[^}]*align-items: flex-end[^}]*border-radius: 24px;[^}]*background: var\(--bg2\)/s.test(css));
check("CSS: an empty #modelBar is hidden", css.indexOf(".model-bar:empty { display: none; }") !== -1);
check("CSS: no old-style order rule left on phones", css.indexOf(".hud-voice .attach-btn { order: 1;") === -1);

check("CHAT_NODE_IDS drops attachBar (it now sits inside the box)",
  consoleJs.indexOf('const CHAT_NODE_IDS = ["callBar", "chatArea", "bgStrip", "modelBar", "hudVoice"];') !== -1);
check("cp-css of the Chat page uses a 24px radius", consoleJs.indexOf(".chatpage-slot .hud-voice{ background:var(--bg2); border:1px solid var(--border); border-radius:24px; }") !== -1);

check("phone -> desktop: the model chip returns to #cpChips before #effBtn",
  mobile.indexOf('chipHost.insertBefore(mbOpen, document.getElementById("effBtn"))') !== -1
  && mobile.indexOf("mbPopHome.appendChild(mbPop)") !== -1);
check("app.js no longer calls #attachBtn directly", app.indexOf('document.getElementById("attachBtn").addEventListener') === -1);
check("Sources comes from the first file that has sources (brain files do not)",
  app.indexOf("(atts.find(a => a.sources) || {}).sources") !== -1);
check("workspace locks both + and send while the session is not ready", /\["plusBtn", "sendBtn"\]\.forEach/.test(ws));
const coding = fs.readFileSync(path.join(ROOT, "dashboard/coding.js"), "utf8");
check("the Coding page still inserts its context chip row into #modelBar (it shows because it is no longer empty)",
  coding.indexOf('getElementById("modelBar")') !== -1 && css.indexOf(".model-bar:empty { display: none; }") !== -1);

if (fails.length) { console.log("\nFAIL - test_khung_go: " + fails.length + " failures"); process.exit(1); }
console.log("\nOK - test_khung_go: all pass");
```

- [ ] **Step 2: Run it and watch it fail**: `node tests/js/test_khung_go.js` -> FAIL (the box has not changed yet).

- [ ] **Step 3: index.html**: replace everything from the `<!-- Attachment chips -->` line (before `#attachBar`) to the closing `</div>` of `#hudVoice` with:

```html
    <!-- The Coding page's own chip row (coding.js inserts into it on desktop). On the home page it is empty
         so it is hidden (.model-bar:empty). The model chip moved into the composer box in 0.148.0. -->
    <div class="model-bar" id="modelBar"></div>

    <!-- ===== Composer: ONE Claude-style rounded box (0.148.0) =====
         Top: attached images and files. Middle: the input. Bottom: the "+" button, model chip, thinking-level chip,
         Fast mode lightning, then mic and send. Popovers open upward from the box. -->
    <div class="hud-voice" id="hudVoice">
      <button id="voiceFocusResume" class="voice-focus-resume" hidden></button>
      <div class="attach-bar" id="attachBar"></div>
      <input type="file" id="fileInput" multiple style="display:none">
      <input type="file" id="folderInput" webkitdirectory multiple style="display:none">
      <textarea id="chatInput" class="voice-input" placeholder="What would you like me to do?" data-i18n-ph="bar.input_ph" rows="1"></textarea>
      <div class="cp-row" id="cpRow">
        <button type="button" class="cp-plus" id="plusBtn" aria-haspopup="menu" aria-expanded="false" aria-controls="plusMenu"
                title="Add files, commands, connections" data-i18n-title="cp.plus" aria-label="Add files, commands, connections" data-i18n-aria="cp.plus">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
        <div class="cp-chips" id="cpChips">
          <button type="button" class="mb-chip" id="mbOpen" title="Change model / provider" data-i18n-title="mb.open">
            <span class="mb-dot"></span>
            <span id="mbModelTxt">Model</span>
            <span class="mb-caret">▾</span>
          </button>
          <button type="button" class="cp-eff" id="effBtn" aria-haspopup="dialog" aria-expanded="false" aria-controls="effPop"
                  title="Thinking level" data-i18n-title="eff.title">
            <span id="effTxt">Off</span><span class="mb-caret">▾</span>
          </button>
          <button type="button" class="cp-fast" id="fastBtn" aria-pressed="false" title="Fast mode" aria-label="Fast mode">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z"/></svg>
          </button>
        </div>
        <span class="cp-gap"></span>
        <button type="button" class="mic-big" id="voiceBtn" title="Click to call Jarvis 007" data-i18n-title="bar.mic">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/>
          </svg>
        </button>
        <button type="button" class="stop-btn" id="stopBtn" title="Interrupt command / stop reading (Esc)" data-i18n-title="bar.stop" style="display:none">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
        </button>
        <button type="button" class="send-btn" id="sendBtn" aria-label="Send" data-i18n-aria="bar.send">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
        </button>
      </div>
      <div class="mb-pop" id="mbPop" hidden></div>
      <div class="eff-pop" id="effPop" role="dialog" aria-label="Effort" hidden></div>
      <div class="cp-menu" id="plusMenu" role="menu" hidden></div>
    </div><!-- /hudVoice -->
```

Note: if `bar.send` is not yet in vi.json/en.json, add it (`"bar.send": "Gửi"` / `"Send"`; the vi value `Gửi` means "Send"). Add the key `cp.plus` (`"Thêm file, lệnh, kết nối"` / `"Add files, commands, connections"`) and `eff.title` (`"Mức suy nghĩ"` / `"Effort"`) in this task; the vi values are Vietnamese on purpose (they are the Vietnamese UI strings: "Add files, commands, connections" and "Thinking level"). The other keys come in Tasks 3-5.

- [ ] **Step 4: style.css**: replace the block from `.hud-voice {` (line ~1353) through the end of the `.attach-btn:hover` rule (line ~1433) with:

```css
.hud-voice {
  position: relative;
  /* One Claude-style rounded box (0.148.0): attached images, the input and the button row stack vertically. Each
     child stretches to the full width (align-self: stretch below); flex-end keeps the children from shrinking
     toward the middle when the box grows taller. */
  display: flex; flex-direction: column; align-items: flex-end; gap: 4px;
  margin: 4px 16px 16px; padding: 10px 12px 8px;
  border: 1px solid var(--border); border-radius: 24px; background: var(--bg2);
  transition: border-color .15s;
}
.hud-voice > * { align-self: stretch; }
.hud-voice:focus-within { border-color: var(--accent-line); }
.hud-voice .attach-bar { padding: 0 2px; }
.hud-voice .attach-bar.has-items { padding: 2px 2px 6px; }
.model-bar:empty { display: none; }
.cp-row { display: flex; align-items: center; gap: 6px; min-width: 0; }
.cp-chips { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 0 1 auto; }
.cp-gap { flex: 1 1 auto; }
.cp-plus, .cp-fast {
  flex: none; width: 32px; height: 32px; border-radius: 50%; padding: 0;
  border: 1px solid var(--border); background: transparent; color: var(--text2);
  display: inline-flex; align-items: center; justify-content: center; cursor: pointer;
  transition: border-color .15s, color .15s, background .15s;
}
.cp-plus:hover, .cp-plus[aria-expanded="true"], .cp-fast:hover { border-color: var(--accent); color: var(--accent); }
.cp-plus:focus-visible, .cp-fast:focus-visible, .cp-eff:focus-visible, .mic-big:focus-visible,
.send-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.cp-eff {
  flex: none; display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
  padding: 4px 11px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg3);
  color: var(--accent-ink); font-family: var(--font); font-weight: 600; cursor: pointer; white-space: nowrap;
}
.cp-eff:hover, .cp-eff[aria-expanded="true"] { border-color: var(--accent); }
/* Fast mode lightning: still when off; when on, an orange background with a light band sweeping across and a gently pulsing bolt. */
.cp-fast[aria-pressed="true"] {
  color: var(--on-accent); border-color: var(--accent);
  background: linear-gradient(110deg, var(--accent) 0%, var(--accent-ink) 25%, var(--accent) 50%, var(--accent-solid) 75%, var(--accent) 100%);
  background-size: 250% 100%; animation: fastWave 1.6s linear infinite;
}
.cp-fast[aria-pressed="true"] svg { animation: fastZap 1.6s ease-in-out infinite; }
.cp-fast[aria-disabled="true"] { opacity: .45; cursor: help; }
@keyframes fastWave { to { background-position: -250% 0; } }
@keyframes fastZap { 50% { transform: scale(1.12); } }
@media (prefers-reduced-motion: reduce) {
  .cp-fast[aria-pressed="true"], .cp-fast[aria-pressed="true"] svg { animation: none; }
}
.mic-big {
  background: transparent; border: 1px solid transparent; color: var(--text2);
  width: 34px; height: 34px; border-radius: 50%; cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.mic-big:hover { border-color: var(--accent); color: var(--accent); }
.mic-big.recording {
  border-color: var(--red); color: var(--red);
  box-shadow: 0 0 0 3px var(--danger-wash); animation: micpulse 1.2s ease-in-out infinite;
}
@keyframes micpulse { 50% { box-shadow: 0 0 0 6px rgba(239,68,68,0); } }
.mic-big.focus-waiting { animation: none; opacity: .65; }
/* Hands-free: always listening - a fixed orange ring */
.mic-big.handsfree {
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-line), 0 0 10px rgba(255,107,43,0.35);
}
.mic-big.handsfree.recording {
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-line);
  animation: micpulse-hf 1.2s ease-in-out infinite;
}
@keyframes micpulse-hf { 50% { box-shadow: 0 0 0 7px rgba(255,107,43,0); } }
.voice-input {
  flex: none; background: transparent; border: none; border-radius: 0;
  color: var(--text); font-size: 16px; padding: 6px 6px 8px; resize: none; outline: none;
  /* max-height 45vh is only a safety net - the real height is set by app.js from scrollHeight
     (it grows with the text, and a line break shows the whole text). The old 90px ceiling once
     hard-capped autosize at ~3 lines on desktop even though the JS computed it correctly - the owner reported it on 27/08. */
  line-height: 1.4; max-height: 45vh; font-family: var(--font-chat);
}
.voice-input:focus { border-color: transparent; }
.voice-input::placeholder { color: var(--text3); }
.send-btn {
  background: var(--accent-solid); border: none; color: var(--on-accent); width: 34px; height: 34px;
  border-radius: 50%; cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; transition: opacity 0.2s;
}
.send-btn:hover { opacity: 0.85; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ===== Mobile: same box, only the padding shrinks; the model chip moves to the top of the page (mobile-chat.js) ===== */
@media (max-width: 860px) {
  .hud-voice {
    margin: 6px 10px 8px; padding: 8px 8px 6px; gap: 2px;
    border: 1px solid var(--border); border-radius: 24px; background: var(--bg2);
    align-items: flex-end;
  }
  .hud-voice .voice-input { min-height: 36px; max-height: 40vh; padding: 6px 6px; font-size: 16px; }
}

.stop-btn {
  background: var(--red); border: none; color: white; width: 34px; height: 34px;
  border-radius: 50%; cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; transition: opacity 0.2s;
  animation: stoppulse 1.3s ease-in-out infinite;
}
.stop-btn:hover { opacity: 0.85; }
@keyframes stoppulse { 50% { box-shadow: 0 0 0 5px var(--danger-wash); } }
```

Then in the `.mb-pop {` block (~line 2122) change `left: 12px` to `left: 8px` (the popover now anchors to the box). After the `.mb-pop[hidden]` block add:

```css
.eff-pop, .cp-menu {
  position: absolute; bottom: calc(100% + 6px); z-index: 60; background: var(--bg2);
  border: 1px solid var(--border); border-radius: 14px; box-shadow: var(--shadow-3);
}
.eff-pop[hidden], .cp-menu[hidden] { display: none; }
```

- [ ] **Step 5: console.js**: change line 7489 to
`  const CHAT_NODE_IDS = ["callBar", "chatArea", "bgStrip", "modelBar", "hudVoice"];`
(add a comment line above it: `// attachBar sits INSIDE #hudVoice since 0.148.0 so it is no longer borrowed separately.`). Change `border-radius:18px;` to `border-radius:24px;` on line 7599.

- [ ] **Step 6: mobile-chat.js**: after `var modelBar = document.getElementById("modelBar");` add

```js
    // Since 0.148.0 the model chip lives in the composer's button row (#cpChips), and the picker panel (#mbPop) is a child of the box.
    var chipHost = document.getElementById("cpChips");
    var mbPopHome = mbPop ? mbPop.parentElement : null;
```

and replace the desktop branch

```js
        if (mbOpen && modelBar && mbOpen.parentElement !== modelBar) {
          modelBar.insertBefore(mbOpen, modelBar.firstChild);
          if (mbPop) modelBar.insertBefore(mbPop, mbOpen.nextSibling);
        }
```

with

```js
        if (mbOpen && chipHost && mbOpen.parentElement !== chipHost) {
          chipHost.insertBefore(mbOpen, document.getElementById("effBtn"));
          if (mbPop && mbPopHome) mbPopHome.appendChild(mbPop);
        }
```

- [ ] **Step 7: app.js**: replace line 3547 with (no Vietnamese text):

```js
const attachBtn = document.getElementById("attachBtn");
if (attachBtn) attachBtn.addEventListener("click", () => fileInput.click());
```

Replace line ~1604 `const src = atts[0].sources || "", attDir = atts[0].attachments || "";` with

```js
    const src = (atts.find(a => a.sources) || {}).sources || "", attDir = (atts.find(a => a.attachments) || {}).attachments || "";
```

- [ ] **Step 8: workspace.js** in `chatReady`, after the line `if (input) input.disabled = !value;` add

```js
    ["plusBtn", "sendBtn"].forEach(function (id) { var b = document.getElementById(id); if (b) b.disabled = !value; });
```

- [ ] **Step 9: test_theme_tokens.py** lines 51-58: change `18px` to `24px` in the two regexes and the two description sentences (`"...corner radius matches the original (24px)"`, `"...is still --bg2 + 24px radius"`); add the comment `# 0.148.0: the repo owner approved a rounder composer box (18px -> 24px).`

- [ ] **Step 10: Bump the cache-buster** in index.html for `style.css?v=`, `console.js?v=`, `mobile-chat.js?v=`, `app.js?v=`, `workspace.js?v=` (+1 each).

- [ ] **Step 11: Run the tests**

Run: `node tests/js/test_khung_go.js` -> OK.
Run: `grep -rln "hudVoice\|hud-voice\|voiceBtn\|attachBtn\|modelBar\|CHAT_NODE_IDS\|chatpage-slot .hud-voice\|attach-bar" tests/` and then run each file in the list (`node tests/js/<f>` or python). Every file green, except `test_model_theo_phien.py` (already red on this machine because of WinError 32).
Run: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py --js` -> everything green.

- [ ] **Step 12: Commit**

```bash
git add dashboard/index.html dashboard/style.css dashboard/console.js dashboard/mobile-chat.js dashboard/app.js dashboard/workspace.js dashboard/i18n/vi.json dashboard/i18n/en.json tests/js/test_khung_go.js tests/python/test_theme_tokens.py
git commit -m "Composer: one rounded card with attachments, input and a single control row"
```

---

### Task 3: Thinking-level chip and the orange slider

**Files:**
- Create: `dashboard/effort-slider.js`
- Modify: `dashboard/model-picker.js` (remove `#mbEffortTxt` and `.mb-eff-row`; add the `#effBtn` chip and the `#effPop` popover; outside-click)
- Modify: `dashboard/index.html` (the tag `<script src="effort-slider.js?v=1"></script>` right BEFORE `model-picker.js`)
- Modify: `dashboard/style.css` (`.eff-*` rules)
- Modify: `dashboard/i18n/vi.json`, `en.json`
- Test: `tests/js/test_thanh_truot_effort.js` (new)

**Interfaces:**
- Consumes: the DOM from Task 2 (`#effBtn`, `#effTxt`, `#effPop`).
- Produces: `window.JavisEffortSlider = { LEVELS, levelFromRatio(r), ratioFromLevel(i), isLocked(provider, model), mount(el, {value, locked, onChange}) -> {set(v), destroy()} }`; in node: `module.exports` with the same pure functions. model-picker.js adds `window.JavisModelBar.effortLabel()` returning the label currently shown.

- [ ] **Step 1: Failing test** `tests/js/test_thanh_truot_effort.js`

```js
/* Thinking-level slider (0.148.0): 6 steps, English labels, a model with a built-in level is locked.

       node tests/js/test_thanh_truot_effort.js
*/
const fs = require("fs");
const path = require("path");
const S = require("../../dashboard/effort-slider.js");
const ROOT = path.join(__dirname, "../..");
const picker = fs.readFileSync(path.join(ROOT, "dashboard/model-picker.js"), "utf8");
const vi = require("../../dashboard/i18n/vi.json"), en = require("../../dashboard/i18n/en.json");
let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

check("6 steps in the server's value order", JSON.stringify(S.LEVELS) === JSON.stringify(["off", "low", "medium", "high", "xhigh", "ultra"]));
check("position 0 -> off, 1 -> ultra", S.levelFromRatio(0) === "off" && S.levelFromRatio(1) === "ultra");
check("a middle position rounds to the nearest step", S.levelFromRatio(0.41) === "medium" && S.levelFromRatio(0.49) === "medium");
check("a position outside the bar is clamped", S.levelFromRatio(-3) === "off" && S.levelFromRatio(9) === "ultra");
check("ratioFromLevel is the inverse", S.ratioFromLevel("medium") === 0.4 && S.ratioFromLevel("unknown") === 0);
check("an Antigravity model with a -high suffix is a level-locked model", S.isLocked("antigravity-cli", "gemini-3.8-flash-high") === true);
check("an Antigravity model without a level suffix is not locked", S.isLocked("antigravity-cli", "claude-sonnet-4-6") === false);
check("other providers are never locked", S.isLocked("openai-oauth", "gpt-6.1-sol-high") === false);
const labels = { off: "Off", low: "Light", medium: "Medium", high: "High", xhigh: "Extra", ultra: "Ultra" };
Object.keys(labels).forEach(k => check("label " + k + " = " + labels[k] + " in both vi and en", vi["eff." + k] === labels[k] && en["eff." + k] === labels[k]));
check("model-picker.js keeps all 6 quoted value strings", ["off", "low", "medium", "high", "xhigh", "ultra"].every(v => picker.indexOf('"' + v + '"') !== -1));
check("the model chip no longer has the text 'Effort:'", picker.indexOf('"Effort: "') === -1 && picker.indexOf("mb-eff-row") === -1);
check("click outside: the model panel closes even when clicking in the button row (+, mic, send)", picker.indexOf('e.target.closest("#modelBar")') === -1);
const srcSlider = fs.readFileSync(path.join(ROOT, "dashboard/effort-slider.js"), "utf8");
check("the slider has role=slider and arrow keys", srcSlider.indexOf('"slider"') !== -1 && srcSlider.indexOf("ArrowRight") !== -1);
check("respects reduced motion", srcSlider.indexOf("prefers-reduced-motion") !== -1);
check("no Vietnamese text in effort-slider.js", !/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i.test(srcSlider.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")));

if (fails.length) { console.log("\nFAIL - test_thanh_truot_effort: " + fails.length + " failures"); process.exit(1); }
console.log("\nOK - test_thanh_truot_effort: all pass");
```

- [ ] **Step 2: Run it and watch it fail**: `node tests/js/test_thanh_truot_effort.js` -> require error (the file does not exist yet).

- [ ] **Step 3: Create `dashboard/effort-slider.js`**

```js
/* effort-slider.js - the thinking-level slider in the composer (0.148.0).
 * The pure parts (steps, position, lock) are tested with node; the drawing part (the orange particle canvas) only runs in the browser.
 */
(function () {
  "use strict";
  var LEVELS = ["off", "low", "medium", "high", "xhigh", "ultra"];
  var LOCKED_SUFFIX = /-(minimal|low|medium|high|xhigh|max)$/i;

  function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }
  function levelFromRatio(r) { return LEVELS[clamp(Math.round(clamp(Number(r) || 0, 0, 1) * 5), 0, 5)]; }
  function ratioFromLevel(v) { var i = LEVELS.indexOf(v); return i < 0 ? 0 : i / 5; }
  // An Antigravity model carries its level in its name (agy refuses an extra --effort): the slider is locked.
  function isLocked(provider, model) { return provider === "antigravity-cli" && LOCKED_SUFFIX.test(String(model || "")); }

  var api = { LEVELS: LEVELS, levelFromRatio: levelFromRatio, ratioFromLevel: ratioFromLevel, isLocked: isLocked };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  function tw(k) { return window.t ? window.t(k) : k; }
  function reduced() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } }

  function mount(el, opt) {
    opt = opt || {};
    var value = LEVELS.indexOf(opt.value) < 0 ? "off" : opt.value;
    el.innerHTML =
      '<div class="eff-head"><span class="eff-lbl"></span><span class="eff-val"></span></div>' +
      (opt.locked ? '<p class="eff-locked"></p>' :
        '<div class="eff-ends"><span class="eff-faster"></span><span class="eff-smarter"></span></div>' +
        '<div class="eff-track" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="5">' +
        '<canvas class="eff-cv" aria-hidden="true"></canvas><div class="eff-ticks" aria-hidden="true">' +
        '<i></i><i></i><i></i><i></i><i></i><i></i></div><div class="eff-thumb" aria-hidden="true"></div></div>' +
        '<div class="eff-rec"></div>');
    el.querySelector(".eff-lbl").textContent = tw("eff.head");
    var valEl = el.querySelector(".eff-val");
    if (opt.locked) {
      el.querySelector(".eff-locked").textContent = tw("eff.locked");
      valEl.textContent = tw("eff." + value);
      return { set: function () {}, destroy: function () { el.innerHTML = ""; } };
    }
    el.querySelector(".eff-faster").textContent = tw("eff.faster");
    el.querySelector(".eff-smarter").textContent = tw("eff.smarter");
    var rec = el.querySelector(".eff-rec");
    rec.textContent = tw("eff.recommended");
    var track = el.querySelector(".eff-track"), thumb = el.querySelector(".eff-thumb");
    var cv = el.querySelector(".eff-cv"), ctx = cv.getContext && cv.getContext("2d");
    var parts = [], raf = 0, alive = true;
    for (var i = 0; i < 70; i++) parts.push({ x: Math.random(), y: Math.random(), s: Math.random() * 1.6 + 0.6, v: Math.random() * 0.0025 + 0.0008, p: Math.random() * 6 });

    function fillPx() { var w = track.clientWidth; return 13 + (w - 26) * ratioFromLevel(value); }
    function paint() {
      var i = LEVELS.indexOf(value);
      thumb.style.left = (fillPx() - 11) + "px";
      valEl.textContent = tw("eff." + value);
      track.setAttribute("aria-valuenow", String(i));
      track.setAttribute("aria-valuetext", tw("eff." + value));
      track.title = value === "ultra" ? tw("eff.ultra_hint") : "";
      rec.style.visibility = value === "medium" ? "visible" : "hidden";
    }
    function draw(t) {
      if (!alive || !ctx) return;
      var W = cv.width = track.clientWidth * 2, H = cv.height = track.clientHeight * 2;
      var fill = fillPx() * 2 + 20;
      var accent = getComputedStyle(el).getPropertyValue("--accent").trim() || "#ff7a3c";
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = 1;
      var g = ctx.createLinearGradient(0, 0, fill, 0);
      g.addColorStop(0, accent + "59");
      g.addColorStop(1, accent);
      ctx.fillStyle = g;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(0, 0, Math.max(fill, 0), H, H / 2); else ctx.rect(0, 0, Math.max(fill, 0), H);
      ctx.fill();
      parts.forEach(function (q) {
        if (!reduced()) { q.x += q.v; if (q.x > 1) q.x = 0; }
        var px = q.x * W;
        if (px > fill - 6) return;
        var d = px / Math.max(fill, 1);
        var a = (0.35 + 0.65 * Math.abs(Math.sin((reduced() ? 0 : t) / 500 + q.p))) * (0.3 + 0.7 * d);
        ctx.fillStyle = "rgba(255,255,255," + a.toFixed(2) + ")";
        ctx.beginPath(); ctx.arc(px, q.y * H, q.s * (1 + d), 0, 7); ctx.fill();
      });
      if (!reduced()) raf = requestAnimationFrame(draw);
    }
    function set(v, fire) {
      if (LEVELS.indexOf(v) < 0 || v === value) return;
      value = v; paint(); if (reduced()) draw(0);
      if (fire && opt.onChange) opt.onChange(v);
    }
    function fromEvent(e) {
      var r = track.getBoundingClientRect();
      set(levelFromRatio((e.clientX - r.left - 13) / Math.max(r.width - 26, 1)), true);
    }
    var dragging = false;
    track.addEventListener("pointerdown", function (e) { dragging = true; try { track.setPointerCapture(e.pointerId); } catch (x) {} fromEvent(e); });
    track.addEventListener("pointermove", function (e) { if (dragging) fromEvent(e); });
    track.addEventListener("pointerup", function () { dragging = false; });
    track.addEventListener("keydown", function (e) {
      var i = LEVELS.indexOf(value);
      if (e.key === "ArrowRight" || e.key === "ArrowUp") i++;
      else if (e.key === "ArrowLeft" || e.key === "ArrowDown") i--;
      else if (e.key === "Home") i = 0;
      else if (e.key === "End") i = 5;
      else return;
      e.preventDefault();
      set(LEVELS[clamp(i, 0, 5)], true);
    });
    paint();
    raf = requestAnimationFrame(draw);
    return {
      set: function (v) { set(v, false); },
      focus: function () { track.focus(); },
      destroy: function () { alive = false; cancelAnimationFrame(raf); el.innerHTML = ""; },
    };
  }
  api.mount = mount;
  window.JavisEffortSlider = api;
})();
```

- [ ] **Step 4: model-picker.js**:
  1. In `renderBar()` replace the line `if (et) et.textContent = "Effort: " + ...` and the variable `et` with:

```js
    const eb = $("effTxt");
    if (eb) eb.textContent = window.t("eff." + (EFFORT.find((e) => e[0] === state.reasoning) || EFFORT[0])[0]);
```
   (keep the `EFFORT` array and the `"off"`..`"ultra"` strings; delete `$("mbEffortTxt")`).
  2. In `renderPop()` delete the three lines that append `html += \`<div class="mb-eff-row">...` and the comment "Only the Effort row is appended here" (the original comment is in Vietnamese).
  3. Add after the `isOpen()` function:

```js
  // Thinking-level chip (0.148.0): split off from the model picker panel, opens a small box with a slider.
  let effSlider = null;
  function effOpen() {
    const pop = $("effPop"), btn = $("effBtn");
    if (!pop || !window.JavisEffortSlider) return;
    close(); closePlus();
    const eff = effective();
    pop.hidden = false;
    pop.style.left = btn ? (btn.offsetLeft) + "px" : "8px";
    if (btn) btn.setAttribute("aria-expanded", "true");
    effSlider = window.JavisEffortSlider.mount(pop, {
      value: state.reasoning,
      locked: window.JavisEffortSlider.isLocked(eff.provider, eff.model),
      onChange: async (v) => { state.reasoning = v; renderBar(); await saveModel({ reasoning: v }); },
    });
    if (effSlider.focus) effSlider.focus();
  }
  function effClose() {
    const pop = $("effPop"), btn = $("effBtn");
    if (effSlider) { effSlider.destroy(); effSlider = null; }
    if (pop) pop.hidden = true;
    if (btn) btn.setAttribute("aria-expanded", "false");
  }
  function effIsOpen() { const pop = $("effPop"); return pop && !pop.hidden; }
  function closePlus() { try { if (window.JavisComposerMenu) window.JavisComposerMenu.close(); } catch (e) {} }
```

  4. In `open()` (the model panel) add `effClose(); closePlus();` at the very start of the function.
  5. In the document `click` listener: replace the first two lines with

```js
    if (e.target.closest("#mbOpen")) { isOpen() ? close() : open(); return; }
    if (e.target.closest("#effBtn")) { effIsOpen() ? effClose() : effOpen(); return; }
    if (!e.target.closest("#effPop") && effIsOpen()) effClose();
    if (!e.target.closest("#mbPop") && !e.target.closest("#mbOpen")) { if (isOpen()) close(); return; }
```
   and delete the block `const eff = e.target.closest(".mb-eff-btn"); if (eff) {...}`.
  6. Escape listener: `if (e.key === "Escape") { if (isOpen()) close(); if (effIsOpen()) { effClose(); const b = $("effBtn"); if (b) b.focus(); } }`.
  7. In `window.JavisModelBar` add `effortLabel: function () { return window.t("eff." + state.reasoning); },`.
  8. After `chonModel`, call `renderBar()` as before (the level chip changes with it); if `effIsOpen()` then `effClose(); effOpen();` so the slider updates its lock for the new model.

- [ ] **Step 5: style.css** add after the `.eff-pop[hidden]` rule:

```css
.eff-pop { padding: 14px 16px; width: min(330px, calc(100vw - 32px)); }
.eff-head { display: flex; align-items: baseline; gap: 8px; font-size: 15px; }
.eff-lbl { color: var(--text2); }
.eff-val { color: var(--accent-ink); font-weight: 600; }
.eff-ends { display: flex; justify-content: space-between; font-size: 13px; color: var(--text2); margin: 12px 0 6px; }
.eff-track { position: relative; height: 28px; border-radius: 999px; background: var(--bg3); overflow: hidden; cursor: pointer; touch-action: none; }
.eff-track:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.eff-cv { position: absolute; inset: 0; width: 100%; height: 100%; }
.eff-ticks { position: absolute; inset: 0; display: flex; justify-content: space-between; align-items: center; padding: 0 13px; pointer-events: none; }
.eff-ticks i { width: 4px; height: 4px; border-radius: 50%; background: var(--text3); opacity: .6; }
.eff-thumb { position: absolute; top: 3px; width: 22px; height: 22px; border-radius: 50%; background: #fff; box-shadow: var(--shadow-1); transition: left .18s; }
.eff-rec { font-size: 12px; color: var(--text3); margin-top: 6px; padding-left: calc(40% - 18px); }
.eff-locked { margin: 10px 0 2px; font-size: 13px; color: var(--text2); line-height: 1.45; }
@media (prefers-reduced-motion: reduce) { .eff-thumb { transition: none; } }
```

(If `--shadow-1` does not exist in style.css, use `0 1px 3px rgba(0,0,0,.25)`; check with `grep -n "\-\-shadow-1" dashboard/style.css`.)

- [ ] **Step 6: i18n** add to vi.json and en.json (the same English text for the labels):
`eff.off` Off, `eff.low` Light, `eff.medium` Medium, `eff.high` High, `eff.xhigh` Extra, `eff.ultra` Ultra, `eff.head` Effort, `eff.faster` Faster, `eff.smarter` Smarter, `eff.recommended` Recommended, `eff.ultra_hint` "max effort"; `eff.locked`: vi "Model này đã gắn sẵn mức suy nghĩ trong tên. Đổi model để đổi mức." (Vietnamese on purpose, it is the vi.json value), en "This model has its effort built into its name. Pick another model to change it."

- [ ] **Step 7: index.html**: add `<script src="effort-slider.js?v=1"></script>` right before the `model-picker.js` line; bump `model-picker.js?v=` and `style.css?v=`.

- [ ] **Step 8: Run the tests**: `node tests/js/test_thanh_truot_effort.js` -> OK; `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/python/test_do_sau_suy_nghi.py`, `test_mobile_layout.py`, `node tests/js/test_i18n.mjs`, `node tests/js/test_studio_chon_model_agent.js` -> green.

- [ ] **Step 9: Commit**

```bash
git add dashboard/effort-slider.js dashboard/model-picker.js dashboard/index.html dashboard/style.css dashboard/i18n/vi.json dashboard/i18n/en.json tests/js/test_thanh_truot_effort.js
git commit -m "Composer: separate effort chip with an orange sparkle slider (Off to Ultra)"
```

---

### Task 4: Fast mode lightning button (saved state, tooltip per brain)

**Files:**
- Modify: `dashboard/model-picker.js`
- Modify: `dashboard/i18n/vi.json`, `en.json`
- Test: `tests/js/test_tia_set_fast.js` (new)

**Interfaces:**
- Consumes: `settings.model.fast` (Task 1), `#fastBtn` (Task 2).
- Produces: `window.JavisModelBar.fastNote(provider, model)` -> `{supported: bool, note: "i18n.key"}` (a pure function; it does not need exporting to node through `window.JavisFast`, the test reads it with vm). The `FAST_NOTE` constant in model-picker.js.

- [ ] **Step 1: Failing test** `tests/js/test_tia_set_fast.js`

```js
/* Fast mode lightning (0.148.0): tooltip per brain, the button is dimmed when the brain has none, saves settings.model.fast.

       node tests/js/test_tia_set_fast.js
*/
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "../..");
const src = fs.readFileSync(path.join(ROOT, "dashboard/model-picker.js"), "utf8");
const vi = require("../../dashboard/i18n/vi.json"), en = require("../../dashboard/i18n/en.json");
let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

const m = src.match(/\/\/ FAST_NOTE_BEGIN[\s\S]*?\/\/ FAST_NOTE_END/);
check("there is a FAST_NOTE block that can be extracted for testing", !!m);
const fastNote = new Function(m[0] + "\nreturn fastNote;")();
const cases = [
  ["anthropic-cli", "", true, "fast.claude"], ["anthropic-cli", "claude-opus-5-5", true, "fast.claude"],
  ["anthropic-cli", "claude-sonnet-5-5", false, "fast.model_none"], ["anthropic-api", "claude-opus-4-8", true, "fast.api"],
  ["openai-oauth", "gpt-6.1-sol", true, "fast.codex"], ["openai", "gpt-6-sol", true, "fast.api"],
  ["openrouter", "openai/gpt-6", true, "fast.api"], ["gemini", "gemini-4-argon", true, "fast.api"],
  ["grok-cli", "", false, "fast.none"], ["antigravity-cli", "gemini-3.8-flash-high", false, "fast.none"],
  ["groq", "x", false, "fast.none"], ["deepseek", "x", false, "fast.none"], ["ollama", "x", false, "fast.none"],
];
cases.forEach(([p, mo, sup, note]) => {
  const r = fastNote(p, mo);
  check(p + " " + (mo || "(default)") + " -> " + (sup ? "supported" : "not supported") + ", " + note, r.supported === sup && r.note === note);
});
["fast.claude", "fast.codex", "fast.api", "fast.none", "fast.model_none"].forEach(k =>
  check("key " + k + " exists in vi and en", !!vi[k] && !!en[k]));
check("the tooltip starts with 'Fast mode', with no on/off text shown on the page", src.indexOf('"Fast mode\\n" + window.t(') !== -1);
check("clicking the lightning saves settings.model.fast", src.indexOf("saveModel({ fast: state.fast })") !== -1);
check("the dimmed button uses aria-disabled, not disabled", src.indexOf('setAttribute("aria-disabled"') !== -1 && src.indexOf("fb.disabled") === -1);

if (fails.length) { console.log("\nFAIL - test_tia_set_fast: " + fails.length + " failures"); process.exit(1); }
console.log("\nOK - test_tia_set_fast: all pass");
```

- [ ] **Step 2: Run it and watch it fail**: `node tests/js/test_tia_set_fast.js` -> FAIL "there is a FAST_NOTE block".

- [ ] **Step 3: model-picker.js**: add after the `EFFORT` declaration:

```js
  // FAST_NOTE_BEGIN
  // Fast mode per brain (research of 15/10/2026, see docs/superpowers/specs/2026-10-15-composer-plus-fast-mode-design.md).
  // Claude only Opus 5.5, Opus 5, Opus 4.8; an empty model = the Claude Code default (Opus), so it counts as supported.
  function fastNote(provider, model) {
    const m = String(model || "").toLowerCase();
    const opusOk = !m || /opus-(5-5|5|4-8)(?![0-9])/.test(m);
    if (provider === "anthropic-cli") return opusOk ? { supported: true, note: "fast.claude" } : { supported: false, note: "fast.model_none" };
    if (provider === "anthropic-api") return opusOk ? { supported: true, note: "fast.api" } : { supported: false, note: "fast.model_none" };
    if (provider === "openai-oauth") return { supported: true, note: "fast.codex" };
    if (provider === "openai" || provider === "openrouter" || provider === "gemini") return { supported: true, note: "fast.api" };
    return { supported: false, note: "fast.none" };
  }
  // FAST_NOTE_END
```

In `state` add `fast: false`; in `loadState()` add `state.fast = m.fast === true;`. Add the function and call it at the end of `renderBar()`:

```js
  function renderFast() {
    const fb = $("fastBtn");
    if (!fb) return;
    const eff = effective();
    const n = fastNote(eff.provider, eff.model);
    fb.setAttribute("aria-pressed", n.supported && state.fast ? "true" : "false");
    fb.setAttribute("aria-disabled", n.supported ? "false" : "true");
    fb.title = "Fast mode\n" + window.t(n.note);
  }
```

In the `click` listener, right after the line that handles `#effBtn`:

```js
    if (e.target.closest("#fastBtn")) {
      const eff = effective();
      if (!fastNote(eff.provider, eff.model).supported) return;
      state.fast = !state.fast;
      renderFast();
      await saveModel({ fast: state.fast });
      return;
    }
```

In `window.JavisModelBar` add `fastNote: fastNote,`.

- [ ] **Step 4: i18n** (vi / en; the vi values are Vietnamese on purpose, they are the Vietnamese UI strings):
  - `fast.claude`: "Tính vào usage credits, giá gấp đôi, không trừ hạn mức gói." / "Billed to usage credits at twice the price, not to your plan limits."
  - `fast.codex`: "Tiêu hạn mức gói nhanh gấp 2,5 lần." / "Uses your plan limits 2.5 times faster."
  - `fast.api`: "Giá token cao hơn, khoảng gấp đôi." / "Higher token price, about twice the standard rate."
  - `fast.none`: "Bộ não này không có Fast mode." / "This brain has no Fast mode."
  - `fast.model_none`: "Model này không có Fast mode, chỉ Opus 5.5, Opus 5 và Opus 4.8." / "This model has no Fast mode; only Opus 5.5, Opus 5 and Opus 4.8 do."

- [ ] **Step 5: Run the tests**: `node tests/js/test_tia_set_fast.js` -> OK; `node tests/js/test_i18n.mjs` -> green.

- [ ] **Step 6: Commit**

```bash
git add dashboard/model-picker.js dashboard/i18n/vi.json dashboard/i18n/en.json tests/js/test_tia_set_fast.js
git commit -m "Composer: Fast mode bolt saves settings.model.fast, tooltip per brain"
```

---

### Task 5: Expandable "+" menu (6 items, Ctrl+U, folders, files in the brain)

**Files:**
- Create: `dashboard/composer-plus.js`
- Modify: `dashboard/app.js` (expose `window.JavisAttach`, after the `fileInput` listener ~line 3550)
- Modify: `dashboard/index.html` (`<script src="composer-plus.js?v=1"></script>` after `model-picker.js`)
- Modify: `dashboard/style.css` (`.cp-menu*` rules)
- Modify: `dashboard/i18n/vi.json`, `en.json`
- Test: `tests/js/test_menu_cong.js` (new)

**Interfaces:**
- Consumes: `#plusBtn`, `#plusMenu`, `#folderInput`, `#chatInput` (Task 2); `GET /files/search`, `GET /files/resolve` (Task 1); `GET /connect/catalog`, `GET /connect/health`, `GET /agents`, `GET /workflows`.
- Produces: `window.JavisComposerMenu = { register(item), list(), open(), close(), isOpen() }`, item = `{ id, order, icon (svg string), label (i18n key), hint?: () => string, run?: (ctx) => void, submenu?: (ctx) => Promise<Array<{label, hint?, dot?: "ok"|"bad"|"unknown", run}>> }`. Node: `module.exports = { createRegistry, pickFolderFiles, runQueue, MAX_FOLDER_FILES }`. app.js: `window.JavisAttach = { pick(), upload(file) -> Promise, addBrainFile({name, path, size, kind}), note(text) }`.

- [ ] **Step 1: Failing test** `tests/js/test_menu_cong.js`

```js
/* The composer's "+" menu (0.148.0): registry, folder filtering, upload queue.

       node tests/js/test_menu_cong.js
*/
const fs = require("fs");
const path = require("path");
const P = require("../../dashboard/composer-plus.js");
const ROOT = path.join(__dirname, "../..");
const src = fs.readFileSync(path.join(ROOT, "dashboard/composer-plus.js"), "utf8");
const app = fs.readFileSync(path.join(ROOT, "dashboard/app.js"), "utf8");
const html = fs.readFileSync(path.join(ROOT, "dashboard/index.html"), "utf8");
let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

const reg = P.createRegistry();
reg.register({ id: "b", order: 20, label: "x.b" });
reg.register({ id: "a", order: 10, label: "x.a" });
reg.register({ id: "b", order: 5, label: "x.b2" });
check("the registry sorts by order, and registering the same id again replaces it", reg.list().map(i => i.id + ":" + i.label).join(",") === "b:x.b2,a:x.a");

const f = (rel) => ({ name: rel.split("/").pop(), webkitRelativePath: rel });
let r = P.pickFolderFiles([f("du-an/a.md"), f("du-an/.env"), f("du-an/.git/config"), f("du-an/node_modules/x/i.js"), f("du-an/con/b.csv")]);
check("folder: skips hidden files, .git, node_modules", r.files.map(x => x.name).join(",") === "a.md,b.csv" && r.skipped === 3 && r.over === 0);
const many = []; for (let i = 0; i < 61; i++) many.push(f("d/" + i + ".txt"));
r = P.pickFolderFiles(many);
check("folder: cap of " + P.MAX_FOLDER_FILES + " files, reports the overflow", r.files.length === P.MAX_FOLDER_FILES && r.over === 11);
r = P.pickFolderFiles([f("d/.DS_Store")]);
check("a folder of only hidden files: no files left", r.files.length === 0 && r.skipped === 1);

(async () => {
  let running = 0, max = 0, done = [];
  await P.runQueue([1, 2, 3, 4, 5, 6, 7, 8, 9], async (x) => {
    running++; max = Math.max(max, running); await new Promise(res => setTimeout(res, 5)); running--; done.push(x);
    if (x === 3) throw new Error("broken");
  }, 4);
  check("queue: at most 4 files at once, a failed file does not block the next ones", max === 4 && done.length === 9);

  ["attach", "folder", "brain_file", "commands", "connections", "partners"].forEach(id =>
    check("default item has id " + id, src.indexOf('id: "' + id + '"') !== -1));
  check("Ctrl+U blocks the browser default (view source)", /key === "u"[\s\S]{0,200}preventDefault/.test(src));
  check("the commands item opens the / menu through an input event", src.indexOf('new Event("input"') !== -1);
  check("calling an assistant inserts the right token of the / menu", src.indexOf('"/agent-" + ') !== -1 && src.indexOf('"/workflow-" + ') !== -1);
  check("app.js exposes JavisAttach (pick, upload, addBrainFile, note)", /window\.JavisAttach = \{[\s\S]*pick[\s\S]*upload[\s\S]*addBrainFile[\s\S]*note/.test(app));
  check("composer-plus.js loads after model-picker.js", html.indexOf("model-picker.js") < html.indexOf("composer-plus.js"));
  check("no Vietnamese text in the running code of composer-plus.js",
    !/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i.test(src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")));
  if (fails.length) { console.log("\nFAIL - test_menu_cong: " + fails.length + " failures"); process.exit(1); }
  console.log("\nOK - test_menu_cong: all pass");
})();
```

- [ ] **Step 2: Run it and watch it fail**: `node tests/js/test_menu_cong.js` -> require error.

- [ ] **Step 3: app.js**: right after the `fileInput.addEventListener("change", ...)` block add (no Vietnamese text in running code):

```js
// The composer's "+" menu (composer-plus.js, 0.148.0) shares the upload path and the attachment list.
window.JavisAttach = {
  pick: () => fileInput.click(),
  upload: (f) => uploadFile(f),
  addBrainFile: (it) => {
    if (!it || !it.path || pendingAttachments.some(a => a.path === it.path)) return;
    pendingAttachments.push({ name: it.name, kind: it.kind || "file", preview: null, path: it.path,
      size: it.size || 0, sources: null, attachments: null, uploading: false, loi: false, xong: Promise.resolve() });
    renderChips();
  },
  note: (s) => { attachNote = String(s || ""); renderChips(); },
};
```

- [ ] **Step 4: Create `dashboard/composer-plus.js`**

```js
/* composer-plus.js - the composer's "+" menu (0.148.0).
 * One registry: a new feature only needs JavisComposerMenu.register({...}), with no change to the composer.
 * The pure parts (registry, folder filter, queue) are tested with node.
 */
(function () {
  "use strict";
  var MAX_FOLDER_FILES = 50, UPLOAD_PARALLEL = 4;
  var SKIP_DIR = /(^|\/)(\.git|node_modules|__pycache__|\.venv|\.obsidian|\.trash)(\/|$)/;

  function createRegistry() {
    var items = [];
    return {
      register: function (it) {
        items = items.filter(function (x) { return x.id !== it.id; });
        items.push(it);
        items.sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
      },
      list: function () { return items.slice(); },
    };
  }
  function pickFolderFiles(files) {
    var keep = [], skipped = 0;
    Array.prototype.forEach.call(files || [], function (f) {
      var rel = String(f.webkitRelativePath || f.name || "");
      var base = rel.split("/").pop();
      if (SKIP_DIR.test(rel) || base.charAt(0) === ".") { skipped++; return; }
      keep.push(f);
    });
    return { files: keep.slice(0, MAX_FOLDER_FILES), skipped: skipped, over: Math.max(0, keep.length - MAX_FOLDER_FILES) };
  }
  function runQueue(list, work, parallel) {
    var i = 0;
    function next() {
      if (i >= list.length) return Promise.resolve();
      var x = list[i++];
      return Promise.resolve().then(function () { return work(x); }).catch(function () {}).then(next);
    }
    var lanes = [];
    for (var k = 0; k < Math.min(parallel || UPLOAD_PARALLEL, list.length); k++) lanes.push(next());
    return Promise.all(lanes);
  }

  var pure = { createRegistry: createRegistry, pickFolderFiles: pickFolderFiles, runQueue: runQueue, MAX_FOLDER_FILES: MAX_FOLDER_FILES };
  if (typeof module !== "undefined" && module.exports) module.exports = pure;
  if (typeof document === "undefined") return;

  var reg = createRegistry();
  function tw(k, v) { return window.t ? window.t(k, v) : k; }
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function brain() { try { return (window.JavisSessions && window.JavisSessions.brain()) || "brain"; } catch (e) { return "brain"; } }
  function getJson(url) { return fetch(url, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function input() { return $("chatInput"); }

  function insertToken(text) {
    var el = input();
    if (!el) return;
    el.focus();
    var a = el.selectionStart || 0, b = el.selectionEnd || 0, v = el.value;
    var before = v.slice(0, a);
    var lead = before && !/\s$/.test(before) ? " " : "";
    el.value = before + lead + text + v.slice(b);
    var pos = (before + lead + text).length;
    el.setSelectionRange(pos, pos);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // ---- menu box ----
  var menu = null, btn = null, view = [], active = 0;
  function isOpen() { return !!menu && !menu.hidden; }
  function close() {
    if (!menu) return;
    menu.hidden = true; menu.innerHTML = "";
    if (btn) btn.setAttribute("aria-expanded", "false");
  }
  function closeOthers() {
    try { var mb = $("mbPop"); if (mb) mb.hidden = true; } catch (e) {}
    try { var ep = $("effPop"); if (ep && !ep.hidden) { var eb = $("effBtn"); if (eb) eb.click(); } } catch (e) {}
  }
  function render(rows, title) {
    view = rows; active = 0;
    var head = title ? '<button type="button" class="cp-mi cp-back" data-back="1">' + ICON.back + '<span>' + esc(title) + '</span></button><div class="cp-sep"></div>' : "";
    menu.innerHTML = head + rows.map(function (r, i) {
      if (r.sep) return '<div class="cp-sep"></div>';
      var dot = r.dot ? '<span class="cp-dot cp-dot-' + r.dot + '"></span>' : "";
      return '<button type="button" class="cp-mi" role="menuitem" data-i="' + i + '">' + (r.icon || dot) +
        '<span class="cp-mi-lbl">' + esc(r.label) + '</span>' + (r.hint ? '<span class="cp-mi-hint' + (r.warn ? " cp-warn" : "") + '">' + esc(r.hint) + "</span>" : "") +
        (r.sub ? ICON.chevron : "") + "</button>";
    }).join("");
    focusRow(0);
  }
  function rowsEls() { return menu ? Array.prototype.slice.call(menu.querySelectorAll(".cp-mi")) : []; }
  function focusRow(i) { var els = rowsEls(); if (!els.length) return; active = (i + els.length) % els.length; els[active].focus(); }
  function topRows() {
    return reg.list().map(function (it) {
      return { icon: it.icon, label: tw(it.label), hint: it.hint ? it.hint() : "", warn: !!it.warn, sub: !!it.submenu, item: it };
    });
  }
  function open() {
    if (!menu || !btn) return;
    closeOthers();
    menu.hidden = false; btn.setAttribute("aria-expanded", "true");
    render(topRows());
  }
  function choose(r) {
    if (!r) return;
    if (r.item && r.item.submenu) {
      var it = r.item;
      render([{ label: tw("cp.loading") }], tw(it.label));
      Promise.resolve(it.submenu()).then(function (rows) {
        if (!isOpen()) return;
        render(rows && rows.length ? rows : [{ label: tw(it.emptyKey || "cp.empty") }], tw(it.label));
      });
      return;
    }
    var run = r.run || (r.item && r.item.run);
    if (run) { close(); run(); }
  }

  // ---- default items ----
  var ICON = {
    clip: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
    folder: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    file: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/></svg>',
    slash: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M14 7l-4 10"/></svg>',
    plug: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 2v6M15 2v6M7 8h10v3a5 5 0 0 1-10 0zM12 16v6"/></svg>',
    users: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a5 5 0 0 1 3.5 6"/></svg>',
    chevron: '<svg class="cp-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
    back: '<svg class="cp-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6"/></svg>',
  };
  var badConn = 0;

  reg.register({ id: "attach", order: 10, icon: ICON.clip, label: "cp.attach", hint: function () { return /Mac/.test(navigator.platform) ? "Cmd+U" : "Ctrl+U"; },
    run: function () { if (window.JavisAttach) window.JavisAttach.pick(); } });
  reg.register({ id: "folder", order: 20, icon: ICON.folder, label: "cp.folder", run: function () { var f = $("folderInput"); if (f) f.click(); } });
  reg.register({ id: "brain_file", order: 30, icon: ICON.file, label: "cp.brain_file", emptyKey: "cp.brain_empty",
    submenu: function () { return Promise.resolve(brainSearchRows("")); } });
  reg.register({ id: "commands", order: 40, icon: ICON.slash, label: "cp.commands", hint: function () { return "/"; },
    run: function () { insertToken("/"); } });
  reg.register({ id: "connections", order: 50, icon: ICON.plug, label: "cp.connections", emptyKey: "cp.conn_none",
    hint: function () { return badConn ? tw("cp.conn_bad", { n: badConn }) : ""; },
    submenu: function () {
      return Promise.all([getJson("/connect/catalog"), getJson("/connect/health")]).then(function (res) {
        var cat = (res[0] && res[0].catalog) || [], conns = (res[0] && res[0].connections) || [];
        var health = (res[1] && res[1].health) || {};
        var names = {}; cat.forEach(function (c) { names[c.id] = c.name; });
        var rows = conns.map(function (c) {
          var h = health[c.id];
          return { label: c.label || names[c.connector] || names[c.catalog_id] || c.name || c.id,
            dot: !h ? "unknown" : (h.ok ? "ok" : "bad"), hint: h && !h.ok ? (h.message || "") : "",
            run: function () { goPage("mcp"); } };
        });
        if (rows.length) rows.push({ sep: true });
        rows.push({ label: tw("cp.conn_open"), run: function () { goPage("mcp"); } });
        return rows;
      });
    } });
  reg.register({ id: "partners", order: 60, icon: ICON.users, label: "cp.partners", emptyKey: "cp.partners_none",
    submenu: function () {
      var b = encodeURIComponent(brain());
      return Promise.all([getJson("/agents?brain=" + b), getJson("/workflows?brain=" + b)]).then(function (res) {
        var ag = (res[0] && (res[0].agents || res[0])) || [], wf = (res[1] && (res[1].workflows || res[1])) || [];
        var rows = [];
        (Array.isArray(ag) ? ag : []).forEach(function (a) { if (a && a.slug) rows.push({ label: a.name || a.slug, hint: a.role || "", run: function () { insertToken("/agent-" + a.slug + " "); } }); });
        (Array.isArray(wf) ? wf : []).forEach(function (w) { if (w && w.slug && w.status === "active") rows.push({ label: w.name || w.slug, hint: tw("cp.workflow"), run: function () { insertToken("/workflow-" + w.slug + " "); } }); });
        return rows;
      });
    } });

  function goPage(id) { try { window.Alpine.store("nav").go(id); } catch (e) { location.hash = "#" + id; } }

  // ---- pick a file in the brain: a search box right in the menu ----
  var brainSeq = 0;
  function brainSearchRows(q) {
    setTimeout(function () { mountBrainSearch(q); }, 0);
    return [{ label: tw("cp.brain_search_hint") }];
  }
  function mountBrainSearch(q) {
    if (!isOpen()) return;
    menu.innerHTML = '<button type="button" class="cp-mi cp-back" data-back="1">' + ICON.back + "<span>" + esc(tw("cp.brain_file")) + "</span></button>" +
      '<input type="search" class="cp-search" placeholder="' + esc(tw("cp.brain_search_ph")) + '" aria-label="' + esc(tw("cp.brain_search_ph")) + '">' +
      '<div class="cp-results"></div>';
    var box = menu.querySelector(".cp-search"), out = menu.querySelector(".cp-results");
    box.value = q || "";
    box.focus();
    var timer = 0;
    box.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(search, 180); });
    function search() {
      var term = box.value.trim(), seq = ++brainSeq;
      if (!term) { out.innerHTML = ""; return; }
      getJson("/files/search?mode=name&limit=20&brain=" + encodeURIComponent(brain()) + "&q=" + encodeURIComponent(term)).then(function (d) {
        if (seq !== brainSeq || !isOpen()) return;
        var items = (d && d.items) || [];
        out.innerHTML = items.length ? items.map(function (it, i) {
          return '<button type="button" class="cp-mi" data-file="' + i + '">' + ICON.file + '<span class="cp-mi-lbl">' + esc(it.name || it.path) +
            '</span><span class="cp-mi-hint">' + esc(it.path || "") + "</span></button>";
        }).join("") : '<div class="cp-empty">' + esc(tw("cp.brain_empty")) + "</div>";
        Array.prototype.forEach.call(out.querySelectorAll("[data-file]"), function (el) {
          el.addEventListener("click", function () {
            var it = items[+el.getAttribute("data-file")];
            getJson("/files/resolve?brain=" + encodeURIComponent(brain()) + "&path=" + encodeURIComponent(it.path)).then(function (r) {
              if (r && r.ok && window.JavisAttach) window.JavisAttach.addBrainFile(r);
              close(); var i2 = input(); if (i2) i2.focus();
            });
          });
        });
      });
    }
    if (q) search();
  }

  // ---- folder ----
  function onFolder(e) {
    var r = pickFolderFiles(e.target.files);
    e.target.value = "";
    var notes = [];
    if (r.skipped) notes.push(tw("cp.folder_skipped", { n: r.skipped }));
    if (r.over) notes.push(tw("cp.folder_over", { max: MAX_FOLDER_FILES }));
    if (!r.files.length) notes.push(tw("cp.folder_empty"));
    else notes.push(tw("cp.folder_flat"));
    if (window.JavisAttach) window.JavisAttach.note(notes.join(" "));
    if (r.files.length && window.JavisAttach) runQueue(r.files, function (f) { return window.JavisAttach.upload(f); }, UPLOAD_PARALLEL);
  }

  // ---- wire up events ----
  function init() {
    menu = $("plusMenu"); btn = $("plusBtn");
    if (!menu || !btn) return;
    btn.addEventListener("click", function (e) { e.stopPropagation(); isOpen() ? close() : open(); });
    menu.addEventListener("click", function (e) {
      e.stopPropagation();
      if (e.target.closest("[data-back]")) { render(topRows()); return; }
      var el = e.target.closest("[data-i]");
      if (el) choose(view[+el.getAttribute("data-i")]);
    });
    menu.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); focusRow(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); focusRow(active - 1); }
      else if (e.key === "Escape") { e.preventDefault(); close(); btn.focus(); }
      else if (e.key === "ArrowLeft" && menu.querySelector("[data-back]")) { e.preventDefault(); render(topRows()); }
    });
    document.addEventListener("click", function (e) { if (isOpen() && !menu.contains(e.target)) close(); });
    var fi = $("folderInput"); if (fi) fi.addEventListener("change", onFolder);
    document.addEventListener("keydown", function (e) {
      var key = String(e.key || "").toLowerCase();
      if (key === "u" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
        var a = document.activeElement;
        var other = a && a !== input() && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
        if (other) return;
        e.preventDefault();
        if (window.JavisAttach) window.JavisAttach.pick();
      }
    });
    // Count the connections that need redoing for the "Connections" row (read when the page opens, so it does not bother the server).
    getJson("/connect/health").then(function (d) {
      var h = (d && d.health) || {};
      badConn = Object.keys(h).filter(function (k) { return h[k] && h[k].ok === false; }).length;
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();

  window.JavisComposerMenu = { register: reg.register, list: reg.list, open: open, close: close, isOpen: isOpen };
})();
```

(Check the return shape of `GET /agents` and `GET /workflows` with `grep -n '@app.get("/agents")' -A30 server/main.py` and similarly for `/workflows`; if the list key differs from `agents`/`workflows`, fix the two lines `res[0].agents`/`res[1].workflows` accordingly. Likewise the label field of one connection in `/connect/catalog` `connections[]`: see `grep -n '"connections"' server/main.py` around line 4498.)

- [ ] **Step 5: style.css** add after `.cp-menu[hidden]`:

```css
.cp-menu { left: 8px; width: min(320px, calc(100vw - 32px)); max-height: min(60vh, 440px); overflow: auto; padding: 6px; }
.cp-mi {
  display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 10px; border: none; border-radius: 8px;
  background: transparent; color: var(--text); font: inherit; font-size: 14px; text-align: left; cursor: pointer;
}
.cp-mi:hover, .cp-mi:focus-visible { background: var(--bg3); outline: none; }
.cp-ic { flex: none; width: 18px; height: 18px; }
.cp-chev { flex: none; width: 15px; height: 15px; margin-left: 4px; color: var(--text3); }
.cp-mi-lbl { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cp-mi-hint { flex: 0 1 auto; max-width: 45%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--text3); }
.cp-warn { color: var(--warn-ink); }
.cp-back { color: var(--text2); font-weight: 600; }
.cp-sep { height: 1px; background: var(--border); margin: 4px 6px; }
.cp-dot { flex: none; width: 8px; height: 8px; border-radius: 50%; margin: 0 5px; background: var(--warn-ink); }
.cp-dot-ok { background: var(--green, #3fb27f); }
.cp-dot-bad { background: var(--red); }
.cp-search { width: 100%; box-sizing: border-box; margin: 4px 0 6px; padding: 7px 9px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font: inherit; font-size: 14px; }
.cp-search:focus { outline: none; border-color: var(--accent); }
.cp-empty { padding: 8px 10px; font-size: 13px; color: var(--text3); }
```

- [ ] **Step 6: i18n** (vi / en; the vi values are Vietnamese on purpose, they are the Vietnamese UI strings, so each is given with its en value):
`cp.attach` "Đính kèm file hoặc ảnh" / "Add files or photos"; `cp.folder` "Đính kèm thư mục" / "Add a folder"; `cp.brain_file` "Chọn file trong brain" / "Pick a file from the brain"; `cp.commands` "Lệnh và kỹ năng" / "Commands and skills"; `cp.connections` "Kết nối" / "Connections"; `cp.conn_bad` "{n} cần kết nối lại" / "{n} need reconnecting"; `cp.conn_open` "Mở trang Kết nối" / "Open the Connections page"; `cp.conn_none` "Chưa có kết nối nào" / "No connections yet"; `cp.partners` "Gọi trợ lý hoặc quy trình" / "Call an assistant or workflow"; `cp.partners_none` "Chưa có trợ lý hay quy trình nào" / "No assistants or workflows yet"; `cp.workflow` "quy trình" / "workflow"; `cp.loading` "Đang tải..." / "Loading..."; `cp.empty` "Không có mục nào" / "Nothing here"; `cp.brain_search_ph` "Gõ tên file" / "Type a file name"; `cp.brain_search_hint` "Gõ tên file để tìm" / "Type a file name to search"; `cp.brain_empty` "Không thấy file nào" / "No matching file"; `cp.folder_skipped` "Đã bỏ {n} file ẩn hoặc file hệ thống." / "Skipped {n} hidden or system files."; `cp.folder_over` "Thư mục có hơn {max} file, chỉ gửi {max} file đầu." / "The folder has more than {max} files; only the first {max} were added."; `cp.folder_empty` "Thư mục không có file nào gửi được." / "The folder has no files to add."; `cp.folder_flat` "File được gửi phẳng, không giữ cấu trúc thư mục." / "Files are added flat; the folder structure is not kept."

- [ ] **Step 7: index.html**: `<script src="composer-plus.js?v=1"></script>` right after the `model-picker.js` line; bump `app.js?v=`, `style.css?v=`.

- [ ] **Step 8: Run the tests**: `node tests/js/test_menu_cong.js` -> OK; `node tests/js/test_i18n.mjs` (app.js still has exactly 12 lines with Vietnamese text) -> green; `node tests/js/test_keo_tha_anh_iphone.js` and the other JS tests that touch `uploadFile`/`fileInput` (`grep -rln "uploadFile\|fileInput" tests/js`) -> green.

- [ ] **Step 9: Commit**

```bash
git add dashboard/composer-plus.js dashboard/app.js dashboard/index.html dashboard/style.css dashboard/i18n/vi.json dashboard/i18n/en.json tests/js/test_menu_cong.js
git commit -m "Composer: extensible plus menu (files, folder, brain file, commands, connections, assistants)"
```

---

### Task 6: The "/" menu anchors to the box, does not cover the attachments

**Files:**
- Modify: `dashboard/chat-slash.js:252-257` (`positionBox`)
- Test: `tests/js/test_khung_go.js` (add one check)

- [ ] **Step 1: Add a check to test_khung_go.js** (before the `if (fails.length)` line):

```js
const slash = fs.readFileSync(path.join(ROOT, "dashboard/chat-slash.js"), "utf8");
check("the / menu anchors to the composer box (#hudVoice), not covering the attachments",
  slash.indexOf('input.closest(".hud-voice") || input') !== -1);
```

- [ ] **Step 2: Run it and watch it fail**: `node tests/js/test_khung_go.js` -> the new check FAILS.

- [ ] **Step 3: chat-slash.js** replace the body of `positionBox`:

```js
    function positionBox(input) {
      // Since 0.148.0 the input sits inside a box that has the attachments above it; anchor to the box so the attachments are not covered.
      var anchor = input.closest(".hud-voice") || input;
      var rect = anchor.getBoundingClientRect();
      box.style.left = rect.left + "px";
      box.style.width = rect.width + "px";
      box.style.bottom = (window.innerHeight - rect.top + 6) + "px";
    }
```

- [ ] **Step 4: Run**: `node tests/js/test_khung_go.js` -> OK; `node tests/js/test_chat_slash.js` (if it exists, `ls tests/js | grep slash`) -> green. Bump `chat-slash.js?v=`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/chat-slash.js dashboard/index.html tests/js/test_khung_go.js
git commit -m "Composer: slash menu anchors to the card instead of the textarea"
```

---

### Task 7: Visual check, full test run, version, PR

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`, `CHANGELOG.en.md`
- Modify: `docs/02-tro-chuyen-va-giong-noi.md`, `docs/en/02-*.md` (the paragraph describing the composer: the "+" button, the thinking-level chip, the lightning)

- [ ] **Step 1: Visual check**: run the worktree sandbox server (port 7788, temporary state; per the "Sandbox UI inspection" note) or build a preview page that uses the real CSS/JS as was done in #655. Check: desktop light and dark; phone at 375px (the model chip goes to the top of the page; the row keeps "+", the level chip, the lightning, mic, send); the Chat page, Coding (the context chip row still shows), Workspace; open and close each popover; drag the slider; turn the lightning on; paste an image, drag and drop a file; Ctrl+U; make one voice call.

- [ ] **Step 2: Full test run**: `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py --js` (all green) and `/d/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py --py` (only the 14 files that are already red on this machine remain; compare the list with the "Fake red tests on this machine" note).

- [ ] **Step 3: Version**: `git fetch origin`, read `git show origin/main:VERSION` and the numbers of the open PRs (`gh pr list --state open --json title`), take the next number nobody holds (expected 0.148.0). Write VERSION; add a block to CHANGELOG.md and CHANGELOG.en.md (short, for a phone screen):

```markdown
## [0.148.0] - 2026-10-15
### Improved
- **The composer is now one block, like Claude.** Attached images, the input and one row of buttons share a single rounded box; the mic is smaller and sits next to the send button.
- **The "+" button gathers everything you can add to a message:** a file or photo (Ctrl+U), a whole folder, a file already in the brain, commands and skills, connections (it shows which one needs reconnecting), and calling an assistant or workflow.
- **The thinking level has its own chip**, and clicking it opens an Off, Light, Medium, High, Extra, Ultra slider; you no longer have to open the model list.
- **A Fast mode lightning button** next to it; hover to see the cost note. This version saves the choice; the next one wires it into each brain.
```

- [ ] **Step 4: Commit, push, open the PR, turn on auto-merge**

```bash
git add VERSION CHANGELOG.md CHANGELOG.en.md docs/
git commit -m "0.148.0: one-card composer with a plus menu, effort slider chip and Fast mode bolt"
git push -u origin claude/composer-plus
gh pr create --title "0.148.0: one-card composer with a plus menu, effort slider chip and Fast mode bolt" --body-file "$SCRATCH/pr-composer-plus.md"
gh pr merge --auto --rebase
```

`$SCRATCH` is the session's scratchpad folder. Write `pr-composer-plus.md` there before running the commands: the PR description summarizes the spec, lists the tests that were changed on purpose (test_theme_tokens 18px -> 24px) and why, and ends with the line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
