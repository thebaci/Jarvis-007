# Zalo: chính sách theo từng cuộc chat + chatbot trả lời

Ngày: 2026-07-20
Trạng thái: đã chốt thiết kế, đang thực thi
Tiếp nối: [2026-07-20-zalo-listener-design.md](2026-07-20-zalo-listener-design.md)

> **CẬP NHẬT 2026-07-21 - đã BỎ chế độ `chatbot` (tự phản hồi).** Chủ quyết định Jarvis 007
> KHÔNG tự trả lời khách trên Zalo: nó chỉ ĐỌC và BÁO về Telegram. Mọi tin gửi ra đều do
> chủ yêu cầu trực tiếp (tool `javis_zalo_send`). Bốn chế độ còn lại (im-lang, bao-het,
> tu-khoa, nhac-quen) giữ nguyên; file luật cũ `mode: chatbot` tự hạ về `im-lang` (im
> lặng) khi đọc. Phần "chatbot" bên dưới chỉ còn giá trị lịch sử.

## Vấn đề

Bản listener hiện tại là một **bộ lọc thông báo toàn cục**: một bộ từ khoá, một
giờ im lặng dùng chung cho mọi cuộc chat, và mọi tin khớp đều dội về Telegram.

Cái chủ thật sự cần là **chính sách riêng cho từng cuộc chat**:

- Nhóm này: bất kỳ tin nào cũng báo.
- Nhóm kia: chỉ nhắc khi chủ quên trả lời quá 30 phút.
- Nhóm nọ: Jarvis 007 tự trả lời như một chatbot, chỉ báo khi gặp việc vượt khả năng.

Ba chỗ cấu trúc cũ không đáp ứng được: cấu hình toàn cục thay vì theo cuộc chat;
listener không nhớ gì nên không làm được luật theo thời gian; và không có đường
nào để Jarvis 007 trả lời.

## Bối cảnh quan trọng: Jarvis 007 có tài khoản Zalo RIÊNG

Chủ đã tạo một tài khoản Zalo riêng cho Jarvis 007 (không phải tài khoản cá nhân).
Điều này thay đổi mấy thứ:

- Người trong nhóm thấy đúng một tài khoản tên Jarvis 007, nên chuyện "không biết đang
  nói chuyện với máy" gần như hết.
- Chủ chấp nhận rủi ro bot trả lời sai.
- Bot chỉ được trả lời trong những cuộc chat đã bật, không phải mọi nơi trên tài khoản.
- **Luật "30 phút chưa trả lời" trở nên làm được**: chủ trả lời bằng tài khoản riêng
  của mình nên trong nhóm chủ là một thành viên KHÁC, tin của chủ về đầy đủ qua
  webhook. Không còn vướng cờ `--no-self` như phân tích ban đầu.

Điều tài khoản riêng KHÔNG giải quyết: engine vẫn là engine của chủ. Người lạ điều
khiển được nó thì thứ họ chạm tới là MCP, file, bộ nhớ - rủi ro rò dữ liệu, khác
loại với rủi ro trả lời sai.

## Quyết định

| Điểm | Chốt |
|---|---|
| Đơn vị cấu hình | Một file luật cho mỗi cuộc chat |
| Nơi lưu | `<brain>/Javis/zalo/<slug>.md` (như loop/agent/skill) |
| Cách đặt luật | Nói bằng lời qua chat hoặc Telegram, Jarvis 007 ghi file |
| Giao diện | CHỈ hiển thị để xem lại, không có form nhập |
| Tri thức của bot | Kịch bản riêng từng nhóm, không chạm brain/POS |

## Năm chế độ

| mode | Làm gì | Có cần engine đọc nội dung? |
|---|---|---|
| `im-lang` | Chỉ ghi nhận vào sổ, không báo | Không |
| `bao-het` | Mọi tin đều báo Telegram | Không |
| `tu-khoa` | Báo khi tin chứa từ khoá | Không |
| `nhac-quen` | Khách nhắn mà quá N phút không ai đáp thì báo | Không |
| `chatbot` | Engine hộp cát tự trả lời, báo khi bí | **Có** |

