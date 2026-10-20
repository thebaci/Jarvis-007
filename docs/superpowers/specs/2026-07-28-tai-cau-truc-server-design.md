# Tái cấu trúc server Jarvis 007

Ngày: 2026-07-28
Trạng thái: giai đoạn 0 XONG (0.9.235 + 0.9.236). Giai đoạn 1-4 chờ kế hoạch thực thi.
Phiên bản gốc: 0.9.234

Tiến độ:
- [x] Giai đoạn 0 - lưới an toàn. Kèm phát hiện ngoài dự kiến: CI đã đỏ liên tục từ 0.9.231,
      nên đã vá luôn hai lỗi chặn (guide connector vượt trần ký tự, và `test_graph_watch.py`
      segfault lúc thoát do luồng Rust của watchfiles). CI xanh toàn bộ từ 0.9.236.
- [x] Giai đoạn 1 - gỡ chặn event loop (0.9.237 đến 0.9.240). Kết quả đo trên brain
      623 md / 30 skill: `build_system_prompt` **150,8 -> 37,2ms**, `import main`
      **2.263 -> ~1.400ms**, `GET /brains` 136,1ms -> chạy trong thread (48-77ms CPU,
      độ trễ event loop đo được 18ms). Hai chỗ spec đoán sai đã sửa lại theo số đo,
      ghi rõ ở mục 5.
- [x] Giai đoạn 2 - dọn dữ liệu runtime khỏi source (0.9.241), nhưng **THU HẸP so với kế hoạch**.
      Mục 2.1 gốc SAI và đã bỏ: `server/brains-backup/` là bản sao làm việc git của tính năng
      sao lưu brain lên GitHub (`main.py:1474`) và đang có thay đổi chưa commit;
      `server/.staging/` chứa file người dùng upload thật; `server/tmp/` đang được
      `claude_sdk_engine.py:254` dùng. Cả ba là nội dung `JAVIS_STATE_DIR`, mà `STATE_DIR`
      mặc định chính là `server/`, nên "dời ra ngoài" thực chất là đổi `STATE_DIR` - đúng
      điều mục 3 cấm. Muốn `server/` gọn thì đó là quyết định cấu hình của từng máy, không
      phải thay đổi code.
      Giá trị thật thu được nằm ở chỗ khác và lớn hơn dự kiến: `.dockerignore` để lọt
      `.secret_key`, `.hub_token`, `.oauth_mcp.json`, `usage_index.db` vào image, và
      context build từ **1.239 MB xuống 6 MB**.
- [x] Giai đoạn 3 - tách test (0.9.242). `server/` từ 126 file `.py` xuống **50 file nguồn**.
      Làm KHÁC kế hoạch theo hướng tốt hơn: spec định giữ `cwd=server` trong CI, nhưng đã bỏ
      hẳn ràng buộc đó - 97 chỗ phụ thuộc vị trí quy về `tests/python/_paths.py`, test chạy
      được từ bất kỳ thư mục nào. Kèm 2 việc ngoài kế hoạch: 7 test JS chưa từng chạy lần nào
      giờ đã chạy (CI liệt tay 4 file, bỏ sót 7), và test JS thôi bị phục vụ công khai qua
      `/static/test_*.js`.
- [~] Giai đoạn 4 - chẻ main.py. **Phạm vi đã thu nhỏ có chủ đích** sau khi đo lại: mục tiêu
      "dưới 800 dòng" bị BỎ. Lý do: lập luận "file to làm agent sửa mù" hoá ra yếu - suốt phiên
      làm giai đoạn 1-3 đã sửa `main.py` khoảng 15 lần theo lối grep rồi sửa đúng vùng, không
      lần nào kích thước file gây lỗi. Lợi ích là TUYẾN TÍNH (dễ đọc, dễ định vị) chứ không
      phải dạng ngưỡng, nên làm một phần được một phần.
      Đã làm (0.9.243): `routes/graph.py`, `routes/domain.py`, và sửa 8 chỗ gọi route handler
      như hàm thường. `main.py` 6.491 -> 6.159.
      CHƯA làm: bóc khối cập nhật (vướng: `test_update.py` vá đè `main._deploy_mode`, hàm đó
      phải ở lại main và được gọi trễ), bóc khối Telegram, và gộp phần trùng lặp giữa
      `_do_turn` với `_tg_answer`.

## Phụ lục: 10 chỗ đã trôi lệch giữa hai bản dispatch engine (đo 2026-07-29)

`_do_turn` (dashboard, trong `@app.websocket("/ws")`) và `_tg_answer` (Telegram) là hai bản
chép của cùng một luồng 4 nhánh engine. Chúng đã trôi lệch thật, không phải nguy cơ lý thuyết.
Ghi lại đây để lần sau sửa có danh sách, khỏi phân tích lại.

Thiếu ở TELEGRAM:
1. ~~Không ghi `usage_store` cho nhánh Claude-CLI và nhánh API~~ - bảng Mức dùng báo thiếu mọi
   cuộc trò chuyện Telegram không đi qua Codex. **XONG 0.9.244.**
2. ~~Không `store.append_message` / `auto_title` / `log_conversation` / `learn_feature.enqueue`~~.
   Hội thoại Telegram vắng mặt ở `/sessions`, ở `brain/Memory/conversations`, và ở vòng tự học.
   Đây là lỗ hổng chức năng lớn nhất trong danh sách. **XONG 0.9.244.**
3. ~~Không có phần phục hồi khi Codex resume thất bại~~ - mất sạch ngữ cảnh, không dựng lại.
   **XONG 0.9.245.**
4. ~~`_codex_safe_model` ép model hợp lệ nhưng KHÔNG ghi lại~~, và không báo user là model đã
   đổi. **XONG 0.9.245.**
