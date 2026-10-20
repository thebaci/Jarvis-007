# Khung lệnh `/` cho dashboard + skill `/notes` - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho khung chat web gõ lệnh `/` (menu gợi ý giống Telegram/Claude), với lệnh đầu tiên `/notes` lưu tin nhắn hiện tại nguyên văn vào `sources/` rồi tự chưng cất wiki nếu đáng.

**Architecture:** Nguyên tắc hợp nhất `/<slug>` = gọi skill `<slug>` (đúng ngữ nghĩa Telegram sẵn có tại `server/main.py:5076`). `/notes` là skill HỆ THỐNG bundled ở `.claude/skills/notes/SKILL.md`, `system_sync.py` tự rải xuống mọi brain. Web thêm một module frontend thuần (`chat-slash.js`) lo phân loại lệnh + menu, `app.js` chặn `/` trong `sendMessage` và định tuyến. Backend gần như không đổi.

**Tech Stack:** Python 3 (FastAPI, chạy trong `.venv`), JavaScript thuần trình duyệt (IIFE + dual export `window`/`module.exports`), test frontend chạy headless bằng `node dashboard/test_*.js`.

## Global Constraints

- Ngôn ngữ chính tiếng Việt; chuỗi hiển thị cho user PHẢI có dấu, kể cả viết trong code.
- TUYỆT ĐỐI không dùng ký tự em dash (U+2014) ở bất kỳ đâu (chat, file, code, wiki). Dùng `-`.
- Skill mới tạo qua tiến trình này là năng lực lõi -> `.claude/skills/notes/SKILL.md` (nguồn chuẩn hệ thống).
- `description` của SKILL.md TỐI ĐA 150 ký tự (router cắt cứng ở 150). `group` BẮT BUỘC có, chọn nhóm sát skill hiện có.
- Skill `notes` giữ nguyên văn note, KHÔNG biên tập lại chữ người dùng.
- Ghi `sources/`/`wiki/` là mức `safe`, chạy được vì do người gõ lệnh; KHÔNG làm hành động tiền/đơn/đăng bài/gửi tin.
- Module frontend theo pattern có sẵn (xem `dashboard/chat-ask.js`): IIFE, `window.X` cho trình duyệt + `module.exports` cho test node.
- Chuỗi gọi skill web phải KHỚP mẫu Telegram (`server/main.py:5079-5080`) để hai kênh nhất quán.

---

## File Structure

- Tạo `.claude/skills/notes/SKILL.md` - skill hệ thống, `system_sync` rải xuống brain.
- Tạo `dashboard/chat-slash.js` - logic thuần (parse/route/menu-data) + controller menu DOM + dual export.
- Tạo `dashboard/test_chat_slash.js` - test node cho các hàm thuần.
- Sửa `dashboard/app.js` - chặn `/` trong `sendMessage()`, định tuyến session-command vs skill.
- Sửa `dashboard/index.html` - nạp `chat-slash.js` TRƯỚC `app.js`.
- Sửa `dashboard/style.css` - CSS menu lệnh.
- Sửa `CHANGELOG.md` + `VERSION` - phát hành (task cuối).

---

## Task 1: Skill hệ thống `notes`

**Files:**
- Create: `.claude/skills/notes/SKILL.md`
- Test: chạy python trong `.venv` để xác minh skill được khám phá + frontmatter hợp lệ.

**Interfaces:**
- Produces: skill slug `notes`, khám phá được qua `skill_router.list_skills()` và có trong `system_sync.system_skill_slugs()`. Frontend map `/notes` -> slug `notes`.

- [ ] **Step 1: Xác định nhóm (group) sát nhất**

Đọc group của các skill hệ thống hiện có để chọn nhóm đồng bộ (đừng để trống -> "Chung"):

Run: `rg -n "^group:" .claude/skills/*/SKILL.md`
Expected: thấy các nhóm đang dùng (vd `ingest-source` = `AI`). Chọn `AI` cho `notes` (cùng họ tri thức/wiki với ingest/query/lint). Nếu quan sát thấy nhóm khác hợp hơn thì dùng nhóm đó.

- [ ] **Step 2: Viết SKILL.md**

