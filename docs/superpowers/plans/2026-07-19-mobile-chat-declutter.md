# Gọn khung chat trên điện thoại - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trên điện thoại, ô nhập chat nở to và màn hình bớt rối (bỏ 2 hàng điều khiển chật), theo hướng chat-là-chính đã duyệt.

**Architecture:** Chỉ thêm rule CSS trong `@media (max-width: 860px)` + ít JS thuần, KHÔNG đụng bản desktop. Tái dùng thành phần sẵn có: bảng chọn model `#mbPop` (event-delegation ở `model-picker.js`), rail nav, nút reset `#resetBtn`. Ba khối: (1) ô nhập thành viên pill lớn; (2) rail thành ngăn kéo trượt trái + header mảnh ☰/model/＋; (3) dời nút hệ thống vào ngăn kéo.

**Tech Stack:** HTML tĩnh + CSS (`style.css`, `console.css`) + JS thuần (`app.js`/`console.js`), Alpine (rail store). Không build step. Font Tabler không dùng (đây là app riêng, giữ SVG sẵn có).

## Global Constraints

- CHỈ sửa giao diện màn hẹp: mọi rule mới nằm trong `@media (max-width: 860px)`. Bản >860px (desktop) GIỮ NGUYÊN.
- Mốc mobile = `max-width: 860px` (khớp `isNarrow()` ở `console.js:130` và block rail mobile `console.css:324`).
- Không dùng ký tự em dash (U+2014). Chuỗi hiển thị tiếng Việt có dấu.
- Tái dùng, không nhân bản: chip model = chính nút `#mbOpen`; ＋ = gọi lại `#resetBtn`.
- `#chatInput` giữ `font-size: 16px` (chống iOS tự zoom khi focus).
- Không có khung test UI tự động: JS đổi thì chạy `node --check <file>`; đúng/sai bố cục kiểm bằng smoke ở bề ngang mobile.
- Bump `?v=` của asset dashboard ở bước cuối để trình duyệt nạp bản mới.

---

## File Structure

- `dashboard/style.css` - CSS `.hud-voice`/`.voice-input`/`.mic-big`/`.send-btn` (định nghĩa gốc ~486-525) + thêm block mobile cho viên pill.
- `dashboard/console.css` - block `@media (max-width: 860px)` (~324-354) đang biến rail thành thanh đáy; sửa thành ngăn kéo + thêm rule header mobile + ẩn sysbar/model-bar.
- `dashboard/index.html` - thêm nút `#navToggle` (☰) + `#newChatBtn` (＋) vào `.hud-top` (mobile-only) + 1 lớp backdrop `#navBackdrop`.
- `dashboard/app.js` hoặc `dashboard/console.js` - wiring ☰ (bật/tắt `body.nav-open` + backdrop + Esc), dời `#mbOpen`/`#mbPop` vào header ở mobile theo `matchMedia`.
- Asset version bump: nơi index.html nạp css/js có `?v=` (tìm ở bước cuối).

---

## Task 1: Ô nhập thành viên pill lớn (mobile)

Đây là phần sửa "ô nhập bé" - giá trị cao nhất, rủi ro thấp nhất, làm trước.

**Files:**
- Modify: `dashboard/style.css` (thêm block mobile sau các rule `.hud-voice` ~525)

**Interfaces:**
- Consumes: cấu trúc `.hud-voice` sẵn có (index.html:285-311): `.mic-big#voiceBtn`, `.attach-btn#attachBtn`, `.attach-btn.tts-bar-btn#ttsToggleBar`, `.voice-input#chatInput`, `.stop-btn#stopBtn`, `.send-btn#sendBtn`.
- Produces: bố cục pill ở mobile (không đổi API JS).

- [ ] **Step 1: Thêm block CSS mobile cho pill**

Trong `dashboard/style.css`, thêm (sau khối `.send-btn` ~525):

