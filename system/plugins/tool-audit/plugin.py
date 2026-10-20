"""Plugin bundled (DEMO HOOK): đếm lượt gọi mỗi tool + tool xem thống kê.

Minh hoạ 2 thứ:
  1. register_hook('post_tool_call', cb) - hook bắn SAU mỗi tool call (mọi engine).
  2. State riêng qua ctx.data_dir (STATE_DIR/plugin-data/tool-audit) - KHÔNG đụng vault.

Hook + tool cùng đọc/ghi 1 file counts.json qua closure (bắt data_dir lúc register).
Mặc định TẮT (manifest enabled:false) để người dùng chủ động bật - thể hiện luồng opt-in.
"""
from __future__ import annotations

import json
import threading


def register(ctx):
    data_dir = ctx.data_dir            # bắt lúc register: Path đã mkdir sẵn
    counts_file = data_dir / "counts.json"
    lock = threading.Lock()

    def _load():
        try:
            d = json.loads(counts_file.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _on_post_tool_call(tool_name="", **_):
        # Đừng tự đếm chính tool đọc thống kê (tránh nhiễu), và bỏ tên rỗng.
        if not tool_name or tool_name == "javis_tool_stats":
            return
        with lock:
            data = _load()
            data[tool_name] = int(data.get(tool_name, 0)) + 1
            try:
                counts_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    def _stats(args, cctx):
        data = _load()
        if not data:
            return "No tool calls recorded yet. Enable the plugin, chat a few turns that call tools, then check again."
        top = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:20]
        return json.dumps({
            "total_calls": sum(data.values()),
            "distinct_tools": len(data),
            "top": [{"tool": k, "calls": v} for k, v in top],
        }, ensure_ascii=False)

    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_tool(
        name="javis_tool_stats",
        description=("Counts how many times each tool has been called (recorded by the tool-audit plugin via the post_tool_call hook). "
                     "Shows which tools and data sources Jarvis 007 uses most."),
        handler=_stats, min_mode="readonly",
        schema={"type": "object", "properties": {}},
    )