Create `.claude/skills/notes/SKILL.md`:

```markdown
---
name: Notes
description: Lưu tin nhắn hiện tại nguyên văn vào sources/ (kèm ảnh), tự chưng cất lên wiki nếu note đáng.
group: AI
---

# NOTES - lưu nhanh 1 note vào Second Brain (giữ nguyên văn), wiki nếu đáng

## Khi nào dùng

Kích hoạt khi người dùng gõ lệnh `/notes` (web hoặc Telegram), hoặc nói "lưu note này",
"ghi nhanh cái này vào brain". Đây là bản CHỘP NHANH: lưu nguyên văn trước, chưng cất sau
nếu đáng. Khác `ingest-source` (dành cho source đã nằm sẵn trong `sources/` và luôn distill).

Đọc schema vault (`CLAUDE.md`/`AGENTS.md` ở gốc brain) trước khi ghi.

## Nội dung note lấy từ đâu

- Phần "yêu cầu" người dùng gõ SAU `/notes` = thân note. Giữ ĐÚNG NGUYÊN VĂN, không sửa,
  không tóm tắt, không thêm bớt chữ nào.
- File/ảnh đính kèm trong CÙNG tin nhắn (đường dẫn được đưa kèm) = tài liệu của note.
- CHỈ tin nhắn hiện tại. Không kéo câu trả lời trước hay các lượt cũ vào.

## Các bước

1. Xác định thư mục brain hiện tại: `sources/`, `attachments/`, `wiki/`.
2. Đặt tên file: `sources/note-YYYY-MM-DD-HHmm-<vài-chữ-đầu-không-dấu>.md` (dùng ngày giờ thật,
   lấy qua tool datetime nếu có; slug từ ~4-6 chữ đầu của note, bỏ dấu, nối gạch ngang).
3. Ghi file source với frontmatter:
   - `type: source`
   - `source_kind: own-note`
   - `status: unprocessed`
   - `created: <YYYY-MM-DD HH:mm>`
   - `tags: [note]`
   Thân file = văn bản gốc NGUYÊN VĂN. Với ảnh đính kèm: chuyển/đảm bảo file nằm trong
   `attachments/`, nhúng `![[tên-ảnh]]` trong thân. Nếu file đã nằm sẵn trong `sources/`/
   `attachments/` do web upload thì dùng chính nó, KHÔNG nhân đôi.
4. Đánh giá đáng-wiki (cùng tiêu chí ingest-source): có khái niệm / framework / nguyên lý /
   quy trình / insight tái dùng được -> ĐÁNG. Tâm sự, việc vặt, nhắc nhất thời, danh sách mua
   đồ -> KHÔNG đáng.
5. Nếu ĐÁNG: áp phép INGEST - viết/cập nhật trang `wiki/` đủ 3 kỷ luật (mỗi claim cụ thể kèm
   `[[Nguồn]]`; phân biệt "(mục tiêu)"/"(thực tế tính đến ...)"; mâu thuẫn với trang cũ thì
   thêm `## Mâu thuẫn` + append `wiki/_open-questions.md`, KHÔNG ghi đè). Mỗi trang tự đủ ngữ
   cảnh (1-2 câu định vị đầu trang) + `aliases:` nếu có tên gọi khác. Cập nhật `wiki/index.md`
   (thêm dòng link + mô tả 1 dòng). Append `wiki/log.md`:
   `## [YYYY-MM-DD] notes | <tên note>` + nguồn/đã tạo/đã cập nhật/insight. Set source
   `status: processed`, `processed_at: <...>`, `wiki_links: [...]`.
6. Nếu KHÔNG đáng: giữ source (`status: unprocessed`), KHÔNG đụng wiki.
7. Báo NGẮN bằng văn nói (không bảng, không gạch ngang dài, không em dash): đã lưu note vào
   `[[tên-source]]`; có lên wiki không, nếu có thì trang nào. Có ảnh thì nhúng lại `![...](...)`
   cho người dùng xem.

## An toàn

