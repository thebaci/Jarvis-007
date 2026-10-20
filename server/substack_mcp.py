"""
Cầu nối Substack (transport "internal" trong catalog).

Server MCP cộng đồng substack-mcp (marcomoauro) CHỈ có 1 tool tạo nháp và không
đăng được, nên Javis tự bọc thẳng API Substack (giống botcake_mcp) để có đủ:
liệt kê nháp, tạo nháp, và ĐĂNG bài. Pure-Python, không cần Node/npx.

Auth: cookie phiên đăng nhập Substack (substack.sid) - dùng cho cả substack.sid
lẫn connect.sid, y như cách substack-mcp làm. spec["secrets"] do mcp_store.resolved
cấp: {publication_url, session_token, user_id}.

Endpoint (đã đối chiếu thư viện python-substack + substack-mcp):
  POST   {pub}/api/v1/drafts                    tạo nháp
  GET    {pub}/api/v1/drafts                    danh sách nháp
  GET    {pub}/api/v1/drafts/{id}/prepublish    kiểm tra trước khi đăng
  POST   {pub}/api/v1/drafts/{id}/publish       đăng (body {"send", "share_automatically"})

Phân loại quyền (khai trong system/mcp-catalog.json):
  substack_list_drafts   -> read
  substack_create_draft  -> write
  substack_publish       -> danger  (đăng thật; send=true còn gửi email cho toàn bộ
                                      người đăng ký - KHÔNG hoàn tác được)
"""
import asyncio
import json
import re
import shutil
import winproc         # lệnh con câm lặng trên Windows
from urllib.parse import quote

# LƯU Ý: gọi API Substack qua CURL, KHÔNG dùng httpx/requests. Substack đứng sau Cloudflare,
# chặn client Python theo TLS fingerprint (trả 403 kèm trang HTML) trong khi curl thì qua được.
# (Đã xác minh: httpx -> 403 <!DOCTYPE html>; curl -> chạm được app, trả JSON / "Not authorized".)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _clip(text, max_chars=6000):
    text = str(text)
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    return (text[:head] + f"\n… [TRUNCATED - dropped {len(text) - head - tail:,} characters] …\n" + text[-tail:])


def _t(name, description, props=None, required=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}, "required": required or []}}


TOOLS = [
    _t("substack_list_drafts",
       "List the recent DRAFTS on Substack (id, title, whether published). Use it to look "
       "at drafts or get the id of an existing draft and then publish it.",
       {"limit": {"type": "integer", "description": "number of drafts to fetch, default 15"}}),
    _t("substack_create_draft",
       "Create a post DRAFT on Substack (does NOT publish). body takes simple markdown: # heading, "
       "- bullet, 1. numbered list, > quote, --- horizontal rule, **bold**, *italic*, "
       "[text](link), `code`. Returns the draft id to edit/publish.",
       {"title": {"type": "string"}, "subtitle": {"type": "string"},
        "body": {"type": "string", "description": "content, simple markdown supported"},
        "audience": {"type": "string",
                     "description": "everyone (default) | only_paid | founding"}},
       ["title", "body"]),
    _t("substack_publish",
       "PUBLISH A REAL POST to Substack. Either create a new one and publish it (pass title+body), or publish an "
       "existing draft (pass draft_id). BY DEFAULT it only publishes to the web and does NOT send email; setting "
       "send_email=true emails ALL subscribers (cannot be undone) - only turn it on "
       "when the user clearly asks. This is a dangerous action, only run it when directly asked.",
       {"draft_id": {"type": "string", "description": "id of an existing draft to publish (leave empty to create a new one)"},
        "title": {"type": "string"}, "subtitle": {"type": "string"},
        "body": {"type": "string", "description": "simple markdown content (when creating a new one)"},
        "audience": {"type": "string", "description": "everyone (default) | only_paid | founding"},
        "send_email": {"type": "boolean",
                       "description": "true = publish AND email the subscribers; default false (web only)"}}),
]


# ============================================================
# Markdown gọn -> ProseMirror doc (định dạng thân bài của Substack)
# ============================================================
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_ITAL = re.compile(r"\*([^*\n]+)\*|_([^_\n]+)_")


