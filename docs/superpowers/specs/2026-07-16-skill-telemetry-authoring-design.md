# Đo skill + Chuẩn viết skill (A+B)

Ngày: 2026-07-16
Trạng thái: đã duyệt thiết kế, chờ kế hoạch triển khai

## Bối cảnh

So sánh Jarvis 007 với `NousResearch/hermes-agent` cho thấy Jarvis 007 tạo skill/agent/workflow
không kém, nhưng thiếu hoàn toàn **vòng đời sau khi tạo**: không đo, không gộp, không dọn.
Jarvis 007 có hệ miễn dịch mạnh (fork học read-only, Python là người ghi duy nhất, provenance
tier, secret/injection scan, git undo) nhưng không có trao đổi chất. Hermes ngược lại.

Định hướng: ghép cơ chế trao đổi chất của Hermes vào bộ khung an toàn sẵn có của Jarvis 007,
không phải ngược lại.

Toàn bộ lộ trình gồm 4 hệ con. Spec này CHỈ phủ A và B.

- **A. Vòng đời skill** - telemetry, trạng thái, hiển thị.
- **B. Chuẩn viết skill** - hạn mức description, bộ chuẩn authoring, skill package.
- C. Curator gộp ô dù (vòng sau, phụ thuộc A và B).
- D. `/learn` từ nguồn (vòng sau, độc lập).

C phụ thuộc cả A lẫn B: không có telemetry thì curator gộp mù, không có chuẩn thì không
biết gộp về hình gì.

## Phát hiện dẫn đường: lỗi cắt cụt description

Đây là lỗi CÓ THẬT, đang chạy, đo được, không phải suy đoán từ Hermes.

Jarvis 007 cắt description ở **ba** nơi, với **ba** hạn mức khác nhau:

- `server/mcp_hub.py:256` - `(s['description'] or '')[:60]`, `metas[:20]`
- `server/main.py:3471` - `(s.get("description") or "")[:100]`, `metas[:15]`
- `server/skill_router.py:90` - `[:140]`, dùng khi frontmatter thiếu `description` thì lấy
  dòng đầu thân file làm mô tả thay thế

Người viết skill không có cách nào biết mình đang bị chấm theo thước nào.

Lưu ý hệ quả: `SKILL_DESC_MAX = 150` KHÔNG trùng với bất kỳ giá trị nào đang chạy. Nó đổi
hành vi ở cả ba chỗ (60 lên 150, 100 lên 150, 140 lên 150) và đổi cap danh sách của
`main.py` từ 15 lên 20. Đây là thay đổi hành vi có chủ đích, không phải refactor trung tính.

Đo bằng chính `skill_router.list_enabled_meta` trên brain `Brain Default`, **6/6 skill
đang bật đều bị cắt**:

- `html-to-webcake` 376 ký tự, mất 316 (84%)
- `javis-builder` 333, mất 273 (82%)
- `ingest-source` 266, mất 206
- `query-wiki` 249, mất 189
- `lint-wiki` 213, mất 153
- `tao-anh-minh-hoa-2d` 139, mất 79

Nghiêm trọng hơn con số: 5/6 skill mở đầu bằng đúng cụm `"Kích hoạt khi người dùng muốn"`
dài 29 ký tự. Gần nửa ngân sách 60 ký tự bị đốt cho boilerplate giống hệt nhau, chỉ còn
khoảng 31 ký tự thật sự phân biệt được skill này với skill kia. Mọi ví dụ trigger (`vd "..."`),
đúng cái phần khiến routing hoạt động, đều bị vứt sạch.

Tệ nhất là **tài liệu đang chủ động dạy viết sai**. CLAUDE.md bảo description phải "viết rõ
trigger", `javis-builder` bảo "viết kỹ", trong khi runtime cắt cụt. Hermes cảnh báo đúng
hiện tượng này và gọi nó là lỗi không-cosmetic: mô tả quá hạn bị cắt im lặng và skill không
bao giờ route được.

