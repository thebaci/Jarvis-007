# Thiết kế bổ sung thống nhất: reaction, heartbeat thích nghi, phán xử theo agent, học trong đội (T2-T4)

Ngày: 15/10/2026. Nền: `main` `1d1b52fa` (0.151.0). Lệnh gốc: `exports/reviews/GOAL-TEAM-CHAT-T1-T4-COMPLETE.md` (bản rà soát
2). Rà hiện trạng: bốn bản recon (T1, reaction, heartbeat, phán xử) tóm ở mục 1. T1 làm song song theo thiết kế team chat đã
duyệt (`2026-10-13-team-chat-design.md`) và không phụ thuộc tài liệu này.

**Bản 2** (sửa theo review độc lập vòng 1, xem mục 15). Tài liệu này là **một** thiết kế cho toàn phần bổ sung, để review một lần. Mọi số trong tài liệu là **tham số khởi tạo có
phiên bản**, không phải kết luận nghiên cứu; chúng được kiểm bằng test đồng hồ giả và chỉ được chỉnh có bằng chứng.

## 0. Thay đổi so với tài liệu cũ (nói rõ, không âm thầm)

| Tài liệu cũ | Nói gì | Nay đổi thành | Vì sao |
|---|---|---|---|
| Spec Resonance 06/10 (`2026-10-06-javis-resonance-design.md`:251,261), roadmap 08/10 | Không gắn tần suất với điểm khen/chê | Nhịp CHỦ ĐỘNG của agent (lớp 3) thay đổi theo ước lượng hữu ích có giới hạn, độ tin và quay lại; lịch trách nhiệm (goal A2, hạn chót, Kanban, nhắc hẹn) **không** đổi theo điểm | GOAL 7.2, 7.3 |
| A3 (`docs/dev/resonance-a3-learning.md` "Những điều không bao giờ xảy ra") | Reaction không tạo lý do thức, không đổi lịch | Reaction hợp lệ trên agent bật Cộng hưởng tạo **một** lý do xem xét gom nhóm theo (agent, ngữ cảnh) và là đầu vào ước lượng hữu ích. Reaction trên agent tắt Cộng hưởng vẫn chỉ lưu và hiển thị | GOAL 6.2, 7.3 |
| A3 làn P | Đề xuất bài học trình bày, chủ duyệt mới áp | Khi Cộng hưởng bật, điều chỉnh trong **phạm vi tự học đã cấp** (nói/im, nhịp, bài học phạm vi nhóm) tự áp có trước/sau, quan sát và tự quay lại; thay đổi quyền, luật của chủ, phạm vi ngoài cấp vẫn chờ chủ | GOAL 8.2 |
| Team chat T1 (spec 13/10 :252, TC8) | Tin của agent không đánh thức ai | Tin của đồng đội/trưởng nhóm mở **lượt xem xét liên quan** chỉ qua sự kiện có cấu trúc (quan hệ việc, input_refs, lệnh `ask_peer`), có trần độ sâu và chống vòng; chữ `@` trong văn bản, trích dẫn và tag giả vẫn không mở gì | GOAL 8.1 |
| Team chat T1 | Bài học `JAVIS_LESSON` ghi vào bộ nhớ chung của agent | Bài học trong nhóm ghi vào kho bài học có **phạm vi nhóm**, có nguồn, lịch sử, thu hồi; chỉ đưa lên phạm vi chung qua tự rà soát có bằng chứng từ nhiều ngữ cảnh hoặc chủ duyệt | GOAL 7.5, 8.2 |
| Chat riêng hiện nay | `JAVIS_LESSON` model đề xuất ghi `MEMORY.md` (đi mọi ngữ cảnh) | Ghi bài học phạm vi `dm:<agent_key>`; chỉ luật chủ và bài học được nâng mới đi mọi ngữ cảnh | GOAL 7.5 |
| Phán xử Zalo | Hai kết luận nói/im; không có sổ lượt | Ba kết luận nói/chờ/im (chờ có điều kiện gỡ); mọi lượt phán xử và tự rà soát vào sổ lượt chung | GOAL 8.1, 8.3 |
| Test emoji (`tests/python/test_icons.py`) | Sáu emoji chỉ được nằm trong `teams.js` | Sáu emoji chỉ được nằm trong **một** bảng dùng chung `dashboard/reactions.js`; mọi chỗ khác vẫn cấm | GOAL 6.1 |

## 1. Hiện trạng tóm tắt (bằng chứng ở các file recon trong gói review)

- **Team chat:** T0-T5 và 0.146.0 đã phát hành. R1-R9 đạt trên head (script reviewer, bản thích nghi engine giả). Thiếu: chốt
  quyền theo lượt (lượt cũ hưởng quyền cấp lại), lease bận/việc không gia hạn trong lượt dài, cap `running_jobs` > 1 không có
  hiệu lực, bảng giới hạn chưa đủ. Các mục này là việc của T1 (PR riêng).
- **Reaction:** sáu reaction có ở team chat (lưu, lý do, góp ý, chống trùng nonce, nhiều tab) nhưng **không** đánh thức ai, chỉ
  chủ được thả, nhật ký thiếu agent/việc/giá trị trước, không có trạng thái. Chat riêng: không có reaction trên câu trả lời
  agent; chỉ có cặp Hữu ích/Chưa ổn của A3 trên tin báo goal. Bong bóng chat chưa mang mã tin.
- **Heartbeat:** lớp 1 (lease) và lớp 2 (A2 theo goal) có. Lớp 3 (theo agent) **chưa có**. Không có sự kiện "đã xem". Sổ lượt
  rời rạc ở năm nơi.
- **Phán xử:** bộ phán xử Zalo tách được "được gọi" khỏi "có nên nói", có học theo ca, tự rà soát có trước/sau và tự quay
  lại, nhưng gắn chặt bot/kênh, chỉ hai kết luận, không sổ lượt, kho ca lấy chéo mọi chat (rò ngữ cảnh nếu dùng nguyên cho
  agent nhiều nhóm).
- **Học:** bài học agent trộn mọi ngữ cảnh, không nguồn, không thu hồi; đồng đội không có kênh góp ý.

## 2. Khái niệm chung

- **Agent:** định danh bền `agent_key` do host cấp (`resonance_agents`). Mọi bảng mới khoá theo `agent_key`, không theo slug; API
  của giao diện nhận slug nhưng host đổi sang `agent_key` đang hoạt động trước khi đọc/ghi (slug có thể bị dùng lại).
- **Ngữ cảnh (`context_ref`):** `team:<team_id>` hoặc `dm:<agent_key>` (toàn bộ chat riêng của chủ với agent đó, mọi phiên kênh
  `agent:<slug>` gộp chung; ranh giới riêng tư là chat riêng khác nhóm, mã phiên chỉ dùng ở tham chiếu tin). Phần tổng hợp
  theo agent dùng `context_ref = "*"` (chỉ để hiển thị và khởi tạo). Không đưa nội dung của ngữ cảnh này vào prompt ngữ cảnh khác.
- **Câu trả lời ở trang Trò chuyện chính** (không có agent, tác giả là Jarvis 007): có sáu reaction để lưu và hiển thị (`agent_key`
  rỗng); không vào ước lượng hữu ích hay phán xử của agent nào.
- **Sự kiện nguồn:** mọi tác động trỏ về một `source_ref` duy nhất (`rx:dm:<log_id>`, `rx:team:<log_id>`, `decision:<id>`,
  `step:<id>`, `seen:<context>:<message_id>`). Mỗi loại tác động có chỉ mục duy nhất theo `source_ref`.
- **Kho nào chứa gì (không có giao dịch xuyên kho):**

| Kho | Bảng mới / cột mới |
|---|---|
| `conversations.db` (tin chat riêng) | `dm_reactions`, `dm_reaction_log` |
| `team.sqlite3` | cột mới của `team_reactions`, `team_reaction_log` (mục 4.1) |
| `resonance.sqlite3` | `agent_calls`, `agent_wake_reasons`, `agent_wake_sources`, `agent_pulse`, `agent_pulse_events`, `pulse_signals`, `pulse_contrib`, `message_seen`, `pulse_opportunities` (khoá `(agent_key, context_ref, source_ref, version)` cơ hội đã tiêu thụ), `agent_lessons`, `agent_lesson_events`, `agent_peer_feedback` |
| `agent_judge.sqlite3` (mới, dữ liệu nội bộ, tách khỏi kho phán xử khách Zalo) | `profiles`, `decisions`, `offsets`, `cases`, `waits`, `changes`, `review_state` |

- **Cộng hưởng (công tắc theo agent) và phạm vi:**

