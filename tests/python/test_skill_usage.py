"""Test sidecar telemetry skill (skill_usage). Chạy tay / CI:

    python tests/run.py skill_usage

Không cần pytest, không chạm mạng. Tự cô lập sang thư mục tạm, KHÔNG để lại rác
ngoài thư mục tạm.
Phủ: bump tăng đúng, ghi atomic, file thiếu, file JSON hỏng, brain root không ghi được,
gọi song song (không mất bump), is_stale (pinned / có use_count / chưa đủ già / đủ già).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path (xem tests/python/_paths.py)
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-usagetest-"))

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
      skill_usage.usage_path(_ROOT) == _ROOT / "Javis" / "skill-usage.json")
check("sidecar thật sự tồn tại trên đĩa", skill_usage.usage_path(_ROOT).is_file())

# ---- file hỏng: KHÔNG được làm gãy ----
skill_usage.usage_path(_ROOT).write_text("{ day khong phai json", encoding="utf-8")
check("sidecar hỏng → read_usage trả {} chứ không raise", skill_usage.read_usage(_ROOT) == {})
try:
    skill_usage.bump(_ROOT, "viet-email")
    check("sidecar hỏng → bump không raise", True)
except Exception as e:
    check(f"sidecar hỏng → bump không raise (raised {e!r})", False)

# ---- brain root KHÔNG ghi được: vẫn không raise ----
# Mẹo: lấy một FILE thường rồi truyền vào như thể nó là brain root. _write_atomic sẽ
# mkdir("<file>/Javis") → OS ném NotADirectoryError/FileExistsError trên MỌI nền tảng.
# KHÔNG dùng đường dẫn kiểu "/khong/ton/tai": trên Windows "/" resolve theo ổ đĩa hiện
# tại nên mkdir THÀNH CÔNG, nhánh except không bao giờ chạy (test rởm) và còn ghi rác ra
# đĩa thật. CI ở đây là win32 nên đây là lỗi thật, không phải khác biệt lý thuyết.
_fd_bogus, _bogus_file = tempfile.mkstemp(prefix="javis-usagebogus-")
os.close(_fd_bogus)
_BOGUS_ROOT = Path(_bogus_file)
try:
    skill_usage.bump(_BOGUS_ROOT, "x")
    check("brain root không ghi được → bump nuốt lỗi, không raise", True)
except Exception as e:
    check(f"brain root không ghi được → bump nuốt lỗi, không raise (raised {e!r})", False)
check("brain root không ghi được → read_usage trả {}", skill_usage.read_usage(_BOGUS_ROOT) == {})
check("brain root không ghi được → không có gì được tạo dưới file đó",
      _BOGUS_ROOT.is_file() and not (_BOGUS_ROOT / "Javis").exists())
os.unlink(_bogus_file)

# ---- gọi song song: _LOCK phải serialize read-modify-write, KHÔNG được mất bump nào ----
# Khẳng định ĐÚNG BẰNG 80, không phải khoảng. bump chạy 1 process, _LOCK bọc trọn vòng
# đọc-sửa-ghi nên kết quả duy nhất đúng là 80. Nếu để khoảng (0 < n <= 80) thì gỡ _LOCK ra
# test vẫn xanh dù bump bị nuốt do race - tức là chỉ chứng minh "không sập", đúng thứ mà
# test này KHÔNG có nhiệm vụ chứng minh.
import threading  # noqa: E402

_R2 = Path(tempfile.mkdtemp(prefix="javis-usagepar-"))


def _hammer():
    for _ in range(20):
        skill_usage.bump(_R2, "dua-xe")


_ts = [threading.Thread(target=_hammer) for _ in range(4)]
[t.start() for t in _ts]
[t.join() for t in _ts]
_n = skill_usage.read_usage(_R2).get("dua-xe", {}).get("use_count", 0)
check(f"4 luồng x 20 bump → không mất bump nào, use_count={_n} (phải đúng 80)", _n == 80)

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

# ---- sidecar bị TAY SỬA HỎNG: is_stale/bump phải KHÔNG raise, không sập trang Studio ----
# (review cuối trước release: main.py:2166 và skill_usage.py từng int(...) trần không có
# type guard - {"slug": "hello"} hoặc {"slug": {"use_count": "abc"}} sẽ raise, 500 GET /skills,
# và bump từng nuốt lỗi rồi để bản ghi hỏng nằm mãi mãi, không tự lành)

# ca A: bản ghi của SLUG là CHUỖI thay vì dict (vd '{"demo": "hello"}')
check("is_stale: bản ghi là CHUỖI thay vì dict -> không raise, coi như chưa đủ căn cứ",
      skill_usage.is_stale("hello", None, _now) is False)
check("is_stale: bản ghi là CHUỖI + có mtime cũ -> fallback tính theo mtime, không sập",
      skill_usage.is_stale("hello", _old, _now) is True)

# ca B: bản ghi là dict nhưng use_count là CHUỖI KHÔNG PHẢI SỐ (vd '{"use_count": "abc"}')
check("is_stale: use_count là chuỗi không-phải-số -> không raise, coi như 0 rồi xét tuổi",
      skill_usage.is_stale({"use_count": "abc", "created_at": _old, "pinned": False},
                            None, _now) is True)
check("is_stale: use_count là chuỗi không-phải-số + bản ghi mới tạo -> không raise, chưa stale",
      skill_usage.is_stale({"use_count": "abc", "created_at": _new, "pinned": False},
                            None, _now) is False)

# ---- bump: bản ghi hỏng phải TỰ LÀNH ở lần bump kế tiếp, không kẹt mãi mãi ----
_R3 = Path(tempfile.mkdtemp(prefix="javis-usagecorrupt-"))
_p3 = skill_usage.usage_path(_R3)
_p3.parent.mkdir(parents=True, exist_ok=True)

# ca A: bump(slug="demo") khi bản ghi của "demo" là CHUỖI thay vì dict
_p3.write_text(json.dumps({"demo": "hello"}, ensure_ascii=False), encoding="utf-8")
try:
    skill_usage.bump(_R3, "demo")
    check("bump: bản ghi slug là CHUỖI thay vì dict -> không raise", True)
except Exception as e:
    check(f"bump: bản ghi slug là CHUỖI thay vì dict -> không raise (raised {e!r})", False)
_u3a = skill_usage.read_usage(_R3)
check("bump: bản ghi chuỗi hỏng -> tự lành thành dict, use_count=1",
      isinstance(_u3a.get("demo"), dict) and _u3a.get("demo", {}).get("use_count") == 1)

# ca B: bump(slug="demo") khi bản ghi là dict nhưng use_count là CHUỖI KHÔNG PHẢI SỐ
_p3.write_text(json.dumps({"demo": {"use_count": "abc"}}, ensure_ascii=False), encoding="utf-8")
try:
    skill_usage.bump(_R3, "demo")
    check("bump: use_count là chuỗi không-phải-số -> không raise", True)
except Exception as e:
    check(f"bump: use_count là chuỗi không-phải-số -> không raise (raised {e!r})", False)
_u3b = skill_usage.read_usage(_R3)
check("bump: use_count hỏng -> tự lành thành 1 (coi hỏng như 0 rồi +1), KHÔNG kẹt mãi mãi",
      _u3b.get("demo", {}).get("use_count") == 1)

# gọi bump thêm 1 lần: bản ghi đã lành THẬT SỰ (không chỉ né lỗi 1 lần rồi hỏng lại) nên
# lần sau phải cộng dồn bình thường, không tự-lành-lại-mỗi-lần (nếu vậy sẽ luôn kẹt ở 1)
skill_usage.bump(_R3, "demo")
_u3c = skill_usage.read_usage(_R3)
check("bump: sau khi lành, lần bump tiếp theo cộng dồn bình thường (use_count=2)",
      _u3c.get("demo", {}).get("use_count") == 2)

# ---- javis_use_skill (mcp_hub): bump đúng tại điểm nghẽn duy nhất ----
# Test HÀNH VI THẬT qua handler (gọi thẳng route["javis_use_skill"]["call"]), KHÔNG quét
# source text - quét chuỗi không phân biệt được code sống với comment/code chết.
import asyncio  # noqa: E402
import shutil  # noqa: E402

import mcp_hub  # noqa: E402

_HUB_ROOT = Path(tempfile.mkdtemp(prefix="javis-hubtest-"))
_HUB_SLUG = "skill-that-ban-dung-thu"
_HUB_SKILL_DIR = _HUB_ROOT / "skills" / _HUB_SLUG
_HUB_SKILL_DIR.mkdir(parents=True)
_HUB_CONTENT = ("---\nname: Demo\ndescription: skill demo cho test hub\ngroup: Test\n---\n"
                "Noi dung that cua skill, dung de doi chieu return value.")
(_HUB_SKILL_DIR / "SKILL.md").write_text(_HUB_CONTENT, encoding="utf-8")

_hub_tools, _hub_route = mcp_hub._builtin_tools("auto", str(_HUB_ROOT))
check("_builtin_tools đăng ký javis_use_skill khi có vault_root thật",
      "javis_use_skill" in _hub_route)
_hub_handler = _hub_route["javis_use_skill"]["call"]

_out1 = asyncio.run(_hub_handler({"name": _HUB_SLUG}))
check("handler trả đúng nội dung SKILL.md thật (bump không nuốt/đổi kết quả trả về)",
      _out1 == _HUB_CONTENT)
_u = skill_usage.read_usage(_HUB_ROOT)
check("gọi javis_use_skill lần 1 → use_count = 1", _u.get(_HUB_SLUG, {}).get("use_count") == 1)

asyncio.run(_hub_handler({"name": _HUB_SLUG}))
_u = skill_usage.read_usage(_HUB_ROOT)
check("gọi javis_use_skill lần 2 → use_count = 2", _u.get(_HUB_SLUG, {}).get("use_count") == 2)

# slug sai (gõ nhầm): KHÔNG được đếm, KHÔNG được tạo bản ghi rác
_out_bad = asyncio.run(_hub_handler({"name": "slug-khong-ton-tai"}))
check("slug sai → trả lỗi rõ ràng (bắt đầu bằng ERROR)", _out_bad.startswith("ERROR"))
_u = skill_usage.read_usage(_HUB_ROOT)
check("slug sai → KHÔNG tạo bản ghi rác cho slug đó", "slug-khong-ton-tai" not in _u)
check("slug sai → không đếm nhầm sang skill khác (use_count không đổi)",
      _u.get(_HUB_SLUG, {}).get("use_count") == 2)

# sidecar hỏng (Javis/ bị 1 FILE THƯỜNG chiếm chỗ → mkdir thất bại khi bump ghi) → việc nạp
# skill KHÔNG ĐƯỢC gãy theo. Đây là hợp đồng chịu lỗi cốt lõi của skill_usage.bump.
_HUB_ROOT2 = Path(tempfile.mkdtemp(prefix="javis-hubtest-broken-"))
_HUB_SLUG2 = "skill-sidecar-hong"
_HUB_SKILL_DIR2 = _HUB_ROOT2 / "skills" / _HUB_SLUG2
_HUB_SKILL_DIR2.mkdir(parents=True)
_HUB_CONTENT2 = "---\nname: Demo2\ndescription: skill sidecar hong\ngroup: Test\n---\nNoi dung 2."
(_HUB_SKILL_DIR2 / "SKILL.md").write_text(_HUB_CONTENT2, encoding="utf-8")
(_HUB_ROOT2 / "Javis").write_text("chiem cho, khong phai thu muc", encoding="utf-8")

_hub_tools2, _hub_route2 = mcp_hub._builtin_tools("auto", str(_HUB_ROOT2))
_hub_handler2 = _hub_route2["javis_use_skill"]["call"]
try:
    _out2 = asyncio.run(_hub_handler2({"name": _HUB_SLUG2}))
    check("sidecar hỏng (Javis/ bị file chiếm chỗ) → handler vẫn trả nội dung thật, không raise",
          _out2 == _HUB_CONTENT2)
except Exception as e:
    check(f"sidecar hỏng → handler không raise (raised {e!r})", False)

shutil.rmtree(_HUB_ROOT, ignore_errors=True)
shutil.rmtree(_HUB_ROOT2, ignore_errors=True)

# ---- GET /skills lộ usage: kiểm CẤU TRÚC qua AST (không phải quét chuỗi thô) ----
# import main.py thật để test HÀNH VI (gọi endpoint) đòi dựng cả app FastAPI - nặng + tác dụng
# phụ lúc import, chủ đích loại khỏi bộ test này (đã chốt riêng ở brief). Hành vi THẬT của
# read_usage/is_stale tự thân đã được test bằng behavioral test ở trên (đọc/ghi sidecar, mọi
# nhánh is_stale). Việc còn thiếu người coi là chấp nhận được: chứng minh GET /skills THỰC SỰ
# NỐI vào hai hàm đó, dùng AST thay vì so chuỗi - so chuỗi không phân biệt nổi code sống với
# comment/code chết (bài học rút ra từ test_skill_caps.py, xem chú thích ở đó).
#
# GIỚI HẠN (nói thẳng): đây vẫn là phân tích TĨNH, không chạy endpoint. Nó chứng minh hàm
# list_skills GỌI đúng skill_usage.read_usage/is_stale và gán is_stale(...) TRỰC TIẾP vào key
# "stale" của dict trả về. Nó KHÔNG chứng minh HTTP response thật trả đúng giá trị lúc chạy (vd
# lỗi ở tầng skill_router hay FastAPI serialize), và không miễn nhiễm 100% với mọi kiểu code
# chết (vd lồng trong "if False:" ast.walk vẫn thấy) - chỉ mạnh hơn so chuỗi thô một bậc.
import ast  # noqa: E402

_main_path = SERVER / "main.py"
_main_tree = ast.parse(_main_path.read_text(encoding="utf-8"))

# 0.9.243: phần dựng chỉ mục đã bóc khỏi handler sang hàm thuần `skills_index`, để Telegram
# gọi được mà không phải gọi route handler như hàm thường. Handler giờ chỉ là vỏ HTTP mỏng,
# nên soi nó bằng AST sẽ không thấy gì. Soi ĐÚNG hàm mang hành vi thay vì đúng cái tên cũ.
_list_skills = next((n for n in ast.walk(_main_tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == "skills_index"), None)
check("tìm thấy hàm skills_index (lõi của GET /skills) trong main.py (AST)",
      _list_skills is not None)

# Và handler PHẢI thật sự dùng lõi đó, không được tự dựng lại một đường khác.
_handler = next((n for n in ast.walk(_main_tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == "list_skills"), None)
check("handler GET /skills gọi skills_index (không tự dựng lại)",
      _handler is not None and any(
          isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "skills_index"
          for n in ast.walk(_handler)))


def _is_call_to(node, module, attr):
    """True nếu node là lời gọi <module>.<attr>(...) (AST Call, không phải chuỗi/comment)."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr and isinstance(node.func.value, ast.Name)
            and node.func.value.id == module)


