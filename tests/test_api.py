# -*- coding: utf-8 -*-
"""API 回归与鲁棒性测试（无第三方依赖，只用标准库）。

覆盖：输入边界 / 参数校验 / 注入尝试 / 协议误用 / 并发 / 依赖故障 / 安全响应头。

用法（服务需先启动）：
    python tests/test_api.py --base http://127.0.0.1:8765
    python tests/test_api.py --base http://127.0.0.1:8765 --with-ai

退出码：0 = 全部通过；1 = 有 FAIL 项。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Windows 控制台默认 GBK，词典数据里会出现 ⓪ 这类字符；统一按 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RESULTS: list[tuple[str, str, str]] = []
BASE = "http://127.0.0.1:8765"


def rec(level: str, name: str, detail: str) -> None:
    RESULTS.append((level, name, detail))
    mark = {"PASS": "  ok  ", "FAIL": "  !!  ", "WARN": "  ??  ", "SKIP": "  --  "}[level]
    print(f"{mark}{name:<50} {detail}", flush=True)


def req(path: str, method: str = "GET", body: bytes | None = None,
        ctype: str | None = None, headers: dict | None = None, timeout: float = 30):
    h = dict(headers or {})
    if ctype:
        h["Content-Type"] = ctype
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(), (time.perf_counter() - t0) * 1000, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), (time.perf_counter() - t0) * 1000, dict(e.headers)
    except Exception as e:  # 连接失败 / 超时
        return None, str(e).encode(), (time.perf_counter() - t0) * 1000, {}


def expect(name: str, want, path: str, **kw):
    st, body, ms, _ = req(path, **kw)
    ok = (st in want) if isinstance(want, (set, list, tuple)) else (st == want)
    snippet = body[:110].decode("utf-8", "replace").replace("\n", " ")
    rec("PASS" if ok else "FAIL", name, f"status={st} {ms:.0f}ms {snippet}")
    return st, body


def section(title: str) -> None:
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--with-ai", action="store_true", help="也测试 Ollama 讲解（需要本机模型）")
    args = ap.parse_args()
    BASE = args.base.rstrip("/")

    # 连通性预检
    st, _, _, _ = req("/")
    if st != 200:
        print(f"[x] 无法访问 {BASE}（status={st}）。先启动服务：.\\start.ps1")
        return 1

    # ---------------------------------------------------------------- A
    section("A. 输入边界")
    expect("空 q", 200, "/api/search?q=")
    expect("仅空格 q", 200, "/api/search?q=" + urllib.parse.quote("   "))
    expect("q 恰好 100 字（上限内）", 200, "/api/search?q=" + urllib.parse.quote("あ" * 100))
    expect("q 101 字（超上限应 422）", 422, "/api/search?q=" + urllib.parse.quote("あ" * 101))
    expect("q 10KB（应 422）", 422, "/api/search?q=" + "a" * 10000)
    expect("q 含 null 字节", {200, 422}, "/api/search?q=a%00b")
    expect("q 含控制字符", {200, 422}, "/api/search?q=a%07b")
    expect("q 含 emoji", 200, "/api/search?q=" + urllib.parse.quote("🍣寿司"))
    expect("q 含 RTL 覆盖字符", 200, "/api/search?q=" + urllib.parse.quote("食べる\u202e"))
    expect("q 为单个汉字", 200, "/api/search?q=" + urllib.parse.quote("食"))
    expect("q 为长日文句", 200, "/api/search?q=" + urllib.parse.quote("私は毎朝駅前のカフェでコーヒーを飲みながら新聞を読む"))

    # ---------------------------------------------------------------- B
    section("B. 参数类型与范围")
    expect("limit=-1", 422, "/api/search?q=a&limit=-1")
    expect("limit=0", 422, "/api/search?q=a&limit=0")
    expect("limit=99999", 422, "/api/search?q=a&limit=99999")
    expect("limit=abc", 422, "/api/search?q=a&limit=abc")
    expect("limit=1.5", 422, "/api/search?q=a&limit=1.5")
    expect("seq=0", 404, "/api/word/0")
    expect("seq=-1", {404, 422}, "/api/word/-1")
    expect("seq 超 int64（应 422）", 422, "/api/word/9223372036854775808")
    expect("seq 40 位数字（应 422）", 422, "/api/word/" + "9" * 40)
    expect("seq=abc", 422, "/api/word/abc")
    expect("seq=1.5", 422, "/api/word/1.5")
    expect("jlpt level=XX", 400, "/api/jlpt?level=XX")
    expect("jlpt level=n2（小写）", 200, "/api/jlpt?level=n2")
    expect("jlpt limit=200（上限）", 200, "/api/jlpt?level=N2&limit=200")
    expect("jlpt limit=201", 422, "/api/jlpt?level=N2&limit=201")
    expect("grammar gid 不存在", 404, "/api/grammar/999999")
    expect("grammar gid=2^63（应 422）", 422, "/api/grammar/9223372036854775808")

    # ---------------------------------------------------------------- C
    section("C. 注入尝试")
    for s in ["' OR 1=1--", "'); DROP TABLE entries;--", "1' UNION SELECT 1,2,3--"]:
        st, body, ms, _ = req("/api/search?q=" + urllib.parse.quote(s))
        leaked = b"sqlite" in body.lower() or b"traceback" in body.lower()
        rec("FAIL" if leaked else "PASS", f"SQLi {s[:20]!r}", f"status={st} leak={leaked}")
    for p in ("/static/../main.py", "/static/..%2fmain.py", "/static/%2e%2e/main.py"):
        st, body, ms, _ = req(p)
        leaked = b"FastAPI" in body or b"import " in body
        rec("FAIL" if leaked else "PASS", f"路径穿越 {p}", f"status={st} leaked={leaked}")

    # ---------------------------------------------------------------- D
    section("D. 协议误用与 CSRF")
    expect("POST 到 GET 端点", 405, "/api/search?q=a", method="POST", body=b"{}")
    expect("GET 到 POST 端点 /api/exam/log（应 405）", 405, "/api/exam/log")
    expect("exam/log 空 body", 400, "/api/exam/log", method="POST", body=b"", ctype="application/json")
    expect("exam/log 非法 JSON", 400, "/api/exam/log", method="POST", body=b"{not json", ctype="application/json")
    expect("exam/log 3MB（应 413）", 413, "/api/exam/log", method="POST",
           body=b'{"x":"' + b"a" * (3 * 1024 * 1024) + b'"}', ctype="application/json")
    expect("exam/log text/plain（应 415）", 415, "/api/exam/log", method="POST", body=b"{}", ctype="text/plain")
    expect("exam/log 无 Content-Type（应 415）", 415, "/api/exam/log", method="POST", body=b"{}")
    expect("weakness/analyze text/plain（应 415）", 415, "/api/weakness/analyze",
           method="POST", body=b'{"sessions":[]}', ctype="text/plain")
    expect("cache/clear 无 Content-Type（应 415）", 415, "/api/cache/clear", method="POST", body=b"")
    expect("cache/clear 正确 Content-Type", 200, "/api/cache/clear",
           method="POST", body=b"{}", ctype="application/json")
    expect("ai/explain 空对象", 400, "/api/ai/explain", method="POST", body=b"{}", ctype="application/json")
    expect("ai/explain 超长 question", 422, "/api/ai/explain", method="POST",
           body=json.dumps({"word": "食べる", "question": "q" * 500}).encode(), ctype="application/json")

    # ---------------------------------------------------------------- E
    section("E. Host 校验（DNS rebinding）")
    for host in ("evil.example.com", "attacker.test"):
        st, _, ms, _ = req("/api/jlpt/counts", headers={"Host": host})
        rec("PASS" if st == 400 else "FAIL", f"Host: {host}（应 400）", f"status={st}")
    for host in ("127.0.0.1", "localhost"):
        st, _, ms, _ = req("/api/jlpt/counts", headers={"Host": host})
        rec("PASS" if st == 200 else "FAIL", f"Host: {host}（应 200）", f"status={st}")

    # ---------------------------------------------------------------- F
    section("F. 安全响应头")
    st, _, ms, hdrs = req("/")
    low = {k.lower(): v for k, v in hdrs.items()}
    for name in ("content-security-policy", "x-frame-options",
                 "x-content-type-options", "referrer-policy"):
        rec("PASS" if name in low else "FAIL", f"响应头 {name}", "present" if name in low else "missing")

    # ---------------------------------------------------------------- G
    section("G. 并发")
    def concurrency(path: str, n: int):
        lat: list[float] = []
        codes: dict = {}
        lock = threading.Lock()

        def worker():
            st, _body, ms, _h = req(path, timeout=60)
            with lock:
                lat.append(ms)
                codes[st] = codes.get(st, 0) + 1

        t0 = time.perf_counter()
        ths = [threading.Thread(target=worker) for _ in range(n)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        return (time.perf_counter() - t0) * 1000, lat, codes

    for path, n, label in (
        ("/api/search?q=" + urllib.parse.quote("食べる"), 50, "search x50"),
        ("/api/jlpt?level=N2&limit=100", 20, "jlpt x20"),
        ("/api/word/1358280", 30, "word x30"),
        ("/api/grammar/counts", 50, "grammar-counts x50"),
    ):
        wall, lat, codes = concurrency(path, n)
        errors = sum(v for k, v in codes.items() if k != 200)
        p95 = statistics.quantiles(lat, n=20)[-1] if len(lat) > 5 else max(lat)
        rec("PASS" if errors == 0 else "FAIL", f"并发 {label}",
            f"wall={wall:.0f}ms p95={p95:.0f}ms errors={errors} codes={codes}")

    # ---------------------------------------------------------------- H
    section("H. 已移除的端点与依赖故障")
    expect("发音接口已移除（应 404）", 404, "/api/audio/1358280")
    expect("不存在的路由（应 404）", 404, "/api/nope")
    st, body, ms, _ = req("/api/word/1358280")
    rec("PASS" if st == 200 else "FAIL", "词条 core 路径", f"status={st} {len(body)}B")

    if args.with_ai:
        section("I. 本地 AI（--with-ai）")
        st, body, ms, _ = req("/api/ai/status")
        model = ""
        try:
            model = json.loads(body).get("model", "")
        except Exception:
            pass
        rec("PASS" if st == 200 else "FAIL", "ai/status", f"status={st} model={model}")
        if st == 200:
            st, body, ms, _ = req("/api/ai/explain", method="POST",
                                  body=json.dumps({"word": "食べる"}).encode(),
                                  ctype="application/json", timeout=300)
            rec("PASS" if st == 200 else "WARN", "ai/explain 一次调用",
                f"status={st} {ms/1000:.1f}s {len(body)}B")
    else:
        section("I. 本地 AI（未测试）")
        rec("SKIP", "AI 相关用例", "加 --with-ai 才会跑（需要本机 Ollama）")

    # ---------------------------------------------------------------- 汇总
    print()
    print("=" * 96)
    total = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for lvl, _, _ in RESULTS:
        total[lvl] += 1
    print(f"汇总：PASS {total['PASS']} / WARN {total['WARN']} / "
          f"FAIL {total['FAIL']} / SKIP {total['SKIP']}（共 {len(RESULTS)} 项）")
    print("=" * 96)
    for want in ("FAIL", "WARN"):
        items = [x for x in RESULTS if x[0] == want]
        if items:
            print(f"\n{want}：")
            for _, name, detail in items:
                print(f"  {name}: {detail}")
    return 1 if total["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
