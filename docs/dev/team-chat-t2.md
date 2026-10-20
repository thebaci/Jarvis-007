# Nhóm chat team T2: sáu reaction và vòng phản hồi (0.120.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) mục 14; ca TC28 tới TC30, TC37 (phần reaction). Chồng trên T1 (PR #628).

## Luồng

1. Rê chuột vào tin của trợ lý hiện nút mặt cười (máy chạm luôn hiện); điện thoại nhấn giữ tin 0,5 giây cũng mở bộ chọn.
2. Bộ chọn mở ngay tại tin: sáu emoji 👍 ❤️ 😂 😮 😢 😡, sáu lý do chất lượng (chọn được nhiều), ô góp ý tối đa 500 ký tự, một câu nhắc "cảm xúc không phải chấm điểm".
3. Bấm một emoji là lưu ngay; bấm lại emoji đang chọn là bỏ; "Lưu góp ý" lưu lý do và góp ý; "Bỏ phản hồi" xoá hết.
4. Emoji đã chọn hiện thành chip dưới tin (kèm số lý do, "có góp ý"); bấm chip để đổi hay bỏ.
5. Lượt KẾ TIẾP của chính trợ lý đó trong chính nhóm đó có khối "Phản hồi gần đây của chủ nhóm" kèm câu dặn cố định.

## Bản đồ mã

| Phần | File | Việc |
|---|---|---|
| Kho | `server/team_store.py` | `team_reactions` (một dòng mỗi người phản hồi mỗi tin), `team_reaction_log` (nối tiếp, `nonce` UNIQUE); `set_reaction`, `reaction_of`, `reactions_for`, `reaction_log`, `recent_feedback`; hằng `REACTIONS`, `REACTION_EMOJI`, `REACTION_REASONS` |
| Bộ chạy | `server/team_runner.py` | `react` (chỉ ghi kho và đẩy gói WS), `_feedback_lines`, `FEEDBACK_NOTE`; khối phản hồi trong `_context` |
| Route | `server/team_api.py` | `POST /teams/{id}/messages/{mid}/reaction {value, reasons, comment, nonce}`; trang tin kèm `reaction` của từng tin |
| Giao diện | `dashboard/teams.js`, `console.css`, i18n | Bảng `REACTIONS`, `reactionPickerHtml`, `reactionChipHtml`, `nextReaction`; nhấn giữ; giữ bản nháp góp ý qua lần vẽ lại |
| Quy ước | `tests/python/test_icons.py` | Ngoại lệ có lý do cho đúng sáu emoji trong `teams.js`, kèm kiểm cả sáu luôn còn và chỉ nằm trong bảng `REACTIONS` |

## Quy tắc đã giữ

- Đúng sáu giá trị, lưu nguyên (`like`, `love`, `haha`, `wow`, `sad`, `angry`), cộng `none` để bỏ emoji. Lý do và góp ý tồn tại được khi không có emoji.
- Đặt phản hồi là THAY TRỌN trạng thái của người đó trên tin; giao diện tính "bấm lại là bỏ". `nonce` trùng thì không đổi gì.
- Lưu kèm người phản hồi (`owner`), tin, agent tác giả, nhóm, việc, `content_sha` của nội dung lúc bấm.
- Không gọi model, không mở lượt, không đánh thức agent, không đổi việc, goal hay hàng đợi (TC29, kiểm bằng sổ lượt và phiên bản hàng đợi).
- Khối phản hồi: tối đa 5 mục, 30 ngày, mới nhất trước, chỉ tin của chính agent trong chính nhóm; mỗi mục có đoạn trích, emoji gốc kèm tên loại, lý do, góp ý; bỏ phản hồi thì rời khối ở lượt kế (đọc trạng thái hiện tại).
- Không dùng bảng `reactions` của A3.

## Phán quyết

