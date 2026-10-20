# Tool `javis_schedule`: chat tạo được việc định kỳ - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho Jarvis 007 một tool để tạo/liệt kê/huỷ việc định kỳ và nhắc hẹn ngay từ chat, thay cho việc gõ YAML bằng tay hoặc shell ra `curl`.

**Architecture:** `javis_schedule` là **plugin bundled** (`system/plugins/javis-schedule/`), KHÔNG phải tool trong hub. Nó route theo bản chất công việc: nhắc/cron/một-lần → kho `reminders` (đã chạy sẵn, có cron đầy đủ); việc lặp + bền + cần prompt sửa được trong Obsidian → file `.md` trong `Javis/loops/`. Người dùng và model chỉ thấy MỘT khái niệm "việc"; chuyện nó rơi vào kho nào là chi tiết triển khai.

**Tech Stack:** Python 3.12, hệ plugin của Jarvis 007 (`plugins_host.py`), test script thuần.

Spec: `docs/superpowers/specs/2026-07-17-hop-nhat-viec-dinh-ky-design.md` (mục "Tool `javis_schedule`")

---

## Spec sai ba chỗ, plan này sửa

Spec viết: *"Thêm vào hub cạnh `javis_use_skill` (`mcp_hub.py:272`)"*. **Sai, và sai theo cách sẽ ship ra một tool vô hình.** Đọc code thật:

**1. Hub HTTP không phục vụ nhóm builtin đó cho Claude/Codex.** `_handle_one` (`mcp_hub.py:391`) gọi `discover_all(mode, include_plugins=...)`, tức `vault_root=None` (mặc định ở `mcp_hub.py:293`). Mà `_builtin_tools` **early-return ngay sau `javis_connections`** (`mcp_hub.py:213-214`: `if not vault_root: return tools, route`). Đặt `javis_schedule` cạnh `javis_use_skill` = Claude Code không bao giờ thấy nó.

**2. Hub chỉ được gắn khi có ít nhất 1 connector MCP.** `claude_config_path` (`mcp_hub.py:~450`) trả `None` khi `not _has_connections()`. Người dùng chưa đấu MCP nào thì không có hub, tức không có tool. Một năng lực lõi không được phụ thuộc việc user đã đấu connector hay chưa.

**3. Đường đúng là plugin, và CLAUDE.md tự dạy vậy.** `claude_sdk_engine._plugins_server` (`:162-186`) dựng **MCP server IN-PROCESS** từ `plugins_host.plugin_tools(mode, None)`, gọi thẳng handler Python, **không qua hub**, nên không dính hai rào trên. Codex và engine API vẫn lấy plugin qua hub (`mcp_hub.py:334-347`). Một plugin bundled tới được mọi engine. `system/plugins/image-chatgpt/` là tiền lệ chính xác: `enabled: true`, `min_mode: safe`, đăng ký `javis_generate_image`, chạy trên mọi engine.

**Giới hạn đã biết, chấp nhận:** `_mcp_servers` (`claude_sdk_engine.py:188-191`) chỉ đấu plugin in-process khi engine **KHÔNG gated**; fork gated (`allowed_tools` có giá trị: loop mode suggest/auto, reminders mode task, workflow) cố ý giữ cô lập và **không** có plugin. Nên `javis_schedule` có ở **chat thường** (`main.py:1731` gọi `claude_engine` không truyền `allowed_tools` → ungated) - đúng ca dùng mà anh Quy nêu - nhưng loop nền sẽ không tự đặt lịch được. Đó là hành vi ĐÚNG (loop tự đẻ lịch là thứ ta không muốn), đừng "sửa".

## Bug có sẵn phải sửa trước, nếu không tool này sẽ ghi nhầm brain

`PluginContext.vault_root` (`plugins_host.py:218`) nhận thẳng tham số `vault_root`. Đường SDK truyền `None` (`claude_sdk_engine.py:169`, comment "None = plugin toàn cục"). Nên **mọi plugin gọi từ Claude Code đều có `ctx.vault_root is None`**.

Hậu quả đang xảy ra HÔM NAY (không phải giả thuyết): `image-chatgpt` truyền `vault_root=cctx.vault_root` (`plugin.py:33`) xuống `image_gen._resolve_vault` (`image_gen.py:95-98`), hàm này thấy rỗng thì **rơi về `brains/Brain Default`**. Tức: anh Quy đang làm việc ở brain "My Bullet Journal", bảo Jarvis 007 tạo ảnh, **ảnh lưu vào Brain Default** và link `![](attachments/...)` trong chat trỏ vào chỗ không có file. Bug im lặng, chưa ai báo.

`javis_schedule` mà copy mẫu này thì sẽ ghi loop vào sai brain và đặt nhắc vào sai kho. **Task 1 sửa đường ống đó**, và sửa luôn `image-chatgpt` như hiệu ứng phụ.

## Global Constraints

