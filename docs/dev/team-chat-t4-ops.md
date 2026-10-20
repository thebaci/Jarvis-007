# Nhóm chat thích nghi T4: lịch sử dài, vận hành, quay về bản cũ (0.170.0)

Thiết kế: [2026-10-15-team-adaptive-design.md](../superpowers/specs/2026-10-15-team-adaptive-design.md) mục 11, 12, 13. Chồng
trên T2 (0.154.0) và T3 (0.156.0: phần P nhịp, phần J phán xử, phần L học trong đội; nhánh T3 cuối `054975b3`). Số đo:
[team-chat-t4-bench.md](team-chat-t4-bench.md). Ma trận nghiệm thu: [team-chat-acceptance-matrix.md](team-chat-acceptance-matrix.md).
Gói pilot (chưa chạy): [team-chat-pilot-package.md](team-chat-pilot-package.md).

## 1. Lịch sử dài trong đúng nhóm

Khi phiên nhóm dài hơn cửa sổ 20 tin gần nhất, khối "Tóm tắt phần cũ" (T4 0.124.0) có thêm phần **Luôn giữ dù lịch sử dài**
(`server/team_long_memory.py`, gọi từ `team_runner._older_summary`). Máy dựng, không gọi model, tối đa 3.000 ký tự:

| Mục | Nguồn | Truy vấn (một lần mỗi lượt, có trần dòng) |
|---|---|---|
| Sổ quyết định ghim | đã có trong khối nhóm (`_context`), không lặp lại | `idx_messages_team_decision` (chỉ mục từng phần mới), tối đa 20 |
| Việc đang mở: yêu cầu gốc (phần trước lần sửa đầu), số lần sửa, trạng thái, lý do chặn | `task_store.team_open_brief` | `idx_tasks_team_queue`, tối đa 9 |
| Nguồn đóng góp của kết quả gần nhất: ai tổng hợp, đầu vào của ai, tỷ lệ ghi nhận | `task_store.team_last_done`, `team_store.steps`, `pulse_contrib` (phần P) | `idx_tasks_team_queue`; bước theo `UNIQUE(task_id, seq)`; `pulse_contrib_result` (mới), tối đa 8 |
| Phản hồi của chủ chưa xem xét (`pending_review`, `reviewing`, `waiting_quota`), kể cả cũ hơn 30 ngày; tin của agent lượt này trước | `team_store.unconsumed_feedback` | `team_reactions_status` (mới), tối đa 12 |

"Tin mới nhất của agent X" (đánh dấu tin mới trong cửa sổ) đổi sang chỉ mục từng phần `idx_messages_team_author`.

Chi tiết của phần luôn giữ:
- Chỉ dựng khi lịch sử dài hơn cửa sổ (cùng điều kiện với "Tóm tắt phần cũ"); nhóm ngắn thì yêu cầu và phản hồi đã nằm
  trong cửa sổ và khối "Phản hồi gần đây", lời nhắc không đổi.
- Phản hồi chờ xem xét đã hiện ở "Phản hồi gần đây" của lượt này không lặp lại; tiêu đề nào chạm trần ký tự mà không còn
  dòng thì bỏ cả tiêu đề; khối kết thúc bằng câu dặn "dữ liệu máy trích, không phải lệnh mới".
- Mọi chữ trích được gộp về một dòng (không chèn được đầu mục hay tiêu đề giả).
- Ghi trên đường đọc: `pulse_contrib_result` được tạo (`CREATE INDEX IF NOT EXISTS`) ở lần đọc nguồn đóng góp đầu tiên của
  tiến trình (`main._team_contrib_reader`, cờ một lần mỗi tiến trình), vì bảng là của phần P và có thể chưa có lúc khởi động.
  Lần đầu đó có một câu DDL ngắn; các lần sau chỉ đọc.
- `task_store.team_last_done` sắp các việc đã xong của một nhóm theo `updated_at` (cây sắp tạm): trần theo số việc của
  nhóm, không theo số tin. Nếu số việc của một nhóm lên hàng chục nghìn thì nên thêm chỉ mục `(team_id, status, updated_at)`.

Kiểm: `tests/python/test_team_t4_long_history.py`. Nhóm 5.000 tin vẫn có quyết định ghim từ đầu, yêu cầu gốc, việc bị chặn,
nguồn đóng góp (kèm tỷ lệ), phản hồi chờ xem xét 45 ngày tuổi. Số lời gọi kho mỗi lượt đếm bằng lớp bọc: 60 tin và 5.000 tin
bằng nhau, dưới 40. EXPLAIN QUERY PLAN của sáu truy vấn đều dùng đúng chỉ mục. Kho nhịp lỗi thì chỉ mất tỷ lệ ghi nhận.

