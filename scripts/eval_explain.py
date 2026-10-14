# -*- coding: utf-8 -*-
"""
Sample grammar items, call local Ollama (tinyswallow) for short explains,
save JSON with human score placeholders (accuracy / usefulness 1–5).

Usage (from project root):
  web\\.venv\\Scripts\\python scripts\\eval_explain.py --limit 10
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DB_PATH = ROOT / "jmdict.db"
OUT_DIR = ROOT / "data"

sys.path.insert(0, str(WEB))

from ai_ollama import OLLAMA_MODEL, OllamaError, build_grammar_messages, chat, check_status  # noqa: E402


def sample_grammar(limit: int, seed: int = 42) -> list[dict]:
    if not DB_PATH.is_file():
        raise SystemExit(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Prefer items with explain + connection; spread by id
    rows = conn.execute(
        """
        SELECT id, pattern, explain, connection, level
        FROM grammar
        WHERE pattern IS NOT NULL AND TRIM(pattern) != ''
        ORDER BY id
        """
    ).fetchall()
    conn.close()
    if not rows:
        raise SystemExit("No grammar rows in DB")
    # Stride sample for coverage
    n = len(rows)
    step = max(1, n // max(limit, 1))
    picked = []
    i = seed % max(step, 1)
    while len(picked) < limit and i < n:
        r = rows[i]
        picked.append(
            {
                "grammar_id": int(r["id"]),
                "pattern": (r["pattern"] or "").strip(),
                "explain": (r["explain"] or "").strip(),
                "connection": (r["connection"] or "").strip() if "connection" in r.keys() else "",
                "level": (r["level"] or "").strip() if "level" in r.keys() else "",
            }
        )
        i += step
    # Fill if short
    for r in rows:
        if len(picked) >= limit:
            break
        gid = int(r["id"])
        if any(p["grammar_id"] == gid for p in picked):
            continue
        picked.append(
            {
                "grammar_id": gid,
                "pattern": (r["pattern"] or "").strip(),
                "explain": (r["explain"] or "").strip(),
                "connection": (r["connection"] or "").strip() if "connection" in r.keys() else "",
                "level": (r["level"] or "").strip() if "level" in r.keys() else "",
            }
        )
    return picked[:limit]


def run_one(item: dict) -> dict:
    data = {
        "pattern": item["pattern"],
        "explain": item["explain"],
        "connection": item.get("connection") or "",
    }
    messages = build_grammar_messages(data, question=None, history=None)
    t0 = time.perf_counter()
    text = chat(messages)
    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "grammar_id": item["grammar_id"],
        "pattern": item["pattern"],
        "level": item.get("level") or "",
        "dict_explain": item["explain"],
        "dict_connection": item.get("connection") or "",
        "model": OLLAMA_MODEL,
        "model_output": text,
        "latency_sec": elapsed,
        "scores": {
            "accuracy": None,
            "usefulness": None,
            "notes": "",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Eval tinyswallow grammar explains")
    ap.add_argument("--limit", type=int, default=10, help="How many items (default 10)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="", help="Output JSON path")
    args = ap.parse_args()
    limit = max(1, min(80, int(args.limit)))

    status = check_status()
    if not status.get("ok"):
        raise SystemExit(
            f"Ollama model not ready (model={status.get('model')}). "
            "Run: ollama pull tinyswallow"
        )

    items = sample_grammar(limit, seed=args.seed)
    results = []
    print(f"Evaluating {len(items)} grammar items with {OLLAMA_MODEL}…")
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item['pattern'][:40]} …", flush=True)
        try:
            results.append(run_one(item))
        except OllamaError as e:
            results.append(
                {
                    "grammar_id": item["grammar_id"],
                    "pattern": item["pattern"],
                    "error": str(e),
                    "scores": {"accuracy": None, "usefulness": None, "notes": ""},
                }
            )
            print(f"  ERROR: {e}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else OUT_DIR / f"explain_eval_{stamp}.json"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": OLLAMA_MODEL,
        "count": len(results),
        "rubric": {
            "accuracy": "1–5 事实是否正确、有无胡编接续/等级",
            "usefulness": "1–5 对 N2 学习者是否有用、结构是否清晰",
        },
        "how_to_score": "填写 items[].scores.accuracy / usefulness（整数 1–5）与 notes，保存后可自行算均分。",
        "items": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("model_output"))
    print(f"Done: {ok}/{len(results)} ok → {out_path}")


if __name__ == "__main__":
    main()
