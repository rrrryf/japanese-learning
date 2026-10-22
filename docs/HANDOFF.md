# HANDOFF · 日语词典 Web 项目交接说明

> 更新时间：2026-10-22
> 本文面向**接手本仓库的协作者（人或 agent）**，说明架构、数据层、已完成的改造、待办清单与禁区。
> 本文已脱敏：不含任何第三方服务的凭据、密钥、账号信息，也不含本机绝对路径。

---

## 0. 项目是什么

本地运行的日语学习 Web 应用，**离线优先**：

```
本地 JMdict SQLite（218,908 词条）  → 查词 / 活用 / 罗马音 / 例句
本地语法库（仓库内示例 100 条）                → 句型检索 / 分级浏览
真题模块（需要自备数据源凭据）      → JLPT 题目 / 选项 / 答案 / 解析 / 听力音频
本机 Ollama（默认 qwen2.5:7b）     → 词条与语法的 AI 讲解
练习日志（jsonl）                   → 做题记录 → 薄弱点复盘
```

技术栈刻意保持极简：**FastAPI + 单文件原生 JS SPA + SQLite**。前端 `static/app.js` 约 92 KB，无构建步骤、无框架；后端依赖只有 `fastapi` + `uvicorn`。

### 当前状态

| 维度 | 状态 |
|---|---|
| 可运行性 | ✅ 五个页面（查词 / 词条 / 语法 / 真题 / 背单词）核对通过 |
| 已改进 | 10 项（性能 340×、8 处 XSS 出口收口、新增离线发音等） |
| 待改进 | 16 项（P0×3 / P1×5 / P2×5 / P3×3） |
| 已知阻断缺陷 | 无 |
| 最急的事 | 版本库忽略了含凭据的本地配置（见 FIX-01） |

---

## 1. 结构与环境

### 1.1 目录

```
jmdict/
├── jmdict.db              # 词库（83 MB，含全部索引）
├── build_db.py            # JMdict XML → SQLite
├── migrate_add_index.py   # 索引迁移（幂等）
├── conjugator.py          # 活用生成
├── jlpt_all.csv           # JLPT 词表
└── web/
    ├── main.py            # FastAPI 路由
    ├── lookup.py          # 查词 / 语法 / 例句查询
    ├── weakness.py        # 练习日志分析
    ├── ai_ollama.py       # 本机 Ollama 调用
    ├── audio_module.py      # 发音（仅标准库）
    ├── db.py              # 只读连接
    ├── conjugator.py      # 活用（root 版本的再导出）
    ├── pos_map.py         # 词性中文映射
    ├── romaji.py          # 假名 → 罗马字
    ├── static/            # index.html / app.js / style.css（无构建）
    └── cache/             # 运行期缓存（不入库）
```

### 1.2 运行时

```
Python 3.13（venv 在 web/.venv）
Node 24（仅用于前端语法检查与测试）
Ollama  http://127.0.0.1:11434，模型默认 qwen2.5:7b
        （OLLAMA_MODEL / OLLAMA_BASE / OLLAMA_TIMEOUT 可覆盖）
```

`web/requirements.txt`：

```
fastapi>=0.110
uvicorn[standard]>=0.27
```

**不要随意加依赖**，这个项目的卖点之一是零构建、轻依赖。

### 1.3 启动

```bash
cd jmdict/web
../.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765
# 或项目自带 start.ps1 / run.bat
```

打开 http://127.0.0.1:8765/

> 本机验证建议用 887x 端口，避免和常用实例抢端口。

### 1.4 一分钟冒烟

```bash
curl -s http://127.0.0.1:8765/api/jlpt/counts
# {"N5":831,"N4":797,"N3":2182,"N2":1945,"N1":4100}

curl -s "http://127.0.0.1:8765/api/search?q=%E9%A3%9F%E3%81%B9%E3%82%8B"
# [{"seq":1358280,"word_form":"食べる","kana":"たべる","gloss_first":"【他动2】吃"}]

curl -s http://127.0.0.1:8765/api/word/1358280 | head -c 200
curl -s http://127.0.0.1:8765/api/grammar/counts
# {"N5":154,"N4":100,"N3":118,"N2":65,"N1":26,"unknown":424}
```

