# Cursor 交接简报

> 把这份文件喂给 Cursor（`@docs/CURSOR-BRIEF.md`），它就能接手这个项目。
> 自包含：不需要再补充背景。读完先复述，确认无误再动手。

---

## 0. 你的第一件事

读完这份文档后，用四句话回答，然后**停下等我确认**：

1. 这个项目是什么，改完之后怎么验证
2. 有几个副本，你默认改哪个
3. 硬约束有哪几条（尤其是不许提交什么、不许删什么）
4. 你打算从哪个任务开始，为什么

不要跳过这一步直接改代码。

---

## 1. 项目是什么

本地优先的日语学习工具。查词、语法浏览、JLPT 模考、薄弱点复盘、可选的本地 AI 讲解。
**所有数据都在本机**，不联网也能用（除了 AI 需要本机 Ollama）。

```
技术栈：FastAPI + 原生 JS（无构建）+ SQLite + 可选 Ollama
规模：约 6000 行（后端 2500 / 前端 3200 / 脚本 800）
用户：单人自用 + 开源分发
```

### 两个副本，别搞混

| | 私有版 | 公开版（**默认改这个**） |
|---|---|---|
| 路径 | `<自用版目录>` | `<本仓库目录>` |
| 端口 | 8765 | 8766 |
| 模考 | 在线真题（自用版，付费，需账号） | 本地 JSON 示例卷 + 用户导入 |
| 语法数据 | thesaurus 887 条 | `data/openjlpt_grammar_*.json` 100 条 |
| 用途 | 自己刷题 | 对外分发 |

两边 `web/lookup.py` 高度相似但**已经分叉**。不要互相覆盖，不要假设改一处另一处也生效。

---

## 2. 代码结构

```
web/
  main.py          路由 + Pydantic 模型 + 安全中间件（CSP/Host/CSRF）   ~430 行
  lookup.py        所有 SQL：查词 / 搜索 / 语法 / JLPT 列表 / 例句      ~780 行
  mock_exam.py     本地卷子的读取、导入、校验、删除                      ~260 行
  weakness.py      练习日志读写 + 正确率统计                            ~300 行
  ai_ollama.py     Ollama 调用（可选，不可用时降级）
  static/
    index.html     ~340 行，无内联脚本（CSP script-src 'self'）
    app.js         ~2700 行，单文件 SPA，hash 路由
    style.css      ~2700 行，CSS 变量
conjugator.py      假名活用生成（纯函数，最值得加测试）
setup_data.py      一键建库（下载 → 解析 → 导入 → 校验）
build_db.py        建表 + 建索引
tests/
  test_units.py    30 项纯函数测试（不需要词典库）
  test_api.py      72 项接口回归（需要服务 + 词典）
run_tests.ps1      起服务 → 跑 test_api → 停服务
.github/workflows/tests.yml
```

**没有的东西（这是设计决定，不要加）**：打包器、前端框架、TypeScript、CSS 预处理器、
ORM、pytest、Docker。

---

## 3. 数据全貌

`jmdict.db` 约 84 MB，本机生成，不进版本库。

| 表 | 行数 | 来源 | 许可 |
|---|---|---|---|
| `entries` / `senses` / `word_forms` | 218,945 / 253,841 / 499,554 | JMdict（本机下载生成） | CC-BY-SA 4.0 |
| `gloss_zh` | 24,522 | thesaurus 23,101 + 本项目补 1,421 | Unlicense / 本项目 |
| `examples` | 32,424 | Tatoeba | CC-BY 2.0 FR |
| `jlpt` | 8,138 | JLPT 词表整理 | 事实性数据 |
| `grammar` | 100 | `data/openjlpt_grammar_*.json` | 本项目 |

### 中文释义覆盖率（重要）

全库只有 **6.2%** 有中文——上游 thesaurus 只覆盖 11,924 个词条，剩下的是生僻词、专有名词、古语。
但 JLPT 五个等级已经用本机模型补到 98%+：

```
N5 98.8%   N4 99.8%   N3 98.7%   N2 98.4%   N1 98.9%
```

