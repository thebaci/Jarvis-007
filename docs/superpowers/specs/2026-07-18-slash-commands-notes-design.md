# Thiết kế: Khung lệnh `/` cho dashboard + skill `/notes`

Ngày: 2026-07-18
Trạng thái: đã duyệt, chuẩn bị triển khai

## Mục tiêu

Trang bị cho khung chat web của Jarvis 007 khả năng dùng lệnh `/` (giống Claude/Telegram),
và làm lệnh đầu tiên là `/notes`: gõ lệnh thì lưu nội dung tin nhắn vào `sources/` nguyên
văn (kèm ảnh/file), rồi tự chưng cất lên wiki nếu note đó đáng.

## Bối cảnh (phát hiện từ code)

- Telegram ĐÃ có hệ lệnh `/` đầy đủ trong `server/telegram_bot.py` + handler `_tg_command`
  ở `server/main.py:4981`. Bất kỳ `/<slug>` lạ nào Telegram tự hiểu thành "gọi skill tên
  đó" (`server/main.py:5076-5081`). Nên `/notes` chạy trên Telegram gần như miễn phí một khi
  skill `notes` tồn tại.
- Dashboard (web) CHƯA có cơ chế lệnh `/`. `sendMessage()` ở `dashboard/app.js:196` gửi
  nguyên chuỗi qua WebSocket, kể cả khi bắt đầu bằng `/`.
- Skill hệ thống nằm ở `<project>/.claude/skills/<slug>/SKILL.md`
  (`system_sync.SYSTEM_SKILLS_DIR`), được `system_sync.py` rải xuống mọi brain
  (`<brain>/skills/<slug>/SKILL.md` canonical + mirror `.claude/skills`). Manifest hash bảo
  vệ bản user đã sửa khỏi bị update ghi đè.
- Endpoint `GET /skills?brain=...` (`server/main.py:2193`) trả danh sách skill của brain
  gồm `slug`, `name`, `description`, `group`, `system`... dùng làm nguồn cho menu `/`.
- Skill `ingest-source` (`.claude/skills/ingest-source/SKILL.md`) đã có sẵn quy trình lưu
  source + chưng cất wiki theo 3 kỷ luật của vault. `/notes` tái dùng phán đoán và kỷ luật
  này cho bước distill.
- Đính kèm file trên web: `sendMessage()` đã tự thêm khối ngữ cảnh liệt kê đường dẫn file
  trong `Sources`/`Attachments` (`dashboard/app.js:210-221`). `/notes` bám vào đây để giữ
  ảnh/file.

## Quyết định đã chốt

1. Phạm vi: làm CẢ khung lệnh `/` cho web VÀ skill `/notes`.
2. `/notes` chộp: chỉ tin nhắn hiện tại (chữ sau `/notes` + file đính kèm cùng tin), nguyên văn.
3. Chỗ ở skill: skill HỆ THỐNG bundled (`.claude/skills/notes/SKILL.md`), tự có ở mọi brain.
4. Menu `/` web đợt đầu: danh sách skill của brain + vài lệnh phiên (`/reset`, `/stop`, `/new`).
5. Note không đáng wiki: VẪN lưu vào `sources/`, chỉ báo nhẹ, không đụng wiki (không hỏi lại).

## Kiến trúc

Nguyên tắc hợp nhất: trên Jarvis 007, `/<slug>` = gọi skill `<slug>` (đúng ngữ nghĩa Telegram đang
dùng). Web sẽ áp cùng luật đó, cộng một nhúm lệnh phiên xử lý tại chỗ.

### Phần A - Khung lệnh `/` cho dashboard

Frontend, không cần đổi backend.

- Module mới `dashboard/chat-slash.js`: quản menu lệnh nổi trên ô chat.
  - Khi `chatInput` bắt đầu bằng `/` và con trỏ ở token lệnh đầu, hiện menu.
  - Nguồn mục:
    - Lệnh phiên tĩnh: `/new` (hội thoại mới), `/reset` (reset phiên), `/stop` (dừng lượt đang chạy).
    - Skill động: fetch `GET /skills?brain=<brain hiện tại>`, lấy `slug` + `name` + `description`.
      Cache theo brain; nạp lại khi đổi brain.
  - Lọc theo chữ sau `/`. Điều hướng bàn phím: mũi tên lên/xuống, Enter/Tab chọn, Esc đóng.
    Chọn skill = điền `/slug ` vào ô để anh gõ tiếp nội dung; chọn lệnh phiên = chạy ngay.