### 1.5 回归四件套

```bash
node --check web/static/app.js
python -m py_compile web/main.py web/lookup.py web/audio_module.py
# 接口性能：自行起服务后按下面的基线表比对
# 前端 XSS 白名单回归（jsdom，15 个用例）随私有版维护，未纳入本仓库
```

| 指标 | 基线（偏差 >3× 需排查） |
|---|---|
| `/api/jlpt?level=N2&limit=100` | ~47 ms |
| `/api/jlpt?level=N3&limit=200` | ~45 ms |
| `/api/word/{seq}` | ~11 ms |
| `/api/search?q=...` | ~6 ms |
| `/api/exam/{id}`（缓存命中） | ~27 ms |
| `/api/audio/{seq}` 首次 / 二次 | ~460 ms / ~22 ms |
| `static/app.js` 大小 | ~92 KB |

### 1.6 页面路由

hash 路由：`#/`（查词）`#/word/{seq}`（词条）`#/study`（背单词）`#/grammar`（语法）`#/exam`（真题列表）`#/exam/{id}`（答题）`#/favorites`（生词本）。

> 已知坑：服务端 `/word`、`/study`、`/exam`、`/grammar` 都返回同一个 `index.html`，但 `route()` 只读 hash，直接访问 `/study` 会落在查词页（FIX-14 一并处理）。

---

## 2. 已完成的改造（10 项，不要重做）

### 2.1 性能：补 `word_forms(seq)` 索引 → 340×

| | |
|---|---|
| 问题 | `word_forms` 只有 `(word_form)` 索引，缺 `(seq)`。所有「按 seq 反查词形」的语句全表扫 499,461 行（约 40 ms/次） |
| 改动 | `CREATE INDEX idx_word_forms_seq ON word_forms(seq)` + `ANALYZE` |
| 位置 | `build_db.py`（新库自动带）、`migrate_add_index.py`（旧库幂等补） |
| 结果 | 库 77.6 → 83.3 MB；建索引 0.13 s |
| 验证 | `EXPLAIN QUERY PLAN SELECT DISTINCT word_form FROM word_forms WHERE seq = 1358280` → `SEARCH word_forms USING INDEX idx_word_forms_seq (seq=?)` |

**实测对比**

| 接口 | 改前 | 改后 | 倍数 |
|---|---|---|---|
| `/api/jlpt?level=N2&limit=100` | 16,014 ms（超时） | 47 ms | **340×** |
| `/api/word/1358280` | 767 ms | 10.9 ms | **70×** |
| `/api/search?q=食べる` | 191 ms | 6.3 ms | **30×** |

### 2.2 安全：真题富文本白名单清洗

后端原用正则黑名单过滤第三方 HTML，但 `\s+on[a-z]+\s*=` 要求 `on` 前有空白，`<svg/onload=alert(1)>` 用 `/` 分隔即可绕过，`<style>` / `<form>` 也不在名单里；前端有 8 处 `innerHTML` 直接注入这些内容。

现在前端新增 `sanitizeExamHtml()`（`static/app.js`）：

- `<template>` 惰性解析——不执行脚本、不加载资源
- 逐节点重建，白名单标签：`B STRONG I EM U S DEL INS BR P DIV SPAN SMALL SUB SUP MARK RUBY RB RT RP OL UL LI BLOCKQUOTE IMG`
- 属性只留 `class`；`IMG` 额外允许 `src`（必须 `https://`）与 `alt`；`on*` / `style` / `srcdoc` 一律丢弃
- 8 处出口全部替换：答题页 `examSubtitle` / `examTranslation` / `examPassage` / `examQuestion`，复查页 `rv-passage` / `rv-question` / 原文 / 翻译

验证：用 jsdom 加载真实的 `index.html` + `app.js`，跑 15 个绕过用例 **15/15 通过**，同时断言 `<u>` / `<ruby>` / `<br>` / `class` 与 https 图片被保留（该回归脚本随私有版维护）。