```css
/* ===== Mobile: ô nhập thành viên pill lớn (chat-là-chính) ===== */
@media (max-width: 860px) {
  .hud-voice {
    margin: 6px 10px 8px; padding: 5px 6px 5px 8px; gap: 4px;
    border: 1px solid var(--border); border-radius: 24px; background: var(--bg2);
    border-top: 1px solid var(--border);           /* ghi đè border-top gốc cho đồng nhất */
    align-items: flex-end;
  }
  #ttsToggleBar { display: none; }                 /* loa dời vào ngăn kéo (Task 3) */
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

- [ ] **Step 2: Smoke bố cục pill**

Mở `dashboard/index.html` qua app ở bề ngang ~375px (trình duyệt thu nhỏ hoặc devtools mobile). Xác nhận: `.hud-voice` là MỘT viên bo tròn; thứ tự trong viên là ＋ (đính kèm) | ô gõ rộng | mic | gửi; KHÔNG còn nút loa; ô gõ chiếm gần hết bề ngang và cao lên khi gõ nhiều dòng; không tràn ngang. Trên desktop (>860px) `.hud-voice` KHÔNG đổi (vẫn hàng nút cũ). Tinh chỉnh số (padding/min-height) tại đây nếu lệch.

- [ ] **Step 3: Commit**

```bash
git add dashboard/style.css
git commit -m "feat(mobile): o nhap chat thanh vien pill lon (attach|input|mic|send)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Header mảnh (☰ + chip model + ＋) và ẩn hàng chật

**Files:**
- Modify: `dashboard/index.html` (thêm `#navToggle`, `#newChatBtn` vào `.hud-top`; thêm `#navBackdrop`)
- Modify: `dashboard/console.css` (rule mobile: hiện ☰/＋, ẩn cụm hud-top cũ + sysbar + model-bar)
- Modify: `dashboard/app.js` hoặc `dashboard/console.js` (dời `#mbOpen`/`#mbPop` vào header ở mobile; ＋ gọi reset)
- Test: `node --check` file JS đã sửa

**Interfaces:**
- Consumes: `.hud-top`, `.hud-top-left`, `.hud-top-right` (index.html:19-71); `#mbOpen`/`#mbPop` (index.html:263,270); `#resetBtn` (index.html:64); `isNarrow()` (console.js:130).
- Produces: `#navToggle` (mở ngăn kéo - Task 3 dùng), `#newChatBtn`, `#navBackdrop`; hàm JS `syncModelChipPlacement()`.

- [ ] **Step 1: Thêm nút ☰ và ＋ vào header + backdrop**

Trong `dashboard/index.html`, ngay sau thẻ mở `<header class="hud-top">` (dòng 19), thêm nút ☰ (mobile-only):

```html
      <button class="hud-icon-btn nav-toggle-btn" id="navToggle" title="Menu" aria-label="Mở menu">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>
        </svg>
      </button>
```

Trong `.hud-top-right` (sau nút `#resetBtn`, trước `</div>` đóng `.hud-actions` ~68), thêm nút ＋ mobile-only:

```html
          <button class="hud-icon-btn new-chat-btn" id="newChatBtn" title="Hội thoại mới" aria-label="Hội thoại mới">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
```

Ngay TRƯỚC `</div>` đóng thẻ `.hud` (tìm thẻ đóng của khung `.hud`, cùng cấp `.hud-top`), thêm lớp backdrop:

```html
    <div class="nav-backdrop" id="navBackdrop" hidden></div>
```

- [ ] **Step 2: CSS mobile - hiện ☰/＋, ẩn cụm cũ + sysbar + model-bar**

Trong `dashboard/console.css`, thêm vào block `@media (max-width: 860px)` (trong khối bắt đầu ~324):

```css
  .nav-toggle-btn { display: inline-flex; }
  .new-chat-btn { display: inline-flex; }
  /* Header mobile chỉ giữ: ☰ (trái) · chip model (giữa) · ＋ (phải). Ẩn phần rườm rà. */
  .hud-top .brand, .hud-top .navbar-brain,
  .hud-top #themeToggle, .hud-top #studioOpenBtn,
  .hud-top #settingsBtn, .hud-top #ttsToggle, .hud-top #resetBtn { display: none; }
  .hud-center-title { font-size: 13px; }
  .sysbar { display: none; }                       /* dải HỆ THỐNG/MCP ẩn ở mobile */
  .model-bar { display: none; }                    /* hàng model gốc ẩn; chip dời lên header (JS) */
  /* Chip model khi đã nằm trong header */
  .hud-top #mbOpen { display: inline-flex; }
```

Ngoài block mobile, thêm mặc định ẩn cho 2 nút mới (desktop không thấy):

```css
.nav-toggle-btn, .new-chat-btn { display: none; }
```

- [ ] **Step 3: JS - dời chip model vào header ở mobile + ＋ gọi reset**

