"""Plugin bundled: tool `javis_add_mcp` - đấu thêm MCP server vào kho Kết nối của Javis.

Vì sao tool này tồn tại
=======================
Người dùng bảo "thêm MCP này cho anh" thì trước bản này Javis không có đường nào ĐÚNG để làm.
Kho kết nối chỉ ghi được qua endpoint `/connect/add`, mà endpoint đó nằm sau lớp đăng nhập nên
chỉ trang web gọi được. Còn lại Javis chỉ có hai lối, cả hai đều hỏng theo cách riêng:

1. Chạy `claude mcp add ...` bằng Bash. Server đó rơi vào config RIÊNG của Claude Code, nên
   (a) chỉ mỗi engine Claude thấy, sáu bộ não còn lại đứng ngoài, (b) trên trang Kết nối nó
   không nằm ở khu "Đã kết nối" mà lọt xuống khu gập "Kết nối sẵn của Claude Code và Codex",
   khu này mặc định ĐÓNG và chỉ tải khi bấm mở. Người dùng nhìn trang Kết nối thấy y như cũ và
   kết luận Javis nói dối. Đó chính là bug được báo.
2. Nói suông "anh vào trang Kết nối tự thêm nhé". Đúng nhưng vô dụng, vì việc này Javis làm được.

Tool này đi thẳng vào `mcp_store` - CÙNG một kho mà trang Kết nối đọc (`/connect/catalog`), nên
thêm xong là thấy ngay ở khu "Đã kết nối", dùng chung cho MỌI bộ não qua hub, có phân quyền và
nhật ký như tài khoản đấu bằng tay.

An toàn (BẮT BUỘC, không tham số nào mở được)
=============================================
- `min_mode="safe"`: chế độ suggest/chỉ-đọc KHÔNG đấu được nguồn mới.
- Mức quyền mặc định là `readonly`. Luật `CLAUDE.md`: "Javis KHÔNG tự nâng quyền - user tự nâng ở
  trang Kết nối". Model chỉ được truyền `perm` cao hơn khi người dùng nói rõ họ muốn vậy, và câu
  trả lời phải nói ra mình đã đặt mức nào.
- Transport `stdio` = CHẠY MỘT LỆNH trên máy chủ Javis. Thêm xong để TẮT, không thử kết nối, vì
  chỉ riêng việc dial thử đã là chạy lệnh đó. Người dùng tự đọc lệnh rồi bật ở trang Kết nối.
  Không có tham số nào bật thẳng được: engine API vốn không có Bash, cho nó đẻ một stdio tự chạy
  là mở cửa hậu đúng bằng Bash.
- Dịch vụ đã có sẵn trong Kho kết nối (Gmail, Lịch, POS...) thì KHÔNG đẻ bản "custom" song song.
  Chúng cần đăng nhập OAuth hoặc key theo mẫu riêng; tool chỉ tay sang đúng card, vì một
  connection rỗng token nằm lại trang Kết nối trông y hệt tài khoản thật mà không chạy được
  (chính là vụ Meta Ads "xoá rồi cứ mọc lại" đã phải vá bằng tay ở `/connect/oauth/start`).
"""
from __future__ import annotations

import json
import re
import shlex

import mcp_catalog
import mcp_store

# Trần ký tự cho phần liệt kê ở op=find. Kết quả tool đi thẳng vào ngữ cảnh lượt chat và engine
# API còn bị cắt ở 8000 ký tự (engine._clip_tool_result) - kể cả kho 30 connector cũng không được
# nuốt mất câu hỏi của người dùng.
_FIND_MAX = 12

_TEN_HOP_LE = re.compile(r"^[^\x00-\x1f]{1,60}$")


def _chuoi(v) -> str:
    return str(v or "").strip()


