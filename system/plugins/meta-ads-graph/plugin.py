"""Plugin bundled: đọc số liệu Meta Ads (Facebook/Instagram) qua Graph API - CHỈ ĐỌC.

Không đi qua MCP beta bị khoá của Meta (mcp.facebook.com/ads); gọi THẲNG graph.facebook.com
Marketing API bằng user access token của kết nối "meta-ads-graph" (connector BYO app - user tự
tạo Facebook App, OAuth do oauth_mcp lo, token tự gia hạn ~60 ngày). Đây là cách Composio/byadsco
làm. Mọi tool đều readonly (chỉ GET) - không tạo/sửa chiến dịch, không tiêu tiền.
"""
from __future__ import annotations

import json

GRAPH = "https://graph.facebook.com/v25.0"
CONNECTOR_ID = "meta-ads-graph"
_INSIGHT_FIELDS = "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,action_values"
_CAMPAIGN_FIELDS = "name,status,effective_status,objective,daily_budget,lifetime_budget,start_time,stop_time"


def _connected_id():
    """id của kết nối meta-ads-graph ĐÃ đăng nhập (None nếu chưa). Import lười để load không phụ thuộc."""
    try:
        import mcp_store
        import oauth_mcp
    except Exception:
        return None
    for c in mcp_store.list_connections():
        if c.get("connector_id") == CONNECTOR_ID and oauth_mcp.status(c["id"]).get("connected"):
            return c["id"]
    return None


def _check():
    if not _connected_id():
        return ("Facebook is not connected. Go to the Connections page, choose 'Meta Ads (own app - Graph API)', "
                "follow the instructions to create a Facebook App, then sign in. After that, call this tool again.")
    return None


async def _token():
    import oauth_mcp
    cid = _connected_id()
    if not cid:
        return None
    hdr = await oauth_mcp.auth_headers(cid)      # tự refresh token ~60 ngày khi sắp hết hạn
    return (hdr.get("Authorization", "") or "").replace("Bearer ", "").strip() or None


async def _get(path, params, token):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{GRAPH}/{str(path).lstrip('/')}",
                            params={**(params or {}), "access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


def _fmt(d):
    if isinstance(d, dict) and d.get("error"):
        e = d["error"]
        return "ERROR: Facebook API: " + (e.get("message") if isinstance(e, dict) else str(e))
    return json.dumps(d, ensure_ascii=False, default=str)


async def _resolve_act(args, token):
    """Chuẩn hoá account_id thành 'act_<id>'; bỏ trống → lấy tài khoản quảng cáo đầu tiên."""
    aid = str((args or {}).get("account_id") or "").strip()
    if not aid:
        d = await _get("me/adaccounts", {"fields": "account_id", "limit": 1}, token)
        if isinstance(d, dict) and d.get("error"):
            return None, _fmt(d)
        data = (d or {}).get("data") or []
        if not data:
            return None, ("ERROR: No ad accounts found. Check that you have the ads_read permission "
                          "and are an admin of the ad account.")
        aid = data[0].get("account_id") or ""
    return "act_" + aid.replace("act_", ""), None


async def _accounts(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "not connected")
    d = await _get("me/adaccounts",
                   {"fields": "account_id,name,currency,account_status,amount_spent,balance", "limit": 100},
                   token)
    return _fmt(d)


async def _insights(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "not connected")
    act, err = await _resolve_act(args, token)
    if err:
        return err
    args = args or {}
    params = {"fields": _INSIGHT_FIELDS, "level": (args.get("level") or "account")}
    since, until = str(args.get("since") or "").strip(), str(args.get("until") or "").strip()
    if since and until:
        params["time_range"] = json.dumps({"since": since, "until": until})
    else:
        params["date_preset"] = args.get("date_preset") or "last_7d"
    d = await _get(f"{act}/insights", params, token)
    return _fmt(d)


async def _campaigns(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "not connected")
    act, err = await _resolve_act(args, token)
    if err:
        return err
    args = args or {}
    try:
        limit = max(1, min(200, int(args.get("limit") or 50)))
    except (TypeError, ValueError):
        limit = 50
    d = await _get(f"{act}/campaigns", {"fields": _CAMPAIGN_FIELDS, "limit": limit}, token)
    return _fmt(d)


async def _raw_get(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "not connected")
    args = args or {}
    path = str(args.get("path") or "").strip().lstrip("/")
    if not path:
        return "ERROR: missing 'path' (e.g. 'me/adaccounts', 'act_123/insights')."
    params = args.get("params")
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    if not isinstance(params, dict):
        params = {}
    d = await _get(path, params, token)
    return _fmt(d)


def register(ctx):
    ctx.register_tool(
        name="meta_ads_accounts", min_mode="readonly", check_fn=_check, handler=_accounts,
        description=("List your Facebook/Instagram ad accounts (id, name, currency, "
                     "status, total spent). Use it first to get the account_id for the other tools."),
        schema={"type": "object", "properties": {}},
    )
    ctx.register_tool(
        name="meta_ads_insights", min_mode="readonly", check_fn=_check, handler=_insights,
        description=("Facebook/Instagram ad performance: spend, impressions, clicks, CTR, CPC, CPM, "
                     "reach, conversion actions. Empty account_id = the first account. Default period "
                     "is 7 days; change it with date_preset (today/yesterday/last_7d/last_14d/last_30d/this_month/"
                     "last_month...) or since+until (YYYY-MM-DD). level = account|campaign|ad."),
        schema={"type": "object", "properties": {
            "account_id": {"type": "string", "description": "act_<id> or <id> (empty = the first account)"},
            "date_preset": {"type": "string", "description": "vd last_7d, last_30d, this_month"},
            "since": {"type": "string", "description": "From date YYYY-MM-DD (use together with until)"},
            "until": {"type": "string", "description": "To date YYYY-MM-DD"},
            "level": {"type": "string", "description": "account | campaign | ad (default account)"}}},
    )
    ctx.register_tool(
        name="meta_ads_campaigns", min_mode="readonly", check_fn=_check, handler=_campaigns,
        description=("List the ad campaigns of an account (name, status, objective, daily/lifetime "
                     "budget, run dates). Empty account_id = the first account."),
        schema={"type": "object", "properties": {
            "account_id": {"type": "string", "description": "act_<id> or <id> (empty = the first account)"},
            "limit": {"type": "integer", "description": "Maximum number of campaigns (default 50)"}}},
    )
    ctx.register_tool(
        name="meta_ads_get", min_mode="readonly", check_fn=_check, handler=_raw_get,
        description=("READ any node/edge of the Marketing Graph API (GET only, no writes). Use it when "
                     "the 3 tools above are not enough. path = Graph path (e.g. 'act_123/adsets', 'me/businesses'); "
                     "params = query parameters (object)."),
        schema={"type": "object", "properties": {
            "path": {"type": "string", "description": "Graph API path, e.g. 'act_123/adsets'"},
            "params": {"type": "object", "description": "Query parameters (e.g. {\"fields\":\"name,status\"})"}},
            "required": ["path"]},
    )