Ghi `sources/` + `wiki/` là mức `safe`, chạy được vì người dùng chủ động gõ lệnh. KHÔNG tạo
đơn, KHÔNG tiêu tiền, KHÔNG đăng bài, KHÔNG gửi tin. Chỉ ghi file trong vault.
```

- [ ] **Step 3: Xác minh skill được khám phá + frontmatter hợp lệ**

Run:
```bash
.venv/Scripts/python -c "import sys; sys.path.insert(0,'server'); import system_sync, skill_router; slugs=system_sync.system_skill_slugs(); print('in system slugs:', 'notes' in slugs); import re,io; t=open('.claude/skills/notes/SKILL.md',encoding='utf-8').read(); d=re.search(r'description:\s*(.+)', t).group(1).strip(); g=re.search(r'group:\s*(.+)', t).group(1).strip(); print('desc_len', len(d), '<=150', len(d)<=150); print('group', repr(g), 'nonempty', bool(g)); assert 'notes' in slugs and len(d)<=150 and g and g!='Chung'; print('OK')"
```
Expected: `in system slugs: True`, `desc_len <n> <=150 True`, `group '...' nonempty True`, `OK`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/notes/SKILL.md
git commit -m "feat(skill): them skill he thong notes - luu note nguyen van + wiki neu dang"
```

---

## Task 2: Logic lệnh `/` thuần (chat-slash.js) + test node

**Files:**
- Create: `dashboard/chat-slash.js`
- Test: `dashboard/test_chat_slash.js`

**Interfaces:**
- Produces (export cho trình duyệt qua `window.JavisSlash` và cho node qua `module.exports`):
  - `parseSlash(text) -> {cmd, arg} | null` - `cmd` viết thường; `arg` phần sau lệnh đã trim (có thể `""`). `null` nếu không phải lệnh.
  - `SESSION_COMMANDS: string[]` = `["new","reset","stop"]`.
  - `classify(cmd) -> "session" | "skill"`.
  - `buildSkillInvocation(cmd, arg) -> string` - khớp mẫu Telegram.
  - `route(text) -> {type:"passthrough"} | {type:"session", cmd} | {type:"skill", cmd, message}`.
  - `buildMenu(skills) -> Item[]` với `Item = {kind, cmd, name, desc}`; `skills` = mảng từ `GET /skills` (mỗi phần tử có `slug`,`name`,`description`).
  - `filterItems(items, query) -> Item[]` - lọc theo `query` (chữ sau `/`, thường hoá), ưu tiên `cmd` khớp tiền tố.

- [ ] **Step 1: Viết test thất bại**

Create `dashboard/test_chat_slash.js`:

