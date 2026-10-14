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


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"JMdict database not found: {DB_PATH}\n"
            "Place jmdict.db at project root (see README), or build via build_db.py."
        )
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