Xác định file wiring: `grep -n "resetBtn\|mbOpen" dashboard/app.js dashboard/console.js`. Thêm đoạn sau vào file phù hợp (nơi các nút DOM khác được bind; nếu chưa rõ, đặt trong `dashboard/app.js` phần khởi tạo DOM):

```javascript
  // ===== Mobile: dời chip model lên header, ẩn khi desktop =====
  (function mobileHeaderSetup() {
    const mq = window.matchMedia("(max-width: 860px)");
    const mbOpen = document.getElementById("mbOpen");
    const mbPop = document.getElementById("mbPop");
    const modelBar = document.getElementById("modelBar");
    const headerCenter = document.querySelector(".hud-center-title");
    const headerRoot = document.querySelector(".hud-top");
    function place() {
      if (!mbOpen || !modelBar || !headerRoot) return;
      if (mq.matches) {                                  // mobile: chip + popover vào giữa header
        if (headerCenter && mbOpen.parentElement !== headerRoot) {
          headerRoot.insertBefore(mbOpen, headerCenter.nextSibling);
          if (mbPop) headerRoot.insertBefore(mbPop, mbOpen.nextSibling);
        }
      } else {                                           // desktop: trả về model-bar
        if (mbOpen.parentElement !== modelBar) {
          modelBar.insertBefore(mbOpen, modelBar.firstChild);
          if (mbPop) modelBar.insertBefore(mbPop, mbOpen.nextSibling);
        }
      }
    }
    place();
    mq.addEventListener ? mq.addEventListener("change", place) : mq.addListener(place);
  })();

  // ===== Mobile: nút ＋ = hội thoại mới (dùng lại reset) =====
  const _newChat = document.getElementById("newChatBtn");
  const _reset = document.getElementById("resetBtn");
  if (_newChat && _reset) _newChat.addEventListener("click", () => _reset.click());
```

Ghi chú: `#mbOpen` bind bằng event delegation ở `model-picker.js:89` (`e.target.closest("#mbOpen")`) nên dời DOM vẫn bấm được. `#mbPop` là `position:absolute` nên phải nằm trong offset-parent có `position:relative` - `.hud-top` cần `position: relative` (thêm ở Step 4 nếu chưa có).

- [ ] **Step 4: CSS - popover model mở XUỐNG dưới header ở mobile**

Trong `dashboard/console.css` block mobile, thêm (mb-pop gốc mở LÊN `bottom: calc(100%+6px)`, ở header phải lật xuống):

```css
  .hud-top { position: relative; }
  .hud-top #mbPop { bottom: auto; top: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    width: min(340px, 92vw); }
```

- [ ] **Step 5: node --check + smoke**

Run: `node --check dashboard/app.js` (và/hoặc `dashboard/console.js` nếu sửa ở đó)
Expected: không lỗi cú pháp.

Smoke ở ~375px: header chỉ còn ☰ (trái) · chip "Jarvis 007 · model ▾" (giữa) · ＋ (phải); KHÔNG còn hàng model-bar và dải HỆ THỐNG ở dưới; bấm chip model mở bảng chọn NGAY DƯỚI header (không bị cắt trên); bấm ＋ reset hội thoại. Desktop (>860px): header + model-bar y như cũ, chip model nằm lại chỗ cũ.

- [ ] **Step 6: Commit**

```bash
git add dashboard/index.html dashboard/console.css dashboard/app.js dashboard/console.js
git commit -m "feat(mobile): header manh ☰ + chip model + ＋; an sysbar/model-bar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Rail thành ngăn kéo trượt trái + dời nút hệ thống vào ngăn kéo

**Files:**
- Modify: `dashboard/console.css` (rail mobile: từ thanh đáy -> ngăn kéo trượt trái + backdrop)
- Modify: `dashboard/app.js`/`dashboard/console.js` (☰ bật/tắt `body.nav-open`; backdrop/Esc/chọn mục đóng)
- Modify: `dashboard/index.html` (thêm mục "Hệ thống" vào rail: bật/tắt loa, cài đặt, đổi tông, Studio, reset) - hoặc để nguyên rail-nav và chỉ hiện lại rail-top/foot
- Test: `node --check`

**Interfaces:**
- Consumes: `#navToggle`, `#navBackdrop` (Task 2); `.rail`, `.rail-nav`, `.rail-top`, `.rail-foot` (index.html:315-351); block rail mobile hiện có (console.css:324-338).
- Produces: hành vi ngăn kéo (`body.nav-open`).