- Chặn lệnh trong `sendMessage()` (`dashboard/app.js`):
  - Nếu `msg` bắt đầu bằng `/`, tách `cmd` (token đầu, bỏ dấu `/`) và `arg` (phần còn lại).
  - `cmd` thuộc lệnh phiên (`new|reset|stop`) → gọi hàm tương ứng có sẵn của app, KHÔNG gửi
    engine. (Tận dụng logic mint session mới / dừng lượt đã có.)
  - Còn lại → coi là skill: dựng `outMsg` = lời gọi skill giống Telegram
    (`Hãy dùng skill \`<cmd>\`` + (` với yêu cầu: <arg>` nếu có) + câu an toàn "nếu không có
    skill tên này thì cứ xử lý bình thường"). Nếu có file đính kèm, GIỮ khối ngữ cảnh path
    hiện có và ghép vào. Gửi qua WebSocket như chat thường.
  - Vẫn `appendUserMessage` hiển thị đúng những gì anh gõ (`/notes ...`), không lộ chuỗi bung.
- CSS menu trong `dashboard/style.css`; nối `<script>` trong `dashboard/index.html`.

Ranh giới: `chat-slash.js` chỉ lo hiển thị + chọn mục và báo cho `app.js` biết đã chọn gì;
`app.js` giữ toàn quyền gửi/không gửi. Không nhét logic engine vào module menu.

### Phần B - Skill hệ thống `notes`

File `.claude/skills/notes/SKILL.md`. Frontmatter: `name`, `description` (<=150 ký tự,
nêu thẳng năng lực), `group` (chọn nhóm sát nhất trong các skill hiện có, dự kiến "Năng suất"
hoặc "AI"). Thân skill hướng dẫn engine mỗi lần chạy:

1. Xác định vault đang làm việc (brain hiện tại) và các thư mục `sources/`, `attachments/`,
   `wiki/`. Đọc `CLAUDE.md`/`AGENTS.md` gốc brain trước (schema vault).
2. Lấy nội dung note = chữ anh gõ sau `/notes` (nguyên văn) + file/ảnh đính kèm nếu có.
   Chỉ tin nhắn hiện tại. TUYỆT ĐỐI không biên tập lại câu chữ.
3. Tạo `sources/note-YYYY-MM-DD-HHmm-<vài-chữ-đầu-không-dấu>.md`:
   - Frontmatter: `type: source`, `source_kind: own-note`, `status: unprocessed`,
     `created: <ngày giờ>`, `tags: [note]`.
   - Thân: văn bản gốc nguyên văn. Ảnh: chuyển file vào `attachments/`, nhúng `![[tên-ảnh]]`.
   - Nếu đã có file đính kèm nằm sẵn trong `Sources` (web upload) thì dùng chính nó/di chuyển,
     không nhân đôi.
4. Đánh giá đáng-wiki: có khái niệm/framework/nguyên lý/quy trình tái dùng được → đáng; tâm
   sự, việc vặt, nhắc nhất thời → không đáng. (Cùng tiêu chí ingest-source.)
5. Nếu đáng: áp phép INGEST của `ingest-source` cho note này - viết/cập nhật trang wiki đủ 3
   kỷ luật (citation `[[Nguồn]]`, mục tiêu vs thực tế, mâu thuẫn giữ rõ), cập nhật
   `wiki/index.md`, append `wiki/log.md`, set source `status: processed` + `processed_at` +
   `wiki_links: [...]`.
6. Nếu không đáng: giữ source `status: unprocessed` (hoặc `skipped` + `note` lý do), KHÔNG
   đụng wiki.
7. Báo ngắn bằng văn nói (không bảng, không gạch ngang dài): đã lưu note vào `[[...]]`, có/không
   lên wiki, trang nào. Nếu có ảnh nhúng thì hiện lại cho anh xem.

An toàn: ghi `sources/`+`wiki/` là mức `safe`, do chính người gõ lệnh nên tự chạy. Không tiền,
không đơn, không đăng bài, không gửi tin.

## Kiểm thử

- Web: gõ `/` thấy menu; gõ `/no` lọc ra `notes`; chọn điền `/notes `; gõ nội dung + gửi →
  file xuất hiện trong `sources/`, nội dung nguyên văn; note có khái niệm thì thấy trang wiki
  mới + `wiki/index.md` cập nhật; note vặt thì chỉ có source, báo nhẹ.
- Web đính ảnh + `/notes` → ảnh vào `attachments/`, source nhúng `![[...]]`.
- Lệnh phiên: `/new` mở hội thoại mới, `/stop` dừng lượt, không gửi cho engine.
- Telegram: gửi `/notes <nội dung>` → chạy skill `notes`, lưu source (kênh này vốn đã route,
  chỉ kiểm còn chạy sau khi thêm skill).
- `system_sync`: brain khác cũng thấy skill `notes` sau khi sync (không phải chỉ brain default).

## Ngoài phạm vi (đợt sau)

- Menu `/` web đầy đủ như Telegram (`/model`, `/brain`, `/status`, `/agents`, `/workflows`)
  cần handler lệnh riêng cho phiên web - để sau.
- `/notes` chộp câu trả lời gần nhất của Jarvis 007 khi gõ trơ - để sau.
- Chộp cả đoạn hội thoại nhiều lượt - để sau.

## File chạm vào

- Thêm: `.claude/skills/notes/SKILL.md` (system_sync tự rải xuống mọi brain).
- Thêm: `dashboard/chat-slash.js`.
- Sửa: `dashboard/app.js` (chặn `/` trong `sendMessage`, expose vài hàm phiên cho module menu).
- Sửa: `dashboard/style.css` (CSS menu), `dashboard/index.html` (nối script).
- Có thể đụng: cập nhật `LEGACY_HASHES`/manifest trong `server/system_sync.py` nếu quy trình
  seed yêu cầu đóng dấu hash skill mới (kiểm khi làm).
