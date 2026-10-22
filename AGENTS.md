# AGENTS.md

给 AI 编码工具（Cursor / Codex / Copilot 等）的项目说明。

**详细规则在 `.cursor/rules/`**，Cursor 会自动加载；其他工具请手动读这四份：

| 文件 | 内容 |
|---|---|
| `.cursor/rules/core.mdc` | 项目结构、禁区、验证方式、编码坑 |
| `.cursor/rules/python-backend.mdc` | SQL 性能红线、错误语义、降级路径 |
| `.cursor/rules/frontend.mdc` | 单文件 SPA、XSS 白名单、状态管理 |
| `.cursor/rules/data.mdc` | 建库流程、数据来源与许可、覆盖率 |

## 30 秒速览

本地优先的日语学习工具。FastAPI + 原生 JS（无构建）+ SQLite + 可选 Ollama。

```
web/main.py       路由 + 安全中间件
web/lookup.py     所有 SQL
web/mock_exam.py  本地卷子读写
web/weakness.py   练习日志统计
conjugator.py     活用生成（纯函数）
setup_data.py     一键建库
tests/            单元测试 + 接口回归
```

## 三条硬约束

1. **不提交大文件**：`jmdict.db`(80MB)、`JMdict_e.xml`(60MB)、`web/cache/imported_exams/`
2. **不删索引**：`idx_word_forms_seq`——删了 `/api/jlpt` 从 47ms 变 16 秒
3. **改完跑测试**：`python tests/test_units.py` 和 `.\run_tests.ps1`，都要 0 fail

## 两个副本

私有版 `<自用版目录>`（端口 8765，在线真题（自用版））
公开版 本仓库（端口 8766，本地示例卷）

默认改公开版。私有版和它已经分叉，别互相覆盖。

## 做什么之前先看

`docs/CURSOR-TASKS.md`——待办清单 + 沟通话术，避免重复劳动和顺手重构。