- [ ] **Step 1: CSS - rail thành ngăn kéo trượt trái (thay thanh đáy)**

Trong `dashboard/console.css`, THAY các rule rail trong block `@media (max-width: 860px)` (hiện đặt rail ở đáy, ~326-338) bằng:

```css
  .rail {
    top: 0; left: 0; bottom: 0; right: auto; width: min(280px, 82vw); height: 100vh;
    flex-direction: column; padding: 10px 8px; gap: 4px;
    border-top: 0; border-right: 1px solid var(--glass-brd);
    transform: translateX(-100%); transition: transform .22s ease; z-index: 60;
    overflow-y: auto;
  }
  body.nav-open .rail { transform: translateX(0); box-shadow: 8px 0 40px rgba(0,0,0,.5); }
  .rail-top, .rail-foot { display: flex; }          /* hiện lại brand + version trong ngăn kéo */
  .rail-nav { flex-direction: column; overflow-x: hidden; overflow-y: auto; gap: 2px; }
  .rail-group, .rail-grp-items { display: block; }  /* trả lại nhóm dạng dọc */
  .rail-grp-lbl { display: flex; }
  .rail-item { flex: none; flex-direction: row; gap: 10px; padding: 9px 10px; }
  .rail-item .rail-lbl { font-size: 13px; }
  /* backdrop */
  .nav-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 55; }
  .nav-backdrop[hidden] { display: none; }
  body.nav-open .nav-backdrop { display: block; }
  /* body không còn chừa 56px đáy cho rail nữa */
  body.has-rail .hud { margin-left: 0; width: 100%; height: 100vh; }
  .cview { left: 0; bottom: 0; }
  .hud { grid-template-rows: 46px 1fr auto; }        /* voice tự cao theo pill, bỏ 62px cứng */
```

- [ ] **Step 2: JS - ☰ bật/tắt ngăn kéo, đóng bằng backdrop/Esc/chọn mục**

Thêm vào file wiring (cạnh đoạn Task 2):

```javascript
  // ===== Mobile: ngăn kéo điều hướng =====
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
    if (rail) rail.addEventListener("click", (e) => {           // chọn một mục nav -> đóng
      if (e.target.closest(".rail-item") && window.matchMedia("(max-width: 860px)").matches) close();
    });
  })();
```

- [ ] **Step 3: (tuỳ chọn) Dời nút hệ thống vào ngăn kéo**

Nếu muốn các nút header cũ (bật/tắt loa `#ttsToggle`, Cài đặt `#settingsBtn`, Đổi tông `#themeToggle`, Studio `#studioOpenBtn`, chọn brain) truy cập được trên mobile: thêm một khối "Hệ thống" vào cuối `.rail` trong index.html (mobile-only hiện). Cách gọn nhất KHÔNG nhân bản handler: thêm các nút mobile-only trong rail mà click ủy quyền sang nút gốc, ví dụ:

```html
      <div class="rail-sys only-mobile">
        <button class="rail-item" onclick="document.getElementById('themeToggle').click()"><span class="rail-lbl">Đổi tông</span></button>
        <button class="rail-item" onclick="document.getElementById('settingsBtn').click()"><span class="rail-lbl">Cài đặt</span></button>
        <button class="rail-item" onclick="document.getElementById('studioOpenBtn').click()"><span class="rail-lbl">Studio</span></button>
        <button class="rail-item" onclick="document.getElementById('ttsToggle').click()"><span class="rail-lbl">Bật/tắt loa</span></button>
      </div>
```

CSS: `.only-mobile { display: none; } @media (max-width:860px){ .only-mobile { display: block; } }`. (Nếu thấy chưa cần trên mobile thì bỏ qua Step này - YAGNI.)

- [ ] **Step 4: node --check + smoke**

Run: `node --check dashboard/app.js` (và console.js nếu sửa)
Expected: không lỗi.

Smoke ~375px: KHÔNG còn thanh nav ở đáy; bấm ☰ -> ngăn kéo trượt từ trái + nền mờ; bấm nền mờ / Esc / chọn một mục -> đóng; danh sách công cụ hiện dạng dọc dễ bấm; đáy màn hình giờ chỉ còn viên nhập. Desktop (>860px): rail vẫn là cột trái cũ, ☰ không hiện, không có backdrop.

- [ ] **Step 5: Commit**

