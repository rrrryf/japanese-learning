# -*- coding: utf-8 -*-
"""JMdict lookup: search candidates and word detail."""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any

# conjugator.py lives in parent of web/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from conjugator import conjugate  # noqa: E402

from db import get_connection
from pos_map import map_pos_list
from romaji import kana_to_romaji

_tls = threading.local()

# Display order for conjugation grid (subset + rest)
_CONJ_ORDER = [
    "ます形",
    "ない形",
    "て形",
    "た形",
    "可能形",
    "ば形",
    "被动形",
    "使役形",
    "意志形",
    "命令形",
    "基本形",
]


def _db() -> sqlite3.Connection:
    """Thread-local read-only connection. A dead handle is reopened."""
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.Error:
            _tls.conn = None
            try:
                conn.close()
            except sqlite3.Error:
                pass
    conn = get_connection()
    _tls.conn = conn
    return conn


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [p for p in value.split("|") if p]


def _unique_forms(*groups: list[str]) -> list[str]:
    """Preserve order; drop empties and duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for f in group:
            f = (f or "").strip()
            if not f or f in seen:
                continue
            seen.add(f)
            out.append(f)
    return out


def _first_sense_gloss(conn: sqlite3.Connection, seq: int) -> str:
    row = conn.execute(
        "SELECT gloss FROM senses WHERE seq = ? LIMIT 1", (seq,)
    ).fetchone()
    if not row or not row["gloss"]:
        return ""
    return row["gloss"].split("|", 1)[0]


def _lookup_jlpt(conn: sqlite3.Connection, forms: list[str]) -> str | None:
    for form in forms:
        row = conn.execute(
            "SELECT level FROM jlpt WHERE word_form = ?", (form,)
        ).fetchone()
        if row and row["level"]:
            return str(row["level"])
    return None


def _norm_form(s: str) -> str:
    """Lightweight key normalize for gloss_zh matching (no meaning change)."""
    s = (s or "").strip()
    for ch in ("・", "･", " ", "　", "ー", "ｰ"):
        s = s.replace(ch, "")
    return s


def _lookup_gloss_zh(
    conn: sqlite3.Connection, forms: list[str]
) -> tuple[str | None, str | None]:
    """Exact form first, then normalized, then common stem X曜 ← X曜日."""
    tried: set[str] = set()
    candidates: list[str] = []
    for form in forms:
        form = (form or "").strip()
        if not form:
            continue
        for c in (form, _norm_form(form)):
            if c and c not in tried:
                tried.add(c)
                candidates.append(c)
        # weekday stem already backfilled; keep runtime fallback
        if form.endswith("曜") and not form.endswith("曜日"):
            c = form + "日"
            if c not in tried:
                tried.add(c)
                candidates.append(c)

    for form in candidates:
        row = conn.execute(
            "SELECT accent, gloss FROM gloss_zh WHERE word_form = ?", (form,)
        ).fetchone()
        if not row:
            continue
        accent = (row["accent"] or "").strip() or None
        gloss = (row["gloss"] or "").strip() or None
        if accent or gloss:
            return accent, gloss
    return None, None


def _gloss_first_for_search(
    conn: sqlite3.Connection,
    seq: int,
    forms: list[str],
) -> str:
    """Prefer Chinese gloss_zh for any form; else English first gloss."""
    _, zh = _lookup_gloss_zh(conn, forms)
    if zh:
        return zh
    return _first_sense_gloss(conn, seq)


def _has_cjk(s: str) -> bool:
    """True if string contains CJK Unified Ideographs (Han)."""
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _has_kana(s: str) -> bool:
    """True if string contains hiragana or katakana."""
    for ch in s:
        o = ord(ch)
        if 0x3041 <= o <= 0x309F or 0x30A1 <= o <= 0x30FF:
            return True
    return False


def _is_latin_query(s: str) -> bool:
    """ASCII letters / spaces / hyphens only (English gloss search)."""
    if not s:
        return False
    return all(
        ("a" <= c <= "z")
        or ("A" <= c <= "Z")
        or c in " -'"
        for c in s
    )


def _candidate_from_seq(
    conn: sqlite3.Connection,
    seq: int,
    preferred_form: str | None = None,
    query: str | None = None,
) -> dict[str, Any] | None:
    """Build one search candidate; prefer preferred_form / query match for word_form."""
    entry = conn.execute(
        "SELECT kanji, kana FROM entries WHERE seq = ?", (seq,)
    ).fetchone()
    if not entry:
        return None
    kanji_list = _split_pipe(entry["kanji"])
    kana_list = _split_pipe(entry["kana"])
    word_form: str | None = None
    if preferred_form:
        word_form = preferred_form.strip() or None
    if not word_form and query:
        wf_row = conn.execute(
            "SELECT word_form FROM word_forms WHERE seq = ? AND word_form = ? LIMIT 1",
            (seq, query),
        ).fetchone()
        if wf_row:
            word_form = wf_row["word_form"]
        else:
            pref = conn.execute(
                "SELECT word_form FROM word_forms WHERE seq = ? AND word_form LIKE ? || '%' "
                "ORDER BY LENGTH(word_form) ASC LIMIT 1",
                (seq, query),
            ).fetchone()
            if pref:
                word_form = pref["word_form"]
    if not word_form:
        if kanji_list:
            word_form = kanji_list[0]
        elif kana_list:
            word_form = kana_list[0]
        else:
            word_form = str(seq)
    kana = kana_list[0] if kana_list else ""
    forms = _unique_forms([word_form], kanji_list, kana_list)
    return {
        "seq": seq,
        "word_form": word_form,
        "kana": kana,
        "gloss_first": _gloss_first_for_search(conn, seq, forms),
    }


def _search_gloss_zh(
    conn: sqlite3.Connection, q: str, limit: int, seen: set[int]
) -> list[dict[str, Any]]:
    """Reverse search: Chinese gloss substring → Japanese entries."""
    if limit <= 0:
        return []
    # Fetch extra rows for dedupe / missing entries
    # Rank: exact gloss / sense-tail match / short gloss / short headword
    rows = conn.execute(
        """
        SELECT gz.word_form AS word_form, gz.gloss AS gloss, wf.seq AS seq,
               jl.level AS lv
        FROM gloss_zh gz
        JOIN word_forms wf ON wf.word_form = gz.word_form
        LEFT JOIN jlpt jl ON jl.word_form = gz.word_form
        WHERE gz.gloss LIKE '%' || ? || '%'
        ORDER BY
          CASE
            WHEN gz.gloss = ? THEN 0
            WHEN gz.gloss LIKE '%】' || ? THEN 1
            WHEN gz.gloss LIKE '%】' || ? || '，%' THEN 2
            WHEN gz.gloss LIKE '%】' || ? || '；%' THEN 2
            WHEN gz.gloss LIKE '% ' || ? THEN 3
            WHEN gz.gloss LIKE '% ' || ? || '，%' THEN 3
            WHEN gz.gloss LIKE '% ' || ? || '；%' THEN 3
            ELSE 4
          END,
          -- 常见词优先：JLPT N5..N1 依次靠前，不在词表里的排最后。
          -- 否则搜「吃」第一条会是麻将用语「吃（チー）」而不是 食べる。
          CASE COALESCE(jl.level, 'ZZ')
            WHEN 'N5' THEN 0 WHEN 'N4' THEN 1 WHEN 'N3' THEN 2
            WHEN 'N2' THEN 3 WHEN 'N1' THEN 4 ELSE 9
          END,
          LENGTH(gz.gloss) ASC,
          LENGTH(gz.word_form) ASC,
          gz.word_form ASC
        LIMIT ?
        """,
        (q, q, q, q, q, q, q, q, max(limit * 4, 40)),
    ).fetchall()
    out: list[tuple[str | None, dict[str, Any]]] = []
    for r in rows:
        seq = int(r["seq"])
        if seq in seen:
            continue
        cand = _candidate_from_seq(conn, seq, preferred_form=r["word_form"])
        if not cand:
            continue
        # Prefer the matched Chinese gloss snippet for list display
        zh = (r["gloss"] or "").strip()
        if zh:
            cand["gloss_first"] = zh
        seen.add(seq)
        lv = r["lv"] if "lv" in r.keys() else None
        out.append((lv, cand))
        if len(out) >= max(limit * 2, 20):
            break

    # 最终排序交给 Python：常见词优先（JLPT N5→N1），再按释义长度。
    # 只靠 SQL 排序不够——候选去重/回表会打乱顺序，「吃」才会把麻将用语
    # 排到 食べる 前面。
    _ORDER = {"N5": 0, "N4": 1, "N3": 2, "N2": 3, "N1": 4}
    out.sort(key=lambda item: (
        _ORDER.get(item[0], 9),
        len(str(item[1].get("gloss_first") or "")),
    ))
    return [cand for _, cand in out[:limit]]


def _search_gloss_en(
    conn: sqlite3.Connection, q: str, limit: int, seen: set[int]
) -> list[dict[str, Any]]:
    """Reverse search: English sense gloss substring → Japanese entries."""
    if limit <= 0:
        return []
    # Match whole pipe-separated gloss tokens (avoid "eat" ⊂ "treat")
    rows = conn.execute(
        """
        SELECT seq, gloss FROM senses
        WHERE gloss = ?
           OR gloss LIKE ? || '|%'
           OR gloss LIKE '%|' || ?
           OR gloss LIKE '%|' || ? || '|%'
           OR gloss = 'to ' || ?
           OR gloss LIKE 'to ' || ? || '|%'
           OR gloss LIKE '%|to ' || ?
           OR gloss LIKE '%|to ' || ? || '|%'
        LIMIT ?
        """,
        (q, q, q, q, q, q, q, q, max(limit * 4, 40)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        seq = int(r["seq"])
        if seq in seen:
            continue
        cand = _candidate_from_seq(conn, seq)
        if not cand:
            continue
        # Keep Chinese-preferred gloss_first from helper; if empty, use EN first
        if not cand.get("gloss_first"):
            gloss = (r["gloss"] or "").split("|", 1)[0].strip()
            cand["gloss_first"] = gloss
        seen.add(seq)
        out.append(cand)
        if len(out) >= limit:
            break
    return out


def search(q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Exact then prefix JP search; fill with Chinese (and Latin→EN) reverse hits."""
    q = (q or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit), 50))
    conn = _db()

    rows = conn.execute(
        "SELECT DISTINCT seq FROM word_forms WHERE word_form = ?", (q,)
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT DISTINCT seq FROM word_forms WHERE word_form LIKE ? || '%' LIMIT ?",
            (q, limit),
        ).fetchall()
    else:
        rows = rows[:limit]

    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for r in rows:
        seq = int(r["seq"])
        if seq in seen:
            continue
        cand = _candidate_from_seq(conn, seq, query=q)
        if not cand:
            continue
        seen.add(seq)
        results.append(cand)

    remaining = limit - len(results)
    # 中文反查的条件：
    #   1) 日语侧没结果 —— 可能是纯中文查询（「漂亮」）
    #   2) 查询里没有假名 —— 纯汉字/Latin 才可能是中文词
    # 「食べる」这种含假名的日语查询，一旦命中就不必再扫 2.3 万行 gloss_zh
    # （实测 食べる 208ms，跳过反查后回到 ~15ms）。
    if remaining > 0 and (not results or (_has_cjk(q) and not _has_kana(q))):
        results.extend(_search_gloss_zh(conn, q, remaining, seen))
        remaining = limit - len(results)

    # English reverse for Latin queries
    if remaining > 0 and _is_latin_query(q):
        results.extend(_search_gloss_en(conn, q, remaining, seen))

    return results