def _cap_key_value(raw, dau_phan_cach) -> dict:
    """Đọc header/env model gõ ra. Nhận cả ba dạng vì mỗi model quen một kiểu: dict thật, chuỗi
    JSON, hoặc nhiều dòng "Khoá: giá trị" / "KHOA=giá trị". Dạng lạ thì bỏ qua chứ không nổ."""
    if isinstance(raw, dict):
        return {_chuoi(k): _chuoi(v) for k, v in raw.items() if _chuoi(k) and _chuoi(v)}
    text = _chuoi(raw)
    if not text:
        return {}
    if text.startswith("{"):
        try:
            d = json.loads(text)
            if isinstance(d, dict):
                return {_chuoi(k): _chuoi(v) for k, v in d.items() if _chuoi(k) and _chuoi(v)}
        except ValueError:
            pass
    out = {}
    for dong in text.replace("\\n", "\n").split("\n"):
        dong = dong.strip().lstrip("-").strip()
        if not dong or dau_phan_cach not in dong:
            continue
        k, v = dong.split(dau_phan_cach, 1)
        if _chuoi(k) and _chuoi(v):
            out[_chuoi(k)] = _chuoi(v)
    return out


def _tham_so(raw) -> list:
    """args của lệnh stdio: nhận mảng sẵn, hoặc chuỗi kiểu dòng lệnh ("-y abc --port 3000")."""
    if isinstance(raw, (list, tuple)):
        return [_chuoi(x) for x in raw if _chuoi(x)]
    text = _chuoi(raw)
    if not text:
        return []
    try:
        return [x for x in shlex.split(text) if x]
    except ValueError:
        return [x for x in text.split() if x]


def _chuan_url(u: str) -> str:
    return _chuoi(u).rstrip("/").lower()


def _trung(url: str, command: str, args: list):
    """Connection ĐÃ CÓ trỏ cùng chỗ, hoặc None. Chặn đẻ bản sao khi người dùng nhờ hai lần."""
    u = _chuan_url(url)
    cmd = _chuoi(command)
    for c in mcp_store.list_connections():
        if u and _chuan_url(c.get("url")) == u:
            return c
        if cmd and _chuoi(c.get("command")) == cmd and list(c.get("args") or []) == list(args):
            return c
    return None


def _tu_kho(tu_khoa: str) -> list:
    """Connector trong Kho kết nối khớp từ khoá (tìm trong tên, id, mô tả, nhóm)."""
    q = _chuoi(tu_khoa).lower()
    if not q:
        return []
    tu = [t for t in re.split(r"[^\w]+", q, flags=re.UNICODE) if len(t) >= 2]
    out = []
    for c in mcp_catalog.public_catalog():
        moi = " ".join([c.get("id", ""), c.get("name", ""), c.get("group", ""),
                        c.get("category", ""), c.get("description", "")]).lower()
        if q in moi or (tu and all(t in moi for t in tu)):
            out.append(c)
    return out


def _mo_ta_card(c: dict) -> str:
    o = [f"- {c.get('name')} (card '{c.get('group') or c.get('name')}' in the Connection store"
         + (f", group {c.get('category')}" if c.get("category") else "") + ")"]
    if c.get("auth_type") == "oauth":
        o.append("  Needs a SIGN-IN (OAuth), so it must be clicked on the Connections page; Jarvis 007 cannot sign in for the user.")
    else:
        ten_o = ", ".join(f.get("label") or f.get("key") for f in (c.get("fields") or []))
        o.append("  To fill in: " + (ten_o or "unknown, see the Connections page") + ".")
    return "\n".join(o)


def _xem_o_dau(cid: str) -> str:
    return (f"View and edit it on the Connections page, in the 'Connected' section (id {cid}): rename, raise the permission level, "
            "turn on/off, delete.")


