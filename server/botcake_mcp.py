"""
Cầu nối Botcake (transport "internal" trong catalog) - Botcake KHÔNG có MCP chính chủ,
Javis tự bọc Public API v1 thành bộ tool MCP-tương-đương.
Đã verify 2026-07-04: base https://botcake.io/api/public_api/v1, auth header
"access-token: <page token>" (Botcake > Cấu hình > Tích hợp > Public API).
spec["secrets"] = {"api_key": <token>, "page_id": <id trang>} (mcp_store.resolved cấp).
"""
import json

import httpx

BASE = "https://botcake.io/api/public_api/v1"


def _clip(text, max_chars=8000):
    text = str(text)
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    return (text[:head] + f"\n… [RESULT TRUNCATED - dropped {len(text) - head - tail:,} characters from the middle] …\n"
            + text[-tail:])


def _t(name, description, props=None, required=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}, "required": required or []}}


TOOLS = [
    _t("botcake_customers", "List of customers (subscribers) of the Botcake page, paginated.",
       {"page": {"type": "integer", "description": "page, default 1"}}),
    _t("botcake_customer", "Activity history / details of one customer by PSID.",
       {"psid": {"type": "string"}}, ["psid"]),
    _t("botcake_customer_fields_get", "Read the custom fields of one customer by PSID.",
       {"psid": {"type": "string"}}, ["psid"]),
    _t("botcake_customer_fields_set", "Write one custom field for a customer (a WRITE action).",
       {"psid": {"type": "string"}, "field_name": {"type": "string"}, "value": {"type": "string"}},
       ["psid", "field_name", "value"]),
    _t("botcake_custom_fields", "List of the page's custom fields."),
    _t("botcake_tags", "List of the page's tags."),
    _t("botcake_tag_statistic", "Customer counts by tag."),
    _t("botcake_flows", "List of the page's flows (chatbot scripts)."),
    _t("botcake_flow_statistics", "Statistics of one flow by flow_id.",
       {"flow_id": {"type": "string"}}, ["flow_id"]),
    _t("botcake_send_flow", "SEND one REAL flow to a customer (PSID) - the message will reach a real person, "
       "use it ONLY when the user explicitly asks. (The API body is not 100% verified - if it errors, report it back.)",
       {"psid": {"type": "string"}, "flow_id": {"type": "string"}}, ["psid", "flow_id"]),
    _t("botcake_keywords", "List of the page's auto-reply keywords."),
    _t("botcake_sequences", "List of the page's sequences (recurring message series)."),
    _t("botcake_message_templates", "List of the page's message templates."),
]

# tool -> (method, path template có {page_id}/{psid}/{flow_id}, query builder?)
_ROUTES = {
    "botcake_customers": ("GET", "/pages/{page_id}/customer"),
    "botcake_customer": ("GET", "/pages/{page_id}/customer/{psid}"),
    "botcake_customer_fields_get": ("GET", "/pages/{page_id}/customer/{psid}/customer_fields"),
    "botcake_customer_fields_set": ("POST", "/pages/{page_id}/customer/{psid}/customer_fields"),
    "botcake_custom_fields": ("GET", "/pages/{page_id}/custom_fields"),
    "botcake_tags": ("GET", "/pages/{page_id}/get_list_tag"),
    "botcake_tag_statistic": ("GET", "/pages/{page_id}/get_tag_statistic"),
    "botcake_flows": ("GET", "/pages/{page_id}/flows"),
    "botcake_flow_statistics": ("GET", "/pages/{page_id}/flows/{flow_id}/statistics"),
    "botcake_send_flow": ("POST", "/pages/{page_id}/flows/send_flow"),
    "botcake_keywords": ("GET", "/pages/{page_id}/keywords"),
    "botcake_sequences": ("GET", "/pages/{page_id}/sequences/"),
    "botcake_message_templates": ("GET", "/pages/{page_id}/message_templates"),
}


async def list_tools(spec):
    return TOOLS


async def call(tool, arguments, spec):
    secrets = (spec or {}).get("secrets") or {}
    token = secrets.get("api_key", "")
    page_id = str(secrets.get("page_id", "")).strip()
    if not token or not page_id:
        return "ERROR: the Botcake connection is missing page_id/API key - fix it on the Connections page"
    ent = _ROUTES.get(tool)
    if not ent:
        return f"ERROR: tool '{tool}' does not exist in the Botcake bridge"
    method, path = ent
    args = arguments or {}
    try:
        path = path.format(page_id=page_id, psid=str(args.get("psid", "")).strip(),
                           flow_id=str(args.get("flow_id", "")).strip())
    except KeyError:
        pass
    params, body = {}, None
    if tool == "botcake_customers":
        params["page"] = int(args.get("page") or 1)
    elif tool == "botcake_customer_fields_set":
        body = {"field_name": args.get("field_name"), "value": args.get("value")}
    elif tool == "botcake_send_flow":
        body = {"psid": args.get("psid"), "flow_id": args.get("flow_id")}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.request(method, BASE + path, params=params or None, json=body,
                                     headers={"access-token": token})
        if r.status_code >= 400:
            return f"ERROR: Botcake {r.status_code}: {(r.text or '')[:300]}"
        try:
            return _clip(json.dumps(r.json(), ensure_ascii=False))
        except ValueError:
            return _clip(r.text or "(empty)")
    except Exception as e:
        return f"ERROR: Botcake did not respond: {type(e).__name__}: {e}"
