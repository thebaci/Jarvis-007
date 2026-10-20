# Nhóm chat team: rà mã trước thiết kế (13/10/2026)

Nền: `main` `bfb1c29f9e87e8b43a0bf1a8a43d3535581047d6` (0.109.0, A1 tới A5 đã phát hành). Nhánh thiết kế `claude/team-chat-design`.

Thiết kế dùng biên bản này: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md).

**Mức bằng chứng.**
- Chỉ đọc mã, không chạy thử. Sáu lượt rà song song theo sáu mảng.
- Tự soát lại các kết luận mà kiến trúc dựa vào (mục 9).
- "Đường thật" nghĩa là đã lần từ giao diện hoặc API tới kho và engine. "Một phần" nghĩa là có mã nhưng thiếu đoạn cần cho nhóm chat. "Chỉ có tên" nghĩa là chỉ thấy tên, chưa có hành vi.
- Số dòng dẫn theo `bfb1c29f`.

## 1. Kết luận ngắn

- **Jarvis 007 chưa có nhóm chat nội bộ.**
  - Không có bảng nhóm hay thành viên. Một phiên chỉ gắn một agent (`sessions.channel`, `workflow_chat.persona_cua_phien`).
  - Tin nhắn chỉ có `role`, không có người gửi (`server/sessions.py:101-108`).
  - Dashboard chưa có @mention.
  - Lời nhắc của agent còn ghi rõ "KHÔNG có cơ chế gọi agent khác" (`server/main.py:9638`).
- **Ba thứ dễ nhầm với nhóm chat nhưng không phải:**
  - **Tag** (0.100.0) chỉ phân loại. `docs/dev/agent-tags.md:5-7` đã ghi nhóm chat team là khái niệm riêng, chưa làm.
  - **Nhóm Zalo và Telegram của chatbot** là kênh ngoài: một bot nói chuyện với người ngoài (`chatbot_store.py`, `chatbot_reply_policy.py`).
  - **Workflow** là đường ống các bước nối tiếp, không phải hội thoại (`main._execute_workflow_raw`).
  - **Cặp làm/review A5** gắn theo từng mục tiêu, không có giao diện chat (`resonance_store` `goal_team`).
- **Phần dùng lại được:**
  - phiên và tin nhắn (thêm cột người gửi);
  - vòng gửi qua WebSocket và stream;
  - `push_to_chat` để đưa kết quả vào một phiên;
  - hàng Kanban (lưu bền, lease, phục hồi sau restart, huỷ, báo kết quả về chat);
  - sổ danh tính agent của Cộng hưởng (mã bền `agent_key`);
  - lời nhắc và bộ nhớ của agent;
  - công tắc Cộng hưởng và các cổng A1 tới A5.

## 2. Danh tính agent, hồ sơ, tag

| Chức năng | File:hàm | Đường | Dùng lại | Khoảng trống |
|---|---|---|---|---|
| File agent | `agents/<slug>.md` trong brain; `main.agents_index` (6678), `POST /agents` tạo và sửa (6741), `POST /agents/delete` (6803), `_agent_file` (6848) | Thật | Hồ sơ, lời nhắc, model riêng | Không có route đổi slug. Đổi tên chỉ sửa `name` |
| Slug | `_ascii_slug` (6479), `valid_file_slug` (`skill_router.py:169`) | Thật | | **Tạo agent trùng tên với file đã có thì ghi đè âm thầm** (không có chặn ở server) |
| Mã bền | `resonance_agents.agent_key` (`resonance_store.py:124-129`); `_insert_agent` (490) nhận `enabled=False`; `agent_set_enabled` (538) chỉ tạo mã ở lần bật đầu | Thật nhưng lười | Mã thành viên nhóm | Agent chưa từng bật Cộng hưởng không có mã |
| Xoá rồi tạo lại cùng slug | `delete_agent` chỉ xoá file rồi `agent_retire` | Thật | | Bộ nhớ `memory/agents/<slug>/`, phiên `agent:<slug>`, gắn chatbot đi theo slug nên agent mới thừa hưởng. Chỉ Cộng hưởng tách được nhờ mã mới và phiên ghim mã (`session_agent` 606) |
| Tag | `agent_tags.py`; `/capability/meta`, `/agents/tags/rename`, `/agents/tags/delete`; khoá `_AGENT_META_LOCK` | Thật | Lọc khi chọn thành viên | Không cấp quyền gì (đã kiểm: không dùng trong lời nhắc, cổng Cộng hưởng, chọn reviewer hay Kanban) |
| Lời nhắc và bộ nhớ agent | `_agent_sysprompt` (9566), `_agent_chat_prompt` (9658), `_ket_luot_agent` (9680): `JAVIS_RULE` vào "Luật chủ dặn" chỉ khi chủ vừa nói trong lượt; `JAVIS_LESSON` giữ 15 dòng | Thật | Lượt của từng thành viên | Không có khối ngữ cảnh nhóm |