Quan hệ với A: skill không route được thì `use_count` sẽ mãi bằng 0, và telemetry ở A sẽ
đọc nhầm thành "skill chết". **B là điều kiện để A có nghĩa.**

## Quyết định đã chốt

1. Phạm vi: A + B chung một spec. C và D để vòng sau.
2. Mức tự động: **đo và hiển thị, không tự động gì**. Mọi việc tắt/archive do người bấm.
3. Hạn mức description: **150 ký tự**, một hằng số duy nhất cho cả hai điểm cắt.

Về con số 150: Hermes dùng 60, quá chật cho tiếng Việt có dấu. 300 đã được cân nhắc và loại,
vì ở mốc 15 skill nó tốn khoảng 3.000 token mỗi lượt mỗi engine và tăng tuyến tính khi
learn.py tự sinh thêm skill, trong khi 4/6 description hiện tại sẽ lọt, tức là không sửa
được bệnh gốc. Bệnh gốc không phải cắt cụt (đó là triệu chứng) mà là description đang bị
viết như tài liệu trong khi nó là một dòng mục lục. 150 rộng gấp 2,5 lần Hermes để tiếng
Việt thở được và nhét vừa 1 ví dụ trigger, vẫn đủ chặt để ép viết sắc.

Bằng chứng không mất thông tin, viết lại `html-to-webcake` (gốc 376 ký tự):

> Chuyển HTML sang file Webcake .pke để upload/sửa trên Webcake.

62 ký tự, và phân biệt TỐT HƠN 60 ký tự đầu của bản gốc (bản gốc cụt giữa chừng ở
`"...CHUYỂN một file/đoạn HTML thàn"`, mất luôn từ khoá quyết định là "Webcake").
316 ký tự còn lại là ví dụ trigger, chỗ của chúng là thân SKILL.md mục "Khi nào dùng".

Kiến trúc: **index để tìm, thân file để làm.**

## A. Đo skill

### A1. Nơi lưu

File `<brain>/Javis/skill-usage.json`. Module mới `server/skill_usage.py`.

Đặt ở `Javis/` chứ không phải `skills/.usage.json` như Hermes, để bám quy ước Jarvis 007 đã có.
`server/self_improve.py` ghi rõ: "STATE runtime tách riêng, server sở hữu:
`<vault>/Javis/loop-state.json`". Telemetry là state runtime, cùng loại với loop-state,
nên nằm cạnh nhau.

Không nhét vào frontmatter SKILL.md: brain là git repo (`git_brain`), mỗi lần dùng skill sẽ
đẻ một commit rác và tạo áp lực xung đột lên file do người viết. Đây cũng là lý do Hermes
chọn sidecar.

Khoá theo slug. Mỗi bản ghi: `use_count`, `last_used_at`, `first_used_at`, `created_at`,
`created_by`, `pinned`.

Ghi atomic qua `atomic_write_text` sẵn có. Mọi thao tác best-effort: sidecar thiếu hoặc
hỏng thì trả rỗng và đi tiếp. **Sidecar hỏng tuyệt đối không được làm gãy lời gọi skill.**

### A2. Điểm đếm

Handler `_skill` trong `server/mcp_hub.py:259` (tool `javis_use_skill`). Một chỗ duy nhất,
mọi engine đi qua (Claude Code, Codex, OpenRouter, OpenAI, Anthropic API). Bump khi nạp
skill thành công, không bump khi slug sai.

### A3. Điểm mù (ghi rõ, chấp nhận)

`system_sync.mirror_skills` mirror skill sang `<brain>/.claude/skills` để Claude Code nạp
NATIVE. Đường native KHÔNG đi qua hub nên không đếm được. Bỏ mirror là mất tính năng thật,
nên không bỏ.

Hệ quả bắt buộc, áp cho toàn bộ spec và mọi vòng sau:

> `use_count` là **tín hiệu dương một chiều**. Có đếm nghĩa là skill chắc chắn có dùng.
> `use=0` chỉ có nghĩa "không có bằng chứng", KHÔNG bao giờ được diễn giải là vô dụng,
> và KHÔNG bao giờ được dùng làm căn cứ tự tắt hay tự archive bất cứ thứ gì.

