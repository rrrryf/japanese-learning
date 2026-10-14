# -*- coding: utf-8 -*-
"""Kana (hiragana/katakana) to Hepburn romaji."""
from __future__ import annotations

# Katakana -> hiragana offset
_KATA_START, _HIRA_START = 0x30A1, 0x3041
_KATA_END = 0x30F6


def _to_hiragana(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if _KATA_START <= code <= _KATA_END:
            out.append(chr(code - _KATA_START + _HIRA_START))
        else:
            out.append(ch)
    return "".join(out)


# Base mora map (hiragana)
_BASIC: dict[str, str] = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "wi", "ゑ": "we", "を": "wo", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo", "ゎ": "wa",
    "ゔ": "vu",
    "ー": "",  # handled with previous vowel lengthening
}

# Digraphs (youon) — longest match first
_DIGRAPHS: dict[str, str] = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "ぢゃ": "ja", "ぢゅ": "ju", "ぢょ": "jo",
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du",
    "うぃ": "wi", "うぇ": "we", "うぉ": "wo",
    "ヴぁ": "va", "ヴぃ": "vi", "ヴぇ": "ve", "ヴぉ": "vo",
}

_VOWELS = set("aeiou")


def _double_consonant_for_sokuon(next_romaji: str) -> str:
    """Return consonant to double before next mora (っ)."""
    if not next_romaji:
        return ""
    if next_romaji.startswith("ch"):
        return "t"
    ch = next_romaji[0]
    if ch in _VOWELS or ch == "n":
        return ""
    return ch


def _apply_long_vowels(romaji: str) -> str:
    """Basic Hepburn long vowels: ou/oo -> o with macron when common patterns."""
    # Keep simple: ou at end of mora often from おう — use ou (modified Hepburn common in dicts)
    # Also handle ー already consumed; double vowels aa/ii/uu/ee/oo -> with macron optionally
    replacements = [
        ("aa", "ā"), ("ii", "ī"), ("uu", "ū"), ("ee", "ē"), ("oo", "ō"),
        ("ou", "ō"),
    ]
    out = romaji
    for a, b in replacements:
        out = out.replace(a, b)
    return out


def kana_to_romaji(kana: str, long_vowel: bool = True) -> str:
    """Convert kana string to Hepburn romaji."""
    if not kana:
        return ""
    text = _to_hiragana(kana.strip())
    # Take first reading if pipe-separated
    if "|" in text:
        text = text.split("|", 1)[0]

    i = 0
    parts: list[str] = []
    n = len(text)
    while i < n:
        ch = text[i]
        # sokuon
        if ch == "っ":
            # peek next mora
            j = i + 1
            nxt = ""
            if j + 1 < n and text[j : j + 2] in _DIGRAPHS:
                nxt = _DIGRAPHS[text[j : j + 2]]
            elif j < n and text[j] in _BASIC:
                nxt = _BASIC[text[j]]
            dbl = _double_consonant_for_sokuon(nxt)
            if dbl:
                parts.append(dbl)
            i += 1
            continue
        # digraph
        if i + 1 < n and text[i : i + 2] in _DIGRAPHS:
            parts.append(_DIGRAPHS[text[i : i + 2]])
            i += 2
            continue
        # chōonpu ー
        if ch == "ー":
            if parts:
                last = parts[-1]
                for v in ("a", "i", "u", "e", "o"):
                    if last.endswith(v):
                        parts[-1] = last[:-1] + {"a": "ā", "i": "ī", "u": "ū", "e": "ē", "o": "ō"}[v]
                        break
            i += 1
            continue
        # n' before vowel / y
        if ch == "ん":
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt and (nxt in "あいうえおやゆよぁぃぅぇぉ" or nxt in "ァィゥェォ"):
                parts.append("n'")
            else:
                parts.append("n")
            i += 1
            continue
        if ch in _BASIC:
            parts.append(_BASIC[ch])
            i += 1
            continue
        # pass through punctuation / spaces / latin
        if ch.isspace() or ch in "・、-〜~":
            parts.append(" " if ch.isspace() else "")
            i += 1
            continue
        parts.append(ch)
        i += 1

    romaji = "".join(parts)
    if long_vowel:
        romaji = _apply_long_vowels(romaji)
    return romaji