Bốn chế độ đầu giữ nguyên rào bảo mật của bản trước (nội dung không chạm engine).
Chỉ `chatbot` mở rào, nên nó có rào riêng ở mục dưới.

## File luật

`<brain>/Javis/zalo/<slug>.md`:

```yaml
---
type: zalo-rule
thread_id: "<id cuộc chat>"
thread_name: "Nhóm Kim Khí Hà Lộc"
mode: chatbot            # im-lang | bao-het | tu-khoa | nhac-quen | chatbot
enabled: false           # chatbot LUÔN tạo ở trạng thái tắt
keywords: []             # chỉ dùng cho mode tu-khoa
escalate_after_min: 30   # chỉ dùng cho mode nhac-quen
owner_uid: ""            # uid Zalo của CHỦ trong nhóm, để biết chủ đã trả lời chưa
max_reply_per_hour: 20   # chỉ dùng cho mode chatbot
updated: 2026-07-20
---
<Kịch bản: bot biết gì, trả lời thế nào, gặp gì thì đẩy về cho chủ.>
```

Đặt trong brain vì ba lý do: nhất quán với loop/agent/skill (đều là `.md` do chat
sinh ra), có git nên lần lại được mọi thay đổi, và sửa tay được khi cần.

Đọc từ brain MẶC ĐỊNH (listener là dịch vụ nền, không có khái niệm "brain đang mở").

## Đặt luật bằng lời

Tool `javis_zalo_rule` (plugin bundled) để engine gọi khi chủ nói bằng lời:

- `op=list` - liệt kê luật đang có.
- `op=show` - xem chi tiết một luật.
- `op=set` - tạo hoặc sửa (nhận `thread`, `mode`, `script`, và các trường tuỳ chọn).
- `op=off` - tắt một luật.

**Nhận diện cuộc chat**: tham số `thread` nhận id hoặc TÊN. Khớp tên theo sổ cuộc
chat đã thấy. Nhiều hơn một kết quả thì tool **trả về danh sách và không làm gì** -
đoán bừa là gắn kịch bản nhầm nhóm rồi bot trả lời khách của nhóm khác.

**Chế độ chatbot luôn tạo với `enabled: false`.** Bốn chế độ kia chỉ báo về Telegram
nên sai cũng chỉ phiền chủ; chatbot gửi tin ra ngoài không rút lại được, nên bật phải
là một hành động riêng có ý thức. Đây là chỗ duy nhất thêm ma sát, và cùng luật với
loop trong CLAUDE.md.

## Chế độ nhac-quen

Cần trạng thái theo cuộc chat: `{since, from_name, text}` = tin của khách đang chờ
được đáp.

- Tin từ người khác (không phải chủ) → nếu chưa có mốc chờ thì đặt mốc.
- Tin từ `owner_uid` → xoá mốc (chủ đã trả lời).
- Bot tự trả lời (mode chatbot) → xoá mốc luôn, vì code biết ngay, không cần đợi webhook.
- Scheduler nền (tick 30s, đã có sẵn) quét: mốc quá `escalate_after_min` thì báo
  Telegram một lần rồi xoá mốc, không nhắc lặp.

`owner_uid` trống thì mốc không bao giờ được xoá bởi tin của chủ, nên sẽ nhắc cả khi
chủ đã trả lời. Tool phải cảnh báo rõ khi tạo luật `nhac-quen` mà chưa có `owner_uid`,
và gợi ý danh sách người gửi đã thấy trong nhóm để chọn.

## Chế độ chatbot: hộp cát

Đây là phần rủi ro nhất, luật phải cứng.

### Bẫy đã phát hiện: `allowed_tools=[]` KHÔNG khoá tool

