# Hợp nhất Loop + Lịch thành một primitive "Việc định kỳ"

Ngày: 2026-07-17
Trạng thái: đã duyệt thiết kế, chờ kế hoạch triển khai

Câu hỏi khởi đầu của chủ dự án: "Loop và Lịch gần giống nhau, có nên gộp còn một? Loop 3 chế
độ nhưng thực tế ai chạy loop cũng muốn toàn quyền rồi. Người dùng thao tác trên chat chứ
không chủ động quản lý loop."

Điều tra bằng 12 agent đọc song song toàn bộ subsystem, cộng ba lens phản biện (skeptic /
migration / UX), cộng nghiên cứu `nousresearch/hermes-agent` và prior art (ChatGPT Tasks,
Claude Code CronCreate + /loop, Anthropic Routines). Mọi khẳng định dưới đây đã được verify
lại thủ công tại file:line.

## Phát hiện lật ngược câu hỏi

**Loop và Lịch không "gần giống nhau". Loop chạy thật, Lịch không chạy gì cả.**

`_read_automations` (`server/main.py:3149`) có đúng 6 chỗ gọi: `main.py:3198, 3211, 3242,
3259, 3299, 3352`. Tất cả đều là HTTP handler hoặc trình dựng index. Scheduler duy nhất của
hệ thống, `_scheduler_loop` (`server/main.py:3613-3656`), tick đúng 6 việc:

| # | Việc | Gọi tại | Có executor thật? |
|---|---|---|---|
| 1 | loop | `main.py:3620` → `self_improve.py:485` | Có |
| 2 | learn (debounce + curator) | `main.py:3625-3626` → `learn.py:306, 872` | Có |
| 3 | kanban | `main.py:3631` → `tasks.py:296` | Có |
| 4 | reminders | `main.py:3636` → `reminders.py:312` | Có |
| 5 | backup GitHub | `main.py:3641-3645` | Có |
| 6 | javis index | `main.py:3650-3651` | Có |
| - | **automations** | **không ở đâu cả** | **KHÔNG** |

Hệ quả cụ thể: tạo một dòng `type: cron, status: active` ở tab Lịch thì nó hiện badge xanh
"đang chạy" (`main.py:3201` đếm `status=='active'`) và **không bao giờ nổ**. Ô lịch là free
text (`dashboard/studio.js:367`, ví dụ "7h sáng hằng ngày") không có dòng code nào parse.

**Lý do nó trông giống loop: vì nó phần lớn ĐANG hiển thị chính loop.**
`_loops_as_routines` (`main.py:3169-3193`) chiếu mọi loop thành dòng giả với chuỗi schedule
bịa ra tại `main.py:3187` (`f"mỗi {v['interval_min']} phút"`), cộng reminders chiếu vào qua
`reminders.pending_as_automations` (`reminders.py:278`).

**Kiểm chứng trên đĩa:** `find brains -name automations.json` trả về **0 hit** trên cả 4
brain (Brain Default, My Bullet Journal, Ngọc Thu Phạm, PostCasterAI). Chưa từng có một dòng
Lịch tay nào tồn tại. Mọi thứ từng nhìn thấy ở tab Lịch đều là loop và nhắc hẹn chiếu vào.

`grep -rln "automation" server/test_*.py` = **0 file**. Không test nào phủ tính năng này.

Nên đây không phải bài toán gộp hai tính năng. Là **xoá một tính năng giả và đổi tên tính
năng thật**. Phía Lịch không có dữ liệu user nào để migrate.

### Lỗ bảo mật nằm đúng trong phần sắp xoá

`/automations/sync` (`main.py:3264-3269`) gọi:

```python
cli = claude_engine(system_prompt=None, cwd=CLAUDE_CWD, tag="routines")
```

Không truyền `allowed_tools`. Theo `claude_sdk_engine.py:290-301`, nhánh `else` khi
`allowed_tools` rỗng đặt `permission_mode="bypassPermissions"` (parity
`--dangerously-skip-permissions`) **và** nạp `setting_sources=["user","project","local"]`.
Đây là engine call ít rào nhất toàn codebase. Bảo đảm "CHỈ LIỆT KÊ, KHÔNG tạo/sửa/xoá/chạy
gì" của nó (`main.py:3273`) chỉ là chữ trong prompt, không có cưỡng chế nào phía sau.

Nó cũng đồng bộ routine chạy **trên hạ tầng Anthropic**, một khái niệm khác hẳn lịch cục bộ,
nên nó không thuộc về cuộc hợp nhất này.