### 2.3 功能：词条发音（新增）

| | |
|---|---|
| 模块 | `web/audio_module.py`（**仅标准库**，未加依赖） |
| 路由 | `GET /api/audio/{seq}?voice=f002`、`GET /api/audio-status`、`POST /api/cache/clear` |
| 前端 | `bindDetailAudio()`；详情页头部「🔊 发音」按钮；样式在 `style.css` 末尾 |
| 行为 | 首次点击联网取一次 mp3 落盘（约 18 KB），之后纯本地；取不到 → 404 → 前端整块隐藏 |
| 实测 | 首次 461 ms，二次 21.9 ms |
| 缓存 | `web/cache/audio/*.mp3`（不入库） |

> 数据源的具体接口不在此文档讨论；凭据与实现细节不随本仓库发布。

### 2.4 健壮性：交卷不再丢数据

原 `submitExam()` 顺序是「渲染复查 → 建日志 → 落盘 → 切页」。`renderExamReview()` 里 `q.options.map()` 缺数组守卫，一道缺 `options` 的题会让**成绩、复查、日志全部丢失**并卡在答题页。

现在：先 `persistExamLog(buildExamLogEntry(stats))` 落盘，再分别 `try/catch` 包住 `renderExamResultTiming()` 与 `renderExamReview()`，最后无条件 `showExamPane("result")`；复查页 `options` 加 `Array.isArray` 守卫。

### 2.5 健壮性：详情页竞态

`openDetail()` 加了 `detailToken` 单调令牌，过期响应直接 `return`；`aiSeq` / `aiHistory` 改到确认渲染时才赋值——修掉「连点两个词旧响应覆盖新页面」和「页面显示 A、AI 上下文是 B」。

### 2.6 样式：一行修掉听力原文串题

`.exam-transcript { display: flex }` 会盖掉 UA 的 `[hidden] { display: none }`，导致非听力题残留上一题的「听力原文/中文翻译」。

`style.css` 顶部加了全局兜底：

```css
[hidden] { display: none !important; }
```

原有三处局部补丁（`.clear-btn[hidden]` / `.grammar-section[hidden]` / `.fc-accent[hidden]`）保留，不影响行为。

### 2.7 性能：词条缓存 + 例句查询

- `main.py` 的 `get_word_cached()` 用 `lru_cache(maxsize=1024)`；详情页 / AI 讲解 / 发音共用；配 `POST /api/cache/clear`
- `lookup.py` 例句查询 `LIKE '%'||?||'%'` → `instr(jpn, ?) > 0`，**13.7 → 6.3 ms**
- ⚠️ 重建 `jmdict.db` 后必须调 `/api/cache/clear`

### 2.8 文件改动

| 文件 | 状态 |
|---|---|
| `jmdict.db` | 修改（加索引） |
| `build_db.py` | 修改 |
| `migrate_add_index.py` | **新增** |
| `web/audio_module.py` | **新增** |
| `web/main.py` | 修改 |
| `web/lookup.py` | 修改 |
| `web/static/app.js` | 修改（+约 5 KB） |
| `web/static/style.css` | 修改（+约 1 KB） |
| `web/static/index.html` | 未改动 |
| 真题模块 | 未改动（公开版为模拟实现） |

### 2.9 主动放弃（别以为是漏了）

`list_jlpt` 的 `ORDER BY RANDOM()` 原计划改哈希抽样。实测加索引后 3.4 ms vs 3.1 ms，**差 0.3 ms**，不值得引入 seed 管理与行为差异 → 保持原样。

### 2.10 安全与鲁棒性测试发现并修复的 6 项（2026-10-22）

三轮测试（63 项功能/边界/并发 + 19 项安全面深挖），发现并修掉 6 个真实缺陷，最终 **63/63 + 0 FAIL**。

