"""Plugin bundled: tool `javis_team` - quản lý nhóm chat từ MỌI engine (0.173.0).

Vì sao có tool này
==================
Chủ dự án (2026-10-16) muốn nói trong chat "tạo nhóm thử gồm vài trợ lý, mỗi người một model" là Javis làm luôn: tạo trợ lý
còn thiếu, lập nhóm, chọn trưởng nhóm. Trước bản này Javis chỉ có route `/teams/*` sau cổng đăng nhập, nên một phiên chat phải
điều khiển trình duyệt (Playwright) và vấp lỗi 401. Tool chạy IN-PROCESS qua `team_api.current()`: cùng một lớp `TeamOps` mà
route của trang Nhóm dùng, nên luật (trợ lý phải có thật, khoá, huỷ việc khi lưu trữ, chạy lại khi mở lại) y như bấm tay.

Luật an toàn
============
- `vault_root` rỗng -> lỗi rõ, không bao giờ đoán brain (giống `javis_task`).
- Xoá chỉ nhận nhóm ĐÃ lưu trữ và phải có `confirm: true`; model chỉ đặt cờ đó khi chủ nói rõ là xoá.
- Mức `safe`: chỉ ghi file trợ lý và dữ liệu nhóm trong máy, không thao tác ra ngoài. Chỉ chủ dùng (`OWNER_ONLY_TOOLS`).
"""
from __future__ import annotations

import asyncio

try:
    import team_api
except Exception:          # chạy lẻ ngoài máy chủ
    team_api = None

_LIST_MAX = 30
_OPS = ("list", "get", "list_agents", "create", "update", "archive", "unarchive", "delete", "add_member",
        "remove_member", "set_leader", "create_agent", "set_agent_model")
_NO_OPS = ("ERROR: the team manager is not ready (is the server starting up?). Try again in a few seconds, "
           "or do it on the Teams page of the dashboard.")


class _Fail(Exception):
    pass


def _s(v) -> str:
    return str(v or "").strip()


def _ops():
    ops = team_api.current() if team_api is not None else None
    if ops is None:
        raise _Fail(_NO_OPS)
    return ops


def _err_text(ex: Exception) -> str:
    if team_api is not None and isinstance(ex, team_api.OpError):
        return f"ERROR: {ex.vi}"
    return f"ERROR: {ex}"


def _agents(ops, root) -> list:
    return list(ops.deps.agents_meta(root) or [])


def _agent_models(root) -> dict:
    """{slug: (model, provider)} đọc thẳng từ frontmatter (agents_meta chỉ có provider đã suy)."""
    out = {}
    try:
        from skill_router import read_frontmatter_only
        from pathlib import Path
        d = Path(root) / "agents"
        for fp in sorted(d.glob("*.md")) if d.is_dir() else []:
            meta = read_frontmatter_only(fp)[0] or {}
            out[fp.stem] = (_s(meta.get("model")), _s(meta.get("model_provider")))
    except Exception:
        pass
    return out


