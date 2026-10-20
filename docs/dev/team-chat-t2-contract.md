# Hợp đồng T2: API, gói WS và dữ liệu reaction (0.154.0)

Tài liệu này chốt mặt tiếp giáp giữa phần máy chủ và phần giao diện của T2, để hai phần làm song song mà ghép khớp. Thiết kế gốc:
`docs/superpowers/specs/2026-10-15-team-adaptive-design.md` mục 2, 3, 4 và 9.1. Đổi hợp đồng thì sửa file này cùng commit.

## 1. Giá trị

- Sáu emoji, giữ đúng mã đang dùng ở chat nhóm (không đổi tên để dữ liệu cũ còn đọc được): `like` 👍, `love` ❤️, `haha` 😂,
  `wow` 😮, `sad` 😢, `angry` 😡. Bỏ emoji: `value: null` (hay `"none"`).
- Lý do chất lượng (chọn nhiều): `on_point`, `wrong_facts`, `missing`, `too_long`, `unclear`, `off_topic`.
- Trục nói/im (chọn một hoặc không): `axis` là `""`, `"should_speak"` ("Đáng lẽ nên nói") hay `"should_silent"` ("Nên im (chen
  ngang)"). Nhận ở cả hai nơi.
- Góp ý chữ: tối đa 500 ký tự.
- Không trường nào bắt buộc để thả emoji.

## 2. Trạng thái của một reaction (do host ghi, giao diện chỉ hiển thị)

`status`: `received` (Đã nhận), `pending_review` (Chờ xem xét), `reviewing` (Đang xem xét), `adjusted` (Đã điều chỉnh),
`no_change` (Không cần đổi), `waiting_quota` (Chờ hạn mức), `stored_only` (Đã nhận, chỉ lưu; `status_reason` nói vì sao:
Cộng hưởng của trợ lý đang tắt, hay phản hồi có trước lúc bật lại Cộng hưởng).
`status_reason`: một câu ngắn host viết sẵn theo ngôn ngữ giao diện (có thể rỗng). Giao diện hiện nhãn của `status` qua i18n
(`react.status.<status>`, viết trọn từng khoá) và thêm `status_reason` nếu có.

## 3. Khuôn reaction `R` trả về

```
{"value": "love", "reasons": ["too_long"], "axis": "", "comment": "", "stale": false,
 "status": "pending_review", "status_reason": "", "source_kind": "owner", "revision": 3, "updated_at": 1760500000.0}
```

`value` có thể `null` khi chỉ có lý do hay góp ý. `R` là `null` khi chủ đã bỏ hết (không emoji, không lý do, không trục, không góp ý).

## 4. Chat riêng (trang Trò chuyện chính và trang Cộng sự `agent:<slug>`)

- `POST /sessions/{session_id}/messages/{message_id}/reaction?brain=<brain>`
  - Thân: `{"value", "reasons", "axis", "comment", "nonce", "seen_sha"}`. `nonce` do trình duyệt sinh MỘT lần cho mỗi thao tác và
    gửi lại y nguyên khi thử lại sau lỗi mạng. `seen_sha` là `content_sha` giao diện đã nhận (tuỳ chọn).
  - 200: `{"ok": true, "reaction": R|null}`. Gửi lại cùng `nonce` trả đúng trạng thái hiện tại, không ghi thêm dòng.
  - 400 thân sai (giá trị lạ, quá dài, nonce rỗng hay dài hơn 100); 404 không có phiên hay tin; 409 tin không phải câu trả lời
    (chỉ tin `role = assistant` nhận reaction), hay nonce đã dùng cho tin khác. Thân lỗi: `{"ok": false, "error": "..."}`.
- `GET /sessions/{session_id}/messages` (đã có): mỗi tin có `id` (đã có) và thêm `content_sha`; tin `assistant` thêm
  `reaction: R|null`. `GET /sessions/{session_id}` (có hay không `?limit=`, dùng khi mở phiên từ lịch sử) cũng vậy: mọi tin
  trong `messages` có `content_sha`, tin `assistant` có `reaction`.
