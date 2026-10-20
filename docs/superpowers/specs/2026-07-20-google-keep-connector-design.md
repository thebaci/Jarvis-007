# Thiết kế: Connector Google Keep

Ngày: 2026-07-20
Trạng thái: chờ duyệt

## Mục tiêu

Cho Jarvis 007 đọc và thao tác note trong Google Keep, đấu qua MCP server cộng đồng
[feuerdev/keep-mcp](https://github.com/feuerdev/keep-mcp) (PyPI `keep-mcp` 0.3.1, Python >=3.10).

## Bối cảnh: vì sao phải dùng master token

Google Keep KHÔNG có API công khai cho tài khoản gmail cá nhân. API chính chủ (Keep API) chỉ mở
cho Google Workspace Enterprise kèm service account + domain-wide delegation. Tài khoản dùng ở đây
là gmail thường, nên đường duy nhất là thư viện không chính thức `gkeepapi`, vốn đòi
**Google Master Token**.

Master token KHÔNG phải OAuth token giới hạn phạm vi. Nó là token cấp thiết bị Android, dạng
`aas_et/...`, [có toàn quyền trên tài khoản và tương đương mật khẩu](https://gkeepapi.readthedocs.io/en/latest/):
nắm nó là mint được token cho gần như mọi dịch vụ Google khác (Gmail, Drive, Photos, Contacts).

Jarvis 007 mã hoá secret at rest bằng Fernet qua `secrets_store.encrypt_map` (xem `mcp_store.save`),
nên token không nằm plaintext trên đĩa. Nhưng mã hoá at rest không đổi được bản chất
"token = toàn quyền tài khoản", và token sẽ nằm cả trên VPS Hostinger.

Rủi ro này đã được nêu rõ với người dùng và người dùng chấp nhận, chọn dùng tài khoản chính.

## Quyết định đã chốt

1. **Phạm vi thao tác**: bật `UNSAFE_MODE` để Jarvis 007 sửa được MỌI note, kể cả note viết tay
   trong app Keep (mặc định của server chỉ cho sửa note nó tự tạo, gắn nhãn `keep-mcp`).
2. **Tài khoản**: dùng tài khoản chính, không lập tài khoản phụ.
3. **Runner**: `uvx` chứ không `pipx` như README gợi ý, cho khớp các connector stdio sẵn có
   (`google-sheets`, `tiktok-ads`). `uv` đã có sẵn qua `requirements.txt`, không cần thêm gì (xem dưới).
4. **`UNSAFE_MODE` là ô nhập tuỳ chọn**, KHÔNG hardcode trong catalog.

Về quyết định 4, lý do: hardcode `UNSAFE_MODE=true` sẽ bật sẵn chế độ sửa-mọi-note cho mọi người
fork Jarvis 007 về, trái nguyên tắc đã chốt là năng lực chạm dữ liệu cá nhân phải opt-in mặc định TẮT.
Để thành ô nhập thì người dùng này vẫn được đúng cái họ chọn (gõ `true`), bản fork vẫn sạch, và
công tắc nguy hiểm hiện rõ trên trang Kết nối nên sau này gỡ được. Cách này cũng KHÔNG cần sửa lõi,
vì `mcp_catalog.build_env` hiện chỉ dựng env từ `auth.fields` có khai `env`, chưa hỗ trợ env tĩnh
ở cấp connector.

## Thay đổi 1: entry catalog

Thêm vào `system/mcp-catalog.json`, mảng `connectors`. Không sửa `mcp_hub`, `mcp_store`,
`mcp_catalog`, hay dashboard: toàn bộ hạ tầng đã sẵn (form đăng nhập tự sinh từ `auth.fields`,
secret tự mã hoá, ba mức quyền tự áp qua `tool_meta`).

Icon dùng emoji thay vì file logo, theo tiền lệ `google-search-console` (`🔍`) và
`google-workspace` (`📧`). Tránh phải tải asset có nhãn hiệu vào repo.

Lưu ý: `requires` là metadata THUẦN TÀI LIỆU, không có chỗ nào trong code đọc nó (đã grep
`server/*.py` và `dashboard/console.js`). `lark` khai `requires: {node: ">=18"}` cũng chỉ để đọc.
Giữ lại cho khớp tiền lệ và để người sau biết connector cần gì, nhưng ĐỪNG trông đợi nó chặn
được việc thiếu `uv`. Cái thật sự bảo đảm `uv` có mặt là dòng `uv>=0.5` trong `requirements.txt`.

```json
{
  "id": "google-keep",
  "name": "Google Keep",
  "icon": "📒",
  "category": "Văn phòng",
  "description": "Đọc và sửa ghi chú Google Keep: tìm note, tạo note/danh sách việc, gắn nhãn, ghim, lưu trữ. Chạy local qua thư viện không chính thức - cần Google master token.",
  "status": "beta",
  "transport": "stdio",
  "command": "uvx",
  "args": ["--from", "keep-mcp", "python", "-m", "server"],
  "requires": { "uv": true },
  "auth": {
    "type": "apikey",
    "fields": [
      {
        "key": "google_email",
        "label": "Email Google",
        "placeholder": "ten@gmail.com",
        "env": "GOOGLE_EMAIL"
      },
      {
        "key": "master_token",
        "label": "Google master token (aas_et/...)",
        "placeholder": "aas_et/...",
        "env": "GOOGLE_MASTER_TOKEN"
      },
      {
        "key": "unsafe_mode",
        "label": "Cho sửa MỌI note - gõ true nếu muốn (để trống = chỉ sửa note do Jarvis 007 tạo)",
        "placeholder": "để trống cho an toàn",
        "optional": true,
        "env": "UNSAFE_MODE"
      }
    ],
    "guide": "Google Keep KHÔNG có API chính chủ cho gmail thường nên phải dùng master token. CẢNH BÁO: token này có TOÀN QUYỀN tài khoản Google của bạn (Gmail, Drive, Photos...), tương đương mật khẩu - đừng chia sẻ cho ai. Lấy 1 lần: (1) Bật xác minh 2 bước cho tài khoản. (2) Vào myaccount.google.com/apppasswords tạo App Password 16 ký tự. (3) Chạy lệnh này trong terminal (cần cài uv: winget install astral-sh.uv): uv run --no-project --with gpsoauth python -c \"import gpsoauth; print(gpsoauth.perform_master_login('EMAIL_CUA_BAN','APP_PASSWORD_16_KY_TU','0123456789abcdef')['Token'])\" (4) Dán chuỗi bắt đầu bằng aas_et/ vào ô Master token. Ô cuối để trống thì Jarvis 007 chỉ sửa được note do chính nó tạo; gõ true thì Jarvis 007 sửa được mọi note kể cả note bạn viết tay.",
    "guide_url": "https://github.com/feuerdev/keep-mcp"
  },
  "validate": { "tool": "list_labels", "args": {} },
  "tool_meta": {
    "read": ["find", "get_note", "list_labels", "list_note_collaborators", "list_note_media"],
    "write": [
      "create_note", "create_list", "update_note",
      "add_list_item", "update_list_item", "delete_list_item",
      "set_note_color", "pin_note", "archive_note", "restore_note",
      "create_label", "add_label_to_note", "remove_label_from_note"
    ],
    "danger": [
      "trash_note", "delete_note", "delete_label",
      "add_note_collaborator", "remove_note_collaborator"
    ]
  },
  "default_perm": "readonly",
  "risk": "Kết nối này dùng Google MASTER TOKEN - token có TOÀN QUYỀN tài khoản Google (Gmail, Drive, Photos), không phải OAuth giới hạn phạm vi. Mức Ghi nháp cho Jarvis 007 tạo/sửa note, ghim, lưu trữ, gắn nhãn thật trong Keep. Mức Toàn quyền thêm quyền VỨT/XOÁ note và CHIA SẺ note cho người khác. Nếu đã gõ true vào ô UNSAFE_MODE thì Jarvis 007 đụng được cả note bạn viết tay, không chỉ note nó tạo."
}
```

### Cách gọi: vì sao KHÔNG phải `uvx keep-mcp`

Bản thiết kế đầu tiên khai `args: ["keep-mcp"]` theo README. Kiểm chứng thực tế cho thấy nó HỎNG,
và hỏng theo kiểu âm thầm nên đáng ghi lại.

Package `keep-mcp` 0.3.1 khai console script tên `mcp` (`server.cli:main`). Nhưng chính dependency
của nó, MCP Python SDK (`mcp` 1.28.1), cũng khai console script tên `mcp` (`mcp.cli:app`). Hai cái
trùng tên nên cài xong thì SDK thắng.

Hậu quả theo từng cách gọi:

- `uvx keep-mcp` → uv báo lỗi thẳng: "An executable named `keep-mcp` is not provided by package
  `keep-mcp`". Hỏng ồn ào, dễ phát hiện.
- `uvx --from keep-mcp mcp` → CHẠY, nhưng chạy nhầm sang CLI của MCP SDK ("MCP development tools",
  các lệnh version/dev/run). Hỏng ÂM THẦM, đây mới là cái bẫy: nó không báo lỗi gì cả.
- `uvx --from keep-mcp python -m server` → đúng server keep-mcp, qua `server/__main__.py`.

Đã xác minh bằng bắt tay MCP stdio thật (initialize + tools/list, không cần credential):
server trả về ĐÚNG 23 tool, trùng khít danh sách README, không có tool ẩn nào ngoài `tool_meta`.
Đây là điều quan trọng với bảo mật, vì tool không khai trong `tool_meta` sẽ rơi xuống heuristic
`WRITE_HINTS` và có thể lọt qua lớp chặn.

Có ghi chú `_args_doc` ngay trong entry catalog để người sau đừng "dọn gọn" nó về `uvx keep-mcp`.

### Phân loại tool và lý do

`mcp_catalog.allowed()` chặn dựa vào `tool_meta`, đây là lớp cứng không phụ thuộc prompt, nên
phân loại phải khai tường minh chứ không dựa heuristic `WRITE_HINTS`.

Hai chủ ý đáng chú ý:

- `restore_note` xếp **write** còn `trash_note` xếp **danger**. Nghĩa là ở mức Ghi nháp, Jarvis 007
  luôn gỡ lại được note bị vứt nhầm nhưng không tự vứt được. Bất đối xứng này là cố ý.
- `add_note_collaborator` và `remove_note_collaborator` xếp **danger** vì chúng chia sẻ note ra
  người khác, tức là rò dữ liệu ra ngoài, khác về chất với sửa nội dung trong nhà.

`archive_note` xếp write vì không phá huỷ (note vẫn còn, chỉ ẩn khỏi danh sách chính).
`delete_list_item` xếp write vì xoá một dòng trong checklist là thao tác soạn thảo bình thường.

### Về khối `validate`

Dùng `list_labels` (không tham số, thuần đọc) để nút Test thực sự chạm tới Keep API, chứng minh
master token còn sống chứ không chỉ chứng minh server khởi động được.

KHÔNG khai `label_paths` vì chưa biết chắc hình dạng response của `list_labels`. Theo
`mcp_hub.validate_connection`, thiếu `label_paths` chỉ làm nhãn hiển thị rỗng, không làm hỏng
kết nối. Đoán sai `label_paths` cũng không làm Test fail, nhưng khai bừa thì vô nghĩa.

Cần lưu ý: khối `validate` này CHƯA được kiểm chứng thực tế vì cần master token thật để chạy.
Nếu `list_labels` trả lỗi khi tài khoản chưa có nhãn nào, nút Test sẽ báo fail oan và phải bỏ
khối `validate` đi. Đây là điểm phải xác nhận khi nghiệm thu.

## Thay đổi 2: KHÔNG cần gì cả (mục này từng SAI, giữ lại để rút kinh nghiệm)

Bản thiết kế đầu có mục "thêm uv vào Docker image", lập luận: `Dockerfile` chỉ có `node`, `npx`,
`pip`, không có `uv` lẫn `pipx`, nên `uvx` sẽ chết trên VPS, và 4 connector `uvx` sẵn có
(`google-sheets`, `google-search-console`, `google-ads`, `tiktok-ads`) chắc cũng đang hỏng.

**Lập luận đó SAI.** `uv>=0.5` đã nằm trong `requirements.txt` từ v0.9.0 (commit 856cb19), mà
`Dockerfile` vẫn chạy `pip install --no-cache-dir -r requirements.txt`. Nên image LUÔN có `uv`,
và 4 connector kia chưa bao giờ hỏng vì lý do này. Dòng `pip install uv` thêm vào là thừa, đã gỡ
ở 0.9.112.

Sai ở đâu: chỉ `grep` Dockerfile tìm chữ `uv`, không thấy thì kết luận là thiếu, trong khi dòng
`pip install -r requirements.txt` nằm ngay đó mà chưa hề mở `requirements.txt` ra xem. Suy đoán
từ một phép tìm kiếm hẹp rồi trình bày như sự thật đã kiểm chứng.

Bài học: khi kết luận "X không có trong image", phải lần theo MỌI đường cài đặt (requirements.txt,
apt, npm, COPY từ stage khác), không chỉ grep tên X trong Dockerfile.

Kiến thức về việc `uv` phục vụ các connector `uvx` giờ nằm ở comment trong `requirements.txt`,
đúng chỗ của nó.

## Kiểm thử nghiệm thu

1. `python -c "import json; json.load(open('system/mcp-catalog.json', encoding='utf-8'))"` phải sạch.
2. `mcp_catalog.load()` nhận được `google-keep`; `public_catalog()` trả đủ 3 field.
3. Kiểm phân loại quyền bằng `mcp_catalog.allowed()`:
   - `readonly` + `find` cho qua; `readonly` + `create_note` bị chặn.
   - `safe` + `create_note` cho qua; `safe` + `delete_note` bị chặn.
   - `safe` + `restore_note` cho qua nhưng `safe` + `trash_note` bị chặn (kiểm bất đối xứng có chủ ý).
   - `full` + `add_note_collaborator` cho qua.
   - `mode: suggest` ép mọi thứ về readonly kể cả khi perm là full.
4. Docker: `docker run --rm <image> uvx --version` phải chạy (uv đến từ requirements.txt).
5. Thủ công: đấu kết nối thật trên trang Kết nối, bấm Test, xác nhận `validate` không báo fail oan.
   Rồi thử `find` qua chat.

### Đã kiểm chứng được gì (2026-07-20)

Điểm 1 tới 3 đã thành `server/test_google_keep.py`, 40 check, chạy bằng
`cd server && ../.venv/Scripts/python.exe test_google_keep.py`. Có canary chứng minh
`mcp_catalog.allowed` thật sự đang chặn chứ không trả True vô điều kiện. Đã chạy lại
`test_fb_monitor`, `test_fb_personal`, `test_meta_graph`, `test_meta_pages`, `test_security`,
`test_plugins_host`, `test_skill_caps` đều xanh.

Ngoài ra đã kiểm bằng tay ngoài test suite:

- `pip install uv` trên venv sạch có sinh ra `uvx` chạy được, tức dòng `uv>=0.5` trong requirements.txt là đủ.
- `uvx --from keep-mcp python -m server` khởi động đúng server keep-mcp và nói giao thức MCP.
- Bắt tay `initialize` + `tools/list` trả về đúng 23 tool, khớp `tool_meta`.

### CHƯA kiểm chứng được, phải làm khi nghiệm thu

- **Chưa chạy `uvx` trong Docker thật.** Máy phát triển không cài Docker. Việc `pip install uv`
  cho ra `uvx` mới chỉ được chứng minh trên Windows venv, chưa chứng minh trên `python:3.12-slim`.
  Rủi ro thấp vì uv có wheel manylinux và dòng `uv>=0.5` đã nằm trong requirements.txt từ v0.9.0
  (tức các connector uvx khác đã chạy đường này từ lâu), nhưng vẫn chưa phải sự thật đã kiểm.
- **Khối `validate` chưa chạy thật** vì cần master token. Nếu tài khoản chưa có nhãn nào mà
  `list_labels` trả lỗi thì nút Test sẽ báo fail oan và phải bỏ khối `validate` đi.
- **Chưa gọi tool nào chạm Keep thật.** Toàn bộ kiểm chứng ở trên không cần credential, nên chưa
  chứng minh được master token chạy thông hay `UNSAFE_MODE` có tác dụng đúng như tài liệu.

## Ngoài phạm vi

- Không viết skill hay agent riêng cho Keep. Tool MCP đủ để Jarvis 007 dùng qua chat; có nhu cầu lặp
  lại thật thì mới cân nhắc sau.
- Không đồng bộ hai chiều Keep với Second Brain. Đây là việc lớn và riêng.
- Không tự động hoá bước lấy master token. Bước đó buộc phải người dùng tự làm vì dính App Password.
- Không đụng 4 connector `uvx` đang hỏng ngoài việc thêm `uv` vào image. Kiểm chứng lại chúng là
  việc riêng.

## Nguồn

- [feuerdev/keep-mcp](https://github.com/feuerdev/keep-mcp)
- [gkeepapi: obtaining a master token](https://gkeepapi.readthedocs.io/en/latest/)
- [simon-weber/gpsoauth](https://github.com/simon-weber/gpsoauth)
