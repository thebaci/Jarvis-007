# Thiết kế: đổi credential ngay trên UI (bỏ bước chạy lệnh)

Ngày: 2026-07-20
Trạng thái: chờ duyệt

## Vấn đề

Connector `google-keep` bắt người dùng mở terminal chạy một lệnh dài để đổi App Password lấy
Google master token, rồi dán token vào Jarvis 007. Người dùng hỏi thẳng: "sao khó thế, không làm trên
UI luôn được à?"

Câu trả lời là ĐƯỢC. `gpsoauth.perform_master_login(email, app_password, android_id)` chỉ là một
lời gọi HTTP tới máy chủ xác thực của Google, trả về dict chứa token. Không có gì buộc nó phải
chạy trong terminal; server Jarvis 007 gọi được y hệt.

Hai bước KHÔNG tự động hoá được vì là giao diện bảo mật của chính Google: bật xác minh 2 bước, và
tạo App Password. Google cố tình bắt làm tay. Ngoài ra thì hết.

## Cơ chế: `auth.exchange` khai báo trong catalog

Thay vì nhét logic riêng cho Google Keep vào `main.py`, dựng một bước ĐỔI CREDENTIAL tổng quát
mà catalog tự khai. Lý do: `google-ads` cũng đang bắt chạy `gcloud auth application-default login`
và sẽ cần đúng cơ chế này; nhét cứng cho Keep thì lần sau lại phải sửa lõi.

Catalog khai thêm trong `auth`:

```json
"exchange": {
  "handler": "google_master_token",
  "inputs": ["google_email", "app_password"],
  "output": "master_token",
  "drop": ["app_password"]
}
```

Ý nghĩa: nếu ô `master_token` để trống mà các ô `inputs` đã điền, gọi handler
`google_master_token` để sinh ra giá trị cho `master_token`, rồi XOÁ các field trong `drop` khỏi
dữ liệu trước khi lưu. Nếu `master_token` đã có sẵn thì BỎ QUA hoàn toàn (đường lui thủ công).

Module mới `server/cred_exchange.py`:

- `HANDLERS` = registry tên → hàm. Chỉ handler khai trong module này mới chạy được; catalog KHÔNG
  chỉ định được mã tuỳ ý (tránh biến catalog thành đường thực thi mã).
- `run(connector, fields) -> (fields_moi, loi)` đọc `auth.exchange`, quyết định có chạy không,
  gọi handler, và luôn xoá field `drop` dù thành công hay thất bại.
- Handler `google_master_token` gọi `gpsoauth.perform_master_login`, dịch mã lỗi của Google sang
  tiếng Việt dễ hiểu.

Nối vào `main.py` tại `/connect/add`, ngay TRƯỚC `mcp_store.add_connection`.

## Bất biến bảo mật (phải có test)

1. **App Password KHÔNG BAO GIỜ được lưu.** Nó nằm trong `drop`, bị xoá trước khi
   `mcp_store.add_connection` mã hoá và ghi xuống đĩa.
2. **App Password KHÔNG map ra env.** Field khai không có `env`, nên `build_env` bỏ qua kể cả khi
   vì lý do nào đó nó còn sót lại.
3. **Đổi thất bại thì không lưu gì.** Trả lỗi ngay, không gọi `add_connection`.
4. **Không ghi log giá trị.** Thông báo lỗi chỉ nói LOẠI lỗi, không kèm giá trị người dùng nhập.
5. **Đường lui còn nguyên.** Ai đã có sẵn master token vẫn dán thẳng vào được, không bị ép qua
   App Password. Quan trọng vì Google hay chặn đăng nhập từ IP trung tâm dữ liệu (VPS).

## Thay đổi UI

`openApikeyFlow` hiện KHÔNG gọi `oauthWizard(con)`, nên connector dạng apikey không hiện được nút
bấm mở trang ngoài dù catalog có khai `auth.setup.links`. Thêm lời gọi đó vào, rồi khai cho
`google-keep` một nút mở thẳng `myaccount.google.com/apppasswords`.