```javascript
/* Test logic thuan cua khung lenh /. Chay: node dashboard/test_chat_slash.js
   KHONG can trinh duyet. */
const S = require("./chat-slash.js");

let fails = [];
function check(name, cond) {
  console.log((cond ? "ok   " : "FAIL ") + name);
  if (!cond) fails.push(name);
}

// ---- parseSlash ----
check("parse: /notes hello", (() => { const r = S.parseSlash("/notes hello"); return r && r.cmd === "notes" && r.arg === "hello"; })());
check("parse: /notes tron -> arg rong", (() => { const r = S.parseSlash("/notes"); return r && r.cmd === "notes" && r.arg === ""; })());
check("parse: chu HOA -> thuong", (() => { const r = S.parseSlash("/Notes X"); return r && r.cmd === "notes" && r.arg === "X"; })());
check("parse: dau / tron -> null", S.parseSlash("/") === null);
check("parse: khong phai lenh -> null", S.parseSlash("chao Jarvis 007") === null);
check("parse: khoang trang dau -> null", S.parseSlash("  /notes") === null);
check("parse: arg nhieu dong giu nguyen", (() => { const r = S.parseSlash("/notes dong1\ndong2"); return r && r.arg === "dong1\ndong2"; })());

// ---- classify ----
check("classify: new = session", S.classify("new") === "session");
check("classify: stop = session", S.classify("stop") === "session");
check("classify: notes = skill", S.classify("notes") === "skill");

// ---- buildSkillInvocation (khop mau Telegram) ----
check("invoke: co arg", S.buildSkillInvocation("notes", "mua sua") ===
  "Hãy dùng skill `notes` với yêu cầu: mua sua. Nếu không có skill tên này thì cứ xử lý yêu cầu của tôi bình thường.");
check("invoke: khong arg", S.buildSkillInvocation("notes", "") ===
  "Hãy dùng skill `notes`. Nếu không có skill tên này thì cứ xử lý yêu cầu của tôi bình thường.");

// ---- route ----
check("route: passthrough", S.route("chao").type === "passthrough");
check("route: session new", (() => { const r = S.route("/new"); return r.type === "session" && r.cmd === "new"; })());
check("route: skill notes co message", (() => { const r = S.route("/notes x"); return r.type === "skill" && r.cmd === "notes" && r.message.indexOf("skill `notes`") !== -1 && r.message.indexOf("x") !== -1; })());

// ---- buildMenu + filterItems ----
const menu = S.buildMenu([
  { slug: "notes", name: "Notes", description: "Luu note" },
  { slug: "ingest-source", name: "Ingest Source", description: "Tieu hoa source" },
]);
check("menu: co lenh phien new", menu.some(i => i.kind === "session" && i.cmd === "new"));
check("menu: co skill notes", menu.some(i => i.kind === "skill" && i.cmd === "notes"));
check("filter: 'no' ra notes", (() => { const r = S.filterItems(menu, "no"); return r.length >= 1 && r[0].cmd === "notes"; })());
check("filter: 'ingest' ra ingest-source", (() => { const r = S.filterItems(menu, "ingest"); return r.some(i => i.cmd === "ingest-source"); })());
check("filter: rong tra ve tat ca", S.filterItems(menu, "").length === menu.length);

if (fails.length) { console.log("\nFAIL - test_chat_slash: " + fails.length + " loi"); process.exit(1); }
console.log("\nOK - test_chat_slash: tat ca pass");
```

- [ ] **Step 2: Chạy test để chắc nó fail**

Run: `node dashboard/test_chat_slash.js`
Expected: FAIL - `Cannot find module './chat-slash.js'`.

- [ ] **Step 3: Viết chat-slash.js (phần thuần)**

Create `dashboard/chat-slash.js`:

```javascript
// Khung lenh / cho khung chat web. Phan LOGIC thuan (parse/route/menu) test duoc headless;
// phan menu DOM o cuoi file chi chay trong trinh duyet. Pattern giong chat-ask.js.
(function () {
  var SESSION_COMMANDS = ["new", "reset", "stop"];

  // Nhan dien lenh: bat dau bang / + token [a-z0-9_-], phan sau la arg.
  function parseSlash(text) {
    if (typeof text !== "string") return null;
    var m = text.match(/^\/([a-zA-Z0-9_-]+)(?:\s+([\s\S]*))?$/);
    if (!m) return null;
    return { cmd: m[1].toLowerCase(), arg: (m[2] || "").trim() };
  }

  function classify(cmd) {
    return SESSION_COMMANDS.indexOf(cmd) !== -1 ? "session" : "skill";
  }

  // Khop DUNG mau fallback cua Telegram (server/main.py) de 2 kenh nhat quan.
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
    { kind: "session", cmd: "new", name: "Hội thoại mới", desc: "Bắt đầu cuộc trò chuyện mới" },
    { kind: "session", cmd: "reset", name: "Reset phiên", desc: "Xoá ngữ cảnh, bắt đầu lại" },
    { kind: "session", cmd: "stop", name: "Dừng", desc: "Dừng lượt đang trả lời" },
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
      if (cmd.indexOf(q) === 0) score = 0;            // cmd khop tien to - uu tien nhat
      else if (cmd.indexOf(q) !== -1) score = 1;      // cmd chua query
      else if (name.indexOf(q) !== -1) score = 2;     // ten chua query
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

  // ===== Phan MENU DOM (chi trinh duyet) - dien o Task 3 =====
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    if (window.JavisSlash) window.JavisSlash._initMenu = function () { /* Task 3 */ };
  }
})();
```

- [ ] **Step 4: Chạy test để chắc nó pass**