```bash
git add dashboard/console.css dashboard/app.js dashboard/console.js dashboard/index.html
git commit -m "feat(mobile): rail thanh ngan keo truot trai + ☰ mo/dong, bo thanh nav day

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Bump asset + smoke tổng + push

**Files:**
- Modify: `dashboard/index.html` (bump `?v=` các asset dashboard)
- Modify: `VERSION`, `CHANGELOG.md`

**Interfaces:**
- Consumes: mọi task trên.

- [ ] **Step 1: Bump ?v= của css/js dashboard**

`grep -n "?v=" dashboard/index.html` -> tăng số version của các asset đã sửa (style.css, console.css, app.js/console.js) để trình duyệt nạp bản mới. Nếu không có `?v=` thì bỏ qua (index.html đổi là trình duyệt tự nạp).

- [ ] **Step 2: Smoke tổng ở mobile + desktop**

Ở ~375px: header 3 nút gọn, ô nhập pill to, ngăn kéo chạy, không hàng chật. Ở >900px: mọi thứ y như trước khi sửa (không regression desktop).

- [ ] **Step 3: Bump VERSION + CHANGELOG**

Lấy VERSION kế tiếp (đọc `cat VERSION`, tăng patch). Thêm mục CHANGELOG:

```markdown
## [x.y.z] - 2026-07-19
Giao diện chat trên điện thoại gọn hẳn: ô nhập thành viên bo tròn lớn, header chỉ còn menu ☰ + chip model + nút hội thoại mới, dãy công cụ chuyển thành ngăn kéo trượt. Chỉ đổi bản điện thoại (màn hẹp), bản máy tính giữ nguyên. Tải lại trang là thấy (đã bump ?v).
### Cải thiện
- **Khung chat điện thoại**: ô nhập nở to (viên pill: đính kèm | ô gõ | mic | gửi), bỏ 2 hàng điều khiển chật (dải HỆ THỐNG và thanh nav đáy), gom công cụ + nút hệ thống vào menu ☰; chip model dời lên header, bấm mở đúng bảng chọn cũ.
```

- [ ] **Step 4: Commit + push**

```bash
git add dashboard/index.html VERSION CHANGELOG.md
git commit -m "chore(release): x.y.z - gon khung chat dien thoai

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git fetch origin && git rebase origin/main
git push origin main
```

- [ ] **Step 5: Xác minh sau push**

Đợi CI build image, rồi trên điện thoại (bản Hostinger) bấm nút Cập nhật ngay (đã bật Watchtower) hoặc chờ, mở lại trang kiểm giao diện mobile thực tế.

---

## Self-Review (đã rà)

**Spec coverage:**
- Khối 1 ô nhập pill -> Task 1. ✓
- Khối 2 header mảnh (☰/chip model/＋) + ẩn sysbar/model-bar + chip model dời lên header (JS, popover lật xuống) -> Task 2. ✓
- Khối 2 ngăn kéo trượt trái thay thanh đáy -> Task 3. ✓
- Khối 2 nút hệ thống vào ngăn kéo -> Task 3 Step 3 (tuỳ chọn). ✓
- Khối 3 loa ẩn ở bar -> Task 1 (`#ttsToggleBar` display:none). ✓
- Mobile-only, desktop giữ nguyên -> mọi rule trong @media 860px; nút mới mặc định display:none. ✓
- Bump ?v= + release -> Task 4. ✓

**Placeholder scan:** không có TBD/TODO; mỗi step có code/lệnh thật. Task 3 Step 3 gắn nhãn tuỳ chọn (YAGNI) rõ ràng, không phải placeholder.

**Type/tên nhất quán:** id nhất quán giữa các task - `#navToggle`, `#newChatBtn`, `#navBackdrop`, `body.nav-open`, `#mbOpen`/`#mbPop`, `.hud-voice`/`.voice-input`/`.mic-big`/`.send-btn`/`.attach-btn#ttsToggleBar`. Mốc `860px` dùng thống nhất.

**Lưu ý thực thi:** đây là việc CSS trực quan - số pixel là điểm khởi đầu, bước smoke của mỗi task là nơi tinh chỉnh. Vì không có test tự động, smoke ở bề ngang mobile là cửa kiểm chính; nếu chạy bằng subagent, subagent nên chụp màn hình qua công cụ Browser ở viewport mobile để tự kiểm, hoặc để người dùng kiểm trên điện thoại.