5. ~~Sự kiện `error` đầu tiên huỷ cả lượt~~, kể cả khi luồng còn hồi phục được. Dashboard coi lỗi
   là không chí mạng. **XONG 0.9.245.**
6. ~~`compact_mem` chạy trong đường request~~ - phiên dài phải chờ một vòng tóm tắt trước khi thấy
   câu trả lời. **XONG 0.9.245.**
9. ~~Nhánh Codex truyền `written=[]` cho `collect_turn_files`~~ trong khi nhánh Claude có thu thập
   đường dẫn Write/NotebookEdit. File Codex ghi ra chỉ được tự đính kèm nếu đường dẫn tuyệt đối
   tình cờ xuất hiện trong câu trả lời. **XONG 0.9.245.**
10. ~~Không có bản tương ứng của `store.clear_codex_thread_id`~~, mà `sess["codex"]` chỉ bị xoá bởi
    `/reset` và `/brain` - đổi provider sang Claude rồi quay lại là resume một luồng Codex chưa
    hề thấy các lượt ở giữa. **XONG 0.9.245.**

Thiếu ở DASHBOARD:
7. ~~Không `strip_control_blocks` trước khi `store.append_message`/`log_conversation`~~, nên khối
   `<!-- JAVIS_ASK ... -->` thô lọt vào kho phiên và vào nhật ký hội thoại - tức lọt vào chính
   corpus dùng để tự học. **XONG 0.9.244.**
8. ~~Khung `response` của nhánh Claude nằm TRONG handler `final`~~, không có `final` thì không có
   `response`. **XONG 0.9.245.**

Về cách chữa: đề xuất dựng tầng trừu tượng chung (`TurnSink` / `ChatHistory` / túi phụ thuộc)
là ĐÚNG về thiết kế nhưng đây là đoạn code rủi ro nhất trong app. Khuyến nghị: sửa thẳng từng
lỗi trên trước (mỗi cái một commit, có test), rồi mới cân nhắc gộp - chứ không gộp trước rồi
mới sửa.

### Đã chữa ở 0.9.244 (lỗi 1, 2, 7)

Chữa theo đúng khuyến nghị trên: KHÔNG gộp cả luồng dispatch, chỉ rút đúng MỘT mảnh chung là
**đường lưu một lượt** - `_persist_turn(store, conv_sid, brain, user_message, final_text)`. Nó
bóc khối điều khiển rồi mới `append_message` + `auto_title` + `log_conversation` +
`learn_feature.enqueue`. Cả `_do_turn` lẫn Telegram gọi chung nó, nên lỗi 7 hết cho cả hai
kênh cùng lúc thay vì chỉ vá dashboard.

Phía Telegram tách vỏ khỏi lõi: `_tg_answer` (vỏ - mở/khớp phiên trong kho, lưu lượt user, gọi
lõi, lưu lượt assistant) và `_tg_answer_engine` (lõi 4 nhánh, giữ nguyên văn). Vỏ quyết định
nhãn engine rồi TRUYỀN XUỐNG lõi chứ không để hai bên tự suy ra - nếu không thì có ngày phiên
bị dán nhãn `cli` trong khi lượt thật chạy qua OpenRouter. Quy ước trả về: **dict = câu trả lời
thật (đáng lưu), chuỗi = thông báo lỗi (không lưu)**; vì thế nhánh gateway lịch đổi sang trả
dict. `sess["sid"]` sống theo RAM giống `sess["cli"]/["or"]/["codex"]` và bị xoá ở `/reset` +
`/brain`.

Lỗi 1 chỉ là hai dòng `usage_store.record` đặt đúng chỗ: nhánh CLI ghi ở sự kiện `final` (kèm
`cost_usd`), nhánh API ghi ở sự kiện `usage` và bám model THẬT từ sự kiện `meta`.

Một thay đổi kèm theo, có chủ ý: `learn_feature.enqueue` từ `asyncio.create_task` đổi thành
`await` thẳng. `enqueue` chỉ đọc config + cộng bộ đếm dưới khoá (mẻ học thật chạy ở `tick`), rẻ
hơn chính lần ghi file log ngay trên nó - nên task mồ côi không ai chờ, nuốt lỗi im, không đáng.

### Đã chữa ở 0.9.245 (bảy lỗi còn lại: 3, 4, 5, 6, 8, 9, 10)

Danh sách đóng. Vẫn KHÔNG gộp luồng dispatch - mỗi lỗi sửa tại chỗ, chỉ rút thêm hai mảnh
chung nhỏ (`_tg_ket` gói câu trả lời, `_tg_compact_bg` đẩy nén sang nền).

Ba lỗi ăn nhau một cụm, và chỉ chữa được vì 0.9.244 đã cho Telegram một kho phiên. **Lỗi 10**
xoá liên kết thread Codex khi provider khác chen vào một lượt, đúng bản tương ứng của
`store.clear_codex_thread_id`. Mất thread thì phải có chỗ dựng lại ngữ cảnh - đó là **lỗi 3**:
`_nuot_codex` trả về cờ resume-hỏng, hỏng thật thì xoá `session_id`, dựng prompt bootstrap từ
transcript trong kho rồi chạy lại đúng một lần. Cùng đường đó phục vụ cả trường hợp phiên chưa
có thread.

**Lỗi 5** đổi hợp đồng lỗi ở cả ba nhánh: sự kiện `error` gom vào danh sách thay vì `return`
ngay. Có chữ thì trả chữ kèm một dòng báo lỗi ở cuối; không có chữ nào thì mới trả lỗi như cũ.
Nhánh Claude còn tích luỹ phần đã stream để luồng đứt trước `final` vẫn còn cái mà trả.

