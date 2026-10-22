# -*- coding: utf-8 -*-
"""一条命令把运行所需的数据准备好。

用法：
    python setup_data.py

做四件事（幂等，可重复运行）：
  1. 下载 JMdict 英文版词库（约 30 MB 压缩包），解压成 JMdict_e.xml
  2. 调用 build_db.py 生成 jmdict.db（词条 / 义项 / 词形）
  3. 把 data/openjlpt_grammar_*.json 里的语法条目导入 grammar 表
  4. 确认所有增强表存在（缺的建空表，避免接口报「表不存在」）

完成后直接：
    .\\start.ps1          然后打开 http://127.0.0.1:8765/

可选环境变量：
    JMDICT_GZ_URL   自定义 JMdict 压缩包地址（默认 EDRDG 官方）
    SKIP_DOWNLOAD=1 已有 JMdict_e.xml 时跳过下载
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
XML = ROOT / "JMdict_e.xml"
GZ = ROOT / "JMdict_e.gz"
DB = ROOT / "jmdict.db"
DATA = ROOT / "data"
DEFAULT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"

REQUIRED_TABLES = {
    "grammar": (
        "CREATE TABLE IF NOT EXISTS grammar (id INTEGER PRIMARY KEY, pattern TEXT, "
        "explain TEXT, level TEXT, connection TEXT, examples TEXT, explain_zh TEXT)"
    ),
    "jlpt": "CREATE TABLE IF NOT EXISTS jlpt (word_form TEXT PRIMARY KEY, level TEXT)",
    "gloss_zh": "CREATE TABLE IF NOT EXISTS gloss_zh (word_form TEXT PRIMARY KEY, accent TEXT, gloss TEXT)",
    "examples": "CREATE TABLE IF NOT EXISTS examples (id INTEGER PRIMARY KEY, jpn TEXT, cmn TEXT)",
}


def step(n: int, total: int, text: str) -> None:
    print(f"\n[{n}/{total}] {text}")


def download(url: str, dest: Path) -> None:
    print(f"    来源 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "japanese-learning-setup/1.0"})
    t0 = time.time()
    last = [0.0]

    def hook(blocks: int, block_size: int, total_size: int) -> None:
        got = blocks * block_size
        now = time.time()
        if now - last[0] > 1.0:
            last[0] = now
            if total_size > 0:
                pct = min(100.0, got * 100.0 / total_size)
                print(f"    {got/1048576:6.1f} MB / {total_size/1048576:5.1f} MB  {pct:5.1f}%", end="\r")
            else:
                print(f"    {got/1048576:6.1f} MB", end="\r")

    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(262144)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            hook(0, got, total)
    print(f"\n    完成，用时 {time.time() - t0:.0f}s，文件 {dest.stat().st_size/1048576:.1f} MB")


def import_grammar(conn: sqlite3.Connection) -> int:
    total = 0
    for level in ("n5", "n4", "n3", "n2", "n1"):
        path = DATA / f"openjlpt_grammar_{level}.json"
        if not path.is_file():
            print(f"    - 跳过 {path.name}（不存在）")
            continue
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"    ! {path.name} 解析失败：{e}")
            continue
        if not isinstance(items, list):
            print(f"    ! {path.name} 不是数组，跳过")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            pattern = (item.get("pattern") or "").strip()
            if not pattern:
                continue
            # examples 里是 [{ja, en}, ...]，原样存 JSON，前端直接渲染
            examples = item.get("examples")
            examples_json = (json.dumps(examples, ensure_ascii=False)
                             if isinstance(examples, list) and examples else None)
            conn.execute(
                "INSERT INTO grammar (pattern, explain, level, connection, examples, explain_zh)"
                " VALUES (?,?,?,?,?,?)",
                (
                    pattern,
                    (item.get("meaning") or "").strip() or None,
                    (item.get("level") or level.upper()).strip() or None,
                    (item.get("formation") or "").strip() or None,
                    examples_json,
                    (item.get("meaning_zh") or "").strip() or None,
                ),
            )
            total += 1
        print(f"    + {path.name}: {len(items)} 条")
    conn.commit()
    return total


def import_grammar_extra(conn: sqlite3.Connection) -> int:
    """追加导入 thesaurus 来源的语法（Japanese-Chinese-thesaurus，Unlicense）。

    与上面 openjlpt 那 100 条分开存放：这里只有中文释义（写进 explain_zh），
    没有英文原文，部分条目带例句。
    """
    path = DATA / "grammar_extra.jsonl.gz"
    if not path.is_file():
        print(f"    - 跳过 {path.name}（不存在）")
        return 0
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            pattern = (o.get("pattern") or "").strip()
            if not pattern:
                continue
            ex = o.get("examples")
            conn.execute(
                "INSERT INTO grammar (pattern, explain, level, connection, examples, explain_zh)"
                " VALUES (?,?,?,?,?,?)",
                (pattern,
                 None,
                 (o.get("level") or None),
                 (o.get("connection") or None),
                 json.dumps(ex, ensure_ascii=False) if isinstance(ex, list) and ex else None,
                 (o.get("explain_zh") or None)),
            )
            n += 1
    conn.commit()
    print(f"    + {path.name}: {n} 条（thesaurus，Unlicense 公有领域）")
    return n


def import_jsonl(conn: sqlite3.Connection, table: str, path: Path, cols: list[str],
                 replace: bool = True) -> int:
    """把 data/*.jsonl.gz 导入指定表。

    replace=True 先清空表（主数据）；replace=False 追加/覆盖单条（补充数据）。
    """
    if not path.is_file():
        print(f"    - 跳过 {path.name}（不存在）")
        return 0
    if replace:
        conn.execute(f"DELETE FROM {table}")
    sql = (f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) "
           f"VALUES ({','.join('?' * len(cols))})")
    n = 0
    batch: list[tuple] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            batch.append(tuple(obj.get(c) for c in cols))
            if len(batch) >= 2000:
                conn.executemany(sql, batch)
                n += len(batch)
                batch.clear()
    if batch:
        conn.executemany(sql, batch)
        n += len(batch)
    conn.commit()
    print(f"    + {path.name}: {n} 行 -> {table}")
    return n


def main() -> int:
    total_steps = 5
    print("=" * 68)
    print("日语学习 · 数据准备")
    print("=" * 68)
    print(f"项目目录：{ROOT}")

    # --- 1. 下载 JMdict -------------------------------------------------
    step(1, total_steps, "检查 JMdict 词库源文件")
    if XML.is_file() and XML.stat().st_size > 5_000_000:
        print(f"    [=] 已有 JMdict_e.xml（{XML.stat().st_size/1048576:.1f} MB），跳过下载")
    elif os.environ.get("SKIP_DOWNLOAD") == "1":
        print("    [x] SKIP_DOWNLOAD=1 但 JMdict_e.xml 不存在或过小")
        return 1
    else:
        url = os.environ.get("JMDICT_GZ_URL", DEFAULT_URL)
        try:
            print("    下载 JMdict（约 30 MB，请耐心等待）…")
            download(url, GZ)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"    [x] 下载失败：{e}")
            print("        手动方案：浏览器打开 https://www.edrdg.org/wiki/index.php/"
                  "JMdict-EDICT_Dictionary_Project")
            print("        下载 JMdict_e.gz，解压出 JMdict_e.xml 放到项目根目录，再重跑本脚本。")
            return 1
        print("    解压 …")
        try:
            with gzip.open(GZ, "rb") as src, open(XML, "wb") as dst:
                shutil.copyfileobj(src, dst)
        except OSError as e:
            print(f"    [x] 解压失败：{e}")
            return 1
        print(f"    [+] JMdict_e.xml {XML.stat().st_size/1048576:.1f} MB")

    # --- 2. 建库 --------------------------------------------------------
    step(2, total_steps, "生成 jmdict.db（可能需 1–3 分钟）")
    t0 = time.time()
    rc = subprocess.call([sys.executable, str(ROOT / "build_db.py")])
    if rc != 0:
        print("    [x] build_db.py 失败")
        return rc
    print(f"    用时 {time.time() - t0:.0f}s")

    if not DB.is_file():
        print("    [x] 没有生成 jmdict.db")
        return 1

    # --- 3. 导入语法 ----------------------------------------------------
    step(3, total_steps, "导入语法条目")
    conn = sqlite3.connect(str(DB))
    try:
        for ddl in REQUIRED_TABLES.values():
            conn.execute(ddl)
        # 老库没有这几列，补上（SQLite 加列是幂等的，重复会报错所以先查）
        existing = {r[1] for r in conn.execute("PRAGMA table_info(grammar)")}
        for col in ("examples", "explain_zh"):
            if col not in existing:
                conn.execute(f"ALTER TABLE grammar ADD COLUMN {col} TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grammar_level ON grammar(level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_examples_jpn ON examples(jpn)")
        existed = conn.execute("SELECT COUNT(*) FROM grammar").fetchone()[0]
        if existed:
            print(f"    [=] grammar 表已有 {existed} 条，清空后重新导入")
            conn.execute("DELETE FROM grammar")
            conn.commit()
        n = import_grammar(conn)
        n += import_grammar_extra(conn)
        print(f"    [+] 共导入 {n} 条语法")
    finally:
        conn.close()

    # --- 4. 导入分级 / 中文释义 / 例句 ----------------------------------
    step(4, total_steps, "导入 JLPT 分级、中文释义、例句")
    conn = sqlite3.connect(str(DB))
    try:
        for ddl in REQUIRED_TABLES.values():
            conn.execute(ddl)
        # 老库没有这几列，补上（SQLite 加列是幂等的，重复会报错所以先查）
        existing = {r[1] for r in conn.execute("PRAGMA table_info(grammar)")}
        for col in ("examples", "explain_zh"):
            if col not in existing:
                conn.execute(f"ALTER TABLE grammar ADD COLUMN {col} TEXT")
        import_jsonl(conn, "jlpt", DATA / "jlpt_words.jsonl.gz", ["word_form", "level"])
        import_jsonl(conn, "gloss_zh", DATA / "gloss_zh.jsonl.gz",
                     ["word_form", "accent", "gloss"])
        # 补充释义：本机模型翻译的 JLPT 缺口词，追加而非覆盖（与上游数据分开存放）
        import_jsonl(conn, "gloss_zh", DATA / "gloss_zh_extra.jsonl.gz",
                     ["word_form", "accent", "gloss"], replace=False)
        import_jsonl(conn, "examples", DATA / "examples.jsonl.gz", ["jpn", "cmn"])
        conn.execute("CREATE INDEX IF NOT EXISTS idx_examples_jpn ON examples(jpn)")
        from migrate_examples_fts import ensure_examples_fts
        ensure_examples_fts(conn, rebuild=True)
        conn.commit()
    finally:
        conn.close()

    # --- 5. 汇总 --------------------------------------------------------
    step(5, total_steps, "校验")
    conn = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
    try:
        rows = []
        for t in ("entries", "senses", "word_forms", "grammar", "jlpt", "gloss_zh", "examples"):
            try:
                c = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                c = -1
            rows.append((t, c))
        for t, c in rows:
            flag = "ok " if c > 0 else "空 "
            print(f"    {flag}{t:<11} {c:>8} 行")
    finally:
        conn.close()

    print()
    print("=" * 68)
    print("准备完成。下一步：")
    print("    1)  .\\start.ps1        启动服务")
    print("    2)  浏览器打开 http://127.0.0.1:8765/")
    print()
    print("说明：")
    print("    · 词库来自 JMdict（EDRDG，CC-BY-SA 4.0），在本机生成")
    print("    · 语法 / JLPT 分级 / 中文释义 / 例句由仓库内 data/ 下的数据导入")
    print("    · AI 讲解需要本机 Ollama：ollama pull qwen2.5:7b")
    print("      （默认 7B，质量可用；首次加载较慢，可换 qwen2.5:3b 提速）")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)