| Năng lực | Cộng hưởng tắt | Cộng hưởng bật |
|---|---|---|
| Trả lời lời gọi trực tiếp, làm việc được giao, việc nhóm | Có | Có |
| Phán xử nói/chờ/im khi tham gia nhóm (chính sách hiện có, đóng băng) | Có | Có |
| Lưu và hiển thị reaction | Có | Có |
| Lý do xem xét từ reaction, nhãn dạy phán xử làm đổi ngưỡng, tự rà soát, tự áp bài học | Không (nhãn chỉ lưu) | Có |
| Heartbeat thích nghi: nhịp chủ động, ngủ, tự tìm việc, nhắc tiếp trong chat riêng | Không | Có |

  **Bật lại:** host ghi `resumed_at = now` vào `agent_pulse` mọi ngữ cảnh của agent. Mọi bộ đếm kích hoạt (lý do xem xét, tự rà
  soát, đếm nhãn, đếm tín hiệu mới) chỉ tính sự kiện **sau** `resumed_at`; phản hồi trước mốc chỉ là bằng chứng/ngữ cảnh, không tạo
  lượt bù, không đặt lại ngân sách. Đường bật bằng lệnh trưởng nhóm (Toàn quyền) cũng ghi `resumed_at` và gọi `wake_agent_goals`
  như đường của chủ.

## 3. Sổ lượt chung, vòng đời lý do, khoá theo agent

### 3.1 `agent_calls` (resonance.sqlite3)

`id, agent_key, brain_id, context_ref, purpose (reply|step|judge_batch|review|proactive|scan|reaction_review|goal), reason_ref,
attempt, engine, model, status (reserved|running|ok|error|refunded|interrupted), counted (0|1), obligation (0|1), tokens_in,
tokens_out, cost_usd, mirror_ref, created_at, settled_at`. Chỉ mục duy nhất **từng phần**: `UNIQUE(reason_ref) WHERE status IN
('reserved','running','ok')`. Một lý do chỉ có tối đa một lượt đang hoặc đã chạy thành công; lượt `refunded`/`interrupted`/`error`
không giữ khoá nên thử lại được (attempt + 1).

- **Một sổ duy nhất cho trần chung** (sửa sau review T1, xem 9.1): mọi lượt thuộc phạm vi trần được **giữ chỗ trong sổ này TRƯỚC khi
  gọi engine**, cùng giao dịch `BEGIN IMMEDIATE` với phép đếm, nên kiểm trần và giữ chỗ nguyên tử kể cả khi nhiều lượt (nhiều luồng,
  nhiều tiến trình cùng kho) chạy đồng thời. Cột `counted` nói dòng có cộng vào trần không, thay cho quy tắc cũ "`mirror_ref = ''`".
- Lượt nhóm (trả lời, bước việc): `team_turns` giữ trần ngày của nhóm như hiện nay, **và** giữ chỗ một dòng `counted = 1`,
  `mirror_ref = team_turn:<id>` ở sổ này ngay sau khi giữ chỗ `team_turns`, trước khoá bận và trước engine. Trần chung đầy thì hoàn
  dòng `team_turns` vừa giữ và lượt nhận kết cục `cap` với `cap = "server_ceiling"` (không gọi engine). Lượt nhóm hoàn (lỗi trước mốc
  gọi engine, hết lượt chờ, huỷ) thì dòng sổ cũng `refunded`; chốt `ok`/`error`/`interrupted` thì dòng sổ chốt theo.
- Lượt goal A2 và bộ lập mục tiêu đã được đếm ở `goals.calls_used` và `call_ledger` (không đổi hành vi A2): bản phản chiếu của chúng ở
  sổ này mang `counted = 0`, `mirror_ref = goal_call:<id>` (chỉ để quan sát và để `agent_daily_calls` biết lượt nào đã chạy).
- Lượt chỉ có ở sổ mới (phán xử theo lô, xem xét, chủ động, quét, xem xét reaction) mang `counted = 1`, `mirror_ref = ''`.
### 3.2 Vòng đời lý do thức theo agent (`agent_wake_reasons`)

`id, agent_key, context_ref, code (reaction_review|related_review|proactive_due|scan_due|wait_unblocked), status (pending|claimed|
served|superseded|failed), attempt, ledger_ref, created_at, updated_at`; nguồn ở `agent_wake_sources(reason_id, source_ref UNIQUE,
added_at, removed_at, consumed_at)`. Chỉ mục duy nhất `(agent_key, context_ref, code) WHERE status = 'pending'`: tối đa một lý do
**chờ** mỗi loại mỗi ngữ cảnh, gom nguồn mới vào; một lý do `pending` mới được phép cùng tồn tại với một lý do đang `claimed`. Nguồn đến
trong lúc lượt xem xét đang chạy vào lý do `pending` mới, không vào lý do đang chạy.

`pending → claimed` (CAS, giữ chỗ `agent_calls`; danh sách nguồn được chốt lúc nhận) `→ served` chỉ khi lượt chốt `ok`. Lúc `served`,
nguồn nào **không** nằm trong `consumed` của lượt được chuyển sang lý do `pending` cùng loại (tạo mới nếu chưa có); test: reaction đến
khi lượt xem xét đang chạy được xem xét đúng một lần ở lượt sau. Lượt kết thúc `interrupted/refunded/error`: nếu đã có lý do
`pending` cùng loại (tạo trong lúc chạy) thì chuyển nguồn của lý do đang chạy sang lý do chờ đó, giữ `attempt` lớn hơn, đánh lý do đang
chạy `superseded` (test "lỗi khi đã có lý do chờ mới hơn"); nếu chưa có thì `→ pending`
(attempt + 1), quá 3 lần → `failed` (hiển thị, chủ bấm thử lại). Nguồn bị bỏ (reaction gỡ) khi lý do còn `pending`: đánh
`removed_at`; lý do không còn nguồn nào → `superseded`.

### 3.3 Định tuyến chuẩn khi một sự kiện thuộc nhiều lớp

- Reaction trên tin có `goal_id` (tin báo goal, hoặc tin trong chat riêng gắn goal): chỉ tạo lý do `feedback` của goal ở **A2**
  (`wake_reasons` hiện có, `source_ref = rx:...`); lớp 3 chỉ ghi **tín hiệu** hữu ích, không tạo lý do riêng.
- Reaction trên tin không gắn goal: lớp 3 tạo lý do `reaction_review`.
- `effective_due` (mục 5.1) bỏ qua agent đang có lượt A2 hoặc lượt nhóm chạy (khoá bận, 3.4) và dời 60 giây.

### 3.4 Khoá bận dùng chung theo agent

Khoá `agent_busy` hiện có (team_store, có gia hạn từ T1) trở thành khoá của **mọi** lượt mang persona agent: lượt nhóm, chủ động,
xem xét reaction, quét việc, và lượt goal A2. Lượt A2 gặp khoá bận thì dời 30 giây (không tính là lỗi). Lượt phán xử theo lô không
mang persona nên không lấy khoá. Lượt chủ động/quét/xem xét thử khoá **không chờ trước khi** nhận lý do (CAS) và giữ chỗ sổ lượt;
bận thì không nhận, lý do giữ `pending`, `attempt` không tăng. Lượt chủ động/quét/xem xét cũng bỏ qua lần này nếu agent đang có việc nhóm hoặc
goal xếp hàng; thời gian tối đa một lượt (10 phút) nằm trong một kỳ lease (15 phút). Test: việc nhóm xếp hàng trong lúc quét bắt đầu
sau tối đa một lượt quét.

### 3.5 Outbox: ghi reaction rồi chiếu tác động (không giao dịch xuyên kho)

Ghi reaction (kho của reaction) kèm `effect_state = 'pending'` trên dòng nhật ký. Bộ chiếu `feedback_projector.project(log_row)`
idempotent theo `source_ref` (UNIQUE ở `agent_wake_sources`, UNIQUE `(source_ref, agent_key)` ở `pulse_signals`): tạo/gom lý do, ghi tín hiệu, rồi đặt `effect_state =
'done'` và `effect_refs_json`. Bộ chiếu chạy ngay sau khi ghi (cùng request, nếu lỗi thì bỏ qua) và chạy lại mỗi nhịp pulse và lúc
khởi động cho mọi dòng còn `pending`. Thứ tự: mỗi cặp (tin, người phản hồi) được chiếu **theo đúng thứ tự mã nhật ký**; dòng `pending`
mà đã có dòng mới hơn của cùng cặp thì chỉ áp **trạng thái ròng** của dòng mới nhất và đánh các dòng cũ `superseded`. Trạng thái hiển
thị trên reaction cũng do bộ chiếu ghi ngược sau khi lý do đổi trạng thái.

## 4. T2: sáu reaction ở chat riêng và chat nhóm

### 4.1 Dữ liệu

- `dm_reactions` (conversations.db): `session_id, message_id, reactor, source_kind (owner|leader|member), agent_key,
  agent_config_version, value (like|heart|haha|wow|sad|angry|NULL), reasons_json, axis (should_speak|should_silent|''), comment,
  content_sha, seen_sha, stale, goal_id, revision, status, status_reason, updated_at, PRIMARY KEY(session_id, message_id, reactor)`;
  `dm_reaction_log(id, session_id, message_id, reactor, prev_json, next_json, nonce UNIQUE, effect_state, effect_refs_json,
  created_at)`.
- Team: `ALTER TABLE team_reactions ADD` `source_kind TEXT NOT NULL DEFAULT 'owner'`, `axis TEXT NOT NULL DEFAULT ''`, `status TEXT
  NOT NULL DEFAULT 'received'`, `status_reason TEXT NOT NULL DEFAULT ''`, `seen_sha TEXT`, `stale INTEGER NOT NULL DEFAULT 0`;
  `team_reaction_log ADD` `agent_key`, `task_id`, `prev_json`, `effect_state TEXT NOT NULL DEFAULT 'done'`, `effect_refs_json`. Dòng
  cũ coi như đã chiếu xong (không backfill tác động). Cột mới đều có mặc định nên bản cũ vẫn chạy trên kho đã nâng.
