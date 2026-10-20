# Thiết kế: Mở link và sửa file .md ngay trong khung chat

Ngày: 2026-07-18
Trạng thái: đã duyệt hướng (cách A)

## Bối cảnh và vấn đề

Trong khung chat, Jarvis 007 thỉnh thoảng gửi file .md, file text và link. Hiện tại:

- Link markdown `[chữ](https://...)` đã bấm mở tab mới được. Nhưng URL "trần" (Jarvis 007 gõ thẳng
  `https://...` không bọc markdown) chỉ hiện thành chữ, không bấm được.
- Bấm link file .md trong chat chỉ nhảy sang trang Tệp tin và tô sáng file đó, người dùng phải
  bấm thêm lần nữa mới mở được khung sửa.

Người dùng muốn: mọi link bấm mở được, và file .md bấm là bung ngay khung sửa (xem + chỉnh sửa).

## Mục tiêu

1. URL trần trong chat tự thành link bấm mở tab mới.
2. Bấm link file .md (và file text) trong chat bung ngay một khung sửa giữa màn hình để xem và
   chỉnh sửa, lưu lại được.

## Ngoài phạm vi

- Không làm editor WYSIWYG kéo-thả (cách B đã loại). Khung sửa dùng textarea nguồn, riêng .md có
  nút gạt xem bản render.
- Không đổi hành vi ảnh inline (bấm ảnh vẫn như cũ).
- Không sửa endpoint server. Tận dụng `/files/read`, `/files/write`, `/files/raw`, `/files/list`
  đang có.

## Chi tiết quan trọng: hai quy ước đường dẫn

- Đường dẫn file trong chat là **tương đối gốc brain** (theo quy ước CLAUDE.md khi AI ghi).
- `/files/read` và `/files/raw` dùng `_safe_serve_path` chấp nhận CẢ hai quy ước (trần duyệt và
  gốc brain) nên đọc/hiện ảnh bằng path chat là được.
- `/files/write` dùng `_safe_path` chỉ tính theo **trần duyệt**. Trên localhost trần = cả ổ đĩa,
  nên nếu ghi bằng path gốc-brain sẽ sai chỗ.

Kết luận: để LƯU đúng, phải đổi path gốc-brain thành path trần duyệt bằng cách ghép tiền tố "nhà"
của brain. Tiền tố này lấy từ `/files/list` (trường `home`). Đây chính là cách editor cây
(`openNote` qua `_vtHome`) đang làm. Khung sửa mới sẽ ghép `home` cho CẢ đọc lẫn ghi để nhất quán.

## Kiến trúc và thành phần

### Phần 1 - Tự nhận URL trần (sửa `dashboard/chat-render.js`)

Trong `mdToHtml`, thêm một bước sau khi code fence, inline code, ảnh và link markdown đã được cất
vào placeholder (sentinel private-use), TRƯỚC khi parse block. Bước này chỉ chạm text thường:

- Bắt `https?://...` bằng regex, loại dấu câu đuôi (`.,;:!?)]}'"`) khỏi link.
- Bọc thành `<a href target="_blank" rel="noopener">`, đưa qua `put()` để không bị escape lại.
- Vì code/link cũ đã là sentinel nên không bị đụng; sentinel không khớp regex URL.

### Phần 2 - Khung sửa file (`dashboard/file-editor.js`, MỚI)

Module IIFE độc lập, tự chèn CSS, gắn modal vào `document.body`. Chạy được từ mọi trang vì
`position: fixed` cấp body, không phụ thuộc layout HUD hay trang Tệp tin.

Giao diện: `window.JavisEditFile(brainRelPath)`

Luồng:

1. Lấy tiền tố `home` của brain (fetch `/files/list?brain=<brain>` một lần, cache theo brain).
   Path trần = `home ? home + "/" + brainRel : brainRel`.
2. Đọc `/files/read?brain=<brain>&path=<pathTran>` → `{name, editable, content}`.
3. Hiện theo loại:
   - Ảnh (`.png .jpg .jpeg .gif .webp .bmp .ico`): `<img src=/files/raw...>`.
   - `.pdf`: `<iframe src=/files/raw...>`.
   - Text sửa được (`editable` từ server): `<textarea>`. Riêng `.md` thêm nút gạt "Nguồn / Xem";
     bản Xem render bằng `window.mdToHtml` sẵn có (chỉ đọc, dựng từ giá trị textarea hiện tại).
   - Khác: nút Tải.
4. Lưu: POST `/files/write` (FormData: brain, path=<pathTran>, content). Nút báo "✓ Đã lưu".
5. Đóng: Esc, nút ✕, bấm nền mờ. Lưu nhanh: Ctrl+S.

Brain lấy từ `window.currentBrainPath()` (nguồn chat đang dùng). `esc` định nghĩa cục bộ trong
module.

### Nối chat vào editor (sửa handler trong `dashboard/chat-render.js`)

Handler click cho `a.jv-floc` (link file/thư mục vault):

- Giữ nhánh Ctrl/Cmd/Shift/Alt/giữa-chuột → để trình duyệt mở deep-link `#open=` tab mới (như cũ).
- Nếu anchor CHỨA `<img>` (ảnh inline) → giữ hành vi cũ (`JavisOpenFiles`).
- Ngược lại xét path: có đuôi file (đoạn cuối chứa dấu chấm) → gọi `window.JavisEditFile(path)`;
  không đuôi (thư mục) → `JavisOpenFiles(path)` như cũ.
- Dự phòng: nếu `window.JavisEditFile` chưa nạp → rơi về `JavisOpenFiles`.

### Nạp script (sửa `dashboard/index.html`)

Thêm `<script src="file-editor.js"></script>` cạnh chỗ nạp `chat-render.js`.

## Luồng dữ liệu

Bấm link .md → handler chat-render → `JavisEditFile(brainRel)` → (fetch home nếu chưa cache) →
`/files/read` → dựng textarea → sửa → Ctrl+S/Lưu → `/files/write` (path trần) → báo đã lưu.

## Xử lý lỗi

- Fetch home lỗi: dùng tiền tố rỗng (đọc vẫn chạy nhờ dual-convention; lưu đúng khi trần == brain).
  Nếu lưu trả lỗi thì nút hiện "⚠ Lỗi", không nuốt im.
- `/files/read` lỗi/không đọc được: hiện thông báo + link "Mở tab mới" / "Tải về" qua `/files/raw`.
- File không sửa được (nhị phân): hiện nút Tải, không cho sửa.

## Kiểm thử

- Đơn vị (node): thêm test cho `mdToHtml` (chat-render.js đã export) kiểm URL trần thành link,
  và không phá code block / link markdown / inline code sẵn có.
- Thủ công (trình duyệt): bấm link .md trong chat bung khung sửa, sửa, Ctrl+S lưu, mở lại thấy đổi;
  bấm URL trần mở tab mới; bấm link thư mục vẫn nhảy trang Tệp tin; ảnh inline bấm như cũ.

## Danh sách file đụng tới

- `dashboard/file-editor.js` (MỚI): khung sửa modal + `window.JavisEditFile`.
- `dashboard/chat-render.js` (SỬA): autolink URL trần; nối click file → editor.
- `dashboard/index.html` (SỬA): nạp file-editor.js.
- Test: thêm case autolink cho mdToHtml (file test cạnh chat-render).
