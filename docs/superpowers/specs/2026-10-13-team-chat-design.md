# Nhóm chat team nhiều agent (thiết kế)

**Trạng thái:** bản thiết kế vòng 1. **Chủ dự án chốt D1 tới D7 theo đề xuất và cho triển khai (13/10/2026)**, bắt đầu từ T0 rồi T1 ([kế hoạch](../plans/2026-10-13-team-chat-t0-t1.md)). Chưa gọi model, chưa pilot, chưa merge, không đụng VPS.

- **Nền:** `main` `bfb1c29f9e87e8b43a0bf1a8a43d3535581047d6` (0.109.0). Cộng hưởng A1 0.87.0, A2 0.88.0, A3 0.89.0, A4 0.96.0, A5 0.109.0 đã phát hành; tag cho agent 0.100.0.
- **Nhánh:** `claude/team-chat-design`. Chưa giữ số phiên bản: số được giữ khi bắt đầu viết mã T1 (mục 19), theo `docs/quy-uoc-dev.md`.
- **Đầu vào:**
  - GOAL của chủ dự án ngày 13/10/2026, gồm ba phần: nhóm chat team; trưởng nhóm và chế độ Toàn quyền; sáu reaction.
  - [Biên bản rà mã](../../dev/team-chat-audit-2026-10-13.md).
  - [Lộ trình agent](2026-10-08-resonance-agent-scope-roadmap.md), [thiết kế A4](2026-10-10-resonance-a4-handoff-grants-design.md), [thiết kế A5](2026-10-11-resonance-a5-maker-reviewer-design.md), [tag của agent](../../dev/agent-tags.md).
- **Wireframe và sơ đồ:** [team-chat-wireframes.md](../../dev/team-chat-wireframes.md).
- **Mức bằng chứng:** chỉ đọc mã và tài liệu. Mọi điều "đã có" đều dẫn file và hàm ở biên bản rà mã. Test tài liệu không phải bằng chứng sản phẩm chạy.

## 1. Mục tiêu và ngoài phạm vi

### 1.1 Trải nghiệm

Anh làm việc với nhiều agent trong các nhóm chat, quen như nhóm Zalo nhưng nằm trong Jarvis 007:
- **Danh sách nhóm**, tạo được nhiều nhóm theo việc hay chủ đề. Mỗi nhóm có tên, mô tả, thành viên, lịch sử và công việc riêng.
- **Thành viên:** thêm agent có sẵn, hoặc tạo agent mới rồi đưa vào nhóm. Một agent ở được nhiều nhóm.
- **Trưởng nhóm:** mỗi nhóm có một trưởng nhóm là agent do anh chọn.
  - Gửi yêu cầu chung thì trưởng nhóm điều phối, phân công và tổng hợp.
  - Anh vẫn @ giao việc hay trao đổi trực tiếp với từng agent.
- **Phối hợp:** agent trao đổi đầu vào và trả kết quả vào đúng nhóm.
- **Cài đặt nhóm:** có việc đang làm, hàng đợi và nút **Ưu tiên**.
- **Màn Trợ lý (Cộng sự):** mỗi trợ lý hiện trạng thái và công tắc Cộng hưởng.
- **Phản hồi:** mỗi câu trả lời của agent có đủ sáu reaction: 👍 Thích, ❤️ Tim, 😂 Haha, 😮 Wow, 😢 Huhu, 😡 Phẫn nộ.
- **Hai chế độ trưởng nhóm:** Quyền giới hạn và Toàn quyền.

### 1.2 Phân biệt, không gộp

| Khái niệm | Là gì | Quan hệ với nhóm chat |
|---|---|---|
| Tag (0.100.0) | Nhãn phân loại agent | Chỉ để lọc khi chọn thành viên. Không phải nhóm, không thêm thành viên, không chọn trưởng nhóm, không cấp quyền |
| Nhóm Zalo/Telegram của chatbot | Một bot nói chuyện với người ngoài trên kênh ngoài | Không liên quan. Nhóm chat team không nối với Zalo trong bản này |
| Workflow | Đường ống các bước nối tiếp | Một việc nhóm có thể dùng workflow làm thân, không thay nhóm |
| Cặp làm/review A5 | Một agent làm, một agent review cho mỗi **mục tiêu Cộng hưởng** | Agent trong nhóm vẫn có thể có mục tiêu Cộng hưởng với cặp A5. Cặp A5 không phải cấu trúc nhóm; nhóm không giới hạn hai agent |
| Mục tiêu Cộng hưởng (goal) | Việc dài hạn agent tự theo đuổi | Tin trong nhóm không tự tạo goal. Goal tạo trong lượt nhóm báo về đúng nhóm (mục 10.3) |

### 1.3 Ngoài phạm vi bản đầu

- nhiều tài khoản, phân quyền tổ chức;
- gọi thoại, video;
- tích hợp nhóm Zalo thật;
- engine riêng cho từng agent ở mọi loại lượt (mục 12.1);
- đưa usage việc nền lên màn usage chung (việc riêng đã ghi sau A5);
- nguồn yêu cầu do host ghim cho reviewer A5 (việc riêng).

## 2. Hiện trạng tóm tắt

Chi tiết và dẫn mã ở [biên bản rà mã](../../dev/team-chat-audit-2026-10-13.md).

**Chưa có:**
- nhóm và thành viên;
- người gửi trên tin nhắn;
- @mention;
- hàng việc theo nhóm;
- khoá bận theo agent;
- sổ lượt theo việc;
- sáu reaction;
- công tắc Cộng hưởng trên dòng trợ lý.

**Đã có và dùng lại:**

| Cần | Dùng lại | Đổi gì |
|---|---|---|
| Hội thoại nhóm | Phiên (`sessions`) với kênh mới `team:<team_id>`; phân trang `get_messages_page` | Thêm cột người gửi vào `messages` |
| Gửi, stream, nối lại | `/ws`, `ChatRuntime`, `push_to_chat` | Gói tin mang `team_id`, người nhận, `client_msg_id` |
| Lời nhắc agent | `_agent_sysprompt`, bộ nhớ agent, `_ket_luot_agent` | Thêm khối ngữ cảnh nhóm |
| Lưu bền việc, lease, phục hồi, huỷ, báo về chat | Bảng `tasks` của Kanban, `claim`, `heartbeat`, `reclaim_stale`, `_report` | Làn `team` riêng (mục 5.4) |
| Danh tính bền | `resonance_agents.agent_key` | Đăng ký mã cho mọi thành viên, không cần bật Cộng hưởng |
| Công tắc Cộng hưởng | `POST /resonance/agents/toggle` và hợp đồng A1 | Đưa lên dòng trợ lý; trang Cài đặt chỉ còn tóm tắt |
| Cổng A4, A5 | Giữ nguyên | Không đổi |

## 3. Ba phương án kiến trúc

| | A. Nhóm trên phiên + làn `team` trong Kanban (**chọn**) | B. Dựng nhóm trên Cộng hưởng | C. Hệ nhóm độc lập |
|---|---|---|---|
| Hội thoại | Phiên kênh `team:` | Phiên kênh `team:` | Kho tin riêng |
| Việc nhóm | Dòng trong `tasks` của Kanban, làn `team`, trạng thái riêng | Mỗi việc là một goal | Bảng việc riêng |
| Ai chạy việc | Bộ chạy nhóm, lượt chat của agent (có công cụ) | Lượt chỉ chữ của Cộng hưởng | Bộ chạy riêng |
| Ưu | Dùng lại lease, phục hồi, huỷ, báo về chat, trang Công việc. Một chỗ cho mọi việc nền. Không đụng hợp đồng A1 tới A5 | Có sẵn sổ lượt, hạn mức, review | Tự do thiết kế |
| Nhược | Phải tách làn để mã Kanban cũ không nhặt nhầm; thêm vài cột | Goal là việc dài hạn chỉ chữ, có trần cố định và lịch thức; mỗi tin thành goal trái yêu cầu "tin thường không tạo goal"; đổi hợp đồng đã phát hành | Thêm một hệ giao việc cạnh tranh với Kanban: đúng điều GOAL cấm |

**Chọn A**, với ba lý do:
- Việc nhóm là việc người dùng giao, chạy một lần, cần thứ tự và hiển thị. Hàng Kanban đã có đủ phần lưu bền, khoá và phục hồi.
- Cộng hưởng giữ nguyên vai trò cho mục tiêu dài hạn.
- Không sinh hệ thứ ba.

## 4. Bất biến

1. **Host quản lý danh tính.** Mã nhóm, thành viên, agent, lượt, tin và việc do host cấp. Không tin mã do model tự khai.
2. **Tin thường không tạo việc hay goal.** Chỉ hành động có quyền mới tạo việc (mục 7.1, 7.3). Tin của agent không tự đánh thức agent khác.
3. **Một lời gọi model tính đúng một lần.**
   - Giữ chỗ trong sổ lượt trước khi dựng engine.
   - Lỗi trước mốc gọi engine thì hoàn lượt.
   - Gửi lại request, nối lại hay restart không gọi lại.
4. **Kết quả chỉ được áp dụng khi còn đúng** việc, revision, người được giao và tư cách thành viên. Sai một điều thì kết quả được lưu là "đến muộn, không áp dụng".
5. **Lệnh của chủ nhóm luôn thắng:** dừng, huỷ, thu hồi, bỏ thành viên. Toàn quyền không vô hiệu được lệnh của chủ.
6. **Mỗi nhóm thuộc đúng một brain.** Không mở truy cập chéo brain. Ngữ cảnh của một nhóm không vào lượt của nhóm khác hay chat riêng.
7. **Hợp đồng A1 tới A5 giữ nguyên.** Đổi vị trí giao diện không đổi chính sách. Không tin nhắn nào mở rộng quyền, bỏ cổng A4 hay vượt yêu cầu review A5.
8. **"Không giới hạn" là trạng thái rõ ràng**, không giả bằng số lớn. Trần nào còn áp (kỹ thuật, nhà cung cấp, máy chủ) thì phải hiện ra.

## 5. Mô hình dữ liệu

### 5.1 Danh tính agent: một sổ chung

Mã bền của agent dùng lại `resonance_agents` (cùng file `resonance.sqlite3`).
- Thêm hàm `agent_register(p, slug)`: tạo mã với `enabled=0` nếu chưa có dòng sống. Owner gọi, hoặc host gọi khi thêm thành viên.
- Không đổi nghĩa cột `enabled`: nó vẫn chỉ là công tắc Cộng hưởng.
- Tên bảng giữ nguyên để không phải di trú. Tài liệu gọi nó là "sổ danh tính agent".