- **Đề xuất bài học từ góp ý để mốc sau** (spec 14.4 mục 4 cho phép): T2 chỉ đưa phản hồi vào ngữ cảnh. Cơ chế "Bài học đề xuất" cần chỗ hiện trên bảng agent, nút nhận và nút gỡ như A3; làm cùng lúc sẽ kéo T2 sang trang Cộng sự. Giá nếu sai: chủ muốn góp ý thành bài học bền thì phải dặn trong chat 1:1 với agent cho tới khi có cơ chế này.
- Người phản hồi chỉ có `owner` (dashboard một tài khoản); cột `reactor` để sẵn.
- Thả cảm xúc được cả ở nhóm đã lưu trữ (chỉ là ghi phản hồi, không mở lượt).
- Nhóm đã lưu trữ hay tin đến muộn (applied=false) vẫn nhận phản hồi; khối phản hồi chỉ đọc theo agent và nhóm.

## Kiểm

| Lệnh | Kết quả |
|---|---|
| `tests/python/test_team_reactions.py` | 31 ca: TC28 (chọn, đổi, bỏ, nonce, nhật ký, giữ qua mở lại kho, từ chối đầu vào sai, chỉ tin của agent đúng nhóm), TC29 (không đổi việc, hàng đợi, không lượt, không engine), TC30 (khối phản hồi, câu dặn, đúng nhóm, đúng agent, bỏ thì rời, tối đa 5, 30 ngày) |
| `tests/python/test_team_api.py` | thêm 6 ca route reaction (200, trang tin kèm reaction, 400, 404 brain khác, không mở lượt) |
| `tests/js/test_teams_ui.js` | thêm 22 ca giao diện reaction |
| `tests/python/test_icons.py` | sáu reaction còn đủ, chỉ trong bảng `REACTIONS`; không emoji trang trí |

**Smoke giao diện** (sandbox cổng 7788, state trong worktree, nhóm tạm dừng, trần lượt ngày 0; tin của trợ lý chèn thẳng vào kho phiên, không gọi model). Ảnh ở `exports/reviews/team-t2-smoke/`:
- desktop: chọn 😢 hiện chip; F5 vẫn còn; thêm lý do "Quá dài" và góp ý; bấm lại 😢 là bỏ emoji, lý do và góp ý còn; đổi sang 😂;
- 375px: nút mặt cười hiện sẵn 44x44; nhấn giữ mở bộ chọn; sáu nút 44x48; không cuộn ngang;
- smoke tìm ra và đã sửa: ở 375px hàng sáu nút tràn mép (😡 bị cắt) vì khe 6px và đệm 10px; chữ "1 reasons" sai ngữ pháp (đổi thành "Reasons: 1");
- sổ lượt của nhóm sau smoke: 0 lượt.

## Review cuối (người review mới, model mạnh nhất)

Kết luận "Ready with fixes": 1 Important, 6 Minor. Xếp lại theo tác động, sửa cả bảy:
- **Important:** chi tiết việc (khung lọc theo việc) trả tin thiếu phản hồi, bấm emoji ở đó xoá mất lý do và góp ý đã lưu. Route `GET /teams/{id}/tasks/{task}` nay kèm `reaction` của từng tin.
- Góp ý nhiều dòng phá khuôn một dòng mỗi mục (giả được đầu mục mới): gộp khoảng trắng.
- Phản hồi của tin không còn vẫn vào khối với đoạn trích rỗng: bỏ qua.
- Đang soạn góp ý mà có tin mới tới thì mất con trỏ, bị kéo xuống cuối: giữ con trỏ, chỗ cuộn.
- Mở bộ chọn không đưa focus vào bảng (Escape không đóng được với bàn phím): focus emoji đầu, đóng thì trả focus về nút mặt cười.
- Nhấn giữ chuột cũng mở bộ chọn, và đè menu nhấn giữ của máy chạm: chỉ chạm và bút; chặn menu ngữ cảnh của lần giữ đó; `-webkit-touch-callout: none` trên máy chạm.
- Nonce đã dùng cho tin khác trả 200 "đã lưu": nay từ chối (0.120.0 trả 400; từ 0.154.0 trả 409 cho khớp hợp đồng T2); nonce dài quá 100 ký tự bị từ chối.

