# Gói pilot nhóm chat thích nghi trên model thật (T1-T4)

Trạng thái: **đã chạy một lần 2026-10-16** trên 0.170.0, chủ duyệt trần 30 (thấp hơn mức 60 đề xuất ở mục 3). Báo cáo gốc và
bằng chứng nằm ngoài repo: `exports/reviews/team-adaptive/pilot-2026-10-16/PILOT-REPORT.md`. Không ai chạy lại gói này, thử lại, nâng trần hay đổi sang API trả phí khi chưa có lệnh duyệt trực tiếp
của chủ dự án (GOAL mục 13). Engine giả đã chứng minh phần kỹ thuật (ma trận: [team-chat-acceptance-matrix.md](team-chat-acceptance-matrix.md));
engine giả KHÔNG chứng minh chất lượng thảo luận, phán xử hay học trên model thật. Gói này là để chứng minh phần đó.

## 1. Điều kiện trước khi xin duyệt

- Head đã chốt: SHA của nhánh tích hợp T1-T4 có CI xanh trên đúng head đó; ghi SHA vào báo cáo. Phần L của T3 (bài học, góp ý
  đồng đội, tự rà soát) đã ghép ở nhánh T3 (cuối `054975b3`, review xác minh đạt).
- Checkout sạch (`git status` rỗng), `.venv` của repo, state MỚI trong thư mục tạm (không dùng state thật của chủ), brain pilot
  riêng gồm 4 trợ lý có vai khác nhau: điều phối (Lan), số liệu (Minh), nội dung (Hoa), kiểm chứng (Tuấn).
- Server sandbox trên cổng 7788 (không bao giờ 7777), `JAVIS_STATE_DIR` trỏ state tạm. Tắt bằng cổng
  (`Get-NetTCPConnection -LocalPort 7788 | Stop-Process`), không theo dòng lệnh.
- Engine và provider do chủ chọn trên trang Models của sandbox (Jarvis 007 không tự chọn model). Ghi lại: engine nhóm (model riêng
  của từng trợ lý hay model chính), engine việc nền (lô phán xử, lượt quét). Không API trả phí nếu chủ không nói rõ.
- `JAVIS_PULSE_TICK_PAUSED=0` chỉ khi kịch bản P4 chạy; các kịch bản khác để nhịp nền dừng (`=1`) và gọi tick bằng tay để đếm
  được lượt.
- **Nhịp nền dừng khi MỘT TRONG HAI cờ bằng 1:** `JAVIS_PULSE_TICK_PAUSED` hay `JAVIS_RESONANCE_TICK_PAUSED` (`_pulse_tick` trong
  `server/main.py`). Kịch bản cần nhịp (P4, lượt chủ động của P5, lượt xem xét phản hồi của P6) phải đặt CẢ HAI bằng 0. Pilot
  2026-10-16 phần 2 chỉ đặt cờ thứ nhất nên 4 tick không chạy lượt nào, lý do `reaction_review` nằm chờ.

## 2. Cổng duyệt của chủ

Gửi chủ đúng một tin gồm: SHA, danh sách kịch bản (mục 4), trần lượt (mục 3), engine/provider, thời gian dự kiến, cách dừng.
Chỉ bắt đầu khi chủ trả lời duyệt rõ ràng trong chat. Ghi nguyên văn câu duyệt và thời điểm vào hồ sơ. Mỗi lần chạy lại (kể cả
sau lỗi kỹ thuật) là một lần xin duyệt mới.

## 3. Trần lượt (`JAVIS_RESONANCE_CALL_CEILING`)

Trần chung tính trọn đời trên state (thiết kế 9.1): mọi lượt nhóm, lô phán xử, lượt quét, xem xét, tự rà soát. State mới nên
bắt đầu từ 0. Đề xuất **`JAVIS_RESONANCE_CALL_CEILING=60`**:

| Kịch bản | Lượt dự kiến | Gồm |
|---|---|---|
| P1 gọi trực tiếp và tự lên tiếng | 10 | 3 tin x (1 lượt trả lời + 1 lô phán xử) + tối đa 4 lượt tự lên tiếng |
| P2 phân công, phản hồi, sửa bản | 14 | kế hoạch, 2 bước làm, 1 kiểm chứng, 1 tổng hợp, sửa yêu cầu một lần rồi làm lại |
| P3 sáu reaction và dạy phán xử | 6 | 2 lượt trả lời để có tin, 2 lô phán xử sau nhãn, 2 dự phòng |
| P4 nhịp và lần thức | 8 | tối đa 4 lượt quét qua 4 tick, 4 dự phòng |
| P5 chat riêng | 6 | 2 câu hỏi trực tiếp (ngoài trần: chủ tự gõ) + 2 lượt chủ động có phán xử + 2 dự phòng |
| P6 học trong đội (cần L) | 8 | 2 lượt xem xét phản hồi, 1 tự rà soát, lượt kế tiếp để thấy thay đổi |
| P7 ghi nhận đóng góp | 4 | 1 tổng hợp có 2 đầu vào, phản hồi kết quả cuối |
| Dự phòng 20% nghĩa vụ | (tự động) | lượt tự phát chỉ dùng tới floor(60 x 0.8) = 48 |

Thêm: `daily_turns` của nhóm pilot 40, `judge_daily` 20, `agent_daily_calls` 6 mặc định. Hạn giờ mỗi lượt nhóm giữ mặc định
(`JAVIS_TEAM_TURN_TIMEOUT=600`).

## 4. Kịch bản và ca của ma trận

| Mã | Làm gì | Ca chứng minh | Chỉ có test giả trước pilot |
|---|---|---|---|
| P1 | Chủ @Minh hỏi số liệu; rồi một câu hỏi chung không @; rồi một câu tán gẫu | 2, 19, 10 | đúng |
| P2 | Giao việc "kế hoạch nhập hàng tháng 11" cho nhóm; Tuấn kiểm chứng; chủ sửa yêu cầu sau kết quả | 3, 12, 11 | đúng |
| P3 | Thả sáu emoji ở nhóm và chat riêng, đổi, bỏ; sửa một ca im thành "Đáng lẽ nên nói", một ca nói thành "chen ngang" | 4, 21, 9 | đúng |
| P4 | Bật Auto cho Minh, Hoa; để nhịp chạy 4 tick; một nhóm có việc, một nhóm im | 6, 7, 23, 24 | đúng (đồng hồ giả) |
| P5 | Chat riêng với Hoa: hỏi trực tiếp; để Hoa có lượt chủ động | 20 | đúng |
| P6 | Phản hồi có lý do chất lượng cho Hoa; chờ lượt xem xét; lượt kế tiếp đổi cách làm | 5, 17, 25, 26 | đúng (L đã ghép ở nhánh T3 `054975b3`) |
| P7 | Thả ❤️ trên bản tổng hợp của P2 | 8, 28 | đúng |

## 5. Điều kiện dừng (dừng ngay, không thử lại)

- Chạm trần chung (lượt bị chặn `server_ceiling`), hay vượt tổng dự kiến của một kịch bản quá 50%.
- Một lượt gọi công cụ, đọc ghi file, hay gửi ra kênh ngoài (Zalo, Telegram) trong nhóm: lỗi an toàn.
- Vòng gọi lặp (cùng cặp trợ lý gọi nhau quá 2 tầng), hay một lý do chạy hai lượt.
- Lỗi đăng nhập hay hết hạn mức của nhà cung cấp: dừng, ghi là lỗi kỹ thuật, không đổi provider.
- Bất kỳ dấu hiệu dữ liệu của state thật bị đụng.

## 6. Bằng chứng cần giữ (không sửa sau khi chạy)

- SHA, lệnh, biến môi trường (che khoá), câu duyệt của chủ, giờ bắt đầu và kết thúc.
- Bản sao state sau pilot (`team.sqlite3`, `conversations.db`, `resonance.sqlite3`, `agent_judge.sqlite3`, `kanban.sqlite3`)
  bằng SQLite backup API, kèm `agent_calls` xuất CSV (mục đích, trạng thái, obligation, mốc engine).
- Ảnh chụp trang Nhóm (desktop, màn hẹp, hai ngôn ngữ), khung nhịp và lịch sử phán xử của từng trợ lý.
- Log server sandbox.
- Kết luận tách năm loại: kỹ thuật đạt, nội dung chờ chủ duyệt, nghiệp vụ chưa hoàn tất, dừng ở cổng, lỗi kỹ thuật. Báo cáo
  gốc giữ nguyên; hậu kiểm viết file riêng, không sửa bằng chứng gốc.

## 7. Quay về sau pilot

State pilot là thư mục tạm riêng: xoá sandbox, không cần công cụ khôi phục. Nếu pilot chạy trên một state có sẵn (chỉ khi chủ
yêu cầu), dùng chuỗi khôi phục ở [team-chat-t4-ops.md](team-chat-t4-ops.md) mục 4 trên bản sao lấy trước pilot.