Hệ quả:
- **Đổi tên** chỉ đổi `name` trong file; mã và slug giữ nguyên, nên tư cách thành viên giữ nguyên.
- **Xoá agent** gọi `agent_retire` như hiện nay: mã thành `retired`, dòng thành viên hiện "đã xoá", việc của agent vào trạng thái chặn (mục 6.4).
- **Tạo lại cùng slug** sinh mã mới, không là thành viên, không thừa hưởng việc hay quyền.
- **Lỗ hổng cũ:** tạo agent trùng tên đang ghi đè âm thầm file cũ (biên bản mục 2). T1 sửa: tạo mới mà slug đã có thì server trả 409, kèm gợi ý slug khác. Không ghi đè.

### 5.2 Kho nhóm mới: `team.sqlite3`

File mới ở `JAVIS_STATE_DIR`, module mới `server/team_store.py`. Mã cũ bỏ qua file này nên hạ phiên bản an toàn (mục 18).

| Bảng | Cột chính | Ghi chú |
|---|---|---|
| `teams` | `team_id` (`tm_`+hex), `brain_id`, `name`, `description`, `session_id` (phiên `team:`), `leader_key` (null được), `leader_mode` (`limited`/`full`), `status` (`active`/`paused`/`archived`), `queue_version`, `caps_json`, `created_at`, `updated_at` | `queue_version` tăng mỗi lần đổi hàng đợi, dùng cho CAS |
| `team_members` | `team_id`, `agent_key`, `slug_at_join`, `role` (`member`/`leader`), `status` (`active`/`removed`/`agent_gone`), `managed_by_team` (0/1), `joined_at`, `left_at` | PK (`team_id`, `agent_key`). Một agent ở nhiều nhóm |
| `team_events` | `id`, `team_id`, `kind`, `by` (`owner`/`leader:<key>`), `before_json`, `after_json`, `created_at` | Nhật ký: thành viên, trưởng nhóm, chế độ quyền, trần, ưu tiên, huỷ |
| `team_steps` | `step_id`, `task_id`, `team_id`, `seq`, `kind` (`plan`/`work`/`help`/`synthesize`/`reply`), `agent_key`, `job_revision`, `brief`, `input_refs_json`, `status`, `parent_step`, `result_msg_id`, `applied` (0/1), `created_at`, `updated_at` | Các bước nội bộ của một việc nhóm. **Không phải việc cấp nhóm** |
| `team_turns` | `turn_id`, `team_id`, `task_id` (null được với lượt trò chuyện), `step_id`, `agent_key`, `role` (`leader_reply`/`member_reply`/`plan`/`work`/`help`/`synthesize`), `engine`, `model`, `status` (`reserved`/`running`/`ok`/`error`/`refunded`/`interrupted`), `engine_at`, `tokens_in`, `tokens_out`, `cost_usd`, `created_at`, `settled_at` | Sổ lượt. Một dòng cho mỗi lời gọi model |
| `agent_busy` | `agent_key` PK, `team_id`, `turn_id`, `lease_until` | Khoá bận theo agent trên toàn hệ thống (mục 8.7) |
| `team_reactions` | `id`, `team_id`, `session_id`, `message_id`, `responder`, `agent_key`, `task_id`, `content_sha`, `value`, `reason`, `comment`, `seq`, `created_at`, `updated_at` | UNIQUE (`session_id`, `message_id`, `responder`) |
| `team_reaction_log` | `id`, `reaction_id`, `value`, `reason`, `comment`, `nonce`, `created_at` | Ghi nối tiếp. UNIQUE (`reaction_id`, `nonce`) |
| `team_authority` | `team_id`, `seq`, `mode`, `grant_json`, `by`, `created_at`, `revoked_at` | Lịch sử cấp và thu hồi Toàn quyền (mục 13) |

### 5.3 Thêm cột vào `messages` của `sessions.db`

Các cột thêm đều cho phép null, mã cũ bỏ qua:

| Cột | Nghĩa |
|---|---|
| `author_kind` | `owner` / `agent` / `system` |
| `author_ref` | `agent_key` khi `author_kind=agent`, rỗng khi khác |
| `client_msg_id` | Mã tin do client sinh; UNIQUE (`session_id`, `client_msg_id`) khi khác null |
| `reply_to` | Mã tin được trả lời |
| `task_id` | Việc nhóm liên quan, null được |
| `step_id` | Bước liên quan, null được |
| `meta_json` | Mention đã kiểm, cờ "đến muộn", trạng thái kết quả |

- Tin cũ không có tác giả hiển thị như hiện nay.
- Chỉ phiên kênh `team:` mới ghi các cột này ở T1. Chat thường không đổi.

### 5.4 Thêm cột vào `tasks` của Kanban (làn `team`)

| Cột | Nghĩa |
|---|---|
| `lane` | `''` (Kanban cũ) hay `team` |
| `team_id` | Nhóm sở hữu việc |
| `team_seq` | Số thứ tự thêm vào hàng của nhóm, tăng dần |
| `team_prio` | null = thường; số = thứ tự trong làn ưu tiên |
| `team_rev` | Revision của yêu cầu, tăng khi chủ nhóm sửa yêu cầu |
| `assignee_key` | Agent được giao trực tiếp (null nếu giao chung cho trưởng nhóm) |
| `coordinator_key` | Trưởng nhóm điều phối, ghim lúc bắt đầu, đổi kèm sự kiện |
| `source_ref` | `msg:<session_id>:<message_id>` của tin giao việc |

- **Trạng thái của làn `team`** dùng giá trị riêng: `team_queued`, `team_running`, `team_blocked`, rồi `done` / `cancelled` khi kết thúc.
- `next_candidate`, `reclaim_stale`, `/kanban/run` và `/kanban/nudge` chỉ làm việc với `triage`/`ready`/`running`. Vì vậy mã Kanban (cả bản cũ khi hạ phiên bản) không bao giờ nhặt việc nhóm.
- **Khoá idempotency** = `source_ref`.
- **Tắt gộp theo tiêu đề cho làn `team`:** hai việc khác nhau cùng tên vẫn là hai việc.

## 6. Vai và quyền

### 6.1 Ba vai

| Vai | Là ai | Được làm |
|---|---|---|
| Chủ nhóm | Người dùng (owner của dashboard) | Mọi thứ: tạo, sửa, lưu trữ nhóm; tạo agent; thêm, bỏ thành viên; chọn, đổi trưởng nhóm; đổi chế độ quyền; ưu tiên, huỷ, dừng; đặt trần |
| Trưởng nhóm | Một agent thành viên do chủ chọn | Quyền giới hạn: điều phối trong việc được giao. Toàn quyền: thêm như mục 13 |
| Thành viên | Agent trong nhóm | Trả lời khi được gọi; làm bước được giao; nhờ hỗ trợ trong trần; nộp kết quả |

- Bản đầu không có nhiều tài khoản: "chủ nhóm" là owner đã đăng nhập dashboard.
- Mọi route quản lý nhóm đi qua lớp auth và CSRF như các route owner hiện có.
- Agent chỉ hành động qua công cụ `javis_team` (mục 15.2), với danh tính lấy từ `turn_context`, không từ tham số model.

### 6.2 Ma trận quyền

| Hành động | Chủ nhóm | Trưởng nhóm (giới hạn) | Trưởng nhóm (Toàn quyền) | Thành viên |
|---|---|---|---|---|
| Tạo, sửa tên, mô tả nhóm | Có | Không | Không | Không |
| Tạo agent mới | Có (qua `POST /agents` hiện có) | Không | Có, agent thành "do nhóm quản lý" | Không |
| Thêm, bỏ thành viên | Có | Đề xuất (chủ bấm) | Có | Không |
| Chọn, đổi trưởng nhóm; đổi chế độ quyền | Có | Không | Không (không tự nâng mình) | Không |
| Mở việc nhóm | Có | Đề xuất (chủ bấm) | Có, trong phạm vi được giao | Không |
| Phân công bước trong việc đang chạy | n/a | Có | Có | Không |
| Nhờ thành viên khác hỗ trợ | n/a | Có | Có | Có, trong trần |
| Ưu tiên, bỏ ưu tiên việc chờ | Có | Không | Có | Không |
| Ngắt việc đang chạy | Có | Không | Chỉ khi chủ bật quyền riêng "Được ngắt việc" | Không |
| Huỷ việc | Có | Không | Có, với việc chờ; với việc đang chạy cần quyền "Được ngắt việc" | Không |
| Bật, tắt Cộng hưởng | Có (mọi agent) | Không | Chỉ agent do nhóm quản lý (mục 13.3) | Không |
| Đổi trần | Có | Không | Trong mức chủ cho phép (mục 13.2) | Không |
| Duyệt phạm vi ghi A4 | Có (trên thẻ) | Không | Chỉ trong thư mục nhóm nếu chủ chọn (D4) | Không |

### 6.3 Đổi hay bỏ trưởng nhóm khi đang chạy

- **Ghim:** `coordinator_key` của việc ghim lúc bắt đầu.
- **Khi chủ đổi trưởng nhóm:**
  - Lượt đang chạy của trưởng nhóm cũ được chạy hết, kết quả lưu nhưng **không áp dụng** như điều phối (`applied=0`, ghi "trưởng nhóm đã đổi").
  - Ở điểm điều phối kế tiếp, việc chuyển cho trưởng nhóm mới, kèm sự kiện `coordinator_changed`.
- **Khi chủ bỏ trưởng nhóm mà không chọn người thay:**
  - Việc đang chạy cần điều phối vào `team_blocked` với lý do `no_leader`.
  - Nhóm hiện băng rôn "Nhóm chưa có trưởng nhóm".
  - Việc @ trực tiếp vẫn chạy.
  - Việc chung mới vẫn vào hàng nhưng không bắt đầu.
  - Không bao giờ âm thầm mất điều phối.
- **Khi trưởng nhóm bị xoá khỏi Jarvis 007:** xử lý như bỏ trưởng nhóm.

### 6.4 Bỏ thành viên đang có việc

- **Bước chưa tới mốc gọi engine:** huỷ và hoàn lượt.
- **Bước đã gọi engine:** chạy hết, kết quả lưu với `applied=0` và nhãn "thành viên đã rời nhóm".
- Việc quay về điểm điều phối để trưởng nhóm phân công lại.
- Nếu việc được giao trực tiếp cho người đó, việc vào `team_blocked` với lý do `assignee_removed`; chủ chọn giao lại hay huỷ.
- Bỏ khỏi nhóm không xoá agent khỏi Jarvis 007 hay khỏi nhóm khác. Bộ nhớ của agent giữ nguyên.

## 7. Luồng chat và phối hợp

### 7.1 Hai loại tin của chủ nhóm

Khung soạn có công tắc **"Giao việc"**, mặc định tắt.

| | Trò chuyện (mặc định) | Giao việc |
|---|---|---|
| Tạo việc nhóm | Không | Có, một việc |
| Vào hàng đợi | Không | Có |
| Lượt model | Lượt trả lời ngắn (mục 7.2) | Theo việc |

