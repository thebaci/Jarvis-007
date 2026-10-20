# Đo skill + Chuẩn viết skill (A+B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vá lỗi cắt cụt description đang âm thầm phá routing của mọi skill, và cho Jarvis 007 biết skill nào thực sự được dùng.

**Architecture:** Gom ba điểm cắt description rời rạc về một hằng số duy nhất ở `skill_router.py` rồi ép hằng số đó ở mọi chỗ GHI (API, learn). Thêm một sidecar telemetry `Javis/skill-usage.json` do `skill_usage.py` sở hữu, bump tại một điểm nghẽn duy nhất là handler `_skill` trong `mcp_hub.py`. Không máy trạng thái, không job nền: `stale` là hàm thuần tính lúc đọc.

**Tech Stack:** Python 3.12, FastAPI, PyYAML, stdlib (`hashlib`, `shutil`, `tempfile`). Không pytest. Vanilla JS cho dashboard.

## Global Constraints

- **Ngôn ngữ:** mọi comment, docstring, thông báo lỗi hướng tới người dùng viết tiếng Việt.
- **TUYỆT ĐỐI không dùng ký tự em dash (U+2014)** trong bất kỳ file nào. Dùng "-".
- **KHÔNG dùng pytest.** Test là script chạy thẳng, dùng `check(name, cond)` + `_fails` + `sys.exit(1)`. Mẫu chuẩn: `server/test_loop_ambient.py:23-30` và `:117-120`.
- **Lệnh chạy test:** `cd server && ../.venv/Scripts/python.exe test_<name>.py`. Venv ở GỐC repo, KHÔNG phải `server/.venv`.
- **Test mới phải đặt tên `server/test_*.py`** thì CI (`.github/workflows/ci.yml:29-39`) mới glob thấy. Đặt chỗ khác là CI bỏ qua.
- **Preamble test, thứ tự load-bearing** (env TRƯỚC import, vì module đọc `JAVIS_STATE_DIR` lúc import):
  ```python
  os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-<x>test-"))
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import <module>  # noqa: E402
  ```
- `SKILL_DESC_MAX = 150`, `SKILL_LIST_MAX = 20`, `SKILL_STALE_AFTER_DAYS = 30`.
- **`skill_router.py` là READ-ONLY** (hợp đồng ở docstring dòng 16). Chỉ thêm hằng số và hàm THUẦN. Mọi thao tác ghi thuộc `system_sync.py`.
- **`use_count` là tín hiệu dương một chiều.** `use=0` KHÔNG BAO GIỜ được hiểu là vô dụng, không bao giờ tự tắt/archive.
- Spec đầy đủ: `docs/superpowers/specs/2026-07-16-skill-telemetry-authoring-design.md`.

---

## File Structure

**Tạo mới:**
- `server/skill_usage.py` - sidecar telemetry. Sở hữu đọc/ghi `<brain>/Javis/skill-usage.json`, `SKILL_STALE_AFTER_DAYS`, hàm `is_stale`. KHÔNG import `main`.
- `server/test_skill_caps.py` - trần description, validator, lint skill hệ thống.
- `server/test_skill_usage.py` - sidecar.
- `server/test_mirror_tree.py` - mirror đệ quy.

**Sửa:**
- `server/skill_router.py` - thêm hằng số + `validate_description`; `_meta_of:90` dùng trần chung.
- `server/main.py` - `_skill_router_block:3464,3470,3471,3473,3474`; `POST /skills:2213-2238`; `GET /skills:2151`.
- `server/mcp_hub.py` - `listing:256-258`; `_skill:237-245`.
- `server/learn.py` - schema prompt `:356-359`; chuẩn authoring trong `_build_prompt`; ép trần trong `_promote_sync:544-568`.
- `server/system_sync.py` - `mirror_skills:235-264` thành đệ quy + tree hash.
- `server/git_brain.py` - `_GITIGNORE:62-72`; `_BACKUP_SKIP_SUBSTR:267-268`; `ensure_git_repo:75-99`.
- `dashboard/studio.js` - `renderSkillList:463-477`.
- `CLAUDE.md:249` - mẫu description.
- `.claude/skills/{html-to-webcake,ingest-source,javis-builder,lint-wiki,query-wiki}/SKILL.md`.

---

### Task 1: Hằng số + validator ở skill_router

**Files:**
- Modify: `server/skill_router.py:21-31` (import + hằng số), `:90` (fallback `[:140]`)
- Test: `server/test_skill_caps.py` (tạo mới)

**Interfaces:**
- Produces: `skill_router.SKILL_DESC_MAX: int`, `skill_router.SKILL_LIST_MAX: int`, `skill_router.validate_description(desc: str) -> Optional[str]` (None = hợp lệ, chuỗi = lý do từ chối bằng tiếng Việt). Task 2, 4, 5 dùng.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_skill_caps.py`:

```python
"""Test trần description skill + hằng số router. Chạy tay / CI:

    cd server && ../.venv/Scripts/python.exe test_skill_caps.py

Không cần pytest, không chạm mạng.
Phủ: hằng số SKILL_DESC_MAX/SKILL_LIST_MAX, validate_description (quá dài, boilerplate,
hợp lệ, rỗng), fallback _meta_of dùng chung trần.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-capstest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skill_router  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---- hằng số ----
check("SKILL_DESC_MAX = 150", getattr(skill_router, "SKILL_DESC_MAX", None) == 150)
check("SKILL_LIST_MAX = 20", getattr(skill_router, "SKILL_LIST_MAX", None) == 20)

# ---- validate_description ----
v = skill_router.validate_description
check("description hợp lệ → None", v("Chuyển HTML sang file Webcake .pke.") is None)
check("description rỗng → None (body-fallback lo)", v("") is None)
check("description None → None", v(None) is None)

long_desc = "x" * 151
r = v(long_desc)
check("description 151 ký tự → bị từ chối", isinstance(r, str))
check("lý do từ chối có nêu số ký tự thật", r is not None and "151" in r)
check("lý do từ chối có nêu trần", r is not None and "150" in r)
check("description đúng 150 ký tự → lọt", v("x" * 150) is None)

check("bắt boilerplate 'Kích hoạt khi'",
      isinstance(v("Kích hoạt khi người dùng muốn tạo ảnh"), str))
check("bắt boilerplate 'Sử dụng skill này khi'",
      isinstance(v("Sử dụng skill này khi cần vẽ"), str))
check("KHÔNG bắt 'Dùng khi cần' (mở đầu hợp lệ, ngắn)",
      v("Dùng khi cần tạo ảnh minh hoạ phong cách flat 2D") is None)

# ---- _meta_of fallback dùng chung trần ----
tmp = Path(tempfile.mkdtemp(prefix="javis-capsbrain-"))
d = tmp / "skills" / "khong-co-desc"
d.mkdir(parents=True)
(d / "SKILL.md").write_text("---\nname: Không mô tả\n---\n" + ("y" * 400) + "\n",
                            encoding="utf-8")
metas = skill_router.list_enabled_meta(tmp)
got = next((m for m in metas if m["slug"] == "khong-co-desc"), None)
check("_meta_of fallback trả về skill", got is not None)
check("fallback cắt theo SKILL_DESC_MAX chứ không phải 140",
      got is not None and len(got["description"]) == skill_router.SKILL_DESC_MAX)

if _fails:
    print(f"\nFAIL - test_skill_caps: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_skill_caps: tất cả pass")
```

- [ ] **Step 2: Chạy test, xác nhận nó FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL. `SKILL_DESC_MAX = 150` fail (hằng số chưa tồn tại, `getattr` trả None), và `validate_description` ném `AttributeError: module 'skill_router' has no attribute 'validate_description'`.

- [ ] **Step 3: Thêm hằng số + validator**

Trong `server/skill_router.py`, sau dòng 31 (`_READ_BASES = ...`), TRƯỚC hai dòng trắng dẫn tới `def skills_base`, chèn:

```python

# Trần độ dài description khi bơm vào router (system prompt + mô tả tool javis_use_skill).
# Dài hơn là BỊ CẮT IM LẶNG → phần đuôi không tới engine, skill không route được. Vì vậy
# trần này được ÉP ở mọi chỗ GHI (POST /skills, learn.py), không chỉ cắt lúc hiển thị.
# Ví dụ trigger đầy đủ thuộc về mục '## Khi nào dùng' trong thân file, nơi không bị cắt.
SKILL_DESC_MAX = 150

# Số skill tối đa liệt kê trong router. Nhiều hơn → trỏ sang Javis/index.md.
SKILL_LIST_MAX = 20

# Cụm mở đầu sáo rỗng: mọi skill đều mở y hệt nhau nên nó đốt ngân sách ký tự mà không
# phân biệt được skill nào với skill nào. Cấm ở chỗ ghi.
_DESC_BOILERPLATE_RE = re.compile(
    r"^\s*(kích\s+hoạt\s+khi"
    r"|sử\s+dụng\s+skill\s+này\s+khi"
    r"|dùng\s+skill\s+này\s+khi"
    r"|skill\s+này\s+(dùng|được\s+dùng)"
    r"|use\s+this\s+skill\s+when"
    r"|activate\s+when)",
    re.I,
)


def validate_description(desc) -> Optional[str]:
    """None = hợp lệ. Chuỗi = lý do từ chối (tiếng Việt, hiện thẳng cho user).
    Hàm THUẦN (không I/O) nên vẫn đúng hợp đồng read-only của module."""
    d = (desc or "").strip()
    if not d:
        return None    # rỗng là hợp lệ: POST /skills có body-fallback lo
    if len(d) > SKILL_DESC_MAX:
        return (f"description dài {len(d)} ký tự, vượt trần {SKILL_DESC_MAX}. Router cắt "
                f"đúng ở {SKILL_DESC_MAX} nên phần dư MẤT IM LẶNG và skill không route "
                "được. Đưa ví dụ trigger xuống mục '## Khi nào dùng' trong thân file.")
    if _DESC_BOILERPLATE_RE.match(d):
        return ("description mở đầu bằng cụm sáo rỗng (vd 'Kích hoạt khi ...'). Mọi skill "
                "đều mở như vậy nên nó đốt ngân sách mà không phân biệt gì. Nêu thẳng "
                "năng lực, vd 'Chuyển HTML sang file Webcake .pke.'")
    return None
```

- [ ] **Step 4: Sửa fallback `[:140]` dùng chung trần**

Trong `server/skill_router.py:90`, đổi:

```python
    desc = meta.get("description", "") or (body.split("\n")[0][:140] if body else "")
```

thành:

```python
    desc = meta.get("description", "") or (body.split("\n")[0][:SKILL_DESC_MAX] if body else "")
```

- [ ] **Step 5: Cập nhật docstring cho khỏi nói dối**

Trong `server/skill_router.py`, sau dòng 16-17 (đoạn "Mọi hàm ở đây CHỈ ĐỌC..."), thêm một dòng:

```
Module này cũng sở hữu TRẦN HIỂN THỊ (SKILL_DESC_MAX / SKILL_LIST_MAX) - trước đây mỗi nơi
tự cắt một kiểu (60 ở hub, 100 ở system prompt, 140 ở fallback) nên người viết skill không
biết mình bị chấm theo thước nào.
```

- [ ] **Step 6: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS, in ra `OK - test_skill_caps: tất cả pass`.

- [ ] **Step 7: Commit**

```bash
git add server/skill_router.py server/test_skill_caps.py
git commit -m "feat(skill): mot thuoc do duy nhat cho description (SKILL_DESC_MAX=150)"
```

---

### Task 2: main.py và mcp_hub dùng chung hằng số

**Files:**
- Modify: `server/main.py:3464` (docstring), `:3470`, `:3471`, `:3473`, `:3474`
- Modify: `server/mcp_hub.py:256`, `:257`, `:258`
- Test: `server/test_skill_caps.py` (thêm vào file Task 1)

**Interfaces:**
- Consumes: `skill_router.SKILL_DESC_MAX`, `skill_router.SKILL_LIST_MAX` (Task 1).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_caps.py`, TRƯỚC khối `if _fails:` ở cuối:

```python
# ---- không còn hằng số cắt nào nằm rải rác (chống mọc lại 'thước thứ hai') ----
_SRC = Path(os.path.dirname(os.path.abspath(__file__)))


def _region(path, start_marker, end_marker):
    """Lấy đoạn mã giữa hai mốc để chỉ soi đúng vùng render router."""
    text = (_SRC / path).read_text(encoding="utf-8")
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j]


hub = _region("mcp_hub.py", "metas = skill_router.list_enabled_meta(vault_root)",
              'add("javis_use_skill"')
check("mcp_hub không còn literal [:60]", "[:60]" not in hub)
check("mcp_hub không còn literal 20", "20" not in hub)
check("mcp_hub dùng SKILL_DESC_MAX", "SKILL_DESC_MAX" in hub)
check("mcp_hub dùng SKILL_LIST_MAX", "SKILL_LIST_MAX" in hub)

blk = _region("main.py", "def _skill_router_block", "@app.get(\"/javis/index\")")
check("main không còn literal [:100]", "[:100]" not in blk)
check("main không còn literal 15", "15" not in blk)
check("main dùng SKILL_DESC_MAX", "SKILL_DESC_MAX" in blk)
check("main dùng SKILL_LIST_MAX", "SKILL_LIST_MAX" in blk)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL với 6 lỗi: `mcp_hub không còn literal [:60]`, `mcp_hub không còn literal 20`, `mcp_hub dùng SKILL_DESC_MAX`, `mcp_hub dùng SKILL_LIST_MAX`, `main không còn literal [:100]`, `main không còn literal 15`.

- [ ] **Step 3: Sửa mcp_hub**

Trong `server/mcp_hub.py`, đổi khối dòng 254-258 từ:

```python
    # Mô tả tool = router thu nhỏ: liệt kê slug + mô tả ngắn để engine biết KHI NÀO gọi skill nào.
    metas = skill_router.list_enabled_meta(vault_root)
    listing = "; ".join(f"{s['slug']}: {(s['description'] or '')[:60]}" for s in metas[:20])
    if len(metas) > 20:
        listing += f"; …(+{len(metas) - 20} skill nữa)"
```

thành:

```python
    # Mô tả tool = router thu nhỏ: liệt kê slug + mô tả ngắn để engine biết KHI NÀO gọi skill nào.
    # Trần lấy từ skill_router (CHUNG với system prompt) - trước đây hub tự cắt 60, system prompt
    # cắt 100 → người viết skill không biết mình bị chấm theo thước nào.
    metas = skill_router.list_enabled_meta(vault_root)
    _cap = skill_router.SKILL_LIST_MAX
    listing = "; ".join(f"{s['slug']}: {(s['description'] or '')[:skill_router.SKILL_DESC_MAX]}"
                        for s in metas[:_cap])
    if len(metas) > _cap:
        listing += f"; …(+{len(metas) - _cap} skill nữa)"
```

- [ ] **Step 4: Sửa main.py**

Trong `server/main.py`, đổi dòng 3464 (dòng cuối docstring của `_skill_router_block`) từ:

```python
    Cap 15 skill để không phình context (nhiều hơn → trỏ Javis/index.md)."""