- `content_sha` tính trên nội dung đã lưu (sau khi bỏ khối điều khiển). `seen_sha` do client gửi; lệch thì `stale = 1`, vẫn nhận.
- Nguồn do host gán: `owner` qua route dashboard; `leader`/`member` chỉ qua lệnh có cấu trúc trong lượt của agent
  (`{"op":"react","message_id":..,"value":..}`), host lấy danh tính từ lượt; không thả lên tin của chính mình. Reaction của agent
  không vào ước lượng hữu ích (chống tự thưởng), chỉ là góp ý cộng tác.
- Chống trùng: client sinh `nonce` một lần cho mỗi thao tác và **dùng lại** khi thử lại sau lỗi mạng.

### 4.2 Giao diện

- Bảng sáu emoji, `nextReaction`, chip, bộ chọn, nhấn giữ chuyển vào `dashboard/reactions.js` (bảng sáu emoji duy nhất của repo;
  `test_icons` đổi phạm vi ngoại lệ sang file này). `teams.js`, `app.js` (bong bóng trả lời, bong bóng stream sau khi chốt, lịch sử)
  và `mobile-chat.js` dùng chung.
- Bong bóng mang `data-mid`: lịch sử lấy `m.id`; lượt mới nhận `message_id` qua gói `turn_saved` phát sau `_persist_turn` (hàm trả mã
  tin). Chưa có mã thì chưa có nút reaction.
- Hai nhóm chip riêng: sáu lý do chất lượng (T2) và trục "Đáng lẽ nên nói" / "Nên im (chen ngang)"; góp ý chữ tuỳ chọn; không bắt
  buộc gì để thả emoji.
- Nhiều tab: gói WS `chat_reaction` (chat riêng) và `team_message` (đã có); khung lọc theo việc của nhóm cũng nhận gói.
- Trạng thái dưới chip theo host: Đã nhận; Chờ xem xét; Đang xem xét; Đã điều chỉnh; Không cần đổi; Chờ hạn mức (mỗi trạng thái có
  lý do ngắn). Agent tắt Cộng hưởng (hay phản hồi có trước lúc bật lại): "Đã nhận, chỉ lưu" kèm lý do đúng trường hợp.
- Điện thoại: nút luôn hiện, vùng chạm 44px, chữ 16px.

### 4.3 Hiệu lực

- Định tuyến theo 3.3, ghi qua outbox 3.5, chỉ khi agent bật Cộng hưởng và sự kiện sau `resumed_at`.
- Đổi/bỏ: nhật ký trước/sau; nguồn trong lý do còn chờ bị gỡ; tín hiệu đã ghi chuyển `superseded_by` (mục 6.3).
- Emoji không chốt đạt, không đổi ưu tiên, không cấp quyền, không đổi trạng thái việc/goal (test cho cả chat riêng).
- Khối phản hồi (như `_feedback_lines` T2, có ghi chú "emoji là cảm xúc") vào lượt kế tiếp của agent trong **đúng ngữ cảnh**; chat
  riêng thêm khối này vào lời nhắc của lượt `agent:<slug>`.

### 4.4 Lượt xem xét reaction (bộ xử lý thật, T3; T2 chỉ tạo lý do)

Khi lý do `reaction_review` được phục vụ: host dựng lời nhắc gồm tin bị phản hồi, các reaction/lý do/góp ý trong nguồn của lý do,
và yêu cầu đầu ra có cấu trúc:

`{"outcome": "keep"|"ask_back"|"revise"|"lesson", "message": "...", "lesson": {"text": "...", "kind": "presentation"|"method"},
"consumed": ["rx:..."], "reason": "..."}`

- `keep`: không gửi gì. `ask_back`: gửi **một tin mới** hỏi lại, trả lời tin bị phản hồi. `revise`: gửi một tin mới là bản sửa (không
  sửa đè tin cũ), chỉ trong phạm vi được phép của ngữ cảnh (chat riêng; nhóm thì qua phán xử như mọi tin tự phát). `lesson`: ghi bài
  học có phạm vi ngữ cảnh (mục 8), có thể kèm `keep`.
- Host kiểm `consumed ⊆ nguồn của lý do`; sai cấu trúc hay `consumed` lệch: lượt `error`, lý do về `pending` (3.2).
- Trạng thái theo **kết quả host thật**: `keep` → "Không cần đổi"; `lesson` → "Đã điều chỉnh"; `ask_back`/`revise` → "Đã điều chỉnh"
  chỉ khi tin mới thật sự được gửi; nếu phán xử (trong nhóm) chọn im thì "Không cần đổi (phán xử chọn im)". Ghi trên mọi reaction trong
  `consumed`.
- Bằng chứng tác động: quyết định ghi vào `agent_pulse_events`; bài học mới xuất hiện trong lời nhắc lượt sau của đúng ngữ cảnh (test
  kiểm prompt kế tiếp chứa bài học và mã nguồn).

## 5. T3: heartbeat thích nghi (lớp 3)

### 5.1 Một nơi quyết định lịch, chạy ngoài tick goal

Module thuần `server/agent_pulse.py` (policy `pulse.v1`). Một coroutine nhịp 30 giây **riêng** trong `_scheduler_loop` (cờ bận
riêng, không nằm trong `_resonance_tick`), chỉ làm việc nhanh bằng code: chiếu outbox còn chờ, tìm `agent_pulse.next_due_at <= now`
và lý do `pending`, nhận lịch bằng CAS, rồi **spawn** lượt cần model ra tác vụ riêng (giữ chỗ sổ lượt trước). `effective_due(agent,
context)` hợp nhất lịch chủ động và lý do đang chờ của lớp 3; không đụng `wake_reasons` của goal. Lịch trách nhiệm (goal, hạn chót,
Kanban, nhắc hẹn) chạy theo nguồn của nó, không bị lớp 3 làm chậm.

### 5.2 Trạng thái (theo agent x ngữ cảnh)

Thang bậc: `B0 15 phút, B1 1 giờ, B2 4 giờ, B3 1 ngày, B4 3 ngày, B5 1 tuần, B6 2 tuần, B7 1 tháng`, trên B7 là ngủ đông (không có
lịch chủ động). Bậc khởi tạo B3.

| Trạng thái | Nghĩa | Vào khi | Ra khi |
|---|---|---|---|
| `active` | bậc B0-B2 | lên bậc tới B2 | xuống dưới B2 |
| `awake` | bậc B3-B4 | mặc định, hoặc thức lại | đổi bậc |
| `slowed` | bậc B5-B7 | xuống tới B5 | lên bậc |
| `hibernating` | sau B7 | ở B7 qua hai kỳ liền không tín hiệu, không cơ hội | sự kiện thức |
| `waiting_owner` | chờ chủ | phán xử/việc cần chủ quyết | chủ trả lời/huỷ; nhắc một lần sau 24 giờ rồi giữ nguyên |
| `paused` | chủ tạm dừng | chủ bấm Tạm dừng | chủ bấm Tiếp |
| `off` | Cộng hưởng tắt | tắt (và mọi agent đang tắt lúc nâng cấp) | bật: về bậc B3, giữ ước lượng cũ, ghi `resumed_at` |

`paused`, `waiting_owner`, `off`, `hibernating` chỉ dừng phần **chủ động**; việc đã nhận, hạn chót, goal, lời gọi trực tiếp vẫn chạy.
**Thức lại:** bậc mới = `min(bậc hiện tại, B3)` (đang nhanh hơn B3 thì giữ), giữ nguyên ước lượng, ký ức và lịch sử; kích hoạt bởi
chủ nhắn/gọi trực tiếp agent trong ngữ cảnh, giao việc mới, reaction mới hợp lệ, sự kiện liên quan có cấu trúc (7.5).

### 5.3 Điều chỉnh nhịp (chỉ theo bằng chứng mới, có độ trễ)

Mỗi **kỳ đánh giá** (tới lịch chủ động hoặc khi phục vụ lý do), theo thứ tự:

1. `new = Σ w·decay` của tín hiệu **sau** `last_change_at` và sau `resumed_at`. Không đổi bậc nếu chưa ở bậc hiện tại đủ **thời gian
   tối thiểu** `dwell = max(2 × khoảng của bậc, 1 ngày)`.
2. Lên một bậc nếu `u ≥ +0.25` **và** `new ≥ 1.0`, không quá `max_tier` được cấp (mặc định B1, chủ có thể cấp B0; Toàn quyền không
   nâng được trần này).
3. Xuống một bậc nếu `u ≤ -0.25` và `new ≥ 1.0` (lý do `unhelpful`).
4. Xuống một bậc nếu không có tín hiệu mới và không có cơ hội (lý do `low_demand`, không ghi là agent sai) trong hai lần khoảng hiện
   tại.
5. Ngược lại giữ.
6. Hysteresis: đổi chiều chỉ sau ít nhất một kỳ giữ nguyên.