def _detect_verb_type(senses: list[dict[str, Any]]) -> str | None:
    """Map JMDict POS strings to conjugator vtype, or None if not a verb."""
    parts: list[str] = []
    for s in senses:
        parts.extend(s.get("pos") or [])
    blob = " | ".join(parts)
    # Order matters: kuru/suru before generic Ichidan/Godan
    if "Kuru verb" in blob:
        return "kuru"
    # 「勉強」「掃除」「料理」这类在 JMdict 里标的是
    # "noun or participle which takes the aux. verb suru"（约 1.7 万条），
    # 光认 "suru verb" 会让它们完全没有活用表。
    if "suru verb" in blob or "takes the aux. verb suru" in blob:
        return "suru"
    if "Ichidan verb" in blob:
        return "ichidan"
    if "Godan verb" in blob:
        return "godan"
    return None


def _ordered_conjugations(raw: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in _CONJ_ORDER:
        if key in raw and raw[key]:
            out[key] = raw[key]
    for key, val in raw.items():
        if key not in out and val:
            out[key] = val
    return out


def _fetch_examples(
    conn: sqlite3.Connection, forms: list[str], cap: int = 15
) -> list[dict[str, str]]:
    """按词形取例句。

    坑：纯子串匹配下，「日」会命中「今日」「一日」这类无关句子。
    对策：
      1. 长词形优先——多字词的命中基本可信
      2. 单字词形只作补充（最多 3 条，且只取短句），避免把结果占满
      3. 同词形内按「词形出现位置 + 句子长度」排序，越靠前越可能真是它的例句
    """
    seen: set[str] = set()
    examples: list[dict[str, str]] = []
    cleaned = {f.strip() for f in forms if f and f.strip()}
    ordered = sorted(cleaned, key=len, reverse=True)

    def take(form: str, limit: int, max_len: int | None = None) -> int:
        rows = conn.execute(
            # instr() 与 LIKE '%%x%%' 同为全扫，但省掉 LIKE 的模式解析：实测 13.7ms -> 6.3ms
            "SELECT jpn, cmn FROM examples WHERE instr(jpn, ?) > 0 LIMIT 40",
            (form,),
        ).fetchall()
        scored = []
        for row in rows:
            jpn = row["jpn"] or ""
            if not jpn or jpn in seen:
                continue
            if max_len is not None and len(jpn) > max_len:
                continue
            pos = jpn.find(form)
            scored.append((pos if pos >= 0 else 999, len(jpn), jpn, row["cmn"] or ""))
        scored.sort()
        added = 0
        for _, _, jpn, cmn in scored:
            if jpn in seen:
                continue
            seen.add(jpn)
            examples.append({"jpn": jpn, "cmn": cmn})
            added += 1
            if added >= limit or len(examples) >= cap:
                break
        return added

    # 第一轮：多字词形
    for form in ordered:
        if len(form) < 2:
            continue
        take(form, cap)
        if len(examples) >= cap:
            return examples

    # 第二轮：单字词形兜底。
    # 单字假名（ひ/に/を）没有独立语义，子串匹配必然跑偏，直接跳过；
    # 单字汉字（日/手/目）只接受「句首或标点/空格之后」的位置，
    # 这样「日曜日」还能命中，但「今日は」「一日に」会被排除。
    def at_word_start(jpn: str, form: str) -> bool:
        if jpn.startswith(form):
            return True
        return any(sep + form in jpn for sep in "、。！？ 　「『（(")

    for form in ordered:
        if len(form) >= 2 or _has_kana(form):
            continue
        rows = conn.execute(
            "SELECT jpn, cmn FROM examples WHERE instr(jpn, ?) > 0 LIMIT 200",
            (form,),
        ).fetchall()
        added = 0
        for row in rows:
            jpn = row["jpn"] or ""
            if not jpn or jpn in seen or len(jpn) > 24:
                continue
            if not at_word_start(jpn, form):
                continue
            seen.add(jpn)
            examples.append({"jpn": jpn, "cmn": row["cmn"] or ""})
            added += 1
            if added >= 2 or len(examples) >= cap:
                break
        if len(examples) >= cap:
            break
    return examples


def get_word(seq: int) -> dict[str, Any] | None:
    """Full word detail by seq, including conjugations and examples."""
    conn = _db()
    entry = conn.execute(
        "SELECT seq, kanji, kana FROM entries WHERE seq = ?", (seq,)
    ).fetchone()
    if not entry:
        return None

    kanji = _split_pipe(entry["kanji"])
    kana = _split_pipe(entry["kana"])
    primary_kana = kana[0] if kana else ""
    romaji = kana_to_romaji(primary_kana) if primary_kana else ""

    sense_rows = conn.execute(
        "SELECT pos, gloss FROM senses WHERE seq = ?", (seq,)
    ).fetchall()
    senses: list[dict[str, Any]] = []
    for s in sense_rows:
        pos_list = _split_pipe(s["pos"])
        gloss_list = _split_pipe(s["gloss"])
        senses.append(
            {
                "pos": pos_list,
                "pos_zh": map_pos_list(pos_list),
                "gloss": gloss_list,
            }
        )

    forms = [
        r["word_form"]
        for r in conn.execute(
            "SELECT DISTINCT word_form FROM word_forms WHERE seq = ? ORDER BY word_form",
            (seq,),
        )
    ]

    # Prefer primary kanji / kana, then remaining word_forms
    primary = []
    if kanji:
        primary.append(kanji[0])
    if primary_kana:
        primary.append(primary_kana)
    lookup_forms = _unique_forms(primary, kanji, kana, forms)

    level = _lookup_jlpt(conn, lookup_forms)
    accent, gloss_zh = _lookup_gloss_zh(conn, lookup_forms)

    conjugations = None
    vtype = _detect_verb_type(senses)
    if vtype and primary_kana:
        try:
            conjugations = _ordered_conjugations(conjugate(primary_kana, vtype))
        except Exception:
            conjugations = None

    # Primary kanji + kana forms for example lookup
    example_forms: list[str] = []
    if kanji:
        example_forms.append(kanji[0])
    if primary_kana:
        example_forms.append(primary_kana)
    examples = _fetch_examples(conn, example_forms, cap=15)

    return {
        "seq": int(entry["seq"]),
        "kanji": kanji,
        "kana": kana,
        "romaji": romaji,
        "level": level,
        "accent": accent,
        "gloss_zh": gloss_zh,
        "senses": senses,
        "all_forms": forms,
        "conjugations": conjugations,
        "examples": examples,
    }


def _grammar_item(r) -> dict[str, Any]:
    lvl = r["level"] if "level" in r.keys() else None
    keys = set(r.keys())
    conn = ""
    if "connection" in keys and r["connection"]:
        conn = str(r["connection"])
    examples = []
    if "examples" in keys and r["examples"]:
        try:
            parsed = json.loads(r["examples"])
            if isinstance(parsed, list):
                examples = [e for e in parsed if isinstance(e, dict) and e.get("ja")]
        except ValueError:
            examples = []
    return {
        "id": int(r["id"]),
        "pattern": (r["pattern"] or ""),
        "explain": (r["explain"] or ""),
        "explain_zh": (r["explain_zh"] if "explain_zh" in keys and r["explain_zh"] else None),
        "level": (lvl or None),
        "connection": conn or None,
        "examples": examples,
    }


def _normalize_grammar_level(level: str | None) -> str | None:
    """Accept N5–N1; unknown/未分级 → 'unknown'; empty → None (no filter)."""
    if level is None:
        return None
    s = str(level).strip()
    if not s or s.lower() in ("all", "全部"):
        return None
    u = s.upper()
    if u in ("N5", "N4", "N3", "N2", "N1"):
        return u
    if s.lower() in ("unknown", "null", "none") or s in ("未分级", "未分級"):
        return "unknown"
    return None


def search_grammar(
    q: str, limit: int = 15, level: str | None = None
) -> list[dict[str, Any]]:
    """Match grammar patterns by substring; empty q → []. Optional level filter."""
    q = (q or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit), 50))
    lvl = _normalize_grammar_level(level)
    conn = _db()
    if lvl == "unknown":
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "WHERE pattern LIKE '%' || ? || '%' AND level IS NULL LIMIT ?",
            (q, limit),
        ).fetchall()
    elif lvl:
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "WHERE pattern LIKE '%' || ? || '%' AND level = ? LIMIT ?",
            (q, lvl, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "WHERE pattern LIKE '%' || ? || '%' LIMIT ?",
            (q, limit),
        ).fetchall()
    return [_grammar_item(r) for r in rows]