余下约 2%（约 100 个词）是难翻译的编号词或语法助词，不必强求。

### 索引（性能命脉）

```sql
idx_word_forms(word_form)     -- 词形反查 seq
idx_word_forms_seq(seq)       -- seq 反查词形 ← 删了 /api/jlpt 从 47ms 变 16 秒
idx_grammar_level(level)
idx_examples_jpn(jpn)
```

---

## 4. 当前性能实测

改动后用同一批查询对比，不要只看"加了索引"。

| 端点 | 耗时 | 备注 |
|---|---|---|
| `/api/search?q=食べる` | 14ms | 含假名，已跳过中文反查 |
| `/api/search?q=たべる` | 2ms | |
| `/api/search?q=吃` | ~200ms | 纯中文必须扫 2.4 万行 `gloss_zh`，**已知慢点** |
| `/api/word/<seq>` | 15ms | |
| `/api/jlpt?limit=100` | 27ms | CTE 先挑 seq 再回表 |
| `/api/exam/<id>` | 5–20ms | 本地 JSON |
| `/api/ai/explain` | 5–10s | 7B 模型，正常 |

---

## 5. 上一轮已经修完的 18 项（不要改回去）

这些是踩过的坑，改动时保持现状。括号里是**为什么**。

### P0 · 崩溃与错输出

1. **AI 端点整数上限** — `AiExplainBody.seq` / `AiGrammarBody.grammar_id` 有 `ge=0, le=MAX_INT64`。
   超过 int64 会让 SQLite 抛 `OverflowError`，它不是 `sqlite3.Error`，异常处理器接不住 → 500。
2. **IPv6 Host 白名单** — `[::1]:8765` 不能直接 `split(":")`（会得到 `[`）。先剥方括号。
3. **サ变活用保留词干** — `conjugate("あいする", "suru")` 必须返回 `あいします` 而不是 `します`。
   `guess()` 认任何 `〜する` 结尾；`_detect_verb_type` 还认
   `"noun or participle which takes the aux. verb suru"`（约 1.7 万条：勉強/掃除/料理）。
   另外 `たべる` 的い段判断要含浊音，否则被误判成五段。

### P1 · 数据质量

4. **模考答案分散** — 打乱后 N3 是 `{0:1,1:1,2:1,3:1}`。`test_units.py` 会检查单一选项 ≤60%。
5. **语法例句入库** — `grammar.examples` 存 `[{ja,en}]` 的 JSON，100/100 条有。
6. **语法中文释义** — `grammar.explain_zh`，100/100 条有。英文单独标「英文」，不混在中文标题下。
7. **例句匹配** — 长词形优先；单字汉字只认句首/标点后（否则「日」会命中「今日は」）；
   单字假名跳过。
8. **听力专项** — 列表项带 `subjects`，没有听力题的等级把 chip 标灰。
9. **中文释义覆盖** — 见上表，JLPT 已 98%+。

### P2 · 性能

10. **搜索跳过无谓全表扫** — 查询含假名且已有结果时，不调 `_search_gloss_zh`（208ms → 14ms）。
11. **中文反查排序** — 按 JLPT 等级再按释义长度，`食べる` 稳定在前 2。
12. **JLPT 列表去 N+1** — CTE 先随机挑 seq 再回表（195ms → 27ms）。
13. **练习日志** — 只写单个 `.json`，不再双写 `sessions.jsonl`；读 jsonl 只取末尾 256KB。

### P3 · 工程化

14. `/api/grammar?level=XX` 返回 **400**（与 `/api/jlpt` 一致），保留 `unknown`。
15. 导入结果成功/失败分开显示；同秒 id 碰撞用随机后缀。
16. `/favicon.ico` 返 svg（不再 404）。
17. `tests/test_units.py` 30 项 + GitHub Actions（push 跑单元测试，手动触发跑接口回归）。
18. README 与 tests/README 已同步现状。

---

## 6. 待办任务（按性价比排序）

每项都写了**改哪里、怎么验收**。做完一项就跑测试，再开始下一项。

### T1 · 例句查询加索引 ⭐ 最值得做