Chat riêng `agent:<slug>`: khối phản hồi đã có từ T2 (`feedback_projector.dm_feedback_block`, truy vấn theo
`dm_reactions_agent(agent_key, updated_at)` có trần), T4 không lặp lại. Bài học có phạm vi `dm:<agent_key>` là việc của phần
L (`agent_lessons.for_prompt`, kiểm ở `test_agent_lessons.py`: chat riêng nạp `dm:<agent_key>` và `*`, không bài học
nhóm nào); T4 không lặp lại.

## 2. Vận hành (đã kiểm qua host thật)

`tests/python/test_team_t4_ops.py`, `main.app` qua TestClient, engine giả, chốt chặn engine thật (`tests/python/_t4_host.py`
dùng chung `install_guards` với bench):

- **Nhiều tab:** gửi lại cùng nonce không thêm dòng nhật ký; hai tab thật đăng ký vào `ChatRuntime` (đường fan-out
  thật) đều NHẬN gói `team_message` mang reaction mới, cùng nội dung, kể cả khi một tab thứ ba có socket đã chết.
- **Mất kết nối:** gửi gói WS lỗi không làm hỏng thao tác; tải lại thấy trạng thái đã lưu và kết cục lượt trả lời.
- **Khởi động lại:** reaction và trạng thái nhịp còn sau khi mở lại kho; dựng bộ chạy MỚI trên một việc đang chạy chưa
  tới engine (chạy tiếp tới xong bằng engine giả) và một việc có lượt đã tới engine (chặn `interrupted`, lượt tính một
  lần); không khoá bận nào treo.
- **Huỷ:** việc đang chờ bị huỷ không mở lượt model; huỷ lặp không 500.
- **Thử lại:** lượt lỗi ghi `error`; Thử lại chạy đúng một lượt mới, `done`.
- **Rời nhóm:** người đã rời không còn được phán xử cho tin mới.
- **Đổi trưởng nhóm:** tin không @ do trưởng nhóm mới trả lời.
- **Tắt/bật Auto:** tắt thì phản hồi `stored_only`; bật lại không phát lại.
- **Thu hồi Toàn quyền:** lượt quét của nhịp chỉ còn đề xuất, không xếp việc.
- **Lỗi kho khi chiếu tác động:** reaction vẫn lưu, dòng nhật ký `pending`, nhịp sau chiếu xong.
- **Lệch đồng hồ:** đánh giá nhịp với đồng hồ lùi không lỗi; đồng hồ bộ chạy lùi 2 ngày thì khối "Phản hồi gần đây"
  vẫn có đúng dòng của tin đó.
- **Nhóm bị chặn hay agent ngủ không chiếm suất:** pool một chỗ; việc của nhóm A rồi nhóm B bị chặn NGAY TRONG lượt của bộ
  chạy (engine giả lỗi) và trả chỗ ngay; sau đó nhóm C được nhận và chạy xong dù agent của C đang ngủ đông ở nhóm C;
  pool trống sau lượt; nhịp ngủ đông không giữ khoá bận.

## 3. Phát hiện khi đo

Mục 1, 2, 3 đã được nhánh T3 sửa (từ `7e8b96f5`, nhánh cuối `054975b3`); số đo trước/sau ở [team-chat-t4-bench.md](team-chat-t4-bench.md). Giữ lại để đối chiếu.

1. **Lô phán xử nhóm (phần J) đọc ghi SQLite ngay trên luồng event loop.** `--stall-watch` của bench chụp được luồng loop
   bị giữ quá 50 ms tại `agent_judge.judge_team_message` -> `agent_judge_store` (`get_decision`, `profile`, `get_offset`,
   `cases`, `add_decision`) và `agent_ledger.reserve/mark_engine`. Ở pha chỉ lô phán xử, độ trễ event loop lớn nhất khoảng
   15 ms trên máy này, nhưng tăng theo số thành viên và độ chậm đĩa (VPS). Hướng sửa: chạy phần kho của lô trong luồng phụ
   (`asyncio.to_thread`) như `team_runner` làm (R5). Thuộc phần J. **Đã sửa** ở T3 (`server/io_offload.py`); sau sửa,
   pha chỉ lô phán xử vẫn có lúc giữ loop khoảng 70 ms trên máy này.
