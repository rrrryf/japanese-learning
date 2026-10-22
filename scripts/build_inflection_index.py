# -*- coding: utf-8 -*-
"""建活用形索引：让「食べた」也能查到「食べる」。

思路：不引入分词库，而是把已有 conjugator.py 的正向活用结果反过来建索引。
  食べる --conjugate--> {た形: たべた, ます形: たべます, ...}
  再用「假名 → 汉字」的后缀替换还原成 食べた / 食べます

产出一张表：
  inflected(form, seq, base, kind)
    form  实际可能被输入的形态（食べた / たべた 都存）
    seq   指向 entries
    base  辞书形，用于提示「食べた 是 食べる 的过去式」
    kind  活用名称（た形 / ます形 …）

用法:
    python scripts/build_inflection_index.py --db jmdict.db
    python scripts/build_inflection_index.py --db jmdict.db --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from conjugator import conjugate, guess  # noqa: E402

DDL = """
CREATE TABLE IF NOT EXISTS inflected (
  form TEXT NOT NULL,
  seq  INTEGER NOT NULL,
  base TEXT NOT NULL,
  kind TEXT
)
"""

# 只收「看起来像活用形」的项，跳过基本形自己
SKIP_KINDS = {"基本形"}

# POS → vtype（与 lookup._detect_verb_type 保持一致）
def vtype_from_pos(pos_blob: str) -> str | None:
    if "Kuru verb" in pos_blob:
        return "kuru"
    if "suru verb" in pos_blob or "takes the aux. verb suru" in pos_blob:
        return "suru"
    if "Ichidan verb" in pos_blob:
        return "ichidan"
    if "Godan verb" in pos_blob:
        return "godan"
    return None


def apply_kana_to_kanji(kanji: str, kana_base: str, kana_form: str) -> str | None:
    """把假名活用形映射回汉字写法。

    食べる / たべる / たべた  →  食べた
    勉強   / べんきょう / べんきょうします → 勉強します
    """
    i = 0
    limit = min(len(kana_base), len(kana_form))
    while i < limit and kana_base[i] == kana_form[i]:
        i += 1
    old, new = kana_base[i:], kana_form[i:]
    if old and not kanji.endswith(old):
        return None
    return (kanji[: -len(old)] if old else kanji) + new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "jmdict.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"[x] 找不到词库：{db}")
        return 1

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute(DDL)

    # 取「有假名、有动词/形容词词性」的词条
    rows = conn.execute(
        """
        SELECT e.seq AS seq, e.kanji AS kanji, e.kana AS kana,
               GROUP_CONCAT(s.pos, ' | ') AS pos
          FROM entries e
          JOIN senses s ON s.seq = e.seq
         WHERE e.kana IS NOT NULL AND e.kana != ''
           AND (s.pos LIKE '%verb%' OR s.pos LIKE '%adjective%')
         GROUP BY e.seq
        """
    ).fetchall()
    print(f"[i] 候选词条 {len(rows)}")

    t0 = time.time()
    batch: list[tuple] = []
    n_forms = n_words = 0
    n_skip = 0
    conn.execute("DELETE FROM inflected")

    for r in rows:
        kana_all = (r["kana"] or "").split("|")
        kanji_all = (r["kanji"] or "").split("|") if r["kanji"] else []
        kana = kana_all[0].strip()
        if not kana:
            continue
        vtype = vtype_from_pos(r["pos"] or "")
        if not vtype:
            if "adjective (keiyoushi)" in (r["pos"] or ""):
                continue      # イ形容词活用暂不覆盖（避免造错形）
            continue

        # suru 类名词要补「する」再活用（勉強 → べんきょうする）
        stem = kana[:-2] if kana.endswith("する") else kana
        # 词干为空或过短时 skip（会让 conjugate 取 kana[-1] 越界）
        if not stem or (vtype in ("ichidan", "godan") and len(stem) < 2):
            continue
        try:
            table = conjugate(stem, vtype)
        except (TypeError, IndexError, KeyError):
            # POS 标成五段但不是标准五段词尾（TE_ONBIN 里没有），跳过而不是中断
            n_skip += 1
            continue

        base_display = (kanji_all[0].strip() if kanji_all else kana)
        got = 0
        for kind, form in table.items():
            if kind in SKIP_KINDS or not form:
                continue
            batch.append((form, int(r["seq"]), base_display, kind))
            got += 1
            # 汉字写法（食べた / 勉強します / 来た）
            for kj in kanji_all[:2]:
                kj = kj.strip()
                if not kj:
                    continue
                if vtype == "kuru" and kj.startswith("来"):
                    # カ変：くる→きます/きた/こない，汉字恒为「来」，去掉首个假名即可
                    mapped = "来" + form[1:] if len(form) > 1 else None
                else:
                    mapped = apply_kana_to_kanji(kj, kana, form)
                if mapped and mapped != form:
                    batch.append((mapped, int(r["seq"]), base_display, kind))
                    got += 1
        if got:
            n_words += 1
        if len(batch) >= 5000:
            conn.executemany(
                "INSERT INTO inflected (form, seq, base, kind) VALUES (?,?,?,?)", batch)
            n_forms += len(batch)
            batch.clear()

    if batch:
        conn.executemany(
            "INSERT INTO inflected (form, seq, base, kind) VALUES (?,?,?,?)", batch)
        n_forms += len(batch)

    conn.commit()
    elapsed = time.time() - t0

    if args.dry_run:
        conn.rollback()
        print(f"[dry-run] 会生成 {n_forms} 条（{n_words} 个词），未写库")
    else:
        print(f"[+] 写入 {n_forms} 条（来自 {n_words} 个词），{elapsed:.1f}s")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inflected_form ON inflected(form)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inflected_seq ON inflected(seq)")
        conn.commit()
        # 去重（同一 form 可能被多个词生成）
        dup = conn.execute(
            "SELECT COUNT(*) FROM (SELECT form, seq FROM inflected "
            "GROUP BY form, seq HAVING COUNT(*) > 1)").fetchone()[0]
        print(f"[i] (form,seq) 重复组 {dup} 个（不影响查询）")

    total = conn.execute("SELECT COUNT(*) FROM inflected").fetchone()[0]
    size = db.stat().st_size / 1048576
    print(f"[i] inflected 表 {total} 行，库 {size:.1f} MB")

    print()
    print("抽样：")
    for f in ("食べた", "たべた", "食べます", "勉強します", "べんきょうした", "愛します", "来た"):
        hit = conn.execute(
            "SELECT form, base, kind FROM inflected WHERE form = ? LIMIT 1", (f,)).fetchone()
        if hit:
            print(f"  {hit['form']:<12} → {hit['base']:<8} ({hit['kind']})")
        else:
            print(f"  {f:<12} → （未收录）")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