## 3. Phiên, tin nhắn, WebSocket

| Chức năng | File:hàm | Đường | Dùng lại | Khoảng trống |
|---|---|---|---|---|
| Phiên | `sessions.py:73-89`, cột thêm 413-455; kênh `web`, `agent:`, `workflow:`, `coding:`, `bot:` | Thật | Kênh mới `team:<id>` | `list_sessions` chỉ ẩn bốn tiền tố (750-753); phải thêm tiền tố mới |
| Tin nhắn | `messages(id, session_id, role, content, ts, tool_calls_json)`; `append_message` (547) | Thật | | **Không có người gửi, mã tin của client, `reply_to`.** Nhóm chatbot nhét tên vào nội dung (`chatbot_runtime.py:1616`), nên danh tính là chữ không tin được |
| Lịch sử | `get_messages_page(limit, before=(ts,id))` (677), tối đa 200 | Thật | Phân trang khung chat | `limit=0` trả toàn bộ; engine vẫn gọi `get_messages` không phân trang |
| Gửi qua WS | `/ws` (`main.py:14376`), vòng nhận (16145), `get_or_create` (16271), kiểm bận (16309), `run_turn` (16417) | Thật | Vòng gửi | Gói tin không có người nhận hay agent đích |
| Bận | `chat_runtime` một job mỗi phiên; tin thứ hai bị từ chối "Phiên này đang trả lời" (16309-16317) | Thật | | Không có hàng chờ phía server; một số tác dụng phụ chạy trước khi kiểm bận |
| Stream và kết lượt | `_SendProxy` (14421), `ChatRuntime.publish` (`chat_runtime.py:92`) phát cho mọi client; `turn_done` (15641) | Thật | | Không có số thứ tự sự kiện, không phát lại sau khi nối lại |
| Nối lại | `hello{running}` (14402); client `_dongBoNeuLech` (`app.js:992`); ping/pong (0.85.11) | Thật | | Chỉ có chữ đang stream; khung khác mất khi rớt mạng |
| Chống gửi trùng | Không có cho tin chữ; tin giọng dùng `utterance_id` và `voice_receipts` | Một phần | Mẫu `voice_receipts` | Gửi lại sau rớt mạng tạo thêm dòng tin người dùng |
| Đưa tin từ việc nền vào phiên | `push_to_chat` (10386), `_notify_owner` (10601), `report_receipts` | Thật | Đăng kết quả của thành viên | Tin đăng vào là `assistant`, không có tác giả |
| `turn_context` | `turn_context.make` (84): kênh, `session_id`, `message_id`, `agent{key,slug,config_version}`, `authority_seq` | Thật | Gắn nhóm và việc vào lượt | Chưa có khoá nhóm hay việc |
| `/agent-<slug>` trong chat chính | `chat-slash.js:61-133`, `_bao_ve_khung_goc` | Thật | Mẫu chuyển tin và báo về | Chạy ở phiên 1:1 riêng, không chung một luồng |

## 4. Engine và model

| Loại lượt | Nguồn engine/model | Model riêng của agent | Ghi usage |
|---|---|---|---|
| Chat thường | ghim theo phiên, rồi `_effective_main` (`main.py:1772`, 2496) | n/a | Claude, Codex, API ghi; Grok và Antigravity không ghi |
| Chat với agent | `model` + `model_provider` của agent ghim vào phiên lúc tạo (16660-16667) | **Một phần:** cần đủ hai trường; ghim là ảnh chụp lúc tạo phiên; thiếu khoá API thì rơi về model chính (2512) | như trên |
| Bước workflow, toàn quyền | `_mk` (9515) | Claude có; Codex có điều kiện; provider khác qua `swap` có thể trôi sang chuỗi dự phòng | log Claude, `usage.json` cho API |
| Bước workflow dưới Kanban có giới hạn công cụ | ép Claude (9549-9554) | Chỉ khi model của agent là Claude | log Claude |
| Kanban, loop, nhắc hẹn | aux (`aux_engine.swap`) | Không | aux |
| Cộng hưởng (cả A5) | `_resonance_engine`: aux, chỉ chữ, không chuỗi dự phòng (2041-2054) | **Không** | `actions.receipt_json` trong kho Cộng hưởng; `usage.json` chỉ khi aux là API |