def _find_team(ops, root, ref) -> dict:
    """`ref` là team_id hay TÊN nhóm (không phân biệt hoa thường) trong brain này."""
    ref = _s(ref)
    if not ref:
        raise _Fail("ERROR: missing team (team id or team name). Use op=list to see the teams.")
    if not ops.api.exists():
        raise _Fail("ERROR: this brain has no teams yet. Use op=create to make one.")
    team = ops.api.teams().get(ref)
    if team and team["brain_id"] == root:
        return team
    hits = [t for t in ops.api.teams().list_teams(root, limit=200, include_archived=True)
            if _s(t.get("name")).lower() == ref.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise _Fail(f"ERROR: {len(hits)} teams share the name '{ref}'. Use the team id: "
                    + ", ".join(f"{t['team_id']} ({t['status']})" for t in hits))
    raise _Fail(f"ERROR: no team '{ref}' in this brain. Use op=list to see the teams.")


def _team_line(ops, team, models=None) -> str:
    members = [m for m in ops.api.teams().members(team["team_id"])]
    names = []
    for m in members:
        slug = m.get("slug_at_join") or m["agent_key"]
        mark = " (team leader)" if m["agent_key"] == team.get("leader_key") else ""
        mdl = (models or {}).get(slug, ("", ""))[0]
        names.append(f"{slug}{mark}" + (f" [{mdl}]" if mdl else ""))
    return (f"- {team['name']} | id {team['team_id']} | {team['status']} | "
            + (", ".join(names) or "no assistants yet"))


def _new_agent(ops, root, spec: dict) -> str:
    name = _s(spec.get("name"))
    if not name:
        raise _Fail("ERROR: a new assistant needs a name.")
    role = _s(spec.get("role")) or name
    return ops.deps.admin.create_agent(root, name, role, _s(spec.get("prompt")), model=_s(spec.get("model")),
                                       model_provider=_s(spec.get("model_provider")), tags=spec.get("tags") or None)


def _do(op: str, args: dict, root: str) -> str:
    ops = _ops()
    if op == "list":
        if not ops.api.exists():
            return "This brain has no teams yet."
        teams = ops.api.teams().list_teams(root, limit=_LIST_MAX, include_archived=bool(args.get("include_archived")))
        models = _agent_models(root)
        return ("Teams in this brain:\n" + "\n".join(_team_line(ops, t, models) for t in teams)) if teams \
            else "This brain has no teams yet (or only archived teams: add include_archived=true)."
    if op == "list_agents":
        models = _agent_models(root)
        rows = _agents(ops, root)
        if not rows:
            return "This brain has no assistants yet. Use op=create_agent to make one."
        return "Assistants in this brain (slug | name | role | own model):\n" + "\n".join(
            f"- {a['slug']} | {a.get('name') or a['slug']} | {a.get('title') or ''} | "
            + (models.get(a["slug"], ("", ""))[0] or "main model") for a in rows[:80])
    if op == "get":
        team = _find_team(ops, root, args.get("team"))
        return _team_line(ops, team, _agent_models(root)) + (f"\nDescription: {team['description']}" if team.get("description")
                                                             else "")
    if op == "create":
        created = [_new_agent(ops, root, a) for a in (args.get("new_agents") or []) if isinstance(a, dict)]
        members = [_s(m) for m in (args.get("members") or []) if _s(m)] + created
        leader = _s(args.get("leader"))
        if leader and leader not in members:
            # Trưởng nhóm có thể là TÊN trợ lý (kể cả trợ lý vừa tạo): đổi về slug thật nếu khớp đúng một trợ lý.
            hits = [a["slug"] for a in _agents(ops, root) if _s(a.get("name")).lower() == leader.lower()]
            leader = hits[0] if len(hits) == 1 else leader
        got = ops.create(root, root, args.get("name"), members, leader, _s(args.get("description")),
                         _s(args.get("client_req_id")))
        team = got["team"]
        head = "This team already existed (same request id), so none was created." if got["duplicate"] else "Team created."
        extra = f" New assistants created: {', '.join(created)}." if created else ""
        return (f"{head}{extra}\n{_team_line(ops, team, _agent_models(root))}\n"
                "The owner opens the Teams page to message the team.")
    if op == "create_agent":
        slug = _new_agent(ops, root, args)
        msg = f"Created assistant '{slug}'" + (f" with model {_s(args.get('model'))}" if _s(args.get("model")) else "") + "."
        if _s(args.get("team")):
            team = _find_team(ops, root, args.get("team"))
            ops.add_member(root, team["team_id"], slug)
            msg += f" Added to team {team['name']}."
            if args.get("leader"):
                ops.set_leader(root, team["team_id"], ops.member_key(team, slug))
                msg += " This assistant is the team leader."
        return msg
    if op == "set_agent_model":
        slug = _s(args.get("slug"))
        if not slug:
            return "ERROR: missing the assistant slug."
        prov = _s(args.get("model_provider"))
        if prov and prov not in ops.deps.admin.providers():
            return "ERROR: invalid model_provider. Choose one of: " + ", ".join(ops.deps.admin.providers())
        try:
            r = ops.deps.admin.set_model(root, slug, _s(args.get("model")), prov)
        except FileNotFoundError:
            return f"ERROR: no assistant '{slug}'. Use op=list_agents to see them."
        return f"Set the model of '{slug}': " + (r["model"] or "use the main model") + (
            f" ({r['model_provider']})" if r["model_provider"] else "") + "."

    team = _find_team(ops, root, args.get("team"))
    tid = team["team_id"]
    if op == "update":
        fields = {k: args.get(k) for k in ("name", "description") if args.get(k) is not None}
        if not fields:
            return "ERROR: op=update needs a new name or description."
        t = ops.update(root, tid, **fields)
        return "Team updated.\n" + _team_line(ops, t)
    if op == "archive":
        ops.update(root, tid, status="archived")
        return f"Team {team['name']} archived: the team's pending work was cancelled. To reopen it use op=unarchive."
    if op == "unarchive":
        ops.update(root, tid, status="active")
        return f"Reopened team {team['name']}."
    if op == "delete":
        if args.get("confirm") is not True:
            return ("ERROR: deleting a team cannot be undone. Only call again with confirm=true when the owner has clearly said to delete the team "
                    f"'{team['name']}'.")
        if team["status"] != "archived":
            return (f"ERROR: team '{team['name']}' is not archived. Archive it first (op=archive), then it can be deleted.")
        ops.delete(root, tid)
        return f"Permanently deleted team {team['name']} together with its conversation."
    if op == "add_member":
        slug = _s(args.get("slug"))
        if not slug:
            return "ERROR: missing the slug of the assistant to add."
        return "Member added.\n" + _team_line(ops, ops.add_member(root, tid, slug))
    if op == "remove_member":
        key = ops.member_key(team, args.get("member") or args.get("slug"))
        return "Member removed.\n" + _team_line(ops, ops.remove_member(root, tid, key))
    if op == "set_leader":
        who = args.get("member") or args.get("slug")
        key = ops.member_key(team, who) if _s(who) else None
        return ("Team leader changed.\n" if key else "Team leader cleared.\n") + _team_line(ops, ops.set_leader(root, tid, key))
    return "ERROR: invalid op."


async def _run(args, ctx) -> str:
    args = args or {}
    op = _s(args.get("op")).lower()
    if op not in _OPS:
        return "ERROR: op must be one of: " + ", ".join(_OPS) + "."
    if not ctx.vault_root:
        return ("ERROR: it is not known which brain is being worked on, so teams cannot be changed. "
                "Do it on the Teams page of the dashboard, where the brain is clearly identified.")
    try:
        root = _ops().root(str(ctx.vault_root))
        return await asyncio.to_thread(_do, op, args, root)
    except _Fail as ex:
        return str(ex)
    except Exception as ex:  # noqa: BLE001 - lỗi kho/luật trả về chữ cho model, không làm hỏng lượt
        return _err_text(ex)


def register(ctx):
    ctx.register_tool(
        "javis_team",
        "Quản lý nhóm chat của brain: tạo, sửa, lưu trữ, xoá nhóm; thêm, bỏ trợ lý; chọn trưởng nhóm; tạo trợ lý mới "
        "(có thể đặt model riêng) rồi ghép vào nhóm. Dùng khi NGƯỜI DÙNG muốn có hay đổi một nhóm; đừng tự lập nhóm khi họ "
        "chưa nhờ. "
        "op=list (nhóm của brain), list_agents (trợ lý và model riêng), get (team). "
        "op=create: name, members (slug trợ lý có sẵn), new_agents (trợ lý cần tạo mới: [{name, role, prompt, model, "
        "model_provider}]), leader (slug hay tên), description. Một lần gọi tạo đủ trợ lý rồi lập nhóm. "
        "op=create_agent: name, role, prompt, model, model_provider; thêm team để ghép luôn vào nhóm, leader=true để làm "
        "trưởng nhóm. op=set_agent_model: slug, model (rỗng = model chính), model_provider. "
        "op=update: team + name/description. op=archive / unarchive: team. "
        "op=delete: chỉ nhóm ĐÃ lưu trữ, và chỉ kèm confirm=true khi chủ nói rõ là xoá (không hoàn tác). "
        "op=add_member: team + slug. op=remove_member / set_leader: team + member (slug). "
        "team nhận mã nhóm hay tên nhóm. Model riêng: model là tên model (vd sonnet, haiku, opus, gpt-5.5), "
        "model_provider là nhà chạy (anthropic-cli, openai-oauth, openrouter, ...); bỏ trống provider thì Javis tự suy.",
        _run,
        schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": list(_OPS)},
                "team": {"type": "string", "description": "Team id (tm_...) or team name"},
                "name": {"type": "string", "description": "Team name (create/update) or assistant name (create_agent)"},
                "description": {"type": "string"},
                "members": {"type": "array", "items": {"type": "string"}, "description": "Slugs of existing assistants"},
                "new_agents": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"},
                    "model": {"type": "string"}, "model_provider": {"type": "string"}}}},
                "leader": {"description": "create: slug or name of the team leader; create_agent: true to make it the team leader"},
                "slug": {"type": "string", "description": "Assistant slug (add_member, set_agent_model)"},
                "member": {"type": "string", "description": "Slug or id of the member (remove_member, set_leader)"},
                "role": {"type": "string"},
                "prompt": {"type": "string"},
                "model": {"type": "string"},
                "model_provider": {"type": "string"},
                "include_archived": {"type": "boolean"},
                "confirm": {"type": "boolean", "description": "Only true when the owner clearly said to delete the team"},
                "client_req_id": {"type": "string"},
            },
            "required": ["op"],
        },
        min_mode="safe",
        emoji="👥",
    )
