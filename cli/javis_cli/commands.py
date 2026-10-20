"""Từng lệnh của CLI. Mỗi hàm trả mã thoát (0 = xong).

Nguyên tắc xuyên suốt: CLI chỉ gọi endpoint SẴN CÓ của máy chủ. Không lệnh nào ở đây được tự
tính toán thay server, vì làm vậy là bắt đầu nuôi một bản Javis thứ hai trong terminal.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

from . import config as cfgmod
from . import render as r
from .client import Client, LoiJavis


def _client(args) -> Client:
    p = cfgmod.ho_so(getattr(args, "profile", "") or "")
    return Client(p.get("url") or "", p.get("token") or "")


def _brain(args) -> str:
    return (getattr(args, "brain", "") or cfgmod.ho_so(getattr(args, "profile", "") or "")
            .get("brain") or "")


def _may() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return ""


# ---------------------------------------------------------------- chat

def hoi(args, cau: str, session: str = "") -> int:
    """Một lượt. Có tty thì đi SSE để thấy tiến độ; đổ vào pipe thì đi đường đồng bộ cho gọn."""
    c = _client(args)
    data = {"message": cau, "brain": _brain(args), "session": session, "host": _may()}
    dung_sse = sys.stderr.isatty() and not getattr(args, "quiet", False)
    if not dung_sse:
        d = c.post("/chat", data)
        return _in_ket_qua(d)
    cuoi = None
    for goi in c.sse("/chat/stream", data):
        loai = goi.get("type")
        if loai == "status":
            r.trang_thai(goi.get("content") or "")
        elif loai == "response":
            cuoi = goi
        elif loai == "error":
            r.loi(goi.get("content") or "")
            return 1
        # Mọi `type` lạ: BỎ QUA im lặng. Server thêm loại gói mới là chuyện thường và một CLI
        # cũ không được vỡ vì điều đó.
    if cuoi is None:
        r.loi("The server closed the stream without sending an answer.")
        return 1
    return _in_ket_qua(cuoi)


def _in_ket_qua(d: dict) -> int:
    chu = d.get("text") or ""
    if not d.get("ok", True):
        r.loi(chu or "The chat turn failed.")
        return 1
    r.tra_loi(chu)
    for f in d.get("files") or []:
        r.trang_thai("file: " + str(f))
    r.duong_chay(d.get("ctx_path") or "")
    return 0


def chat(args) -> int:
    """Phiên tương tác. Giữ NGUYÊN một mã phiên cho cả phiên terminal, nên Javis nhớ mạch."""
    sid = getattr(args, "session", "") or "t" + uuid.uuid4().hex[:8]
    r.tieu_de("Jarvis 007 - type a question, Ctrl+D or /quit to exit. Session: " + sid)
    while True:
        try:
            cau = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\n")
            return 0
        if not cau:
            continue
        if cau in ("/thoat", "/quit", "/exit"):
            return 0
        try:
            hoi(args, cau, session=sid)
        except LoiJavis as e:
            r.loi(str(e))


# ---------------------------------------------------------------- kết nối

def login(args) -> int:
    url = (args.url or "").rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    token = args.token or ""
    if not token:
        r.tieu_de("Create a token in the dashboard: Account > API token, then paste it here.")
        try:
            token = input("Token: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\n")
            return 1
    c = Client(url, token)
    d = c.get("/version")           # thử thật, không lưu một cấu hình chưa bao giờ chạy được
    ten = args.name or "mac-dinh"
    cfgmod.luu(ten, url, token, args.brain or "")
    r.tieu_de(f"Saved profile '{ten}' -> {url} (Jarvis 007 v{d.get('current', '?')})")
    r.trang_thai("Config: " + str(cfgmod.DUONG_DAN))
    return 0


def status(args) -> int:
    c = _client(args)
    v = c.get("/version")
    r.tieu_de(f"Jarvis 007 v{v.get('current', '?')} · {v.get('mode', '?')}")
    if v.get("update_available"):
        r.nhac(f"New version available: v{v.get('latest')}")
    try:
        d = c.get("/runtime/diagnostics", {"hours": 24, "limit": 20})
        eng = d.get("engine_hien_tai") or {}
        if eng.get("label"):
            r.tieu_de("Brain: " + str(eng.get("label")))
        muc = {"off": "Off", "saving": "Optimized", "max": "Ultra saving"}.get(d.get("preset"), "")
        if muc:
            r.tieu_de("Saving level: " + muc)
        do = d.get("do_duoc") or {}
        if do.get("du_du_lieu"):
            r.trang_thai(f"Over the last 24 hours tokens per turn dropped {do.get('phan_tram')}%")
    except LoiJavis:
        # Token scope `chat` không vào được trang chẩn đoán. Không phải lỗi, chỉ là ít thông tin.
        r.trang_thai("(this token cannot view diagnostics)")
    return 0


def profiles(args) -> int:
    d = cfgmod.danh_sach()
    if not d["profiles"]:
        r.nhac("No profiles yet. Run: javis login <address>")
        return 1
    for ten, p in d["profiles"].items():
        dau = "*" if ten == d["default"] else " "
        r.tra_loi(f"{dau} {ten}\t{p.get('url', '')}\t{p.get('brain') or '(default brain)'}")
    return 0


# ---------------------------------------------------------------- việc, brain, loop

def task_add(args) -> int:
    c = _client(args)
    d = c.post("/kanban/task", {"title": args.title, "brain": _brain(args),
                                "mode": args.mode or "suggest"})
    if not d.get("ok", True):
        r.loi(str(d.get("error") or "Could not assign the task."))
        return 1
    r.tra_loi(str(d.get("id") or ""))
    r.trang_thai("Assigned. Check progress with: javis tasks")
    return 0


def tasks(args) -> int:
    c = _client(args)
    d = c.get("/kanban", {"brain": _brain(args)})
    cot = d.get("columns") or d.get("cols") or {}
    if isinstance(cot, dict):
        for ten, ds in cot.items():
            for t in ds or []:
                r.tra_loi(f"{ten}\t{t.get('id', '')}\t{t.get('title', '')}")
    else:
        r.tra_loi(json.dumps(d, ensure_ascii=False))
    return 0


def brain_ls(args) -> int:
    c = _client(args)
    d = c.get("/files/list", {"brain": _brain(args) or "brain",
                              **({"path": args.path} if args.path else {})})
    if d.get("error"):
        r.loi(str(d["error"]))
        return 1
    for it in d.get("items") or []:
        loai = "d" if it.get("type") == "dir" else "-"
        r.tra_loi(f"{loai} {it.get('name', '')}")
    return 0


def brain_cat(args) -> int:
    c = _client(args)
    d = c.get("/files/read", {"brain": _brain(args) or "brain", "path": args.path})
    if d.get("error") or d.get("content") is None:
        r.loi(str(d.get("error") or "Could not read the file."))
        return 1
    r.tra_loi(d["content"])
    return 0


def loops(args) -> int:
    c = _client(args)
    d = c.get("/loops", {"brain": _brain(args)})
    ds = d.get("loops") if isinstance(d, dict) else d
    for lp in ds or []:
        bat = "on " if lp.get("enabled") else "off"
        r.tra_loi(f"{bat}\t{lp.get('slug', '')}\t{lp.get('mode', '')}\t{lp.get('name', '')}")
    return 0


# ---------------------------------------------------------------- javis up

def _dang_chay(url: str) -> bool:
    try:
        import httpx
        with httpx.Client(timeout=2) as c:
            return c.get(url + "/health").status_code < 500
    except Exception:
        return False


def _tim_javis() -> Path:
    """Tìm bản cài Javis trên máy này. Chỉ nhận chỗ có `server/main.py` THẬT.

    Không đoán bừa: `javis up` mà bật nhầm thứ gì đó là kiểu hỏng khó lần nhất.
    """
    ung_vien = []
    if os.getenv("JAVIS_HOME"):
        ung_vien.append(Path(os.environ["JAVIS_HOME"]))
    ung_vien += [Path.cwd(), Path.cwd().parent,
                 Path(os.path.expanduser("~")) / "javis-os",
                 Path(os.path.expanduser("~")) / "Javis-OS"]
    for p in ung_vien:
        try:
            if (p / "server" / "main.py").is_file():
                return p
        except Exception:
            continue
    return None


def up(args) -> int:
    """Bật Javis trên chính máy này rồi gắn CLI vào.

    Vẫn MỘT server, MỘT brain - CLI chỉ là thứ khởi động nó. Gói CLI KHÔNG chứa server, nên
    lệnh này chỉ chạy khi máy đã có bản cài Javis; không có thì nói thẳng chứ không giả vờ.
    """
    url = (getattr(args, "url", "") or "http://127.0.0.1:7777").rstrip("/")
    if _dang_chay(url):
        r.tieu_de("Jarvis 007 is already running at " + url)
    else:
        goc = _tim_javis()
        if not goc:
            r.loi("No Jarvis 007 installation found on this machine.\n"
                  "javis up only starts a Jarvis 007 that is already installed - it does NOT contain the server inside.\n"
                  "How to fix: set JAVIS_HOME to point at the Jarvis 007 folder, or run this command from inside "
                  "that folder, or use `javis login <address>` to connect to a Jarvis 007 running "
                  "elsewhere.")
            return 1
        py = shutil.which("python3") or shutil.which("python") or sys.executable
        r.tieu_de(f"Starting Jarvis 007 from {goc} ...")
        try:
            subprocess.Popen(
                [py, "-m", "uvicorn", "main:app", "--app-dir", "server",
                 "--host", "127.0.0.1", "--port", str(getattr(args, "port", 7777) or 7777)],
                cwd=str(goc), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
        except Exception as e:
            r.loi(f"Could not start: {type(e).__name__}: {e}")
            return 1
        for _ in range(60):          # 30 giây: lần đầu còn phải nạp model/registry
            if _dang_chay(url):
                break
            time.sleep(0.5)
        else:
            r.loi("Started, but the server has not answered after 30 seconds. Check the log in the Jarvis 007 folder.")
            return 1
        r.tieu_de("Jarvis 007 is ready at " + url)

    # Lưu hồ sơ localhost nếu chưa có, để lần sau `javis "..."` là chạy luôn.
    p = cfgmod.ho_so()
    if not p.get("url"):
        cfgmod.luu("local", url, "", "")
        r.trang_thai("Saved profile 'local'. Try it: javis \"hello\"")
    return 0