if _list_skills is not None:
    _ru_assign = [n for n in ast.walk(_list_skills)
                  if isinstance(n, ast.Assign) and _is_call_to(n.value, "skill_usage", "read_usage")]
    check("skills_index gọi skill_usage.read_usage(...) và gán vào biến (AST)", bool(_ru_assign))

    _is_calls = [n for n in ast.walk(_list_skills) if _is_call_to(n, "skill_usage", "is_stale")]
    check("skills_index gọi skill_usage.is_stale(...) (AST)", bool(_is_calls))

    _stale_wired = _has_use_count_key = _has_last_used_key = False
    for node in ast.walk(_list_skills):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if not isinstance(k, ast.Constant):
                    continue
                if k.value == "stale" and _is_call_to(v, "skill_usage", "is_stale"):
                    _stale_wired = True
                if k.value == "use_count":
                    _has_use_count_key = True
                if k.value == "last_used_at":
                    _has_last_used_key = True
    check("key 'stale' trong dict trả về được gán TRỰC TIẾP từ skill_usage.is_stale(...) "
          "(AST - chặn kiểu gọi rồi vứt kết quả, không nối vào response)", _stale_wired)
    check("dict trả về của GET /skills có key 'use_count'", _has_use_count_key)
    check("dict trả về của GET /skills có key 'last_used_at'", _has_last_used_key)

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