Run: `node dashboard/test_chat_slash.js`
Expected: `OK - test_chat_slash: tat ca pass`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/chat-slash.js dashboard/test_chat_slash.js
git commit -m "feat(web): logic khung lenh / (parse/route/menu) + test node"
```

---

## Task 3: Menu DOM + chặn `/` trong sendMessage + wiring

**Files:**
- Modify: `dashboard/chat-slash.js` (điền `_initMenu` - phần DOM)
- Modify: `dashboard/app.js:196-231` (chặn `/` trong `sendMessage`)
- Modify: `dashboard/index.html:581-582` (nạp script trước app.js)
- Modify: `dashboard/style.css` (CSS menu)
- Test: xác minh thủ công trong trình duyệt (Task 5 chạy end-to-end).

**Interfaces:**
- Consumes: `window.JavisSlash.route/buildMenu/filterItems/parseSlash` (Task 2); `newChat()`, `stopCurrent()`, `currentBrainPath()`, `chatInput`, `pendingAttachments` (có sẵn trong app.js).
- Produces: khi `sendMessage` thấy `/`, session-command chạy tại chỗ (không gửi engine); skill-command gửi chuỗi `buildSkillInvocation` (+ path đính kèm) qua WebSocket.

- [ ] **Step 1: Điền menu DOM trong chat-slash.js**

Thay khối `// ===== Phan MENU DOM ... =====` cuối `dashboard/chat-slash.js` bằng:

```javascript
  // ===== Phan MENU DOM (chi trinh duyet) =====
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
        // Dien '/slug ' de nguoi dung go tiep noi dung roi Enter gui.
        input.value = "/" + it.cmd + " ";
        input.focus();
        input.dispatchEvent(new Event("input"));
      } else {
        // Lenh phien: chay ngay.
        input.value = "";
        if (typeof window.JavisSend === "function") window.JavisSend("/" + it.cmd);
      }
    }

    async function onInput() {
      var input = document.getElementById("chatInput");
      var val = input.value;
      var p = parseSlash(val.trim());
      // Chi mo menu khi dang go token lenh dau (chua co khoang trang sau lenh) hoac vua go '/'.
      var typingCmd = /^\/[a-zA-Z0-9_-]*$/.test(val);
      if (!typingCmd) { hide(); return; }
      ensureBox();
      var skills = await loadSkills();
      var all = buildMenu(skills);
      var query = val.slice(1);   // bo dau '/'
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
      input.addEventListener("keydown", onKeydown);   // dang ky TRUOC app.js (script nap truoc)
      input.addEventListener("blur", function () { setTimeout(hide, 120); });
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", api._initMenu);
    } else {
      api._initMenu();
    }
  }
```

- [ ] **Step 2: Chặn `/` trong sendMessage (app.js)**

Trong `dashboard/app.js`, ngay ĐẦU thân hàm `sendMessage` (sau dòng `const msg = (text || chatInput.value).trim();` tại dòng ~197), chèn khối định tuyến lệnh. Tìm:

```javascript
function sendMessage(text) {
  const msg = (text || chatInput.value).trim();
  const atts = pendingAttachments.filter(a => a.path);  // chỉ file đã upload xong
```

Chèn NGAY sau dòng `const atts = ...`:

```javascript
  // Lệnh / : session-command chạy tại chỗ; skill-command bung thành lời gọi skill.
  const _slash = (window.JavisSlash && msg) ? window.JavisSlash.route(msg) : { type: "passthrough" };
  if (_slash.type === "session") {
    chatInput.value = ""; chatInput.style.height = "auto";
    if (_slash.cmd === "stop") { try { stopCurrent(); } catch (e) {} }
    else { try { newChat(); } catch (e) {} }   // new | reset -> hội thoại mới trên web
    return;
  }
```

Sau đó, để skill-command gửi ĐÚNG chuỗi bung (không phải chữ `/notes ...` thô), sửa phần dựng `outMsg`. Tìm khối (dòng ~209-221):