def _inline(text):
    """Chuỗi 1 dòng -> list node inline (text + marks strong/em/code/link)."""
    text = str(text or "")
    nodes, i, n = [], 0, len(text)

    def push_plain(chunk):
        if chunk:
            nodes.append({"type": "text", "text": chunk})

    while i < n:
        best = None
        for rx, kind in ((_LINK, "link"), (_BOLD, "strong"), (_CODE, "code"), (_ITAL, "em")):
            m = rx.search(text, i)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m, kind)
        if best is None:
            push_plain(text[i:])
            break
        start, m, kind = best
        push_plain(text[i:start])
        if kind == "link":
            nodes.append({"type": "text", "text": m.group(1),
                          "marks": [{"type": "link", "attrs": {"href": m.group(2)}}]})
        elif kind == "em":
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            nodes.append({"type": "text", "text": inner, "marks": [{"type": "em"}]})
        else:
            nodes.append({"type": "text", "text": m.group(1), "marks": [{"type": kind}]})
        i = m.end()
    return nodes


def _para(text):
    inl = _inline(text)
    return {"type": "paragraph", "content": inl} if inl else {"type": "paragraph"}


def _body_to_doc(text):
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    content, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            content.append({"type": "heading", "attrs": {"level": min(len(hm.group(1)), 3)},
                            "content": _inline(hm.group(2).strip()) or [{"type": "text", "text": " "}]})
            i += 1
            continue
        if re.match(r"^([-*_])\1{2,}$", s):
            content.append({"type": "horizontal_rule"})
            i += 1
            continue
        if s.startswith(">"):
            content.append({"type": "blockquote", "content": [_para(s[1:].strip())]})
            i += 1
            continue
        if re.match(r"^[-*]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append({"type": "list_item",
                              "content": [_para(re.sub(r"^[-*]\s+", "", lines[i].strip()))]})
                i += 1
            content.append({"type": "bullet_list", "content": items})
            continue
        if re.match(r"^\d+[.)]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                items.append({"type": "list_item",
                              "content": [_para(re.sub(r"^\d+[.)]\s+", "", lines[i].strip()))]})
                i += 1
            content.append({"type": "ordered_list", "attrs": {"start": 1, "order": 1}, "content": items})
            continue
        content.append(_para(s))
        i += 1
    return {"type": "doc", "content": content or [{"type": "paragraph"}]}


# ============================================================
# HTTP helpers
# ============================================================
def _ctx(spec):
    """Trả (api_base, hostname, headers, user_id, lỗi). Lỗi != None nghĩa là thiếu cấu hình."""
    secrets = (spec or {}).get("secrets") or {}
    pub = str(secrets.get("publication_url", "")).strip().rstrip("/")
    token = str(secrets.get("session_token", "")).strip()
    user_id = str(secrets.get("user_id", "")).strip()
    if not pub or not token or not user_id:
        return None, None, None, None, ("ERROR: the Substack connection is missing publication_url / session_token "
                                        "/ user_id - fix it on the Connections page")
    if not re.match(r"^https?://", pub):
        pub = "https://" + pub
    try:
        int(user_id)
    except ValueError:
        return None, None, None, None, "ERROR: User ID must be a string of digits (take it from the URL of your Substack profile page)"
    headers = {
        "Cookie": f"substack.sid={token}; connect.sid={token};",
        "referer": f"{pub}/publish/post",
        "content-type": "application/json",
        "user-agent": _UA,
        "accept": "application/json",
    }
    return pub + "/api/v1", pub, headers, user_id, None


def _draft_payload(title, subtitle, body, user_id, audience):
    aud = (audience or "everyone").strip() or "everyone"
    return {
        "draft_title": title or "",
        "draft_subtitle": subtitle or "",
        "draft_body": json.dumps(_body_to_doc(body), ensure_ascii=False),
        "draft_bylines": [{"id": int(user_id), "is_guest": False}],
        "audience": aud,
        "draft_section_id": None,
        "section_chosen": True,
        "write_comment_permissions": aud,
    }


