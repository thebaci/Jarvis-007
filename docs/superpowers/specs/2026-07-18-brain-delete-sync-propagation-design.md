# Thiết kế: Xóa não lan sang mọi máy qua Sync (tombstone + thùng rác 30 ngày)

Ngày: 2026-07-18
Trạng thái: Đã duyệt thiết kế, chờ lập kế hoạch triển khai.

## 1. Bối cảnh và vấn đề

Jarvis 007 đồng bộ 2 chiều toàn bộ thư mục `brains/` giữa nhiều máy qua một repo GitHub riêng
(`git_brain.sync_brains`, mô hình `máy A ⇄ repo ⇄ máy B/VPS`). Topology thực tế của user:
**2+ máy chạy song song**, đều có thể sửa/xóa.

Sync hiện theo chính sách "xóa KHÔNG BAO GIỜ thắng bản còn sống" để chống mất dữ liệu:
- `_merge_with_policy` (`git_brain.py`): khi một bên xóa một bên sửa cùng file, GIỮ bản sửa.
- Khối tự-vá trong `_sync_brains_locked` (dòng ~663-669): file có trong mirror HEAD nhưng thiếu
  trong `brains/` thì luôn áp về (khôi phục).
- Nhánh restore (`_integrate_remote` khi `pre_head is None`) và merge lịch-sử-rời
  (`--allow-unrelated-histories`) kéo nguyên bản remote về.

Hệ quả: **một não đã bị xóa có chủ đích ở máy A có thể bị "hồi sinh"** khi sync với máy B hoặc
remote còn giữ nó. User muốn: xóa não là hành động cố ý (UI bắt gõ ĐÚNG tên dự án mới cho xóa),
nên nó phải **lan việc xóa sang mọi máy**, không bị hồi sinh.

## 2. Mục tiêu và ngoài phạm vi

Mục tiêu:
- Một lần xóa não có chủ đích (qua `/brains/delete`, đã gõ đúng tên) phải lan sang mọi máy đồng bộ,
  ghi đè đúng chính sách "xóa không thắng" cho RIÊNG lần xóa đó.
- KHÔNG nới lỏng lá chắn chống mất dữ liệu chung: mọi trường hợp folder biến mất mà KHÔNG phải do
  xóa có chủ đích (volume chưa mount, engine ghi dở, máy mới trống) vẫn được bảo vệ như cũ.
- Mỗi máy giữ một bản sao cục bộ (thùng rác) 30 ngày để cứu hộ; khi xóa báo rõ điều này.

Ngoài phạm vi (v1):
- UI "Thùng rác" để bấm khôi phục. v1 khôi phục bằng tay (chuyển folder từ thùng rác về `brains/`).
- Đồng bộ thùng rác giữa các máy (thùng rác là CỤC BỘ từng máy, không lên git).
- Kênh push realtime để máy khác xóa tức thì (vẫn dựa trên chu kỳ sync của từng máy).

## 3. Quyết định thiết kế đã chốt

- **Hướng A**: giấy báo tử (tombstone) đồng bộ + thùng rác cục bộ. (Hướng B "xóa luôn thắng" bị
  loại vì phá lá chắn; Hướng C "xóa thẳng remote không tombstone" bị loại vì máy B vẫn hồi sinh.)
- Thùng rác giữ **30 ngày**, tự dọn. Khi xóa, lời xác nhận báo rõ "giữ trong thùng rác 30 ngày".
- Tombstone giữ **180 ngày** (lâu hơn thùng rác) để máy lỡ offline lâu quay lại không hồi sinh não.
  Đây là hằng số nội bộ, không lộ ra UI.

## 4. Kiến trúc (các thành phần)

### 4.1 Tombstone store (đồng bộ)
- Vị trí: `<BRAINS_DIR>/.javis-tombstones/<tên>.json` - tên file dùng ĐÚNG tên folder não (kết quả
  `_safe_brain_name`, đã bỏ ký tự nguy hiểm `\/:*?"<>|` + cắt 60 ký tự, giữ dấu tiếng Việt). Một file
  cho mỗi não. Vì tên folder não là duy nhất và đã an toàn hệ thống file nên tên tombstone không đụng
  nhau, không cần slug riêng.
- Vì sao một-file-mỗi-tên: khi merge giữa các máy, các file khác tên không đụng nhau -> git gộp
  sạch, hợp nhất tự nhiên mọi lệnh xóa (union). Xóa lại cùng tên thì ghi đè file (ts mới hơn).
- Dot-dir này đồng bộ theo repo (`_backup_skip` chỉ bỏ `.git`, thư mục conversations/log, `.lock`,
  `.tmp` - KHÔNG bỏ dot-dir gốc khác) và KHÔNG hiện thành não (`/brains` bỏ tên bắt đầu bằng `.`).
  Sync đọc/ghi đường dẫn tiếng Việt qua `core.quotepath=false` + `-z` (đã có trong `git_brain`).
