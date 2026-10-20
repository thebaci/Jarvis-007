# Giai đoạn 1: Xoá Lịch giả, gộp về một trang "Việc" - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xoá registry Lịch (không executor nào đọc nó), bịt lỗ `bypassPermissions` của `/automations/sync`, và gộp loop + nhắc hẹn về một trang "Việc" duy nhất.

**Architecture:** Thuần xoá + đổi tên, **không thêm endpoint nào**. `automations.json` chưa từng được scheduler đọc (`main.py:3613-3656` không có nhánh nào), và 0 file `automations.json` tồn tại trên cả 4 brain, nên phía dữ liệu user không có gì để migrate.

Điểm mấu chốt (tìm ra ở pre-flight, đã sửa plan theo): `_loops_as_routines` (`main.py:3169`) và `pending_as_automations` (`reminders.py:278`) **không phải helper dùng chung** - chúng là **lớp chiếu vào hình dạng Lịch giả**, và caller duy nhất của cả hai là `main.py:3199`, tức chính `/automations` GET sắp xoá. Lịch chết thì chúng chết theo. Trang Việc dùng thẳng **endpoint thật đã có sẵn**: loop từ `GET /loops` (`console.js:812` đang dùng), nhắc hẹn từ `GET /reminders` (`reminders.py:498`, trả `{pending, history, counts}` với `_view()` giàu hơn bản chiếu) và huỷ qua `POST /reminders/cancel` (`reminders.py:551`). Bản nháp plan đầu đã bịa ra một lớp API `/jobs` mới chỉ để bảo tồn lớp chiếu vốn chỉ tồn tại vì cái giả - đó là YAGNI, đã bỏ.

Vẫn giữ nguyên yêu cầu: xoá rail Lịch mà không gộp nhắc hẹn vào trang Việc = user **mất chỗ nhìn nhắc hẹn**, vì hiện chúng chỉ hiện ở tab Lịch.

**Tech Stack:** Python 3.12, FastAPI, vanilla JS (dashboard), test script thuần (không pytest).

Spec: `docs/superpowers/specs/2026-07-17-hop-nhat-viec-dinh-ky-design.md`

## Global Constraints

- **TUYỆT ĐỐI không dùng ký tự em dash (U+2014)** trong bất kỳ file nào: code, comment, test, doc, commit message. Dùng "-" hoặc viết lại câu. (CLAUDE.md, nguyên tắc 8.)
- Tiếng Việt là ngôn ngữ chính cho comment, docstring, tên hiển thị, thông báo lỗi.
- Test là **script thuần, không pytest**. Quy ước nhà: `server/test_*.py`, có `def check(name, cond)`, gom `_fails`, `sys.exit(1)` khi có lỗi. CI chạy `for f in test_*.py; do python "$f"; done` (`.github/workflows/ci.yml:35-37`), nên mọi file `server/test_*.py` tự động vào CI.
- Chạy test bằng venv: `.venv/Scripts/python.exe` (python hệ thống thiếu lib).
- Test phải tự cô lập: `os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="..."))` **trước** khi import module Jarvis 007.
- **Helper của `dashboard/console.js`** (dùng cho Task 2): chỉ có `esc(s)` (`:116`) và `fbrain()` (`:363`), gọi HTTP bằng `fetch()` trần với `FormData` dựng tại chỗ. **KHÔNG** có `api()`, `fd()`, `brain()` - đó là helper của `studio.js`, không dùng được ở console.js.
- Không chạm `Javis/loops/*.md`, `loop-state.json`, hay `system_sync.LEGACY_HASHES` trong giai đoạn này. Loop giữ nguyên hành vi.
- Không sửa `self_improve.py:105-113` (`_isolate`). Nó là nhánh chết trong production (`main.py:3029` luôn inject `apply_mcp`) nhưng `test_loop_ambient.py` đang dựa vào nó.

## File Structure

| File | Trách nhiệm sau giai đoạn 1 |
|---|---|
| `server/main.py` | Bỏ 5 route `/automations*`, 3 helper registry, lớp chiếu `_loops_as_routines`, khối caps. **Không thêm endpoint nào.** |
| `server/reminders.py` | Bỏ lớp chiếu `pending_as_automations` (caller duy nhất là `/automations` GET). Phần còn lại nguyên vẹn. |
| `server/test_jobs.py` | **Mới.** Phủ: route + helper + lớp chiếu đã chết, caps sạch và còn chạy, và các endpoint THẬT mà trang Việc dựa vào (`/loops`, `/reminders`, `/reminders/cancel`) vẫn còn. |
| `dashboard/studio.js` | Bỏ page `automations` (loader, form `editAutomation`, nút sync). |
| `dashboard/console.js` | Bỏ rail `automations`. Rail `selfimprove` đổi nhãn "Loop" → "Việc", render thêm khối nhắc hẹn, sửa copy trỏ tới tab Lịch. |
| `dashboard/index.html` | Chỉ bỏ panel loop cũ đã chết (`:160-192`, Task 3). **Không** có `panel-automations` ở đây - nó do `console.js:222` dựng động từ `STUDIO_PAGES`. |
| `dashboard/app.js` | Bỏ fetch `/loop/config` của panel chết (`:1497`). |