# Byte trên đĩa phải là LF: write_text không có newline="\n" sẽ dịch \n -> os.linesep (CRLF
# trên Windows). Hiện chỉ vô hại nhờ core.autocrlf=true; deploy chạy autocrlf=false thì merge
# lên .gitignore đã commit dạng LF sẽ đẻ diff đổi line-ending TOÀN FILE. Đọc BINARY, không
# đọc text (read_text dịch ngược CRLF->\n nên sẽ không bao giờ thấy lỗi này).
check("reconcile ghi LF thuần, không CRLF (đọc nhị phân)",
      b"\r\n" not in (_gi_root / ".gitignore").read_bytes())

_gi_fresh = Path(tempfile.mkdtemp(prefix="javis-gifresh-"))
git_brain._ensure_gitignore_lines(_gi_fresh)
check("file .gitignore dựng mới cũng LF thuần",
      b"\r\n" not in (_gi_fresh / ".gitignore").read_bytes())

# ---- commit vá .gitignore PHẢI giành BrainLock ----
# Vì sao quan trọng: commit_paths chạy `git commit` = commit CẢ INDEX. Một learn/curator chạy
# song song vừa `git add` file của nó thì commit 'chore:' sẽ cuốn tri thức đó vào commit KHÔNG
# hiện ở Review UI + revert_last_learn KHÔNG undo được. Test HÀNH VI: giữ sẵn BrainLock (giả
# lập learn đang ghi) rồi gọi ensure_git_repo -> KHÔNG được sinh commit mới.
# Toàn bộ chạy trong thư mục tạm, KHÔNG đụng repo thật / brains thật.
import subprocess  # noqa: E402