**Lỗi 8** là cùng lớp lỗi đó bên dashboard: khung `response` chuyển ra NGOÀI vòng lặp sự kiện,
dùng phần đã stream làm phương án dự phòng. Trước đây không có `final` là client không nhận
`response` nào cả và bong bóng chat treo mãi, dù chữ đã hiện ra rồi.

**Lỗi 6** đẩy `compact_mem` sang task nền, và chỉ ÁP kết quả khi lịch sử chưa đổi kể từ lúc bắt
đầu nén - có lượt chen vào giữa mà cứ đè là nuốt mất lượt vừa nói.

**Lỗi 9** không chữa bằng cách đoán khuôn JSON của Codex (đường dẫn nằm rải trong
`changes[].path`, trong `arguments`, hay lẫn trong `command`, và khuôn còn đổi theo bản CLI).
`CodexCLI` đẩy nguyên payload thô lên, `channel_context.candidate_paths_from_tool` đi hết
payload và thu RỘNG mọi thứ trông giống đường dẫn. Thu rộng an toàn vì `collect_turn_files`
phía sau vốn chỉ giữ tệp CÓ THẬT và VỪA ĐỔI trong lượt - ứng viên thừa lặng lẽ rơi. Item lạ
(vd bản vá file) cũng được đẩy lên dưới dạng sự kiện `item`, không in ra để khỏi ồn.

**`_codex_safe_model`** (lỗi 4) ghi lại model đã ép vào Settings và nói cho user biết. Trên
Telegram lời báo phải nằm trong CÂU TRẢ LỜI chứ không phải progress - progress bị thay bằng
câu trả lời nên user không bao giờ đọc được.

Về kiểm thử: sáu lỗi Telegram test bằng cách gọi thẳng `_tg_answer` thật với engine giả. Lỗi 8
nằm trong hàm lồng bên trong `@app.websocket("/ws")` nên không gọi thẳng được - test bằng AST,
khẳng định đúng hai điều tạo nên lỗi (khung `response` không nằm trong vòng lặp, và vòng lặp có
tích luỹ text đã stream).

Kèm một chỗ THỨ 9 gọi route handler như hàm thường mà lưới 0.9.243 bỏ sót:
`bench_hotpath.py:103` gọi `asyncio.run(main.list_brains())`. Lưới cũ chỉ soi `main.py` +
`routes/` và chỉ bắt lời gọi trần, nên vừa không thấy file này vừa không thấy dạng
`module.handler()`. Nay `test_handler_khong_goi_truc_tiep` quét toàn bộ `server/` và bắt cả hai
dạng, có phân biệt theo module để `skill_router.list_skills()` (hàm thường trùng tên) không bị
báo động giả.

## 1. Vì sao làm, và ba giả định đã bị bác bỏ

Xuất phát điểm là nhận định "main.py quá nặng, cấu trúc thư mục không clean bằng hermes-agent,
sợ ảnh hưởng hiệu năng về sau". Đã đo bằng số trước khi thiết kế. Ba giả định trong đó sai,
và spec này được xây trên phần còn đúng.

**Bác bỏ 1: hermes-agent không gọn hơn.** Bản clone tại `.learn/hermes` là repo thật
(remote NousResearch/hermes-agent, HEAD 972b1620). `gateway/run.py` 18.911 dòng, `cli.py` 15.695,
`hermes_cli/web_server.py` 14.142, `hermes_cli/config.py` 7.731. Có 12 file source của hermes lớn
hơn `server/main.py` (6.442). Trung bình 712 dòng/file so với 558 của Jarvis 007. Về đăng ký route hermes
còn kém hơn: 200 route treo `@app.*` trong một file 14k dòng, `APIRouter` chỉ dùng ở 4 chỗ phụ,
trong khi Jarvis 007 đã có 5 module feature dùng `APIRouter` + `register(app, Deps)`.
Kết luận: không lấy hermes làm khuôn mẫu cấu trúc. Bốn thứ duy nhất đáng học là `pyproject.toml`,
`tools/registry.py` (tự đăng ký + discovery lazy bằng AST), `PluginContext` 18 điểm mở rộng có kiểu,
và `tests/` soi gương cây source.

**Bác bỏ 2: độ dài file không tốn thời gian chạy.** Compile 6.442 dòng tốn 155ms đúng một lần,
sau đó nạp `__pycache__/main.cpython-312.pyc` hết 1,7ms. Chi phí duy nhất liên quan kích thước là
Starlette quét tuyến tính `app.routes`: 0,13ms route đầu, 0,64ms route cuối, 0,52ms cho một 404 quét
hết 192 route. Con số đó phụ thuộc SỐ ROUTE chứ không phải số dòng, và `include_router` gộp router con
trở lại `app.routes` nên chẻ file để lại bảng route y hệt.
Kết luận: giai đoạn 4 của spec này là để người và agent đọc/sửa được, TUYỆT ĐỐI không quảng cáo là fix hiệu năng.

**Bác bỏ 3: cấu trúc thư mục không phải nguyên nhân treo app.** Nguyên nhân là chặn event loop trên
một tiến trình uvicorn duy nhất không `--workers` (`Dockerfile:96`, `main.py:6441`), làm healthcheck
4 giây trượt, Traefik gỡ route, ra 404.

**Phần đúng và là lý do thật để làm:**

- `main.py` 6.442 dòng / 311 KB, xấp xỉ 80.000 token. Bị sửa trong 50 trên 200 commit gần nhất,
  tức một phần tư số commit của dự án. Agent hoặc đốt 80k token để nhìn một file, hoặc grep rồi sửa mù.