Bốn lỗi phía server có test đỏ trước rồi xanh (`test_team_reactions.py`, `test_team_api.py`). Ba lỗi giao diện kiểm bằng test nguồn trong `test_teams_ui.js` viết sau khi sửa (hành vi DOM chưa chạy được dưới node; chưa soi lại trên trình duyệt).

Phần reviewer không kết luận: nhấn giữ trên iOS Safari, Android Chrome thật; trình đọc màn hình đọc chip; `de.json` chưa có khoá `teams.*` (rơi về tiếng Anh, có từ trước T2).

---

## Team chat T2 (0.154.0), phần máy chủ: reaction hai nơi, sổ lượt chung, lý do thức, bộ chiếu phản hồi

Thiết kế gốc: `docs/superpowers/specs/2026-10-15-team-adaptive-design.md` mục 2, 3.1-3.5, 4.1-4.4, 9, 9.1, 12, 13. Hợp
đồng với giao diện: `docs/dev/team-chat-t2-contract.md`. Phần giao diện (reactions.js, app.js, teams.js, mobile-chat.js)
do nhánh UI làm riêng; tài liệu này chỉ nói phần máy chủ.

### 1. Làm gì

- **Sổ lượt chung và trần máy chủ (3.1, 9.1).** Bảng `agent_calls` trong `resonance.sqlite3`. Một phép đếm
  `_ceiling_used(c)` = `SUM(goals.calls_used)` + `COUNT(call_ledger used)` + `COUNT(agent_calls counted = 1, chưa hoàn)`.
  Lượt nghĩa vụ (goal A2, phép thử, bộ lập mục tiêu, lượt nhóm) dùng cả trần; lượt tự phát (`obligation = 0`) chỉ tới
  `floor(trần * 0.8)`. Trần tính trên toàn bộ thời gian sống của kho, không theo ngày. Chỉ mục duy nhất từng phần
  `UNIQUE(reason_ref) WHERE status IN ('reserved','running','ok')`.
- **Lượt nhóm giữ chỗ trước engine.** `TeamRunner` có phụ thuộc `ceiling` (`agent_ledger.TeamCeiling`). Ngay sau khi giữ
  chỗ `team_turns`, lượt giữ một dòng `counted = 1`, `mirror_ref = team_turn:<id>`. Trần đầy: hoàn `team_turns`, kết cục
  `{"status": "cap", "cap": "server_ceiling"}`, không gọi engine. Lượt trả lời lỗi với lý do `server_ceiling`; bước việc
  bị chặn với `block_kind = server_ceiling` (nút "Cho thêm lượt" không gỡ được). Mọi đường hoàn/mốc/chốt (`busy_long`,
  lỗi trước engine, huỷ, hết giờ, `lease_lost` trước engine của T1, phục hồi) đi qua `_refund_if_unmarked`,
  `_mark_engine`, `_settle_turn`, nên dòng sổ chốt theo. Lỗi kho chung lúc mốc/chốt không làm hỏng lượt nhóm.
- **Đối soát** (`TeamCeiling.reconcile`): lúc khởi động (cuối `TeamRunner.recover`) và mỗi 60 giây (vòng của
  `TeamApi.tick`). Dòng `team_turn:*` chỉ theo trạng thái của chính lượt nhóm (đã hoàn/không còn thì hoàn, đã chốt thì
  chốt theo, còn `reserved`/`running` thì để nguyên), không bao giờ theo tuổi. Dòng và lượt mới hơn 120 giây bị bỏ qua.
  Lượt nhóm đã tới mốc engine mà thiếu dòng sổ thì dựng lại dòng tính. Quy tắc 10 phút chỉ cho dòng `mirror_ref = ''`.
- **Lý do thức theo agent (3.2-3.4).** `agent_wake_reasons` và `agent_wake_sources` với đủ vòng đời (pending, claimed,
  served, superseded, failed). API ở `agent_ledger.WakeReasons`: `add_source`, `remove_source`, `remove_group`, `claim`
  (thử khoá bận trước, bận không tốn lần thử; CAS và giữ chỗ sổ lượt trong một giao dịch), `settle`, `retry_failed`.
  Chỉ T3 phục vụ lý do; T2 tạo chúng và có test đủ vòng đời.