Hermes tự nó cũng ra đúng luật này vì lý do khác (bộ đếm còn mới): "use=0 is not evidence a
skill is valuable; it's absence of evidence either way. Corollary: use=0 is ALSO not a reason
to PRUNE." Với Jarvis 007 luật đó còn bắt buộc hơn vì có điểm mù thật.

### A4. Không có máy trạng thái

Vì đã chốt "đo và hiển thị, không tự động", bỏ luôn máy trạng thái. Không lưu `state` trong
file, không job nền, không scheduler.

`stale` là **hàm thuần** tính lúc đọc từ `(created_at, last_used_at, pinned, now)`.

Điều kiện cụ thể: `pinned == False` VÀ `use_count == 0` VÀ `now - created_at > SKILL_STALE_AFTER_DAYS`.

Hằng số `SKILL_STALE_AFTER_DAYS = 30` đặt trong `skill_usage.py`, KHÔNG đặt trong
`skill_router.py`. Bản đầu của spec ghi đặt cùng `SKILL_DESC_MAX` là sai: `skill_router`
không có một dòng logic thời gian nào (không import `datetime`, không `time`, không đọc
`st_mtime`), và nó không thấy dữ liệu usage. Đặt hằng số ở đó thì nó nằm chết. Hàm stale
cần cả `created_at` lẫn `use_count`, cả hai đều thuộc sidecar, nên nó thuộc về
`skill_usage.py`.

`created_at` lấy ở đâu: sidecar ghi khi lần đầu thấy skill. Với skill có sẵn từ trước khi
tính năng này tồn tại (chưa có bản ghi sidecar), fallback là `mtime` của `SKILL.md`, bọc
`try/except OSError`. Fallback này chỉ dùng để tính stale, không ghi ngược vào sidecar.

Ngưỡng 30 ngày lấy theo luật của Hermes: skill mới tạo có thể đơn giản là chưa gặp trigger,
nên chưa đủ già thì không được gắn nhãn gì. Skill có `use_count > 0` không bao giờ stale,
bất kể lần dùng cuối cách đây bao lâu (vì điểm mù native khiến `last_used_at` không đáng
tin làm căn cứ phủ định).

Cả A thu lại còn: một sidecar, một chỗ bump, một hàm tính. Phần lifecycle phức tạp của
Hermes (active/stale/archived, transition walk, `.archive/`) để dành cho C, khi đã có dữ
liệu telemetry thật để kiểm nghiệm.

### A5. Hiển thị

`GET /skills` trả thêm trường usage. Trang Skill hiện số lần dùng, lần dùng cuối, và nhãn
"chưa thấy dùng" cho skill đủ già mà chưa có tín hiệu dương.

Nhãn này BẮT BUỘC kèm chú thích rằng đường native không đếm được nên chỉ để tham khảo.
Không được trình bày như một phán quyết.

## B. Chuẩn viết skill

### B1. Một thước đo

Thêm vào `server/skill_router.py`:

- `SKILL_DESC_MAX = 150`
- `SKILL_LIST_MAX = 20` (gom hai cap 15 và 20 hiện nay về một; lấy 20 vì description đã
  giảm từ 300 xuống 150 nên ngân sách dôi ra, và 20 phủ hết số skill thực tế hiện nay)
- `SKILL_STALE_AFTER_DAYS = 30` (dùng cho A4)

Cả `main.py:3471` lẫn `mcp_hub.py:256` import từ đây. Hết cảnh hai thước.

Ghi nhận (KHÔNG sửa trong spec này): hai nơi này cùng render danh sách skill, nên chi phí
context bị trả gấp đôi mỗi lượt. Cả hai đều có lý do tồn tại (`_skill_router_block` phục vụ
engine không có tool, mô tả tool phục vụ engine có tool). Tối ưu chỗ này là việc riêng,
đừng gộp vào đây.

