# Update triệt để cho Jarvis 007 - Thiết kế

Ngày: 2026-07-18
Trạng thái: đã duyệt thiết kế, chuẩn bị lập kế hoạch.

## Mục tiêu

Làm cho tính năng cập nhật của Jarvis 007 chắc chắn và an toàn: người dùng bấm một nút
"Cập nhật ngay" là lên được bản mới trên mọi môi trường, trong lúc chạy hiện tiến
trình rõ ràng, và nếu bản mới lỗi thì có đường quay về bản cũ.

Phạm vi đã chốt với chủ dự án:
- KHÔNG làm tự động update nền (đã cân nhắc và loại).
- KHÔNG viết updater sidecar cho Docker (để dành cho VPS tự quản sau này).
- Môi trường ưu tiên: Docker (Hostinger/VPS).
- Rollback Docker theo Hướng B (có hướng dẫn), không phải rollback tự động trong container.

## Bối cảnh hiện trạng

Đã có sẵn (không làm lại từ đầu):
- `GET /version` (server/main.py ~3688): đọc `VERSION` local, so với
  `raw.githubusercontent.com/blogminhquy/javis-os/main/VERSION`, so kiểu semver,
  trả `{current, latest, update_available, mode, can_self_update, error}`.
- `POST /update` (~3712): theo mode. Docker gọi Watchtower `http://watchtower:8080/v1/update`
  (chỉ khi Watchtower đang chạy); Windows ghi `_selfupdate.bat` (git pull + relaunch)
  chạy tách rời; Native chạy `bash update.sh native`.
- `GET /changelog` (~3859): parse CHANGELOG.md local + đối chiếu GitHub.
- `GET /health` (~1436): trả 200 khi server sống (kèm trạng thái Claude CLI).
- Frontend `dashboard/console.js`: `ovLoadVersion()` (~1379) + handler nút cập nhật
  (~1411) poll `/version` tới khi đổi phiên bản rồi reload; trang changelog (~336).
- Autostart Windows (HKCU Run key) + `start-javis.vbs` (kill bản cũ + chạy nền
  `.venv\Scripts\python.exe server\main.py`).
- CI `.github/workflows/docker-publish.yml`: push main -> build + đẩy GHCR tag
  `:latest` và `:<git-sha>`.
- Docker: app KHÔNG mount docker socket (bảo mật). Hostinger dùng
  `docker-compose.hostinger.yml` (KHÔNG có Watchtower, cập nhật bằng Redeploy).
  `docker-compose.yml` có service Watchtower nằm trong profile `update` (mặc định tắt).
  Dockerfile + compose đều có HEALTHCHECK gọi `/health`.

## Bốn lỗ hổng cần vá

1. Windows updater THIẾU `pip install`. `_selfupdate.bat` chỉ git pull + relaunch.
   Bản mới thêm thư viện Python là app bật lại sẽ crash. (Bản native `update.sh` có cài.)
2. Cây git bẩn làm `git pull --ff-only` abort im lặng -> update thất bại mà UI chỉ
   báo mơ hồ "server lên lại nhưng phiên bản chưa đổi".
3. Không có kiểm tra sức khoẻ + rollback. Bản mới lỗi boot thì app chết, không tự quay lại.
4. Trải nghiệm update nghèo: không hiện tiến trình theo bước, không hiện changelog bản
   mới trước khi bấm, không có đường lùi rõ ràng khi hỏng.

Sự thật kỹ thuật định hình thiết kế: Watchtower KHÔNG tự rollback (chủ dự án xác nhận
không thêm tính năng này). App trong Docker không có quyền Docker nên không tự đổi/lùi
image. Do đó rollback tự động thật chỉ khả thi ở bản git checkout (Windows/native);
Docker dùng rollback có hướng dẫn.

## Kiến trúc giải pháp

Chia theo bốn khối, giao tiếp qua các file trạng thái trên STATE_DIR và các endpoint HTTP.

### Khối 1 - CI: tag phiên bản (nền của Hướng B)

`docker-publish.yml` thêm tag `${IMAGE}:<version>` (đọc từ file VERSION) cạnh `:latest`
và `:<sha>`. Kết quả: GHCR luôn có một tag phiên bản cố định, dễ đọc, để pin khi lùi bản.

- Đầu vào: file VERSION ở gốc repo.
- Đầu ra: thêm dòng tag trong step "Build & push".
- Phụ thuộc: không.

### Khối 2 - Trạng thái update (nguồn sự thật dùng chung)

