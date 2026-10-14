# -*- coding: utf-8 -*-
"""Map English JMdict POS labels to Chinese."""
from __future__ import annotations

# Longer / more specific keys first for contains-match
_POS_RULES: list[tuple[str, str]] = [
    ("Ichidan verb", "一段动词"),
    ("Godan verb", "五段动词"),
    ("transitive verb", "他动词"),
    ("intransitive verb", "自动词"),
    ("adjective (i)", "い形容词"),
    ("adjectival nouns", "な形容词"),
    ("quasi-adjectives", "な形容词"),
    ("expressions", "惯用语"),
    ("conjunction", "接续词"),
    ("interjection", "感叹词"),
    ("particle", "助词"),
    ("counter", "量词"),
    ("adverb", "副词"),
    ("noun", "名词"),
]


def map_pos(pos_en: str) -> str:
    """Map one English POS string to Chinese; keep English if unmapped."""
    s = (pos_en or "").strip()
    if not s:
        return s
    for en, zh in _POS_RULES:
        if en in s:
            return zh
    return s


def map_pos_list(pos_parts: list[str]) -> list[str]:
    return [map_pos(p) for p in pos_parts if p]