- Định dạng JSON (`name` = tên folder não, dùng để định vị thư mục lúc áp tombstone):
  ```json
  { "name": "<tên folder não>", "deleted_at": 1752800000, "host": "<host tag>", "v": 1 }
  ```

### 4.2 Thùng rác cục bộ (KHÔNG đồng bộ)
- Vị trí: `<STATE_DIR>/brain-trash/<tên>__<YYYYMMDD-HHMMSS>/` (nằm NGOÀI `brains/` nên không lên git;
  mỗi máy một thùng riêng). `STATE_DIR` = `server/` local, `/data` trên Docker - đều tách khỏi
  `brains/` (local `<project>/brains`, Docker mount `/brains`).
- Dọn tự động: xóa mục quá 30 ngày, chạy đầu mỗi lần sync (`_sync_brains_locked`). Không GC lúc
  khởi động (giữ phạm vi gọn); sync chạy đủ thường xuyên để thùng rác không phình.

### 4.3 Bước áp tombstone trong sync
- Hàm mới `_apply_tombstones(brains_dir, mirror_dir, trash_dir, sync_start)` trong `git_brain.py`,
  gọi trong `_sync_brains_locked` SAU `_integrate_remote` (mirror đã gộp tombstone từ mọi máy),
  TRƯỚC bước push. Trả về danh sách não đã xóa + lỗi (nếu có) để giữ bất biến "áp không trọn -> không push".

## 5. Luồng dữ liệu chi tiết

### 5.1 Luồng xóa (`server/main.py`: `/brains/delete`)
Giữ nguyên các rào cũ (chặn xóa não mặc định, `confirm == tên`, chỉ xóa folder trong `BRAINS_DIR`).
Thay đổi phần thực thi:
1. `_safe_brain_name(name)` -> `root = BRAINS_DIR/<name>`.
2. Chuyển `root` vào thùng rác: `<STATE_DIR>/brain-trash/<name>__<ts>/` (dùng `shutil.move`; nếu
   khác ổ đĩa thì copytree + rmtree). KHÔNG `rmtree` cứng nữa.
3. Ghi tombstone `<BRAINS_DIR>/.javis-tombstones/<name>.json` (name = tên folder não) với
   `deleted_at = now`, `host`.
4. Kích hoạt một lần sync nền best-effort (nếu backup đã cấu hình) để remote nhận lệnh xóa + tombstone
   ngay, thay vì chờ chu kỳ 6 tiếng. Không chặn response; lỗi sync không làm hỏng việc xóa cục bộ.
5. Trả `{ok: true, name, trashed: true}`.

Frontend (`dashboard/brains-ui.js` `deleteBrain`): đổi lời xác nhận cuối thành thông báo rõ
"sẽ chuyển vào thùng rác, tự xóa hẳn sau 30 ngày, và đồng bộ việc xóa sang các máy khác".

### 5.2 Luồng sync (`git_brain.py`: `_sync_brains_locked`)
Thứ tự mới (chèn bước áp tombstone), giữ nguyên phần còn lại:
1. Dọn thùng rác quá 30 ngày (đầu hàm).
2. `_sync_mirror(brains_dir, mirror)` + `git add -A` + commit backup (như cũ). Vì đã chuyển não vào
   thùng rác ở bước xóa nên `_sync_mirror` tự prune não khỏi mirror + tombstone mới được add vào.
3. fetch + `_integrate_remote` (như cũ) -> mirror gộp mọi tombstone + mọi thay đổi từ remote.
4. **`_apply_tombstones`** (MỚI): với mỗi tombstone trong mirror sau hoà nhập:
   - `bn = tombstone.name`; bỏ qua nếu `bn` là não mặc định (miễn nhiễm) hoặc tên không hợp lệ.
   - Chốt thời gian: nếu `brains_dir/bn` còn tồn tại và có file nào `mtime > deleted_at` -> não được
     dựng/sửa lại có chủ đích sau khi xóa -> BỎ QUA + gỡ file tombstone (superseded).
   - Ngược lại (xóa dứt khoát):
     - `brains_dir/bn` (nếu còn): chuyển vào thùng rác (giữ `BrainLock(brains_dir/bn)` khi thao tác;
       không lấy được lock sau timeout thì bỏ qua vòng này, lần sau áp lại - không xóa mù).
     - `mirror/bn` (nếu còn): `git rm -r --` để stage việc xóa.
   - Nếu có bất kỳ `git rm` nào: commit mirror `sync: áp tombstone xóa <n> não` để HEAD phản ánh
     việc xóa -> khối tự-vá (5.3) không hồi sinh.
   - Trả `{deleted: [...], failed: [...]}`. `failed` không rỗng -> giữ bất biến: rollback mirror +
     KHÔNG push (giống nhánh `_apply_back` lỗi hiện có).