`skill_router` là nơi đặt đúng vì nó đã tự nhận là "nguồn chân lý DUY NHẤT cho việc khám phá
skill, dùng chung bởi main.py và mcp_hub.py để hai nơi KHÔNG bao giờ lệch nhau". Hằng số
hạn mức thuộc về chính trách nhiệm đó.

### B2. Ép lúc ghi

`POST /skills` từ chối description quá `SKILL_DESC_MAX` và từ chối cụm mở đầu boilerplate.

learn.py kiểm tra tương tự trong `_promote_sync`. Vi phạm thì đưa vào `rep["blocked"]` đúng
như secret-scan và injection-scan đang làm, KHÔNG ghi bừa rồi để runtime cắt.

Boilerplate bị cấm: các biến thể mở đầu kiểu `Kích hoạt khi (người dùng) muốn`,
`Dùng khi cần`, `Sử dụng skill này khi`. Chúng đốt tới 29 ký tự mà không phân biệt gì,
vì mọi skill đều mở đầu như vậy.

### B3. Bộ chuẩn dùng chung

Một hằng số text (theo mẫu `_AUTHORING_STANDARDS` của `hermes/agent/learn_prompt.py`),
nhúng vào cả prompt learn (`learn.py:_build_prompt`) lẫn `javis-builder/SKILL.md`.

Nội dung:

- Hạn mức 150 **kèm lý do**: router cắt đúng ở 150, viết dài hơn là mất im lặng và skill
  không route được. Viết xong TỰ ĐẾM. (Hermes nhấn mạnh đây là luật bị vi phạm nhiều nhất
  và không phải chuyện thẩm mỹ.)
- Cấm boilerplate mở đầu. Nêu năng lực, không nêu ngữ cảnh kích hoạt.
- Ví dụ trigger đầy đủ nằm ở mục "Khi nào dùng" trong thân file, không nhét vào description.
- Thứ tự mục cố định: Khi nào dùng / Chuẩn bị / Cách chạy / Quy trình / Bẫy / Kiểm chứng.
- Cấm bịa flag, path, API chưa thấy trong nguồn.
- Trần độ dài thân file: khoảng 100 dòng cho skill đơn giản, 200 cho skill phức tạp.
  Dài hơn thì đẩy xuống `references/`.
- Cấm skill kiểu router chỉ trỏ sang skill khác.
- Nội dung lớn đẩy xuống `scripts/` và `references/`, tham chiếu bằng đường dẫn tương đối.
- Giữ luật hiện có của Jarvis 007: `group` bắt buộc, slug ASCII không dấu, cấm em dash.

### B4. Skill thành package

Cho phép `references/`, `scripts/`, `templates/` trong thư mục skill.

**SỬA LỖI TRONG CHÍNH SPEC NÀY (bản đầu viết sai, đã kiểm chứng lại bằng cách đọc
`system_sync.py:235-264` đầy đủ):** `mirror_skills` KHÔNG phải "chỉ copy mỗi SKILL.md".
Dòng 258-260 copy **mọi file top-level** trong thư mục skill qua `d.iterdir()` +
`if f.is_file()`. Thứ thực sự bị rơi là **THƯ MỤC CON**, vì `f.is_file()` false với dir và
không có đệ quy.

Nên việc cần làm là "file phẳng thành cây đệ quy", không phải "một file thành thư mục".

**Bug đi kèm phải sửa cùng lúc:** cổng hash-skip (dòng 251-256) chỉ băm nội dung `SKILL.md`.
Nếu `references/x.md` đổi mà `SKILL.md` không đổi thì hash trùng, `continue` chạy, và thay
đổi KHÔNG BAO GIỜ tới được bản mirror. Lỗi này đã tồn tại sẵn với file asset ngang hàng, và
sẽ nặng hơn khi có thư mục con. Skip phải trở thành tree-aware.

Bẫy khi làm tree-aware: mirror là add-only, nên bản mirror có file THỪA sẽ không bao giờ
khớp digest của nguồn, gây copy lại vô hạn mỗi lần gọi. Phải tính digest của đích **chỉ trên
tập đường dẫn có ở nguồn**. Và không được đưa file nhị phân qua `read_text`/`skill_hash`
(`errors="replace"` sẽ làm hỏng thầm lặng, và `_norm_text` chuẩn hoá ngày) - dùng sha256
trên raw bytes cho file không phải text.