- `build_system_prompt()` (`main.py:261`) chặn event loop 95-110ms mỗi lượt chat, gọi từ 6 chỗ.
- `server/` nặng 1,5 GB, trong đó `brains-backup/` 1,4 GB và `.staging/` 114 MB nằm ngay trong thư mục source.
- 67 file test trộn lẫn 55 module source trong cùng một thư mục phẳng, không có cấu hình pytest nào.

## 2. Mục tiêu

1. Bỏ các cú chặn event loop rẻ tiền nhất, đưa mỗi lượt chat từ ~100ms xuống ~30ms và `/brains`
   từ 110ms về gần 0.
2. Đưa `main.py` xuống mức một agent ôm trọn được trong context (mục tiêu 400-600 dòng, trần cứng 800).
3. Tách dữ liệu runtime ra khỏi thư mục source, tách test ra khỏi source.
4. Không thay đổi một hành vi nào quan sát được từ bên ngoài. Bảng 182 endpoint phải diff ra rỗng.

## 3. Không phải mục tiêu

- **Không** đổi sang package `pyproject.toml` / `src/javis/`. Lý do là bẫy ở mục 8.1.
- **Không** cache system prompt theo chữ ký file trong đợt này. Nếu sót một đầu vào thì prompt cũ
  được dùng âm thầm, model hành xử sai mà không có lỗi nào báo. Chờ đo lại sau giai đoạn 1.
- **Không** đụng 3 vòng import đang được phá bằng import trong hàm (`config`↔`secrets_store`,
  `oauth_mcp`↔`mcp_store`, `claude_cli`↔`claude_sdk_engine`).
- **Không** đổi mặc định `JAVIS_STATE_DIR`. Nó đang trỏ `server/`, nơi mọi bản cài hiện có giữ
  `settings.json`, `.secret_key`, `.hub_token`, `kanban.sqlite3`, `conversations.db`. Đổi mặc định
  là người dùng bật lên thấy mất tài khoản và toàn bộ connector.
- **Không** gộp đoạn dispatch engine 4 nhánh bị viết hai lần ở `_do_turn` (5459-5599) và
  `_tg_answer` (5838-5966). Việc riêng, làm sau.
- **Không** viết lại 60 file test dạng script thành pytest thật trong đợt này. Chỉ di chuyển.

## 4. Giai đoạn 0: lưới an toàn (khoảng 1 giờ, làm trước mọi thứ)

Không có bước này thì mọi bước sau là hy vọng chứ không phải chứng minh.

1. `tests/test_route_table.py`: dump `[(route.path, sorted(route.methods or []), route.name) for route in app.routes]`
   ra `tests/fixtures/route_table.json`, commit file đó, và so khớp trong test. 182 endpoint.
   Đây là dây bảo hiểm cho toàn bộ giai đoạn 4.
2. Thêm `python -c "import main"` vào `.github/workflows/ci.yml`. Hiện CI chỉ byte-compile
   (`ci.yml:22-23`), nên một vòng import bị gãy vẫn qua CI, vẫn push, vẫn tự deploy, rồi mới chết lúc chạy.
3. `server/bench_hotpath.py`: đo và in `build_system_prompt`, `skill_router.list_skills`,
   `plugins_host.describe`, `usage_index.summary`, `GET /brains`. Chạy trước và sau giai đoạn 1.

Nghiệm thu: CI đỏ nếu cố tình đổi một path route.

### 4.1 Baseline đã đo (2026-07-28, VERSION 0.9.234)

Ảnh bảng route: **192 mục** (185 APIRoute, 2 WebSocket, 4 route mặc định FastAPI, 1 Mount StaticFiles),
tức 187 endpoint của app. Con số 182 nêu trong bản nghiên cứu là ước lượng cộng tay và thấp hơn thực tế;
từ nay lấy `server/route_table.json` làm nguồn sự thật.

Guard đã được kiểm chứng là bắt được lỗi: cố tình xoá `/brains`, dịch thứ tự `/health`, đổi tên
`/version` thì test in ra đủ ba loại sai và trả exit 1.

Số đo trên brain lớn `brains/My Bullet Journal` (623 file .md, 30 skill), máy Windows, cache nóng:

- `build_system_prompt()` **150,8ms** (trung vị 5 lần). Bóc ra: `list_skills` 53,4ms,
  `plugins_host.describe` 34,7ms, `_gather_capabilities` 76,9ms, `_javis_capability_summary` 69,8ms,
  `_skill_router_block` 26,9ms.
- `GET /brains` **136,1ms**.
- `usage_index.summary()` 46,7ms, `usage_index.insights()` 46,6ms.
- `import main` **2.263ms** (đã trừ 63ms khởi động interpreter trần).

Trên brain mặc định nhỏ (101 file .md, 7 skill) thì `build_system_prompt` chỉ 39,6ms. Chênh gần 4 lần,
nên **mọi ngưỡng nghiệm thu phải nói rõ đo trên brain nào**, nếu không là tự lừa mình.

Lưu ý baseline này cao hơn con số 95-110ms của bản nghiên cứu. Không đi tìm lý do chênh, chỉ lấy số
đo lại làm chuẩn vì cùng máy cùng script thì mới so trước-sau được.

## 5. Giai đoạn 1: gỡ chặn event loop (khoảng 1 ngày)

Toàn bộ là thay đổi không đổi hành vi, mỗi mục một commit revert độc lập được.

