# -*- coding: utf-8 -*-
"""纯函数单元测试：不需要启动服务，也不需要完整词典。

覆盖评审提到的几类 bug：
  - conjugator：サ变词干、guess 判断（P0-3）
  - mock_exam._normalize：选项/答案校验（P1-4 数据质量）
  - weakness.analyze_sessions：统计口径
  - sanitizeExamHtml 的白名单行为在 tests/test_sanitize.mjs 里单独跑

用法（在项目根目录）：
    python tests/test_units.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PASS = FAIL = 0
FAIELD: list[str] = []


def check(name: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        FAIELD.append(name)
        print(f"  !!  {name}\n        得到 {got!r}\n        期望 {want!r}")


def truthy(name: str, got) -> None:
    global PASS, FAIL
    if got:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        FAIELD.append(name)
        print(f"  !!  {name}（值为假）")


# ---------------------------------------------------------------- conjugator
print("=" * 70)
print("conjugator")
print("=" * 70)
from conjugator import conjugate, guess  # noqa: E402

check("する ます形", conjugate("する", "suru")["ます形"], "します")
check("あいする ます形（保留词干）", conjugate("あいする", "suru")["ます形"], "あいします")
check("あいする ない形", conjugate("あいする", "suru")["ない形"], "あいしない")
check("あいする て形", conjugate("あいする", "suru")["て形"], "あいして")
check("べんきょう ます形（只给词干）", conjugate("べんきょう", "suru")["ます形"],
      "べんきょうします")
check("べんきょう 可能形", conjugate("べんきょう", "suru")["可能形"], "べんきょうできる")
check("たべる て形", conjugate("たべる", "ichidan")["て形"], "たべて")
check("かく て形（音便）", conjugate("かく", "godan")["て形"], "かいて")
check("いく て形（特殊）", conjugate("いく", "godan")["て形"], "いって")
check("guess あいする", guess("あいする"), "suru")
check("guess べんきょうする", guess("べんきょうする"), "suru")
check("guess かす（五段，不是サ変）", guess("かす"), "godan")
check("guess たべる（浊音え段）", guess("たべる"), "ichidan")
check("guess あそぶ", guess("あそぶ"), "godan")

# ---------------------------------------------------------------- mock_exam
print()
print("=" * 70)
print("mock_exam._normalize")
print("=" * 70)
import mock_exam  # noqa: E402

good = {
    "tag": "N3", "title": "t",
    "questions": [
        {"id": "q1", "subject": "vocabulary", "options": ["a", "b"], "answer": 1},
        {"id": "q2", "subject": "grammar", "options": ["a", "b"], "answer": 9},   # 越界
        {"id": "q3", "subject": "grammar", "options": ["only"], "answer": 0},     # 选项不足
        {"id": "q4", "subject": "reading", "options": ["a", "b"], "answer": "x"},  # 非数字
    ],
}
out = mock_exam._normalize(dict(good), "x")
check("只保留合法题", [q["id"] for q in out["questions"]], ["q1"])
check("subjects 归并", out["subjects"], ["vocabulary"])

try:
    mock_exam._normalize({"tag": "N3", "questions": []}, "x")
    truthy("空题应抛错", False)
except mock_exam.MockExamError:
    truthy("空题抛 MockExamError", True)

for bad_id in ("../etc", "a" * 100, "", "a b"):
    try:
        mock_exam.fetch_full_exam(bad_id)
        truthy(f"非法 id {bad_id!r} 应拒绝", False)
    except mock_exam.InvalidExamId:
        truthy(f"非法 id {bad_id!r} 抛 InvalidExamId", True)
    except mock_exam.MockExamError:
        truthy(f"非法 id {bad_id!r} 抛 MockExamError", True)

# 答案分布：仓库内卷子不该再偏向某个位置
print()
print("=" * 70)
print("模考答案分布（不该集中在 A）")
print("=" * 70)
from collections import Counter
for path in sorted((ROOT / "web" / "data" / "mock_exams").glob("mock-*.json")):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    n = len(data["questions"])
    if n < 4:
        continue
    counts = Counter(q["answer"] for q in data["questions"])
    share = counts.most_common(1)[0][1] / n
    truthy(f"{path.name} 单一选项占比 {share:.0%} ≤ 60%", share <= 0.6)

# ---------------------------------------------------------------- weakness
print()
print("=" * 70)
print("weakness.analyze_sessions / save_session")
print("=" * 70)
import weakness  # noqa: E402

fake = [
    {"id": "s1", "subjectFilter": "vocabulary", "questions": [
        {"subject": "vocabulary", "isCorrect": True},
        {"subject": "vocabulary", "isCorrect": False},
    ]},
    {"id": "s2", "subjectFilter": "grammar", "questions": [
        {"subject": "grammar", "isCorrect": True},
    ]},
]
stats = weakness.analyze_sessions(fake)
truthy("analyze_sessions 返回 dict", isinstance(stats, dict))

with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    r1 = weakness.save_session(d, {"examId": "e1", "questions": []})
    r2 = weakness.save_session(d, {"examId": "e1", "questions": []})
    truthy("同秒连续保存生成不同文件", r1["file"] != r2["file"])
    truthy("只写单个 json（不再双写 jsonl）", not (d / "sessions.jsonl").exists())
    loaded = weakness.load_sessions(d, limit=10)
    check("能读回两条", len(loaded), 2)

# ---------------------------------------------------------------- 汇总
print()
print("=" * 70)
print(f"PASS {PASS} / FAIL {FAIL}")
print("=" * 70)
if FAIELD:
    print("失败项：")
    for f in FAIELD:
        print("  ! " + f)
sys.exit(1 if FAIL else 0)