Bằng chứng cũ không thể tự đẩy bậc mãi: bước 2-3 cần bằng chứng mới; bước 4 kéo nhịp chậm lại khi im lâu.
Bổ sung khi làm T3 (độ lệch đã chấp nhận, xem mục 15): bước 4 còn xuống bậc (`low_demand`) khi tín hiệu tương tác gần nhất và
cơ hội gần nhất đều cũ hơn `max(4 x khoảng, 3 ngày)`, để một reaction ngay sau lần đổi bậc không giữ nhịp nhanh mãi mãi. Mọi lần đổi bậc ghi
`agent_pulse_events` (trước/sau, nguồn, `u`, `new`, lý do, `policy_version`). Chủ có thể quay lại một thay đổi hoặc đặt lại ngữ cảnh.

**Vectơ test đồng hồ giả bắt buộc** (từ B3, Cộng hưởng bật, giá trị tính theo 6.3, có kèm số trong test):

| Kịch bản | Kỳ vọng |
|---|---|
| Chủ chỉ dùng ❤️, 1 ❤️ (`k ≈ 1.00`, `u ≈ 0.05`) hay 2 ❤️ (`k ≈ 0.99`, `u ≈ 0.13`) | giữ B3 |
| Chủ chỉ dùng ❤️, 5 ❤️ trong 3 ngày (tuổi trung bình 1,5 ngày, `k ≈ 0.935`, `u ≈ 0.28`) | lên đúng một bậc (B2) sau dwell; không lên tiếp nếu không có tín hiệu mới |
| Chủ chỉ dùng ❤️, 5 ❤️ rải đều 2 tuần (`u ≈ 0.248`) | giữ B3 (sát ngưỡng; test ghim mốc thời gian chính xác) |
| Chủ chỉ dùng ❤️, 10 ❤️ trong 1 phút (`k ≈ 0.82`, `u ≈ 0.39`) | tối đa một bậc ở kỳ đó; kỳ sau không lên nữa vì không có bằng chứng mới |
| Sau đó thêm 10 ❤️ rải trong 2 tuần | lên B1 (= `max_tier`), không bao giờ B0 |
| Chủ dùng lẫn (3 👍, 1 ❤️, 1 😮 trong vài ngày, `n = 5`) | `k(❤️) = k(😮) ≈ 0.997`, `k(👍) ≈ 0.966`; emoji chưa dùng lần nào `k ≈ 1.013`; mọi `k` trong 0.75-1.25 |
| Im hoàn toàn từ B3 | khoảng ngày 2 xuống B4, ngày 8 B5, ngày 22 B6, ngày 50 B7, ngày 110 ngủ đông; tức tới ngày 30 đang ở B6, ngày 90 ở B7, ngày 180 đang ngủ đông |
| 3 tin chủ động đã xem bị bỏ qua | ước lượng âm nhẹ (`u ≈ -0.02`), không tự xuống bậc vì `unhelpful`; chỉ `low_demand` nếu cũng không có gì khác |
| 5 reaction có lý do "sai dữ kiện" (`u ≈ -0.24`) | giữ (chưa đủ); reaction thứ 6 (`u ≈ -0.27`) thì xuống một bậc (`unhelpful`) sau dwell |
| im lặng đúng (không tín hiệu, có cơ hội nhưng phán xử chọn im) | không phạt; không coi là `low_demand` khi có cơ hội |
| chủ gọi trực tiếp lúc ngủ đông | về B3 ngay, giữ ước lượng |

### 5.4 Lưu bền và restart

`agent_pulse(agent_key, context_ref, state, tier, next_due_at, estimate, confidence, n_eff, last_eval_at, last_change_dir,
last_change_at, resumed_at, max_tier, scan_counter, policy_version, updated_at, PK(agent_key, context_ref))`. Nhận lịch bằng CAS;
chết giữa chừng thì lịch tự tới hạn lại. Lệch đồng hồ: tuổi âm kẹp về 0, `next_due_at` quá khứ xa chỉ chạy một lần rồi tính lại.

### 5.5 Lần thức: code trước, model sau

`Thức không đồng nghĩa gọi model. Gọi model không đồng nghĩa gửi tin.` Mỗi lần thức chạy bước code: cập nhật ước lượng, tính bậc,
lập **danh sách cơ hội** trong phạm vi đã giao bằng code: việc nhóm agent là thành viên có cập nhật cũ hơn khoảng hiện tại, việc bị
chặn có dữ kiện mới, goal của agent chờ chủ quá 24 giờ, đề xuất chưa ai xử lý, lý do đang chờ. Mỗi cơ hội có khoá `(source_ref,
version)` (bảng `pulse_opportunities`, bền qua restart) và chỉ được tiêu thụ **một lần** (kể cả khi lượt quét trả `none`) cho tới khi nguồn có phiên bản mới; cơ hội đã tiêu thụ không
mở lượt quét nữa và **không** được tính là "có cơ hội" ở luật `low_demand` (5.3). Không có gì: ghi `no_action`, ngủ.

- Có lý do `reaction_review`/`related_review`/`wait_unblocked`: chạy lượt tương ứng (4.4, 7.5, 7.4).
- Có cơ hội: chạy lượt **quét** (purpose `scan`) với danh sách đó làm đầu vào, đầu ra có cấu trúc `{"action": "none"|"propose"|
  "enqueue"|"say", ...}`. `enqueue` chỉ khi quyền của agent cho phép (qua hàng đợi chung, có nguồn); không có quyền thì `propose` (thẻ
  đề xuất cho chủ/trưởng nhóm); `say` qua phán xử (mục 7). Tối đa một hành động mỗi lần quét.
- Ở `active`/`awake`, dù danh sách rỗng, cứ mỗi 3 lần thức có một lượt quét giới hạn (đếm `scan_counter`, tối đa một lượt/ngày/ngữ
  cảnh) để agent có cơ hội tự thấy việc từ nguồn đã giao; quét không thấy gì không tạo tín hiệu xấu.
- Không tạo việc để giữ mình hoạt động; đề xuất không được duyệt không mở lại nếu không có dữ kiện mới.

## 6. T3: ước lượng hữu ích

### 6.1 Tín hiệu (`pulse_signals`, một dòng mỗi sự kiện nguồn mỗi agent, UNIQUE `(source_ref, agent_key)`)

| Nguồn | Giá trị khởi tạo (giả thuyết `pulse.v1`) | Độ tin nguồn `w` |
|---|---|---|
| ❤️ / 😮 / 👍 không lý do | +0.8 / +0.6 / +0.4 | 1.0 |
| 😂 không lý do | +0.2 | 0.5 (không mặc định là khen chất lượng) |
| 😢 / 😡 không lý do | -0.2 / -0.4 | 0.4 (có thể là cảm xúc về sự việc) |
| Reaction có lý do chất lượng | đúng ý +0.8; quá dài -0.3; sai dữ kiện, thiếu ý, khó hiểu, lạc đề -0.6 (lý do thắng emoji) | 1.0 |
| Trục nói/im | không vào ước lượng (dạy phán xử, 7.6) | |
| Chấp nhận đề xuất, chốt quyết định, dùng kết quả có sự kiện host | +0.6 | 0.8 |
| Sửa yêu cầu sau kết quả, huỷ, bác đề xuất, thu hồi | -0.4 | 0.8 |
| Kiểm khách quan đạt / không đạt | +0.5 / -0.5 | 0.8 |
| Tin chủ động đã xem (6.2), qua 24 giờ không tương tác | -0.15 | 0.6 |
| Tin chủ động chưa có bằng chứng xem; im lặng/quan sát; việc bắt buộc đã giao | không tạo tín hiệu | |
| Reaction của agent; agent tự nhận công | không tạo tín hiệu | |

### 6.2 Sự kiện "đã xem" (`message_seen`, resonance.sqlite3)

Dashboard gửi `POST /seen {context_ref, message_ids}` khi tin của agent nằm trong khung nhìn ≥ 1,5 giây và tab đang hiển thị (nhóm
và chat riêng). Host ghi lần đầu. Chỉ tin của agent trong Jarvis 007; không theo dõi gì khác.

### 6.3 Công thức (`pulse.v1`)

- Suy giảm theo thời gian, nửa đời 21 ngày (`decay`).
- **Cá nhân hoá theo người phản hồi và loại ngữ cảnh** (nhóm hay chat riêng), **chỉ cho reaction không kèm lý do** (reaction có lý do
  chất lượng dùng giá trị của lý do, `k = 1`): với người r, loại ngữ cảnh c, emoji e: `n` = số reaction của r trong c, tỷ lệ làm trơn
  `p_s(e) = (số lần e + 3)/(n + 18)`, `p̄ = 1/6`, `k = clamp(1 + 0.3 × (p̄ − p_s(e))/p̄ × n/(n + 20), 0.75, 1.25)`, `v = v0(e) × k`. `k`
  **tính lại ở mỗi kỳ đánh giá** từ lịch sử hiện tại (không đóng băng lúc ghi). Ít mẫu thì `k ≈ 1`; làm trơn và trần 0.75-1.25 giữ
  người dùng nhất quán khỏi trôi về âm (lời khen quen dùng của họ vẫn ≥ 0.75, emoji hiếm tối đa 1.25); độ hiếm không đứng một mình làm
  kết luận.