def list_grammar(
    limit: int = 30, offset: int = 0, level: str | None = None
) -> dict[str, Any]:
    """Paginated grammar browse: {total, items:[{id,pattern,explain,level}]}."""
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    lvl = _normalize_grammar_level(level)
    conn = _db()
    if lvl == "unknown":
        total_row = conn.execute(
            "SELECT COUNT(*) AS n FROM grammar WHERE level IS NULL"
        ).fetchone()
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "WHERE level IS NULL ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    elif lvl:
        total_row = conn.execute(
            "SELECT COUNT(*) AS n FROM grammar WHERE level = ?", (lvl,)
        ).fetchone()
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "WHERE level = ? ORDER BY id ASC LIMIT ? OFFSET ?",
            (lvl, limit, offset),
        ).fetchall()
    else:
        total_row = conn.execute("SELECT COUNT(*) AS n FROM grammar").fetchone()
        rows = conn.execute(
            "SELECT id, pattern, explain, level, connection FROM grammar "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    total = int(total_row["n"] or 0) if total_row else 0
    return {"total": total, "items": [_grammar_item(r) for r in rows]}


def get_grammar(gid: int) -> dict[str, Any] | None:
    """Single grammar row by id, or None."""
    conn = _db()
    row = conn.execute(
        "SELECT id, pattern, explain, level, connection, examples, explain_zh "
        "FROM grammar WHERE id = ?",
        (int(gid),),
    ).fetchone()
    if row is None:
        return None
    return _grammar_item(row)


def grammar_counts() -> dict[str, int]:
    """Counts by JLPT level plus unknown (NULL)."""
    conn = _db()
    out: dict[str, int] = {"N5": 0, "N4": 0, "N3": 0, "N2": 0, "N1": 0, "unknown": 0}
    for lvl in ("N5", "N4", "N3", "N2", "N1"):
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM grammar WHERE level = ?", (lvl,)
        ).fetchone()
        out[lvl] = int(row["n"] or 0) if row else 0
    unk = conn.execute(
        "SELECT COUNT(*) AS n FROM grammar WHERE level IS NULL"
    ).fetchone()
    out["unknown"] = int(unk["n"] or 0) if unk else 0
    return out



