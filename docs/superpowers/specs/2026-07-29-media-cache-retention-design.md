# Thiết kế: media là vùng cache, không phải tri thức

Ngày: 2026-07-29
Trạng thái: đã brainstorm + duyệt hướng, chờ triển khai.

## Vấn đề

Media chảy vào vault qua ba đường và không đường nào có cơ chế dọn:

- Ảnh Jarvis 007 tự tạo lưu vào `<vault>/attachments/` - `server/image_gen.py:202` (`save_png_b64`).
- File/ảnh user gửi qua Telegram tải về `<vault>/inbox/telegram/` - `server/main.py:6242` (`_tg_inbox_dir`).
- Ingest source chép ảnh gốc sang thư mục Attachments khi user yêu cầu - `server/main.py:1888`.

Grep toàn bộ `server/` không thấy một dòng retention, prune hay expire nào cho media.

Chỗ đắt hơn nằm ở git. Mẫu `.gitignore` của brain (`server/git_brain.py:63`) chỉ loại lock, `learn-staging`, `learn-log`, `loop-log`, `skill-usage.json` và `conversations/`. `attachments/` với `inbox/` được commit bình thường. Nghĩa là mỗi tấm ảnh là một blob nằm vĩnh viễn trong lịch sử git của brain: xoá file trên đĩa về sau cũng không lấy lại được dung lượng, mà `git_brain` còn giữ mirror nên nhân đôi. Ảnh 2MB hôm nay là 4MB chiếm chỗ mãi mãi, cộng thêm dung lượng trên GitHub nếu bật sao lưu.

## Đối chiếu hermes

Hermes để media ở `~/.hermes/cache/images` (`.learn/hermes/agent/image_gen_provider.py:234`), cùng họ với `cache/audio`, `cache/videos`, `cache/documents`, `cache/screenshots` (`.learn/hermes/gateway/platforms/base.py:950`). Media nằm trong thư mục state của app, đặt tên thẳng là **cache**, tách hẳn khỏi tầng tri thức, không dính git. Chỗ này hermes làm đúng hơn Jarvis 007.

Nhưng hermes chỉ giải nửa bài. Nó prune session 90 ngày (`.learn/hermes/gateway/session.py:1429`) và checkpoint 7 ngày (`.learn/hermes/gateway/run.py:2821`), còn `cache/images` thì không có dòng dọn nào. Gọi là cache nhưng không ai xoá, vẫn phình vô hạn. Nên lấy ý tưởng "media là cache" của hermes, không lấy cách nó bỏ mặc.

## Quyết định đã chốt

- Media là **nguyên liệu đi qua**, không phải tài sản. Đọc xong, rút thành text .md là đủ dùng.
- Muốn lưu ảnh lâu dài thì về sau đấu Drive làm kho, không để Jarvis 007 ôm. Hiện tại chưa làm.
- Không backup media lên GitHub.
- Chấp nhận lịch sử chat cũ bị mất ảnh, miễn là chỗ đó ghi rõ "ảnh đã hết hạn" chứ không phải icon vỡ trơ.
- Lịch sử git đã lỡ commit ảnh thì **kệ**, không viết lại history. Chỉ chặn từ nay về sau.
- Giữ 30 ngày, trần 300MB mỗi brain.

## Thiết kế

### Ranh giới

Coi `attachments/` và `inbox/` của mỗi brain là **vùng cache**, không phải tri thức. Tri thức là file .md. Cái gì trong hai thư mục đó đều có thể biến mất mà brain vẫn nguyên vẹn.

### Phần 1 - Chặn git

Thêm vào `_GITIGNORE` ở `server/git_brain.py:63`. `_ensure_gitignore_lines` là merge-only nên brain cũ tự nhận dòng mới ở lần commit kế tiếp, không đè dòng user tự thêm.

Hai bẫy phải xử đúng:

**Bẫy tên thư mục.** Jarvis 007 dò thư mục attachments bằng regex `^(\d+\s*[-_.]\s*)?attachments$` không phân biệt hoa thường (`server/image_gen.py:40`, `server/main.py:1931`), nên trên thực tế nó có thể tên là `attachments`, `Attachments`, `05 - attachments`, `05-attachments`, `05_attachments` hay `05.attachments`. Git thì phân biệt hoa thường trên Linux (VPS chạy Linux). Một dòng `attachments/` là không đủ.

