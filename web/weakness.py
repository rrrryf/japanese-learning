# -*- coding: utf-8 -*-
"""Analyze exam logs for subject-level weak points."""
from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SUBJECT_LABELS = {
    "vocabulary": "文字·词汇",
    "grammar": "文法",
    "reading": "读解",
    "listening": "听力",
}

SUBJECT_ORDER = ["vocabulary", "grammar", "reading", "listening"]

SUBJECT_ACTIONS = {
    "vocabulary": {
        "action": "daily_vocab",
        "label": "加强每日词汇",
        "href": "#/",
        "drill": None,
    },
    "grammar": {
        "action": "grammar_browse",
        "label": "去刷语法",
        "href": "#/grammar",
        "drill": "grammar",
    },
    "reading": {
        "action": "exam_drill",
        "label": "练读解专项",
        "href": "#/exam",
        "drill": "reading",
    },
    "listening": {
        "action": "exam_drill",
        "label": "练听力专项",
        "href": "#/exam",
        "drill": "listening",
    },
}


LOG_LOCK = threading.Lock()


def _safe_slug(value: str, fallback: str = "session") -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", (value or "").strip(), flags=re.UNICODE)
    text = text.strip("_")[:80]
    return text or fallback


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def save_session(log_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Write one exam session. Concurrent saves get distinct files."""
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    ms = f"{now.microsecond // 1000:03d}"
    exam_id = _safe_slug(str(payload.get("examId") or "unknown"), "unknown")
    mode = _safe_slug(str(payload.get("subjectFilter") or "full"), "full")
    if "savedAt" not in payload:
        payload["savedAt"] = now.isoformat(timespec="seconds")

    with LOG_LOCK:
        filename = f"{stamp}-{ms}_{exam_id}_{mode}.json"
        path = log_dir / filename
        n = 1
        while path.exists():
            filename = f"{stamp}-{ms}_{exam_id}_{mode}_{n}.json"
            path = log_dir / filename
            n += 1
        if "id" not in payload:
            payload["id"] = path.stem
        jsonl_path = log_dir / "sessions.jsonl"
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                f.flush()
        except OSError:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    return {"ok": True, "file": filename}


def _norm_subject(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    aliases = {
        "vocab": "vocabulary",
        "vocabulary": "vocabulary",
        "word": "vocabulary",
        "文字": "vocabulary",
        "词汇": "vocabulary",
        "grammar": "grammar",
        "文法": "grammar",
        "reading": "reading",
        "读解": "reading",
        "listening": "listening",
        "听力": "listening",
    }
    return aliases.get(s, s if s in SUBJECT_LABELS else None)


def load_sessions(log_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    log_dir.mkdir(parents=True, exist_ok=True)
    with LOG_LOCK:
        return _load_sessions_unlocked(log_dir, limit)


def _load_sessions_unlocked(log_dir: Path, limit: int) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    jsonl = log_dir / "sessions.jsonl"
    if jsonl.is_file():
        try:
            lines = jsonl.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    sessions.append(obj)
                if len(sessions) >= limit:
                    break
        except OSError:
            sessions = []
    if len(sessions) < limit:
        files = sorted(
            (p for p in log_dir.glob("*.json") if p.name != "sessions.jsonl"),
            key=_mtime,
            reverse=True,
        )
        seen_ids = {str(s.get("id") or "") for s in sessions}
        for path in files:
            if len(sessions) >= limit:
                break
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(obj, dict):
                continue
            sid = str(obj.get("id") or path.stem)
            if sid in seen_ids:
                continue
            sessions.append(obj)
            seen_ids.add(sid)
    return sessions[:limit]


def analyze_sessions(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = {
        k: {"subject": k, "label": SUBJECT_LABELS[k], "total": 0, "wrong": 0, "correct": 0, "blank": 0}
        for k in SUBJECT_ORDER
    }
    section_wrong: dict[str, int] = defaultdict(int)
    session_count = 0
    question_count = 0

    for sess in sessions:
        session_count += 1
        qs = sess.get("questions")
        if not isinstance(qs, list):
            # session-level fallback
            subj = _norm_subject(sess.get("subjectFilter") or sess.get("subject"))
            total = max(0, _as_int(sess.get("total")))
            correct = min(max(0, _as_int(sess.get("correct"))), total)
            blank = min(max(0, _as_int(sess.get("blank"))), max(0, total - correct))
            if subj and total > 0 and subj in stats:
                wrong = max(0, total - correct - blank)
                stats[subj]["total"] += total
                stats[subj]["correct"] += correct
                stats[subj]["wrong"] += wrong
                question_count += total
            continue
        for q in qs:
            if not isinstance(q, dict):
                continue
            subj = _norm_subject(q.get("subject") or sess.get("subjectFilter"))
            if not subj or subj not in stats:
                continue
            question_count += 1
            stats[subj]["total"] += 1
            selected = q.get("selected")
            is_correct = q.get("correct")
            if is_correct is True:
                stats[subj]["correct"] += 1
            elif selected is None or selected == "" or selected == -1:
                stats[subj]["blank"] += 1
                stats[subj]["wrong"] += 1
            else:
                stats[subj]["wrong"] += 1
                sec = (q.get("sectionTitle") or q.get("questionTitle") or "").strip()
                if sec:
                    section_wrong[f"{subj}:{sec[:40]}"] += 1

    subjects_out: list[dict[str, Any]] = []
    for k in SUBJECT_ORDER:
        s = stats[k]
        total = s["total"]
        wrong = s["wrong"]
        accuracy = round(100.0 * s["correct"] / total, 1) if total else None
        wrong_rate = round(100.0 * wrong / total, 1) if total else None
        subjects_out.append(
            {
                **s,
                "accuracy": accuracy,
                "wrong_rate": wrong_rate,
                "action": SUBJECT_ACTIONS[k],
            }
        )

    # Rank weaknesses: prefer high wrong_rate with enough samples; then high wrong count
    ranked = [
        s
        for s in subjects_out
        if s["total"] > 0
    ]
    ranked.sort(
        key=lambda s: (
            -(s["wrong_rate"] if s["wrong_rate"] is not None else 0),
            -s["wrong"],
            s["accuracy"] if s["accuracy"] is not None else 100,
        )
    )

    top_sections = sorted(section_wrong.items(), key=lambda x: -x[1])[:8]
    suggestions: list[dict[str, Any]] = []
    for s in ranked:
        if s["wrong"] <= 0:
            continue
        # Weak if accuracy < 70 or wrong_rate >= 40 with at least 2 wrong
        acc = s["accuracy"]
        wr = s["wrong_rate"] or 0
        if (acc is not None and acc < 70) or wr >= 40 or s["wrong"] >= 2:
            act = s["action"]
            suggestions.append(
                {
                    "subject": s["subject"],
                    "label": s["label"],
                    "reason": f"正确率 {acc if acc is not None else '—'}%，错 {s['wrong']}/{s['total']}",
                    "action_label": act["label"],
                    "href": act["href"],
                    "drill": act["drill"],
                    "bias_daily": s["subject"] == "vocabulary",
                }
            )
        if len(suggestions) >= 3:
            break

    bias_daily = any(x.get("bias_daily") for x in suggestions)
    top = ranked[0] if ranked and ranked[0]["wrong"] > 0 else None

    return {
        "session_count": session_count,
        "question_count": question_count,
        "subjects": subjects_out,
        "ranked": ranked,
        "top_weak": top,
        "suggestions": suggestions,
        "top_sections": [{"key": k, "wrong": v} for k, v in top_sections],
        "bias_daily_vocab": bias_daily,
        "summary": (
            f"基于 {session_count} 次练习、{question_count} 题"
            if session_count
            else "暂无练习记录，先去做几套模考专项"
        ),
    }


def analyze_log_dir(log_dir: Path, limit: int = 50) -> dict[str, Any]:
    return analyze_sessions(load_sessions(log_dir, limit=limit))
