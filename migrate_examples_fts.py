# -*- coding: utf-8 -*-
"""给现有 jmdict.db 补例句全文索引 examples_fts（幂等，可重复执行）。

lookup._fetch_examples 对 3 字及以上的词形走这张 trigram 索引，
避免每次 instr() 全表扫 3.2 万行例句。

用法:
    python migrate_examples_fts.py
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parent / "jmdict.db"

_CREATE = (
    "CREATE VIRTUAL TABLE examples_fts USING fts5("
    "jpn, content='examples', content_rowid='id', tokenize='trigram')"
)


def ensure_examples_fts(conn: sqlite3.Connection, rebuild: bool = False) -> str:
    """Create examples_fts when missing. Rebuild when asked or when row counts differ."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='examples_fts'"
    ).fetchone()
    sql = (row[0] or "") if row else ""
    if "trigram" not in sql:
        if row is not None:
            conn.execute("DROP TABLE examples_fts")
        conn.execute(_CREATE)
        rebuild = True
    n_ex = conn.execute("SELECT COUNT(*) FROM examples").fetchone()[0]
    n_fts = conn.execute("SELECT COUNT(*) FROM examples_fts").fetchone()[0]
    if rebuild or n_fts != n_ex:
        conn.execute("INSERT INTO examples_fts(examples_fts) VALUES('rebuild')")
        n_fts = conn.execute("SELECT COUNT(*) FROM examples_fts").fetchone()[0]
        action = "rebuild"
    else:
        action = "skip"
    conn.commit()
    return f"{action} examples={n_ex} fts={n_fts}"


def main() -> int:
    if not DB.is_file():
        print(f"[x] 找不到 {DB}")
        return 1

    before = DB.stat().st_size
    conn = sqlite3.connect(str(DB), timeout=30)
    try:
        t0 = time.perf_counter()
        status = ensure_examples_fts(conn)
        print(f"[+] {status}（{time.perf_counter() - t0:.2f}s）")
        plan = " | ".join(
            str(r[3]) for r in conn.execute(
                "EXPLAIN QUERY PLAN SELECT rowid FROM examples_fts "
                "WHERE examples_fts MATCH '\"食べる\"'"
            )
        )
        print(f"[i] 查询计划: {plan}")
    finally:
        conn.close()

    after = DB.stat().st_size
    print(f"[i] 库大小 {before / 1048576:.1f}MB -> {after / 1048576:.1f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