- Prior về 0: `estimate = Σ w·v·decay / (Σ w·decay + 2)`; `n_eff = Σ w·decay`; `confidence = n_eff / (n_eff + 4)`; `u = estimate ×
  confidence`. Im lâu thì `estimate` và `confidence` cùng về 0.
- Mỗi sự kiện nguồn đóng góp `|w·v| ≤ 1`. `pulse_signals` có chỉ mục duy nhất `(source_ref, agent_key)`: phản hồi phân bổ cho nhiều
  agent (6.5) ghi một dòng mỗi agent với `share`; agent đó dùng `w·share` ở cả tử số lẫn `n_eff`. Tổng `share` của một nguồn bằng 1
  (test).
- Thay/bỏ reaction: dòng cũ `superseded_by`; xoá nguồn (xoá tin/agent): `void`. Không cộng dồn.
- Theo ngữ cảnh: tính riêng từng `context_ref`; bản `*` chỉ hiển thị và là giá trị khởi tạo cho ngữ cảnh mới (nhân 0.5).
- Không tối ưu số tim/tin/lượt: tin không có tín hiệu không có điểm.

### 6.4 Quay lại thay đổi chính sách

Chỉ áp cho thay đổi **chính sách** (độ lệch ngưỡng phán xử, độ hăng hái, bài học tự áp, phiên bản `pulse`), không áp cho bước bậc
(bậc chỉ theo 5.3). Sau thay đổi có cửa sổ quan sát (≥ 6 nhãn hoặc ≥ 5 tín hiệu mới, tối đa 14 ngày); tỷ lệ lỗi phán xử tăng quá 0.15
(≥ 6 nhãn) hoặc `estimate` của ngữ cảnh giảm quá 0.3 (`confidence ≥ 0.5`) thì tự quay lại và ghi lý do. Không tuyên bố cải thiện khi
chưa qua cửa sổ.
Ghép T3: dịch ngưỡng do nhãn của chủ là chủ dạy trực tiếp, không mở cửa sổ quay lại; cửa sổ chỉ mở cho thay đổi do tự rà soát
(phần L ghi) và đổi phiên bản `pulse`.

### 6.5 Ghi nhận đóng góp (`pulse_contrib`)

- Chuỗi do host ghi: bước làm/hỗ trợ (`team_steps`) với `input_refs`; tin tổng hợp trỏ các bước đã dùng.
- Phản hồi của chủ trên **bản tổng hợp** (một sự kiện nguồn, tổng 1.0): "được dùng" là **tập đầu vào host đã đưa cho bước tổng hợp**
  (`input_refs` của bước đó, do host ghi), không phải trích dẫn agent tự khai; agent tổng hợp không thể thu hẹp tập này. 0.8 chia cho các
  bước trong tập **chia đều theo tập đầu vào của host** (không theo số lần trích dẫn trong văn bản tổng hợp), trần 0.6 mỗi agent;
  phần vượt trần chia tiếp cho các người đóng góp khác còn dưới trần, chỉ khi mọi người đã chạm trần mới về tác giả tổng hợp; 0.2 còn lại
  về tác giả tổng hợp. Tập rỗng (câu
  trả lời trực tiếp không qua bước nào): tác giả nhận 1.0. Một agent vừa làm bước vừa tổng hợp: gộp phần, không đếm hai lần. Tác giả tổng hợp **không** nhận
  thêm tín hiệu trực tiếp riêng ở 6.1 cho cùng nguồn.
- Thay bản kết quả: phân bổ cũ `superseded`, tính lại theo bản mới. Trích dẫn/chuyển tiếp/tổng hợp nhiều tầng không nhân điểm (một
  nguồn phân bổ một lần).
- Agent không tự nhận công; điểm hữu ích không thành quyền (chỉ trong `max_tier`).

## 7. T3: bộ phán xử của từng agent

### 7.1 Kiến trúc

Module thuần `server/agent_judge.py` theo hình dạng phán xử Zalo (tách được gọi / có nên nói, cổng thô, ca theo ngữ cảnh, ngưỡng có độ
lệch, tự rà soát), không gọi mã bot. Kho `agent_judge.sqlite3`: `profiles(agent_key, role_text, eagerness, role_hash)`, `decisions(id,
agent_key, context_ref, source_event, verdict speak|wait|silent, address certain|none, score, threshold, reason, silence_code,
wait_until_json, ledger_ref, label, label_source, created_at)`, `offsets(agent_key, context_ref, offset, updated_at)`, `cases(agent_key,
context_ref, text_sha, features_json, label, weight, created_at)`, `waits(decision_id, agent_key, context_ref, until_kinds, until_ts,
status, rejudged)`, `changes(...)`, `review_state(agent_key, last_review_at)`.

Hồ sơ riêng từng agent; ngưỡng và ca **theo ngữ cảnh** (ca thô chỉ lấy cùng ngữ cảnh). Kết quả chỉ là `{verdict, score, reason,
wait_until, ask_clarify}`; câu trả lời do agent tạo.

### 7.2 Chat nhóm

1. Được gọi trực tiếp (mentions có cấu trúc, ô điều phối của tin thường, việc giao): đường trả lời hiện có, không qua phán xử; ghi
   `decision` `address=certain`.
2. Không được gọi: lọc bằng code cho từng thành viên hoạt động (quan hệ việc mở, câu hỏi chung cho nhóm, từ khoá vai, đóng góp liên quan
   gần đây). Không qua cổng: `silent`/`no_signal`, không model.
3. Ứng viên qua cổng: **một** lời gọi theo lô (spawn ngoài request), engine là model việc nền người dùng đã chọn, timeout 25 giây,
   tối đa 2 lô đồng thời toàn máy; một dòng `agent_calls` purpose `judge_batch` (`agent_key` rỗng, `context_ref` nhóm), mỗi agent
   một `decision` trỏ `ledger_ref` về dòng đó. Chi phí tính cho nhóm, không chia cho agent.
4. Điều phối: tối đa `K` người tự lên tiếng mỗi tin (mặc định 1), ưu tiên điểm cao, không trùng người đã được gọi; không round-robin.
   Người được chọn chạy lượt `member_volunteer` (không lệnh quản trị).
5. Lỗi phán xử: ứng viên `silent`/`policy_error`; lời gọi trực tiếp không ảnh hưởng.

### 7.3 Chat riêng

Câu hỏi trực tiếp của chủ đi luồng trả lời thường, không bao giờ qua phán xử. Phán xử chỉ cho tin **chủ động** (từ lượt quét/xem xét
lớp 3): nói/chờ/im trước khi gửi. Phán xử lỗi/hết giờ/sai cấu trúc: không gửi, ghi lý do; không mất câu hỏi nào, không chốt việc.

### 7.4 Chờ và gỡ chờ

`wait` ghi `waits` với điều kiện gỡ (tin mới của chủ trong ngữ cảnh, người đang nói chốt lượt, việc liên quan đổi trạng thái, mốc giờ
tối đa 30 phút). Gỡ chờ xét ở `_settle_reply_out`, chuyển trạng thái việc, vòng 5 giây của nhóm; tạo lý do `wait_unblocked`. Mỗi
(agent, tin gốc) được xét lại **tối đa một lần**. Hết hạn: `silent` có lý do, hoặc một câu `ask_clarify` gửi trưởng nhóm/chủ.

### 7.5 Lượt xem xét liên quan từ đồng đội

Sau `_accept` đăng tin của agent X, host sinh `related_review` chỉ cho agent có quan hệ có cấu trúc: người nhận/điều phối việc đó, bước
có `input_refs` trỏ tới tin của X, người nhờ hỗ trợ, hoặc lệnh `{"op":"ask_peer","agent_key":..}` (host kiểm danh tính). Chặn: tự gọi
mình, trích dẫn (bỏ trước khi xét), `@` trong văn bản, độ sâu ≤ 2 từ tin gốc của chủ, một lượt mỗi (agent, tin gốc), không A→B→A, trần
của nhóm. Đi qua phán xử của agent nhận (7.2 bước 2-5).

### 7.6 Dạy phán xử

- Nhãn từ chủ: chip "Đáng lẽ nên nói" / "Nên im (chen ngang)" trên tin, và **lịch sử quyết định** nói/chờ/im theo agent và nhóm (cả ca
  im không có tin) có nút sửa. Lời nhắc kiểu "sao em không trả lời?" chỉ **gợi ý** liên kết tới quyết định im gần nhất; đường xác nhận là
  sửa trong lịch sử quyết định.
- Nhãn dịch độ lệch ngưỡng theo ngữ cảnh (kẹp ±0.25, nửa đời 14 ngày) và thêm ca; không đổi ước lượng nội dung.
- Cộng hưởng tắt: nhãn lưu, ngưỡng không đổi; bật lại không phát lại (chỉ nhãn sau `resumed_at` được tính).

## 8. T3: học trong đội

### 8.1 Kho bài học có phạm vi (`agent_lessons`, resonance.sqlite3)