- **Bộ chiếu phản hồi (3.5)** `server/feedback_projector.py`: idempotent theo `source_ref`, chiếu theo thứ tự nhật ký,
  trạng thái ròng, dòng cũ `superseded`. Chạy ngay sau khi ghi (lỗi nuốt và ghi log), mỗi nhịp scheduler và lúc khởi
  động (`_feedback_pulse_tick` trong main.py). Định tuyến: tin gắn goal chỉ vào lý do `feedback` của A2; tin khác vào lý
  do `reaction_review` ở `team:<id>` hay `dm:<agent_key>`; chỉ khi agent bật Cộng hưởng và sự kiện sau `resumed_at`.
  Cộng hưởng tắt: `stored_only`. Trang Trò chuyện chính: `received`. Trạng thái reaction ghi ngược theo lý do.
  Điểm nối để trống cho T3: `FeedbackProjector.record_pulse_signal`.
- **`resumed_at`.** Bảng `agent_pulse` (đủ cột của mục 5.4). Mốc ghi trong `GoalStore.agent_set_enabled` cùng giao dịch
  với công tắc, nên cả route của chủ lẫn lệnh `set_resonance` của trưởng nhóm đều có mốc. Nâng cấp: agent đang bật nhận
  `resumed_at = lúc nâng cấp`.
- **Reaction chat riêng (4.1, hợp đồng mục 4).** `dm_reactions`, `dm_reaction_log` trong `conversations.db`. Route
  `POST /sessions/{session_id}/messages/{message_id}/reaction`. `GET /sessions/{id}/messages` và `GET /sessions/{id}` có
  `content_sha` trên mọi tin và `reaction` trên tin `assistant`. Gói WS `chat_reaction` sau mỗi lần ghi và mỗi lần host đổi
  trạng thái. `_persist_turn` trả mã tin và đẩy `turn_saved` ngay sau khi lưu (mọi đường gọi: dashboard, Telegram, giọng,
  quy trình).
- **Reaction nhóm mở rộng (4.1, hợp đồng mục 5).** Cột mới cho `team_reactions`/`team_reaction_log` (ALTER idempotent, có
  mặc định). Gửi lại cùng nonce trả trạng thái hiện tại; nonce của tin khác: 409. Lệnh `react` của agent trong lượt nhóm
  (mọi vai, tối đa 5 mỗi lượt, nonce `<turn_id>#rx<i>`): host gán `leader`/`member`, không thả lên tin của chính mình.
  Tin mang `agent_reactions` và `content_sha`.
- **Hiệu lực (4.3).** Emoji không chốt đạt, không đổi ưu tiên, không cấp gì, không đổi trạng thái việc hay goal (test cả
  chat riêng). Khối phản hồi vào lượt kế tiếp đúng ngữ cảnh: nhóm (`_feedback_lines`, thêm trục nói/im) và chat riêng
  (`_agent_turn_system_prompt` thêm `feedback_projector.dm_feedback_block`, chỉ của đúng agent đó).

### 2. Ở đâu

| File | Nội dung |
|---|---|
| `server/agent_ledger.py` (mới) | `CallLedger`, `TeamCeiling`, `WakeReasons` |
| `server/feedback_projector.py` (mới) | bộ chiếu phản hồi, khối phản hồi chat riêng |
| `server/reaction_values.py` (mới) | sáu giá trị, lý do, trục, kiểm đầu vào, khuôn R |
| `server/resonance_store.py` | `_ceiling_used`, `ceiling_limit`, bảng T2, `resumed_at`, `agent_any`, A2 supersede |
| `server/team_store.py` | cột reaction mới, `set_reaction_ex`, outbox, `NonceConflict`, `turns_since` |
| `server/team_runner.py` | phụ thuộc `ceiling`/`projector`, lệnh `react`, `server_ceiling`, góp ý đồng đội |
| `server/team_api.py` | nối phụ thuộc, nhịp đối soát, route reaction (axis, seen_sha, 409) |
| `server/sessions.py` | `dm_reactions`, `dm_reaction_log`, `content_sha` trên tin |
| `server/main.py` | route reaction chat riêng, `turn_saved`, khối phản hồi, nhịp bộ chiếu, nối trần |
| `dashboard/i18n/{vi,en}.json` | `teams.reply.why.server_ceiling`, `teams.block.server_ceiling` |