Trưởng nhóm có thể **đề xuất** biến một trao đổi thành việc, bằng `javis_team op=propose_job`:
- Quyền giới hạn: đề xuất hiện thành thẻ "Trưởng nhóm đề xuất giao việc: ..." với hai nút Tạo việc và Bỏ qua. Chưa bấm thì không có việc nào.
- Toàn quyền: trưởng nhóm mở việc thẳng, trong phạm vi được giao. Thẻ vẫn hiện để chủ nhìn thấy và huỷ được.

### 7.2 Định tuyến tin trò chuyện

@mention là danh sách có cấu trúc do khung soạn tạo khi chọn từ gợi ý: `mentions=[agent_key...]`. Server kiểm từng mã với danh sách thành viên đang hoạt động. Chữ "@tên" gõ tay mà không chọn từ gợi ý chỉ là chữ.

| Tin | Ai trả lời | Số lượt |
|---|---|---|
| Không @ | Trưởng nhóm (D1). Nhóm chưa có trưởng nhóm: không lượt nào, hiện "Nhóm chưa có trưởng nhóm; @ một thành viên để hỏi trực tiếp" | 1 |
| Một @X | Chỉ X; trưởng nhóm không bị gọi | 1 |
| Nhiều @ (tối đa 3, chỉnh được) | Từng người theo thứ tự @; người sau thấy câu trả lời của người trước trong cùng lượt hỏi | Bằng số @ hợp lệ |
| Quá số @ cho phép | Từ chối gửi, nói rõ trần | 0 |
| @ không còn hợp lệ (đã rời, đã xoá, `missing`) | Bỏ qua người đó, hiện "X không còn trong nhóm"; người hợp lệ vẫn trả lời | Bằng số @ hợp lệ |

- **Tin của agent không đánh thức ai.** Chữ "@Y" trong câu trả lời của agent chỉ là chữ. Agent muốn nhờ người khác phải gọi `javis_team op=request_help` trong một việc đang chạy (mục 7.4).
- Lượt trả lời trò chuyện chạy ngay khi agent rảnh. Không đi qua hàng việc nhóm, nhưng phải đợi khoá bận của agent (mục 8.7).
- Lượt trả lời trò chuyện không được mở việc, không được nhờ người khác. Nó chỉ trả lời, hoặc đề xuất việc (mục 7.1).

### 7.3 Giao việc

| Tin "Giao việc" | Việc tạo ra |
|---|---|
| Không @ | Giao chung: `assignee_key` null, `coordinator_key` = trưởng nhóm. Bắt đầu bằng bước `plan` của trưởng nhóm |
| @X | Giao trực tiếp: `assignee_key` = X, `coordinator_key` = trưởng nhóm (chỉ theo dõi). Bắt đầu bằng bước `work` của X; trưởng nhóm không làm lại phần của X |
| Nhiều @ | Một việc, danh sách người làm lưu trong `metadata.assignees`; trưởng nhóm tổng hợp nếu có hơn một người |

- **Không tạo việc trùng:** khoá = `source_ref`. Gửi lại cùng `client_msg_id` trả lại tin cũ và việc cũ.
- **Ví dụ luồng B (giao chung):**
  1. Chủ gửi "Giao việc: soạn kế hoạch ra mắt".
  2. Việc `team_queued` vào hàng.
  3. Tới lượt, bước `plan` của trưởng nhóm gọi `javis_team op=assign` cho thành viên 1 và 2, mỗi người kèm brief và đầu vào.
  4. Host ghi hai bước `work`.
  5. Từng bước chạy (tuần tự mặc định); kết quả đăng vào nhóm với tác giả là thành viên và nhãn việc.
  6. Bước `synthesize` của trưởng nhóm đăng bản tổng hợp; việc `done`.

### 7.4 Nhờ hỗ trợ (luồng D)

1. Đang ở bước `work`, agent A gọi `javis_team op=request_help(B, câu hỏi, đầu vào)`.
2. Host ghi bước `help` cho B, với `parent_step` là bước của A. Bước của A kết thúc với trạng thái chờ.
3. Bước của B chạy, trả lời được lưu.
4. Host tạo lượt tiếp của A với câu trả lời của B làm đầu vào. A làm tiếp.

**Trần chống vòng (mặc định, chỉnh được ở mục 12.3):**
- độ sâu nhờ hỗ trợ: 2 (A nhờ B, B nhờ C; C không nhờ tiếp);
- **A nhờ B rồi B nhờ lại A trong cùng một việc: chặn**, kèm ghi "không nhờ ngược";
- số bước mỗi việc: 8;
- số lượt model mỗi việc: 12;
- **không tiến triển:** hai lượt liền nhau của cùng một bước mà không có kết quả mới (cùng `content_sha`) thì dừng bước đó. Việc vào `team_blocked`, lý do `no_progress`.

### 7.5 Cùng agent ở hai nhóm (luồng E)

Mỗi cặp (nhóm, agent) có một **mạch thành viên** riêng: phiên ẩn kênh `teammate:<team_id>:<agent_key>`, giữ `cli_session_id` và `codex_thread_id` để resume.

- Phiên `team:` hiện lịch sử chung, chỉ trên trang Nhóm. Mạch thành viên chỉ giữ mạch engine.
- `list_sessions` ẩn cả tiền tố `team:` lẫn `teammate:`, như đang ẩn `agent:`, `workflow:`, `coding:`, `bot:`. Hai loại phiên này không hiện trong danh sách lịch sử của chat chính.
- Lượt ở nhóm X chỉ nhận ngữ cảnh của nhóm X (mục 11.2).
- Kết quả gắn `team_id` và `task_id` của lượt đó, nên luôn đăng về đúng nhóm.

### 7.6 Chủ chen lời, sửa hay huỷ (luồng F)

Khi nhóm đang chạy một việc, khung soạn hiện "Đang làm: <tóm tắt việc>" với hai nút.

**"Sửa yêu cầu":**
- Chủ nhập phần sửa; việc tăng `team_rev`.
- Bước chưa bắt đầu dùng revision mới.
- Bước đang chạy chạy hết, kết quả gắn revision cũ: được lưu và hiện nhưng `applied=0`, nhãn "theo yêu cầu cũ".
- Ở điểm điều phối kế tiếp, trưởng nhóm (hay người được giao trực tiếp) lập lại kế hoạch theo revision mới.

**"Huỷ việc":**
- Huỷ lượt đang chạy (`cancel_all` theo thẻ của lượt). Bước chưa tới mốc gọi engine thì hoàn lượt.
- Việc `cancelled`. Kết quả đến sau được lưu với nhãn "đến sau khi huỷ, không áp dụng".

Tin trò chuyện chen vào trong lúc chạy đi theo mục 7.2. Nếu người được @ đang bận trong việc, câu trả lời chờ khoá bận và hiện "X đang làm việc '<tóm tắt>', sẽ trả lời sau".

### 7.7 Liên kết tin, việc, sản phẩm

- Mỗi việc có `source_ref` trỏ về tin giao việc.
- Mỗi bước có `input_refs` (mã tin và mã kết quả bước trước) và `result_msg_id`.
- Mỗi tin của agent trong việc mang `task_id`, `step_id` và `reply_to`.
- File sản phẩm (nếu có, qua A4 hay công cụ ghi) ghi đường dẫn và `sha256` vào `meta_json` của tin kết quả.

Giao diện:
- lọc khung chat theo một việc;
- bấm nhãn việc trên tin để mở chi tiết việc;
- chi tiết việc liệt kê tin nguồn, các bước, các trao đổi và sản phẩm.

Nhiều việc trong cùng nhóm không lẫn nhau vì mọi liên kết đi theo mã, không theo vị trí trong khung chat.

## 8. Hàng đợi và nút Ưu tiên

### 8.1 Đơn vị và trạng thái

- **Đơn vị xếp hàng là việc cấp nhóm** (một dòng `tasks` làn `team`). Các bước nội bộ (`team_steps`) không phải việc cấp nhóm và không hiện trong hàng.
- **Mỗi nhóm chạy tối đa một việc tại một thời điểm.** Toàn quyền có thể đổi mức song song (mục 13.2).

| Trạng thái | Nghĩa | Giữ chỗ chạy của nhóm? |
|---|---|---|
| `team_queued` | Đang chờ | Không |
| `team_running` | Đang làm | Có |
| `team_blocked` | Bị chặn, lý do: `waiting_user`, `failed`, `no_leader`, `assignee_removed`, `interrupted`, `no_progress`, `cap_reached`, `agent_busy_long` | **Không:** hàng đi tiếp |
| `done` / `cancelled` | Lịch sử | Không |

### 8.2 Thứ tự

Thứ tự chạy của các việc chờ trong một nhóm:

```
ORDER BY (team_prio IS NULL), team_prio, team_seq
```

- `team_seq` tăng theo thời điểm thêm vào hàng.
- `team_prio` = null với việc thường. Bấm Ưu tiên thì `team_prio = (max team_prio của nhóm) + 1`, nên các việc ưu tiên chạy theo **thứ tự được bấm ưu tiên**, và cả nhóm ưu tiên đứng trước mọi việc thường.
- **Bấm Ưu tiên lần nữa** trên việc đã ưu tiên: không đổi gì, trả lại vị trí hiện tại. Không có "đẩy lên đầu nhóm ưu tiên" trong bản đầu.
- **Bỏ ưu tiên:** đặt `team_prio = null`. Việc về đúng vị trí theo `team_seq` ban đầu.
- **Ưu tiên không ngắt việc đang chạy,** không nhân đôi việc, không tăng trần, không gọi model.

**Ví dụ bắt buộc.** A đang chạy; B, C đang chờ (`team_seq` của B nhỏ hơn C). Chủ bấm Ưu tiên C:
- C nhận `team_prio = 1`; thứ tự chờ thành C, B.
- A chạy tiếp, không bị ngắt.
- A xong thì C chạy, rồi B.
- A không chạy lại; C không chen ngang A.

### 8.3 Ai được chạy tiếp

Bộ điều phối nhóm mới, `team_runner.dispatch`, chạy trong vòng 5 giây của Kanban và cũng được gọi khi có sự kiện. Với mỗi nhóm `active` không có việc `team_running` (hay còn chỗ song song):
- lấy việc đầu hàng;
- nhận việc bằng một giao dịch `BEGIN IMMEDIATE`: kiểm không có việc khác đang chạy trong nhóm, kiểm `queue_version` chưa đổi, đặt `team_running`, ghi `task_runs`.

Việc nhóm **không phụ thuộc công tắc "AI tự vận hành"** của bảng Kanban: việc nhóm là việc chủ giao rõ. Công tắc riêng của nhóm là Tạm dừng nhóm (`teams.status=paused`).

**Pool chạy:**
- việc nhóm dùng pool riêng `team_max_parallel` (mặc định 2 nhóm cùng lúc trên cả máy), không lấy chỗ của Kanban;
- lượt trò chuyện không vào pool này, chỉ đợi khoá bận của agent.

### 8.4 Bị chặn, lỗi, chờ người dùng

