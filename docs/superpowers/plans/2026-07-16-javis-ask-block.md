# Khối hỏi-lại có lựa chọn trong khung chat Jarvis 007 - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jarvis 007 nhúng một khối ẩn ở cuối câu trả lời, dashboard bóc ra vẽ thành các nút bấm được ngay dưới bong bóng chat, bấm một nút thì gửi đi như người dùng gõ tay.

**Architecture:** Đi theo đúng vết khối `JAVIS_METRICS` đã chạy sẵn trong dự án: model nhúng HTML comment `<!-- JAVIS_ASK: {...} -->` ở cuối phản hồi, client bóc bằng regex ở nhánh `response` của WebSocket. Không đụng MCP hub, không đụng engine, nên chạy trên mọi bộ não chỉ nhờ system prompt. Logic mới nằm gọn trong một file `dashboard/chat-ask.js`; `app.js` chỉ thêm ba chỗ móc. Phía server thêm một hàm thuần trong `channel_context.py` hạ khối xuống thành danh sách đánh số cho Telegram.

**Tech Stack:** JavaScript thuần ES5-style IIFE (không build step, không framework), Python 3.12, FastAPI, test là script chạy thẳng (`python test_x.py`, `node test_x.js`).

## Global Constraints

- **TUYỆT ĐỐI không dùng ký tự em dash (U+2014)** ở bất kỳ đâu: mã, chú thích, tài liệu, chuỗi hiển thị. Dùng dấu gạch nối `-` hoặc viết lại câu. Đây là luật cứng của dự án (CLAUDE.md).
- Chú thích viết theo lệ của CHÍNH file đang sửa, đã kiểm chứng:
  - `dashboard/chat-ask.js` (file mới): tiếng Việt **KHÔNG DẤU**, theo lệ file cùng loại `chat-render.js`.
  - `dashboard/app.js`: tiếng Việt **CÓ DẤU**, đúng lệ đang có trong file đó.
  - `server/*.py`: tiếng Việt **CÓ DẤU**, đúng lệ `channel_context.py`.
  - Chuỗi HIỂN THỊ cho người dùng thì luôn có dấu, kể cả trong `chat-ask.js` (ví dụ `"Ý khác…"`).
- Mọi text do model sinh ra là **không tin được**: phải escape trước khi nhét vào HTML.
- File JS dashboard theo khuôn IIFE `(function () { "use strict"; ... })()`, phơi API qua `window.X`, và có nhánh `module.exports` cuối file để test bằng node. Xem `chat-render.js:484-491` làm mẫu.
- Test là script chạy thẳng, tự in `ok`/`FAIL` và `sys.exit(1)` khi có lỗi. KHÔNG dùng pytest (CI chạy `python test_*.py` từng file).
- Thêm `<script>` vào `index.html` phải có tham số cache-bust `?v=N`.
- Tối đa 4 lựa chọn mỗi khối. Một khối là một câu hỏi. Không có chọn nhiều đáp án.

---

### Task 1: Bóc khối JAVIS_ASK ra khỏi text (hàm thuần)

Đây là phần lõi và là phần duy nhất test tự động được không cần trình duyệt. Làm trước, xong mới vẽ giao diện.

**Files:**
- Create: `dashboard/chat-ask.js`
- Test: `dashboard/test_chat_ask.js`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: không có (task đầu tiên).
- Produces: `window.JavisAsk.extract(text)` trả `{ clean: string, ask: Ask|null }`, trong đó
  `Ask = { question: string, header: string, options: Array<{label: string, desc: string}> }`.
  `clean` luôn là text đã bị bóc sạch khối, kể cả khi JSON hỏng. `ask` là `null` khi
  không có khối, JSON hỏng, thiếu `question`, hoặc không còn lựa chọn hợp lệ nào.
  Task 2 và Task 3 dùng đúng tên này.

- [ ] **Step 1: Viết test thất bại**

Tạo `dashboard/test_chat_ask.js`:

```js
/* Test bo boc khoi JAVIS_ASK. Chay tay / CI:
       node dashboard/test_chat_ask.js
   KHONG can trinh duyet: chi test ham thuan extract(). */
const { extract } = require("./chat-ask.js");

let fails = [];
function check(name, cond) {
  console.log((cond ? "ok   " : "FAIL ") + name);
  if (!cond) fails.push(name);
}

// ---- 1. Khoi hop le ----
const okBlock = 'Doanh thu hom nay 250k.\n\n<!-- JAVIS_ASK: {"question":"Xem ky nao?","header":"Ky","options":[{"label":"Tuan nay","desc":"7 ngay"},{"label":"Thang nay","desc":"Tu mung 1"}]} -->';
let r = extract(okBlock);
check("hop le: clean bo sach khoi", r.clean === "Doanh thu hom nay 250k.");
check("hop le: doc dung question", r.ask && r.ask.question === "Xem ky nao?");
check("hop le: doc dung header", r.ask && r.ask.header === "Ky");
check("hop le: doc dung 2 lua chon", r.ask && r.ask.options.length === 2 &&
  r.ask.options[0].label === "Tuan nay" && r.ask.options[1].desc === "Tu mung 1");

// ---- 2. Khong co khoi ----
r = extract("Chi la cau tra loi binh thuong.");
check("khong khoi: ask = null", r.ask === null);
check("khong khoi: clean giu nguyen text", r.clean === "Chi la cau tra loi binh thuong.");

// ---- 3. JSON hong: KHONG duoc nuot cau tra loi, van phai bo khoi rac ----
r = extract('Cau tra loi that.\n\n<!-- JAVIS_ASK: {"question": broken json here -->');
check("json hong: ask = null", r.ask === null);
check("json hong: van giu cau tra loi", r.clean === "Cau tra loi that.");
check("json hong: khoi rac bi bo, khong lo ra man hinh", r.clean.indexOf("JAVIS_ASK") === -1);

// ---- 4. Thua lua chon -> cat con 4 ----
const many = '<!-- JAVIS_ASK: {"question":"Chon?","options":[{"label":"a"},{"label":"b"},{"label":"c"},{"label":"d"},{"label":"e"},{"label":"f"}]} -->';
r = extract(many);
check("thua lua chon: cat con 4", r.ask && r.ask.options.length === 4);
check("thua lua chon: giu 4 cai dau", r.ask && r.ask.options[3].label === "d");
check("thieu desc: desc thanh chuoi rong", r.ask && r.ask.options[0].desc === "");

// ---- 5. options rong / thieu question -> coi nhu khong co khoi ----
r = extract('Text.\n<!-- JAVIS_ASK: {"question":"Chon?","options":[]} -->');
check("options rong: ask = null", r.ask === null);
check("options rong: van bo khoi", r.clean === "Text.");
r = extract('<!-- JAVIS_ASK: {"options":[{"label":"a"}]} -->');
check("thieu question: ask = null", r.ask === null);

// ---- 6. Khoi nam GIUA bai (khong phai cuoi) van boc duoc ----
r = extract('Dau bai.\n<!-- JAVIS_ASK: {"question":"Chon?","options":[{"label":"a"}]} -->\nCuoi bai.');
check("khoi giua bai: van doc duoc ask", r.ask && r.ask.question === "Chon?");
check("khoi giua bai: clean noi lai 2 dau", r.clean === "Dau bai.\n\nCuoi bai.");

// ---- 7. Song chung voi JAVIS_METRICS ----
const both = 'Bao cao.\n<!-- JAVIS_METRICS: [{"label":"Doanh thu","value":"250k"}] -->\n<!-- JAVIS_ASK: {"question":"Chon?","options":[{"label":"a"}]} -->';
r = extract(both);
check("song chung metrics: doc duoc ask", r.ask && r.ask.question === "Chon?");
check("song chung metrics: KHONG dung vao khoi metrics", r.clean.indexOf("JAVIS_METRICS") !== -1);

// ---- 8. Dau vao khong phai chuoi ----
r = extract(null);
check("dau vao null: khong no", r.ask === null && r.clean === "");

if (fails.length) {
  console.log("\nFAIL - " + fails.length + " test: " + fails.join(", "));
  process.exit(1);
}
console.log("\nOK - test_chat_ask: tat ca pass");
```

- [ ] **Step 2: Chạy test để chắc chắn nó thất bại**

Run: `node dashboard/test_chat_ask.js`
Expected: FAIL, `Error: Cannot find module './chat-ask.js'`

- [ ] **Step 3: Viết bản cài đặt tối thiểu**

Tạo `dashboard/chat-ask.js`:

```js
/* chat-ask.js - khoi hoi-lai co lua chon cho khung chat Jarvis 007.

   Jarvis 007 ket thuc cau tra loi bang mot khoi an:
     <!-- JAVIS_ASK: {"question":"...","header":"...","options":[{"label":"..","desc":".."}]} -->
   File nay boc khoi do ra, ve thanh hang chip duoi bong bong tra loi, va bat su kien bam.
   Bam mot chip = gui dung nhan do di nhu mot tin nhan nguoi dung binh thuong.

   Di theo dung vet khoi JAVIS_METRICS da chay san (app.js). KHONG dung MCP hub, khong
   dung engine -> chay tren moi bo nao chi nho system prompt.

   An toan: moi text trong khoi la do model sinh ra -> escape het truoc khi nhet vao HTML.
   Ghi chu: KHONG dung ky tu em dash o bat ky dau. */
(function () {
  "use strict";

  var ASK_RE = /<!--\s*JAVIS_ASK:\s*([\s\S]*?)\s*-->/;
  var MAX_OPTS = 4;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Boc khoi JAVIS_ASK khoi text. LUON tra clean da bo khoi (ke ca khi JSON hong) -
  // mot khoi sai cu phap KHONG duoc phep nuot mat cau tra loi cua Jarvis 007.
  function extract(text) {
    if (typeof text !== "string") return { clean: "", ask: null };
    var m = text.match(ASK_RE);
    if (!m) return { clean: text, ask: null };
    var clean = text.replace(ASK_RE, "").replace(/\n{3,}/g, "\n\n").trim();
    var ask = null;
    try {
      var o = JSON.parse(m[1]);
      var opts = (o && Array.isArray(o.options) ? o.options : [])
        .filter(function (x) { return x && typeof x.label === "string" && x.label.trim(); })
        .slice(0, MAX_OPTS)
        .map(function (x) {
          return { label: String(x.label).trim(), desc: String(x.desc == null ? "" : x.desc).trim() };
        });
      var q = (o && typeof o.question === "string") ? o.question.trim() : "";
      if (q && opts.length) {
        ask = { question: q, header: String((o && o.header) == null ? "" : o.header).trim(), options: opts };
      }
    } catch (e) {}
    return { clean: clean, ask: ask };
  }

  if (typeof window !== "undefined") {
    window.JavisAsk = { extract: extract };
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { extract: extract };
  }
})();
```

- [ ] **Step 4: Chạy test để chắc chắn nó pass**

Run: `node dashboard/test_chat_ask.js`
Expected: PASS, dòng cuối `OK - test_chat_ask: tat ca pass`

- [ ] **Step 5: Cho CI chạy test node này**

Sửa `.github/workflows/ci.yml`, chèn một step MỚI ngay trước step `Chạy test (auth/secret/MCP-perm/traversal/CSRF + plugin)`. Runner `ubuntu-latest` đã có sẵn node, không cần cài gì thêm và không có `package.json` nên không cần `npm install`:

```yaml
      - name: Chạy test JS dashboard
        run: node dashboard/test_chat_ask.js
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/chat-ask.js dashboard/test_chat_ask.js .github/workflows/ci.yml
git commit -m "feat(chat): bóc khối JAVIS_ASK khỏi câu trả lời (hàm thuần + test)"
```

---

### Task 2: Vẽ hàng chip và bắt sự kiện bấm

**Files:**
- Modify: `dashboard/chat-ask.js` (thêm vào file đã tạo ở Task 1)
- Modify: `dashboard/style.css` (thêm vào cuối file)
- Modify: `dashboard/index.html:602`

**Interfaces:**
- Consumes: `extract()` và `esc()` từ Task 1, cùng file.
- Produces: mở rộng `window.JavisAsk` thành
  `{ extract, render(msgEl, ask, live) -> HTMLElement|null, freezeAll() -> void }`.
  `render` nhận thẻ `.msg-javis`, tự tìm `.bubble` bên trong rồi gắn khối chip vào cuối
  bubble; `live=false` thì vẽ luôn ở trạng thái đông cứng. `freezeAll()` đông cứng mọi
  hàng chip đang sống. Task 3 gọi đúng hai tên này.
- Phụ thuộc NGOÀI file: chip khi được bấm sẽ gọi `window.JavisSend(label)`. Hàm đó do
  **Task 3** tạo trong `app.js`. Ở task này `window.JavisSend` chưa tồn tại, nên mã phải
  kiểm tra trước khi gọi và không được nổ nếu thiếu.

- [ ] **Step 1: Thêm render + freezeAll + bắt sự kiện vào chat-ask.js**

Trong `dashboard/chat-ask.js`, chèn khối dưới đây vào NGAY TRƯỚC đoạn `if (typeof window !== "undefined")` ở cuối file:

```js
  var MAX_LABEL = 40;
  function cut(s) {
    s = String(s || "");
    return s.length > MAX_LABEL ? s.slice(0, MAX_LABEL - 1) + "…" : s;
  }

  // Ve hang chip vao cuoi .bubble cua thu tin nhan Jarvis 007.
  // live=false -> ve san o trang thai dong cung (dung khi khoi phuc lich su).
  function render(msgEl, ask, live) {
    if (!msgEl || !ask || !ask.options || !ask.options.length) return null;
    var host = msgEl.querySelector(".bubble") || msgEl;
    var old = host.querySelector(".jv-ask");
    if (old) old.parentNode.removeChild(old);   // re-render thi thay, khong chong len nhau
    var box = document.createElement("div");
    box.className = "jv-ask" + (live ? "" : " jv-ask-done");
    var tag = ask.header ? '<span class="jv-ask-tag">' + esc(ask.header) + "</span>" : "";
    var chips = ask.options.map(function (o, i) {
      return '<button class="jv-ask-chip" type="button" data-i="' + i + '" title="' +
        esc(o.desc || o.label) + '">' + esc(cut(o.label)) + "</button>";
    }).join("");
    box.innerHTML =
      '<div class="jv-ask-q">' + tag + esc(ask.question) + "</div>" +
      '<div class="jv-ask-row">' + chips +
        '<button class="jv-ask-chip jv-ask-other" type="button" data-other="1">Ý khác…</button>' +
      "</div>";
    box._ask = ask;              // giu ban goc de doc lai nhan that (khong phai nhan da cat)
    host.appendChild(box);
    return box;
  }

  // Dong cung moi hang chip dang song. Goi khi co tin nhan moi (bam chip hoac go tay):
  // cuon nguoc len lich su ma bam duoc cau hoi cu se lam roi mach hoi thoai.
  function freezeAll() {
    if (typeof document === "undefined") return;
    var boxes = document.querySelectorAll(".jv-ask:not(.jv-ask-done)");
    Array.prototype.forEach.call(boxes, function (b) { b.classList.add("jv-ask-done"); });
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", function (e) {
      var chip = e.target.closest ? e.target.closest(".jv-ask-chip") : null;
      if (!chip) return;
      var box = chip.closest(".jv-ask");
      if (!box || box.classList.contains("jv-ask-done")) return;   // lich su: bam khong an gi
      e.preventDefault();
      if (chip.dataset.other) {                                     // "Y khac" = tu go, khong gui gi
        var inp = document.getElementById("chatInput");
        if (inp) inp.focus();
        return;
      }
      var ask = box._ask;
      var opt = ask && ask.options[+chip.dataset.i];
      if (!opt) return;
      chip.classList.add("jv-ask-picked");   // danh dau TRUOC khi gui: JavisSend se freeze ca hang
      if (typeof window.JavisSend === "function") window.JavisSend(opt.label);
    });
  }
```

Rồi sửa đoạn cuối file để phơi thêm hai hàm mới:

```js
  if (typeof window !== "undefined") {
    window.JavisAsk = { extract: extract, render: render, freezeAll: freezeAll };
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { extract: extract };
  }
```

- [ ] **Step 2: Chạy lại test Task 1 để chắc chắn không làm hỏng hàm thuần**

Run: `node dashboard/test_chat_ask.js`
Expected: PASS, `OK - test_chat_ask: tat ca pass`

Nếu FAIL với lỗi `document is not defined` thì nghĩa là đã quên bọc `if (typeof document !== "undefined")` quanh phần bắt sự kiện. Node không có DOM.

- [ ] **Step 3: Thêm CSS**

Thêm vào CUỐI `dashboard/style.css`:

```css
/* Khoi hoi-lai co lua chon (chat-ask.js) */
.jv-ask { margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--border); }
.jv-ask-q { font-size: 13px; color: var(--text2); margin-bottom: 7px; }
.jv-ask-tag {
  display: inline-block; margin-right: 6px; padding: 1px 6px; border-radius: 5px;
  background: var(--bg3); border: 1px solid var(--border);
  color: var(--text3); font-size: 11px; text-transform: uppercase; letter-spacing: .4px;
}
.jv-ask-row { display: flex; flex-wrap: wrap; gap: 6px; }
.jv-ask-chip {
  background: var(--bg3); border: 1px solid var(--border); color: var(--text);
  border-radius: 999px; padding: 5px 12px; font-family: var(--font); font-size: 13px;
  cursor: pointer; transition: border-color .15s, color .15s, background .15s;
}
.jv-ask-chip:hover { border-color: var(--accent); color: var(--accent); }
.jv-ask-other { color: var(--text3); border-style: dashed; }

/* Da tra loi: cung lai, chi con doc duoc */
.jv-ask-done .jv-ask-chip { cursor: default; opacity: .45; }
.jv-ask-done .jv-ask-chip:hover { border-color: var(--border); color: var(--text); }
.jv-ask-done .jv-ask-other { display: none; }
.jv-ask-done .jv-ask-chip.jv-ask-picked {
  opacity: 1; border-color: var(--accent); color: var(--accent); background: rgba(255,122,60,.12);
}
.jv-ask-done .jv-ask-chip.jv-ask-picked::before { content: "✓ "; }
```

- [ ] **Step 4: Nạp file vào trang**

Sửa `dashboard/index.html`, thêm một dòng NGAY SAU dòng 602 (`chat-render.js`) và TRƯỚC `app.js`:

```html
  <script src="/static/chat-ask.js?v=1"></script>
```

- [ ] **Step 5: Kiểm tra bằng mắt trong trình duyệt**

Bật app lên (`start-javis.bat`, hoặc `cd server && python main.py`), mở dashboard, mở Console của trình duyệt (F12) rồi dán:

```js
const el = document.querySelector(".msg-javis");
JavisAsk.render(el, { question: "Anh muốn xem kỳ nào?", header: "Kỳ",
  options: [{label:"Tuần này",desc:"7 ngày gần nhất"},{label:"Tháng này",desc:"Từ mùng 1"}] }, true);
```

Expected: hàng chip hiện ra dưới bong bóng trả lời gần nhất, có nhãn "KỲ", hai nút bấm được và một nút "Ý khác…" viền đứt. Rê chuột lên nút thấy tooltip mô tả. Bấm "Ý khác…" thì con trỏ nhảy xuống ô nhập liệu. Bấm "Tuần này" thì nó nhận dấu tích và mờ đi các nút còn lại (chưa gửi được vì `window.JavisSend` sẽ có ở Task 3).

Rồi chạy `JavisAsk.freezeAll()` trong Console: mọi hàng chip còn sống phải cứng lại và nút "Ý khác…" biến mất.

- [ ] **Step 6: Commit**

```bash
git add dashboard/chat-ask.js dashboard/style.css dashboard/index.html
git commit -m "feat(chat): vẽ hàng chip lựa chọn dưới bong bóng trả lời"
```

---

### Task 3: Nối vào luồng chat của app.js

**Files:**
- Modify: `dashboard/app.js:159-175` (nhánh `response`)
- Modify: `dashboard/app.js:242-246` (`recordTurn`)
- Modify: `dashboard/app.js:247-264` (`restoreSession`)
- Modify: `dashboard/app.js:331-337` (`appendJavisMessage`)
- Modify: `dashboard/app.js:189-232` (`sendMessage`)
- Modify: `dashboard/index.html:603` (bump `?v=` của app.js)

**Interfaces:**
- Consumes: `window.JavisAsk.extract(text)`, `window.JavisAsk.render(msgEl, ask, live)`,
  `window.JavisAsk.freezeAll()` từ Task 1 và Task 2.
- Produces: `window.JavisSend(text)` - hàm chip gọi để gửi lựa chọn đi. Task 2 đã gọi tên
  này rồi, task này mới tạo ra nó.

- [ ] **Step 1: Cho appendJavisMessage trả về thẻ vừa tạo**

Ở `dashboard/app.js:331`, hàm hiện đang không trả gì. Cần thẻ đó để gắn chip vào. Sửa thành:

```js
function appendJavisMessage(text) {
  const div = document.createElement("div");
  div.className = "msg msg-javis";
  div.innerHTML = `<div class="bubble">${markdownToHtml(text)}</div>` +
    `<button class="msg-copy" type="button" title="Copy cả tin nhắn">⧉</button>`;
  chatAppend(div); scrollBottom();
  return div;
}
```

- [ ] **Step 2: Cho recordTurn nhớ luôn khối ask**

Ở `dashboard/app.js:242`, sửa thành:

```js
function recordTurn(role, text, atts, ask) {
  convo.push({ role, text: text || "", atts: atts || [], ask: ask || null });
  if (convo.length > 200) convo = convo.slice(-200);
  persistSession();
}
```

Tham số thêm ở cuối và có giá trị mặc định, nên hai chỗ gọi cũ (`recordTurn("user", ...)` và `recordTurn("javis", finalText)`) vẫn chạy y như trước.

- [ ] **Step 3: Bóc ask ở nhánh response và vẽ chip**

Ở `dashboard/app.js:159`, nhánh `else if (data.type === "response")` hiện là:

```js
  } else if (data.type === "response") {
    const { clean, cards } = extractMetrics(data.content);
    const finalText = clean || (t && t.text) || "";
```

Sửa thành (bóc metrics trước, rồi bóc ask trên phần còn lại):

```js
  } else if (data.type === "response") {
    const { clean, cards } = extractMetrics(data.content);
    const { clean: askClean, ask } = window.JavisAsk.extract(clean);
    const finalText = askClean || (t && t.text) || "";
```