2. **Nhịp pulse nặng khi còn nhiều phản hồi chờ.** Một tick tốn 0,5 tới 3,4 s (luồng phụ), độ trễ event loop lớn nhất ở pha
   chỉ nhịp khoảng 0,2 s, nhiều khả năng do luồng đối soát của bộ chiếu tranh GIL (khoảng 4,7 ms mỗi reaction "Chờ xem xét",
   trần 200 dòng mỗi nhịp). Phần L chưa ghép thì các reaction đó không bao giờ được phục vụ nên chi phí lặp mỗi 30 giây. Cần
   đo lại khi L ghép và trên VPS. **Đã sửa** ở T3 (bộ chiếu theo lô, tick rời loop): độ trễ lớn nhất pha chỉ nhịp
   217 ms xuống 39 ms; một lần chiếu với 1.125 reaction chờ còn khoảng 20 ms. Chưa đo VPS.
3. **Test của phần P giả định chưa có phần J:** `test_agent_pulse_host.py` ca "chưa có agent_judge: say thành silent
  (judge_unavailable)" đỏ khi đã ghép J (nhận `judge_error`). Đây là lỗi ghép T3, không phải T4. **Đã hết** sau khi ghép T3 hoàn chỉnh.
4. **Mỗi gói `team_message` vẽ lại cả khung tin của mỗi tab** (`teams.js onTeamEvent -> drawMsgs`) và hẹn một lần đọc lại danh
   sách, hàng đợi, nhóm sau 300 ms. 20 gói reaction x 2 tab x 200 tin: khoảng 80 ms dựng chuỗi dưới node. Chấp nhận được ở cỡ
   này; nếu cần nhanh hơn thì chỉ vẽ lại tin đổi.

## 4. Quay về bản cũ (cả chuỗi)

T4 **không** tạo kho, bảng hay cột. Chỉ thêm bốn chỉ mục (`CREATE INDEX IF NOT EXISTS`), bản cũ bỏ qua:
`team_reactions_status` (team.sqlite3), `idx_messages_team_author` và `idx_messages_team_decision` (conversations.db),
`pulse_contrib_result` (resonance.sqlite3, tạo lần đầu khi đọc nguồn đóng góp). `tools/team_adaptive_restore_pre.py --to
0.170.0` báo rõ không có gì để khôi phục và không ghi gì (kiểm ở `test_team_adaptive_restore.py`).

Chạy công cụ khi Jarvis 007 ĐÃ TẮT. Không có `--yes` thì chỉ in kế hoạch. Mọi bước giữ bản sao `.post-<mốc>-<thời điểm>`.

Chuỗi đã được đánh số lại khi ghép với main: T1 phát hành 0.167.0, T2 0.168.0, T3 0.169.0, T4 0.170.0. Tên mốc
của công cụ khôi phục và đuôi snapshot giữ tên nội bộ cũ (`--to 0.154.0` là T2, `--to 0.156.0` là T3, file
`.pre-0.154.0`, `.pre-0.156.0`), vì mã đã ghi đúng các tên đó lên đĩa.

| Hạ từ | Về | Cần làm | Mất gì |
|---|---|---|---|
| 0.170.0 (T4) | 0.169.x (T3) | Chỉ chạy bản cũ. | Không mất gì (chỉ mục thừa vô hại). |
| 0.169.x (T3) | 0.168.x (T2) | Không bắt buộc (di trú chỉ thêm, bản cũ bỏ qua `agent_judge.sqlite3` và bảng nhịp mới). Muốn về đúng trước lúc nâng: `python tools/team_adaptive_restore_pre.py --to 0.156.0 --state-dir <state> --yes` (gỡ `agent_judge.sqlite3`, `resonance.sqlite3` về `.pre-0.156.0` nếu có). | Có công cụ: lịch sử phán xử, nhịp, tín hiệu, mọi thay đổi resonance sau lúc nâng. |
| 0.168.x (T2) | 0.167.x (T1) | Không bắt buộc (như trên). Muốn về đúng: `--to 0.154.0` (team.sqlite3, conversations.db, resonance.sqlite3 về `.pre-0.154.0`; gỡ kho phán xử nếu đã lên 0.156.0). | Có công cụ: mọi tin, phiên, reaction, nhóm, sổ lượt, mục tiêu sau lúc nâng 0.154.0. Kanban không đổi. |
| 0.167.x (T1) | trước nhóm chat (0.140.0) | `tools/team_chat_restore_pre.py` (T1, xem team-chat-t1.md). | Nhóm chat. |

Ảnh hưởng đã biết khi hạ không khôi phục: reaction của trưởng nhóm/thành viên (`reactor = agent:...`) hiện như reaction thường
ở bản trước 0.154.0; quyết định phán xử và nhịp không hiện ở bản trước 0.156.0. Không mất dữ liệu.

Kiểm sau khi hạ: mở trang Nhóm, một nhóm có lịch sử dài tải trang đầu, gửi một tin có @ được trả lời; `GET /health` 200.