- **Việc bị chặn rời chỗ chạy**, và hàng đi tiếp. Nhóm không bao giờ kẹt vì một việc chờ vô hạn.
- **Việc bị chặn hiện ở mục "Bị chặn/chờ anh"**, có lý do bằng chữ và nút phù hợp: Trả lời, Chạy lại bước, Giao lại, Huỷ.
- **Huy hiệu số việc chờ anh** hiện trên dòng nhóm trong danh sách nhóm. Mỗi lần một việc bị chặn có một tin vào hộp thư (chuông).
- **Khi được gỡ chặn** (chủ trả lời, chạy lại), việc về `team_queued` với `team_seq` và `team_prio` cũ. Nó vẫn đứng đúng chỗ cũ, thường là đầu hàng vì vào sớm.
- **Nhắc lại:** việc chờ chủ quá 24 giờ có một tin nhắc (không gọi model). Không tự huỷ.

### 8.5 Hai tab cùng đổi, điều phối vừa nhận việc

- Mọi thao tác hàng đợi (ưu tiên, bỏ ưu tiên, huỷ việc chờ) gửi kèm `expected_queue_version`.
- Server dùng CAS trong cùng giao dịch với bước nhận việc. Sai version thì trả 409 kèm hàng đợi mới; giao diện vẽ lại theo trạng thái thật và báo "Hàng đợi vừa thay đổi".
- Nếu bộ điều phối đã nhận B ngay trước lúc lệnh ưu tiên C được ghi, B là việc đang chạy, C đứng đầu hàng chờ. Giao diện hiện đúng như vậy. Không có trạng thái nào mà hai việc cùng chạy trong một nhóm.

### 8.6 Restart

| Lúc restart | Sau khi khởi động lại |
|---|---|
| Việc `team_running` có bước chưa tới mốc gọi engine | Bước về chờ, hoàn lượt; việc tiếp tục ở bước đó |
| Bước đã gọi engine mà chưa kết thúc | Bước thành `interrupted`, lượt tính một lần; việc vào `team_blocked`, lý do `interrupted`, nút "Chạy lại bước". **Không tự chạy lại**, để tránh trả tiền hai lần |
| Việc chờ | Giữ nguyên thứ tự |

- Hàng đợi và thứ tự lưu trong `kanban.sqlite3`, nên còn nguyên qua F5, nối lại và restart.
- Lease 90 giây của Kanban được dùng cho việc `team_running`. Hàm thu hồi riêng `team_reclaim` xử lý như bảng trên.

### 8.7 Cùng agent bận ở nhiều nhóm

- **Khoá bận theo agent** (`agent_busy`, mặc định một lượt mỗi agent cùng lúc trên cả máy, D3).
  - Lý do: tránh hai lượt cùng ghi `MEMORY.md` của agent, và tránh lẫn mạch.
  - Khoá có lease, nhịp làm mới như Kanban.
- Khi việc ở nhóm X cần agent đang bận ở nhóm Y:
  - bước ở X chờ khoá, không mất chỗ trong việc;
  - giao diện nhóm X hiện "<Tên> đang làm ở nhóm Y";
  - khoá nhả theo thứ tự xin (FIFO theo thời điểm xin), nên không nhóm nào bị bỏ quên.
- Chờ quá 30 phút thì việc vào `team_blocked`, lý do `agent_busy_long`, để chủ thấy và quyết.
- Chat riêng 1:1 với agent và mục tiêu Cộng hưởng của agent **không** lấy khoá này ở T1, vì chúng có cơ chế riêng. Tài liệu ghi rõ đây là giới hạn: một agent vẫn có thể cùng lúc chạy một lượt nhóm và một lượt chat riêng.

## 9. Một lượt của thành viên

### 9.1 Đường chạy

1. **Giữ chỗ:**
   - ghi `team_turns` (`reserved`);
   - lấy khoá `agent_busy`;
   - kiểm trần của việc và của nhóm;
   - kiểm thành viên còn `active`, việc còn đúng revision.
2. **Dựng engine:** dùng đường chat của agent như hiện nay (`_chat_provider_for_session` với mạch thành viên). Model theo mục 12.1.
3. **Lời nhắc:**
   - lời nhắc hệ thống của agent (`_agent_sysprompt`: vai, bộ nhớ, luật chủ dặn, bài học);
   - khối nhóm (mục 11.2);
   - khối phản hồi (mục 14.4).
4. **Mốc gọi engine:** ghi `engine_at` ngay trước lời gọi. Lỗi trước mốc thì hoàn lượt (`refunded`).
5. **Công cụ:**
   - bộ công cụ của agent như chat riêng, cộng `javis_team`;
   - `javis_task` ẩn trong lượt nhóm, vì giao việc nền trong nhóm đi qua `javis_team`, một chỗ;
   - `javis_goal` chỉ có khi agent bật Cộng hưởng.
6. **Kết thúc:**
   - kiểm lại thành viên, revision, việc chưa huỷ, trưởng nhóm chưa đổi (nếu là lượt điều phối);
   - đủ điều kiện thì đăng tin vào phiên `team:` với tác giả là agent, `applied=1`;
   - không đủ thì đăng với nhãn đến muộn, `applied=0`;
   - ghi token và chi phí; nhả khoá;
   - `_ket_luot_agent` xử lý `JAVIS_LESSON` / `JAVIS_RULE` như hiện nay: luật chỉ ghi khi chính chủ nói trong lượt đó.

### 9.2 Kết quả dễ hiểu

Mỗi tin của agent trong việc hiện:
- tên và ảnh agent;
- nhãn việc (bấm được);
- vai trong việc (Lập kế hoạch, Làm, Hỗ trợ, Tổng hợp);
- trạng thái (Đang làm, Xong, Lỗi, Đến muộn, Theo yêu cầu cũ).

Bản tổng hợp cuối có nhãn "Kết quả việc".

## 10. Công tắc Cộng hưởng trên từng trợ lý

### 10.1 Vị trí

- **Mỗi dòng trợ lý ở cột trái trang Cộng sự** (`workspace.js` `mucHtml`):
  - chữ "Cộng hưởng: Bật" hay "Cộng hưởng: Tắt", và một công tắc có nhãn cho trình đọc màn hình (không chỉ dựa vào màu);
  - agent `missing` hiện "Cần xác nhận" và một liên kết mở cột phải, nơi có hai nút xác nhận như hiện nay.
- `GET /agents?prompt=0` trả thêm `resonance: {enabled, status, registered}`, nối với sổ danh tính trong một lần đọc. Không gọi thêm request cho từng dòng.
- **Cột phải** (bảng Cộng hưởng của agent): giữ ô Người review, mục tiêu, bài học, các nút xác nhận. Công tắc trong bảng này **được bỏ**, để không có hai công tắc cho cùng một agent trên cùng màn.
- **Trang Cài đặt:**
  - bỏ danh sách công tắc theo agent;
  - thay bằng một dòng tóm tắt "N trợ lý đang bật Cộng hưởng · Quản lý ở trang Cộng sự", kèm liên kết;
  - giữ các công cụ chung đang có: mục tiêu mồ côi, gán mục tiêu chưa có chủ, ghi chú công tắc brain cũ.
- **Danh sách thành viên trong cài đặt nhóm:** hiện cùng trạng thái. Đổi tại đây dùng **đúng route** `POST /resonance/agents/toggle`, cùng quyền chủ.

### 10.2 Hành vi

- **Gửi và chờ:** gửi `{slug, enabled}`; công tắc ở trạng thái "đang lưu" cho tới khi server trả lời.
  - Chỉ báo thành công khi server xác nhận.
  - Lỗi hay 409 thì tải lại `GET /resonance/agents` và vẽ theo trạng thái thật (sửa lỗi hiện tại: 409 chỉ hiện chữ).
- **Đồng bộ hai tab:**
  - sau mỗi lần đổi, phát sự kiện `javis:resonance-agents-changed` trong tab;
  - server phát gói `{"type":"resonance_agents"}` qua WebSocket để tab khác tải lại.
- **Tắt agent đang có việc:** hộp xác nhận nêu tác động thật:
  - số mục tiêu Cộng hưởng đang mở sẽ dừng ở bước kế tiếp (hợp đồng A1);
  - các nhóm agent đang tham gia;
  - "việc nhóm không bị dừng bởi công tắc này; muốn dừng việc nhóm thì huỷ ở cài đặt nhóm".
- **Giữ luồng `missing`, xác nhận danh tính, "cần mở phiên mới" của A1.** Công tắc trên dòng không gửi `session_id`. Khi server trả trạng thái cần phiên mới, cột phải hiện nút như hiện nay.
- **Agent không bao giờ tự bật Cộng hưởng.** Riêng ở Toàn quyền, trưởng nhóm bật hay tắt được agent do nhóm quản lý, qua cùng hàm của kho với `by=leader:<key>` và ghi sự kiện (mục 13.3). Agent khác vẫn chỉ chủ đổi được.

### 10.3 Agent chưa bật Cộng hưởng làm được gì

| Việc | Chưa bật | Đã bật |
|---|---|---|
| Trò chuyện trong nhóm, trả lời khi được @ | Có | Có |
| Làm bước trong việc nhóm (lượt chat có công cụ của agent) | Có | Có |
| Là trưởng nhóm | Có | Có |
| Tạo và theo đuổi mục tiêu Cộng hưởng (`javis_goal`), bàn giao sản phẩm theo A4 | Không | Có; báo cáo của goal tạo trong lượt nhóm về đúng phiên `team:` đó |
| Là reviewer A5 | Không | Có |

Tư cách thành viên **không** tự cấp quyền Cộng hưởng.

## 11. Danh tính, quyền và ngữ cảnh

### 11.1 Nhóm và brain

- Mỗi nhóm thuộc đúng một brain (`teams.brain_id`). Thành viên phải là agent của brain đó.
- Đổi brain trên dashboard thì danh sách nhóm đổi theo.
- Quyền đọc, ghi file của agent trong lượt nhóm **giống hệt** trong chat riêng: tư cách thành viên không thêm quyền file nào.

### 11.2 Khối ngữ cảnh nhóm

Khối nhóm do code dựng, không gọi model:
- tên, mô tả nhóm;
- danh sách thành viên (tên, vai, có phải trưởng nhóm);
- vai của chính agent trong lượt này;
- việc hiện tại: tóm tắt, revision, bước, brief, đầu vào (theo `input_refs`);
- **tin mới trong nhóm kể từ lượt trước của chính agent ở nhóm này**, tối đa 20 tin và 8.000 ký tự. Mạch resume của agent giữ phần cũ hơn.
- **"Sổ quyết định" của nhóm:** các tin chủ ghim là quyết định (nút "Ghim làm quyết định"), tối đa 20 dòng. Lịch sử dài vẫn giữ yêu cầu và quyết định mà không phải gửi lại toàn bộ.

Khối nhóm **không** gồm:
- hội thoại riêng của chủ;
- dữ liệu của nhóm khác;
- `CLAUDE.md` và bộ nhớ của chủ (giống chat agent hiện nay);
- bí mật cấu hình.

