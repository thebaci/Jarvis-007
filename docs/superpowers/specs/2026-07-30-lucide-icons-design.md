# Thay emoji bằng bộ icon Lucide trong dashboard

Ngày: 2026-07-30
Trạng thái: đã chốt, đang thi công

## Vấn đề

Dashboard đang dùng ~400 emoji dán trực tiếp vào chuỗi HTML làm icon. Ba cái sai:

1. **Mỗi máy vẽ một kiểu.** Emoji do font hệ thống vẽ, nên Windows, macOS, Android
   và Linux ra bốn hình khác nhau. Không kiểm soát được hình dạng.
2. **Cứng màu, không theo tông.** Jarvis 007 có tông TỐI và tông SÁNG. Emoji không nhận
   `color`, nên ở tông sáng nó chọc vào mắt và lệch hẳn khỏi bảng màu.
3. **Nét không đồng bộ.** Emoji màu đứng cạnh ký hiệu hình học (`✕ ↻ ▾`) cho ra
   giao diện chắp vá, không có cảm giác một bộ.

## Mục tiêu

Toàn bộ icon trong giao diện dashboard vẽ bằng Lucide: một bộ nét, tự đổi màu theo
tông và theo màu chữ chỗ nó đứng, giống nhau trên mọi máy.

## Phạm vi

**Trong phạm vi:** `dashboard/index.html`, `dashboard/*.js`, `dashboard/style.css`,
`dashboard/console.css`.

**Ngoài phạm vi, có lý do:**

- **Cú pháp Obsidian Tasks trong file .md** (`📅` hạn chót, `⏫🔼🔽` ưu tiên,
  `✅` ngày hoàn thành, `🛫` ngày bắt đầu). Đây là **định dạng dữ liệu**, không
  phải icon. Đổi là hỏng tương thích với Obsidian và làm sai
  `tests/python/test_dataview_tasks.py`. Phần **hiển thị** các mốc này trên giao
  diện thì vẫn đổi sang icon; chỉ chuỗi ghi vào file .md là giữ nguyên.
- **Emoji trong tin nhắn Telegram phía server.** Telegram tự render emoji đều trên
  mọi thiết bị nên không có vấn đề hiển thị, và tin nhắn không phải giao diện web.
- **`dashboard/vendor/`** (mã của người khác), `dashboard/docs/`, `voice-test.html`
  (trang lẻ đứng riêng, không thuộc giao diện Jarvis 007).

## Cách làm: vendor bộ rút gọn + hàm trả chuỗi

Đã cân ba đường:

| Cách | Được | Mất | Kết |
|---|---|---|---|
| **A. Vendor bộ rút gọn + `ic()`** | 18.1KB cho 102 icon; không gọi mạng lúc chạy; trả về chuỗi đúng thứ code cần | Cần script sinh code + manifest | **Chọn** |
| B. Vendor cả bộ UMD | Gõ tên nào cũng có ngay | 414KB (thừa 95%); `createIcons()` quét DOM nên phải quét lại sau mỗi lần đổi `innerHTML`, vừa chậm vừa dễ sót icon; vẫn phải tự viết hàm trả chuỗi | Loại |
| C. Sprite SVG + `<use>` | Markup ngắn, một file cache chung | Thêm một lượt tải mạng mới hiện được icon (nháy trắng lúc mở trang); `currentColor` với file ngoài từng lỗi trên Safari | Loại |

Lý do quyết định: dashboard dựng HTML bằng template string (`innerHTML = \`...\``)
ở khắp nơi, nên thứ cần nhất là **một hàm trả về chuỗi SVG**. Cách A cũng khớp
đúng thói quen sẵn có của repo (file trong `vendor/` + biến toàn cục, không build,
không import) và repo này không có `package.json` nên không thể thêm bước build.

## Kiến trúc

Bốn phần, mỗi phần một việc:

```
dashboard/icons.manifest.json   nguồn sự thật: danh sách tên icon, chia nhóm
        |
        v  python tools/gen_icons.py   (chạy tay, cần internet, chỉ lúc phát triển)
        |
dashboard/vendor/lucide-icons.js  file TỰ SINH, commit vào repo
        |                          window.LucideIcons = { tên: ruột svg }
        v
dashboard/icons.js               tầng API: ic() / Icons.msg() / Icons.render()
        |
        v
style.css .ic                    cỡ theo 1em, màu currentColor, canh chân chữ
```

Vì sao tách manifest ra khỏi file sinh: file sinh không được sửa tay, nhưng người
dùng cần một chỗ dễ đọc để thêm icon. Manifest chia nhóm theo mục đích nên tra
nhanh, và script chặn tên lặp lẫn tên không có thật.

### Ba lối dùng

```js
// 1. Trong template string - lối chính, dùng nhiều nhất
html += `<button>${ic("save")} Lưu</button>`;

// 2. Trong HTML tĩnh của index.html - Icons.render() thay hộ lúc tải trang
<i data-ic="search" class="vs-ico"></i>

// 3. Thông báo trạng thái có chuỗi từ server - BẮT BUỘC dùng lối này
el.innerHTML = Icons.msg("triangle-alert", r.error);
```

Lối 3 là quyết định về **bảo mật**, không phải tiện tay. Rất nhiều chỗ hiện nay là
`el.textContent = "⚠ " + r.error`. `textContent` không diễn giải HTML nên an toàn
sẵn. Đổi sang icon buộc phải chuyển sang `innerHTML`, mà `r.error` là chuỗi từ
server - nối thẳng là mở lỗ XSS ở đúng những chỗ trước đây an toàn.
`Icons.msg()` escape phần chữ nên bịt hẳn đường đó. Đây là rủi ro thật của việc
di trú này và phải xử lý bằng API, không bằng nhắc nhở.

### Quyết định thiết kế

**Bảng dữ liệu chứa TÊN icon, không chứa SVG.** `VIEW_META` trong console.js được
tính lúc nạp file. Nếu để `icon: ic("workflow")` thì nó gọi `ic()` ngay lúc parse,
buộc thứ tự nạp script phải đúng tuyệt đối. Để `icon: "workflow"` rồi gọi `ic()`
lúc render thì bảng vẫn dễ đọc và hết ràng buộc thứ tự.

**Cỡ icon là `1em`, không phải px.** Icon co theo cỡ chữ của khối chứa nó, nên
icon trong nút 11px và icon trong tiêu đề 18px đều cân mà không cần khai báo cỡ
riêng từng chỗ. Nét mảnh dần khi icon to lên (`.ic-lg`, `.ic-xl`) vì nét 2 ở cỡ
16px là vừa nhưng ở cỡ 32px thì thô.

**Icon thiếu phải lộ ra.** Gõ sai tên là lỗi vô hình. `ic()` vẽ dấu hỏi thay chỗ
và `console.warn` một lần cho mỗi tên sai; test tĩnh bắt luôn lúc chạy CI.

**`<select>` dùng `<optgroup>` + chữ thuần.** Thẻ `<option>` chỉ nhận chữ, không
nhận SVG. Ba chỗ bị ảnh hưởng: bộ chọn brain (`📁` phân biệt folder ngoài - đây là
**thông tin** chứ không phải trang trí, nên chuyển thành
`<optgroup label="Thư mục ngoài">`), chọn model (`✏️` bỏ hẳn), chọn ưu tiên việc
(`🔺🔼🔽` thành chữ "Cao/Vừa/Thấp"). Không làm dropdown tự vẽ: phải tự lo bàn
phím, cảm ứng, đóng khi bấm ra ngoài - quá nhiều rủi ro cho bộ chọn brain.

**Đèn trạng thái dùng `circle` + class màu.** `●` đặc và `○` rỗng thành
`ic("circle", {cls:"ic-fill ic-ok"})` và `ic("circle")`. Được thêm: đèn giờ ăn
theo biến màu nên tông sáng tự có bản đậm hơn, việc `🟢🔴⚪` không làm được.

