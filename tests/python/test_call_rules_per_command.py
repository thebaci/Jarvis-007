"""`call_rules` classifies each sub-command of a multi-action tool as read, write or danger.

    python tests/run.py call_rules_per_command

Real case (2026-10-13): GitHub's MCP bundles create, update and delete into one tool chosen by a
`method` argument (`label_write`, `projects_write`, `discussion_comment_write`). A rule could only
say "read" or "everything else", so the store had two bad choices: put the whole tool in danger
(creating a label then needed Full access) or in write (deleting labels ran at Draft level). The
rule now takes `write_values` and `danger_values` too.

Checks:
  1. Per-command classes, with unknown and missing commands falling to `else` (fail-closed).
  2. Listing time (no args): the lightest class the rule can produce, so a tool with only write
     commands is not offered at Read-only level just to be blocked on every call.
  3. The block message names the blocked command, also for rules without `items`.
  4. The hub hides such a tool at Read-only, lists it at Draft, runs create, blocks delete.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-call-rules-"))

import config  # noqa: E402
import mcp_catalog  # noqa: E402
import mcp_client  # noqa: E402
import mcp_hub  # noqa: E402
import mcp_store  # noqa: E402

_fails = []


def check(name, cond, them=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or them is None else f"  [{them}]"))
    if not cond:
        _fails.append(name)


LABEL = {"key": "method", "else": "danger", "write_values": ["create", "update"],
         "danger_values": ["delete"]}
GH = {"id": "gh-test", "tool_meta": {"read": ["get_*", "list_*"], "write": ["*_write"],
                                     "danger": ["label_write"]},
      "call_rules": {"label_write": LABEL,
                     "mixed": {"key": "method", "else": "danger", "read_values": ["get"],
                               "write_values": ["create"], "danger_values": ["get_and_delete"]},
                     "soft": {"key": "action", "else": "write", "read_values": ["list"]},
                     "only_danger": {"key": "op", "else": "danger"}}}
cls = mcp_catalog.classify

# ============================================================
# 1. Per-command classes
# ============================================================
check("create -> write", cls(GH, "label_write", {"method": "create", "name": "bug"}) == "write")
check("update -> write", cls(GH, "label_write", {"method": "update"}) == "write")
check("delete -> danger", cls(GH, "label_write", {"method": "delete"}) == "danger")
check("values match case-insensitively", cls(GH, "label_write", {"method": "Create"}) == "write")
check("unknown command -> else (danger)", cls(GH, "label_write", {"method": "purge"}) == "danger")
check("missing command -> else (danger)", cls(GH, "label_write", {}) == "danger")
check("a value is matched whole, not by prefix", cls(GH, "label_write", {"method": "create_and_delete"}) == "danger")
check("call_rules wins over the static danger list", cls(GH, "label_write", {"method": "create"}) == "write")
check("read value still read", cls(GH, "mixed", {"method": "get"}) == "read")
check("danger_values beats read tokens and write values", cls(GH, "mixed", {"method": "get_and_delete"}) == "danger")
check("else=write rule: unknown command -> write", cls(GH, "soft", {"action": "watch"}) == "write")

# ============================================================
# 2. Listing time: lightest class the rule can produce
# ============================================================
check("only write/danger commands -> listed as write", cls(GH, "label_write") == "write")
check("has a read command -> listed as read", cls(GH, "mixed") == "read")
check("else=write -> listed as read when it has read values", cls(GH, "soft") == "read")
check("no values, else=danger -> listed as danger", cls(GH, "only_danger") == "danger")
check("floor: else=write with no values -> write",
      mcp_catalog.call_rule_floor({"key": "a", "else": "write"}) == "write")
check("floor: read_tokens count as a read command",
      mcp_catalog.call_rule_floor({"items": "tools", "key": "slug", "read_tokens": ["LIST"]}) == "read")

# ============================================================
# 3. allowed() and its message
# ============================================================
ok, why = mcp_catalog.allowed(GH, "readonly", "full", "label_write", {"method": "create"})
check("Read-only blocks create", not ok)
check("message names the command and the tool", "Command create via 'label_write'" in why, why)
ok, _ = mcp_catalog.allowed(GH, "safe", "full", "label_write", {"method": "create"})
check("Draft runs create", ok)
ok, why = mcp_catalog.allowed(GH, "safe", "full", "label_write", {"method": "delete"})
check("Draft blocks delete", not ok)
check("Draft message names delete and says plain writes still run",
      "Command delete via 'label_write'" in why and "ordinary write commands still work" in why, why)
ok, _ = mcp_catalog.allowed(GH, "full", "full", "label_write", {"method": "delete"})
check("Full access runs delete", ok)
ok, _ = mcp_catalog.allowed(GH, "full", "auto", "label_write", {"method": "delete"})
check("an auto-mode loop cannot delete even on a Full connection", not ok)
ok, _ = mcp_catalog.allowed(GH, "full", "auto", "label_write", {"method": "update"})
check("an auto-mode loop can update", ok)

# ============================================================
# 4. Hub: hidden at Read-only, listed at Draft, create runs, delete is blocked
# ============================================================
_goi = []


class _Pool:
    async def call_tool(self, spec, tool, args):
        _goi.append((tool, args))
        return "OK"


TEN = ["label_write", "list_label"]
CONN_REC = {"id": "gh1", "connector_id": "gh-test", "label": "GitHub", "slug": "github",
            "namespace": "github", "perm": "readonly", "transport": "http",
            "url": "https://example.invalid/mcp", "headers": {}, "env": {}, "deny_tools": []}


def _discover_for(perm):
    async def _discover(conns, bo_qua=None):
        spec = {"transport": "http", "url": CONN_REC["url"], "headers": {}}
        tools, route = [], {}
        for name in TEN:
            fn = f"github__{name}"
            route[fn] = {"spec": spec, "tool": name,
                         "conn": {"id": "gh1", "namespace": "github", "perm": perm, "deny_tools": [],
                                  "label": "GitHub", "connector_id": "gh-test"}}
            tools.append({"fn": fn, "server": "github", "name": name, "description": name,
                          "schema": {"type": "object", "properties": {"method": {"type": "string"}}},
                          "conn_id": "gh1", "connector_id": "gh-test", "namespace": "github",
                          "label": "GitHub"})
        return tools, route
    return _discover


_goc_get = mcp_catalog.get
mcp_catalog.get = lambda cid: GH if cid == "gh-test" else _goc_get(cid)
mcp_store.resolved = lambda enabled_only=True: [CONN_REC]
mcp_client.pool = _Pool()
mcp_hub._builtin_tools = lambda *a, **k: ([], {})
config.read_settings = lambda: {"mcp": {"lazy_tools": "off"}}


def _list(perm):
    mcp_client.discover_resolved = _discover_for(perm)
    mcp_hub._cache.clear()
    return asyncio.run(mcp_hub.discover_all("full", include_plugins=False, force_refresh=True))


tools, _ = _list("readonly")
ten = {t["name"] for t in tools}
check("Read-only hides a tool with only write commands", "github__label_write" not in ten
      and "label_write" not in ten, sorted(ten))
check("Read-only still lists the read tool", any("list_label" in x for x in ten), sorted(ten))

tools, route = _list("safe")
ten = {t["name"] for t in tools}
check("Draft lists the tool", any("label_write" in x for x in ten), sorted(ten))
kq = asyncio.run(mcp_client.call_route(route, "github__label_write", {"method": "create", "name": "bug"}))
check("Draft: create reaches the server", kq == "OK" and _goi and _goi[-1][1]["method"] == "create", kq)
n = len(_goi)
kq = asyncio.run(mcp_client.call_route(route, "github__label_write", {"method": "delete", "name": "bug"}))
check("Draft: delete is blocked before the server", kq.startswith("ERROR:") and len(_goi) == n, kq)

if _fails:
    raise SystemExit(f"{len(_fails)} FAIL")
print("Tất cả xanh")