def _clean_err(text):
    """Rút gọn thân lỗi để KHÔNG đổ nguyên HTML/JSON dài vào chat + form Kết nối."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t[:200].lower()
    if t.startswith("<") or "<html" in low or "<!doctype" in low:
        return "Substack blocked the request (usually a wrong/expired session token or a temporary block)"
    try:
        j = json.loads(t)
        if isinstance(j, dict) and (j.get("error") or j.get("message")):
            return str(j.get("error") or j.get("message"))[:180]
    except ValueError:
        pass
    return t[:180]


async def _req(method, url, headers, body=None, params=None):
    """Gọi 1 request qua curl (bypass Cloudflare). Trả JSON đã parse; lỗi thì raise RuntimeError
    với thông điệp NGẮN, sạch (không đổ HTML)."""
    if params:
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url += ("&" if "?" in url else "?") + qs
    curl = shutil.which("curl") or "curl"
    argv = [curl, "-s", "-X", method, "--max-time", "45", "-w", "\n%{http_code}"]
    for k, v in headers.items():
        argv += ["-H", f"{k}: {v}"]
    stdin_data = None
    if body is not None:
        argv += ["--data-binary", "@-"]
        stdin_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    argv.append(url)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            **winproc.kwargs_no_window())
        out, errb = await asyncio.wait_for(proc.communicate(stdin_data), timeout=55)
    except FileNotFoundError:
        raise RuntimeError("the machine running Jarvis 007 has no 'curl' - install curl to call Substack")
    except Exception as e:
        raise RuntimeError(f"could not call Substack ({type(e).__name__})")
    text = out.decode("utf-8", "replace")
    body_text, sep, status_s = text.rpartition("\n")
    if not sep:
        body_text, status_s = text, ""
    try:
        status = int(status_s.strip())
    except ValueError:
        status = 0
    if status == 0:
        raise RuntimeError(f"curl error: {_clean_err(errb.decode('utf-8', 'replace')) or 'unknown'}")
    if status >= 400:
        raise RuntimeError(f"Substack {status}: {_clean_err(body_text) or 'unknown error'}")
    body_text = body_text.strip()
    if not body_text:
        return {}
    try:
        return json.loads(body_text)
    except ValueError:
        return body_text


async def list_tools(spec):
    return TOOLS


async def call(tool, arguments, spec):
    api, pub, headers, user_id, err = _ctx(spec)
    if err:
        return err
    args = arguments or {}
    try:
        if tool == "substack_list_drafts":
            limit = int(args.get("limit") or 15)
            data = await _req("GET", f"{api}/drafts", headers, params={"limit": limit, "offset": 0})
            rows = data if isinstance(data, list) else (data.get("drafts") or data.get("posts") or [])
            out = []
            for d in rows[:limit]:
                out.append({
                    "id": d.get("id"),
                    "title": d.get("draft_title") or d.get("title") or "(untitled)",
                    "is_published": bool(d.get("is_published")),
                    "post_date": d.get("post_date"),
                })
            return _clip(json.dumps({"drafts": out}, ensure_ascii=False))

        if tool == "substack_create_draft":
            if not args.get("title") or not args.get("body"):
                return "ERROR: title and body are needed to create a draft"
            payload = _draft_payload(args.get("title"), args.get("subtitle"), args.get("body"),
                                     user_id, args.get("audience"))
            draft = await _req("POST", f"{api}/drafts", headers, body=payload)
            did = draft.get("id") if isinstance(draft, dict) else None
            return (f"OK - draft created, id={did}. Edit or publish at: {pub}/publish/post/{did}"
                    if did else _clip(json.dumps(draft, ensure_ascii=False)))

        if tool == "substack_publish":
            send_email = bool(args.get("send_email"))
            did = str(args.get("draft_id") or "").strip()
            if not did:
                if not args.get("title") or not args.get("body"):
                    return "ERROR: need draft_id (publish an existing draft) OR title+body (create new, then publish)"
                payload = _draft_payload(args.get("title"), args.get("subtitle"), args.get("body"),
                                         user_id, args.get("audience"))
                draft = await _req("POST", f"{api}/drafts", headers, body=payload)
                did = str(draft.get("id")) if isinstance(draft, dict) else ""
                if not did:
                    return "ERROR: creating the draft returned no id, nothing was published: " + _clip(json.dumps(draft, ensure_ascii=False))
            # prepublish: best-effort, không chặn nếu server không cần
            try:
                await _req("GET", f"{api}/drafts/{did}/prepublish", headers)
            except Exception:
                pass
            res = await _req("POST", f"{api}/drafts/{did}/publish", headers,
                             body={"send": send_email, "share_automatically": False})
            url = ""
            if isinstance(res, dict):
                slug = res.get("slug")
                url = res.get("canonical_url") or (f"{pub}/p/{slug}" if slug else "")
            mail = "email SENT to subscribers" if send_email else "published to the web only (no email)"
            return f"OK - post PUBLISHED (id={did}, {mail}). {('Link: ' + url) if url else ''}".strip()

        return f"ERROR: tool '{tool}' is not in the Substack bridge"
    except RuntimeError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: Substack did not respond: {type(e).__name__}: {e}"