**问题**：`lookup.py` 的 `_fetch_examples` 用 `instr(jpn, ?)`，3.2 万行全表扫，占 `/api/word` 响应时间一半。

**做法**：建 FTS5 虚拟表 `examples_fts(jpn)`，`_fetch_examples` 改走 `MATCH`。
需要同步改 `build_db.py`（建表）、`setup_data.py`（导入后重建索引），
并写一个迁移脚本（参考 `migrate_add_index.py` 的幂等写法）。

**验收**：查 10 个常见词的 `/api/word`，例句部分 < 12ms；贴前后对比；两套测试 0 fail。

**不要做**：不要改 `_fetch_examples` 的签名和返回结构（`[{jpn, cmn}]`）。

---

### T2 · 语法接续中文化

**现状**：`grammar.connection` 是英文 `Clause A + が + Clause B`，前端已加「英文」标注。

**做法**：加 `connection_zh` 列。100 条里 80 条是固定模式，用规则翻译即可：
`Clause` → `从句`、`Verb-stem` → `动词词干`、`Noun` → `名词`、`Adjective` → `形容词`、
`+` 保留。剩下 20 条手写。

**验收**：100/100 有中文；前端接续区优先显示中文；`test_units.py` 0 fail。

---

### T3 · 刷新页面丢状态 ⭐ 用户可感知

**现状**：在 `#/exam/<id>` 做到第 5 题按 F5，回到第 1 题；等级下拉和专项筛选也重置。

**做法**：把 `examLevel` / `examDrillSubject` / 当前题号写进 `sessionStorage`，
`app.js` 初始化时读回。**不要**存答题进度（那属于练习日志，已经存了）。

**验收**：做到第 5 题刷新，仍在第 5 题且已选项保留；等级和专项不重置。

---

### T4 · 私有版单元测试适配

**现状**：私有版没有 `mock_exam.py`（走在线真题接口），直接复制 `test_units.py` 会
`ModuleNotFoundError`。

**做法**：`mock_exam` 相关用例用 `try: import mock_exam / except ImportError: skip` 包起来。

**验收**：两版各自 `python tests/test_units.py` 都 0 fail。

---

### T5 · 搜索排序（用现成数据）

**现状**：搜「吃」第一条是麻将用语 `チー`（「吃」在 JMdict 里确实是独立词条，精确匹配优先），
`食べる` 排第 2。

**做法**：用 `examples` 表统计每个词形的出现次数当频次权重，次数多的排前面。
不需要外部词频表。

**验收**：搜「吃」「漂亮」「おいしい」，第 1 条都是 JLPT N5–N3 的常见词。

---

### T6 · 移动端布局

**现状**：只在 1280px 验证过。375px 下 `exam-drill-chips` 换行、`ld-section` padding 偏大。

**做法**：加 `@media (max-width: 640px)`。重点三页：查词详情、模考答题、语法列表。

**验收**：375px 宽无横向滚动、按钮可点、题干不截断。

---

### T7 · 数据导出与备份

**现状**：练习日志在 `web/cache/exam-logs/`，换机器就丢。

**做法**：前端加「导出我的记录」按钮，下载 JSON（练习日志 + 生词本）；
可选再加导入。

**验收**：导出再导入，薄弱点统计数字一致。

---

### T8 · 语法条目扩容（先找数据源）

**现状**：只有 100 条（N5–N1 各 20）。真实 JLPT 语法点约 500+。

**警告**：**不要用 LLM 编语法条目**。语法解释错了比没有更糟。
必须先找到有明确许可的数据源，再谈扩容。

---

## 7. 硬约束

### 不许提交

```
jmdict.db、jmdict.db.bak、JMdict_e.xml、JMdict_e.gz   （共约 150MB，已在 .gitignore）
web/cache/imported_exams/                              （可能是付费题库内容，只在本地）
web/cache/exam-logs/*.json                             （练习记录，除两个 demo 外）
```

`git add -f` 也不行。不要写"导出题库/分享题库"这类功能。

### 不许删

`idx_word_forms_seq` —— 见第 3 节。

### 不许放宽