```

thành:

```python
    Cap skill_router.SKILL_LIST_MAX để không phình context (nhiều hơn → trỏ Javis/index.md)."""
```

Đổi khối dòng 3470-3474 từ:

```python
    for s in metas[:15]:
        desc = (s.get("description") or "").replace("\n", " ")[:100]
        lines.append(f"- {s['slug']} ({s['name']}): {desc}")
    if len(metas) > 15:
        lines.append(f"…(+{len(metas) - 15} skill nữa - xem `Javis/index.md`)")
```

thành:

```python
    cap = skill_router.SKILL_LIST_MAX
    for s in metas[:cap]:
        desc = (s.get("description") or "").replace("\n", " ")[:skill_router.SKILL_DESC_MAX]
        lines.append(f"- {s['slug']} ({s['name']}): {desc}")
    if len(metas) > cap:
        lines.append(f"…(+{len(metas) - cap} skill nữa - xem `Javis/index.md`)")
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/mcp_hub.py server/test_skill_caps.py
git commit -m "fix(skill): gom 3 diem cat description ve mot hang so chung"
```

---

### Task 3: Lint CI + viết lại 5 description hệ thống

**Files:**
- Test: `server/test_skill_caps.py` (thêm phần lint)
- Modify: `.claude/skills/html-to-webcake/SKILL.md`, `.claude/skills/javis-builder/SKILL.md`, `.claude/skills/ingest-source/SKILL.md`, `.claude/skills/query-wiki/SKILL.md`, `.claude/skills/lint-wiki/SKILL.md`

**Interfaces:**
- Consumes: `skill_router.validate_description` (Task 1), `system_sync.SYSTEM_SKILLS_DIR` (`system_sync.py:52`).

**Lưu ý:** KHÔNG đụng `brains/Brain Default/skills/tao-anh-minh-hoa-2d/SKILL.md`. Nó 139 ký tự, đã dưới trần, và mở đầu "Dùng khi cần" không phải boilerplate bị cấm.

- [ ] **Step 1: Viết lint thất bại**

Thêm `import system_sync  # noqa: E402` cạnh `import skill_router` ở đầu `server/test_skill_caps.py`, rồi thêm khối này TRƯỚC `if _fails:`:

```python
# ---- LINT: mọi skill HỆ THỐNG phải lọt trần + sạch boilerplate ----
# Đây là rào chặn tái phát: bug cắt cụt description không được quay lại qua skill ship kèm app.
# Dùng system_sync.SYSTEM_SKILLS_DIR chứ không hardcode đường dẫn; và KHÔNG rglob toàn repo
# (sẽ dính bản mirror trong brains/ và .claude/worktrees/).
_sys_dir = system_sync.SYSTEM_SKILLS_DIR
check("tìm thấy thư mục skill hệ thống", _sys_dir.is_dir())
for _slug in sorted(system_sync.system_skill_slugs()):
    _f = _sys_dir / _slug / "SKILL.md"
    _meta, _ = skill_router.split_frontmatter(_f.read_text(encoding="utf-8"))
    _desc = _meta.get("description", "") or ""
    _err = skill_router.validate_description(_desc)
    check(f"skill hệ thống '{_slug}' description hợp lệ ({len(_desc)} ký tự)"
          + (f" → {_err}" if _err else ""), _err is None)
```

- [ ] **Step 2: Chạy lint, xác nhận nó bắt đúng 5 skill**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL, liệt kê ĐỦ 5 dòng (không dừng ở cái đầu, vì dùng `check` chứ không dùng bare assert): `html-to-webcake` (376 ký tự), `javis-builder` (333), `ingest-source` (266), `query-wiki` (249), `lint-wiki` (213).

- [ ] **Step 3: Viết lại description + thêm mục "Khi nào dùng"**

Với MỖI file dưới đây: thay dòng `description:` trong frontmatter, rồi chèn mục `## Khi nào dùng` vào thân file ngay SAU tiêu đề H1, chứa đúng các ví dụ trigger vừa bị lấy ra khỏi description. Không mất thông tin, chỉ đổi chỗ.

`.claude/skills/html-to-webcake/SKILL.md` (69 ký tự):
```yaml
description: Chuyển HTML sang file Webcake .pke để tải lên Webcake chỉnh sửa tiếp.
```
```markdown
## Khi nào dùng

Kích hoạt khi người dùng nói những câu như: "chuyển file html này sang webcake",
"đổi html thành pke", "tạo file webcake từ html", "làm landing này thành file sửa được
trên webcake", "html to webcake", "convert html sang webcake".

Việc skill làm: đọc HTML, tái dựng thành page_source đúng khuôn Webcake rồi xuất .pke.
```

`.claude/skills/javis-builder/SKILL.md` (110 ký tự):
```yaml
description: Tạo hoặc sửa năng lực của Jarvis 007: agent, skill, workflow, loop, plugin. Kèm mẫu file chuẩn và luật chống trùng.
```
```markdown
## Khi nào dùng

Kích hoạt khi người dùng nói những câu như: "tạo agent chuyên X", "thêm kỹ năng Y",
"dựng workflow nghiên cứu rồi viết", "tạo loop mỗi 2 tiếng làm Z", "viết tool/plugin
tính ...", "làm cho Jarvis 007 biết làm ...".
```
LƯU Ý: `description` này chứa dấu hai chấm. YAML sẽ hiểu nhầm thành mapping. PHẢI bọc cả giá trị trong nháy kép:
```yaml
description: "Tạo hoặc sửa năng lực của Jarvis 007: agent, skill, workflow, loop, plugin. Kèm mẫu file chuẩn và luật chống trùng."
```

`.claude/skills/ingest-source/SKILL.md` (81 ký tự):
```yaml
description: Tiêu hoá một source thô vào Second Brain, chưng cất thành tri thức wiki tích luỹ.
```
```markdown
## Khi nào dùng

Kích hoạt khi người dùng nói những câu như: "tiêu hoá source này", "xử lý bài này vào
wiki", "đọc file này rồi ghi lại kiến thức", hoặc khi có file mới thả vào `sources/`.

Skill làm theo đúng 3 kỷ luật của vault.
```

`.claude/skills/query-wiki/SKILL.md` (91 ký tự) - nhớ bọc nháy kép vì có dấu hai chấm:
```yaml
description: "Khai thác tri thức trong Second Brain: tổng hợp, so sánh, giả thuyết. Trả lời có trích dẫn."
```
```markdown
## Khi nào dùng

Kích hoạt khi người dùng hỏi/khai thác tri thức trong Second Brain, vd "tổng hợp các
framework về X", "so sánh A vs B vs C", "wiki có gì về Y".

Năm kiểu khai thác: tổng hợp, so sánh, giả thuyết, liệt kê, trực quan hoá. Luôn trả lời
có trích dẫn và lưu lại kết quả giá trị.
```

`.claude/skills/lint-wiki/SKILL.md` (88 ký tự):
```yaml
description: Rà soát sức khoẻ wiki của Second Brain, trả về danh sách vấn đề. Không tự sửa hàng loạt.
```
```markdown
## Khi nào dùng

Kích hoạt khi người dùng nói những câu như: "health check wiki", "lint wiki", "wiki có
lỗi gì không", "rà soát bộ não".
```

- [ ] **Step 4: Chạy lint, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS. Cả 5 dòng `skill hệ thống '<slug>' description hợp lệ` đều `ok`.

- [ ] **Step 5: Xác minh YAML không vỡ vì dấu hai chấm**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router, system_sync
for s in sorted(system_sync.system_skill_slugs()):
    f = system_sync.SYSTEM_SKILLS_DIR / s / 'SKILL.md'
    m, _ = skill_router.split_frontmatter(f.read_text(encoding='utf-8'))
    print(s, '|', type(m.get('description')).__name__, '|', (m.get('description') or '')[:50])
"
```
Expected: mọi dòng in `str` (KHÔNG phải `dict`). Nếu ra `dict` thì description có dấu hai chấm chưa được bọc nháy kép.

- [ ] **Step 6: Commit**

```bash
git add server/test_skill_caps.py .claude/skills/
git commit -m "fix(skill): viet lai 5 description he thong cho lot tran 150 + lint CI chan tai phat"
```

---

### Task 4: javis-builder - sửa đường dẫn canonical + nhúng chuẩn viết skill

**Files:**
- Modify: `.claude/skills/javis-builder/SKILL.md:23-24`, `:38`, `:54`, chèn sau `:62`

**Interfaces:** không có. Task này thuần tài liệu, nhưng nó là NỬA CÒN LẠI của spec mục B3 (nửa kia là prompt learn ở Task 7). Thiếu nó thì skill tạo qua chat vẫn vô định hình.

**Phụ thuộc:** làm SAU Task 3 (Task 3 đã viết lại `description` của chính file này).

`javis-builder` đang dạy ghi skill vào `.claude/skills/`, nhưng đó là bản MIRROR phái sinh. Canonical là `skills/<slug>/SKILL.md` (xem `skill_router.py:6` và `CLAUDE.md:245`). Sai ở 3 chỗ, phải sửa cả ba kẻo file tự mâu thuẫn.

- [ ] **Step 1: Sửa dòng 54**

Đổi:
```markdown
### Skill -> `.claude/skills/<slug>/SKILL.md`
```
thành:
```markdown
### Skill -> `skills/<slug>/SKILL.md`
```
(canonical phẳng; Jarvis 007 tự mirror sang `.claude/skills` cho Claude Code nạp native)

- [ ] **Step 2: Sửa dòng 23-24**

Đổi:
```markdown
3. **Chống trùng.** TRƯỚC khi tạo, đọc folder tương ứng (agents/ workflows/ .claude/skills/
   loops/). Nếu đã có cái gần giống -> cập nhật cái cũ, đừng đẻ bản sao.
```
thành:
```markdown
3. **Chống trùng.** TRƯỚC khi tạo, đọc folder tương ứng (agents/ workflows/ skills/
   loops/). Nếu đã có cái gần giống -> cập nhật cái cũ, đừng đẻ bản sao.
```

- [ ] **Step 3: Sửa dòng 38**

Đổi:
```markdown
skills: [slug-skill]      # [] nếu chưa gán; chỉ gán skill đã có trong .claude/skills
```
thành:
```markdown
skills: [slug-skill]      # [] nếu chưa gán; chỉ gán skill đã có trong skills/
```

- [ ] **Step 4: Nhúng CHUẨN VIẾT SKILL vào javis-builder**

Spec mục B3 yêu cầu bộ chuẩn có ở CẢ HAI nơi sinh skill: prompt learn (Task 7) và javis-builder (đây). Thiếu một nơi thì skill tạo qua chat vẫn ra vô định hình.

Trong `.claude/skills/javis-builder/SKILL.md`, ngay SAU khối template Skill (kết thúc ở dòng 62 với dấu ``` đóng), chèn:

```markdown
#### Chuẩn viết skill (bắt buộc, server sẽ CHẶN nếu vi phạm)

1. `description` **TỐI ĐA 150 ký tự**. Router cắt đúng ở đó (`skill_router.SKILL_DESC_MAX`)
   ở cả system prompt lẫn mô tả tool, nên viết dài hơn là phần đuôi MẤT IM LẶNG và skill
   không route được. Viết xong hãy ĐẾM, đừng ước lượng. `POST /skills` trả 400 nếu vượt.
2. `description` nêu THẲNG năng lực. KHÔNG mở đầu bằng "Kích hoạt khi...", "Sử dụng skill
   này khi..." - mọi skill đều mở như vậy nên nó đốt 29 ký tự mà không phân biệt gì.
   Tốt: `Chuyển HTML sang file Webcake .pke.` Xấu: `Kích hoạt khi người dùng muốn chuyển...`
3. `description` có dấu hai chấm thì phải bọc cả giá trị trong nháy kép, kẻo YAML hiểu
   nhầm thành mapping.
4. Ví dụ trigger đầy đủ đưa vào THÂN file, mục `## Khi nào dùng` - nơi không bị cắt và chỉ
   đọc khi skill đã nạp. Index để TÌM, thân file để LÀM.
5. Thứ tự mục trong thân: `## Khi nào dùng` / `## Chuẩn bị` / `## Cách chạy` /
   `## Quy trình` / `## Bẫy` / `## Kiểm chứng`. Mục nào không có nội dung thật thì bỏ,
   đừng bịa cho đủ.
6. KHÔNG bịa flag, đường dẫn, API chưa thấy trong nguồn. Không thấy thì đừng viết.
7. Thân file khoảng 100 dòng cho skill đơn giản, 200 cho skill phức tạp. Dài hơn thì tách
   nội dung xuống `skills/<slug>/references/<chủ-đề>.md`, script xuống
   `skills/<slug>/scripts/`, và trỏ tới bằng đường dẫn tương đối.
8. KHÔNG viết skill kiểu router chỉ trỏ sang skill khác.
```

- [ ] **Step 5: Xác minh không còn tham chiếu sai**

Run: `grep -n "\.claude/skills" .claude/skills/javis-builder/SKILL.md`
Expected: chỉ còn các dòng NÓI VỀ mirror (nếu có), không còn dòng nào bảo GHI vào đó. Nếu grep trả rỗng thì cũng đạt.

- [ ] **Step 6: Chạy lint để chắc không vỡ frontmatter**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS. Đặc biệt dòng `skill hệ thống 'javis-builder' description hợp lệ` phải `ok` - Task 3 đã viết lại description của chính file này, Step 4 ở đây chỉ thêm vào THÂN nên không được làm nó vượt trần trở lại.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/javis-builder/SKILL.md
git commit -m "fix(docs): javis-builder tro dung canonical skills/ + nhung chuan viet skill"
```

---

### Task 5: CLAUDE.md thôi dạy viết description dài

**Files:**
- Modify: `CLAUDE.md:249`, chèn thêm 1 bullet sau `:253`

**Interfaces:** không có. Thuần tài liệu.

- [ ] **Step 1: Sửa mẫu frontmatter**

Trong `CLAUDE.md:249`, đổi:
```yaml
description: <mô tả NGẮN, quyết định KHI NÀO skill được kích hoạt - viết rõ trigger>
```
thành:
```yaml
description: <nêu THẲNG năng lực, TỐI ĐA 150 ký tự - vd "Chuyển HTML sang file Webcake .pke.">
```

- [ ] **Step 2: Thêm bullet luật trần**

Ngay SAU dòng 253 (dấu ``` đóng khối) và TRƯỚC bullet "Tự phân nhóm (group)" ở dòng 254, chèn:

```markdown
- **`description` TỐI ĐA 150 ký tự - đây KHÔNG phải chuyện thẩm mỹ.** Router cắt đúng ở 150
  (`skill_router.SKILL_DESC_MAX`) ở cả system prompt lẫn mô tả tool, nên viết dài hơn là phần
  đuôi MẤT IM LẶNG và skill không route được. Viết xong hãy ĐẾM. Nêu thẳng năng lực, KHÔNG mở
  đầu bằng cụm sáo rỗng kiểu "Kích hoạt khi người dùng muốn..." (mọi skill đều mở như vậy nên
  nó đốt 29 ký tự mà không phân biệt gì). Ví dụ trigger đầy đủ đưa xuống mục `## Khi nào dùng`
  trong THÂN file, nơi không bị cắt và chỉ được đọc khi skill đã nạp. Index để TÌM, thân file
  để LÀM.
```

- [ ] **Step 3: Xác minh không có em dash lọt vào**

Run: `cd "D:/Project/Javis-OS" && ./.venv/Scripts/python.exe -c "import pathlib; t=pathlib.Path('CLAUDE.md').read_text(encoding='utf-8'); print('em dash:', t.count(chr(8212)))"`
Expected: `em dash: 0`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): neu ro tran 150 ky tu cho description skill kem ly do"
```

---

### Task 6: POST /skills ép chuẩn lúc ghi

**Files:**
- Modify: `server/main.py:2213-2238`
- Test: `server/test_skill_caps.py`

**Interfaces:**
- Consumes: `skill_router.validate_description` (Task 1).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_caps.py` trước `if _fails:`:

```python
# ---- POST /skills phải ép trần TRƯỚC khi tạo thư mục ----
# Mốc kết thúc là /skills/delete (main.py:2241) chứ KHÔNG phải /skills/toggle: toggle nằm ở
# dòng 2161, TRƯỚC save_skill (2214), nên dùng nó làm mốc sau sẽ ném ValueError.
_save = _region("main.py", "async def save_skill", '@app.post("/skills/delete")')
check("POST /skills gọi validate_description", "validate_description" in _save)
check("POST /skills ép TRƯỚC khi mkdir",
      _save.index("validate_description") < _save.index("d.mkdir("))
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL với `POST /skills gọi validate_description`.

- [ ] **Step 3: Thêm kiểm tra vào endpoint**

Trong `server/main.py`, ngay SAU khối kiểm tra slug (dòng 2219-2220):

```python
    if not skill_router.valid_slug(slug):
        return JSONResponse({"error": "Tên skill không hợp lệ"}, status_code=400)
```

chèn:

```python
    # Ép trần description NGAY, trước khi tạo bất cứ thư mục nào → request bị từ chối không
    # để lại folder skill rỗng trên đĩa. Router cắt ở SKILL_DESC_MAX nên vượt trần = mất chữ
    # im lặng; chặn ở đây tốt hơn là ghi bừa rồi để runtime cắt.
    desc_err = skill_router.validate_description(description)
    if desc_err:
        return JSONResponse({"error": desc_err}, status_code=400)
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 5: Xác minh thủ công không tạo folder rác khi bị từ chối**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router
print(skill_router.validate_description('x'*200)[:60])
print('rong ->', skill_router.validate_description(''))
"
```
Expected: dòng 1 in lý do từ chối có chứa `200`; dòng 2 in `rong -> None`.

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/test_skill_caps.py
git commit -m "feat(skill): POST /skills tu choi description vuot tran hoac sao rong"
```

---

### Task 7: learn.py ép chuẩn + nhúng bộ chuẩn vào prompt

**Files:**
- Modify: `server/learn.py:156` (hằng số), `:356-359` (schema), `_build_prompt` (chèn khối chuẩn), `:544-568` (ép trần)
- Test: `server/test_skill_caps.py`

**Interfaces:**
- Consumes: `skill_router.SKILL_DESC_MAX`, `skill_router.validate_description` (Task 1). `learn.py:35` đã có `import skill_router`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_caps.py` trước `if _fails:`:

```python
# ---- learn.py: chuẩn viết skill vào prompt + ép trần lúc promote ----
_learn = (_SRC / "learn.py").read_text(encoding="utf-8")
check("learn.py nhúng chuẩn viết skill vào prompt", "CHUẨN VIẾT SKILL" in _learn)
check("learn.py nội suy SKILL_DESC_MAX vào prompt (không hardcode số)",
      "SKILL_DESC_MAX" in _learn)
check("learn.py ép trần description khi promote",
      "validate_description" in _learn)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: FAIL cả 3 dòng `learn.py ...`.

- [ ] **Step 3: Mở rộng schema skill trong `_build_prompt`**

Trong `server/learn.py`, đổi khối dòng 356-359 từ:

```python
        if caps.get("skill"):
            schema_bits.append(
                '"skills":[{"slug":"kebab","name":"..","description":"khi nào dùng","body":"quy trình các bước",'
                '"self_observed":true|false,"confidence":0..3}]')
```

thành:

```python
        if caps.get("skill"):
            schema_bits.append(
                '"skills":[{"slug":"kebab","name":"..",'
                f'"description":"năng lực, TỐI ĐA {skill_router.SKILL_DESC_MAX} ký tự",'
                '"group":"tên nhóm","body":"markdown theo CHUẨN VIẾT SKILL bên dưới",'
                '"self_observed":true|false,"confidence":0..3}]')
```

- [ ] **Step 4: Chèn khối CHUẨN VIẾT SKILL vào prompt**

Trong `server/learn.py`, trong `return (...)` của `_build_prompt`, chèn NGAY TRƯỚC dòng
`+ ("TASK (chống spam backlog): ...` (dòng 386), theo đúng thành ngữ fragment-có-điều-kiện
đã dùng ở đó:

```python
            + (f"CHUẨN VIẾT SKILL (bắt buộc, Python sẽ CHẶN nếu vi phạm):\n"
               f"  1. description TỐI ĐA {skill_router.SKILL_DESC_MAX} ký tự. Router cắt "
               f"đúng ở đó nên phần dư MẤT IM LẶNG và skill không route được. VIẾT XONG HÃY "
               "ĐẾM, đừng ước lượng.\n"
               "  2. description nêu THẲNG năng lực. KHÔNG mở đầu bằng 'Kích hoạt khi...', "
               "'Sử dụng skill này khi...' - mọi skill đều mở như vậy nên nó đốt ngân sách mà "
               "không phân biệt gì. Tốt: 'Chuyển HTML sang file Webcake .pke.'\n"
               "  3. Ví dụ trigger đầy đủ đưa vào body, mục '## Khi nào dùng' - KHÔNG nhét "
               "vào description.\n"
               "  4. body theo thứ tự mục: '## Khi nào dùng' / '## Chuẩn bị' / '## Cách chạy' "
               "/ '## Quy trình' / '## Bẫy' / '## Kiểm chứng'. Mục nào không có nội dung thật "
               "thì bỏ, đừng bịa.\n"
               "  5. KHÔNG bịa flag, đường dẫn, API chưa thấy trong hội thoại. Không thấy thì "
               "đừng viết.\n"
               "  6. body khoảng 100 dòng cho skill đơn giản, 200 cho skill phức tạp.\n"
               "  7. KHÔNG tạo skill kiểu router chỉ trỏ sang skill khác.\n"
               "  8. group BẮT BUỘC, chọn nhóm sát nhất với skill đã có.\n\n"
               if caps.get("skill") else "")
```

- [ ] **Step 5: Ép trần lúc promote**

Trong `server/learn.py`, trong khối SKILLS của `_promote_sync`, đổi dòng 549-550 từ:

```python
                    slug = _slugify(s.get("slug") or s.get("name") or "")
                    body = (s.get("body") or "").strip()
```

thành:

```python
                    slug = _slugify(s.get("slug") or s.get("name") or "")
                    body = (s.get("body") or "").strip()
                    desc = (s.get("description") or "").strip()
```

Rồi NGAY SAU khối secret/injection (dòng 553-554):

```python
                    if secret_hits(body) or injection_in_output(body):
                        rep["blocked"].append(f"skill '{slug}': nội dung không an toàn"); continue
```

chèn:

```python
                    # Ép CHUẨN VIẾT SKILL: prompt đã dặn, nhưng fork có thể phớt lờ → chặn ở
                    # Python (người ghi tin cậy duy nhất), cùng thành ngữ với secret/injection.
                    desc_err = skill_router.validate_description(desc)
                    if desc_err:
                        rep["blocked"].append(f"skill '{slug}': {desc_err}"); continue
```

Và đổi dòng 564-565 (frontmatter) từ:

```python
                    fm = (f"---\nname: {s.get('name', slug)}\ndescription: {s.get('description','')}\n"
                          f"origin: javis-learned\nstatus: active\ncreated: {today}\n---\n")
```

thành:

```python
                    fm = (f"---\nname: {s.get('name', slug)}\ndescription: {desc}\n"
                          f"group: {s.get('group') or 'Chung'}\n"
                          f"origin: javis-learned\nstatus: active\ncreated: {today}\n---\n")
```

- [ ] **Step 6: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_caps.py`
Expected: PASS.

- [ ] **Step 7: Xác minh learn.py vẫn import được (bắt lỗi cú pháp f-string)**

Run: `cd server && ../.venv/Scripts/python.exe -c "import py_compile; py_compile.compile('learn.py', doraise=True); print('learn.py compile OK')"`
Expected: `learn.py compile OK`

- [ ] **Step 8: Commit**

```bash
git add server/learn.py server/test_skill_caps.py
git commit -m "feat(learn): nhung chuan viet skill vao prompt + chan description vuot tran"
```

---

### Task 8: skill_usage.py - sidecar telemetry

**Files:**
- Create: `server/skill_usage.py`
- Test: `server/test_skill_usage.py` (tạo mới)

**Interfaces:**
- Produces:
  - `skill_usage.SKILL_STALE_AFTER_DAYS: int` = 30
  - `skill_usage.usage_path(brain_root) -> Path` = `<brain_root>/Javis/skill-usage.json`
  - `skill_usage.read_usage(brain_root) -> dict` - `{slug: {use_count, last_used_at, first_used_at, created_at, created_by, pinned}}`. Lỗi/thiếu/hỏng → `{}`.
  - `skill_usage.bump(brain_root, slug) -> None` - best-effort, không bao giờ raise.
  - `skill_usage.is_stale(rec: dict, skill_md_mtime: Optional[float], now: float) -> bool`
- Task 9 (bump ở hub) và Task 10 (GET /skills) dùng.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_skill_usage.py`:

```python
"""Test sidecar telemetry skill (skill_usage). Chạy tay / CI:

    cd server && ../.venv/Scripts/python.exe test_skill_usage.py

