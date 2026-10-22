# -*- coding: utf-8 -*-
"""JLPT 模考数据（本地 JSON，无外部 API）。

两个来源：
  1. 内置示例卷  web/data/mock_exams/        随仓库分发，git 跟踪
  2. 用户导入卷  web/cache/imported_exams/   本地导入，git 忽略

导入卷不进版本库——如果你导入的是付费题库内容，它只该留在本机。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

WEB = Path(__file__).resolve().parent
DATA_DIR = WEB / "data" / "mock_exams"
LISTS_FILE = DATA_DIR / "lists.json"
IMPORT_DIR = WEB / "cache" / "imported_exams"

LEVELS = ("N5", "N4", "N3", "N2", "N1")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_BYTES = 8 * 1024 * 1024  # 单卷上限；真实整卷约 130–270 KB，留足余量


class MockExamError(Exception):
    """数据缺失、格式错误或 id 非法。"""


class InvalidExamId(MockExamError):
    """id 不符合规范（会被映射成 400，而不是 404）。"""


class ExamNotFound(MockExamError):
    """id 合法但找不到对应文件（映射成 404）。"""


# ---------------------------------------------------------------- 内置卷
def _load_lists() -> dict[str, list]:
    if not LISTS_FILE.is_file():
        return {lv: [] for lv in LEVELS}
    try:
        data = json.loads(LISTS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {lv: [] for lv in LEVELS}
    if not isinstance(data, dict):
        return {lv: [] for lv in LEVELS}
    return {lv: list(data.get(lv) or []) for lv in LEVELS}


# ---------------------------------------------------------------- 导入卷
def _safe_id(name: str) -> str:
    """从文件名生成合法 id：只留字母数字、- 和 _，最多 64 字符。"""
    stem = Path(str(name)).stem
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-_")
    return cleaned[:64]


def _imported_files() -> list[Path]:
    if not IMPORT_DIR.is_dir():
        return []
    return sorted(p for p in IMPORT_DIR.glob("*.json") if p.is_file())


def _read_exam_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise MockExamError(f"读取失败：{path.name}（{e}）") from e
    if len(raw) > MAX_BYTES:
        raise MockExamError(f"文件过大：{path.name}（超过 {MAX_BYTES // 1048576} MB）")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        raise MockExamError(f"不是合法 JSON：{path.name}（{e}）") from e
    if not isinstance(data, dict):
        raise MockExamError(f"顶层必须是对象：{path.name}")
    if not isinstance(data.get("questions"), list) or not data["questions"]:
        raise MockExamError(f"缺少 questions 数组：{path.name}")
    return data


def _imported_entry(path: Path) -> dict[str, Any]:
    """把导入文件整理成列表项；解析失败的条目跳过并记下原因。"""
    try:
        data = _read_exam_file(path)
    except MockExamError:
        return {}
    tag = str(data.get("tag") or "").strip().upper()
    if tag not in LEVELS:
        tag = ""
    return {
        "objectId": path.stem,
        "id": path.stem,
        "_id": path.stem,
        "tag": tag,
        "title": str(data.get("title") or path.stem),
        "isFree": True,
        "hasPractice": True,
        "imported": True,
        "questionCount": len(data["questions"]),
    }


# ---------------------------------------------------------------- 对外接口
def fetch_exam_list(level: str) -> list[dict[str, Any]]:
    """内置卷 + 导入卷，按等级合并。"""
    level_u = (level or "").strip().upper()
    builtin = list(_load_lists().get(level_u) or [])
    imported = []
    for p in _imported_files():
        entry = _imported_entry(p)
        if entry and entry.get("tag") == level_u:
            imported.append(entry)
    # 导入的排在前面，方便刚导入就能看到
    return imported + builtin


def all_imported() -> list[dict[str, Any]]:
    out = []
    for p in _imported_files():
        entry = _imported_entry(p)
        if entry:
            out.append(entry)
    return out


def fetch_full_exam(exam_id: str, refresh: bool = False) -> dict[str, Any]:
    del refresh  # 本地文件，无需刷新逻辑
    if not SAFE_ID.match(exam_id or ""):
        raise InvalidExamId(f"invalid exam id: {exam_id!r}")

    # 先找导入卷，再找内置卷（同名时导入的优先）
    imported = IMPORT_DIR / f"{exam_id}.json"
    if imported.is_file():
        data = _read_exam_file(imported)
        data.setdefault("objectId", exam_id)
        data["imported"] = True
        return _normalize(data, exam_id)
    builtin = DATA_DIR / f"{exam_id}.json"
    if builtin.is_file():
        data = _read_exam_file(builtin)
        data.setdefault("objectId", exam_id)
        return _normalize(data, exam_id)
    raise ExamNotFound(f"exam not found: {exam_id}")


def _normalize(data: dict[str, Any], exam_id: str) -> dict[str, Any]:
    """补齐前端依赖的字段，并剔除答案下标越界的题。"""
    questions = []
    for i, q in enumerate(data.get("questions") or []):
        if not isinstance(q, dict):
            continue
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            continue
        try:
            answer = int(q.get("answer"))
        except (TypeError, ValueError):
            continue
        if not (0 <= answer < len(opts)):
            continue
        questions.append({
            "id": str(q.get("id") or f"q{i+1}"),
            "subject": q.get("subject") or "vocabulary",
            "sectionTitle": q.get("sectionTitle") or "",
            "passage": q.get("passage") or "",
            "title": q.get("title") or "",
            "options": [str(o) for o in opts],
            "answer": answer,
            "analysis": q.get("analysis") or "",
            "imageId": q.get("imageId") or "",
            "mediaId": q.get("mediaId") or "",
            "audioUrl": q.get("audioUrl") or "",
            "subtitle": q.get("subtitle") or "",
            "translation": q.get("translation") or "",
        })
    if not questions:
        raise MockExamError(f"没有可用题目（选项或答案不合法）：{exam_id}")
    data["questions"] = questions
    subjects = []
    for q in questions:
        if q["subject"] not in subjects:
            subjects.append(q["subject"])
    data["subjects"] = subjects or ["vocabulary"]
    data.setdefault("tag", "")
    data.setdefault("title", exam_id)
    return data


def import_exam(payload: dict[str, Any], filename: str) -> dict[str, Any]:
    """校验并写入导入目录，返回 {id, title, tag, questionCount}。"""
    if not isinstance(payload, dict):
        raise MockExamError("内容必须是 JSON 对象")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise MockExamError("缺少 questions 数组，或数组为空")

    # id 优先用文件名（用户上传时最明确），其次是文件里自带的 objectId/id。
    # 避免直接用 objectId：它可能正好等于某套内置卷的名字，那样会遮住内置卷。
    exam_id = ""
    for cand in (filename, payload.get("objectId"), payload.get("id")):
        exam_id = _safe_id(str(cand or ""))
        if exam_id:
            break
    if not exam_id:
        raise MockExamError("无法生成合法 id（文件名或 objectId 只允许字母、数字、-、_）")

    tag = str(payload.get("tag") or "").strip().upper()
    if tag not in LEVELS:
        raise MockExamError("缺少或非法的 tag（应为 N5/N4/N3/N2/N1）")

    # 用 normalize 校验一遍：题干/选项/答案都合法才落盘
    data = dict(payload)
    data["tag"] = tag
    data.setdefault("title", exam_id)
    data["objectId"] = exam_id
    normalized = _normalize(data, exam_id)

    builtin_ids = {p.stem for p in DATA_DIR.glob("*.json")}
    if exam_id in builtin_ids:
        exam_id = f"{exam_id}-local"
        normalized["objectId"] = exam_id

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = IMPORT_DIR / f"{exam_id}.json"
    if target.is_file():
        # 已存在则不覆盖，加时间戳生成新 id，避免误毁旧卷
        exam_id = f"{exam_id}-{time.strftime('%Y%m%d%H%M%S')}"
        target = IMPORT_DIR / f"{exam_id}.json"
        normalized["objectId"] = exam_id
    target.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return {
        "id": exam_id,
        "title": normalized.get("title") or exam_id,
        "tag": tag,
        "questionCount": len(normalized["questions"]),
        "subjects": normalized["subjects"],
    }


def delete_imported(exam_id: str) -> bool:
    if not SAFE_ID.match(exam_id or ""):
        raise InvalidExamId(f"invalid exam id: {exam_id!r}")
    path = IMPORT_DIR / f"{exam_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True
