# -*- coding: utf-8 -*-
"""Read-only SQLite connection for JMdict."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Prefer project-root jmdict.db; fall back to web/jmdict.db.
# JMDICT_DB overrides both.
_ROOT = Path(__file__).resolve().parent.parent
_WEB = Path(__file__).resolve().parent
_DEFAULT = _ROOT / "jmdict.db"
if not _DEFAULT.is_file():
    _DEFAULT = _WEB / "jmdict.db"
DB_PATH = Path(os.environ.get("JMDICT_DB") or _DEFAULT)


class DatabaseUnavailable(Exception):
    """Dictionary file missing or SQLite could not open it."""


def get_connection() -> sqlite3.Connection:
    """One connection per caller thread. Do not share it across threads."""
    if not DB_PATH.is_file():
        raise DatabaseUnavailable(
            f"词典数据库不存在：{DB_PATH.name}\n"
            "把 jmdict.db 放在仓库根目录，或设置环境变量 JMDICT_DB。"
        )
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.Error as e:
        raise DatabaseUnavailable("无法打开词典数据库") from e
    conn.row_factory = sqlite3.Row
    return conn