**1.1 `server/fastyaml.py`.** Hàm `safe_load` chọn `yaml.CSafeLoader`, fallback `yaml.SafeLoader`
khi thiếu libyaml, xuất cờ `HAS_C` để log lúc boot. Thay đủ 9 chỗ gọi `yaml.safe_load` ngoài test:
`main.py:2465` (trong `_read_md`), `main.py:3065` (trong `_scan_note_md`), `plugins_host.py:151`,
`self_improve.py:311`, `share_bundle.py:47`, `skill_router.py:117`, `system_sync.py:91`,
`system_sync.py:271`, `system_sync.py:279`. Nóng nhất là `skill_router.py:117` và `plugins_host.py:151`.
Đo được: 0,446ms xuống 0,072ms trên một frontmatter SKILL.md 130 byte, nhanh 6,2 lần. YAML chiếm
64% chi phí `build_system_prompt`. Kèm một test đối chiếu hai loader cho ra cùng kết quả trên
toàn bộ frontmatter trong repo.

**1.2 Xoá cú quét skill chạy trùng.** `_gather_capabilities` gọi `skill_router.list_skills(root)`
(`main.py:4061`), rồi `_skill_router_block` gọi `skill_router.list_enabled_meta(root)`
(`main.py:4222`), mà `list_enabled_meta` chỉ là `[s for s in list_skills(root) if s.get("enabled")]`
(`skill_router.py:186`). Cả cây skill bị đi và parse YAML hai lần mỗi lượt, 46,3ms mỗi lần.
Sửa: gọi `list_skills` một lần rồi truyền kết quả xuống cả hai chỗ.

**1.3 Cache `plugins_host.describe()`.** Đọc và parse lại mọi `plugin.yaml` không cache,
21,9ms mỗi lần, gọi từ `_gather_capabilities` nên chạy mỗi lượt chat, mỗi task Kanban,
mỗi lần nhắc hẹn nổ, mỗi tick loop. Gắn cache theo `(mtime_ns, size)` của các `plugin.yaml`,
đúng khuôn mẫu đã có sẵn ở `config.py:136-169`.

**1.4 Offload các truy vấn usage.** `main.py:3435/3449/3462` đã bọc `usage_index.refresh` bằng
`asyncio.to_thread` đúng cách, nhưng ngay dòng sau lại gọi thẳng `usage_index.summary()`
(`main.py:3437`, đo được 68ms) và `usage_index.insights()` (`main.py:3451`) trên loop. Bọc nốt.

**Hai chỗ spec này đoán sai, đã sửa theo số đo thật (ghi lại để lần sau đừng lặp):**

- Mục 1.5 dưới đây cho rằng DDL lặp lúc `_connect` là chi phí đáng kể. Đo ra `_connect`
  chỉ tốn 1,14ms trong 65ms của `summary()`, tức chưa tới 1,5%. Thủ phạm thật là
  `usage_parsers.estimate_cost` quét tuyến tính cả bảng giá cho MỖI dòng: 321.009 lần
  `startswith` cho 3 vòng, trong khi chỉ có 11 model phân biệt và 6 khoá giá. Đã nhớ đệm.
  Nhưng nói thẳng mức lợi: chỉ 9% tổng, vì hàm vẫn bị gọi đủ 53.496 lần do `_group` chạy
  lại trên cùng bộ dòng cho 15 chiều. Sửa triệt để là đổi cấu trúc `_group` - CHƯA làm,
  vì đây là endpoint dashboard và mục 1.4 đã gỡ phần nguy hiểm là chặn loop.
  Thứ THẬT SỰ cần ở 1.5 là WAL, và không phải để nhanh mà để ĐÚNG: sau 1.4 thì
  summary/insights đọc song song với `refresh()` đang ghi.
- Mục 1.7 đặt đích `/brains` dưới 15ms dựa trên việc dùng `_MDINDEX_CACHE`. Thực tế dùng
  `_count_md` (scandir có trần) cho 48-77ms CPU. Không đạt con số đó, nhưng tính chất quan
  trọng thì đạt: nó chạy trong thread, độ trễ event loop đo được 18ms khi quét brain 3000
  note. Đích 15ms là sai chỗ - cái cần chặn là thời gian KHOÁ LOOP, không phải thời gian hàm.

**1.5 Vệ sinh sqlite của usage_index.** `usage_index._connect()` (`usage_index.py:60-69`) mở
connection mới mỗi lần gọi và chạy lại 2 `CREATE TABLE IF NOT EXISTS` + 2 `CREATE INDEX IF NOT EXISTS`
mỗi lần connect, không `journal_mode=WAL`, không `busy_timeout`. Đây là kho sqlite duy nhất trong
codebase làm sai cả ba, trong khi `sessions.py:100-118` và `task_store.py:61-65` đều làm đúng.
Sửa theo đúng khuôn hai file kia.

**1.6 Import lười `edge_tts`.** `main.py:22` import ở mức module không điều kiện, dù TTS là tính năng
tuỳ chọn. Nó chiếm 944ms trong tổng 2.280ms import `main`, và kéo theo cả chuỗi `aiohttp` 212ms.
Chuyển vào trong hàm TTS.

**1.7 `GET /brains` thôi rglob.** `main.py:2360` gọi `p.rglob("*.md")` trên từng brain chỉ để đếm
ghi chú, không offload, không cache, đo được 108-115ms mỗi request, dashboard gọi lúc boot từ hai chỗ
(`dashboard/brains-ui.js:75`, `dashboard/console.js:1191`). Đúng lỗi này đã được chẩn và ghi comment
tiếng Việt cho `/viec/all` ở `main.py:3946`, nhưng `/brains` để nguyên.
Sửa: lấy số đếm từ `_MDINDEX_CACHE` đã prewarm, rơi về `_count_md` (`main.py:4404`, đã là scandir
early-exit có trần) khi chưa có cache. Chấp nhận số đếm gần đúng, đúng như đã chấp nhận cho `/viec/all`.