## Vấn đề thật: đường chat không có tool

Chủ dự án nói người dùng sống ở chat. Đường chat tạo việc định kỳ hiện tại:

Toàn bộ tool surface của hub là `javis_connections`, `javis_read_file`, `javis_list_dir`,
`javis_write_file`, `javis_use_skill` (`server/mcp_hub.py:207-272`). **Không có
`javis_schedule`.** `grep -rn "javis_schedule\|create_loop\|javis_remind\|javis_task"` = 0 hit.

Nên hôm nay:
- Tạo loop = model **tự tay gõ YAML frontmatter** vào `Javis/loops/<slug>.md` qua
  `javis_write_file`.
- Tạo nhắc hẹn = model **shell ra `curl` POST /reminders qua Bash** (`reminders.py:17` ghi
  thẳng: "engine (Jarvis 007) tự gọi POST /reminders qua Bash curl từ localhost").
- Tạo task Kanban = tương tự, curl.

Đường thứ hai còn tự mâu thuẫn: loop ở mode suggest/auto bị chặn Bash (`self_improve.py:112`,
`disallowed_tools = ["Bash", "WebFetch", "WebSearch", "Task"]`) nên **loop không tự đặt nhắc
được cho chính nó**.

Xoá tab không sửa được điều này. Đây mới là phần đắt và đáng làm nhất.

## Hermes làm gì (và bài học)

