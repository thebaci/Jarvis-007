# Số đo T4 nhóm chat thích nghi (0.170.0) - máy local, engine GIẢ, KHÔNG phải VPS

Công cụ: `tools/team_adaptive_bench.py` (host thật `main.app` trong tiến trình qua httpx ASGITransport, engine giả có bộ đếm,
chốt chặn mọi lối dựng engine thật) và `tools/team_adaptive_ui_bench.js` (hàm vẽ thuần dưới node). Kết quả gốc:
`exports/reviews/team-adaptive/t4-bench-2026-10-15.json` (thư mục gói review, ngoài git). Hồi quy:
`tests/python/test_team_t4_perf.py` (kiểm bằng số đếm, ngưỡng thời gian rộng).

Không có số nào ở đây là số VPS. Kịch bản đo VPS chỉ đọc đã chuẩn bị ở `tools/team_adaptive_vps_measure.py`, **chưa chạy**.
Chưa đo VPS thì không kết luận đã hết lag.

## Máy và điều kiện

- Windows 11 Pro 10.0.26200, Intel64 Family 6 Model 165 (8 luồng), Python 3.12.10, node v24.15.0. Máy đang chạy các phiên
  làm việc khác (không cô lập), nên thời gian chỉ để so thứ bậc, không phải cam kết.
- Lệnh: `python tools/team_adaptive_bench.py --out exports/reviews/team-adaptive/t4-bench-2026-10-15.json` (mặc định).
- Dữ liệu: 12 nhóm x 1.500 tin = 18.000 tin, 8 trợ lý (4 bật Auto), mỗi nhóm 4 thành viên, 1.500 reaction của chủ seed
  thẳng vào kho (outbox còn chờ chiếu), 12 ngữ cảnh nhóm ngủ đông và 12 ngữ cảnh đến hạn, 8 phiên chat riêng.
- Engine giả: mỗi lượt 5 ms. Nhịp nền của scheduler dừng (`JAVIS_PULSE_TICK_PAUSED=1`), bench gọi tick trực tiếp. Không đặt
  `JAVIS_RESONANCE_CALL_CEILING`. Số câu SQL đếm bằng trace callback của sqlite3 trên mọi kết nối.

## API tuần tự (30 lần mỗi route, thời gian phía server)

| Route | p50 | p95 | câu SQL đọc / ghi (tối đa) |
|---|---|---|---|
| GET /teams/{id} (trang nhóm) | 54 ms | 64 ms | 25 / 0 |
| GET /teams/{id}/messages (trang tin) | 10 ms | 13 ms | 5 / 0 |
| POST reaction nhóm | 72 ms | 96 ms | 26 / 9 |
| POST reaction chat riêng | 52 ms | 76 ms | 25 / 8 |
| GET /agents/{slug}/pulse (khung nhịp) | 37 ms | 45 ms | 17 / 0 |

Số câu SQL của trang tin và trang nhóm **không đổi** giữa nhóm 60 tin và 600 tin (test hồi quy) và giữa 100 và 1.500 tin.

## Độ trễ event loop (bộ hẹn giờ 10 ms)

| Pha | Thời gian | p95 | lớn nhất |
|---|---|---|---|
| Chỉ request (8 luồng x 30 request hỗn hợp) | 6,2 s | 0 ms | 45 ms |
| Chỉ lô phán xử (24 tin không @ cùng lúc) | 1,1 s | 1,7 ms | 75 ms |
| Chỉ nhịp pulse (5 tick) | 7,1 s | 10,7 ms | 217 ms |
| Tất cả cùng lúc | 13,5 s | 3,2 ms | 245 ms |

Trong pha đồng thời, độ trễ request p50 338 ms, p95 1,29 s (240 request, cùng lúc với 24 lô phán xử và 5 tick).

Một tick nhịp: 3,4 s ở lần đầu (chiếu outbox còn lại), 0,5 tới 1,5 s các lần sau; 1,9 tới 3,0 s khi chạy cùng tải. Phần
nặng chạy ở luồng phụ (`asyncio.to_thread`).

## Lượt model giả

Pha đồng thời: 24 lượt nhóm, 24 lô phán xử (mỗi tin không @ đúng một lô), 0 lượt quét. Lượt quét bằng 0 là đúng thiết kế 5.5:
lần thức chạy code trước, không có cơ hội mới thì không gọi model. Không engine thật nào được dựng (`real_engine_guard`).

## Outbox phản hồi

1.500 reaction còn `pending` xả hết trong 8 lần chiếu (mỗi lần tối đa 200 dòng), 48 s, khoảng 32 ms mỗi reaction. Ở bản chạy
6 nhóm x 300 tin (cùng máy): 150 reaction ở "Chờ xem xét" sau khi xả, mỗi lần chiếu ổn định tốn khoảng 700 ms (khoảng 4,7 ms
mỗi reaction đang chờ, trần 200 dòng mỗi nhịp).

## Vẽ trên trình duyệt (giới hạn)

Playwright cho Python không có trong `.venv`, nên chưa đo trình duyệt thật (layout, paint, hai tab thật). Thay thế: thời gian
dựng chuỗi HTML bằng chính hàm vẽ của dashboard dưới node:

| Việc | p50 | p95 |
|---|---|---|
| Danh sách 12 nhóm | 0,4 ms | 7,7 ms |
| Khung 200 tin (94 KB HTML) | 2,8 ms | 5,3 ms |
| MÔ PHỎNG 20 gói reaction tới 2 tab, mỗi gói vẽ lại cả khung 200 tin (vòng lặp của bench làm lại việc của `onTeamEvent`, không gọi nó) | 92 ms | 101 ms |
| 500 chip + bộ chọn reaction | 25 ms | 36 ms |

## Trước và sau bản sửa hiệu năng của T3 (nhánh T3 `7e8b96f5`)

Cùng máy, cùng lệnh mặc định, cùng dữ liệu. "Trước" là head T4 `89a0acd1` (T3 chỉ có P và J, chưa sửa hiệu năng); "sau" là
head T4 sau khi ghép T3 `7e8b96f5` (P, J, L; lô phán xử và tick nhịp rời event loop qua `server/io_offload.py`, bộ chiếu theo
lô; số đo của T3 ở docs/dev/team-chat-t3-pulse.md mục 9). (Các nhánh T3 sau `7e8b96f5` tới `054975b3` chỉ sửa hành vi và giao diện, không đổi đường nóng đã đo.) Kết quả gốc của lần sau:
`exports/reviews/team-adaptive/t4-bench-2026-10-15-after-t3-fix.json`. Máy dùng chung với phiên khác nên lệch vài chục ms
giữa hai lần là nhiễu; chỉ đọc các thay đổi lớn.

| Số đo | Trước | Sau |
|---|---|---|
| Event loop lớn nhất, chỉ nhịp pulse | 217 ms | **39 ms** |
| Event loop lớn nhất, tất cả cùng lúc | 245 ms | **67 ms** |
| Event loop lớn nhất, chỉ lô phán xử | 75 ms | 73 ms |
| Event loop lớn nhất, chỉ request | 45 ms | 52 ms |
| Request p95 khi tất cả cùng lúc | 1,29 s | 0,93 s |
| Một tick nhịp (chỉ nhịp, lần 2 tới 5) | 0,46 tới 1,5 s | 0,26 tới 0,51 s |
| Một lần chiếu ổn định của bộ chiếu | 2,5 tới 3,6 ms (0 reaction chờ) | 16 tới 21 ms với **1.125** reaction "Chờ xem xét" (bản trước: khoảng 700 ms với 150) |
| Xả outbox 1.500 reaction | 48 s | 81 s (nhiều reaction vào "Chờ xem xét" hơn, vì phần L giờ phục vụ lý do) |
| GET trang nhóm p50 / câu SQL đọc | 54 ms / 25 | 49 ms / 25 |
| GET trang tin p50 / câu SQL đọc | 10 ms / 5 | 14 ms / 5 |
| POST reaction nhóm p50 / đọc, ghi | 72 ms / 26, 9 | 80 ms / 26, 9 |
| POST reaction chat riêng p50 | 52 ms | 43 ms |
| GET khung nhịp p50 / câu SQL đọc | 37 ms / 17 | 83 ms / **29** (thêm mục bài học của phần L) |
| Lượt model giả, pha đồng thời | 24 nhóm, 24 lô phán xử, 0 quét | 24 nhóm, 24 lô phán xử, 0 quét (cả bench: 6 lượt học giả của L) |
| Engine thật được dựng | 0 | 0 |

Kết luận: bản sửa của T3 gỡ được phần lớn độ trễ event loop ở pha nhịp và pha đồng thời, và chi phí đối soát của bộ chiếu
không còn tăng theo số reaction đang chờ. Khung nhịp chậm hơn vì có thêm mục bài học (29 câu SQL đọc, vẫn là hằng số). Lô
phán xử vẫn có lúc giữ loop khoảng 70 ms ở máy này. Chưa đo VPS.

## Nhận xét (lần đo trước bản sửa của T3)

1. **Lô phán xử giữ event loop:** chẩn đoán `--stall-watch` (chụp ngăn xếp luồng loop khi bị giữ quá 50 ms) chỉ ra
   `agent_judge.judge_team_message` gọi `agent_judge_store` (`get_decision`, `profile`, `get_offset`, `add_decision`),
   `resonance_store.agent_any` (qua `_agent_judge_resonance_on`) và `agent_ledger._tx` ngay trên luồng loop. Thuộc phần J;
   hướng sửa là đưa phần kho của lô sang luồng phụ. Lưu ý: bật `--stall-watch` làm chậm cả tiến trình (chụp ngăn xếp tranh
   GIL), chỉ dùng để chẩn đoán, không dùng số đo của lần chạy đó.
2. **Nhịp pulse:** ở pha chỉ nhịp, không ngăn xếp nào của code Jarvis 007 bị bắt trên luồng loop; độ trễ lớn nhất khoảng 0,2 s
   nhiều khả năng do luồng phụ của bộ chiếu (đối soát trạng thái từng reaction, mỗi dòng mở vài kết nối SQLite) tranh GIL.
   Phần L chưa ghép thì reaction "Chờ xem xét" không bao giờ được phục vụ, nên phần đối soát này lặp lại mỗi nhịp 30 giây
   (tối đa 200 dòng).
3. **Đồng thời làm request chậm:** p95 request 1,3 s khi có 8 luồng request cùng lô phán xử và nhịp, so với dưới 0,1 s khi
   tuần tự. Cần đo lại trên VPS (đĩa và CPU khác) trước khi kết luận.
4. **Mỗi gói reaction vẽ lại cả khung tin** của mỗi tab (O(số tin đang hiện)). Ổn ở 200 tin.
