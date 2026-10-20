"""Nhờ Javis qua chat thêm một MCP thì nó phải HIỆN ở trang Kết nối.

    python tests/run.py them_mcp_qua_chat

Bug gốc (người dùng báo 2026-08-06): "yêu cầu Javis thêm mcp nào đó thì nó đang không hiện ra
phần kết nối". Nguyên nhân: Javis không có tool nào ghi được vào kho kết nối, nên đường duy nhất
là `claude mcp add` - thứ rơi vào config riêng của Claude Code, không nằm ở khu "Đã kết nối" của
trang Kết nối mà lọt xuống khu gập "Kết nối sẵn của Claude Code và Codex" (mặc định ĐÓNG).

Test này canh plugin bundled `javis-connect`, và canh mạnh nhất đúng cái người dùng cần: kể cả khi
thử kết nối THẤT BẠI, mục đó vẫn phải nằm lại kho để họ nhìn thấy và biết vì sao chưa chạy - khác
hẳn `/connect/add` (xoá sạch khi validate lỗi, hợp lý cho form nhưng sai cho chat).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import mcp_store

PLUGIN_DIR = ROOT / "system" / "plugins" / "javis-connect"

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


def nap_plugin():
    spec = importlib.util.spec_from_file_location("javis_connect_plugin", PLUGIN_DIR / "plugin.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


plugin = nap_plugin()

# Kho riêng cho test: KHÔNG đụng mcp_servers.json thật. Phải chặn cả _LEGACY_STORE, vì _load()
# rơi về vị trí cũ (server/mcp_servers.json) khi STORE chưa tồn tại - trên máy dev file đó có thật.
_tmp = Path(tempfile.mkdtemp(prefix="javis-mcp-test-"))
mcp_store.STORE = _tmp / "mcp_servers.json"
mcp_store._LEGACY_STORE = _tmp / "khong-co.json"
mcp_store.CONFIG = _tmp / ".mcp_config.json"


def chay(**kw):
    return asyncio.run(plugin._chay(kw, None))


def so_luong():
    return len(mcp_store.list_connections())


def tim_theo_ten(ten):
    return next((c for c in mcp_store.list_connections() if c.get("label") == ten), None)


# ---- manifest ----
raw_yaml = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8")
raw_py = (PLUGIN_DIR / "plugin.py").read_text(encoding="utf-8")
check("manifest khai đúng tool javis_add_mcp", "javis_add_mcp" in raw_yaml)
check("manifest min_mode: safe (chế độ chỉ đọc không đấu được nguồn)", "min_mode: safe" in raw_yaml)
check("plugin không có em dash (U+2014)", "—" not in raw_yaml and "—" not in raw_py)

# ---- đọc header/env model gõ ra ----
check("headers dạng dict", plugin._cap_key_value({"Authorization": "Bearer x"}, ":") == {"Authorization": "Bearer x"})
check("headers dạng dòng 'Khoá: giá trị'",
      plugin._cap_key_value("Authorization: Bearer abc\nX-Shop: 12", ":")
      == {"Authorization": "Bearer abc", "X-Shop": "12"})
check("headers dạng chuỗi JSON",
      plugin._cap_key_value('{"X-Key":"abc"}', ":") == {"X-Key": "abc"})
check("env dạng dòng 'KHOA=giá trị'", plugin._cap_key_value("API_KEY=abc\nMODE=live", "=")
      == {"API_KEY": "abc", "MODE": "live"})
check("args dạng chuỗi dòng lệnh", plugin._tham_so("-y @abc/mcp-server") == ["-y", "@abc/mcp-server"])
check("args dạng mảng", plugin._tham_so(["-y", "abc"]) == ["-y", "abc"])

# ---- op sai / thiếu tham số ----
check("op lạ bị từ chối", chay(op="xoa").startswith("ERROR"))
check("thiếu name thì báo lỗi", chay(op="add", url="https://a.b/mcp").startswith("ERROR"))
r = chay(op="add", name="Nguồn lạ chưa từng có")
check("thiếu cả url lẫn command thì báo lỗi", r.startswith("ERROR"))
check("kho vẫn trống sau các lượt lỗi", so_luong() == 0)

# ---- dịch vụ ĐÃ CÓ trong Kho kết nối thì chỉ sang card, không đẻ bản custom song song ----
r = chay(op="add", name="Gmail")
check("Gmail (có sẵn trong kho) không bị thêm kiểu tự khai", "Connection store" in r)
check("Gmail không tạo connection rỗng token", so_luong() == 0)
r = chay(op="find", name="gmail")
check("op=find tra được kho", "Gmail" in r)

# ---- stdio: thêm được nhưng ĐỂ TẮT (dial thử là chạy lệnh trên máy chủ) ----
r = chay(op="add", name="Máy chủ thử", command="npx -y @abc/mcp-server")
c = tim_theo_ten("Máy chủ thử")
check("stdio được thêm vào kho", c is not None)
check("stdio để TẮT, chờ người dùng duyệt", bool(c) and c.get("enabled") is False)
check("lệnh gõ nguyên cụm được tách đúng",
      bool(c) and c.get("command") == "npx" and list(c.get("args") or []) == ["-y", "@abc/mcp-server"])
check("câu trả lời chỉ đường tới trang Kết nối", "Connections page" in r)

# ---- http: thử kết nối OK thì bật, và mức quyền mặc định là chỉ đọc ----
import mcp_hub  # noqa: E402  - nạp sau khi đã trỏ kho sang thư mục tạm


async def _val_ok(cid):
    return {"ok": True, "label": "", "tools": 7, "error": ""}


async def _val_fail(cid):
    return {"ok": False, "label": "", "tools": 0, "error": "Không kết nối được (ConnectError)"}


mcp_hub.validate_connection = _val_ok
r = chay(op="add", name="Context7", url="https://mcp.context7.com/mcp",
         headers="Authorization: Bearer abc")
c = tim_theo_ten("Context7")
check("MCP qua mạng đấu được từ chat", c is not None)
check("thử kết nối OK thì để BẬT", bool(c) and c.get("enabled") is True)
check("mức quyền mặc định là chỉ đọc (Javis không tự nâng quyền)", bool(c) and c.get("perm") == "readonly")
check("header xác thực có được lưu", bool(c) and "Authorization" in (c.get("header_keys") or []))
check("báo lại số tool tìm thấy", "7 tool" in r)

# ---- ĐIỂM MẤU CHỐT: thử kết nối HỎNG thì vẫn phải nằm lại kho cho người dùng thấy ----
mcp_hub.validate_connection = _val_fail
truoc = so_luong()
r = chay(op="add", name="Nguồn hỏng", url="https://khong-ton-tai.example/mcp")
c = tim_theo_ten("Nguồn hỏng")
check("kết nối lỗi vẫn được giữ lại trong kho (không xoá như form web)", c is not None)
check("kho tăng đúng 1 mục", so_luong() == truoc + 1)
check("mục lỗi để TẮT", bool(c) and c.get("enabled") is False)
check("câu trả lời nêu nguyên văn lỗi", "ConnectError" in r)

# ---- không đẻ bản sao khi nhờ thêm lần nữa ----
mcp_hub.validate_connection = _val_ok
truoc = so_luong()
r = chay(op="add", name="Context7 lần hai", url="https://mcp.context7.com/mcp/")
check("URL trùng thì không thêm nữa", so_luong() == truoc)
check("nói rõ là đã có sẵn", "Already exists" in r)
truoc = so_luong()
chay(op="add", name="stdio lần hai", command="npx", args="-y @abc/mcp-server")
check("lệnh stdio trùng thì không thêm nữa", so_luong() == truoc)

# ---- perm chỉ nâng khi được truyền rõ ----
r = chay(op="add", name="Nguồn full quyền", url="https://x.example/mcp", perm="full")
c = tim_theo_ten("Nguồn full quyền")
check("perm truyền rõ thì tôn trọng", bool(c) and c.get("perm") == "full")

# ---- luật trong system prompt: engine phải biết dùng tool này thay cho claude mcp add ----
rule = (SERVER / "channel_context.py").read_text(encoding="utf-8")
check("system prompt dặn dùng javis_add_mcp", "javis_add_mcp" in rule)
check("system prompt cấm claude mcp add", "claude mcp add" in rule)

# ---- kho ghi ra đúng file JSON v2 ----
d = json.loads(mcp_store.STORE.read_text(encoding="utf-8"))
check("file kho đúng định dạng v2", d.get("version") == 2 and isinstance(d.get("connections"), list))

print()
if _fails:
    print(f"{len(_fails)} lỗi: " + ", ".join(_fails))
    sys.exit(1)
print("Tất cả OK")