## Bảng đối chiếu

Không phải thay máy móc từng ký tự: cùng một ký tự mang nghĩa khác nhau tuỳ chỗ.
`✓` trong "✓ Đã lưu" là `check`, còn `✓` làm đèn kết quả là `circle-check`.

### Thanh điều hướng (`VIEW_META` trong console.js)

| Cũ | Mới | Mục |
|---|---|---|
| `⬡` | `hexagon` | Jarvis 007 |
| `💬` | `message-circle` | Trò chuyện |
| `🤖` | `bot` | Agents |
| `🧩` | `puzzle` | Skills |
| `⚡` | `workflow` | Workflows |
| `♻` | `repeat` | Việc định kỳ |
| `🔌` | `plug` | Kết nối |
| `📊` | `chart-column` | Mức dùng |
| `⚙` | `settings` | Cài đặt |
| `◈` | `cpu` | Models |
| `✉` | `mail` | Kênh kết nối |
| `🗂` | `folder-tree` | Tệp tin |
| `🗒` | `scroll-text` | Nhật ký |
| `🧰` | `toolbox` | Plugins |

### Nút và thao tác

| Cũ | Mới | | Cũ | Mới |
|---|---|---|---|---|
| `💾` | `save` | | `✕` | `x` |
| `↻` `🔄` | `rotate-cw` | | `▶` | `play` |
| `■` | `circle-stop` | | `🗑` | `trash-2` |
| `✎` `✏` | `pencil` | | `🔍` | `search` |
| `➕` | `plus` | | `⌂` `🏠` | `house` |
| `⬆` | `arrow-up` | | `↗` | `external-link` |
| `⇩` | `download` | | `↩` `↶` | `undo-2` |
| `↓` | `arrow-down` | | `←` | `chevron-left` |
| `⇅` | `arrow-up-down` | | `🕘` | `history` |
| `🔊` | `volume-2` | | `🔗` | `link` |
| `❝` | `quote` | | `📎` | `paperclip` |
| `⛶` | `maximize` | | `☰` | `menu` |
| `▾` `⌄` | `chevron-down` | | `▸` | `chevron-right` |
| `🧹` | `brush-cleaning` | | `🧠` | `brain` |

### Trạng thái

| Cũ | Mới | Ghi chú |
|---|---|---|
| `⚠` `⚠️` | `triangle-alert` + `.ic-warn` | 78 chỗ, phần lớn qua `Icons.msg()` |
| `✓` | `check` | dấu xác nhận trong câu |
| `✅` | `circle-check` + `.ic-ok` | đèn kết quả |
| `✗` | `circle-x` + `.ic-err` | |
| `⏳` | `hourglass` | đang chờ |
| `◎` | `loader` + `.ic-spin` | đang tải |
| `●` `⬤` | `circle` + `.ic-fill` | đèn bật |
| `○` | `circle` | đèn tắt |
| `🟢` | `circle` + `.ic-fill .ic-ok` | |
| `🔴` | `circle` + `.ic-fill .ic-err` | |
| `⚪` | `circle` + `.ic-dim` | |
| `▲` `▼` | `trending-up` `trending-down` | biến động token |

### Loại tệp và các thứ khác

| Cũ | Mới | | Cũ | Mới |
|---|---|---|---|---|
| `📁` | `folder` | | `📂` | `folder-open` |
| `🖼` | `image` | | `📕` `📝` | `file-text` |
| `📜` | `file-code` | | `🎵` | `file-audio` |
| `📄` | `file` | | `🌐` | `globe` |
| `📖` | `book-open` | | `📦` | `package` |
| `★` `⭐` | `star` | | `🛡` | `shield` |
| `⛔` | `ban` | | `🔒` | `lock` |
| `🔧` | `wrench` | | `✨` `✦` | `sparkles` |
| `💡` | `lightbulb` | | `⏰` | `alarm-clock` |
| `🔁` | `repeat` | | `🪝` | `webhook` |
| `▦` | `table-2` | | `☑` | `list-todo` |
| `❓` | `circle-help` | | `♙` | `user` |
| `◆` | `diamond` | | `✍` | `pen-line` |
| `🔺` | `chevrons-up` | | `🔼` | `chevron-up` |
| `🔽` | `chevron-down` | | `⏫` `⏬` | `chevrons-up` `chevrons-down` |
| `🛫` | `plane-takeoff` | | `📅` | `calendar` |

