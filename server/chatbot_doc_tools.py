"""Read-only document tools for a dedicated bot at the "read_docs" level (0.80.0).

Why this level exists. At the "suggest" level a bot has no tools: Javis searches the bot's brain
by keyword BEFORE the turn and pastes the best chunks into the prompt. That keeps the bot honest,
but it misses whenever the customer's words differ from the document's ("đổi trả" vs "hoàn trả").
The "auto" level fixes that by handing the bot the hub's file tools, and with them write access and
every connected data source, all steered by a stranger. The owner asked (2026-10-05) for the
middle ground: "đọc được brain nhưng không ghi".

So this module is the WHOLE tool set of that level, and it is deliberately tiny:

1. **Three tools, all read-only.** List the documents, search them, open one. No write tool, no
   MCP source, no plugin, no skill, no lazy `javis_run_tool`. `mcp_hub.discover_all` returns this
   set and nothing else for the mode, so no engine (API or Claude Code via the hub) sees more.
2. **Same document set as the pre-turn search, minus a little.** A document is readable only if
   `chatbot_grounding.ds_tai_lieu` lists it: `inbox/` (customer uploads), `memory/`, skills,
   plugins, Javis' own convention files and the data cache are already excluded there, and this
   module also drops `agents/` and `workflows/` (the owner's internal instructions). The tools
   therefore never reveal anything the keyword search could not already put in a prompt.
3. **The path a customer types never touches the filesystem.** `docs_read` matches it against
   that list and opens the LISTED file, so `../`, absolute paths and symlinks lead nowhere.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chatbot_grounding

MODE = "read_docs"

# Folders the pre-turn search reads but a stranger with an "open any document" tool should not:
# they hold the owner's instructions to agents, not knowledge for customers.
EXTRA_SKIP = {"agents", "workflows"}

READ_MAX = 20_000          # characters returned by one docs_read call
LIST_MAX = 8_000           # characters returned by docs_list
SEARCH_K = 6               # chunks returned by docs_search
SEARCH_CHUNK = 1_200       # characters per search chunk
INDEX_MAX = 1_500          # characters of the table of contents handed to the reply judge


def _root(vault_root: Any) -> Optional[Path]:
    if not vault_root:
        return None
    try:
        r = Path(str(vault_root)).expanduser().resolve()
    except Exception:
        return None
    return r if r.is_dir() else None


def allowed_docs(vault_root: Any) -> List[str]:
    """Relative posix paths of every document the tools may show, in a stable order."""
    r = _root(vault_root)
    if r is None:
        return []
    out = []
    for rel in chatbot_grounding.ds_tai_lieu(r):
        parts = rel.split("/")
        if any(p.lower() in EXTRA_SKIP for p in parts[:-1]):
            continue
        # A symlink that points out of the brain is not a document of this brain.
        try:
            (r / rel).resolve().relative_to(r)
        except (OSError, ValueError):
            continue
        out.append(rel)
    return out


def _norm(p: Any) -> str:
    s = str(p or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def _match(vault_root: Any, requested: Any) -> Optional[str]:
    """The listed document the request names, or None. Exact first, then case-insensitive, then
    a unique file-name match (models often drop the folder)."""
    want = _norm(requested)
    if not want:
        return None
    docs = allowed_docs(vault_root)
    if want in docs:
        return want
    low = want.lower()
    for d in docs:
        if d.lower() == low:
            return d
    by_name = [d for d in docs if d.rsplit("/", 1)[-1].lower() == low.rsplit("/", 1)[-1]]
    return by_name[0] if len(by_name) == 1 else None


def _headings(vault_root: Any) -> Dict[str, List[str]]:
    """{path: [section titles]} from the cached keyword index (no extra disk scan)."""
    r = _root(vault_root)
    if r is None:
        return {}
    ok = set(allowed_docs(r))
    out: Dict[str, List[str]] = {}
    for m in chatbot_grounding.chi_muc(r).get("manh") or []:
        path = str(m.get("path") or "").replace("\\", "/")
        if path not in ok:
            continue
        ds = out.setdefault(path, [])
        ten = str(m.get("ten") or "").strip()
        if ten and ten not in ds and ten != Path(path).stem:
            ds.append(ten)
    for path in ok:
        out.setdefault(path, [])
    return out


def table_of_contents(vault_root: Any, max_chars: int = INDEX_MAX) -> str:
    """One line per document ("path: heading · heading"), cut at `max_chars`. Empty when the brain
    has no documents. Used by the reply judge: a bot that can open documents itself should not be
    silenced just because the customer's words missed the keyword search."""
    rows, used = [], 0
    for path, hs in sorted(_headings(vault_root).items()):
        line = path + (": " + " · ".join(hs[:8]) if hs else "")
        if used + len(line) + 1 > max_chars:
            rows.append("…")
            break
        rows.append(line)
        used += len(line) + 1
    return "\n".join(rows)