**Ghi chú decomposition:** khối registry + khối caps **phải cùng một task**. `_gather_capabilities` (`main.py:3352`) gọi `_read_automations`; xoá helper mà để lại lời gọi thì `rebuild_javis_index` ném `NameError` **mỗi tick scheduler** (`main.py:3650-3651`). Reviewer không thể duyệt cái này mà từ chối cái kia, nên chúng là một deliverable.

---

### Task 1: Xoá registry Lịch + sync + hai lớp chiếu + khối caps (xoá thuần)

**Files:**
- Modify: `server/main.py:3140-3262` (xoá `_automations_path`/`_read_automations`/`_write_automations`, `_loops_as_routines`, và CẢ 5 route `/automations*` gồm `/automations/sync` ở `:3264-3313`)
- Modify: `server/main.py:3324, 3352-3354, 3411-3413` (xoá khối caps chết)
- Modify: `server/reminders.py:278-296` (xoá `pending_as_automations`)
- Test: `server/test_jobs.py` (tạo mới)

**Interfaces:**
- Consumes: không. Đây là task **xoá thuần, không thêm endpoint nào**.
- Produces: `_gather_capabilities(brain)` trả dict **không còn** key `"automations"`. Task 2 (UI) **không** tiêu thụ gì từ task này - nó dùng các endpoint thật đã có sẵn: `GET /loops`, `GET /reminders`, `POST /reminders/cancel`.

**Vì sao xoá cả hai lớp chiếu:** `grep -rn "_loops_as_routines\|pending_as_automations" server/` cho thấy caller **duy nhất** của cả hai là `main.py:3199` (`/automations` GET). Chúng là bản chiếu loop/nhắc hẹn vào hình dạng dòng-Lịch (`{id: "__loop__:<slug>", schedule: "mỗi N phút", ...}`), trong đó chuỗi `schedule` là **bịa ra lúc GET** (`main.py:3187`). Hết Lịch thì hết lý do tồn tại. Giữ lại = code chết.

**GỘP TASK 2 VÀO ĐÂY (sửa lúc chạy, 2026-07-17):** bản plan trước tách `/automations/sync` thành Task 2 riêng với lý do "reviewer có thể từ chối phần này mà vẫn duyệt Task 1". Lý do đó SAI: `automations_sync` (`:3264-3313`) đọc/ghi chính `automations.json` (`:3299`, `:3308`), nên nó **không thể sống sót** khi registry bị xoá. Hai task chưa bao giờ độc lập, và assert `not any(p.startswith("/automations"))` của Task 1 sẽ FAIL nếu sync còn sống. Xoá cả 5 endpoint trong một task.

