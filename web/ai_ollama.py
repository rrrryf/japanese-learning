# -*- coding: utf-8 -*-
"""Local Ollama helper for word/grammar explanations (default: tinyswallow)."""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "tinyswallow")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))


class OllamaError(Exception):
    """Ollama unreachable or returned an error."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def _model_listed(names: list[str], wanted: str) -> bool:
    """Match tinyswallow against tinyswallow:latest etc."""
    w = (wanted or "").strip()
    if not w:
        return False
    if w in names:
        return True
    base = w.split(":", 1)[0]
    for n in names:
        if not n:
            continue
        if n == base or n.startswith(base + ":"):
            return True
        if base == n.split(":", 1)[0]:
            return True
    return False


def check_status() -> dict[str, Any]:
    """Return {ok, model} — ok True if Ollama answers and model is listed."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/tags",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = [m.get("name") or m.get("model") or "" for m in data.get("models") or []]
        ok = _model_listed(names, OLLAMA_MODEL)
        return {"ok": bool(ok), "model": OLLAMA_MODEL}
    except Exception:
        return {"ok": False, "model": OLLAMA_MODEL}


def _word_summary(data: dict[str, Any]) -> str:
    kanji = data.get("kanji") or []
    kana = data.get("kana") or []
    head = (kanji[0] if kanji else (kana[0] if kana else ""))
    reading = kana[0] if kana else ""
    gloss_zh = (data.get("gloss_zh") or "").strip()
    level = (data.get("level") or "").strip()
    accent = (data.get("accent") or "").strip()
    senses = data.get("senses") or []
    en_parts: list[str] = []
    for s in senses[:4]:
        glosses = s.get("gloss") or []
        pos = s.get("pos_zh") or s.get("pos") or []
        g = "；".join(glosses[:5])
        if g:
            en_parts.append(f"[{'/'.join(pos)}] {g}" if pos else g)
    lines = [
        f"词形：{head}",
        f"读音：{reading}",
        f"罗马音：{(data.get('romaji') or '').strip()}",
    ]
    if level:
        lines.append(f"JLPT：{level}")
    if accent:
        lines.append(f"音调：{accent}")
    if gloss_zh:
        lines.append(f"中文释义：{gloss_zh}")
    if en_parts:
        lines.append("英文释义：\n" + "\n".join(en_parts))
    return "\n".join(lines)


def build_messages(
    word_data: dict[str, Any] | None,
    word: str | None,
    question: str | None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    q = (question or "").strip()
    if q:
        system = (
            "你是面向中国日语学习者（目标 JLPT N2）的耐心助教。用简体中文回答。"
            "只根据当前词条信息与对话上下文回答学习者的具体问题；"
            "不要跑题。不要编造不存在的 JLPT 等级或音调数字；"
            "没有的信息就说明不确定。回答简洁实用，控制在 280 字以内。"
        )
    else:
        system = (
            "你是面向中国日语学习者（目标 JLPT N2）的耐心助教。用简体中文讲解日语单词。"
            "结构清晰：1) 核心意思 2) 语感/使用场景 3) 一句短例句（日语+中文翻译）"
            "4) 常见误用或易混点。不要编造不存在的 JLPT 等级或音调数字；"
            "没有的信息就跳过。回答简洁实用，控制在 350 字以内。"
        )

    if word_data:
        summary = _word_summary(word_data)
        context = f"当前词条：\n{summary}"
    elif word:
        context = f"当前词条：日语词「{word.strip()}」"
    else:
        context = "当前词条：食べる"
        summary = context

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    prior: list[dict[str, str]] = []
    if history:
        for h in history:
            role = h.get("role")
            content = (h.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                prior.append({"role": role, "content": content})

    if prior:
        messages.append({"role": "user", "content": context})
        messages.append(
            {"role": "assistant", "content": "好的，我已了解这个词。请提问。"}
        )
        messages.extend(prior)
        if q:
            messages.append({"role": "user", "content": q})
        else:
            messages.append({"role": "user", "content": "请再简要讲解一下这个词。"})
    else:
        if q:
            user = f"{context}\n\n学习者问题：{q}"
        elif word_data:
            user = f"请讲解下面这个词：\n\n{summary}"
        else:
            user = f"请讲解：{context}"
        messages.append({"role": "user", "content": user})

    return messages


def _grammar_summary(data: dict[str, Any]) -> str:
    pattern = (data.get("pattern") or "").strip()
    explain = (data.get("explain") or "").strip()
    connection = (data.get("connection") or "").strip()
    lines = [f"句型：{pattern}"]
    if connection:
        lines.append(f"接续：{connection}")
    if explain:
        lines.append(f"词典说明：{explain}")
    return "\n".join(lines)

def build_grammar_messages(
    grammar_data: dict[str, Any] | None,
    question: str | None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Messages for grammar explain / Q&A (简体中文). Do not invent JLPT level."""
    q = (question or "").strip()
    if q:
        system = (
            "你是面向中国日语学习者（目标 JLPT N2）的语法助教。用简体中文回答。"
            "只围绕当前语法句型与对话上下文回答；不要跑题。"
            "不要编造不存在的 JLPT 等级；没有的信息就说明不确定。"
            "回答简洁实用，控制在 280 字以内。"
        )
    else:
        system = (
            "你是面向中国日语学习者（目标 JLPT N2）的语法助教。用简体中文讲解日语句型。"
            "结构清晰：1) 接续（接什么词形）2) 意思与用法 3) 一句短例句（日语+中文翻译）"
            "4) 易错点或近义辨析。不要编造不存在的 JLPT 等级；"
            "没有的信息就跳过。回答简洁实用，控制在 350 字以内。"
        )

    if grammar_data:
        summary = _grammar_summary(grammar_data)
        context = f"当前语法：\n{summary}"
    else:
        summary = "当前语法：未知句型"
        context = summary

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    prior: list[dict[str, str]] = []
    if history:
        for h in history:
            role = h.get("role")
            content = (h.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                prior.append({"role": role, "content": content})

    if prior:
        messages.append({"role": "user", "content": context})
        messages.append(
            {"role": "assistant", "content": "好的，我已了解这个句型。请提问。"}
        )
        messages.extend(prior)
        if q:
            messages.append({"role": "user", "content": q})
        else:
            messages.append({"role": "user", "content": "请再简要讲解一下这个语法。"})
    else:
        if q:
            user = f"{context}\n\n学习者问题：{q}"
        else:
            user = f"请讲解下面这个语法句型：\n\n{summary}"
        messages.append({"role": "user", "content": user})

    return messages


def chat(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.4},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise OllamaError(f"Ollama 返回错误 HTTP {e.code}: {detail}", status=503) from e
    except urllib.error.URLError as e:
        raise OllamaError(
            f"无法连接本机 Ollama（{OLLAMA_BASE}）。请确认 ollama serve 已启动。",
            status=503,
        ) from e
    except (TimeoutError, socket.timeout) as e:
        raise OllamaError("Ollama 响应超时，请稍后重试。", status=503) from e
    except Exception as e:
        raise OllamaError(f"调用 Ollama 失败：{e}", status=503) from e

    msg = data.get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text:
        raise OllamaError("Ollama 返回空内容。", status=503)
    return text