`id, agent_key, scope (team:<id>|dm:<agent_key>|*), kind (speak|method|presentation|collab), text, source (owner|teammate|leader|self|
review), source_refs_json, status (active|revoked|superseded), created_at, revoked_at, revoked_by`; nhật ký `agent_lesson_events`.

- `JAVIS_LESSON` trong lượt nhóm: scope `team:<id>`, nguồn `self`, gắn lượt/tin/revision; chỉ khi đầu ra còn hợp lệ (R3). Lượt nhóm nạp
  scope của nhóm đó và `*`.
- Chat riêng: `JAVIS_RULE` (luật chủ nói thẳng) vẫn vào "Luật chủ dặn", phạm vi `*` như hiện nay. **Đổi:** `JAVIS_LESSON` do model đề
  xuất trong chat riêng nay ghi `agent_lessons` scope `dm:<agent_key>` thay vì `MEMORY.md`, để bài học riêng không rò vào lượt nhóm;
  chỉ luật của chủ và bài học được tự rà soát/chủ nâng lên mới thành `*`. Lượt chat riêng (mọi phiên) nạp scope `dm:<agent_key>` và
  `*`.
- Bài học cũ trong `MEMORY.md` (đã trộn nhiều nhóm): giữ nguyên, đánh dấu "bài học cũ chưa có phạm vi" trên giao diện; không tự di trú,
  chủ có thể xoá tay như trước.
- Lên phạm vi `*` từ bài học nhóm chỉ qua tự rà soát (bằng chứng ≥ 2 ngữ cảnh) hoặc chủ.
- Thu hồi: chủ bấm trên thẻ agent; `revoked`, không nạp nữa, nhật ký giữ.

### 8.2 Góp ý của đồng đội (`agent_peer_feedback`)

Lệnh `{"op":"peer_feedback","message_id":..,"note":..}` trong lượt agent: host gán nguồn `teammate`/`leader`, gắn tin, sản phẩm, revision;
vào lượt kế tiếp của agent nhận trong đúng nhóm dưới mục "Góp ý của đồng đội (không phải yêu cầu của chủ, không phải sự thật đã kiểm)".
Không thành luật của chủ; nhiều agent đồng ý không là bằng chứng độc lập; kết quả đến muộn sau huỷ/sửa/bỏ thành viên/thu hồi chỉ là bằng
chứng.

### 8.3 Tự rà soát và tự áp dụng (Cộng hưởng bật)

- Kích hoạt khi có ≥ 6 nhãn nói/im **mới sau `resumed_at`**, hoặc ≥ 5 tín hiệu hữu ích mới sau `resumed_at`, và cách lần trước ≥ 24
  giờ; purpose `review`. Tối đa 3 thay đổi từ danh sách đóng: `offset_set` (ngữ cảnh), `eagerness_set`, `lesson_add`/`lesson_remove`
  (scope nhóm hoặc dm), `lesson_promote` (cần bằng chứng ≥ 2 ngữ cảnh). Mỗi thay đổi dẫn mã quyết định/tín hiệu đã cho xem.
- Tự áp ngay, ghi trước/sau; quay lại theo 6.4; không lặp thay đổi đã quay lại trong 14 ngày; không đè thiết lập chủ đang giữ.
- Ngoài phạm vi (quyền, luật chủ, mã/skill/workflow, cấu trúc agent): chỉ ghi đề xuất cho chủ.
- **Không hai vòng học cho một phản hồi:** nguồn đã thuộc lý do `reaction_review`/tự rà soát được đánh dấu đã tiêu thụ. `learn.py`
  (rewire từ nhật ký hội thoại) và curator không đọc bảng reaction; A3 làn P/M chỉ cho tin báo goal; tự soát Zalo chỉ cho bot. Vì vậy
  một reaction không mở hai lần rà soát.

## 9. Trần, chi phí, dự trữ cho nghĩa vụ

| Trần | Mặc định | Ai chỉnh | Ghi chú |
|---|---|---|---|
| Lượt phán xử theo lô mỗi nhóm/ngày `judge_daily` | 40 | chủ; Toàn quyền điều chỉnh được; có "Không giới hạn" | **tách** khỏi `daily_turns`, không ăn suất trả lời |
| `K` người tự lên tiếng mỗi tin | 1 | chủ; Toàn quyền | 0 = tắt tự lên tiếng |
| Chế độ phán xử khi Cộng hưởng tắt | lọc code + lô | chủ | "chỉ lọc code" = không lượt model cho agent tắt Cộng hưởng |
| Lượt chủ động/xem xét/quét/tự rà soát mỗi agent/ngày `agent_daily_calls` | 6 | chủ; có "Không giới hạn" | Toàn quyền không chỉnh (không phải trần nhóm) |
| `max_tier` (nhịp nhanh nhất) | B1 | chủ (tới B0) | trưởng nhóm không nâng được, kể cả Toàn quyền |
| Dự trữ nghĩa vụ trong trần chung server | 20% | server | lượt tự phát (chủ động, xem xét, quét, phán xử theo lô) chỉ dùng tới 80% trần; goal A2, việc giao, lời gọi trực tiếp dùng được cả trần (9.1) |
| Trần chung `JAVIS_RESONANCE_CALL_CEILING` | env | server | cố định với Toàn quyền; phạm vi ở 9.1 |

`agent_daily_calls` tiêu theo thứ tự ưu tiên `reaction_review` > `related_review` > `wait_unblocked` > tin chủ động/quét, và luôn
giữ 2 lượt/ngày cho hai loại xem xét đầu (quét/chủ động không dùng phần giữ). Lượt phán xử cho tin chủ động trong chat riêng tính vào
`agent_daily_calls`; phán xử theo lô trong nhóm tính vào `judge_daily` của nhóm.

Hết trần: lần thức chỉ chạy code, lý do giữ `pending`, trạng thái "Chờ hạn mức"; qua ngày mỗi lý do tối đa một lượt (không bù hàng loạt).
Các trần mới vào **bảng giới hạn** của T1 (loại: chủ chỉnh, Toàn quyền chỉnh, server cố định, nhà cung cấp).

### 9.1 Phạm vi và thực thi trần chung (`JAVIS_RESONANCE_CALL_CEILING`)

Sửa sau review T1: bản trước chỉ cộng `goals.calls_used` và `call_ledger`, nên lượt nhóm (lưu ở `team_turns`, kho khác) nằm ngoài trần.

- **Phạm vi:** mọi lượt engine cấp host do Jarvis 007 tự chạy ở đường nhóm và Cộng hưởng: lượt goal A2 và phép thử, bộ lập mục tiêu, lượt
  nhóm (trả lời tin nhóm, bước việc nhóm), phán xử theo lô, lượt chủ động, quét, xem xét, xem xét reaction, gỡ chờ. **Ngoài phạm vi:**
  lượt chat riêng chủ tự gõ (chủ đang ngồi đó, không phải lượt tự chạy), loop và nhắc hẹn (có trần riêng). Đây là trần của pilot có
  hạn mức do chủ duyệt; không đặt biến thì không có trần chung.
- **Phép đếm** (một hàm `_ceiling_used(c)` dùng chung): `SUM(goals.calls_used) + COUNT(call_ledger WHERE status = 'used') +
  COUNT(agent_calls WHERE counted = 1 AND status <> 'refunded')`. Dòng `reserved`, `running`, `ok`, `error`, `interrupted` đều tính
  (lượt đã hoặc có thể đã tới model); chỉ `refunded` (chắc chắn chưa gọi model) được trả lại. Lượt phản chiếu goal có `counted = 0`
  nên không đếm hai lần.
- **Nguyên tử:** kiểm và giữ chỗ trong cùng một giao dịch `BEGIN IMMEDIATE` của `resonance.sqlite3` (SQLite tuần tự hoá mọi giao dịch
  ghi, kể cả từ tiến trình khác), giống `reserve_ledger_call` hiện có.
- **Dự trữ nghĩa vụ 20%:** dòng có `obligation = 1` (goal A2, phép thử, bộ lập mục tiêu, bước việc nhóm, trả lời tin nhóm, lời gọi
  trực tiếp @) giữ chỗ khi `dùng + n <= trần`. Dòng `obligation = 0` (phán xử theo lô, chủ động, quét, xem xét, xem xét reaction, gỡ
  chờ) chỉ giữ chỗ khi `dùng + n <= floor(trần * 0.8)`. Phép đếm `dùng` gồm cả hai loại, nên lượt tự phát không bao giờ ăn vào 20%
  cuối, còn nghĩa vụ vẫn dùng được phần đó.
- **Thử lại, lỗi, hoàn:** mỗi lần thử là một dòng mới (`attempt + 1`) và giữ chỗ lại từ đầu (kiểm trần lại). Lỗi sau mốc gọi engine
  (`error`, `interrupted`) vẫn tính, không hoàn. Hoàn chỉ khi chắc chắn chưa gọi model (mốc `engine_started` chưa ghi).
