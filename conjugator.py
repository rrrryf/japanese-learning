# -*- coding: utf-8 -*-
"""日语动词活用生成（纯假名，基于读音）。

用法：
    from conjugator import conjugate
    conjugate('たべる')            # 自动判断（一段）
    conjugate('かく', 'godan')     # 显式指定类型

vtype 取值：'ichidan' 一段 / 'godan' 五段 / 'suru' サ変 / 'kuru' カ変 / 'auto' 自动判断

注意：自动判断有歧义（如 帰る/切る 是五段），做网站时优先用 JMDict 的
senses.pos（含 "Ichidan verb" / "Godan verb" 等）判断类型，本函数仅兜底。
"""

# 五十音行（用于「段」转换）
ROWS = [
    "あいうえお", "かきくけこ", "さしすせそ", "たちつてと",
    "なにぬねの", "はひふへほ", "まみむめも", "やいゆえよ",
    "らりるれろ", "わいうえを", "がぎぐげご", "ざじずぜぞ",
    "だぢづでど", "ばびぶべぼ", "ぱぴぷぺぽ",
]

# 五段动词 て形/た形 音便（词尾假名 -> 音便）
TE_ONBIN = {
    "く": "いて", "ぐ": "いで", "す": "して",
    "つ": "って", "る": "って", "う": "って",
    "ぬ": "んで", "ぶ": "んで", "む": "んで",
}
TA_ONBIN = {
    "く": "いた", "ぐ": "いだ", "す": "した",
    "つ": "った", "る": "った", "う": "った",
    "ぬ": "んだ", "ぶ": "んだ", "む": "んだ",
}

# 常被误判为一段的五段「る」动词
GODAN_RU_EXCEPTIONS = {
    "かえる", "きる", "はしる", "はいる", "しる", "いる", "へる",
    "すべる", "かぎる", "ける", "あせる", "しめる", "しげる",
    "にぎる", "まいる", "ちる", "おる", "こる", "とる",
}


def _row(k):
    for r in ROWS:
        if k in r:
            return r
    return None


def _dan(k, i):
    r = _row(k)
    return r[i] if r else k


def _a(k):   # 未然形（あ段）；う 的あ段是 わ
    return "わ" if k == "う" else _dan(k, 0)


def _i(k):
    return _dan(k, 1)


def _e(k):
    return _dan(k, 3)


def _o(k):
    return _dan(k, 4)


def guess(kana):
    # サ変：する / 愛する / 勉強する —— 只要以「する」结尾都算，
    # 「かす」「あせる」这类五段词不会以「する」结尾，不会误判。
    if kana.endswith("する"):
        return "suru"
    if kana == "くる":
        return "kuru"
    if not kana.endswith("る"):
        return "godan"
    if kana in GODAN_RU_EXCEPTIONS:
        return "godan"
    prev = kana[-2] if len(kana) >= 2 else ""
    if prev in "いきしちにひみりぎじぢびぴ":   # い段（含浊音/半浊音）
        return "ichidan"
    if prev in "えけせてねへめれげぜでべぺ":   # え段（含浊音/半浊音）
        return "ichidan"
    return "godan"


def conjugate(kana, vtype="auto"):
    if vtype == "auto":
        vtype = guess(kana)

    if vtype == "suru":
        # サ変要保留词干：愛する → 愛します（不是「します」）。
        # 传进来的可能已经是「あいする」，也可能只有词干「あい」，两种都兼容。
        stem = kana[:-2] if kana.endswith("する") else kana
        tail = f"{stem}する" if stem else "する"
        return {
            "基本形": tail, "ます形": stem + "します", "ない形": stem + "しない",
            "て形": stem + "して", "た形": stem + "した",
            "可能形": stem + "できる",
            "被动形": stem + "される", "使役形": stem + "させる",
            "意志形": stem + "しよう", "命令形": stem + "しろ",
            "ば形": stem + "すれば",
        }
    if vtype == "kuru":
        return {
            "基本形": "くる", "ます形": "きます", "ない形": "こない",
            "て形": "きて", "た形": "きた", "可能形": "こられる",
            "被动形": "こられる", "使役形": "こさせる", "意志形": "こよう",
            "命令形": "こい", "ば形": "くれば",
        }

    stem = kana[:-1]
    end = kana[-1]

    if vtype == "ichidan":
        return {
            "基本形": kana, "ます形": stem + "ます", "ない形": stem + "ない",
            "て形": stem + "て", "た形": stem + "た", "可能形": stem + "られる",
            "被动形": stem + "られる", "使役形": stem + "させる",
            "意志形": stem + "よう", "命令形": stem + "ろ", "ば形": stem + "れば",
        }

    # godan
    te = TE_ONBIN.get(end)
    ta = TA_ONBIN.get(end)
    if kana == "いく":   # 行く 的特殊促音便（く→って/った）
        te, ta = "って", "った"
    return {
        "基本形": kana, "ます形": stem + _i(end) + "ます",
        "ない形": stem + _a(end) + "ない", "て形": stem + te,
        "た形": stem + ta, "可能形": stem + _e(end) + "る",
        "被动形": stem + _a(end) + "れる", "使役形": stem + _a(end) + "せる",
        "意志形": stem + _o(end) + "う", "命令形": stem + _e(end),
        "ば形": stem + _e(end) + "ば",
    }


if __name__ == "__main__":
    tests = [
        ("たべる", "ichidan"), ("かく", "godan"), ("かう", "godan"),
        ("およぐ", "godan"), ("はなす", "godan"), ("まつ", "godan"),
        ("しぬ", "godan"), ("よむ", "godan"), ("あそぶ", "godan"),
        ("いく", "godan"), ("する", "suru"), ("くる", "kuru"),
    ]
    for kana, t in tests:
        forms = conjugate(kana, t)
        keys = ["ます形", "ない形", "て形", "た形", "可能形", "ば形"]
        print(f"{kana}({t}): " + " / ".join(f"{k}→{forms[k]}" for k in keys))