| ID | 缺陷 | 现象 | 修复 |
|---|---|---|---|
| R-01 | 整数溢出 → 500 | `/api/word/2^63`、`/api/audio/2^63`、`/api/grammar/2^63`、40 位数字 id 全部返回 `500 Internal Server Error`。根因：Python 无限精度 int 超出 SQLite int64，绑定时抛 `OverflowError`，它不属于 `sqlite3.Error`，全局 handler 接不住 | 定义 `MAX_INT64 = 2**63 - 1`，所有 URL 整数参数改为 `ApiPath(..., ge=0, le=MAX_INT64)` → 422 |
| R-02 | 任意试卷 id 直通外部接口（请求放大器） | `GET /api/exam/<任意字符串>` 每次都会真实请求外部（约 200 ms），未认证者可无限刷、消耗对方配额；`GET /api/exam/log` 本该 405，却被 `{exam_id}` 路由吞掉返回 502 | 试卷 id 加 `^[A-Za-z0-9_-]{1,64}$` 校验（非法 → 400）+ 保留名 `log/logs/list` → 405 + 真题模块加 **5 分钟负缓存**（结构拉取失败也写入） |
| R-03 | 缺安全响应头 | 无 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy | 加 `@app.middleware("http")` 统一注入。`index.html` 无内联脚本，故 `script-src` 收紧到 `'self'` |
| R-04 | **CSRF：POST 端点不校验 Content-Type** | `/api/weakness/analyze`、`/api/exam/log` 用裸 `request.body()` 读字节再 `json.loads`，所以 `text/plain`、`form-urlencoded`、无 Content-Type 全都接受。这类是浏览器「简单请求」，跨站表单不触发预检即可发送 → 任意网页能往本机 API 注入数据（伪造练习记录、清缓存） | 新增 `_require_json()`：Content-Type 必须 `application/json`，否则 **415**；`/api/cache/clear` 同样加固 |
| R-05 | 无 Host 头校验（DNS rebinding） | `Host: evil.example.com` 返回 200。攻击者把自有域名解析到 127.0.0.1，浏览器即可绕过同源策略读本机 API（含做题记录） | 中间件加回环白名单 `{127.0.0.1, localhost, ::1}`，其它 Host → **400** |
| R-06 | 并发首次拉同一卷子放大外部请求 | 8 并发首次请求 → **8 次真实外部拉取**（wall 2022 ms，各自 1.6–2.0 s） | 真题模块加 per-id 锁（singleflight）：只让一个线程真打外部，其余等落盘读缓存。8 并发 → **1 次外部**，wall **2022 → 1030 ms** |

**验证数据**

- 溢出类 4 个端点：500 → **422**
- `GET /api/exam/<坏 id>` 连续 4 次：**258 ms → 7 ms → 2 ms → 2 ms**（负缓存生效）
- CSRF：`text/plain` / `form-urlencoded` / 无 Content-Type → **415**；`application/json` → 200
- Host：非回环域名 → **400**；`127.0.0.1` / `localhost` → 200
- 并发拉卷：8 并发 wall **2022 → 1030 ms**，外部请求 8 → 1 次
- 正常卷子：55 ms / 130,468 bytes（无回归）
- 首页与答题页在 CSP 下渲染正常（无白屏）
- 并发 50×search / 30×word / 50×grammar-counts / 20×jlpt：**0 错误**，p95 ≤ 399 ms

**确认健壮、无需改动**：SQLi 4 种 payload 全无效（全参数化）；路径穿越 4 变体全 404；3MB body → 413；错误响应不含 traceback / SQL / 绝对路径；`/static/` 不列目录；文件名注入被转义；音频支持 Range（206）。

**仍开放**：`LIKE` 通配符未转义（`q=%` 匹配全部词条，被 limit 截断，不慢不崩）；后端 HTML 白名单收口（FIX-03 后半）；AI 端点串行排队（FIX-08，实测 3 并发 2.4→6.7 s，行为正确但占线程）。

---

## 3. 待办清单（16 项）

> 行号会随改动漂移，请用关键词定位。

### P0 · 数据安全（约半天）

**FIX-01 · 版本库忽略了本地凭据文件**