### 3. Di trú

- `resonance.sqlite3`: chụp `resonance.sqlite3.pre-0.154.0` lần đầu (chưa có `agent_calls`), rồi tạo bảng mới. Không đổi
  bảng cũ.
- `team.sqlite3`: chụp `team.sqlite3.pre-0.154.0` lần đầu (chưa có cột `axis`), rồi ALTER thêm cột có mặc định. Dòng nhật
  ký cũ có `effect_state = 'done'` (không backfill tác động).
- `conversations.db`: chụp `conversations.db.pre-0.154.0` lần đầu (chưa có `dm_reactions`), rồi tạo hai bảng mới.

### 4. Quay về bản cũ

Bản 0.153.x bỏ qua bảng và cột mới, nên hạ phiên bản chạy được không cần khôi phục. Reaction của trưởng nhóm/thành viên
(reactor `agent:...`) sẽ hiện như reaction thường ở bản cũ (ảnh hưởng đã biết, không mất dữ liệu). Muốn khôi phục hẳn:
dùng công cụ ở mục dưới, đừng chép tay (chép thô file `.sqlite3` bỏ sót phần còn trong WAL và không có đường lui).

#### Khôi phục về trước 0.154.0

**Thường không cần khôi phục.** Mọi di trú của 0.154.0 chỉ THÊM (bảng mới, cột mới có mặc định), nên chạy lại bản 0.152.0
hay 0.153.0 trên kho đã nâng vẫn được: bản cũ bỏ qua bảng mới, không thấy trạng thái reaction mới, reaction của agent
(`reactor` dạng `agent:...`) hiện như reaction thường. Chỉ dùng công cụ dưới đây khi muốn kho về ĐÚNG trạng thái trước lúc
nâng (mất mọi tin và thay đổi sau lúc đó).

Công cụ nội bộ `tools/team_adaptive_restore_pre.py` (không ghi CHANGELOG). Chạy khi Jarvis 007 ĐÃ TẮT hẳn:

```
python tools/team_adaptive_restore_pre.py --to 0.154.0 --state-dir /duong/dan/state          # chỉ in kế hoạch
python tools/team_adaptive_restore_pre.py --to 0.154.0 --state-dir /duong/dan/state --yes    # khôi phục thật
```

Không có `--state-dir` thì lấy `JAVIS_STATE_DIR`. Trên VPS thì dừng container trước, chạy công cụ trên thư mục state, rồi
mới chạy bản cũ.

- Về snapshot `.pre-0.154.0`: `team.sqlite3`, `conversations.db`, `resonance.sqlite3`. Đã lên 0.156.0 thì
  `agent_judge.sqlite3` (T3, trước đó không có) bị cất bản sao rồi gỡ, và `resonance.sqlite3.pre-0.156.0` đổi tên thành
  `.superseded-<thời điểm>` (giữ lại; lần nâng sau chụp bản mới đúng dòng thời gian).
- Mất khỏi kho chạy: mọi thay đổi của ba kho sau lúc nâng: tin và phiên chat (chat riêng lẫn nhóm), reaction ở cả hai nơi
  (gồm reaction của agent), nhóm và sổ lượt nhóm, mục tiêu Cộng hưởng, sổ lượt chung, lý do thức, nhịp agent.
- Giữ: bản sao `<kho>.post-0.154.0-<thời điểm>` cạnh mỗi file kho bị đụng (đọc lại bằng sqlite3 khi cần đối chiếu), và
  snapshot `.pre-0.154.0` (nâng lại dùng lại đúng bản này, không chụp đè).
