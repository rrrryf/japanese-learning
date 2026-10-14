# 日语学习

本地推理优先的日语学习 **AI 应用**：词典 + 语法 + 自建 JLPT 模考 + 薄弱点复盘，接入 Ollama 本地小模型（默认 `tinyswallow` / TinySwallow）做按需讲解。

> 个人 JLPT N2 备考工具 / 作品集项目。无强制云端 API，数据与推理均可离线。

## 如何跑起来（Windows 一键）

最短路径：

1. **准备词库**：把 `jmdict.db` 放到**本仓库根目录**（与 `start.ps1` 同级）。本仓库不附带完整库（约 80MB，含 JMdict 衍生数据）。
2. **安装依赖**：
   ```powershell
   cd web
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   cd ..
   ```
3. **（可选）本地讲解模型**：先安装并启动 [Ollama](https://ollama.com)，再拉取：
   ```powershell
   ollama pull tinyswallow
   ```
4. **一键启动**：
   ```powershell
   .\start.ps1
   # 或
   .\run.bat
   ```
5. 浏览器打开 **http://127.0.0.1:8765/**

没有现成 `jmdict.db` 时，可从 [EDRDG JMdict](https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project) 下载 `JMdict_e.xml` 放到仓库根目录后运行 `python build_db.py`（仅基础 entries/senses，不含完整语法增强）。

## 功能亮点

| 模块 | 说明 |
|------|------|
| 本地 LLM 讲解 | 词条 / 语法详情页「本地讲解」按钮 → Ollama TinySwallow（`tinyswallow`，按需推理约 2–5s） |
| 讲解评测 | `scripts/eval_explain.py` 抽样生成 JSON，支持人工打分闭环 |
| 薄弱点复盘 | 根据模考日志按科目统计正确率，反哺练习建议与每日计划 |
| 自建 JLPT 模考 | 本地 JSON 题库（`web/data/mock_exams/`），支持词汇 / 文法 / 读解专项 |
| 词典 | JMdict → SQLite：检索 / 活用 / 中日释义 |
| 语法 | ~887 条句型：接续 / 意思 / N5–N1；详情独立整页 |

## 技术栈

- **后端**：Python 3 + FastAPI + Uvicorn
- **前端**：原生 SPA（`web/static/`，hash 路由）
- **数据**：SQLite `jmdict.db`（只读，放在仓库根目录）
- **本地模型**：Ollama + Sakana TinySwallow 1.5B（日语蒸馏；拉取名 `tinyswallow`）
- **模考**：本地 mock JSON（无第三方付费题库依赖）

## 环境变量（可选）

| 变量 | 默认 | 说明 |
|------|------|------|
| `OLLAMA_BASE` | `http://127.0.0.1:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | `tinyswallow` | 模型名（CLI / Ollama tag） |
| `OLLAMA_TIMEOUT` | `120` | 超时（秒） |

## 目录结构

```
japanese-learning/
  README.md
  start.ps1 / run.bat       # 一键启动
  build_db.py               # JMdict XML → SQLite（基础表）
  jmdict.db                 # 自行放置（不入库）
  data/                     # 开放语法参考等
  scripts/eval_explain.py   # 本地讲解评测
  docs/screenshots/         # 界面截图
  web/
    main.py                 # FastAPI
    ai_ollama.py            # 本地讲解
    mock_exam.py            # 自建模考
    weakness.py             # 薄弱点
    data/mock_exams/        # 模考 JSON
    static/                 # 前端
    cache/exam-logs/        # 练习日志（演示用）
```

## 模考数据

题目位于 `web/data/mock_exams/`，均为**自建练习内容**，用于演示刷题与薄弱点流程。可按同格式自行增补 JSON。

## 讲解评测

```powershell
.\web\.venv\Scripts\python scripts\eval_explain.py --limit 10
```

结果写入 `data/explain_eval_<时间戳>.json`，可在其中填写 `scores.accuracy` / `usefulness`（1–5）。

## 数据来源与协议

- **JMdict / EDICT**：EDRDG，[CC-BY-SA 4.0](https://www.edrdg.org/)
- **开放语法参考**：`data/openjlpt_grammar_*.json` 等
- **模考题目**：本仓库自建示例，仅供个人学习演示

代码可用于作品集展示；词库数据请遵守上游协议，勿二次商用分发未授权内容。

## License

代码部分可按作品集用途使用。词典数据版权归原作者 / EDRDG。