Ràng buộc phải giữ: add/update-only, không xoá entry lạ ở `.claude`, bỏ qua `.disabled`,
và `mirror_skills` phải KHÔNG tự lấy `_LOCK` (`sync_brain:356` gọi nó khi đang giữ lock, mà
`threading.Lock` không reentrant nên sẽ deadlock).

**Đây là chỗ rủi ro cao nhất của cả spec**, cần test riêng.

**Phạm vi:** `references/`/`scripts/`/`templates/` CHỈ áp cho skill của brain (do người dùng
hoặc learn tạo). Skill HỆ THỐNG vẫn một file `SKILL.md`, vì `_system_items` (`system_sync.py:142-160`)
ship nội dung dưới dạng chuỗi đơn và tuple `(key, kind, slug, content)` của nó bị `sync_brain`
lẫn CLI `--hash` tiêu thụ; nới ra sẽ phá cả hai. Không đáng, và chưa cần.

### B5. Viết lại 6 description

Không mất thông tin: ví dụ trigger chuyển xuống mục "Khi nào dùng" trong thân file, nơi
không bị cắt và chỉ được đọc khi skill đã nạp.

Thực tế chỉ phải viết lại **5**, không phải 6. `tao-anh-minh-hoa-2d` đo lại chính xác được
139 ký tự, tức là ĐÃ dưới 150 và không có ví dụ trigger nào trong description để dời đi.
Không đụng vào nó.

5 skill hệ thống sửa ở NGUỒN `<project>/.claude/skills/`, KHÔNG sửa bản mirror trong brain:

- `html-to-webcake` 376 ký tự, dư 226 (nặng nhất, rủi ro cao nhất)
- `javis-builder` 333, dư 183
- `ingest-source` 266, dư 116
- `query-wiki` 249, dư 99
- `lint-wiki` 213, dư 63 (nhẹ nhất)

Sửa luôn hai chỗ tài liệu đang dạy sai: CLAUDE.md (mục description "viết rõ trigger") và
`javis-builder` (mục description "viết kỹ").

### B6. Lỗi lệch phát hiện trong lúc đọc

`javis-builder` đang dạy ghi skill vào `.claude/skills/`, trong khi CLAUDE.md và `skill_router`
nói canonical là `skills/<slug>/SKILL.md` còn `.claude/skills` chỉ là bản mirror phái sinh.
Skill builder đang dạy ghi vào chỗ mirror.

Không phải 1 chỗ mà **3 chỗ** trong cùng file, phải sửa cả ba kẻo file tự mâu thuẫn:

- dòng 54: `### Skill -> \`.claude/skills/<slug>/SKILL.md\``
- dòng 23-24: bước chống trùng bảo đọc folder `.claude/skills/`
- dòng 38: chú thích field `skills:` bảo "chỉ gán skill đã có trong .claude/skills"

## Kiểm thử

**Quy ước nhà (bắt buộc theo, đã kiểm chứng):** repo này KHÔNG dùng pytest. Không có
conftest.py, pytest.ini, pyproject.toml hay tox.ini nào. Mọi test là script Python chạy
thẳng, dùng helper tự viết `check(name, cond)` gom lỗi vào `_fails` rồi `sys.exit(1)` ở
cuối (mẫu chuẩn: `server/test_loop_ambient.py:23-30` và `:117-120`).

Preamble bắt buộc, thứ tự load-bearing (env TRƯỚC import, vì module state đọc
`JAVIS_STATE_DIR` lúc import):

```python
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-<x>test-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import <module>  # noqa: E402
```

KHÔNG lấy `server/test_plugins_host.py` làm mẫu: nó dùng bare assert nên dừng ở lỗi ĐẦU
TIÊN, trong khi lint description cần liệt kê MỌI skill vi phạm trong một lần chạy. Lệnh
chạy ghi trong docstring của file đó (`.venv/Scripts/python`) cũng sai: `server/.venv`
không tồn tại, venv nằm ở gốc repo.