Dùng bốn dòng: `attachments/`, `Attachments/`, `*attachments/`, `*Attachments/`, cộng `inbox/`. Dấu `*` phủ mọi tiền tố số thứ tự mà regex chấp nhận mà không phải liệt kê từng dấu phân cách. Hai dòng không có `*` giữ lại cho dễ đọc, dù về mặt cú pháp `*` cũng khớp chuỗi rỗng.

**Bẫy file đã track.** `.gitignore` không có tác dụng với file git đã theo dõi từ trước. Phải chạy `git rm --cached -r` một lần cho các thư mục đó ở mỗi brain đang là git checkout. Hệ quả: commit kế tiếp ghi nhận "đã xoá ảnh", và kéo brain về máy khác thì ảnh cũ không đi theo nữa. Đây là hệ quả đã được chấp nhận, không phải lỗi.

Bước `git rm --cached` chạy ở đâu: cùng chỗ đã có sẵn cơ chế vá `.gitignore` cho brain cũ (`server/git_brain.py:114-147`), chạy một lần, idempotent (không còn gì trong index thì lệnh không làm gì).

### Phần 2 - Janitor

Module mới `server/media_gc.py`.

Phần quyết định tách thành hàm **thuần**:

```
plan_deletions(entries, now, max_age_days, max_mb) -> list[path]
```

`entries` là danh sách `(path, size, mtime)`. Hàm không chạm đĩa nên test được không cần fixture. Cùng kiểu `save_png_b64` bên `server/image_gen.py` đang làm.

Hai luật chạy cùng nhau:

1. **Hạn tuổi**: file có mtime quá 30 ngày thì vào danh sách xoá.
2. **Trần dung lượng**: sau khi trừ nhóm quá hạn, nếu tổng còn lại vẫn vượt 300MB thì xoá tiếp từ cũ tới mới cho tới khi xuống dưới trần.

Trần là van an toàn cho trường hợp sinh một trăm tấm ảnh trong một ngày, lúc đó luật tuổi chưa kịp cứu.

File `.md` nằm trong hai thư mục đó thì chừa ra, phòng khi có note lạc vào.

Janitor **không** phân biệt ảnh Jarvis 007 tự tạo với ảnh user chủ động bảo "lưu vào source". Ảnh ingest nhúng trong note Sources cũng hết hạn như mọi ảnh khác, note .md giữ lại nội dung đã trích còn chỗ nhúng ảnh thành ô xám. Đây là hệ quả đã được chấp nhận, đúng với quyết định "media là nguyên liệu đi qua". Muốn giữ ảnh lâu dài thì đường đi là Drive, không phải chừa ngoại lệ trong janitor.

Phần chạm đĩa là hàm riêng: quét thư mục, gọi `plan_deletions`, xoá, trả về số file và số byte đã dọn.

**Quét đĩa phải dùng `os.scandir` và không được nằm trong event loop.** Bài học cũ ở dự án này: `glob(...)[:N]` đi hết cây rồi mới cắt, không phải trần thật, và quét đĩa đồng bộ làm nghẽn event loop tới mức Traefik gỡ route vì container unhealthy.

### Phần 3 - Móc vào scheduler

Thêm một mục vào `_scheduler_loop` (`server/main.py:4220`), nhưng **không** chạy theo nhịp 30 giây của vòng lặp đó. Giữ mốc `last_run` trong bộ nhớ tiến trình, đủ 6 tiếng mới chạy một lượt, và bọc trong `asyncio.to_thread`. Bọc `try/except` riêng in ra stderr theo đúng khuôn các mục đang có, để janitor hỏng không kéo sập tick của loop, kanban hay reminders.

Quét theo danh sách brain của `loop_feature.scheduler_brains()`, giống mục Jarvis 007 index ở `server/main.py:4263`.

### Phần 4 - Cấu hình

Khoá `media` trong `settings.json`, đọc qua `cfgmod.read_settings()`:

- `enabled`: mặc định `true`.
- `max_age_days`: mặc định `30`.
- `max_mb`: mặc định `300`.

Đặt `enabled: false` thì janitor không xoá gì, dùng khi user muốn tự quản.

### Phần 5 - Ô ảnh hết hạn

`/files/raw` trả 404 khi file không tồn tại (`server/main.py:2864`), nên `<img>` sẽ bắn sự kiện `error`.

Sửa `imgHtml` ở `dashboard/chat-render.js:172`: gắn `onerror` để thay thẻ `<img>` bằng một ô xám ghi **"Ảnh đã hết hạn"**. Làm ở tầng `onerror` thì đúng luôn cả trường hợp user xoá tay hay đổi tên file, không chỉ riêng janitor.