- **TUYỆT ĐỐI không dùng ký tự em dash (U+2014)** trong bất kỳ file nào: code, comment, test, doc, commit message. Dùng "-" hoặc viết lại câu. (CLAUDE.md, nguyên tắc 8.)
- Tiếng Việt cho comment, docstring, mô tả tool, thông báo lỗi.
- Test là **script thuần, không pytest**: `server/test_*.py`, có `def check(name, cond)`, gom `_fails`, `sys.exit(1)` khi lỗi. CI chạy `for f in test_*.py; do python "$f"; done` (`.github/workflows/ci.yml:35-37`).
- Chạy test bằng venv: `.venv/Scripts/python.exe`. Test tự cô lập bằng `os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="..."))` TRƯỚC khi import module Jarvis 007.
- **Mô tả tool phải nói rõ KHI NÀO gọi**, vì đó là thứ duy nhất model đọc để quyết định. Bám giọng `image-chatgpt`.
- Plugin bundled (`system/plugins/`) đi theo app, `enabled: true`. **Không** áp luật "plugin do chat tạo thì `enabled: false`" - luật đó dành cho plugin user tự viết.
- Không sửa `server/self_improve.py` phần executor (`_eligible_overdue`, `run_cycle`). Plan này chỉ TẠO việc, không đổi cách chạy.
- Nhắc lại từ giai đoạn 1: `dashboard/style.css` có `.loop-sel` và `.loop-row` còn SỐNG. Plan này không đụng CSS.

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/claude_sdk_engine.py:162-186` | `_plugins_server` truyền vault_root THẬT thay vì `None`. |
| `server/plugins_host.py` | `plugin_tools(mode, vault_root)` phân biệt "nạp plugin nào" với "ctx thấy vault nào". |
| `server/test_plugin_vault.py` | **Mới.** Chặn hồi quy: ctx của plugin phải thấy đúng brain, không rơi về Brain Default. |
| `system/plugins/javis-schedule/plugin.yaml` | **Mới.** Khai báo plugin, `min_mode: safe`. |
| `system/plugins/javis-schedule/plugin.py` | **Mới.** Tool `javis_schedule`: op create/list/cancel, route hai kho. |
| `server/test_javis_schedule.py` | **Mới.** Phủ: route đúng kho, parse lịch, list thấy CẢ HAI kho, cancel. |
| `CLAUDE.md` | Mục điều phối: nói cho Jarvis 007 biết đã có tool này, đừng gõ YAML tay nữa. |

---

### Task 1: Plugin phải thấy đúng brain (sửa bug ghi nhầm Brain Default)

**Files:**
- Modify: `server/claude_sdk_engine.py:162-186` (`_plugins_server`)
- Modify: `server/plugins_host.py` (`plugin_tools`)
- Test: `server/test_plugin_vault.py` (tạo mới)

**Interfaces:**
- Consumes: chữ ký HIỆN TẠI đã verify: `plugin_tools(mode: str = "full", vault_root: Optional[str] = None) -> Tuple[List[dict], Dict[str, dict]]` (`plugins_host.py:415`). Task này THÊM keyword-only `scope_vault: bool = True`.
- Produces: `ctx.vault_root` **không còn là None** ở đường chat. **Cơ chế THẬT (đã sửa lúc chạy, khác bản nháp plan):** brain đi TƯỜNG MINH qua `_apply_mcp(cli, mode="full", brain=None)` (`main.py:693`) đặt `cli.javis_vault = _brain_root(brain) if brain else None`, y khuôn `cli.javis_mode` sẵn có; `_plugins_server` đọc `self.javis_vault`. Bản nháp plan bảo suy từ `cwd` (`_brain_root()` kiểm `(cwd/"Jarvis 007").is_dir()`) - **SAI và đã xoá hẳn**: `CLAUDE_CWD` (`main.py:318`) là gốc project, không có `Javis/`, mà chat (`main.py:4213`, `:4537`) dùng đúng cwd đó, nên suy-từ-cwd luôn trượt ở chính đường chat.

**Vì sao task riêng:** đây là bug có sẵn, độc lập với `javis_schedule`, và một reviewer có thể duyệt/từ chối nó riêng. Nó cũng sửa `image-chatgpt` (đang lưu ảnh nhầm brain) mà không cần đụng file plugin đó.

- [ ] **Step 1: Chứng minh bug tồn tại trước khi sửa**

Tạo `server/test_plugin_vault.py`:

```python
"""Test: plugin phải thấy ĐÚNG brain, không âm thầm rơi về Brain Default. Chạy tay / CI:

    cd server && python test_plugin_vault.py

Bối cảnh bug: claude_sdk_engine._plugins_server gọi plugin_tools(mode, None) nên
PluginContext.vault_root (plugins_host.py:218) = None với MỌI plugin gọi từ Claude Code.
image-chatgpt truyền cctx.vault_root xuống image_gen._resolve_vault (image_gen.py:95-98),
hàm này thấy rỗng thì rơi về brains/Brain Default -> ảnh lưu SAI brain, im lặng.

Phủ:
- PluginContext giữ đúng vault_root được truyền.
- plugin_tools(mode, vault) dựng ctx có vault đó (không None).
- _resolve_vault: có vault hợp lệ thì KHÔNG rơi về Brain Default (khẳng định tiền đề của bug).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-pvault-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plugins_host  # noqa: E402
import image_gen     # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


_BRAIN = tempfile.mkdtemp(prefix="javis-brain-that-")

# ---- 1. Tiền đề của bug: _resolve_vault rơi về Brain Default khi vault rỗng ----
# Nếu assert này đỏ thì bug đã được sửa ở nơi khác và test cần viết lại.
fallback = str(image_gen._resolve_vault(None))
check("tiền đề: _resolve_vault(None) rơi về Brain Default",
      fallback.endswith("Brain Default"))
check("tiền đề: _resolve_vault(<vault thật>) tôn trọng vault",
      str(image_gen._resolve_vault(_BRAIN)) == _BRAIN)

# ---- 2. PluginContext giữ vault_root ----
# Chữ ký THẬT (plugins_host.py:214): __init__(self, slug, source, plugin_dir, vault_root)
ctx = plugins_host.PluginContext(slug="thu-nghiem", source="bundled",
                                 plugin_dir=Path(_BRAIN), vault_root=_BRAIN)
check("ctx: giữ đúng vault_root được truyền", ctx.vault_root == _BRAIN)
check("ctx: data_dir là property, không phải field gán tay", isinstance(ctx.data_dir, Path))

# ---- 3. _load_all dựng ctx THẤY vault (đây là chỗ bug sống) ----
# Assert vào ctx THẬT của plugin đã nạp, không assert kiểu trả về. LoadedPlugin giữ ctx
# (plugins_host.py:257 __slots__ có "ctx"), nên đọc thẳng được. Assert kiểu
# `isinstance(tools, list)` là TAUTOLOGY: luôn đúng kể cả khi ctx mù vault.
ent = plugins_host._load_all(_BRAIN)
loaded = ent["plugins"]
check("nạp: có ít nhất 1 plugin bundled để soi ctx", len(loaded) > 0)
check("ctx: MỌI plugin đã nạp thấy đúng brain (không None, không Brain Default)",
      all(lp.ctx.vault_root == _BRAIN for lp in loaded))

# Chứng minh bug: truyền None thì ctx mù -> đây chính là thứ đường SDK đang làm.
ent_none = plugins_host._load_all(None)
check("bug: _load_all(None) -> ctx.vault_root là None (tiền đề của lỗi lưu nhầm brain)",
      all(lp.ctx.vault_root is None for lp in ent_none["plugins"]))


if _fails:
    print(f"\nFAIL - test_plugin_vault: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_plugin_vault: tất cả pass")
```

- [ ] **Step 2: Chạy test, xác nhận nó chạy được và tiền đề đỏ/xanh đúng**

Run: `cd server && ../.venv/Scripts/python.exe test_plugin_vault.py`

Expected: hai assert "tiền đề" PASS (chứng minh bug có thật và `_resolve_vault` hành xử như mô tả). Nếu `PluginContext(...)` ném `TypeError` vì chữ ký khác, ĐỌC `plugins_host.py:209-220` rồi sửa test cho khớp chữ ký THẬT - đừng sửa code cho khớp test ở bước này.

- [ ] **Step 3: Đọc chữ ký thật trước khi sửa**

Run: `cd /d/Project/Javis-OS && sed -n '160,175p;209,225p' server/plugins_host.py && sed -n '160,172p' server/claude_sdk_engine.py`

Ghi lại: `plugin_tools` nhận gì, `PluginContext.__init__` nhận gì, `_plugins_server` đang truyền gì. Plan này mô tả theo hiểu biết lúc soạn; **code thật thắng**.

- [ ] **Step 4: Sửa `_plugins_server` truyền vault thật**

Trong `server/claude_sdk_engine.py`, hàm `_plugins_server` (`:162`), dòng hiện tại:

```python
        p_tools, p_route = plugins_host.plugin_tools(mode, None)   # None = plugin toàn cục, như hub phục vụ CLI
```

Vấn đề: một tham số `None` đang gánh HAI nghĩa - "nạp plugin toàn cục (bundled + global, không nạp plugin riêng của vault)" VÀ "ctx không thấy vault nào". Nghĩa thứ nhất là cố ý, nghĩa thứ hai là bug.

Sửa thành:

```python
        # vault_root: CHỈ để ctx của plugin biết đang làm việc ở brain nào (vd image-chatgpt lưu
        # ảnh vào đúng attachments/). Trước đây truyền None nên MỌI plugin gọi từ Claude Code đều
        # có ctx.vault_root=None -> image_gen._resolve_vault rơi về "Brain Default" -> lưu SAI brain.
        # Vẫn KHÔNG nạp plugin riêng-của-vault (giữ nguyên hành vi cũ): xem _plugin_scope dưới.
        p_tools, p_route = plugins_host.plugin_tools(mode, self._brain_root())
```

Và thêm helper vào cùng class:

```python
    def _brain_root(self):
        """Brain đang làm việc, suy từ cwd. Trả None nếu cwd không phải một brain hợp lệ
        (vd chat chạy với cwd = thư mục project) - khi đó plugin tự lo fallback như cũ."""
        try:
            root = Path(self.cwd)
            return str(root) if (root / "Jarvis 007").is_dir() else None
        except Exception:
            return None
```

Đảm bảo `from pathlib import Path` đã có ở đầu file (`grep -n "^from pathlib\|^import pathlib" server/claude_sdk_engine.py`); nếu chưa thì thêm.

- [ ] **Step 5: Tách hai nghĩa của tham số trong `plugins_host`**

Đọc `plugin_tools` và `_iter_plugin_dirs` (`plugins_host.py:129-140`). `_iter_plugin_dirs(vault_root)` dùng `vault_root` để quyết định có nạp `vault_plugins_dir(vault_root)` hay không. Nếu Step 4 giờ truyền vault thật, plugin **riêng của vault** sẽ bắt đầu được nạp cho engine SDK - đó là **đổi hành vi ngoài phạm vi** và dính rào `JAVIS_ENABLE_USER_PLUGINS`.

Nên thêm tham số tách bạch vào `plugin_tools`:

```python
def plugin_tools(mode, vault_root=None, *, scope_vault=True):
    """mode: mức quyền lượt chạy. vault_root: brain để ctx của plugin biết đang ở đâu.
    scope_vault=False: KHÔNG nạp plugin riêng-của-vault (chỉ bundled + global) nhưng ctx VẪN
    thấy vault_root. Tách hai nghĩa vì trước đây một chữ None gánh cả hai, làm ctx mù brain."""
```

**Đường dây thật (đã verify, đừng đoán):** `plugin_tools` (`:415`) gọi `_load_all(vault_root)`; `_load_all` mới là chỗ gọi `_iter_plugin_dirs(vault_root)` (`:129`) và dựng `PluginContext(..., vault_root=vault_root)`. Nên `scope_vault` phải xuyên qua CẢ HAI: `plugin_tools(..., scope_vault=...)` → `_load_all(vault_root, scope_vault=...)` → `_iter_plugin_dirs(vault_root if scope_vault else None)`, trong khi `PluginContext` vẫn nhận `vault_root` THẬT.

Chỉ `_iter_plugin_dirs` được nhận `None`; `PluginContext` thì không. Đó chính là chỗ tách hai nghĩa.

**Cache:** `_load_all` cache theo `vault_root` (`plugins_host.py:63`). Thêm `scope_vault` vào khoá cache, nếu không hai lượt chạy cùng vault nhưng khác scope sẽ dùng nhầm cache của nhau. Đọc `:63-70` xem khoá đang dựng thế nào rồi thêm cho khớp.

Rồi ở `claude_sdk_engine._plugins_server` gọi:

```python
        p_tools, p_route = plugins_host.plugin_tools(mode, self._brain_root(), scope_vault=False)
```

- [ ] **Step 6: Bổ sung assert cho hành vi mới**

Thêm vào `server/test_plugin_vault.py` trước khối `if _fails:`:

```python
# ---- 4. scope_vault=False: ctx VẪN thấy vault nhưng KHÔNG nạp plugin riêng-của-vault ----
import inspect  # noqa: E402
sig = inspect.signature(plugins_host.plugin_tools)
check("plugin_tools: có tham số scope_vault", "scope_vault" in sig.parameters)
check("plugin_tools: scope_vault mặc định True (giữ hành vi cũ cho hub)",
      sig.parameters["scope_vault"].default is True)

import claude_sdk_engine  # noqa: E402
# Class THẬT tên ClaudeSDK (claude_sdk_engine.py:124), KHÔNG phải ClaudeSDKEngine.
check("SDK: có helper _brain_root", hasattr(claude_sdk_engine.ClaudeSDK, "_brain_root"))

src_sdk = (Path(__file__).parent / "claude_sdk_engine.py").read_text(encoding="utf-8")
check("SDK: không còn truyền None mù vào plugin_tools",
      "plugin_tools(mode, None)" not in src_sdk)
check("SDK: truyền brain thật + scope_vault=False",
      "scope_vault=False" in src_sdk)
```

**Tên class đã verify:** `ClaudeSDK` (`claude_sdk_engine.py:124`). Không phải `ClaudeSDKEngine`.

- [ ] **Step 7: Chạy test**

Run: `cd server && ../.venv/Scripts/python.exe test_plugin_vault.py`

Expected: PASS toàn bộ.

- [ ] **Step 8: Chạy hồi quy các test đụng plugin/engine**

Run: `cd server && for f in test_plugins_host.py test_sdk_engine.py test_image_gen.py test_loop_ambient.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: cả 4 in `OK - ...`. Nếu `test_plugins_host.py` đỏ vì đổi chữ ký, sửa TEST cho khớp chữ ký mới (thêm `scope_vault`), đừng bỏ tham số.

- [ ] **Step 9: Commit**

```bash
git add server/claude_sdk_engine.py server/plugins_host.py server/test_plugin_vault.py
git commit -m "fix(plugins): ctx thay dung brain - truoc day moi plugin goi tu Claude Code deu mu

_plugins_server truyen plugin_tools(mode, None) nen PluginContext.vault_root
(plugins_host.py:218) = None voi MOI plugin goi tu Claude Code. image-chatgpt
truyen cctx.vault_root xuong image_gen._resolve_vault (image_gen.py:95-98), ham
nay thay rong thi roi ve brains/Brain Default -> lam viec o brain khac ma anh
lai luu vao Brain Default, link attachments/ tro vao cho khong co file. Bug im
lang, chua ai bao.

Mot chu None dang ganh HAI nghia: 'khong nap plugin rieng-cua-vault' (co y) va
'ctx khong thay vault nao' (bug). Tach bang tham so scope_vault.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Plugin `javis-schedule` - tool tạo/liệt kê/huỷ việc

**Files:**
- Create: `system/plugins/javis-schedule/plugin.yaml`
- Create: `system/plugins/javis-schedule/plugin.py`
- Test: `server/test_javis_schedule.py` (tạo mới)

**Interfaces:**
- Consumes: `ctx.vault_root` thấy đúng brain khi gọi từ **chat** (Task 1, cơ chế: `_apply_mcp(cli, brain=...)` → `cli.javis_vault` → `plugin_tools(mode, self.javis_vault, scope_vault=False)`). **Lưu ý:** loop nền gọi `apply_mcp` KHÔNG truyền brain nên `javis_vault=None` ở đó - nhưng loop suggest/auto vốn gated nên không có plugin, còn loop `mode: full` thì có. Vì vậy handler PHẢI báo lỗi rõ khi `ctx.vault_root` rỗng, TUYỆT ĐỐI không fallback về Brain Default. `reminders` HTTP API `POST /reminders` (`server/reminders.py:507`, localhost-exempt qua `_AUTH_LOCAL_EXACT` ở `main.py:70`), `GET /reminders`, `POST /reminders/cancel`.
- Produces: tool `javis_schedule(op, ...)`. Không task nào sau dựa vào nó.

**Quyết định wiring, đọc kỹ trước khi code:**

Plugin **KHÔNG import `main.py`** (vòng lặp import, và `main.py` 5000 dòng có side-effect lúc import). Hai kho được với tới theo hai đường khác nhau, vì luật auth khác nhau:

- **Nhắc hẹn** → gọi HTTP `POST /reminders` trên `127.0.0.1`. Đường này CỐ Ý miễn đăng nhập cho localhost (`main.py:70`, `_AUTH_LOCAL_EXACT = ("/telegram/send-file", "/reminders")`), chính là đường mà `reminders.py:17` mô tả agent đang dùng bằng `curl`. Tool chỉ gói lại cho tử tế.
- **Loop** → **ghi thẳng file** `.md` vào `<vault_root>/Javis/loops/<slug>.md`. KHÔNG dùng `POST /loops` vì route đó **cần đăng nhập** (không nằm trong `_AUTH_LOCAL_EXACT`) nên plugin không gọi được từ localhost. Ghi file là đúng bản chất: loop VỐN LÀ một file `.md` (`self_improve.py:6`), scheduler tự đọc thư mục.

Port server: đọc từ env `JAVIS_PORT` nếu có, mặc định `7777`. Xác nhận bằng `grep -rn "7777\|JAVIS_PORT" server/main.py server/config.py | head`.

- [ ] **Step 1: Viết test thất bại**

Tạo `server/test_javis_schedule.py`:

```python
"""Test tool javis_schedule (plugin bundled). Chạy tay / CI:

    cd server && python test_javis_schedule.py