Lệnh chạy đúng: `cd server && ../.venv/Scripts/python.exe test_<name>.py`

CI (`.github/workflows/ci.yml:29-39`) glob `test_*.py` trong `server/` rồi chạy từng file
bằng `python` trần. Nên test mới **chỉ cần đặt tên `server/test_*.py` là tự vào CI**, không
phải sửa ci.yml. Ngược lại, đặt ngoài `server/` thì CI sẽ KHÔNG chạy.

`test_skill_usage.py`: bump tăng đúng, ghi atomic, file thiếu, file hỏng (JSON rác), gọi
song song, sidecar hỏng không làm gãy lời gọi skill.

`test_skill_router.py`: khẳng định `main.py` và `mcp_hub.py` cùng dùng `SKILL_DESC_MAX`,
không còn hằng số rời (60 hay 100) nằm rải rác.

`test_system_sync.py`: `mirror_skills` copy đủ `references/`, `scripts/`, `templates/`;
vẫn bỏ qua `.disabled`; vẫn không ghi lại khi hash trùng.

**Test CI quan trọng nhất:** quét mọi skill hệ thống trong `<project>/.claude/skills/`,
FAIL nếu có description vượt `SKILL_DESC_MAX` hoặc dính boilerplate. Đây là thứ khiến con
bug hôm nay không bao giờ quay lại, và là lý do chính khiến B đáng làm chứ không chỉ là
dọn dẹp một lần.

Chạy test phải dùng `.venv` (python hệ thống thiếu lib).

## Rủi ro

Đổi nội dung system prompt sẽ phá prompt cache một lần ở lượt đầu sau deploy. Chấp nhận được.

Viết lại description là đổi hành vi routing thật. Kỳ vọng tốt lên nhưng vẫn là thay đổi
hành vi cần theo dõi.

`mirror_skills` copy thư mục là chỗ dễ sinh lỗi nhất. Rủi ro cụ thể: xoá nhầm file trong
`.claude/skills`, hoặc copy đè lên thứ người dùng sửa tay. Giữ nguyên tinh thần hiện tại
(add/update-only, không xoá entry lạ).

`Javis/skill-usage.json` là state runtime, không phải tri thức, nên PHẢI được gitignore ở
brain. Đây không phải chuyện cân nhắc: `.gitignore` của brain đã nêu nguyên tắc dứt khoát
là "Git chỉ version TRI THỨC ĐÃ CHƯNG CẤT (facts/wiki/skills/MEMORY.md)" và đã loại sẵn
learn-log, loop-log, conversations, lock. Telemetry rơi đúng vào nhóm bị loại.

Vị trí chính xác (bản đầu ghi lệch, đã kiểm chứng lại):

- Template là hằng số `_GITIGNORE` ở `server/git_brain.py:62-72` (dòng 63-64 là comment,
  các mục ignore thật nằm ở 65-71).
- "Danh sách path song song" KHÔNG nằm trong hàm nào. Đó là hằng số module
  `_BACKUP_SKIP_SUBSTR` ở `git_brain.py:267-268`, do helper `_backup_skip()` (271-276) tiêu
  thụ, dùng ở 4 chỗ: `_sync_mirror` (289), `_apply_back` (467), `_brains_has_content` (532),
  `_sync_brains_locked` (604).

Hai chỗ này ở **hai không gian đường dẫn KHÁC NHAU**, dễ sai:

- `.gitignore` tương đối với gốc BRAIN, nên viết `Javis/skill-usage.json` (không slash đầu).
- `_BACKUP_SKIP_SUBSTR` so khớp chuỗi con trên rel tương đối với thư mục CHA của brain, và
  `_backup_skip` bọc rel trong hai dấu slash. Nên phải viết `"/Javis/skill-usage.json/"`
  đúng dạng đó (cả slash đầu lẫn slash cuối), giống mọi mục hiện có.