Không cần pytest, không chạm mạng. Tự cô lập sang thư mục tạm.
Phủ: bump tăng đúng, ghi atomic, file thiếu, file JSON hỏng, gọi song song,
is_stale (pinned / có use_count / chưa đủ già / đủ già).
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-usagetest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import skill_usage  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_ROOT = Path(tempfile.mkdtemp(prefix="javis-usagebrain-"))

# ---- file thiếu ----
check("brain chưa có sidecar → read_usage trả {}", skill_usage.read_usage(_ROOT) == {})

# ---- bump ----
skill_usage.bump(_ROOT, "viet-email")
u = skill_usage.read_usage(_ROOT)
check("bump lần 1 tạo bản ghi", "viet-email" in u)
check("bump lần 1 → use_count = 1", u.get("viet-email", {}).get("use_count") == 1)
check("bump lần 1 đặt created_at", u.get("viet-email", {}).get("created_at"))
check("bump lần 1 đặt first_used_at", u.get("viet-email", {}).get("first_used_at"))

skill_usage.bump(_ROOT, "viet-email")
u = skill_usage.read_usage(_ROOT)
check("bump lần 2 → use_count = 2", u.get("viet-email", {}).get("use_count") == 2)

skill_usage.bump(_ROOT, "skill-khac")
u = skill_usage.read_usage(_ROOT)
check("bump slug khác không đè slug cũ", u.get("viet-email", {}).get("use_count") == 2)
check("bump slug khác tạo bản ghi riêng", u.get("skill-khac", {}).get("use_count") == 1)