File `STATE_DIR/update_state.json` là nguồn sự thật, SỐNG QUA restart/recreate container
(nằm trên volume /data ở Docker). Schema:

```json
{
  "phase": "idle|preparing|pulling|installing|restarting|health_check|rolling_back|done|error",
  "result": "success|rolled_back|pull_failed|rollback_failed|error|null",
  "old_version": "0.9.78",
  "target_version": "0.9.79",
  "old_sha": "<git sha trước khi pull, chỉ mode git>",
  "previous_version": "0.9.78",
  "last_good_version": "0.9.79",
  "stashed": false,
  "started_at": "<iso>",
  "finished_at": "<iso|null>",
  "error": "<chuỗi lỗi ngắn|null>"
}
```

- `last_good_version` / `previous_version` do một hook lúc KHỞI ĐỘNG server duy trì:
  đọc file; nếu `last_good_version` khác `current` và `current` mới hơn thì đặt
  `previous_version = last_good_version` cũ, rồi `last_good_version = current`. Nhờ vậy
  mọi mode (kể cả Docker) đều biết "lùi về đâu".
- `phase`/`result`/`error` do updater (Windows/native) hoặc luồng `/update` (Docker) ghi
  trong quá trình cập nhật.
- Helper Python thuần: `_read_update_state()`, `_write_update_state(patch)`,
  `_record_boot_version(current)`. Đây là phần dễ test nhất.

### Khối 3 - Backend: /update, /update/status, /version

`POST /update` viết lại theo mode:

- Windows (git checkout): server ghi `update_state` (preparing, old_version, old_sha
  từ `git rev-parse HEAD`, target=latest), rồi spawn TÁCH RỜI script
  `server/updater/win_update.ps1` (PowerShell, dễ làm HTTP poll + logic hơn .bat)
  với tham số: root, đường dẫn python .venv, port, old_sha, target, logfile, statefile.
  Không còn sinh .bat inline.
- Native (git checkout): spawn `bash update.sh native` như cũ nhưng update.sh được nâng.
- Docker có Watchtower: trigger như cũ, ghi update_state (phase=restarting,
  target=latest). Container mới bật -> hook boot chốt success.
- Docker không Watchtower (Hostinger): trả `ok:false` kèm hướng dẫn Redeploy GIÀU hơn:
  nêu `current`, `latest`, và tag phiên bản cũ `previous_version` để pin khi cần lùi.
- Chống chạy trùng: nếu `phase` đang dở và `started_at` gần đây thì trả "đang cập nhật rồi".

`GET /update/status` (mới): trả nội dung `update_state.json` + ~50 dòng cuối `update.log`.
UI poll cái này để vẽ tiến trình và hiện kết quả (kể cả sau khi server restart xong).

`GET /version`: thêm trường `previous_version` (từ update_state) để UI biết đích lùi.
Giữ nguyên các trường cũ.

Script updater (Windows ps1 và native update.sh) làm chung một chuỗi:

1. preparing: đảm bảo đã có old_sha, target.
2. pulling: xử lý cây git bẩn an toàn - `git stash push -u? KHÔNG` (u kéo cả file rác);
   dùng `git stash` (chỉ tracked), đặt `stashed=true` nếu có cất; `git pull --ff-only`.
   KHÔNG tự `stash pop` (tránh xung đột với code mới) - để lại stash cho user tự khôi
   phục, ghi `stashed=true` để UI báo. Pull lỗi -> result=pull_failed, relaunch bản CŨ
   (code chưa đổi), dừng.
3. installing: `pip install -r requirements.txt` vào .venv (Windows: đây là bước đang thiếu).
4. restarting: dừng bản đang chạy rồi bật bản mới (Windows dùng stop-javis.bat +
   start-javis.vbs; native dùng systemctl restart javis nếu có).
5. health_check: poll `http://127.0.0.1:<port>/health` tới ~90s. Thành công =
   /health trả 200 VÀ `/version.current == target`. Nếu /health không lên trong 90s -> lỗi.
6. Kết luận:
   - Khoẻ + đúng bản: phase=done, result=success.
   - /health không lên (bản mới hỏng): phase=rolling_back, `git reset --hard <old_sha>`,
     pip install (bản cũ), restart, poll lại. Lên được -> result=rolled_back; vẫn hỏng ->
     result=rollback_failed (ghi log để cứu tay).
   - /health lên nhưng version chưa đổi (pull không áp được dù báo ok): coi là cảnh báo,
     server vẫn sống (bản cũ), không rollback; result=error kèm ghi chú.