`claude_sdk_engine.py:300` viết `if self.allowed_tools:`. Danh sách **rỗng là falsy**,
nên `allowed_tools=[]` rơi xuống nhánh `else`: `permission_mode = "bypassPermissions"`
kèm nạp settings máy và MCP sẵn có.

Nghĩa là cách viết trực giác nhất để tạo hộp cát lại **mở toang mọi quyền**, đúng lúc
nội dung do người lạ soạn đi vào engine.

Phải truyền whitelist KHÁC RỖNG chứa một tên tool không tồn tại
(`__zalo_bot_khong_co_tool__`). Khi đó `allowed_tools` truthy → gate bật → mọi tool
thật rơi vào `_permission_gate` → bị từ chối thật từng lần. Có test chốt điều này.

### Các rào khác

- `mcp_config` trỏ file MCP rỗng + `mcp_strict = True` → không thấy connector nào.
- System prompt = kịch bản của nhóm + rào chống injection. **Không** kèm bộ nhớ,
  không kèm brain, không kèm CLAUDE.md của chủ.
- Nội dung khách được rào giữa hai vạch có nhãn, y như cách làm với Telegram.
- **Model không có tool nào nên không thể chọn người nhận.** Nó chỉ sinh ra CHỮ; code
  Jarvis 007 quyết định gửi đi đâu, và luôn gửi về đúng cuộc chat vừa phát sinh tin. Dù bị
  dụ hoàn toàn cũng không nhắn được cho người khác. Đây là khác biệt giữa rào thật và
  lời dặn trong prompt.
- Đầu ra bắt đầu bằng `[CHUYEN CHU]` → không gửi cho khách, đẩy về Telegram cho chủ.
- Trần `max_reply_per_hour` mỗi nhóm. Vượt thì im và báo chủ một lần.
- `max_wall_s = 60`: đây là trả lời chat, chậm hơn thì vô nghĩa.
- Mọi tin bot tự gửi đều ghi log để chủ soi lại được.

### Gửi tin đi bằng đường nào

Sidecar `listen` không gửi được tin. Gửi qua connector MCP `zalo` (tool
`zalo_send_message`). Đây là chỗ CHẠM vào va chạm một-socket-mỗi-tài-khoản đã ghi
trong spec trước. Chưa kiểm chứng được; nếu va thật thì phương án là tạm dừng listener,
gửi, bật lại. Không đoán trước, để lộ ra rồi xử.

## An toàn tổng thể

- Bot chỉ trả lời trong cuộc chat có luật `mode: chatbot` **và** `enabled: true`.
  Kiểm bằng code trước khi gọi engine, không phải bằng lời dặn.
- Bốn chế độ còn lại không gọi engine.
- Tin của chính tài khoản Jarvis 007 không kích hoạt gì (tránh bot tự nói chuyện với mình).
- Rào XSS trên giao diện giữ nguyên: tên nhóm và tên người gửi vẫn bọc `esc()`.

## Test

- Đọc/ghi file luật, khớp tên nhóm nhập nhằng thì trả danh sách chứ không đoán.
- Từng chế độ: đúng tin nào báo, tin nào không.
- `nhac-quen`: đặt mốc, xoá mốc khi chủ trả lời, bắn đúng một lần khi quá hạn.
- Chatbot: whitelist tool KHÁC RỖNG (chốt cứng cái bẫy `[]`), đầu ra `[CHUYEN CHU]`
  không gửi cho khách, trần số tin mỗi giờ, và bot không chạy khi luật đang tắt.
- Không gọi engine ở bốn chế độ đầu.

## Ngoài phạm vi

Bot đọc Wiki hoặc số liệu POS (đã chốt là không, chỉ kịch bản riêng nhóm). Duyệt
từng câu trả lời qua Telegram trước khi gửi (chủ chọn tự gửi thẳng). Đường OA chính thức.
