# -*- coding: utf-8 -*-
"""给缺例句的语法条补例句（本机 Ollama 生成）。

只补没有 examples 的条目；已有例句的一律不动。
生成的例句存成 {ja, zh}，前端优先显示中文，没有则显示 en。

用法：
    python scripts/fill_grammar_examples.py --db jmdict.db --level N5,N4 --dry-run --limit 5
    python scripts/fill_grammar_examples.py --db jmdict.db --level N5,N4
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "grammar_examples_extra.jsonl.gz"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SYSTEM = """你是日语教材编辑。给下面每个语法点造 1 个例句。

规则：
1. 句子自然、贴近日常，长度 10~24 个假名
2. 必须正确使用该语法点的接续
3. 每行输出三个字段，用 TAB 分隔：语法点<TAB>日语例句<TAB>中文翻译
4. 不要编号、不要加解释、不要输出别的任何内容
5. 保持输入顺序
"""


def ollama(base: str, model: str, prompt: str, timeout: int = 240) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 1200},
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (json.loads(r.read().decode("utf-8")).get("response") or "").strip()


def missing(conn: sqlite3.Connection, levels: list[str], limit: int) -> list[dict]:
    q = ("SELECT id, pattern, connection, explain, level FROM grammar "
         "WHERE (examples IS NULL OR examples = '')")
    params: list = []
    if levels:
        q += " AND level IN (" + ",".join("?" * len(levels)) + ")"
        params += levels
    q += " ORDER BY CASE level WHEN 'N5' THEN 0 WHEN 'N4' THEN 1 WHEN 'N3' THEN 2 "
    q += "WHEN 'N2' THEN 3 WHEN 'N1' THEN 4 ELSE 9 END, id"
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    return [dict(r) for r in conn.execute(q, params)]


def generate(batch: list[dict], base: str, model: str) -> dict[int, dict]:
    lines = []
    for b in batch:
        pattern = (b["pattern"] or "").strip()
        conn = (b["connection"] or "").strip()[:40] or "—"
        mean = (b["explain"] or "").strip()[:60] or "—"
        lines.append(f"{pattern}\t{conn}\t{mean}")
    prompt = SYSTEM + "\n" + "\n".join(lines)
    text = ollama(base, model, prompt)

    # 模型不老实：有时用 TAB，有时用 2+ 个空格当分隔符，
    # 还会把 pattern 改写（「あります/います」→「あります」）。
    # 所以先按顺序对齐（提示词里要求了保持顺序），pattern 匹配只作兜底。
    rows: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", raw)]
        parts = [p for p in parts if p]
        if len(parts) < 3:
            continue
        rows.append((parts[0], parts[1], parts[2]))

    def usable(ja: str, zh: str) -> bool:
        if not ja or not zh:
            return False
        if not any(0x3040 <= ord(ch) <= 0x30FF for ch in ja):
            return False          # 例句里必须有假名
        if not any("\u4e00" <= ch <= "\u9fff" for ch in zh):
            return False          # 译文里必须有汉字
        return True

    out: dict[int, dict] = {}
    if len(rows) == len(batch):
        for item, (key, ja, zh) in zip(batch, rows):
            if usable(ja, zh):
                out[item["id"]] = {"ja": ja, "zh": zh}
        return out

    # 行数对不上时退回 pattern 匹配（先精确，再归一化）
    def norm(s: str) -> str:
        s = str(s or "")
        s = re.sub(r"[（(][A-Za-z][^）)]*[）)]", "", s)
        s = s.replace("～", "").replace("〜", "").replace("~", "")
        s = re.sub(r"[（）()\s　]", "", s)
        return s.strip("・/／").lower()

    by_exact = {(b["pattern"] or "").strip(): b["id"] for b in batch}
    by_norm = {norm(b["pattern"]): b["id"] for b in batch}
    for key, ja, zh in rows:
        gid = by_exact.get(key) or by_norm.get(norm(key))
        if gid and usable(ja, zh):
            out[gid] = {"ja": ja, "zh": zh}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "jmdict.db"))
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--base", default="http://127.0.0.1:11434")
    ap.add_argument("--level", default="N5,N4", help="逗号分隔，留空表示全部")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"[x] 找不到词库：{db}")
        return 1
    levels = [x.strip().upper() for x in args.level.split(",") if x.strip()]

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    targets = missing(conn, levels, args.limit)
    print(f"[i] 待补例句：{len(targets)} 条（等级 {levels or '全部'}）")
    if not targets:
        print("[=] 没有缺口")
        return 0

    got: dict[int, dict] = {}
    t0 = time.time()
    for i in range(0, len(targets), args.batch):
        batch = targets[i: i + args.batch]
        try:
            got.update(generate(batch, args.base, args.model))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            print(f"  ! 第 {i//args.batch+1} 批失败：{e}")
        done = min(i + args.batch, len(targets))
        elapsed = time.time() - t0
        eta = elapsed / done * (len(targets) - done) if done else 0
        print(f"  [{done}/{len(targets)}] 累计 {len(got)}  已用 {elapsed:.0f}s  "
              f"预计还要 {eta:.0f}s", flush=True)

    print(f"\n[i] 生成 {len(got)} / {len(targets)} 条")

    if args.dry_run:
        print("\n--- 抽样 ---")
        shown = 0
        for t in targets:
            g = got.get(t["id"])
            if not g:
                continue
            print(f"  {t['pattern']}")
            print(f"    接续 {t['connection']}")
            print(f"    {g['ja']}")
            print(f"    {g['zh']}")
            shown += 1
            if shown >= 8:
                break
        conn.close()
        return 0

    if not got:
        print("[x] 一条都没生成")
        conn.close()
        return 1

    n = 0
    for gid, ex in got.items():
        conn.execute("UPDATE grammar SET examples = ? WHERE id = ?",
                     (json.dumps([ex], ensure_ascii=False), gid))
        n += 1
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM grammar").fetchone()[0]
    with_ex = conn.execute(
        "SELECT COUNT(*) FROM grammar WHERE examples IS NOT NULL AND examples != ''").fetchone()[0]
    conn.close()
    print(f"[+] 写入 {n} 条；现在 {with_ex}/{total} 条有例句 "
          f"（{with_ex*100/total:.0f}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
