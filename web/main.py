# -*- coding: utf-8 -*-
"""FastAPI app: Japanese learning (local JMdict + mock JLPT + Ollama)."""
from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db import DatabaseUnavailable

from lookup import get_word, get_grammar, grammar_counts, jlpt_counts, list_grammar, list_jlpt, search, search_grammar
from ai_ollama import (
    OllamaError,
    build_grammar_messages,
    build_messages,
    chat,
    check_status,
    OLLAMA_MODEL,
)
import mock_exam
import audio_module
from weakness import analyze_log_dir, analyze_sessions, load_sessions, save_session

STATIC_DIR = Path(__file__).resolve().parent / "static"
CACHE_DIR = Path(__file__).resolve().parent / "cache"
EXAM_LOG_DIR = CACHE_DIR / "exam-logs"
EXAM_LOG_MAX_BYTES = 2 * 1024 * 1024

app = FastAPI(title="日语学习", version="1.0.0")


@lru_cache(maxsize=1024)
def get_word_cached(seq: int) -> dict[str, Any] | None:
    """Process-local cache for read-only word details."""
    return get_word(seq)


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable(_request: Request, exc: DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(sqlite3.Error)
async def sqlite_unavailable(_request: Request, _exc: sqlite3.Error):
    return JSONResponse(status_code=503, content={"detail": "词典数据库暂时不可用"})


@app.get("/api/search")
def api_search(
    q: str = Query("", min_length=0, max_length=100),
    limit: int = Query(10, ge=1, le=50),
):
    return search(q, limit=limit)


@app.get("/api/grammar")
def api_grammar(
    q: str = Query("", min_length=0, max_length=100),
    limit: int = Query(15, ge=1, le=50),
    level: str | None = Query(None, min_length=0, max_length=16),
):
    return search_grammar(q, limit=limit, level=level)


@app.get("/api/grammar/counts")
def api_grammar_counts():
    return grammar_counts()


@app.get("/api/grammar/list")
def api_grammar_list(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    level: str | None = Query(None, min_length=0, max_length=16),
):
    return list_grammar(limit=limit, offset=offset, level=level)


@app.get("/api/grammar/{gid}")
def api_grammar_one(gid: int):
    data = get_grammar(gid)
    if data is None:
        raise HTTPException(status_code=404, detail="grammar not found")
    return data


@app.get("/api/jlpt/counts")
def api_jlpt_counts():
    return jlpt_counts()


@app.get("/api/jlpt")
def api_jlpt(
    level: str = Query(..., min_length=2, max_length=2),
    limit: int = Query(100, ge=1, le=200),
):
    level_u = level.strip().upper()
    if level_u not in {"N5", "N4", "N3", "N2", "N1"}:
        raise HTTPException(status_code=400, detail="level must be N5..N1")
    return list_jlpt(level_u, limit=limit)


class AiHistoryItem(BaseModel):
    role: str = Field(..., max_length=20)
    content: str = Field(..., max_length=4000)


class AiExplainBody(BaseModel):
    seq: int | None = None
    word: str | None = Field(default=None, max_length=80)
    question: str | None = Field(default=None, max_length=400)
    history: list[AiHistoryItem] | None = None


@app.get("/api/ai/status")
def api_ai_status():
    return check_status()


@app.post("/api/ai/explain")
def api_ai_explain(body: AiExplainBody):
    word_data = None
    if body.seq is not None:
        word_data = get_word_cached(int(body.seq))
        if word_data is None:
            raise HTTPException(status_code=404, detail="word not found")
    elif not (body.word and body.word.strip()):
        raise HTTPException(status_code=400, detail="seq or word required")
    hist: list[dict[str, Any]] | None = None
    if body.history:
        hist = []
        for h in body.history[-12:]:
            role = (h.role or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = (h.content or "").strip()
            if not content:
                continue
            hist.append({"role": role, "content": content[:3500]})
    messages = build_messages(word_data, body.word, body.question, history=hist)
    try:
        text = chat(messages)
    except OllamaError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return {"text": text, "model": OLLAMA_MODEL}


class AiGrammarBody(BaseModel):
    grammar_id: int
    question: str | None = Field(default=None, max_length=400)
    history: list[AiHistoryItem] | None = None


@app.post("/api/ai/grammar")
def api_ai_grammar(body: AiGrammarBody):
    data = get_grammar(int(body.grammar_id))
    if data is None:
        raise HTTPException(status_code=404, detail="grammar not found")
    hist: list[dict[str, Any]] | None = None
    if body.history:
        hist = []
        for h in body.history[-12:]:
            role = (h.role or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = (h.content or "").strip()
            if not content:
                continue
            hist.append({"role": role, "content": content[:3500]})
    messages = build_grammar_messages(data, body.question, history=hist)
    try:
        text = chat(messages)
    except OllamaError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return {"text": text, "model": OLLAMA_MODEL}


@app.get("/api/word/{seq}")
def api_word(seq: int):
    data = get_word_cached(seq)
    if data is None:
        raise HTTPException(status_code=404, detail="word not found")
    return data


@app.get("/api/audio/{seq}")
def api_audio(seq: int, voice: str = Query(audio_module.DEFAULT_VOICE)):
    """Word audio. The first request downloads an mp3; later requests stay local."""
    if voice not in audio_module.VOICES:
        raise HTTPException(status_code=400, detail="unsupported voice")
    data = get_word_cached(seq)
    if data is None:
        raise HTTPException(status_code=404, detail="word not found")
    kanji = data.get("kanji") or []
    kana = data.get("kana") or []
    form = (kanji[0] if kanji else (kana[0] if kana else "")).strip()
    if not form:
        raise HTTPException(status_code=404, detail="word has no readable form")
    path = audio_module.fetch_cached(form, voice)
    if path is None:
        raise HTTPException(status_code=404, detail="audio unavailable")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/audio-status")
def api_audio_status():
    return audio_module.audio_status()


@app.post("/api/cache/clear")
def api_cache_clear():
    """Drop the in-memory word cache after rebuilding jmdict.db."""
    before = get_word_cached.cache_info()
    get_word_cached.cache_clear()
    return {"ok": True, "cleared": before.currsize}


@app.get("/api/exam/list")
def api_exam_list(level: str = Query("N2", min_length=2, max_length=2)):
    level_u = level.strip().upper()
    if level_u not in {"N5", "N4", "N3", "N2", "N1"}:
        raise HTTPException(status_code=400, detail="level must be N5..N1")
    try:
        return {"list": mock_exam.fetch_exam_list(level_u)}
    except mock_exam.MockExamError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/exam/log")
async def api_exam_log_save(request: Request):
    raw = await request.body()
    if len(raw) > EXAM_LOG_MAX_BYTES:
        raise HTTPException(status_code=413, detail="log payload too large (max 2MB)")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    try:
        return save_session(EXAM_LOG_DIR, payload)
    except OSError as e:
        raise HTTPException(status_code=500, detail="failed to save exam log") from e


@app.get("/api/exam/logs")
def api_exam_logs(limit: int = Query(20, ge=1, le=100)):
    sessions = load_sessions(EXAM_LOG_DIR, limit=limit)
    return {"list": sessions, "count": len(sessions)}





@app.get("/api/weakness")
def api_weakness(limit: int = Query(50, ge=1, le=200)):
    """Subject-level weak points from exam logs (server cache)."""
    return analyze_log_dir(EXAM_LOG_DIR, limit=limit)


@app.post("/api/weakness/analyze")
async def api_weakness_analyze(request: Request, limit: int = Query(50, ge=1, le=200)):
    """Merge optional client sessions with server logs for richer 复盘."""
    from weakness import load_sessions

    raw = await request.body()
    client_sessions: list = []
    if raw:
        if len(raw) > EXAM_LOG_MAX_BYTES:
            raise HTTPException(status_code=413, detail="payload too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e
        if isinstance(payload, dict):
            client_sessions = payload.get("sessions") or []
        elif isinstance(payload, list):
            client_sessions = payload
        if not isinstance(client_sessions, list):
            raise HTTPException(status_code=400, detail="sessions must be a list")
    merged = []
    seen = set()
    for s in list(client_sessions) + load_sessions(EXAM_LOG_DIR, limit=limit):
        if not isinstance(s, dict):
            continue
        key = str(s.get("id") or s.get("savedAt") or s.get("finishedAt") or id(s))
        if key in seen:
            continue
        seen.add(key)
        merged.append(s)
        if len(merged) >= limit:
            break
    result = analyze_sessions(merged)
    result["source"] = "merged"
    return result

@app.get("/api/exam/{exam_id}")
def api_exam(exam_id: str, refresh: bool = Query(False)):
    try:
        return mock_exam.fetch_full_exam(exam_id, refresh=refresh)
    except mock_exam.MockExamError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/word")
def word_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favorites")
def favorites_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/study")
def study_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/exam")
def exam_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/grammar")
def grammar_page():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