**1.8 Batch `_snapshot()` của Kanban.** `tasks.py:114` gọi `list_tasks(limit=5000)` rồi lặp từng task
gọi `list_events(task_id, 20)`, tức N+1 truy vấn, rồi serialize và ghi lại file JSON, không offload,
gọi từ `_claim_and_spawn` (`tasks.py:313`) và `_worker_done` (`tasks.py:324`). Hiện miễn phí vì bảng
rỗng, nhưng tăng tuyến tính tới trần 5000. Gộp thành một truy vấn events theo lô, và offload.

Nghiệm thu (đo bằng `bench_hotpath.py` trên brain `My Bullet Journal`, so với baseline mục 4.1):

- `build_system_prompt` từ 150,8ms xuống **dưới 60ms**. Tính tay: bỏ cú quét trùng bớt ~53ms,
  cache `describe` bớt ~35ms, còn lại phần lớn là `list_skills` mà YAML chiếm 64% nên `CSafeLoader`
  đưa 53ms xuống ~24ms. Cộng lại khoảng 34ms, nên 60ms là ngưỡng thoải mái còn 40ms là mục tiêu phấn đấu.
- `GET /brains` từ 136,1ms xuống **dưới 15ms**.
- `import main` từ 2.263ms xuống **dưới 1.400ms** (bỏ `edge_tts` là bớt 944ms).
- `usage_index.summary/insights` không cần nhanh hơn, chỉ cần không còn nằm trên event loop.

Toàn bộ test cũ vẫn xanh, và `test_route_table.py` vẫn khớp 192 mục.

## 6. Giai đoạn 2: dọn dữ liệu runtime khỏi source (1-2 giờ)

**2.1 Dời hai thư mục nặng ra ngoài repo:** `server/brains-backup/` (1,4 GB) và `server/.staging/`
(114 MB). Cả hai đã gitignore nhưng nằm vật lý trong cây source nên mọi `find`, `grep`, index IDE,
và docker context đều phải đi qua. Xoá luôn hai thư mục rỗng vô nghĩa `server/utf-8/` (0 byte, sinh
do một lệnh redirect hỏng) và `server/tmp/`.

**2.2 Vá `.gitignore` cho 6 artifact đang vừa không track vừa không ignore:** `server/_selfupdate.bat`
(hardcode `D:\Project\Javis-OS`), `server/brain-trash/`, `server/kanban.sqlite3`, `server/logs/`,
`server/tg_brain.json`, `server/update_state.json`. Một cú `git add -A` là commit hết.
Đã xác minh hiện không có gì nhạy cảm bị TRACK.

**2.3 Đồng bộ `.dockerignore` với `.gitignore`.** `Dockerfile:64` là `COPY . .` nên `.dockerignore`
là hàng rào duy nhất, mà nó là bản sao cũ và yếu hơn nhiều. Nó KHÔNG loại: `server/.secret_key`,
`server/.hub_token`, `server/.oauth_mcp.json`, `server/.mcp_hub_*.json`, `server/plugins/`,
`server/connector-home/`, `server/usage_index.db`, `server/session_brain.db`, `server/kanban.sqlite3`,
`server/brain-trash/`, `server/brains-backup/`, `server/logs/`, `.gitnexus/` (106 MB), `.superpowers/`,
`.pytest_cache/`, `videos/` (754 MB), `cap.txt`, `scratch_url.txt`.
Build trên GHCR chạy từ checkout sạch nên không dính, nhưng bất kỳ ai `docker build` cục bộ đều nướng
`.secret_key` và `.hub_token` của mình vào image.

**2.4 Dọn rác gốc repo:** xoá thư mục `memory/` rỗng, xoá hai file không đuôi `agents` và `workflows`
ở gốc (nội dung là mảnh log `  - Move: Jarvis\agents  -`), rồi gỡ hai dòng `/agents` `/workflows`
ở `.gitignore:83-84` vì chúng đang vĩnh viễn chặn việc tạo thư mục `agents/` `workflows/` thật ở gốc.

Nghiệm thu: `du -sh server/` dưới 50 MB. `git status --porcelain -uall server/` sạch.
`docker build` cục bộ không còn nuốt secret.

## 7. Giai đoạn 3: tách test (2-3 giờ)

Chuyển 67 file `server/test_*.py` (11.340 dòng) sang `tests/python/`, thêm `conftest.py`.
Giữ nguyên runner vòng lặp hiện tại ở `ci.yml:34-42`, vì 55 file gọi `sys.exit()` và 52 gọi ngay ở
mức module, 11 file gọi `asyncio.run()` ở mức module, và chỉ 1 file có `if __name__ == "__main__"`.
Dưới pytest, bước collect import từng module là chạy luôn assert rồi `sys.exit(1)`, huỷ cả lượt chạy.
Chuyển dần sang pytest thật là việc nền, không nằm trên đường găng của spec này.

Điểm gãy phải xử lý: 56 file dựa vào idiom `sys.path` theo thư mục script, 12 file dựa thuần vào cwd,
và 2 file mở thẳng file source bằng đường dẫn tương đối (`test_zalo_listener.py:222-878`,
`test_zalo_rules.py:146`). Giữ `cwd=server` trong CI và trỏ glob sang `../tests/python/`.

Kèm theo: 7 trong 11 test JS của dashboard chưa từng chạy trong CI (`test_brains_ui.mjs`,
`test_dataview`, `test_task_suggest`, `test_zalo_panel`, `test_chat_acts`, `test_graph_timelapse`,
`test_graph_tooltip_cleanup`). Thêm vào `ci.yml:28-33`. Và các file test JS đang nằm dưới mount
StaticFiles nên `/static/test_chat_render.js` đang được phục vụ công khai, cần chuyển ra ngoài `dashboard/`.

Nghiệm thu: CI xanh với đủ 67 test Python và 11 test JS, `server/` không còn file `test_*.py`.