Rồi trong cùng nhánh đó, khối `if (isActive) { ... }` hiện là:

```js
      if (!t || !t.bubble) appendJavisMessage(shownText);
      else t.bubble.querySelector(".bubble").innerHTML = markdownToHtml(shownText);
      if (data.engine) setEngineBadge(data.engine, data.model);   // sự thật engine+model của lượt này
      if (finalText.trim()) recordTurn("javis", finalText);
```

Sửa thành:

```js
      let msgEl = t && t.bubble;
      if (!msgEl) msgEl = appendJavisMessage(shownText);
      else msgEl.querySelector(".bubble").innerHTML = markdownToHtml(shownText);
      if (ask) window.JavisAsk.render(msgEl, ask, true);   // chip chỉ mọc khi lượt xong
      if (data.engine) setEngineBadge(data.engine, data.model);   // sự thật engine+model của lượt này
      if (finalText.trim()) recordTurn("javis", finalText, null, ask);
```

- [ ] **Step 4: Đông cứng chip cũ khi có tin nhắn mới, và phơi JavisSend**

Ở `dashboard/app.js:189`, hàm `sendMessage(text)` hiện có đoạn:

```js
  voice.stopSpeaking();
  appendUserMessage(msg, atts);
```

Sửa thành:

```js
  voice.stopSpeaking();
  window.JavisAsk.freezeAll();   // trả lời rồi thì chip của lượt trước hết bấm được
  appendUserMessage(msg, atts);
```

Rồi thêm NGAY SAU dấu `}` đóng của hàm `sendMessage`:

```js
// Chip lựa chọn (chat-ask.js) gửi đáp án qua đây: bấm chip = y như người dùng gõ tay nhãn đó.
window.JavisSend = sendMessage;
```

- [ ] **Step 5: Khôi phục chip sau F5**

Ở `dashboard/app.js:254`, đoạn dựng lại bong bóng hiện là:

```js
  convo.forEach(t => {
    if (t.role === "user") appendUserMessage(t.text, t.atts || []);
    else appendJavisMessage(t.text);
  });
```

Sửa thành:

```js
  convo.forEach((t, i) => {
    if (t.role === "user") { appendUserMessage(t.text, t.atts || []); return; }
    const el = appendJavisMessage(t.text);
    // Chip chỉ sống lại ở tin CUỐI: có tin sau nó nghĩa là câu hỏi đã được trả lời rồi.
    if (t.ask) window.JavisAsk.render(el, t.ask, i === convo.length - 1);
  });
```

- [ ] **Step 6: Bump cache-bust của app.js**

Ở `dashboard/index.html:603`, đổi `<script src="/static/app.js?v=66"></script>` thành `?v=67`. Không bump thì trình duyệt của anh Quy vẫn nạp app.js cũ và chip sẽ không bao giờ hiện.

- [ ] **Step 7: Kiểm tra bằng tay trong trình duyệt**

Bật app, mở dashboard, gõ vào ô chat:

```
Trả lời "Xong rồi anh." rồi nhúng đúng khối này vào cuối, giữ nguyên từng ký tự:
<!-- JAVIS_ASK: {"question":"Anh muốn xem kỳ nào?","header":"Kỳ","options":[{"label":"Tuần này","desc":"7 ngày gần nhất"},{"label":"Tháng này","desc":"Từ mùng 1"}]} -->
```

Expected, theo đúng thứ tự:
1. Lúc chữ đang chảy về: KHÔNG thấy khối JSON thô nào nhấp nháy trên màn hình.
2. Lượt xong: hàng chip mọc ra dưới bong bóng, câu trả lời "Xong rồi anh." vẫn còn nguyên.
3. Bấm "Tuần này": hiện tin nhắn người dùng "Tuần này" y như gõ tay, Jarvis 007 bắt đầu trả lời tiếp, hàng chip cứng lại với dấu tích ở "Tuần này".
4. Cuộn lên bấm lại vào hàng chip cũ: không có gì xảy ra.
5. F5: chip vẫn còn, vẫn ở trạng thái đã trả lời, không bấm được.
6. Làm lại bước 1-2 rồi F5 NGAY (chưa trả lời): chip sống lại và bấm được.

- [ ] **Step 8: Commit**

```bash
git add dashboard/app.js dashboard/index.html
git commit -m "feat(chat): nối khối hỏi-lại vào luồng chat, bấm chip là gửi như gõ tay"
```

---

### Task 4: Hạ khối xuống chữ cho Telegram (và vá lỗi rò JAVIS_METRICS)

Task này độc lập hoàn toàn với Task 1-3, làm trước hay sau đều được.

Lưu ý bối cảnh: khối `JAVIS_METRICS` **đang lọt nguyên xi sang Telegram** ở bản hiện tại. `_tg_answer` trả `out` thô, còn `telegram_bot.md_to_mdv2` chỉ escape chứ không bóc comment, nên người dùng Telegram đang nhìn thấy cả cụm `<\!\-\- JAVIS\_METRICS: ...`. Khối `JAVIS_ASK` sẽ rò y hệt nếu không xử. Hàm ở task này vá cả hai cùng lúc.

**Files:**
- Modify: `server/channel_context.py` (thêm hàm mới ở cuối file)
- Create: `server/test_channel_ask.py`
- Modify: `server/main.py:4614-4693` (hàm `_tg_answer`)

**Interfaces:**
- Consumes: không có.
- Produces: `channel_context.strip_control_blocks(text: str) -> str`. Bóc mọi khối
  `<!-- JAVIS_*: ... -->` khỏi text. Riêng `JAVIS_ASK` thì thay bằng câu hỏi cộng danh
  sách đánh số. Trả text đã sạch.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_channel_ask.py`:

```python
"""Test hạ khối điều khiển xuống chữ cho kênh không phải web (v0.9.61). Chạy tay / CI:

    cd server && python test_channel_ask.py

KHÔNG mạng. Phủ: JAVIS_ASK xuống danh sách đánh số, JAVIS_METRICS biến mất sạch
(hồi quy cho lỗi rò sang Telegram), JSON hỏng không nuốt câu trả lời.
"""
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-asktest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import channel_context  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


