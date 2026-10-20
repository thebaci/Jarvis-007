"""Snapshot một lần trước khi nhóm chat team (0.140.0) thêm cột vào kho có sẵn (spec 2026-10-13-team-chat-design mục 18).

`task_store.TaskStore` (cột làn `team` của `tasks`) và `sessions.SessionStore` (cột người gửi của `messages`) gọi
`snapshot_once` TRƯỚC khi mở kết nối và chạy migration. Lần đầu mã mới gặp một kho cũ (bảng có mà chưa có cột đánh dấu),
kho được chép nguyên thành `<tên>.pre-0.140.0` bằng SQLite backup API (lấy cả phần còn trong WAL). Bản sao đã có thì không
ghi đè; kho mới tinh thì không chép. Khôi phục: `tools/team_chat_restore_pre.py` (chạy khi Javis đã tắt).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

SNAPSHOT_SUFFIX = ".pre-0.140.0"


def snapshot_once(path: Path, table: str, marker_column: str, suffix: str = SNAPSHOT_SUFFIX) -> Optional[Path]:
    """Chép kho `path` thành `<tên><suffix>` (mặc định `.pre-0.140.0`) nếu bảng `table` có mà chưa có cột `marker_column`.
    Trả đường dẫn bản sao vừa tạo, hay None. Lỗi chỉ in ra, không chặn việc mở kho (mất bản sao còn hơn không chạy được).
    T2 (0.154.0) dùng `suffix=".pre-0.154.0"` cho `team.sqlite3` (cột mới của reaction)."""
    path = Path(path)
    bak = path.with_name(path.name + suffix)
    try:
        if bak.exists() or not path.is_file() or path.stat().st_size == 0:
            return None
        with closing(sqlite3.connect(str(path), timeout=10)) as src:
            cols = {r[1] for r in src.execute(f"PRAGMA table_info({table})").fetchall()}
            if not cols or marker_column in cols:
                return None
            tmp = bak.with_name(bak.name + ".tmp")
            with closing(sqlite3.connect(str(tmp))) as dst:
                src.backup(dst)
            os.replace(tmp, bak)
        return bak
    except Exception as ex:  # noqa: BLE001
        import sys
        print(f"[team migration] could not snapshot {path.name}: {type(ex).__name__}: {ex}", file=sys.stderr)
        return None


def snapshot_before_table(path: Path, base_table: str, marker_table: str, suffix: str) -> Optional[Path]:
    """Chép kho `path` thành `<tên><suffix>` lần đầu mã mới gặp một kho cũ: bảng `base_table` có mà bảng `marker_table`
    chưa có (T2 dùng cho `conversations.db`, bảng `dm_reactions`). Cùng luật với `snapshot_once`."""
    path = Path(path)
    bak = path.with_name(path.name + suffix)
    try:
        if bak.exists() or not path.is_file() or path.stat().st_size == 0:
            return None
        with closing(sqlite3.connect(str(path), timeout=10)) as src:
            names = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if base_table not in names or marker_table in names:
                return None
            tmp = bak.with_name(bak.name + ".tmp")
            with closing(sqlite3.connect(str(tmp))) as dst:
                src.backup(dst)
            os.replace(tmp, bak)
        return bak
    except Exception as ex:  # noqa: BLE001
        import sys
        print(f"[migration] could not snapshot {path.name}: {type(ex).__name__}: {ex}", file=sys.stderr)
        return None