def jlpt_counts() -> dict[str, int]:
    """Distinct entry counts per JLPT level N5..N1."""
    conn = _db()
    out: dict[str, int] = {}
    for level in ("N5", "N4", "N3", "N2", "N1"):
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT wf.seq) AS n
            FROM jlpt j
            JOIN word_forms wf ON wf.word_form = j.word_form
            WHERE j.level = ?
            """,
            (level,),
        ).fetchone()
        out[level] = int(row["n"] or 0) if row else 0
    return out


def list_jlpt(level: str, limit: int = 30) -> list[dict[str, Any]]:
    """JLPT deck cards: seq, word_form, kana, accent, gloss_first (zh preferred)."""
    level = (level or "").strip().upper()
    if level not in {"N5", "N4", "N3", "N2", "N1"}:
        return []
    limit = max(1, min(int(limit), 200))
    conn = _db()

    # 先随机挑 seq（只扫 jlpt+word_forms），再回表取字段。
    # 直接在 JOIN 后 ORDER BY RANDOM() 会先把 entries 全连一遍再随机，白做很多工作。
    rows = conn.execute(
        """
        WITH picked AS (
          SELECT DISTINCT wf.seq AS seq
          FROM jlpt j
          JOIN word_forms wf ON wf.word_form = j.word_form
          WHERE j.level = ?
          ORDER BY RANDOM()
          LIMIT ?
        )
        SELECT p.seq AS seq,
               e.kanji AS kanji,
               e.kana AS kana,
               (SELECT j2.word_form FROM jlpt j2
                 JOIN word_forms w2 ON w2.word_form = j2.word_form
                WHERE w2.seq = p.seq AND j2.level = ? LIMIT 1) AS word_form
        FROM picked p
        JOIN entries e ON e.seq = p.seq
        """,
        (level, limit, level),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for r in rows:
        seq = int(r["seq"])
        word_form = (r["word_form"] or "").strip()
        entry = {"kanji": r["kanji"], "kana": r["kana"]}
        if entry["kanji"] is None and entry["kana"] is None:
            continue
        kanji_list = _split_pipe(entry["kanji"])
        kana_list = _split_pipe(entry["kana"])
        if not word_form:
            word_form = kanji_list[0] if kanji_list else (kana_list[0] if kana_list else str(seq))
        kana = kana_list[0] if kana_list else ""
        extra_forms = [
            row["word_form"]
            for row in conn.execute(
                "SELECT DISTINCT word_form FROM word_forms WHERE seq = ?", (seq,)
            )
        ]
        forms = _unique_forms([word_form], kanji_list, kana_list, extra_forms)
        accent, gloss_zh = _lookup_gloss_zh(conn, forms)
        gloss_en = _first_sense_gloss(conn, seq)
        gloss_first = (gloss_zh or "").strip() or gloss_en
        results.append(
            {
                "seq": seq,
                "word_form": word_form,
                "kana": kana,
                "accent": accent,
                "gloss_zh": gloss_zh,
                "gloss_en": gloss_en or None,
                "gloss_first": gloss_first,
            }
        )
    return results