## 8. Giai đoạn 4: chẻ main.py (3-4 ngày, mỗi module một commit)

### 8.1 Bẫy phải biết trước

`updater.py:143` hardcode `pip install -r requirements.txt` (không có `-e .`) và `updater.py:131`
hardcode `uvicorn main:app`. `javis.service` là template có `__APP_DIR__` được `install.sh` thay,
nên unit systemd đang chạy không nằm trong git và `git pull` không bao giờ cập nhật `ExecStart`.
Hệ quả: mọi thay đổi làm `main:app` không còn import được từ `server/` sẽ khiến lần tự cập nhật kế tiếp
trên VPS pull về code mà updater cũ không cài và không khởi động được, health trượt, rollback tự động,
và máy kẹt vĩnh viễn dưới commit đó.

**Ràng buộc cứng của giai đoạn 4: sau mỗi commit, `uvicorn main:app --app-dir server` phải chạy được y nguyên.**
Đây là lý do spec giữ `server/` phẳng, giữ import bằng tên trần, và không đổi `Dockerfile`,
`javis.service`, `start-javis.vbs`, `updater.py`.

### 8.2 Module nền, làm trước

- `server/paths.py` (~250 dòng, nâng nguyên văn): `atomic_write_text` (149), `brain_memory_dir` (179),
  `default_brain_dir` (1960), `brain_root` (1972), `brain_sub` (1979), `resolve_subfolder` (1991),
  `slugify`/`ascii_slug` (2439-2452), `read_md`/`write_md` (2456/2471), `today` (2477),
  `agents_dir`/`workflows_dir` (2479/2481), `skills_dir` (2531), `TEXT_EXTS` (2721),
  `files_ceiling` (2726), `files_root` (2754), `safe_path` (2759), `safe_serve_path`, `files_rel`.
  Không dính FastAPI. `_brain_root` có 60 chỗ gọi trải khắp mọi domain, đây là thứ khó gỡ nhất
  nên phải xong trước tiên.
- `server/prompt.py`: `build_system_prompt` (261-317) + khối capability (4034-4248). Đây cũng là nơi
  các sửa 1.2 và 1.3 của giai đoạn 1 đã hạ cánh, nên chuyển sau khi giai đoạn 1 xong.
- `server/logging_redact.py`: regex che secret + `_mask_secret`, `_redact_secrets`, `_clip_for_log`,
  `log_conversation` (319-408).
- `server/lifecycle.py`: 4 hook `@app.on_event` (`_prewarm_mdindex` 3199, `_start_scheduler` 4296-4397,
  `_warm_mcp_hub` 6402, `_shutdown_mcp_pool` 6416) cùng `_scheduler_loop` lồng bên trong.

### 8.3 Đợt lá (9 router, mỗi cái 45-90 phút)

Nhóm chỉ dùng helper của chính nó, gỡ ra không đụng ai:
`routes/graph.py` (1727-1937), `routes/backup.py` (1449-1552), `routes/usage.py` (3402-3464),
`routes/browse.py` (4400-4509), `routes/ops_update.py` (4512-5021), `routes/branding.py` (5024-5110),
`routes/domain.py` (5113-5282), `routes/tts.py` (5285-5382), `routes/sessions_api.py` (5674-5707).

### 8.4 Đợt lõi (phần làm nên giá trị thật)

`routes/auth.py` (468-575), `routes/settings_api.py` (1320-1446), `routes/upload.py` (1939-2095),
`routes/vault.py` (2097-2437, chứa `/vault/*` `/brain/migrate` `/brains*`),
`routes/studio.py` (2439-2712 + 3305-3345 + 3615-3658, chứa agents/skills/workflows/studio),
`routes/files.py` (2715-3009 + 3012-3196 + 3222-3302), `routes/connectors.py` (966-1317, 26 route),
`routes/models.py` (884-960 + 1555-1676, 14 route), `routes/chat_ws.py` (5385-5671),
`channels/telegram.py` (5710-6399), `routes/misc.py` (`/`, `/stop`, `/health`, `/memory/stats`,
`/reflect`, `/viec/all`, `/lint`, `/javis/index`, `/image/generate`, `/plugins`).

**Thứ tự bắt buộc:** `vault.py` và `files.py` phải đi SAU `lifecycle.py`, vì `_prewarm_mdindex` và
`_ensure_default_brain`/`_sync_system_all_brains` là hook khởi động chạm vào chúng.

**Chỗ khó nhất là Telegram.** `_tg_command` (6264/6271/6282), `_tg_callback` (6147) và
`_tg_skills_text` (5991) đang gọi thẳng các route handler (`list_agents`, `list_workflows`,
`list_brains`, `list_skills`, `provider_models`) như hàm Python thường. Khi tách, `channels/telegram.py`
phải import từ các router tương ứng. Đây là cạnh phụ thuộc thật nhưng không tạo vòng, miễn là không
router nào import ngược `telegram`. Nếu phát sinh vòng thì tách hàm dùng chung xuống `paths.py`
hoặc một module `services/` mới, KHÔNG dùng import trong hàm để giấu vòng.

### 8.5 Xoá code chết (đi kèm, khoảng 20 phút)

Đã xác minh lại bằng `grep -nw` trên toàn bộ file .py không phải test trong `server/`:
`SOURCES_PATH` (425), `_update_outcome` (37), `_trim_history` (719), `_LOOP_LOCK` (3781),
`_write_loop_config` (3788), `run_loop_cycle` (3792). Bốn cái cuối có thêm một hit nữa nhưng đều nằm
trong docstring hoặc comment (`compaction.py:4`, `self_improve.py:44`, `self_improve.py:550`),
không phải lời gọi. Xoá code thì sửa luôn mấy comment đó cho khỏi trỏ vào hư không.

