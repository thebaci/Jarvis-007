"""Điểm vào của lệnh `javis`.

Javis CLI là CLIENT MỎNG: nó KHÔNG chứa Javis bên trong, chỉ nói chuyện với một máy chủ Javis
đang chạy (trên máy này hoặc trên VPS). Mọi năng lực - brain, MCP, skill, loop, việc - nằm ở
máy chủ đó. Xem docs/dev/2026-08-cli-spec.md để biết vì sao lại thiết kế như vậy.
"""
import argparse
import sys

from . import commands as cmd
from . import render as r
from .client import LoiJavis


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="javis",
        description="Talk to Jarvis 007 from the terminal. Needs a running Jarvis 007 server.",
        epilog="Quick use:  javis \"how is revenue this week\"")
    p.add_argument("--profile", default="", help="connection profile (default: the default profile)")
    p.add_argument("--brain", default="", help="brain to use for this command")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="do not print progress, only the answer")

    sub = p.add_subparsers(dest="lenh")

    s = sub.add_parser("chat", help="continuous Q&A session")
    s.add_argument("--session", default="", help="session id (keeps the thread across runs)")

    s = sub.add_parser("login", help="save the address + token of a Jarvis 007 server")
    s.add_argument("url")
    s.add_argument("--token", default="")
    s.add_argument("--name", default="", help="profile name (default: mac-dinh)")
    s.add_argument("--brain", default="")

    sub.add_parser("status", help="version, brain, savings level")
    sub.add_parser("profiles", help="saved profiles")

    s = sub.add_parser("up", help="start the Jarvis 007 installed on this machine and attach to it")
    s.add_argument("--port", type=int, default=7777)
    s.add_argument("--url", default="")

    s = sub.add_parser("task", help="Kanban tasks")
    ts = s.add_subparsers(dest="task_lenh")
    a = ts.add_parser("add", help="assign a task")
    a.add_argument("title")
    a.add_argument("--mode", default="suggest", choices=["suggest", "auto", "full"])

    sub.add_parser("tasks", help="list tasks")

    s = sub.add_parser("brain", help="browse the brain")
    bs = s.add_subparsers(dest="brain_lenh")
    a = bs.add_parser("ls", help="list a folder")
    a.add_argument("path", nargs="?", default="")
    a = bs.add_parser("cat", help="print file content")
    a.add_argument("path")

    sub.add_parser("loops", help="list loops")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `javis "câu hỏi"` là ĐƯỜNG CHÍNH, nên nó phải là thứ dễ gõ nhất: bất cứ thứ gì không
    # khớp tên lệnh con đều được hiểu là câu hỏi. Bắt người dùng gõ `javis ask "..."` chỉ để
    # bộ phân tích tham số đỡ phải nghĩ là đặt sự tiện của mã lên trên sự tiện của người.
    ten_lenh = {"chat", "login", "status", "profiles", "up", "task", "tasks", "brain", "loops"}
    co_lenh = any(a in ten_lenh for a in argv if not a.startswith("-"))

    p = _parser()
    if not argv:
        p.print_help(sys.stderr)
        return 1
    if not co_lenh:
        cau = " ".join(a for a in argv if not a.startswith("-")).strip()
        args = p.parse_args([a for a in argv if a.startswith("-")])
        if not cau:
            p.print_help(sys.stderr)
            return 1
        try:
            return cmd.hoi(args, cau)
        except LoiJavis as e:
            r.loi(str(e))
            return 1

    args = p.parse_args(argv)
    ham = {
        "chat": cmd.chat, "login": cmd.login, "status": cmd.status,
        "profiles": cmd.profiles, "tasks": cmd.tasks, "loops": cmd.loops, "up": cmd.up,
    }.get(args.lenh)
    if args.lenh == "task":
        ham = cmd.task_add if getattr(args, "task_lenh", "") == "add" else None
    if args.lenh == "brain":
        ham = {"ls": cmd.brain_ls, "cat": cmd.brain_cat}.get(getattr(args, "brain_lenh", ""))
    if ham is None:
        p.print_help(sys.stderr)
        return 1
    try:
        return ham(args)
    except LoiJavis as e:
        r.loi(str(e))
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