**Bộ nhớ dùng chung và bộ nhớ riêng:**
- **Chung:** `memory/agents/<slug>/MEMORY.md` thuộc agent, dùng ở mọi nhóm. Bài học tự học ở nhóm X có thể ảnh hưởng nhóm Y; thiết kế chấp nhận và ghi rõ.
- **Riêng:** ngữ cảnh từng nhóm nằm ở phiên `team:` và mạch thành viên.

### 11.3 Ai chịu trách nhiệm, kết quả về đâu

| Câu hỏi | Trả lời |
|---|---|
| Ai chịu trách nhiệm cuối cho việc nhóm | Trưởng nhóm điều phối (`coordinator_key`) với việc chung; người được giao với việc @ trực tiếp. Chủ nhóm quyết nghiệm thu |
| Ai chịu trách nhiệm cuối cho goal | Như A1: agent sở hữu goal. Goal tạo trong lượt nhóm có `origin` là phiên `team:` đó, nên báo cáo về đúng nhóm |
| Kết quả, thông báo đi đâu | Phiên `team:` của nhóm; việc bị chặn có thêm tin vào hộp thư |

### 11.4 Dừng, huỷ, tắt, thu hồi

| Lệnh của chủ | Tác động |
|---|---|
| Tạm dừng nhóm | Không bắt đầu việc mới hay lượt trò chuyện mới. Lượt đang chạy chạy hết, kết quả áp dụng nếu còn đúng. Việc đang chạy giữ `team_running` và dừng ở điểm điều phối kế tiếp |
| Huỷ việc | Mục 7.6 |
| Bỏ thành viên, đổi trưởng nhóm | Mục 6.3, 6.4 |
| Tắt Cộng hưởng của agent | Chỉ ảnh hưởng goal (hợp đồng A1). Việc nhóm không đổi |
| Thu hồi Toàn quyền | Mục 13.5 |
| Xoá agent | Mã thành `retired`; thành viên thành `agent_gone`; xử lý như bỏ thành viên |
| Lưu trữ nhóm | Như tạm dừng, cộng huỷ mọi việc chờ; lịch sử giữ, đọc được |

**Phần đã cam kết ghi hay đăng** đi theo hợp đồng A4: bản đã cam kết đăng vẫn hoàn tất; bản chưa cam kết thì hết hiệu lực.

## 12. Model, hạn mức và phục hồi

### 12.1 Model cho từng loại lượt

| Lượt | Model |
|---|---|
| Lượt trò chuyện, lập kế hoạch, làm, hỗ trợ, tổng hợp trong nhóm | Đường chat của agent: dùng `model` + `model_provider` của agent khi có đủ; không đủ thì model chính |
| Mục tiêu Cộng hưởng (cả cặp A5) | Model việc nền chung, chỉ chữ, như A1 tới A5. Không đổi |
| Việc Kanban thường | Như hiện nay (aux) |

Trong lượt nhóm, model của agent được đọc từ file agent **mỗi lượt**, không ghim theo phiên. Lý do: mạch thành viên là phiên ẩn, ảnh chụp lúc tạo phiên sẽ cũ.

**Không hứa quá:**
- Provider của agent thiếu khoá thì lượt dùng model chính và ghi rõ trong sổ lượt.
- Grok và Antigravity hiện không ghi usage (biên bản mục 4); sổ lượt nhóm vẫn đếm lượt, nhưng token để trống.

### 12.2 Tính lượt

- **Một dòng `team_turns` cho mỗi lời gọi model**, có vai (`role`), việc, bước, agent, engine, model, token, chi phí.
- **Trước mốc `engine_at`:** lỗi thì `refunded`, không tính.
- **Sau mốc:** tính, kể cả lỗi, hết giờ hay bị huỷ.
- **Restart giữa chừng:** `interrupted`, tính một lần, không tự chạy lại.
- **Cài đặt nhóm, tab Lượt:** lượt và token theo việc, theo agent, theo ngày.
- Màn usage chung chưa nhận các lượt này (việc riêng đã ghi).

### 12.3 Trần mặc định (Quyền giới hạn)

| Trần | Mặc định | Đơn vị |
|---|---|---|
| Lượt model mỗi việc | 12 | việc |
| Bước mỗi việc | 8 | việc |
| Độ sâu nhờ hỗ trợ | 2 | việc |
| Nhờ ngược trong một việc | 0 (chặn) | việc |
| Lượt không tiến triển liên tiếp | 2 | bước |
| @ mỗi tin | 3 | tin |
| Lượt model mỗi nhóm mỗi ngày | 100 | nhóm |
| Việc đang chạy mỗi nhóm | 1 | nhóm |
| Nhóm chạy việc cùng lúc trên cả máy | 2 | máy |
| Lượt cùng lúc của một agent | 1 | agent |
| Chờ khoá bận trước khi báo chặn | 30 phút | việc |

- **Trần lượt mỗi nhóm mỗi ngày** tính mọi lượt của nhóm, kể cả lượt trò chuyện. Chạm trần thì tin trò chuyện vẫn được lưu nhưng không có lượt trả lời; nhóm hiện "Nhóm đã dùng hết N lượt hôm nay".
- **Chạm trần của việc:** việc vào `team_blocked`, lý do `cap_reached`, nói rõ trần nào. Chủ chọn Cho thêm lượt (chỉ chủ ở chế độ giới hạn) hay Huỷ.
- **Không vượt trần bằng cách tạo thêm việc:**
  - lượt của mọi việc cộng vào trần ngày của nhóm;
  - trưởng nhóm ở chế độ giới hạn không tự mở việc;
  - nhờ hỗ trợ là bước trong cùng việc, cộng vào trần của việc đó.
- **Agent không tự nâng trần hay đổi provider.**

### 12.4 Chống trùng và đầu ra lỗi thời

| Tình huống | Cách chặn |
|---|---|
| Gửi lại tin sau rớt mạng | `client_msg_id` UNIQUE trong phiên; trùng thì trả tin cũ và không tạo lượt |
| Giao việc trùng | Khoá việc là `source_ref` |
| Bước chạy trùng | `team_steps` CAS `queued` thành `running`; mỗi bước tối đa một lượt `running` |
| Nối lại WebSocket | Lượt là job của server; nối lại không tạo lượt |
| Đầu ra muộn | Mục 9.1 bước 6: kiểm thành viên, revision, huỷ, trưởng nhóm trước khi áp dụng |

### 12.5 Hiệu năng

- Danh sách nhóm phân trang (50 dòng mỗi trang), kèm số việc chờ anh. Đếm bằng chỉ mục, không tải việc của mọi nhóm.
- Khung chat dùng phân trang theo con trỏ đang có (30 tin, tối đa 200).
- Mở một nhóm chỉ tải: 30 tin mới nhất, việc đang chạy, 20 việc chờ đầu, 20 việc bị chặn, thành viên. Lịch sử việc tải khi mở tab Lịch sử.
- Mọi I/O SQLite chạy trong luồng phụ như các kho hiện có, không chặn vòng sự kiện.
- **Đo:**
  - API: thời gian `GET /teams`, `GET /teams/{id}`, `GET /teams/{id}/queue` với 50 nhóm và 5.000 tin;
  - trình duyệt: thời gian vẽ khung chat 200 tin;
  - ghi rõ máy đo. Số trên máy local hay sandbox không phải bằng chứng VPS.

## 13. Trưởng nhóm Toàn quyền

### 13.1 Bật, tắt, phạm vi

- Chủ bật "Toàn quyền cho trưởng nhóm" trong cài đặt nhóm. Bật xong lưu một dòng `team_authority`.
- **Trưởng nhóm không tự nâng mình lên Toàn quyền.** Không công cụ nào đổi được `leader_mode`.
- **Hộp cấp quyền ghi rõ:**
  - phạm vi: trong nhóm này;
  - các agent nhóm được quản lý;
  - provider và model được dùng (chọn từ provider đã cấu hình; không thêm tài khoản hay thông tin đăng nhập);
  - nguồn thanh toán: gói thuê bao hay API trả phí;
  - các trần (mục 13.2);
  - có cho "Được ngắt việc đang chạy" hay không (mặc định không);
  - có cho duyệt phạm vi ghi trong thư mục nhóm hay không (D4).
- **Đổi trưởng nhóm thì Toàn quyền không chuyển theo.** Nhóm về Quyền giới hạn cho tới khi chủ bật lại cho trưởng nhóm mới.

### 13.2 Trần ở Toàn quyền

- Mỗi trần ở mục 12.3 có ba trạng thái: **số**, **Không giới hạn**, hay **Theo mặc định**.
- "Không giới hạn" lưu là `null` kèm cờ `unlimited=true`. Mã kiểm trần coi đó là không có trần, **không thay bằng một số lớn**.
- **Chủ đặt trần trần (ceiling) cho từng mục.** Trưởng nhóm Toàn quyền đổi được trần của nhóm trong mức trần trần đó. Trần trần là "Không giới hạn" thì trưởng nhóm đặt được bất kỳ giá trị nào.
- **Trần không bỏ được, luôn hiện trong hộp cấp quyền:**
  - `JAVIS_RESONANCE_CALL_CEILING` do máy chủ đặt (chỉ ảnh hưởng goal);
  - hạn mức của gói thuê bao hay của nhà cung cấp;
  - quyền của tài khoản;
  - giới hạn kỹ thuật (mục 13.6, nhóm c).
- **Mục tiêu Cộng hưởng tạo bởi agent trong nhóm Toàn quyền** nhận trần của goal (lượt mỗi goal, chia vai A5, số vòng sửa) từ cài đặt nhóm thay cho hằng số. Cần sửa mã (mục 13.6). Cổng review A5 vẫn giữ.

### 13.3 Cấu hình dùng chung của agent

Một agent có thể ở nhiều nhóm, nên đổi cấu hình chung (lời nhắc, model, Cộng hưởng) ảnh hưởng mọi nhóm.

- **Agent do nhóm quản lý:** agent do trưởng nhóm Toàn quyền tạo, hoặc agent chủ đánh dấu "giao cho nhóm này quản lý". Mỗi agent tối đa một nhóm quản lý.
  - Trưởng nhóm Toàn quyền sửa được lời nhắc, model (trong danh sách provider được cấp) và Cộng hưởng của agent này.
  - Mọi thay đổi ghi `by=leader:<key>`, `team_id`.
- **Agent không do nhóm quản lý:** trưởng nhóm không đổi được cấu hình chung (D5).
- **Đổi cấu hình của agent đang ở nhóm khác:** hộp xác nhận (với chủ) hay tin báo (với trưởng nhóm) liệt kê các nhóm khác bị ảnh hưởng. Không âm thầm mở rộng quyền từ một nhóm sang mọi nhóm.

### 13.4 Toàn quyền và hàng đợi