Bối cảnh: trước tool này, chat muốn tạo việc định kỳ phải TỰ GÕ YAML frontmatter vào
Javis/loops/<slug>.md, hoặc shell ra curl POST /reminders (reminders.py:17). Tool gói cả hai
lại và tự route: nhắc/cron/một-lần -> kho reminders; việc lặp + bền -> file .md.

KHÔNG chạm mạng: mọi test đều gọi hàm thuần hoặc ghi file trong thư mục tạm.

Phủ:
- _route_kind: phân loại đúng lịch -> kho nào.
- _slugify_vn: tên tiếng Việt -> slug ascii, không đụng file đã có.
- op=create việc lặp -> ghi .md đúng chỗ, frontmatter đọc lại được, enabled=false.
- op=create nhắc -> KHÔNG ghi .md (phải đi đường reminders).
- Tool đăng ký đúng tên + min_mode.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-schedtest-"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).parent.parent / "system" / "plugins" / "javis-schedule"))

import plugin as sched  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---- 1. Route: lịch nào về kho nào ----
check("route: '120m' -> loop (lặp, bền)", sched._route_kind("120m", False) == "loop")
check("route: 'mỗi 2 tiếng' -> loop", sched._route_kind("mỗi 2 tiếng", False) == "loop")
check("route: '0 7 * * *' -> reminder (cron, reminders đã có sẵn)",
      sched._route_kind("0 7 * * *", False) == "reminder")