# ---- đúng vị trí ----
check("sidecar nằm ở Javis/skill-usage.json",
      skill_usage.usage_path(_ROOT) == _ROOT / "Jarvis 007" / "skill-usage.json")
check("sidecar thật sự tồn tại trên đĩa", skill_usage.usage_path(_ROOT).is_file())

# ---- file hỏng: KHÔNG được làm gãy ----
skill_usage.usage_path(_ROOT).write_text("{ day khong phai json", encoding="utf-8")
check("sidecar hỏng → read_usage trả {} chứ không raise", skill_usage.read_usage(_ROOT) == {})
try:
    skill_usage.bump(_ROOT, "viet-email")
    check("sidecar hỏng → bump không raise", True)
except Exception as e:
    check(f"sidecar hỏng → bump không raise (raised {e!r})", False)

# ---- không có quyền ghi / đường dẫn vô lý: vẫn không raise ----
try:
    skill_usage.bump(Path("/khong/ton/tai/o/dau/ca"), "x")
    check("brain không tồn tại → bump không raise", True)
except Exception as e:
    check(f"brain không tồn tại → bump không raise (raised {e!r})", False)

# ---- gọi song song ----
import threading  # noqa: E402

_R2 = Path(tempfile.mkdtemp(prefix="javis-usagepar-"))