5. Khối tự-vá (dòng ~663-669) + `_apply_back` + push: như cũ. Vì tombstone đã xóa não khỏi mirror
   HEAD, tự-vá không thấy nó "thiếu trong brains" nữa (nó đã bị xóa hợp lệ ở cả hai).

Máy B ở lần sync của nó: fetch nhận tombstone (bước 3) -> `_apply_tombstones` xóa não ở B (chuyển vào
thùng rác của B) + git rm khỏi mirror B -> push (nếu B là bên đẩy) hoặc đơn giản là đã đồng thuận với
remote. Việc xóa lan mà không cần B từng biết lệnh xóa gốc.

### 5.3 Vì sao không còn hồi sinh
- modify/delete "giữ bản sửa": kể cả khi merge giữ lại vài file của não, `_apply_tombstones` chạy SAU
  sẽ xóa dứt khoát toàn bộ subtree não đó (vì có tombstone).
- Khối tự-vá: chạy SAU khi tombstone đã commit việc xóa khỏi mirror HEAD -> không thấy "thiếu".
- Nhánh restore/lịch-sử-rời: sau khi kéo bản remote về, tombstone (cũng nằm trong bản remote đó) được
  áp -> xóa lại các não có tombstone.

## 6. Rào an toàn và bất biến

- Tombstone chỉ xóa được một não là **con trực tiếp** của `brains_dir` (kiểm tra `resolve()` nằm
  đúng dưới `brains_dir`, giống guard trong `/brains/delete` hiện tại). Không bao giờ đụng rộng hơn.
- **Não mặc định miễn nhiễm**: `_apply_tombstones` bỏ qua tombstone trỏ tên não mặc định. Luồng xóa
  cũng đã chặn xóa não mặc định nên tombstone đó không thể sinh ra một cách hợp lệ; đây là chặn 2 lớp.
- **Chốt thời gian**: não có file mới hơn `deleted_at` được coi là dựng lại có chủ đích -> không giết.
- **Không push nửa vời**: chuyển-vào-thùng-rác hoặc git rm lỗi -> `failed` -> rollback mirror, hoãn push.
- Tombstone chỉ sinh ra từ `/brains/delete` (đã gõ đúng tên). Không endpoint nào khác tạo tombstone.
- `_safe_brain_name` làm sạch tên trước mọi thao tác đường dẫn.

## 7. Kiểm thử

File test mới ở `server/` (theo khuôn test hiện có: standalone, chạy `python test_*.py`, không mạng
thật - dùng remote `file://` cục bộ). Các ca:
1. **Lan xóa**: dựng brains_A, brains_B, mirror_A, mirror_B, remote bare `file://`. Tạo não "Foo" ở cả
   hai, sync cho đồng bộ. Xóa "Foo" ở A (tombstone + move trash), sync A -> push. Sync B -> "Foo" bị
   xóa ở B, nằm trong thùng rác B, remote không còn "Foo".
2. **Chốt thời gian**: sau khi có tombstone "Foo", tạo lại "Foo" mới (file mtime > deleted_at) rồi
   sync -> "Foo" mới KHÔNG bị xóa, tombstone bị gỡ.
3. **Bảo vệ khi KHÔNG tombstone**: xóa thủ công folder "Bar" khỏi brains_B (không qua endpoint, không
   tombstone) rồi sync -> "Bar" được khôi phục (lá chắn cũ nguyên vẹn), không bị xóa vĩnh viễn.
4. **Não mặc định miễn nhiễm**: tombstone giả trỏ não mặc định -> `_apply_tombstones` bỏ qua, não còn.
5. **Endpoint xóa**: gọi `/brains/delete` -> não vào thùng rác `<STATE_DIR>/brain-trash/...`, tombstone
   được ghi, không còn trong `brains/`.
6. **Dọn thùng rác**: tạo mục thùng rác giả có mtime > 30 ngày -> sau khi chạy dọn thì bị xóa; mục mới
   thì giữ.

## 8. Rủi ro và câu hỏi mở

- Máy offline > 180 ngày quay lại vẫn có thể hồi sinh não (tombstone đã bị dọn). Chấp nhận được: hiếm,
  và có thể nới hằng số nếu cần. Không lộ ra UI.
- Xung đột hiếm: hai máy cùng xóa cùng một tên gần như đồng thời -> hai tombstone cùng slug, merge theo
  policy sẵn có (nội dung gần như nhau, không mất mát). Không cần xử lý thêm.
- Eager sync lúc xóa có thể trùng với sync theo lịch: đã có `_SYNC_LOCK` (non-blocking) nên phiên trùng
  bị bỏ qua an toàn, tombstone vẫn đi ở phiên kế tiếp.