- `kanban.sqlite3` KHÔNG đổi (mốc này không chụp nó): việc nhóm tạo sau lúc nâng còn trong Kanban dù nhóm hay tin của nó
  đã về bản trước.
- An toàn: kiểm cả bộ trước khi ghi (thiếu snapshot của kho đã nâng, snapshot hỏng hay đã có dấu T2 thì dừng, chưa ghi
  gì); ghi xong kiểm lại; một bước hỏng thì trả MỌI kho đã đụng về bản `.post-*` và báo lỗi, không bao giờ báo thành công
  cho lần khôi phục dở. File bị giữ (Jarvis 007 chưa tắt) thì báo rõ và gợi ý tắt hẳn.
- Dấu "đã nâng" mà công cụ dùng: cột `team_reactions.source_kind`, bảng `dm_reactions`, bảng `agent_calls`
  (`test_team_adaptive_restore.py` soi khớp với mã). Kho tạo mới từ 0.154.0 (không có snapshot) thì không có bản trước để
  về: công cụ dừng và nói rõ.
- `--to 0.156.0` (T3) đã có sẵn trong bảng `MILESTONES` của công cụ: gỡ `agent_judge.sqlite3`, về
  `resonance.sqlite3.pre-0.156.0` nếu có. T3 điền bảng dấu của snapshot đó khi chốt.

### 5. Quyết định khi làm

1. **Mã emoji `love`, không `heart`.** Thiết kế 4.1 ghi `heart`; hợp đồng giữ `love` để dữ liệu cũ đọc được. Theo hợp đồng.
2. **Nonce của tin khác trong nhóm trả 409** (0.120.0 chọn 400, xem phần trên) để khớp hợp đồng T2 mục 4 và chat riêng; sửa `test_team_api.py` theo.
3. **Chưa ghi dòng phản chiếu `goal_call:<id>` (`counted = 0`) cho lượt A2.** Chúng chỉ để quan sát; A2 không đổi hành vi.
   T3 thêm khi `agent_daily_calls` cần.
4. **Đối soát theo bản sửa thiết kế của điều phối (d408d89a):** dòng nhóm chỉ theo trạng thái lượt nhóm, ân hạn 120 giây,
   quy tắc 10 phút chỉ cho `mirror_ref = ''`. Bản đầu của nhánh này có hoàn theo tuổi lúc khởi động; đã bỏ.
5. **Kho chung lỗi lúc giữ chỗ:** có đặt trần thì hoàn lượt nhóm và báo lỗi `internal` (không chạy khi không kiểm được
   trần); không đặt trần thì chạy tiếp, đối soát dựng lại dòng tính khi lượt tới mốc engine.
6. **Tác giả chat riêng:** route cấp mã bền cho trợ lý (`agent_register`, Cộng hưởng vẫn tắt) và ghim phiên
   (`session_agent`), như nhóm chat cấp mã cho thành viên. Không tra được thì `agent_key` rỗng.
7. **Tin gắn goal đã kết thúc:** không tạo lý do, trạng thái `no_change` "Mục tiêu đã kết thúc".
8. **Lý do A2 đã phục vụ:** trạng thái `no_change` kèm "Mục tiêu đã đọc phản hồi ở lượt việc kế tiếp" (A2 không báo kết
   quả theo từng phản hồi). Lý do lớp 3 đã phục vụ và tiêu thụ: `no_change` mặc định; T3 ghi `adjusted`/`no_change` thật và
   bộ chiếu không ghi đè.
9. **`revision`** của R là số dòng nhật ký của cặp (tin, người phản hồi).
10. **Reaction của agent vào lượt kế tiếp** của tác giả thành khối riêng "Góp ý của đồng đội"; khối "Phản hồi gần đây
    của chủ nhóm" nay chỉ lấy reaction của chủ.