### Không đổi, có lý do

`→` (212 chỗ) là dấu trong **câu văn**: "Hostinger → App terminal", "Đăng nhập
Claude → đủ MCP". Đây là chữ, không phải icon. Cùng lý do với `─` `•` `↔`
(gạch phân cách, đầu dòng, ký hiệu trong ghi chú của lập trình viên).

## Thi công theo 5 đợt

Mỗi đợt chạy test được ngay, không đợt nào để giao diện ở trạng thái nửa vời.

1. **Hạ tầng** - manifest, script sinh code, file vendor, `icons.js`, CSS, test.
   Chưa đổi gì về mặt hiển thị. *(xong)*
2. **Các bảng có cấu trúc** - `VIEW_META`, `GROUP_META`, `_fileIcon()`, `_PRIO`.
   Ít chỗ sửa nhất mà thấy khác nhất, vì mỗi bảng là một điểm đổi duy nhất.
3. **HTML tĩnh + nút bấm** - `index.html` chuyển sang `data-ic`; các nút trong JS.
   Chú ý: chỗ nào đang gán `textContent` phải chuyển sang `innerHTML`.
4. **Chuỗi trạng thái** - 78 chỗ `⚠`, 41 chỗ `✓`, 18 chỗ `✅` qua `Icons.msg()`.
5. **`<select>` + quét nốt** - `<optgroup>`, bỏ emoji trong `<option>`, dọn phần
   sót cho test đợt 6 xanh.

## Kiểm chứng

`tests/python/test_icons.py`, chạy như mọi test khác trong repo
(`python tests/python/test_icons.py`):

- Bộ vendor khớp manifest, không thiếu không thừa.
- **Mọi tên icon gọi trong nguồn đều có thật.** Chặn lỗi gõ sai thành icon vô hình.
- Tầng API còn đủ `ic`, `Icons.msg` (rào XSS), `Icons.render`, cảnh báo console,
  `aria-hidden`, `currentColor`.
- Thứ tự nạp script trong `index.html` đúng: dữ liệu trước API, API trước mọi file dùng nó.
- CSS còn `.ic`, cỡ `1em`, canh chân chữ, `.ic-fill`, tôn trọng `prefers-reduced-motion`.
- **Không còn emoji trong giao diện.** Có danh sách ngoại lệ ngắn, ghi rõ lý do
  từng dòng, cho cú pháp Obsidian Tasks. Test in ra file và số dòng vi phạm nên
  vừa là thước đo tiến độ trong lúc thi công, vừa là rào chặn về sau.

Kiểm bằng mắt sau khi xong: mở cả tông TỐI và tông SÁNG, soát thanh điều hướng,
trang Kết nối, trang Tệp tin, trang Việc, cửa sổ Cài đặt, và khung chat.

## Rủi ro

| Rủi ro | Cách chặn |
|---|---|
| Chuyển `textContent` sang `innerHTML` mở lỗ XSS | `Icons.msg()` escape sẵn; đợt 4 đi từng chỗ có chuỗi từ server |
| Gõ sai tên icon thành icon vô hình | Test đối chiếu tên; `ic()` vẽ dấu hỏi + cảnh báo console |
| Icon lệch hàng so với chữ | `.ic` canh `-0.14em`; kiểm mắt ở đợt cuối |
| Đổi cú pháp Obsidian Tasks làm hỏng dữ liệu | Đã loại khỏi phạm vi; ghi vào danh sách ngoại lệ của test |
| Thêm 2 file script làm chậm tải | 18.1KB, không gọi mạng; cache-bust `?v=` đã tự động theo VERSION |