`mock_exam._normalize` 会丢弃"选项不足 2 个 / answer 越界 / 答案非数字"的题。
这是数据质量护栏，不要为了"多导入几套"而放宽。

### 必须保持

- 整数参数夹紧 `ge=0, le=MAX_INT64`（URL 和 JSON body 都要）
- POST 端点要求 `Content-Type: application/json`（挡 CSRF 简单请求）
- Host 白名单处理 IPv6 方括号
- `conjugator` 的 suru 分支保留词干
- 无 `jmdict.db` 时服务仍能启动（`/api/*` 返 503，前端显示横幅）
- 无 Ollama 时 AI 端点 503，要 2 秒内失败，不要长超时重试
- 前端所有用户文本走 `escapeHtml()`；题干走 `sanitizeExamHtml()` 白名单

---

## 8. 环境坑（Windows）

1. **`.ps1` 必须 UTF-8 with BOM**。否则 PowerShell 5.1 按 GBK 解析中文注释，
   报 `Unexpected token '}'` 这种莫名其妙的语法错误。
2. **Python 输出要 UTF-8**。词典里有 `⓪`，GBK 控制台会 `UnicodeEncodeError`。
   脚本开头加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，
   或在 PowerShell 里 `$env:PYTHONIOENCODING='utf-8'`。
3. **端口**：8765 私有版、8766 公开版。起服务前先看端口占用，
   别把公开版起在 8765 上——用户会以为私有版的数据丢了。
4. **`lru_cache` 与重建库**：`main.py` 的 `get_word_cached` 是 `lru_cache(1024)`。
   重建 `jmdict.db` 后必须 `POST /api/cache/clear`，否则读到旧结构。

---

## 9. 验证方式

改完**必须**跑这两条，都要 0 fail：

```powershell
# 单元测试（只要 Python，30 项）
$env:PYTHONIOENCODING='utf-8'; python tests/test_units.py

# 接口回归（自己起服务、测 72 项、关掉）
.\run_tests.ps1
```

`run_tests.ps1` 退出码非 0 就是有问题。把最后两行汇总贴出来，**不要只说"测试通过"**。

改数据相关（`data/`、`build_db.py`、`setup_data.py`）还要跑一次：

```powershell
python setup_data.py    # 幂等，会跳过已下载的 JMdict
```

期望输出里 `entries/senses/word_forms/grammar/gloss_zh/examples` 全部 `ok`。

---

## 10. 怎么跟我配合

### 一次一个任务

不要一次接 5 个任务。做完 T1、跑测试、我确认、再做 T2。
多任务并行会让改动互相干扰（改 A 的时候顺手动 B 的接口）。

### 范围限制

每个任务我都会说改哪几个文件。**其他文件不要动**，包括：
不加类型标注、不改函数名、不格式化整个文件、不调整 import 顺序。

发现别的问题，写在回复末尾的「发现的其它问题」里，不要直接改。

### 用数字验收

我会给具体指标（如"从 76ms 降到 30ms 以内"）。改完要贴实测数字，
不要用"更快了""优化完成"这种描述。

### 测试失败时

先怀疑代码，不要改测试断言。如果确实认为测试写错了，
说明理由并等确认，不要顺手改掉。

---

## 11. 快速参考

```powershell
# 启动
.\start.ps1                    # 自动检测端口、缺库会提示

# 测试
python tests/test_units.py     # 30 项
.\run_tests.ps1                # 72 项接口回归
.\run_tests.ps1 -WithAi        # 额外测一次 Ollama（6-10 秒）

# 数据
python setup_data.py                                   # 一键建库（幂等）
python scripts/fill_gloss_zh.py --db jmdict.db --dry-run --limit 10   # 看补释义效果
python scripts/export_data.py                          # 从完整库导出 data/ 下三份

# 服务
Get-NetTCPConnection -LocalPort 8766 -State Listen     # 查端口占用
```

关键 URL：`/` 首页 · `/api/search?q=` 搜索 · `/api/word/<seq>` 词条 ·
`/api/grammar/<id>` 语法 · `/api/exam/<id>` 卷子 · `/api/jlpt?level=N2&limit=100` 背单词