`web/.git` 是零提交仓库，根目录缺 `.gitignore`。含 session token 的本地配置文件、`.venv/`、`cache/`、`*.bak` 全部处于未跟踪但可被 `git add .` 收走的状态。

**做法**：删 `web/.git`（推荐，本仓库为唯一源头），或补 `.gitignore`。
**验收**：`git status --porcelain` 不再列出凭据文件、`.venv`、缓存、`.bak`。

**FIX-02 · `static/*.bak` 可被 HTTP 下载**

历史备份放在 `StaticFiles` 挂载目录里，例如 `/static/app.js.bak-pre-old` 可被任意人取走。
**做法**：移到 `web/_archive/`。**验收**：该 URL 返回 404，`static/` 下无 `*.bak*`。

**FIX-03 · 后端仍是黑名单（CSP 已随 R-03 完成）**

前端白名单是唯一防线；后端清洗函数仍可被 `<svg/onload>` 绕过。

- **已完成**：`security_headers` 中间件已注入 CSP / X-Frame-Options / nosniff / Referrer-Policy，`curl -I /` 可验证
- **待做**：在清洗函数出口追加 `lxml` 白名单收口

**验收**：前端 15 个 XSS 用例仍全过；后端单测断言 `<svg/onload=alert(1)>x` 的输出不含 `onload` 且保留 `x`。

### P1 · 体感与架构

**FIX-04 · `db.py` 硬编码绝对路径** —— 换机器即 `DatabaseUnavailable`。改为 `os.environ.get("JMDICT_DB", <脚本上级目录>/jmdict.db)`，报错带实际解析路径。

**FIX-05 · 四段 N+1 串行 fetch（体感收益最大）**

`renderFavorites()`、`refreshStudyHome()`、复习队列、单卡补全四处同构：先清空列表 → `for` 循环逐条 `await fetch` → 逐条吞错。收藏 N 个词 = N 个 RTT 白屏；全失败时列表隐藏，既无内容也无空态。

```js
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
async function fetchWords(seqs) {
  const rs = await Promise.allSettled(seqs.map((s) => api(`/api/word/${s}`)));
  return rs.filter((r) => r.status === "fulfilled").map((r) => cardFromWord(r.value));
}
```

**验收**：收藏 10 词 → Network 显示 10 个并发请求；后端停掉时显示失败文案而非白屏。

**FIX-06 · 刷新丢路由状态**

`route()` 只读 hash，练习队列与考试答案是内存变量：刷新 `#/study/session` 丢整轮练习，刷新 `#/exam/{id}` 把已选答案清零。
**做法**：`sessionStorage` 存 `study:session`（queue/index/mode）与 `exam:state`（examId/answers/index/seconds），`route()` 分支前恢复。

**FIX-07 · 查词交互**：回车无动作（加 `keydown` + `Enter`，先 `clearTimeout(debounceTimer)`）；点热词 chip 发两次请求；双请求无 `AbortController`。

**FIX-08 · AI 端点同步阻塞**：`/api/ai/*` 是同步 `def` + `urlopen(timeout=120)`，两个并发请求占住两个线程 120 秒。
**做法**：`threading.Semaphore(1)` + 超时降到 60 s；或改 `async def` + `httpx.AsyncClient`（需加依赖）。另可给 `(seq, question)` 加结果 LRU。
**验收**：2 个并发请求排队；Ollama 停掉后 3 秒内 503。

### P2 · 健壮性

**FIX-09 · `weakness.py` 日志双写**：同时写单文件 `*.json` 与追加 `sessions.jsonl`，读时靠 `path.stem` 去重；`LOG_LOCK` 内做磁盘 IO 且无 `fsync`；直接改调用方 `payload`。建议只写 jsonl + `dict()` 拷贝 + 一次性迁移老数据。

**FIX-10 · 真题模块重试/负缓存/限速**：有失败大题时不写缓存 → 每次全量重拉（建议单大题负缓存 TTL 10 分钟）；无重试退避（429/5xx 重试 2 次）；`ThreadPoolExecutor(max_workers=6)` 无全局限速（建议 `Semaphore(3)`）。

