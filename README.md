# 日语学习

本地推理优先的日语学习应用：**词典 + 语法 + JLPT 模考 + 薄弱点复盘**，可选接入 Ollama 本地小模型做按需讲解。

> 个人 JLPT 备考工具 / 作品集项目。默认不依赖任何云端 API。

---

## 三步跑起来（Windows）

```powershell
# 1. 准备数据（首次运行，会自动下载词库，约 30MB）
python setup_data.py

# 2. 装依赖并启动（首次会自动建虚拟环境）
.\start.ps1

# 3. 浏览器打开
#    http://127.0.0.1:8765/
```

`run.bat` 与 `start.ps1` 等价，双击即可。

### 关于第 1 步

`setup_data.py` 做四件事：

| 步骤 | 说明 |
|---|---|
| 下载词库 | 从 EDRDG 拉 `JMdict_e.gz`（约 30MB）并解压成 `JMdict_e.xml` |
| 建 SQLite | 调用 `build_db.py` 生成 `jmdict.db`（词条 / 义项 / 词形，约 80MB） |
| 导入语法 | 把仓库内 `data/openjlpt_grammar_n1..n5.json` 导入 `grammar` 表（N5–N1 各 20 条，共 100 条） |
| 校验 | 打印各表行数，确认接口可用 |

脚本幂等，可重复运行。如果网络受限，也可以手动下载 `JMdict_e.xml` 放到项目根目录后再跑一次。

**没有 `jmdict.db` 时**：服务仍能启动，页面顶部会出现一条黄色提示条，查词与语法返回「词典库未就绪」——不会白屏。

### 可选：本地讲解模型

```powershell
# 先安装 Ollama（https://ollama.com），然后
ollama pull qwen2.5:7b
```

模型可换：`$env:OLLAMA_MODEL='qwen2.5:7b'` 后再启动。

> **关于模型**：默认 `qwen2.5:7b`，讲解质量可用，但 7B 单次讲解约 6–10 秒。
> 想更快可换更小的模型（例如 `qwen2.5:3b`），代价是讲解质量下降。
> 换模型只需设置 `$env:OLLAMA_MODEL='模型名'`，前端显示会自动跟随。
> 任何本地小模型的讲解都可能出错——实测 7B 级仍会偶发混淆自他动词、夹带英文单词。
> **请当作辅助参考**，词形、读音、释义以词典区和例句为准。

---

## 功能

| 模块 | 说明 | 数据来源 |
|---|---|---|
| 词典 | 日文/假名/中文反查、活用表、罗马音 | JMdict（本地 SQLite） |
| 语法 | 100 条句型（N5–N1 各 20 条示例），接续/释义/例句 | 仓库内 `data/openjlpt_grammar_*.json` |
| 模考 | 词汇 / 文法 / 读解专项，交卷后进「薄弱点复盘」 | 仓库内 `web/data/mock_exams/`（示例卷） |
| 薄弱点 | 按科目统计正确率，反哺每日计划 | 本地练习日志 |
| 本地讲解 | 词条/语法详情页「本地讲解」按钮 → Ollama | 本机 Ollama |

### 关于示例卷

`web/data/mock_exams/` 目前提供 **N2、N3 各一套示例卷**，用于演示刷题与复盘流程。N1 / N4 / N5 为空（下拉会显示「暂无症状卷」）。按同样 JSON 格式可自行增补：

```
web/data/mock_exams/
  lists.json                 # 各等级卷子清单
  mock-n2-practice.json      # 一套卷子的题目
```

### 数据构成

| 表 | 内容 | 来源 |
|---|---|---|
| `entries` / `senses` / `word_forms` | 218,945 词条 / 253,841 义项 / 499,554 词形 | JMdict（本机下载生成，约 80 MB） |
| `grammar` | 100 条语法（N5–N1 各 20） | `data/openjlpt_grammar_*.json` |
| `jlpt` | 8,138 条分级词表 | `data/jlpt_words.jsonl.gz`（37 KB） |
| `gloss_zh` | 23,101 条中文释义 + 音调 | `data/gloss_zh.jsonl.gz`（346 KB） |
| `examples` | 32,424 条双语例句 | `data/examples.jsonl.gz`（970 KB） |

三份 gzip JSONL 随仓库分发（合计约 1.4 MB），`setup_data.py` 会自动导入；完整词库仍在你本机生成。

导出脚本在 `scripts/export_data.py`：如果你有自己的完整词库，可以重跑它刷新这些数据文件。

---

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `JMDICT_DB` | 项目根 `jmdict.db` | 自定义词库路径 |
| `JMDICT_GZ_URL` | EDRDG 官方地址 | `setup_data.py` 的下载源 |
| `SKIP_DOWNLOAD` | 未设置 | 设为 `1` 时跳过下载（已有 XML 时用） |
| `OLLAMA_BASE` | `http://127.0.0.1:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 模型名 |
| `OLLAMA_TIMEOUT` | `120` | 讲解超时（秒） |

---

## 目录结构

```
japanese-learning/
  README.md
  setup_data.py             # 一键数据准备（下载 + 建库 + 导入语法）
  build_db.py               # JMdict XML → SQLite
  start.ps1 / run.bat       # 启动（含端口占用检测）
  jmdict.db                 # setup_data.py 生成（不入库）
  data/                     # 语法 JSON + 分级/释义/例句（gzip JSONL，约 1.4MB）
  scripts/eval_explain.py   # 讲解评测脚本
  docs/screenshots/         # 界面截图
  docs/HANDOFF.md           # 架构与开发交接说明
  web/
    main.py                 # FastAPI 路由
    lookup.py               # 查词 / 语法 / 例句查询
    mock_exam.py            # 本地模考
    weakness.py             # 薄弱点分析
    ai_ollama.py            # 本地讲解
    db.py                   # 只读连接
    data/mock_exams/        # 示例卷 JSON
    static/                 # 前端（原生 JS，无构建）
    cache/                  # 运行期缓存
```

---

## 常见问题

**端口 8765 被占用**
`start.ps1` 会自动检测并改用 8766 起，提示里会给出实际地址。也可以手动指定：
```powershell
cd web
.\.venv\Scripts\uvicorn.exe main:app --port 9000
```

**页面显示「词典库未就绪」**
没找到 `jmdict.db`。跑 `python setup_data.py`，或把已有的 `jmdict.db` 放到项目根目录，然后重启。

**「本地讲解」按钮点了报错**
Ollama 没启动，或没有对应模型。先 `ollama serve`，再 `ollama pull qwen2.5:7b`。页面会提示「本机 Ollama 未响应」。

**装依赖很慢**
首次 `start.ps1` 会装 fastapi + uvicorn 等 19 个包。可以换国内镜像：
```powershell
.\.venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 数据来源与协议

- **JMdict / EDICT**：EDRDG，[CC-BY-SA 4.0](https://www.edrdg.org/) — `setup_data.py` 自动下载
- **开放语法参考**：`data/openjlpt_grammar_*.json`
- **模考题目**：本仓库自建的示例内容，仅供演示

代码可用于作品集展示；词库数据请遵守上游协议，勿二次商用分发未授权内容。

## License

代码部分可按作品集用途使用。词典数据版权归原作者 / EDRDG。
