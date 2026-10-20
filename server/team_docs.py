"""Files, links and a working folder for a team chat (0.191.0).

Owner, 16/10/2026: "ở trong phần nhóm em cho anh thêm phần thêm file, thêm folder làm việc trong khung chat nữa chứ, và
còn việc có phần thêm file tài liệu trong nhóm sử dụng với các link trong nhóm nữa". A team is a normal conversation
underneath (`sessions` row with channel `team:<id>`), so its documents ARE that conversation's documents
(`session_files`, `session_links`) and its working folder IS that conversation's pinned folder (`coding_store`). Nothing
new is stored; the main chat's machinery is reused.

Team turns stay text only (decision R3 of team chat T1: no file tools, no MCP). So a member cannot open a file: what it
can read is what the server puts in the prompt. Attached text files are pinned (their content is loaded, within the same
token caps as a chat's pinned files); a PDF or Word file gets a text copy next to it that is pinned instead; a pinned
working folder is shown as a short folder tree.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable, Iterable, List, Optional

MAX_PER_SEND = 10
TREE_DEPTH = 2
TREE_MAX = 120
HIDDEN = (".", "node_modules", "__pycache__")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _safe_name(name: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", str(name or "").strip()).strip(" .")
    return s[:120] or "file"


def _unique(dest_dir: Path, name: str) -> Path:
    p = dest_dir / name
    if not p.exists():
        return p
    stem, suf = Path(name).stem, Path(name).suffix
    for i in range(2, 1000):
        q = dest_dir / f"{stem} ({i}){suf}"
        if not q.exists():
            return q
    return dest_dir / f"{stem} ({len(list(dest_dir.iterdir()))}){suf}"


def _inside(p: Path, root: Path) -> bool:
    return p == root or root in p.parents


def save(attachments: Iterable[dict], *, staging: Path, brain_root: Path, dest_dir: Path,
         to_rel: Callable[[Path], str], add: Callable[[str, str], Optional[str]],
         pin: Callable[[str], object], readable: Iterable[str],
         extract: Optional[Callable[[Path], str]] = None, extract_suffixes: Iterable[str] = ()) -> List[dict]:
    """Keep the files attached in a team (from the upload staging area, or already in the brain) as team documents.

    A staged upload is copied into `dest_dir` (inside the brain: the staging area is swept after a few days). A file
    already in the brain stays where it is. Every file becomes a document row of the team's conversation; text files are
    pinned so team turns read them; a PDF or Word file gets a pinned `.txt` copy. Anything outside the staging area and
    the brain is refused. Returns [{name, path, image}] for the files kept."""
    staging, brain_root = Path(staging).resolve(), Path(brain_root).resolve()
    readable = {s.lower() for s in readable}
    extract_suffixes = {s.lower() for s in extract_suffixes}
    out = []
    for a in list(attachments or [])[:MAX_PER_SEND]:
        if not isinstance(a, dict):
            continue
        try:
            src = Path(str(a.get("path") or "")).resolve()
        except (OSError, RuntimeError):
            continue
        if not src.is_file():
            continue
        staged, in_brain = _inside(src, staging), _inside(src, brain_root)
        if not (staged or in_brain):
            continue                       # never pull a file from elsewhere on the machine into a team
        name = _safe_name(a.get("name") or src.name)
        if staged:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique(dest_dir, name)
            shutil.copy2(src, dest)
        else:
            dest = src
        suf = dest.suffix.lower()
        fid = add(to_rel(dest), name)
        if not fid:
            continue                       # the team already holds the most documents a conversation may hold
        if suf in readable:
            pin(fid)
        elif extract is not None and suf in extract_suffixes:
            text = extract(dest) or ""
            if text and not text.startswith("ERROR"):
                txt = _unique(dest.parent if staged else dest_dir, dest.stem + ".txt")
                txt.parent.mkdir(parents=True, exist_ok=True)
                txt.write_text(text, encoding="utf-8")
                tid = add(to_rel(txt), f"{name} (text)")
                if tid:
                    pin(tid)
        out.append({"name": name, "path": to_rel(dest), "image": suf in IMAGE_SUFFIXES})
    return out


def save_description(names: List[str], text: str, who: str, *, dest_dir: Path, to_rel: Callable[[Path], str],
                     add: Callable[[str, str], Optional[str]], pin: Callable[[str], object]) -> Optional[str]:
    """Keep what another brain saw in the pictures of a team message as a pinned text document (0.192.0).

    Team turns are text only, so a member cannot look at a picture; this description is what it reads instead. One file
    per message, named after the first picture. Returns the document's path, or None when nothing was kept."""
    body = str(text or "").strip()
    if not body or not names:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    first = Path(_safe_name(names[0])).stem
    out = _unique(dest_dir, f"{first} - mo ta anh.txt")
    head = "Description of image " + ", ".join(names) + (f" (viewed on its behalf by {who})" if who else "") + ":\n\n"
    out.write_text(head + body + "\n", encoding="utf-8")
    fid = add(to_rel(out), ", ".join(names) + " (image description)")
    if not fid:
        return None
    pin(fid)
    return to_rel(out)


def tree(folder: str, depth: int = TREE_DEPTH, cap: int = TREE_MAX) -> List[str]:
    """A short indented listing of a folder (folders first), at most `cap` lines, hidden folders left out."""
    root = Path(folder or "")
    if not folder or not root.is_dir():
        return []
    lines: List[str] = []

    def walk(d: Path, level: int) -> None:
        try:
            kids = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except OSError:
            return
        for k in kids:
            if len(lines) >= cap:
                return
            if k.name.startswith(HIDDEN[0]) or k.name in HIDDEN[1:]:
                continue
            is_dir = k.is_dir()
            lines.append("  " * level + ("- " + k.name + ("/" if is_dir else "")))
            if is_dir and level + 1 < depth:
                walk(k, level + 1)

    walk(root, 0)
    if len(lines) >= cap:
        lines.append("  ... (more not shown, cut off)")
    return lines


def block(listed: List[str], loaded: List[str], folder: str, tools: bool = False) -> str:
    """The team documents block of a member's prompt. "" when the team has nothing attached and no folder.
    `tools=True` (0.194.0): the wording of a Work/Help turn, which can open the files and the folder itself."""
    out = ""
    if listed:
        how = ("This turn has tools: open a file directly by its path when you need to read all of it or edit it; the preloaded part below "
               "is only a quick read. For an image, read the accompanying \"image description\" document, or open the image if your engine can view images."
               if tools else
               "Text-only team turn: you can NOT open files or links; you can only read the content preloaded below. For an image, "
               "read the accompanying \"image description\" document (another brain looked at it on your behalf); if an image or document is not preloaded, "
               "say plainly that you have not been able to read it, and do not guess its content from its name.")
        out += ("\n\n# === TEAM DOCUMENTS AND LINKS ===\n"
                "The team owner attached these documents and links for the whole team. " + how + "\n" + "\n".join(listed))
    if loaded:
        out += "\n\n# === TEAM DOCUMENT CONTENT (preloaded) ===" + "".join(loaded)
    lines = tree(folder)
    if folder:
        out += ("\n\n# === TEAM WORKING FOLDER ===\n"
                f"The team owner pinned this folder: {folder}\n"
                + ("This turn runs right inside that folder: read and edit files and run commands here when your step needs it.\n"
                   if tools else
                   "This is the folder tree so the whole team knows what the project contains. A team turn cannot open files in it; to read a file, "
                   "ask the team owner to attach that file to the team documents.\n") + "\n".join(lines))
    return out