- Sổ usage chỉ có các chiều ngày, provider, nguồn, loại hoạt động, model, project. **Không có chiều phiên, agent hay việc** (`usage_index.py`).
- Phanh ngân sách tháng chỉ áp cho aux khi aux là provider API (`aux_engine.read_spec` 177-185). Chat chính và chat agent không bị phanh.

## 5. Công việc, Kanban, workflow

| Chức năng | File:hàm | Đường | Dùng lại | Khoảng trống |
|---|---|---|---|---|
| Bảng việc | `task_store.py:84-113` (`kanban.sqlite3`): status, priority 1..3, `chat_id`, attempts, lease, `not_before`, metadata, deps, runs, events | Thật | Lưu bền việc nhóm | Không có cột nhóm, người được giao, thứ tự; phạm vi theo brain |
| Thêm việc | `enqueue` (255-274) | Thật | khoá idempotency | **Gộp việc cùng tiêu đề đang mở**: hai việc nhóm cùng tên thành một |
| Chọn việc tiếp | `next_candidate` (667-680): triage trước, rồi `priority`, rồi `created_at`; `_dispatch_available` (`tasks.py:355`) mỗi 5 giây | Thật | Khung vòng điều phối | Một pool chung `max_workers` mặc định 2 cho mọi brain; không có "một việc chạy mỗi nhóm"; `/kanban/run`, `/kanban/nudge` bỏ qua thứ tự và số chỗ |
| Chế độ bảng | `off`/`manual`/`auto`, brain mới là `off` (`task_store.py:78`) | Thật | | Việc nhóm do người dùng giao rõ không nên phụ thuộc công tắc này |
| Lease, phục hồi | `claim` (682-746), lease 90 giây, nhịp 20 giây; `reclaim_stale` (459) | Thật | Dùng lại | Sau crash không hoàn lượt thử |
| Huỷ | `/kanban/task/cancel` (1561) | Thật | Dùng lại | Chỉ huỷ được trong tiến trình đang giữ worker |
| Kiểm nghiệm thu (0.107.0) | `_check_acceptance` (1030-1082) | Thật | Có thể làm cổng xong việc | Không chạy được kiểm thì vẫn đánh dấu xong (`unverified`) |
| Báo về chat | `_report` (1224-1290) qua `_notify_owner` theo `chat_id` | Thật | Báo kết quả về nhóm | |
| Đổi thứ tự | Không có API; giao diện không kéo thả | Chỉ có tên `priority` | | Thiếu thứ tự, nút ưu tiên, kiểm phiên bản khi hai tab cùng sửa |
| Workflow | `_execute_workflow_raw` (9855-10014): bước nối tiếp, `{{prev}}`; `verify_agent` đóng khi lỗi (0.107.0), `max_retries` theo bước | Thật | Thân của một việc | Không có trần vòng cho cả lượt chạy |
| Bận theo agent | Không có | | | Cùng một agent có thể chạy cùng lúc ở Kanban, chat riêng và Cộng hưởng |

## 6. Cộng hưởng A1 tới A5

- **Công tắc theo agent:**
  - route `POST /resonance/agents/toggle` (`resonance_api.py:341-371`), gọi `agent_set_enabled`;
  - chỉ chủ (`_owner_only`); agent và công cụ không gọi được;
  - lần bật đầu cấp mã; mỗi lần đổi tăng `config_version`;
  - agent `missing` phải được xác nhận mới bật lại được.
- **Tắt không giết lượt đang chạy, nhưng đóng mọi bước sau:**
  - cổng làm việc chặn `agent_off`;
  - `begin_action` kiểm lại;
  - quyền ghi đang giữ hết hiệu lực;
  - kết quả review gắn version cũ bị loại.
- **Chủ luôn thắng:** tạm dừng, huỷ, thu hồi, bỏ yêu cầu review vẫn chạy được khi agent đã tắt. Bản đã cam kết đăng vẫn hoàn tất.
- **Model không bao giờ tự làm được:**
  - bật hay tắt agent; đặt reviewer;
  - duyệt, thu hồi hay cấp quyền ghi;
  - tạm dừng hay huỷ mục tiêu; đổi trần;
  - chọn engine; nhắn hay giao việc cho agent khác.
