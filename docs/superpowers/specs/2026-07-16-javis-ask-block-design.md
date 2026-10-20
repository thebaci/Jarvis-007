# Khối hỏi-lại có lựa chọn trong khung chat Jarvis 007

Ngày: 2026-07-16
Trạng thái: đã chốt thiết kế, chờ lập kế hoạch triển khai

## Mục tiêu

Khi Jarvis 007 cần hỏi lại người dùng, khung chat hiện các lựa chọn bấm được ngay dưới câu
trả lời, thay vì bắt người dùng đọc câu hỏi rồi tự gõ đáp án. Mục đích là làm trải
nghiệm khung chat quen thuộc với người đã dùng Claude Code.

Phạm vi lần này CHỈ có khối hỏi-lại. Không làm timeline tool, không làm danh sách việc,
không làm xin quyền. Chạy đúng trên mọi engine (Claude Agent SDK, Codex CLI, và các
engine chat API). Dashboard có nút bấm thật; Telegram nhận bản chữ.

## Bối cảnh kỹ thuật

Khung chat chạy qua WebSocket. Server đẩy về `status` / `tool_call` / `tool_result` /
`stream` / `response` / `error` / `turn_done`; chiều ngược lại client chỉ gửi được một
loại tin nhắn văn bản (`{message, brain, session_id}`).

Dự án đã có sẵn đúng một tiền lệ cho việc này: khối `JAVIS_METRICS`. Jarvis 007 nhúng một
HTML comment ở cuối phản hồi, `app.js:1126` bóc nó ra bằng regex rồi bơm vào panel trái.
Thiết kế này đi theo đúng vết đó.

Hai chi tiết có sẵn khiến đường này rẻ:
- `chat-render.js:246` đã nuốt mọi HTML comment, kể cả comment chưa đóng lúc đang stream.
  Nên khối điều khiển không bao giờ nhấp nháy ra màn hình giữa chừng.
- `app.js:160` đã có sẵn chỗ móc: `const { clean, cards } = extractMetrics(data.content)`
  ngay trong nhánh xử lý `response`.

## Hướng đã chọn và hướng đã loại

Chọn: **quy ước đánh dấu ở cuối câu trả lời**.

Loại: **tool thật `javis_ask_user` qua MCP hub** (model gọi tool, server treo lượt chờ
người dùng bấm, trả kết quả làm tool result). Đây là cách Claude Code làm thật và cho
phép hỏi giữa chừng lúc đang làm dở. Loại vì giá quá đắt so với phần dùng được: hub là
HTTP nên phải nhét session vào header config MCP cho từng lượt (file config hiện cache
theo mode chứ không theo phiên), phải lo timeout, lo người dùng F5 giữa lúc đang chờ,
và phải làm ba lần cho ba đường engine. Trong khi ở khung chat Jarvis 007 gần như mọi câu
hỏi lại đều rơi vào cuối lượt.

Nếu sau này thật sự cần hỏi giữa chừng thì đắp hướng tool lên trên vẫn được: phần giao
diện chip dùng lại nguyên, chỉ thay nguồn phát câu hỏi.

## Hợp đồng dữ liệu

Jarvis 007 kết thúc câu trả lời bằng:

```
<!-- JAVIS_ASK: {"question":"Anh muốn xem doanh thu kỳ nào?","header":"Kỳ","options":[{"label":"Tuần này","desc":"7 ngày gần nhất"},{"label":"Tháng này","desc":"Từ mùng 1"},{"label":"So tháng trước","desc":"Có đối chiếu"}]} -->
```

- `question`: câu hỏi đầy đủ, bắt buộc.
- `header`: nhãn ngắn gọn chủ đề, tuỳ chọn.
- `options`: tối đa 4 phần tử. `label` là chữ trên nút, `desc` là một dòng giải thích.

Một khối là một câu hỏi. Không hỗ trợ chọn nhiều đáp án: trong khung chat gần như luôn
là chọn một, thêm chọn nhiều là phải đẻ thêm nút xác nhận cho một thứ hiếm dùng.

Khối này và khối `JAVIS_METRICS` sống chung được trong một phản hồi.

## Hành vi giao diện

Chip hiện thành một hàng dưới bong bóng trả lời, nằm trong cùng thẻ tin nhắn đó. `desc`
nằm ở tooltip để hàng chip không phình. Chip cuối cùng luôn là "Ý khác": bấm vào không
gửi gì, chỉ đưa con trỏ xuống ô nhập liệu.

Bấm một chip thì gửi đúng `label` đó đi như một tin nhắn người dùng bình thường, cùng
phiên. Lịch sử hội thoại đọc vẫn xuôi, không có tin nhắn ma, và Jarvis 007 không cần biết
người dùng bấm hay gõ.

**Chỉ tin nhắn cuối cùng mới có chip sống.** Sau khi người dùng trả lời (bấm chip hoặc
gõ tay câu khác), hàng chip đông cứng: cái đã chọn giữ dấu tích, cái còn lại mờ và hết
bấm được. Lý do: cuộn ngược lên đọc lịch sử mà bấm được câu hỏi của mười lượt trước thì
làm rối mạch hội thoại. Khôi phục phiên sau F5 theo đúng luật đó: chip sống lại chỉ khi
nó thuộc tin cuối và chưa được trả lời.

