# `/` Command Box for the Dashboard + `/notes` Skill - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web chat box accept `/` commands (a suggestion menu like Telegram/Claude), with the first command `/notes` saving the current message verbatim into `sources/` and then automatically distilling it into the wiki if it is worthy.

**Architecture:** The unifying principle is `/<slug>` = call skill `<slug>` (exactly the existing Telegram semantics at `server/main.py:5076`). `/notes` is a bundled SYSTEM skill at `.claude/skills/notes/SKILL.md`, which `system_sync.py` spreads into every brain automatically. The web adds one plain frontend module (`chat-slash.js`) that handles command classification + the menu, and `app.js` intercepts `/` in `sendMessage` and routes it. The backend barely changes.

**Tech Stack:** Python 3 (FastAPI, run inside `.venv`), plain browser JavaScript (IIFE + dual export `window`/`module.exports`), frontend tests run headless with `node dashboard/test_*.js`.

## Global Constraints

- The main language is Vietnamese; strings shown to the user MUST have diacritics, even when written in code. (Translation note: in this English edition, user-facing strings are written in English.)
- NEVER use the em dash character (U+2014) anywhere (chat, files, code, wiki). Use `-`.
- A skill created through this process is a core capability -> `.claude/skills/notes/SKILL.md` (the system's canonical source).
- The SKILL.md `description` is AT MOST 150 characters (the router hard-cuts at 150). `group` is REQUIRED, pick the group closest to existing skills.
- The `notes` skill keeps the note verbatim and does NOT re-edit the user's words.
- Writing `sources/`/`wiki/` is level `safe`, allowed to run because the person typed the command; it does NOT do money/order/post/message actions.
- The frontend module follows the existing pattern (see `dashboard/chat-ask.js`): IIFE, `window.X` for the browser + `module.exports` for node tests.
- The web skill-invocation string MUST MATCH the Telegram pattern (`server/main.py:5079-5080`) so the two channels stay consistent.

---

## File Structure

- Create `.claude/skills/notes/SKILL.md` - system skill, `system_sync` spreads it into brains.
- Create `dashboard/chat-slash.js` - pure logic (parse/route/menu-data) + DOM menu controller + dual export.
- Create `dashboard/test_chat_slash.js` - node tests for the pure functions.
- Edit `dashboard/app.js` - intercept `/` in `sendMessage()`, route session-command vs skill.
- Edit `dashboard/index.html` - load `chat-slash.js` BEFORE `app.js`.
- Edit `dashboard/style.css` - command menu CSS.
- Edit `CHANGELOG.md` + `VERSION` - release (last task).

---

## Task 1: `notes` system skill

**Files:**
- Create: `.claude/skills/notes/SKILL.md`
- Test: run python in `.venv` to verify the skill is discovered + the frontmatter is valid.

**Interfaces:**
- Produces: skill slug `notes`, discoverable via `skill_router.list_skills()` and present in `system_sync.system_skill_slugs()`. The frontend maps `/notes` -> slug `notes`.

- [ ] **Step 1: Find the closest group**

Read the group of the existing system skills to pick a consistent group (do not leave it empty -> "Chung", i.e. "General"):

Run: `rg -n "^group:" .claude/skills/*/SKILL.md`
Expected: you see the groups in use (e.g. `ingest-source` = `AI`). Pick `AI` for `notes` (same knowledge/wiki family as ingest/query/lint). If you observe a better-fitting group, use that one.

- [ ] **Step 2: Write SKILL.md**

Create `.claude/skills/notes/SKILL.md`:

```markdown
---
name: Notes
description: Save the current message verbatim into sources/ (images included), then distil it up to the wiki if it earns a place.
group: AI
---

# NOTES - quickly save 1 note into the Second Brain (kept verbatim), wiki if worthy

## When to use

Activate when the user types the `/notes` command (web or Telegram), or says "save this note",
"jot this into the brain". This is the QUICK-CAPTURE version: save verbatim first, distil later
if worthy. Different from `ingest-source` (for a source already sitting in `sources/`, which always distils).

Read the vault schema (`CLAUDE.md`/`AGENTS.md` at the brain root) before writing.

## Where the note content comes from

- The "request" part the user types AFTER `/notes` = the note body. Keep it EXACTLY VERBATIM, do not edit,
  do not summarize, do not add or remove a single word.
- Files/images attached in the SAME message (paths are provided) = the note's documents.
- ONLY the current message. Do not pull in the previous answer or earlier turns.

## Steps

1. Identify the current brain folder: `sources/`, `attachments/`, `wiki/`.
2. Name the file: `sources/note-YYYY-MM-DD-HHmm-<first-few-words-without-diacritics>.md` (use the real date and time,
   taken via the datetime tool if available; the slug comes from the first ~4-6 words of the note, diacritics removed, joined with hyphens).
3. Write the source file with frontmatter:
   - `type: source`
   - `source_kind: own-note`
   - `status: unprocessed`
   - `created: <YYYY-MM-DD HH:mm>`
   - `tags: [note]`
   Body = the original text VERBATIM. For attached images: move/ensure the file is in
   `attachments/`, embed `![[image-name]]` in the body. If the file is already in `sources/`/
   `attachments/` because of a web upload, use that one, do NOT duplicate it.
4. Judge wiki-worthiness (same criteria as ingest-source): a reusable concept / framework / principle /
   procedure / insight -> WORTHY. Confessions, small chores, passing reminders, shopping
   lists -> NOT worthy.
5. If WORTHY: apply the INGEST operation - write/update `wiki/` pages with all 3 disciplines (every specific claim with
   `[[Source]]`; distinguish "(target)"/"(actual as of ...)"; a contradiction with an old page means
   adding `## Mâu thuẫn` ("Contradiction") + appending to `wiki/_open-questions.md`, do NOT overwrite). Every page self-contained in
   context (1-2 positioning sentences at the top) + `aliases:` if there are other names. Update `wiki/index.md`
   (add a link line + a 1-line description). Append to `wiki/log.md`:
   `## [YYYY-MM-DD] notes | <note name>` + source/created/updated/insight. Set the source
   `status: processed`, `processed_at: <...>`, `wiki_links: [...]`.
6. If NOT worthy: keep the source (`status: unprocessed`), do NOT touch the wiki.
7. Report BRIEFLY in spoken prose (no tables, no long dashes, no em dash): the note was saved to
   `[[source-name]]`; whether it went up to the wiki, and if so which page. If there is an image, embed it again with `![...](...)`
   so the user can see it.

## Safety

Writing `sources/` + `wiki/` is level `safe`, allowed to run because the user deliberately typed the command. Do NOT create
orders, do NOT spend money, do NOT publish posts, do NOT send messages. Only write files in the vault.
```

- [ ] **Step 3: Verify the skill is discovered + the frontmatter is valid**

Run:
```bash
.venv/Scripts/python -c "import sys; sys.path.insert(0,'server'); import system_sync, skill_router; slugs=system_sync.system_skill_slugs(); print('in system slugs:', 'notes' in slugs); import re,io; t=open('.claude/skills/notes/SKILL.md',encoding='utf-8').read(); d=re.search(r'description:\s*(.+)', t).group(1).strip(); g=re.search(r'group:\s*(.+)', t).group(1).strip(); print('desc_len', len(d), '<=150', len(d)<=150); print('group', repr(g), 'nonempty', bool(g)); assert 'notes' in slugs and len(d)<=150 and g and g!='Chung'; print('OK')"
```
Expected: `in system slugs: True`, `desc_len <n> <=150 True`, `group '...' nonempty True`, `OK`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/notes/SKILL.md
git commit -m "feat(skill): add system skill notes - save a note verbatim + wiki if worthy"
```

---

## Task 2: Pure `/` command logic (chat-slash.js) + node test

**Files:**
- Create: `dashboard/chat-slash.js`
- Test: `dashboard/test_chat_slash.js`

**Interfaces:**
- Produces (exported to the browser via `window.JavisSlash` and to node via `module.exports`):
  - `parseSlash(text) -> {cmd, arg} | null` - `cmd` lowercase; `arg` is the trimmed part after the command (may be `""`). `null` if it is not a command.
  - `SESSION_COMMANDS: string[]` = `["new","reset","stop"]`.
  - `classify(cmd) -> "session" | "skill"`.
  - `buildSkillInvocation(cmd, arg) -> string` - matches the Telegram pattern.
  - `route(text) -> {type:"passthrough"} | {type:"session", cmd} | {type:"skill", cmd, message}`.
  - `buildMenu(skills) -> Item[]` with `Item = {kind, cmd, name, desc}`; `skills` = the array from `GET /skills` (each element has `slug`,`name`,`description`).
  - `filterItems(items, query) -> Item[]` - filters by `query` (the text after `/`, lowercased), prioritizing `cmd` prefix matches.

- [ ] **Step 1: Write the failing test**

Create `dashboard/test_chat_slash.js`:

```javascript
/* Tests for the pure logic of the / command box. Run: node dashboard/test_chat_slash.js
   NO browser needed. */
const S = require("./chat-slash.js");

let fails = [];
function check(name, cond) {
  console.log((cond ? "ok   " : "FAIL ") + name);
  if (!cond) fails.push(name);
}

// ---- parseSlash ----
check("parse: /notes hello", (() => { const r = S.parseSlash("/notes hello"); return r && r.cmd === "notes" && r.arg === "hello"; })());
check("parse: bare /notes -> empty arg", (() => { const r = S.parseSlash("/notes"); return r && r.cmd === "notes" && r.arg === ""; })());
check("parse: UPPERCASE -> lowercase", (() => { const r = S.parseSlash("/Notes X"); return r && r.cmd === "notes" && r.arg === "X"; })());
check("parse: bare / -> null", S.parseSlash("/") === null);
check("parse: not a command -> null", S.parseSlash("hello Jarvis 007") === null);
check("parse: leading whitespace -> null", S.parseSlash("  /notes") === null);
check("parse: multi-line arg kept as is", (() => { const r = S.parseSlash("/notes line1\nline2"); return r && r.arg === "line1\nline2"; })());

// ---- classify ----
check("classify: new = session", S.classify("new") === "session");
check("classify: stop = session", S.classify("stop") === "session");
check("classify: notes = skill", S.classify("notes") === "skill");

// ---- buildSkillInvocation (matches the Telegram pattern; the Vietnamese text is deliberate:
// it is the exact prompt string the Telegram server uses, "Please use skill `X` with the request: ...
// If there is no skill by this name, just handle my request normally.") ----
check("invoke: with arg", S.buildSkillInvocation("notes", "buy milk") ===
  "Hãy dùng skill `notes` với yêu cầu: buy milk. Nếu không có skill tên này thì cứ xử lý yêu cầu của tôi bình thường.");
check("invoke: without arg", S.buildSkillInvocation("notes", "") ===
  "Hãy dùng skill `notes`. Nếu không có skill tên này thì cứ xử lý yêu cầu của tôi bình thường.");

// ---- route ----
check("route: passthrough", S.route("hello").type === "passthrough");
check("route: session new", (() => { const r = S.route("/new"); return r.type === "session" && r.cmd === "new"; })());
check("route: skill notes has message", (() => { const r = S.route("/notes x"); return r.type === "skill" && r.cmd === "notes" && r.message.indexOf("skill `notes`") !== -1 && r.message.indexOf("x") !== -1; })());

// ---- buildMenu + filterItems ----
const menu = S.buildMenu([
  { slug: "notes", name: "Notes", description: "Save note" },
  { slug: "ingest-source", name: "Ingest Source", description: "Digest source" },
]);
check("menu: has session command new", menu.some(i => i.kind === "session" && i.cmd === "new"));
check("menu: has skill notes", menu.some(i => i.kind === "skill" && i.cmd === "notes"));
check("filter: 'no' yields notes", (() => { const r = S.filterItems(menu, "no"); return r.length >= 1 && r[0].cmd === "notes"; })());
check("filter: 'ingest' yields ingest-source", (() => { const r = S.filterItems(menu, "ingest"); return r.some(i => i.cmd === "ingest-source"); })());
check("filter: empty returns all", S.filterItems(menu, "").length === menu.length);

if (fails.length) { console.log("\nFAIL - test_chat_slash: " + fails.length + " failures"); process.exit(1); }
console.log("\nOK - test_chat_slash: all pass");
```

- [ ] **Step 2: Run the test to make sure it fails**

Run: `node dashboard/test_chat_slash.js`
Expected: FAIL - `Cannot find module './chat-slash.js'`.

- [ ] **Step 3: Write chat-slash.js (the pure part)**

Create `dashboard/chat-slash.js`:

```javascript
// / command box for the web chat box. The pure LOGIC part (parse/route/menu) is testable headless;
// the DOM menu part at the end of the file only runs in the browser. Same pattern as chat-ask.js.
(function () {
  var SESSION_COMMANDS = ["new", "reset", "stop"];

  // Recognize a command: starts with / + a [a-z0-9_-] token, the rest is the arg.
  function parseSlash(text) {
    if (typeof text !== "string") return null;
    var m = text.match(/^\/([a-zA-Z0-9_-]+)(?:\s+([\s\S]*))?$/);
    if (!m) return null;
    return { cmd: m[1].toLowerCase(), arg: (m[2] || "").trim() };
  }

  function classify(cmd) {
    return SESSION_COMMANDS.indexOf(cmd) !== -1 ? "session" : "skill";
  }

  // Match the Telegram fallback pattern (server/main.py) EXACTLY so the 2 channels stay consistent.
  // (The Vietnamese is deliberate: "Please use skill `X`" + " with the request: <arg>" + ". If there is no
  // skill by this name, just handle my request normally.")
  function buildSkillInvocation(cmd, arg) {
    return "Hãy dùng skill `" + cmd + "`" +
      (arg ? " với yêu cầu: " + arg : "") +
      ". Nếu không có skill tên này thì cứ xử lý yêu cầu của tôi bình thường.";
  }

  function route(text) {
    var p = parseSlash(text);
    if (!p) return { type: "passthrough" };
    if (classify(p.cmd) === "session") return { type: "session", cmd: p.cmd };
    return { type: "skill", cmd: p.cmd, message: buildSkillInvocation(p.cmd, p.arg) };
  }

  var SESSION_ITEMS = [
    { kind: "session", cmd: "new", name: "New conversation", desc: "Start a new conversation" },
    { kind: "session", cmd: "reset", name: "Reset session", desc: "Clear the context and start over" },
    { kind: "session", cmd: "stop", name: "Stop", desc: "Stop the answer in progress" },
  ];

  function buildMenu(skills) {
    var out = SESSION_ITEMS.slice();
    (skills || []).forEach(function (s) {
      if (!s || !s.slug) return;
      out.push({ kind: "skill", cmd: s.slug, name: s.name || s.slug, desc: s.description || "" });
    });
    return out;
  }

  function filterItems(items, query) {
    var q = (query || "").toLowerCase();
    if (!q) return items.slice();
    var scored = [];
    (items || []).forEach(function (it) {
      var cmd = (it.cmd || "").toLowerCase();
      var name = (it.name || "").toLowerCase();
      var score = -1;
      if (cmd.indexOf(q) === 0) score = 0;            // cmd prefix match - highest priority
      else if (cmd.indexOf(q) !== -1) score = 1;      // cmd contains the query
      else if (name.indexOf(q) !== -1) score = 2;     // name contains the query
      if (score >= 0) scored.push({ it: it, score: score });
    });
    scored.sort(function (a, b) { return a.score - b.score; });
    return scored.map(function (x) { return x.it; });
  }

  var api = {
    parseSlash: parseSlash,
    SESSION_COMMANDS: SESSION_COMMANDS,
    classify: classify,
    buildSkillInvocation: buildSkillInvocation,
    route: route,
    buildMenu: buildMenu,
    filterItems: filterItems,
  };

  if (typeof window !== "undefined") window.JavisSlash = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  // ===== DOM MENU part (browser only) - filled in Task 3 =====
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    if (window.JavisSlash) window.JavisSlash._initMenu = function () { /* Task 3 */ };
  }
})();
```

- [ ] **Step 4: Run the test to make sure it passes**

Run: `node dashboard/test_chat_slash.js`
Expected: `OK - test_chat_slash: all pass`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/chat-slash.js dashboard/test_chat_slash.js
git commit -m "feat(web): / command box logic (parse/route/menu) + node test"
```

---

## Task 3: DOM menu + intercept `/` in sendMessage + wiring

**Files:**
- Modify: `dashboard/chat-slash.js` (fill in `_initMenu` - the DOM part)
- Modify: `dashboard/app.js:196-231` (intercept `/` in `sendMessage`)
- Modify: `dashboard/index.html:581-582` (load the script before app.js)
- Modify: `dashboard/style.css` (menu CSS)
- Test: manual verification in the browser (Task 5 runs end-to-end).

**Interfaces:**
- Consumes: `window.JavisSlash.route/buildMenu/filterItems/parseSlash` (Task 2); `newChat()`, `stopCurrent()`, `currentBrainPath()`, `chatInput`, `pendingAttachments` (already in app.js).
- Produces: when `sendMessage` sees `/`, a session-command runs in place (not sent to the engine); a skill-command sends the `buildSkillInvocation` string (+ attachment paths) over the WebSocket.

- [ ] **Step 1: Fill in the DOM menu in chat-slash.js**

Replace the `// ===== DOM MENU part ... =====` block at the end of `dashboard/chat-slash.js` with:

```javascript
  // ===== DOM MENU part (browser only) =====
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    var box = null, items = [], active = 0, skillsCache = null, cacheBrain = null;

    function ensureBox() {
      if (box) return box;
      box = document.createElement("div");
      box.id = "slashMenu";
      box.className = "slash-menu";
      box.style.display = "none";
      document.body.appendChild(box);
      return box;
    }

    async function loadSkills() {
      var brain = (typeof window.currentBrainPath === "function") ? window.currentBrainPath() : "brain";
      if (skillsCache && cacheBrain === brain) return skillsCache;
      try {
        var r = await fetch("/skills?brain=" + encodeURIComponent(brain));
        var d = await r.json();
        skillsCache = (d && d.skills) || [];
      } catch (e) { skillsCache = []; }
      cacheBrain = brain;
      return skillsCache;
    }

    function hide() { if (box) box.style.display = "none"; items = []; active = 0; }

    function positionBox(input) {
      var rect = input.getBoundingClientRect();
      box.style.left = rect.left + "px";
      box.style.width = rect.width + "px";
      box.style.bottom = (window.innerHeight - rect.top + 6) + "px";
    }

    function renderList() {
      box.innerHTML = "";
      items.forEach(function (it, i) {
        var row = document.createElement("div");
        row.className = "slash-item" + (i === active ? " active" : "");
        row.innerHTML = '<span class="slash-cmd">/' + it.cmd + '</span>' +
          '<span class="slash-name">' + (it.name || "") + '</span>' +
          '<span class="slash-desc">' + (it.desc || "") + '</span>';
        row.addEventListener("mousedown", function (e) { e.preventDefault(); choose(i); });
        box.appendChild(row);
      });
    }

    function choose(i) {
      var it = items[i];
      if (!it) return;
      var input = document.getElementById("chatInput");
      hide();
      if (it.kind === "skill") {
        // Fill in '/slug ' so the user types the content next, then Enter to send.
        input.value = "/" + it.cmd + " ";
        input.focus();
        input.dispatchEvent(new Event("input"));
      } else {
        // Session command: run right away.
        input.value = "";
        if (typeof window.JavisSend === "function") window.JavisSend("/" + it.cmd);
      }
    }

    async function onInput() {
      var input = document.getElementById("chatInput");
      var val = input.value;
      var p = parseSlash(val.trim());
      // Only open the menu while typing the first command token (no space after the command yet) or right after typing '/'.
      var typingCmd = /^\/[a-zA-Z0-9_-]*$/.test(val);
      if (!typingCmd) { hide(); return; }
      ensureBox();
      var skills = await loadSkills();
      var all = buildMenu(skills);
      var query = val.slice(1);   // drop the '/'
      items = filterItems(all, query);
      active = 0;
      if (!items.length) { hide(); return; }
      positionBox(input);
      renderList();
      box.style.display = "block";
    }

    function onKeydown(e) {
      if (!box || box.style.display === "none") return;
      if (e.key === "ArrowDown") { e.preventDefault(); active = (active + 1) % items.length; renderList(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); active = (active - 1 + items.length) % items.length; renderList(); }
      else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); e.stopImmediatePropagation(); choose(active); }
      else if (e.key === "Escape") { e.preventDefault(); hide(); }
    }

    api._initMenu = function () {
      var input = document.getElementById("chatInput");
      if (!input) return;
      input.addEventListener("input", onInput);
      input.addEventListener("keydown", onKeydown);   // registered BEFORE app.js (script is loaded first)
      input.addEventListener("blur", function () { setTimeout(hide, 120); });
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", api._initMenu);
    } else {
      api._initMenu();
    }
  }
```

- [ ] **Step 2: Intercept `/` in sendMessage (app.js)**

In `dashboard/app.js`, right at the START of the `sendMessage` body (after the line `const msg = (text || chatInput.value).trim();` at line ~197), insert the command routing block. Find:

```javascript
function sendMessage(text) {
  const msg = (text || chatInput.value).trim();
  const atts = pendingAttachments.filter(a => a.path);  // only files that finished uploading
```

Insert RIGHT AFTER the `const atts = ...` line:

```javascript
  // / commands: a session-command runs in place; a skill-command expands into a skill call.
  const _slash = (window.JavisSlash && msg) ? window.JavisSlash.route(msg) : { type: "passthrough" };
  if (_slash.type === "session") {
    chatInput.value = ""; chatInput.style.height = "auto";
    if (_slash.cmd === "stop") { try { stopCurrent(); } catch (e) {} }
    else { try { newChat(); } catch (e) {} }   // new | reset -> a new conversation on the web
    return;
  }
```

Then, so that a skill-command sends the EXACT expanded string (not the raw `/notes ...` text), change the part that builds `outMsg`. Find the block (lines ~209-221). Note: the Vietnamese prefix `[File đính kèm ...` ("[Attached file ...") is a machine token the code matches (the `_KHOI_NGU_CANH` list in `app.js`), so it stays verbatim; the rest of the prompt text is translated:

```javascript
  // Compose the message sent to Jarvis 007 (with the file paths in Sources)
  let outMsg = msg;
  if (atts.length) {
    const lines = atts.map(a => `- ${a.path}`).join("\n");
    const src = atts[0].sources || "", attDir = atts[0].attachments || "";
    const ctx =
      `[File đính kèm để ĐỌC (đường dẫn):\n${lines}\n` +
      `Default: only read the file and answer, do NOT save it anywhere by yourself.\n` +
      `ONLY when the user explicitly asks (e.g. "save to source", "ingest", "write to second brain") then: ` +
      `convert to .md (for images: read and describe) and save into Sources="${src}" (move the original image into Attachments="${attDir}"), with source frontmatter.]`;
    outMsg = msg
      ? `${ctx}\n\n${msg}`
      : `${ctx}\n\nPlease read the file(s) above and respond / summarize the main content.`;
  }
```

Replace it with:

```javascript
  // Compose the message sent to Jarvis 007 (with the file paths in Sources)
  const _isSkill = _slash.type === "skill";
  let outMsg = _isSkill ? _slash.message : msg;
  if (atts.length) {
    const lines = atts.map(a => `- ${a.path}`).join("\n");
    const src = atts[0].sources || "", attDir = atts[0].attachments || "";
    if (_isSkill) {
      // For a skill command (e.g. /notes): hand over the paths as data, so the skill itself decides what to save.
      outMsg = `[File đính kèm (đường dẫn), Sources="${src}", Attachments="${attDir}":\n${lines}]\n\n${_slash.message}`;
    } else {
      const ctx =
        `[File đính kèm để ĐỌC (đường dẫn):\n${lines}\n` +
        `Default: only read the file and answer, do NOT save it anywhere by yourself.\n` +
        `ONLY when the user explicitly asks (e.g. "save to source", "ingest", "write to second brain") then: ` +
        `convert to .md (for images: read and describe) and save into Sources="${src}" (move the original image into Attachments="${attDir}"), with source frontmatter.]`;
      outMsg = msg
        ? `${ctx}\n\n${msg}`
        : `${ctx}\n\nPlease read the file(s) above and respond / summarize the main content.`;
    }
  }
```

Note: `appendUserMessage(msg, atts)` above still shows `/notes ...` exactly as the user typed it; only `outMsg`, the string sent to the engine, is the expanded one.

- [ ] **Step 3: Load chat-slash.js before app.js (index.html)**

In `dashboard/index.html`, find the line that loads `chat-ask.js` (line ~581):

```html
  <script src="/static/chat-ask.js?v=1"></script>
  <script src="/static/app.js?v=68"></script>
```

Insert `chat-slash.js` BETWEEN the two lines (before app.js so the keydown listener registers first) and raise the app.js version:

```html
  <script src="/static/chat-ask.js?v=1"></script>
  <script src="/static/chat-slash.js?v=1"></script>
  <script src="/static/app.js?v=69"></script>
```

- [ ] **Step 4: Menu CSS (style.css)**

Append to the end of `dashboard/style.css`:

```css
/* / command menu (chat-slash.js) */
.slash-menu {
  position: fixed;
  z-index: 999;
  max-height: 280px;
  overflow-y: auto;
  background: var(--panel, #14161c);
  border: 1px solid var(--border, #2a2f3a);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0,0,0,.35);
  padding: 4px;
}
.slash-item {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas: "cmd name" "cmd desc";
  gap: 0 10px;
  padding: 6px 10px;
  border-radius: 7px;
  cursor: pointer;
}
.slash-item.active, .slash-item:hover { background: var(--accent-soft, rgba(120,140,255,.14)); }
.slash-cmd { grid-area: cmd; align-self: center; font-weight: 600; color: var(--accent, #8ab4ff); }
.slash-name { grid-area: name; font-size: 13px; }
.slash-desc { grid-area: desc; font-size: 11px; opacity: .65; }
```

- [ ] **Step 5: Re-run the node test (no logic regression)**

Run: `node dashboard/test_chat_slash.js`
Expected: `OK - test_chat_slash: all pass`.

- [ ] **Step 6: Commit**

```bash
git add dashboard/chat-slash.js dashboard/app.js dashboard/index.html dashboard/style.css
git commit -m "feat(web): / command menu on the chat box + skill/session-command routing"
```

---

## Task 4: End-to-end verification (web + Telegram + sync)

**Files:** no files changed (just run + observe). If something fails -> go back to the matching task.

**Interfaces:** Consumes all of Tasks 1-3.

- [ ] **Step 1: Start the local server (if not already running)**

Use `.venv` (the system python lacks libs - see memory). Start the app the project's way (e.g. `.venv/Scripts/python server/main.py` or `start-javis.bat`). Open the dashboard in a browser.

- [ ] **Step 2: Verify the web menu**

In the chat box: type `/` -> the menu shows `/new /reset /stop` + the skills (including `/notes`). Type `/no` -> filtered so `notes` is first in the list. Arrow keys + Enter pick `notes` -> the box fills in `/notes `. Esc closes the menu.
Expected: as above; no console errors.

- [ ] **Step 3: Verify /notes saves verbatim (a wiki-worthy note)**

Type: `/notes Pareto principle: 80% of results come from 20% of causes. Apply it when prioritizing work.` then send.
Expected: a file `sources/note-<date>-*.md` appears with the body EXACTLY verbatim; a new `wiki/` page (concept) exists + `wiki/index.md` is updated; the reply says it was saved and went up to the wiki. Check:
```bash
ls "brains/Brain Default/sources/" | grep note-
```

- [ ] **Step 4: Verify /notes with a trivial note (not worthy)**

Type: `/notes Meeting with Nam at 3pm this afternoon.` then send.
Expected: a file in `sources/`, NO new wiki page; the reply says "note saved, did not look worth putting on the wiki".

- [ ] **Step 5: Verify /notes with an image**

Drag 1 image into the chat box + type `/notes sample product photo` + send.
Expected: the image is in `attachments/`, the source embeds `![[...]]`; the reply embeds the image again.

- [ ] **Step 6: Verify session commands**

`/new` -> opens a new conversation (not sent to the engine). `/stop` while a turn is running -> stops it.
Expected: correct behavior, no "/new" message is sent to the engine.

- [ ] **Step 7: Verify Telegram has no regression**

From Telegram send `/notes Test from Telegram.`
Expected: the `notes` skill runs, creating a source in the Telegram session's brain.

- [ ] **Step 8: Verify sync to another brain**

Switch to another brain (dropdown), type `/` -> you still see `/notes` (system_sync spread it). If not, run the project's system sync and try again.
Expected: `/notes` is present in every brain.

---

## Task 5: Release (bump VERSION + CHANGELOG + push)

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

Per project convention: once done and tests are OK, bump VERSION + CHANGELOG + commit + push origin/main on your own.

- [ ] **Step 1: Bump VERSION**

Read the current `VERSION`, raise the patch (e.g. 0.9.83 -> 0.9.84). Write it back to `VERSION`.

- [ ] **Step 2: Write the CHANGELOG**

Add a top entry to `CHANGELOG.md` for the new version: describe the `/` command box for the dashboard + the `/notes` skill (saves verbatim into sources, wiki if worthy, works on both web and Telegram).

- [ ] **Step 3: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore(release): 0.9.84 - / command box + /notes skill"
git push origin main
```

Expected: the push to origin/main succeeds.

---

## Self-Review (run while writing the plan)

- **Spec coverage:** web command box (Tasks 2+3), notes skill (Task 1), verbatim save + images (Task 1 + Task 3 step 2), wiki if worthy / light report if not (Task 1 step 2), bundled + sync (Task 1 + Task 4 step 8), Telegram consistency (Task 2 buildSkillInvocation matches the pattern + Task 4 step 7). Complete.
- **Placeholder scan:** No TBD/TODO; every step has real code/commands.
- **Type consistency:** `route/parseSlash/buildMenu/filterItems/buildSkillInvocation` are used consistently between Task 2 (definition) and Task 3 (consumption). `newChat()/stopCurrent()` are the real names in app.js.
