# -*- coding: utf-8 -*-
"""从完整词库导出可分发的小体积数据（JLPT 分级 / 中文释义 / 例句）。

公开仓库只带这三份导出的数据（压缩后合计约 1.4 MB），
完整词库（jmdict.db，约 80 MB）仍由 `setup_data.py` 在本机生成。

用法（在项目根目录）：
    python scripts/export_data.py --db jmdict.db

导出的文件：
    data/jlpt_words.jsonl.gz     word_form / level
    data/gloss_zh.jsonl.gz       word_form / accent / gloss
    data/examples.jsonl.gz       jpn / cmn

隐私处理：导出时会丢弃正文里出现邮箱地址的例句（语料里偶有真实邮箱）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 语料里偶见真实邮箱（来源例句本身如此），分发前一律剔除
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def dump(rows, path: Path, keep=None) -> tuple[int, int]:
    """写 gzip JSONL，返回 (保留行数, 丢弃行数)。"""
    kept = dropped = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as f:
        for obj in rows:
            if keep is not None and not keep(obj):
                dropped += 1
                continue
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            kept += 1
    size = path.stat().st_size
    print(f"  {path.name:<26} {kept:>6} 行  {size/1024:>7.0f} KB"
          + (f"   （丢弃 {dropped} 行）" if dropped else ""))
    return kept, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "jmdict.db"), help="完整词库路径")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"[x] 找不到词库：{db}")
        print("    先运行 python setup_data.py 生成，或用 --db 指定已有词库。")
        return 1

    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    print(f"[i] 源词库：{db}  ({db.stat().st_size/1048576:.1f} MB)")
    print("[i] 导出：")

    # 1. JLPT 分级
    rows = [{"word_form": r["word_form"], "level": r["level"]}
            for r in conn.execute("SELECT word_form, level FROM jlpt ORDER BY word_form")]
    dump(rows, DATA / "jlpt_words.jsonl.gz")

    # 2. 中文释义 + 音调
    rows = [{"word_form": r["word_form"], "accent": r["accent"] or "", "gloss": r["gloss"]}
            for r in conn.execute("SELECT word_form, accent, gloss FROM gloss_zh ORDER BY word_form")]
    dump(rows, DATA / "gloss_zh.jsonl.gz")

    # 3. 双语例句（剔除含邮箱的）
    rows = ({"jpn": r["jpn"], "cmn": r["cmn"] or ""}
            for r in conn.execute("SELECT jpn, cmn FROM examples ORDER BY id"))
    dump(rows, DATA / "examples.jsonl.gz",
         keep=lambda o: not EMAIL_RE.search(o["jpn"]) and not EMAIL_RE.search(o["cmn"]))

    conn.close()
    print()
    print("[+] 完成。这些文件可以随仓库分发；setup_data.py 会自动把它们导入 jmdict.db。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