**Câu hỏi brain cũ đã có lời đáp dứt khoát: KHÔNG, brain cũ sẽ không bao giờ nhận template
mới.** `ensure_git_repo` có hai chốt chặn độc lập:

1. Dòng 82 `if is_git_checkout(root): return {...}` return TRƯỚC khi chạm bất cứ code
   `.gitignore` nào. Brain đã là git repo thì không bao giờ đọc lại template.
2. Dòng 92-93 `if not gi.exists(): gi.write_text(_GITIGNORE)` - kể cả nhánh init, `.gitignore`
   có sẵn cũng không bị đụng.

Nên `ensure_git_repo` idempotent theo nghĩa "gọi lại không hỏng", nhưng KHÔNG reconcile.

Cách sửa: tách helper `_ensure_gitignore_lines(root) -> bool` đọc `.gitignore` hiện có, chỉ
APPEND các dòng của `_GITIGNORE` chưa có (merge theo dòng, TUYỆT ĐỐI không ghi đè kẻo xoá
mục user tự thêm), trả về có đổi hay không. Gọi ở cả hai nhánh. Nhánh brain-cũ nếu có đổi
thì commit bằng `commit_paths` với prefix `chore:` (KHÔNG dùng `learn:`/`curator:` vì
`LEARN_COMMIT_PREFIXES` ở dòng 31 quyết định cái gì hiện ở UI Review và cái gì
`revert_last_learn` sẽ undo). Không thêm `add -A` mới: dòng 95 tự ghi rõ đó là chỗ DUY NHẤT
được phép dùng `-A`.

Hai điều còn lại phải xử lý: (a) brain cũ có thể ĐÃ track `Javis/skill-usage.json` do
`add -A` baseline, mà gitignore không có tác dụng với file đã track, nên cần một lần
`git rm --cached` khi path vừa bị ignore vừa đang được track; (b) không caller nào chạy lúc
server khởi động (chỉ `/learn/enable` và `/reflect` gọi), nên việc reconcile chỉ xảy ra khi
một trong hai endpoint đó được gọi.

## HOÃN: B4 (mirror_skills đệ quy) - cần spec riêng

Ngày 2026-07-17, sau khi fan-out 6 reader lập bản đồ rủi ro, **B4 bị hoãn** (anh Quy quyết).
Ghi lại đây vì ledger thi công bị gitignore, phát hiện sẽ mất theo.

**Spec này đã SAI ba chỗ về B4:**

1. *"Skill HỆ THỐNG vẫn một file SKILL.md"* - **sai**. `.claude/skills/html-to-webcake` đã
   ship `tools/` (4 file) + `examples/` (9 file) ngay bây giờ.
2. *"7 hot path"* - **sai**. Chỉ MỘT chỗ nóng thật: `main.py:184` trong `build_system_prompt`,
   chạy mỗi lượt chat (dashboard, Telegram, Kanban task, loop, nhắc hẹn, learn spawn). Sáu chỗ
   còn lại là endpoint do người bấm, cộng `system_sync.py:356` chạy 1 lần/brain/process.
3. Cảnh báo symlink và file nhị phân - **không có cơ sở**. Đĩa không có symlink/reparse point
   nào, không file nhị phân nào (kể cả `.pke` cũng là base64 ASCII).

**Sáu blocker khiến B4 không làm được như đã viết:**

- `main.py:184` KHÔNG có cổng chặn (khác `ensure_synced` ngay trên nó, vốn được gác bởi
  `_SYNCED_ROOTS`). Cố ý như vậy để skill viết giữa phiên hiện ra không cần khởi động lại.
  Làm đệ quy = rglob + băm mọi file trong mọi skill dir MỖI LƯỢT CHAT. Số thật đo được:
  `brains/My Bullet Journal/skills` = 27 dir / 41 file / 496 KB. Và chi phí tăng theo đúng
  thứ tính năng này khuyến khích thêm vào (`references/`, `scripts/`).
