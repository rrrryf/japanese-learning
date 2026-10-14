# -*- coding: utf-8 -*-
"""自建 JLPT 模考数据（本地 JSON，无外部 API）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data" / "mock_exams"
LISTS_FILE = DATA_DIR / "lists.json"


class MockExamError(Exception):
    pass


def _load_lists() -> dict[str, list]:
    if not LISTS_FILE.is_file():
        return {lv: [] for lv in ("N5", "N4", "N3", "N2", "N1")}
    return json.loads(LISTS_FILE.read_text(encoding="utf-8"))


def fetch_exam_list(level: str) -> list[dict[str, Any]]:
    level_u = level.strip().upper()
    lists = _load_lists()
    return list(lists.get(level_u) or [])


def fetch_full_exam(exam_id: str, refresh: bool = False) -> dict[str, Any]:
    del refresh  # local files only
    safe = "".join(c for c in exam_id if c.isalnum() or c in "-_")
    if not safe or safe != exam_id:
        raise MockExamError(f"invalid exam id: {exam_id!r}")
    path = DATA_DIR / f"{safe}.json"
    if not path.is_file():
        raise MockExamError(f"exam not found: {exam_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "questions" not in data:
        raise MockExamError(f"bad exam file: {path.name}")
    return data
