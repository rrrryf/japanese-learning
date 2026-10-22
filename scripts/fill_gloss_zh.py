# -*- coding: utf-8 -*-
"""给 JLPT 词表里缺中文释义的词补上释义（用本机 Ollama 翻译英文释义）。

只补 JLPT 分级词表里的缺口——那才是备考高频词。补出来的内容单独存成
data/gloss_zh_extra.jsonl.gz，与上游 thesaurus 数据分开，来源清晰。

用法：
    python scripts/fill_gloss_zh.py --db jmdict.db --dry-run --limit 10   # 只看结果不写库
    python scripts/fill_gloss_zh.py --db jmdict.db                        # 全量补
    python scripts/fill_gloss_zh.py --db jmdict.db --model qwen2.5:7b --batch 12
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "gloss_zh_extra.jsonl.gz"

SYSTEM = """你是日语词典编辑。把下面每个日语词的英文释义翻译成简洁的中文释义。

规则：
1. 每行输出一个词，格式固定：词形<TAB>中文释义
2. 中文释义不超过 15 个汉字，只翻译词义本身
3. 不要加词性标注（如【名】）、不要加例句、不要解释、不要编号
4. 保持输入顺序
5. 只输出这些行，不要任何前言后语
"""

LINE_RE = re.compile(r"^([^\t]{1,40})\t(.{1,40})$")


def ollama(base: str, model: str, prompt: str, timeout: int = 180) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 800},
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("response") or "").strip()


def missing_words(conn: sqlite3.Connection) -> list[dict]:
    """JLPT 词表里没有中文释义的词，附带英文释义。"""
    rows = conn.execute(
        """
        SELECT j.word_form AS form, j.level AS level,
               (SELECT gloss FROM senses s
                 JOIN word_forms w ON w.seq = s.seq
                WHERE w.word_form = j.word_form LIMIT 1) AS gloss
          FROM jlpt j
          LEFT JOIN gloss_zh g ON g.word_form = j.word_form
         WHERE g.word_form IS NULL
         ORDER BY j.level DESC, j.word_form
        """
    ).fetchall()
    out = []
    for r in rows:
        if not r["gloss"]:
            continue
        # 英文释义只取前两条，太长会拖慢翻译且没意义
        english = "|".join(r["gloss"].split("|")[:2])
        out.append({"form": r["form"], "level": r["level"], "gloss": english})
    return out


def translate(batch: list[dict], base: str, model: str) -> dict[str, str]:
    lines = "\n".join(f"{w['form']}\t{w['gloss']}" for w in batch)
    text = ollama(base, model, SYSTEM + "\n" + lines)
    got: dict[str, str] = {}
    wanted = {w["form"] for w in batch}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = LINE_RE.match(raw)
        if not m:
            continue
        form, zh = m.group(1).strip(), m.group(2).strip()
        if form in wanted and zh and not zh.isascii():
            got[form] = zh
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "jmdict.db"))
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--base", default="http://127.0.0.1:11434")
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个词（试跑用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印结果，不写库")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"[x] 找不到词库：{db}")
        return 1

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    targets = missing_words(conn)
    if args.limit:
        targets = targets[: args.limit]
    print(f"[i] 待补词数：{len(targets)}（JLPT 词表缺口）")
    if not targets:
        print("[=] 没有缺口了")
        return 0

    print(f"[i] 模型 {args.model}，每批 {args.batch} 条，预计 {len(targets)/args.batch:.0f} 次请求")
    results: dict[str, str] = {}
    t0 = time.time()

    for i in range(0, len(targets), args.batch):
        batch = targets[i: i + args.batch]
        try:
            got = translate(batch, args.base, args.model)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            print(f"  ! 第 {i//args.batch + 1} 批失败：{e}")
            continue
        results.update(got)
        done = min(i + args.batch, len(targets))
        elapsed = time.time() - t0
        eta = elapsed / done * (len(targets) - done) if done else 0
        print(f"  [{done}/{len(targets)}] 本批拿到 {len(got)}/{len(batch)}"
              f"  累计 {len(results)}  已用 {elapsed:.0f}s  预计还要 {eta:.0f}s", flush=True)

    print()
    print(f"[i] 共补出 {len(results)} 条（覆盖率提升 {len(results)}/{len(targets)}）")

    if args.dry_run:
        print("\n--- 抽样 15 条 ---")
        for w in targets[:15]:
            zh = results.get(w["form"])
            print(f"  {w['form']:<10} {w['gloss'][:30]:<32} → {zh or '（未拿到）'}")
        print("\n[dry-run] 未写入词库")
        conn.close()
        return 0

    if not results:
        print("[x] 一条都没拿到，未写库")
        conn.close()
        return 1

    # 写库
    for form, zh in results.items():
        conn.execute(
            "INSERT OR REPLACE INTO gloss_zh (word_form, accent, gloss) VALUES (?,?,?)",
            (form, "", zh),
        )
    conn.commit()

    # 单独导出，与上游数据分开
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if OUT_FILE.is_file():
        with gzip.open(OUT_FILE, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                    existing[o["word_form"]] = o["gloss"]
                except (ValueError, KeyError):
                    pass
    existing.update(results)
    with gzip.open(OUT_FILE, "wt", encoding="utf-8", newline="\n") as f:
        for form in sorted(existing):
            f.write(json.dumps({"word_form": form, "accent": "", "gloss": existing[form]},
                               ensure_ascii=False) + "\n")

    total_zh = conn.execute("SELECT COUNT(*) FROM gloss_zh").fetchone()[0]
    conn.close()
    print(f"[+] 已写入 {len(results)} 条到 gloss_zh（现共 {total_zh} 条）")
    print(f"[+] 另存 {OUT_FILE.name}（{OUT_FILE.stat().st_size/1024:.0f} KB，共 {len(existing)} 条）")
    print("    这个文件可以随仓库分发，setup_data.py 会自动导入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