check("route: '30 phút nữa' -> reminder (một lần)", sched._route_kind("30 phút nữa", False) == "reminder")
check("route: notify_only ép về reminder dù lịch lặp",
      sched._route_kind("120m", True) == "reminder")

# ---- 2. Slug ----
check("slug: bỏ dấu tiếng Việt", sched._slugify_vn("Đọc source mỗi 2 tiếng") == "doc-source-moi-2-tieng")
check("slug: không rỗng khi tên toàn ký tự lạ", sched._slugify_vn("!!!") != "")

# ---- 3. Tạo việc lặp -> ghi .md ----
_vault = tempfile.mkdtemp(prefix="javis-vault-")
res = sched._create_loop_file(_vault, name="Quét đơn mỗi 2 tiếng",
                              prompt="Mỗi vòng đọc số đơn hôm nay qua MCP POS rồi ghi nháp.",
                              schedule="120m", owner_chat="123")
f = Path(_vault) / "Jarvis 007" / "loops" / "quet-don-moi-2-tieng.md"
check("loop: ghi đúng <vault>/Javis/loops/<slug>.md", f.is_file())
body = f.read_text(encoding="utf-8") if f.is_file() else ""
check("loop: frontmatter có type: loop", "type: loop" in body)
check("loop: MẶC ĐỊNH enabled: false (luật an toàn CLAUDE.md)", "enabled: false" in body)
check("loop: MẶC ĐỊNH mode: suggest (không bao giờ tự đặt full)", "mode: suggest" in body)
check("loop: interval_min từ '120m'", "interval_min: 120" in body)
check("loop: giữ owner_chat để báo đúng người", 'owner_chat: "123"' in body)
check("loop: thân file LÀ prompt (tự đủ, không phụ thuộc chat)", "MCP POS" in body)
check("loop: trả về đường dẫn cho model biết đã ghi đâu", "quet-don-moi-2-tieng" in str(res))