Một cơ chế duy nhất. Job là record trong `~/.hermes/cron/jobs.json` (một file JSON, không
phải mỗi job một file markdown). `parse_schedule()` chuẩn hoá **mọi** input ("30m", "every
2h", "0 9 * * *", ISO timestamp) thành schedule dict với `kind ∈ {once, interval, cron}`.

Bài học cốt lõi: **"mỗi 2 tiếng" và "7h sáng" là cùng một primitive; `kind` chỉ là một
field.** Claude Code xác nhận độc lập: nó convert interval thành cron ngay lúc tạo.

Bên Jarvis 007 hôm nay chúng là hai code path không chung một dòng:
- Loop: interval-since-last-run (`self_improve.py:465`), nên nó **trôi** dần theo thời gian
  chạy.
- Reminders: wall-clock tuyệt đối `due_at`, lặp qua `cron_next` (`reminders.py:391-399`) dùng
  `cron_util.next_after` (`cron_util.py:120`).

Trớ trêu: **cron engine thật đã có sẵn**. `cron_util.py` là parser 5 trường Vixie đầy đủ
(macro `@daily`, ngữ nghĩa OR giữa dom và dow, timezone VN UTC+7), chỉ là nó đấu vào
`reminders.py` chứ không phải vào cái tab tên là "Lịch".

Bài học prior art quan trọng thứ hai: **không hệ nào bắt end user chọn mức quyền.** Routines,
ChatGPT Tasks, Claude Code đều không có mode picker. Cách thay thế là *giới hạn năng lực*:
routine chỉ với tới được connector được gắn cho nó.

Ranh giới cần giữ (Paperclip RFC + Claude Code cùng vạch): gộp mọi thứ trên trục **thời
gian**, nhưng đừng gộp time-driven với event-driven. Chuyện đó thuộc về Monitor/webhook, không
thuộc spec này.

## Về 3 chế độ: một hiểu nhầm cần đính chính

Mode **có cưỡng chế thật**, không phải trang trí. `_make_cli` (`self_improve.py:611-685`) rẽ 4
nhánh loại trừ nhau, đổi hẳn tư thế bảo mật của SDK:
- suggest → `allowed_tools = readonly_tools`
- auto → `allowed_tools = safe_tools`
- full → `allowed_tools = None` + `apply_mcp(cli, mode="full")` (`self_improve.py:639-642`)

Nhưng phát hiện quyết định là ở tầng dưới: **hub đã có sẵn mô hình scoping.**

- Mỗi connection đã có field `perm` riêng (readonly|safe|full, `mcp_store.py:154`, ranking
  tại `mcp_catalog.PERM_RANK`).
- `mcp_hub.py:143` gọi `mcp_catalog.allowed(connector, conn.get("perm"), mode, tool, args)`.
- `mcp_hub.py:314` gọi `effective_perm(conn.get("perm"), mode)` = **min của perm-connector và
  mode-lượt-chạy**.
- `mcp_hub.py:322-325` lọc tool ngay lúc LIST: readonly ẩn class write/danger, safe ẩn danger.

Nghĩa là **`mode` của loop chưa bao giờ là "cái dial quyền". Nó chỉ là một đầu vào của
`effective_perm`.** Bỏ dial khỏi UI không đập rào nào; chỉ là thôi bắt user tự vặn một tham số
mà hệ thống suy ra được.

Lý do không cho mọi loop chạy `full` mặc định (bác bỏ ý ban đầu của chủ dự án): loop **đọc dữ
liệu ngoài vào mỗi vòng** (đơn POS, comment quảng cáo, mail). Đó là text kẻ khác soạn được.
Routines phải bọc payload trong `<routine-fire-payload>` và dặn model đừng nghe lời bên trong,
chính vì lý do này. Loop `full` + connector POS + prompt injection là đường thẳng tới tiền
thật, và loop `full` được `allowed_tools=None` nên nó nuốt luôn Bash.

## Thiết kế

### Giai đoạn 1: xoá đồ giả (không đụng dữ liệu user)

Xoá:
- 5 endpoint: `/automations` GET (`main.py:3196`), POST (`:3205`), `/automations/toggle`
  (`:3224`), `/automations/delete` (`:3251`), `/automations/sync` (`:3264`).
- `_automations_path` (`:3145`), `_read_automations` (`:3149`), `_write_automations` (`:3161`).
- Khối `caps["automations"]` (`_gather_capabilities`, `main.py:3324, 3352-3354`) và mục "##
  Lịch (automations)" trong `_render_javis_index` (`main.py:3411-3413`). Đính chính khi soát
  plan: khối này **không** rác vào system prompt. Nó đi vào `Javis/index.md` qua
  `rebuild_javis_index` (`main.py:3462`), và vì list luôn rỗng nên `if caps["automations"]:`
  luôn falsy, section không bao giờ render. Là code chết, dọn cho sạch chứ không phải sửa bug.
  (`_javis_capability_summary` tại `main.py:3477` không hề nhắc automations.)
- Form `editAutomation` (`dashboard/studio.js:358-370`), rail `automations`
  (`dashboard/console.js:49, 65, 97, 107`).

Giữ và đổi vai:
- `_loops_as_routines` (`main.py:3169`) và `pending_as_automations` (`reminders.py:278`) từ
  chỗ là bản chiếu vào một registry giả trở thành **nguồn thật** của trang mới.
- Rail `selfimprove` (`console.js:46, 94`, `renderSelfImprove` tại `console.js:674`) đổi nhãn
  từ "Loop" thành **"Việc"**, gộp nhóm `"Việc & lịch"` (`console.js:65`).

Dọn kèm (đã chết sẵn, xác nhận trong lúc điều tra):
- Panel loop cũ `dashboard/index.html:160-192` (`display:none`) vẫn fetch `/loop/config` qua
  `app.js:1497`. Xoá cả DOM chết lẫn fetch, hoặc giữ shim có chủ đích.
- `_isolate()` (`self_improve.py:105-113`) chỉ chạy dưới unit test: call site duy nhất là
  nhánh `else` của `if self.deps.apply_mcp` (`:683`), mà `main.py:3029` **luôn** inject
  `apply_mcp`. Ghi chú lại chứ đừng xoá nhầm, `test_loop_ambient.py` đang dựa vào nó.

`/automations/sync` xoá hẳn (bịt lỗ `bypassPermissions`). Nếu về sau cần đồng bộ routine
claude.ai thì viết lại thành nút riêng ở trang Model, có `allowed_tools` tử tế.

### Giai đoạn 2: một record "Việc"

**Ranh giới lưu trữ (giải mơ hồ tìm ra khi tự soát spec):** hợp nhất là hợp nhất **mô hình
thời gian và đường tạo**, KHÔNG phải nhét mọi thứ vào một file store.

- **Việc bền** (lặp lại, chạy engine: loop hôm nay + cron chưa từng có executor) → `.md` trong
  `Javis/loops/`. Chúng là tài liệu: user mở trong Obsidian, sửa prompt, commit theo brain.
- **Nhắc hẹn một lần** (`action: notify`, `kind: once`) → **ở nguyên `reminders.py` store**.
  Lý do: "30 phút nữa nhắc anh uống thuốc" mà đẻ một file `.md` trong vault rồi xoá đi là rác,
  và nó mâu thuẫn với chính lý do chọn `.md` (để người dùng mở trong Obsidian). Nhắc hẹn là
  thứ phù du, không phải tài liệu.

Cái được hợp nhất giữa hai kho:
1. **`parse_schedule()` dùng chung** cho cả hai (một field `schedule`, ba `kind`).
2. **`javis_schedule` tạo được cả hai**, tự route theo `kind`/`action` (xem dưới). User và
   model chỉ thấy một khái niệm "Việc"; chuyện nó rơi vào kho nào là chi tiết triển khai.
3. **Một trang "Việc" duy nhất** hiển thị cả hai, đúng như `_loops_as_routines` +
   `pending_as_automations` đang làm sẵn.

Đây là lý do giữ `reminders.py` chứ không xoá: nó không trùng loop, nó phủ đúng nửa "phù du"
mà loop không nên phủ.

**Lưu trữ việc bền: giữ nguyên `<brain>/Javis/loops/<slug>.md`.** Frontmatter sửa được trong Obsidian
là giá trị thật của Jarvis 007 (`self_improve.py:11` có comment cố ý tách state ra
`loop-state.json` để "tránh giẫm chân user đang mở file trong Obsidian"). Đổi tên thư mục phải
đụng 6 file loop trên 4 brain cộng `LEGACY_HASHES` (`system_sync.py:536`) và loop builtin
`tu-cai-tien-javis` có mặt ở cả 4 brain, để đổi lấy đúng con số không. Đường dẫn là chi tiết
triển khai; user nhìn thấy chữ "Việc".

Frontmatter mới:

```yaml
schedule: "0 7 * * *"      # MỘT field: "120m" | "0 7 * * *" | ISO timestamp
                           #   -> parse ra {kind: interval|cron|once}, kiểu Hermes
connectors: [pancake-pos]  # QUYỀN: việc này chỉ với tới được từng này
allow_real_actions: false  # công tắc leo thang, có tên rõ
```

Các field cũ giữ nguyên nghĩa: `name`, `slug`, `enabled`, `owner_chat`, `notify`,
`quiet_hours`, `max_runs_per_day`, `workspace`, `tools_profile`, `ambient_mcp`. Thân file vẫn
là prompt.

Không có field `action` ở đây: file `.md` trong `Javis/loops/` **luôn** là `action: run`.
`notify` và `script` là chuyện của kho nhắc hẹn (`reminders.py:48` đã có sẵn ba mode
`notify|task|script`), không phải của việc bền.

Tương thích ngược, không file user nào phải sửa tay:
- `interval_min: 120` → `schedule: "120m"`.
- `mode: full` → `allow_real_actions: true`; `suggest`/`auto` → `false`.
- Luật ưu tiên khi có cả hai: `schedule` thắng `interval_min` (đúng luật `reminders.py:235`
  đã dùng).

**Định danh vẫn là TÊN FILE, không phải slug frontmatter** (`self_improve.py:273`).
`save_loop:321-327` cố ý: slug thô trùng file có sẵn thì ghi đè đúng file đó, chỉ loop mới
mới bị `_ascii_slug`. Comment giải thích vì sao: nếu không, toggle một loop tên tiếng Việt sẽ
**fork ra bản ascii trong khi bản gốc vẫn chạy**. Giữ nguyên hành vi này qua cuộc hợp nhất.

**Mô hình thời gian:** sửa `_eligible_overdue` (`self_improve.py:455-466`) để tính
`next_run_at` theo `kind`:
- `interval`: giữ ngữ nghĩa hiện tại (overdue = `now - last_run - interval*60`).
- `cron`: `cron_util.next_after(last_run)` <= now. Tái dùng parser sẵn có, không viết mới.
- `once`: chỉ xuất hiện ở kho nhắc hẹn (`reminders.py` đã xử lý sẵn). Một file `.md` mà
  `kind: once` là lỗi cấu hình: nổ một lần rồi tự `enabled: false` (đừng xoá file, user còn
  muốn xem lại), và cảnh báo trên trang Việc.

San cửa sổ 5 phút đang ép ở 3 chỗ (`self_improve.py:257, 929, 213`) cần rà lại cho `cron`:
"mỗi 5 phút tối thiểu" là luật của interval, không phải của cron.

**Jitter (cho bản fork):** cron cộng jitter suy từ `hash(slug)`, 0 tới 5 phút. Nếu Jarvis 007 được
fork rộng thì mọi bản đều `0 7 * * *` và cùng đập vào Pancake lúc 7:00:00. Deterministic theo
slug nên ổn định qua các lần chạy.

### Mô hình quyền

`allow_real_actions` đưa `mode="full"` hoặc `mode="safe"` vào **đúng `effective_perm` đang
chạy hôm nay** (`mcp_hub.py:314`). Toàn bộ cưỡng chế giữ nguyên, chỉ mất cái dial khỏi UI.
`mode: suggest` (readonly, không ghi file) gộp vào `safe`: ghi file nháp trong vault là vô
hại, và đó chính là thứ user muốn khi bật một việc.

`connectors: [...]` là phần **mới thật sự**, và là rủi ro triển khai chính của spec:
- Hub cần header `X-Javis-Connectors` (cạnh `X-Javis-Mode` sẵn có tại `mcp_hub.py:457, 483`).
- `mcp_hub.py:304` (`mcp_store.resolved(enabled_only=True)`) lọc thêm theo danh sách đó.
- Danh sách rỗng hoặc thiếu field = giữ hành vi cũ (mọi connector đang bật), để 6 file loop
  hiện có không đổi hành vi.

Giá trị: một việc không gắn connector POS thì **không cách nào** tạo đơn, bất kể prompt
injection nói gì. `mode: suggest` chỉ là lời xin; scoping là rào.

### Tool `javis_schedule` (đường chat)

Thêm vào hub cạnh `javis_use_skill` (`mcp_hub.py:272`):

```
javis_schedule(op: create|list|cancel, name, schedule, prompt,
               kind_hint?, connectors?, notify_only?)
```

`min_mode: safe`.

**Luật route (một tool, hai kho):**
- `notify_only: true` hoặc schedule parse ra `kind: once` → vào kho **nhắc hẹn**
  (`reminders.py`), **bật ngay**. Nó chỉ bắn một tin Telegram, và đây là hành vi hiện tại
  user đang dựa vào ("30 phút nữa nhắc anh...").
- Còn lại (lặp lại, chạy engine) → ghi `.md` vào `Javis/loops/`, `enabled: false`, user tự
  bật. Đúng luật CLAUDE.md hiện hành.

`op: list` và `op: cancel` phải nhìn thấy **cả hai kho** (union), nếu không model sẽ báo với
user là "không có việc nào" trong khi việc nằm ở kho bên kia. Đây là lỗi dễ mắc nhất khi
triển khai.

Cái này bỏ luôn đường `curl` qua Bash và chuyện model gõ YAML bằng tay, và sửa được nghịch lý
loop-không-tự-đặt-nhắc-được.

Prompt của việc phải **tự đủ**: mỗi vòng chạy không có ký ức về cuộc chat đã tạo ra nó. Thiết
kế "thân file = prompt" hiện tại đã đúng; giữ nguyên qua cuộc hợp nhất, đừng để primitive mới
bắt đầu phụ thuộc context chat.

## Ngoài phạm vi spec này

- Gộp time-driven với event-driven (webhook, Monitor). Ranh giới cố ý.
- Kanban tasks. Nó là máy trạng thái `todo -> ready -> running`, **không có đồng hồ**
  (`tasks.py:296`), nên nó không thuộc trục thời gian. (Ghi nhận riêng: `main.py:3631` gọi
  `tasks_feature.tick(["brain"])` với brain **hardcode**, trong khi `tick(brains)` nhận list.
  Board ở brain khác không bao giờ được dispatch. Đây là bug độc lập, nên tách issue riêng.)
- TTL/auto-expire bắt buộc cho việc bị bỏ quên. Prior art nói nên có (Claude Code hết hạn sau
  7 ngày, ChatGPT tự pause khi user thôi tương tác); Jarvis 007 mới có `max_runs_per_day` tuỳ chọn
  và auto-pause theo `fail_streak`. Đáng làm, nhưng vòng sau.
- Bọc dữ liệu MCP trả về như untrusted (kiểu `<routine-fire-payload>`). Đáng làm, vòng sau.

## Rủi ro

1. **`X-Javis-Connectors` là phần duy nhất phải sửa hub.** Hub là lớp cứng của mô hình bảo
   mật; sai ở đây là hỏng rào cho mọi engine, không chỉ loop. Cần test riêng cho: danh sách
   rỗng = hành vi cũ, danh sách sai tên = fail-closed chứ không fail-open.
2. **Đổi `_eligible_overdue` đụng vòng chạy của loop builtin `tu-cai-tien-javis`** đang sống ở
   cả 4 brain. Cần test migration đọc được cả frontmatter cũ lẫn mới.
3. **Zero test hiện phủ automations**, nên xoá thì an toàn, nhưng cũng nghĩa là không có lưới
   an toàn cho phần đổi tên UI. Cần test mới cho trang "Việc".
4. `test_loop_ambient.py` dựa vào `_isolate()` (nhánh chết trong production). Đừng dọn nhầm.