# ============================================================
# Tools
# ============================================================
def _tool(name: str, description: str, props: dict, required: list) -> dict:
    return {"fn": name, "server": "javis", "name": name, "description": description,
            "schema": {"type": "object", "properties": props, "required": required}}


def _route(call) -> dict:
    return {"call": call, "source_type": "builtin", "source_id": "javis-bot-docs", "effect": "read",
            "required_mode": "readonly", "health": "healthy"}


def build(vault_root: Any) -> Tuple[List[dict], Dict[str, dict]]:
    """(tools_spec, route) for one bot brain. No brain, no tools."""
    r = _root(vault_root)
    if r is None:
        return [], {}

    async def _list(args):
        hs = _headings(r)
        if not hs:
            return "(this brain has no documents yet)"
        rows, used = [], 0
        for path, ds in sorted(hs.items()):
            line = "- " + path + (" | sections: " + " · ".join(ds[:12]) if ds else "")
            if used + len(line) > LIST_MAX:
                rows.append(f"… ({len(hs) - len(rows)} more documents, use javis_docs_search to find them)")
                break
            rows.append(line)
            used += len(line) + 1
        return f"{len(hs)} documents:\n" + "\n".join(rows)

    async def _search(args):
        q = str((args or {}).get("query") or "").strip()
        if not q:
            return "ERROR: missing query"
        ok = set(allowed_docs(r))
        hits = [h for h in chatbot_grounding.tim(r, q, k=SEARCH_K * 3)
                if str(h.get("path") or "").replace("\\", "/") in ok][:SEARCH_K]
        if not hits:
            return (f"No passage contains the words of '{q}'. Try again with other words (synonyms, "
                    f"other names for it, with or without diacritics), or see javis_docs_list to pick a document.")
        parts = []
        for h in hits:
            t = str(h.get("text") or "")
            t = t[:SEARCH_CHUNK] + ("…" if len(t) > SEARCH_CHUNK else "")
            parts.append(f"### {h.get('ten')}\n(source: {str(h.get('path')).replace(chr(92), '/')})\n\n{t}")
        return "\n\n".join(parts)

    async def _read(args):
        rel = _match(r, (args or {}).get("path"))
        if not rel:
            return (f"ERROR: there is no document '{(args or {}).get('path')}' in the readable list. "
                    f"Call javis_docs_list to see the right path.")
        p = (r / rel).resolve()
        try:
            p.relative_to(r)
        except ValueError:
            return "ERROR: this document is outside the brain so it cannot be read."
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"ERROR: could not read '{rel}': {type(e).__name__}"
        text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
        if len(text) > READ_MAX:
            text = text[:READ_MAX] + f"\n… [cut, the document is {len(text):,} characters long]"
        return f"# {rel}\n\n{text}"

    tools = [
        _tool("javis_docs_search",
              "Search your documents for passages containing the words of the question. Customers often use different words from the documents, "
              "so if nothing is found, try again with synonyms or other names before concluding that "
              "there is no answer.",
              {"query": {"type": "string", "description": "The words to search for"}}, ["query"]),
        _tool("javis_docs_list",
              "List all your documents with the names of the sections in each one. Use it when searching by words "
              "finds nothing, to pick the document that seems to fit the topic and then open it to read.",
              {}, []),
        _tool("javis_docs_read",
              "Open and read one whole document by the path taken from javis_docs_list or javis_docs_search.",
              {"path": {"type": "string", "description": "Document path, e.g. 'faq/doi-tra.md'"}}, ["path"]),
    ]
    route = {"javis_docs_search": _route(_search), "javis_docs_list": _route(_list),
             "javis_docs_read": _route(_read)}
    return tools, route