# ---- 4. Không ghi đè loop đã có bằng bản ascii song song ----
# self_improve.py:273 lấy ĐỊNH DANH theo TÊN FILE. Tạo trùng slug -> phải báo, không âm thầm fork.
res2 = sched._create_loop_file(_vault, name="Quét đơn mỗi 2 tiếng", prompt="khác", schedule="60m")
check("loop: trùng slug -> báo lỗi rõ, không đẻ bản sao",
      str(res2).startswith("ERROR:") or "đã có" in str(res2).lower())

# ---- 5. Tool đăng ký đúng ----
_regs = []


class _FakeCtx:
    # data_dir là @property trên PluginContext thật (plugins_host.py:223) nên KHÔNG gán được;
    # fake ctx chỉ cần thứ handler thật sự đọc.
    vault_root = _vault
    slug = "javis-schedule"

    def register_tool(self, **kw):
        _regs.append(kw)

    def register_hook(self, *a, **k):
        pass


sched.register(_FakeCtx())
check("đăng ký: đúng 1 tool", len(_regs) == 1)
check("đăng ký: tên javis_schedule", _regs and _regs[0].get("name") == "javis_schedule")
check("đăng ký: min_mode=safe (tạo việc là GHI, chặn ở suggest)",
      _regs and _regs[0].get("min_mode") == "safe")