def _tim(args, ctx) -> str:
    q = _chuoi((args or {}).get("name")) or _chuoi((args or {}).get("url"))
    kho = _tu_kho(q)
    dang_co = mcp_store.list_connections()
    dong = []
    if kho:
        dong.append(f"The Connection store already has {len(kho)} matching services for '{q}':")
        dong += [_mo_ta_card(c) for c in kho[:_FIND_MAX]]
        if len(kho) > _FIND_MAX:
            dong.append(f"...(+{len(kho) - _FIND_MAX} more services, see them all on the Connections page)")
        dong.append("A service in the store is connected through its own card, do NOT add it by declaring a URL yourself - "
                    "only the card has the sign-in template and the read/write tool classification built in.")
    else:
        dong.append(f"The Connection store has no service matching '{q}'. If the user can give an MCP address "
                    "(URL) or a run command, call this tool again with op=add to declare it yourself.")
    if dang_co:
        dong.append("")
        dong.append("Already connected: " + ", ".join(
            f"{c.get('label')}{'' if c.get('enabled') else ' (turned off)'}" for c in dang_co[:_FIND_MAX]))
    return "\n".join(dong)


async def _them(args, ctx) -> str:
    args = args or {}
    ten = _chuoi(args.get("name"))
    url = _chuoi(args.get("url"))
    command = _chuoi(args.get("command"))
    tham_so = _tham_so(args.get("args"))

    # Lệnh gõ nguyên cụm ("npx -y abc") là kiểu model hay viết nhất - tách ra chứ đừng bắt
    # người dùng gõ lại cho vừa ý máy.
    if command and not tham_so and (" " in command):
        phan = _tham_so(command)
        command, tham_so = phan[0], phan[1:]

    if not _TEN_HOP_LE.match(ten):
        return ("ERROR: missing name - give this source a display name (e.g. 'Context7', 'POS shop 2'). "
                "This name is what the user sees on the Connections page.")

    if not url and not command:
        kho = _tu_kho(ten)
        if kho:
            return ("Nothing connected yet. This service ALREADY EXISTS in the Connection store; connect it through its own card "
                    "instead of declaring it yourself:\n" + "\n".join(_mo_ta_card(c) for c in kho[:_FIND_MAX])
                    + "\nTell the user to open the Connections page, find that card and click Connect. "
                    "Jarvis 007 cannot sign in for the user.")
        return ("ERROR: missing url (an MCP that runs over the network) or command (an MCP that runs by a command on the machine). "
                "Ask the user for the MCP address, or call op=find to check whether the Connection store already has this service.")

    cu = _trung(url, command, tham_so)
    if cu:
        return (f"Already exists, NOT adding a duplicate: '{cu.get('label')}' "
                f"({'turned on' if cu.get('enabled') else 'TURNED OFF, turn it back on from the Connections page'}), "
                f"permission level {cu.get('perm')}. " + _xem_o_dau(cu.get("id")))

    transport = _chuoi(args.get("transport")).lower()
    if transport not in ("http", "sse", "stdio"):
        transport = "stdio" if command else "http"
    if transport == "stdio" and not command:
        return "ERROR: transport=stdio requires a command (the command that runs the MCP server)."
    if transport in ("http", "sse") and not url:
        return f"ERROR: transport={transport} requires a url."

    perm = _chuoi(args.get("perm")).lower()
    if perm not in mcp_catalog.PERM_RANK:
        perm = "readonly"

    cid, loi = mcp_store.add_connection("custom", {
        "label": ten,
        "transport": transport,
        "url": url,
        "command": command,
        "args": tham_so,
        "headers": _cap_key_value(args.get("headers"), ":"),
        "env": _cap_key_value(args.get("env"), "="),
        "perm": perm,
    })
    if loi:
        return f"ERROR: could not add - {loi}"

    import mcp_hub   # nạp muộn: mcp_hub nạp plugins_host, import ở đầu file là vòng tròn

    # stdio = chạy lệnh trên máy chủ. Để TẮT và KHÔNG dial thử (dial là chạy lệnh đó rồi).
    if transport == "stdio":
        mcp_store.update_connection(cid, {"enabled": False})
        mcp_hub.invalidate_cache()
        lenh = " ".join([command] + tham_so)
        return (f"Added '{ten}' to the Connections page but LEFT IT OFF, because this source runs by a command on the "
                f"Jarvis 007 server: `{lenh}`. The user reads the command and, if it looks fine, turns it on from the Connections page "
                f"(Jarvis 007 never turns this kind on by itself). Permission level set: {perm}. " + _xem_o_dau(cid))

    val = await mcp_hub.validate_connection(cid)
    if not val.get("ok"):
        # KHÔNG xoá như `/connect/add` làm. Người dùng nhờ qua chat thì thứ họ cần là NHÌN THẤY
        # nó nằm đó và biết vì sao chưa chạy, chứ không phải một câu lỗi rồi trang Kết nối trống trơn.
        mcp_store.update_connection(cid, {"enabled": False})
        mcp_hub.invalidate_cache()
        return (f"Added '{ten}' to the Connections page but LEFT IT OFF because the test connection failed: "
                f"{val.get('error') or 'reason unknown'}\n"
                "Tell the user this exact error, and suggest checking the URL or key, fixing it and turning it back on. "
                + _xem_o_dau(cid))

    if val.get("label") and not ten:
        mcp_store.update_connection(cid, {"label": val["label"]})
    mcp_hub.invalidate_cache()
    try:
        mcp_hub.codex_profile("full")   # để engine ChatGPT/Codex thấy nguồn mới ở lượt sau
    except Exception:
        pass
    return (f"Connected '{ten}' and it is running: {val.get('tools', 0)} tools found, permission level "
            f"{perm} (a safe default; if writes should be allowed, the user raises it on the Connections page). "
            "Every brain can use this source through the hub. " + _xem_o_dau(cid))