Script chạy DETACHED để sống độc lập khi server bị kill. Mọi bước đều ghi update_state
+ append update.log.

### Khối 4 - Frontend: trải nghiệm update

Trang Tổng quan: panel phiên bản mở rộng.

- Trạng thái thường: hiện `current`, `latest`, mode. Có bản mới thì hiện thêm CHANGELOG
  các bản giữa current và latest (dùng dữ liệu `/changelog`, lọc bản chưa cài) để user
  thấy sắp nhận gì trước khi bấm.
- Nút "Cập nhật ngay": hiện khi `update_available && can_self_update`. Docker không
  Watchtower thì thay bằng khối hướng dẫn Redeploy (giàu hơn: kèm lệnh + tag để lùi).
- Khi bấm: confirm -> POST /update -> vào màn tiến trình.
- Màn tiến trình: thanh bước Chuẩn bị -> Tải code -> Cài thư viện -> Khởi động lại ->
  Kiểm tra sức khoẻ -> Xong. Đổ dữ liệu từ poll `/update/status` (trường `phase`) kết
  hợp `/version`. Có sẵn dòng trấn an: "nếu bản mới lỗi hệ thống sẽ tự quay về bản cũ"
  (mode git) hoặc "có thể lùi về bản cũ theo hướng dẫn" (Docker).
- Trạng thái kết thúc:
  - success -> "Đã cập nhật lên vX" -> tự reload.
  - rolled_back -> "Bản mới vX lỗi, đã tự quay về vY. Xem update.log." (không reload).
  - pull_failed / error -> hiện lỗi + đuôi log + lệnh thủ công.
  - Docker bản mới không lên (version không tới sau lâu) -> panel lùi bản có hướng dẫn:
    pin tag `:<previous_version>` + nút copy lệnh (`docker compose ... pull && up -d`
    hoặc đổi tag rồi Redeploy trên Hostinger).

Giữ nguyên trang changelog hiện có.

## Xử lý lỗi (tóm tắt)

- Cây git bẩn: stash tracked trước khi pull, không auto-pop, báo user đã cất vào stash.
- Thiếu dep mới: bước pip install bắt buộc ở mọi mode git.
- Bản mới crash boot: git mode tự `git reset --hard` về old_sha + restart. Docker: hướng
  dẫn pin previous_version.
- Update chạy trùng: guard theo phase + started_at.
- Mất mạng khi kiểm bản mới: `/version`/`/changelog` vẫn trả phần local.
- Rollback cũng hỏng: giữ nguyên log, báo rõ, để cứu tay (không xoá gì).

## Kiểm thử

- Hàm thuần: `_ver_tuple`, `_ver_newer` (thêm ca), so sánh phiên bản edge cases.
- update_state: round-trip read/write; suy ra `previous_version` khi boot lên bản mới hơn.
- `/update/status`: trả đúng cấu trúc khi có/không có file trạng thái.
- Quyết định rollback: tách helper (vd `_health_ok(port)` + hàm quyết định) và test với
  health giả (mock) -> health đỏ thì báo cần rollback.
- Guard chạy trùng của `/update`.
- Script ps1/sh khó unit-test trên CI: ít nhất lint + kiểm JSON chúng sinh; smoke test tay
  trên máy Windows của chủ dự án.

Chạy test bằng .venv (python hệ thống thiếu lib). Xong test + xanh mới bump VERSION +
CHANGELOG + commit + push origin/main (đúng nếp auto-push của chủ dự án).

## File dự kiến đụng tới

- `.github/workflows/docker-publish.yml` - thêm tag phiên bản.
- `server/main.py` - viết lại `POST /update`; thêm `GET /update/status`; thêm
  `previous_version` vào `/version`; hook boot ghi version; helper update_state; bỏ sinh
  `_selfupdate.bat` inline.
- `server/updater/win_update.ps1` - script updater Windows mới (nhận tham số).
- `update.sh` - thêm lưu SHA + health poll + git reset rollback.
- `dashboard/console.js` (+ CSS liên quan) - panel update + màn tiến trình + panel lùi bản.
- `server/tests/test_update.py` - test như trên.
- `VERSION` + `CHANGELOG.md` - bump khi hoàn tất.

## Ngoài phạm vi (không làm lần này)

- Tự động update nền (poller + công tắc bật/tắt + kênh + quiet hours).
- Updater sidecar có socket cho Docker (rollback tự động trong container).
- Đổi mô hình deploy Hostinger khỏi Redeploy.