desc = (_regs[0].get("description") or "") if _regs else ""
check("đăng ký: mô tả nói rõ KHI NÀO gọi", len(desc) > 60 and "op" in desc)
props = ((_regs[0].get("schema") or {}).get("properties") or {}) if _regs else {}
check("đăng ký: schema có op/name/schedule/prompt",
      {"op", "name", "schedule", "prompt"}.issubset(set(props)))


if _fails:
    print(f"\nFAIL - test_javis_schedule: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_javis_schedule: tất cả pass")
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `cd server && ../.venv/Scripts/python.exe test_javis_schedule.py`

Expected: `ModuleNotFoundError: No module named 'plugin'` (chưa tạo plugin).

- [ ] **Step 3: Tạo `plugin.yaml`**

Tạo `system/plugins/javis-schedule/plugin.yaml`:

```yaml
name: Đặt việc định kỳ & nhắc hẹn
slug: javis-schedule
version: 1.0.0
description: Tạo/liệt kê/huỷ việc chạy định kỳ và nhắc hẹn ngay từ chat. Tự chọn kho - việc lặp và bền thì ghi Javis/loops/<slug>.md để sửa được trong Obsidian; nhắc một lần hoặc lịch cron thì vào kho nhắc hẹn (đã có sẵn cron 5 trường). Thay cho việc gõ YAML tay hoặc curl.
author: Jarvis 007 (bundled)
enabled: true
min_mode: safe
tools:
  - javis_schedule
hooks: []
```

- [ ] **Step 4: Viết `plugin.py`**

Tạo `system/plugins/javis-schedule/plugin.py`. Đọc `system/plugins/image-chatgpt/plugin.py` trước để bám đúng khuôn `register(ctx)` / `ctx.register_tool` / trả `"ERROR: ..."` khi lỗi.

Yêu cầu nội dung (viết đầy đủ, đây là mô tả hành vi bắt buộc chứ không phải gợi ý):

1. `_slugify_vn(name) -> str`: bỏ dấu tiếng Việt (dùng `unicodedata.normalize("NFD", s)` rồi lọc `category != "Mn"`), hạ chữ thường, thay mọi ký tự không phải `[a-z0-9]` bằng `-`, gộp `-` liên tiếp, cắt hai đầu. Rỗng thì trả `"viec"`.
2. `_route_kind(schedule, notify_only) -> "loop" | "reminder"`:
   - `notify_only` True → `"reminder"`.
   - Chuỗi khớp cron 5 trường (5 token cách nhau bởi khoảng trắng, hoặc bắt đầu bằng `@`) → `"reminder"`.
   - Chuỗi chỉ ra CHU KỲ lặp (`"120m"`, `"90 phút"`, `"mỗi 2 tiếng"`, `"2h"`) → `"loop"`.
   - Còn lại (mốc một lần: `"30 phút nữa"`, `"9h sáng mai"`, ISO) → `"reminder"`.
3. `_interval_min(schedule) -> int`: rút số phút từ chuỗi chu kỳ. `"2 tiếng"`/`"2h"` → 120. Tối thiểu **5** (khớp trần cứng ở `self_improve.py:257`).
4. `_create_loop_file(vault_root, name, prompt, schedule, owner_chat="") -> str`: ghi `<vault_root>/Javis/loops/<slug>.md`. **File đã tồn tại → trả `"ERROR: đã có việc tên ... , sửa nó thay vì tạo bản sao"`**, KHÔNG ghi đè (`self_improve.py:321-327` lấy định danh theo tên file; đẻ bản ascii song song thì bản gốc VẪN CHẠY). Frontmatter đúng khuôn CLAUDE.md:

```
---
type: loop
name: <name>
slug: <slug>
enabled: false
mode: suggest
interval_min: <n>
owner_chat: "<chat_id>"
updated: <YYYY-MM-DD>
---
<prompt>
```

   `enabled: false` và `mode: suggest` là **BẮT BUỘC**, không nhận tham số để đổi. Luật CLAUDE.md: "Loop do chat tạo LUÔN mặc định `mode: suggest` + `enabled: false`. KHÔNG bao giờ tự đặt `mode: full`."
5. `_post_reminder(payload) -> str`: `httpx.post(f"http://127.0.0.1:{_port()}/reminders", json=payload, timeout=10)`. `_port()` đọc env `JAVIS_PORT` mặc định `7777`.
6. Handler `javis_schedule(args, cctx)`:
   - `op="create"`: cần `name` + `prompt` + `schedule`. Route bằng `_route_kind`. `"loop"` → `_create_loop_file(cctx.vault_root, ...)`; `"reminder"` → `_post_reminder`. `cctx.vault_root` rỗng → trả `"ERROR: không xác định được brain đang làm việc"` (ĐỪNG fallback về Brain Default - đó là chính bug Task 1 vừa sửa).
   - `op="list"`: trả **union CẢ HAI kho** - đọc `<vault>/Javis/loops/*.md` (tên + enabled + interval) và `GET /reminders` (pending). Đây là lỗi dễ mắc nhất: chỉ nhìn một kho thì model sẽ báo "không có việc nào" trong khi việc nằm ở kho kia.
   - `op="cancel"`: `id` bắt đầu bằng slug loop → xoá file `.md`; còn lại → `POST /reminders/cancel`.
   - Trả CHUỖI người đọc được (model sẽ đọc lại), lỗi thì `"ERROR: ..."`.