**FIX-11 · 语法 424/887（32%）等级未知**：`/api/grammar/counts` 的 `unknown` 项。按 N 级筛选会整批漏掉。建议规则映射 + 人工补，无法判定的引入 `unrated` 第三档并在前端单独分组。

**FIX-12 · 前端零散 7 处**

| # | 问题 |
|---|---|
| 1 | 薄弱点卡把后端字符串直插 DOM（`/api/weakness/analyze` 会回传客户端 POST 的数据）→ `Number()` + clamp |
| 2 | `items = res.ok ? await res.json() : []` 把 HTTP 500 显示成「无结果」 |
| 3 | 听力音频 `src` 无协议校验、无 `onerror` |
| 4 | AI 历史只增不减，全量回传会溢出上下文 → `slice(-8)` + 上限 40 |
| 5 | 收藏页全失败分支：列表与空态都不显示 |
| 6 | 两处死代码（恒定 hidden 的元素、0 引用的变量） |
| 7 | 一个全局变量兼作取牌策略与记账开关，靠临时改值绕过 → 抽函数传参 |

**FIX-13 · 后端零散 7 处**

| # | 问题 |
|---|---|
| 1 | `sqlite3.Error` 全局转 503，把编程错误也掩盖 → 只对 `OperationalError`/`DatabaseError` 转 503 |
| 2 | JLPT 等级查询逐 form 查（N+1）→ `WHERE word_form IN (...)` |
| 3 | `search()` 精确分支先 `fetchall()` 再切片 → SQL 里 `LIMIT ?` |
| 4 | 活用生成 `except Exception` 全吞 → 收窄 + `logging.exception` |
| 5 | 一个函数里局部变量与数据库连接同名 |
| 6 | 语法检索/列表三分支重复 SQL → 参数化合并 |
| 7 | 无 `/healthz` → 加汇总 db/ollama/audio/缓存的端点 |

### P3 · 收尾

**FIX-14 · 可访问性与语义**：`role="tablist"` 子按钮缺 `role="tab"`/`aria-selected`；搜索框只有 `placeholder` 无 `label`；结果项无 `tabindex`/`role` 键盘不可选；`button` 内嵌块级 `div`；无 `noscript`；服务端路由与 hash 路由不一致。

**FIX-15 · 工程基建**：无自动化测试（建议 `tests/` + pytest + `TestClient`，覆盖查词/词条/词表/发音（mock 网络）/日志大小上限/后端 sanitize）；`print()` 散落改 `logging`；可跑 `pyright`/`mypy` 收 type error。

**FIX-16 · 与私有版的同步**：本仓库是脱敏公开版（真题为模拟实现、不含词库与凭据）。私有版的通用改动（`app.js`、`style.css`、`audio_module.py`、`migrate_add_index.py`）可同步过来；`main.py`/`lookup.py` 合并时跳过真题模块相关 import；**不要覆盖本仓库的 `.gitignore`**。

---

## 4. 数据层事实

### 4.1 表与规模

| 表 | 行数 | 列 |
|---|---|---|
| `entries` | 218,908 | `seq`(PK) `kanji` `kana`（`\|` 分隔多值） |
| `senses` | 253,792 | `seq` `pos` `gloss`（`\|` 分隔） |
| `word_forms` | 499,461 | `word_form` `seq` |
| `examples` | 32,428 | `id` `jpn` `cmn` |
| `gloss_zh` | 23,101 | `word_form` `accent` `gloss` |
| `jlpt` | 8,138 | `word_form` `level` |
| `grammar` | 100 | `id` `pattern` `explain` `level` `connection` |

### 4.2 索引

```
entries     idx_entries_kanji, idx_entries_kana
senses      idx_senses_seq
word_forms  idx_word_forms(word_form), idx_word_forms_seq(seq)   ← 本轮新增
examples    idx_examples_jpn
gloss_zh    autoindex(word_form)
jlpt        autoindex(word_form)
```