- Bảng đầy đủ mọi trần và cổng ở thiết kế, mục 13.6.

## 7. Giao diện

- **Trang Cộng sự** (`dashboard/workspace.js`):
  - Cột trái liệt kê trợ lý (`mucHtml` 827-849): ảnh, tên, vai, tag, ghim, menu "...". **Dòng chưa có trạng thái Cộng hưởng**, vì `/agents?prompt=0` không trả trường này.
  - Cột phải, tab Cài đặt, có bảng Cộng hưởng (`resonance-agent.js`): công tắc, ô Người review, mục tiêu, bài học.
- **Công tắc hiện có ở hai nơi:** cột phải trang Cộng sự, và trang Cài đặt (`index.html:447-450`, `settingsHtml` 208-240).
- **Các lỗi nhỏ đã thấy:**
  - bản ở Cài đặt nuốt lỗi;
  - bản ở Cộng sự gặp 409 thì chỉ hiện chữ, không tải lại trạng thái;
  - ô Người review không trả về giá trị cũ khi lỗi.
- **Thẻ mục tiêu** (`chat-resonance.js`): đủ nút tạm dừng, tiếp tục, huỷ, cho phép phạm vi, bật lại reviewer, bỏ yêu cầu review. Không tự làm mới định kỳ.
- **Reaction A3:**
  - chỉ `up`, `down`, `none` và ba lý do `too_long`, `too_often`, `unclear` (`resonance_learning.py:36-37`);
  - chỉ trên **tin báo do host ghi** của mục tiêu;
  - bảng `reactions` bắt buộc có `goal_id`, `revision`, `report_key`, `notice_kind` (`resonance_store.py:171-181`).
- **i18n và màn hẹp:**
  - Chữ mới phải có khoá ở cả `vi.json` và `en.json` (`tests/js/test_i18n.mjs`).
  - Trang Cộng sự đổi cột thành ngăn kéo ở 1060px và 900px.
  - Bẫy `[hidden]` bị `display:flex` đè.

## 8. Khoảng trống phải lấp cho nhóm chat

1. Bảng nhóm, thành viên, vai trưởng nhóm, chế độ quyền.
2. Tin nhắn có người gửi, mã tin của client, liên kết với việc.
3. Mã bền cho mọi agent là thành viên, không chỉ agent đã bật Cộng hưởng.
4. Hàng việc theo nhóm: một việc chạy mỗi nhóm, thứ tự lưu bền, làn ưu tiên, kiểm phiên bản khi hai tab cùng sửa.
5. Chạy lượt của từng thành viên với đúng lời nhắc, model riêng, và mạch resume riêng.
6. Công cụ điều phối do host ghi (phân công, nhờ hỗ trợ, nộp kết quả) với trần chống vòng.
7. Khoá bận theo agent trên toàn hệ thống.
8. Sổ lượt theo nhóm, việc, vai.
9. Sáu reaction trên mọi câu trả lời của agent.
10. Công tắc Cộng hưởng trên dòng trợ lý.

## 9. Tự soát lại (đọc lại mã, không qua lượt rà)

| Kết luận | Kiểm tại | Kết quả |
|---|---|---|
| Tin nhắn chỉ có `role` | `server/sessions.py:101-108` | Đúng |
| Stream phát cho mọi client | `server/chat_runtime.py:92-106` | Đúng |
| Kanban gộp việc cùng tiêu đề đang mở | `server/task_store.py:255-274` | Đúng |
| Phiên bận thì từ chối tin mới | `server/main.py:16309-16317` | Đúng |
| Kho danh tính tạo được mã mà không bật | `_insert_agent(..., enabled, ...)` (`resonance_store.py:490-500`) | Đúng; `agent_set_enabled` hiện chỉ gọi với `True` |
| Lời nhắc agent cấm gọi agent khác | `server/main.py:9638` | Đúng |
| Reaction A3 chỉ ba giá trị, gắn tin báo mục tiêu | `resonance_learning.py:36`, `resonance_store.py:171-181` | Đúng |

**Chưa kiểm:**
- đường engine Codex, Claude CLI, API trong `_do_turn` ngoài nhánh Grok;
- lớp `_auth_guard` và `_csrf_guard`;
- đường đi của một lượt engine đang chạy khi agent bị tắt;
- mọi đường client chống trùng tên khi tạo agent.
