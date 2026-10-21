# -*- coding: utf-8 -*-
"""Read-only SQLite connection for JMdict."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Prefer project-root jmdict.db; fall back to web/jmdict.db
_ROOT = Path(__file__).resolve().parent.parent
_WEB = Path(__file__).resolve().parent
DB_PATH = _ROOT / "jmdict.db"
if not DB_PATH.is_file():
    DB_PATH = _WEB / "jmdict.db"


class DatabaseUnavailable(Exception):
    """Dictionary file missing or SQLite could not open it."""


def get_connection() -> sqlite3.Connection:
    """One connection per caller thread. Do not share it across threads."""
    if not DB_PATH.is_file():
        raise DatabaseUnavailable(
            f"词典数据库不存在：{DB_PATH.name}\n"
            "Place jmdict.db at project root (see README), or build via build_db.py."
        )
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.Error as e:
        raise DatabaseUnavailable("无法打开词典数据库") from e
    conn.row_factory = sqlite3.Row
    return conn