11. **`agent_wake_sources.group_ref`** (cột thêm ngoài thiết kế) để gỡ nguồn theo cặp (tin, người phản hồi).
12. **`attempt` của lý do tăng lúc nhận;** lượt hoàn không tốn lần thử; đủ 3 lần lỗi thì `failed`.
13. **`waiting_quota`** chưa được ghi ở T2 (thuộc lượt xem xét của T3).
14. **`content_sha`** thêm vào mọi dict tin của kho phiên (`_tin`, `_team_msg`).
15. Câu `FIXED_LIMITS["server_call_ceiling"]` đổi thành "mục tiêu Auto và lượt nhóm".
16. **Nâng cấp không tính lịch sử nhóm vào trần** (review T2 P1, quyết định của chủ): mốc `ceiling_state.t2_migrated_at` ghi một
    lần lúc tạo bảng; đối soát chỉ dựng dòng cho lượt tạo sau mốc (trừ 120 giây) hay còn mở lúc nâng. Quét theo con trỏ bền
    `ceiling_cursor` `(created_at, turn_id)`, tối đa 2000 dòng mỗi lần, cộng nhóm nhỏ lượt còn mở và vừa chốt.
17. **Đổi/bỏ reaction khi lý do đang chạy** (P2-1): nguồn của lý do `claimed` cũng được đánh `removed_at`, nên không bị mang
    sang lý do chờ kế tiếp.
18. **Mọi đường bật Cộng hưởng ghi `resumed_at`**, kể cả đường bật người review của A5 (P2-3).
19. **Route chat riêng** kiểm thân, tin và nonce gửi lại TRƯỚC khi tra tác giả; kho resonance lỗi lúc tra thì reaction vẫn lưu
    (`effect_state = 'pending_author'`, trạng thái Đã nhận kèm lý do) và nhịp phản hồi tra lại rồi chiếu. Bộ chiếu khoá theo cặp
    (tin, người phản hồi) trong tiến trình để request và nhịp không chiếu xen nhau.
20. **Tin báo goal chỉ còn sáu emoji** (chủ quyết định 2026-10-15): hàng Hữu ích / Chưa ổn của A3 không vẽ nữa (cờ
    `A3_REACT_ROW = false` trong `chat-resonance.js`); cảm xúc trên tin báo goal đánh thức goal qua lý do `feedback` của A2. API và
    kho của A3 giữ nguyên, dữ liệu cũ vẫn đọc được. Route reaction chat riêng không kiểm `brain` (giống `GET /sessions/{id}`): phiên là khoá.

### 6. Còn mở

- Đã có `tools/team_adaptive_restore_pre.py --to 0.154.0` (mục 4). `team_chat_restore_pre.py` vẫn chỉ cho `.pre-0.140.0`.
- Khi gộp T1 `d408d89a`: `_REPLY_REASON` hai bên cùng thêm khoá (`lease_lost`, `server_ceiling`), gộp cả hai. Đường
  `lease_lost` trước engine của T1 gọi `_refund_if_unmarked`, nên dòng sổ tự hoàn (test của nhánh này kiểm đúng hàm đó).

### Bằng chứng

Bản đầy đủ: `exports/reviews/team-adaptive/t2-be-evidence.txt` (ngoài repo). Tóm tắt, engine giả, không model thật:

- `test_agent_calls_ledger.py` 67 kiểm, `test_feedback_projector.py` 23, `test_feedback_wake.py` 22, `test_dm_reactions.py`
  49, `test_team_reactions.py` 55 (mở rộng), `test_team_api.py` 83: đều xanh.
- Bộ lọc `team route_table i18n resonance dm_reactions feedback agent_calls sessions`: 85/86, cái đỏ duy nhất (canary nguồn
  của `test_resonance_a1_transport`) đã sửa và xanh ở lần chạy đầy đủ.
- Cả bộ (Python và JS): 698/712. 14 cái đỏ đều đỏ y hệt trên `origin/claude/team-adaptive-t2` (46ae9471) trong một worktree
  sạch (cùng mã thoát, cùng số FAIL): antigravity, grok, cài Windows, ollama máy nhà, terminal, khởi động nhẹ, bản dịch máy...
  `test_link_file_uri` khác số FAIL chỉ vì ổ đĩa (thư mục tạm ở C:, worktree ở D:); đặt TEMP cùng ổ thì giống hệt bản gốc.
