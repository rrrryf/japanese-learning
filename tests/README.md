# 测试

无第三方依赖（只用 Python 标准库），不引入 pytest。

## 怎么跑

在项目根目录：

```powershell
.\run_tests.ps1              # 起服务 -> 跑测试 -> 停服务
.\run_tests.ps1 -WithAi      # 额外测一次 Ollama 讲解（需要本机模型）
.\run_tests.ps1 -Port 9100   # 指定端口
.\run_tests.ps1 -KeepRunning # 测完不关服务
```

脚本会：
1. 检查 `web\.venv` 和 `jmdict.db`（缺了会提示先跑 `start.ps1` / `setup_data.py`）
2. 挑一个空闲端口启动 uvicorn
3. 等 `/api/jlpt/counts` 有响应（200 或 503 都算就绪）
4. 跑 `tests/test_api.py`
5. 停服务，返回测试退出码

也可以手动针对已在跑的服务测试：

```powershell
.\.venv\Scripts\python.exe tests\test_api.py --base http://127.0.0.1:8765
```

## 覆盖范围

| 组 | 内容 | 项数 |
|---|---|---|
| A | 输入边界：空值、超长、控制字符、emoji、RTL、中文/日文查询 | 11 |
| B | 参数类型与范围：limit/seq/gid 的负数、越界、超 int64、非数字 | 17 |
| C | 注入尝试：SQLi 4 种、路径穿越 3 种 | 7 |
| D | 协议误用与 CSRF：方法错用、非法 JSON、超大 body、Content-Type 强制 | 12 |
| E | Host 校验（DNS rebinding）：非回环 Host 应 400 | 4 |
| F | 安全响应头：CSP / X-Frame-Options / nosniff / Referrer-Policy | 4 |
| G | 并发：search×50、jlpt×20、word×30、grammar×50，要求 0 错误 | 4 |
| H | 已移除端点、无效路由、核心路径 | 3 |
| I | 本地 AI（仅 `-WithAi`）：状态 + 一次真实讲解 | 1–2 |

全部通过时退出码为 0。

## 加新用例

`tests/test_api.py` 里用两个辅助函数：

```python
expect("用例名", 期望状态或状态集合, "/api/path", method="POST", body=b"{}", ctype="application/json")

# 需要自己看响应体时用 req()
st, body, ms, headers = req("/api/search?q=test")
```

`rec("PASS"/"FAIL"/"WARN"/"SKIP", 名称, 说明)` 负责记录与打印，末尾自动汇总。

## 注意

- 测试会**写一条练习日志**（`web/cache/exam-logs/`），属预期行为
- `-WithAi` 会真实调用 Ollama，7B 模型单次约 6–10 秒
- 测试只读词典数据，不会修改 `jmdict.db`