def _git_q(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


if not git_brain.has_git():
    # Cố tình BÁO LỖI chứ không "skip" im lặng: test bị bỏ qua âm thầm = test luôn-xanh, đúng
    # cái bẫy file này đã dính 1 lần (xem chú thích khẳng-định-80 ở trên). git là phụ thuộc
    # cứng của chính tính năng đang test - không có git thì git_brain vô nghĩa.
    check("máy không có git → KHÔNG kiểm được khoá lúc commit (cần git dựng repo tạm)", False)
else:
    _lk_root = Path(tempfile.mkdtemp(prefix="javis-gilock-"))
    # brain CŨ: đã là repo, .gitignore cũ thiếu dòng sidecar (đúng ca brains/Brain Default)
    (_lk_root / ".gitignore").write_text("Javis/learn-log/\n", encoding="utf-8", newline="\n")
    _git_q(_lk_root, "init")
    _git_q(_lk_root, "config", "user.email", "test@localhost")
    _git_q(_lk_root, "config", "user.name", "Test")
    _git_q(_lk_root, "add", ".gitignore")
    _git_q(_lk_root, "commit", "-m", "chore: baseline")
    _n_before = len(_git_q(_lk_root, "log", "--oneline").stdout.strip().splitlines())

    _held = git_brain.BrainLock(str(_lk_root), timeout=1)
    check("dựng được cảnh: giành BrainLock trước (giả lập learn đang ghi)", _held.acquire() is True)
    _t0 = time.time()
    try:
        _r_locked = git_brain.ensure_git_repo(str(_lk_root))
    finally:
        _held.release()
    _stall = time.time() - _t0
    _n_after = len(_git_q(_lk_root, "log", "--oneline").stdout.strip().splitlines())
    _txt_locked = (_lk_root / ".gitignore").read_text(encoding="utf-8")

    check("kẹt khoá → ensure_git_repo vẫn trả ok (không gãy luồng bật học)",
          _r_locked.get("ok") is True and _r_locked.get("created") is False)
    check("kẹt khoá → KHÔNG sinh commit nào (không cuốn index của learn đang chạy)",
          _n_after == _n_before)
    check("kẹt khoá → .gitignore trên đĩa VẪN được vá (git đọc ignore từ working tree)",
          "Javis/skill-usage.json" in _txt_locked)
    # ensure_git_repo bị gọi THẲNG (không qua asyncio.to_thread) từ 2 handler async, mà
    # BrainLock.acquire() chờ bằng time.sleep CHẶN → chờ lâu = đóng băng CẢ event loop. Phải
    # fail nhanh (timeout=1.0), không dùng mặc định 30s. Ngưỡng 10s rộng rãi để không nhạy với
    # máy CI chậm, nhưng vẫn bắt được nếu ai đó trả về mặc định 30s. Đo lại chính lời gọi kẹt
    # khoá ở trên nên không tốn thêm thời gian chạy.
    check(f"kẹt khoá → fail nhanh, không treo event loop (chặn {_stall:.2f}s, phải < 10s)",
          _stall < 10)

    # thả khoá ra → lần gọi sau commit được bình thường, prefix chore:
    _r_free = git_brain.ensure_git_repo(str(_lk_root))
    _log_free = _git_q(_lk_root, "log", "--oneline").stdout
    _n_free = len(_log_free.strip().splitlines())
    check("thả khoá → lần gọi sau commit được đúng 1 commit vá .gitignore",
          _n_free == _n_before + 1)
    check("commit vá .gitignore mang prefix 'chore:' (không lọt Review UI / không bị undo)",
          "chore: update brain .gitignore" in _log_free)
    check("commit vá .gitignore KHÔNG khớp LEARN_COMMIT_PREFIXES",
          not any("chore: update brain .gitignore".startswith(p)
                  for p in git_brain.LEARN_COMMIT_PREFIXES))
    check("sau khi commit xong, working tree sạch (.gitignore không còn dirty)",
          not git_brain.working_tree_dirty(str(_lk_root)))

if _fails:
    print(f"\nFAIL - test_skill_usage: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_skill_usage: tất cả pass")