Cộng ba nhánh không bao giờ chạy được: `_check_structure` nhánh `"exact"` (2136-2139) và
`"file_any"` (2140-2144), cùng `_ensure_brain_scaffold` nhánh `"file_any"` (2193-2194).
Lý do: đã đếm lại, cả 12 mục của `STANDARD_STRUCTURE` (2099-2119) đều là `"kind": "dir"`, và ba nhánh
đó tham chiếu key `it["path"]`/`it["files"]` mà không mục nào có, tức sẽ KeyError nếu chạm tới.
Kéo theo hằng `SCHEMA_SEED` (2170) chết, vì chỗ ghi nó duy nhất là dòng 2194 nằm trong nhánh chết.
Lưu ý nhánh `it["kind"] in ("dir", "exact")` ở 2191 thì KHÔNG chết, giữ nguyên.

### 8.6 Còn lại trong main.py

Tạo `app`, 3 middleware (`_csrf_guard` 94, `_auth_guard` 105, `_static_cache_headers` 128),
mount StaticFiles, danh sách allowlist đường dẫn của auth, bảng `include_router`, 5 lệnh
`register(app, Deps)` của các module feature (3672/3802/3824/3870/3893), và khối `__main__`.
Mục tiêu 400-600 dòng, trần cứng 800.

Lưu ý phân quyền: allowlist auth là so khớp chuỗi đường dẫn trong middleware gắn trên `app`
(76-91, 105-119), KHÔNG theo phạm vi router, nên việc chẻ file không thể đổi ai được vào đâu.
Bao gồm cả các mục `/reminders`, `/reminders/cancel`, `/hook/zalo` mà `main.py` đang giữ hộ module khác.

Nghiệm thu mỗi commit: `tests/test_route_table.py` xanh (diff bảng route rỗng),
`python -c "import main"` chạy được, 67 test cũ xanh, app khởi động và `GET /health` trả 200.

## 9. Rủi ro và cách chặn

**Sót import khi chuyển khối.** Bắt ngay bằng `python -c "import main"` trong CI, và mọi handler đã
chuyển vẫn phải chạy được ở request đầu tiên. Đây là lý do giai đoạn 0 đi trước.

**Đổi thứ tự đăng ký route.** `include_router` đặt đúng vị trí dòng cũ trong `main.py` tái tạo đúng
thứ tự đăng ký. Ảnh của bảng route chứng minh trên cả 182 endpoint.

**Xung đột merge.** PR của cloud agent hay merge trên GitHub trước local. Mỗi router một commit nhỏ,
và luôn `git fetch` trước khi bump version.

**Dời file trên VPS ở giai đoạn 2.** Dừng server trước khi dời, liệt kê thư mục đích trước khi khởi
động lại, giữ bản cũ trong `server/` một tuần trước khi xoá hẳn.

**Cache đếm ghi chú gần đúng ở 1.7.** Với brain mà prewarm chưa chạm tới, số đếm bị capped.
Đây là đánh đổi đã được chấp nhận trước đó cho `/viec/all`, ghi rõ trong comment.

## 10. Việc đã nhận diện nhưng để ngoài phạm vi

- `dashboard/console.js` 4.767 dòng, cùng tần suất sửa với `main.py` (50/200 commit), có sẵn đường cắt
  `renderPage()` ở `console.js:221`. Cùng công thức, làm sau khi server xong.
- 4 thư viện vẫn nạp từ CDN lúc chạy dù đã có chính sách self-host: `three@0.159.0` và
  `3d-force-graph@1.73.4` (`app.js:644-645`), `turndown` (`console.js:4495-4496`), `mermaid@10`
  (`chat-render.js:480`). Deploy offline là đồ thị 3D, round-trip markdown và mermaid chết im lặng.
- `?v=NN` viết tay trong `index.html` là code chết, vì `main.py:443` đã ghi đè mọi
  `/static/*.js|css?v=` bằng VERSION lúc phục vụ. Nên xoá để người sau khỏi tưởng còn tác dụng.
  Riêng `/brand-logo?v=5` ở `index.html:8-9` không khớp regex đó nên vẫn phải sửa tay.
- `GET /browse` và `/path/exists` cho liệt kê hệ thống file, và guard `_safe_path` bị chép lặp 12 chỗ.
  Cần rà riêng, quan trọng với người fork hơn là chuyện kích thước file.
- Chưa có logging có cấu trúc hay gom lỗi, nên mọi tái cấu trúc hiện chỉ nghiệm thu được bằng cảm giác
  ngoài phần test.
- `mcp_store._load()` (`mcp_store.py:57`) đọc và giải mã lại `mcp_servers.json` mỗi lần gọi, không cache,
  35 chỗ gọi. Đã được `mcp_hub` che ở đường tool call nên chỉ cắn các endpoint dashboard. Ưu tiên thấp.

## 11. Tiêu chí nghiệm thu tổng

1. `bench_hotpath.py` trên brain `My Bullet Journal`: `build_system_prompt` dưới 60ms
   (baseline 150,8ms), `GET /brains` dưới 15ms (baseline 136,1ms), import `main` dưới 1.400ms
   (baseline 2.263ms).
2. `server/main.py` dưới 800 dòng.
3. `du -sh server/` dưới 50 MB, `git status --porcelain -uall server/` sạch.
4. `test_route_table.py` xanh, tức 192 mục bảng route không đổi path, method, tên hay thứ tự.
5. 68 test Python và 11 test JS chạy trong CI, tất cả xanh.
6. `uvicorn main:app --app-dir server` vẫn là lệnh khởi động, `updater.py` không cần sửa.