async def _chay(args, ctx) -> str:
    op = _chuoi((args or {}).get("op")).lower()
    if op == "add":
        return await _them(args, ctx)
    if op == "find":
        return _tim(args, ctx)
    return "ERROR: op must be 'add' (connect a new source) or 'find' (check the Connection store for an existing one)."


def register(ctx):
    ctx.register_tool(
        "javis_add_mcp",
        "Connect another MCP server into Jarvis 007's Connections store, so it SHOWS UP on the Connections page and EVERY "
        "brain shares it. Use this tool every time the user asks to add/connect/link an MCP or a data "
        "source (thêm/đấu/nối một MCP hay một nguồn dữ liệu); NEVER use `claude mcp add` or `codex mcp add` (they land in one "
        "CLI's own config, which the user cannot see on the Connections page). "
        "op=find: check whether the Connection store already has that service (call it before declaring a URL yourself). "
        "op=add: needs name, plus url (a network MCP) or command (an MCP run by a command). headers for "
        "keys such as 'Authorization: Bearer xxx'. The default permission level is read-only; only pass a higher perm "
        "when the user says so clearly. A source run by a command is always added TURNED OFF so the "
        "user can review it. Tell the user it lives on the Connections page.",
        _chay,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["add", "find"]},
                "name": {"type": "string", "description": "Display name on the Connections page (op=add), "
                                                          "or a service keyword (op=find)"},
                "url": {"type": "string", "description": "MCP address, e.g. https://mcp.abc.com/mcp"},
                "command": {"type": "string", "description": "Command that runs the MCP on the machine, e.g. npx"},
                "args": {"type": "string", "description": "Arguments of the command, e.g. '-y @abc/mcp-server'"},
                "transport": {"type": "string", "enum": ["http", "sse", "stdio"]},
                "headers": {"type": "string", "description": "Auth headers, one per line 'Key: value'"},
                "env": {"type": "string", "description": "Environment variables for the command, one per line 'KEY=value'"},
                "perm": {"type": "string", "enum": ["readonly", "safe", "full"],
                         "description": "Default readonly. Only raise it when the user clearly asks."},
            },
            "required": ["op"],
        },
        min_mode="safe",
        emoji="🔌",
    )