def _hammer():
    for _ in range(20):
        skill_usage.bump(_R2, "dua-xe")


_ts = [threading.Thread(target=_hammer) for _ in range(4)]
[t.start() for t in _ts]
[t.join() for t in _ts]
_n = skill_usage.read_usage(_R2).get("dua-xe", {}).get("use_count", 0)
check(f"4 luồng x 20 bump → sidecar còn đọc được, use_count={_n} (>0, <=80)", 0 < _n <= 80)

# ---- is_stale ----
_now = time.time()
_old = _now - 40 * 86400
_new = _now - 3 * 86400

check("pinned → không bao giờ stale",
      skill_usage.is_stale({"use_count": 0, "created_at": _old, "pinned": True}, None, _now) is False)
check("có use_count > 0 → không bao giờ stale",
      skill_usage.is_stale({"use_count": 5, "created_at": _old, "pinned": False}, None, _now) is False)
check("use=0 nhưng mới tạo → chưa stale",
      skill_usage.is_stale({"use_count": 0, "created_at": _new, "pinned": False}, None, _now) is False)
check("use=0 + đủ già → stale",
      skill_usage.is_stale({"use_count": 0, "created_at": _old, "pinned": False}, None, _now) is True)
check("không có bản ghi + mtime cũ → stale (fallback mtime)",
      skill_usage.is_stale({}, _old, _now) is True)
check("không có bản ghi + mtime mới → chưa stale",
      skill_usage.is_stale({}, _new, _now) is False)
check("không có bản ghi + không có mtime → không stale (không đủ căn cứ)",
      skill_usage.is_stale({}, None, _now) is False)

if _fails:
    print(f"\nFAIL - test_skill_usage: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_skill_usage: tất cả pass")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL với `ModuleNotFoundError: No module named 'skill_usage'`.

- [ ] **Step 3: Viết module**

Tạo `server/skill_usage.py`:

```python
"""
skill_usage.py - Sidecar TELEMETRY cho skill: đo skill nào THẬT SỰ được dùng.

Vị trí: <brain>/Javis/skill-usage.json. Đặt cạnh Javis/loop-state.json theo đúng quy ước
đã có của Jarvis 007 ("STATE runtime tách riêng, server sở hữu" - xem self_improve.py). KHÔNG
nhét vào frontmatter SKILL.md: brain là git repo, mỗi lần dùng skill sẽ đẻ một commit rác
và tạo áp lực xung đột lên file do người viết.

⚠ TÍN HIỆU DƯƠNG MỘT CHIỀU. Bộ đếm chỉ bump ở tool javis_use_skill (mcp_hub). Claude Code
nạp skill NATIVE qua bản mirror <brain>/.claude/skills KHÔNG đi qua đó, nên:
  - use_count > 0  → skill CHẮC CHẮN có dùng.
  - use_count == 0 → KHÔNG có bằng chứng. TUYỆT ĐỐI không suy ra "vô dụng", không tự tắt,
    không tự archive. Nhãn stale chỉ để hiển thị tham khảo cho người, người tự quyết.

Mọi hàm BEST-EFFORT: sidecar thiếu/hỏng/không ghi được thì trả rỗng và đi tiếp. Sidecar
hỏng KHÔNG BAO GIỜ được làm gãy lời gọi skill.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# Skill chưa có tín hiệu dùng nào và đã quá ngần này ngày thì gắn nhãn "chưa thấy dùng".
# Ngưỡng rộng tay có chủ đích: skill mới đơn giản là chưa gặp trigger (luật của Hermes).
SKILL_STALE_AFTER_DAYS = 30

_LOCK = threading.Lock()   # serialize read-modify-write trong process


def usage_path(brain_root) -> Path:
    return Path(brain_root) / "Jarvis 007" / "skill-usage.json"


def read_usage(brain_root) -> dict:
    """{slug: {...}}. Thiếu file / JSON hỏng / lỗi đọc → {} (không raise)."""
    try:
        p = usage_path(brain_root)
        if not p.is_file():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_atomic(p: Path, text: str) -> None:
    """Ghi atomic: .tmp cạnh đích rồi os.replace (cùng ổ đĩa → rename nguyên tử)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".skill-usage-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def bump(brain_root, slug: str, created_by: str = "") -> None:
    """Đếm 1 lần dùng skill. BEST-EFFORT: nuốt mọi lỗi, chỉ log stderr.
    Gọi ở ĐIỂM THÀNH CÔNG của handler _skill (mcp_hub) - không gọi khi slug sai."""
    slug = str(slug or "").strip()
    if not slug:
        return
    try:
        now = time.time()
        with _LOCK:
            data = read_usage(brain_root)
            rec = data.get(slug)
            if not isinstance(rec, dict):
                rec = {"use_count": 0, "created_at": now, "created_by": created_by,
                       "first_used_at": None, "last_used_at": None, "pinned": False}
            rec["use_count"] = int(rec.get("use_count", 0) or 0) + 1
            rec["last_used_at"] = now
            if not rec.get("first_used_at"):
                rec["first_used_at"] = now
            if not rec.get("created_at"):
                rec["created_at"] = now
            data[slug] = rec
            _write_atomic(usage_path(brain_root),
                          json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[skill usage] bump {slug}: {type(e).__name__}: {e}", file=sys.stderr)


def is_stale(rec: dict, skill_md_mtime: Optional[float], now: Optional[float] = None) -> bool:
    """Hàm THUẦN. True = "chưa thấy dùng và đã đủ già" - CHỈ để hiển thị, KHÔNG để tự tắt.

    Luật:
      - pinned → không bao giờ stale.
      - use_count > 0 → không bao giờ stale, BẤT KỂ last_used_at cũ đến đâu (điểm mù native
        khiến last_used_at không đủ tin làm căn cứ phủ định).
      - Không có created_at (skill có từ trước khi có tính năng này) → fallback mtime của
        SKILL.md. Không có cả mtime → False (không đủ căn cứ thì không phán).
    """
    now = time.time() if now is None else now
    rec = rec if isinstance(rec, dict) else {}
    if rec.get("pinned"):
        return False
    if int(rec.get("use_count", 0) or 0) > 0:
        return False
    born = rec.get("created_at") or skill_md_mtime
    if not born:
        return False
    return (now - float(born)) > SKILL_STALE_AFTER_DAYS * 86400
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS, in `OK - test_skill_usage: tất cả pass`.

- [ ] **Step 5: Commit**

```bash
git add server/skill_usage.py server/test_skill_usage.py
git commit -m "feat(skill): sidecar telemetry Javis/skill-usage.json (tin hieu duong mot chieu)"
```

---

### Task 9: Bump ở điểm nghẽn duy nhất trong mcp_hub

**Files:**
- Modify: `server/mcp_hub.py:237-245`
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Consumes: `skill_usage.bump` (Task 8).

**Ràng buộc:** `_skill` là `async` và chạy TRÊN event loop. `bump` có I/O đĩa. Skill dir nhỏ và ghi rất thưa (chỉ khi nạp skill) nên chấp nhận ghi đồng bộ; KHÔNG được để `bump` raise (nó đã nuốt lỗi).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_usage.py` trước `if _fails:`:

```python
# ---- mcp_hub bump đúng chỗ: CHỈ ở đường thành công ----
_hub = (Path(os.path.dirname(os.path.abspath(__file__))) / "mcp_hub.py").read_text(encoding="utf-8")
check("mcp_hub import skill_usage", "import skill_usage" in _hub)
check("mcp_hub gọi skill_usage.bump", "skill_usage.bump" in _hub)
_i_err = _hub.index('ERROR: không có skill đó')
_i_bump = _hub.index("skill_usage.bump")
check("bump nằm SAU nhánh trả lỗi slug sai (không đếm gõ nhầm)", _i_bump > _i_err)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL với `mcp_hub import skill_usage` và `mcp_hub gọi skill_usage.bump`.

- [ ] **Step 3: Thêm import**

Trong `server/mcp_hub.py`, cạnh `import skill_router` (dòng 27), thêm:

```python
import skill_usage
```

- [ ] **Step 4: Bump ở điểm thành công**

Trong `server/mcp_hub.py`, đổi dòng 245 từ:

```python
        return f.read_text(encoding="utf-8", errors="replace")[:60_000]
```

thành:

```python
        text = f.read_text(encoding="utf-8", errors="replace")[:60_000]
        # ĐIỂM ĐẾM DUY NHẤT: mọi engine nạp skill qua tool này đều đi ngang đây. Chỉ đếm ở
        # đường THÀNH CÔNG - nhánh trên đã lọc slug sai/skill tắt nên không đếm gõ nhầm.
        # Dùng f.parent.name (slug canonical trên đĩa) chứ không dùng `name` thô từ engine.
        # bump tự nuốt lỗi → sidecar hỏng không bao giờ làm gãy việc nạp skill.
        skill_usage.bump(vault_root, f.parent.name)
        return text
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 6: Xác minh mcp_hub vẫn import được**

Run: `cd server && ../.venv/Scripts/python.exe -c "import py_compile; py_compile.compile('mcp_hub.py', doraise=True); print('mcp_hub compile OK')"`
Expected: `mcp_hub compile OK`

- [ ] **Step 7: Commit**

```bash
git add server/mcp_hub.py server/test_skill_usage.py
git commit -m "feat(skill): dem luot dung tai handler javis_use_skill"
```

---

### Task 10: GET /skills lộ usage + dashboard hiển thị

**Files:**
- Modify: `server/main.py:2144-2152`
- Modify: `dashboard/studio.js:463-477`
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Consumes: `skill_usage.read_usage`, `skill_usage.is_stale` (Task 8).
- Produces: mỗi item của `GET /skills` có thêm `use_count: int`, `last_used_at: float|None`, `stale: bool`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_usage.py` trước `if _fails:`:

```python
# ---- GET /skills lộ usage ----
_main = (Path(os.path.dirname(os.path.abspath(__file__))) / "main.py").read_text(encoding="utf-8")
_list = _main[_main.index('@app.get("/skills")'):_main.index('def _skills_dir')]
check("GET /skills đọc usage", "read_usage" in _list)
check("GET /skills tính stale", "is_stale" in _list)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL cả 2 dòng `GET /skills ...`.

- [ ] **Step 3: Thêm import vào main.py**

Trong `server/main.py`, cạnh `import skill_router` (dòng 43), thêm:

```python
import skill_usage
```

- [ ] **Step 4: Mở rộng endpoint**

Trong `server/main.py`, đổi thân `GET /skills` (dòng 2149-2152) từ:

```python
    root = _brain_root(brain)
    sys_slugs = system_sync.system_skill_slugs()   # skill HỆ THỐNG (đi theo phiên bản app)
    out = [{**s, "system": s["slug"] in sys_slugs} for s in skill_router.list_skills(root)]
    return {"skills": out}
```

thành:

```python
    root = _brain_root(brain)
    sys_slugs = system_sync.system_skill_slugs()   # skill HỆ THỐNG (đi theo phiên bản app)
    usage = skill_usage.read_usage(root)           # telemetry (tín hiệu DƯƠNG một chiều)
    now = time.time()

    def _mtime(p):
        try:
            return Path(p).stat().st_mtime
        except OSError:
            return None

    out = []
    for s in skill_router.list_skills(root):
        rec = usage.get(s["slug"]) or {}
        out.append({**s,
                    "system": s["slug"] in sys_slugs,
                    "use_count": int(rec.get("use_count", 0) or 0),
                    "last_used_at": rec.get("last_used_at"),
                    "pinned": bool(rec.get("pinned", False)),
                    # stale = "chưa thấy dùng + đủ già". CHỈ để hiển thị tham khảo: skill nạp
                    # native qua .claude/skills không đi qua bộ đếm nên use=0 KHÔNG có nghĩa
                    # là vô dụng. Không có gì tự tắt dựa trên cờ này.
                    "stale": skill_usage.is_stale(rec, _mtime(s["path"]), now)})
    return {"skills": out}
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 6: Hiển thị ở dashboard**

Trong `dashboard/studio.js`, trong `renderSkillList()`, ngay SAU dòng khai báo `sysBadge` và TRƯỚC `div.innerHTML = ...`, chèn:

```javascript
      // Telemetry: use_count là tín hiệu DƯƠNG một chiều. Skill nạp native qua .claude/skills
      // không đi qua bộ đếm, nên "chưa thấy dùng" là tham khảo, KHÔNG phải phán quyết.
      let usageHtml = "";
      if (s.use_count > 0) {
        const when = s.last_used_at ? new Date(s.last_used_at * 1000).toLocaleDateString("vi-VN") : "";
        usageHtml = ` · <span class="sk-usage">đã dùng ${s.use_count} lần${when ? ", gần nhất " + when : ""}</span>`;
      } else if (s.stale) {
        usageHtml = ` · <span class="sk-usage sk-stale" title="Jarvis 007 chỉ đếm được skill nạp qua tool javis_use_skill. Claude Code nạp native qua .claude/skills thì không đếm được, nên đây chỉ là tham khảo - không có nghĩa skill vô dụng.">chưa thấy dùng</span>`;
      }
