# -*- coding: utf-8 -*-
"""JMdict lookup: search candidates and word detail."""
from __future__ import annotations

import sys
import sqlite3
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

_conn: sqlite3.Connection | None = None

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
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn


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


def _lookup_gloss_zh(
    conn: sqlite3.Connection, forms: list[str]
) -> tuple[str | None, str | None]:
    for form in forms:
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
        SELECT gz.word_form AS word_form, gz.gloss AS gloss, wf.seq AS seq
        FROM gloss_zh gz
        JOIN word_forms wf ON wf.word_form = gz.word_form
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
          LENGTH(gz.gloss) ASC,
          LENGTH(gz.word_form) ASC,
          gz.word_form ASC
        LIMIT ?
        """,
        (q, q, q, q, q, q, q, q, max(limit * 4, 40)),
    ).fetchall()
    out: list[dict[str, Any]] = []
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
        out.append(cand)
        if len(out) >= limit:
            break
    return out


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
    # Chinese reverse: Han in query, or JP found nothing (pure Chinese gloss query)
    if remaining > 0 and (_has_cjk(q) or not results):
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
    if "suru verb" in blob:
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
    """Query examples by each form substring; merge and dedupe."""
    seen: set[str] = set()
    examples: list[dict[str, str]] = []
    for form in forms:
        form = (form or "").strip()
        if not form:
            continue
        rows = conn.execute(
            "SELECT jpn, cmn FROM examples WHERE jpn LIKE '%' || ? || '%' LIMIT 20",
            (form,),
        ).fetchall()
        for row in rows:
            jpn = row["jpn"] or ""
            if not jpn or jpn in seen:
                continue
            seen.add(jpn)
            examples.append({"jpn": jpn, "cmn": row["cmn"] or ""})
            if len(examples) >= cap:
                return examples
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
    return {
        "id": int(r["id"]),
        "pattern": (r["pattern"] or ""),
        "explain": (r["explain"] or ""),
        "level": (lvl or None),
        "connection": conn or None,
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
        "SELECT id, pattern, explain, level, connection FROM grammar WHERE id = ?",
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

    # One row per seq; prefer the jlpt word_form that matched
    rows = conn.execute(
        """
        SELECT wf.seq AS seq, MIN(j.word_form) AS word_form
        FROM jlpt j
        JOIN word_forms wf ON wf.word_form = j.word_form
        WHERE j.level = ?
        GROUP BY wf.seq
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (level, limit),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for r in rows:
        seq = int(r["seq"])
        word_form = (r["word_form"] or "").strip()
        entry = conn.execute(
            "SELECT kanji, kana FROM entries WHERE seq = ?", (seq,)
        ).fetchone()
        if not entry:
            continue
        kanji_list = _split_pipe(entry["kanji"])
        kana_list = _split_pipe(entry["kana"])
        if not word_form:
            word_form = kanji_list[0] if kanji_list else (kana_list[0] if kana_list else str(seq))
        kana = kana_list[0] if kana_list else ""
        forms = _unique_forms([word_form], kanji_list, kana_list)
        accent, _zh = _lookup_gloss_zh(conn, forms)
        results.append(
            {
                "seq": seq,
                "word_form": word_form,
                "kana": kana,
                "accent": accent,
                "gloss_first": _gloss_first_for_search(conn, seq, forms),
            }
        )
    return results