- Trưởng nhóm Toàn quyền đổi được thứ tự các **việc chờ** (ưu tiên, bỏ ưu tiên), với cùng CAS như chủ.
- **Quy tắc "việc đang làm chạy hết rồi mới nhận việc kế" giữ nguyên.** Ngắt hay huỷ việc đang chạy chỉ được khi chủ bật quyền riêng "Được ngắt việc đang chạy"; khi đó lý do ngắt ghi vào sự kiện và hiện trong nhóm.

### 13.5 Thu hồi

Chủ thu hồi bất cứ lúc nào: tắt Toàn quyền, đổi trưởng nhóm hay dừng nhóm.
- Ghi `revoked_at`. Mọi lời gọi `javis_team` sau mốc đó kiểm lại chế độ trong giao dịch và bị từ chối.
- Lượt đang chạy của trưởng nhóm chạy hết. Hành động quản trị nó yêu cầu sau mốc thu hồi bị từ chối. Kết quả nội dung vẫn áp dụng nếu hợp lệ ở Quyền giới hạn.
- Trần quay về mức của Quyền giới hạn. Việc đang chạy vượt trần mới vào `team_blocked`, lý do `cap_reached`, chờ chủ.
- Agent do nhóm quản lý vẫn tồn tại; trưởng nhóm hết quyền sửa chúng.

### 13.6 Bảng giới hạn hiện có và cách xử lý trong Toàn quyền

Nhóm: (a) trần sản phẩm, (b) bảo đảm toàn vẹn, (c) giới hạn kỹ thuật hay bên ngoài.

| Giới hạn | Giá trị | Ở đâu | Nhóm | Trong Toàn quyền | Cần sửa mã? |
|---|---|---|---|---|---|
| Lượt mỗi goal | 6 | `resonance.py:451`, `begin_action` CAS | a | Lấy theo cài đặt nhóm | Có: truyền `budget_calls` lúc tạo goal |
| Lượt goal có đội, chia vai | 8, 4/4 | `resonance_store.py:311-312` | a | Theo cài đặt nhóm | Có: hằng số thành tham số khi gắn đội |
| Số vòng sửa A5 | 2 | `resonance_store.py:313` | a | Theo cài đặt nhóm | Có |
| Lượt review tính trên một bản ghim | 3 | `resonance_heartbeat.py:57` | a | Theo cài đặt nhóm | Có |
| Thử lại, lùi, nhịp kiểm (15 phút, 1 h/4 h/24 h, 6 h tới 7 ngày) | | `resonance_heartbeat.py:28-38` | a | Giữ trong bản đầu | Có nếu muốn mở |
| Không còn lệnh nâng ngân sách goal đã hết | | | a | Thêm lệnh "Cho thêm lượt" cho chủ, và cho trưởng nhóm Toàn quyền trong trần trần | Có |
| Trần toàn máy `JAVIS_RESONANCE_CALL_CEILING` | env | `resonance_store.py:32-59` | a (cấp máy chủ) | Không bỏ; hiện trong hộp cấp quyền | Không |
| Engine chỉ chữ cho goal | | `main._resonance_engine` | b | Giữ | Không |
| Thư mục cấm đăng (`javis`, `plugins`, `skills`, `agents`, `workflows`, `memory`, dotfile) | | `resonance.py:2268-2280` | b | Giữ | Không |
| Loại file sản phẩm `.md`/`.txt`, 1 MB | | `resonance.py:1025-1026` | b/a | Giữ trong bản đầu | Có nếu muốn mở |
| Duyệt phạm vi ghi A4 trên thẻ | chỉ chủ | `approve_scope` | b | Chỉ thư mục nhóm nếu chủ chọn (D4) | Có: nguồn cấp mới `team_full` cho đúng thư mục |
| Cổng review A5 | | `resonance_store.py:2425-2430` | b | Giữ; trưởng nhóm không bỏ được yêu cầu review | Không |
| Một lượt chạy mỗi goal (lease), CAS, ghim hash, khoá idempotency | | | b | Giữ | Không |
| Công tắc Cộng hưởng chỉ chủ | | `_owner_only` | b | Trưởng nhóm đổi được agent do nhóm quản lý | Có: `by=leader` và kiểm quản lý trong kho |
| Kanban `max_workers` | 2 | `tasks.py:138` | a/c | Không áp cho việc nhóm (pool riêng) | Có |
| Kanban gộp việc cùng tiêu đề | | `task_store.enqueue` | a | Tắt cho làn `team` | Có |
| Kanban `priority` 1..3 cố định lúc tạo | | `task_store.py:288` | a | Làn `team` dùng `team_prio` | Có |
| Kanban lease 90 giây, nhịp 20 giây | | `tasks.py:41-42` | c | Giữ | Không |
| Workflow `max_retries` theo bước | 1 | `main.py:9906` | a | Theo cài đặt nhóm khi việc chạy workflow | Có |
| Trần nhóm (mục 12.3) | | mới | a | Số, Không giới hạn, Theo mặc định | Mới |
| Một lượt mỗi agent cùng lúc | 1 | mới | a | Chủ đổi được; trưởng nhóm không | Mới |
| Phát hiện vòng không tiến triển | 2 lượt | mới | b (luôn bật) | Vẫn phát hiện. Ở "Không giới hạn", chính sách là **tạm dừng việc và báo**, chủ bấm Tiếp tục mới chạy tiếp; không âm thầm chạy | Mới |
| Lệnh dừng, huỷ, thu hồi của chủ | | | b | Luôn thắng | Không |
| Hạn mức gói thuê bao, nhà cung cấp | | | c | Không vượt | Không |

## 14. Sáu reaction và vòng phản hồi

### 14.1 Giá trị

Đúng sáu giá trị lưu nguyên, không gộp:

| Giá trị | Emoji | Nhãn |
|---|---|---|
| `like` | 👍 | Thích |
| `love` | ❤️ | Tim / Yêu thích |
| `haha` | 😂 | Haha |
| `wow` | 😮 | Ồ / Wow |
| `sad` | 😢 | Huhu / Buồn |
| `angry` | 😡 | Phẫn nộ / Nổi nóng |

- Cộng thêm `none` để bỏ reaction.
- Mỗi người phản hồi có một reaction trên một tin: chọn cái khác là đổi, chọn lại cái đang chọn là bỏ.

### 14.2 Lưu

- **Bảng `team_reactions`:** người phản hồi, tin (`session_id`, `message_id`), agent (`author_ref` của tin), nhóm, việc, `content_sha` của nội dung tin lúc bấm.
- **`team_reaction_log`** ghi nối tiếp mọi lần đổi, với `nonce` chống gửi trùng.
- Giữ qua F5 và restart.
- **Không dùng bảng `reactions` của A3:** bảng đó bắt buộc gắn goal và tin báo do host ghi (biên bản mục 7).

### 14.3 Giao diện

- **Desktop:** rê chuột vào tin của agent hiện nút mặt cười; bấm mở bộ chọn sáu emoji ngay tại tin.
- **Điện thoại:** nhấn giữ tin mở cùng bộ chọn dạng hàng ngang lớn; vùng chạm tối thiểu 44px.
- Emoji đã chọn hiện dưới tin; bấm vào để đổi hay bỏ.
- **Phần bổ sung, không thay sáu emoji:**
  - **Lý do chất lượng** (chọn được nhiều): "Đúng ý", "Sai dữ kiện", "Thiếu ý", "Quá dài", "Khó hiểu", "Lạc đề";
  - **góp ý bằng chữ** (tối đa 500 ký tự).
- Mọi chữ có khoá i18n ở cả `vi.json` và `en.json`.

### 14.4 Vòng phản hồi

Không gọi model riêng cho mỗi lần bấm. Mọi xử lý bằng code.

**1. Tách hai loại tín hiệu:**

| Tín hiệu | Nghĩa trong thiết kế |
|---|---|
| Emoji (sáu loại) | Tín hiệu **cảm xúc**. Có thể hướng tới nội dung được kể (Huhu vì câu chuyện buồn; Phẫn nộ vì sự việc), tới cách trả lời, hay là đùa, mỉa mai. Không bao giờ tự là đánh giá chất lượng |
| Lý do chất lượng và góp ý chữ | Tín hiệu **đánh giá**, có thể dẫn tới điều chỉnh |

**2. Điều không được suy ra:** từ emoji, hệ thống không suy ra "agent làm sai", "phải sửa ngay", "việc đã đạt" hay "goal đã đạt". Cụ thể:
- reaction không đổi trạng thái việc, goal hay hàng đợi;
- không đánh thức agent;
- không mở lượt.

**3. Đưa vào lượt kế tiếp:** ở lượt kế tiếp của **chính agent đó trong chính nhóm đó**, khối "Phản hồi gần đây của chủ nhóm" (tối đa 5 mục, 30 ngày, chỉ mục chưa bị bỏ) liệt kê cho mỗi tin:
- đoạn trích ngắn;
- emoji gốc, không đổi tên;
- lý do chất lượng;
- góp ý chữ.

Kèm câu dặn cố định:

> Emoji là cảm xúc của chủ nhóm, có thể về sự việc được kể; đừng coi là chấm điểm. Chỉ điều chỉnh theo lý do chất lượng và góp ý chữ. Chưa rõ thì giữ cách làm.

**4. Không tạo bài học chắc chắn từ emoji.**
- Bài học bền chỉ đến từ lý do chất lượng hay góp ý chữ, qua cơ chế đề xuất có nguồn: một gợi ý "Bài học đề xuất" hiện ở bảng agent, chủ bấm nhận mới thành bài học.
- Cơ chế đề xuất làm ở T2 nếu đủ đơn giản; nếu không thì để mốc sau, và T2 chỉ đưa phản hồi vào ngữ cảnh.

**5. Thu hồi:** chủ bỏ reaction, sửa hay xoá góp ý thì mục đó rời khỏi khối phản hồi ở lượt kế. Bài học đã nhận có nút gỡ như A3.

**6. Phạm vi học:** phản hồi trong nhóm X chỉ vào lượt ở nhóm X. Bài học đã nhận thuộc agent nên dùng ở mọi nơi; điều này hiện rõ trong hộp "Nhận bài học".

## 15. API và công cụ dự kiến

### 15.1 Route của chủ (dashboard, auth và CSRF như hiện nay)