- **Khởi động lại và đối soát** (chạy lúc khởi động và mỗi nhịp pulse, idempotent):
  - Dòng `team_turn:*` **chỉ** đối soát theo trạng thái của chính lượt nhóm, **không bao giờ theo tuổi**: lượt nhóm có thể đứng
    `reserved` chưa có mốc engine suốt lúc chờ khoá bận (tới `busy_wait_s`, mặc định 1800 giây) và một bước chạy tới
    `STEP_TIMEOUT_S` (3600 giây). Lượt nhóm đã hoàn hay không còn thì dòng `refunded`; lượt nhóm đã chốt thì dòng chốt theo
    (`ok`/`error`/`interrupted`); lượt nhóm còn `reserved` hay đang chạy thì để nguyên. Lúc khởi động (mọi lượt của tiến trình cũ đã
    chết) dòng `reserved`/`running` của lượt nhóm chưa chốt theo đúng đường hoàn/ngắt mà `team_store` áp cho lượt đó.
  - Có **khoảng ân hạn** 120 giây tính từ `created_at` của dòng sổ: đối soát không đụng dòng mới hơn, để nhịp pulse không bắt gặp
    một lượt đang ở giữa hai bước giữ chỗ của hai kho.
  - Dòng chỉ có ở sổ mới (`mirror_ref = ''`: phán xử, xem xét, chủ động, quét) không có kho thứ hai nên mới dùng hạn tuổi: `reserved`
    không mốc engine quá 10 phút (dài hơn mọi lượt loại này) thì `refunded`, có mốc engine thì `interrupted` (tính).
  - Lượt nhóm đã tới mốc engine mà **thiếu** dòng sổ (tiến trình chết giữa hai kho, hay kho chung lỗi lúc giữ chỗ) thì dựng lại
    dòng `counted = 1` (có thể tạm vượt trần: không làm mất lượt đã tính), **chỉ với lượt tạo sau mốc nâng lên T2**
    (`t2_migrated_at`, ghi một lần lúc tạo bảng) hay lượt còn mở lúc nâng. Lượt nhóm đã chốt trước khi nâng là lịch sử, không bao
    giờ tính vào trần (quyết định của chủ sau review T2: nâng cấp không được chặn ngay máy pilot đang đặt trần). Lượt nhóm thiếu
    dòng sổ mà chưa tới mốc engine thì để nguyên (có thể đang chờ khoá bận sau một lần kho chung lỗi); khi nó tới mốc engine thì
    được dựng dòng như trên. Quét theo con trỏ bền `(created_at, turn_id)` có trần số dòng mỗi lần, cộng nhóm nhỏ: lượt còn mở,
    lượt mở lúc nâng, lượt vừa chốt gần đây.
- **Trần tính trọn đời, không theo ngày:** phép đếm cộng mọi dòng còn hiệu lực từ trước tới nay (như `goals.calls_used` hiện có), nên
  khi chạm trần thì mọi lượt trong phạm vi bị chặn (kể cả trả lời tin nhóm và bước việc) tới khi chủ nâng biến môi trường. Đây là
  trần của pilot có hạn mức, không phải hạn mức hằng ngày; trần theo ngày vẫn là `daily_turns` của nhóm và `agent_daily_calls`.