Chuỗi hiển thị phải là tiếng Việt **có dấu** (luật dự án, đã mắc lỗi này hai lần trước).

CSS ô xám thêm vào `dashboard/style.css`, nhớ bump `?v` (asset tĩnh cache theo VERSION, đã tự động từ v0.9.139).

## Bổ sung sau khi triển khai: đường thứ tư

Bản khảo sát ban đầu đếm ba đường media và bỏ sót đường thứ tư, vì lúc đó chỉ quét `brains/`.

`STATE_DIR/.staging` (`server/main.py:1779`) là nơi file user dán hoặc tải lên khung chat rơi xuống trước khi engine đọc. Code chỉ có hai thao tác với nó: tạo thư mục và ghi file vào (`server/main.py:1848`). Không có gì dọn. Đo trên máy phát triển ngày 2026-07-29: **114MB, 62 tệp, file cũ nhất 27 ngày**, tức là to hơn cả `attachments` của brain.

Nó không nằm trong vault nên không dính git (đã bị chặn sẵn ở `.gitignore:11`), nhưng vẫn ăn đĩa VPS như mọi thứ khác.

Xử lý: `media_gc.sweep_staging`, hạn **3 ngày**, cấu hình qua `media.staging_days`. Khác luật của vùng cache brain ở hai điểm, cả hai đều vì staging là chỗ trung chuyển thuần:

- **Không chừa `.md`.** Chat không bao giờ nhúng đường dẫn staging nên không ai cuộn lại mở nó; một file `.md` ở đây là thứ user vừa dán vào chat, không phải note. Điều này đòi `plan_deletions` thêm tham số `keep_md`, mặc định `True` để luật của brain không đổi.
- **Chỉ có luật tuổi, không trần dung lượng.** Hạn 3 ngày đã đủ chặt.

Staging là thư mục dùng chung, không theo brain, nên scheduler quét nó đúng một lần ngoài vòng lặp brain.

## Phạm vi và ranh giới

- **Không** viết code đẩy Drive trong phạm vi này. Janitor là một hàm nhỏ, sau này muốn đẩy Drive thì chèn một bước ngay trước lệnh xoá. Không dựng sẵn khung hook rỗng.
- **Không** viết lại lịch sử git của brain. Đã chốt là kệ phần đã lỡ.
- **Không** dời media ra ngoài vault kiểu hermes. Đường dẫn `![](attachments/x.png)` giữ nguyên nên `/files/raw`, `chat-render.js`, `console.js`, `file-editor.js` không phải sửa gì về đường dẫn.
- Media của Zalo listener không nằm trong phạm vi: `server/zalo_listener.py` không tải file về vault.

## File đụng tới

- `server/media_gc.py` - mới. `plan_deletions` thuần + hàm quét/xoá.
- `server/git_brain.py` - thêm dòng vào `_GITIGNORE`; thêm bước `git rm --cached` một lần cho brain cũ.
- `server/main.py` - thêm mục janitor vào `_scheduler_loop`, tiết tấu 6 tiếng, chạy trong `to_thread`.
- `dashboard/chat-render.js` - `onerror` cho `imgHtml`.
- `dashboard/style.css` - ô xám "Ảnh đã hết hạn"; bump `?v`.
- `tests/python/test_media_gc.py` - mới.

## Kiểm thử

`plan_deletions` (thuần, không cần đĩa):

- File mới hơn hạn tuổi và tổng dưới trần thì không xoá gì.
- File quá hạn tuổi thì vào danh sách, file trong hạn thì không.
- Tổng vượt trần dù mọi file còn trong hạn: xoá từ cũ tới mới, dừng ngay khi xuống dưới trần, không xoá thừa.
- Vừa quá hạn vừa vượt trần: hai luật cộng dồn, không đếm trùng một file hai lần.
- File `.md` không bao giờ vào danh sách xoá.
- `max_age_days` hoặc `max_mb` bằng 0 hoặc âm: coi như tắt luật đó, không xoá sạch nhầm.

Phần chạm đĩa: dựng thư mục tạm với vài file giả mtime, chạy hàm quét, kiểm đúng file biến mất và số byte trả về khớp.

Gitignore: brain mới tạo có đủ các dòng biến thể; brain cũ đã có `.gitignore` riêng thì được merge thêm chứ không mất dòng cũ.

Thủ công trên dashboard: xoá tay một ảnh trong `attachments/` rồi tải lại chat cũ, chỗ đó phải hiện ô xám "Ảnh đã hết hạn" chứ không phải icon vỡ.