| Route | Việc |
|---|---|
| `GET /teams?brain=&cursor=` | Danh sách nhóm, phân trang |
| `POST /teams` | Tạo nhóm `{name, description, members:[slug], leader_slug}` (đăng ký mã cho thành viên) |
| `GET /teams/{id}` | Nhóm, thành viên, trưởng nhóm, chế độ, trần, việc đang chạy, số việc chờ và bị chặn |
| `PATCH /teams/{id}` | Tên, mô tả, trạng thái (`active`/`paused`/`archived`) |
| `POST /teams/{id}/members` | Thêm `{slug}` hay tạo agent mới rồi thêm (gọi `POST /agents` hiện có trước) |
| `DELETE /teams/{id}/members/{agent_key}` | Bỏ thành viên |
| `POST /teams/{id}/leader` | Chọn, đổi, bỏ trưởng nhóm `{agent_key or null}` |
| `POST /teams/{id}/authority` | Bật, sửa, thu hồi Toàn quyền `{mode, grant}` |
| `GET /teams/{id}/queue` | Việc đang chạy, chờ (đúng thứ tự), bị chặn; `queue_version` |
| `POST /teams/{id}/queue/{task_id}/priority` | `{on: true/false, expected_queue_version}` |
| `POST /teams/{id}/tasks/{task_id}/cancel` | Huỷ việc |
| `POST /teams/{id}/tasks/{task_id}/amend` | Sửa yêu cầu, tăng `team_rev` |
| `POST /teams/{id}/tasks/{task_id}/unblock` | Trả lời, chạy lại bước, giao lại `{action, ...}` |
| `POST /teams/{id}/messages/{mid}/reaction` | `{value, reasons, comment, nonce}` |
| `POST /teams/{id}/messages/{mid}/decision` | Ghim hay bỏ ghim làm quyết định |
| `GET /teams/{id}/turns` | Sổ lượt theo việc, agent, ngày |

Gửi tin đi qua `/ws` như chat hiện nay. Gói tin thêm các trường:
- `team_id`;
- `client_msg_id` (bắt buộc với phiên `team:`);
- `mentions:[agent_key]`;
- `as_job: bool`.

### 15.2 Công cụ `javis_team` (chỉ trong lượt nhóm)

| `op` | Ai | Việc |
|---|---|---|
| `assign` | Trưởng nhóm, trong bước `plan` | Tạo bước `work` cho một thành viên, kèm brief và đầu vào |
| `request_help` | Thành viên đang ở bước `work` | Tạo bước `help` (mục 7.4) |
| `submit` | Người đang làm bước | Nộp kết quả của bước; host đăng tin |
| `propose_job` | Trưởng nhóm | Đề xuất việc (mục 7.1) |
| `open_job`, `reprioritize`, `add_member`, `remove_member`, `create_agent`, `set_cap`, `set_resonance` | Trưởng nhóm Toàn quyền | Như mục 13, mỗi lời gọi kiểm chế độ trong giao dịch |

Danh tính, nhóm, việc, bước lấy từ `turn_context` (thêm khoá `team_id`, `task_id`, `step_id`). Tham số model chỉ mang nội dung (brief, câu hỏi, kết quả).

## 16. Giao diện

Wireframe đầy đủ (desktop, màn hẹp, các trạng thái) ở [team-chat-wireframes.md](../../dev/team-chat-wireframes.md).

- **Thanh bên:** thêm mục "Nhóm" cạnh "Cộng sự". Trang Nhóm gồm ba phần:
  - danh sách nhóm (trái);
  - khung chat (giữa);
  - cài đặt nhóm (phải, ngăn kéo trên màn hẹp) với các tab Thành viên, Việc, Lượt, Cài đặt.
- **Khung chat:**
  - tin có tên và ảnh người gửi;
  - nhãn việc trên tin;
  - @ có gợi ý từ danh sách thành viên;
  - công tắc "Giao việc" trong khung soạn;
  - thanh "Đang làm: ..." với hai nút Sửa yêu cầu và Huỷ.
- **Màn hẹp:** danh sách nhóm là trang đầu; chạm một nhóm mở khung chat toàn màn; cài đặt nhóm là trang trượt lên.
- **Theo đúng các quy ước đang có:**
  - trang cài đặt xếp một cột, nút Lưu ở cuối;
  - không bảng hai ô;
  - lớp có `display:flex` phải kèm luật `[hidden]{display:none}` riêng.

## 17. Đo hiệu năng

Xem mục 12.5. Đo trước và sau T1 trên cùng máy:
- thời gian API (phía server) cho các route nhóm;
- thời gian trình duyệt (vẽ khung chat, mở cài đặt nhóm).

Hai loại số đo ghi tách nhau. Kết luận về VPS chỉ có khi đo trên VPS sau khi chủ dự án duyệt riêng.

## 18. Nâng và hạ phiên bản

- **Kho mới** `team.sqlite3`: mã cũ không đọc.
- **Cột thêm vào `messages` và `tasks`** đều cho phép null, mã cũ bỏ qua.
- **Trạng thái `team_*`** không nằm trong tập trạng thái mà mã Kanban cũ nhặt, nên khi hạ phiên bản, việc nhóm không bị mã cũ chạy bằng aux.
- **Snapshot lần đầu nâng:** chép `kanban.sqlite3` và `sessions.db` thành `.pre-<số phiên bản T1>`, bằng SQLite backup như A5.
- **Công cụ khôi phục** `tools/team_chat_restore_pre.py`, theo mẫu `tools/resonance_restore_pre_a5.py`.
- **Test quay về** chạy mã bản phát hành thật trước T1 qua `git show`, như `test_resonance_a5_rollback.py`.
- **Hạ không khôi phục:** mã cũ hiện các dòng `team_*` trên trang Công việc với trạng thái lạ nhưng không chạy chúng. Phiên `team:` hiện như phiên thường. Ghi rõ trong hướng dẫn.

## 19. Mốc triển khai

| Mốc | Nội dung | Luồng hữu ích |
|---|---|---|
| **T0** (nhỏ, làm trước được) | Công tắc Cộng hưởng trên dòng trợ lý; `/agents` trả trạng thái; trang Cài đặt chỉ còn tóm tắt; tải lại khi 409; đồng bộ hai tab | Bật, tắt ngay trên màn Trợ lý |
| **T1** (lõi nhóm chat) | Mục 5 đến 12 ở chế độ Quyền giới hạn, trần mặc định cố định, các màn ở mục 16 | **Tạo nhóm, thêm agent, chọn trưởng nhóm, giao chung hay @, hàng đợi có Ưu tiên, phối hợp và nhờ hỗ trợ, kết quả về đúng nhóm** |
| **T2** | Sáu reaction, lý do, góp ý; khối phản hồi trong lượt kế; (đề xuất bài học nếu đủ đơn giản) | Phản hồi theo đủ sáu cảm xúc |
| **T3** | Toàn quyền: hộp cấp quyền, trần chỉnh được và "Không giới hạn", agent do nhóm quản lý, công cụ quản trị cho trưởng nhóm, trần goal theo nhóm (mục 13.6), quyền "Được ngắt việc", phát hiện vòng có chính sách | Trưởng nhóm tự vận hành trong phạm vi chủ cấp |
| **T4** | Lịch sử dài: tóm tắt bằng code, tìm trong nhóm, đo trên VPS (cần duyệt riêng) | Nhiều nhóm, lịch sử dài |

- Mỗi mốc là một PR, giữ số phiên bản khi bắt đầu viết mã.
- **T1 lớn nhất. Không tách nhỏ hơn**, vì GOAL đòi mốc đầu phải có đủ luồng từ tạo nhóm tới kết quả đúng nhóm.
- **Pilot model thật** cho từng mốc là gói riêng, có đầu vào, engine, trần và lời duyệt riêng. Thiết kế này không cấp phép pilot.

## 20. Ma trận nghiệm thu

Mọi ca chạy bằng **engine giả** trừ khi ghi khác. Mã ca: TC. "Mốc" là mốc đầu tiên phải đạt.