strip = channel_context.strip_control_blocks

# ---- 1. JAVIS_ASK xuống danh sách đánh số ----
ask = ('Doanh thu hôm nay 250k.\n\n<!-- JAVIS_ASK: {"question":"Xem kỳ nào?",'
       '"options":[{"label":"Tuần này","desc":"7 ngày"},{"label":"Tháng này"}]} -->')
out = strip(ask)
check("ask: giữ câu trả lời", "Doanh thu hôm nay 250k." in out)
check("ask: có câu hỏi", "Xem kỳ nào?" in out)
check("ask: đánh số 1", "1. Tuần này" in out)
check("ask: đánh số 2", "2. Tháng này" in out)
check("ask: không lộ khối thô", "JAVIS_ASK" not in out and "<!--" not in out)

# ---- 2. JAVIS_METRICS biến mất sạch (hồi quy lỗi rò sang Telegram) ----
met = 'Báo cáo xong.\n\n<!-- JAVIS_METRICS: [{"label":"Doanh thu","value":"250k"}] -->'
out = strip(met)
check("metrics: biến mất sạch", "JAVIS_METRICS" not in out and "<!--" not in out)
check("metrics: giữ câu trả lời", out.strip() == "Báo cáo xong.")

# ---- 3. Cả hai khối cùng lúc ----
both = ('Báo cáo.\n<!-- JAVIS_METRICS: [{"label":"A","value":"1"}] -->\n'
        '<!-- JAVIS_ASK: {"question":"Chọn?","options":[{"label":"a"}]} -->')
out = strip(both)
check("cả hai: metrics mất, ask thành danh sách", "JAVIS_METRICS" not in out
      and "1. a" in out and "Chọn?" in out)

# ---- 4. JSON hỏng: bỏ khối rác nhưng KHÔNG nuốt câu trả lời ----
bad = 'Câu trả lời thật.\n<!-- JAVIS_ASK: {"question": hỏng rồi -->'
out = strip(bad)
check("json hỏng: giữ câu trả lời", out.strip() == "Câu trả lời thật.")
check("json hỏng: không lộ khối thô", "JAVIS_ASK" not in out)

# ---- 5. Thừa lựa chọn cắt còn 4 ----
many = ('<!-- JAVIS_ASK: {"question":"Chọn?","options":[{"label":"a"},{"label":"b"},'
        '{"label":"c"},{"label":"d"},{"label":"e"}]} -->')
out = strip(many)
check("thừa lựa chọn: cắt còn 4", "4. d" in out and "5. e" not in out)

# ---- 6. Không có khối: trả nguyên văn ----
check("không khối: giữ nguyên", strip("Chỉ là câu trả lời.") == "Chỉ là câu trả lời.")
check("text rỗng: không nổ", strip("") == "")
check("None: không nổ", strip(None) == "")

if _fails:
    print(f"\nFAIL - {len(_fails)} test: {_fails}")
    sys.exit(1)
print("\nOK - test_channel_ask: tất cả pass")
```

- [ ] **Step 2: Chạy test để chắc chắn nó thất bại**

Run: `cd server && python test_channel_ask.py`
Expected: FAIL với `AttributeError: module 'channel_context' has no attribute 'strip_control_blocks'`

- [ ] **Step 3: Viết bản cài đặt tối thiểu**

Đầu file `server/channel_context.py` hiện là `import os` / `import re` / `from pathlib import Path`. Thêm `import json` vào đúng thứ tự bảng chữ cái (trước `import os`), theo lệ file:

```python
import json
import os
import re
from pathlib import Path
```

Rồi thêm vào CUỐI `server/channel_context.py`:

```python
# ============================================================
# Hạ khối điều khiển xuống chữ cho kênh không phải web
# ============================================================
# Jarvis 007 nhúng khối điều khiển dạng HTML comment ở cuối câu trả lời cho dashboard
# đọc (JAVIS_METRICS bơm panel trái, JAVIS_ASK vẽ nút lựa chọn). Kênh chữ thuần
# như Telegram không hiểu mấy khối này, mà md_to_mdv2 chỉ escape chứ không bóc,
# nên không lọc là người dùng nhìn thấy nguyên cụm "<\!\-\- JAVIS\_METRICS: ...".
_CTRL_RE = re.compile(r"<!--\s*JAVIS_([A-Z_]+):\s*([\s\S]*?)\s*-->")
_MAX_ASK_OPTS = 4


def _ask_to_text(payload: str) -> str:
    """JSON của khối JAVIS_ASK -> câu hỏi + danh sách đánh số. JSON hỏng -> chuỗi rỗng.

    Người dùng Telegram nhắn lại "1" là xong: Jarvis 007 đọc "1" trong ngữ cảnh câu hỏi
    vừa hỏi thì tự hiểu, không cần lưu state.
    """
    try:
        o = json.loads(payload)
    except Exception:
        return ""
    if not isinstance(o, dict):
        return ""
    q = str(o.get("question") or "").strip()
    opts = [x for x in (o.get("options") or [])
            if isinstance(x, dict) and str(x.get("label") or "").strip()]
    if not q or not opts:
        return ""
    lines = [q]
    for i, x in enumerate(opts[:_MAX_ASK_OPTS], 1):
        lines.append(f"{i}. {str(x['label']).strip()}")
    return "\n".join(lines)