7. `register(ctx)` gọi `ctx.register_tool(...)`. Chữ ký THẬT đã verify (`plugins_host.py:~230`):

```python
def register_tool(self, name: str, description: str, handler: Callable,
                  schema: Optional[dict] = None, parameters: Optional[dict] = None,
                  min_mode: str = "readonly", check_fn: Optional[Callable] = None,
                  emoji: str = "") -> None
```

   `handler(args: dict, ctx: PluginContext) -> str` (sync hoặc async). Tên tool phải khớp `a-z0-9_` nếu không nó **ném ValueError**. Dùng `min_mode="safe"`, schema có `op` (enum create|list|cancel), `name`, `schedule`, `prompt`, `notify_only`, `id`. Mô tả tool phải nêu rõ khi nào gọi kèm ví dụ lịch hợp lệ.

- [ ] **Step 5: Chạy test tới khi PASS**

Run: `cd server && ../.venv/Scripts/python.exe test_javis_schedule.py`

Expected: PASS toàn bộ. Nếu assert nào sai vì chữ ký `ctx.register_tool` khác thật, đọc `plugins_host.py:209-260` lấy chữ ký thật rồi sửa TEST.

- [ ] **Step 6: Xác nhận plugin được nạp thật (không chỉ pass test đơn vị)**

Run:

```bash
cd server && ../.venv/Scripts/python.exe -c "
import os, sys, tempfile
os.environ.setdefault('JAVIS_STATE_DIR', tempfile.mkdtemp())
sys.path.insert(0, '.')
import plugins_host
d = plugins_host.describe(None)
p = [x for x in d if x['slug'] == 'javis-schedule']
print('mo ta:', p)
t, r = plugins_host.plugin_tools('safe', None)
print('tool safe:', [x['fn'] for x in t])
t2, _ = plugins_host.plugin_tools('readonly', None)
print('tool readonly (KHONG duoc co javis_schedule):', [x['fn'] for x in t2])
"
```

Expected: `javis-schedule` xuất hiện trong `describe`, `loaded: True`, `error` rỗng. `javis_schedule` CÓ trong danh sách mode `safe`, **KHÔNG** có trong mode `readonly` (min_mode chặn). Nếu `loaded: False` thì đọc trường `error` để biết import hỏng ở đâu.

- [ ] **Step 7: Chạy hồi quy**

Run: `cd server && for f in test_plugins_host.py test_plugin_vault.py test_javis_schedule.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: cả 3 in `OK - ...`.

- [ ] **Step 8: Commit**

```bash
git add system/plugins/javis-schedule/ server/test_javis_schedule.py
git commit -m "feat(schedule): tool javis_schedule - chat dat duoc viec dinh ky, thoi go YAML tay

Truoc: chat muon tao viec dinh ky phai TU GO YAML frontmatter vao
Javis/loops/<slug>.md, hoac shell ra curl POST /reminders (reminders.py:17 ghi
thang nhu vay). Duong thu hai con tu mau thuan: loop mode suggest/auto bi chan
Bash (self_improve.py:112) nen loop khong tu dat nhac duoc cho chinh no.

La PLUGIN bundled chu khong phai tool trong hub, vi hub khong voi toi duoc moi
engine: _builtin_tools early-return khi vault_root=None (mcp_hub.py:213) ma
duong HTTP luon goi vay, va claude_config_path tra None khi chua co connector
MCP nao. Plugin di qua MCP server IN-PROCESS (claude_sdk_engine.py:162-186),
khong dinh hai rao do.

Route hai kho: viec lap + ben -> .md (sua duoc trong Obsidian); nhac/cron/mot-lan
-> kho reminders (da co cron 5 truong san). op=list phai nhin CA HAI kho.

An toan: loop tao qua chat LUON enabled:false + mode:suggest, khong nhan tham so
de doi (luat CLAUDE.md). Trung slug thi bao loi, khong de ban sao song song
(self_improve.py:321-327: dinh danh theo TEN FILE).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Dạy Jarvis 007 dùng tool + tài liệu

**Files:**
- Modify: `CLAUDE.md` (mục "Điều phối", bậc 2/6/7)
- Modify: `CHANGELOG.md`, `VERSION`

**Interfaces:**
- Consumes: tool `javis_schedule` (Task 2).
- Produces: không.

**Vì sao cần:** tool tồn tại mà system prompt vẫn dạy "ghi file `Javis/loops/<slug>.md`" thì model sẽ tiếp tục gõ YAML tay. Mô tả tool cạnh tranh trực tiếp với chỉ dẫn trong prompt, và prompt thường thắng.

- [ ] **Step 1: Đọc mục Điều phối hiện tại**

Run: `cd /d/Project/Javis-OS && sed -n '18,40p' CLAUDE.md`

Ghi lại nguyên văn bậc 2 (Kanban task), bậc 6 (Nhắc hẹn), bậc 7 (Loop).

- [ ] **Step 2: Sửa CLAUDE.md**

Bậc 6 hiện tại (sau giai đoạn 1): `6. **Tạo Nhắc hẹn** - nhắc nhở / job có MỐC GIỜ cố định → `POST /reminders` (xem ở trang Việc).`

Đổi thành:

```markdown
6. **Tạo Nhắc hẹn** - nhắc nhở / job có MỐC GIỜ cố định → gọi tool `javis_schedule` (op=create, notify_only=true nếu chỉ nhắc). Xem lại ở trang Việc định kỳ.
```

Bậc 7 hiện tại nói loop ghi file `Javis/loops/<slug>.md`. Thêm vào ĐẦU phần format loop một câu:

```markdown
**Ưu tiên gọi tool `javis_schedule` (op=create) thay vì tự ghi file** - tool tự đặt đúng slug, đúng frontmatter, chặn trùng tên, và tự chọn kho (việc lặp → file .md; nhắc/cron → kho nhắc hẹn). Chỉ ghi file tay khi cần trường nâng cao mà tool chưa nhận (quiet_hours, max_runs_per_day, workspace, ambient_mcp).
```

**Giữ nguyên** phần mô tả format file loop bên dưới: nó vẫn đúng, và người dùng lẫn model vẫn cần biết để SỬA loop đã có.

- [ ] **Step 3: Kiểm tra không còn chỗ nào dạy curl**

Run: `cd /d/Project/Javis-OS && grep -n "curl\|POST /reminders\|POST /kanban" CLAUDE.md`

Với mỗi hit: nếu nó dạy model tự gọi HTTP để đặt lịch/nhắc, đổi sang gọi `javis_schedule`. Nếu là chuyện khác (vd Kanban task) thì để yên - plan này không đụng Kanban.

- [ ] **Step 4: Bump VERSION + CHANGELOG**

Đọc `VERSION`, tăng patch. Đọc khối `## [0.9.69]` trong `CHANGELOG.md` để bám giọng: chủ dự án viết CHANGELOG **giải thích nguyên nhân gốc kèm bằng chứng file:line**, không chỉ liệt kê. Thêm khối mới trên cùng, nhóm `### Thêm mới` và `### Sửa lỗi`, phủ:
- Tool `javis_schedule`: trước đây chat phải gõ YAML tay hoặc curl; vì sao là plugin chứ không phải hub (hai rào: `mcp_hub.py:213` early-return, `claude_config_path` trả None khi chưa có connector).
- Bug plugin mù brain (Task 1): ảnh của `javis_generate_image` gọi từ Claude Code luôn lưu vào Brain Default.

- [ ] **Step 5: Chạy toàn bộ test như CI**

Run: `cd server && for f in test_*.py; do echo "--- $f"; ../.venv/Scripts/python.exe "$f" || echo "FAIL: $f"; done`

Expected: mọi file in `OK - ...`.

Run: `cd /d/Project/Javis-OS && .venv/Scripts/python.exe -m compileall -q server system/plugins`

Expected: không output.

- [ ] **Step 6: Commit + push**

```bash
git add CLAUDE.md CHANGELOG.md VERSION
git commit -m "docs(schedule): day Jarvis 007 goi javis_schedule thay vi go YAML tay

Tool ton tai ma system prompt van day 'ghi file Javis/loops/<slug>.md' thi model
van go YAML tay: mo ta tool canh tranh truc tiep voi chi dan trong prompt, va
prompt thuong thang.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push origin main
```

---

## Kiểm tra bằng mắt (BẮT BUỘC trước khi coi là xong)

Giai đoạn 1 dạy một bài đắt: **mọi kiểm chứng tĩnh đều xanh mà vẫn suýt ship bản hỏng** (quy ước cache-bust `?v=` không nằm trong plan, không test nào bắt, chỉ mở trình duyệt mới lộ). Task 1 và 2 ở đây động vào đường tool của engine THẬT, mà không test đơn vị nào chứng minh được Claude Code thực sự NHÌN THẤY và GỌI ĐƯỢC tool.

Nên sau Task 3, phải làm bằng tay:

1. Khởi động lại server (code mới), mở dashboard, đăng nhập.
2. Chat: *"tạo cho anh một việc mỗi 2 tiếng đọc source mới rồi đề xuất wiki"*. Kỳ vọng: Jarvis 007 **gọi tool** (không gõ YAML), báo đã tạo, và `brains/<brain đang dùng>/Javis/loops/doc-source-*.md` xuất hiện với `enabled: false`.
3. Kiểm tra file rơi vào **ĐÚNG brain đang mở**, không phải Brain Default. Đây là điểm chính Task 1 sửa.
4. Chat: *"30 phút nữa nhắc anh gọi cho khách"*. Kỳ vọng: vào kho nhắc hẹn (không đẻ file .md), và hiện ở khối "Nhắc hẹn đang chờ" trên trang Việc định kỳ.
5. Chat: *"anh đang có những việc định kỳ nào"*. Kỳ vọng: `op=list` liệt kê **cả hai** thứ vừa tạo.
6. Mở trang Việc định kỳ: thấy loop mới (đang tắt) + nhắc hẹn đang chờ.
7. Xoá dọn: tắt/xoá loop thử nghiệm, huỷ nhắc thử nghiệm.

## Ngoài phạm vi plan này

- **Scoping connector + `allow_real_actions`** (bỏ dial 3 nấc). Plan riêng, rủi ro cao nhất vì phải sửa hub - lớp cứng, sai là hỏng rào cho MỌI engine.
- **Cron trên loop** (`schedule` một field + jitter). **Đã hoãn có chủ ý (YAGNI)**: `reminders.py` đã có cron 5 trường đầy đủ (`cron_util.py`, tự tính lần kế ở `reminders.py:364`) và mode `task` chạy engine thật (`reminders.py:426`), nên "7h sáng chạy báo cáo" đã làm được. Chỉ làm khi thực sự cần việc BỀN (file .md sửa trong Obsidian) chạy theo đồng hồ - reminders phù du và chạy cứng ở mức `safe_tools`.
- Số phận 5 route shim legacy `/loop/*` (`self_improve.py:988-1036`).
- Kanban task (`op=create` không route sang Kanban - Kanban là máy trạng thái, không có đồng hồ).