```javascript
  // Soạn message gửi Jarvis 007 (kèm đường dẫn file trong Sources)
  let outMsg = msg;
  if (atts.length) {
    const lines = atts.map(a => `- ${a.path}`).join("\n");
    const src = atts[0].sources || "", attDir = atts[0].attachments || "";
    const ctx =
      `[File đính kèm để ĐỌC (đường dẫn):\n${lines}\n` +
      `Mặc định: chỉ đọc file rồi trả lời, KHÔNG tự lưu đi đâu.\n` +
      `CHỈ khi user yêu cầu rõ (vd "lưu vào source", "ingest", "ghi vào second brain") thì mới: ` +
      `chuyển thành .md (ảnh thì đọc hiểu + mô tả) lưu vào Sources="${src}" (ảnh gốc chuyển vào Attachments="${attDir}"), kèm frontmatter source.]`;
    outMsg = msg
      ? `${ctx}\n\n${msg}`
      : `${ctx}\n\nHãy đọc (các) file trên và phản hồi / tóm tắt nội dung chính.`;
  }
```

Thay bằng:

```javascript
  // Soạn message gửi Jarvis 007 (kèm đường dẫn file trong Sources)
  const _isSkill = _slash.type === "skill";
  let outMsg = _isSkill ? _slash.message : msg;
  if (atts.length) {
    const lines = atts.map(a => `- ${a.path}`).join("\n");
    const src = atts[0].sources || "", attDir = atts[0].attachments || "";
    if (_isSkill) {
      // Với lệnh skill (vd /notes): đưa path như dữ liệu, để chính skill quyết định lưu.
      outMsg = `[File đính kèm (đường dẫn), Sources="${src}", Attachments="${attDir}":\n${lines}]\n\n${_slash.message}`;
    } else {
      const ctx =
        `[File đính kèm để ĐỌC (đường dẫn):\n${lines}\n` +
        `Mặc định: chỉ đọc file rồi trả lời, KHÔNG tự lưu đi đâu.\n` +
        `CHỈ khi user yêu cầu rõ (vd "lưu vào source", "ingest", "ghi vào second brain") thì mới: ` +
        `chuyển thành .md (ảnh thì đọc hiểu + mô tả) lưu vào Sources="${src}" (ảnh gốc chuyển vào Attachments="${attDir}"), kèm frontmatter source.]`;
      outMsg = msg
        ? `${ctx}\n\n${msg}`
        : `${ctx}\n\nHãy đọc (các) file trên và phản hồi / tóm tắt nội dung chính.`;
    }
  }
```

Lưu ý: `appendUserMessage(msg, atts)` phía trên vẫn hiển thị `/notes ...` đúng như người dùng gõ; chỉ `outMsg` gửi engine mới là chuỗi bung.

- [ ] **Step 3: Nạp chat-slash.js trước app.js (index.html)**

Trong `dashboard/index.html`, tìm dòng nạp `chat-ask.js` (dòng ~581):

```html
  <script src="/static/chat-ask.js?v=1"></script>
  <script src="/static/app.js?v=68"></script>
```

Chèn `chat-slash.js` GIỮA hai dòng (trước app.js để listener keydown đăng ký trước) và tăng version app.js:

```html
  <script src="/static/chat-ask.js?v=1"></script>
  <script src="/static/chat-slash.js?v=1"></script>
  <script src="/static/app.js?v=69"></script>
```

- [ ] **Step 4: CSS menu (style.css)**

Thêm cuối `dashboard/style.css`:

```css
/* Menu lệnh / (chat-slash.js) */
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

- [ ] **Step 5: Chạy lại test node (không hồi quy logic)**

Run: `node dashboard/test_chat_slash.js`
Expected: `OK - test_chat_slash: tat ca pass`.

- [ ] **Step 6: Commit**

```bash
git add dashboard/chat-slash.js dashboard/app.js dashboard/index.html dashboard/style.css
git commit -m "feat(web): menu lenh / tren khung chat + dinh tuyen skill/lenh phien"
```

---

## Task 4: Xác minh end-to-end (web + Telegram + sync)

**Files:** không sửa file (chỉ chạy + quan sát). Nếu lỗi -> quay lại task tương ứng.

**Interfaces:** Consumes toàn bộ Task 1-3.

- [ ] **Step 1: Khởi động server nội bộ (nếu chưa chạy)**

Dùng `.venv` (python hệ thống thiếu lib - xem memory). Khởi động app theo cách dự án (vd `.venv/Scripts/python server/main.py` hoặc `start-javis.bat`). Mở dashboard trên trình duyệt.

- [ ] **Step 2: Xác minh menu web**

Trong ô chat: gõ `/` -> menu hiện, có `/new /reset /stop` + các skill (gồm `/notes`). Gõ `/no` -> lọc còn `notes` đầu danh sách. Mũi tên + Enter chọn `notes` -> ô điền `/notes `. Esc đóng menu.
Expected: đúng như trên; không có lỗi console.

- [ ] **Step 3: Xác minh /notes lưu nguyên văn (note đáng wiki)**

Gõ: `/notes Nguyên lý Pareto: 80% kết quả đến từ 20% nguyên nhân. Áp dụng khi ưu tiên công việc.` rồi gửi.
Expected: xuất hiện file `sources/note-<ngày>-*.md` với thân ĐÚNG nguyên văn; có trang `wiki/` mới (khái niệm) + `wiki/index.md` cập nhật; câu trả lời báo đã lưu + đã lên wiki. Kiểm:
```bash
ls "brains/Brain Default/sources/" | grep note-
```

- [ ] **Step 4: Xác minh /notes note vặt (không đáng)**

Gõ: `/notes Chiều nay 3h họp với anh Nam.` rồi gửi.
Expected: có file trong `sources/`, KHÔNG tạo trang wiki mới; câu trả lời báo "đã lưu note, chưa thấy đáng lên wiki".

- [ ] **Step 5: Xác minh /notes kèm ảnh**

Kéo 1 ảnh vào ô chat + gõ `/notes ảnh sản phẩm mẫu` + gửi.
Expected: ảnh nằm trong `attachments/`, source nhúng `![[...]]`; câu trả lời nhúng lại ảnh.

- [ ] **Step 6: Xác minh lệnh phiên**

`/new` -> mở hội thoại mới (không gửi cho engine). `/stop` khi đang có lượt chạy -> dừng.
Expected: đúng hành vi, không có tin nhắn "/new" gửi tới engine.

- [ ] **Step 7: Xác minh Telegram không hồi quy**

Từ Telegram gửi `/notes Test từ Telegram.`
Expected: skill `notes` chạy, tạo source trong brain của phiên Telegram.

- [ ] **Step 8: Xác minh sync sang brain khác**

Đổi sang một brain khác (dropdown), gõ `/` -> vẫn thấy `/notes` (system_sync đã rải). Nếu chưa thấy, chạy đồng bộ hệ thống theo dự án rồi thử lại.
Expected: `/notes` có mặt ở mọi brain.

---

## Task 5: Phát hành (bump VERSION + CHANGELOG + push)

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

Theo quy ước dự án: xong + test OK thì tự bump VERSION + CHANGELOG + commit + push origin/main.

- [ ] **Step 1: Bump VERSION**

Đọc `VERSION` hiện tại, tăng patch (vd 0.9.83 -> 0.9.84). Ghi lại vào `VERSION`.

- [ ] **Step 2: Ghi CHANGELOG**

Thêm mục đầu `CHANGELOG.md` cho phiên bản mới: mô tả khung lệnh `/` cho dashboard + skill `/notes` (lưu nguyên văn vào sources, wiki nếu đáng, chạy cả web lẫn Telegram).

- [ ] **Step 3: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore(release): 0.9.84 - khung lenh / + skill /notes"
git push origin main
```

Expected: push thành công lên origin/main.

---

## Self-Review (đã chạy khi viết plan)

- **Spec coverage:** Khung lệnh web (Task 2+3), skill notes (Task 1), lưu nguyên văn + ảnh (Task 1 + Task 3 step 2), wiki nếu đáng / báo nhẹ nếu không (Task 1 step 2), bundled + sync (Task 1 + Task 4 step 8), Telegram nhất quán (Task 2 buildSkillInvocation khớp mẫu + Task 4 step 7). Đủ.
- **Placeholder scan:** Không có TBD/TODO; mọi bước có code/lệnh thật.
- **Type consistency:** `route/parseSlash/buildMenu/filterItems/buildSkillInvocation` dùng thống nhất giữa Task 2 (định nghĩa) và Task 3 (tiêu thụ). `newChat()/stopCurrent()` là tên thật trong app.js.