| Mã | Ca | Mốc | Đường mã dự kiến | Bằng chứng |
|---|---|---|---|---|
| TC1 | Tạo ba nhóm; cùng một agent ở hai nhóm, làm trưởng nhóm ở một nhóm, thành viên ở nhóm kia | T1 | `team_store.create`, `add_member`, `agent_register` | Test kho và route; ảnh chụp danh sách nhóm |
| TC2 | Thêm agent có sẵn; tạo agent mới trong cài đặt nhóm (qua `POST /agents`) rồi thêm; bỏ thành viên; agent vẫn còn ở Jarvis 007 và nhóm khác | T1 | route `members` | Test |
| TC3 | Tạo agent trùng slug trả 409, không ghi đè file cũ | T1 | `POST /agents` | Test so bytes file cũ |
| TC4 | Đổi tag của thành viên: tư cách thành viên, trưởng nhóm, quyền không đổi | T1 | `/capability/meta` | Test |
| TC5 | Đổi tên agent: vẫn là thành viên; xoá rồi tạo lại cùng slug: mã mới, không là thành viên, không nhận việc cũ | T1 | `agent_retire`, `team_members.status` | Test |
| TC6 | Tin không @: chỉ trưởng nhóm trả lời một lượt; nhóm không có trưởng nhóm: 0 lượt, có băng rôn | T1 | định tuyến mục 7.2 | Sổ lượt của engine giả |
| TC7 | Một @, nhiều @ (đúng thứ tự, người sau thấy người trước), quá trần @, @ thành viên đã rời | T1 | như trên | Sổ lượt, tin hiển thị |
| TC8 | Chữ "@Y" trong câu trả lời của agent không đánh thức Y | T1 | | Sổ lượt = 0 cho Y |
| TC9 | Tin thường không tạo việc hay goal; công tắc "Giao việc" tạo đúng một việc; gửi lại cùng `client_msg_id` không tạo thêm tin, việc hay lượt | T1 | `client_msg_id`, `source_ref` | Đếm dòng `tasks`, `messages`, `team_turns` |
| TC10 | Giao chung: bước `plan`, hai bước `work`, `synthesize`; kết quả có tác giả, nhãn việc, trạng thái | T1 | `team_runner` | Test luồng với engine giả |
| TC11 | @ giao trực tiếp: bắt đầu bằng `work` của người được @; trưởng nhóm không làm lại; việc vẫn vào hàng chung | T1 | | Test |
| TC12 | Nhờ hỗ trợ A sang B rồi A tiếp tục; B nhờ ngược A bị chặn; độ sâu 3 bị chặn; không tiến triển hai lượt thì chặn | T1 | `request_help` | Test |
| TC13 | Trần lượt mỗi việc, bước mỗi việc, lượt mỗi ngày của nhóm: chạm trần thì `cap_reached`, không gọi thêm | T1 | kiểm trần lúc giữ chỗ | Sổ lượt |
| TC14 | **A đang chạy, B, C chờ, ưu tiên C: thứ tự A, C, B; A không chạy lại; C không chen** | T1 | `team_prio`, `dispatch` | Test với đồng hồ giả |
| TC15 | Ưu tiên lặp (không đổi gì); bỏ ưu tiên (về vị trí cũ); hai việc ưu tiên theo thứ tự bấm | T1 | | Test |
| TC16 | Hai tab cùng đổi thứ tự: một bên 409 và nhận hàng đợi mới; không bao giờ hai việc chạy cùng lúc trong một nhóm | T1 | CAS `queue_version` | Test đồng thời |
| TC17 | Restart giữa lúc nhận việc, giữa bước trước mốc engine, sau mốc engine | T1 | `team_reclaim` | Test với kho thật, server dựng lại |
| TC18 | Việc chờ chủ, việc lỗi: rời chỗ chạy, hàng đi tiếp, hiện ở "Bị chặn", có tin hộp thư, có nhắc sau 24 giờ | T1 | | Test |
| TC19 | Bỏ thành viên đang làm (trước và sau mốc engine); đổi trưởng nhóm giữa việc; bỏ trưởng nhóm thì `no_leader` | T1 | mục 6.3, 6.4 | Test |
| TC20 | Sửa yêu cầu và huỷ việc giữa chừng; kết quả muộn có nhãn, `applied=0` | T1 | mục 7.6 | Test |
| TC21 | Cùng agent ở hai nhóm cùng có việc: khoá bận, chờ FIFO, mỗi kết quả về đúng nhóm, ngữ cảnh không lẫn | T1 | `agent_busy`, mạch thành viên | Test kiểm lời nhắc gửi engine giả |
| TC22 | Không lẫn dữ liệu: lời nhắc của lượt nhóm không chứa tin nhóm khác, chat riêng hay bộ nhớ chủ | T1 | khối nhóm mục 11.2 | Test so lời nhắc |
| TC23 | Agent chưa bật Cộng hưởng làm được bước nhóm nhưng không có `javis_goal`; goal tạo trong lượt nhóm báo về đúng phiên `team:` | T1 | | Test |
| TC24 | Cổng A4 và A5 giữ nguyên: tin nhắn không cấp quyền ghi; goal có đội vẫn cần reviewer đạt | T1 | test A4, A5 hiện có chạy lại | Test hồi quy |
| TC25 | Công tắc Cộng hưởng trên dòng trợ lý: chỉ báo thành công khi server xác nhận; 409 thì tải lại; hai tab đồng bộ; danh sách thành viên nhóm hiện cùng trạng thái | T0/T1 | `workspace.js`, route toggle | Test JS, smoke giao diện |
| TC26 | Tắt agent đang có việc: hộp xác nhận nêu goal và các nhóm; việc nhóm không dừng | T0/T1 | | Smoke giao diện |
| TC27 | Trang Cài đặt không còn công tắc theo agent; có tóm tắt và liên kết | T0 | | Test i18n, smoke |
| TC28 | Sáu reaction: chọn, đổi, bỏ; desktop và điện thoại; giữ qua F5, restart; đúng người, tin, agent, nhóm, `content_sha` | T2 | `team_reactions` | Test kho, smoke giao diện |
| TC29 | Reaction không đổi trạng thái việc, goal, hàng đợi, không mở lượt, không gọi model | T2 | | Sổ lượt = 0 |
| TC30 | Khối phản hồi ở lượt kế giữ emoji gốc, lý do, góp ý; có câu dặn; chỉ trong đúng nhóm; bỏ reaction thì rời khối | T2 | | Test so lời nhắc |
| TC31 | Toàn quyền: trưởng nhóm không tự bật được; chủ bật thì ghi `team_authority`; trưởng nhóm thêm thành viên, tạo agent, đổi thứ tự việc chờ; mọi thao tác có sự kiện | T3 | `javis_team` op quản trị | Test |
| TC32 | "Không giới hạn" là `null` + cờ, không phải số; trần máy chủ và hạn mức nhà cung cấp vẫn hiện và vẫn áp | T3 | | Test |
| TC33 | Trưởng nhóm Toàn quyền không sửa được cấu hình agent không do nhóm quản lý; sửa agent do nhóm quản lý thì báo các nhóm khác bị ảnh hưởng | T3 | | Test |
| TC34 | Thu hồi Toàn quyền giữa lượt: công cụ quản trị sau mốc bị từ chối; trần về mức giới hạn; việc vượt trần bị chặn | T3 | | Test |
| TC35 | Không có quyền "Được ngắt việc" thì trưởng nhóm Toàn quyền không ngắt được việc đang chạy | T3 | | Test |
| TC36 | Vòng không tiến triển ở "Không giới hạn": tạm dừng và báo, không chạy tiếp âm thầm | T3 | | Test |
| TC37 | Màn hẹp 375px và desktop: danh sách nhóm, chat, cài đặt nhóm, bộ chọn reaction, không cuộn ngang | T1/T2 | | Ảnh chụp sandbox |
| TC38 | 50 nhóm, 5.000 tin: mở nhóm chỉ tải trang đầu; số đo API và trình duyệt ghi tách nhau | T1/T4 | | Số đo kèm máy đo |
| TC39 | Quay về bản trước T1 bằng snapshot; hạ không khôi phục không chạy việc nhóm | T1 | công cụ khôi phục | Test quay về với mã phát hành thật |

## 21. Bảng quyết định

### 21.1 Yêu cầu đã chốt (theo GOAL, không hỏi lại)

- Nhiều nhóm; nhóm có tên, mô tả, thành viên, lịch sử, việc riêng.
- Agent ở nhiều nhóm; mỗi nhóm một trưởng nhóm do chủ chọn.
- Tag chỉ phân loại; cặp A5 không phải cấu trúc nhóm.
- Hàng đợi: việc đang làm chạy tiếp; Ưu tiên xét trước việc thường sau khi việc đang làm xong; lưu bền; @ giao trực tiếp vẫn vào hàng chung; ví dụ A, C, B.
- Công tắc Cộng hưởng trên màn Trợ lý, chỉ báo thành công khi server xác nhận.
- Hai chế độ trưởng nhóm. "Không giới hạn" là trạng thái rõ. Chủ luôn thu hồi được.
- Sáu reaction, giữ loại emoji gốc, không suy diễn chắc chắn, không gọi model cho mỗi lần bấm.

### 21.2 Mặc định đề xuất (em tự chọn, có lý do; đổi được khi review)

| # | Mặc định | Lý do |
|---|---|---|
| M1 | Kiến trúc A (mục 3) | Dùng lại lưu bền và phục hồi của Kanban, không thêm hệ giao việc |
| M2 | Một việc chạy mỗi nhóm; hai nhóm chạy cùng lúc trên cả máy | Đúng yêu cầu hàng đợi; giữ chi phí và tải trong tầm |
| M3 | Ưu tiên theo thứ tự bấm; bấm lặp không đổi; bỏ ưu tiên về vị trí cũ | Dễ hiểu, xác định được |
| M4 | Việc bị chặn rời chỗ chạy | Không để nhóm kẹt vô hình |
| M5 | Bước đã gọi engine bị gián đoạn khi restart: không tự chạy lại | Tránh trả tiền hai lần |
| M6 | Trần mặc định ở mục 12.3 | Đủ cho một việc vừa (lập kế hoạch, ba người làm, hỗ trợ, tổng hợp) |
| M7 | Model của agent đọc mỗi lượt từ file agent | Mạch thành viên là phiên ẩn, ảnh chụp sẽ cũ |
| M8 | `javis_task` ẩn trong lượt nhóm | Một chỗ giao việc trong nhóm |
| M9 | Bỏ công tắc trùng ở cột phải và trang Cài đặt | Không hai công tắc cho một agent |
| M10 | Bảng reaction riêng cho nhóm, không dùng bảng A3 | Bảng A3 gắn goal và tin báo |
| M11 | Toàn quyền không chuyển theo khi đổi trưởng nhóm | Quyền gắn người, không gắn chức danh |

### 21.3 Điểm đã chốt (chủ dự án đồng ý cả bảy đề xuất, 13/10/2026)

| # | Câu hỏi | Đã chốt | Ảnh hưởng |
|---|---|---|---|
| D1 | Tin không @ ở chế độ trò chuyện: trưởng nhóm trả lời (một lượt mỗi tin), hay không ai trả lời trừ khi @? | Trưởng nhóm trả lời | Chi phí mỗi tin, cảm giác "nhóm có người" |
| D2 | Giao việc: chỉ khi anh bật "Giao việc", hay trưởng nhóm được tự nhận ra yêu cầu và đề xuất (anh bấm một lần)? | Cả hai: công tắc rõ ràng, cộng đề xuất của trưởng nhóm cần anh bấm | Số lần bấm và chi phí |
| D3 | Một agent chỉ chạy một lượt nhóm cùng lúc trên cả máy (an toàn bộ nhớ, chậm hơn khi agent ở nhiều nhóm)? | Có | Tốc độ và chống lẫn |
| D4 | Toàn quyền có được duyệt quyền ghi file A4 không? | Chỉ trong một thư mục nhóm do anh chọn; ngoài thư mục đó vẫn chờ anh bấm trên thẻ | Mở một phần cổng A4 |
| D5 | Trưởng nhóm Toàn quyền sửa cấu hình chung (lời nhắc, model, Cộng hưởng) của agent nào? | Chỉ agent do nhóm quản lý | Ảnh hưởng chéo nhóm |
| D6 | "Không giới hạn" lượt model có được áp cho provider API trả phí? | Chỉ cho provider anh tích trong hộp cấp quyền; luôn hiện số đã dùng | Chi phí |
| D7 | Trần mặc định mục 12.3 (12 lượt mỗi việc, 8 bước, 3 @, 100 lượt mỗi nhóm mỗi ngày) | Như bảng | Chi phí và độ sâu phối hợp |

## 22. Tự soát mâu thuẫn

| Cặp có thể vênh | Kết luận |
|---|---|
| Ưu tiên và "@ trực tiếp không vượt hàng" | Không vênh: @ giao việc vào hàng chung; chỉ Ưu tiên của chủ hay trưởng nhóm Toàn quyền đổi thứ tự |
| Lượt trò chuyện không qua hàng và "một việc chạy mỗi nhóm" | Không vênh: lượt trò chuyện không phải việc nhóm; nó chỉ đợi khoá bận của agent. Ghi rõ ở mục 7.2 |
| Toàn quyền và "lệnh của chủ luôn thắng" | Không vênh: mọi thao tác Toàn quyền kiểm chế độ trong giao dịch; thu hồi có mốc `revoked_at` |
| Toàn quyền và "việc đang làm chạy hết" | Không vênh: ngắt cần quyền riêng mặc định tắt (mục 13.4) |
| Tắt Cộng hưởng và việc nhóm | Đã chốt: công tắc chỉ ảnh hưởng goal; hộp xác nhận nói rõ (mục 10.2) |
| Restart và chống gọi trùng | Bước đã gọi engine không tự chạy lại; bước chưa gọi thì hoàn lượt (mục 8.6) |
| Huỷ việc và bản đã cam kết đăng A4 | Theo A4: bản đã cam kết vẫn hoàn tất; chưa cam kết thì hết hiệu lực (mục 11.4) |
| Reaction và vòng học | Emoji không đổi trạng thái hay tạo bài học chắc chắn; chỉ lý do và góp ý chữ dẫn tới đề xuất (mục 14.4) |
| Khoá bận theo agent và chat riêng, goal | Giới hạn đã ghi: T1 chưa khoá chat riêng và goal (mục 8.7) |
| Model riêng của agent và Cộng hưởng | Goal vẫn dùng model việc nền như A1 tới A5; ghi rõ ở mục 12.1 |