```

Rồi trong `div.innerHTML`, đổi dòng `gp` từ:

```javascript
<div class="gp">📂 ${esc(s.group || "Chung")} · ${esc(s.slug)}${s.source === ".agents" ? " · .agents" : ""}</div>
```

thành:

```javascript
<div class="gp">📂 ${esc(s.group || "Chung")} · ${esc(s.slug)}${s.source === ".agents" ? " · .agents" : ""}${usageHtml}</div>
```

LƯU Ý: `usageHtml` KHÔNG bọc `esc()` vì nó là HTML mình tự dựng. Mọi giá trị nội suy vào nó (`s.use_count`, `s.last_used_at`) đều là số do server sinh, không phải chuỗi người dùng nhập, nên không có đường XSS. Đừng nhét `s.name` hay `s.description` vào đây mà không `esc()`.

- [ ] **Step 7: Thêm CSS**

Trong `dashboard/studio.js`, trong chuỗi CSS của `_injectSkillCss()` (dòng 384-409), thêm:

```css
.sk-usage { font-size: 11px; color: var(--muted, #888); margin-left: 8px; }
.sk-stale { opacity: .75; font-style: italic; cursor: help; }
```

- [ ] **Step 8: Kiểm mắt thường**

Mở trang Skill trên dashboard. Expected: skill chưa dùng bao giờ và mới tạo thì không có nhãn gì; skill đã dùng hiện `Đã dùng N lần`. Rê chuột vào `Chưa thấy dùng` thấy tooltip giải thích điểm mù.

- [ ] **Step 9: Commit**

```bash
git add server/main.py dashboard/studio.js server/test_skill_usage.py
git commit -m "feat(skill): GET /skills tra use_count/stale, dashboard hien so luot dung"
```

---

### Task 11: mirror_skills copy cả cây con

**Files:**
- Modify: `server/system_sync.py:235-264`
- Test: `server/test_mirror_tree.py` (tạo mới)

**Interfaces:**
- Produces: `system_sync.skill_tree_hash(d: Path, rel_paths=None) -> str`.

**Ràng buộc phải giữ (đây là task rủi ro cao nhất của plan):**
1. `mirror_skills` KHÔNG được tự lấy `_LOCK`. `sync_brain:356` gọi nó khi ĐANG giữ lock, mà `threading.Lock` (`:280`) không reentrant → deadlock.
2. Add/update-only. KHÔNG xoá gì ở `mirror/<slug>` mà nguồn không có. Việc gỡ mirror do `main.py:2186-2188` (`rmtree`) lo.
3. Bỏ qua `.disabled`.
4. Giữ `(p / "SKILL.md").is_file()` làm cổng vào.
5. **Bẫy digest tập-con:** mirror là add-only nên đích có file THỪA sẽ không bao giờ khớp digest nguồn → copy lại vô hạn mỗi lần gọi (mà hàm này được gọi ở 7 hot path). Digest của ĐÍCH phải tính CHỈ trên tập rel path có ở NGUỒN.
6. **KHÔNG** đưa file nhị phân qua `read_text`/`skill_hash`: `errors="replace"` làm hỏng thầm lặng, và `_norm_text` chuẩn hoá ngày. Dùng sha256 raw bytes cho file không phải `.md`.
7. KHÔNG đổi chữ ký hay ngữ nghĩa của `skill_hash`: `sync_brain:303`, `LEGACY_HASHES:388-405` và CLI `--hash:409-414` phụ thuộc output chính xác của nó.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_mirror_tree.py`:

```python
"""Test mirror_skills copy cả cây con (references/, scripts/). Chạy tay / CI:

    cd server && ../.venv/Scripts/python.exe test_mirror_tree.py

Không cần pytest, không chạm mạng. Tự dựng brain giả trong thư mục tạm.
Phủ: copy thư mục con, đổi references/ thì mirror nhận, bỏ qua .disabled, add-only
(không xoá file lạ ở mirror), không copy lại khi không đổi (chống loop vô hạn).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-mirrortest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import system_sync  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_ROOT = Path(tempfile.mkdtemp(prefix="javis-mirrorbrain-"))
_sk = _ROOT / "skills" / "co-tai-lieu"
(_sk / "references").mkdir(parents=True)
(_sk / "scripts").mkdir(parents=True)
(_sk / "SKILL.md").write_text("---\nname: Có tài liệu\ndescription: Thử cây con.\n---\nthân\n",
                              encoding="utf-8")
(_sk / "references" / "chi-tiet.md").write_text("chi tiết v1\n", encoding="utf-8")
(_sk / "scripts" / "chay.py").write_text("print('hi')\n", encoding="utf-8")
(_sk / "anh.png").write_bytes(b"\x89PNG\r\n\x1a\n binary")

# skill đã TẮT thì không được mirror
_dis = _ROOT / "skills" / ".disabled" / "da-tat"
_dis.mkdir(parents=True)
(_dis / "SKILL.md").write_text("---\nname: Đã tắt\n---\nx\n", encoding="utf-8")

_mir = _ROOT / ".claude" / "skills" / "co-tai-lieu"

system_sync.mirror_skills(_ROOT)
check("mirror có SKILL.md", (_mir / "SKILL.md").is_file())
check("mirror có references/chi-tiet.md", (_mir / "references" / "chi-tiet.md").is_file())
check("mirror có scripts/chay.py", (_mir / "scripts" / "chay.py").is_file())
check("mirror giữ nguyên file nhị phân",
      (_mir / "anh.png").is_file() and (_mir / "anh.png").read_bytes() == b"\x89PNG\r\n\x1a\n binary")
check("KHÔNG mirror skill đã tắt",
      not (_ROOT / ".claude" / "skills" / "da-tat").exists())

# đổi references/ mà KHÔNG đổi SKILL.md → mirror vẫn phải nhận (bug hash-skip cũ)
(_sk / "references" / "chi-tiet.md").write_text("chi tiết v2\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("đổi references/ (SKILL.md không đổi) → mirror nhận bản mới",
      (_mir / "references" / "chi-tiet.md").read_text(encoding="utf-8") == "chi tiết v2\n")

# add-only: file lạ ở mirror KHÔNG bị xoá
(_mir / "nguoi-dung-them.md").write_text("giữ tôi lại\n", encoding="utf-8")
system_sync.mirror_skills(_ROOT)
check("add-only: không xoá file lạ ở mirror", (_mir / "nguoi-dung-them.md").is_file())

# không đổi gì → KHÔNG copy lại (chống copy lại vô hạn dù mirror có file thừa)
# KHÔNG kiểm bằng mtime: shutil.copy2 giữ nguyên mtime của NGUỒN, nên đích luôn có cùng
# mtime dù có copy lại hay không → test kiểu đó xanh kể cả khi code sai. Phải ĐẾM số lần
# copy2 thật sự được gọi. Ở thời điểm này mirror đang có file thừa (nguoi-dung-them.md), nên
# đây đồng thời là test cho bẫy digest-tập-con: digest đích phải tính CHỈ trên rel của nguồn.
import shutil as _sh  # noqa: E402

_copies = []
_orig_copy2 = _sh.copy2


def _spy_copy2(src, dst, *a, **kw):
    _copies.append(str(dst))
    return _orig_copy2(src, dst, *a, **kw)


_sh.copy2 = _spy_copy2
try:
    system_sync.mirror_skills(_ROOT)
    system_sync.mirror_skills(_ROOT)
finally:
    _sh.copy2 = _orig_copy2
check(f"không đổi gì → KHÔNG copy lại lần nào (đếm được {len(_copies)} lượt copy)",
      len(_copies) == 0)

if _fails:
    print(f"\nFAIL - test_mirror_tree: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_mirror_tree: tất cả pass")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_mirror_tree.py`
Expected: FAIL với `mirror có references/chi-tiet.md`, `mirror có scripts/chay.py`, và `đổi references/ ... → mirror nhận bản mới`.

Dòng `không đổi gì → KHÔNG copy lại lần nào` có thể XANH ngay ở bước này dù code chưa sửa (bản cũ skip theo hash SKILL.md nên cũng không copy). Đó là bình thường: dòng đó không phải để bắt lỗi hiện tại, nó là lưới chặn regression cho bản đệ quy ở Step 4, nơi digest sai sẽ gây copy lại vô hạn trên 7 hot path.

- [ ] **Step 3: Thêm `skill_tree_hash`**

Trong `server/system_sync.py`, ngay SAU `skill_hash` (dòng 97-99), thêm:

```python
def skill_tree_hash(d: Path, rel_paths=None) -> str:
    """Digest CẢ CÂY của 1 thư mục skill (SKILL.md + asset + references/ + scripts/...).

    rel_paths=None → băm mọi file có trong d. rel_paths=<list> → CHỈ băm đúng các đường dẫn
    đó (dùng cho bên ĐÍCH: mirror là add-only nên đích có file THỪA là chuyện bình thường;
    băm cả đích sẽ không bao giờ khớp nguồn → copy lại vô hạn mỗi lần gọi).

    File .md băm qua skill_hash (chuẩn hoá CRLF/BOM/ngày như bản gốc). File khác băm sha256
    RAW BYTES - KHÔNG đưa file nhị phân qua read_text (errors='replace' làm hỏng thầm lặng).
    """
    h = hashlib.sha256()
    if rel_paths is None:
        try:
            rel_paths = sorted(p.relative_to(d).as_posix()
                               for p in d.rglob("*") if p.is_file())
        except OSError:
            return ""
    for rel in sorted(rel_paths):
        f = d / rel
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        try:
            if f.suffix.lower() == ".md":
                h.update(skill_hash(f.read_text(encoding="utf-8", errors="replace")).encode())
            else:
                h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
        except OSError:
            h.update(b"<missing>")   # thiếu ở đích → digest khác nguồn → sẽ copy
        h.update(b"\x00")
    return h.hexdigest()
```

- [ ] **Step 4: Viết lại `mirror_skills` cho đệ quy**

Trong `server/system_sync.py`, đổi thân vòng lặp (dòng 249-260) từ:

```python
            try:
                dst_dir = mirror / d.name
                dst = dst_dir / "SKILL.md"
                src_text = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")
                if dst.is_file():
                    cur = dst.read_text(encoding="utf-8", errors="replace")
                    if skill_hash(cur) == skill_hash(src_text):
                        continue   # đã trùng nội dung → khỏi ghi lại
                dst_dir.mkdir(parents=True, exist_ok=True)
                for f in d.iterdir():   # SKILL.md + file phụ (asset) cùng thư mục skill
                    if f.is_file():
                        shutil.copy2(str(f), str(dst_dir / f.name))
            except Exception as e:
                print(f"[skill mirror] {d.name}: {type(e).__name__}: {e}", file=sys.stderr)
```

thành:

```python
            try:
                dst_dir = mirror / d.name
                # Tập file NGUỒN, đệ quy (SKILL.md + asset + references/ + scripts/ + templates/).
                rels = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
                if not rels:
                    continue
                # So digest CẢ CÂY. Đích chỉ băm trên ĐÚNG tập rel của nguồn → file lạ ở mirror
                # (add-only) không làm digest lệch vĩnh viễn gây copy lại vô hạn.
                if dst_dir.is_dir() and skill_tree_hash(d, rels) == skill_tree_hash(dst_dir, rels):
                    continue   # trùng cả cây → khỏi ghi lại
                for rel in rels:
                    dst_f = dst_dir / rel
                    dst_f.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(d / rel), str(dst_f))
            except Exception as e:
                print(f"[skill mirror] {d.name}: {type(e).__name__}: {e}", file=sys.stderr)
```

- [ ] **Step 5: Cập nhật docstring `mirror_skills`**

Trong `server/system_sync.py`, đổi dòng 236 từ:

```python
    """Mirror MỘT CHIỀU <root>/skills → <root>/.claude/skills (CHỈ skill đang BẬT).
```

thành:

```python
    """Mirror MỘT CHIỀU <root>/skills → <root>/.claude/skills (CHỈ skill đang BẬT), ĐỆ QUY
    cả references/ scripts/ templates/ (skill là PACKAGE, không phải một file).
```

- [ ] **Step 6: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_mirror_tree.py`
Expected: PASS.

- [ ] **Step 7: Chạy toàn bộ test cho chắc không phá gì**

Run: `cd server && for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || echo "^^ FAIL"; done`
Expected: mọi file in `OK - ...`. Đặc biệt để mắt `test_loop_ambient.py` và `test_security.py`.

- [ ] **Step 8: Commit**

```bash
git add server/system_sync.py server/test_mirror_tree.py
git commit -m "fix(sync): mirror_skills copy ca cay con + hash theo cay (references/ khong con bi bo roi)"
```

---

### Task 12: gitignore cho sidecar + reconcile brain cũ

**Files:**
- Modify: `server/git_brain.py:62-72` (`_GITIGNORE`), `:267-268` (`_BACKUP_SKIP_SUBSTR`), `:75-99` (`ensure_git_repo`)
- Test: `server/test_skill_usage.py`

**Interfaces:**
- Produces: `git_brain._ensure_gitignore_lines(root) -> bool` (True = có thay đổi).

**Ràng buộc:** hai chỗ ở **hai không gian đường dẫn KHÁC NHAU**. `.gitignore` tương đối gốc BRAIN → `Javis/skill-usage.json`. `_BACKUP_SKIP_SUBSTR` so khớp chuỗi con trên rel tương đối thư mục CHA của brain và `_backup_skip` bọc rel trong hai slash → phải viết `"/Javis/skill-usage.json/"` (cả slash đầu lẫn cuối), giống mọi mục hiện có.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `server/test_skill_usage.py` trước `if _fails:`:

```python
# ---- sidecar là state runtime → phải bị gitignore + không lên mirror backup ----
import git_brain  # noqa: E402

check("_GITIGNORE có Javis/skill-usage.json", "Javis/skill-usage.json" in git_brain._GITIGNORE)
check("_backup_skip bỏ qua sidecar", git_brain._backup_skip("brain/Javis/skill-usage.json") is True)
check("_backup_skip KHÔNG bỏ nhầm skill thật",
      git_brain._backup_skip("brain/skills/viet-email/SKILL.md") is False)

# reconcile brain cũ: .gitignore có sẵn thiếu dòng mới → phải được append, KHÔNG ghi đè
_gi_root = Path(tempfile.mkdtemp(prefix="javis-gitest-"))
(_gi_root / ".gitignore").write_text("# cua toi\nrieng-cua-toi/\n", encoding="utf-8")
_changed = git_brain._ensure_gitignore_lines(_gi_root)
_txt = (_gi_root / ".gitignore").read_text(encoding="utf-8")
check("reconcile báo có thay đổi", _changed is True)
check("reconcile GIỮ dòng user tự thêm", "rieng-cua-toi/" in _txt)
check("reconcile thêm dòng sidecar", "Javis/skill-usage.json" in _txt)
check("reconcile lần 2 là no-op", git_brain._ensure_gitignore_lines(_gi_root) is False)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: FAIL với `_GITIGNORE có Javis/skill-usage.json`, `_backup_skip bỏ qua sidecar`, và `AttributeError` ở `_ensure_gitignore_lines`.

- [ ] **Step 3: Thêm dòng vào `_GITIGNORE`**

Trong `server/git_brain.py`, đổi khối 62-72 thành (chèn 1 dòng sau `Javis/loop-log/`, giữ nhóm `Javis/` liền nhau; mỗi mục PHẢI tự mang `\n` vì đây là các literal nối chuỗi):

```python
_GITIGNORE = (
    "# Jarvis 007 brain - KHÔNG commit: khoá, log thô (có thể chứa secret), nhật ký nền.\n"
    "# Git chỉ version TRI THỨC ĐÃ CHƯNG CẤT (facts/wiki/skills/MEMORY.md) → undo sạch, an toàn.\n"
    ".javis-learn.lock\n"
    "Javis/learn-staging/\n"
    "Javis/learn-log/\n"
    "Javis/loop-log/\n"
    "Javis/skill-usage.json\n"
    "memory/conversations/\n"
    "Memory/conversations/\n"
    "*.tmp\n"
)
```

- [ ] **Step 4: Thêm vào `_BACKUP_SKIP_SUBSTR`**

Trong `server/git_brain.py`, đổi dòng 267-268 từ:

```python
_BACKUP_SKIP_SUBSTR = ("/memory/conversations/", "/Memory/conversations/",
                       "/Javis/loop-log/", "/Javis/learn-log/", "/Javis/learn-staging/")
```

thành:

```python
_BACKUP_SKIP_SUBSTR = ("/memory/conversations/", "/Memory/conversations/",
                       "/Javis/loop-log/", "/Javis/learn-log/", "/Javis/learn-staging/",
                       "/Javis/skill-usage.json/")
```

- [ ] **Step 5: Thêm helper reconcile**

Trong `server/git_brain.py`, ngay TRƯỚC `def ensure_git_repo` (dòng 75), thêm:

```python
def _ensure_gitignore_lines(root) -> bool:
    """Merge các dòng của _GITIGNORE vào <root>/.gitignore, CHỈ THÊM dòng còn thiếu.
    Trả True nếu có thay đổi. TUYỆT ĐỐI không ghi đè: brain cũ có thể đã có dòng user tự
    thêm. Cần thiết vì ensure_git_repo return sớm ở nhánh brain-đã-là-repo → brain cũ sẽ
    đông cứng mãi ở template lúc nó ra đời."""
    try:
        gi = Path(root) / ".gitignore"
        cur = gi.read_text(encoding="utf-8") if gi.exists() else ""
        have = {l.strip() for l in cur.splitlines() if l.strip()}
        missing = [l for l in _GITIGNORE.splitlines()
                   if l.strip() and not l.strip().startswith("#") and l.strip() not in have]
        if not missing:
            return False
        text = (cur.rstrip("\n") + "\n") if cur.strip() else _GITIGNORE.split(".javis-learn")[0]
        gi.write_text(text + "\n".join(missing) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        print(f"[gitignore] {root}: {type(e).__name__}: {e}", file=__import__('sys').stderr)
        return False
```

- [ ] **Step 6: Gọi reconcile ở nhánh brain-cũ**

Trong `server/git_brain.py`, đổi dòng 81-82 từ:

```python
    if is_git_checkout(root):
        return {"ok": True, "created": False}
```

thành:

```python
    if is_git_checkout(root):
        # Brain ĐÃ là repo: trước đây return thẳng ở đây nên template .gitignore mới không
        # bao giờ tới được brain cũ. Merge dòng còn thiếu rồi commit riêng bằng prefix
        # 'chore:' - KHÔNG dùng 'learn:'/'curator:' (xem LEARN_COMMIT_PREFIXES dòng 31) để
        # một lần vá .gitignore không bị hiện ở UI Review hay bị revert_last_learn undo.
        if _ensure_gitignore_lines(root):
            commit_paths(root, [".gitignore"], "chore: cập nhật .gitignore brain")
        return {"ok": True, "created": False}
```

Và đổi dòng 91-93 từ:

```python
        gi = Path(root) / ".gitignore"
        if not gi.exists():
            gi.write_text(_GITIGNORE, encoding="utf-8")
```

thành:

```python
        _ensure_gitignore_lines(root)   # merge chứ không ghi đè (brain có thể đã có .gitignore)
```

- [ ] **Step 7: Chạy test, xác nhận PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_skill_usage.py`
Expected: PASS.

- [ ] **Step 8: Chạy toàn bộ test**

Run: `cd server && for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || echo "^^ FAIL"; done`
Expected: mọi file `OK`.

- [ ] **Step 9: Commit**

```bash
git add server/git_brain.py server/test_skill_usage.py
git commit -m "fix(git): gitignore sidecar telemetry + reconcile .gitignore cho brain cu"
```

---

### Task 13: Chạy thật đầu-cuối + bump phiên bản

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

- [ ] **Step 1: Chạy toàn bộ test như CI chạy**

Run: `cd server && status=0; for f in test_*.py; do echo "==== $f ===="; ../.venv/Scripts/python.exe "$f" || status=1; done; echo "EXIT=$status"`
Expected: `EXIT=0`.

- [ ] **Step 2: Đo lại thiệt hại cắt cụt, xác nhận đã hết**

Run:
```bash
cd server && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
import skill_router, pathlib
root = pathlib.Path('../brains/Brain Default')
bad = 0
for s in skill_router.list_enabled_meta(root):
    e = skill_router.validate_description(s['description'])
    print(('CUT ' if e else 'ok  '), len(s['description'] or ''), s['slug'])
    bad += 1 if e else 0
print('vi pham:', bad)
"
```
Expected: `vi pham: 0`. Mọi skill in `ok` với độ dài <= 150. Trước khi làm plan này con số là 6/6 vi phạm.

- [ ] **Step 3: Chạy app, xác nhận skill vẫn route được**

Khởi động server, mở chat, hỏi một câu khớp trigger của một skill (vd "chuyển file html này sang webcake"). Expected: Jarvis 007 nạp đúng skill `html-to-webcake`. Sau đó mở trang Skill, expected: `html-to-webcake` hiện `Đã dùng 1 lần`, chứng minh telemetry chạy end-to-end.

- [ ] **Step 4: Bump VERSION + CHANGELOG**

`VERSION` hiện là `0.9.61`. Ghi `0.9.62`.

```bash
echo "0.9.62" > VERSION
```

Thêm mục vào đầu `CHANGELOG.md` theo đúng định dạng các mục đã có trong file, nội dung phủ: gom 3 điểm cắt description (60 ở hub, 100 ở system prompt, 140 ở fallback) về một hằng số `SKILL_DESC_MAX = 150`; ép trần ở `POST /skills` và learn.py; viết lại 5 description skill hệ thống (6/6 skill đang bị cắt, mất 79 tới 316 ký tự); thêm telemetry `Javis/skill-usage.json` đếm ở `javis_use_skill`; `mirror_skills` copy cả cây con và hash theo cây; gitignore sidecar + reconcile `.gitignore` cho brain cũ.

- [ ] **Step 5: Commit + push**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump phien ban - do skill + chuan viet skill (A+B)"
git push origin main
```

---

## Ghi chú cho người thực thi

**Thứ tự phụ thuộc:**

- Task 1 (hằng số + validator) chặn Task 2, 3, 6, 7.
- Task 3 (viết lại description) chặn Task 4 (cùng đụng `javis-builder/SKILL.md`, Task 3 sửa frontmatter, Task 4 sửa thân).
- Task 8 (sidecar) chặn Task 9, 10.
- Task 5 (CLAUDE.md), Task 11 (mirror), Task 12 (gitignore) độc lập, chen vào đâu cũng được.
- Task 13 làm cuối.

**Spec mục B3 nằm ở HAI task, đừng làm nửa vời:** bộ chuẩn viết skill phải có ở cả prompt learn (Task 7) lẫn javis-builder (Task 4 Step 4). Chỉ làm một nơi thì đường sinh skill còn lại vẫn đẻ ra skill vô định hình.

**Task rủi ro nhất là 11** (`mirror_skills` đệ quy). Nếu bí, đọc lại mục B4 trong spec: bẫy digest tập-con và bẫy deadlock `_LOCK` là hai chỗ dễ chết nhất.

**Nếu một test đỏ mà tưởng là không liên quan:** `mirror_skills` được gọi ở 7 hot path (`main.py:184`, `:2186`, `:2235`, `:2277`, `:2651`, `:2703`, `system_sync.py:356`). Sửa nó có thể vọng ra xa.

**Không mở rộng phạm vi.** Curator gộp ô dù, `/learn` từ nguồn, auto-archive, `related_skills` thành graph đều CỐ Ý nằm ngoài. Thấy chỗ đáng làm thì ghi lại, đừng làm.