Đây là sửa 1 dòng và có lợi cho mọi connector apikey về sau, không riêng Keep.

## Luồng sau khi sửa

1. Bấm nút trong Jarvis 007, mở thẳng trang App Password của Google.
2. Copy chuỗi 16 ký tự.
3. Dán email + chuỗi đó vào Jarvis 007, bấm Kết nối.

Jarvis 007 tự đổi lấy master token, lưu token, vứt App Password. Không còn terminal.

## Rủi ro đã biết

- **Google có thể chặn đăng nhập từ IP VPS.** Đăng nhập từ trung tâm dữ liệu ở nước khác dễ bị
  trả `BadAuthentication` hơn từ máy nhà. Vì vậy đường lui dán tay master token phải giữ, và
  thông báo lỗi phải gợi ý đúng cách xử lý này.
- **App Password đi qua server Jarvis 007.** Không lưu, không log, dùng một lần rồi bỏ. Nhưng khác với
  cách cũ (chuỗi chỉ nằm trên máy người dùng), nên phải nói rõ trong hướng dẫn.
- **Thêm 4 gói phụ thuộc**: gpsoauth, pycryptodomex, requests, charset-normalizer, urllib3. Đã
  kiểm bằng `pip install --dry-run`: KHÔNG đụng tới `fastapi`/`starlette`, nên không dẫm vào cái
  pin nguy hiểm đã ghi chú trong `requirements.txt`.

## Phần 2: google-ads (ĐÃ LÀM, 0.9.114)

`google-ads` bắt cài Google Cloud CLI rồi chạy `gcloud auth application-default login` với một
chuỗi `--scopes=` rất dài, xong đi tìm file JSON trong `%APPDATA%` mà dán vào. Còn cực hơn Keep.

Chìa khoá: file ADC mà gcloud sinh ra thực chất CHỈ LÀ
`{type: authorized_user, client_id, client_secret, refresh_token}`. Mà Jarvis 007 đã có sẵn luồng OAuth
Google hoàn chỉnh đang chạy cho Gmail và Lịch. Nên chỉ cần chạy luồng đó với scope
`https://www.googleapis.com/auth/adwords` rồi TỰ DỰNG file ADC. Không cần gcloud, không chạy lệnh.

Vướng đã gỡ: `oauth_mcp.auth_headers()` sinh HTTP HEADER, tức thiết kế cho `transport: http`.
`google-ads` là `stdio`, chỉ nhận credential qua FILE + biến môi trường. Cầu nối gồm hai mảnh:

1. `oauth_mcp.credentials_file(conn_id, fmt)` - ĐỒNG BỘ, không gọi mạng, ghép refresh_token trong
   kho oauth với client_id/secret trong `mcp_store` thành đúng khuôn ADC. Không refresh ở đây vì
   file chứa refresh_token, chính tiến trình con sẽ tự đổi lấy access token khi cần.
2. `mcp_store.resolved()` - connector khai `oauth_file: {format, env, ext}` thì ghi file 0600 vào
   `connector-files/` rồi trỏ env vào, tái dùng đúng khuôn sẵn có của field `file`.

Import phải TRỄ (`import oauth_mcp` bên trong hàm) vì `oauth_mcp` đã import `mcp_store` ở cấp
module; import thẳng là vòng lặp. Giống cách `mcp_client._oauth_headers` đang làm.

Giữ ô `adc_json` làm ĐƯỜNG LUI cho ai đã lỡ chạy gcloud, và nó THẮNG: nếu user dán tay thì OAuth
không ghi đè (kiểm bằng `not env.get(of["env"])`).

Kèm sửa `openOauthFlow` biết render `multiline` thành textarea. Trước đó nó ép mọi field thành
input một dòng, nên ô dán file ADC sẽ không dùng nổi.

KHÔNG đụng vào `args` của google-ads: nó tải server từ `git+https://...`, mà `google-ads-mcp` trên
PyPI mới ở 0.0.1 (tháng 10/2025) nên đổi sang PyPI là rước rủi ro không cần thiết. Git vẫn là yêu
cầu, nhưng Docker image đã cài sẵn `git`.