def strip_control_blocks(text: str) -> str:
    """Bóc mọi khối <!-- JAVIS_*: ... --> khỏi text.

    JAVIS_ASK -> thay bằng câu hỏi + danh sách đánh số. Khối khác -> bỏ hẳn.
    Khối sai cú pháp cũng bị bỏ: một khối hỏng KHÔNG được phép nuốt mất câu trả lời.
    """
    def _sub(m):
        if m.group(1) == "ASK":
            t = _ask_to_text(m.group(2))
            return ("\n\n" + t) if t else ""
        return ""

    out = _CTRL_RE.sub(_sub, text or "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()
```

- [ ] **Step 4: Chạy test để chắc chắn nó pass**

Run: `cd server && python test_channel_ask.py`
Expected: PASS, dòng cuối `OK - test_channel_ask: tất cả pass`

- [ ] **Step 5: Nối vào đường trả lời Telegram**

`_tg_answer` có ĐÚNG HAI lệnh `return` mang text của model, phải sửa cả hai. Các lệnh `return "⚠ " + ev["content"]` thì để nguyên: đó là câu báo lỗi do Jarvis 007 tự sinh, không bao giờ chứa khối.

**Đường 1, engine API** (`server/main.py`, khoảng dòng 4655). Hiện là:

```python
        sess["or"] = await compaction.compact_mem(sess["or"], prov, api_key, api_model, _api_stream)
        return out   # engine API không có tool ghi file → không có gì để đính kèm
```

Sửa thành:

```python
        sess["or"] = await compaction.compact_mem(sess["or"], prov, api_key, api_model, _api_stream)
        # Telegram là kênh chữ thuần: hạ khối điều khiển xuống chữ, đừng để lọt cụm thô.
        # Lọc lúc TRẢ, không lọc trước khi append vào sess["or"]: lịch sử của model giữ nguyên bản gốc.
        return channel_context.strip_control_blocks(out)   # engine API không có tool ghi file → không có gì để đính kèm
```

Lưu ý thứ tự: dòng `sess["or"].append({"role": "assistant", "content": out})` ở phía trên giữ nguyên `out` thô. Đó là lịch sử hội thoại của model, không phải thứ hiển thị cho người, nên không lọc.

**Đường 2, engine Claude CLI** (khoảng dòng 4690, cuối hàm). Hiện là:

```python
        # File sinh ra trong lượt → bot gửi đính kèm SAU câu trả lời (xem telegram_bot._handle_turn)
        files = channel_context.collect_turn_files(out, written, t0,
                                                   cwd=CLAUDE_CWD, exclude=sess["sent"])
        return {"text": out, "files": files}
```

Sửa thành:

```python
        # File sinh ra trong lượt → bot gửi đính kèm SAU câu trả lời (xem telegram_bot._handle_turn)
        files = channel_context.collect_turn_files(out, written, t0,
                                                   cwd=CLAUDE_CWD, exclude=sess["sent"])
        # Lọc SAU collect_turn_files: hàm đó dò đường dẫn file trong text gốc, lọc trước là mất dấu.
        return {"text": channel_context.strip_control_blocks(out), "files": files}
```

- [ ] **Step 6: Kiểm chứng lỗi rò đã hết**

Run:

```bash
cd server && python -c "
import channel_context as c
s = 'Doanh thu 250k.\n\n<!-- JAVIS_METRICS: [{\"label\":\"Doanh thu\",\"value\":\"250k\"}] -->'
print(repr(c.strip_control_blocks(s)))
"
```

Expected: in ra đúng `'Doanh thu 250k.'`, không còn dấu vết `JAVIS_METRICS`. So với trước khi sửa, chạy `md_to_mdv2` trên cùng chuỗi cho ra `'Doanh thu 250k\\.\n\n<\\!\\-\\- JAVIS\\_METRICS: ...'`.

- [ ] **Step 7: Chạy toàn bộ test server để chắc chắn không làm hỏng gì**

Run: `cd server && for f in test_*.py; do echo "==== $f ===="; python "$f" || echo BROKEN; done`
Expected: mọi file in dòng `OK - ...`, không có `BROKEN`.

- [ ] **Step 8: Commit**

```bash
git add server/channel_context.py server/test_channel_ask.py server/main.py
git commit -m "fix(telegram): hạ khối điều khiển xuống chữ, vá lỗi rò JAVIS_METRICS"
```

---

### Task 5: Dạy Jarvis 007 khi nào hỏi lại, và phát hành

**Files:**
- Modify: `CLAUDE.md` (mục "Làm rõ trước khi trả lời")
- Modify: `VERSION`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: hợp đồng khối `JAVIS_ASK` từ Task 1, đường Telegram từ Task 4.
- Produces: không có mã.

- [ ] **Step 1: Thêm luật vào CLAUDE.md**

Trong `CLAUDE.md`, mục "Làm rõ trước khi trả lời (prompt chuẩn)" hiện kết thúc bằng:

```
4. Câu đơn giản/rõ ràng thì bỏ qua bước này, trả lời thẳng.

Mục tiêu: biến câu hỏi thô thành yêu cầu rõ ràng rồi mới thực thi - đỡ làm sai, đỡ hỏi đi hỏi lại.
```

Thêm NGAY SAU đoạn đó:

```markdown
### Hỏi lại bằng nút bấm (khối JAVIS_ASK)

Khi bước 3 ở trên bắt buộc phải hỏi lại VÀ câu hỏi có vài đáp án rõ ràng, hãy nhúng khối
sau vào CUỐI câu trả lời (vô hình với user, dashboard tự vẽ thành nút bấm):

```
<!-- JAVIS_ASK: {"question":"Anh muốn xem doanh thu kỳ nào?","header":"Kỳ","options":[{"label":"Tuần này","desc":"7 ngày gần nhất"},{"label":"Tháng này","desc":"Từ mùng 1"},{"label":"So tháng trước","desc":"Có đối chiếu"}]} -->
```

- `question` bắt buộc, `header` là nhãn chủ đề ngắn, `options` **tối đa 4**, mỗi cái có
  `label` (chữ trên nút, ngắn gọn) và `desc` (một dòng giải thích).
- Một khối = MỘT câu hỏi. Không có chọn nhiều đáp án. Luôn có sẵn lối gõ tay nên KHÔNG
  cần thêm lựa chọn kiểu "Khác".
- **Vẫn phải viết câu hỏi thành lời** trong phần trả lời. Khối chỉ là nút bấm cho nhanh,
  không thay câu nói - kênh Telegram sẽ hạ nó xuống danh sách đánh số.
- Dùng ĐÚNG lúc bí thật: phải đoán một tham số mà đoán sai thì hại (kỳ thời gian, chọn
  shop nào, chọn kênh nào). KHÔNG dùng khối này để hỏi han lịch sự hay xin xác nhận vặt.
  Luật ở trên vẫn nguyên giá trị: đoán được thì cứ đoán rồi nêu giả định, đừng hỏi.
- Khối này sống chung được với `JAVIS_METRICS`, nhúng cả hai cùng lúc cũng không sao.
```

- [ ] **Step 2: Kiểm tra đầu cuối bằng tay**

Bật app, mở dashboard, hỏi một câu cố tình mơ hồ để Jarvis 007 phải hỏi lại:

```
Báo cáo doanh thu cho anh
```

Expected: Jarvis 007 nhận ra thiếu kỳ thời gian, viết câu hỏi thành lời trong câu trả lời, và hiện hàng chip lựa chọn kỳ ở dưới. Bấm một chip thì nó gửi đi và Jarvis 007 báo cáo đúng kỳ đó.

Nếu Jarvis 007 trả lời mà không có chip, đó là chuyện bình thường chứ không phải lỗi: luật prompt nói rõ đoán được thì đừng hỏi. Thử câu mơ hồ hơn hoặc kiểm tra brain đang chạy có nạp `CLAUDE.md` gốc không.

- [ ] **Step 3: Bump VERSION**

Sửa `VERSION` từ `0.9.60` thành `0.9.61`.

- [ ] **Step 4: Ghi CHANGELOG**

Thêm mục mới lên ĐẦU phần nội dung của `CHANGELOG.md`, theo đúng khuôn các mục đã có trong file (mở file ra xem mục `0.9.60` rồi bắt chước y hệt cách trình bày):

```markdown
## 0.9.61 - Khối hỏi-lại có lựa chọn trong khung chat

- Jarvis 007 hỏi lại được bằng nút bấm ngay trong chat, kiểu Claude Code: nhúng khối ẩn
  `JAVIS_ASK` ở cuối câu trả lời, dashboard vẽ thành hàng chip dưới bong bóng. Bấm một
  nút là gửi đi như gõ tay, cùng phiên. Chỉ tin nhắn cuối mới bấm được; cuộn lên lịch sử
  thì chip đã đông cứng.
- Chạy trên MỌI engine (Claude Agent SDK, Codex CLI, các engine API) vì chỉ dựa vào
  system prompt, không đụng MCP hub.
- Fix: khối `JAVIS_METRICS` trước đây lọt nguyên xi sang Telegram. Nay mọi khối điều
  khiển đều bị bóc trước khi ra kênh chữ; riêng `JAVIS_ASK` hạ xuống danh sách đánh số
  để nhắn lại "1" là chọn.
```

- [ ] **Step 5: Commit và đẩy lên GitHub**

Anh Quy đã dặn: xong và test OK thì tự bump, commit, push thẳng `origin/main`, không hỏi lại.

```bash
git add CLAUDE.md VERSION CHANGELOG.md
git commit -m "feat(chat): hỏi lại bằng nút bấm kiểu Claude Code (v0.9.61)"
git push origin main
```

---

## Ghi chú cho người triển khai

**Vì sao không làm tool thật `javis_ask_user` qua MCP hub.** Đó là cách Claude Code làm thật và nó cho phép hỏi GIỮA CHỪNG lúc đang làm dở việc. Đã cân nhắc và loại: hub là HTTP nên phải nhét session vào header config MCP cho từng lượt (file config đang cache theo mode chứ không theo phiên), phải lo timeout, lo người dùng F5 giữa lúc server đang treo chờ, và phải làm ba lần cho ba đường engine. Trong khi ở khung chat Jarvis 007 gần như mọi câu hỏi lại đều rơi vào cuối lượt. Nếu sau này cần hỏi giữa chừng thật thì đắp hướng tool lên trên vẫn được: `JavisAsk.render()` dùng lại nguyên, chỉ thay nguồn phát câu hỏi từ `data.type === "response"` sang một sự kiện WebSocket mới.

**Vì sao chip không nằm ngoài `.bubble`.** `.msg-javis` là flex-row chứa `.bubble` và nút copy (`style.css:401`). Nhét chip làm con thứ ba của nó thì chip sẽ nằm bên PHẢI bong bóng. Nên `render()` gắn chip vào trong `.bubble`.

**Vì sao `render()` phải gọi SAU khi gán `innerHTML`.** Nhánh `response` của `app.js` gán đè `bubble.innerHTML` bằng bản markdown cuối cùng. Gọi `render()` trước dòng đó thì chip bị xoá sạch ngay.

**Vì sao chip không nhấp nháy lúc stream.** `chat-render.js:246` đã nuốt mọi HTML comment, kể cả comment CHƯA ĐÓNG ở cuối chuỗi. Không cần làm gì thêm.

Spec gốc: `docs/superpowers/specs/2026-07-16-javis-ask-block-design.md`.