Muốn giữ tính năng đồng bộ routine claude.ai thì phải **viết lại** (nút riêng ở trang Model, có `allowed_tools`), không có đường giữ nguyên trạng - vì cái kho nó ghi vào đã biến mất.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_jobs.py`:

```python
"""Test: registry Lịch giả đã xoá sạch, nguồn thật của trang Việc còn nguyên. Chạy tay / CI:

    cd server && python test_jobs.py

Bối cảnh: automations.json CHƯA TỪNG có executor - _scheduler_loop (main.py:3613-3656) không
có nhánh nào đọc nó, và 0 file automations.json tồn tại trên cả 4 brain. Giai đoạn 1 xoá nó,
KHÔNG thêm endpoint nào: trang Việc dùng thẳng /loops + /reminders đã có sẵn.

Phủ:
- 4 path /automations* đã biến mất khỏi app.routes.
- 3 helper registry + 2 lớp chiếu đã xoá (caller duy nhất của chúng là /automations GET).
- caps: key 'automations' đã xoá, và _gather_capabilities/_render_javis_index còn chạy được
  (nếu xoá helper mà để lại lời gọi thì rebuild_javis_index NameError MỖI tick scheduler).
- Các endpoint THẬT mà trang Việc dựa vào vẫn còn sống.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-jobstest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


src = (Path(__file__).parent / "main.py").read_text(encoding="utf-8")
paths = {getattr(r, "path", "") for r in main.app.routes}

# ---- 1. Route Lịch đã chết ----
check("route: mọi /automations* đã xoá", not any(p.startswith("/automations") for p in paths))

# ---- 2. Helper registry đã xoá hẳn (không còn đường ghi automations.json) ----
check("helper: _read_automations đã xoá", not hasattr(main, "_read_automations"))
check("helper: _write_automations đã xoá", not hasattr(main, "_write_automations"))
check("helper: _automations_path đã xoá", not hasattr(main, "_automations_path"))
# Assert CHÍNH XÁC vào biểu thức dựng đường dẫn, KHÔNG assert chuỗi trần "automations.json":
# main.py:121 có nhắc tên file đó trong một comment không liên quan (bàn về ghi file nguyên
# tử), và comment mới ở đầu khối cũng nhắc nó để giải thích vì sao đã xoá. Assert trần sẽ
# BẤT KHẢ THI dù code đã đúng.
check("nguồn: không còn code dựng đường dẫn tới automations.json",
      '"Jarvis 007" / "automations.json"' not in src)

# ---- 2b. Hai lớp chiếu vào hình dạng Lịch giả cũng chết theo ----
# Caller duy nhất của cả hai là /automations GET (main.py:3199). Chúng chiếu loop/nhắc hẹn
# vào dòng-Lịch với chuỗi schedule BỊA RA lúc GET (main.py:3187). Hết Lịch thì hết lý do.
check("chiếu: _loops_as_routines đã xoá", not hasattr(main, "_loops_as_routines"))
check("chiếu: pending_as_automations đã xoá",
      not hasattr(main.reminders_feature, "pending_as_automations"))

# ---- 3. caps sạch VÀ còn chạy được ----
# Đây là assert quan trọng nhất của task: xoá _read_automations mà để lại lời gọi ở
# _gather_capabilities:3352 → rebuild_javis_index (main.py:3650-3651) ném NameError mỗi tick.
caps = main._gather_capabilities("brain")
check("caps: không còn key 'automations'", "automations" not in caps)
check("caps: _gather_capabilities vẫn chạy (không NameError)", isinstance(caps, dict))
check("caps: _render_javis_index vẫn chạy", isinstance(main._render_javis_index(caps), str))
check("caps: index không còn mục 'Lịch (automations)'",
      "Lịch (automations)" not in main._render_javis_index(caps))

# ---- 4. Endpoint THẬT mà trang Việc dựa vào phải còn sống ----
# Xoá Lịch KHÔNG được kéo theo hai nguồn thật. Task 2 (UI) gọi đúng ba cái này; nếu task này
# xoá nhầm thì trang Việc trắng và test UI mới phát hiện - bắt ngay tại đây rẻ hơn nhiều.
check("route: GET /loops còn (trang Việc lấy loop từ đây)", "/loops" in paths)
check("route: GET /reminders còn (trang Việc lấy nhắc hẹn từ đây)", "/reminders" in paths)
check("route: POST /reminders/cancel còn (nút Huỷ nhắc hẹn)", "/reminders/cancel" in paths)


if _fails:
    print(f"\nFAIL - test_jobs: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_jobs: tất cả pass")
```

- [ ] **Step 2: Chạy test để xác nhận nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_jobs.py`

Expected: FAIL. Cụ thể: `route: mọi /automations* đã xoá` fail (4 path còn sống), ba assert `helper: *` fail, hai assert `chiếu: *` fail, `caps: không còn key 'automations'` fail. Bốn assert cuối (`route: GET /loops còn`, `/reminders`, `/reminders/cancel`) **phải PASS ngay từ đầu** - chúng khẳng định thứ đã có sẵn và không được xoá nhầm.

- [ ] **Step 3: Xoá 3 helper registry + lớp chiếu + 4 route cũ**

Trong `server/main.py`, xoá:
- Nguyên khối từ `def _automations_path(brain):` (`:3145`) tới hết `_write_automations` (`:3166`).
- Nguyên hàm `_loops_as_routines` (`:3169-3193`) - lớp chiếu, caller duy nhất là route sắp xoá.
- 4 route: `automations_list` (`:3196-3202`), `automations_save` (`:3205-3221`), `automations_toggle` (`:3224-3249`), `automations_delete` (`:3251-3261`).

Sửa comment đầu khối (`:3140-3144`) thành:

```python
# ============================================================
# Trang Việc = loop (việc bền, chạy engine theo chu kỳ) + nhắc hẹn (việc phù du, 1 lần).
# KHÔNG có registry tay và KHÔNG có endpoint gộp: dashboard đọc thẳng hai nguồn thật là
# GET /loops và GET /reminders. Tab Lịch cũ (5 route /automations*) đã xoá vì nó chưa từng
# có executor - _scheduler_loop không đọc nó. Xem spec 2026-07-17-hop-nhat-viec-dinh-ky.
# ============================================================
```

- [ ] **Step 4: Xoá lớp chiếu `pending_as_automations` trong reminders.py**

Trong `server/reminders.py`, xoá nguyên method `pending_as_automations` (`:278-296`, neo: `def pending_as_automations(self, brain: str) -> List[dict]:`).

Giữ nguyên mọi thứ khác trong file, đặc biệt là `cancel` (`:300`), `_view` (`:263`), và các route `/reminders*` (`:498+`) - trang Việc dựa vào chúng.

Kiểm tra `List` còn được dùng chỗ khác không trước khi động vào import:

Run: `cd /d/Project/Javis-OS && grep -c "List\[" server/reminders.py`

Nếu kết quả > 0 thì **giữ** `from typing import ... List`. Không xoá import đang có người dùng.

- [ ] **Step 5: Xoá khối caps chết (bắt buộc cùng task, xem ghi chú decomposition)**

Ba sửa trong `server/main.py`:

1. Dòng `:3324`, bỏ key `"automations"`:

```python
    caps = {"agents": [], "skills": [], "workflows": [], "loops": [], "plugins": []}
```

2. Xoá 3 dòng `:3352-3354`:

```python
    for a in _read_automations(brain):
        caps["automations"].append({"id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
            "schedule": a.get("schedule", ""), "status": a.get("status", "active")})
```

3. Xoá 4 dòng `:3411-3413`:

```python
    if caps["automations"]:
        L.append("\n## Lịch (automations)")
        for a in caps["automations"]:
            L.append(f"- **{a['name']}** - {a['type']} · {a['schedule']} · {a['status']}")
```

Ghi chú: khối này **không** rác vào system prompt. Nó đi vào `Javis/index.md` qua `rebuild_javis_index` (`main.py:3462`), và vì list luôn rỗng nên `if caps["automations"]:` luôn falsy → section chưa từng render. Đây là dọn code chết. `_javis_capability_summary` (`:3477`) không hề nhắc automations.

- [ ] **Step 6: Chạy test để xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_jobs.py`

Expected: PASS, in `OK - test_jobs: tất cả pass`.

- [ ] **Step 7: Xác nhận không còn ai gọi thứ đã xoá trong server/**

Run: `cd /d/Project/Javis-OS && grep -rn "/automations\|_read_automations\|_loops_as_routines\|pending_as_automations" server/ --include=*.py`

Expected: **0 hit** (trừ `server/test_jobs.py`, nơi chúng là chuỗi trong assert). Nếu còn hit code thật, xoá nốt trước khi commit.

- [ ] **Step 8: Commit**

```bash
git add server/main.py server/reminders.py server/test_jobs.py
git commit -m "refactor(jobs): xoa registry Lich gia + hai lop chieu cua no

automations.json chua tung co executor: _scheduler_loop (main.py:3613-3656)
khong co nhanh nao doc no, va 0 file automations.json ton tai tren ca 4 brain.

Xoa 3 helper registry + 4 route /automations* + khoi caps chet. Caps phai xoa
CUNG dot: _gather_capabilities:3352 goi _read_automations, de lai la NameError
moi tick scheduler.

Xoa luon _loops_as_routines + pending_as_automations: caller duy nhat cua ca hai
la /automations GET. Chung khong phai helper dung chung ma la lop CHIEU vao hinh
dang Lich gia (chuoi schedule 'moi N phut' bia ra luc GET, main.py:3187). Het
Lich thi het ly do ton tai.

KHONG them endpoint nao: trang Viec doc thang /loops + /reminders da co san.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Một trang "Việc" - xoá studio page Lịch, gộp nhắc hẹn vào rail selfimprove

**Files:**
- Modify: `dashboard/console.js:23, 46, 49, 64-65, 94, 97, 107` (rail + nhãn), `:683` (copy), `:708` (thêm host), `:809-826` (`loadLoops`: gọi render nhắc hẹn)
- Modify: `dashboard/studio.js` (xoá loader + form + nút sync) - **neo bằng tên hàm, KHÔNG bằng số dòng**, xem cảnh báo dưới
- Modify: `dashboard/index.html:113-116` (xoá ô thống kê ROUTINES) - **bổ sung lúc chạy**, xem dưới
- Modify: `dashboard/app.js` `loadBrainStats()` (xoá fetch `/automations` + `_setStat("statRoutines"...)`) - **bổ sung lúc chạy**

> **KHOẢNG HỞ PLAN BỎ SÓT (implementer Task 2 tìm ra, 2026-07-17):** plan chỉ grep `console.js`/`studio.js`/`index.html`, **chưa bao giờ grep `dashboard/app.js`**. Thực tế còn hai chỗ nữa:
> - `index.html:113` có `<button class="bstat" data-tab="automations">` nhãn **ROUTINES**, bấm vào gọi `openStudio("automations")` (`app.js:1211-1214`) - tab vừa xoá, nên thành nút chết.
> - `app.js:1201` trong `loadBrainStats()` vẫn `fetch('/automations?brain=')` để đếm số cho đúng ô đó. Route đã xoá ở Task 1 nên đây là 404 im lặng (bị `.catch(() => ({}))` nuốt), số ROUTINES vĩnh viễn = 0.
>
> Trớ trêu: ô ROUTINES chính là **badge nói dối** mà cả spec này sinh ra để giết (đếm "đang chạy" từ registry không chạy gì), mà plan lại bỏ sót nó. Quyết định: **xoá hẳn ô ROUTINES**, không thay bằng ô khác. Ba ô còn lại (AGENTS/SKILLS/WORKFLOWS) đều là studio page nên nhất quán; Việc là rail của console, không thuộc hàng đó nữa.
>
> Đính chính câu "KHÔNG đụng `dashboard/index.html`": nghĩa hẹp là đừng đi tìm `panel-automations` trong đó (nó không nằm ở đó) và đừng đụng panel loop chết `:160-192` (việc của Task 3). index.html KHÔNG bất khả xâm phạm.

> **CẢNH BÁO TRANH CHẤP (đọc trước khi sửa `studio.js`):** một phiên khác đang sửa `dashboard/studio.js` song song. Lúc soạn plan này, commit `0fcb34f` (không thuộc plan này) đã sửa `studio.js` + `index.html` + `VERSION` + `CHANGELOG.md`, và working tree còn `M dashboard/studio.js` (+43/-10 dòng, vùng dòng 211-273) chưa commit. **Mọi số dòng của `studio.js` trong plan này đã trôi và không đáng tin.** Trước khi sửa, chạy `git status` và `grep -n` để lấy vị trí thật. Nếu working tree còn sửa dở của người khác, hỏi trước khi commit đè.
>
> Vị trí đúng **tại thời điểm soát plan** (đã tự trôi so với bản nháp đầu): `loadAutomations` ở `:341` (nháp ghi 306), nút `/automations/sync` ở `:350` (nháp ghi 314), `editAutomation` ở `:395` (nháp ghi 358). Dùng `grep -n "function loadAutomations\|function editAutomation"` để lấy số hiện hành.
>
> `panel-automations` **không nằm trong `index.html`**. Nó do `console.js:222` dựng động (`el.innerHTML = '<div class="stab-panel" id="panel-${id}"></div>'`) từ `STUDIO_PAGES`. Bỏ `"automations"` khỏi `STUDIO_PAGES` (`:107`) là đủ. Hai file `dashboard/_wf_harness*.html` có chứa `panel-automations` nhưng chúng là harness test chưa track của phiên khác - **đừng đụng**.

**Interfaces:**
- Consumes: `GET /reminders?brain=` → `{"pending": [...], "history": [...], "counts": {...}}`, mỗi phần tử `pending` có `_view()` shape (`reminders.py:263`): `{id, text, label, mode, due_at, due_human, chat_id, repeat_min, cron, script, result, error}`. Và `POST /reminders/cancel` với form `{id, brain}` → `{ok, error}`. **Cả hai đã tồn tại sẵn**, Task 1 không tạo gì.
- Produces: không có API mới. Rail `automations` biến mất; rail `selfimprove` **giữ nguyên id** (không đổi id để khỏi vỡ deep-link/localStorage) nhưng đổi nhãn thành "Việc".

**Lưu ý `id`:** `_view()` trả `id` **thô** (không có tiền tố `__reminder__:` như bản chiếu cũ), và `POST /reminders/cancel` nhận đúng `id` thô đó. Đừng thêm/bóc tiền tố.

**Vì sao không xoá trơn rail Lịch:** nhắc hẹn **chỉ** hiện ở tab Lịch, qua `pending_as_automations` (`reminders.py:278`). Xoá rail mà không gộp = user mất chỗ nhìn nhắc hẹn đang chờ. Đây là hồi quy dễ lọt nhất của cả plan.

**Nhắc lại ràng buộc helper:** console.js **chỉ** có `esc()` (`:116`) và `fbrain()` (`:363`). Dùng `fetch()` trần + `FormData` dựng tại chỗ. `api()`/`fd()`/`brain()` là của studio.js, gọi ở đây sẽ `ReferenceError`.

- [ ] **Step 1: Chụp trạng thái trước + kiểm tra tranh chấp**

Run:

```bash
cd /d/Project/Javis-OS
git status --short dashboard/
grep -rc "automations" dashboard/console.js dashboard/studio.js dashboard/index.html
```

Ghi lại ba con số. Cuối task cả ba phải về **0**.

Nếu `git status` cho thấy `dashboard/studio.js` (hoặc file dashboard khác trong task này) đang có sửa chưa commit **không phải của mình**, DỪNG và hỏi người review. Một phiên khác đang làm việc trên chính file này.

- [ ] **Step 2: Xoá rail `automations` khỏi console.js**

Trong `dashboard/console.js`:

1. Xoá dòng `:49`: `{ id: "automations", icon: ICON.automations, label: "Lịch" },`
2. Xoá `ICON.automations` (`:23`).
3. Xoá entry `automations:` trong map mô tả (`:97`).
4. Bỏ `"automations"` khỏi `STUDIO_PAGES` (`:107`) - còn lại `["workflows", "agents", "skills"]`.
5. Sửa nhóm rail (`:64-65`):

```js
    { label: "Năng lực",    ids: ["agents", "skills", "workflows", "plugins"] },
    { label: "Việc",        ids: ["kanban", "selfimprove"] },
```

6. Sửa nhãn rail `selfimprove` (`:46`):

```js
    { id: "selfimprove", icon: ICON.selfimprove, label: "Việc" },
```

7. Sửa mô tả (`:94`):

```js
    selfimprove: { icon: "♻", label: "Việc", sub: "Việc định kỳ + nhắc hẹn đang chờ" },
```

- [ ] **Step 3: Sửa copy trỏ tới tab Lịch (dễ sót)**

`dashboard/console.js:683` hiện kết thúc bằng: `Loop bật sẽ hiện ở tab <b>Lịch</b>.` Tab đó sắp không tồn tại. Bỏ đúng câu cuối đó, giữ nguyên phần còn lại của đoạn văn.

Run kiểm chứng: `cd /d/Project/Javis-OS && grep -n "tab <b>Lịch</b>" dashboard/console.js`

Expected sau khi sửa: 0 hit.

- [ ] **Step 4: Thêm host cho khối nhắc hẹn**

`dashboard/console.js:708` hiện là `<div id="lpCards">Đang tải...</div>`. Thêm host ngay sau nó, trước `<div class="si-log">`:

```html
      <div id="lpCards">Đang tải...</div>
      <div id="lpReminders"></div>
```

- [ ] **Step 5: Viết `loadReminders` + gọi từ `loadLoops`**

Thêm hàm này vào `renderSelfImprove`, ngay trước `async function loadLoops()` (`:809`):

```js
    // Nhắc hẹn đang chờ: trước đây CHỈ hiện ở tab Lịch (đã xoá). Không gộp vào đây thì user
    // mất chỗ nhìn chúng. Loop = việc bền (.md, sửa trong Obsidian); nhắc = việc phù du.
    // Đọc thẳng /reminders (nguồn thật), KHÔNG qua lớp chiếu: lớp đó chỉ tồn tại vì tab Lịch.
    async function loadReminders() {
      if (myGen !== _renderGen) return;
      const box = el.querySelector("#lpReminders");
      if (!box) return;
      let d = { pending: [] };
      try { d = await (await fetch(`/reminders?brain=${encodeURIComponent(fbrain())}`)).json(); } catch (e) {}
      if (myGen !== _renderGen) return;
      const rem = d.pending || [];
      if (!rem.length) { box.innerHTML = ""; return; }
      const MODE_LBL = { notify: "nhắc", task: "tự làm + báo", script: "script" };
      box.innerHTML = `<h3 style="font-size:15px;color:#cdd8ee;margin:18px 0 8px">Nhắc hẹn đang chờ</h3>`;
      rem.forEach(r => {
        const title = r.label || r.text || "Nhắc hẹn";
        const when = r.cron ? `cron ${r.cron}` : (r.due_human || "");
        const kind = MODE_LBL[r.mode] || "nhắc";
        const div = document.createElement("div");
        div.className = "si-card";
        div.innerHTML = `<b>${esc(title)}</b>
          <div class="dim" style="font-size:12px;color:#6b7894">${esc(when)} · ${esc(kind)}</div>
          <button class="s-btn-ghost rmCancel" style="margin-top:8px">Huỷ</button>`;
        div.querySelector(".rmCancel").onclick = async () => {
          if (!confirm(`Huỷ "${title}"?`)) return;
          const f = new FormData();
          f.append("id", r.id);        // id THÔ, /reminders/cancel nhận đúng dạng này
          f.append("brain", fbrain());
          await fetch("/reminders/cancel", { method: "POST", body: f });
          loadReminders();
        };
        box.appendChild(div);
      });
    }
```

Rồi gọi nó ở cuối `loadLoops` (`:809-826`), ngay trước dòng `clearTimeout(pollTimer);`:

```js
      loadReminders();
```

- [ ] **Step 6: Xoá studio page `automations`**

Trước tiên lấy vị trí thật (số dòng trong plan đã trôi, xem cảnh báo tranh chấp ở đầu task):

```bash
cd /d/Project/Javis-OS
git status --short dashboard/studio.js
grep -n "function loadAutomations\|function editAutomation\|automations" dashboard/studio.js
```

Nếu `git status` cho thấy `studio.js` đang có sửa dở của người khác, **dừng và hỏi** trước khi động vào.

Trong `dashboard/studio.js` (ba chỗ đầu vẫn ở đúng dòng cũ vì nằm trên vùng trôi):
- Bỏ `automations: loadAutomations` khỏi map (`:46`).
- Bỏ `"automations"` khỏi mảng `["workflows", "agents", "skills", "automations"]` (`:55`).
- Xoá nhánh `else if (tab === "automations") loadAutomations();` (`:58`).
- Xoá nguyên hàm `loadAutomations` (neo: `async function loadAutomations() {`) tới hết thân hàm, gồm cả nút gọi `/automations/sync` bên trong nó.
- Xoá nguyên hàm `editAutomation` (neo: `function editAutomation(a) {`) tới hết thân hàm.

**Không** đụng `dashboard/index.html`: `panel-automations` do `console.js:222` dựng động từ `STUDIO_PAGES`, và Step 2.4 đã bỏ `"automations"` khỏi mảng đó rồi.

- [ ] **Step 7: Xác nhận không còn tham chiếu**

Run: `cd /d/Project/Javis-OS && grep -rn "automations" dashboard/console.js dashboard/studio.js dashboard/index.html`

Expected: **0 hit** ở ba file này. (So với ba con số ghi ở Step 1.)

Cố ý **không** grep cả `dashboard/*.js`: `_studio_old.js` và `_wf_harness*.html` là file cũ/harness chưa track, còn chứa `panel-automations`, và không thuộc phạm vi task này.

- [ ] **Step 8: Kiểm tra bằng mắt trong app thật**

Chạy server, mở dashboard:
1. Rail trái **không còn** mục "Lịch".
2. Mục "Loop" giờ tên là "Việc", nằm trong nhóm "Việc" cùng Kanban.
3. Mở trang Việc: thấy danh sách loop; đoạn mô tả đầu trang **không** còn câu "Loop bật sẽ hiện ở tab Lịch".
4. Console trình duyệt **không** có lỗi 404 tới `/automations`, không có `ReferenceError`.
5. Tạo một nhắc hẹn qua chat ("30 phút nữa nhắc anh test"), tải lại trang Việc: thấy khối "Nhắc hẹn đang chờ" với đúng nhắc đó. Bấm Huỷ: nhắc biến mất và không quay lại sau khi tải lại.

- [ ] **Step 9: Commit**

```bash
git add dashboard/console.js dashboard/studio.js dashboard/index.html
git commit -m "feat(dashboard): mot trang Viec thay cho Loop + Lich

Xoa studio page Lich (form 4 field khong dan toi executor nao) va rail
automations. Rail selfimprove doi nhan thanh Viec, render them khoi nhac hen
dang cho, va bo cau copy tro toi tab Lich da xoa.

Bat buoc phai gop nhac hen: pending_as_automations (reminders.py:278) truoc
day CHI hien o tab Lich, xoa rail ma khong gop = user mat cho nhin chung.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Dọn panel loop chết trong index.html

**Files:**
- Modify: `dashboard/index.html:160-192` (xoá panel `display:none`)
- Modify: `dashboard/app.js:1497` (xoá fetch `/loop/config` phục vụ panel đó)

**Interfaces:**
- Consumes: không.
- Produces: không. Task xoá thuần, tách riêng để reviewer từ chối được độc lập.

**Bối cảnh:** panel loop cũ ở `index.html:160-192` có `display:none` (không ai thấy) nhưng `app.js:1497` vẫn fetch `/loop/config` mỗi lần tải trang. Route `/loop/config` là shim legacy (`self_improve.py:988-1036`) và giai đoạn 2 sẽ đụng nó, nên dọn client trước cho gọn.

- [ ] **Step 1: Xác nhận panel thật sự chết**

Run: `cd /d/Project/Javis-OS && sed -n '160,192p' dashboard/index.html | grep -n "display:none"; grep -rn "loop/config" dashboard/*.js`

Expected: thấy `display:none` trong panel, và hit `loop/config` ở `app.js:1497`. Nếu **không** thấy `display:none`, DỪNG - panel đang sống, task này sai giả định, báo lại người review.

- [ ] **Step 2: Xoá panel + fetch**

Xoá khối `dashboard/index.html:160-192`. Xoá fetch `/loop/config` và code xử lý kết quả của nó ở `dashboard/app.js:1497`.

- [ ] **Step 3: Xác nhận route legacy vẫn còn (chưa xoá backend)**

Run:

```bash
cd server && ../.venv/Scripts/python.exe -c "
import os, sys, tempfile
os.environ.setdefault('JAVIS_STATE_DIR', tempfile.mkdtemp())
sys.path.insert(0, '.')
import main
paths = {getattr(r,'path','') for r in main.app.routes}
print('/loop/config con:', '/loop/config' in paths)
"
```

Expected: `True`. Giai đoạn 1 **không** xoá shim backend, chỉ bỏ client chết. Giai đoạn 2 quyết định số phận shim.

- [ ] **Step 4: Kiểm tra bằng mắt**

Tải lại dashboard. Tab Network không có request tới `/loop/config`, console không có lỗi JS, trang Việc vẫn hiện đúng.

- [ ] **Step 5: Commit**

```bash
git add dashboard/index.html dashboard/app.js
git commit -m "chore(dashboard): xoa panel loop chet + fetch /loop/config thua

Panel index.html:160-192 co display:none (khong ai thay) nhung app.js:1497 van
fetch /loop/config moi lan tai trang. Shim backend giu nguyen, giai doan 2
quyet dinh so phan no.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Chạy toàn bộ test + cập nhật tài liệu

**Files:**
- Modify: `CLAUDE.md` (bỏ nhắc tab Lịch ở mục điều phối)
- Modify: `.claude/skills/javis-builder/SKILL.md` (nếu có nhắc automations/Lịch)
- Modify: `CHANGELOG.md`, `VERSION`

**Interfaces:**
- Consumes: mọi task trước.
- Produces: không.

- [ ] **Step 1: Chạy toàn bộ test suite như CI**

Run: `cd server && for f in test_*.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: mọi file in `OK - ...`. Không file nào FAIL. Đặc biệt chú ý `test_loop_ambient.py` (dựa vào `_isolate`) và `test_system_sync.py` (dựa vào `LEGACY_HASHES`) - giai đoạn 1 không được đụng hai thứ đó.

- [ ] **Step 2: Chạy compileall như CI**

Run: `cd /d/Project/Javis-OS && .venv/Scripts/python.exe -m compileall -q server system/plugins`

Expected: không output (thành công).

- [ ] **Step 3: Chạy test JS của CI**

Run: `cd /d/Project/Javis-OS && node dashboard/test_chat_ask.js`

Expected: pass. (CI chạy đúng lệnh này ở `.github/workflows/ci.yml:27`.)

- [ ] **Step 4: Sửa CLAUDE.md**

Run: `cd /d/Project/Javis-OS && grep -n "tab Lịch\|automations" CLAUDE.md`

Ở mục "Điều phối", bậc 6 hiện ghi: `**Tạo Lịch** - nhắc nhở / job có MỐC GIỜ cố định → qua automations (tab Lịch).` Sửa thành:

```markdown
6. **Tạo Nhắc hẹn** - nhắc nhở / job có MỐC GIỜ cố định → `POST /reminders` (xem ở trang Việc).
```

Giữ nguyên 8 bậc, không đánh số lại, để khỏi vỡ các chỗ khác tham chiếu tới thang này.

- [ ] **Step 5: Kiểm tra javis-builder skill**

Run: `cd /d/Project/Javis-OS && grep -rn "automations\|tab Lịch" .claude/skills/javis-builder/SKILL.md skills/javis-builder/SKILL.md 2>/dev/null`

Nếu có hit, sửa theo cùng cách Step 4. Nếu không có hit, bỏ qua step này.

- [ ] **Step 6: Bump VERSION + CHANGELOG**

Đọc `VERSION`, tăng patch. Thêm mục đầu `CHANGELOG.md`:

```markdown
## <phiên bản mới>

- Xoá tab Lịch: registry `automations.json` chưa từng có executor (scheduler không đọc nó), 0 file tồn tại trên mọi brain. Thay bằng một trang **Việc** duy nhất hiện loop + nhắc hẹn đang chờ.
- Bảo mật: xoá `/automations/sync`, route gọi engine không truyền `allowed_tools` nên chạy `bypassPermissions` + nạp `setting_sources`; bảo đảm "chỉ liệt kê" của nó chỉ là chữ trong prompt.
- Xoá 5 route `/automations*` mà **không** thêm endpoint nào: trang Việc đọc thẳng `GET /loops` và `GET /reminders` vốn đã có. Xoá kèm hai lớp chiếu `_loops_as_routines` + `pending_as_automations` (chúng chỉ tồn tại để dựng hình dạng dòng-Lịch).
```

- [ ] **Step 7: Commit + push**

```bash
git add CLAUDE.md CHANGELOG.md VERSION .claude/skills/javis-builder/SKILL.md
git commit -m "docs: cap nhat tai lieu sau khi xoa tab Lich

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

---

## Còn lại cho giai đoạn 2 (plan riêng)

Không làm trong plan này, ghi ra để khỏi quên:

- `parse_schedule()` dùng chung: một field `schedule` → `{kind: once|interval|cron}` kiểu Hermes.
- `cron` trong `_eligible_overdue` (`self_improve.py:455-466`) + jitter theo `hash(slug)`.
- Hub `X-Javis-Connectors` + `connectors: [...]` trên frontmatter loop (rủi ro cao nhất: hub là lớp cứng, phải fail-closed).
- `allow_real_actions` thay dial 3 nấc, map vào `effective_perm` (`mcp_hub.py:314`) sẵn có.
- Tool `javis_schedule` route hai kho; `op: list`/`cancel` phải nhìn union cả hai.
- Số phận 5 route shim legacy `/loop/*` (`self_improve.py:988-1036`).

## Bug độc lập phát hiện khi soạn plan (tách issue riêng)

`main.py:3631` gọi `tasks_feature.tick(["brain"])` với brain **hardcode**, trong khi `tick(brains)` nhận list. Board Kanban ở brain khác `"brain"` không bao giờ được dispatch. Không thuộc plan này.