- **Hiển thị khi chạm trần chung:** lượt trả lời mang lý do `server_ceiling` (khoá `teams.reply.why.server_ceiling`: "Đã chạm
  trần lượt chung của máy chủ"), việc bị chặn với loại `server_ceiling` (khoá `teams.block.server_ceiling`). Nút "Cho thêm lượt" của
  nhóm **không** nâng được trần này (chỉ biến môi trường của máy chủ); giao diện nói rõ điều đó thay vì mở hộp giới hạn của nhóm.
- **Thứ tự hai kho:** giữ chỗ `team_turns` (kho nhóm) rồi mới giữ chỗ sổ chung; sổ chung từ chối thì hoàn `team_turns` ngay. Mọi lần
  hoàn hay chốt của lượt nhóm đi qua một hàm gọi cả hai kho; lỗi kho chung lúc chốt không làm hỏng lượt nhóm (đối soát sửa sau).
- **Test bắt buộc:** trần sát giới hạn (trần N: lượt thứ N được, N+1 bị chặn trước engine), nhiều lượt đồng thời (luồng và hai kết
  nối khác nhau, không vượt trần), dự trữ 20% (tự phát bị chặn ở 80% còn nghĩa vụ chạy tới 100%), đối soát phản chiếu thiếu và dư,
  khởi động lại giữa giữ chỗ và chốt, thử lại sau lỗi tính đúng số.

## 10. Giao diện (mục 11 GOAL)

Thẻ trợ lý và hàng thành viên ngăn Nhóm, API `GET /agents/{slug}/pulse` (host đổi slug sang `agent_key` đang hoạt động):

- Cộng hưởng bật/tắt; trạng thái (`active/awake/slowed/hibernating/waiting_owner/paused/off`, "Chờ hạn mức") và bậc **theo từng ngữ
  cảnh**; lần xem xét gần nhất, lần dự kiến, lý do thức;
- lý do đổi nhịp gần đây (trước/sau, nguồn); phản hồi đã xử lý và trạng thái;
- bài học đang dùng theo phạm vi, nguồn, nút thu hồi (và nhãn "bài học cũ chưa có phạm vi");
- bộ phán xử: nơi áp dụng, quyết định nói/chờ/im gần đây (cả ca im) và nút sửa;
- việc đang làm/chờ/bị chặn (tab Công việc có sẵn);
- nhật ký quản trị của nhóm (`team_events`: cấp/thu quyền, thêm/bỏ thành viên, lệnh của trưởng nhóm) trong ngăn Nhóm, mục Nâng cao.

Nút: Đánh thức, Tạm dừng/Tiếp, Đặt lại nhịp ngữ cảnh, Quay lại thay đổi. Chỉ hiện thành công sau khi host xác nhận. Hai ngôn ngữ, màn
hẹp, chữ ≥ 16px.

## 11. T4: lịch sử dài, hiệu năng, vận hành

- **Lịch sử dài trong đúng nhóm** (T4 0.124.0 đã có phân trang theo con trỏ, tìm không dấu, khối tóm tắt phần cũ bằng code): bổ sung
  vào khối tóm tắt các mục **luôn giữ** mà không nạp toàn bộ lịch sử: sổ quyết định ghim, yêu cầu gốc và trạng thái các việc mở, nguồn
  đóng góp của kết quả gần nhất (từ `pulse_contrib`), phản hồi chưa tiêu thụ của agent trong nhóm; mỗi mục là truy vấn có chỉ mục và trần
  số dòng. Chat riêng: lượt `agent:<slug>` nạp bài học phạm vi và khối phản hồi theo cùng cách. Test: nhóm 5.000 tin vẫn giữ yêu cầu,
  quyết định, nguồn đóng góp và phản hồi trong prompt; số đọc kho mỗi lượt có trần.
- Đo bằng engine giả: nhiều nhóm, hàng nghìn tin, nhiều reaction, agent ngủ/thức, phán xử đồng thời; đo API, độ trễ event loop, số lượt
  model giả, số đọc/ghi kho; trình duyệt (vẽ danh sách, nhiều tab).
- Kiểm: nhiều tab, mất kết nối, restart, huỷ, retry, rời nhóm, đổi trưởng nhóm, bật/tắt Cộng hưởng, thu hồi quyền.
- Nhóm bị chặn hay agent ngủ không chiếm suất của nhóm có việc. Kịch bản VPS chuẩn bị sẵn, **chưa chạy**.

## 12. Di trú và quay về bản cũ

- Nâng cấp: tạo bảng/kho mới; mọi `agent_pulse` khởi tạo B3 với `resumed_at = lúc nâng cấp`; reaction cũ **không** backfill vào bậc
  (chỉ là bằng chứng hiển thị). Cột mới đều có mặc định để bản cũ chạy trên kho đã nâng.
- Quay về bản cũ: bản cũ bỏ qua bảng/kho mới; công cụ khôi phục (R9) mở rộng chép thêm `agent_judge.sqlite3` và các bảng mới trong
  `resonance.sqlite3`, `conversations.db`, `team.sqlite3` vào bộ sao lưu trước nâng.
- Lỗi kho khi ghi tác động: outbox giữ `pending`, chiếu lại sau; không mất reaction, không tác động kép.
- Quay về bản cũ khi đã có reaction của trưởng nhóm/thành viên trong `team_reactions` (reactor `agent:...`): bản cũ hiển thị
  chúng như reaction thường; đây là ảnh hưởng đã biết của việc quay về (không mất dữ liệu), ghi trong hướng dẫn khôi phục.

## 13. Ma trận nghiệm thu (GOAL mục 12) → nơi kiểm

| Ca | Mốc | Test chính (host thật, engine giả) |
|---|---|---|
| 1 hai nhóm, tag | T1/T3 | test tag của T1; `test_agent_judge_scope.py`; `test_agent_lessons.py` |
| 2 gọi trực tiếp/tự tham gia/im | T3 | `test_agent_judge_team.py` |
| 3 phân công, phản hồi, sửa bản | T1/T3 | test team hiện có; `test_team_peer_feedback.py` |
| 4 sáu reaction hai nơi | T2 | `test_dm_reactions.py`, `test_team_reactions.py` mở rộng, JS |
| 5 bật/tắt với feedback | T2/T3 | `test_feedback_wake.py` |
| 6 nhịp dài hạn, ít nhu cầu, im không phạt | T3 | `test_agent_pulse_policy.py` (vectơ 5.3) |
| 7 ngủ thức lại, tắt không tự bật, nghĩa vụ giữ | T3 | `test_agent_pulse_host.py` |
| 8, 28 đóng góp, không đếm trùng, không tự thưởng | T3 | `test_pulse_contrib.py` |
| 9 thay/bỏ reaction, xoá nguồn | T2/T3 | `test_dm_reactions.py`, `test_agent_pulse_policy.py` |
| 10 không vòng vô hạn, chờ chủ | T3 | `test_agent_judge_team.py`, `test_related_review.py` |
| 11 ưu tiên A→C→B, hai kick | T1 | test T1 |
| 12 sửa/bỏ/đổi/thu hồi/huỷ, quyền theo lượt | T1 | test T1 |
| 13 lỗi engine, lỗi kho, huỷ lặp, restart | T1/T3 | `test_agent_calls_ledger.py`, `test_feedback_projector.py` |
| 14 khôi phục nhiều kho | T1/T3 | test rollback hiện có + kho mới |
| 15 ba lớp không ba lượt | T3 | `test_agent_calls_ledger.py` (định tuyến 3.3, chỉ mục từng phần) |
| 16 đồng hồ giả ngày/tuần/tháng | T3 | `test_agent_pulse_policy.py` |
| 17 phán xử/tự rà soát có sổ, nguồn, quay lại | T3 | `test_agent_judge_review.py` |
| 18 giao diện, hai ngôn ngữ, số đo | T3/T4 | JS, smoke trình duyệt, bench |
| 19 hồ sơ riêng từng agent | T3 | `test_agent_judge_team.py` |
| 20 chat riêng, lỗi phán xử | T2/T3 | `test_agent_judge_dm.py` (timeout, JSON sai, engine lỗi) |
| 21 sửa ca im/chen ngang | T3 | `test_agent_judge_labels.py` |
| 22 cá nhân hoá, ít mẫu, emoji sự việc, chưa xem | T3 | `test_agent_pulse_policy.py` |
| 23 hoạt động ở A, ngủ ở B | T3 | `test_agent_pulse_host.py` |
| 24 tự tìm việc đúng quyền | T3 | `test_agent_pulse_host.py` (quét, propose/enqueue) |
| 25 bật lại không phát lại | T2/T3 | `test_feedback_wake.py` |
| 26 tự áp, trước/sau, quay lại | T3 | `test_agent_judge_review.py`, `test_agent_lessons.py` |
| 27 tín hiệu đồng đội, trích dẫn, gỡ chờ | T3 | `test_related_review.py` |
| Lỗi kho/outbox, lệch đồng hồ | T2/T3 | `test_feedback_projector.py`, `test_agent_pulse_policy.py` |

## 14. Cần anh quyết (không tự thu hẹp)

1. **Phán xử khi Cộng hưởng tắt:** mặc định vẫn lọc code + lô theo GOAL; có tuỳ chọn "chỉ lọc code" nếu anh không muốn tốn lượt cho
   agent tắt Cộng hưởng.
2. **Sự kiện "đã xem":** cần dashboard báo tin của agent đã nằm trong khung nhìn.
3. **Pilot chất lượng trên model thật** và **đo VPS:** chỉ chuẩn bị gói, chờ lệnh.

## 15. Sổ sửa theo review thiết kế

Review độc lập vòng 1 (FAIL, 6 chặn, 10 quan trọng, 6 nhỏ). Mỗi mục đã xử lý tại: (1) kho và outbox: 2, 3.1, 3.5, 12; (2) chỉ mục từng
phần, vòng đời lý do, định tuyến, khoá bận: 3.1-3.4; (3) nhịp chỉ theo bằng chứng mới, prior về 0, dwell, vectơ test: 5.3, 6.3; (4) lượt
xem xét reaction: 4.4; (5) trần phán xử riêng, dự trữ nghĩa vụ, `_under_ceiling`: 3.1, 9; (6) lịch sử dài: 11; (7) phân bổ theo bằng
chứng, trần mỗi agent, không tín hiệu trùng: 6.5; (8) cá nhân hoá theo người và ngữ cảnh, 😂 độ tin thấp, `p̄`, một luật xuống bậc: 6.1,
6.3, 5.3; (9) quay lại chỉ cho chính sách: 6.4; (10) quét việc giới hạn: 5.5; (11) nhịp pulse ngoài tick goal: 5.1; (12) sổ lượt phán
xử theo lô, timeout, engine: 7.2; (13) di trú, quay về, lệch đồng hồ: 12, 5.4; (14) trần mới vào bảng giới hạn, Toàn quyền không nâng
`max_tier`, `resumed_at` ở đường trưởng nhóm: 2, 9; (15) scope `dm:<agent_key>`, `MEMORY.md`, không hai vòng học: 8.1, 8.3; (16) đếm sau
`resumed_at`: 8.3, 7.6; (17) thức lại `min`, nghĩa vụ khi tạm dừng, nhắc chờ chủ: 5.2; (18) xét lại sau gỡ chờ một lần: 7.4; (19) "sao em
không trả lời" chỉ gợi ý: 7.6; (20) trang Trò chuyện chính, `mobile-chat.js`, nonce dùng lại, API theo `agent_key`: 2, 4.1, 4.2, 10;
(21) "Chờ hạn mức", chờ chủ, nhật ký quản trị: 5.2, 10; (22) ma trận thêm ca 14, lỗi kho, lỗi phán xử chat riêng: 13.

Review vòng 2 (PASS WITH CHANGES, 2 chặn, 8 quan trọng, 4 nhỏ), đã xử lý: (B1) `k` chỉ cho reaction không lý do, làm trơn, trần
0.75-1.25, tính lại mỗi kỳ, vectơ tính lại kèm `k` và thêm người dùng nhất quán/dùng lẫn: 5.3, 6.3; (B2) chỉ mục `pending` riêng, nguồn
chưa tiêu thụ chuyển sang lý do chờ mới: 3.2; (3) chiếu theo thứ tự nhật ký, trạng thái ròng: 3.5; (4) cơ hội tiêu thụ một lần, không
tính cho `low_demand`: 5.5; (5) khoá không chờ cho lượt chủ động: 3.4; (6) bài học chat riêng phạm vi `dm`: 8.1, 0; (7) tập "được dùng"
do host ghi: 6.5; (8) dòng tín hiệu theo agent với `share`: 6.3; (9) trạng thái theo kết quả gửi thật: 4.4; (10) thứ tự tiêu trần và phần
giữ cho xem xét: 9; (11) câu chữ vectơ im lặng: 5.3; (12) trần chung chỉ đếm lượt còn hiệu lực: 3.1; (13) bật lại giữ ước lượng, agent tắt
lúc nâng cấp ở `off`: 5.2; (14) ảnh hưởng quay về bản cũ: 12.

Review vòng 3 (PASS WITH CHANGES, không còn chặn; người review xác nhận các mục quan trọng sửa xong không cần vòng nữa), đã xử lý: (1)
vectơ người dùng lẫn và vectơ 5 ❤️ rải 2 tuần sát ngưỡng: 5.3; (2) lỗi lượt khi đã có lý do chờ mới hơn: 3.2; (3) thử khoá trước khi
nhận lý do, bận không tốn lần thử: 3.4; (4) chia đều theo tập đầu vào của host, phần vượt trần cho người khác trước: 6.5; (5) phạm vi
chat riêng theo agent (`dm:<agent_key>`), không theo phiên: 2, 8.1; (nhỏ) ghi chú UNIQUE, bảng `pulse_opportunities`: 2, 3.5, 5.5, 6.1.

Sửa sau review T1 (trần chung, 2026-10-15): bản trước loại dòng `agent_calls` có `mirror_ref` khỏi trần mà phép đếm cũ chỉ có
`goals.calls_used` và `call_ledger`, nên lượt nhóm nằm ngoài trần. Nay: một sổ duy nhất, cột `counted` và `obligation`, lượt nhóm giữ
chỗ trước engine, dự trữ 20% thực thi bằng `floor(trần * 0.8)`, quy tắc thử lại, hoàn và đối soát: 3.1, 9, 9.1. Review bản sửa đó
(vòng 2): dòng sổ của lượt nhóm chỉ đối soát theo trạng thái lượt nhóm, không theo tuổi, có khoảng ân hạn 120 giây; trần tính trọn
đời; cách hiển thị `server_ceiling`: 9.1.

Sửa khi làm T3 phần nhịp (2026-10-15, độ lệch được điều phối chấp nhận): luật `low_demand` (5.3 bước 4) thêm điều kiện "im
lâu hơn `max(4 x khoảng, 3 ngày)`" bên cạnh cách đọc nguyên chữ, vì đọc nguyên chữ thì một reaction ngay sau lần đổi bậc giữ
nhịp nhanh mãi mãi; ngưỡng 4 lần khoảng giữ đúng các vectơ 5.3 ("5 ❤️ rải 2 tuần" giữ B3, "10 ❤️ mỗi 1,4 ngày" tới B1).
Chi tiết và test: `docs/dev/team-chat-t3-pulse.md` mục 6.