### 4.3 连接

`db.py` 用 `file:...?mode=ro` 只读打开 + `sqlite3.Row`。`lookup.py` 的 `_db()` 是 thread-local 连接，`SELECT 1` 探活失败自动重开。

PRAGMA 为默认值。**实测：加 `cache_size=-65536` + `mmap_size=256MB` 对当前查询无可测收益**（瓶颈是缺索引，已解决）。

### 4.4 已知反模式（当前可接受）

- 子串全扫：中文/英文反查、例句、语法检索都是 `LIKE '%q%'` 或 `instr`，当前 6–80 ms。要质变得上 FTS5 + trigram，属独立任务。
- `list_jlpt` 是 N+1（每行再查 4 张表）。索引补齐后总 47 ms，已不是问题。

---

## 5. 回滚

改动前的备份按 `*.bak-pre-<批次>` 命名（数据库另存 `*.bak-pre-index-<日期>`）。回滚即覆盖回去；新增文件（`audio_module.py`、`migrate_add_index.py`、`cache/audio/`）直接删除即可。

---

## 6. 边界与禁区

**不要做**

1. 不要 `git commit` / `git push`，除非维护者明确要求。
2. 不要改 `jmdict.db` 的表结构或数据；索引可加（有 `migrate_add_index.py`），改数据前先备份。
3. 不要把任何凭据、token、密钥写进文档、日志或提交。
4. 不要直接 `innerHTML` 拼第三方 HTML，一律先过 `sanitizeExamHtml()`。
5. 不要动 8765 上可能在跑的实例；验证用 887x。
6. `ai_ollama.py` 的 prompt 约束是有意写的（不许编造 JLPT 等级或音调数字），改 prompt 时保留。

**边界**

本仓库是**个人学习用途**的脱敏公开版：真题为模拟实现，不含词库、不含任何第三方凭据。词典内容版权属于 JMdict / EDRDG（CC-BY-SA 4.0），例句来自 Tatoeba（CC-BY 2.0 FR），发布与再分发时保留相应署名。

---

## 7. 建议批次

| 批次 | 任务 | 预估 | 关键验收 |
|---|---|---|---|
| 1 卫生 | FIX-01、02、04 | 半天 | `git status` 干净 / `.bak` 404 / 换路径能启动 |
| 2 后端小修 | FIX-13、09 | 半天 | 性能基线不劣化 / `/healthz` 200 / 交卷只多一行 jsonl |
| 3 前端重构 | FIX-05、06、07、12 | 1–2 天 | 收藏 10 词并发 / 刷新不丢状态 / 15/15 仍通过 |
| 4 异步与外部依赖 | FIX-08、10、03 | 1 天 | 并发 AI 排队 / 数据源挂掉 3 s 报错 / CSP 头存在 |
| 5 内容与收尾 | FIX-11、14、15、16 | 1–2 天 | 测试全绿 / unknown < 100 / 仓库干净 |

---

## 附录 A · 评估过但不做

| 项 | 结论 |
|---|---|
| `list_jlpt` 的 `ORDER BY RANDOM()` 改哈希抽样 | 差 0.3 ms，不值 |
| PRAGMA `cache_size` / `mmap_size` | 无可测收益 |
| `list_jlpt` 改单条 JOIN | 收益 < 20 ms |
| FTS5 + trigram | 建库与迁移复杂度升一档，当前 6–80 ms 可接受，独立任务 |
| 在线查词兜底 | 第三方接口上限 5 条、无分页，比本地 218k 词条差 |

## 附录 B · 一页速记

- **已做**：索引（340×）、XSS 白名单（15/15）、离线发音、交卷不丢数据、竞态修复、`[hidden]` 一行、词条缓存、例句 `instr`。
- **最急**：FIX-01（凭据文件）、FIX-02（`.bak` 外泄）、FIX-04（路径硬编码）——都是半小时级。
- **最值**：FIX-05（收藏/学习页白屏与串行请求）。
- **别碰**：附录 A 那五项。
- **改完必跑**：第 1.5 节四条命令。