- Gói WS (gửi mọi tab dashboard qua `_CHAT_RUNTIME.publish`):
  - `{"type": "chat_reaction", "session_id": "...", "message_id": 123, "reaction": R|null}` sau mỗi lần ghi và mỗi lần host đổi
    trạng thái (bộ chiếu, lượt xem xét).
  - `{"type": "turn_saved", "session_id": "...", "message_id": 123, "content_sha": "..."}` ngay sau khi lưu câu trả lời của một
    lượt (`_persist_turn` trả mã tin và CHỜ gửi xong gói này trước khi trả về, nên gói luôn tới trước `turn_done` của
    lượt đó). Gói tới sau `response`, trước `turn_done`. Bong bóng vừa trả lời nhận
    `data-mid` từ gói này; chưa có mã thì chưa hiện nút reaction.
- Tác giả: phiên kênh `agent:<slug>` (hay có dòng `session_agents`) là agent đó, `agent_key` do host tra; phiên Jarvis 007 chính là
  `agent_key` rỗng (lưu và hiện, không vào học hay phán xử của agent nào, `status` luôn `received`).

## 5. Chat nhóm

- `POST /teams/{team_id}/messages/{message_id}/reaction?brain=<brain>` (đã có): thân thêm `axis` và `seen_sha`; `R` thêm `axis`,
  `stale`, `status`, `status_reason`, `source_kind`, `revision`. Cùng quy tắc nonce dùng lại (gửi lại cùng nonce trả trạng thái
  hiện tại, 200).
- Tin trong trang tin nhóm và chi tiết việc mang `reaction: R|null` như hiện nay, kèm các trường mới, và `content_sha`.
- Gói WS `team_message` (đã có) mang tin đã gắn `reaction` mới; khung lọc theo việc (`S.filterTask`) cũng phải nhận và vẽ lại tin
  đó nếu đang hiện.
- Reaction của agent (trưởng nhóm, thành viên) đi qua lệnh có cấu trúc trong lượt của agent, không qua route:
  `<!-- JAVIS_TEAM: {"op": "react", "message_id": 123, "value": "like", "reasons": [], "comment": ""} -->`. Host gán
  `source_kind` theo lượt; agent không thả lên tin của chính mình. Tin mang thêm `agent_reactions: [{"agent_key", "name",
  "source_kind", "value", "reasons", "comment"}]`; giao diện hiện thành chip riêng có tên agent, chỉ đọc, tách khỏi chip của chủ.

## 6. Giao diện dùng chung (`dashboard/reactions.js`)

- `window.JavisReactions` (và `module.exports` cho node): `EMOJI` (bảng sáu emoji duy nhất của repo), `REASONS`, `AXES`,
  `nextReaction(cur, pick)`, `chipHtml(R, opts)`, `pickerHtml(mid, R, opts)`, `statusHtml(R)`, `agentChipsHtml(list)`,
  `newNonce()`, `bindLongPress(root, selector, onOpen)`.
- `teams.js`, `app.js` (bong bóng trả lời, bong bóng stream sau khi chốt, lịch sử) và `mobile-chat.js` dùng module này; không
  file nào khác chứa ký tự emoji của bảng (`test_icons` đổi phạm vi ngoại lệ sang `reactions.js`).
- Bấm chọn, đổi, bỏ; nhấn giữ 500 ms trên điện thoại; nút luôn hiện ở `@media (hover: none)`; vùng chạm 44px; chữ 16px.
- Gửi: giữ `nonce` của thao tác đang gửi tới khi có kết quả; lỗi mạng thì Thử lại gửi lại cùng `nonce`. Thành công hay lỗi 4xx thì
  thao tác kế tiếp dùng nonce mới.