Chip chỉ mọc khi lượt kết thúc (sự kiện `response`), không mọc lúc đang stream.

## Kiến trúc mã

**Mới: `dashboard/chat-ask.js`** (cỡ 100 dòng). Lo đúng ba việc: bóc khối JSON ra khỏi
text, vẽ hàng chip, bắt sự kiện bấm. Phơi ra `window.JavisAsk`:

- `extract(text) -> { clean, ask }` thuần, không đụng DOM.
- `render(msgEl, ask, live)` vẽ chip vào thẻ tin nhắn; `live=false` thì vẽ dạng đông cứng.
- `freezeAll()` đông cứng mọi hàng chip đang sống (gọi khi có tin nhắn mới).

Không nhét vào `app.js` vì file đó đã 1900 dòng. Cách chia này theo đúng vết dự án đang
làm với `chat-render.js`, `chat-zoom.js`, `voice.js`, và cho phép sửa hay test phần
hỏi-lại mà không mở `app.js`.

**Sửa `dashboard/app.js`**, đúng ba chỗ:
- nhánh `response`: bóc `ask` cùng lúc với `cards`, gọi `JavisAsk.render(..., live=true)`.
- `sendMessage()`: gọi `JavisAsk.freezeAll()` trước khi thêm bong bóng người dùng.
- `restoreSession()`: vẽ lại chip, chỉ để sống ở tin cuối chưa trả lời. Ask được lưu
  kèm trong bản ghi lượt của `convo`.

**Mới: hàm bóc khối điều khiển phía server**, đặt trong `channel_context.py` vì module
đó đúng là nơi lo chuyện text theo từng kênh và đã có sẵn các hàm thuần cùng loại
(`extract_paths`, `collect_turn_files`); `main.py` đã import sẵn nó. Hàm bóc mọi khối
`JAVIS_*` ra khỏi text trước khi trả về kênh không phải web, gọi ở cuối `_tg_answer`.
Với `JAVIS_ASK` thì thay bằng danh sách đánh số:

```
Anh muốn xem doanh thu kỳ nào?
1. Tuần này
2. Tháng này
3. So tháng trước
```

Người dùng nhắn "1" là xong. Jarvis 007 đọc "1" trong ngữ cảnh câu hỏi vừa hỏi thì tự hiểu,
không cần lưu state. Bot Telegram đã có sẵn hạ tầng nút inline (`reply_markup`,
`_handle_callback`) nhưng lần này không dùng.

**Sửa `CLAUDE.md`**: dạy Jarvis 007 khi nào nhúng khối, gắn vào mục "Làm rõ trước khi trả
lời" đã có sẵn chứ không mở luật mới. Mục đó đang nói chỉ hỏi lại khi thực sự tắc, tối
đa 1-3 câu. Khối này là cách trình bày cho bước "chỉ hỏi lại khi thực sự tắc" đó. Điểm
dùng điển hình: phải đoán một tham số mà đoán sai thì hại, ví dụ kỳ thời gian hay chọn
shop nào.

## Lỗi có sẵn sẽ vá luôn

Khối `JAVIS_METRICS` **đang lọt nguyên xi sang Telegram** hôm nay. `_tg_answer`
(`main.py:4614`) trả `out` thô, `telegram_bot._send` gọi `md_to_mdv2` vốn chỉ escape chứ
không bóc comment. Đã kiểm chứng bằng cách chạy thẳng `md_to_mdv2`, đầu ra chứa nguyên
`<\!\-\- JAVIS\_METRICS: ...`.

Đây là lỗi có sẵn, nhưng nằm đúng đường đi của thiết kế này: khối `JAVIS_ASK` sẽ rò y
hệt nếu không xử. Hàm bóc khối điều khiển nói trên vá cả hai cùng lúc.

## Đường lỗi

- JSON hỏng: bỏ qua khối im lặng, vẫn hiện câu trả lời. Tuyệt đối không để một khối sai
  cú pháp nuốt mất câu trả lời của Jarvis 007.
- Thừa lựa chọn: cắt còn 4.
- Nhãn quá dài: cắt gọn khi vẽ.
- Khối nằm giữa bài thay vì cuối: vẫn bóc được, vì bắt bằng regex chứ không theo vị trí.
- Nhãn do model sinh ra nên không tin được: escape toàn bộ khi vẽ.
- Không có `options` hoặc `options` rỗng: coi như không có khối.

## Test

Thuần, không cần trình duyệt:
- `extract()` với JSON hợp lệ, JSON hỏng, không có khối, thừa lựa chọn, options rỗng,
  khối nằm giữa bài, có cả `JAVIS_ASK` lẫn `JAVIS_METRICS`.
- Hàm bóc khối phía server: `JAVIS_ASK` xuống đúng danh sách đánh số; `JAVIS_METRICS`
  biến mất sạch (test hồi quy cho lỗi rò ở trên).

Bấm tay để xác nhận (hành vi DOM):
- Chip mọc sau khi lượt xong, không nhấp nháy lúc stream.
- Bấm chip thì ra tin nhắn người dùng đúng nhãn, Jarvis 007 chạy tiếp.
- Chip đông cứng sau khi trả lời; cuộn lên lịch sử không bấm được.
- F5 rồi khôi phục: chip sống lại đúng ở tin cuối chưa trả lời.