- `build_system_prompt` là hàm ĐỒNG BỘ, gọi trần từ handler async (`main.py:4359`, `:4641`).
  Đi bộ cây thư mục sẽ chặn event loop -> đứng mọi WebSocket, Telegram poller, scheduler loop,
  tick nhắc hẹn. Không chỉ lượt chat đó. Repo biết dùng `asyncio.to_thread` ở chỗ khác.
- `_LOCK` là `threading.Lock` KHÔNG reentrant. `sync_brain:356` gọi `mirror_skills` khi ĐANG
  giữ lock, nhưng 7 chỗ ở `main.py` gọi nó mà KHÔNG giữ lock nào. Nên bản đệ quy không thể
  lấy lock (deadlock) mà cũng không thể bỏ lock (copy cây không đồng bộ đua với bản đang khoá).
  Cần thiết kế lại, không phải sửa vài dòng.
- Lần gọi đầu cho mỗi brain, `mirror_skills` chạy HAI LẦN liền nhau (`sync_brain` bước 3, rồi
  `main.py:184`). Rẻ hôm nay, nhưng nhân đôi băm-cả-cây đúng lúc khởi động.
- KHÔNG một test nào trong repo chạm `mirror_skills`. `test_system_sync.py` mà spec giả định
  là có thì KHÔNG TỒN TẠI. Rewrite không có lưới nào.
- Lợi ích B4 hứa thì nó KHÔNG giao được: `html-to-webcake` hỏng vì `_system_items`
  (`system_sync.py:142-160`) chỉ ship chuỗi SKILL.md, nằm PHÍA TRÊN `mirror_skills`.

**Bug có thật phát hiện kèm (ghi nhận, xử sau - anh Quy quyết):**

`html-to-webcake` **đang hỏng ở MỌI brain ngay bây giờ**. SKILL.md của nó bảo agent chạy
`tools/` và đọc `examples/`, nhưng cây con chưa bao giờ tới brain nào vì `_system_items` chỉ
ship SKILL.md và `_atomic_write` là text-only. Bug CÓ SẴN, không do kế hoạch này gây ra.
Sửa đòi: `_system_items` ship cả cây + manifest chuyển từ per-item sang per-file (hiện là
một chuỗi `hash` mỗi skill, dù khoá tên là `"files"`). Manifest quyết định app có tự cập nhật
đè skill user đã sửa hay không, nên chạm vào nó cần cẩn trọng riêng.

**Bug có thật thứ hai (cũng có sẵn):** cổng hash-skip của `mirror_skills` chỉ băm SKILL.md,
nhưng vòng copy lại copy MỌI file top-level. Nên asset ngang hàng đổi mà SKILL.md không đổi
thì bản mirror KHÔNG BAO GIỜ nhận. Đã đúng hôm nay, sẽ nặng hơn nếu có cây con.

**Dữ liệu thật:** 11/59 skill dir đã có thư mục con (10 × `references/` trong brain, cộng
`html-to-webcake`). Nên nhu cầu là THẬT, không tưởng tượng - chỉ là cách làm trong spec này sai.

Việc còn lại khi làm spec riêng cho B4: gác chi phí ở `main.py:184` trước, giải bài toán lock,
dựng `test_system_sync.py` từ số 0, rồi mới đụng tới đệ quy. Và sửa `_system_items` nếu muốn
skill hệ thống ship được cây con.

## Ngoài phạm vi (cố ý)

Curator gộp ô dù (C). `/learn` từ nguồn (D). Auto-archive và `.archive/`. `related_skills`
thành graph. Máy trạng thái lifecycle đầy đủ. Skill templating kiểu `${HERMES_SKILL_DIR}`
và shell nội tuyến.

## Tham chiếu

Repo Hermes đọc tại commit `53adb3f`. Các file đáng đọc lại khi làm C:
`agent/learn_prompt.py` (bộ chuẩn authoring), `tools/skill_usage.py` (sidecar telemetry,
lifecycle), `agent/curator.py` (prompt gộp ô dù, các luật cứng), `agent/background_review.py`
(fork review sau lượt), `agent/learning_graph.py` (đồ thị hiển thị).
